"""Admin panel forms."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q
from django.utils.text import slugify
from apps.accounts.models import User, StudentProfile
from apps.classes.models import FreeClass
from apps.courses.models import PaidCourse, CourseMaterial
from apps.announcements.models import Announcement
from apps.notifications.models import EmailTemplate
from apps.rewards.models import Achievement, RewardRule
from apps.core.models import SiteSettings, ProjectPlan, ProjectPlanPerk


class AdminLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or mobile",
        widget=forms.TextInput(
            attrs={
                "class": "ap-login__input",
                "placeholder": "Email or mobile number",
                "autocomplete": "username",
                "autofocus": True,
                "inputmode": "text",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "ap-login__input",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )
    remember_me = forms.BooleanField(
        label="Keep me remembered for 15 days",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input ap-login__check",
                "autocomplete": "off",
            }
        ),
    )

    def clean(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if username and "@" not in username:
            digits = "".join(ch for ch in username if ch.isdigit())
            key = digits[-10:] if len(digits) >= 10 else ""
            user = None
            if key:
                user = (
                    User.objects.filter(Q(is_staff=True) | Q(is_superuser=True) | Q(role="admin"))
                    .filter(Q(profile__phone__endswith=key) | Q(profile__phone__icontains=key))
                    .first()
                )
            if user:
                self.cleaned_data["username"] = user.email
        return super().clean()


class JobSearchUserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or mobile",
        widget=forms.TextInput(
            attrs={
                "class": "ap-login__input",
                "placeholder": "Email or mobile number",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "ap-login__input",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input ap-login__check"}),
    )

    def clean(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if username and "@" not in username:
            digits = "".join(ch for ch in username if ch.isdigit())
            key = digits[-10:] if len(digits) >= 10 else ""
            if key:
                from apps.linkedin.models import LinkedInSearchUser

                access = (
                    LinkedInSearchUser.objects.select_related("user")
                    .filter(is_active=True, phone__endswith=key, user__role="linkedin_search", user__is_active=True)
                    .first()
                )
                if access:
                    self.cleaned_data["username"] = access.user.email
        return super().clean()


class AdminForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label="Admin email",
        widget=forms.EmailInput(
            attrs={
                "class": "ap-login__input",
                "placeholder": "you@projectmate.com",
                "autocomplete": "email",
                "autofocus": True,
                "inputmode": "email",
            }
        ),
    )


class FreeClassForm(forms.ModelForm):
    class Meta:
        model = FreeClass
        fields = (
            "title",
            "technology",
            "description",
            "preparation_guide",
            "date",
            "start_time",
            "duration_minutes",
            "google_meet_link",
            "zoom_link",
            "meeting_password",
            "meeting_instructions",
            "banner",
            "class_notes",
            "recording",
            "instructor_name",
            "max_seats",
            "registration_deadline",
            "registration_enabled",
            "tags",
            "status",
            "is_featured",
            "important_instructions",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "technology": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "preparation_guide": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "google_meet_link": forms.URLInput(attrs={"class": "form-control"}),
            "zoom_link": forms.URLInput(attrs={"class": "form-control"}),
            "meeting_password": forms.TextInput(attrs={"class": "form-control"}),
            "meeting_instructions": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "banner": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "class_notes": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "recording": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "instructor_name": forms.TextInput(attrs={"class": "form-control"}),
            "max_seats": forms.NumberInput(attrs={"class": "form-control"}),
            "registration_deadline": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "registration_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tags": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "important_instructions": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.slug:
            base = slugify(obj.title)[:180] or "class"
            slug = base
            i = 1
            while FreeClass.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            obj.slug = slug
        if commit:
            obj.save()
        return obj


class PaidCourseForm(forms.ModelForm):
    class Meta:
        model = PaidCourse
        fields = (
            "title",
            "technology",
            "short_description",
            "description",
            "curriculum",
            "features",
            "benefits",
            "prerequisites",
            "faqs",
            "price",
            "discount_price",
            "duration_weeks",
            "duration_hours",
            "image",
            "instructor_name",
            "max_students",
            "status",
            "is_featured",
            "start_date",
        )
        widgets = {f: forms.TextInput(attrs={"class": "form-control"}) for f in (
            "title", "short_description", "instructor_name"
        )}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.Textarea,)):
                field.widget.attrs.setdefault("class", "form-control")
                field.widget.attrs.setdefault("rows", 3)
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs.setdefault("class", "form-control")
            elif isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.setdefault("class", "form-control")
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({"class": "form-control", "type": "date"})
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.slug:
            base = slugify(obj.title)[:180] or "course"
            slug = base
            i = 1
            while PaidCourse.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            obj.slug = slug
        if commit:
            obj.save()
        return obj


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = (
            "title",
            "category",
            "summary",
            "content",
            "is_pinned",
            "is_published",
            "scheduled_at",
            "expires_at",
            "cover_image",
            "pdf_file",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "summary": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "is_pinned": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "scheduled_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "expires_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "cover_image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "pdf_file": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdf"}),
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.slug:
            base = slugify(obj.title)[:180] or "announcement"
            slug = base
            i = 1
            while Announcement.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            obj.slug = slug
        if commit:
            obj.save()
        return obj


class StudentEditForm(forms.ModelForm):
    first_name = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    class Meta:
        model = StudentProfile
        fields = ("phone", "college", "college_location", "branch", "year", "city", "skills")
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "college": forms.TextInput(attrs={"class": "form-control"}),
            "college_location": forms.TextInput(attrs={"class": "form-control", "placeholder": "City / area"}),
            "branch": forms.TextInput(attrs={"class": "form-control"}),
            "year": forms.Select(attrs={"class": "form-select"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "skills": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name
        self.fields["is_active"].initial = self.user.is_active

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data.get("last_name", "")
        self.user.is_active = self.cleaned_data.get("is_active", True)
        if commit:
            self.user.save()
            profile.save()
        return profile


class EmailTemplateForm(forms.ModelForm):
    """Admin writes plain text; HTML is generated automatically on save."""

    class Meta:
        model = EmailTemplate
        fields = ("code", "subject", "body_text", "is_active")
        labels = {
            "body_text": "Message (plain text)",
        }
        help_texts = {
            "body_text": "Write normal text only. Use {{student_name}} etc. for placeholders. HTML is generated for you.",
            "subject": "Email subject line (can include {{placeholders}}).",
        }
        widgets = {
            "code": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Subject line"}),
            "body_text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 8,
                    "placeholder": "Hi {{student_name}},\n\nYour message here…",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing an old HTML-only template, seed the text field from HTML
        if self.instance and self.instance.pk and not (self.instance.body_text or "").strip():
            from django.utils.html import strip_tags

            self.fields["body_text"].initial = strip_tags(self.instance.body_html or "").strip()

    def save(self, commit=True):
        from apps.notifications.services import EmailHtmlBuilder

        obj = super().save(commit=False)
        plain = (obj.body_text or "").strip()
        obj.body_text = plain
        obj.body_html, _ = EmailHtmlBuilder.build(obj.subject, plain)
        if commit:
            obj.save()
        return obj


class BulkEmailForm(forms.Form):
    subject = forms.CharField(
        label="Subject",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Email subject"}),
    )
    body_text = forms.CharField(
        label="Message (plain text)",
        help_text="Write text only — we generate the HTML email layout for you.",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "Hi,\n\nWrite your message here. Line breaks are kept.",
                "id": "id_body_text",
            }
        ),
    )
    audience = forms.ChoiceField(
        choices=[
            ("all_students", "All students"),
            ("active", "Active students only"),
            ("selected", "Selected student IDs"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    student_ids = forms.CharField(
        required=False,
        help_text="Comma-separated user IDs when audience=selected",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    preview_confirmed = forms.BooleanField(
        required=True,
        label="I reviewed the generated email preview and want to send it",
        error_messages={"required": "Generate the HTML preview and confirm it before sending."},
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "id": "id_preview_confirmed", "disabled": True}
        ),
    )


class SelectedStudentsEmailForm(forms.Form):
    """Email only the students selected on the list page."""

    subject = forms.CharField(
        label="Subject",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Email subject", "id": "bulk_mail_subject"}),
    )
    body_text = forms.CharField(
        label="Message (plain text)",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Hi,\n\nWrite your message here.",
                "id": "bulk_mail_body_text",
            }
        ),
    )
    selected_ids = forms.CharField(widget=forms.HiddenInput(attrs={"id": "bulk_mail_selected_ids"}))
    preview_confirmed = forms.BooleanField(
        required=True,
        label="I reviewed the generated email preview and want to send it",
        error_messages={"required": "Generate the HTML preview and confirm it before sending."},
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "id": "bulk_mail_preview_confirmed", "disabled": True}
        ),
    )


class RewardRuleForm(forms.ModelForm):
    class Meta:
        model = RewardRule
        fields = ("code", "label", "points", "is_active", "description")
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "points": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
        }


class AchievementForm(forms.ModelForm):
    class Meta:
        model = Achievement
        fields = ("code", "title", "description", "icon", "badge_color", "points_required", "is_active")
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "icon": forms.TextInput(attrs={"class": "form-control"}),
            "badge_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "points_required": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class BonusPointsForm(forms.Form):
    student_email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    points = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "form-control"}))
    description = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))


class CourseMaterialForm(forms.ModelForm):
    class Meta:
        model = CourseMaterial
        fields = (
            "title",
            "material_type",
            "course",
            "free_class",
            "file",
            "description",
            "is_public",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "material_type": forms.Select(attrs={"class": "form-select"}),
            "course": forms.Select(attrs={"class": "form-select"}),
            "free_class": forms.Select(attrs={"class": "form-select"}),
            "file": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": ".pdf,.doc,.docx,.zip"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AdminNotificationForm(forms.Form):
    title = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    message = forms.CharField(widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}))
    audience = forms.ChoiceField(
        choices=[
            ("all", "All students"),
            ("active", "Active students"),
            ("selected", "Selected student IDs"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    channel = forms.ChoiceField(
        choices=[
            ("dashboard", "Dashboard only"),
            ("email", "Email only"),
            ("both", "Dashboard + Email"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    student_ids = forms.CharField(
        required=False,
        help_text="Comma-separated user IDs for selected audience",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    scheduled_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
        help_text="Leave blank to send immediately",
    )
    link = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))


class FeedbackReplyForm(forms.Form):
    admin_reply = forms.CharField(
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Reply to student..."}
        )
    )


class SiteSettingsForm(forms.ModelForm):
    """Edit public site / About page content from the admin panel."""

    class Meta:
        model = SiteSettings
        fields = (
            "site_name",
            "tagline",
            "logo",
            "primary_color",
            "mentor_name",
            "mentor_title",
            "mentor_photo",
            "about_mentor",
            "why_learn_with_us",
            "footer_text",
            "login_trust_message",
            "contact_email",
            "contact_phone",
            "contact_address",
            "instagram_url",
            "whatsapp_url",
            "youtube_url",
            "linkedin_url",
            "show_whatsapp_icon",
            "show_instagram_icon",
            "show_linkedin_icon",
            "show_youtube_icon",
        )
        labels = {
            "mentor_name": "Mentor name (About page)",
            "mentor_title": "Mentor title",
            "about_mentor": "About mentor text",
            "why_learn_with_us": "Why learn with us",
            "show_whatsapp_icon": "Show WhatsApp icon",
            "show_instagram_icon": "Show Instagram icon",
            "show_linkedin_icon": "Show LinkedIn icon",
            "show_youtube_icon": "Show YouTube icon",
        }
        help_texts = {
            "about_mentor": "Shown on the About page and home mentor card.",
            "why_learn_with_us": "Shown on About and the home “Why learn with us” section.",
            "mentor_title": "e.g. Founder & Mentor - Aniket.ProjectMate",
            "show_whatsapp_icon": "Floating social bar on the public site",
            "show_instagram_icon": "Floating social bar on the public site",
            "show_linkedin_icon": "Floating social bar on the public site",
            "show_youtube_icon": "Floating social bar on the public site",
        }
        widgets = {
            "site_name": forms.TextInput(attrs={"class": "form-control"}),
            "tagline": forms.TextInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "primary_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "mentor_name": forms.TextInput(attrs={"class": "form-control"}),
            "mentor_title": forms.TextInput(attrs={"class": "form-control"}),
            "mentor_photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "about_mentor": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "why_learn_with_us": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "footer_text": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "login_trust_message": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "contact_email": forms.EmailInput(attrs={"class": "form-control"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "contact_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control"}),
            "whatsapp_url": forms.URLInput(attrs={"class": "form-control"}),
            "youtube_url": forms.URLInput(attrs={"class": "form-control"}),
            "linkedin_url": forms.URLInput(attrs={"class": "form-control"}),
            "show_whatsapp_icon": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "show_instagram_icon": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "show_linkedin_icon": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "show_youtube_icon": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ProjectPlanForm(forms.ModelForm):
    class Meta:
        model = ProjectPlan
        fields = (
            "name",
            "slug",
            "tagline",
            "description",
            "price",
            "price_label",
            "currency_prefix",
            "features",
            "badge",
            "is_highlighted",
            "is_active",
            "order",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "tagline": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "price_label": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional e.g. ₹4,999"}),
            "currency_prefix": forms.TextInput(attrs={"class": "form-control"}),
            "features": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "placeholder": "One feature per line"}
            ),
            "badge": forms.TextInput(attrs={"class": "form-control"}),
            "is_highlighted": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.slug:
            base = slugify(obj.name)[:120] or "plan"
            slug = base
            i = 1
            while ProjectPlan.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            obj.slug = slug
        if commit:
            obj.save()
        return obj


class ProjectPlanPerkForm(forms.ModelForm):
    class Meta:
        model = ProjectPlanPerk
        fields = ("title", "icon", "order", "is_active")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "icon": forms.TextInput(attrs={"class": "form-control", "placeholder": "fas fa-check"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
