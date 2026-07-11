"""Root URL configuration for Aniket.ProjectMate."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

# Keep Django's built-in admin at a hidden path (optional/emergency only)
admin.site.site_header = "Django ORM Admin (internal)"
admin.site.site_title = "Internal"

urlpatterns = [
    path("admin/", include("apps.adminpanel.urls")),  # Custom admin panel
    path("admin/linkedin/", include("apps.linkedin.urls")),  # LinkedIn parsing (admin)
    path("django-admin/", admin.site.urls),  # Default Django admin (internal)
    path("accounts/", include("apps.accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("dashboard/", include("apps.accounts.dashboard_urls")),
    path("classes/", include("apps.classes.urls")),
    path("courses/", include("apps.courses.urls")),
    path("announcements/", include("apps.announcements.urls")),
    path("feedback/", include("apps.feedback.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("", include("apps.core.urls")),
]

# Centralized error handlers (404/500 when DEBUG=False; CSRF always via CSRF_FAILURE_VIEW)
handler400 = "apps.core.errors.bad_request"
handler403 = "apps.core.errors.permission_denied"
handler404 = "apps.core.errors.page_not_found"
handler500 = "apps.core.errors.server_error"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
