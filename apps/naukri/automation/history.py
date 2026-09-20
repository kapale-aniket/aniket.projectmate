"""Scrape Naukri application history — today's Connected by Email companies."""

from datetime import datetime

from naukri_config import HISTORY_CSV, HISTORY_STATUS_FILTER, HISTORY_URL, HISTORY_XLSX, MIN_DELAY, MAX_DELAY
from helpers import dismiss_popups, pause, write_csv, write_xlsx

# text_looks_like_today kept available for tests / callers
from helpers import text_looks_like_today  # noqa: F401

HISTORY_FIELDS = [
    "timestamp",
    "company",
    "job_title",
    "status",
    "applied_on",
    "raw_text",
]

EXTRACT_HISTORY_JS = """() => {
  const statusNeedles = [
    'connected by email',
    'applied via email',
    'email',
  ];
  const todayNeedles = [
    'today', 'just now', 'hour ago', 'hours ago', 'few hours', 'mins ago', 'min ago',
  ];

  const isToday = (text) => {
    const t = (text || '').toLowerCase();
    if (todayNeedles.some((n) => t.includes(n))) return true;
    // e.g. 07 Aug 2026 / 7 Aug / 07-08-2026
    const now = new Date();
    const day = String(now.getDate()).padStart(2, '0');
    const monShort = now.toLocaleString('en-GB', { month: 'short' }).toLowerCase();
    const monLong = now.toLocaleString('en-GB', { month: 'long' }).toLowerCase();
    if (t.includes(day) && (t.includes(monShort) || t.includes(monLong))) return true;
    return false;
  };

  const isEmailStatus = (text) => {
    const t = (text || '').toLowerCase();
    if (t.includes('connected by email') || t.includes('applied via email')) return true;
    if (t.includes('email') && (t.includes('connected') || t.includes('applied') || t.includes('status'))) {
      return true;
    }
    return false;
  };

  const roots = [];
  const selectors = [
    '[class*="application"]',
    '[class*="applyHistory"]',
    '[class*="ApplyHistory"]',
    '[class*="history"]',
    '[class*="tuple"]',
    '[class*="card"]',
    'li',
    'article',
  ];
  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((el) => roots.push(el));
  }

  const seen = new Set();
  const rows = [];
  for (const el of roots) {
    const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
    if (text.length < 20 || text.length > 1200) continue;
    if (seen.has(text)) continue;
    // Prefer leaf-ish cards: skip huge containers
    if ((el.querySelectorAll('[class*="card"], [class*="tuple"]').length || 0) > 8) continue;

    const lower = text.toLowerCase();
    const emailOk = isEmailStatus(lower);
    const todayOk = isToday(lower);
    if (!emailOk && !lower.includes('connected by email')) continue;
    if (!todayOk) continue;

    seen.add(text);
    const lines = text.split(/\\n+/).map((s) => s.trim()).filter(Boolean);
    let company = '';
    let title = '';
    const companyEl = el.querySelector(
      '[class*="company"], [class*="comp-name"], [class*=" Comp"], strong, h3, h4'
    );
    const titleEl = el.querySelector(
      '[class*="title"], [class*="desig"], a, h2, h3'
    );
    company = (companyEl && companyEl.innerText || '').replace(/\\s+/g, ' ').trim();
    title = (titleEl && titleEl.innerText || '').replace(/\\s+/g, ' ').trim();
    if (!company) company = lines[0] || '';
    if (!title || title === company) title = lines[1] || lines[0] || '';

    rows.push({
      company,
      job_title: title,
      status: 'Connected by Email',
      applied_on: 'today',
      raw_text: text.slice(0, 500),
    });
    if (rows.length >= 80) break;
  }
  return {
    url: location.href,
    title: document.title,
    row_count: rows.length,
    body_sample: (document.body && document.body.innerText || '').slice(0, 400),
    rows,
  };
}"""


