"""Shared path setup for automation entry scripts."""

import os
import sys

_AUTOMATION_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def automation_root():
    return _AUTOMATION_ROOT


def ensure_automation_path():
    if _AUTOMATION_ROOT not in sys.path:
        sys.path.insert(0, _AUTOMATION_ROOT)
