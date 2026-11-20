import re

from django.db import migrations

# A frozen copy of apps.portal.models.class_sort_key and its patterns.


def padded(value):
    return re.sub(r"\d+", lambda m: m.group().zfill(10), (value or "").strip().lower())[:200]


WORD_START = r"(?<![a-z0-9])"
PRE_PRIMARY = re.compile(WORD_START + r"(play|pg(?![a-z])|pp(?![a-z])|pre[\s.-]*(nur|kg|primary|school)|prep|nur|"
                         r"toddler|lkg|ukg|(jr|sr)kg|kg)")
CLASS_WORD = re.compile(WORD_START + r"(class|cls|std|standard|grade|gr)(?![a-z])\.?")
CLASS_NUMBER = re.compile(r"(?:(?<![a-z0-9])|(?<=class)|(?<=cls)|(?<=std)|(?<=standard)|(?<=grade)|(?<=gr))"
                          r"(\d+)(?!\d)")
ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii")
CLASS_ROMAN = re.compile(WORD_START + r"(xii|xi|ix|x|viii|vii|vi|iv|v|iii|ii|i)(?![a-z])")


def _letters(value: str) -> str:
    """Only letters and (padded) numbers: "UKG-A", "UKG A" and "UKGA" sort together."""
    return re.sub(r"[^a-z0-9]+", "", padded(value))


def _class_number(value: str) -> tuple[int | None, str]:
    """The class number in a lower-cased name (1 to 12 first, else any
    number), and the name without it or words like "Class"."""
    numbers = list(CLASS_NUMBER.finditer(value))
    match = next((m for m in numbers if 1 <= int(m.group(1)) <= 12), numbers[0] if numbers else None)
    if match is not None:
        number = int(match.group(1))
    elif match := CLASS_ROMAN.search(value):
        number = ROMAN.index(match.group(1)) + 1
    else:
        return None, value
    return number, CLASS_WORD.sub(" ", value[:match.start()] + " " + value[match.end():])


def class_sort_key(name: str) -> str:
    value = (name or "").strip().lower()
    pre_primary = PRE_PRIMARY.search(value)
    number, rest = (None, value) if pre_primary else _class_number(value)
    if number is None:
        # From the pre-primary word on, so a school code before it ("G43 Lkga") doesn't count.
        return f"0{_letters(value[pre_primary.start():] if pre_primary else value)} {padded(value)}"[:200]
    return f"1{number:010d}{_letters(rest)} {padded(value)}"[:200]


def refill_class_keys(apps, schema_editor):
    SchoolClass = apps.get_model("portal", "SchoolClass")
    classes = list(SchoolClass.objects.only("pk", "name"))
    for cls in classes:
        cls.sort_key = class_sort_key(cls.name)
    SchoolClass.objects.bulk_update(classes, ["sort_key"], batch_size=500)


class Migration(migrations.Migration):
    """Recomputes the hidden class sort key of every class for the new order:
    classes without a number first, alphabetically (KG, LKG, NUR, UKG-A),
    then by class number and the rest of the name (1A … 12C). Only that key changes; no row is added or removed."""

    dependencies = [("portal", "0017_portal_watermarks_gallery_size")]

    operations = [migrations.RunPython(refill_class_keys, migrations.RunPython.noop)]
