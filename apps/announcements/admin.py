from django.contrib import admin
from .models import Announcement, AnnouncementAttachment


class AttachmentInline(admin.TabularInline):
    model = AnnouncementAttachment
    extra = 1


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_pinned", "is_published", "published_at", "views")
    list_filter = ("category", "is_pinned", "is_published")
    search_fields = ("title", "content", "summary")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [AttachmentInline]
    date_hierarchy = "published_at"
