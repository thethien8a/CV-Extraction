import random
import time

import requests
from dotenv import load_dotenv

from scripts.configs.config import COOKIES_FILE
from scripts.crawl.crawl_metadata.api import fetch_page
from scripts.crawl.crawl_metadata.browser import (
    is_cookie_expired,
    load_cookie_lines,
    open_browser_and_get_cookie_line,
)
from scripts.crawl.crawl_metadata.utils import (
    cookie_str_to_dict,
    extract_bearer_from_cookie,
    flatten_cv_item,
    safe_get,
)
from scripts.utils.db import get_conn, init_db, upsert_cv_rows

load_dotenv()


def scrape_all(max_pages: int, conn, sleep_range=(0.6, 1.2)) -> int:
    cookie_lines = load_cookie_lines(COOKIES_FILE)
    if not cookie_lines:
        raise RuntimeError("Không có cookie nào để dùng (kể cả sau khi mở Selenium).")

    cookie_line = cookie_lines[0]
    if is_cookie_expired(cookie_line):
        print("[SKIP] Cookie hết hạn.")
        print("[ACTION] Thử lấy cookie mới bằng Selenium")
        new_cookie_line = open_browser_and_get_cookie_line()
        if not new_cookie_line:
            print("[FATAL] Không lấy được cookie mới. Dừng.")
            return 0
        cookie_line = new_cookie_line

    session = requests.Session()
    cookies = cookie_str_to_dict(cookie_line)
    session.cookies.clear()
    session.cookies.update(cookies)
    bearer = extract_bearer_from_cookie(cookies)

    page = 1
    total_upserted = 0
    while page <= max_pages:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://tuyendung.topcv.vn",
            "Referer": "https://tuyendung.topcv.vn/",
            "Authorization": bearer,
            "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }

        try:
            j = fetch_page(session, headers, page)
        except RuntimeError as e:
            msg = str(e)
            print(f"{msg}")
            break

        data = safe_get(j, "cvs", "data", default=[])
        if not data:
            print(f"[STOP] page={page} không còn data (data rỗng).")
            break

        rows = [flatten_cv_item(item) for item in data]
        upserted = upsert_cv_rows(conn, rows)
        total_upserted += upserted

        cur = safe_get(j, "cvs", "current_page", default=page)
        last = safe_get(j, "cvs", "last_page", default=None)
        print(
            f"[OK] page={cur} rows={len(data)} upserted={upserted} total_upserted={total_upserted} last_page={last}"
        )

        if last is not None:
            try:
                if page >= int(str(last)):
                    print("[DONE] Đã tới last_page từ API.")
                    break
            except (ValueError, TypeError):
                pass

        page += 1
        time.sleep(random.uniform(*sleep_range))

    return total_upserted


if __name__ == "__main__":
    max_pages = 100

    conn = get_conn()
    init_db(conn)
    total = scrape_all(max_pages=max_pages, conn=conn)
    conn.close()

    if total > 0:
        print(f"\n[SAVED] Đã upsert {total} CV vào PostgreSQL.")
    else:
        print("\n[INFO] Không có CV mới nào được ghi.")