from django.db import migrations


class Migration(migrations.Migration):
    """The Schools/Colleges filter chips now take their labels from the catalog's
    institution types, so the events page no longer carries its own copy of them."""

    dependencies = [
        ('content', '0008_stat_live_counts_portal_nav'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='eventspage',
            name='filter_schools',
        ),
        migrations.RemoveField(
            model_name='eventspage',
            name='filter_colleges',
        ),
    ]
