"""
Portal sign-in and stateless tokens signed with SECRET_KEY (django.core.signing).

Two kinds of login reach the portal:
  * an institution, with the portal username and password kept on its
    Institution row — it sees only its own workspace;
  * a Spectrum team member, with their own admin username and password, when
    their User holds the "Spectrum team portal access" permission (or is a
    superuser) — they may open every institution.

Access tokens live 30 minutes, refresh tokens 14 days. Bumping
Institution.portal_token_version (admin action "Sign out of the portal
everywhere", or a new password) invalidates every token for that institution;
a Spectrum member's tokens end when their password changes, they are made
inactive or lose the permission.
"""

import time
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.utils.crypto import salted_hmac

from apps.catalog.models import Institution
from apps.core.http import ApiError

from .models import SPECTRUM_PORTAL_PERM

ACCESS_SALT = "portal.access"
REFRESH_SALT = "portal.refresh"
INSTITUTION, SPECTRUM = "institution", "spectrum"


@dataclass
class PortalLogin:
    """Who is signed in to the portal: an institution, or a Spectrum team user."""

    role: str
    pk: int
    version: str
    login_id: str
    display_name: str
    institution: Institution | None

    @property
    def is_spectrum(self) -> bool:
        return self.role == SPECTRUM

    @property
    def id(self) -> str:
        # Unique across both kinds; the website keys its caches on it.
        return f"{self.role[0]}{self.pk}"

    @classmethod
    def for_institution(cls, institution: Institution) -> "PortalLogin":
        return cls(INSTITUTION, institution.pk, str(institution.portal_token_version), institution.portal_username,
                   institution.name, institution)

    @classmethod
    def for_user(cls, user) -> "PortalLogin":
        return cls(SPECTRUM, user.pk, _user_version(user), user.get_username(),
                   user.get_full_name() or user.get_username(), None)


def _user_version(user) -> str:
    # Derived from the password hash, so a new password ends every session.
    return salted_hmac("portal.user-version", user.password).hexdigest()[:16]


def has_spectrum_access(user) -> bool:
    return bool(user and user.is_active and user.has_perm(SPECTRUM_PORTAL_PERM))


def authenticate_portal(request, username: str, password: str) -> PortalLogin | None:
    username = username.strip()
    # Usernames are matched ignoring letter case (phones capitalise the first
    # letter); an exact match wins if two differ only in case.
    institution = (Institution.objects.filter(portal_username=username).first()
                   or Institution.objects.filter(portal_username__iexact=username).first())
    if institution is not None and institution.check_portal_password(password):
        return PortalLogin.for_institution(institution)
    user = authenticate(request, username=username, password=password)  # Spectrum team
    if has_spectrum_access(user):
        return PortalLogin.for_user(user)
    return None


def issue_tokens(login: PortalLogin, signed_in_at: int | None = None) -> dict:
    # "t" is the original sign-in time; refreshing never extends a session past the refresh TTL.
    payload = {"r": login.role, "id": login.pk, "v": login.version, "t": signed_in_at or int(time.time())}
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


def member_from_token(token: str, salt: str, max_age: int) -> PortalLogin | None:
    payload = read_token(token, salt, max_age)
    if payload is None:
        return None
    role, pk, version = payload.get("r"), payload.get("id"), str(payload.get("v"))
    if role == INSTITUTION:
        institution = Institution.objects.filter(pk=pk).first()
        if institution is None or not institution.has_portal_login:
            return None
        login = PortalLogin.for_institution(institution)
    elif role == SPECTRUM:
        user = get_user_model().objects.filter(pk=pk).first()
        if not has_spectrum_access(user):
            return None
        login = PortalLogin.for_user(user)
    else:  # a token from before logins moved onto institutions: sign in again
        return None
    return login if login.version == version else None


def require_member(request) -> PortalLogin:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError("Please sign in.", status=401)
    member = member_from_token(header[7:], ACCESS_SALT, settings.PORTAL_ACCESS_TTL)
    if member is None:
        raise ApiError("Your session has expired. Please sign in again.", status=401)
    return member
