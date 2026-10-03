from django.db import migrations, models


def wire_up_defaults(apps, schema_editor):
    """
    The portal link moves from the footer to the navbar, so relabel a nav_portal
    the admin has not touched. Stats keep their saved numbers; the ones still
    carrying the seeded labels get the matching live count switched on.
    """
    SiteSettings = apps.get_model("content", "SiteSettings")
    SiteSettings.objects.filter(nav_portal="Institution").update(nav_portal="Institution Portal")

    Stat = apps.get_model("content", "Stat")
    for label, source in [("Events Captured", "events"), ("Schools & Colleges", "institutions"),
                          ("Photos Delivered", "photos")]:
        Stat.objects.filter(label=label, source="").update(source=source)

    # update() skips the save signals that invalidate the public API cache; bump it by hand
    # so the home payload is rebuilt with the new labels and live counts right away.
    from apps.core.cache import bump
    bump()


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0007_workspace_subtitle'),
    ]

    operations = [
        migrations.AddField(
            model_name='stat',
            name='source',
            field=models.CharField(blank=True, choices=[('', 'Nothing — show the number as is'),
                                                        ('events', 'Published events'),
                                                        ('institutions', 'Published institutions'),
                                                        ('photos', 'Photos delivered (paid orders)')],
                                   default='', help_text='The number grows by itself as the platform delivers more.',
                                   max_length=12, verbose_name='add live count of'),
        ),
        migrations.AlterField(
            model_name='stat',
            name='value',
            field=models.PositiveIntegerField(help_text='Base number. The live count, if chosen, is added on top.'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='nav_portal',
            field=models.CharField(blank=True, default='Institution Portal',
                                   help_text='Navbar link to the institution portal.', max_length=40),
        ),
        migrations.RemoveField(
            model_name='sitesettings',
            name='footer_portal_link',
        ),
        migrations.RunPython(wire_up_defaults, migrations.RunPython.noop),
    ]
