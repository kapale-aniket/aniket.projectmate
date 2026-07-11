"""Attendance business logic including consistency rewards."""
import logging
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from apps.rewards.services import RewardService
from apps.notifications.services import EmailService, NotificationService

logger = logging.getLogger(__name__)


class AttendanceService:
    @staticmethod
    @transaction.atomic
    def mark(student, free_class, status, marked_by=None, join_time=None, leave_time=None, notes=""):
        from apps.attendance.models import Attendance

        attendance, created = Attendance.objects.update_or_create(
            student=student,
            free_class=free_class,
            defaults={
                "status": status,
                "marked_by": marked_by,
                "join_time": join_time,
                "leave_time": leave_time,
                "notes": notes,
            },
        )

        if status in (Attendance.Status.PRESENT, Attendance.Status.LATE) and not attendance.points_awarded:
            if status == Attendance.Status.LATE:
                reason = "attend_class_active"
                description = f"Active in session: {free_class.title}"
            else:
                reason = "attend_class"
                description = f"Attended: {free_class.title}"
            RewardService.award_points(
                student,
                reason,
                description=description,
                metadata={"class_id": free_class.id, "status": status},
            )
            attendance.points_awarded = True
            attendance.save(update_fields=["points_awarded"])
            AttendanceService.update_consecutive(student)
            AttendanceService.refresh_percentage(student)

        return attendance

    @staticmethod
    def update_consecutive(student):
        from apps.attendance.models import Attendance
        from apps.rewards.models import ResumeUpload

        profile = student.profile
        # Count recent consecutive present/late from latest classes
        records = (
            Attendance.objects.filter(student=student)
            .select_related("free_class")
            .order_by("-free_class__date", "-free_class__start_time")
        )
        streak = 0
        for record in records:
            if record.status in (Attendance.Status.PRESENT, Attendance.Status.LATE):
                streak += 1
            else:
                break

        profile.consecutive_attendance = streak
        profile.save(update_fields=["consecutive_attendance", "updated_at"])

        threshold = getattr(settings, "CONSECUTIVE_ATTENDANCE_REWARD", 6)
        if streak >= threshold and streak % threshold == 0:
            AttendanceService.trigger_consistency_reward(student, streak)

    @staticmethod
    def trigger_consistency_reward(student, streak):
        RewardService.award_points(
            student,
            "consistency",
            points=100,
            description=f"{streak} consecutive sessions — Free Resume Review unlocked!",
            metadata={"streak": streak, "resume_review_eligible": True},
        )
        NotificationService.notify(
            student,
            title="Consistency Reward Unlocked!",
            message=(
                f"Amazing! You attended {streak} consecutive sessions. "
                "Upload your resume for a free review with Aniket.ProjectMate."
            ),
            level="reward",
            link="/dashboard/resume/",
        )
        EmailService.send_from_template(
            "consistency_reward",
            student.email,
            {
                "student_name": student.get_full_name() or student.email,
                "streak": streak,
                "site_name": "Aniket.ProjectMate",
            },
            recipient=student,
        )

    @staticmethod
    def refresh_percentage(student):
        from apps.attendance.models import Attendance

        totals = Attendance.objects.filter(student=student).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status__in=["present", "late"])),
        )
        total = totals["total"] or 0
        present = totals["present"] or 0
        pct = round((present / total) * 100, 2) if total else 0
        profile = student.profile
        profile.attendance_percentage = pct
        profile.save(update_fields=["attendance_percentage", "updated_at"])

    @staticmethod
    def bulk_mark(free_class, student_status_map, marked_by=None):
        results = []
        for student_id, status in student_status_map.items():
            from apps.accounts.models import User

            student = User.objects.get(pk=student_id)
            results.append(
                AttendanceService.mark(student, free_class, status, marked_by=marked_by)
            )
        return results
