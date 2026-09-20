from django.urls import path

from apps.naukri import api_views, views

app_name = "naukri"

urlpatterns = [
    path("", views.naukri_home, name="home"),
    path("session/", views.session_view, name="session"),
    path("output/", views.output_view, name="output"),
    path("download/", views.download_file, name="download"),
    path("api/task/status/", api_views.api_task_status, name="api_task_status"),
    path("api/task/start/", api_views.api_task_start, name="api_task_start"),
    path("api/task/control/", api_views.api_task_control, name="api_task_control"),
    path("api/files/", api_views.api_files, name="api_files"),
    path("api/session/", api_views.api_session_status, name="api_session_status"),
    path("api/browser/preview/", api_views.api_browser_preview, name="api_browser_preview"),
    path("api/browser/screenshot/", api_views.api_browser_screenshot, name="api_browser_screenshot"),
]