def _click_status_filter(page, logger):
    """Try to open / select the Connected by Email filter on history page."""
    # Click chips / tabs that mention email
    try:
        clicked = page.evaluate(
            """() => {
              const needles = ['connected by email', 'applied via email', 'email'];
              const nodes = [...document.querySelectorAll('button, a, label, span, div[role="button"], li')];
              for (const el of nodes) {
                const t = (el.innerText || '').trim().toLowerCase();
                if (!t || t.length > 60) continue;
                if (needles.some((n) => t === n || t.includes('connected by email') || t.includes('applied via email'))) {
                  el.click();
                  return t;
                }
              }
              // Try opening a Status dropdown first
              for (const el of nodes) {
                const t = (el.innerText || '').trim().toLowerCase();
                if (t === 'status' || t.includes('application status') || t === 'filter') {
                  el.click();
                  return 'opened:' + t;
                }
              }
              return '';
            }"""
        )
        pause(page, MIN_DELAY, MAX_DELAY)
        if clicked and not str(clicked).startswith("opened:"):
            logger(f"Applied history filter chip: {clicked}")
            return True
        if str(clicked).startswith("opened:"):
            picked = page.evaluate(
                """() => {
                  const nodes = [...document.querySelectorAll('button, a, label, span, li, div')];
                  for (const el of nodes) {
                    const t = (el.innerText || '').trim().toLowerCase();
                    if (t.includes('connected by email') || t.includes('applied via email')) {
                      el.click();
                      return t;
                    }
                  }
                  return '';
                }"""
            )
            pause(page, MIN_DELAY, MAX_DELAY)
            if picked:
                logger(f"Applied history filter via dropdown: {picked}")
                return True
    except Exception as exc:
        logger(f"Filter click error: {exc}")

    logger("Could not click Connected by Email filter — scanning all visible rows.")
    return False


def scrape_today_email_applications(page, logger=print):
    logger(f"Opening application history: {HISTORY_URL}")
    page.goto(HISTORY_URL, wait_until="domcontentloaded", timeout=90000)
    pause(page, MIN_DELAY, MAX_DELAY)
    dismiss_popups(page)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    pause(page, MIN_DELAY, MAX_DELAY)

    current_url = page.url
    logger(f"History page URL: {current_url}")
    if "login" in (current_url or "").lower():
        logger("*** Redirected to login — session expired. Re-save session. ***")
        write_csv(HISTORY_CSV, [], HISTORY_FIELDS)
        write_xlsx(HISTORY_XLSX, [], HISTORY_FIELDS, sheet_name="Email Applications")
        return []

    _click_status_filter(page, logger)
    dismiss_popups(page)

    for _ in range(6):
        page.mouse.wheel(0, 2200)
        pause(page, MIN_DELAY, MAX_DELAY)

    try:
        payload = page.evaluate(EXTRACT_HISTORY_JS) or {}
    except Exception as exc:
        logger(f"History DOM extract failed: {exc}")
        payload = {}

    raw_rows = payload.get("rows") or []
    logger(f"History DOM sample: {(payload.get('body_sample') or '')[:180]!r}")
    logger(f"History extract found {len(raw_rows)} matching row(s).")

    rows = []
    for item in raw_rows:
        rows.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "company": (item.get("company") or "").strip(),
                "job_title": (item.get("job_title") or "").strip(),
                "status": item.get("status") or "Connected by Email",
                "applied_on": item.get("applied_on") or "today",
                "raw_text": (item.get("raw_text") or "")[:500],
            }
        )

    # If email+today filter found nothing, fall back to all visible today rows
    if not rows:
        logger("No email+today rows — collecting all today-looking application cards...")
        try:
            fallback = page.evaluate(
                """() => {
                  const todayNeedles = ['today','just now','hour ago','hours ago','few hours','mins ago'];
                  const cards = [...document.querySelectorAll(
                    '[class*="tuple"], [class*="card"], [class*="application"], li, article'
                  )];
                  const rows = [];
                  const seen = new Set();
                  for (const el of cards) {
                    const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (text.length < 20 || text.length > 900 || seen.has(text)) continue;
                    const lower = text.toLowerCase();
                    if (!todayNeedles.some((n) => lower.includes(n))) continue;
                    seen.add(text);
                    const lines = text.split(/\\n+/).map((s) => s.trim()).filter(Boolean);
                    rows.push({
                      company: lines[0] || '',
                      job_title: lines[1] || '',
                      status: (lower.includes('email') ? 'Connected by Email' : 'Today'),
                      applied_on: 'today',
                      raw_text: text.slice(0, 500),
                    });
                    if (rows.length >= 50) break;
                  }
                  return rows;
                }"""
            ) or []
            for item in fallback:
                rows.append(
                    {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        **item,
                    }
                )
            logger(f"Fallback collected {len(rows)} today application row(s).")
        except Exception as exc:
            logger(f"Fallback extract failed: {exc}")

    seen = set()
    unique = []
    for row in rows:
        key = (row.get("company", "").lower(), row.get("job_title", "").lower())
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    write_csv(HISTORY_CSV, unique, HISTORY_FIELDS)
    write_xlsx(HISTORY_XLSX, unique, HISTORY_FIELDS, sheet_name="Email Applications")
    logger(f"Saved {len(unique)} today's application(s) (email-preferred).")
    logger(f"  CSV : {HISTORY_CSV}")
    logger(f"  XLSX: {HISTORY_XLSX}")
    return unique
