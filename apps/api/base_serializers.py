"""
Shared DRF serializers — inherit BaseSerializer / BaseModelSerializer.
"""
from rest_framework import serializers


class BaseSerializer(serializers.Serializer):
    """Plain serializer base with shared response helpers."""

    def success(self, data=None, message="OK"):
        return {"success": True, "message": message, "data": data}

    def failure(self, message="Error", errors=None):
        return {"success": False, "message": message, "errors": errors or {}}


class BaseModelSerializer(serializers.ModelSerializer):
    """
    ModelSerializer base for all ProjectMate APIs.

    Subclasses only declare model-specific fields; timestamps are included
    automatically when present on the model.
    """

    class Meta:
        abstract = True
        read_only_fields = ("id", "created_at", "updated_at")

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        # Ensure timestamps appear when model has them and fields is not __all__
        meta_fields = getattr(self.Meta, "fields", None)
        if meta_fields and meta_fields != "__all__":
            extras = []
            model = self.Meta.model
            for name in ("created_at", "updated_at"):
                if hasattr(model, name) and name not in fields:
                    # only auto-append if subclass opted into timestamps via include_timestamps
                    if getattr(self.Meta, "include_timestamps", False):
                        extras.append(name)
            if extras:
                return list(fields) + extras
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data


class ReadOnlyModelSerializer(BaseModelSerializer):
    """All fields read-only — for public list/detail endpoints."""

    def get_fields(self):
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields
