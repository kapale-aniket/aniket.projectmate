"""Extra admin views: materials, notifications, reports, feedback extras."""
import json
from datetime import timedelta
from django.contrib import messages
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncDate, TruncMonth
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from apps.adminpanel.mixins import AdminRequiredMixin, ModalFormMixin, MessageDeleteMixin
from apps.adminpanel.forms import CourseMaterialForm, AdminNotificationForm, ProjectPlanForm, ProjectPlanPerkForm
from apps.core.models import ProjectPlan, ProjectPlanPerk
from apps.accounts.models import User, StudentProfile, ActivityLog
from apps.classes.models import Registration
from apps.courses.models import CourseEnrollment, CourseMaterial
from apps.attendance.models import Attendance
from apps.feedback.models import Feedback
from apps.referrals.models import Referral
from apps.notifications.models import EmailLog, ScheduledNotification
from apps.notifications.services import EmailService, NotificationService
from apps.announcements.models import Announcement


def content_url(tab=None):
    url = reverse("adminpanel:content")
    return f"{url}?tab={tab}" if tab else url


def community_url(tab=None):
    url = reverse("adminpanel:community")
    return f"{url}?tab={tab}" if tab else url


def tools_url(tab=None):
    url = reverse("adminpanel:tools")
    return f"{url}?tab={tab}" if tab else url


def _audience_users(audience, student_ids_raw=""):
    users = User.objects.filter(role="student")
    if audience == "active":
        users = users.filter(is_active=True)
    elif audience == "selected":
        ids = [i.strip() for i in (student_ids_raw or "").split(",") if i.strip().isdigit()]
        users = users.filter(id__in=ids)
    return users


def dispatch_notification(title, message, users, channel, link="", created_by=None):
    count = 0
    for user in users:
        if channel in ("dashboard", "both"):
            NotificationService.notify(user, title=title, message=message, level="info", link=link)
        if channel in ("email", "both"):
            EmailService.send_plain(
                to_email=user.email,
                subject=title,
                body_text=message,
                recipient=user,
            )
        count += 1
    return count


# ---------- Announcement pin toggle ----------
class AnnouncementPinView(AdminRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(Announcement, pk=pk)
        obj.is_pinned = not obj.is_pinned
        obj.save(update_fields=["is_pinned", "updated_at"])
        messages.success(request, f"{'Pinned' if obj.is_pinned else 'Unpinned'}: {obj.title}")
        return redirect(content_url())


# ---------- Feedback extras ----------
class FeedbackFeatureView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.feedback.services import FeedbackService

        fb = get_object_or_404(Feedback, pk=pk)
        turning_on = not fb.is_featured
        if turning_on and fb.status != Feedback.Status.APPROVED:
            ok, reason = FeedbackService.can_approve(fb)
            if not ok:
                messages.error(
                    request,
                    reason or "Cannot feature — student must be present/active for this workshop.",
                )
                return redirect(community_url("feedback"))
            fb.status = Feedback.Status.APPROVED
            fb.reviewed_by = request.user
        fb.is_featured = turning_on
        fb.save()
        messages.success(
            request,
            f"Feedback {'marked featured' if fb.is_featured else 'unfeatured'}.",
        )
        return redirect(community_url("feedback"))


class FeedbackShowOnUIView(AdminRequiredMixin, View):
    """Toggle public site visibility (landing / testimonials)."""

    def post(self, request, pk):
        from apps.feedback.services import FeedbackService

        fb = get_object_or_404(Feedback, pk=pk)
        turning_on = not fb.show_on_landing
        if turning_on:
            ok, reason = FeedbackService.can_approve(fb)
            if not ok:
                messages.error(
                    request,
                    reason or "Cannot show on UI — student must be present/active for this workshop.",
                )
                return redirect(community_url("feedback"))
            fb.status = Feedback.Status.APPROVED
            fb.reviewed_by = request.user
        fb.show_on_landing = turning_on
        fb.save()
        messages.success(
            request,
            f"Feedback {'shown on UI' if fb.show_on_landing else 'hidden from UI'}.",
        )
        return redirect(community_url("feedback"))


class FeedbackLikeView(AdminRequiredMixin, View):
    """Like feedback — notifies that student only (not public)."""

    def post(self, request, pk):
        fb = get_object_or_404(Feedback, pk=pk)
        fb.admin_liked = not fb.admin_liked
        fb.save(update_fields=["admin_liked", "updated_at"])
        if fb.admin_liked:
            NotificationService.notify(
                fb.student,
                title="Admin liked your feedback",
                message="Thanks for sharing your experience — the team liked your review.",
                level="success",
                link="/feedback/",
            )
            messages.success(request, f"Liked — notified {fb.student.email} only.")
        else:
            messages.info(request, "Like removed.")
        return redirect(community_url("feedback"))


class FeedbackDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = Feedback
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:community")
    success_message = "Feedback deleted."


class FeedbackReplyView(AdminRequiredMixin, View):
    """Reply — notification + email to that student only."""

    def post(self, request, pk):
        fb = get_object_or_404(Feedback, pk=pk)
        reply = request.POST.get("admin_reply", "").strip()
        if not reply:
            messages.error(request, "Reply cannot be empty.")
            return redirect(community_url("feedback"))
        fb.admin_reply = reply
        fb.replied_at = timezone.now()
        fb.replied_by = request.user
        fb.save(update_fields=["admin_reply", "replied_at", "replied_by", "updated_at"])
        NotificationService.notify(
            fb.student,
            title="Reply to your feedback",
            message=reply,
            level="info",
            link="/feedback/",
        )
        EmailService.send_plain(
            to_email=fb.student.email,
            subject="Reply to your ProjectMate feedback",
            body_text=f"Hi,\n\nAdmin replied to your feedback:\n\n{reply}",
            recipient=fb.student,
        )
        messages.success(request, f"Reply sent to {fb.student.email} only.")
        return redirect(community_url("feedback"))


# ---------- Course materials ----------
class MaterialListView(AdminRequiredMixin, ListView):
    model = CourseMaterial
    template_name = "adminpanel/materials/list.html"
    context_object_name = "materials"
    paginate_by = 10

    def get_queryset(self):
        qs = CourseMaterial.objects.select_related("course", "free_class", "uploaded_by")
        course = self.request.GET.get("course")
        if course:
            qs = qs.filter(course_id=course)
        return qs


class MaterialCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = CourseMaterial
    form_class = CourseMaterialForm
    template_name = "adminpanel/materials/form.html"
    success_url = reverse_lazy("adminpanel:content")
    modal_title = "Upload material"

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=materials"

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, "Material uploaded.")
        return super().form_valid(form)


class MaterialDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = CourseMaterial
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:content")
    success_message = "Material “{object}” deleted."

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=materials"


# ---------- Project plans (public Project page) ----------
class ProjectPlanCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = ProjectPlan
    form_class = ProjectPlanForm
    template_name = "adminpanel/project_plans/form.html"
    success_url = reverse_lazy("adminpanel:content")
    modal_title = "New project plan"

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=plans"

    def form_valid(self, form):
        messages.success(self.request, "Project plan saved.")
        return super().form_valid(form)


class ProjectPlanUpdateView(AdminRequiredMixin, ModalFormMixin, UpdateView):
    model = ProjectPlan
    form_class = ProjectPlanForm
    template_name = "adminpanel/project_plans/form.html"
    success_url = reverse_lazy("adminpanel:content")
    modal_title = "Edit project plan"

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=plans"

    def form_valid(self, form):
        messages.success(self.request, "Project plan updated.")
        return super().form_valid(form)


class ProjectPlanDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = ProjectPlan
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:content")
    success_message = "Project plan “{object}” deleted."

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=plans"


class ProjectPlanPerkCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = ProjectPlanPerk
    form_class = ProjectPlanPerkForm
    template_name = "adminpanel/project_plans/perk_form.html"
    success_url = reverse_lazy("adminpanel:content")
    modal_title = "New shared perk"

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=plans"

    def form_valid(self, form):
        messages.success(self.request, "Perk saved.")
        return super().form_valid(form)


class ProjectPlanPerkUpdateView(AdminRequiredMixin, ModalFormMixin, UpdateView):
    model = ProjectPlanPerk
    form_class = ProjectPlanPerkForm
    template_name = "adminpanel/project_plans/perk_form.html"
    success_url = reverse_lazy("adminpanel:content")
    modal_title = "Edit shared perk"

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=plans"

    def form_valid(self, form):
        messages.success(self.request, "Perk updated.")
        return super().form_valid(form)


class ProjectPlanPerkDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = ProjectPlanPerk
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:content")
    success_message = "Perk “{object}” deleted."

    def get_success_url(self):
        return reverse("adminpanel:content") + "?tab=plans"


