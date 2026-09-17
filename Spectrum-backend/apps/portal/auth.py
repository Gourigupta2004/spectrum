"""
Stateless portal tokens signed with SECRET_KEY (django.core.signing).

Access tokens live 30 minutes, refresh tokens 14 days. Bumping Member.token_version
(admin action "Sign out everywhere") invalidates every token for that login.
"""

import time

from django.conf import settings
from django.core import signing

from apps.core.http import ApiError

from .models import Member

ACCESS_SALT = "portal.access"
REFRESH_SALT = "portal.refresh"


def issue_tokens(member: Member, signed_in_at: int | None = None) -> dict:
    # "t" is the original sign-in time; refreshing never extends a session past the refresh TTL.
    payload = {"u": member.user_id, "v": member.token_version, "t": signed_in_at or int(time.time())}
    return {
        "access": signing.dumps(payload, salt=ACCESS_SALT),
        "refresh": signing.dumps(payload, salt=REFRESH_SALT),
        "expiresIn": settings.PORTAL_ACCESS_TTL,
    }


def read_token(token: str, salt: str, max_age: int) -> dict | None:
    try:
        payload = signing.loads(token, salt=salt, max_age=max_age)
    except signing.BadSignature:
        return None
    if time.time() - int(payload.get("t") or 0) > settings.PORTAL_REFRESH_TTL:
        return None
    return payload


def member_from_token(token: str, salt: str, max_age: int) -> Member | None:
    payload = read_token(token, salt, max_age)
    if payload is None:
        return None
    return (
        Member.objects.select_related("user", "institution")
        .filter(user_id=payload.get("u"), token_version=payload.get("v"), user__is_active=True)
        .first()
    )


def require_member(request) -> Member:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError("Please sign in.", status=401)
    member = member_from_token(header[7:], ACCESS_SALT, settings.PORTAL_ACCESS_TTL)
    if member is None:
        raise ApiError("Your session has expired. Please sign in again.", status=401)
    return member
