"""Shared form helpers — required-field marking for the whole project."""
from django import forms


_PATCHED = False


def patch_required_field_attrs():
    """
    Ensure every required form field exposes data-pm-required (and HTML required
    where appropriate) so the UI can show a red asterisk on labels.
    """
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    original_init = forms.BaseForm.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        skip_html_required = (
            forms.CheckboxInput,
            forms.CheckboxSelectMultiple,
            forms.RadioSelect,
            forms.HiddenInput,
            forms.FileInput,
            forms.ClearableFileInput,
        )
        for field in self.fields.values():
            if not field.required:
                continue
            attrs = getattr(field.widget, "attrs", None)
            if attrs is None:
                continue
            attrs["data-pm-required"] = "1"
            if not isinstance(field.widget, skip_html_required):
                attrs.setdefault("required", True)

    forms.BaseForm.__init__ = patched_init
