from django.contrib import admin
from .models import Feedback
from .services import FeedbackService


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "rating",
        "status",
        "is_featured",
        "show_on_landing",
        "admin_liked",
        "created_at",
    )
    list_filter = ("status", "rating", "is_featured", "show_on_landing", "admin_liked")
    search_fields = ("student__email", "review", "suggestions")
    autocomplete_fields = ("student", "reviewed_by")
    actions = ["approve_feedback", "reject_feedback"]

    @admin.action(description="Approve & show on landing (present/active only)")
    def approve_feedback(self, request, queryset):
        approved = 0
        blocked = 0
        for fb in queryset.select_related("student", "free_class"):
            ok, _reason = FeedbackService.can_approve(fb)
            if not ok:
                blocked += 1
                continue
            fb.status = "approved"
            fb.show_on_landing = True
            fb.reviewed_by = request.user
            fb.save()
            approved += 1
        if approved:
            self.message_user(request, f"{approved} feedback item(s) approved.")
        if blocked:
            self.message_user(
                request,
                f"{blocked} skipped — student must be present/active (not absent).",
                level="WARNING",
            )

    @admin.action(description="Reject selected")
    def reject_feedback(self, request, queryset):
        queryset.update(status="rejected", reviewed_by=request.user)
        self.message_user(request, "Feedback rejected.")
