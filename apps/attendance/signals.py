"""Attendance signals."""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender="attendance.Attendance")
def on_attendance_saved(sender, instance, created, **kwargs):
    # Business logic lives in AttendanceService; signal kept for extensibility
    logger.debug("Attendance saved: %s", instance.pk)
