from django.contrib import admin
from .models import FreeClass, Registration


class RegistrationInline(admin.TabularInline):
    model = Registration
    extra = 0
    readonly_fields = ("created_at",)
    autocomplete_fields = ("student",)


@admin.register(FreeClass)
class FreeClassAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "technology",
        "date",
        "start_time",
        "status",
        "max_seats",
        "is_featured",
    )
    list_filter = ("status", "technology", "is_featured")
    search_fields = ("title", "technology", "tags", "instructor_name")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [RegistrationInline]
    date_hierarchy = "date"


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "free_class", "status", "confirmation_sent", "reminder_sent", "created_at")
    list_filter = ("status", "confirmation_sent", "reminder_sent")
    search_fields = ("student__email", "free_class__title")
    autocomplete_fields = ("student", "free_class")
    actions = ["resend_confirmation"]

    @admin.action(description="Resend confirmation email")
    def resend_confirmation(self, request, queryset):
        from apps.classes.services import RegistrationService

        for reg in queryset:
            RegistrationService.send_confirmation(reg)
        self.message_user(request, f"Resent {queryset.count()} confirmation emails.")