# ---------- Notifications ----------
class NotificationHubView(AdminRequiredMixin, TemplateView):
    template_name = "adminpanel/notifications/hub.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = AdminNotificationForm()
        ctx["scheduled"] = ScheduledNotification.objects.all()[:30]
        return ctx


class NotificationSendView(AdminRequiredMixin, View):
    def post(self, request):
        form = AdminNotificationForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please fix the form errors.")
            return redirect(content_url("notifications"))

        data = form.cleaned_data
        scheduled_at = data.get("scheduled_at")
        ids = []
        if data["audience"] == "selected":
            ids = [int(i) for i in data.get("student_ids", "").split(",") if i.strip().isdigit()]

        if scheduled_at and scheduled_at > timezone.now():
            ScheduledNotification.objects.create(
                title=data["title"],
                message=data["message"],
                audience=data["audience"],
                channel=data["channel"],
                status="scheduled",
                scheduled_at=scheduled_at,
                selected_user_ids=ids,
                created_by=request.user,
                link=data.get("link", ""),
            )
            messages.success(request, f"Notification scheduled for {scheduled_at}.")
            return redirect(content_url("notifications"))

        users = _audience_users(data["audience"], data.get("student_ids", ""))
        count = dispatch_notification(
            data["title"],
            data["message"],
            users,
            data["channel"],
            link=data.get("link", ""),
            created_by=request.user,
        )
        ScheduledNotification.objects.create(
            title=data["title"],
            message=data["message"],
            audience=data["audience"],
            channel=data["channel"],
            status="sent",
            scheduled_at=None,
            sent_at=timezone.now(),
            selected_user_ids=ids,
            created_by=request.user,
            link=data.get("link", ""),
        )
        messages.success(request, f"Sent to {count} students.")
        return redirect(content_url("notifications"))


class NotificationDispatchDueView(AdminRequiredMixin, View):
    """Process due scheduled notifications (can also be a Celery beat task)."""

    def post(self, request):
        now = timezone.now()
        due = ScheduledNotification.objects.filter(status="scheduled", scheduled_at__lte=now)
        total = 0
        for item in due:
            if item.audience == "selected":
                users = User.objects.filter(id__in=item.selected_user_ids, role="student")
            else:
                users = _audience_users(item.audience)
            total += dispatch_notification(
                item.title, item.message, users, item.channel, link=item.link
            )
            item.status = "sent"
            item.sent_at = now
            item.save(update_fields=["status", "sent_at", "updated_at"])
        messages.success(request, f"Dispatched scheduled notifications to {total} recipients.")
        return redirect(content_url("notifications"))


