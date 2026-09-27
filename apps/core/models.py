"""Core platform settings, gallery, FAQ, mentor, stats."""
from django.db import models
from django.core.cache import cache
from apps.core.basemodels import BaseModel, TimeStampedModel  # noqa: F401


class SiteSettings(BaseModel):
    """Singleton editable settings — no code changes needed for links/theme."""

    site_name = models.CharField(max_length=120, default="Aniket.ProjectMate")
    tagline = models.CharField(max_length=255, blank=True, default="Learn. Build. Grow.")
    logo = models.ImageField(upload_to="branding/", blank=True, null=True)
    favicon = models.ImageField(upload_to="branding/", blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#1a365d")
    secondary_color = models.CharField(max_length=7, default="#0b1929")
    default_theme = models.CharField(
        max_length=10,
        choices=[("light", "Light"), ("dark", "Dark")],
        default="light",
    )
    instagram_url = models.URLField(blank=True)
    whatsapp_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    show_whatsapp_icon = models.BooleanField(
        default=True,
        help_text="Show WhatsApp in the floating social icons",
    )
    show_instagram_icon = models.BooleanField(
        default=True,
        help_text="Show Instagram in the floating social icons",
    )
    show_linkedin_icon = models.BooleanField(
        default=True,
        help_text="Show LinkedIn in the floating social icons",
    )
    show_youtube_icon = models.BooleanField(
        default=True,
        help_text="Show YouTube in the floating social icons",
    )
    default_meet_link = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True, default="aniketkapale02@gmail.com")
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_address = models.TextField(blank=True)
    footer_text = models.TextField(blank=True, default="Empowering students through practical learning.")
    meta_description = models.CharField(max_length=300, blank=True)
    meta_keywords = models.CharField(max_length=300, blank=True)
    students_count = models.PositiveIntegerField(default=0)
    workshops_count = models.PositiveIntegerField(default=0)
    login_trust_message = models.TextField(
        default=(
            "We ask you to sign in so we can securely reserve your seat, send your "
            "Google Meet link, track your attendance, and provide rewards based on "
            "your learning journey. Your information is never shared."
        )
    )
    about_mentor = models.TextField(blank=True)
    mentor_name = models.CharField(max_length=120, default="Aniket")
    mentor_photo = models.ImageField(upload_to="branding/", blank=True, null=True)
    mentor_title = models.CharField(max_length=200, blank=True, default="Founder & Mentor")
    why_learn_with_us = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        try:
            cache.delete("site_settings")
        except Exception:
            pass

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        try:
            cached = cache.get("site_settings")
            if cached:
                return cached
        except Exception:
            pass
        try:
            obj, _ = cls.objects.get_or_create(pk=1)
        except Exception:
            # DB not migrated yet — return unsaved defaults so pages still render
            return cls(pk=1)
        try:
            cache.set("site_settings", obj, 300)
        except Exception:
            pass
        return obj


class FAQ(BaseModel):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class GalleryImage(BaseModel):
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to="gallery/")
    caption = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.title


class CourseCategory(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="FontAwesome class e.g. fa-python")
    color = models.CharField(max_length=7, default="#1a365d")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Course Categories"

    def __str__(self):
        return self.name


class SuccessStory(BaseModel):
    student_name = models.CharField(max_length=120)
    college = models.CharField(max_length=200, blank=True)
    story = models.TextField()
    photo = models.ImageField(upload_to="success/", blank=True, null=True)
    company = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=120, blank=True)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name_plural = "Success Stories"

    def __str__(self):
        return self.student_name


class ContactMessage(BaseModel):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} from {self.name}"


class ProjectIdea(BaseModel):
    """Student project idea submissions — customize their project in real."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWING = "reviewing", "Reviewing"
        CONTACTED = "contacted", "Contacted"
        DONE = "done", "Done"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    college = models.CharField(max_length=200, blank=True)
    project_title = models.CharField(max_length=200, help_text="Working title for your idea")
    idea = models.TextField(help_text="Describe your project idea in your own words")
    tech_stack = models.CharField(
        max_length=300,
        blank=True,
        help_text="Preferred tech (e.g. Django, React) — optional",
    )
    timeline = models.CharField(max_length=120, blank=True, help_text="When do you need it?")
    selected_plan = models.ForeignKey(
        "core.ProjectPlan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="idea_submissions",
        help_text="Plan the student chose before submitting",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Project idea"
        verbose_name_plural = "Project ideas"

    def __str__(self):
        return f"{self.project_title} — {self.name}"


class ProjectPlan(BaseModel):
    """Priced project packages shown on the public Project page (admin-managed)."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_label = models.CharField(
        max_length=40,
        blank=True,
        help_text="Optional display override, e.g. ₹4,999 or From ₹3k",
    )
    currency_prefix = models.CharField(max_length=8, default="₹")
    features = models.TextField(
        blank=True,
        help_text="One feature per line (shown as bullets on the plan card).",
    )
    badge = models.CharField(
        max_length=60,
        blank=True,
        help_text="Optional badge, e.g. Popular or Best for viva",
    )
    is_highlighted = models.BooleanField(default=False, help_text="Emphasize this plan on the page")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "price", "name"]
        verbose_name = "Project plan"
        verbose_name_plural = "Project plans"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify

            base = slugify(self.name)[:120] or "plan"
            slug = base
            i = 1
            while ProjectPlan.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def display_price(self):
        if self.price_label:
            return self.price_label
        amount = f"{self.price:,.0f}" if self.price == self.price.to_integral_value() else f"{self.price:,.2f}"
        return f"{self.currency_prefix}{amount}"

    @property
    def feature_list(self):
        return [line.strip() for line in (self.features or "").splitlines() if line.strip()]


class ProjectPlanPerk(BaseModel):
    """Shared inclusions shown under all project plans (admin-managed)."""

    title = models.CharField(max_length=160)
    icon = models.CharField(
        max_length=60,
        blank=True,
        default="fas fa-check",
        help_text="Font Awesome class, e.g. fas fa-diagram-project",
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Project plan perk"
        verbose_name_plural = "Project plan perks"

    def __str__(self):
        return self.title
