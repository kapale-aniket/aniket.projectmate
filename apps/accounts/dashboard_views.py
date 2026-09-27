"""Student dashboard views."""
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, UpdateView, ListView, CreateView, FormView
from django.views.generic.edit import FormMixin
from django import forms
from apps.accounts.forms import ProfileForm, StudentPasswordChangeForm
from apps.accounts.models import StudentProfile, ActivityLog
from apps.classes.models import Registration, FreeClass
from apps.attendance.models import Attendance
from apps.rewards.models import Reward, StudentAchievement, ResumeUpload
from apps.referrals.models import Referral
from apps.announcements.models import Announcement
from apps.notifications.models import Notification, EmailLog
from apps.notifications.services import NotificationService, EmailService
from apps.core.models import SiteSettings, ProjectIdea
from apps.feedback.models import Feedback
from apps.feedback.forms import FeedbackForm
from apps.feedback.services import FeedbackService


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        profile = user.profile
        today = timezone.localdate()
        ctx.update(
            {
                "profile": profile,
                "upcoming_classes": FreeClass.objects.filter(
                    status="upcoming", date__gte=today, registrations__student=user, registrations__status="confirmed"
                ).distinct()[:5],
                "registered_classes": Registration.objects.filter(
                    student=user, status="confirmed"
                ).select_related("free_class")[:8],
                "attendance_records": Attendance.objects.filter(student=user).select_related("free_class")[:8],
                "recent_rewards": Reward.objects.filter(student=user)[:8],
                "achievements": StudentAchievement.objects.filter(student=user).select_related("achievement")[:8],
                "announcements": Announcement.objects.visible()[:5],
                "emails": EmailLog.objects.filter(recipient=user)[:5],
                "referrals": Referral.objects.filter(referrer=user)[:5],
                "activities": ActivityLog.objects.filter(user=user)[:10],
                "notifications": Notification.objects.filter(user=user)[:8],
            }
        )
        return ctx


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = StudentProfile
    form_class = ProfileForm
    template_name = "dashboard/profile.html"
    success_url = reverse_lazy("dashboard:profile")

    def get_object(self, queryset=None):
        return self.request.user.profile

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("dashboard:profile") + "#dash-content"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "password_form" not in ctx:
            ctx["password_form"] = StudentPasswordChangeForm(user=self.request.user)
        ctx.setdefault("open_password_modal", False)
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)


class PasswordChangeView(LoginRequiredMixin, FormView):
    """Change password via profile modal — stay logged in and email a confirmation."""

    template_name = "dashboard/profile.html"
    form_class = StudentPasswordChangeForm
    success_url = reverse_lazy("dashboard:profile")

    def get(self, request, *args, **kwargs):
        return redirect("dashboard:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        password_form = kwargs.get("form") or ctx.get("form") or self.get_form()
        ctx["object"] = self.request.user.profile
        ctx["password_form"] = password_form
        ctx["form"] = ProfileForm(user=self.request.user, instance=self.request.user.profile)
        ctx["open_password_modal"] = True
        return ctx

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)

        changed_at = timezone.localtime().strftime("%d %b %Y, %I:%M %p")
        site = SiteSettings.load()
        contact = getattr(site, "contact_email", "") or settings.PROJECT_MAIL
        name = user.get_full_name() or user.email

        EmailService.send_from_template(
            "password_changed",
            user.email,
            {
                "student_name": name,
                "changed_at": changed_at,
                "contact_email": contact,
                "site_name": getattr(site, "site_name", "Aniket.ProjectMate"),
                "subject": "Your ProjectMate password was changed",
                "body_html": (
                    f"<p>Hi {name},</p>"
                    f"<p>Your account password was changed successfully on {changed_at}.</p>"
                    f"<p>If you did not make this change, contact us at {contact}.</p>"
                    "<p>You remain logged in. Use your new password the next time you sign in.</p>"
                ),
            },
            recipient=user,
        )
        NotificationService.notify(
            user,
            title="Password changed",
            message=f"Your password was updated on {changed_at}. Use the new password next time you log in.",
            level="success",
            link="/dashboard/profile/",
        )
        ActivityLog.objects.create(
            user=user,
            action="password_changed",
            description="User changed their account password",
            ip_address=self.request.META.get("REMOTE_ADDR"),
        )
        messages.success(
            self.request,
            "Password updated. You are still logged in — use the new password next time you sign in. "
            "A confirmation email was sent.",
        )
        return super().form_valid(form)


class RewardsView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/rewards.html"

    def get_context_data(self, **kwargs):
        from apps.adminpanel.pagination import paginate_queryset

        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        rewards_qs = Reward.objects.filter(student=user).order_by("-created_at")
        page_obj = paginate_queryset(self.request, rewards_qs)
        ctx["rewards"] = page_obj
        ctx["page_obj"] = page_obj
        ctx["achievements"] = StudentAchievement.objects.filter(student=user).select_related("achievement")
        ctx["profile"] = user.profile
        # Leaderboard top 10
        ctx["leaderboard"] = StudentProfile.objects.select_related("user").order_by("-reward_points")[:10]
        return ctx


