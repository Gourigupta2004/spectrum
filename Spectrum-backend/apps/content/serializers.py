"""Turns page singletons into camelCase dicts without hand-listing every field."""

from functools import lru_cache

from django.db import models

SEO_FIELDS = {"seo_title", "seo_description", "og_title", "og_description"}


def camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


@lru_cache(maxsize=None)
def _text_fields(model) -> tuple[tuple[str, str], ...]:
    return tuple(
        (field.attname, camel(field.name))
        for field in model._meta.concrete_fields
        if isinstance(field, (models.CharField, models.TextField)) and field.name not in SEO_FIELDS
    )


def copy_of(obj) -> dict:
    return {key: getattr(obj, attname) for attname, key in _text_fields(type(obj))}
