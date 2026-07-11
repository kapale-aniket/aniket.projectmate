"""Shared search and sort helpers for dashboard data."""


def _match_search(item, query, fields):
    if not query:
        return True
    q = query.lower()
    return any(q in str(item.get(f, "")).lower() for f in fields)


def filter_files(files, search="", file_type=""):
    result = files
    if search:
        result = [f for f in result if _match_search(f, search, ["name", "type", "date", "path"])]
    if file_type:
        result = [f for f in result if f.get("type", "").lower() == file_type.lower()]
    return result


def sort_files(files, sort_by="date", sort_dir="desc"):
    reverse = sort_dir != "asc"

    def key_fn(item):
        if sort_by == "name":
            return item.get("name", "").lower()
        if sort_by == "type":
            return item.get("type", "").lower()
        if sort_by == "records":
            return int(item.get("records") or 0)
        if sort_by == "size":
            return float(item.get("size_kb") or 0)
        return float(item.get("mtime") or 0)

    return sorted(files, key=key_fn, reverse=reverse)


def filter_sort_files(files, search="", file_type="", sort_by="date", sort_dir="desc"):
    return sort_files(filter_files(files, search, file_type), sort_by, sort_dir)


def filter_preview_rows(headers, rows, search=""):
    if not search:
        return headers, rows
    q = search.lower()
    filtered = []
    for row in rows:
        text = " ".join(str(c) for c in row).lower()
        if q in text:
            filtered.append(row)
    return headers, filtered


def sort_preview_rows(headers, rows, sort_by="", sort_dir="asc"):
    if not sort_by or sort_by not in headers:
        return rows
    idx = headers.index(sort_by)
    reverse = sort_dir == "desc"
    return sorted(rows, key=lambda r: str(r[idx] if idx < len(r) else "").lower(), reverse=reverse)


PREVIEW_PAGE_SIZE = 10


def paginate_preview_rows(rows, page=1, per_page=PREVIEW_PAGE_SIZE):
    total = len(rows)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(int(page or 1), total_pages))
    start = (page - 1) * per_page
    end = min(start + per_page, total)
    return rows[start:end], {
        "page": page,
        "per_page": per_page,
        "total_rows": total,
        "total_pages": total_pages,
        "start": start + 1 if total else 0,
        "end": end,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def sort_logs(logs, sort_by="date", sort_dir="desc"):
    reverse = sort_dir != "asc"
    level_order = {"error": 0, "warning": 1, "info": 2, "success": 3}

    def key_fn(log):
        if sort_by == "level":
            return level_order.get(log.get("level", "info"), 9)
        if sort_by == "message":
            return log.get("message", "").lower()
        return log.get("created_at") or log.get("time", "")

    return sorted(logs, key=key_fn, reverse=reverse)
