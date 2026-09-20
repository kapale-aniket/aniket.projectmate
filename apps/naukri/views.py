from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.naukri.forms import NaukriApplyForm
from apps.naukri.models import NaukriTask
from apps.naukri.services import task_manager


def _admin_required(view):
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect("adminpanel:login")
        if not (user.is_staff or user.is_superuser or getattr(user, "role", "") == "admin"):
            messages.error(request, "Admin access required.")
            return redirect("adminpanel:login")
        return view(request, *args, **kwargs)

    return wrapper


def _base_context(request, nav="home"):
    active = task_manager.get_active_task()
    return {
        "naukri_nav": nav,
        "session_ready": task_manager.session_exists(),
        "active_task": active,
        "output_files": task_manager.list_output_files()[:20],
    }


@_admin_required
def naukri_home(request):
    form = NaukriApplyForm(
        initial={
            "job_keyword": "python",
            "multi_apply_batch_size": 5,
            "headless": False,
        }
    )
    ctx = _base_context(request, "home")
    ctx["form"] = form
    return render(request, "adminpanel/naukri/index.html", ctx)


@_admin_required
def session_view(request):
    ctx = _base_context(request, "session")
    return render(request, "adminpanel/naukri/session.html", ctx)


@_admin_required
def output_view(request):
    ctx = _base_context(request, "output")
    return render(request, "adminpanel/naukri/output.html", ctx)


@_admin_required
@require_GET
def download_file(request):
    name = (request.GET.get("name") or "").strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        raise Http404("Invalid file")
    path = Path(settings.NAUKRI_AUTOMATION_ROOT) / "output" / name
    if not path.exists() or not path.is_file():
        raise Http404("File not found")
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)
