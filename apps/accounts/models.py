"""Custom user and student profile models."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.text import slugify
import uuid
from apps.core.basemodels import BaseModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=extra_fields.pop("username", email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        INSTRUCTOR = "instructor", "Instructor"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    is_email_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    last_login_reward_at = models.DateField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_platform_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser


class StudentProfile(BaseModel):
    YEAR_CHOICES = [
        ("1", "1st Year"),
        ("2", "2nd Year"),
        ("3", "3rd Year"),
        ("4", "4th Year"),
        ("pg", "Post Graduate"),
        ("other", "Other"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True)
    college = models.CharField(max_length=200, blank=True)
    college_location = models.CharField(
        max_length=200,
        blank=True,
        help_text="City / area where the college is located",
    )
    branch = models.CharField(max_length=120, blank=True)
    year = models.CharField(max_length=10, choices=YEAR_CHOICES, blank=True)
    city = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    skills = models.TextField(blank=True, help_text="Comma-separated skills")
    resume = models.FileField(upload_to="resumes/", blank=True, null=True)
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    referred_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals_made",
    )
    reward_points = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    profile_completed = models.BooleanField(default=False)
    consecutive_attendance = models.PositiveIntegerField(default=0)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["-reward_points", "user__email"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} Profile"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            base = slugify(self.user.username or self.user.email.split("@")[0])[:8].upper()
            self.referral_code = f"{base}{uuid.uuid4().hex[:4].upper()}"
        self.profile_completed = self.compute_profile_completed()
        self.level = max(1, (self.reward_points // 500) + 1)
        super().save(*args, **kwargs)

    def compute_profile_completed(self):
        required = [self.phone, self.college, self.branch, self.year, self.city]
        return all(required) and bool(self.user.first_name)

    def skill_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]


class ActivityLog(BaseModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="activities", null=True, blank=True
    )
    action = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M}"
