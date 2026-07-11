"""Admin-only access mixins."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = reverse_lazy("adminpanel:login")

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin")

    def handle_no_permission(self):
        from django.utils.cache import patch_cache_control

        if self.request.user.is_authenticated:
            messages.error(self.request, "Admin access required. Please sign in with an admin account.")
        response = redirect(self.get_login_url())
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
        return response

    def is_htmx(self):
        return self.request.headers.get("HX-Request") == "true"


class ModalFormMixin:
    """Render create/edit forms inside the shared admin modal via HTMX."""

    modal_title = "Form"
    form_multipart = True

    def get_template_names(self):
        if self.is_htmx():
            return ["adminpanel/partials/modal_form.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modal_title"] = self.get_modal_title()
        ctx["form_multipart"] = self.form_multipart
        return ctx

    def get_modal_title(self):
        return self.modal_title

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.is_htmx():
            redirect_to = getattr(response, "url", None) or str(self.get_success_url())
            out = HttpResponse(status=204)
            out["HX-Redirect"] = redirect_to
            return out
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please fix the form errors and try again.")
        if self.is_htmx():
            return self.render_to_response(self.get_context_data(form=form))
        return super().form_invalid(form)


class MessageDeleteMixin:
    """Flash a success toast after delete."""

    success_message = "Deleted successfully."

    def form_valid(self, form):
        obj = self.object if hasattr(self, "object") and self.object else self.get_object()
        msg = self.success_message
        try:
            msg = msg.format(object=obj)
        except (KeyError, IndexError, ValueError):
            pass
        messages.success(self.request, msg)
        return super().form_valid(form)
