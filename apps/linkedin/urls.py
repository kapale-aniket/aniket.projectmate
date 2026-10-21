from django.urls import path
from apps.linkedin import views, api_views

app_name = "linkedin"

urlpatterns = [
    path("", views.linkedin_home, name="home"),
    path("jobs/", views.job_scraper, name="jobs"),
    path("perfect-match/", views.perfect_match_scraper, name="perfect_match"),
    path("connections/", views.connection_scraper, name="connections"),
    path("perfect-connection/", views.perfect_connection_scraper, name="perfect_connection"),
    path("api/perfect-connection/preview/", api_views.api_perfect_connection_preview, name="api_perfect_connection_preview"),
    path("posts/", views.posts_scraper, name="posts"),
    path("session/", views.session_manager, name="session"),
    path("logs/", views.logs_view, name="logs"),
    path("output/", views.output_view, name="output"),
    path("output/restore/", views.restore_trashed_file, name="restore_trashed_file"),
    path("trash/", views.trash_view, name="trash"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/users/", views.linkedin_users, name="users"),
    path("download/", views.download_file, name="download"),
    # JSON API
    path("api/task/status/", api_views.api_task_status, name="api_task_status"),
    path("api/task/start/", api_views.api_task_start, name="api_task_start"),
    path("api/task/control/", api_views.api_task_control, name="api_task_control"),
    path("api/task/skip-searches/", api_views.api_task_skip_searches, name="api_task_skip_searches"),
    path("api/logs/", api_views.api_logs, name="api_logs"),
    path("api/stats/", api_views.api_stats, name="api_stats"),
    path("api/files/", api_views.api_files, name="api_files"),
    path("api/settings/", api_views.api_settings_save, name="api_settings_save"),
    path("api/session/", api_views.api_session_status, name="api_session_status"),
    path("api/files/delete/", api_views.api_delete_file, name="api_delete_file"),
    path("api/files/restore/", api_views.api_restore_file, name="api_restore_file"),
    path("api/files/trash/delete/", api_views.api_permanent_delete_file, name="api_permanent_delete_file"),
    path("api/files/merge/", api_views.api_merge_files, name="api_merge_files"),
    path("api/files/merge/preview/", api_views.api_merge_preview, name="api_merge_preview"),
    path("api/browser/preview/", api_views.api_browser_preview, name="api_browser_preview"),
    path("api/browser/screenshot/", api_views.api_browser_screenshot, name="api_browser_screenshot"),
]
