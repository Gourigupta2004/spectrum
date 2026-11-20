import django.core.validators
from django.db import migrations, models


def copy_hours(apps, schema_editor):
    """Keeps whatever was set in Site settings."""
    site = apps.get_model("content", "SiteSettings").objects.filter(pk=1).first()
    if site is not None:
        PortalPage = apps.get_model("content", "PortalPage")
        PortalPage.objects.update_or_create(pk=1, defaults={"class_edit_hours": site.class_edit_hours})


def copy_back(apps, schema_editor):
    page = apps.get_model("content", "PortalPage").objects.filter(pk=1).first()
    if page is not None:
        apps.get_model("content", "SiteSettings").objects.filter(pk=1).update(class_edit_hours=page.class_edit_hours)


class Migration(migrations.Migration):
    """The hours a class stays open after its first Submit move from Site
    settings to Institution portal pages, as "Individual photos TTL". The
    value set so far is carried over; nothing else changes."""

    dependencies = [
        ("content", "0031_class_edit_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalpage",
            name="class_edit_hours",
            field=models.PositiveSmallIntegerField(
                default=48,
                help_text="In hours. After a teacher's first Submit on a class, how long they have to name the "
                          "rest, add absentees and comment, before the class locks by itself. A change applies to "
                          "classes still open too: their time counts from their first Submit.",
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(720)],
                verbose_name="Individual photos TTL"),
        ),
        migrations.RunPython(copy_hours, copy_back),
        migrations.RemoveField(model_name="sitesettings", name="class_edit_hours"),
    ]
