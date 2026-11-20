from django.db import migrations, models


class Migration(migrations.Migration):
    """Orders get "released without payment": set when staff send an unpaid
    order's links by hand, to test. Adds one empty column; nothing else changes."""

    dependencies = [
        ("orders", "0005_checkout_charges"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="released_at",
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name="released without payment"),
        ),
    ]
