import re
from urllib.parse import quote

from common.geo_urns import DEFAULT_LOCATION_GEO_URNS, resolve_geo_urn
from common.helpers import search_delay
from connections.config import LOCATION_GEO_URNS

PEOPLE_SEARCH_URL = "https://www.linkedin.com/search/results/people/"

RESULT_CARD_SELECTORS = (
    "li.reusable-search__result-container",
    "div[data-chameleon-result-urn]",
    "div.entity-result",
    "ul.reusable-search__entity-result-list > li",
    "main ul > li:has(a[href*='/in/'])",
    "main ol > li:has(a[href*='/in/'])",
)
RESULT_CARD_SELECTOR = ", ".join(RESULT_CARD_SELECTORS)
PROFILE_LINK_SELECTOR = "main a[href*='/in/']"
CONNECT_INVITE_LINK_SELECTOR = "main a[href*='/preload/search-custom-invite/']"


def location_geo_urn(location):
    merged = dict(DEFAULT_LOCATION_GEO_URNS)
    merged.update(LOCATION_GEO_URNS or {})
    return resolve_geo_urn(location, merged)


def _escape_locator_text(text):
    return str(text or "").replace("'", "\\'")


def _pick_location_option(page, location):
    loc = (location or "").strip()
    if not loc:
        return None

    exact = page.locator(
        f"[role='option']:has-text('{_escape_locator_text(loc)}'), "
        f"div.basic-typeahead__selectable:has-text('{_escape_locator_text(loc)}')"
    )
    if exact.count() > 0:
        return exact.first

    loc_lower = loc.casefold()
    options = page.locator("[role='option'], div.basic-typeahead__selectable")
    count = options.count()
    for idx in range(count):
        option = options.nth(idx)
        try:
            label = (option.inner_text() or "").strip()
        except Exception:
            continue
        if label.casefold() == loc_lower or loc_lower in label.casefold():
            return option
    return None


def build_people_search_url(keyword, location="", page_num=1, *, include_location_in_keywords=False):
    keyword = (keyword or "").strip()
    if not keyword:
        raise ValueError("Keyword is required for people search.")
    search_text = keyword
    if include_location_in_keywords and location:
        search_text = f"{keyword} {location}".strip()
    params = [f"keywords={quote(search_text)}", "origin=GLOBAL_SEARCH_HEADER"]

    geo = None if include_location_in_keywords else location_geo_urn(location)
    if geo:
        params.append(f"geoUrn=%5B%22{geo}%22%5D")

    url = f"{PEOPLE_SEARCH_URL}?{'&'.join(params)}"
    if page_num > 1:
        url += f"&page={page_num}"
    return url, bool(geo)


def apply_location_filter_ui(page, location, logger, min_delay=1, max_delay=2):
    if not location:
        return True

    try:
        location_button = page.locator(
            "button.search-reusables__filter-pill-button:has-text('Locations'), "
            "button.search-reusables__filter-pill-button:has-text('Location'), "
            "button:has-text('Locations'), "
            "button:has-text('Location'), "
            "button[aria-label*='Location' i], "
            "button[aria-label*='location' i], "
            "label:has-text('Locations')"
        )
        if location_button.count() == 0:
            logger.info(f"Location filter button not found for '{location}'.")
            return False

        location_button.first.click()
        search_delay(page, min_delay, max_delay)

        location_input = page.locator(
            "input[placeholder*='location' i], "
            "input[aria-label*='location' i], "
            "input[aria-label*='Add a location' i]"
        )
        if location_input.count() == 0:
            logger.info(f"Location input not found for '{location}'.")
            return False

        location_input.first.fill(location)
        search_delay(page, min_delay, max_delay)

        option = _pick_location_option(page, location)
        if option is None:
            logger.info(f"No location suggestion matching '{location}'.")
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            return False

        option.click()
        search_delay(page, min_delay, max_delay)

        for label in ("Show results", "Apply", "Done"):
            button = page.locator(f"button:has-text('{label}')")
            if button.count() > 0:
                button.first.click()
                search_delay(page, min_delay, max_delay)
                break

        logger.info(f"Location filter applied: {location}")
        return True
    except Exception as exc:
        logger.info(f"Could not apply location filter for '{location}': {exc}")
        return False


def wait_for_results(page, timeout=15000):
    try:
        page.wait_for_selector(RESULT_CARD_SELECTOR, timeout=timeout)
        return True
    except Exception:
        try:
            page.wait_for_selector(PROFILE_LINK_SELECTOR, timeout=5000)
            return True
        except Exception:
            return False


def open_search(page, keyword, location, page_num, logger, min_delay=1, max_delay=2):
    url, geo_filter_used = build_people_search_url(keyword, location, page_num)
    filter_mode = "geoUrn filter" if geo_filter_used else (
        "Locations filter" if location else "no location"
    )
    logger.info(
        f"Searching keyword='{keyword}' location='{location or 'anywhere'}' "
        f"({filter_mode}, page {page_num})"
    )
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    search_delay(page, min_delay, max_delay)

    if location and not geo_filter_used:
        if apply_location_filter_ui(page, location, logger, min_delay, max_delay):
            wait_for_results(page)
            return
        logger.info(
            f"Location UI filter unavailable for '{location}' — "
            "retrying with location appended to keywords."
        )
        url, _ = build_people_search_url(
            keyword, location, page_num, include_location_in_keywords=True
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        search_delay(page, min_delay, max_delay)

    wait_for_results(page)


def scroll_results(page, scroll_rounds=6, min_delay=1, max_delay=2):
    for _ in range(scroll_rounds):
        page.mouse.wheel(0, 3000)
        search_delay(page, min_delay, max_delay)


def unique_profile_link_count(page):
    try:
        return page.evaluate(
            """() => {
                const slugs = new Set();
                for (const link of document.querySelectorAll('main a[href*="/in/"]')) {
                    const match = link.href.match(/\\/in\\/([^/?#]+)/);
                    if (match) slugs.add(match[1]);
                }
                return slugs.size;
            }"""
        )
    except Exception:
        return 0


def result_count(page):
    for selector in RESULT_CARD_SELECTORS:
        count = page.locator(selector).count()
        if count > 0:
            return count

    return unique_profile_link_count(page)


def no_results(page):
    if result_count(page) > 0:
        return False
    try:
        body = page.locator("body").inner_text().lower()
    except Exception:
        return True
    return any(
        phrase in body
        for phrase in (
            "no results found",
            "we couldn't find",
            "couldn't find a match",
            "try different keywords",
            "no results for",
        )
    )


def first_profile_slug(page):
    try:
        link = page.locator(f"{RESULT_CARD_SELECTOR} {PROFILE_LINK_SELECTOR}").first
        if link.count() == 0:
            link = page.locator("main " + PROFILE_LINK_SELECTOR).first
        if link.count() == 0:
            return None
        href = link.get_attribute("href")
        if not href:
            return None
        slug = href.split("/in/", 1)[-1].split("?", 1)[0].split("/", 1)[0]
        return slug or None
    except Exception:
        return None
