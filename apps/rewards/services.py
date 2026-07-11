"""Reward / gamification service layer."""
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class RewardService:
    @staticmethod
    @transaction.atomic
    def award_points(user, reason, points=None, description="", metadata=None):
        from apps.rewards.models import Reward, Achievement, StudentAchievement
        from apps.notifications.services import NotificationService

        if points is None:
            from apps.rewards.models import RewardRule

            points = RewardRule.points_for(reason, settings.REWARD_POINTS.get(reason, 0))
        if not points:
            return None

        reward = Reward.objects.create(
            student=user,
            points=points,
            reason=reason,
            description=description or reason.replace("_", " ").title(),
            metadata=metadata or {},
        )
        profile = user.profile
        profile.reward_points = max(0, profile.reward_points + points)
        profile.save(update_fields=["reward_points", "level", "updated_at"])

        # Unlock achievements by points threshold
        for achievement in Achievement.objects.filter(
            is_active=True, points_required__lte=profile.reward_points
        ):
            StudentAchievement.objects.get_or_create(student=user, achievement=achievement)

        NotificationService.notify(
            user,
            title=f"+{points} points earned!",
            message=description or f"You earned {points} points for {reason.replace('_', ' ')}.",
            level="reward",
            link="/dashboard/rewards/",
        )
        logger.info("Awarded %s points to %s for %s", points, user.email, reason)
        return reward

    @staticmethod
    def award_daily_login(user):
        today = timezone.localdate()
        if user.last_login_reward_at == today:
            return None
        user.last_login_reward_at = today
        user.save(update_fields=["last_login_reward_at"])
        return RewardService.award_points(
            user, "daily_login", description="Daily login bonus"
        )

    @staticmethod
    def check_profile_completion(user):
        profile = user.profile
        if profile.compute_profile_completed() and not profile.profile_completed:
            profile.profile_completed = True
            profile.save(update_fields=["profile_completed", "updated_at"])
            return RewardService.award_points(
                user, "profile_completed", description="Profile completed"
            )
        return None
