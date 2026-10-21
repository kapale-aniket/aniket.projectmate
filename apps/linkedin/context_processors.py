"""JOB search login tab permissions for templates."""
from django.urls import reverse

TAB_KEYS = (
    "home",
    "session",
    "jobs",
    "perfect_match",
    "connections",
    "perfect_connection",
    "posts",
    "output",
    "logs",
    "settings",
)
DEFAULT_TABS = {"home", "session", "jobs", "output"}


def linkedin_access(request):
    user = getattr(request, "user", None)
    limited = bool(
        user and getattr(user, "is_authenticated", False) and getattr(user, "role", "") == "linkedin_search"
    )
    allowed = set(TAB_KEYS)
    landing = ""
    if limited:
        allowed = set(DEFAULT_TABS)
        try:
            access = user.linkedin_search_access
        except Exception:
            access = None
        if access and access.is_active and access.tab_set():
            allowed = access.tab_set() & set(TAB_KEYS)
        order = ("jobs", "home", "session", "output")
        for key in order:
            if key in allowed:
                landing = reverse(
                    {
                        "jobs": "linkedin:jobs",
                        "home": "linkedin:home",
                        "session": "linkedin:session",
                        "output": "linkedin:output",
                    }[key]
                )
                break
        if not landing:
            landing = reverse("adminpanel:job_search_login")
    return {
        "li_access": {
            "limited": limited,
            "manage_users": bool(
                user
                and getattr(user, "is_authenticated", False)
                and getattr(user, "role", "") != "linkedin_search"
                and (user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin")
            ),
            "tabs": {key: key in allowed for key in TAB_KEYS},
            "landing_url": landing,
        }
    }
