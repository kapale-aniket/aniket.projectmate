"""DRF serializers for ProjectMate API — all inherit BaseModelSerializer."""
from rest_framework import serializers
from apps.api.base_serializers import BaseSerializer, BaseModelSerializer, ReadOnlyModelSerializer
from apps.accounts.models import User, StudentProfile
from apps.announcements.models import Announcement
from apps.classes.models import FreeClass, Registration
from apps.courses.models import PaidCourse
from apps.attendance.models import Attendance
from apps.rewards.models import Reward, Achievement
from apps.referrals.models import Referral
from apps.feedback.models import Feedback
from apps.notifications.models import Notification


class UserSerializer(ReadOnlyModelSerializer):
    class Meta(BaseModelSerializer.Meta):
        model = User
        fields = ("id", "email", "first_name", "last_name", "role", "date_joined")


class StudentProfileSerializer(BaseModelSerializer):
    user = UserSerializer(read_only=True)
    skills_list = serializers.SerializerMethodField()

    class Meta(BaseModelSerializer.Meta):
        model = StudentProfile
        fields = (
            "id",
            "user",
            "phone",
            "college",
            "college_location",
            "branch",
            "year",
            "city",
            "bio",
            "profile_picture",
            "linkedin_url",
            "github_url",
            "portfolio_url",
            "skills",
            "skills_list",
            "referral_code",
            "reward_points",
            "level",
            "profile_completed",
            "consecutive_attendance",
            "attendance_percentage",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "referral_code",
            "reward_points",
            "level",
            "profile_completed",
            "consecutive_attendance",
            "attendance_percentage",
            "created_at",
            "updated_at",
        )

    def get_skills_list(self, obj):
        return obj.skill_list()


class AnnouncementSerializer(ReadOnlyModelSerializer):
    class Meta(BaseModelSerializer.Meta):
        model = Announcement
        fields = (
            "id",
            "title",
            "slug",
            "category",
            "content",
            "summary",
            "is_pinned",
            "published_at",
            "cover_image",
            "views",
            "created_at",
        )


class FreeClassSerializer(ReadOnlyModelSerializer):
    seats_left = serializers.IntegerField(read_only=True)
    is_registration_open = serializers.BooleanField(read_only=True)
    registered_count = serializers.IntegerField(read_only=True)

    class Meta(BaseModelSerializer.Meta):
        model = FreeClass
        fields = (
            "id",
            "title",
            "slug",
            "technology",
            "description",
            "date",
            "start_time",
            "duration_minutes",
            "banner",
            "instructor_name",
            "max_seats",
            "tags",
            "status",
            "is_featured",
            "seats_left",
            "is_registration_open",
            "registered_count",
            "created_at",
        )


class RegistrationSerializer(BaseModelSerializer):
    free_class = FreeClassSerializer(read_only=True)
    free_class_id = serializers.PrimaryKeyRelatedField(
        queryset=FreeClass.objects.all(), source="free_class", write_only=True
    )

    class Meta(BaseModelSerializer.Meta):
        model = Registration
        fields = ("id", "free_class", "free_class_id", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")


class PaidCourseSerializer(ReadOnlyModelSerializer):
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    features_list = serializers.SerializerMethodField()

    class Meta(BaseModelSerializer.Meta):
        model = PaidCourse
        fields = (
            "id",
            "title",
            "slug",
            "technology",
            "short_description",
            "description",
            "curriculum",
            "price",
            "discount_price",
            "effective_price",
            "duration_weeks",
            "duration_hours",
            "image",
            "instructor_name",
            "features_list",
            "prerequisites",
            "is_featured",
            "start_date",
            "created_at",
        )

    def get_features_list(self, obj):
        return obj.feature_list()


class AttendanceSerializer(BaseModelSerializer):
    class Meta(BaseModelSerializer.Meta):
        model = Attendance
        fields = (
            "id",
            "student",
            "free_class",
            "status",
            "join_time",
            "leave_time",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class RewardSerializer(ReadOnlyModelSerializer):
    class Meta(BaseModelSerializer.Meta):
        model = Reward
        fields = ("id", "points", "reason", "description", "created_at")


class AchievementSerializer(ReadOnlyModelSerializer):
    class Meta(BaseModelSerializer.Meta):
        model = Achievement
        fields = ("id", "code", "title", "description", "icon", "badge_color", "points_required")


class ReferralSerializer(ReadOnlyModelSerializer):
    referred_email = serializers.EmailField(source="referred_user.email", read_only=True)

    class Meta(BaseModelSerializer.Meta):
        model = Referral
        fields = (
            "id",
            "referral_code",
            "referred_email",
            "status",
            "points_awarded",
            "created_at",
        )


class FeedbackSerializer(BaseModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta(BaseModelSerializer.Meta):
        model = Feedback
        fields = (
            "id",
            "rating",
            "review",
            "suggestions",
            "status",
            "student_name",
            "created_at",
        )
        read_only_fields = ("id", "status", "student_name", "created_at")

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.email.split("@")[0]


class NotificationSerializer(ReadOnlyModelSerializer):
    class Meta(BaseModelSerializer.Meta):
        model = Notification
        fields = ("id", "title", "message", "level", "link", "is_read", "created_at")


class DashboardSerializer(BaseSerializer):
    profile = StudentProfileSerializer()
    reward_points = serializers.IntegerField()
    level = serializers.IntegerField()
    upcoming_count = serializers.IntegerField()
    attendance_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    unread_notifications = serializers.IntegerField()
