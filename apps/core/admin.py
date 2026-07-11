from django.contrib import admin
from .models import (
    SiteSettings,
    FAQ,
    GalleryImage,
    CourseCategory,
    SuccessStory,
    ContactMessage,
    ProjectIdea,
    ProjectPlan,
    ProjectPlanPerk,
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Brand", {"fields": ("site_name", "tagline", "logo", "favicon", "primary_color", "secondary_color", "default_theme")}),
        ("Social", {"fields": (
            "instagram_url", "whatsapp_url", "youtube_url", "linkedin_url",
            "twitter_url", "github_url", "default_meet_link",
            "show_whatsapp_icon", "show_instagram_icon", "show_linkedin_icon", "show_youtube_icon",
        )}),
        ("Contact", {"fields": ("contact_email", "contact_phone", "contact_address")}),
        ("Content", {"fields": ("footer_text", "meta_description", "meta_keywords", "login_trust_message", "about_mentor", "mentor_name", "mentor_photo", "mentor_title", "why_learn_with_us")}),
        ("Status", {"fields": ("is_active",)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "is_published")
    list_editable = ("order", "is_published")


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_published", "created_at")
    list_editable = ("order", "is_published")


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("order", "is_active")


@admin.register(SuccessStory)
class SuccessStoryAdmin(admin.ModelAdmin):
    list_display = ("student_name", "company", "role", "is_featured", "is_published")
    list_filter = ("is_featured", "is_published")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("name", "email", "subject")
    readonly_fields = ("created_at",)


@admin.register(ProjectIdea)
class ProjectIdeaAdmin(admin.ModelAdmin):
    list_display = ("project_title", "name", "email", "selected_plan", "status", "created_at")
    list_filter = ("status", "selected_plan")
    search_fields = ("name", "email", "project_title", "idea")
    list_editable = ("status",)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("selected_plan",)


@admin.register(ProjectPlan)
class ProjectPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "display_price", "order", "is_highlighted", "is_active")
    list_editable = ("order", "is_highlighted", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "tagline")

    @admin.display(description="Price")
    def display_price(self, obj):
        return obj.display_price


@admin.register(ProjectPlanPerk)
class ProjectPlanPerkAdmin(admin.ModelAdmin):
    list_display = ("title", "icon", "order", "is_active")
    list_editable = ("order", "is_active")
