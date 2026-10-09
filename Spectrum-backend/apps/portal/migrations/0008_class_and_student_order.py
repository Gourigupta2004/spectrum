import re

from django.db import migrations, models

PRE_PRIMARY = ("play group", "playgroup", "pre-nursery", "pre nursery", "nursery", "lkg", "ukg", "kg")
CLASS_PREFIX = re.compile(r"^(class|grade|std\.?|standard)\s*", re.I)


def padded(value):
    return re.sub(r"\d+", lambda m: m.group().zfill(10), (value or "").strip().lower())[:200]


def class_sort_key(name):
    # A frozen copy of apps.portal.models.class_sort_key.
    value = CLASS_PREFIX.sub("", (name or "").strip().lower())
    for rank, word in enumerate(PRE_PRIMARY):
        if value.startswith(word):
            return f"0{min(rank, 6):02d}{padded(value)}"
    return f"{1 if value[:1].isdigit() else 2}{padded(value)}"[:200]


def fill_class_keys(apps, schema_editor):
    SchoolClass = apps.get_model("portal", "SchoolClass")
    classes = list(SchoolClass.objects.only("pk", "name"))
    for cls in classes:
        cls.sort_key = class_sort_key(cls.name)
    SchoolClass.objects.bulk_update(classes, ["sort_key"], batch_size=500)
    # Students uploaded so far have no file name on record; they keep their
    # upload order (sort_order) under an empty key.


class Migration(migrations.Migration):
    """Classes in school order and photos in file-name order; admin renames.
    Only adds columns and widens two; no existing value changes."""

    dependencies = [
        ("portal", "0007_delete_member"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="portalaccessemail",
            options={"ordering": ["institution__name", "email"], "verbose_name": "institution credential",
                     "verbose_name_plural": "institution credentials"},
        ),
        migrations.AlterModelOptions(
            name="schoolclass",
            options={"ordering": ["institution", "sort_key", "pk"], "verbose_name": "class",
                     "verbose_name_plural": "all classes"},
        ),
        migrations.AlterModelOptions(
            name="student",
            options={"ordering": ["sort_key", "sort_order", "pk"]},
        ),
        migrations.AlterField(
            model_name="schoolclass",
            name="name",
            field=models.CharField(help_text='e.g. "6C" or "Nursery". Uploaded folders become classes of the same name.', max_length=60),
        ),
        migrations.AlterField(
            model_name="schoolclass",
            name="slug",
            field=models.SlugField(blank=True, help_text="Filled from the name.", max_length=70),
        ),
        migrations.AddField(
            model_name="schoolclass",
            name="sort_key",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=200),
        ),
        migrations.AddField(
            model_name="student",
            name="source_name",
            field=models.CharField(blank=True, editable=False, max_length=200, verbose_name="file name"),
        ),
        migrations.AddField(
            model_name="student",
            name="sort_key",
            field=models.CharField(blank=True, editable=False, max_length=200),
        ),
        migrations.AddIndex(
            model_name="student",
            index=models.Index(fields=["school_class", "sort_key"], name="portal_stud_class_sortkey"),
        ),
        migrations.RunPython(fill_class_keys, migrations.RunPython.noop),
    ]
