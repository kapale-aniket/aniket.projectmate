import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.linkedin.forms import (
    ConnectionScraperForm,
    JobScraperForm,
    PerfectMatchJobForm,
    PostsScraperForm,
)
from apps.linkedin.models import ScraperTask, TaskLog
from apps.linkedin.services.config_service import (
    load_settings,
    normalize_max_job_age_hours,
    save_settings,
)
from apps.linkedin.services.file_errors import friendly_file_error
from apps.linkedin.services.stats import (
    collect_logs,
    dashboard_stats,
    list_output_files,
    log_automation_files,
    preview_file,
    recent_activity,
    session_status,
)
from apps.linkedin.services.browser_preview import (
    get_state as get_preview_state,
    screenshot_path,
    set_preview_enabled,
)
from apps.linkedin.services.settings_helpers import persist_run_config_to_settings
from apps.linkedin.services.task_manager import (
    get_active_task,
    get_running_task,
    pause_task,
    resume_task,
    start_task,
    stop_task,
    task_status_payload,
)


def _admin_api(view):
    @login_required(login_url="/admin/")
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not (user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin"):
            return JsonResponse({"ok": False, "message": "Admin access required"}, status=403)
        return view(request, *args, **kwargs)

    return _wrapped


# Re-apply admin gate to exported API endpoints below after definitions



def _busy_json(exc, status=409):
    active = get_active_task()
    return JsonResponse(
        {
            "ok": False,
            "message": str(exc),
            "running_task": task_status_payload(active) if active else None,
        },
        status=status,
    )


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _form_errors(form):
    return {field: errors[0] for field, errors in form.errors.items()}


@require_GET
def api_task_status(request):
    task_id = request.GET.get("id")
    task = ScraperTask.objects.filter(pk=task_id).first() if task_id else get_active_task()
    if not task:
        task = ScraperTask.objects.order_by("-created_at").first()
        if task and not task.is_active:
            task = None
    return JsonResponse(task_status_payload(task))


@require_POST
def api_task_start(request):
    body = _json_body(request)
    task_type = body.get("task_type")
    config = body.get("config", {})

    if not task_type:
        return JsonResponse({"ok": False, "message": "task_type is required"}, status=400)

    form_map = {
        ScraperTask.TASK_JOB: (JobScraperForm, _job_config_from_api),
        ScraperTask.TASK_PERFECT_MATCH: (PerfectMatchJobForm, _perfect_match_config_from_api),
        ScraperTask.TASK_CONNECTION: (ConnectionScraperForm, _connection_config_from_api),
        ScraperTask.TASK_POSTS: (PostsScraperForm, _posts_config_from_api),
    }

    if task_type == ScraperTask.TASK_SESSION:
        try:
            task = start_task(ScraperTask.TASK_SESSION, config={})
            return JsonResponse({"ok": True, "task_id": task.id, "message": "Session login started"})
        except RuntimeError as exc:
            return _busy_json(exc)

    if task_type not in form_map:
        return JsonResponse({"ok": False, "message": f"Unknown task type: {task_type}"}, status=400)

    form_class, normalizer = form_map[task_type]
    form_data = normalizer(config)
    form = form_class(form_data)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _form_errors(form), "message": "Invalid configuration"}, status=400)

    try:
        task_config = form.cleaned_config()
        if task_type in (ScraperTask.TASK_JOB, ScraperTask.TASK_PERFECT_MATCH):
            task_config["skip_searches"] = config.get("skip_searches") or []
        persist_run_config_to_settings(task_type, task_config)
        task = start_task(task_type, config=task_config, run_in_background=True)
        return JsonResponse(
            {
                "ok": True,
                "task_id": task.id,
                "message": f"{task.get_task_type_display()} started in background",
                "status": task_status_payload(task),
            }
        )
    except RuntimeError as exc:
        return _busy_json(exc)


def _job_config_from_api(config):
    return {
        "keywords": _lines(config.get("keywords")),
        "locations": _lines(config.get("locations")),
        "max_pages": config.get("max_pages", 40),
        "max_jobs": config.get("max_jobs", 0),
        "max_job_age_hours": normalize_max_job_age_hours(config.get("max_job_age_hours", 24)),
        "headless": True,
        "resume": config.get("resume", True),
        "skip_previous_jobs": bool(config.get("skip_previous_jobs")),
        "skip_searches": config.get("skip_searches") or [],
    }


