"""Single source of truth for default Excel/output format definitions."""

EMPTY_STYLE = {
    "header_bg": "1F4E79",
    "header_font_color": "FFFFFF",
    "header_font_size": 11,
    "title_font_size": 16,
    "title_color": "1F4E79",
    "section_bg": "D6E4F0",
    "section_font_color": "1F4E79",
    "banner_bg": "1F4E79",
    "banner_font_color": "FFFFFF",
    "alternate_row_bg": "F2F7FB",
    "border_color": "D9D9D9",
    "link_color": "0563C1",
    "yes_color": "2E7D32",
    "row_height": 22,
    "header_row_height": 28,
    "title_row_height": 36,
    "freeze_panes_row": 2,
}


def default_style():
    return dict(EMPTY_STYLE)


def default_job_excel_format():
    return {
        "sheet_title": "aniket.projectmate Daily Jobs",
        "sheet_name": "Daily Jobs",
        "watermark_text": "aniket.projectmate",
        "style": default_style(),
        "layout": {
            "group_by_experience": True,
            "group_by_company_size": True,
            "zero_year_section": "0 Years Experience",
            "one_year_section": "1 Year Experience",
        },
        "columns": [
            {"key": "sr_no", "header": "Sr No", "width": 7, "visible": True},
            {"key": "job_role", "header": "Job Role", "width": 30, "visible": True},
            {"key": "company_name", "header": "Company Name", "width": 28, "visible": True},
            {"key": "company_size", "header": "Company Size", "width": 16, "visible": True},
            {"key": "freshers_eligible", "header": "Freshers Eligible", "width": 16, "visible": True},
            {"key": "experience_required", "header": "Experience Required", "width": 18, "visible": True},
            {"key": "skills_required", "header": "Skills Required", "width": 42, "visible": True},
            {"key": "location", "header": "Location", "width": 16, "visible": True},
            {"key": "package_lpa", "header": "Package (LPA)", "width": 14, "visible": True},
            {"key": "posted_text", "header": "Posted", "width": 14, "visible": True},
            {"key": "easy_apply", "header": "Easy Apply", "width": 12, "visible": True},
            {"key": "apply_link", "header": "Apply Link", "width": 55, "visible": True},
        ],
    }


def default_connection_excel_format():
    return {
        "sheet_title": "aniket.projectmate Connections",
        "sheet_name": "Connections",
        "watermark_text": "aniket.projectmate",
        "style": default_style(),
        "layout": {"export_excel": True},
        "columns": [
            {"key": "timestamp", "header": "Timestamp", "width": 20, "visible": True},
            {"key": "name", "header": "Name", "width": 28, "visible": True},
            {"key": "headline", "header": "Headline", "width": 40, "visible": True},
            {"key": "profile_url", "header": "Profile URL", "width": 50, "visible": True},
            {"key": "keyword", "header": "Keyword", "width": 24, "visible": True},
            {"key": "location", "header": "Location", "width": 18, "visible": True},
            {"key": "connect_status", "header": "Connect Status", "width": 16, "visible": True},
        ],
    }


def default_posts_excel_format():
    return {
        "sheet_title": "LinkedIn Hiring Posts (Freshers / Interns)",
        "sheet_name": "Hiring Posts",
        "watermark_text": "aniket.projectmate",
        "style": default_style(),
        "layout": {},
        "columns": [
            {"key": "sr_no", "header": "Sr No", "width": 7, "visible": True},
            {"key": "post_url", "header": "Post URL", "width": 45, "visible": True},
            {"key": "apply_link", "header": "Apply Link", "width": 45, "visible": True},
            {"key": "company_name", "header": "Company Name", "width": 24, "visible": True},
            {"key": "job_role", "header": "Job Role", "width": 28, "visible": True},
            {"key": "company_size", "header": "Company Size", "width": 18, "visible": True},
            {"key": "package_lpa", "header": "Package (LPA)", "width": 14, "visible": True},
            {"key": "description", "header": "Description", "width": 60, "visible": True},
            {"key": "post_id", "header": "Post ID", "width": 22, "visible": True},
        ],
    }


DEFAULT_FORMATS = {
    "job": default_job_excel_format,
    "connection": default_connection_excel_format,
    "posts": default_posts_excel_format,
}


def get_default_format(scraper_type):
    factory = DEFAULT_FORMATS.get(scraper_type)
    if not factory:
        raise ValueError(f"Unknown scraper type: {scraper_type}")
    return factory()


def visible_columns(fmt):
    return [col for col in fmt.get("columns", []) if col.get("visible", True)]
