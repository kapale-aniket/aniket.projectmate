"""Scrape Naukri recommended jobs that mention Python, then multi-apply in batches of 5."""

import re
from datetime import datetime

from naukri_config import (
    APPLIED_CSV,
    JOB_KEYWORD,
    MAX_DELAY,
    MIN_DELAY,
    MULTI_APPLY_BATCH_SIZE,
    RECOMMENDED_CSV,
    RECOMMENDED_URL,
    RECOMMENDED_XLSX,
)
from helpers import dismiss_popups, pause, write_csv, write_xlsx

JOB_FIELDS = [
    "timestamp",
    "role",
    "company",
    "skills",
    "salary",
    "location",
    "experience",
    "job_url",
    "contains_python",
]

APPLIED_FIELDS = [
    "timestamp",
    "role",
    "company",
    "skills",
    "salary",
    "apply_status",
]

EXTRACT_JOBS_JS = """(keyword) => {
  const needle = (keyword || 'python').toLowerCase();
  const cards = [];
  const selectors = [
    '.jobTuple',
    '.cust-job-tuple',
    '.srp-jobtuple-wrapper',
    '[class*="jobTuple"]',
    '[class*="JobCard"]',
    '[class*="job-card"]',
    '[class*="tuple"]',
    '[data-job-id]',
    'article',
    'li[class*="job"]',
  ];
  const seenEls = new Set();
  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((el) => {
      if (seenEls.has(el)) return;
      seenEls.add(el);
      cards.push(el);
    });
  }

  const pick = (el, sels) => {
    for (const s of sels) {
      const n = el.querySelector(s);
      if (n && (n.innerText || '').trim()) return (n.innerText || '').replace(/\\s+/g, ' ').trim();
    }
    return '';
  };

  const results = [];
  const seenText = new Set();
  cards.forEach((el, idx) => {
    const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
    if (text.length < 15 || text.length > 2500) return;
    if (seenText.has(text)) return;
    // Skip giant wrappers
    if (el.querySelectorAll('[data-job-id], [class*="jobTuple"], [class*="tuple"]').length > 12) return;
    if (!text.toLowerCase().includes(needle)) return;
    seenText.add(text);

    const role = pick(el, ['a.title', '.title', 'h2 a', 'h2', '[class*="title"] a', '[class*="title"]']);
    const company = pick(el, ['.comp-name', '.companyInfo .comp-name', '[class*="company"]', 'a.subTitle']);
    const skills = pick(el, ['.tags-gt', '.key-skill', '[class*="skill"]', '[class*="tag"]']);
    const salary = pick(el, ['.salary', '[class*="salary"]', '[class*="rupee"]']);
    const location = pick(el, ['.locWdth', '.location', '[class*="location"]', '[class*="loc"]']);
    const experience = pick(el, ['.expwdth', '.experience', '[class*="exp"]']);
    let jobUrl = '';
    const link = el.querySelector("a.title, h2 a, a[href*='job-listings'], a[href*='/job/']");
    if (link && link.href) jobUrl = link.href;

    const lines = text.split(/\\n+/).map((s) => s.trim()).filter(Boolean);
    results.push({
      card_index: idx,
      role: role || lines[0] || '',
      company: company || lines[1] || '',
      skills: (skills || '').slice(0, 300),
      salary: salary || '-',
      location: location || '',
      experience: experience || '',
      job_url: jobUrl,
      contains_python: 'yes',
      raw_text: text.slice(0, 300),
    });
  });

  return {
    url: location.href,
    title: document.title,
    card_candidates: cards.length,
    matched: results.length,
    body_sample: (document.body && document.body.innerText || '').slice(0, 400),
    jobs: results,
  };
}"""


def _has_keyword(text, keyword=None):
    needle = (keyword or JOB_KEYWORD or "python").strip()
    if not needle:
        return True
    return needle.casefold() in (text or "").casefold()


def _find_checkboxes(page, card=None):
    root = card if card is not None else page
    selectors = (
        ".naukicon-ot-checkbox",
        "i.naukicon-ot-checkbox",
        ".dspIB.naukicon.naukicon-ot-checkbox",
        'i[class*="naukicon-ot-checkbox"]',
        'span[class*="naukicon-ot-checkbox"]',
        'label[class*="checkbox"]',
        'input[type="checkbox"]',
        ".checkbox",
    )
    for selector in selectors:
        loc = root.locator(selector)
        if loc.count() > 0:
            return loc
    return None


def _click_multi_apply(page, logger):
    selectors = (
        "button.multi-apply-button",
        ".multi-apply-button.typ-16Bold.opaque-button",
        ".multi-apply-button",
        'button:has-text("Apply")',
        'button:has-text("Apply to")',
    )
    for selector in selectors:
        try:
            btn = page.locator(selector)
            if btn.count() == 0:
                continue
            target = btn.first
            if target.is_visible():
                target.click(timeout=5000)
                pause(page, MIN_DELAY, MAX_DELAY)
                logger("Clicked multi-apply button.")
                return True
        except Exception:
            continue
    # JS fallback
    try:
        clicked = page.evaluate(
            """() => {
              const btn = document.querySelector('button.multi-apply-button, .multi-apply-button');
              if (!btn) return false;
              btn.click();
              return true;
            }"""
        )
        if clicked:
            logger("Clicked multi-apply button (JS).")
            pause(page, MIN_DELAY, MAX_DELAY)
            return True
    except Exception:
        pass
    logger("Multi-apply button not found.")
    return False


def _relocate_cards(page):
    for selector in (
        ".jobTuple",
        ".cust-job-tuple",
        ".srp-jobtuple-wrapper",
        "[class*='jobTuple']",
        "[class*='JobCard']",
        "[class*='tuple']",
        "[data-job-id]",
        "article",
    ):
        loc = page.locator(selector)
        if loc.count() > 0:
            return loc
    return None


