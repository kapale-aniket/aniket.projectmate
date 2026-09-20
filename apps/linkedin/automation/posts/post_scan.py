from common.bootstrap import ensure_automation_path

ensure_automation_path()

import os

from common.browser import launch_browser
from common.dedupe import dedupe_records
from common.session import check_session_via_feed
from posts.config import (
    MAX_POSTS_PER_RUN,
    MAX_SCROLL_ROUNDS,
    SEARCH_MAX_DELAY,
    SEARCH_MIN_DELAY,
)
from posts.excel_writer import write_hiring_excel
from posts.post_filter import parse_hiring_post
from posts.post_scraper import iter_new_feed_posts
from posts.post_store import (
    OUTPUT_DIR,
    checked_post_id_set,
    daily_excel_path,
    load_state,
    save_state,
)


def is_logged_in(page):
    return check_session_via_feed(page, SEARCH_MIN_DELAY, SEARCH_MAX_DELAY)


def merge_hiring_posts(existing_posts, new_posts):
    return dedupe_records(new_posts + existing_posts, lambda post: post.get("post_id"))


def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    state = load_state()
    already_checked = checked_post_id_set(state)
    hiring_posts = list(state.get("hiring_posts", []))
    resume_from_post_id = state.get("last_checked_post_id", "")

    with launch_browser(blocked_resource_types={"image", "media", "font"}) as (
        browser,
        context,
        page,
    ):
        try:
            from posts.post_store import purge_old_files

            purge_old_files(retention_days=4)
        except Exception:
            pass
        if not is_logged_in(page):
            print("\n*** LinkedIn session expired! ***")
            print("Run: python common/save_session.py")
            print("Then: python posts/post_scan.py")
            raise SystemExit(1)

        if resume_from_post_id:
            print(f"Resuming from last checked post id: {resume_from_post_id}")
        else:
            print("First run — checking feed from the top.")

        checked_this_run = 0
        new_hiring_count = 0
        last_new_post_id = resume_from_post_id

        for post in iter_new_feed_posts(
            page,
            resume_from_post_id,
            already_checked,
            MAX_SCROLL_ROUNDS,
            SEARCH_MIN_DELAY,
            SEARCH_MAX_DELAY,
        ):
            post_id = post["post_id"]
            checked_this_run += 1
            already_checked.add(post_id)
            state["checked_post_ids"].append(post_id)
            last_new_post_id = post_id

            hiring = parse_hiring_post(
                post_id,
                post["post_url"],
                post.get("author", ""),
                post.get("text", ""),
                post.get("apply_link_hrefs"),
            )
            if hiring:
                hiring_posts = merge_hiring_posts(hiring_posts, [hiring])
                new_hiring_count += 1
                print(
                    f"  Hiring post: {hiring.get('company_name', '-')} | "
                    f"{hiring.get('job_role', '-')} | {post_id}"
                )

            if MAX_POSTS_PER_RUN and checked_this_run >= MAX_POSTS_PER_RUN:
                print(f"Reached MAX_POSTS_PER_RUN={MAX_POSTS_PER_RUN}.")
                break

        state["last_checked_post_id"] = last_new_post_id
        state["hiring_posts"] = hiring_posts
        save_state(state)

        excel_path = daily_excel_path()
        row_count = write_hiring_excel(hiring_posts, excel_path)
        print(
            f"\nChecked {checked_this_run} new post(s) this run. "
            f"Last checked post id: {last_new_post_id or '-'}"
        )
        print(
            f"Excel: {excel_path} — {new_hiring_count} new hiring post(s), "
            f"{row_count} total fresher/intern hiring post(s)."
        )
        file_name = os.path.basename(excel_path)
        print(f'Scraping completed. Check "{file_name}" in Output.')


if __name__ == "__main__":
    run()
