"""Core middleware."""
from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import patch_cache_control
from django.middleware.csrf import get_token


class EnsureCsrfCookieMiddleware(MiddlewareMixin):
    """Always set the CSRF cookie so JS/fetch POSTs stay in sync."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        get_token(request)
        return None

    def process_response(self, request, response):
        if request.method == "GET" and "csrftoken" in getattr(response, "cookies", {}):
            patch_cache_control(response, no_cache=True, must_revalidate=True)
        return response


class ThemeMiddleware(MiddlewareMixin):
    """Attach theme preference from cookie/session."""

    def process_request(self, request):
        theme = request.COOKIES.get("theme") or request.session.get("theme") or "light"
        if theme not in ("light", "dark"):
            theme = "light"
        request.theme = theme


class AdminNoCacheMiddleware(MiddlewareMixin):
    """Prevent browser/back-forward cache from restoring admin pages after logout."""

    def process_response(self, request, response):
        path = request.path or ""
        if not path.startswith("/admin"):
            return response
        # Always revalidate admin HTML so Back/Forward cannot show a logged-in shell
        if "text/html" in (response.get("Content-Type") or ""):
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


class ActivityLogMiddleware(MiddlewareMixin):
    """Lightweight activity tracking for authenticated users on key paths."""

    TRACK_PREFIXES = (
        "/dashboard/",
        "/classes/",
        "/feedback/",
        "/courses/",
        "/accounts/",
        "/admin/",
    )
    SKIP_PREFIXES = (
        "/admin/login/",
        "/admin/logout/",
        "/admin/forgot-password/",
        "/admin/logs/",
        "/accounts/login/",
        "/accounts/logout/",
        "/accounts/password",
        "/accounts/trust/",
    )

    def process_response(self, request, response):
        path = request.path
        # Admin login is served at /admin/ (exact); do not treat it as tracked admin activity
        if path.rstrip("/") == "/admin":
            return response
        if (
            getattr(request, "user", None)
            and request.user.is_authenticated
            and request.method in ("POST", "PUT", "PATCH", "DELETE")
            and any(path.startswith(p) for p in self.TRACK_PREFIXES)
            and not any(path.startswith(p) for p in self.SKIP_PREFIXES)
            and 200 <= response.status_code < 400
        ):
            try:
                from apps.accounts.models import ActivityLog

                action = f"{request.method} {path}"
                ActivityLog.objects.create(
                    user=request.user,
                    action=action[:100],
                    description="User action",
                    ip_address=self._client_ip(request),
                    metadata={"status": response.status_code},
                )
            except Exception:
                pass
        return response

    @staticmethod
    def _client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
