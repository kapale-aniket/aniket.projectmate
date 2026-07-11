import csv
import os
from datetime import datetime

from common.logger import get_logger

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_MODULE_DIR, "new_connection")
LOG_FILE = os.path.join(OUTPUT_DIR, "connections.log")
INVITES_CSV = os.path.join(OUTPUT_DIR, "connections_sent.csv")


class ConnectionLogger:
    def __init__(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self._log = get_logger("connections", log_file=LOG_FILE)
        self._ensure_invites_csv_header()

    def _ensure_invites_csv_header(self):
        if not os.path.exists(INVITES_CSV):
            with open(INVITES_CSV, "w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(
                    ["timestamp", "keyword", "location", "name", "status"]
                )

    def info(self, message):
        self._log.info(message)

    def log_invite_action(self, name, keyword, location, status):
        with open(INVITES_CSV, "a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    keyword,
                    location or "anywhere",
                    name,
                    status,
                ]
            )
        self._log.info(f"[{status}] {name}  ({keyword} | {location or 'anywhere'})")
