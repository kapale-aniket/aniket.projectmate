"""Ensure automation package is importable from Django services."""

import sys

from django.conf import settings


def ensure_automation_path():
    root = str(settings.LINKEDIN_AUTOMATION_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
