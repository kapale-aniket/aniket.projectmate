"""Student feedback and testimonials."""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from apps.core.basemodels import BaseModel


class Feedback(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedbacks"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField()
    suggestions = models.TextField(blank=True)
    free_class = models.ForeignKey(
        "classes.FreeClass", on_delete=models.SET_NULL, null=True, blank=True, related_name="feedbacks"
    )
    course = models.ForeignKey(
        "courses.PaidCourse", on_delete=models.SET_NULL, null=True, blank=True, related_name="feedbacks"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_featured = models.BooleanField(default=False)
    show_on_landing = models.BooleanField(
        default=False,
        help_text="When enabled, this feedback appears on the public site.",
    )
    admin_liked = models.BooleanField(
        default=False,
        help_text="Admin liked this feedback (visible/notified to that student only).",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks_reviewed",
    )
    points_awarded = models.BooleanField(default=False)
    admin_reply = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_replies",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Feedback"

    def __str__(self):
        return f"{self.student.email} — {self.rating}★ ({self.status})"