def _perfect_match_config_from_api(config):
    skills = config.get("skills")
    if isinstance(skills, list):
        skills_list = [str(s).strip() for s in skills if str(s).strip()]
        skills_text = "\n".join(skills_list)
    else:
        skills_text = _lines(skills)
        skills_list = [s.strip() for s in skills_text.splitlines() if s.strip()]
    search_query = " ".join(skills_list)
    return {
        "skills": skills_text,
        "experience": (config.get("experience") or "fresher").strip(),
        "min_skills_match": config.get("min_skills_match", 1),
        "locations": _lines(config.get("locations")),
        "max_pages": config.get("max_pages", 40),
        "max_jobs": config.get("max_jobs", 0),
        "max_job_age_hours": normalize_max_job_age_hours(config.get("max_job_age_hours", 24)),
        "headless": True,
        "resume": bool(config.get("resume", False)),
        "skip_previous_jobs": bool(config.get("skip_previous_jobs")),
        "skip_searches": config.get("skip_searches") or [],
        # Kept for checklist compatibility; cleaned_config rebuilds from skills.
        "keywords": [search_query] if search_query else [],
    }


def _connection_config_from_api(config):
    return {
        "keywords": _lines(config.get("keywords")),
        "locations": _lines(config.get("locations")),
        "max_connections_per_run": config.get("max_connections_per_run", 30),
        "max_pages": config.get("max_pages", 200),
        "headless": True,
        "run_in_background": True,
    }


def _posts_config_from_api(config):
    return {
        "max_scroll_rounds": config.get("max_scroll_rounds", 30),
        "max_posts_per_run": config.get("max_posts_per_run", 0),
        "headless": True,
        "run_in_background": True,
    }


def _lines(value):
    if isinstance(value, list):
        return "\n".join(value)
    return value or ""


@require_POST
def api_task_control(request):
    body = _json_body(request)
    action = body.get("action") or request.POST.get("action")
    task_id = body.get("task_id") or request.POST.get("task_id")

    if action == "stop":
        result = stop_task(task_id)
        result["status"] = task_status_payload(get_active_task())
        return JsonResponse(result)
    if action == "pause":
        result = pause_task(task_id)
        result["status"] = task_status_payload(ScraperTask.objects.filter(pk=task_id).first() if task_id else get_active_task())
        return JsonResponse(result)
    if action == "resume":
        try:
            task = resume_task(task_id)
            return JsonResponse(
                {
                    "ok": True,
                    "task_id": task.id if task else None,
                    "message": "Task resumed",
                    "status": task_status_payload(task),
                }
            )
        except RuntimeError as exc:
            return _busy_json(exc)
    return JsonResponse({"ok": False, "message": "Unknown action"}, status=400)


@require_POST
def api_task_skip_searches(request):
    body = _json_body(request)
    task_id = body.get("task_id")
    skip_searches = body.get("skip_searches")
    if task_id is None:
        return JsonResponse({"ok": False, "message": "task_id is required"}, status=400)
    if skip_searches is None or not isinstance(skip_searches, list):
        return JsonResponse({"ok": False, "message": "skip_searches must be a list"}, status=400)

    task = ScraperTask.objects.filter(pk=task_id).first()
    if not task or task.task_type not in (
        ScraperTask.TASK_JOB,
        ScraperTask.TASK_PERFECT_MATCH,
    ):
        return JsonResponse({"ok": False, "message": "Job task not found"}, status=404)
    if task.status not in {
        ScraperTask.STATUS_PENDING,
        ScraperTask.STATUS_RUNNING,
        ScraperTask.STATUS_PAUSED,
    }:
        return JsonResponse({"ok": False, "message": "Task is not active"}, status=409)

    from apps.linkedin.services.progress_tracker import build_job_search_checklist
    from apps.linkedin.services.search_skip_service import write_skip_searches

    config = dict(task.config or {})
    config["skip_searches"] = skip_searches
    task.config = config
    task.save(update_fields=["config"])
    write_skip_searches(task.id, skip_searches)

    return JsonResponse(
        {
            "ok": True,
            "message": "Search queue updated",
            "search_checklist": build_job_search_checklist(task),
        }
    )


