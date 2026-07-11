"""Broadcast class-related emails to registered / enrolled students."""
import logging
from apps.notifications.services import EmailService, NotificationService, EmailHtmlBuilder

logger = logging.getLogger(__name__)


class ClassMailService:
    ACTIVE_ENROLLMENT_STATUSES = ("paid", "active", "completed", "pending_payment")

    @staticmethod
    def _free_class_students(free_class):
        from apps.classes.models import Registration

        return [
            r.student
            for r in Registration.objects.filter(
                free_class=free_class, status=Registration.Status.CONFIRMED
            ).select_related("student")
        ]

    @staticmethod
    def _paid_course_students(course):
        from apps.courses.models import CourseEnrollment

        return [
            e.student
            for e in CourseEnrollment.objects.filter(
                course=course,
                status__in=ClassMailService.ACTIVE_ENROLLMENT_STATUSES,
            ).select_related("student")
        ]

    @staticmethod
    def _meet_link(free_class=None):
        from apps.core.models import SiteSettings

        settings_obj = SiteSettings.load()
        if free_class and free_class.google_meet_link:
            return free_class.google_meet_link
        return settings_obj.default_meet_link or ""

    @staticmethod
    def _site_name():
        from apps.core.models import SiteSettings

        return SiteSettings.load().site_name

    @staticmethod
    def _send_one(student, template_code, context, *, notify_title, notify_message, notify_link=""):
        from apps.notifications.models import EmailTemplate

        if EmailTemplate.objects.filter(code=template_code, is_active=True).exists():
            EmailService.send_from_template(
                template_code, student.email, context, recipient=student
            )
        else:
            subject = context.get("email_subject") or notify_title
            body_text = context.get("email_body_text") or notify_message
            body_html, plain = EmailHtmlBuilder.build(subject, body_text)
            EmailService.send(
                to_email=student.email,
                subject=subject,
                body_html=body_html,
                body_text=plain,
                recipient=student,
                meta={"template_code": template_code},
            )
        NotificationService.notify(
            student,
            title=notify_title,
            message=notify_message,
            level="info",
            link=notify_link or "",
        )

    @classmethod
    def send_free_live(cls, free_class):
        meet = cls._meet_link(free_class)
        site = cls._site_name()
        students = cls._free_class_students(free_class)
        sent = 0
        for student in students:
            name = student.get_full_name() or student.email
            ctx = {
                "student_name": name,
                "class_title": free_class.title,
                "class_date": free_class.date.strftime("%d %B %Y"),
                "class_time": free_class.start_time.strftime("%I:%M %p"),
                "meet_link": meet,
                "site_name": site,
                "email_subject": f"LIVE now: {free_class.title} — join the session!",
                "email_body_text": (
                    f"Hi {name},\n\n{free_class.title} is live right now.\n\n"
                    f"Join the session: {meet}\n\nSee you in class!\n— {site}"
                ),
            }
            cls._send_one(
                student,
                "session_live",
                ctx,
                notify_title="Session is live — join now!",
                notify_message=f"{free_class.title} is live. Join now.",
                notify_link=meet or free_class.get_absolute_url(),
            )
            sent += 1
        logger.info("Free live mail: class=%s sent=%s", free_class.pk, sent)
        return sent

    @classmethod
    def send_free_reminder(cls, free_class):
        meet = cls._meet_link(free_class)
        site = cls._site_name()
        students = cls._free_class_students(free_class)
        sent = 0
        for student in students:
            name = student.get_full_name() or student.email
            ctx = {
                "student_name": name,
                "class_title": free_class.title,
                "class_date": free_class.date.strftime("%d %B %Y"),
                "class_time": free_class.start_time.strftime("%I:%M %p"),
                "meet_link": meet,
                "site_name": site,
                "email_subject": f"Reminder: {free_class.title} starts soon",
                "email_body_text": (
                    f"Hi {name},\n\nReminder: {free_class.title} is coming up.\n\n"
                    f"Date: {free_class.date.strftime('%d %B %Y')} · "
                    f"Time: {free_class.start_time.strftime('%I:%M %p')}\n\n"
                    f"Join link: {meet}\n\n— {site}"
                ),
            }
            cls._send_one(
                student,
                "class_reminder",
                ctx,
                notify_title="Class reminder",
                notify_message=f"Reminder: {free_class.title} starts soon.",
                notify_link=meet or free_class.get_absolute_url(),
            )
            sent += 1
        logger.info("Free reminder mail: class=%s sent=%s", free_class.pk, sent)
        return sent

    @classmethod
    def send_free_feedback_reminder(cls, free_class):
        site = cls._site_name()
        feedback_url = "/feedback/"
        students = cls._free_class_students(free_class)
        sent = 0
        for student in students:
            name = student.get_full_name() or student.email
            ctx = {
                "student_name": name,
                "class_title": free_class.title,
                "class_date": free_class.date.strftime("%d %B %Y"),
                "feedback_url": feedback_url,
                "site_name": site,
                "email_subject": f"Share feedback for {free_class.title}",
                "email_body_text": (
                    f"Hi {name},\n\nThanks for attending {free_class.title}.\n\n"
                    f"Please share your feedback — it helps us improve.\n\n"
                    f"Submit feedback: {feedback_url}\n\n— {site}"
                ),
            }
            cls._send_one(
                student,
                "feedback_reminder",
                ctx,
                notify_title="Feedback reminder",
                notify_message=f"Please share feedback for {free_class.title}.",
                notify_link=feedback_url,
            )
            sent += 1
        logger.info("Free feedback reminder: class=%s sent=%s", free_class.pk, sent)
        return sent

    @classmethod
    def send_paid_live(cls, course):
        meet = cls._meet_link()
        site = cls._site_name()
        students = cls._paid_course_students(course)
        sent = 0
        for student in students:
            name = student.get_full_name() or student.email
            ctx = {
                "student_name": name,
                "class_title": course.title,
                "class_date": course.start_date.strftime("%d %B %Y") if course.start_date else "TBA",
                "class_time": "",
                "meet_link": meet,
                "site_name": site,
                "email_subject": f"LIVE now: {course.title} — join the session!",
                "email_body_text": (
                    f"Hi {name},\n\n{course.title} is live right now.\n\n"
                    f"Join the session: {meet or course.get_absolute_url()}\n\n— {site}"
                ),
            }
            cls._send_one(
                student,
                "session_live",
                ctx,
                notify_title="Session is live — join now!",
                notify_message=f"{course.title} is live. Join now.",
                notify_link=meet or course.get_absolute_url(),
            )
            sent += 1
        logger.info("Paid live mail: course=%s sent=%s", course.pk, sent)
        return sent

    @classmethod
    def send_paid_reminder(cls, course):
        meet = cls._meet_link()
        site = cls._site_name()
        students = cls._paid_course_students(course)
        sent = 0
        for student in students:
            name = student.get_full_name() or student.email
            date_str = course.start_date.strftime("%d %B %Y") if course.start_date else "TBA"
            ctx = {
                "student_name": name,
                "class_title": course.title,
                "class_date": date_str,
                "class_time": "",
                "meet_link": meet,
                "site_name": site,
                "email_subject": f"Reminder: {course.title} starts soon",
                "email_body_text": (
                    f"Hi {name},\n\nReminder: {course.title} is coming up.\n\n"
                    f"Start date: {date_str}\n\n"
                    f"Details: {course.get_absolute_url()}\n\n— {site}"
                ),
            }
            cls._send_one(
                student,
                "class_reminder",
                ctx,
                notify_title="Course reminder",
                notify_message=f"Reminder: {course.title} starts soon.",
                notify_link=course.get_absolute_url(),
            )
            sent += 1
        logger.info("Paid reminder mail: course=%s sent=%s", course.pk, sent)
        return sent
