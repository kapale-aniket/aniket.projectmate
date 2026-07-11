"""Custom admin panel views."""
from datetime import timedelta
import json
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q, Avg
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.utils.text import slugify
from django.views import View
from django.views.generic import (
    TemplateView,
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    DeleteView,
    FormView,
)
from apps.adminpanel.mixins import AdminRequiredMixin, ModalFormMixin, MessageDeleteMixin
from apps.adminpanel.forms import (
    AdminLoginForm,
    AdminForgotPasswordForm,
    FreeClassForm,
    PaidCourseForm,
    AnnouncementForm,
    StudentEditForm,
    EmailTemplateForm,
    BulkEmailForm,
    SelectedStudentsEmailForm,
    RewardRuleForm,
    AchievementForm,
    BonusPointsForm,
    SiteSettingsForm,
)
from apps.accounts.models import User, StudentProfile, ActivityLog
from apps.accounts.forms import StudentPasswordChangeForm
from apps.classes.models import FreeClass, Registration
from apps.courses.models import PaidCourse, CourseEnrollment
from apps.attendance.models import Attendance
from apps.attendance.services import AttendanceService
from apps.announcements.models import Announcement
from apps.feedback.models import Feedback
from apps.rewards.models import Reward, Achievement, ResumeUpload, RewardRule, StudentAchievement
from apps.rewards.services import RewardService
from apps.referrals.models import Referral
from apps.notifications.models import EmailTemplate, EmailLog, Notification
from apps.notifications.services import EmailService, NotificationService
from apps.core.exports import export_queryset_xlsx, export_simple_pdf
from apps.core.models import SiteSettings
from django.contrib.auth import update_session_auth_hash


class AdminLoginView(LoginView):
    template_name = "adminpanel/login.html"
    authentication_form = AdminLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and (
            user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin"
        ):
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        return reverse("adminpanel:dashboard")

    def form_valid(self, form):
        user = form.get_user()
        if not (user.is_staff or user.is_superuser or user.role == "admin"):
            messages.error(self.request, "You do not have admin access.")
            return self.render_to_response(self.get_context_data(form=form))

        # Browser session only — ends on logout / browser close (no “keep me signed in”)
        response = super().form_valid(form)
        self.request.session.set_expiry(0)
        self.request.session.pop("admin_remember_me", None)
        if self.request.session.pop("admin_temp_password_sent", None):
            messages.info(
                self.request,
                "You’re using a temporary password. Please change it now under your account password settings.",
            )
            return redirect(reverse("adminpanel:password_change"))
        messages.success(self.request, f"Welcome, {user.first_name or 'Admin'}!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Invalid admin credentials.")
        return super().form_invalid(form)


