"""
Moves every portal login onto where it now lives, before portal.0007 drops
the Member ("Portal logins") table:

  * an institution login -> its username and password hash are copied onto the
    Institution (the hash as-is, so the current password keeps working); the
    login's own User row, which could only ever open the portal, is removed;
  * a Spectrum team login -> its User keeps everything and is given the
    "Spectrum team portal access" permission (shown in the Users table).

An institution now has one sign-in. If one had several logins, its oldest
moves onto the institution and the others' User rows are left untouched in
the Users table (listed in the migrate output), so nothing is lost. Reversing
rebuilds the Member rows (and the removed User rows) from the institutions.
"""

from collections import defaultdict

from django.conf import settings
from django.db import migrations

CODENAME = "spectrum_portal_access"
PERMISSION_NAME = "Can sign in to the institution portal as the Spectrum team"


def _permission(apps):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type, _ = ContentType.objects.get_or_create(app_label="portal", model="captionworkspace")
    permission, _ = Permission.objects.get_or_create(content_type=content_type, codename=CODENAME,
                                                     defaults={"name": PERMISSION_NAME})
    return permission


def move_logins(apps, schema_editor):
    Member = apps.get_model("portal", "Member")
    Institution = apps.get_model("catalog", "Institution")

    by_institution = defaultdict(list)
    for member in Member.objects.filter(role="institution").exclude(institution=None).select_related("user", "institution").order_by("pk"):
        by_institution[member.institution_id].append(member)

    for logins in by_institution.values():
        if len(logins) > 1:
            extra = ", ".join(m.user.username for m in logins[1:])
            print(f"\n  {logins[0].institution.name}: portal sign-in is now {logins[0].user.username!r}; "
                  f"its other login(s) {extra} were kept as Users but no longer open the portal.")

    for logins in by_institution.values():
        member = logins[0]
        Institution.objects.filter(pk=member.institution_id).update(
            portal_username=member.user.username,
            portal_password=member.user.password,  # the hash itself: same password, nothing re-typed
            portal_token_version=member.token_version,
        )

    spectrum = list(Member.objects.filter(role="spectrum").select_related("user"))
    if spectrum:
        permission = _permission(apps)
        for member in spectrum:
            user = member.user
            user.user_permissions.add(permission)
            if member.display_name and not (user.first_name or user.last_name):
                user.first_name = member.display_name[:150]
                user.save(update_fields=["first_name"])

    # An institution login's User could only open the portal; its username and
    # password now live on the institution. Users that are also admin users
    # (staff or superuser) are left alone. Institution-role logins linked to no
    # institution (which could never open anything) keep their User too.
    # Only the login that moved is removed; extra logins of the same
    # institution keep their User rows.
    moved = [logins[0].user_id for logins in by_institution.values()
             if not (logins[0].user.is_staff or logins[0].user.is_superuser)]
    Member.objects.filter(user_id__in=moved).delete()
    apps.get_model(settings.AUTH_USER_MODEL).objects.filter(pk__in=moved).delete()


def restore_logins(apps, schema_editor):
    Member = apps.get_model("portal", "Member")
    Institution = apps.get_model("catalog", "Institution")
    User = apps.get_model(settings.AUTH_USER_MODEL)

    for institution in Institution.objects.exclude(portal_username=None).exclude(portal_username=""):
        user = User.objects.filter(username=institution.portal_username).first()
        if user is None:
            user = User.objects.create(username=institution.portal_username, password=institution.portal_password,
                                       is_staff=False)
        if not Member.objects.filter(user=user).exists():
            Member.objects.create(user=user, institution=institution, role="institution",
                                  display_name=institution.name, token_version=institution.portal_token_version)

    Permission = apps.get_model("auth", "Permission")
    permission = Permission.objects.filter(content_type__app_label="portal", codename=CODENAME).first()
    if permission is not None:
        for user in User.objects.filter(user_permissions=permission):
            if not Member.objects.filter(user=user).exists():
                Member.objects.create(user=user, role="spectrum",
                                      display_name=(f"{user.first_name} {user.last_name}".strip() or user.username)[:120])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0005_caption_item_class_photograph"),
        ("catalog", "0005_institution_portal_login"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="captionworkspace",
            options={
                "ordering": ["institution__name"],
                "permissions": [(CODENAME, PERMISSION_NAME)],
                "verbose_name": "institution workspace",
            },
        ),
        migrations.RunPython(move_logins, restore_logins),
    ]
