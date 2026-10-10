from django.db import migrations


class Migration(migrations.Migration):
    """Drops the institution's portal sign-in columns, copied onto each of its
    access emails by portal.0009 first."""

    dependencies = [
        ("catalog", "0006_institution_kind_named_type"),
        ("portal", "0009_sign_in_on_each_access_email"),
    ]

    operations = [
        migrations.RemoveField(model_name="institution", name="portal_username"),
        migrations.RemoveField(model_name="institution", name="portal_password"),
        migrations.RemoveField(model_name="institution", name="portal_token_version"),
    ]