class AdminForgotPasswordView(FormView):
    """Email a temporary password to an admin account; they can change it after login."""

    template_name = "adminpanel/forgot_password.html"
    form_class = AdminForgotPasswordForm
    success_url = reverse_lazy("adminpanel:forgot_password")

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and (
            user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin"
        ):
            return redirect("adminpanel:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data["email"].strip().lower()
        user = (
            User.objects.filter(email__iexact=email)
            .filter(Q(is_staff=True) | Q(is_superuser=True) | Q(role="admin"))
            .first()
        )

        # Always show the same message (do not reveal whether the email exists).
        generic_msg = (
            "If that email belongs to an admin account, a temporary password has been sent. "
            "Sign in with it, then change your password."
        )

        if user:
            from django.utils.crypto import get_random_string

            temp_password = "Pm-" + get_random_string(
                10, allowed_chars="abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            )
            user.set_password(temp_password)
            user.save(update_fields=["password"])

            site = SiteSettings.load()
            site_name = getattr(site, "site_name", None) or "Aniket.ProjectMate"
            contact = getattr(site, "contact_email", "") or "backendbyaniket@gmail.com"
            name = user.get_full_name() or user.email
            login_url = self.request.build_absolute_uri(reverse("adminpanel:login"))
            change_url = self.request.build_absolute_uri(reverse("adminpanel:password_change"))

            EmailService.send_plain(
                to_email=user.email,
                subject=f"Your temporary admin password — {site_name}",
                body_text=(
                    f"Hi {name},\n\n"
                    f"You requested a password reset for the {site_name} admin panel.\n\n"
                    f"Your temporary password is:\n{temp_password}\n\n"
                    f"Sign in here:\n{login_url}\n\n"
                    f"After signing in, change your password here:\n{change_url}\n\n"
                    f"If you did not request this, contact {contact} immediately."
                ),
                recipient=user,
                meta={"kind": "admin_temp_password"},
            )
            ActivityLog.objects.create(
                user=user,
                action="admin_temp_password",
                description="Temporary admin password emailed via forgot password",
                ip_address=self.request.META.get("REMOTE_ADDR"),
            )
            self.request.session["admin_temp_password_sent"] = True

        messages.success(self.request, generic_msg)
        return redirect(reverse("adminpanel:login") + "?reset=1")

    def form_invalid(self, form):
        messages.error(self.request, "Please enter a valid email address.")
        return super().form_invalid(form)


class AdminLogoutView(View):
    """Sign out without CSRF — GET or POST both clear the session and redirect to login."""

    def post(self, request):
        return self._logout(request)

    def get(self, request):
        return self._logout(request)

    def dispatch(self, request, *args, **kwargs):
        # Avoid 403 "Session expired" when the admin page CSRF token is stale
        return super().dispatch(request, *args, **kwargs)

    def _logout(self, request):
        logout(request)
        try:
            request.session.flush()
        except Exception:
            pass
        response = redirect(reverse("adminpanel:login") + "?logged_out=1")
        patch_cache_control(
            response,
            no_cache=True,
            no_store=True,
            must_revalidate=True,
            private=True,
            max_age=0,
        )
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        # Ensure the browser drops the old session id
        response.delete_cookie(
            settings.SESSION_COOKIE_NAME,
            path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
            domain=getattr(settings, "SESSION_COOKIE_DOMAIN", None) or None,
            samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
        )
        return response


class AdminPasswordChangeView(AdminRequiredMixin, FormView):
    template_name = "adminpanel/password_change.html"
    form_class = StudentPasswordChangeForm
    success_url = reverse_lazy("adminpanel:password_change")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)
        changed_at = timezone.localtime().strftime("%d %b %Y, %I:%M %p")
        site = SiteSettings.load()
        contact = getattr(site, "contact_email", "") or "backendbyaniket@gmail.com"
        name = user.get_full_name() or user.email
        EmailService.send_from_template(
            "password_changed",
            user.email,
            {
                "student_name": name,
                "changed_at": changed_at,
                "contact_email": contact,
                "subject": "Your ProjectMate password was changed",
                "body_html": (
                    f"<p>Hi {name},</p>"
                    f"<p>Your admin account password was changed on {changed_at}.</p>"
                    f"<p>If this wasn’t you, contact {contact} immediately.</p>"
                ),
            },
            recipient=user,
        )
        ActivityLog.objects.create(
            user=user,
            action="password_changed",
            description="Admin changed their password",
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )
        messages.success(
            self.request,
            "Password updated. You are still logged in. A confirmation email was sent.",
        )
        return super().form_valid(form)


class DashboardView(AdminRequiredMixin, TemplateView):
    template_name = "adminpanel/dashboard.html"

    def get_context_data(self, **kwargs):
        from apps.classes.services import ClassStatusService

        ClassStatusService.sync_all()
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        students = User.objects.filter(role="student")
        free_regs = Registration.objects.filter(status="confirmed")
        paid_enrolls = CourseEnrollment.objects.exclude(status="cancelled")
        paid_revenue = (
            CourseEnrollment.objects.filter(status__in=["paid", "active", "completed"]).aggregate(
                total=Sum("amount_paid")
            )["total"]
            or 0
        )
        estimated = (
            CourseEnrollment.objects.filter(status__in=["paid", "active", "completed", "pending_payment"])
            .select_related("course")
        )
        revenue = paid_revenue
        if not revenue:
            revenue = sum(
                float(e.course.effective_price)
                for e in estimated
                if e.status in ("paid", "active", "completed")
            )

        attendance_avg = (
            StudentProfile.objects.aggregate(avg=Avg("attendance_percentage"))["avg"] or 0
        )

        # Last 14 days — CSS bar strip instead of a chart
        day_counts = {
            g["day"]: g["count"]
            for g in students.annotate(day=TruncDate("date_joined"))
            .values("day")
            .annotate(count=Count("id"))
            .filter(day__gte=today - timedelta(days=13))
        }
        growth_days = []
        max_day = 1
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            count = day_counts.get(d, 0)
            max_day = max(max_day, count)
            growth_days.append(
                {
                    "date": d,
                    "label": d.strftime("%a"),
                    "day_num": d.strftime("%d"),
                    "count": count,
                    "is_today": d == today,
                }
            )
        for item in growth_days:
            item["height"] = max(8, int(round((item["count"] / max_day) * 100))) if max_day else 8

        week_start = today - timedelta(days=today.weekday())
        prev_week_start = week_start - timedelta(days=7)
        week_new = students.filter(date_joined__date__gte=week_start).count()
        prev_week_new = students.filter(
            date_joined__date__gte=prev_week_start,
            date_joined__date__lt=week_start,
        ).count()
        if prev_week_new:
            week_delta_pct = round(((week_new - prev_week_new) / prev_week_new) * 100)
        else:
            week_delta_pct = 100 if week_new else 0

        recent_students = (
            StudentProfile.objects.select_related("user")
            .filter(user__role="student")
            .order_by("-user__date_joined")[:6]
        )

        ctx.update(
            {
                "total_students": students.count(),
                "total_free_regs": free_regs.count(),
                "total_paid_enrolls": paid_enrolls.count(),
                "today_regs": free_regs.filter(created_at__date=today).count()
                + paid_enrolls.filter(created_at__date=today).count(),
                "upcoming_classes": FreeClass.objects.filter(
                    status__in=["upcoming", "live"], date__gte=today
                ).order_by("date")[:6],
                "attendance_avg": round(float(attendance_avg), 1),
                "revenue": revenue,
                "growth_days": growth_days,
                "week_new": week_new,
                "prev_week_new": prev_week_new,
                "week_delta_pct": week_delta_pct,
                "new_today": students.filter(date_joined__date=today).count(),
                "recent_students": recent_students,
                "recent_activities": ActivityLog.objects.select_related("user")[:8],
                "pending_resumes": ResumeUpload.objects.filter(status="pending").count(),
                "pending_feedback": Feedback.objects.filter(status="pending").count(),
                "pending_referrals": Referral.objects.filter(status="pending").count(),
            }
        )
        return ctx


# ---------- Students ----------
def _student_profile_queryset(request):
    """Shared filtered queryset for student list + select-all IDs."""
    qs = StudentProfile.objects.select_related("user").filter(user__role="student")
    q = request.GET.get("q", "").strip()
    college = request.GET.get("college", "").strip()
    year = request.GET.get("year", "").strip()
    course = request.GET.get("course", "").strip()
    active = request.GET.get("active", "").strip()
    if q:
        qs = qs.filter(
            Q(user__email__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(phone__icontains=q)
        )
    if college:
        qs = qs.filter(
            Q(college__icontains=college) | Q(college_location__icontains=college)
        )
    if year:
        qs = qs.filter(year=year)
    if course:
        qs = qs.filter(
            Q(user__registrations__free_class__technology__icontains=course)
            | Q(user__enrollments__course__technology__icontains=course)
        ).distinct()
    if active in ("1", "true", "yes"):
        qs = qs.filter(user__is_active=True)
    elif active in ("0", "false", "no"):
        qs = qs.filter(user__is_active=False)
    return qs.order_by("-created_at")


class StudentListView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/students/list.html"
    context_object_name = "profiles"
    paginate_by = 10

    def get_queryset(self):
        return _student_profile_queryset(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["colleges"] = (
            StudentProfile.objects.exclude(college="")
            .values_list("college", flat=True)
            .distinct()[:50]
        )
        ctx["years"] = StudentProfile.YEAR_CHOICES
        ctx["active_filter"] = self.request.GET.get("active", "")
        ctx["bulk_mail_form"] = SelectedStudentsEmailForm()
        ctx["students_ids_url"] = reverse("adminpanel:students_ids")
        # Preserve filter query for select-all endpoint
        ctx["filter_query"] = self.request.GET.urlencode()
        return ctx


class StudentIdsView(AdminRequiredMixin, View):
    """Return all student profile IDs matching current filters (for select-all)."""

    def get(self, request):
        ids = list(_student_profile_queryset(request).values_list("pk", flat=True))
        return JsonResponse({"ids": ids, "count": len(ids)})


class StudentDetailView(AdminRequiredMixin, DetailView):
    template_name = "adminpanel/students/detail.html"
    context_object_name = "profile"
    model = StudentProfile

    def get_template_names(self):
        if self.is_htmx():
            return ["adminpanel/students/detail_modal.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.object.user
        ctx.update(
            {
                "registrations": Registration.objects.filter(student=user).select_related("free_class")[:20],
                "attendance": Attendance.objects.filter(student=user).select_related("free_class")[:20],
                "rewards": Reward.objects.filter(student=user)[:20],
                "referrals": Referral.objects.filter(referrer=user).select_related("referred_user")[:20],
                "enrollments": CourseEnrollment.objects.filter(student=user).select_related("course")[:20],
            }
        )
        return ctx


class StudentEditView(AdminRequiredMixin, ModalFormMixin, UpdateView):
    model = StudentProfile
    form_class = StudentEditForm
    template_name = "adminpanel/students/form.html"
    modal_title = "Edit student"
    form_multipart = False

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.object.user
        return kwargs

    def get_success_url(self):
        return reverse("adminpanel:students")

    def form_valid(self, form):
        messages.success(self.request, "Student updated.")
        return super().form_valid(form)


class StudentToggleActiveView(AdminRequiredMixin, View):
    """Activate or deactivate a single student from the row action."""

    def post(self, request, pk):
        profile = get_object_or_404(StudentProfile, pk=pk)
        set_active = request.POST.get("set_active")
        if set_active in ("1", "true", "yes"):
            profile.user.is_active = True
        elif set_active in ("0", "false", "no"):
            profile.user.is_active = False
        else:
            profile.user.is_active = not profile.user.is_active
        profile.user.save(update_fields=["is_active"])
        messages.success(
            request,
            f"Account {'activated' if profile.user.is_active else 'deactivated'}.",
        )
        return redirect("adminpanel:students")


class StudentDeleteView(AdminRequiredMixin, DeleteView):
    model = StudentProfile
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:students")

    def form_valid(self, form):
        profile = self.get_object()
        email = profile.user.email
        profile.user.delete()
        messages.success(self.request, f"Deleted {email}")
        return redirect(self.success_url)


class StudentBulkActionView(AdminRequiredMixin, View):
    """Deactivate, activate, or delete multiple selected students."""

    def post(self, request):
        action = (request.POST.get("action") or "").strip()
        raw_ids = request.POST.getlist("selected")
        ids = [int(i) for i in raw_ids if str(i).isdigit()]
        profiles = StudentProfile.objects.select_related("user").filter(
            pk__in=ids, user__role="student"
        )
        count = profiles.count()
        if not count:
            messages.error(request, "Select at least one student.")
            return redirect("adminpanel:students")

        if action == "deactivate":
            User.objects.filter(pk__in=profiles.values_list("user_id", flat=True)).update(is_active=False)
            messages.success(request, f"Deactivated {count} student(s).")
        elif action == "activate":
            User.objects.filter(pk__in=profiles.values_list("user_id", flat=True)).update(is_active=True)
            messages.success(request, f"Activated {count} student(s).")
        elif action == "delete":
            user_ids = list(profiles.values_list("user_id", flat=True))
            deleted, _ = User.objects.filter(pk__in=user_ids, role="student").delete()
            messages.success(request, f"Deleted {count} student(s).")
        else:
            messages.error(request, "Unknown bulk action.")
        return redirect("adminpanel:students")


class StudentBulkEmailView(AdminRequiredMixin, FormView):
    """Send email to students selected on the list page."""

    form_class = SelectedStudentsEmailForm
    template_name = "adminpanel/students/bulk_email.html"
    success_url = reverse_lazy("adminpanel:students")

    def form_valid(self, form):
        raw = form.cleaned_data["selected_ids"]
        ids = [int(i) for i in raw.replace(" ", "").split(",") if i.isdigit()]
        profiles = StudentProfile.objects.select_related("user").filter(
            pk__in=ids, user__role="student"
        )
        if not profiles.exists():
            messages.error(self.request, "No valid students selected.")
            return redirect("adminpanel:students")

        sent = 0
        for profile in profiles:
            EmailService.send_plain(
                to_email=profile.user.email,
                subject=form.cleaned_data["subject"],
                body_text=form.cleaned_data["body_text"],
                recipient=profile.user,
            )
            sent += 1
        messages.success(self.request, f"Sent email to {sent} student(s).")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please fix the email form and try again.")
        return redirect("adminpanel:students")


class StudentExportView(AdminRequiredMixin, View):
    def get(self, request):
        fmt = request.GET.get("format", "xlsx")
        qs = StudentProfile.objects.select_related("user").filter(user__role="student")
        if fmt == "pdf":
            lines = [
                f"{p.user.email} | {p.user.get_full_name()} | {p.college} | {p.year} | pts:{p.reward_points}"
                for p in qs[:500]
            ]
            return export_simple_pdf("Students Export", lines, "students.pdf")
        return export_queryset_xlsx(
            qs,
            "students.xlsx",
            [
                ("Email", "user.email"),
                ("Name", "user.get_full_name"),
                ("Phone", "phone"),
                ("College", "college"),
                ("College location", "college_location"),
                ("Year", "year"),
                ("City", "city"),
                ("Points", "reward_points"),
                ("Active", "user.is_active"),
            ],
        )


class StudentEmailView(AdminRequiredMixin, FormView):
    template_name = "adminpanel/students/email.html"
    form_class = BulkEmailForm

    def dispatch(self, request, *args, **kwargs):
        self.profile = get_object_or_404(StudentProfile, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profile"] = self.profile
        return ctx

    def get_initial(self):
        return {"audience": "selected", "student_ids": str(self.profile.user_id)}

    def form_valid(self, form):
        EmailService.send_plain(
            to_email=self.profile.user.email,
            subject=form.cleaned_data["subject"],
            body_text=form.cleaned_data["body_text"],
            recipient=self.profile.user,
        )
        messages.success(self.request, f"Email sent to {self.profile.user.email}")
        return redirect("adminpanel:students")


# ---------- Free Classes ----------
class FreeClassListView(AdminRequiredMixin, ListView):
    model = FreeClass
    template_name = "adminpanel/classes/list.html"
    context_object_name = "classes"
    paginate_by = 10

    def get_queryset(self):
        from apps.classes.services import ClassStatusService

        ClassStatusService.sync_all()
        qs = FreeClass.objects.annotate(
            attendance_count=Count("attendance_records", distinct=True)
        )
        q = self.request.GET.get("q", "").strip()
        date = self.request.GET.get("date", "").strip()
        status = self.request.GET.get("status", "").strip()
        reg_date = self.request.GET.get("reg_date", "").strip()
        reg_month = self.request.GET.get("reg_month", "").strip()
        pk = self.request.GET.get("id", "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(technology__icontains=q))
        if date:
            qs = qs.filter(date=date)
        if status:
            qs = qs.filter(status=status)
        if pk.isdigit():
            qs = qs.filter(pk=int(pk))
        if reg_date:
            qs = qs.filter(registrations__created_at__date=reg_date).distinct()
        if reg_month:
            try:
                year, month = reg_month.split("-")[:2]
                qs = qs.filter(
                    registrations__created_at__year=int(year),
                    registrations__created_at__month=int(month),
                ).distinct()
            except (ValueError, TypeError):
                pass
        return qs.order_by("-date", "-start_time")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_q"] = self.request.GET.get("q", "")
        ctx["filter_status"] = self.request.GET.get("status", "")
        ctx["filter_reg_date"] = self.request.GET.get("reg_date", "")
        ctx["filter_reg_month"] = self.request.GET.get("reg_month", "")
        ctx["status_choices"] = FreeClass.Status.choices
        return ctx


class FreeClassCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = FreeClass
    form_class = FreeClassForm
    template_name = "adminpanel/classes/form.html"
    success_url = reverse_lazy("adminpanel:classes")
    modal_title = "Create free class"

    def form_valid(self, form):
        messages.success(self.request, "Free class created.")
        return super().form_valid(form)


class FreeClassUpdateView(AdminRequiredMixin, ModalFormMixin, UpdateView):
    model = FreeClass
    form_class = FreeClassForm
    template_name = "adminpanel/classes/form.html"
    success_url = reverse_lazy("adminpanel:classes")
    modal_title = "Edit free class"

    def form_valid(self, form):
        messages.success(self.request, "Class updated.")
        return super().form_valid(form)


class FreeClassDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = FreeClass
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:classes")
    success_message = "Class “{object}” deleted."


class FreeClassCancelView(AdminRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(FreeClass, pk=pk)
        if obj.status != FreeClass.Status.UPCOMING:
            messages.error(
                request,
                "Only upcoming classes can be cancelled.",
            )
            return redirect("adminpanel:classes")
        obj.status = FreeClass.Status.CANCELLED
        obj.registration_enabled = False
        obj.save(update_fields=["status", "registration_enabled", "updated_at"])
        messages.warning(request, f"Cancelled: {obj.title}")
        return redirect("adminpanel:classes")


class FreeClassGoLiveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.classes.services import ClassStatusService
        from django.core.exceptions import ValidationError

        obj = get_object_or_404(FreeClass, pk=pk)
        try:
            sent = ClassStatusService.go_live(obj)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
            return redirect("adminpanel:classes")
        messages.success(
            request,
            f"“{obj.title}” is live. Join-now email sent to {sent} registered student(s).",
        )
        return redirect("adminpanel:classes")


class FreeClassDuplicateView(AdminRequiredMixin, View):
    def post(self, request, pk):
        src = get_object_or_404(FreeClass, pk=pk)
        if src.status not in (FreeClass.Status.COMPLETED, FreeClass.Status.CANCELLED):
            messages.error(request, "Only completed or cancelled classes can be duplicated.")
            return redirect("adminpanel:classes")
        src.pk = None
        src.slug = f"{slugify(src.title)[:160]}-{timezone.now().strftime('%m%d%H%M')}"
        src.status = FreeClass.Status.UPCOMING
        src.date = timezone.localdate() + timedelta(days=7)
        src.registration_enabled = True
        src.save()
        messages.success(request, f"Duplicated as {src.title}")
        return redirect("adminpanel:classes")


class FreeClassToggleRegView(AdminRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(FreeClass, pk=pk)
        if obj.status != FreeClass.Status.UPCOMING:
            messages.error(request, "Registration can only be turned on/off for upcoming classes.")
            return redirect("adminpanel:classes")
        obj.registration_enabled = not obj.registration_enabled
        obj.save(update_fields=["registration_enabled", "updated_at"])
        messages.info(request, f"Registrations {'enabled' if obj.registration_enabled else 'disabled'}.")
        return redirect("adminpanel:classes")


# ---------- Paid Courses ----------
class CourseListView(AdminRequiredMixin, ListView):
    model = PaidCourse
    template_name = "adminpanel/courses/list.html"
    context_object_name = "courses"
    paginate_by = 10

    def get_queryset(self):
        qs = PaidCourse.objects.all()
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        featured = self.request.GET.get("featured", "").strip()
        pk = self.request.GET.get("id", "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(technology__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if featured in ("1", "true", "yes"):
            qs = qs.filter(is_featured=True)
        elif featured in ("0", "false", "no"):
            qs = qs.filter(is_featured=False)
        if pk.isdigit():
            qs = qs.filter(pk=int(pk))
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_q"] = self.request.GET.get("q", "")
        ctx["filter_status"] = self.request.GET.get("status", "")
        ctx["filter_featured"] = self.request.GET.get("featured", "")
        ctx["status_choices"] = PaidCourse.Status.choices
        return ctx


class CourseCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = PaidCourse
    form_class = PaidCourseForm
    template_name = "adminpanel/courses/form.html"
    success_url = reverse_lazy("adminpanel:courses")
    modal_title = "Create course"

    def form_valid(self, form):
        messages.success(self.request, "Course created.")
        return super().form_valid(form)


class CourseUpdateView(AdminRequiredMixin, ModalFormMixin, UpdateView):
    model = PaidCourse
    form_class = PaidCourseForm
    template_name = "adminpanel/courses/form.html"
    success_url = reverse_lazy("adminpanel:courses")
    modal_title = "Edit course"

    def form_valid(self, form):
        messages.success(self.request, "Course updated.")
        return super().form_valid(form)


class CourseDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = PaidCourse
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:courses")
    success_message = "Course “{object}” deleted."


class CourseToggleFeaturedView(AdminRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(PaidCourse, pk=pk)
        obj.is_featured = not obj.is_featured
        obj.save(update_fields=["is_featured", "updated_at"])
        messages.success(
            request,
            f"“{obj.title}” {'marked featured' if obj.is_featured else 'unfeatured'}.",
        )
        return redirect("adminpanel:courses")


class CourseToggleStatusView(AdminRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(PaidCourse, pk=pk)
        obj.status = (
            PaidCourse.Status.ARCHIVED
            if obj.status == PaidCourse.Status.PUBLISHED
            else PaidCourse.Status.PUBLISHED
        )
        obj.save(update_fields=["status", "updated_at"])
        messages.success(request, f"“{obj.title}” is now {obj.get_status_display()}.")
        return redirect("adminpanel:courses")


# ---------- Attendance ----------
class AttendanceHubView(AdminRequiredMixin, TemplateView):
    template_name = "adminpanel/attendance/hub.html"

    def get_context_data(self, **kwargs):
        from apps.classes.services import ClassStatusService
        from apps.adminpanel.pagination import paginate_queryset

        ClassStatusService.sync_all()
        ctx = super().get_context_data(**kwargs)
        status = self.request.GET.get("status", "").strip()
        classes_qs = (
            FreeClass.objects.exclude(status="draft")
            .annotate(attendance_count=Count("attendance_records", distinct=True))
            .order_by("-date")
        )
        records = Attendance.objects.select_related("student", "free_class").order_by("-created_at")
        if status:
            records = records.filter(status=status)
            classes_qs = (
                FreeClass.objects.filter(attendance_records__status=status)
                .annotate(attendance_count=Count("attendance_records", distinct=True))
                .distinct()
                .order_by("-date")
            )
        page_obj = paginate_queryset(self.request, classes_qs)
        records_page = paginate_queryset(self.request, records, page_param="rpage")
        ctx.update(
            {
                "classes": page_obj,
                "page_obj": page_obj,
                "status_filter": status,
                "attendance_records": records_page if status else [],
                "records_page": records_page if status else None,
                "top_attendees": StudentProfile.objects.select_related("user").order_by(
                    "-consecutive_attendance", "-attendance_percentage"
                )[:15],
            }
        )
        return ctx


class AttendanceMarkView(AdminRequiredMixin, TemplateView):
    template_name = "adminpanel/attendance/mark.html"
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        free_class = get_object_or_404(FreeClass, pk=kwargs["pk"])
        if not free_class.can_mark_attendance:
            if free_class.status == FreeClass.Status.CANCELLED:
                messages.error(request, "Cannot mark attendance for a cancelled class.")
            else:
                end = timezone.localtime(free_class.datetime_end)
                messages.warning(
                    request,
                    f"Attendance opens after the class ends ({end.strftime('%d %b %Y, %I:%M %p')}).",
                )
            return redirect("adminpanel:attendance")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        free_class = get_object_or_404(FreeClass, pk=kwargs["pk"])
        regs = Registration.objects.filter(
            free_class=free_class, status="confirmed"
        ).select_related("student", "student__profile").order_by("student__email")
        existing = {
            a.student_id: a
            for a in Attendance.objects.filter(free_class=free_class)
        }
        paginator = Paginator(regs, self.paginate_by)
        page_number = self.request.GET.get("page") or 1
        page_obj = paginator.get_page(page_number)
        ctx.update(
            {
                "free_class": free_class,
                "page_obj": page_obj,
                "is_paginated": page_obj.has_other_pages(),
                "total_students": paginator.count,
                "rows": [
                    {"reg": r, "attendance": existing.get(r.student_id)}
                    for r in page_obj.object_list
                ],
            }
        )
        return ctx

    def post(self, request, pk):
        free_class = get_object_or_404(FreeClass, pk=pk)
        if not free_class.can_mark_attendance:
            messages.error(request, "Attendance can only be marked after the class ends.")
            return redirect("adminpanel:attendance")
        for key, value in request.POST.items():
            if key.startswith("status_"):
                student_id = int(key.replace("status_", ""))
                student = get_object_or_404(User, pk=student_id)
                AttendanceService.mark(
                    student,
                    free_class,
                    value,
                    marked_by=request.user,
                )
        messages.success(request, "Attendance saved.")
        return redirect("adminpanel:attendance")


class AttendanceExportView(AdminRequiredMixin, View):
    def get(self, request, pk):
        free_class = get_object_or_404(FreeClass, pk=pk)
        qs = Attendance.objects.filter(free_class=free_class).select_related("student")
        return export_queryset_xlsx(
            qs,
            f"attendance-{free_class.slug}.xlsx",
            [
                ("Email", "student.email"),
                ("Status", "status"),
                ("Join", "join_time"),
                ("Leave", "leave_time"),
            ],
        )


# ---------- Announcements ----------
class AnnouncementListView(AdminRequiredMixin, ListView):
    model = Announcement
    template_name = "adminpanel/announcements/list.html"
    context_object_name = "announcements"
    paginate_by = 10


class AnnouncementCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "adminpanel/announcements/form.html"
    success_url = reverse_lazy("adminpanel:content")
    modal_title = "New announcement"

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.published_at = timezone.now()
        messages.success(self.request, "Announcement published.")
        return super().form_valid(form)


class AnnouncementUpdateView(AdminRequiredMixin, ModalFormMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = "adminpanel/announcements/form.html"
    success_url = reverse_lazy("adminpanel:content")
    modal_title = "Edit announcement"

    def form_valid(self, form):
        messages.success(self.request, "Announcement updated.")
        return super().form_valid(form)


class AnnouncementDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = Announcement
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:content")
    success_message = "Announcement “{object}” deleted."


# ---------- Feedback / Resume ----------
class FeedbackModerationView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/feedback/list.html"
    context_object_name = "items"
    paginate_by = 10

    def get_queryset(self):
        status = self.request.GET.get("status", "pending")
        qs = Feedback.objects.select_related("student", "free_class").order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        from apps.feedback.services import FeedbackService

        ctx = super().get_context_data(**kwargs)
        for fb in ctx["items"]:
            ok, reason = FeedbackService.can_approve(fb)
            fb.can_approve = ok
            fb.approve_block_reason = reason
            att = FeedbackService.get_attendance(fb.student, fb.free_class)
            fb.attendance_status = att.status if att else ""
            fb.attendance_label = att.get_status_display() if att else "Not marked"
        return ctx


class FeedbackApproveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.feedback.services import FeedbackService

        fb = get_object_or_404(Feedback, pk=pk)
        ok, reason = FeedbackService.can_approve(fb)
        if not ok:
            messages.error(request, reason or "This feedback cannot be approved.")
            return redirect(reverse("adminpanel:community") + "?tab=feedback")
        fb.status = "approved"
        fb.reviewed_by = request.user
        fb.save(update_fields=["status", "reviewed_by", "updated_at"])
        messages.success(request, "Feedback approved. Use Show on UI to publish publicly.")
        return redirect(reverse("adminpanel:community") + "?tab=feedback")


class FeedbackRejectView(AdminRequiredMixin, View):
    def post(self, request, pk):
        fb = get_object_or_404(Feedback, pk=pk)
        fb.status = "rejected"
        fb.reviewed_by = request.user
        fb.save(update_fields=["status", "reviewed_by", "updated_at"])
        messages.warning(request, "Feedback rejected.")
        return redirect(reverse("adminpanel:community") + "?tab=feedback")


class ResumeListView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/resumes/list.html"
    context_object_name = "uploads"
    queryset = ResumeUpload.objects.select_related("student").order_by("-created_at")
    paginate_by = 10


class ResumeReviewView(AdminRequiredMixin, View):
    def post(self, request, pk):
        upload = get_object_or_404(ResumeUpload, pk=pk)
        feedback = request.POST.get("feedback", "").strip()
        score = request.POST.get("score") or None
        from apps.rewards.models import ResumeReview

        ResumeReview.objects.create(
            resume_upload=upload,
            reviewer=request.user,
            feedback=feedback,
            score=int(score) if score else None,
        )
        upload.status = "completed"
        upload.save(update_fields=["status", "updated_at"])
        EmailService.send_from_template(
            "resume_feedback",
            upload.student.email,
            {"student_name": upload.student.get_full_name() or upload.student.email},
            recipient=upload.student,
        )
        messages.success(request, "Resume review saved & emailed.")
        return redirect(reverse("adminpanel:community") + "?tab=resumes")


# ---------- Email ----------
class EmailTemplateListView(AdminRequiredMixin, ListView):
    model = EmailTemplate
    template_name = "adminpanel/emails/templates.html"
    context_object_name = "templates"
    paginate_by = 10


class EmailTemplateUpdateView(AdminRequiredMixin, ModalFormMixin, UpdateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = "adminpanel/emails/template_form.html"
    success_url = reverse_lazy("adminpanel:tools")
    modal_title = "Edit email template"
    form_multipart = False

    def get_template_names(self):
        if self.is_htmx():
            return ["adminpanel/emails/template_form_modal.html"]
        return super().get_template_names()

    def get_success_url(self):
        return reverse("adminpanel:tools") + "?tab=emails"

    def form_valid(self, form):
        messages.success(self.request, "Email template updated. HTML layout regenerated.")
        return super().form_valid(form)


class EmailTemplateCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = "adminpanel/emails/template_form.html"
    success_url = reverse_lazy("adminpanel:tools")
    modal_title = "New email template"
    form_multipart = False

    def get_template_names(self):
        if self.is_htmx():
            return ["adminpanel/emails/template_form_modal.html"]
        return super().get_template_names()

    def get_success_url(self):
        return reverse("adminpanel:tools") + "?tab=emails"

    def form_valid(self, form):
        messages.success(self.request, "Email template created. HTML layout generated.")
        return super().form_valid(form)


class EmailPreviewView(AdminRequiredMixin, View):
    """Generate branded HTML from plain text and return a preview fragment."""

    def post(self, request):
        subject = (request.POST.get("subject") or "Preview").strip()
        body_text = (request.POST.get("body_text") or "").strip()
        if not body_text:
            return render(
                request,
                "adminpanel/emails/preview_partial.html",
                {"error": "Write a message first, then generate the preview."},
            )
        body_html, _ = EmailService.build_html_from_text(subject, body_text)
        return render(
            request,
            "adminpanel/emails/preview_partial.html",
            {
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "preview_ok": True,
            },
        )


class BulkEmailView(AdminRequiredMixin, FormView):
    template_name = "adminpanel/emails/bulk.html"
    form_class = BulkEmailForm
    success_url = reverse_lazy("adminpanel:tools")

    def get_success_url(self):
        return reverse("adminpanel:tools") + "?tab=emails"

    def form_valid(self, form):
        audience = form.cleaned_data["audience"]
        users = User.objects.filter(role="student")
        if audience == "active":
            users = users.filter(is_active=True)
        elif audience == "selected":
            ids = [i.strip() for i in form.cleaned_data.get("student_ids", "").split(",") if i.strip()]
            users = users.filter(id__in=ids)
        count = 0
        for user in users:
            EmailService.send_plain(
                to_email=user.email,
                subject=form.cleaned_data["subject"],
                body_text=form.cleaned_data["body_text"],
                recipient=user,
            )
            count += 1
        messages.success(self.request, f"Sent {count} emails.")
        return super().form_valid(form)


class EmailLogListView(AdminRequiredMixin, ListView):
    model = EmailLog
    template_name = "adminpanel/emails/logs.html"
    context_object_name = "logs"
    paginate_by = 10


class SendRemindersView(AdminRequiredMixin, View):
    def post(self, request):
        from apps.notifications.tasks import send_class_reminders

        sent = send_class_reminders()
        messages.success(request, f"Reminder task finished. Sent: {sent}")
        return redirect(reverse("adminpanel:tools") + "?tab=emails")


# ---------- Rewards ----------
class RewardsHubView(AdminRequiredMixin, TemplateView):
    template_name = "adminpanel/rewards/hub.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rules"] = RewardRule.objects.all()
        ctx["achievements"] = Achievement.objects.all()
        ctx["leaderboard"] = StudentProfile.objects.select_related("user").order_by("-reward_points")[:30]
        ctx["bonus_form"] = BonusPointsForm()
        ctx["rule_form"] = RewardRuleForm()
        return ctx


class RewardRuleCreateView(AdminRequiredMixin, View):
    def post(self, request):
        form = RewardRuleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Reward rule saved.")
        else:
            messages.error(request, "Could not save rule.")
        return redirect(reverse("adminpanel:tools") + "?tab=rewards")


class RewardRuleUpdateView(AdminRequiredMixin, UpdateView):
    model = RewardRule
    form_class = RewardRuleForm
    template_name = "adminpanel/rewards/rule_form.html"
    success_url = reverse_lazy("adminpanel:tools")


class AchievementCreateView(AdminRequiredMixin, ModalFormMixin, CreateView):
    model = Achievement
    form_class = AchievementForm
    template_name = "adminpanel/rewards/achievement_form.html"
    success_url = reverse_lazy("adminpanel:tools")
    modal_title = "Add achievement badge"
    form_multipart = True

    def get_success_url(self):
        return reverse("adminpanel:tools") + "?tab=rewards"

    def form_valid(self, form):
        messages.success(self.request, "Achievement badge created.")
        return super().form_valid(form)


class AchievementDeleteView(AdminRequiredMixin, MessageDeleteMixin, DeleteView):
    model = Achievement
    template_name = "adminpanel/confirm_delete.html"
    success_url = reverse_lazy("adminpanel:tools")
    success_message = "Achievement “{object}” removed."

    def get_success_url(self):
        return reverse("adminpanel:tools") + "?tab=rewards"


class BonusPointsView(AdminRequiredMixin, View):
    def post(self, request):
        form = BonusPointsForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid bonus form.")
            return redirect(reverse("adminpanel:tools") + "?tab=rewards")
        try:
            user = User.objects.get(email__iexact=form.cleaned_data["student_email"])
        except User.DoesNotExist:
            messages.error(request, "Student not found.")
            return redirect(reverse("adminpanel:tools") + "?tab=rewards")
        pts = form.cleaned_data["points"]
        RewardService.award_points(
            user,
            "manual",
            points=pts,
            description=form.cleaned_data.get("description") or "Admin adjustment",
        )
        messages.success(request, f"{pts:+d} points for {user.email}")
        return redirect(reverse("adminpanel:tools") + "?tab=rewards")


class ResetLeaderboardView(AdminRequiredMixin, View):
    def post(self, request):
        StudentProfile.objects.update(reward_points=0, level=1)
        Reward.objects.all().delete()
        StudentAchievement.objects.all().delete()
        messages.warning(request, "Leaderboard reset.")
        return redirect(reverse("adminpanel:tools") + "?tab=rewards")


class ReferralListView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/referrals/list.html"
    context_object_name = "referrals"
    queryset = Referral.objects.select_related("referrer", "referred_user").order_by("-created_at")
    paginate_by = 10


class ReferralApproveView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.referrals.services import ReferralService

        ref = get_object_or_404(Referral, pk=pk)
        ReferralService.approve(ref, request.user)
        messages.success(request, "Referral approved.")
        return redirect(reverse("adminpanel:community") + "?tab=referrals")


class ReferralRejectView(AdminRequiredMixin, View):
    def post(self, request, pk):
        from apps.referrals.services import ReferralService

        ref = get_object_or_404(Referral, pk=pk)
        ReferralService.reject(ref, request.user)
        messages.warning(request, "Referral rejected.")
        return redirect(reverse("adminpanel:community") + "?tab=referrals")


class SiteSettingsUpdateView(AdminRequiredMixin, UpdateView):
    """Edit About page + public site content from the admin panel."""

    model = SiteSettings
    form_class = SiteSettingsForm
    template_name = "adminpanel/settings/edit.html"
    success_url = reverse_lazy("adminpanel:settings")

    def get_object(self, queryset=None):
        return SiteSettings.load()

    def form_valid(self, form):
        messages.success(self.request, "Site settings saved. About page and public site updated.")
        return super().form_valid(form)