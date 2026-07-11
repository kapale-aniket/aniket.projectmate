"""Default and validation for per-scraper Excel / output column formatting."""

import json
import re
import sys

from django.conf import settings

HEX_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


def _ensure_automation_path():
    root = str(settings.LINKEDIN_AUTOMATION_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _import_defaults():
    _ensure_automation_path()
    from common.excel_format_defaults import (
        DEFAULT_FORMATS,
        default_connection_excel_format,
        default_job_excel_format,
        default_posts_excel_format,
        get_default_format,
        visible_columns,
    )

    return (
        DEFAULT_FORMATS,
        default_connection_excel_format,
        default_job_excel_format,
        default_posts_excel_format,
        get_default_format,
        visible_columns,
    )


(
    DEFAULT_FORMATS,
    default_job_excel_format,
    default_connection_excel_format,
    default_posts_excel_format,
    get_default_format,
    visible_columns,
) = _import_defaults()


def _normalize_color(value, fallback):
    text = str(value or "").strip().lstrip("#")
    if HEX_COLOR_RE.match(text):
        return text.upper()
    return fallback


def _normalize_columns(columns, defaults):
    default_by_key = {col["key"]: col for col in defaults.get("columns", [])}
    allowed_keys = list(default_by_key.keys())
    if not isinstance(columns, list) or not columns:
        return defaults["columns"]

    normalized = []
    seen = set()
    for col in columns:
        if not isinstance(col, dict):
            continue
        key = str(col.get("key", "")).strip()
        if key not in default_by_key or key in seen:
            continue
        base = default_by_key[key]
        width = col.get("width", base["width"])
        try:
            width = max(5, min(80, int(width)))
        except (TypeError, ValueError):
            width = base["width"]
        header = str(col.get("header", base["header"])).strip() or base["header"]
        normalized.append(
            {
                "key": key,
                "header": header[:80],
                "width": width,
                "visible": bool(col.get("visible", True)),
            }
        )
        seen.add(key)

    for key in allowed_keys:
        if key not in seen:
            normalized.append(dict(default_by_key[key]))

    return normalized


def normalize_excel_format(scraper_type, data):
    """Merge user data with defaults and validate."""
    defaults = get_default_format(scraper_type)
    if not isinstance(data, dict):
        data = {}

    default_style = defaults.get("style", {})
    style_in = data.get("style") if isinstance(data.get("style"), dict) else {}
    style = {
        "header_bg": _normalize_color(style_in.get("header_bg"), default_style["header_bg"]),
        "header_font_color": _normalize_color(
            style_in.get("header_font_color"), default_style["header_font_color"]
        ),
        "header_font_size": int(style_in.get("header_font_size", default_style["header_font_size"])),
        "title_font_size": int(style_in.get("title_font_size", default_style["title_font_size"])),
        "title_color": _normalize_color(style_in.get("title_color"), default_style["title_color"]),
        "section_bg": _normalize_color(style_in.get("section_bg"), default_style["section_bg"]),
        "section_font_color": _normalize_color(
            style_in.get("section_font_color"), default_style["section_font_color"]
        ),
        "banner_bg": _normalize_color(style_in.get("banner_bg"), default_style["banner_bg"]),
        "banner_font_color": _normalize_color(
            style_in.get("banner_font_color"), default_style["banner_font_color"]
        ),
        "alternate_row_bg": _normalize_color(
            style_in.get("alternate_row_bg"), default_style["alternate_row_bg"]
        ),
        "border_color": _normalize_color(style_in.get("border_color"), default_style["border_color"]),
        "link_color": _normalize_color(style_in.get("link_color"), default_style["link_color"]),
        "yes_color": _normalize_color(style_in.get("yes_color"), default_style["yes_color"]),
        "row_height": max(14, min(60, int(style_in.get("row_height", default_style["row_height"])))),
        "header_row_height": max(
            18, min(60, int(style_in.get("header_row_height", default_style["header_row_height"])))
        ),
        "title_row_height": max(
            20, min(80, int(style_in.get("title_row_height", default_style["title_row_height"])))
        ),
        "freeze_panes_row": max(
            0, min(10, int(style_in.get("freeze_panes_row", default_style["freeze_panes_row"])))
        ),
    }

    layout = dict(defaults.get("layout", {}))
    layout_in = data.get("layout") if isinstance(data.get("layout"), dict) else {}
    layout.update(layout_in)

    if scraper_type == "job":
        layout["group_by_experience"] = bool(layout.get("group_by_experience", True))
        layout["group_by_company_size"] = bool(layout.get("group_by_company_size", True))
        layout["zero_year_section"] = str(
            layout.get("zero_year_section") or defaults["layout"]["zero_year_section"]
        )[:80]
        layout["one_year_section"] = str(
            layout.get("one_year_section") or defaults["layout"]["one_year_section"]
        )[:80]
    if scraper_type == "connection":
        layout["export_excel"] = bool(layout.get("export_excel", True))

    return {
        "sheet_title": str(data.get("sheet_title") or defaults["sheet_title"])[:120],
        "sheet_name": str(data.get("sheet_name") or defaults["sheet_name"])[:31],
        "watermark_text": str(data.get("watermark_text") or defaults["watermark_text"])[:60],
        "style": style,
        "layout": layout,
        "columns": _normalize_columns(data.get("columns"), defaults),
    }


def parse_excel_format_json(scraper_type, raw):
    if not raw:
        return get_default_format(scraper_type)
    if isinstance(raw, dict):
        return normalize_excel_format(scraper_type, raw)
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return get_default_format(scraper_type)
    return normalize_excel_format(scraper_type, data)
