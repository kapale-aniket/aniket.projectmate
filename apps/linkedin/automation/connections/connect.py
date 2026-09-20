import re
from urllib.parse import parse_qs, urlparse

from common.helpers import invite_delay
from connections.people_search import RESULT_CARD_SELECTOR

CONNECT_LINK_SELECTOR = "a[href*='/preload/search-custom-invite/']"
CONNECT_BUTTON_SELECTORS = (
    CONNECT_LINK_SELECTOR,
    "button[aria-label*='connect' i]",
    "button[aria-label*='Invite' i]",
)

SEND_WITHOUT_NOTE_LABELS = (
    "Send without a note",
    "Send now",
    "Send",
)


def name_from_connect_target(href=None, aria_label=None):
    if aria_label:
        match = re.match(r"Invite\s+(.+?)\s+to connect", aria_label, re.I)
        if match:
            return match.group(1).strip()
        name = aria_label.replace("Invite", "").replace("to connect", "")
        name = name.strip(" ,")
        if name:
            return name
    if href:
        vanity = parse_qs(urlparse(href).query).get("vanityName", [""])[0]
        if vanity:
            return vanity.replace("-", " ").title()
    return "(unknown)"


def dismiss_open_dialogs(page):
    for _ in range(2):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception:
            pass

    try:
        dialog = page.locator("div[role='dialog']")
        if dialog.count() > 0:
            dialog.first.wait_for(state="hidden", timeout=3000)
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass


def click_connect_target(target):
    try:
        target.scroll_into_view_if_needed()
        target.click(timeout=8000)
        return True
    except Exception:
        try:
            target.evaluate("el => el.click()")
            return True
        except Exception:
            return False


def click_send_without_note_button(dialog):
    for button_label in SEND_WITHOUT_NOTE_LABELS:
        button = dialog.get_by_role(
            "button", name=re.compile(re.escape(button_label), re.I)
        )
        if button.count() > 0:
            try:
                button.first.click(timeout=5000)
                return True
            except Exception:
                pass

        button = dialog.locator(f"button:has-text('{button_label}')")
        if button.count() > 0:
            try:
                button.first.click(timeout=5000)
                return True
            except Exception:
                pass

        try:
            clicked = dialog.first.evaluate(
                """(node, label) => {
                    const buttons = [...node.querySelectorAll('button')];
                    const match = buttons.find((btn) =>
                        (btn.textContent || '').trim().toLowerCase() === label.toLowerCase()
                    );
                    if (!match) return false;
                    match.click();
                    return true;
                }""",
                button_label,
            )
            if clicked:
                return True
        except Exception:
            pass

    try:
        return dialog.first.evaluate(
            """(node) => {
                const buttons = [...node.querySelectorAll('button')];
                const match = buttons.find((btn) =>
                    (btn.textContent || '').toLowerCase().includes('without a note')
                );
                if (!match) return false;
                match.click();
                return true;
            }"""
        )
    except Exception:
        return False


def confirm_invite_dialog(page):
    dialog = page.locator("div[role='dialog']")
    try:
        dialog.first.wait_for(state="visible", timeout=5000)
    except Exception:
        # Some flows send immediately with no modal.
        page.wait_for_timeout(800)
        return True

    page.wait_for_timeout(500)

    try:
        note_field = dialog.locator("textarea")
        if note_field.count() > 0:
            note_field.first.fill("")
    except Exception:
        pass

    if not click_send_without_note_button(dialog):
        dismiss_open_dialogs(page)
        return False

    try:
        dialog.first.wait_for(state="hidden", timeout=8000)
    except Exception:
        dismiss_open_dialogs(page)

    return True


def _card_is_connectable(card):
    try:
        if card.locator("button[aria-label*='Message' i]").count() > 0:
            return False
        if card.locator("button[aria-label*='Pending' i]").count() > 0:
            return False
        text = card.inner_text().lower()
        if "pending" in text and "connect" not in text:
            return False
    except Exception:
        pass
    return True


def _card_connect_button(card):
    for selector in CONNECT_BUTTON_SELECTORS:
        element = card.locator(selector).first
        if element.count() > 0:
            return element

    connect_btn = card.locator("button").filter(
        has_text=re.compile(r"^\s*Connect\s*$", re.I)
    )
    if connect_btn.count() > 0:
        return connect_btn.first

    return None


