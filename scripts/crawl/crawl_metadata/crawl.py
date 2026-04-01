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
from scripts.utils.db import get_conn, init_db, insert_cv_rows
from scripts.crawl.crawl_metadata.get_crawled_ids import get_crawled_ids
from scripts.configs.config import HEADERS

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
    print(f"[INFO] Đã cập nhật cookies vào session.")

    bearer = extract_bearer_from_cookie(cookies)
    if bearer:
        HEADERS["Authorization"] = bearer
        print(f"[INFO] Đã set Authorization header từ cookie.")
    else:
        print("[WARN] Không tìm thấy Bearer token trong cookie.")
    
    page = 1
    needed_stop = 0
    total_inserted = 0

    while page <= max_pages and not needed_stop:

        try:
            j = fetch_page(session, HEADERS, page)
        except RuntimeError as e:
            msg = str(e)
            print(f"{msg}")
            break

        data = safe_get(j, "cvs", "data", default=[])

        if not data:
            print(f"[STOP] page={page} không còn data (data rỗng).")
            break
        
        rows = [flatten_cv_item(item) for item in data]
        if not rows:
            print("[SKIP] Không có CV nào mới để insert.")
            break
        
        inserted = insert_cv_rows(conn, rows)
        total_inserted += inserted

        if inserted == 0:
            print("[STOP] Không có CV mới nào được insert, dừng crawl.")
            break

        cur = safe_get(j, "cvs", "current_page", default=page)
        last = safe_get(j, "cvs", "last_page", default=None)

        print(
            f"[OK] page={cur} rows={len(data)} inserted={inserted} total_inserted={total_inserted} last_page={last}"
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

    return total_inserted


if __name__ == "__main__":
    max_pages = 100

    conn = get_conn()
    init_db(conn)
    total = scrape_all(max_pages=max_pages, conn=conn)
    conn.close()

    if total > 0:
        print(f"\n[SAVED] Đã insert {total} CV vào PostgreSQL.")
    else:
        print("\n[INFO] Không có CV mới nào được ghi.")