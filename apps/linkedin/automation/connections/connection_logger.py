import os
from common.logger import get_logger

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_MODULE_DIR, "new_connection")
LOG_FILE = os.path.join(OUTPUT_DIR, "connections.log")


class ConnectionLogger:
    def __init__(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self._log = get_logger("connections", log_file=LOG_FILE)

    def info(self, message):
        self._log.info(message)

    def log_invite_action(self, name, keyword, location, status):
        # Log only — no CSV/Excel output files for connection runs.
        self._log.info(f"[{status}] {name}  ({keyword} | {location or 'anywhere'})")
