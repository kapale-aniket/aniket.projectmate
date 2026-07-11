"""Announcement models with rich content and attachments."""
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from apps.core.basemodels import BaseModel


class AnnouncementQuerySet(models.QuerySet):
    def visible(self):
        now = timezone.now()
        return self.filter(is_published=True).filter(
            models.Q(scheduled_at__isnull=True) | models.Q(scheduled_at__lte=now)
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )

    def recent(self, days=15):
        """Visible announcements published/created within the last `days` days."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.visible().filter(
            models.Q(published_at__gte=cutoff)
            | models.Q(published_at__isnull=True, created_at__gte=cutoff)
        )


class Announcement(BaseModel):
    class Category(models.TextChoices):
        GENERAL = "general", "General"
        WORKSHOP = "workshop", "Workshop News"
        PLACEMENT = "placement", "Placement News"
        HOLIDAY = "holiday", "Holiday Notice"
        UPDATE = "update", "Latest Update"

    title = models.CharField(max_length=250)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    content = models.TextField()
    summary = models.CharField(max_length=300, blank=True)
    is_pinned = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(
        null=True, blank=True, help_text="Go live at this time (leave blank to publish immediately)"
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Hide after this date/time"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="announcements",
    )
    cover_image = models.ImageField(upload_to="announcements/", blank=True, null=True)
    pdf_file = models.FileField(upload_to="announcements/pdfs/", blank=True, null=True)
    views = models.PositiveIntegerField(default=0)

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ["-is_pinned", "-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("announcements:detail", kwargs={"slug": self.slug})

    @property
    def is_live(self):
        now = timezone.now()
        if not self.is_published:
            return False
        if self.scheduled_at and self.scheduled_at > now:
            return False
        if self.expires_at and self.expires_at <= now:
            return False
        return True


class AnnouncementAttachment(BaseModel):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="announcements/files/")
    name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name or self.file.name
