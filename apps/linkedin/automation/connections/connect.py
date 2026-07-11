import re
from urllib.parse import parse_qs, urlparse

from common.helpers import invite_delay

CONNECT_SELECTORS = (
    "main a[href*='/preload/search-custom-invite/']",
    "button[aria-label*='to connect']",
)
CONNECT_BUTTON_SELECTOR = CONNECT_SELECTORS[0]

SEND_WITHOUT_NOTE_LABELS = (
    "Send without a note",
    "Send now",
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
        target.first.scroll_into_view_if_needed()
        target.first.click(timeout=8000)
        return True
    except Exception:
        try:
            target.first.evaluate("el => el.click()")
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
        dialog.first.wait_for(state="visible", timeout=8000)
    except Exception:
        return False

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


def collect_connect_targets(page):
    targets = []
    seen = set()

    for selector in CONNECT_SELECTORS:
        elements = page.locator(selector)
        for i in range(elements.count()):
            element = elements.nth(i)
            href = element.get_attribute("href") or ""
            aria_label = element.get_attribute("aria-label") or ""
            key = href or aria_label
            if not key or key in seen:
                continue
            seen.add(key)
            targets.append({"href": href, "aria_label": aria_label})
        if targets:
            break

    return targets


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

        href = target_info["href"]
        aria_label = target_info["aria_label"]
        if href:
            target = page.locator(f'main a[href="{href}"]')
        elif aria_label:
            target = page.locator(f'button[aria-label="{aria_label}"]')
        else:
            continue

        if target.count() == 0:
            continue

        name = name_from_connect_target(href=href, aria_label=aria_label)
        if not click_connect_target(target):
            logger.info(f"Could not click Connect for {name}")
            dismiss_open_dialogs(page)
            continue

        page.wait_for_timeout(800)

        if confirm_invite_dialog(page):
            invites_sent += 1
            logger.log_invite_action(name, keyword, location, "sent")
        else:
            logger.log_invite_action(name, keyword, location, "skipped")

        dismiss_open_dialogs(page)
        invite_delay(page, min_delay, max_delay)

    return invites_sent