class ReferralsView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/referrals.html"

    def get_context_data(self, **kwargs):
        from apps.adminpanel.pagination import paginate_queryset

        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["profile"] = user.profile
        referrals_qs = Referral.objects.filter(referrer=user).select_related("referred_user")
        ctx["pending_count"] = referrals_qs.filter(status="pending").count()
        ctx["approved_count"] = referrals_qs.filter(status="approved").count()
        page_obj = paginate_queryset(self.request, referrals_qs)
        ctx["referrals"] = page_obj
        ctx["page_obj"] = page_obj
        return ctx


class AttendanceView(LoginRequiredMixin, ListView):
    template_name = "dashboard/attendance.html"
    context_object_name = "records"
    paginate_by = 10

    def get_queryset(self):
        return Attendance.objects.filter(student=self.request.user).select_related("free_class")


class NotificationsView(LoginRequiredMixin, ListView):
    template_name = "dashboard/notifications.html"
    context_object_name = "notifications"
    paginate_by = 10

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def get(self, request, *args, **kwargs):
        NotificationService.mark_all_read(request.user)
        return super().get(request, *args, **kwargs)


class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = ResumeUpload
        fields = ("file", "notes")
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdf,.doc,.docx"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class ResumeView(LoginRequiredMixin, CreateView):
    model = ResumeUpload
    form_class = ResumeUploadForm
    template_name = "dashboard/resume.html"
    success_url = reverse_lazy("dashboard:resume")

    def get_success_url(self):
        return reverse("dashboard:resume") + "#dash-content"

    def form_valid(self, form):
        form.instance.student = self.request.user
        # Mark eligible if consistency reward earned
        from apps.rewards.models import Reward

        eligible = Reward.objects.filter(
            student=self.request.user, reason="consistency"
        ).exists()
        form.instance.is_reward_eligible = eligible
        messages.success(self.request, "Resume uploaded! Admin will review it soon.")
        from apps.rewards.services import RewardService

        response = super().form_valid(form)
        RewardService.award_points(
            self.request.user, "resume_uploaded", description="Resume uploaded"
        )
        return response

    def get_context_data(self, **kwargs):
        from apps.adminpanel.pagination import paginate_queryset

        ctx = super().get_context_data(**kwargs)
        uploads_qs = ResumeUpload.objects.filter(student=self.request.user).prefetch_related("reviews")
        page_obj = paginate_queryset(self.request, uploads_qs)
        ctx["uploads"] = page_obj
        ctx["page_obj"] = page_obj
        return ctx


class MyClassesView(LoginRequiredMixin, ListView):
    template_name = "dashboard/my_classes.html"
    context_object_name = "registrations"
    paginate_by = 10

    def get_queryset(self):
        return Registration.objects.filter(student=self.request.user).select_related("free_class")


class ProjectRequestsView(LoginRequiredMixin, ListView):
    """Student view of their project idea submissions and status."""

    template_name = "dashboard/project_requests.html"
    context_object_name = "project_requests"
    paginate_by = 10

    def get_queryset(self):
        email = (self.request.user.email or "").strip()
        return (
            ProjectIdea.objects.filter(email__iexact=email)
            .select_related("selected_plan")
            .order_by("-created_at")
        )


class MyFeedbacksView(LoginRequiredMixin, FormMixin, ListView):
    """Student view of their submitted feedback — write form opens inline."""

    template_name = "dashboard/my_feedbacks.html"
    context_object_name = "feedbacks"
    paginate_by = 10
    form_class = FeedbackForm
    success_url = reverse_lazy("dashboard:my_feedbacks")

    def get_queryset(self):
        return (
            Feedback.objects.filter(student=self.request.user)
            .select_related("student", "student__profile", "free_class", "course")
            .order_by("-created_at")
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "form" not in ctx:
            ctx["form"] = self.get_form()
        ctx["show_feedback_form"] = (
            self.request.method == "POST"
            or self.request.GET.get("write") == "1"
            or bool(getattr(self, "_form_had_errors", False))
        )
        ctx["has_eligible_workshops"] = FeedbackService.eligible_workshops_for_feedback(
            self.request.user
        ).exists()
        return ctx

    def post(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        self._form_had_errors = True
        return self.form_invalid(form)

    def form_valid(self, form):
        form.instance.student = self.request.user
        form.save()
        messages.success(
            self.request,
            "Thank you! Your feedback was submitted and will appear after admin approval.",
        )
        return redirect(reverse("dashboard:my_feedbacks") + "#dash-content")

    def form_invalid(self, form):
        messages.error(self.request, "Please fix the feedback form and try again.")
        return self.render_to_response(self.get_context_data(form=form))
