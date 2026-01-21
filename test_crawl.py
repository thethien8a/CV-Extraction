import urllib.parse
import pdfplumber
import re
import time
import random
import requests
import pandas as pd
from urllib.parse import unquote
from pathlib import Path

# ==== SELENIUM ====
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from dotenv import load_dotenv

load_dotenv()

# ================== CONFIG ==================

FILTER_BY = "all"      # hoặc "not-viewed" 
SOURCE = "1"           # 1 = TopCV, nếu sau này muốn tất cả nguồn thì để "" hoặc None

API_BASE = "https://tuyendung-api.topcv.vn"
LIST_ENDPOINT = f"{API_BASE}/api/v1/cv-management/cvs"

# Trang login / dashboard
LOGIN_URL = "https://tuyendung.topcv.vn/app/login"

# Trang quản lý CV chưa xem
CV_PAGE_URL = (
    "https://tuyendung.topcv.vn/app/cvs-management"
    "?get_newest_cv=true"
    "&recruitment_campaign_id"
    f"&source={SOURCE}"
    "&status"
    "&label"
    "&filter_cv_pro=false"
    "&start_date"
    "&end_date"
    f"&filter_by={FILTER_BY}"
)

KEEP_BROWSER_OPEN = True  # debug: chạy xong thì giữ chrome, bấm Enter mới đóng

BASE_DIR = Path(__file__).resolve().parent
CHROME_USER_DATA_DIR = str(BASE_DIR / "chrome_profile_topcv")
COOKIES_FILE = str(BASE_DIR / "cookies.txt")
OUTPUT_CSV = str(BASE_DIR / "topcv_cvs_api_list.csv")
DOWNLOAD_DIR = str(BASE_DIR / "downloads_cv_pdf_topcv")
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


# ================== CORE UTILS ==================

def cookie_str_to_dict(s: str) -> dict:
    cookies = {}
    for part in s.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        cookies[k.strip()] = v.strip()
    return cookies

def extract_bearer_from_cookie(cookies: dict) -> str | None:
    raw = cookies.get("cookie__token.refresh")
    if not raw:
        return None
    raw = unquote(raw).strip()
    if raw.lower().startswith("bearer "):
        return raw
    if re.match(r"^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$", raw):
        return f"Bearer {raw}"
    return raw

def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default

def flatten_cv_item(item: dict) -> dict:
    campaign = item.get("campaign") or {}
    job = (campaign.get("job") or {}) if isinstance(campaign, dict) else {}
    apply = item.get("apply") or {}

    return {
        "cv_id": item.get("id"),
        "candidate_id ": item.get("user_id"),
        "full_name": item.get("fullname") or item.get("full_name"),
        "gender": item.get("gender"),
        "phone": item.get("phone"),
        "email": item.get("email"),
        "campaign_id": campaign.get("id"),
        "campaign_title": campaign.get("title"),
        "job_id": job.get("id"),
        "applied_position": job.get("title") or campaign.get("position_title"),
        "application_date": apply.get("created_at") or item.get("created_at_str"),
        "status_str": item.get("status_str"),
        "created_at_str": item.get("created_at_str"),
        "cv_last_update_time_str": item.get("last_update_time_str"),
        "cv_last_update_time": item.get("last_update_time"),
        "apply_id": apply.get("id"),
        "apply_status": apply.get("status"),
        "is_viewed": item.get("is_viewed"),
        "source": item.get("source"),
        "source_str": item.get("source_str"),
        "CV_Source":  "TopCV",
    }

# ================== SELENIUM HELPERS ==================

def build_cookie_header_from_driver(driver) -> str:
    cookies = driver.get_cookies()
    return "; ".join([f"{c['name']}={c.get('value', '')}" for c in cookies])

