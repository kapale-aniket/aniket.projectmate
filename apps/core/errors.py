"""Centralized HTTP / CSRF error handling for Aniket.ProjectMate.

Wire in settings:
  CSRF_FAILURE_VIEW = "apps.core.errors.csrf_failure"

And in config/urls.py:
  handler400 = "apps.core.errors.bad_request"
  handler403 = "apps.core.errors.permission_denied"
  handler404 = "apps.core.errors.page_not_found"
  handler500 = "apps.core.errors.server_error"
"""
import logging
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def _wants_json(request):
    accept = (request.headers.get("Accept") or "").lower()
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("HX-Request") == "true"
        or "application/json" in accept
    )


def _render_error(request, status, title, message, hint=""):
    """Shared renderer for friendly error pages / JSON responses."""
    context = {
        "status_code": status,
        "error_title": title,
        "error_message": message,
        "error_hint": hint,
    }
    if _wants_json(request):
        return JsonResponse(
            {
                "ok": False,
                "error": title,
                "message": message,
                "status": status,
            },
            status=status,
        )
    return render(request, "errors/error.html", context, status=status)


def csrf_failure(request, reason=""):
    """Friendly CSRF failure — never show Django's debug CSRF page."""
    logger.warning("CSRF failure on %s: %s", request.path, reason or "unknown")
    # Logout should never be blocked by a stale CSRF token
    path = (request.path or "").rstrip("/")
    if path.endswith("/admin/logout") or path.endswith("/accounts/logout"):
        from django.contrib.auth import logout
        from django.shortcuts import redirect

        logout(request)
        try:
            request.session.flush()
        except Exception:
            pass
        if "/admin/" in (request.path or ""):
            return redirect("/admin/?logged_out=1")
        return redirect("/")
    return _render_error(
        request,
        status=403,
        title="Session expired",
        message="Your form session expired or was refreshed. Please go back and try again.",
        hint="Reload the page, then submit the form once more. If you just signed in, open the page again before submitting.",
    )


def bad_request(request, exception=None):
    return _render_error(
        request,
        status=400,
        title="Bad request",
        message="We couldn’t process that request. Please check what you submitted and try again.",
    )


def permission_denied(request, exception=None):
    return _render_error(
        request,
        status=403,
        title="Access denied",
        message="You don’t have permission to view this page.",
        hint="Sign in with an account that has access, or go back to the home page.",
    )


def page_not_found(request, exception=None):
    return _render_error(
        request,
        status=404,
        title="Page not found",
        message="The page you’re looking for doesn’t exist or may have moved.",
        hint="Check the URL, or use the navigation to find what you need.",
    )


def server_error(request):
    logger.exception("Unhandled server error on %s", getattr(request, "path", "?"))
    return _render_error(
        request,
        status=500,
        title="Something went wrong",
        message="An unexpected error occurred on our side. Please try again in a moment.",
        hint="If this keeps happening, contact support with the page you were on.",
    )
