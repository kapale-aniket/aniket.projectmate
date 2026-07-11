from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, StudentProfile, ActivityLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_staff", "date_joined")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name", "username")
    ordering = ("-date_joined",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("ProjectMate", {"fields": ("role", "is_email_verified", "last_login_reward_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2", "role"),
            },
        ),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "college",
        "college_location",
        "branch",
        "year",
        "city",
        "reward_points",
        "level",
        "referral_code",
        "profile_completed",
    )
    list_filter = ("year", "profile_completed", "level")
    search_fields = ("user__email", "college", "college_location", "city", "referral_code", "phone")
    readonly_fields = ("referral_code", "created_at", "updated_at")
    actions = ["export_excel"]

    @admin.action(description="Export selected to Excel")
    def export_excel(self, request, queryset):
        from apps.core.exports import export_queryset_xlsx

        return export_queryset_xlsx(
            queryset,
            "students.xlsx",
            [
                ("Email", "user.email"),
                ("Name", "user.get_full_name"),
                ("College", "college"),
                ("College location", "college_location"),
                ("Branch", "branch"),
                ("City", "city"),
                ("Points", "reward_points"),
                ("Referral", "referral_code"),
            ],
        )


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "ip_address", "created_at")
    list_filter = ("action",)
    search_fields = ("user__email", "action", "description")
    readonly_fields = ("created_at",)
