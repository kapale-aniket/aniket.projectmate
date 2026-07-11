from django.contrib import admin
from .models import ScraperTask, TaskLog, ActivityEvent


@admin.register(ScraperTask)
class ScraperTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "task_type", "status", "created_at", "finished_at")
    list_filter = ("task_type", "status")


@admin.register(TaskLog)
class TaskLogAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "level", "created_at")
    list_filter = ("level",)


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "title", "created_at")
