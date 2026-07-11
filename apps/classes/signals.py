"""Class registration signals for email automation."""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender="classes.Registration")
def on_registration_created(sender, instance, created, **kwargs):
    """Confirmation email is primarily sent via RegistrationService;
    this signal covers admin-created registrations."""
    if created and instance.status == "confirmed" and not instance.confirmation_sent:
        try:
            from apps.classes.services import RegistrationService

            RegistrationService.send_confirmation(instance)
        except Exception:
            logger.exception("Auto confirmation email failed for registration %s", instance.pk)
