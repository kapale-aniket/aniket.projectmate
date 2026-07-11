"""Account signals — auto-create profile, welcome email, daily login."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_student_profile(sender, instance, created, **kwargs):
    from apps.accounts.models import StudentProfile
    from apps.notifications.services import EmailService

    if created:
        StudentProfile.objects.get_or_create(user=instance)
        try:
            EmailService.send_from_template(
                "welcome",
                instance.email,
                {
                    "student_name": instance.get_full_name() or instance.email,
                    "site_name": "Aniket.ProjectMate",
                },
                recipient=instance,
            )
        except Exception:
            logger.exception("Welcome email failed for %s", instance.email)