def wait_for_auth_cookie(driver, timeout=300) -> bool:
    """
    Chờ đến khi xuất hiện cookie__token.refresh (tối đa timeout giây).
    Trong lúc này bạn cứ login, nhập OTP, v.v. bình thường.
    """
    end = time.time() + timeout
    print(f"[SELENIUM] Đang chờ bạn login (tối đa {timeout} giây)...")
    last_log = 0
    while time.time() < end:
        cookies = driver.get_cookies()
        if any(c.get("name") == "cookie__token.refresh" for c in cookies):
            print("[SELENIUM] Đã thấy cookie__token.refresh → login OK.")
            return True
        if time.time() - last_log > 10:
            print("[SELENIUM] Chưa thấy cookie__token.refresh, vẫn tiếp tục chờ...")
            last_log = time.time()
        time.sleep(2)
    print("[SELENIUM] Hết thời gian chờ nhưng chưa thấy cookie__token.refresh.")
    return False

def dismiss_popups(driver):
    """
    Auto đóng mấy popup / modal sau login:
    - Modal quảng cáo lớn (button.close)
    - Popover thông báo có nút 'Không, cảm ơn' (#topcv-popover-allow-button)
    """
    # đóng modal quảng cáo lớn (nút X)
    try:
        close_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.close"))
        )
        close_btn.click()
        time.sleep(0.5)
        print("[SELENIUM] Đã click nút X (modal quảng cáo).")
    except Exception:
        pass

    # đóng popover thông báo "Không, cảm ơn"
    try:
        deny_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#topcv-popover-allow-button"))
        )
        deny_btn.click()
        time.sleep(0.5)
        print("[SELENIUM] Đã click nút 'Không, cảm ơn' (popover thông báo).")
    except Exception:
        pass

def open_browser_and_download_cvs_ui(limit=10):
    profile_path = Path(CHROME_USER_DATA_DIR)
    profile_path.mkdir(parents=True, exist_ok=True)

    opts = uc.ChromeOptions()
    opts.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--start-maximized")
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    opts.add_experimental_option("prefs", prefs)

    driver = uc.Chrome(options=opts)

    try:
        driver.get(LOGIN_URL)

        # auto login nếu có .env
        email = os.getenv("TOPCV_USERNAME")
        password = os.getenv("TOPCV_PASSWORD")
        if email and password:
            try:
                email_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Email"]'))
                )
                password_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="Mật khẩu"]')
                login_btn = driver.find_element(By.CSS_SELECTOR, 'button[class*="btn-primary"]')
                email_input.clear(); email_input.send_keys(email)
                password_input.clear(); password_input.send_keys(password)
                login_btn.click()
            except Exception as e:
                print(f"[SELENIUM] Auto login không thành công (có thể đã login rồi): {e}")

        if not wait_for_auth_cookie(driver, timeout=300):
            print("[SELENIUM] Login chưa xong / chưa có cookie auth.")
            return

        dismiss_popups(driver)

        driver.get(CV_PAGE_URL)
        time.sleep(2)

        try:
            auto_download_cv_from_list(driver, limit=limit)
            print("[DL] Hoàn tất auto_download_cv_from_list().")
        except Exception as e:
            # QUAN TRỌNG: bắt lỗi để không out sớm
            print(f"[DL][FATAL] auto_download_cv_from_list bị lỗi: {type(e).__name__}: {e}")

        # Debug: giữ browser lại để bạn nhìn trạng thái
        if KEEP_BROWSER_OPEN:
            input("[DEBUG] Đã chạy xong. Nhấn Enter để đóng Chrome...")
    finally:
        driver.quit()