# ---------- Reports ----------
class ReportsView(AdminRequiredMixin, TemplateView):
    template_name = "adminpanel/reports/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        month_start = today.replace(day=1)

        daily_regs = list(
            Registration.objects.filter(created_at__date__gte=today - timedelta(days=14))
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        monthly_regs = list(
            Registration.objects.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("-month")[:12]
        )
        monthly_regs.reverse()

        attendance_report = list(
            Attendance.objects.values("status").annotate(count=Count("id")).order_by("status")
        )
        referral_report = list(
            Referral.objects.values("status").annotate(count=Count("id")).order_by("status")
        )
        popular_courses = list(
            CourseEnrollment.objects.exclude(status="cancelled")
            .values("course_id", "course__title")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        popular_classes = list(
            Registration.objects.filter(status="confirmed")
            .values("free_class_id", "free_class__title")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        email_delivery = list(
            EmailLog.objects.values("status").annotate(count=Count("id")).order_by("status")
        )
        revenue = (
            CourseEnrollment.objects.filter(status__in=["paid", "active", "completed"]).aggregate(
                total=Sum("amount_paid")
            )["total"]
            or 0
        )
        if not revenue:
            enrolls = CourseEnrollment.objects.filter(
                status__in=["paid", "active", "completed"]
            ).select_related("course")
            revenue = sum(float(e.course.effective_price) for e in enrolls)

        active_users = User.objects.filter(role="student", is_active=True).count()
        inactive_users = User.objects.filter(role="student", is_active=False).count()
        recent_activity = ActivityLog.objects.select_related("user")[:25]

        # Chart.js payloads with click-through URLs
        charts = {
            "daily": {
                "labels": [r["day"].strftime("%b %d") if r["day"] else "" for r in daily_regs],
                "values": [r["count"] for r in daily_regs],
                "urls": [
                    reverse("adminpanel:classes") + f"?reg_date={r['day'].isoformat()}"
                    for r in daily_regs
                    if r["day"]
                ],
                "tooltips": [
                    f"{r['count']} registration{'s' if r['count'] != 1 else ''} on {r['day'].strftime('%d %b %Y')}"
                    for r in daily_regs
                    if r["day"]
                ],
            },
            "monthly": {
                "labels": [r["month"].strftime("%b %Y") if r["month"] else "" for r in monthly_regs],
                "values": [r["count"] for r in monthly_regs],
                "urls": [
                    reverse("adminpanel:classes") + f"?reg_month={r['month'].strftime('%Y-%m')}"
                    for r in monthly_regs
                    if r["month"]
                ],
                "tooltips": [
                    f"{r['count']} registration{'s' if r['count'] != 1 else ''} in {r['month'].strftime('%B %Y')}"
                    for r in monthly_regs
                    if r["month"]
                ],
            },
            "attendance": {
                "labels": [a["status"].title() for a in attendance_report],
                "values": [a["count"] for a in attendance_report],
                "urls": [
                    reverse("adminpanel:attendance") + f"?status={a['status']}"
                    for a in attendance_report
                ],
                "tooltips": [
                    f"{a['count']} marked as {a['status']}" for a in attendance_report
                ],
            },
            "referrals": {
                "labels": [r["status"].title() for r in referral_report],
                "values": [r["count"] for r in referral_report],
                "urls": [
                    reverse("adminpanel:community") + f"?tab=referrals&status={r['status']}"
                    for r in referral_report
                ],
                "tooltips": [
                    f"{r['count']} {r['status']} referral{'s' if r['count'] != 1 else ''}"
                    for r in referral_report
                ],
            },
            "emails": {
                "labels": [e["status"].title() for e in email_delivery],
                "values": [e["count"] for e in email_delivery],
                "urls": [
                    reverse("adminpanel:tools") + f"?tab=emails&status={e['status']}"
                    for e in email_delivery
                ],
                "tooltips": [
                    f"{e['count']} email{'s' if e['count'] != 1 else ''} — {e['status']}"
                    for e in email_delivery
                ],
            },
            "courses": {
                "labels": [(c["course__title"] or "Untitled")[:28] for c in popular_courses],
                "values": [c["count"] for c in popular_courses],
                "urls": [
                    reverse("adminpanel:courses") + f"?id={c['course_id']}"
                    for c in popular_courses
                ],
                "tooltips": [
                    f"{c['course__title']}: {c['count']} enrollment{'s' if c['count'] != 1 else ''}"
                    for c in popular_courses
                ],
            },
            "classes": {
                "labels": [(c["free_class__title"] or "Untitled")[:28] for c in popular_classes],
                "values": [c["count"] for c in popular_classes],
                "urls": [
                    reverse("adminpanel:classes") + f"?id={c['free_class_id']}"
                    for c in popular_classes
                ],
                "tooltips": [
                    f"{c['free_class__title']}: {c['count']} registration{'s' if c['count'] != 1 else ''}"
                    for c in popular_classes
                ],
            },
            "users": {
                "labels": ["Active", "Inactive"],
                "values": [active_users, inactive_users],
                "urls": [
                    reverse("adminpanel:students") + "?active=1",
                    reverse("adminpanel:students") + "?active=0",
                ],
                "tooltips": [
                    f"{active_users} active student{'s' if active_users != 1 else ''}",
                    f"{inactive_users} inactive student{'s' if inactive_users != 1 else ''}",
                ],
            },
        }

        ctx.update(
            {
                "charts_json": json.dumps(charts),
                "revenue": revenue,
                "active_users": active_users,
                "inactive_users": inactive_users,
                "recent_activity": recent_activity,
                "month_regs_count": Registration.objects.filter(
                    created_at__date__gte=month_start
                ).count(),
                "today_regs_count": Registration.objects.filter(created_at__date=today).count(),
                "avg_attendance": StudentProfile.objects.aggregate(
                    avg=Avg("attendance_percentage")
                )["avg"]
                or 0,
                "students_active_url": reverse("adminpanel:students") + "?active=1",
                "students_inactive_url": reverse("adminpanel:students") + "?active=0",
                "classes_today_url": reverse("adminpanel:classes")
                + f"?reg_date={today.isoformat()}",
                "classes_month_url": reverse("adminpanel:classes")
                + f"?reg_month={today.strftime('%Y-%m')}",
                "courses_url": reverse("adminpanel:courses"),
            }
        )
        return ctx
