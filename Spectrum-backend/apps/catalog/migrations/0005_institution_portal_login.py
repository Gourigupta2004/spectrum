from django.db import migrations, models


class Migration(migrations.Migration):
    """Portal sign-in columns on the institution. Filled from the old portal
    logins by portal.0006, before that table is dropped."""

    dependencies = [
        ("catalog", "0004_eventphoto_all_photos"),
    ]

    operations = [
        migrations.AddField(
            model_name="institution",
            name="portal_username",
            field=models.CharField(blank=True, help_text='What the institution types to sign in to the portal, e.g. "dps-newdelhi".', max_length=150, null=True, unique=True, verbose_name="portal username"),
        ),
        migrations.AddField(
            model_name="institution",
            name="portal_password",
            field=models.CharField(blank=True, editable=False, max_length=128, verbose_name="portal password"),
        ),
        migrations.AddField(
            model_name="institution",
            name="portal_token_version",
            field=models.PositiveIntegerField(default=1, editable=False),
        ),
    ]
