from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from apps.classes.forms import ClassRegistrationForm
from apps.notifications.services import EmailService, NotificationService
from .models import PaidCourse, CourseEnrollment


class PaidCourseListView(ListView):
    model = PaidCourse
    template_name = "pages/paid_courses.html"
    context_object_name = "courses"
    paginate_by = 10

    def get_queryset(self):
        qs = PaidCourse.objects.filter(status=PaidCourse.Status.PUBLISHED)
        tech = self.request.GET.get("technology")
        q = self.request.GET.get("q")
        if tech:
            qs = qs.filter(technology=tech)
        if q:
            qs = qs.filter(title__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["technologies"] = PaidCourse.TECHNOLOGY_CHOICES
        return ctx


class PaidCourseDetailView(DetailView):
    model = PaidCourse
    template_name = "pages/paid_course_detail.html"
    context_object_name = "course"
    slug_field = "slug"

    def get_queryset(self):
        return PaidCourse.objects.filter(status=PaidCourse.Status.PUBLISHED)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_enrolled"] = False
        user = self.request.user
        if user.is_authenticated:
            ctx["is_enrolled"] = (
                CourseEnrollment.objects.filter(student=user, course=self.object)
                .exclude(status="cancelled")
                .exists()
            )
            ctx["register_form"] = ClassRegistrationForm(user=user)
        else:
            ctx["register_form"] = None
        return ctx


class EnrollCourseView(LoginRequiredMixin, View):
    """Register interest / enroll for a paid course (payment future-ready)."""

    login_url = "/accounts/trust/"

    def post(self, request, slug):
        course = get_object_or_404(PaidCourse, slug=slug, status="published")
        form = ClassRegistrationForm(request.POST, user=request.user)
        if not form.is_valid():
            for field, errors in form.errors.items():
                for err in errors:
                    messages.error(request, err)
            return redirect("courses:detail", slug=slug)

        form.apply_to_user()
        enrollment, created = CourseEnrollment.objects.get_or_create(
            student=request.user,
            course=course,
            defaults={"status": CourseEnrollment.Status.PENDING_PAYMENT},
        )
        if not created and enrollment.status == "cancelled":
            enrollment.status = CourseEnrollment.Status.PENDING_PAYMENT
            enrollment.save(update_fields=["status", "updated_at"])

        NotificationService.notify(
            request.user,
            title="Course registration received",
            message=f"You’re registered for {course.title}. Check your email for session details.",
            level="success",
            link=course.get_absolute_url(),
        )
        EmailService.send_plain(
            to_email=request.user.email,
            subject=f"Registered: {course.title}",
            body_text=(
                f"Hi {request.user.first_name or 'there'},\n\n"
                f"You’re registered for {course.title}.\n\n"
                "Check this email inbox for the session Meet link and next updates.\n\n"
                "— Aniket.ProjectMate"
            ),
            recipient=request.user,
        )
        messages.success(
            request,
            "You’re registered! Check your registered email for the session Meet link.",
        )
        return redirect("courses:detail", slug=slug)
