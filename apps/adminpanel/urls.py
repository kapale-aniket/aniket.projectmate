from django.urls import path
from django.views.generic import RedirectView
from apps.adminpanel import views
from apps.adminpanel import extra_views
from apps.adminpanel import hub_views

app_name = "adminpanel"

urlpatterns = [
    # /admin/ → login page; dashboard lives at /admin/dashboard/
    path("", views.AdminLoginView.as_view(), name="login"),
    path("job-search/", views.JobSearchUserLoginView.as_view(), name="job_search_login"),
    path("login/", RedirectView.as_view(pattern_name="adminpanel:login", permanent=False)),
    path("forgot-password/", views.AdminForgotPasswordView.as_view(), name="forgot_password"),
    path("logout/", views.AdminLogoutView.as_view(), name="logout"),
    path("password/", views.AdminPasswordChangeView.as_view(), name="password_change"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # Hubs (slim sidebar)
    path("content/", hub_views.ContentHubView.as_view(), name="content"),
    path("community/", hub_views.CommunityHubView.as_view(), name="community"),
    path("tools/", hub_views.ToolsHubView.as_view(), name="tools"),
    path("logs/", hub_views.LogsHubView.as_view(), name="logs"),
    path("logs/clear/", hub_views.LogClearView.as_view(), name="logs_clear"),
    path("logs/<str:kind>/<int:pk>/delete/", hub_views.LogDeleteView.as_view(), name="log_delete"),
    path("latest-classes/", hub_views.LatestClassesHubView.as_view(), name="latest_classes"),
    path(
        "latest-classes/free/<int:pk>/<str:action>/",
        hub_views.FreeClassMailActionView.as_view(),
        name="free_class_mail",
    ),
    path(
        "latest-classes/paid/<int:pk>/<str:action>/",
        hub_views.PaidCourseMailActionView.as_view(),
        name="paid_course_mail",
    ),
    # Students
    path("students/", views.StudentListView.as_view(), name="students"),
    path("students/export/", views.StudentExportView.as_view(), name="students_export"),
    path("students/ids/", views.StudentIdsView.as_view(), name="students_ids"),
    path("students/bulk/", views.StudentBulkActionView.as_view(), name="students_bulk"),
    path("students/bulk-email/", views.StudentBulkEmailView.as_view(), name="students_bulk_email"),
    path("students/<int:pk>/", views.StudentDetailView.as_view(), name="student_detail"),
    path("students/<int:pk>/edit/", views.StudentEditView.as_view(), name="student_edit"),
    path("students/<int:pk>/toggle/", views.StudentToggleActiveView.as_view(), name="student_toggle"),
    path("students/<int:pk>/delete/", views.StudentDeleteView.as_view(), name="student_delete"),
    path("students/<int:pk>/email/", views.StudentEmailView.as_view(), name="student_email"),
    # Free classes
    path("classes/", views.FreeClassListView.as_view(), name="classes"),
    path("classes/new/", views.FreeClassCreateView.as_view(), name="class_create"),
    path("classes/<int:pk>/edit/", views.FreeClassUpdateView.as_view(), name="class_edit"),
    path("classes/<int:pk>/delete/", views.FreeClassDeleteView.as_view(), name="class_delete"),
    path("classes/<int:pk>/cancel/", views.FreeClassCancelView.as_view(), name="class_cancel"),
    path("classes/<int:pk>/go-live/", views.FreeClassGoLiveView.as_view(), name="class_go_live"),
    path("classes/<int:pk>/duplicate/", views.FreeClassDuplicateView.as_view(), name="class_duplicate"),
    path("classes/<int:pk>/toggle-reg/", views.FreeClassToggleRegView.as_view(), name="class_toggle_reg"),
    # Courses
    path("courses/", views.CourseListView.as_view(), name="courses"),
    path("courses/new/", views.CourseCreateView.as_view(), name="course_create"),
    path("courses/<int:pk>/edit/", views.CourseUpdateView.as_view(), name="course_edit"),
    path("courses/<int:pk>/delete/", views.CourseDeleteView.as_view(), name="course_delete"),
    path("courses/<int:pk>/featured/", views.CourseToggleFeaturedView.as_view(), name="course_featured"),
    path("courses/<int:pk>/status/", views.CourseToggleStatusView.as_view(), name="course_status"),
    # Attendance
    path("attendance/", views.AttendanceHubView.as_view(), name="attendance"),
    path("attendance/<int:pk>/", views.AttendanceMarkView.as_view(), name="attendance_mark"),
    path("attendance/<int:pk>/export/", views.AttendanceExportView.as_view(), name="attendance_export"),
    # Announcements
    path("announcements/", views.AnnouncementListView.as_view(), name="announcements"),
    path("announcements/new/", views.AnnouncementCreateView.as_view(), name="announcement_create"),
    path("announcements/<int:pk>/edit/", views.AnnouncementUpdateView.as_view(), name="announcement_edit"),
    path("announcements/<int:pk>/delete/", views.AnnouncementDeleteView.as_view(), name="announcement_delete"),
    path("announcements/<int:pk>/pin/", extra_views.AnnouncementPinView.as_view(), name="announcement_pin"),
    # Feedback / resumes
    path("feedback/", views.FeedbackModerationView.as_view(), name="feedback"),
    path("feedback/<int:pk>/approve/", views.FeedbackApproveView.as_view(), name="feedback_approve"),
    path("feedback/<int:pk>/reject/", views.FeedbackRejectView.as_view(), name="feedback_reject"),
    path("feedback/<int:pk>/feature/", extra_views.FeedbackFeatureView.as_view(), name="feedback_feature"),
    path("feedback/<int:pk>/show-on-ui/", extra_views.FeedbackShowOnUIView.as_view(), name="feedback_show_on_ui"),
    path("feedback/<int:pk>/like/", extra_views.FeedbackLikeView.as_view(), name="feedback_like"),
    path("feedback/<int:pk>/delete/", extra_views.FeedbackDeleteView.as_view(), name="feedback_delete"),
    path("feedback/<int:pk>/reply/", extra_views.FeedbackReplyView.as_view(), name="feedback_reply"),
    path("resumes/", views.ResumeListView.as_view(), name="resumes"),
    path("resumes/<int:pk>/review/", views.ResumeReviewView.as_view(), name="resume_review"),
    # Course materials
    path("materials/", extra_views.MaterialListView.as_view(), name="materials"),
    path("materials/new/", extra_views.MaterialCreateView.as_view(), name="material_create"),
    path("materials/<int:pk>/delete/", extra_views.MaterialDeleteView.as_view(), name="material_delete"),
    # Project plans
    path("project-plans/new/", extra_views.ProjectPlanCreateView.as_view(), name="project_plan_create"),
    path("project-plans/<int:pk>/edit/", extra_views.ProjectPlanUpdateView.as_view(), name="project_plan_edit"),
    path("project-plans/<int:pk>/delete/", extra_views.ProjectPlanDeleteView.as_view(), name="project_plan_delete"),
    path("project-perks/new/", extra_views.ProjectPlanPerkCreateView.as_view(), name="project_perk_create"),
    path("project-perks/<int:pk>/edit/", extra_views.ProjectPlanPerkUpdateView.as_view(), name="project_perk_edit"),
    path("project-perks/<int:pk>/delete/", extra_views.ProjectPlanPerkDeleteView.as_view(), name="project_perk_delete"),
    # Notifications
    path("notifications/", extra_views.NotificationHubView.as_view(), name="notifications"),
    path("notifications/send/", extra_views.NotificationSendView.as_view(), name="notification_send"),
    path(
        "notifications/dispatch-due/",
        extra_views.NotificationDispatchDueView.as_view(),
        name="notification_dispatch_due",
    ),
    # Reports
    path("reports/", extra_views.ReportsView.as_view(), name="reports"),
    # Email
    path("emails/templates/", views.EmailTemplateListView.as_view(), name="email_templates"),
    path("emails/templates/new/", views.EmailTemplateCreateView.as_view(), name="email_template_create"),
    path("emails/templates/<int:pk>/", views.EmailTemplateUpdateView.as_view(), name="email_template_edit"),
    path("emails/preview/", views.EmailPreviewView.as_view(), name="email_preview"),
    path("emails/bulk/", views.BulkEmailView.as_view(), name="bulk_email"),
    path("emails/logs/", views.EmailLogListView.as_view(), name="email_logs"),
    path("emails/reminders/", views.SendRemindersView.as_view(), name="send_reminders"),
    # Rewards
    path("rewards/", views.RewardsHubView.as_view(), name="rewards"),
    path("rewards/rules/new/", views.RewardRuleCreateView.as_view(), name="reward_rule_create"),
    path("rewards/rules/<int:pk>/", views.RewardRuleUpdateView.as_view(), name="reward_rule_edit"),
    path("rewards/achievements/new/", views.AchievementCreateView.as_view(), name="achievement_create"),
    path("rewards/achievements/<int:pk>/delete/", views.AchievementDeleteView.as_view(), name="achievement_delete"),
    path("rewards/bonus/", views.BonusPointsView.as_view(), name="bonus_points"),
    path("rewards/reset/", views.ResetLeaderboardView.as_view(), name="reset_leaderboard"),
    # Referrals
    path("referrals/", views.ReferralListView.as_view(), name="referrals"),
    path("referrals/<int:pk>/approve/", views.ReferralApproveView.as_view(), name="referral_approve"),
    path("referrals/<int:pk>/reject/", views.ReferralRejectView.as_view(), name="referral_reject"),
    # Site / About settings
    path("settings/", views.SiteSettingsUpdateView.as_view(), name="settings"),
]
