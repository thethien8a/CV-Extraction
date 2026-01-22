import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]

# Cấu hình lọc CV
SOURCE = "1"           # 1 = TopCV, nếu sau này muốn tất cả nguồn thì để "" hoặc None
FILTER_BY = "all"      # hoặc "not-viewed" 

# API endpoints
API_BASE = "https://tuyendung-api.topcv.vn"
LIST_ENDPOINT = f"{API_BASE}/api/v1/cv-management/cvs"
LOGIN_URL = "https://tuyendung.topcv.vn/app/login"
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


CHROME_USER_DATA_DIR = str(BASE_DIR / "chrome_profile_topcv")
COOKIES_FILE = str(BASE_DIR / "cookies.txt")
OUTPUT_CSV = str(BASE_DIR / "topcv_cvs_api_list.csv")
DOWNLOAD_DIR = str(BASE_DIR / "downloads_cv_pdf_topcv")
KEEP_BROWSER_OPEN = True

# Postgres
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "topcv")
PG_USER = os.getenv("PG_USER", "topcv")
PG_PASSWORD = os.getenv("PG_PASSWORD", "topcv_pass")

# MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "topcv-cv-pdf")