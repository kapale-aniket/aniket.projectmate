from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import FeedbackForm
from .models import Feedback


class FeedbackCreateView(LoginRequiredMixin, CreateView):
    model = Feedback
    form_class = FeedbackForm
    template_name = "pages/feedback.html"
    success_url = reverse_lazy("feedback:create")
    login_url = "/accounts/trust/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.student = self.request.user
        form.save()
        messages.success(
            self.request,
            "Thank you! Your feedback was submitted and will appear after admin approval.",
        )
        return redirect(reverse("feedback:create") + "#feedback-top")


class TestimonialListView(ListView):
    model = Feedback
    template_name = "pages/testimonials.html"
    context_object_name = "testimonials"
    paginate_by = None  # View all — every public feedback

    def get_queryset(self):
        return (
            Feedback.objects.filter(status="approved", show_on_landing=True)
            .select_related("student", "student__profile", "free_class", "course")
            .order_by("-is_featured", "-created_at")
        )
