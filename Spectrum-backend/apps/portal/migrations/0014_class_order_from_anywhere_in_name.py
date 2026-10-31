import re

from django.db import migrations

# A frozen copy of apps.portal.models.class_sort_key and its patterns.
WORD_START = r"(?<![a-z0-9])"
PRE_PRIMARY = tuple(re.compile(WORD_START + pattern) for pattern in (
    r"play\s*(group|school)|pg(?![a-z])",
    r"pre[\s.-]*(nur|kg)",
    r"nur",
    r"lkg|(jr|junior)\.?\s*kg",
    r"ukg|(sr|senior)\.?\s*kg",
    r"kg",
))
CLASS_NUMBER = re.compile(WORD_START + r"(\d{1,2})(?!\d)")
ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii")
CLASS_ROMAN = re.compile(WORD_START + r"(xii|xi|ix|x|viii|vii|vi|iv|v|iii|ii|i)(?![a-z])")


def padded(value):
    return re.sub(r"\d+", lambda m: m.group().zfill(10), (value or "").strip().lower())[:200]


def class_sort_key(name):
    value = (name or "").strip().lower()
    for rank, pattern in enumerate(PRE_PRIMARY):
        if pattern.search(value):
            return f"0{rank}{padded(value)}"[:200]
    number = next((int(m.group(1)) for m in CLASS_NUMBER.finditer(value) if 1 <= int(m.group(1)) <= 12), None)
    if number is None and (roman := CLASS_ROMAN.search(value)):
        number = ROMAN.index(roman.group(1)) + 1
    if number is not None:
        return f"1{number:02d}{padded(value)}"[:200]
    return f"2{padded(value)}"[:200]


def refill_class_keys(apps, schema_editor):
    SchoolClass = apps.get_model("portal", "SchoolClass")
    classes = list(SchoolClass.objects.only("pk", "name"))
    for cls in classes:
        cls.sort_key = class_sort_key(cls.name)
    SchoolClass.objects.bulk_update(classes, ["sort_key"], batch_size=500)


class Migration(migrations.Migration):
    """Recomputes each class's hidden sort key so "NUR-B", "G43 Lkga" and the
    like sort in school order. Only that key changes; no row is added or removed."""

    dependencies = [("portal", "0013_readable_portal_passwords")]

    operations = [migrations.RunPython(refill_class_keys, migrations.RunPython.noop)]
