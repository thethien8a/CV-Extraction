import os
import time
from pathlib import Path

import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scripts.configs.config import (
    CHROME_USER_DATA_DIR, LOGIN_URL, CV_PAGE_URL, COOKIES_FILE, HEADERS, LIST_ENDPOINT
)
from scripts.utils.get_chrome_version import get_chrome_major_version
from .utils import cookie_str_to_dict

def _force_quit_suppress_errors(self):
    try:
        self.quit()
    except OSError:
        pass
uc.Chrome.__del__ = _force_quit_suppress_errors

def is_cookie_expired(cookie_line: str) -> bool:
    cookies = cookie_str_to_dict(cookie_line)
    exp_ms = cookies.get("cookie__token_expiration.refresh")
    if not exp_ms:
        return True
    
    try:
        exp_timestamp = int(exp_ms)
        current_timestamp = int(time.time() * 1000)
        return current_timestamp > exp_timestamp
    except ValueError:
        return True

def build_cookie_header_from_driver(driver) -> str:
    cookies = driver.get_cookies()
    return "; ".join([f"{c['name']}={c.get('value', '')}" for c in cookies])

def wait_for_auth_cookie(driver, timeout=300) -> bool:
    """
    Chờ đến khi xuất hiện cookie__token.refresh (tối đa timeout giây).
    Trong lúc này bạn cứ login, nhập OTP, v.v. bình thường.
    """
    end = time.time() + timeout
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

def login(driver):
    """
    Hàm login tự động nếu có TOPCV_USERNAME / TOPCV_PASSWORD trong .env
    """
    email = os.getenv("TOPCV_USERNAME")
    password = os.getenv("TOPCV_PASSWORD")

    if email and password:
        print("[SELENIUM] Phát hiện credentials, đang thử tự động đăng nhập")
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

def open_browser_and_get_cookie_line() -> str | None:
    """
    Mở Chrome với profile riêng, cho bạn login,
    auto đợi có cookie__token.refresh, auto đóng popup,
    nhảy sang trang quản lý CV, rồi lấy cookie và lưu cookies.txt.
    """
    profile_path = Path(CHROME_USER_DATA_DIR)
    profile_path.mkdir(parents=True, exist_ok=True)

    opts = uc.ChromeOptions()
    opts.add_argument("--headless")
    opts.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--start-maximized")
    prefs = {"profile.default_content_setting_values.notifications": 2}
    opts.add_experimental_option("prefs", prefs)
    
    driver = uc.Chrome(options=opts, version_main=get_chrome_major_version())
    try:
        print(f"[SELENIUM] Mở trình duyệt tới: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        # Thử auto login nếu có credentials
        login(driver)

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
    end = time.time() + timeout
    while time.time() < end:
        if not list(Path(download_dir).glob("*.crdownload")):
            return True
        time.sleep(0.4)
    return False
