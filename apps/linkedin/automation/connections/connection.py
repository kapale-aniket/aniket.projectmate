import argparse

from common.bootstrap import ensure_automation_path

ensure_automation_path()

from common.browser import launch_browser
from common.helpers import search_delay
from common.session import check_session_via_feed
from connections.config import (
    CONNECTION_KEYWORDS,
    CONNECTION_LOCATIONS,
    MAX_CONNECTIONS_PER_RUN,
    MAX_DELAY,
    MAX_PAGES,
    MIN_DELAY,
    SCROLL_ROUNDS,
    SEARCH_MAX_DELAY,
    SEARCH_MIN_DELAY,
)
from connections.connect import send_connection_invites
from connections.people_search import (
    first_profile_slug,
    no_results,
    open_search,
    result_count,
    scroll_results,
)
from connections.connection_logger import ConnectionLogger


def parse_args():
    parser = argparse.ArgumentParser(description="LinkedIn connection search bot")
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        help="Search keyword (use multiple times for more keywords)",
    )
    parser.add_argument(
        "--location",
        action="append",
        dest="locations",
        help="Location filter (use multiple times for more cities)",
    )
    return parser.parse_args()


def pause_search(page):
    try:
        search_delay(page, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)
    except Exception:
        pass


def is_logged_in(page, logger):
    return check_session_via_feed(
        page,
        SEARCH_MIN_DELAY,
        SEARCH_MAX_DELAY,
        logger=logger,
    )


def run(keywords=None, locations=None):
    keywords = [k.strip() for k in (keywords or CONNECTION_KEYWORDS) if str(k).strip()]
    locations = locations if locations is not None else CONNECTION_LOCATIONS
    locations = [str(loc).strip() for loc in locations] if locations else [""]
    if not keywords:
        raise SystemExit("No keywords configured. Add at least one keyword.")

    logger = ConnectionLogger()
    logger.info(f"Starting (max {MAX_CONNECTIONS_PER_RUN} invites this run).")
    logger.info(
        f"Search plan: {len(keywords)} keyword(s) × {len(locations)} location(s)."
    )
    for kw in keywords:
        for loc in locations:
            logger.info(f"  - {kw} | {loc or 'anywhere'}")
    invites_sent = 0

    with launch_browser(blocked_resource_types={"image", "media", "font"}) as (
        browser,
        context,
        page,
    ):
        if not is_logged_in(page, logger):
            raise SystemExit(1)

        for keyword in keywords:
            if invites_sent >= MAX_CONNECTIONS_PER_RUN:
                break
            for location in locations:
                if invites_sent >= MAX_CONNECTIONS_PER_RUN:
                    break

                page_num = 1
                previous_first_slug = None

                while page_num <= MAX_PAGES:
                    if invites_sent >= MAX_CONNECTIONS_PER_RUN:
                        break
                    try:
                        pause_search(page)
                        open_search(
                            page,
                            keyword,
                            location,
                            page_num,
                            logger,
                            SEARCH_MIN_DELAY,
                            SEARCH_MAX_DELAY,
                        )
                        scroll_results(
                            page,
                            SCROLL_ROUNDS,
                            SEARCH_MIN_DELAY,
                            SEARCH_MAX_DELAY,
                        )

                        if no_results(page):
                            logger.info(
                                f"No more people for '{keyword}' | "
                                f"{location or 'anywhere'} (page {page_num})."
                            )
                            break

                        profile_count = result_count(page)
                        if profile_count == 0:
                            logger.info(f"No profiles on page {page_num}. Stopping.")
                            break

                        first_slug = first_profile_slug(page)
                        if page_num > 1 and first_slug and first_slug == previous_first_slug:
                            logger.info(f"Last page reached (page {page_num - 1} repeated).")
                            break
                        previous_first_slug = first_slug

                        pause_search(page)
                        # No CSV/Excel output for connections — invites only.
                        invites_remaining = MAX_CONNECTIONS_PER_RUN - invites_sent
                        invites_sent += send_connection_invites(
                            page,
                            logger,
                            keyword,
                            location,
                            invites_remaining,
                            MIN_DELAY,
                            MAX_DELAY,
                        )
                        logger.info(f"Finished page {page_num} ({profile_count} profile(s)).")
                        pause_search(page)
                        page_num += 1
                    except Exception as exc:
                        logger.info(
                            f"Page failed ({keyword} | {location} | page {page_num}): {exc}"
                        )
                        page_num += 1

                if page_num > MAX_PAGES:
                    logger.info(
                        f"Reached MAX_PAGES={MAX_PAGES} for "
                        f"'{keyword}' | {location or 'anywhere'}."
                    )

                pause_search(page)

    logger.info(f"Done. Sent {invites_sent} connection request(s). No output file created.")


if __name__ == "__main__":
    args = parse_args()
    run(keywords=args.keywords, locations=args.locations)
