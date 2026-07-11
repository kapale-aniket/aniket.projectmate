from django.contrib import admin
from .models import Referral, ReferralHistory
from apps.referrals.services import ReferralService


class ReferralHistoryInline(admin.TabularInline):
    model = ReferralHistory
    extra = 0
    readonly_fields = ("action", "actor", "details", "created_at")


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        "referrer",
        "referred_user",
        "referral_code",
        "status",
        "points_awarded",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("referrer__email", "referred_user__email", "referral_code")
    autocomplete_fields = ("referrer", "referred_user", "reviewed_by")
    inlines = [ReferralHistoryInline]
    actions = ["approve_referrals", "reject_referrals"]

    @admin.action(description="Approve selected referrals")
    def approve_referrals(self, request, queryset):
        for ref in queryset.filter(status="pending"):
            ReferralService.approve(ref, request.user)
        self.message_user(request, "Referrals approved.")

    @admin.action(description="Reject selected referrals")
    def reject_referrals(self, request, queryset):
        for ref in queryset.filter(status="pending"):
            ReferralService.reject(ref, request.user)
        self.message_user(request, "Referrals rejected.")


@admin.register(ReferralHistory)
class ReferralHistoryAdmin(admin.ModelAdmin):
    list_display = ("referral", "action", "actor", "created_at")
    readonly_fields = ("created_at",)
