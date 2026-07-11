"""Free class and registration models."""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from apps.core.basemodels import BaseModel
from apps.core.models import CourseCategory


class FreeClass(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        UPCOMING = "upcoming", "Upcoming"
        LIVE = "live", "Live"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    technology = models.CharField(max_length=100)
    category = models.ForeignKey(
        CourseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="free_classes"
    )
    description = models.TextField()
    preparation_guide = models.TextField(blank=True)
    date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    google_meet_link = models.URLField(blank=True)
    zoom_link = models.URLField(blank=True)
    meeting_password = models.CharField(max_length=100, blank=True)
    meeting_instructions = models.TextField(blank=True)
    banner = models.ImageField(upload_to="classes/", blank=True, null=True)
    class_notes = models.FileField(upload_to="classes/notes/", blank=True, null=True)
    recording = models.FileField(upload_to="classes/recordings/", blank=True, null=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instructed_classes",
    )
    instructor_name = models.CharField(max_length=120, blank=True, default="Aniket")
    max_seats = models.PositiveIntegerField(default=100)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    registration_enabled = models.BooleanField(default=True)
    tags = models.CharField(max_length=300, blank=True, help_text="Comma-separated tags")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPCOMING)
    is_featured = models.BooleanField(default=False)
    important_instructions = models.TextField(blank=True)

    class Meta:
        ordering = ["date", "start_time"]
        verbose_name_plural = "Free Classes"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("classes:detail", kwargs={"slug": self.slug})

    @property
    def registered_count(self):
        return self.registrations.filter(status=Registration.Status.CONFIRMED).count()

    @property
    def seats_left(self):
        return max(0, self.max_seats - self.registered_count)

    @property
    def is_full(self):
        return self.seats_left <= 0

    @property
    def is_registration_open(self):
        if not self.registration_enabled:
            return False
        if self.status == self.Status.CANCELLED:
            return False
        # Past classes (ended or previous calendar day) are not registerable
        if self.has_ended or self.date < timezone.localdate():
            return False
        if self.status not in (self.Status.UPCOMING, self.Status.LIVE):
            return False
        if self.is_full:
            return False
        if self.registration_deadline and timezone.now() > self.registration_deadline:
            return False
        return True

    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @classmethod
    def public_queryset(cls):
        """
        Public UI: no draft/cancelled.
        Show upcoming + live, plus past classes from the last 2 weeks.
        """
        from datetime import timedelta
        from django.db.models import Q

        today = timezone.localdate()
        two_weeks_ago = today - timedelta(days=14)
        return (
            cls.objects.exclude(status__in=[cls.Status.DRAFT, cls.Status.CANCELLED])
            .filter(
                Q(status__in=[cls.Status.UPCOMING, cls.Status.LIVE])
                | Q(date__gte=two_weeks_ago)
            )
            .order_by("date", "start_time")
        )

    @property
    def datetime_start(self):
        from datetime import datetime

        naive = datetime.combine(self.date, self.start_time)
        return timezone.make_aware(naive)

    @property
    def datetime_end(self):
        from datetime import timedelta

        return self.datetime_start + timedelta(minutes=self.duration_minutes or 0)

    @property
    def has_ended(self):
        """True once the scheduled class end time has passed."""
        return timezone.now() >= self.datetime_end

    @property
    def can_mark_attendance(self):
        """Attendance can only be marked after the class has finished."""
        if self.status == self.Status.CANCELLED:
            return False
        return self.has_ended

    @property
    def can_go_live(self):
        """Upcoming classes can be marked live only on the class date, before end."""
        if self.status != self.Status.UPCOMING:
            return False
        today = timezone.localdate()
        if self.date != today:
            return False
        return not self.has_ended

    def compute_status_from_schedule(self):
        """
        Expected status from system date/time.
        Draft and cancelled are never auto-changed.
        Completed is sticky. Live stays live until end time.
        """
        if self.status in (self.Status.DRAFT, self.Status.CANCELLED):
            return self.status
        if self.status == self.Status.COMPLETED:
            return self.Status.COMPLETED

        now = timezone.now()
        start = self.datetime_start
        end = self.datetime_end

        if now >= end:
            return self.Status.COMPLETED

        # Manual or auto live — keep until class ends
        if self.status == self.Status.LIVE:
            return self.Status.LIVE

        if now < start:
            return self.Status.UPCOMING
        return self.Status.LIVE

    def refresh_status(self, save=True):
        """Update this class status from the schedule. Returns True if changed."""
        new_status = self.compute_status_from_schedule()
        if new_status == self.status:
            return False
        self.status = new_status
        update_fields = ["status", "updated_at"]
        if new_status == self.Status.COMPLETED and self.registration_enabled:
            self.registration_enabled = False
            update_fields.append("registration_enabled")
        if save:
            self.save(update_fields=update_fields)
        return True

    @classmethod
    def sync_statuses(cls):
        """Bulk-refresh statuses for all non-draft, non-cancelled classes."""
        updated = 0
        qs = cls.objects.exclude(status__in=[cls.Status.DRAFT, cls.Status.CANCELLED])
        for free_class in qs.iterator():
            if free_class.refresh_status(save=True):
                updated += 1
        return updated


class Registration(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        WAITLISTED = "waitlisted", "Waitlisted"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registrations"
    )
    free_class = models.ForeignKey(FreeClass, on_delete=models.CASCADE, related_name="registrations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    confirmation_sent = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("student", "free_class")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.email} → {self.free_class.title}"
