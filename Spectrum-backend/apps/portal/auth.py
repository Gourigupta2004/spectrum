"""
Portal sign-in and stateless tokens signed with SECRET_KEY (django.core.signing).

Two kinds of login reach the portal:
  * an institution, with the username and password kept on the access email
    the visitor verified (Institution credentials) — it sees only its own
    workspace;
  * a Spectrum team member, with their own admin username and password, when
    their User holds the "Spectrum team portal access" permission (or is a
    superuser) — they may open every institution.

Access tokens live 30 minutes, refresh tokens 14 days. Bumping
PortalAccessEmail.token_version (admin action "Sign out of the portal
everywhere", or a new password) invalidates every token from that sign-in;
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

from .models import SPECTRUM_PORTAL_PERM, PortalAccessEmail

ACCESS_SALT = "portal.access"
REFRESH_SALT = "portal.refresh"
INSTITUTION, SPECTRUM = "institution", "spectrum"
# The token's marker for an access-email sign-in. Not "institution": tokens
# from when the sign-in lived on the Institution carried that marker with an
# institution id, which must never be read as an access-email id.
ACCESS_TOKEN = "access"


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

    @property
    def token_role(self) -> str:
        return ACCESS_TOKEN if self.role == INSTITUTION else SPECTRUM

    @classmethod
    def for_access(cls, row: PortalAccessEmail) -> "PortalLogin":
        return cls(INSTITUTION, row.pk, str(row.token_version), row.username, row.institution.name, row.institution)

    @classmethod
    def for_user(cls, user) -> "PortalLogin":
        return cls(SPECTRUM, user.pk, _user_version(user), user.get_username(),
                   user.get_full_name() or user.get_username(), None)


def _user_version(user) -> str:
    # Derived from the password hash, so a new password ends every session.
    return salted_hmac("portal.user-version", user.password).hexdigest()[:16]


def has_spectrum_access(user) -> bool:
    return bool(user and user.is_active and user.has_perm(SPECTRUM_PORTAL_PERM))


def authenticate_portal(request, username: str, password: str, email: str = "") -> PortalLogin | None:
    """
    The sign-in for these credentials. With the verified email (the website
    always sends it) only that email's own username and password count;
    without one, any access email with this username. Usernames ignore letter
    case (phones capitalise the first letter).
    """
    username = username.strip()
    rows = PortalAccessEmail.objects.select_related("institution").exclude(username="").exclude(password="")
    rows = rows.filter(email=email) if email else rows.filter(username__iexact=username).order_by("pk")
    for row in rows:
        if row.username.lower() == username.lower() and row.check_password(password):
            return PortalLogin.for_access(row)
    user = authenticate(request, username=username, password=password)  # Spectrum team
    if has_spectrum_access(user):
        return PortalLogin.for_user(user)
    return None


def issue_tokens(login: PortalLogin, signed_in_at: int | None = None) -> dict:
    # "t" is the original sign-in time; refreshing never extends a session past the refresh TTL.
    payload = {"r": login.token_role, "id": login.pk, "v": login.version, "t": signed_in_at or int(time.time())}
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
    if role == ACCESS_TOKEN:
        row = PortalAccessEmail.objects.select_related("institution").filter(pk=pk).first()
        if row is None or not row.has_login:
            return None
        login = PortalLogin.for_access(row)
    elif role == SPECTRUM:
        user = get_user_model().objects.filter(pk=pk).first()
        if not has_spectrum_access(user):
            return None
        login = PortalLogin.for_user(user)
    else:  # a token from an older sign-in scheme: sign in again
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
