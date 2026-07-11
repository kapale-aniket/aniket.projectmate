"""django-allauth adapters for ProjectMate student Google sign-in."""
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from apps.accounts.models import User


class ProjectMateSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Ensure Google sign-ups become students with verified email."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = (data.get("email") or getattr(user, "email", "") or "").strip().lower()
        if email:
            user.email = email
            user.username = email
        user.role = User.Role.STUDENT
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form=form)
        updates = []
        if user.role != User.Role.STUDENT:
            user.role = User.Role.STUDENT
            updates.append("role")
        if not user.is_email_verified:
            user.is_email_verified = True
            updates.append("is_email_verified")
        email = (user.email or "").strip().lower()
        if email and user.username != email:
            user.username = email
            updates.append("username")
        if updates:
            user.save(update_fields=updates)
        return user

    def is_open_for_signup(self, request, sociallogin):
        return True
