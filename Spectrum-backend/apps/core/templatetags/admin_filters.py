"""The filters a changelist currently applies, shown as chips beside its search bar."""

import datetime

from django import template
from django.contrib.admin.views.main import PAGE_VAR, SEARCH_VAR
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.utils.formats import date_format

register = template.Library()


def _without(cl, params) -> str:
    # Exact keys (get_query_string's `remove` matches prefixes); back to page 1.
    return cl.get_query_string({**{param: None for param in params}, PAGE_VAR: None})


def _date_label(params, field) -> str:
    year, month, day = (params.get(f"{field}__{part}", [None])[-1] for part in ("year", "month", "day"))
    try:
        if day:
            return date_format(datetime.date(int(year), int(month), int(day)), "j F Y")
        if month:
            return date_format(datetime.date(int(year), int(month), 1), "F Y")
    except (TypeError, ValueError):
        pass
    return str(year or "")


def _field_title(model, param: str) -> str:
    """'date__year' -> 'date'; falls back to the raw name."""
    try:
        return str(model._meta.get_field(param.split("__")[0]).verbose_name)
    except FieldDoesNotExist:
        return param.split("__")[0].replace("_", " ")


LOOKUP_ENDINGS = {"exact", "id", "pk", "in"}


def _lookup_chip(model, param: str, values) -> tuple[str, str]:
    """A lookup that came in a link: 'school_class__institution__id__exact=5'
    reads as ('institution', 'Delhi Public School'), naming the related row."""
    parts = param.split("__")
    while len(parts) > 1 and parts[-1] in LOOKUP_ENDINGS:
        parts.pop()
    current, field = model, None
    try:
        for name in parts:
            field = current._meta.get_field(name)
            current = field.related_model or current
    except FieldDoesNotExist:
        return _field_title(model, param), ", ".join(map(str, values))
    if field is not None and field.is_relation and field.related_model is not None:
        ids = [v for value in values for v in str(value).split(",") if v]
        try:
            names = [str(obj) for obj in field.related_model._default_manager.filter(pk__in=ids)]
        except (ValueError, ValidationError):  # a hand-edited URL with a malformed id
            names = []
        if names:
            return str(field.verbose_name), ", ".join(names)
    return str(getattr(field, "verbose_name", parts[-1])), ", ".join(map(str, values))


@register.inclusion_tag("admin/core/active_filters.html")
def active_filters(cl):
    applied = cl.get_filters_params()
    chips, covered = [], set()

    for spec in cl.filter_specs:
        params = [p for p in spec.expected_parameters() if p]
        covered.update(params)
        active = [p for p in params if p in applied]
        if not active:
            continue
        labels = [str(choice["display"]) for choice in spec.choices(cl)
                  if choice.get("selected") and choice.get("query_string") != _without(cl, params)]
        value = ", ".join(labels) or ", ".join(str(v) for p in active for v in applied[p])
        chips.append({"title": spec.title, "value": value, "url": _without(cl, params)})

    if cl.date_hierarchy:
        params = [f"{cl.date_hierarchy}__{part}" for part in ("year", "month", "day")]
        covered.update(params)
        if any(p in applied for p in params):
            chips.append({"title": _field_title(cl.model, cl.date_hierarchy),
                          "value": _date_label(applied, cl.date_hierarchy), "url": _without(cl, params)})

    # Lookups that came in a link (e.g. "see all of this class") with no
    # sidebar filter of their own.
    for param, values in applied.items():
        if param not in covered:
            title, value = _lookup_chip(cl.model, param, values)
            chips.append({"title": title, "value": value, "url": _without(cl, [param])})

    if cl.query:
        chips.insert(0, {"title": "Search", "value": f"“{cl.query}”", "url": _without(cl, [SEARCH_VAR])})

    return {
        "chips": chips,
        "clear_url": _without(cl, [*applied, SEARCH_VAR]) if len(chips) > 1 else "",
    }
