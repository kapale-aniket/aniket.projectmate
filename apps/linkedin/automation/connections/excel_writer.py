import csv
import os

from common.excel_format import all_column_headers, all_column_keys, load_excel_format
from common.excel_table import record_row_values, write_formatted_workbook

_HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_HERE, "new_connection")
PROFILES_CSV = os.path.join(OUTPUT_DIR, "new_connections.csv")
EXCEL_PATH = os.path.join(OUTPUT_DIR, "new_connections.xlsx")


def get_csv_columns():
    fmt = load_excel_format("connection")
    return all_column_keys(fmt)


def get_csv_headers():
    fmt = load_excel_format("connection")
    return all_column_headers(fmt)


def _read_profiles():
    if not os.path.isfile(PROFILES_CSV):
        return []
    with open(PROFILES_CSV, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_connections_excel(path=None, fmt=None):
    fmt = fmt or load_excel_format("connection")
    layout = fmt.get("layout") or {}
    if not layout.get("export_excel", True):
        return 0

    rows_data = _read_profiles()
    if not rows_data:
        return 0

    path = path or EXCEL_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rows = [record_row_values(None, item, fmt) for item in rows_data]
    return write_formatted_workbook(
        path,
        fmt,
        scraper_type="connection",
        rows=rows,
        link_keys={"profile_url"},
    )
