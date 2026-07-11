"""
Shared abstract models — use these instead of repeating timestamp / soft-delete fields.
"""
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base for almost every ProjectMate model.

    Provides:
    - created_at / updated_at
    - default ordering by newest first
    - soft helpers for subclasses
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def touch(self, save=True):
        """Bump updated_at without changing other fields."""
        self.updated_at = timezone.now()
        if save:
            self.save(update_fields=["updated_at"])


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def soft_delete(self):
        return self.update(is_deleted=True, deleted_at=timezone.now())


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=True)


class SoftDeleteModel(BaseModel):
    """Optional soft-delete layer for models that should not hard-delete."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


class PublishableModel(BaseModel):
    """Shared publish flag used by announcements, FAQs, gallery, etc."""

    is_published = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True

    @classmethod
    def published(cls):
        return cls.objects.filter(is_published=True)


# Backwards-compatible alias
TimeStampedModel = BaseModel
