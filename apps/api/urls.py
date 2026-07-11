from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AnnouncementViewSet,
    FreeClassViewSet,
    RegistrationViewSet,
    PaidCourseViewSet,
    AttendanceViewSet,
    RewardViewSet,
    AchievementViewSet,
    ReferralViewSet,
    FeedbackViewSet,
    NotificationViewSet,
    StudentViewSet,
    api_login,
    api_dashboard,
    api_leaderboard,
)

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="api-announcements")
router.register("classes", FreeClassViewSet, basename="api-classes")
router.register("registrations", RegistrationViewSet, basename="api-registrations")
router.register("courses", PaidCourseViewSet, basename="api-courses")
router.register("attendance", AttendanceViewSet, basename="api-attendance")
router.register("rewards", RewardViewSet, basename="api-rewards")
router.register("achievements", AchievementViewSet, basename="api-achievements")
router.register("referrals", ReferralViewSet, basename="api-referrals")
router.register("feedback", FeedbackViewSet, basename="api-feedback")
router.register("notifications", NotificationViewSet, basename="api-notifications")
router.register("students", StudentViewSet, basename="api-students")

urlpatterns = [
    path("auth/login/", api_login, name="api-login"),
    path("dashboard/", api_dashboard, name="api-dashboard"),
    path("leaderboard/", api_leaderboard, name="api-leaderboard"),
    path("", include(router.urls)),
]
