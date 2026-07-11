"""Feedback signals — award points on approval."""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender="feedback.Feedback")
def track_feedback_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender="feedback.Feedback")
def on_feedback_approved(sender, instance, created, **kwargs):
    from apps.rewards.services import RewardService

    old = getattr(instance, "_old_status", None)
    if (
        instance.status == "approved"
        and old != "approved"
        and not instance.points_awarded
    ):
        RewardService.award_points(
            instance.student,
            "feedback_submitted",
            description="Feedback approved and published",
        )
        instance.points_awarded = True
        sender.objects.filter(pk=instance.pk).update(points_awarded=True)
