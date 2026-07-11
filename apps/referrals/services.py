"""Referral approval service."""
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.rewards.services import RewardService
from apps.notifications.services import EmailService, NotificationService

logger = logging.getLogger(__name__)


class ReferralService:
    @staticmethod
    @transaction.atomic
    def create_from_code(new_user, referral_code):
        from apps.accounts.models import StudentProfile
        from apps.referrals.models import Referral, ReferralHistory

        if not referral_code:
            return None
        try:
            referrer_profile = StudentProfile.objects.select_related("user").get(
                referral_code__iexact=referral_code.strip()
            )
        except StudentProfile.DoesNotExist:
            return None

        if referrer_profile.user_id == new_user.id:
            return None

        new_user.profile.referred_by = referrer_profile
        new_user.profile.save(update_fields=["referred_by", "updated_at"])

        referral, created = Referral.objects.get_or_create(
            referrer=referrer_profile.user,
            referred_user=new_user,
            defaults={
                "referral_code": referrer_profile.referral_code,
                "status": "pending",
            },
        )
        if created:
            ReferralHistory.objects.create(
                referral=referral,
                action="created",
                actor=new_user,
                details=f"Registered with code {referral_code}",
            )
        return referral

    @staticmethod
    @transaction.atomic
    def approve(referral, reviewer):
        from apps.referrals.models import Referral, ReferralHistory

        if referral.status == Referral.Status.APPROVED:
            return referral

        points = settings.REWARD_POINTS.get("referral_approved", 200)
        referral.status = Referral.Status.APPROVED
        referral.points_awarded = points
        referral.reviewed_by = reviewer
        referral.reviewed_at = timezone.now()
        referral.save()

        ReferralHistory.objects.create(
            referral=referral,
            action="approved",
            actor=reviewer,
            details=f"Awarded {points} points",
        )
        RewardService.award_points(
            referral.referrer,
            "referral_approved",
            points=points,
            description=f"Referral approved: {referral.referred_user.email}",
        )
        NotificationService.notify(
            referral.referrer,
            title="Referral approved!",
            message=f"Your referral of {referral.referred_user.email} was approved. +{points} points!",
            level="reward",
            link="/dashboard/referrals/",
        )
        EmailService.send_from_template(
            "referral_approved",
            referral.referrer.email,
            {
                "student_name": referral.referrer.get_full_name() or referral.referrer.email,
                "referred_email": referral.referred_user.email,
                "points": points,
            },
            recipient=referral.referrer,
        )
        return referral

    @staticmethod
    @transaction.atomic
    def reject(referral, reviewer, notes=""):
        from apps.referrals.models import Referral, ReferralHistory

        referral.status = Referral.Status.REJECTED
        referral.reviewed_by = reviewer
        referral.reviewed_at = timezone.now()
        referral.notes = notes
        referral.save()
        ReferralHistory.objects.create(
            referral=referral,
            action="rejected",
            actor=reviewer,
            details=notes or "Rejected",
        )
        return referral
