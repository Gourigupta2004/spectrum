from django.db import migrations


class Migration(migrations.Migration):
    """Drops the Portal logins table, now empty of anything not moved by 0006."""

    dependencies = [
        ("portal", "0006_move_portal_logins_to_institutions"),
    ]

    operations = [
        migrations.DeleteModel(name="Member"),
    ]
