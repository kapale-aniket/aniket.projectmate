"""Hub views that combine related admin sections into fewer pages."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from apps.adminpanel.mixins import AdminRequiredMixin
from apps.adminpanel.forms import (
    AnnouncementForm,
    CourseMaterialForm,
    AdminNotificationForm,
    EmailTemplateForm,
    BulkEmailForm,
    RewardRuleForm,
    AchievementForm,
    BonusPointsForm,
)
from apps.core.models import ProjectPlan, ProjectPlanPerk
from apps.announcements.models import Announcement
from apps.courses.models import CourseMaterial, PaidCourse
from apps.notifications.models import ScheduledNotification, EmailTemplate, EmailLog
from apps.feedback.models import Feedback
from apps.rewards.models import ResumeUpload, RewardRule, Achievement
from apps.accounts.models import StudentProfile
from apps.referrals.models import Referral
from apps.classes.models import FreeClass
from apps.classes.services import ClassStatusService
from apps.classes.mail_services import ClassMailService


class ContentHubView(AdminRequiredMixin, TemplateView):
    """Announcements + materials + notifications in one page with modals."""

    template_name = "adminpanel/hubs/content.html"

    def get_context_data(self, **kwargs):
        from apps.adminpanel.pagination import paginate_queryset

        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "announcements")
        announcements_qs = Announcement.objects.all()
        materials_qs = CourseMaterial.objects.select_related("course", "free_class")
        scheduled_qs = ScheduledNotification.objects.all()
        plans_qs = ProjectPlan.objects.all()
        perks_qs = ProjectPlanPerk.objects.all()

        if tab == "announcements":
            page_obj = paginate_queryset(self.request, announcements_qs)
            announcements, materials, scheduled = page_obj, materials_qs[:10], scheduled_qs[:10]
            plans, perks = plans_qs[:10], perks_qs[:10]
        elif tab == "materials":
            page_obj = paginate_queryset(self.request, materials_qs)
            announcements, materials, scheduled = announcements_qs[:10], page_obj, scheduled_qs[:10]
            plans, perks = plans_qs[:10], perks_qs[:10]
        elif tab == "plans":
            page_obj = paginate_queryset(self.request, plans_qs)
            announcements, materials, scheduled = announcements_qs[:10], materials_qs[:10], scheduled_qs[:10]
            plans, perks = page_obj, perks_qs
        else:
            page_obj = paginate_queryset(self.request, scheduled_qs)
            announcements, materials, scheduled = announcements_qs[:10], materials_qs[:10], page_obj
            plans, perks = plans_qs[:10], perks_qs[:10]

        ctx.update(
            {
                "tab": tab,
                "announcements": announcements,
                "materials": materials,
                "scheduled": scheduled,
                "project_plans": plans,
                "project_perks": perks,
                "page_obj": page_obj,
                "announcement_form": AnnouncementForm(),
                "material_form": CourseMaterialForm(),
                "notification_form": AdminNotificationForm(),
            }
        )
        return ctx


class CommunityHubView(AdminRequiredMixin, TemplateView):
    """Feedback + resumes + referrals."""

    template_name = "adminpanel/hubs/community.html"

    def get_context_data(self, **kwargs):
        from apps.adminpanel.pagination import paginate_queryset

        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "feedback")
        # Default feedback to pending only on first visit (no status param)
        if tab == "feedback" and "status" not in self.request.GET:
            status = "pending"
        else:
            status = self.request.GET.get("status", "").strip()
            if status == "all":
                status = ""
        feedback = Feedback.objects.select_related("student", "student__profile", "free_class").order_by("-created_at")
        if tab == "feedback" and status:
            feedback = feedback.filter(status=status)
        referrals = Referral.objects.select_related("referrer", "referred_user").order_by("-created_at")
        if tab == "referrals" and status:
            referrals = referrals.filter(status=status)
        uploads = ResumeUpload.objects.select_related("student").order_by("-created_at")

        if tab == "feedback":
            page_obj = paginate_queryset(self.request, feedback)
            items, uploads_page, referrals_page = page_obj, uploads[:10], referrals[:10]
            from apps.feedback.services import FeedbackService

            for fb in items:
                ok, reason = FeedbackService.can_approve(fb)
                fb.can_approve = ok
                fb.approve_block_reason = reason
                att = FeedbackService.get_attendance(fb.student, fb.free_class)
                fb.attendance_status = att.status if att else ""
                fb.attendance_label = att.get_status_display() if att else "Not marked"
        elif tab == "resumes":
            page_obj = paginate_queryset(self.request, uploads)
            items, uploads_page, referrals_page = feedback[:10], page_obj, referrals[:10]
        else:
            page_obj = paginate_queryset(self.request, referrals)
            items, uploads_page, referrals_page = feedback[:10], uploads[:10], page_obj

        ctx.update(
            {
                "tab": tab,
                "status": status,
                "items": items,
                "uploads": uploads_page,
                "referrals": referrals_page,
                "page_obj": page_obj,
            }
        )
        return ctx


class ToolsHubView(AdminRequiredMixin, TemplateView):
    """Emails + rewards — full page fallback or HTMX modal body."""

    template_name = "adminpanel/hubs/tools.html"

    def get_template_names(self):
        if self.request.headers.get("HX-Request") == "true":
            return ["adminpanel/hubs/tools_content.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        from apps.adminpanel.pagination import paginate_queryset

        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "emails")
        email_status = self.request.GET.get("status", "").strip()
        email_logs = EmailLog.objects.select_related("recipient").order_by("-created_at")
        if email_status:
            email_logs = email_logs.filter(status=email_status)
        templates_qs = EmailTemplate.objects.all()
        logs_page = paginate_queryset(self.request, email_logs)
        templates_page = paginate_queryset(self.request, templates_qs, page_param="tpage")
        ctx.update(
            {
                "tab": tab,
                "email_status": email_status,
                "templates": templates_page if tab == "emails" else templates_qs[:10],
                "email_logs": logs_page if tab == "emails" else email_logs[:10],
                "page_obj": logs_page,
                "templates_page": templates_page,
                "tools_hx_target": "#apToolsModalBody" if self.request.headers.get("HX-Request") == "true" else "",
                "bulk_form": BulkEmailForm(),
                "template_form": EmailTemplateForm(),
                "rules": RewardRule.objects.filter(is_active=True),
                "achievements": Achievement.objects.all(),
                "leaderboard": StudentProfile.objects.select_related("user").order_by("-reward_points")[:15],
                "bonus_form": BonusPointsForm(),
                "rule_form": RewardRuleForm(),
                "achievement_form": AchievementForm(),
            }
        )
        return ctx


class LatestClassesHubView(AdminRequiredMixin, TemplateView):
    """Latest free + paid classes with broadcast mail actions."""

    template_name = "adminpanel/hubs/latest_classes.html"

    def get_context_data(self, **kwargs):
        ClassStatusService.sync_all()
        ctx = super().get_context_data(**kwargs)

        # Free: upcoming only — next class day (all on that day if multiple)
        free_qs = FreeClass.objects.filter(status=FreeClass.Status.UPCOMING)
        latest_free_date = free_qs.order_by("date").values_list("date", flat=True).first()
        latest_free = (
            free_qs.filter(date=latest_free_date).order_by("start_time")
            if latest_free_date
            else FreeClass.objects.none()
        )

        # Paid: published only (not draft/archived) — next start day
        paid_qs = (
            PaidCourse.objects.filter(status=PaidCourse.Status.PUBLISHED)
            .exclude(start_date__isnull=True)
        )
        latest_paid_date = paid_qs.order_by("start_date").values_list("start_date", flat=True).first()
        if latest_paid_date:
            latest_paid = paid_qs.filter(start_date=latest_paid_date).order_by("title")
        else:
            latest_paid = (
                PaidCourse.objects.filter(status=PaidCourse.Status.PUBLISHED)
                .order_by("-created_at")[:1]
            )

        ctx.update(
            {
                "latest_free": latest_free,
                "latest_free_date": latest_free_date,
                "latest_paid": latest_paid,
                "latest_paid_date": latest_paid_date,
            }
        )
        return ctx


class FreeClassMailActionView(AdminRequiredMixin, View):
    """POST mail actions for a free class: live | reminder | feedback."""

    def post(self, request, pk, action):
        free_class = get_object_or_404(FreeClass, pk=pk)
        if action == "live":
            sent = ClassMailService.send_free_live(free_class)
            messages.success(request, f"Live mail sent to {sent} student(s) for “{free_class.title}”.")
        elif action == "reminder":
            sent = ClassMailService.send_free_reminder(free_class)
            messages.success(request, f"Reminder mail sent to {sent} student(s) for “{free_class.title}”.")
        elif action == "feedback":
            sent = ClassMailService.send_free_feedback_reminder(free_class)
            messages.success(
                request, f"Feedback reminder sent to {sent} student(s) for “{free_class.title}”."
            )
        else:
            messages.error(request, "Unknown mail action.")
        return redirect("adminpanel:latest_classes")


class PaidCourseMailActionView(AdminRequiredMixin, View):
    """POST mail actions for a paid course: live | reminder."""

    def post(self, request, pk, action):
        course = get_object_or_404(PaidCourse, pk=pk)
        if action == "live":
            sent = ClassMailService.send_paid_live(course)
            messages.success(request, f"Live mail sent to {sent} student(s) for “{course.title}”.")
        elif action == "reminder":
            sent = ClassMailService.send_paid_reminder(course)
            messages.success(request, f"Reminder mail sent to {sent} student(s) for “{course.title}”.")
        else:
            messages.error(request, "Unknown mail action.")
        return redirect("adminpanel:latest_classes")


def logs_url(tab="activity"):
    return reverse("adminpanel:logs") + f"?tab={tab}"


class LogsHubView(AdminRequiredMixin, TemplateView):
    """Browse and manage activity, email, notification, and system logs."""

    template_name = "adminpanel/hubs/logs.html"
    TABS = ("activity", "emails", "notifications", "system")

    def get_context_data(self, **kwargs):
        from apps.adminpanel.pagination import paginate_queryset
        from apps.adminpanel.log_services import LogService
        from apps.accounts.models import ActivityLog
        from apps.notifications.models import Notification

        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get("tab", "activity")
        if tab not in self.TABS:
            tab = "activity"
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        action = self.request.GET.get("action", "").strip()
        level = self.request.GET.get("level", "").strip()

        page_obj = None
        activity_logs = email_logs = notifications = None
        system_lines, system_path, system_total = [], "", 0

        if tab == "activity":
            qs = LogService.activity_queryset(q=q, action=action)
            page_obj = paginate_queryset(self.request, qs)
            activity_logs = page_obj
        elif tab == "emails":
            qs = LogService.email_queryset(q=q, status=status)
            page_obj = paginate_queryset(self.request, qs)
            email_logs = page_obj
        elif tab == "notifications":
            qs = LogService.notification_queryset(q=q, level=level)
            page_obj = paginate_queryset(self.request, qs)
            notifications = page_obj
        else:
            system_lines, system_path, system_total = LogService.read_system_log(300)

        ctx.update(
            {
                "tab": tab,
                "q": q,
                "status": status,
                "action_filter": action,
                "level": level,
                "page_obj": page_obj,
                "activity_logs": activity_logs,
                "email_logs": email_logs,
                "notifications": notifications,
                "system_lines": system_lines,
                "system_path": system_path,
                "system_total": system_total,
                "counts": {
                    "activity": ActivityLog.objects.count(),
                    "emails": EmailLog.objects.count(),
                    "notifications": Notification.objects.count(),
                    "system": system_total,
                },
            }
        )
        return ctx


class LogDeleteView(AdminRequiredMixin, View):
    """Delete a single activity / email / notification log row."""

    def post(self, request, kind, pk):
        from apps.accounts.models import ActivityLog
        from apps.notifications.models import Notification
        from apps.adminpanel.log_services import LogService

        model_map = {
            "activity": ActivityLog,
            "email": EmailLog,
            "notification": Notification,
        }
        model = model_map.get(kind)
        tab = {"activity": "activity", "email": "emails", "notification": "notifications"}.get(
            kind, "activity"
        )
        if not model:
            messages.error(request, "Unknown log type.")
            return redirect(logs_url())
        obj = get_object_or_404(model, pk=pk)
        obj.delete()
        LogService.record(request.user, "log_deleted", f"Deleted {kind} log #{pk}", request=request)
        messages.success(request, "Log entry deleted.")
        return redirect(logs_url(tab))


class LogClearView(AdminRequiredMixin, View):
    """Clear activity / email / notification / system logs."""

    def post(self, request):
        from apps.adminpanel.log_services import LogService

        kind = request.POST.get("kind", "activity")
        days_raw = request.POST.get("days", "").strip()
        days = int(days_raw) if days_raw.isdigit() else None
        status = request.POST.get("status", "").strip()

        if kind == "activity":
            n = LogService.clear_activity(days=days)
            messages.success(request, f"Cleared {n} activity log(s).")
            tab = "activity"
        elif kind == "emails":
            n = LogService.clear_emails(days=days, status=status)
            messages.success(request, f"Cleared {n} email log(s).")
            tab = "emails"
        elif kind == "notifications":
            n = LogService.clear_notifications(days=days)
            messages.success(request, f"Cleared {n} notification(s).")
            tab = "notifications"
        elif kind == "system":
            path = LogService.clear_system_log()
            messages.success(request, f"System log cleared ({path}).")
            tab = "system"
        else:
            messages.error(request, "Unknown log type.")
            return redirect(logs_url())

        LogService.record(
            request.user,
            "logs_cleared",
            f"Cleared {kind} logs" + (f" older than {days} days" if days else ""),
            metadata={"kind": kind, "days": days, "status": status},
            request=request,
        )
        return redirect(logs_url(tab))