def open_browser_and_get_cookie_line() -> str | None:
    """
    Mở Chrome với profile riêng, cho bạn login,
    auto đợi có cookie__token.refresh, auto đóng popup,
    nhảy sang trang quản lý CV, rồi lấy cookie và lưu cookies.txt.
    """
    profile_path = Path(CHROME_USER_DATA_DIR)
    profile_path.mkdir(parents=True, exist_ok=True)

    opts = uc.ChromeOptions()
    opts.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--start-maximized")
    prefs = {"profile.default_content_setting_values.notifications": 2}
    opts.add_experimental_option("prefs", prefs)
    
    driver = uc.Chrome(options=opts)
    try:
        print(f"[SELENIUM] Mở trình duyệt tới: {LOGIN_URL}")
        driver.get(LOGIN_URL)

        # Tự động đăng nhập nếu có thông tin trong .env
        email = os.getenv("TOPCV_USERNAME")
        password = os.getenv("TOPCV_PASSWORD")

        if email and password:
            print(f"[SELENIUM] Phát hiện credentials, đang thử tự động đăng nhập tài khoản: {email}")
            try:
                email_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Email"]'))
                )
                password_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="Mật khẩu"]')
                login_btn = driver.find_element(By.CSS_SELECTOR, 'button[class*="btn-primary"]')

                email_input.clear()
                email_input.send_keys(email)
                password_input.clear()
                password_input.send_keys(password)
                
                login_btn.click()
                print("[SELENIUM] Đã submit form đăng nhập.")
            except Exception as e:
                # Trong trường hợp ta đã tồn tại session trước đó đăng nhập rồi hoặc khi selector sai
                print(f"[SELENIUM] Lỗi khi tự động đăng nhập (có thể đã login rồi hoặc selector sai)")
        else:
            print("[SELENIUM] Không tìm thấy TOPCV_EMAIL/TOPCV_PASSWORD trong .env. Vui lòng đăng nhập thủ công.")

        # Đợi login hoàn tất dựa trên cookie auth
        if not wait_for_auth_cookie(driver, timeout=300):
            print("[SELENIUM] Không lấy được cookie auth trong thời gian cho phép.")
            return None
        try:
            # Đóng popup ở dashboard
            dismiss_popups(driver)
        except Exception:
            pass

        # NHẢY TỚI TRANG QUẢN LÝ CV
        print(f"[SELENIUM] Điều hướng tới trang CV: {CV_PAGE_URL}")
        driver.get(CV_PAGE_URL)

        # Đợi trang CV load sơ bộ
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.app, div#app, body")
                )
            )
        except Exception:
            pass

        time.sleep(2)

        cookie_line = build_cookie_header_from_driver(driver)
        if not cookie_line:
            print("[SELENIUM] Không thu được cookie nào!")
            return None

        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            f.write(cookie_line + "\n")

        print(f"[SELENIUM] Đã lưu cookie vào {COOKIES_FILE}")
        return cookie_line

    finally:
        driver.quit()

