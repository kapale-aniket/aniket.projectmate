from django.contrib import admin
from .models import Attendance
from apps.attendance.services import AttendanceService


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "free_class", "status", "join_time", "leave_time", "points_awarded")
    list_filter = ("status", "points_awarded", "free_class")
    search_fields = ("student__email", "free_class__title")
    autocomplete_fields = ("student", "free_class", "marked_by")
    actions = ["mark_present", "mark_absent"]

    @admin.action(description="Mark selected as Present")
    def mark_present(self, request, queryset):
        for att in queryset:
            AttendanceService.mark(
                att.student, att.free_class, Attendance.Status.PRESENT, marked_by=request.user
            )
        self.message_user(request, f"Marked {queryset.count()} as present.")

    @admin.action(description="Mark selected as Absent")
    def mark_absent(self, request, queryset):
        for att in queryset:
            AttendanceService.mark(
                att.student, att.free_class, Attendance.Status.ABSENT, marked_by=request.user
            )
        self.message_user(request, f"Marked {queryset.count()} as absent.")
