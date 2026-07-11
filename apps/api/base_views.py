"""
Shared DRF viewsets / API bases — inherit instead of repeating queryset & response logic.
"""
from rest_framework import viewsets, mixins, status, permissions
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class BaseAPIViewSet(viewsets.GenericViewSet):
    """
    Root API base for ProjectMate.

    Provides:
    - consistent success / error responses
    - optional student ownership filtering via `owner_field`
    - optional select_related / prefetch_related
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    owner_field = None  # e.g. "student" or "user" or "referrer"
    select_related_fields = ()
    prefetch_related_fields = ()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.select_related_fields:
            qs = qs.select_related(*self.select_related_fields)
        if self.prefetch_related_fields:
            qs = qs.prefetch_related(*self.prefetch_related_fields)
        return self.filter_queryset_for_user(qs)

    def filter_queryset_for_user(self, qs):
        """Limit to current user when owner_field is set (staff see all)."""
        if not self.owner_field:
            return qs
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_staff:
            return qs
        return qs.filter(**{self.owner_field: user})

    def success_response(self, data=None, message="OK", status_code=status.HTTP_200_OK):
        return Response(
            {"success": True, "message": message, "data": data},
            status=status_code,
        )

    def error_response(self, message="Error", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        return Response(
            {"success": False, "message": message, "errors": errors or {}},
            status=status_code,
        )

    def handle_service_call(self, func, *args, success_message="OK", created=False, **kwargs):
        """Wrap service-layer calls with consistent error handling."""
        try:
            result = func(*args, **kwargs)
            code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            serializer = self.get_serializer(result) if hasattr(result, "_meta") else None
            data = serializer.data if serializer else result
            return self.success_response(data=data, message=success_message, status_code=code)
        except DjangoValidationError as exc:
            msg = exc.messages[0] if hasattr(exc, "messages") else str(exc)
            return self.error_response(message=msg)
        except DRFValidationError as exc:
            return self.error_response(message=str(exc.detail), errors=exc.detail)


class BaseReadOnlyAPIViewSet(BaseAPIViewSet, viewsets.ReadOnlyModelViewSet):
    """Public/read-only list + retrieve (announcements, courses, classes)."""

    permission_classes = [permissions.AllowAny]
    lookup_field = "pk"


class BaseSlugReadOnlyAPIViewSet(BaseReadOnlyAPIViewSet):
    """Read-only endpoints that look up by slug."""

    lookup_field = "slug"


class BaseStudentOwnedAPIViewSet(
    mixins.ListModelMixin,
    BaseAPIViewSet,
):
    """Authenticated list scoped to the logged-in student."""

    permission_classes = [permissions.IsAuthenticated]
    owner_field = "student"


class BaseModelAPIViewSet(BaseAPIViewSet, viewsets.ModelViewSet):
    """Full CRUD when needed (admin-oriented endpoints)."""

    permission_classes = [IsAdminOrReadOnly]
