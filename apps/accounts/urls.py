from django.urls import path
from django.contrib.auth import views as auth_views
from .views import StudentLoginView, StudentRegisterView, StudentLogoutView, TrustLoginView

app_name = "accounts"

urlpatterns = [
    path("login/", StudentLoginView.as_view(), name="login"),
    path("register/", StudentRegisterView.as_view(), name="register"),
    path("logout/", StudentLogoutView.as_view(), name="logout"),
    path("trust/", TrustLoginView.as_view(), name="trust"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/password_reset.html",
            email_template_name="auth/password_reset_email.html",
            success_url="/accounts/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="auth/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/password_reset_confirm.html",
            success_url="/accounts/password-reset/complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="auth/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
