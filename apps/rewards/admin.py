from django.contrib import admin
from .models import (
    Reward,
    Achievement,
    StudentAchievement,
    ResumeUpload,
    ResumeReview,
)


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("student", "points", "reason", "description", "created_at")
    list_filter = ("reason",)
    search_fields = ("student__email", "description")
    autocomplete_fields = ("student",)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "points_required", "is_active")
    search_fields = ("title", "code")
    prepopulated_fields = {"code": ("title",)}


@admin.register(StudentAchievement)
class StudentAchievementAdmin(admin.ModelAdmin):
    list_display = ("student", "achievement", "created_at")
    autocomplete_fields = ("student", "achievement")


class ResumeReviewInline(admin.StackedInline):
    model = ResumeReview
    extra = 0


@admin.register(ResumeUpload)
class ResumeUploadAdmin(admin.ModelAdmin):
    list_display = ("student", "status", "is_reward_eligible", "created_at")
    list_filter = ("status", "is_reward_eligible")
    search_fields = ("student__email",)
    autocomplete_fields = ("student",)
    inlines = [ResumeReviewInline]


@admin.register(ResumeReview)
class ResumeReviewAdmin(admin.ModelAdmin):
    list_display = ("resume_upload", "reviewer", "score", "emailed", "created_at")
    autocomplete_fields = ("resume_upload", "reviewer")
