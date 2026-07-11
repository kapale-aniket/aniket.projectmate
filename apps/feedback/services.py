"""Feedback eligibility and approval rules."""
from apps.attendance.models import Attendance
from apps.classes.models import FreeClass, Registration


# Attendance statuses that allow admin approval
APPROVABLE_ATTENDANCE = (
    Attendance.Status.PRESENT,
    Attendance.Status.LATE,  # "Active" in the UI
)


class FeedbackService:
    @staticmethod
    def registered_workshop_ids(student):
        """Confirmed registrations for this student."""
        return Registration.objects.filter(
            student=student,
            status=Registration.Status.CONFIRMED,
        ).values_list("free_class_id", flat=True)

    @classmethod
    def eligible_workshops_for_feedback(cls, student):
        """
        Workshops a student may review: live/completed AND they registered.
        """
        FreeClass.sync_statuses()
        return (
            FreeClass.objects.filter(
                status__in=[FreeClass.Status.LIVE, FreeClass.Status.COMPLETED],
                id__in=cls.registered_workshop_ids(student),
            )
            .order_by("-date", "-start_time")
        )

    @staticmethod
    def student_was_registered(student, free_class):
        if not student or not free_class:
            return False
        return Registration.objects.filter(
            student=student,
            free_class=free_class,
            status=Registration.Status.CONFIRMED,
        ).exists()

    @staticmethod
    def get_attendance(student, free_class):
        if not student or not free_class:
            return None
        return (
            Attendance.objects.filter(student=student, free_class=free_class)
            .only("status")
            .first()
        )

    @classmethod
    def attendance_allows_approval(cls, student, free_class):
        """Present or Active (late) only — absent / missing / excused cannot be approved."""
        att = cls.get_attendance(student, free_class)
        if not att:
            return False
        return att.status in APPROVABLE_ATTENDANCE

    @classmethod
    def can_approve(cls, feedback):
        """
        Admin may approve only when:
        - feedback is linked to a workshop
        - student was registered
        - attendance is present or active
        """
        if not feedback or not feedback.free_class_id:
            return False, "Feedback must be linked to a workshop."
        if not cls.student_was_registered(feedback.student, feedback.free_class):
            return False, "Student was not registered for this workshop."
        att = cls.get_attendance(feedback.student, feedback.free_class)
        if not att:
            return False, "Attendance not marked yet — mark present/active before approving."
        if att.status == Attendance.Status.ABSENT:
            return False, "Student was absent — feedback cannot be approved."
        if att.status not in APPROVABLE_ATTENDANCE:
            return False, "Only present or active attendance can be approved."
        return True, ""

    @classmethod
    def approval_block_reason(cls, feedback):
        ok, reason = cls.can_approve(feedback)
        return "" if ok else reason
