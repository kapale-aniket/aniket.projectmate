"""Search LinkedIn for each name from a sheet and send one matching connection."""
import re

from common.bootstrap import ensure_automation_path

ensure_automation_path()

from common.browser import launch_browser
from common.helpers import invite_delay, search_delay
from common.session import check_session_via_feed
from connections.config import MAX_DELAY, MIN_DELAY, SEARCH_MAX_DELAY, SEARCH_MIN_DELAY
from connections.connect import (
    _card_connect_button,
    _card_is_connectable,
    click_connect_target,
    confirm_invite_dialog,
    dismiss_open_dialogs,
    name_from_connect_target,
)
from connections.connection_logger import ConnectionLogger
from connections.people_search import RESULT_CARD_SELECTOR, open_search, scroll_results

_STOP_WORDS = {
    "college", "university", "institute", "institution", "department", "science",
    "commerce", "arts", "engineering", "technology", "computer", "applications",
    "dist", "tal", "road", "ward", "the", "and", "for", "of", "at",
}


def _tokens(name):
    return [part.casefold() for part in str(name or "").split() if part]


def _card_display_name(card):
    try:
        link = card.locator("a[href*='/in/']").first
        if link.count() == 0:
            return ""
        text = (link.inner_text() or "").strip()
    except Exception:
        return ""
    line = text.split("\n")[0].strip()
    line = re.sub(r"\s*[•|].*$", "", line).strip()
    return line


def _meaningful_tokens(text, min_len=4):
    tokens = []
    for word in re.split(r"[^a-z0-9]+", str(text or "").casefold()):
        if len(word) < min_len or word in _STOP_WORDS:
            continue
        if word not in tokens:
            tokens.append(word)
        if len(tokens) >= 6:
            break
    return tokens


def _name_matches(name, haystack):
    """True when a real name token from the sheet appears on the LinkedIn card."""
    tokens = [token for token in _tokens(name) if len(token) >= 3 and token not in _STOP_WORDS]
    if not tokens:
        return False
    return any(token in haystack for token in tokens)


def _field_matches(value, haystack):
    """True when the college, designation, or university text appears on the card."""
    raw = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    if len(raw) >= 3 and raw in haystack:
        return True
    return any(token in haystack for token in _meaningful_tokens(value))


def match_fields(person, display, blob):
    """Which sheet fields hit this LinkedIn card. Any one field is enough to connect."""
    haystack = f"{display}\n{blob}".casefold()
    found = []
    if _name_matches(person.get("name"), haystack):
        found.append("name")
    if _field_matches(person.get("college"), haystack):
        found.append("college")
    if _field_matches(person.get("designation"), haystack):
        found.append("designation")
    if _field_matches(person.get("university"), haystack):
        found.append("university")
    return found


def _result_cards(page):
    cards = page.locator(RESULT_CARD_SELECTOR)
    try:
        if cards.count() > 0:
            return cards
    except Exception:
        pass
    return page.locator("main li:has(a[href*='/in/'])")


def pick_matching_card(page, person):
    """Return (card, display_name, reason). reason lists the fields that matched."""
    cards = _result_cards(page)
    scored = []
    try:
        count = min(cards.count(), 12)
    except Exception:
        count = 0
    for index in range(count):
        card = cards.nth(index)
        display = _card_display_name(card)
        try:
            blob = card.inner_text() or ""
        except Exception:
            blob = ""
        fields = match_fields(person, display, blob)
        if not fields:
            continue
        score = 0
        if "name" in fields:
            score += 40
        if "college" in fields:
            score += 25
        if "designation" in fields:
            score += 15
        if "university" in fields:
            score += 15
        scored.append((score, index, display or person.get("name") or "", fields))
    if not scored:
        return None, "", "no match on name, college, designation, or university"
    scored.sort(key=lambda item: (-item[0], item[1]))
    _score, best_index, best_name, fields = scored[0]
    return cards.nth(best_index), best_name, ", ".join(fields)


def open_did_you_mean(page, logger):
    """Follow LinkedIn's spelling suggestion when the typed name is not exact."""
    try:
        banner = page.get_by_text(re.compile(r"did you mean", re.I))
        if banner.count() == 0:
            return False
        link = page.locator("main a[href*='keywords=']").first
        if link.count() == 0:
            return False
        logger.info("Opening LinkedIn name suggestion.")
        link.click(timeout=8000)
        page.wait_for_load_state("domcontentloaded", timeout=20000)
        search_delay(page, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)
        return True
    except Exception:
        return False


def _send_on_card(page, card, logger, keyword, location):
    if not _card_is_connectable(card):
        return "already"
    button = _card_connect_button(card)
    if button is None:
        return "no_button"
    href = button.get_attribute("href") or ""
    aria = button.get_attribute("aria-label") or ""
    label = name_from_connect_target(href=href, aria_label=aria) or keyword
    dismiss_open_dialogs(page)
    if not click_connect_target(button):
        dismiss_open_dialogs(page)
        return "click_failed"
    page.wait_for_timeout(800)
    if confirm_invite_dialog(page):
        logger.log_invite_action(label, keyword, location, "sent")
        invite_delay(page, MIN_DELAY, MAX_DELAY)
        return "sent"
    dismiss_open_dialogs(page)
    return "skipped"


def run(people=None, max_connections=0):
    people = [person for person in (people or []) if str(person.get("name") or "").strip()]
    if not people:
        raise SystemExit("No names to search. Upload a sheet with a name column.")
    limit = int(max_connections or 0)
    if limit > 0:
        people = people[:limit]

    logger = ConnectionLogger()
    total = len(people)
    logger.info(f"Perfect connection search: {total} name(s).")
    invites_sent = 0

    with launch_browser(blocked_resource_types={"image", "media", "font"}) as (
        _browser,
        _context,
        page,
    ):
        if not check_session_via_feed(page, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY, logger=logger):
            raise SystemExit(1)

        for index, person in enumerate(people, start=1):
            name = person["name"]
            place = person.get("district") or person.get("college") or "anywhere"
            logger.info(f"Searching person {index}/{total}: {name} | {place}")
            try:
                search_delay(page, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)
                open_search(page, name, "", 1, logger, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)
                scroll_results(page, 2, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)
                card, matched_name, reason = pick_matching_card(page, person)
                if card is None and open_did_you_mean(page, logger):
                    scroll_results(page, 2, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)
                    card, matched_name, reason = pick_matching_card(page, person)
                if card is None:
                    logger.info(f"Skipped {name}: {reason}.")
                    continue
                outcome = _send_on_card(page, card, logger, name, place)
                if outcome == "sent":
                    invites_sent += 1
                    sent_line = f"Sent {invites_sent} connection request(s)."
                    logger.info(f"{sent_line} Matched {matched_name} on {reason}.")
                    print(sent_line, flush=True)
                elif outcome == "already":
                    logger.info(f"Skipped {name}: matched {matched_name} but already connected or pending.")
                else:
                    logger.info(f"Skipped {name}: matched {matched_name} but Connect was not sent ({outcome}).")
            except Exception as exc:
                logger.info(f"Person failed ({name}): {exc}")

    logger.info(f"Done. Sent {invites_sent} connection request(s).")
