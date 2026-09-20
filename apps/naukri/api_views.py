import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.naukri.forms import NaukriApplyForm
from apps.naukri.models import NaukriTask
from apps.naukri.services import task_manager
from apps.naukri.views import _admin_required


@_admin_required
@require_GET
def api_task_status(request):
    task_id = request.GET.get("id")
    task = None
    if task_id:
        task = NaukriTask.objects.filter(pk=task_id).first()
    return JsonResponse(task_manager.task_status_payload(task))


@_admin_required
@require_POST
def api_task_start(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "message": "Invalid JSON"}, status=400)

    task_type = (payload.get("task_type") or NaukriTask.TASK_APPLY).strip()
    if task_type not in {NaukriTask.TASK_APPLY, NaukriTask.TASK_SESSION}:
        return JsonResponse({"ok": False, "message": "Unknown task type"}, status=400)

    config = {}
    if task_type == NaukriTask.TASK_APPLY:
        form = NaukriApplyForm(data=payload)
        if not form.is_valid():
            return JsonResponse({"ok": False, "message": "Invalid form", "errors": form.errors}, status=400)
        config = {
            "job_keyword": form.cleaned_data.get("job_keyword") or "python",
            "multi_apply_batch_size": form.cleaned_data.get("multi_apply_batch_size") or 5,
            "headless": bool(form.cleaned_data.get("headless")),
        }

    try:
        task = task_manager.start_task(task_type, config=config)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=409)

    return JsonResponse(
        {
            "ok": True,
            "message": f"{task.get_task_type_display()} started",
            "task": task_manager.task_status_payload(task)["task"],
        }
    )


@_admin_required
@require_POST
def api_task_control(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "message": "Invalid JSON"}, status=400)

    action = (payload.get("action") or "").strip().lower()
    task_id = payload.get("task_id") or payload.get("id")
    if action == "stop":
        result = task_manager.stop_task(task_id)
        return JsonResponse(result, status=200 if result.get("ok") else 400)
    return JsonResponse({"ok": False, "message": f"Unknown action: {action}"}, status=400)


@_admin_required
@require_GET
def api_files(request):
    return JsonResponse({"ok": True, "files": task_manager.list_output_files()})


@_admin_required
@require_GET
def api_session_status(request):
    return JsonResponse({"ok": True, "session_ready": task_manager.session_exists()})


@_admin_required
@require_POST
def api_browser_preview(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "message": "Invalid JSON"}, status=400)

    enabled = bool(payload.get("enabled"))
    task_id = payload.get("task_id")
    task = None
    if task_id:
        task = NaukriTask.objects.filter(pk=task_id).first()
    if not task:
        task = task_manager.get_active_task()

    from apps.linkedin.services.browser_preview import set_preview_enabled

    set_preview_enabled(enabled, task.id if task else None)
    return JsonResponse(
        {
            "ok": True,
            "enabled": enabled,
            "task_id": task.id if task else None,
            "message": "Live Naukri view enabled." if enabled else "Live Naukri view closed.",
        }
    )


@_admin_required
@require_GET
def api_browser_screenshot(request):
    from django.http import FileResponse, HttpResponse
    from apps.linkedin.services.browser_preview import get_state, screenshot_path

    state = get_state()
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
