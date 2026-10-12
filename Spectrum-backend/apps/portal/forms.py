from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.html import format_html

from .models import PortalAccessEmail


class AccessEmailForm(forms.ModelForm):
    """
    One institution sign-in: the email, its username and its password. The
    username and password are optional (an email alone unlocks the Portal
    link, but signing in then needs both). The password is shown as it was set,
    so the team can read it out to the institution; editing it sets a new one.
    """

    new_password = forms.CharField(
        label="Password", required=False, strip=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "size": 18, "spellcheck": "false"}),
        help_text="Shown as set. Change it to set a new password (that signs this sign-in out of the portal on "
                  "every device); leave it as it is to keep it.")

    class Meta:
        model = PortalAccessEmail
        fields = ("institution", "email", "username", "new_password", "note")
        widgets = {"username": forms.TextInput(attrs={"size": 18, "autocomplete": "off"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["new_password"]
        field.initial = self.instance.visible_password if self.instance.pk else ""
        if self.instance.pk and self.instance.password and not field.initial:
            # Set before passwords were kept readable: it can only be replaced.
            field.widget.attrs["placeholder"] = "Hidden — type a new one"

    def _password_changed(self) -> bool:
        return "new_password" in self.changed_data and bool(self.cleaned_data.get("new_password"))

    def clean_username(self):
        return (self.cleaned_data.get("username") or "").strip()

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        if password and password != self.fields["new_password"].initial:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        username, password = cleaned.get("username"), cleaned.get("new_password")
        has_password = bool(password or self.instance.password)
        if username and not has_password:
            self.add_error("new_password", "Set a password for this username.")
        if password and not username:
            self.add_error("username", "Add the username this password goes with.")
        institution = cleaned.get("institution") or getattr(self.instance, "institution", None)
        if username:
            # Two schools can never share a username; two emails of one school
            # may. (A school being added has no sign-ins yet to share with.)
            taken = PortalAccessEmail.objects.filter(username__iexact=username).exclude(pk=self.instance.pk)
            if institution is not None and institution.pk:
                taken = taken.exclude(institution=institution)
            if taken.exists():
                self.add_error("username", "Another institution already signs in with that username.")
        return cleaned

    def save(self, commit=True):
        row = super().save(commit=False)
        if self._password_changed():
            row.set_password(self.cleaned_data["new_password"])
        elif not row.username:
            row.password = ""  # no username, no sign-in: nothing to keep a password for
        if commit:
            row.save()
        return row


def password_status(row) -> str:
    quiet = '<span style="color:var(--body-quiet-color,#666)">{}</span>'
    if not (row and row.pk and row.password):
        return format_html(quiet, "Not set")
    if not row.visible_password:
        return format_html(quiet, "Set (hidden — set again to show)")
    return "Set"


def password_display(row) -> str:
    """The password for list pages; legacy hidden ones say so."""
    if not (row and row.pk and row.password):
        return "—"
    return row.visible_password or format_html('<span style="color:var(--body-quiet-color,#666)">{}</span>',
                                               "hidden")