def load_cookie_lines(file_path: str = COOKIES_FILE) -> list[str]:
    path = Path(file_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if lines:
            print(f"[INFO] Đã đọc {len(lines)} dòng cookie từ {file_path}")
            return lines
        else:
            print(f"[WARN] {file_path} trống.")
    else:
        print(f"[WARN] Không tìm thấy {file_path}.")

    print("[ACTION] Mở Selenium để lấy cookie mới.")
    new_cookie_line = open_browser_and_get_cookie_line()
    if new_cookie_line:
        return [new_cookie_line]
    return []

def js_click(driver, el):
    driver.execute_script("arguments[0].click();", el)

def wait_download_done(download_dir: str, timeout=120):
    """
    Chờ đến khi không còn file .crdownload trong thư mục download.
    (TopCV thường tải PDF nên cách này ổn)
    """
    end = time.time() + timeout
    while time.time() < end:
        cr = list(Path(download_dir).glob("*.crdownload"))
        if not cr:
            return True
        time.sleep(0.5)
    return False

from selenium.webdriver.common.action_chains import ActionChains

def js_click(driver, el):
    driver.execute_script("arguments[0].click();", el)

def wait_download_done(download_dir: str, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        if not list(Path(download_dir).glob("*.crdownload")):
            return True
        time.sleep(0.4)
    return False

def auto_download_cv_from_list(driver, limit=10, sleep_range=(0.6, 1.2), per_row_retry=2):
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))

    downloaded = 0
    seen = set()
    
    # Biến để theo dõi số lần không có row mới
    no_new_rows_count = 0
    max_no_new_rows = 3

    while downloaded < limit:
        # Scroll xuống cuối trang để load thêm row (nếu có lazy loading)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        if not rows:
            print("[DL] Không thấy row nào.")
            break

        progressed = False
        new_rows_found = False

        for idx, row in enumerate(rows):
            # Kiểm tra nếu row đã được xử lý trước đó
            key = (row.get_attribute("innerText") or "")[:120]
            if key in seen:
                continue
            
            # Đánh dấu có row mới
            new_rows_found = True
            
            # Nếu đã đủ limit, dừng xử lý thêm row mới
            if downloaded >= limit:
                break
                
            seen.add(key)

            ok_this_row = False

            for attempt in range(1, per_row_retry + 1):
                try:
                    # 1) nút "..." mở menu (đúng theo ảnh: span[data-toggle="dropdown"])
                    btn = row.find_element(By.CSS_SELECTOR, 'span[data-toggle="dropdown"][role="button"]')
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.15)

                    # click bằng ActionChains trước, fail thì JS click
                    try:
                        ActionChains(driver).move_to_element(btn).pause(0.05).click(btn).perform()
                    except Exception:
                        js_click(driver, btn)

                    # 2) chờ đúng dropdown-menu đang show *trong row này*
                    def _menu_in_row(d):
                        menus = row.find_elements(By.CSS_SELECTOR, "div.dropdown-menu.show")
                        return menus[0] if menus else None

                    menu = WebDriverWait(driver, 6).until(_menu_in_row)

                    # 3) tìm item "Tải CV" *trong menu này* (span hoặc a hoặc div)
                    def _download_item(d):
                        items = menu.find_elements(
                            By.XPATH,
                            ".//*[contains(@class,'dropdown-item') and normalize-space()='Tải CV']"
                        )
                        return items[0] if items else None

                    item = WebDriverWait(driver, 6).until(_download_item)

                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", item)
                    time.sleep(0.05)

                    # Lưu số tab hiện tại để xử lý nếu mở tab mới
                    original_window = driver.current_window_handle
                    original_tabs_count = len(driver.window_handles)
                    
                    # Click vào "Tải CV" - thử ActionChains trước, fail thì dùng JS
                    try:
                        ActionChains(driver).move_to_element(item).pause(0.05).click(item).perform()
                    except Exception:
                        js_click(driver, item)
                    
                    # Đợi một chút để xem có tab mới mở không
                    time.sleep(1.5)
                    
                    # Nếu có tab mới được mở, ĐỢI FILE DOWNLOAD XONG rồi mới đóng tab
                    if len(driver.window_handles) > original_tabs_count:
                        print(f"[DL] Phát hiện tab mới đã mở, đang đợi file download...")
                        
                        # QUAN TRỌNG: Đợi file download xong TRƯỚC KHI đóng tab
                        done = wait_download_done(DOWNLOAD_DIR, timeout=120)
                        print(f"[DL] File download xong (done={done}), đang đóng tab mới...")
                        
                        # Sau khi download xong mới đóng tab
                        for handle in driver.window_handles:
                            if handle != original_window:
                                driver.switch_to.window(handle)
                                driver.close()
                        driver.switch_to.window(original_window)
                        print(f"[DL] Đã đóng tab mới và quay lại trang chính")
                        time.sleep(0.5)
                    else:
                        # Không có tab mới, đợi download bình thường
                        done = wait_download_done(DOWNLOAD_DIR, timeout=120)

                    # Đã đợi download xong ở trên rồi
                    downloaded += 1
                    progressed = True
                    ok_this_row = True
                    print(f"[DL] Row#{idx} click 'Tải CV' OK ({downloaded}/{limit})")
                    time.sleep(random.uniform(*sleep_range))
                    break

                except Exception as e:
                    # đóng menu nếu đang mở (ESC) rồi retry
                    try:
                        driver.execute_script(
                            "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));"
                        )
                    except Exception:
                        pass
                    if attempt == per_row_retry:
                        print(f"[DL][SKIP] Row#{idx} attempt={attempt} lỗi: {type(e).__name__}: {e}")
                    else:
                        time.sleep(0.2)

            # nếu row này fail thì qua row khác
            if not ok_this_row:
                continue
        
        # Kiểm tra xem có row mới không
        if not new_rows_found:
            no_new_rows_count += 1
            print(f"[DL] Không tìm thấy row mới ({no_new_rows_count}/{max_no_new_rows})")
            if no_new_rows_count >= max_no_new_rows:
                print("[DL] Đã thử nhiều lần nhưng không có row mới. Dừng lại.")
                break
        else:
            # Reset counter nếu tìm thấy row mới
            no_new_rows_count = 0

        if not progressed:
            print("[DL] Không tiến triển thêm (có thể hết row mới hoặc DOM thay đổi).")
            break


# ================== REQUESTS + API ==================