def scrape_and_apply_python_jobs(page, logger=print, batch_size=None):
    batch_size = batch_size or MULTI_APPLY_BATCH_SIZE
    keyword = (JOB_KEYWORD or "python").strip().lower()

    logger(f"Opening recommended jobs: {RECOMMENDED_URL}")
    page.goto(RECOMMENDED_URL, wait_until="domcontentloaded", timeout=90000)
    pause(page, MIN_DELAY, MAX_DELAY)
    dismiss_popups(page)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    current_url = page.url
    logger(f"Recommended page URL: {current_url}")
    if "login" in (current_url or "").lower():
        logger("*** Redirected to login — session expired. Re-save session. ***")
        write_csv(RECOMMENDED_CSV, [], JOB_FIELDS)
        write_xlsx(RECOMMENDED_XLSX, [], JOB_FIELDS, sheet_name="Python Jobs")
        return [], []

    for _ in range(8):
        page.mouse.wheel(0, 2600)
        pause(page, MIN_DELAY, MAX_DELAY)
        dismiss_popups(page)

    try:
        payload = page.evaluate(EXTRACT_JOBS_JS, keyword) or {}
    except Exception as exc:
        logger(f"Recommended DOM extract failed: {exc}")
        payload = {}

    logger(
        f"Recommended scan: {payload.get('card_candidates', 0)} card candidates, "
        f"{payload.get('matched', 0)} matched '{keyword}'."
    )
    logger(f"Recommended sample: {(payload.get('body_sample') or '')[:180]!r}")

    jobs = []
    for item in payload.get("jobs") or []:
        jobs.append(
            {
                "card_index": item.get("card_index", 0),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "role": item.get("role", ""),
                "company": item.get("company", ""),
                "skills": item.get("skills", ""),
                "salary": item.get("salary", "-"),
                "location": item.get("location", ""),
                "experience": item.get("experience", ""),
                "job_url": item.get("job_url", ""),
                "contains_python": "yes",
            }
        )

    write_csv(RECOMMENDED_CSV, jobs, JOB_FIELDS)
    write_xlsx(RECOMMENDED_XLSX, jobs, JOB_FIELDS, sheet_name="Python Jobs")
    logger(f"Found {len(jobs)} recommended job(s) containing '{keyword}'.")
    logger(f"  CSV : {RECOMMENDED_CSV}")
    logger(f"  XLSX: {RECOMMENDED_XLSX}")

    if not jobs:
        logger("No Python jobs to apply.")
        return jobs, []

    cards = _relocate_cards(page)
    if cards is None:
        logger("Job cards locator lost — cannot multi-select.")
        return jobs, []

    selected = jobs[:batch_size]
    logger(f"Selecting up to {len(selected)} job(s) for multi-apply...")

    selected_ok = []
    for job in selected:
        idx = int(job.get("card_index") or 0)
        try:
            # Prefer matching by role text if index drifted
            card = None
            role = (job.get("role") or "").strip()
            if role:
                try:
                    matched = cards.filter(has_text=re.compile(re.escape(role[:40]), re.I))
                    if matched.count() > 0:
                        card = matched.first
                except Exception:
                    card = None
            if card is None and idx < cards.count():
                card = cards.nth(idx)
            if card is None:
                logger(f"  Could not locate card for: {role}")
                continue

            card.scroll_into_view_if_needed()
            pause(page, 0.4, 0.8)
            boxes = _find_checkboxes(page, card)
            clicked = False
            if boxes is not None and boxes.count() > 0:
                try:
                    boxes.first.click(timeout=3000, force=True)
                    clicked = True
                except Exception:
                    try:
                        boxes.first.evaluate("el => el.click()")
                        clicked = True
                    except Exception:
                        clicked = False
            if not clicked:
                try:
                    icon = card.locator(".naukicon-ot-checkbox, .dspIB.naukicon, i[class*='checkbox']").first
                    if icon.count() > 0:
                        icon.click(timeout=3000, force=True)
                        clicked = True
                except Exception:
                    pass
            if clicked:
                selected_ok.append(job)
                logger(f"  Selected: {job.get('role') or '(untitled)'} @ {job.get('company') or '-'}")
            else:
                logger(f"  Could not select checkbox for: {job.get('role')}")
            pause(page, MIN_DELAY, MAX_DELAY)
        except Exception as exc:
            logger(f"  Select failed ({job.get('role')}): {exc}")

    applied_rows = []
    if selected_ok:
        if _click_multi_apply(page, logger):
            pause(page, MIN_DELAY, MAX_DELAY)
            dismiss_popups(page)
            for label in ("Apply", "Continue", "Yes", "Confirm", "Submit"):
                try:
                    btn = page.locator(f'button:has-text("{label}")')
                    if btn.count() > 0 and btn.first.is_visible():
                        btn.first.click(timeout=3000)
                        pause(page, MIN_DELAY, MAX_DELAY)
                except Exception:
                    continue
            for job in selected_ok:
                applied_rows.append(
                    {
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "role": job.get("role", ""),
                        "company": job.get("company", ""),
                        "skills": job.get("skills", ""),
                        "salary": job.get("salary", ""),
                        "apply_status": "multi_apply_clicked",
                    }
                )
            write_csv(APPLIED_CSV, applied_rows, APPLIED_FIELDS)
            logger(f"Multi-applied {len(applied_rows)} job(s). Log: {APPLIED_CSV}")
        else:
            logger("Selection done but multi-apply click failed.")
    else:
        logger("No jobs were selected for multi-apply.")

    return jobs, applied_rows
