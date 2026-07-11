"""Auth backends."""
from django.contrib.auth.backends import ModelBackend


class AllowInactiveStudentBackend(ModelBackend):
    """
    Students can authenticate even when admin has deactivated the account.
    Staff/admin accounts still require is_active=True.
    """

    def user_can_authenticate(self, user):
        if user is None:
            return False
        role = getattr(user, "role", None)
        if getattr(user, "is_staff", False) or role == "admin":
            return getattr(user, "is_active", True)
        # Students (and instructors) may log in while deactivated
        return True
