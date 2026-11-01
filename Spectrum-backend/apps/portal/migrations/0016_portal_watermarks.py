from django.db import migrations


def queue_watermarks(apps, schema_editor):
    """Photos already on the portal get their watermark ("Preview" on
    individual photographs; For Title / For Approval / Submitted on class
    photographs). Only background jobs are queued: no row changes here, and
    each photo stays listed, unmarked, until its job has run."""
    Task = apps.get_model("core", "Task")
    for model, label in (("CaptionItem", "portal.captionitem"), ("Student", "portal.student")):
        pks = apps.get_model("portal", model).objects.filter(image_status="ready").values_list("pk", flat=True)
        Task.objects.bulk_create((Task(name="core.refresh_watermark", args=[label, pk]) for pk in pks),
                                 batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0015_class_edit_window"),
        ("core", "0003_upload_file_created"),
    ]

    operations = [migrations.RunPython(queue_watermarks, migrations.RunPython.noop)]
