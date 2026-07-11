from common.excel_table import record_row_values, write_formatted_workbook


def write_hiring_excel(posts, path, fmt=None):
    rows = [
        record_row_values(idx, post, fmt)
        for idx, post in enumerate(posts, start=1)
    ]
    return write_formatted_workbook(
        path,
        fmt,
        scraper_type="posts",
        rows=rows,
        link_keys={"post_url", "apply_link"},
    )