def fetch_page(session: requests.Session, headers: dict, page: int) -> dict:
    params = {
        "page": page,
        "get_newest_cv": "true",
        "source": SOURCE,
        "filter_cv_pro": "false",
        "filter_by": FILTER_BY,
    }
    r = session.get(LIST_ENDPOINT, headers=headers, params=params, timeout=30)

    if r.status_code in (401, 419):
        raise RuntimeError(f"AUTH_EXPIRED status={r.status_code}, body={r.text[:200]}")

    if r.status_code != 200:
        print(f"\n[ERROR] Status: {r.status_code}")
        print(f"Response: {r.text[:500]}")
        print(f"Headers sent: {headers}")
    r.raise_for_status()
    return r.json()

def scrape_all(max_pages: int, sleep_range=(0.6, 1.2)) -> pd.DataFrame:
    cookie_lines = load_cookie_lines(COOKIES_FILE)
    if not cookie_lines:
        raise RuntimeError("Không có cookie nào để dùng (kể cả sau khi mở Selenium).")

    all_rows = []
    session = requests.Session()
    cookie_index = 0
    total_cookies = len(cookie_lines)

    page = 1
    while page <= max_pages:
        cookie_line = cookie_lines[cookie_index % total_cookies]
        cookie_index += 1

        cookies = cookie_str_to_dict(cookie_line)
        session.cookies.clear()
        session.cookies.update(cookies)

        bearer = extract_bearer_from_cookie(cookies)
        if not bearer:
            print(f"[SKIP] Cookie #{cookie_index} thiếu bearer token (cookie__token.refresh).")
            if total_cookies == 1:
                print("[ACTION] Thử lấy cookie mới bằng Selenium vì bearer thiếu.")
                new_cookie_line = open_browser_and_get_cookie_line()
                if not new_cookie_line:
                    print("[FATAL] Không lấy được cookie mới. Dừng.")
                    break
                cookie_lines = [new_cookie_line]
                total_cookies = 1
                cookie_index = 0
                continue
            else:
                continue

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
            if "AUTH_EXPIRED" in msg:
                print(f"[AUTH] Token hết hạn trên page={page}: {msg}")
                print("[ACTION] Mở Selenium lấy cookie/token mới rồi retry page hiện tại.")
                new_cookie_line = open_browser_and_get_cookie_line()
                if not new_cookie_line:
                    print("[FATAL] Không lấy được cookie mới sau khi AUTH_EXPIRED. Dừng.")
                    break
                cookie_lines = [new_cookie_line]
                total_cookies = 1
                cookie_index = 0

                cookies = cookie_str_to_dict(new_cookie_line)
                session.cookies.clear()
                session.cookies.update(cookies)
                bearer = extract_bearer_from_cookie(cookies)
                if not bearer:
                    print("[FATAL] Cookie mới vẫn không có bearer. Dừng.")
                    break
                headers["Authorization"] = bearer
                j = fetch_page(session, headers, page)
            else:
                print(f"[ERROR] page={page}, cookie #{cookie_index}: {e}")
                break
        except Exception as e:
            print(f"[ERROR] page={page}, cookie #{cookie_index}: {e}")
            break

        data = safe_get(j, "cvs", "data", default=[])
        if not data:
            print(f"[STOP] page={page} không còn data (data rỗng).")
            break

        for item in data:
            all_rows.append(flatten_cv_item(item))

        cur = safe_get(j, "cvs", "current_page", default=page)
        last = safe_get(j, "cvs", "last_page", default=None)
        print(f"[OK] page={cur} rows={len(data)} total={len(all_rows)} last_page={last}")

        if last and page >= int(last):
            print("[DONE] Đã tới last_page từ API.")
            break

        page += 1
        time.sleep(random.uniform(*sleep_range))

    return pd.DataFrame(all_rows)

# ================== MAIN ==================

if __name__ == "__main__":
    max_pages = 1
    df = scrape_all(max_pages=max_pages)

    if not df.empty:
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"\n[SAVED] {OUTPUT_CSV} với {len(df)} dòng.")
    else:
        print("\n[WARN] Không có CV nào được lấy.")

    # chạy UI download sau cùng
    open_browser_and_download_cvs_ui(limit=15)
