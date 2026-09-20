from django import forms

from apps.linkedin.services.config_service import load_settings


class JobScraperForm(forms.Form):
    keywords = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "One keyword per line"}),
        help_text="One keyword per line",
    )
    locations = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "One location per line"}),
    )
    max_pages = forms.IntegerField(
        min_value=1, max_value=200, initial=40,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    max_jobs = forms.IntegerField(
        min_value=0, required=False, initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    max_job_age_hours = forms.IntegerField(
        min_value=1,
        max_value=48,
        initial=24,
        label="Job age (hours)",
        help_text="Search jobs posted within the last 1–48 hours",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    headless = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    resume = forms.BooleanField(
        required=False, initial=True, label="Resume from checkpoint",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    skip_previous_jobs = forms.BooleanField(
        required=False,
        initial=False,
        label="Skip previous jobs",
        help_text="When checked, skip jobs already collected in earlier runs.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    run_in_background = forms.BooleanField(
        required=False, initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = load_settings().get("job", {})
        self.fields["keywords"].initial = "\n".join(settings.get("keywords", []))
        self.fields["locations"].initial = "\n".join(settings.get("locations", []))
        self.fields["max_pages"].initial = settings.get("max_pages", 40)
        self.fields["max_jobs"].initial = settings.get("max_jobs", 0)
        self.fields["max_job_age_hours"].initial = settings.get("max_job_age_hours", 24)
        self.fields["headless"].initial = settings.get("headless", False)

    def clean(self):
        cleaned = super().clean()
        keywords = [k.strip() for k in cleaned.get("keywords", "").splitlines() if k.strip()]
        locations = [l.strip() for l in cleaned.get("locations", "").splitlines() if l.strip()]
        if not keywords:
            raise forms.ValidationError({"keywords": "At least one keyword is required."})
        if not locations:
            raise forms.ValidationError({"locations": "At least one location is required."})
        return cleaned

    def cleaned_config(self):
        data = self.cleaned_data
        return {
            "keywords": [k.strip() for k in data["keywords"].splitlines() if k.strip()],
            "locations": [l.strip() for l in data["locations"].splitlines() if l.strip()],
            "max_pages": data["max_pages"],
            "max_jobs": data.get("max_jobs") or 0,
            "max_job_age_hours": int(data.get("max_job_age_hours") or 24),
            "headless": True,
            "resume": data.get("resume", True),
            "skip_previous_jobs": bool(data.get("skip_previous_jobs")),
        }


class ConnectionScraperForm(forms.Form):
    keywords = forms.CharField(widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}))
    locations = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    max_connections_per_run = forms.IntegerField(
        min_value=1, max_value=500, initial=30,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    max_pages = forms.IntegerField(
        min_value=1, max_value=500, initial=200,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    headless = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    run_in_background = forms.BooleanField(
        required=False, initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = load_settings().get("connection", {})
        self.fields["keywords"].initial = "\n".join(settings.get("keywords", []))
        self.fields["locations"].initial = "\n".join(settings.get("locations", []))
        self.fields["max_connections_per_run"].initial = settings.get("max_connections_per_run", 30)
        self.fields["max_pages"].initial = settings.get("max_pages", 200)
        self.fields["headless"].initial = settings.get("headless", False)

    def cleaned_config(self):
        data = self.cleaned_data
        return {
            "keywords": [k.strip() for k in data["keywords"].splitlines() if k.strip()],
            "locations": [l.strip() for l in data["locations"].splitlines() if l.strip()],
            "max_connections_per_run": data["max_connections_per_run"],
            "max_pages": data["max_pages"],
            "headless": True,
        }


class PostsScraperForm(forms.Form):
    max_scroll_rounds = forms.IntegerField(
        min_value=1, max_value=100, initial=30,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    max_posts_per_run = forms.IntegerField(
        min_value=0, required=False, initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    headless = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    run_in_background = forms.BooleanField(
        required=False, initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings = load_settings().get("posts", {})
        self.fields["max_scroll_rounds"].initial = settings.get("max_scroll_rounds", 30)
        self.fields["max_posts_per_run"].initial = settings.get("max_posts_per_run", 0)
        self.fields["headless"].initial = settings.get("headless", False)

    def cleaned_config(self):
        data = self.cleaned_data
        return {
            "max_scroll_rounds": data["max_scroll_rounds"],
            "max_posts_per_run": data.get("max_posts_per_run") or 0,
            "headless": True,
        }


class SessionForm(forms.Form):
    run_in_background = forms.BooleanField(
        required=False,
        initial=True,
        label="Run in background (opens browser window for manual login)",
    )


class SettingsForm(forms.Form):
    TAB_CHOICES = [
        ("job", "Job Scraper"),
        ("connection", "Connection Scraper"),
        ("posts", "Posts Scraper"),
        ("browser", "Browser"),
        ("cursor", "Screen Awake"),
    ]
    tab = forms.ChoiceField(choices=TAB_CHOICES, initial="job", required=False)

    job_keywords = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}))
    job_locations = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
    job_max_pages = forms.IntegerField(required=False, min_value=1, widget=forms.NumberInput(attrs={"class": "form-control"}))
    job_max_jobs = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={"class": "form-control"}))
    job_max_age_hours = forms.IntegerField(
        required=False, min_value=1, max_value=48, widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    job_min_delay = forms.FloatField(required=False, min_value=0.5, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}))
    job_max_delay = forms.FloatField(required=False, min_value=0.5, widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}))

    sheet_title = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    whatsapp_group_url = forms.CharField(required=False, widget=forms.URLInput(attrs={"class": "form-control"}))
    whatsapp_group_name = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    instagram_url = forms.CharField(required=False, widget=forms.URLInput(attrs={"class": "form-control"}))
    instagram_handle = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    connection_keywords = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}))
    connection_locations = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
    connection_max = forms.IntegerField(required=False, min_value=1, widget=forms.NumberInput(attrs={"class": "form-control"}))
    connection_max_pages = forms.IntegerField(required=False, min_value=1, widget=forms.NumberInput(attrs={"class": "form-control"}))

    posts_max_scroll = forms.IntegerField(required=False, min_value=1, widget=forms.NumberInput(attrs={"class": "form-control"}))
    posts_max_posts = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={"class": "form-control"}))

    browser_headless = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    cursor_enabled = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    cursor_interval_seconds = forms.IntegerField(
        required=False, min_value=15, max_value=600, widget=forms.NumberInput(attrs={"class": "form-control"})
    )

    job_excel_format = forms.CharField(required=False, widget=forms.HiddenInput())
    connection_excel_format = forms.CharField(required=False, widget=forms.HiddenInput())
    posts_excel_format = forms.CharField(required=False, widget=forms.HiddenInput())
