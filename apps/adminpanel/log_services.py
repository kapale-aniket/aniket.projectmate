"""Admin log browsing and cleanup helpers."""
from pathlib import Path
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import ActivityLog
from apps.notifications.models import EmailLog, Notification


SYSTEM_LOG_PATH = Path(settings.BASE_DIR) / "logs" / "projectmate.log"


class LogService:
    """Unified helpers for project logs (activity, email, system file)."""

    @staticmethod
    def activity_queryset(q="", action=""):
        qs = ActivityLog.objects.select_related("user").order_by("-created_at")
        if action:
            qs = qs.filter(action__icontains=action)
        if q:
            qs = qs.filter(
                Q(action__icontains=q)
                | Q(description__icontains=q)
                | Q(user__email__icontains=q)
                | Q(ip_address__icontains=q)
            )
        return qs

    @staticmethod
    def email_queryset(q="", status=""):
        qs = EmailLog.objects.select_related("recipient", "template").order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(
                Q(to_email__icontains=q)
                | Q(subject__icontains=q)
                | Q(error_message__icontains=q)
            )
        return qs

    @staticmethod
    def notification_queryset(q="", level=""):
        qs = Notification.objects.select_related("user").order_by("-created_at")
        if level:
            qs = qs.filter(level=level)
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(message__icontains=q)
                | Q(user__email__icontains=q)
            )
        return qs

    @staticmethod
    def clear_activity(days=None):
        qs = ActivityLog.objects.all()
        if days is not None:
            cutoff = timezone.now() - timedelta(days=int(days))
            qs = qs.filter(created_at__lt=cutoff)
        deleted, _ = qs.delete()
        return deleted

    @staticmethod
    def clear_emails(days=None, status=""):
        qs = EmailLog.objects.all()
        if status:
            qs = qs.filter(status=status)
        if days is not None:
            cutoff = timezone.now() - timedelta(days=int(days))
            qs = qs.filter(created_at__lt=cutoff)
        deleted, _ = qs.delete()
        return deleted

    @staticmethod
    def clear_notifications(days=None):
        qs = Notification.objects.all()
        if days is not None:
            cutoff = timezone.now() - timedelta(days=int(days))
            qs = qs.filter(created_at__lt=cutoff)
        deleted, _ = qs.delete()
        return deleted

    @staticmethod
    def read_system_log(max_lines=200):
        """Return the last N lines from the app file log."""
        path = SYSTEM_LOG_PATH
        if not path.exists():
            return [], str(path), 0
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], str(path), 0
        lines = text.splitlines()
        total = len(lines)
        return lines[-max_lines:], str(path), total

    @staticmethod
    def clear_system_log():
        path = SYSTEM_LOG_PATH
        path.parent.mkdir(exist_ok=True)
        path.write_text("", encoding="utf-8")
        return str(path)

    @staticmethod
    def record(user, action, description="", metadata=None, request=None):
        """Create an activity log entry (safe to call from views)."""
        ip = None
        if request is not None:
            xff = request.META.get("HTTP_X_FORWARDED_FOR")
            ip = (xff.split(",")[0].strip() if xff else None) or request.META.get("REMOTE_ADDR")
        return ActivityLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=action[:100],
            description=description or "",
            metadata=metadata or {},
            ip_address=ip,
        )
