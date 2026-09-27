from django.db import models
from django.utils import timezone


class ScraperTask(models.Model):
    TASK_JOB = "job"
    TASK_PERFECT_MATCH = "perfect_match"
    TASK_CONNECTION = "connection"
    TASK_POSTS = "posts"
    TASK_SESSION = "session"

    TASK_TYPES = [
        (TASK_JOB, "Job Scraper"),
        (TASK_PERFECT_MATCH, "Perfect Match Job Search"),
        (TASK_CONNECTION, "Connection Scraper"),
        (TASK_POSTS, "Posts Scraper"),
        (TASK_SESSION, "LinkedIn Session"),
    ]

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_STOPPED = "stopped"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_STOPPED, "Stopped"),
    ]

    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    config = models.JSONField(default=dict, blank=True)
    progress = models.JSONField(default=dict, blank=True)
    pid = models.IntegerField(null=True, blank=True)
    run_in_background = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_task_type_display()} #{self.pk} ({self.status})"

    @property
    def is_active(self):
        return self.status in {self.STATUS_PENDING, self.STATUS_RUNNING, self.STATUS_PAUSED}

    def mark_running(self, pid=None):
        self.status = self.STATUS_RUNNING
        self.started_at = timezone.now()
        if pid is not None:
            self.pid = pid
        self.save(update_fields=["status", "started_at", "pid"])

    def mark_finished(self, status, error_message=""):
        self.status = status
        self.finished_at = timezone.now()
        self.error_message = error_message or ""
        self.pid = None
        self.save(update_fields=["status", "finished_at", "error_message", "pid"])


class TaskLog(models.Model):
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"
    LEVEL_SUCCESS = "success"

    LEVEL_CHOICES = [
        (LEVEL_INFO, "Info"),
        (LEVEL_WARNING, "Warning"),
        (LEVEL_ERROR, "Error"),
        (LEVEL_SUCCESS, "Success"),
    ]

    task = models.ForeignKey(
        ScraperTask, on_delete=models.CASCADE, related_name="logs", null=True, blank=True
    )
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.level}] {self.message[:60]}"


class ActivityEvent(models.Model):
    event_type = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
