"""
Re-export shared bases for convenient imports:

    from apps.core.basemodels import BaseModel
    from apps.api.base_serializers import BaseModelSerializer
    from apps.api.base_views import BaseAPIViewSet
"""
from apps.core.basemodels import BaseModel, SoftDeleteModel, PublishableModel, TimeStampedModel
from apps.api.base_serializers import BaseSerializer, BaseModelSerializer, ReadOnlyModelSerializer
from apps.api.base_views import (
    BaseAPIViewSet,
    BaseReadOnlyAPIViewSet,
    BaseSlugReadOnlyAPIViewSet,
    BaseStudentOwnedAPIViewSet,
    BaseModelAPIViewSet,
    IsAdminOrReadOnly,
)

__all__ = [
    "BaseModel",
    "SoftDeleteModel",
    "PublishableModel",
    "TimeStampedModel",
    "BaseSerializer",
    "BaseModelSerializer",
    "ReadOnlyModelSerializer",
    "BaseAPIViewSet",
    "BaseReadOnlyAPIViewSet",
    "BaseSlugReadOnlyAPIViewSet",
    "BaseStudentOwnedAPIViewSet",
    "BaseModelAPIViewSet",
    "IsAdminOrReadOnly",
]
