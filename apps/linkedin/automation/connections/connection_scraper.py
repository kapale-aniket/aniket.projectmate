import csv
import os
import re
from datetime import datetime

from connections.people_search import CONNECT_INVITE_LINK_SELECTOR, RESULT_CARD_SELECTOR

_HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_HERE, "new_connection")
PROFILES_CSV = os.path.join(OUTPUT_DIR, "new_connections.csv")

from connections.excel_writer import get_csv_columns, get_csv_headers

PROFILE_URL_PATTERN = re.compile(r"/in/[^/?#]+")
SCRAPE_PROFILES_JS = """() => {
    const links = [...document.querySelectorAll('main a[href*="/in/"]')];
    const seen = new Set();
    const profiles = [];

    for (const link of links) {
        const match = link.href.match(/\\/in\\/([^/?#]+)/);
        if (!match || seen.has(match[1])) continue;
        seen.add(match[1]);

        let card = link;
        let cardFound = false;
        for (let depth = 0; depth < 12; depth++) {
            card = card.parentElement;
            if (!card) break;

            const actionEl = [...card.querySelectorAll('a, button')].find((el) => {
                const text = (el.textContent || '').trim().toLowerCase();
                return ['connect', 'message', 'pending', 'follow'].includes(text);
            });
            if (!actionEl) continue;

            const actionText = (actionEl.textContent || '').trim().toLowerCase();
            let connectStatus = 'unknown';
            if (actionText === 'connect') connectStatus = 'connect';
            else if (actionText === 'message') connectStatus = 'connected';
            else if (actionText === 'pending') connectStatus = 'pending';

            let name = '';
            const inviteLabel = actionEl.getAttribute('aria-label') || '';
            const nameMatch = inviteLabel.match(/Invite\\s+(.+?)\\s+to connect/i);
            if (nameMatch) {
                name = nameMatch[1].trim();
            } else {
                const spans = [...link.querySelectorAll('span')]
                    .map((el) => (el.textContent || '').trim())
                    .filter(Boolean);
                name = spans[0] || (link.textContent || '').trim().split('\\n')[0].slice(0, 80);
            }

            let headline = '';
            const subtitle = card.querySelector(
                '.entity-result__primary-subtitle, .entity-result__summary, div[class*="primary-subtitle"]'
            );
            if (subtitle) {
                headline = (subtitle.textContent || '').trim();
            } else {
                const lines = [...card.querySelectorAll('span, div, p')]
                    .map((el) => (el.textContent || '').trim())
                    .filter((text) => text.length > 8 && text.length < 200);
                const nameText = (link.textContent || '').trim();
                headline = lines.find((text) => text !== nameText) || '';
            }

            profiles.push({
                name,
                headline: headline.slice(0, 200),
                profile_url: `https://www.linkedin.com/in/${match[1]}/`,
                connect_status: connectStatus,
            });
            cardFound = true;
            break;
        }

        if (!cardFound) {
            profiles.push({
                name: (link.textContent || '').trim(),
                headline: '',
                profile_url: `https://www.linkedin.com/in/${match[1]}/`,
                connect_status: 'unknown',
            });
        }
    }

    return profiles;
}"""


def normalize_profile_url(href):
    if not href:
        return None
    match = PROFILE_URL_PATTERN.search(href)
    if not match:
        return None
    slug = match.group(0).split("/")[-1]
    if not slug:
        return None
    return f"https://www.linkedin.com/in/{slug}/"


def profile_connection_state(card):
    try:
        if card.locator("button[aria-label*='Pending' i]").count() > 0:
            return "pending"
        card_text = card.inner_text().lower()
        if re.search(r"\bpending\b", card_text):
            return "pending"
    except Exception:
        pass
    if card.locator(CONNECT_INVITE_LINK_SELECTOR).count() > 0:
        return "connect"
    if card.locator("button[aria-label*='to connect' i]").count() > 0:
        return "connect"
    if card.locator("button").filter(has_text=re.compile(r"^\s*Connect\s*$", re.I)).count() > 0:
        return "connect"
    if card.locator("button[aria-label*='Message' i]").count() > 0:
        return "connected"
    return "unknown"


def scrape_profiles_from_dom(page):
    try:
        return page.evaluate(SCRAPE_PROFILES_JS)
    except Exception:
        return []


def load_saved_profile_urls():
    saved = set()
    if not os.path.exists(PROFILES_CSV):
        return saved
    try:
        with open(PROFILES_CSV, "r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                url = row.get("profile_url", "").strip()
                if url:
                    saved.add(url)
    except (OSError, csv.Error):
        pass
    return saved


def ensure_profiles_csv():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    expected_headers = get_csv_headers()
    if not os.path.exists(PROFILES_CSV):
        with open(PROFILES_CSV, "w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(expected_headers)
        return

    try:
        with open(PROFILES_CSV, "r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            current_header = next(reader, None)
    except (OSError, csv.Error):
        current_header = None

    if current_header != expected_headers:
        existing_rows = []
        try:
            with open(PROFILES_CSV, "r", encoding="utf-8", newline="") as handle:
                existing_rows = list(csv.DictReader(handle))
        except (OSError, csv.Error):
            existing_rows = []

        columns = get_csv_columns()
        with open(PROFILES_CSV, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in existing_rows:
                writer.writerow({key: row.get(key, "") for key in columns})


def scrape_profiles_to_csv(page, logger, keyword, location):
    ensure_profiles_csv()
    saved_urls = load_saved_profile_urls()
    new_rows = []

    cards = page.locator(RESULT_CARD_SELECTOR)
    card_count = cards.count()
    scraped_profiles = []

    if card_count > 0:
        for i in range(card_count):
            card = cards.nth(i)
            name = ""
            headline = ""
            profile_url = None

            try:
                link = card.locator("a[href*='/in/']").first
                if link.count() > 0:
                    name = (link.inner_text() or "").strip()
                    profile_url = normalize_profile_url(link.get_attribute("href"))
            except Exception:
                pass

            try:
                subtitle = card.locator(
                    ".entity-result__primary-subtitle, "
                    ".entity-result__summary, "
                    "div[class*='primary-subtitle']"
                ).first
                if subtitle.count() > 0:
                    headline = (subtitle.inner_text() or "").strip()
            except Exception:
                pass

            if not profile_url:
                continue

            scraped_profiles.append(
                {
                    "name": name or "(unknown)",
                    "headline": headline,
                    "profile_url": profile_url,
                    "connect_status": profile_connection_state(card),
                }
            )
    else:
        scraped_profiles = scrape_profiles_from_dom(page)
        card_count = len(scraped_profiles)

    for profile in scraped_profiles:
        profile_url = profile.get("profile_url")
        if not profile_url or profile_url in saved_urls:
            continue

        saved_urls.add(profile_url)
        new_rows.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "name": profile.get("name") or "(unknown)",
                "headline": profile.get("headline", ""),
                "profile_url": profile_url,
                "keyword": keyword,
                "location": location or "anywhere",
                "connect_status": profile.get("connect_status", "unknown"),
            }
        )

    if new_rows:
        with open(PROFILES_CSV, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=get_csv_columns())
            writer.writerows(new_rows)

    logger.info(f"Scraped {card_count} profile(s); {len(new_rows)} new saved to CSV.")
    return len(new_rows)
