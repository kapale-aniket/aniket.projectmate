"""Template context processors."""
from apps.core.models import SiteSettings


def site_settings(request):
    try:
        settings_obj = SiteSettings.load()
    except Exception:
        settings_obj = None
    return {
        "site_settings": settings_obj,
        "SITE_NAME": getattr(settings_obj, "site_name", "Aniket.ProjectMate"),
    }


def theme(request):
    return {"theme": getattr(request, "theme", "light")}