@require_GET
def api_logs(request):
    search = request.GET.get("q", "")
    task_id = request.GET.get("task")
    sort_by = request.GET.get("sort", "date")
    sort_dir = request.GET.get("order", "desc")
    limit = int(request.GET.get("limit", 200))
    db_logs = collect_logs(limit=limit, task_id=task_id, search=search, sort_by=sort_by, sort_dir=sort_dir)
    file_logs = log_automation_files(limit=50)
    return JsonResponse(
        {
            "logs": [
                {
                    "level": log.level,
                    "message": log.message,
                    "time": log.created_at.strftime("%H:%M:%S"),
                    "date": log.created_at.strftime("%Y-%m-%d"),
                }
                for log in db_logs
            ],
            "file_logs": file_logs,
        }
    )


@require_GET
def api_stats(request):
    stats = dashboard_stats()
    active = get_active_task()
    activity = [
        {
            "title": event.title,
            "detail": event.detail,
            "time_ago": _timesince(event.created_at),
            "type": event.event_type,
        }
        for event in recent_activity(8)
    ]
    return JsonResponse(
        {
            "stats": stats,
            "activity": activity,
            "task": task_status_payload(active),
            "session": session_status(),
        }
    )


@require_GET
def api_files(request):
    from apps.linkedin.services.filter_utils import filter_sort_files
    from apps.linkedin.services.stats import apply_preview_view_filters, preview_file

    files = list_output_files()
    search = request.GET.get("q", "")
    file_type = request.GET.get("type", "")
    sort_by = request.GET.get("sort", "date")
    sort_dir = request.GET.get("order", "desc")
    files = filter_sort_files(files, search, file_type, sort_by, sort_dir)

    selected = request.GET.get("file")
    preview_search = request.GET.get("preview_q", "")
    preview_sort = request.GET.get("preview_sort", "")
    preview_order = request.GET.get("preview_order", "asc")
    preview = None
    if selected:
        preview = preview_file(selected)
        if preview and not preview.get("error"):
            preview = apply_preview_view_filters(
                preview,
                preview_search=preview_search,
                preview_sort=preview_sort,
                preview_order=preview_order,
            )

    return JsonResponse({"files": files, "preview": preview, "selected": selected})


@require_GET
def api_session_status(request):
    return JsonResponse(session_status())


@require_POST
def api_settings_save(request):
    from apps.linkedin.forms import SettingsForm
    from apps.linkedin.services.settings_helpers import (
        form_to_settings,
        is_config_locked,
        settings_to_form,
    )

    body = _json_body(request)
    tab = body.get("tab", "job")
    active = get_active_task()
    if is_config_locked(active, settings_tab=tab):
        return JsonResponse(
            {
                "ok": False,
                "message": (
                    f"{active.get_task_type_display()} is {active.status}. "
                    "Stop it before changing settings."
                ),
            },
            status=409,
        )

    app_settings = load_settings()
    form = SettingsForm({**settings_to_form(app_settings, tab), **body})
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _form_errors(form)}, status=400)
    updated = form_to_settings(app_settings, form.cleaned_data)
    save_settings(updated)
    return JsonResponse({"ok": True, "message": "Settings saved", "settings": updated})


@require_POST
def api_browser_preview(request):
    body = _json_body(request)
    enabled = bool(body.get("enabled"))
    task = get_running_task() or get_active_task()

    # Allow enabling preview even when no scraper is currently running so the
    # UI can show the waiting placeholder. Still block enabling for session
    # login tasks which require a separate browser window.
    if enabled and task and task.task_type == ScraperTask.TASK_SESSION:
        return JsonResponse(
            {"ok": False, "message": "Session login uses a separate browser window for sign-in."},
            status=400,
        )

    set_preview_enabled(enabled, task.id if task else None)
    return JsonResponse(
        {
            "ok": True,
            "enabled": enabled,
            "task_id": task.id if task else None,
            "message": "Live scraping view opened in app."
            if enabled
            else "Live scraping view closed.",
        }
    )


