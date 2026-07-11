from django.urls import path
from .dashboard_views import (
    DashboardHomeView,
    ProfileUpdateView,
    PasswordChangeView,
    RewardsView,
    ReferralsView,
    AttendanceView,
    NotificationsView,
    ResumeView,
    MyClassesView,
    ProjectRequestsView,
    MyFeedbacksView,
)

app_name = "dashboard"

urlpatterns = [
    path("", DashboardHomeView.as_view(), name="home"),
    path("profile/", ProfileUpdateView.as_view(), name="profile"),
    path("password/", PasswordChangeView.as_view(), name="password_change"),
    path("rewards/", RewardsView.as_view(), name="rewards"),
    path("referrals/", ReferralsView.as_view(), name="referrals"),
    path("attendance/", AttendanceView.as_view(), name="attendance"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
    path("resume/", ResumeView.as_view(), name="resume"),
    path("classes/", MyClassesView.as_view(), name="classes"),
    path("project-requests/", ProjectRequestsView.as_view(), name="project_requests"),
    path("feedbacks/", MyFeedbacksView.as_view(), name="my_feedbacks"),
]
