"""Class / course registration forms."""
from django import forms


class ClassRegistrationForm(forms.Form):
    """Community follow confirmation before register (no profile fields)."""

    following_community = forms.BooleanField(
        label="I am following the Instagram & WhatsApp community for next updates",
        required=True,
        error_messages={
            "required": "Please follow our Instagram & WhatsApp community, then tick this box to register.",
        },
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_following_community"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def apply_to_user(self):
        """Kept for call-site compatibility — profile fields are no longer collected here."""
        return
