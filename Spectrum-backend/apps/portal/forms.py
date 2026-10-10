from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils.html import format_html

from .models import PortalAccessEmail


class AccessEmailForm(forms.ModelForm):
    """
    One institution sign-in: the email, its username and its password. The
    username and password are optional (an email alone unlocks the Portal
    link, but signing in then needs both). The password is stored hashed: it
    can be set or replaced here, never read back.
    """

    new_password = forms.CharField(
        label="Password", required=False, strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password", "size": 18}),
        help_text="Type one to set or change it; leave blank to keep the current one. A new password signs this "
                  "sign-in out of the portal on every device.")

    class Meta:
        model = PortalAccessEmail
        fields = ("institution", "email", "username", "new_password", "note")
        widgets = {"username": forms.TextInput(attrs={"size": 18, "autocomplete": "off"})}

    def clean_username(self):
        return (self.cleaned_data.get("username") or "").strip()

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        if password:
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
        if self.cleaned_data.get("new_password"):
            row.set_password(self.cleaned_data["new_password"])
        elif not row.username:
            row.password = ""  # no username, no sign-in: nothing to keep a password for
        if commit:
            row.save()
        return row


def password_status(row) -> str:
    if not (row and row.pk and row.password):
        return format_html('<span style="color:var(--body-quiet-color,#666)">{}</span>', "Not set")
    return "Set"
