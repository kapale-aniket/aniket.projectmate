from django import forms
from django.core.validators import MaxLengthValidator, MinLengthValidator

from apps.classes.models import FreeClass

from .models import Feedback
from .services import FeedbackService

REVIEW_MIN_LENGTH = 50
REVIEW_MAX_LENGTH = 100


class WorkshopChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        date_str = obj.date.strftime("%d %b %Y") if obj.date else ""
        status = obj.get_status_display()
        if date_str:
            return f"{obj.title} — {status} ({date_str})"
        return f"{obj.title} — {status}"


class FeedbackForm(forms.ModelForm):
    free_class = WorkshopChoiceField(
        label="Workshop",
        queryset=FreeClass.objects.none(),
        empty_label="Select a workshop…",
        widget=forms.Select(
            attrs={
                "class": "form-select pm-select2",
                "data-placeholder": "Select a registered workshop…",
            }
        ),
    )

    class Meta:
        model = Feedback
        fields = ("free_class", "rating", "review", "suggestions")
        widgets = {
            "rating": forms.RadioSelect(
                choices=[(i, str(i)) for i in range(1, 6)],
                attrs={"class": "pm-star-rating__input"},
            ),
            "review": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": f"Share your experience ({REVIEW_MIN_LENGTH}–{REVIEW_MAX_LENGTH} characters)…",
                    "minlength": REVIEW_MIN_LENGTH,
                    "maxlength": REVIEW_MAX_LENGTH,
                    "data-pm-char-count": "1",
                    "data-pm-char-min": REVIEW_MIN_LENGTH,
                    "data-pm-char-max": REVIEW_MAX_LENGTH,
                }
            ),
            "suggestions": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Suggestions (optional)"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            qs = FeedbackService.eligible_workshops_for_feedback(user)
        else:
            qs = FreeClass.objects.none()
        self.fields["free_class"].queryset = qs
        self.fields["free_class"].required = True
        self.fields["free_class"].help_text = (
            "Only workshops you registered for (live or completed)."
        )
        self.fields["free_class"].empty_label = "Select a workshop…"
        self.fields["free_class"].widget.attrs["data-placeholder"] = "Select a workshop…"
        if not qs.exists():
            self.fields["free_class"].required = False
            self.fields["free_class"].widget.attrs["disabled"] = True
            self.fields["free_class"].widget.attrs.pop("class", None)
            self.fields["free_class"].widget.attrs["class"] = "form-select"
        self.fields["suggestions"].required = False
        self.fields["review"].validators = [
            MinLengthValidator(
                REVIEW_MIN_LENGTH,
                message=f"Review must be at least {REVIEW_MIN_LENGTH} characters.",
            ),
            MaxLengthValidator(
                REVIEW_MAX_LENGTH,
                message=f"Review must be at most {REVIEW_MAX_LENGTH} characters.",
            ),
        ]
        self.fields["review"].help_text = (
            f"{REVIEW_MIN_LENGTH}–{REVIEW_MAX_LENGTH} characters required."
        )

    def clean_free_class(self):
        free_class = self.cleaned_data.get("free_class")
        if not free_class:
            raise forms.ValidationError("Please select a workshop.")
        if not self.user or not FeedbackService.student_was_registered(self.user, free_class):
            raise forms.ValidationError(
                "You can only give feedback for workshops you registered for."
            )
        if free_class.status not in (FreeClass.Status.LIVE, FreeClass.Status.COMPLETED):
            raise forms.ValidationError("Feedback is only open for live or completed workshops.")
        return free_class
