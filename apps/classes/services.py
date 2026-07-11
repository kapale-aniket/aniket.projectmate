"""Free class registration business logic."""
import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.notifications.services import EmailService, NotificationService
from apps.core.models import SiteSettings

logger = logging.getLogger(__name__)


class ClassStatusService:
    """Keep free-class status aligned with system date/time."""

    @staticmethod
    def sync_all():
        from apps.classes.models import FreeClass

        updated = FreeClass.sync_statuses()
        if updated:
            logger.info("Synced status for %s free class(es)", updated)
        return updated

    @staticmethod
    @transaction.atomic
    def go_live(free_class):
        """
        Mark an upcoming class as live (class day only) and email all
        confirmed registrants to join now.
        """
        from apps.classes.models import FreeClass
        from apps.classes.mail_services import ClassMailService

        free_class.refresh_from_db()
        if not free_class.can_go_live:
            raise ValidationError(
                "This class can only be marked live on its scheduled day while it is still upcoming."
            )

        free_class.status = FreeClass.Status.LIVE
        free_class.save(update_fields=["status", "updated_at"])
        sent = ClassMailService.send_free_live(free_class)
        logger.info("Class %s marked live; emailed %s student(s)", free_class.pk, sent)
        return sent


class RegistrationService:
    @staticmethod
    @transaction.atomic
    def register(student, free_class):
        from apps.classes.models import Registration

        free_class.refresh_status(save=True)

        if not free_class.is_registration_open:
            raise ValidationError("Registration is closed for this class.")

        existing = Registration.objects.filter(student=student, free_class=free_class).first()
        if existing and existing.status != Registration.Status.CANCELLED:
            raise ValidationError("You are already registered for this class.")

        if existing:
            existing.status = Registration.Status.CONFIRMED
            existing.save(update_fields=["status", "updated_at"])
            registration = existing
        else:
            # Always auto-confirmed — no admin approval required
            registration = Registration.objects.create(
                student=student,
                free_class=free_class,
                status=Registration.Status.CONFIRMED,
            )

        if registration.status == Registration.Status.CONFIRMED:
            # Email sent via post_save signal to avoid duplication
            pass

        NotificationService.notify(
            student,
            title="Class registration confirmed",
            message=f"You are registered for {free_class.title}. Check your email for the session Meet link.",
            level="success",
            link=free_class.get_absolute_url(),
        )
        return registration

    @staticmethod
    def send_confirmation(registration):
        settings_obj = SiteSettings.load()
        free_class = registration.free_class
        student = registration.student
        context = {
            "student_name": student.get_full_name() or student.email,
            "class_title": free_class.title,
            "class_date": free_class.date.strftime("%d %B %Y"),
            "class_time": free_class.start_time.strftime("%I:%M %p"),
            "duration": free_class.duration_minutes,
            "meet_link": free_class.google_meet_link or settings_obj.default_meet_link,
            "preparation_guide": free_class.preparation_guide,
            "important_instructions": free_class.important_instructions,
            "instagram_url": settings_obj.instagram_url,
            "whatsapp_url": settings_obj.whatsapp_url,
            "site_name": settings_obj.site_name,
        }
        ics = EmailService.build_ics(
            title=free_class.title,
            description=free_class.description[:500],
            start_dt=free_class.datetime_start,
            duration_minutes=free_class.duration_minutes,
            location=free_class.google_meet_link or "",
        )
        EmailService.send_from_template(
            "registration_confirm",
            student.email,
            context,
            recipient=student,
            ics_content=ics,
        )
        registration.confirmation_sent = True
        registration.save(update_fields=["confirmation_sent"])
