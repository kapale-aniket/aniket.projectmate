from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.urls import reverse_lazy
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, TemplateView
from django.contrib import messages
import json
from .forms import EmailAuthenticationForm, StudentRegistrationForm
from apps.rewards.services import RewardService


def safe_next_url(request, fallback=None):
    """Return a safe relative/absolute next URL from GET/POST, or fallback."""
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback or resolve_url("dashboard:home")


def redirect_with_replace(url: str) -> HttpResponse:
    """
    Client-side redirect that replaces the current history entry.
    Prevents Back from returning to login/register (and then bouncing to dashboard).
    """
    target = json.dumps(url)
    safe_href = escape(url)
    return HttpResponse(
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<script>window.location.replace({target});</script>"
        f"<noscript><meta http-equiv='refresh' content='0;url={safe_href}'></noscript>"
        "<title>Redirecting…</title></head>"
        f'<body><p><a href="{safe_href}">Continue</a></p></body></html>',
        content_type="text/html; charset=utf-8",
    )


class StudentLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        # Already signed in + landed here via Back → stay on public home, not dashboard
        if self.redirect_authenticated_user and request.user.is_authenticated:
            return redirect_with_replace(resolve_url("core:home"))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = form.cleaned_data.get("remember_me")
        if remember:
            self.request.session.set_expiry(60 * 60 * 24 * 15)  # 15 days
        else:
            self.request.session.set_expiry(0)
        user = self.request.user
        RewardService.award_daily_login(user)
        if not user.is_active:
            messages.warning(
                self.request,
                "Your account is deactivated. You can still sign in — contact admin if you need full access restored.",
            )
        else:
            messages.success(
                self.request, f"Welcome back, {user.first_name or 'learner'}!"
            )
        return redirect_with_replace(response.url)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid email or password. Please try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return safe_next_url(self.request, fallback=super().get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        next_url = self.request.GET.get("next", "")
        ctx["next"] = next_url
        ctx["show_trust"] = bool(next_url)
        from django.conf import settings as dj_settings

        ctx["google_oauth_configured"] = getattr(dj_settings, "GOOGLE_OAUTH_CONFIGURED", False)
        return ctx


class StudentRegisterView(CreateView):
    form_class = StudentRegistrationForm
    template_name = "auth/register.html"
    success_url = reverse_lazy("dashboard:home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect_with_replace(resolve_url("core:home"))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return safe_next_url(self.request, fallback=str(self.success_url))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = self.request.GET.get("next") or self.request.POST.get("next") or ""
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object, backend="apps.accounts.backends.AllowInactiveStudentBackend")
        next_url = safe_next_url(self.request, fallback="")
        if next_url and "/classes/" in next_url:
            messages.success(
                self.request,
                "Account created! Complete registration for the free class below.",
            )
        else:
            messages.success(self.request, "Account created! Welcome to Aniket.ProjectMate.")
        return redirect_with_replace(response.url)

    def form_invalid(self, form):
        messages.error(self.request, "Please fix the registration errors and try again.")
        return super().form_invalid(form)


class StudentLogoutView(LogoutView):
    next_page = reverse_lazy("core:home")

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Session is new after logout — flash still works on the new session
        messages.info(request, "You've been logged out. See you soon!")
        if hasattr(response, "url"):
            return redirect_with_replace(response.url)
        return response


class TrustLoginView(TemplateView):
    """Intermediate trust message before login for gated actions."""

    template_name = "auth/trust_login.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["next"] = self.request.GET.get("next", "/dashboard/")
        return ctx