def _collect_connect_targets_from_cards(page):
    targets = []
    seen = set()
    cards = page.locator(RESULT_CARD_SELECTOR)
    card_count = cards.count()

    for index in range(card_count):
        card = cards.nth(index)
        if not _card_is_connectable(card):
            continue

        button = _card_connect_button(card)
        if button is None:
            continue

        href = button.get_attribute("href") or ""
        aria_label = button.get_attribute("aria-label") or ""
        vanity = ""
        if href:
            vanity = parse_qs(urlparse(href).query).get("vanityName", [""])[0]

        key = vanity or href or aria_label or f"card-{index}"
        if key in seen:
            continue
        seen.add(key)

        targets.append(
            {
                "card_index": index,
                "href": href,
                "aria_label": aria_label,
                "vanity": vanity,
            }
        )

    return targets


def _collect_connect_targets_page_level(page):
    targets = []
    seen = set()

    for selector in CONNECT_BUTTON_SELECTORS:
        elements = page.locator(f"main {selector}")
        for index in range(elements.count()):
            element = elements.nth(index)
            href = element.get_attribute("href") or ""
            aria_label = element.get_attribute("aria-label") or ""
            vanity = parse_qs(urlparse(href).query).get("vanityName", [""])[0] if href else ""
            key = vanity or href or aria_label
            if not key or key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "card_index": None,
                    "href": href,
                    "aria_label": aria_label,
                    "vanity": vanity,
                }
            )

    plain_buttons = page.locator("main button").filter(
        has_text=re.compile(r"^\s*Connect\s*$", re.I)
    )
    for index in range(plain_buttons.count()):
        element = plain_buttons.nth(index)
        aria_label = element.get_attribute("aria-label") or ""
        key = aria_label or f"connect-btn-{index}"
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "card_index": None,
                "href": "",
                "aria_label": aria_label,
                "vanity": "",
            }
        )

    return targets


def collect_connect_targets(page):
    targets = _collect_connect_targets_from_cards(page)
    if targets:
        return targets
    return _collect_connect_targets_page_level(page)


def resolve_connect_target(page, target_info):
    card_index = target_info.get("card_index")
    if card_index is not None:
        cards = page.locator(RESULT_CARD_SELECTOR)
        if card_index < cards.count():
            button = _card_connect_button(cards.nth(card_index))
            if button is not None:
                return button

    vanity = target_info.get("vanity") or ""
    if vanity:
        link = page.locator(
            f"main a[href*='search-custom-invite'][href*='{vanity}']"
        ).first
        if link.count() > 0:
            return link

    href = target_info.get("href") or ""
    if href:
        link = page.locator(f'main a[href*="{href.split("?")[0].split("/")[-1]}"]').first
        if link.count() > 0 and "search-custom-invite" in (link.get_attribute("href") or ""):
            return link

    aria_label = target_info.get("aria_label") or ""
    if aria_label:
        button = page.get_by_role("button", name=re.compile(re.escape(aria_label), re.I))
        if button.count() > 0:
            return button.first

    return None


def invite_sent_on_card(page, card_index):
    if card_index is None:
        return False
    try:
        cards = page.locator(RESULT_CARD_SELECTOR)
        if card_index >= cards.count():
            return False
        text = cards.nth(card_index).inner_text().lower()
        return "pending" in text
    except Exception:
        return False


def send_connection_invites(page, logger, keyword, location, invites_remaining, min_delay, max_delay):
    if invites_remaining <= 0:
        return 0

    dismiss_open_dialogs(page)
    connect_targets = collect_connect_targets(page)
    logger.info(f"Found {len(connect_targets)} connectable profile(s).")

    invites_sent = 0
    for target_info in connect_targets:
        if invites_sent >= invites_remaining:
            break

        dismiss_open_dialogs(page)

        target = resolve_connect_target(page, target_info)
        if target is None:
            continue

        name = name_from_connect_target(
            href=target_info.get("href"),
            aria_label=target_info.get("aria_label"),
        )
        if not click_connect_target(target):
            logger.info(f"Could not click Connect for {name}")
            dismiss_open_dialogs(page)
            continue

        page.wait_for_timeout(800)

        card_index = target_info.get("card_index")
        if confirm_invite_dialog(page) or invite_sent_on_card(page, card_index):
            invites_sent += 1
            logger.log_invite_action(name, keyword, location, "sent")
        else:
            logger.log_invite_action(name, keyword, location, "skipped")

        dismiss_open_dialogs(page)
        invite_delay(page, min_delay, max_delay)

    return invites_sent
