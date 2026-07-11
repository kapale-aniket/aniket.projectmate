import re

from common.helpers import search_delay

FEED_URL = "https://www.linkedin.com/feed/"
POST_CARD_SELECTOR = "div.feed-shared-update-v2[data-urn*='activity']"
POST_CARD_FALLBACK = "div[data-urn*='activity:']"


def post_id_from_urn(urn):
    if not urn:
        return None
    match = re.search(r"activity:(\d+)", urn)
    return match.group(1) if match else None


def post_url_from_id(post_id):
    return f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/"


def expand_post_text(card):
    try:
        see_more = card.locator("button:has-text('see more'), button:has-text('…see more')")
        if see_more.count() > 0:
            see_more.first.click()
    except Exception:
        pass


def read_post_card(card):
    urn = card.get_attribute("data-urn")
    post_id = post_id_from_urn(urn)
    if not post_id:
        return None

    author = ""
    text = ""

    try:
        author_node = card.locator(
            ".update-components-actor__name, .feed-shared-actor__name, span[dir='ltr'] span"
        ).first
        if author_node.count() > 0:
            author = (author_node.inner_text() or "").strip()
    except Exception:
        pass

    expand_post_text(card)

    try:
        text_node = card.locator(
            ".feed-shared-update-v2__description, "
            ".update-components-text, "
            ".feed-shared-text"
        ).first
        if text_node.count() > 0:
            text = (text_node.inner_text() or "").strip()
    except Exception:
        pass

    if not text:
        try:
            text = (card.inner_text() or "").strip()
        except Exception:
            text = ""

    apply_link_hrefs = []
    try:
        link_nodes = card.locator("a[href]")
        for index in range(link_nodes.count()):
            href = link_nodes.nth(index).get_attribute("href")
            if href:
                apply_link_hrefs.append(href)
    except Exception:
        pass

    return {
        "post_id": post_id,
        "post_url": post_url_from_id(post_id),
        "author": author,
        "text": text,
        "apply_link_hrefs": apply_link_hrefs,
    }


def collect_feed_posts(page):
    posts = []
    seen_ids = set()

    cards = page.locator(POST_CARD_SELECTOR)
    if cards.count() == 0:
        cards = page.locator(POST_CARD_FALLBACK)

    for index in range(cards.count()):
        post = read_post_card(cards.nth(index))
        if not post or post["post_id"] in seen_ids:
            continue
        seen_ids.add(post["post_id"])
        posts.append(post)

    return posts


def load_feed(page, min_delay, max_delay):
    page.goto(FEED_URL, wait_until="domcontentloaded", timeout=60000)
    search_delay(page, min_delay, max_delay)


def is_checkpoint_post(post_id, last_checked_post_id, already_checked):
    if post_id in already_checked:
        return True
    if last_checked_post_id and post_id == last_checked_post_id:
        return True
    return False


def iter_new_feed_posts(
    page,
    last_checked_post_id,
    already_checked,
    scroll_rounds,
    min_delay,
    max_delay,
):
    """Yield only posts newer than the last run. Stop at the last checked post."""
    load_feed(page, min_delay, max_delay)

    seen_this_run = set()
    checkpoint_reached = False

    for _ in range(scroll_rounds + 1):
        if checkpoint_reached:
            break

        for post in collect_feed_posts(page):
            post_id = post["post_id"]
            if post_id in seen_this_run:
                continue
            seen_this_run.add(post_id)

            if is_checkpoint_post(post_id, last_checked_post_id, already_checked):
                checkpoint_reached = True
                break

            yield post

        if not checkpoint_reached:
            page.mouse.wheel(0, 3500)
            search_delay(page, min_delay, max_delay)
