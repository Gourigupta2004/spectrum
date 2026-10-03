from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .cache import bump_for
from .models import ImageStatus, ProcessedImage


def _private_fields(instance) -> list[str]:
    return ["original", *getattr(instance, "EXTRA_PRIVATE_FILES", ())]


def _file_fields(instance) -> list[str]:
    return [*_private_fields(instance), *instance.variant_names()]


@receiver(pre_delete)
def collect_image_files(sender, instance, **kwargs):
    if not isinstance(instance, ProcessedImage):
        return
    fields = _file_fields(instance)
    if instance.get_deferred_fields() & set(fields):
        # The admin may have loaded the row with only(); read the real names.
        row = type(instance).objects.filter(pk=instance.pk).values(*fields).first() or {}
    else:
        row = {name: str(instance.__dict__.get(name) or "") for name in fields}
    instance._files_to_delete = row


@receiver(post_delete)
def remove_image_files(sender, instance, **kwargs):
    row = getattr(instance, "_files_to_delete", None)
    if not row:
        return
    from .tasks import enqueue

    private_keys = set(_private_fields(instance))
    private = [name for key, name in row.items() if key in private_keys and name]
    public = [name for key, name in row.items() if key not in private_keys and name]
    # Deleting from S3 is slow; do it in the worker once the delete has committed.
    if private:
        transaction.on_commit(lambda: enqueue("core.delete_files", "private", private))
    if public:
        transaction.on_commit(lambda: enqueue("core.delete_files", "default", public))


@receiver(post_save)
def invalidate_on_save(sender, instance, created=False, **kwargs):
    # A freshly uploaded photo isn't public until processed; the worker bumps the cache then.
    if created and isinstance(instance, ProcessedImage) and instance.image_status != ImageStatus.READY:
        return
    bump_for(sender)


@receiver(post_delete)
def invalidate_on_delete(sender, **kwargs):
    bump_for(sender)
