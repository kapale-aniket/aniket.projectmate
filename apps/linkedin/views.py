"""Admin LinkedIn automation pages (ProjectMate theme)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.linkedin.forms import (
    ConnectionScraperForm,
    JobScraperForm,
    PerfectConnectionForm,
    PerfectMatchJobForm,
    PostsScraperForm,
    SessionForm,
    SettingsForm,
)
from apps.linkedin.models import LinkedInSearchUser, ScraperTask
from apps.linkedin.services.config_service import load_settings
from apps.linkedin.services.settings_helpers import (
    apply_last_task_form_defaults,
    config_lock_message,
    is_config_locked,
    settings_to_form,
)
from apps.linkedin.services.stats import (
    apply_preview_view_filters,
    collect_logs,
    dashboard_stats,
    get_latest_job_output_file,
    list_output_files,
    list_recent_job_output_files,
    log_automation_files,
    preview_file,
    recent_activity,
    session_status,
)
from apps.linkedin.services.task_manager import (
    ensure_settings_initialized,
    get_active_task,
    task_status_payload,
)


def _admin_required(view):
    @login_required(login_url="/admin/")
    def _wrapped(request, *args, **kwargs):
        user = request.user
        role = getattr(user, "role", "")
        if not (user.is_staff or user.is_superuser or role in {"admin", "linkedin_search"}):
            messages.error(request, "Admin access required.")
            return redirect("adminpanel:login")
        return view(request, *args, **kwargs)

    return _wrapped


def _staff_only(view):
    @login_required(login_url="/admin/")
    def _wrapped(request, *args, **kwargs):
        user = request.user
        role = getattr(user, "role", "")
        if role == "linkedin_search":
            return redirect("linkedin:jobs")
        if not (user.is_staff or user.is_superuser or role == "admin"):
            messages.error(request, "Admin access required.")
            return redirect("adminpanel:login")
        return view(request, *args, **kwargs)

    return _wrapped


def _scraper_context(request, form_class, task_type):
    ensure_settings_initialized()
    form = form_class()
    apply_last_task_form_defaults(form, task_type)
    active = get_active_task()
    task_status = task_status_payload(active)
    other_task_busy = bool(active and active.is_active and active.task_type != task_type)
    config_locked = is_config_locked(active, task_type)
    app_settings = load_settings()
    settings_form = SettingsForm(initial=settings_to_form(app_settings, task_type))
    ctx = {
        "form": form,
        "settings_form": settings_form,
        "task_type": task_type,
        "active_task": active,
        "task_status": task_status,
        "other_task_busy": other_task_busy,
        "busy_task": task_status if other_task_busy else None,
        "config_locked": config_locked,
        "config_lock_message": config_lock_message(active) if config_locked else "",
        "session": session_status(),
        "linkedin_nav": task_type,
        "app_settings": app_settings,
    }
    if task_type == ScraperTask.TASK_JOB:
        ctx["recent_job_outputs"] = list_recent_job_output_files()
        ctx["latest_job_output"] = get_latest_job_output_file()
    if task_type == ScraperTask.TASK_PERFECT_MATCH:
        ctx["recent_job_outputs"] = list_recent_job_output_files(prefix="skill_match_job")
        ctx["latest_job_output"] = get_latest_job_output_file(prefix="skill_match_job")
    return ctx


@_admin_required
def linkedin_home(request):
    ensure_settings_initialized()
    active = get_active_task()
    return render(
        request,
        "adminpanel/linkedin/index.html",
        {
            "stats": dashboard_stats(),
            "activity": recent_activity(8),
            "active_task": active,
            "task_status": task_status_payload(active),
            "session": session_status(),
            "linkedin_nav": "home",
            "app_settings": load_settings(),
        },
    )


@_admin_required
def job_scraper(request):
    return render(
        request,
        "adminpanel/linkedin/jobs.html",
        _scraper_context(request, JobScraperForm, ScraperTask.TASK_JOB),
    )


@_admin_required
def perfect_match_scraper(request):
    return render(
        request,
        "adminpanel/linkedin/perfect_match.html",
        _scraper_context(request, PerfectMatchJobForm, ScraperTask.TASK_PERFECT_MATCH),
    )


@_admin_required
def connection_scraper(request):
    return render(
        request,
        "adminpanel/linkedin/connections.html",
        _scraper_context(request, ConnectionScraperForm, ScraperTask.TASK_CONNECTION),
    )


@_admin_required
def perfect_connection_scraper(request):
    return render(
        request,
        "adminpanel/linkedin/perfect_connection.html",
        _scraper_context(request, PerfectConnectionForm, ScraperTask.TASK_PERFECT_CONNECTION),
    )


@_admin_required
def posts_scraper(request):
    return render(
        request,
        "adminpanel/linkedin/posts.html",
        _scraper_context(request, PostsScraperForm, ScraperTask.TASK_POSTS),
    )


@_admin_required
def session_manager(request):
    ensure_settings_initialized()
    active = get_active_task()
    task_status = task_status_payload(active)
    other_task_busy = bool(
        active and active.is_active and active.task_type != ScraperTask.TASK_SESSION
    )
    return render(
        request,
        "adminpanel/linkedin/session.html",
        {
            "form": SessionForm(),
            "session": session_status(),
            "active_task": active,
            "task_status": task_status,
            "other_task_busy": other_task_busy,
            "busy_task": task_status if other_task_busy else None,
            "linkedin_nav": "session",
            "app_settings": load_settings(),
        },
    )


@_admin_required
def logs_view(request):
    return render(
        request,
        "adminpanel/linkedin/logs.html",
        {
            "logs": collect_logs(
                limit=200,
                search=request.GET.get("q", ""),
                sort_by=request.GET.get("sort", "date"),
                sort_dir=request.GET.get("order", "desc"),
            ),
            "file_logs": log_automation_files(),
            "search": request.GET.get("q", ""),
            "sort_by": request.GET.get("sort", "date"),
            "sort_dir": request.GET.get("order", "desc"),
            "active_task": get_active_task(),
            "task_status": task_status_payload(get_active_task()),
            "session": session_status(),
            "linkedin_nav": "logs",
        },
    )


@_admin_required
def output_view(request):
    from apps.linkedin.services.filter_utils import filter_sort_files
    from apps.linkedin.services.stats import output_file_key, resolve_output_file_path
    from apps.linkedin.services.trash_service import list_trashed_files

    all_files = list_output_files()
    search = request.GET.get("q", "")
    file_type = request.GET.get("type", "")
    sort_by = request.GET.get("sort", "date")
    sort_dir = request.GET.get("order", "desc")
    files = filter_sort_files(all_files, search, file_type, sort_by, sort_dir)

    selected_raw = request.GET.get("file")
    selected = ""
    selected_path = ""
    preview_search = request.GET.get("preview_q", "")
    preview_sort = request.GET.get("preview_sort", "")
    preview_order = request.GET.get("preview_order", "asc")
    preview_page = request.GET.get("preview_page", "1")
    preview = None
    if selected_raw:
        selected_path = resolve_output_file_path(selected_raw) or ""
        selected = output_file_key(selected_raw) if selected_path else selected_raw
        if selected_path:
            preview = preview_file(selected_path)
            if preview and not preview.get("error"):
                preview = apply_preview_view_filters(
                    preview,
                    preview_search=preview_search,
                    preview_sort=preview_sort,
                    preview_order=preview_order,
                    preview_page=preview_page,
                )

    show_trash = request.GET.get("trash", "").lower() in ("1", "true", "yes")
    return render(
        request,
        "adminpanel/linkedin/output.html",
        {
            "files": files,
            "selected": selected,
            "selected_path": selected_path,
            "preview": preview,
            "search": search,
            "file_type": file_type,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "preview_search": preview_search,
            "preview_sort": preview_sort,
            "preview_order": preview_order,
            "preview_page": preview_page,
            "file_types": sorted({f["type"] for f in all_files}),
            "deleted_files": list_trashed_files(),
            "show_trash": show_trash,
            "session": session_status(),
            "linkedin_nav": "output",
        },
    )


@_admin_required
@require_POST
def restore_trashed_file(request):
    from apps.linkedin.services.trash_service import restore_from_trash

    trash_id = request.POST.get("id", "").strip()
    if not trash_id:
        messages.error(request, "Missing file id.")
        return redirect("linkedin:output")
    try:
        result = restore_from_trash(trash_id)
        messages.success(request, result["message"])
    except (FileNotFoundError, FileExistsError, ValueError, OSError) as exc:
        messages.error(request, str(exc))
    return redirect(f"{reverse('linkedin:output')}?trash=1")


@_admin_required
def trash_view(request):
    return redirect(f"{reverse('linkedin:output')}?trash=1")


ASSIGNABLE_TABS = [
    ("home", "Overview"),
    ("session", "Session"),
    ("jobs", "Jobs"),
    ("perfect_match", "Perfect Match"),
    ("connections", "Connections"),
    ("perfect_connection", "Perfect Connection"),
    ("posts", "Posts"),
    ("output", "Output"),
    ("logs", "Logs"),
]


def _normalize_phone(raw):
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def _save_search_user(request):
    from apps.accounts.models import User

    raw_id = (request.POST.get("user_id") or "").strip()
    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    phone = _normalize_phone(request.POST.get("phone"))
    password = request.POST.get("password") or ""
    allowed = {key for key, _label in ASSIGNABLE_TABS}
    tabs = []
    for key in request.POST.getlist("tabs"):
        if key in allowed and key not in tabs:
            tabs.append(key)
    is_active = request.POST.get("is_active") == "1"
    if not name or "@" not in email:
        messages.error(request, "Name and a valid email are required.")
        return
    if not tabs:
        messages.error(request, "Select at least one tab.")
        return
    if password and len(password) < 6:
        messages.error(request, "Password must be at least 6 characters.")
        return
    if phone and len(phone) != 10:
        messages.error(request, "Mobile number must be 10 digits, or leave it blank.")
        return

    if raw_id:
        access = LinkedInSearchUser.objects.select_related("user").filter(pk=raw_id).first()
        if not access:
            messages.error(request, "User not found.")
            return
        user = access.user
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            messages.error(request, "That email is already used.")
            return
    else:
        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "That email is already used.")
            return
        user = User(
            email=email,
            username=email,
            role=User.Role.LINKEDIN_SEARCH,
            is_staff=False,
            is_superuser=False,
        )
        access = LinkedInSearchUser(user=user)

    user.email = email
    user.username = email
    user.first_name = name[:150]
    user.role = User.Role.LINKEDIN_SEARCH
    user.is_staff = False
    user.is_superuser = False
    user.is_active = is_active
    if password or not user.pk:
        user.set_password(password)
    user.save()
    access.phone = phone
    access.tabs = tabs
    access.is_active = is_active
    access.user = user
    access.save()
    messages.success(request, "Search user saved.")


def _delete_search_user(request):
    access = LinkedInSearchUser.objects.select_related("user").filter(pk=request.POST.get("user_id")).first()
    if not access:
        messages.error(request, "User not found.")
        return
    account = access.user
    if account.pk == request.user.pk or account.is_superuser or account.role == "admin":
        messages.error(request, "This account cannot be removed here.")
        return
    email = account.email
    account.delete()
    messages.success(request, f"Removed {email}.")


@_staff_only
def linkedin_users(request):
    from apps.linkedin.services.stats import session_status

    if request.method == "POST":
        if (request.POST.get("action") or "") == "delete":
            _delete_search_user(request)
        else:
            _save_search_user(request)
        return redirect("linkedin:users")
    return render(
        request,
        "adminpanel/linkedin/settings.html",
        {
            "settings_tab": "users",
            "search_users": LinkedInSearchUser.objects.select_related("user"),
            "assignable_tabs": ASSIGNABLE_TABS,
            "session": session_status(),
            "linkedin_nav": "settings",
            "config_locked": False,
        },
    )


@_staff_only
def settings_view(request):
    ensure_settings_initialized()
    tab = request.GET.get("tab", "job")
    if tab not in {"job", "connection", "posts", "browser", "cursor"}:
        tab = "job"
    app_settings = load_settings()
    active = get_active_task()
    return render(
        request,
        "adminpanel/linkedin/settings.html",
        {
            "settings_form": SettingsForm(initial=settings_to_form(app_settings, tab)),
            "settings_tab": tab,
            "app_settings": app_settings,
            "config_locked": is_config_locked(active, settings_tab=tab),
            "config_lock_message": config_lock_message(active),
            "session": session_status(),
            "linkedin_nav": "settings",
            "active_task": active,
        },
    )


@_admin_required
@require_GET
def download_file(request):
    from pathlib import Path
    from django.conf import settings

    rel = request.GET.get("path", "").strip()
    if not rel or ".." in rel:
        raise Http404()
    root = Path(settings.LINKEDIN_AUTOMATION_ROOT).resolve()
    # Accept absolute paths under automation root (legacy) or relative
    candidate = Path(rel)
    target = candidate.resolve() if candidate.is_absolute() else (root / rel).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise Http404()
    return FileResponse(target.open("rb"), as_attachment=True, filename=target.name)