@require_GET
def api_browser_screenshot(request):
    from django.http import FileResponse, HttpResponse

    state = get_preview_state()
    if not state.get("enabled"):
        return HttpResponse(status=204)

    task_id = state.get("task_id")
    if not task_id:
        return HttpResponse(status=204)

    path = screenshot_path(task_id)
    if not path.exists():
        return HttpResponse(status=204)

    response = FileResponse(open(path, "rb"), content_type="image/jpeg")
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@require_POST
def api_merge_files(request):
    body = _json_body(request)
    paths = body.get("paths") or []
    if not isinstance(paths, list):
        return JsonResponse({"ok": False, "message": "paths must be a list"}, status=400)

    try:
        from apps.linkedin.services.file_merge_service import merge_files

        result = merge_files(
            paths=paths,
            dedupe=bool(body.get("dedupe", True)),
            dedupe_column=body.get("dedupe_column") or None,
            output_format=body.get("output_format", "xlsx"),
        )
        return JsonResponse(
            {
                "ok": True,
                "message": f"Merged {result['records']} rows from {len(result['source_files'])} files.",
                "file": result,
            }
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    except OSError as exc:
        return JsonResponse(
            {"ok": False, "message": friendly_file_error(exc, action="merge")},
            status=409,
        )


@require_POST
def api_merge_preview(request):
    body = _json_body(request)
    paths = body.get("paths") or []
    if not isinstance(paths, list):
        return JsonResponse({"ok": False, "message": "paths must be a list"}, status=400)

    try:
        from apps.linkedin.services.file_merge_service import preview_merge

        preview = preview_merge(paths)
        return JsonResponse({"ok": True, "preview": preview})
    except ValueError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    except OSError as exc:
        locked_path = paths[0] if paths else None
        return JsonResponse(
            {
                "ok": False,
                "message": friendly_file_error(exc, locked_path, "preview"),
            },
            status=409,
        )


@require_POST
def api_delete_file(request):
    from apps.linkedin.services.trash_service import move_to_trash

    body = _json_body(request)
    path_str = body.get("path", "")
    try:
        trash_entry = move_to_trash(path_str)
        return JsonResponse(
            {
                "ok": True,
                "message": f"Moved \"{trash_entry['name']}\" to trash. Use the trash icon on Output to restore.",
                "trash_entry": trash_entry,
            }
        )
    except FileNotFoundError:
        return JsonResponse({"ok": False, "message": "File not found"}, status=404)
    except OSError as exc:
        file_path = Path(path_str)
        return JsonResponse(
            {"ok": False, "message": friendly_file_error(exc, file_path, "delete")},
            status=409,
        )


@require_POST
def api_restore_file(request):
    from apps.linkedin.services.trash_service import restore_from_trash

    body = _json_body(request)
    trash_id = body.get("id", "")
    if not trash_id:
        return JsonResponse({"ok": False, "message": "Missing trash id"}, status=400)
    try:
        result = restore_from_trash(trash_id)
        return JsonResponse({"ok": True, **result})
    except FileNotFoundError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=404)
    except FileExistsError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=409)
    except (ValueError, OSError) as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)


@require_POST
def api_permanent_delete_file(request):
    from apps.linkedin.services.trash_service import (
        permanent_delete_from_trash,
        permanent_delete_many_from_trash,
    )

    body = _json_body(request)
    ids = body.get("ids")
    if isinstance(ids, list) and ids:
        try:
            result = permanent_delete_many_from_trash(ids)
            status = 200 if result["count"] else 404
            return JsonResponse({"ok": result["count"] > 0, **result}, status=status)
        except ValueError as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)
        except OSError as exc:
            return JsonResponse(
                {"ok": False, "message": friendly_file_error(exc, action="delete")},
                status=409,
            )

    trash_id = body.get("id", "")
    if not trash_id:
        return JsonResponse({"ok": False, "message": "Missing trash id"}, status=400)
    try:
        result = permanent_delete_from_trash(trash_id)
        return JsonResponse({"ok": True, **result})
    except FileNotFoundError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=404)
    except OSError as exc:
        entry_path = body.get("path", "")
        return JsonResponse(
            {
                "ok": False,
                "message": friendly_file_error(exc, entry_path or None, "delete"),
            },
            status=409,
        )


def _timesince(dt):
    from django.utils import timezone

    delta = timezone.now() - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


# Require admin auth on all LinkedIn JSON APIs
api_task_status = _admin_api(api_task_status)
api_task_start = _admin_api(api_task_start)
api_task_control = _admin_api(api_task_control)
api_task_skip_searches = _admin_api(api_task_skip_searches)
api_logs = _admin_api(api_logs)
api_stats = _admin_api(api_stats)
api_files = _admin_api(api_files)
api_session_status = _admin_api(api_session_status)
api_settings_save = _admin_api(api_settings_save)
api_browser_preview = _admin_api(api_browser_preview)
api_browser_screenshot = _admin_api(api_browser_screenshot)
api_merge_files = _admin_api(api_merge_files)
api_merge_preview = _admin_api(api_merge_preview)
api_delete_file = _admin_api(api_delete_file)
api_restore_file = _admin_api(api_restore_file)
api_permanent_delete_file = _admin_api(api_permanent_delete_file)
