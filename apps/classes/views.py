from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, View
from .models import FreeClass, Registration
from .forms import ClassRegistrationForm
from .services import RegistrationService, ClassStatusService


class FreeClassListView(ListView):
    model = FreeClass
    template_name = "pages/free_classes.html"
    context_object_name = "classes"
    paginate_by = 10

    def get_queryset(self):
        ClassStatusService.sync_all()
        qs = FreeClass.public_queryset()
        tech = self.request.GET.get("technology")
        status = self.request.GET.get("status")
        q = self.request.GET.get("q")
        if tech:
            qs = qs.filter(technology__icontains=tech)
        if status in ("upcoming", "live", "completed"):
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(title__icontains=q)
        return qs


class FreeClassDetailView(DetailView):
    model = FreeClass
    template_name = "pages/free_class_detail.html"
    context_object_name = "free_class"
    slug_field = "slug"

    def get_queryset(self):
        ClassStatusService.sync_all()
        return FreeClass.public_queryset()

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.refresh_status(save=True)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["is_registered"] = False
        if user.is_authenticated:
            ctx["is_registered"] = Registration.objects.filter(
                student=user,
                free_class=self.object,
                status=Registration.Status.CONFIRMED,
            ).exists()
            ctx["register_form"] = ClassRegistrationForm(user=user)
        else:
            ctx["register_form"] = None
        return ctx


class RegisterClassView(LoginRequiredMixin, View):
    """Class seat registration — auto-confirmed (no admin approval)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            detail = reverse("classes:detail", kwargs={"slug": kwargs["slug"]})
            return redirect(f"{reverse('accounts:register')}?next={detail}")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, slug):
        free_class = get_object_or_404(FreeClass.public_queryset(), slug=slug)
        form = ClassRegistrationForm(request.POST, user=request.user)
        if not form.is_valid():
            for field, errors in form.errors.items():
                for err in errors:
                    messages.error(request, err)
            return redirect("classes:detail", slug=slug)

        try:
            form.apply_to_user()
            free_class.refresh_status(save=True)
            RegistrationService.register(request.user, free_class)
            messages.success(
                request,
                "You’re registered! Check your registered email for the session Meet link.",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))

        return redirect("classes:detail", slug=slug)
