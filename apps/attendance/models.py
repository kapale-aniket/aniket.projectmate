"""Attendance tracking for free classes."""
from django.conf import settings
from django.db import models
from apps.core.basemodels import BaseModel


class Attendance(BaseModel):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Active"  # Active in session — bonus points vs present
        EXCUSED = "excused", "Excused"  # Legacy; not used in mark UI

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records"
    )
    free_class = models.ForeignKey(
        "classes.FreeClass", on_delete=models.CASCADE, related_name="attendance_records"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABSENT)
    join_time = models.DateTimeField(null=True, blank=True)
    leave_time = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_marked",
    )
    notes = models.TextField(blank=True)
    points_awarded = models.BooleanField(default=False)

    class Meta:
        unique_together = ("student", "free_class")
        ordering = ["-created_at"]
        verbose_name_plural = "Attendance records"

    def __str__(self):
        return f"{self.student.email} — {self.free_class.title}: {self.status}"

    @property
    def duration_minutes(self):
        if self.join_time and self.leave_time:
            return int((self.leave_time - self.join_time).total_seconds() / 60)
        return None
