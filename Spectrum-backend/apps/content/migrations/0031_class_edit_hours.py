import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """Site settings get the hours a class stays open after its first Submit
    (it was fixed at 48). Adds one column; nothing else changes."""

    dependencies = [
        ("content", "0030_checkout_charges"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="class_edit_hours",
            field=models.PositiveSmallIntegerField(
                default=48,
                help_text="After a teacher's first Submit on a class, how many hours they have to name the rest, "
                          "add absentees and comment, before the class locks by itself. A change applies to "
                          "classes still open too: their time counts from their first Submit.",
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(720)],
                verbose_name="hours to finish a class"),
        ),
    ]
