"""Public landing and static pages."""
from django.views.generic import TemplateView, FormView, View
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django import forms
from apps.core.models import FAQ, GalleryImage, CourseCategory, ContactMessage, ProjectIdea, ProjectPlan, ProjectPlanPerk
from apps.announcements.models import Announcement
from apps.classes.models import FreeClass
from apps.courses.models import PaidCourse
from apps.feedback.models import Feedback
from apps.accounts.models import User


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}),
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Subject"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Message"}),
        }


class ProjectIdeaForm(forms.ModelForm):
    class Meta:
        model = ProjectIdea
        fields = (
            "selected_plan",
            "name",
            "email",
            "phone",
            "college",
            "project_title",
            "idea",
            "tech_stack",
            "timeline",
        )
        widgets = {
            "selected_plan": forms.HiddenInput(),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your full name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "WhatsApp / phone"}),
            "college": forms.TextInput(attrs={"class": "form-control", "placeholder": "College / university"}),
            "project_title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. College attendance app"}
            ),
            "idea": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Share your idea in your own words — what should it do, who is it for, any must-have features…",
                }
            ),
            "tech_stack": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Django, React, MySQL… (optional)"}
            ),
            "timeline": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. 2 weeks / before viva"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_plans = ProjectPlan.objects.filter(is_active=True)
        self.fields["selected_plan"].queryset = active_plans
        self.fields["selected_plan"].required = active_plans.exists()
        self.fields["selected_plan"].error_messages = {
            "required": "Please select a plan first, then fill your details.",
        }

    def clean_selected_plan(self):
        plan = self.cleaned_data.get("selected_plan")
        if self.fields["selected_plan"].required and not plan:
            raise forms.ValidationError("Please select a plan first, then fill your details.")
        return plan


def _landing_testimonials(limit=None):
    qs = (
        Feedback.objects.filter(status="approved", show_on_landing=True)
        .select_related("student", "student__profile", "free_class", "course")
        .order_by("-is_featured", "-created_at")
    )
    if limit is not None:
        qs = qs[:limit]
    return list(qs)


class HomeView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        live_students = User.objects.filter(role="student", is_active=True).count()
        live_workshops = FreeClass.public_queryset().count()
        live_courses = PaidCourse.objects.filter(status="published").count()

        featured_paid = list(
            PaidCourse.objects.filter(status="published", is_featured=True)[:6]
        )
        if not featured_paid:
            featured_paid = list(PaidCourse.objects.filter(status="published")[:6])

        all_testimonials = _landing_testimonials()
        recent_announcements = list(Announcement.objects.recent(15)[:5])
        ctx.update(
            {
                "latest_announcement": recent_announcements[0] if recent_announcements else None,
                "announcements": recent_announcements,
                "upcoming_free": FreeClass.public_queryset()
                .filter(status__in=["upcoming", "live"])
                .order_by("date", "start_time")[:6],
                "upcoming_paid": featured_paid,
                "testimonials": all_testimonials,
                "faqs": FAQ.objects.filter(is_published=True),
                "categories": CourseCategory.objects.filter(is_active=True),
                "gallery": GalleryImage.objects.filter(is_published=True)[:12],
                "stats": {
                    "students": live_students,
                    "workshops": live_workshops,
                    "courses": live_courses,
                },
                "contact_form": ContactForm(),
            }
        )
        return ctx


class AboutView(TemplateView):
    template_name = "pages/about.html"


class ContactView(FormView):
    template_name = "pages/contact.html"
    form_class = ContactForm
    success_url = reverse_lazy("core:contact")

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Thanks! We'll get back to you soon.")
        return super().form_valid(form)


class ProjectView(FormView):
    """Custom project service — share your idea, we customize it with you."""

    template_name = "pages/project.html"
    form_class = ProjectIdeaForm
    success_url = reverse_lazy("core:project")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project_plans"] = ProjectPlan.objects.filter(is_active=True)
        ctx["project_perks"] = ProjectPlanPerk.objects.filter(is_active=True)
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            "Idea received! We’ll review it and reach out to customize your project with you.",
        )
        return super().form_valid(form)


class SearchView(TemplateView):
    template_name = "pages/search.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "").strip()
        ctx["q"] = q
        if q:
            ctx["classes"] = FreeClass.public_queryset().filter(title__icontains=q)[:20]
            ctx["courses"] = PaidCourse.objects.filter(title__icontains=q)[:20]
            ctx["announcements"] = Announcement.objects.filter(title__icontains=q)[:20]
        else:
            ctx["classes"] = ctx["courses"] = ctx["announcements"] = []
        return ctx


class ThemeToggleView(View):
    """Persist theme preference. Client applies theme instantly; this syncs cookie/session."""

    def post(self, request, *args, **kwargs):
        from django.http import JsonResponse

        new_theme = (request.POST.get("theme") or "").strip()
        if new_theme not in ("light", "dark"):
            current = request.COOKIES.get("theme") or request.session.get("theme") or "light"
            new_theme = "dark" if current == "light" else "light"

        request.session["theme"] = new_theme
        if request.headers.get("HX-Request") == "true" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            response = JsonResponse({"theme": new_theme})
        else:
            response = redirect(request.META.get("HTTP_REFERER", "/"))
        response.set_cookie("theme", new_theme, max_age=60 * 60 * 24 * 365, samesite="Lax")
        return response
