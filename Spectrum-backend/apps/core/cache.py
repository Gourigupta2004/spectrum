"""
Versioned response cache.

Public payloads are serialised once and stored as bytes. Any save or delete of a
model that feeds them bumps the namespace version, so stale entries are simply
never read again and expire on their own. No key scanning, no Redis needed.
"""

import json
import time

from django.core.cache import cache

PUBLIC = "public"

# Models whose changes invalidate the public API cache.
PUBLIC_APPS = {"content", "catalog"}
NOT_PUBLIC = {"enquiry"}


def _version(namespace: str) -> int:
    version = cache.get(f"v:{namespace}")
    if version is None:
        # A fresh timestamp, never a small counter: if the key is ever evicted, old
        # entries can't be mistaken for current ones.
        version = time.time_ns()
        cache.set(f"v:{namespace}", version, None)
    return version


def bump(namespace: str = PUBLIC) -> None:
    cache.set(f"v:{namespace}", time.time_ns(), None)


def bump_for(model) -> None:
    meta = getattr(model, "_meta", None)
    if meta is not None and meta.app_label in PUBLIC_APPS and meta.model_name not in NOT_PUBLIC:
        bump(PUBLIC)


def cached_bytes(key: str, builder, namespace: str = PUBLIC, timeout: int = 24 * 3600) -> bytes:
    full_key = f"{namespace}:{_version(namespace)}:{key}"
    body = cache.get(full_key)
    if body is None:
        body = dumps(builder())
        cache.set(full_key, body, timeout)
    return body


def dumps(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
