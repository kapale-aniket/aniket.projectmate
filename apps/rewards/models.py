"""Gamification — rewards, achievements, badges, leaderboard."""
from django.conf import settings
from django.db import models
from apps.core.basemodels import BaseModel


class Reward(BaseModel):
    class Reason(models.TextChoices):
        ATTEND_CLASS = "attend_class", "Attend Class"
        ATTEND_CLASS_ACTIVE = "attend_class_active", "Active in Session"
        DAILY_LOGIN = "daily_login", "Daily Login"
        PROFILE_COMPLETED = "profile_completed", "Profile Completed"
        FEEDBACK_SUBMITTED = "feedback_submitted", "Feedback Submitted"
        REFERRAL_APPROVED = "referral_approved", "Referral Approved"
        WORKSHOP_COMPLETED = "workshop_completed", "Workshop Completed"
        RESUME_UPLOADED = "resume_uploaded", "Resume Uploaded"
        CONSISTENCY = "consistency", "Consistency Reward"
        MANUAL = "manual", "Manual Adjustment"
        OTHER = "other", "Other"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rewards"
    )
    points = models.IntegerField()
    reason = models.CharField(max_length=40, choices=Reason.choices, default=Reason.OTHER)
    description = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.email}: {self.points:+d} ({self.reason})"


class RewardRule(BaseModel):
    """Admin-configurable point rules (overrides settings.REWARD_POINTS when active)."""

    code = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=120)
    points = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.label}: {self.points:+d}"

    @classmethod
    def points_for(cls, code, fallback=0):
        rule = cls.objects.filter(code=code, is_active=True).first()
        if rule:
            return rule.points
        from django.conf import settings

        return settings.REWARD_POINTS.get(code, fallback)


class Achievement(BaseModel):
    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default="fa-trophy")
    badge_color = models.CharField(max_length=7, default="#f59e0b")
    points_required = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["points_required", "title"]

    def __str__(self):
        return self.title


class StudentAchievement(BaseModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements"
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="awarded_to")

    class Meta:
        unique_together = ("student", "achievement")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.email} — {self.achievement.title}"


class Certificate(BaseModel):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    free_class = models.ForeignKey(
        "classes.FreeClass", on_delete=models.SET_NULL, null=True, blank=True
    )
    course = models.ForeignKey(
        "courses.PaidCourse", on_delete=models.SET_NULL, null=True, blank=True
    )
    file = models.FileField(upload_to="certificates/", blank=True, null=True)
    issued_at = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.title} — {self.student.email}"


class ResumeUpload(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        IN_REVIEW = "in_review", "In Review"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_uploads"
    )
    file = models.FileField(upload_to="resume_reviews/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_reward_eligible = models.BooleanField(
        default=False, help_text="Earned via 6 consecutive attendance"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Resume — {self.student.email} ({self.status})"


class ResumeReview(BaseModel):
    resume_upload = models.ForeignKey(
        ResumeUpload, on_delete=models.CASCADE, related_name="reviews"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reviews_given"
    )
    feedback = models.TextField()
    score = models.PositiveIntegerField(null=True, blank=True, help_text="1-10")
    emailed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review for {self.resume_upload.student.email}"
