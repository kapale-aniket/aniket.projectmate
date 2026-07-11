"""Celery tasks for email reminders and bulk operations."""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_class_reminders(self):
    """Send reminder emails for classes starting within 24 hours."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.classes.models import FreeClass, Registration
    from apps.classes.services import RegistrationService
    from apps.notifications.services import EmailService
    from apps.core.models import SiteSettings

    now = timezone.now()
    window_end = now + timedelta(hours=24)
    classes = FreeClass.objects.filter(
        status=FreeClass.Status.UPCOMING,
        date__gte=now.date(),
        date__lte=window_end.date(),
    )
    settings_obj = SiteSettings.load()
    sent = 0
    for free_class in classes:
        regs = Registration.objects.filter(
            free_class=free_class,
            status=Registration.Status.CONFIRMED,
            reminder_sent=False,
        ).select_related("student")
        for reg in regs:
            EmailService.send_from_template(
                "class_reminder",
                reg.student.email,
                {
                    "student_name": reg.student.get_full_name() or reg.student.email,
                    "class_title": free_class.title,
                    "class_date": free_class.date.strftime("%d %B %Y"),
                    "class_time": free_class.start_time.strftime("%I:%M %p"),
                    "meet_link": free_class.google_meet_link or settings_obj.default_meet_link,
                    "site_name": settings_obj.site_name,
                },
                recipient=reg.student,
            )
            reg.reminder_sent = True
            reg.save(update_fields=["reminder_sent"])
            sent += 1
    logger.info("Sent %s class reminders", sent)
    return sent


@shared_task
def sync_class_statuses():
    """Advance free-class statuses from schedule (upcoming → live → completed)."""
    from apps.classes.services import ClassStatusService

    updated = ClassStatusService.sync_all()
    logger.info("Celery synced %s class status(es)", updated)
    return updated


@shared_task
def send_bulk_email(subject, body_html, user_ids):
    from apps.accounts.models import User
    from apps.notifications.services import EmailService

    users = User.objects.filter(id__in=user_ids)
    count = 0
    for user in users:
        EmailService.send(
            to_email=user.email,
            subject=subject,
            body_html=body_html,
            recipient=user,
        )
        count += 1
    return count


@shared_task
def send_joining_instructions(registration_id):
    from apps.classes.models import Registration
    from apps.notifications.services import EmailService
    from apps.core.models import SiteSettings

    try:
        reg = Registration.objects.select_related("student", "free_class").get(pk=registration_id)
    except Registration.DoesNotExist:
        return False
    settings_obj = SiteSettings.load()
    EmailService.send_from_template(
        "joining_instructions",
        reg.student.email,
        {
            "student_name": reg.student.get_full_name() or reg.student.email,
            "class_title": reg.free_class.title,
            "meet_link": reg.free_class.google_meet_link or settings_obj.default_meet_link,
            "important_instructions": reg.free_class.important_instructions,
            "site_name": settings_obj.site_name,
        },
        recipient=reg.student,
    )
    return True
