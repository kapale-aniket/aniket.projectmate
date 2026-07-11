"""Notifications and email templates."""
from django.conf import settings
from django.db import models
from apps.core.basemodels import BaseModel


class EmailTemplate(BaseModel):
    class Code(models.TextChoices):
        REGISTRATION_CONFIRM = "registration_confirm", "Registration Confirmation"
        CLASS_REMINDER = "class_reminder", "Class Reminder"
        JOINING_INSTRUCTIONS = "joining_instructions", "Joining Instructions"
        SESSION_LIVE = "session_live", "Session Live — Join Now"
        FEEDBACK_REMINDER = "feedback_reminder", "Feedback Reminder"
        CONSISTENCY_REWARD = "consistency_reward", "Consistency Reward"
        RESUME_FEEDBACK = "resume_feedback", "Resume Feedback"
        WELCOME = "welcome", "Welcome Email"
        REFERRAL_APPROVED = "referral_approved", "Referral Approved"
        PASSWORD_CHANGED = "password_changed", "Password Changed"
        CUSTOM = "custom", "Custom"

    code = models.CharField(max_length=50, choices=Code.choices, unique=True)
    subject = models.CharField(max_length=250)
    body_html = models.TextField(help_text="Auto-generated branded HTML (from plain text)")
    body_text = models.TextField(blank=True, help_text="Plain text message — edit this in admin")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.get_code_display()}"


class EmailLog(BaseModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="emails_received"
    )
    to_email = models.EmailField()
    subject = models.CharField(max_length=250)
    body_html = models.TextField(blank=True)
    template = models.ForeignKey(
        EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    error_message = models.TextField(blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.to_email}: {self.subject} ({self.status})"


class Notification(BaseModel):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        REWARD = "reward", "Reward"
        REMINDER = "reminder", "Reminder"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO)
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email}: {self.title}"


class ScheduledNotification(BaseModel):
    class Audience(models.TextChoices):
        ALL = "all", "All students"
        SELECTED = "selected", "Selected students"
        ACTIVE = "active", "Active students"

    class Channel(models.TextChoices):
        DASHBOARD = "dashboard", "Dashboard only"
        EMAIL = "email", "Email only"
        BOTH = "both", "Dashboard + Email"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=200)
    message = models.TextField()
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.BOTH)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    selected_user_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_notifications",
    )
    link = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"
