import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]

# Cấu hình lọc CV
SOURCE = "1"           # 1 = TopCV, nếu sau này muốn tất cả nguồn thì để "" hoặc None
FILTER_BY = "all"      # hoặc "not-viewed" 

# API endpoints
CAMPAIGN_ID = 2350596

API_BASE = "https://tuyendung-api.topcv.vn"
LIST_ENDPOINT = f"{API_BASE}/api/v1/cv-management/cvs"
LOGIN_URL = "https://tuyendung.topcv.vn/app/login"
CV_PAGE_URL = (
    "https://tuyendung.topcv.vn/app/cvs-management"
    "?get_newest_cv=true"
    f"&recruitment_campaign_id={CAMPAIGN_ID}"
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

# CV extraction
MAX_CONCURRENCY = 1
BATCH_SIZE = 5
MAX_RETRIES = 3

# Gemini
MODEL_NAME = "gemini-2.0-flash-lite"

CV_INFO_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "goal_description": {"type": "string"},
        "date_of_birth": {"type": "string"},
        "contact_platforms": {
            "type": "object",
            "properties": {
                "facebook": {"type": "string"},
                "linkedin": {"type": "string"},
            },
        },
        "address": {"type": "string"},
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "institution": {"type": "string"},
                    "study_time": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string"},
                            "end": {"type": "string"},
                        },
                    },
                },
            },
        },
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "organization": {"type": "string"},
                    "time": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "skills": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
        "prizes": {"type": "array", "items": {"type": "string"}},
        "languages": {"type": "array", "items": {"type": "string"}},
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "time": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
        },
    },
}
