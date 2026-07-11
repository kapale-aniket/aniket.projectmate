"""Re-export file error helpers from the automation package."""

from apps.linkedin.services.automation_path import ensure_automation_path


def friendly_file_error(exc, path=None, action="use"):
    ensure_automation_path()
    from common.file_errors import friendly_file_error as _friendly_file_error

    return _friendly_file_error(exc, path, action)
