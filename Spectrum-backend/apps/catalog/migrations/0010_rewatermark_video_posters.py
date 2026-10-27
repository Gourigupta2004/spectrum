from django.db import migrations


def requeue_posters(apps, schema_editor):
    """Video posters made before they had their own watermark get re-made
    with "Video preview not available"; each keeps showing until then."""
    EventVideo = apps.get_model("catalog", "EventVideo")
    Task = apps.get_model("core", "Task")
    Task.objects.bulk_create(
        Task(name="core.process_image", args=["catalog.eventvideo", pk])
        for pk in EventVideo.objects.exclude(original="").values_list("pk", flat=True)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_recent_is_automatic"),
        ("core", "0003_upload_file_created"),
    ]

    operations = [migrations.RunPython(requeue_posters, migrations.RunPython.noop)]
