from django.db import migrations

LABELS = ("portal.captionitem", "portal.student")


def requeue_watermarks(apps, schema_editor):
    """The portal's marks now use the gallery's letter size, so photos marked
    before are re-marked. Watermark jobs still waiting are replaced rather than
    added to, so no photo is done twice. Only background jobs change here."""
    Task = apps.get_model("core", "Task")
    waiting = Task.objects.filter(name="core.refresh_watermark", status="queued")
    waiting.filter(args__0__in=LABELS).delete()
    for model, label in (("CaptionItem", LABELS[0]), ("Student", LABELS[1])):
        pks = apps.get_model("portal", model).objects.filter(image_status="ready").values_list("pk", flat=True)
        Task.objects.bulk_create((Task(name="core.refresh_watermark", args=[label, pk]) for pk in pks),
                                 batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("portal", "0016_portal_watermarks")]

    operations = [migrations.RunPython(requeue_watermarks, migrations.RunPython.noop)]
