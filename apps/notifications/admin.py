from django.contrib import admin
from .models import EmailTemplate, EmailLog, Notification


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "subject", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "subject")


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("to_email", "subject", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("to_email", "subject")
    readonly_fields = ("created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "level", "is_read", "created_at")
    list_filter = ("level", "is_read")
    search_fields = ("user__email", "title", "message")
    autocomplete_fields = ("user",)
