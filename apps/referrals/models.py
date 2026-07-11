"""Referral system with admin approval."""
from django.conf import settings
from django.db import models
from apps.core.basemodels import BaseModel


class Referral(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals_sent"
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_received"
    )
    referral_code = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    points_awarded = models.PositiveIntegerField(default=0)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("referrer", "referred_user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer.email} → {self.referred_user.email} ({self.status})"


class ReferralHistory(BaseModel):
    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=50)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Referral histories"

    def __str__(self):
        return f"{self.action} on referral #{self.referral_id}"
