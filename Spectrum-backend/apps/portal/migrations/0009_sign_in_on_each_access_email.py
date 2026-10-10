"""
Each access email becomes a full sign-in: email + username + password.

The institution's one username and password hash (moved onto the
Institution by 0006) are copied onto every access email it has, so every
email that could sign in before still signs in with exactly the same
username and password. Only after this does catalog.0007 drop the
institution's columns.

An institution with a username but no access email could not sign in on the
website (the email step comes first); its username is written into its
workspace notes, and named in the migrate output, so it can be given an
email row. Reversing puts each institution's first sign-in back on it.
"""

from django.db import migrations, models


def to_access_emails(apps, schema_editor):
    Institution = apps.get_model("catalog", "Institution")
    PortalAccessEmail = apps.get_model("portal", "PortalAccessEmail")
    CaptionWorkspace = apps.get_model("portal", "CaptionWorkspace")

    for institution in Institution.objects.exclude(portal_username=None).exclude(portal_username=""):
        rows = PortalAccessEmail.objects.filter(institution=institution)
        if rows.exists():
            rows.update(username=institution.portal_username, password=institution.portal_password,
                        token_version=institution.portal_token_version)
            continue
        workspace, _ = CaptionWorkspace.objects.get_or_create(institution=institution)
        line = (f"Portal username {institution.portal_username!r} had no access email when sign-ins moved onto "
                f"emails (Oct 2026): add an email under Institution credentials with this username and its password.")
        workspace.notes = f"{workspace.notes.rstrip()}\n\n{line}".strip()
        workspace.save(update_fields=["notes"])
        print(f"\n  {institution.name}: {line}")


def to_institutions(apps, schema_editor):
    Institution = apps.get_model("catalog", "Institution")
    PortalAccessEmail = apps.get_model("portal", "PortalAccessEmail")

    taken = set()
    for row in PortalAccessEmail.objects.exclude(username="").order_by("institution_id", "pk"):
        if row.institution_id in taken:
            continue
        if Institution.objects.filter(portal_username=row.username).exists():
            print(f"\n  {row.username!r} is already another institution's username; {row.email} not restored.")
            continue
        Institution.objects.filter(pk=row.institution_id).update(
            portal_username=row.username, portal_password=row.password, portal_token_version=row.token_version)
        taken.add(row.institution_id)


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0008_class_and_student_order"),
        ("catalog", "0006_institution_kind_named_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalaccessemail",
            name="username",
            field=models.CharField(blank=True, db_index=True, help_text='What they type to sign in after entering this email, e.g. "dps-newdelhi".', max_length=150),
        ),
        migrations.AddField(
            model_name="portalaccessemail",
            name="password",
            field=models.CharField(blank=True, editable=False, max_length=128),
        ),
        migrations.AddField(
            model_name="portalaccessemail",
            name="token_version",
            field=models.PositiveIntegerField(default=1, editable=False),
        ),
        migrations.RunPython(to_access_emails, to_institutions),
    ]
