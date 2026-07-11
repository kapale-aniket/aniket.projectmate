"""DRF viewsets for ProjectMate API — all inherit BaseAPI bases."""
from rest_framework import mixins, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from apps.announcements.models import Announcement
from apps.classes.models import FreeClass, Registration
from apps.courses.models import PaidCourse
from apps.attendance.models import Attendance
from apps.rewards.models import Reward, Achievement
from apps.referrals.models import Referral
from apps.feedback.models import Feedback
from apps.notifications.models import Notification
from apps.accounts.models import StudentProfile
from apps.classes.services import RegistrationService
from apps.api.base_views import (
    BaseAPIViewSet,
    BaseSlugReadOnlyAPIViewSet,
    BaseReadOnlyAPIViewSet,
    BaseStudentOwnedAPIViewSet,
    IsAdminOrReadOnly,
)
from .serializers import (
    AnnouncementSerializer,
    FreeClassSerializer,
    RegistrationSerializer,
    PaidCourseSerializer,
    AttendanceSerializer,
    RewardSerializer,
    AchievementSerializer,
    ReferralSerializer,
    FeedbackSerializer,
    NotificationSerializer,
    StudentProfileSerializer,
    UserSerializer,
    DashboardSerializer,
)


class AnnouncementViewSet(BaseSlugReadOnlyAPIViewSet):
    queryset = Announcement.objects.visible()
    serializer_class = AnnouncementSerializer
    search_fields = ("title", "content", "summary")
    filterset_fields = ("category", "is_pinned")


class FreeClassViewSet(BaseSlugReadOnlyAPIViewSet):
    queryset = FreeClass.public_queryset()
    serializer_class = FreeClassSerializer
    search_fields = ("title", "technology", "tags")
    filterset_fields = ("status", "technology", "is_featured")

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def register(self, request, slug=None):
        free_class = self.get_object()
        try:
            reg = RegistrationService.register(request.user, free_class)
            return self.success_response(
                data=RegistrationSerializer(reg).data,
                message="Registered successfully",
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            from django.core.exceptions import ValidationError

            if isinstance(exc, ValidationError):
                msg = exc.messages[0] if hasattr(exc, "messages") else str(exc)
                return self.error_response(message=msg)
            raise


class RegistrationViewSet(BaseStudentOwnedAPIViewSet):
    serializer_class = RegistrationSerializer
    queryset = Registration.objects.all()
    owner_field = "student"
    select_related_fields = ("free_class",)


class PaidCourseViewSet(BaseSlugReadOnlyAPIViewSet):
    queryset = PaidCourse.objects.filter(status="published")
    serializer_class = PaidCourseSerializer
    search_fields = ("title", "short_description")
    filterset_fields = ("technology", "is_featured")


class AttendanceViewSet(BaseStudentOwnedAPIViewSet):
    serializer_class = AttendanceSerializer
    queryset = Attendance.objects.all()
    owner_field = "student"
    select_related_fields = ("student", "free_class")


class RewardViewSet(BaseStudentOwnedAPIViewSet):
    serializer_class = RewardSerializer
    queryset = Reward.objects.all()
    owner_field = "student"


class AchievementViewSet(BaseReadOnlyAPIViewSet):
    queryset = Achievement.objects.filter(is_active=True)
    serializer_class = AchievementSerializer


class ReferralViewSet(BaseStudentOwnedAPIViewSet):
    serializer_class = ReferralSerializer
    queryset = Referral.objects.all()
    owner_field = "referrer"
    select_related_fields = ("referred_user",)


class FeedbackViewSet(mixins.CreateModelMixin, BaseAPIViewSet):
    serializer_class = FeedbackSerializer
    queryset = Feedback.objects.all()

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        if self.action == "list":
            return Feedback.objects.filter(status="approved", show_on_landing=True)
        if self.request.user.is_authenticated:
            return Feedback.objects.filter(student=self.request.user)
        return Feedback.objects.none()

    def list(self, request, *args, **kwargs):
        qs = Feedback.objects.filter(status="approved", show_on_landing=True)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class NotificationViewSet(BaseStudentOwnedAPIViewSet):
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    owner_field = "user"

    @action(detail=False, methods=["post"])
    def mark_read(self, request):
        from apps.notifications.services import NotificationService

        NotificationService.mark_all_read(request.user)
        return self.success_response(message="All notifications marked as read")


class StudentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, BaseAPIViewSet):
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = StudentProfile.objects.select_related("user")
    search_fields = ("user__email", "college", "city", "phone")


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def api_login(request):
    email = request.data.get("email")
    password = request.data.get("password")
    user = authenticate(request, username=email, password=password)
    if not user:
        return Response(
            {"success": False, "message": "Invalid credentials", "data": None},
            status=400,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {
            "success": True,
            "message": "Login successful",
            "data": {"token": token.key, "user": UserSerializer(user).data},
        }
    )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def api_dashboard(request):
    profile = request.user.profile
    data = {
        "profile": profile,
        "reward_points": profile.reward_points,
        "level": profile.level,
        "upcoming_count": Registration.objects.filter(
            student=request.user, status="confirmed", free_class__status="upcoming"
        ).count(),
        "attendance_percentage": profile.attendance_percentage,
        "unread_notifications": Notification.objects.filter(
            user=request.user, is_read=False
        ).count(),
    }
    return Response(
        {
            "success": True,
            "message": "OK",
            "data": DashboardSerializer(data).data,
        }
    )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def api_leaderboard(request):
    profiles = StudentProfile.objects.select_related("user").order_by("-reward_points")[:10]
    return Response(
        {
            "success": True,
            "message": "OK",
            "data": StudentProfileSerializer(profiles, many=True).data,
        }
    )
