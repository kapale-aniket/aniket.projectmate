from django.contrib import admin
from .models import PaidCourse, CourseEnrollment


class EnrollmentInline(admin.TabularInline):
    model = CourseEnrollment
    extra = 0
    autocomplete_fields = ("student",)


@admin.register(PaidCourse)
class PaidCourseAdmin(admin.ModelAdmin):
    list_display = ("title", "technology", "price", "discount_price", "status", "is_featured")
    list_filter = ("technology", "status", "is_featured")
    search_fields = ("title", "short_description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [EnrollmentInline]


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "status", "amount_paid", "created_at")
    list_filter = ("status",)
    search_fields = ("student__email", "course__title", "payment_reference")
    autocomplete_fields = ("student", "course")
