import requests
from scripts.configs.config import SOURCE, FILTER_BY, LIST_ENDPOINT, CAMPAIGN_ID

def fetch_page(session: requests.Session, headers: dict, page: int) -> dict:
    params = {
        "page": page,
        "get_newest_cv": "true",
        "source": SOURCE,
        "filter_cv_pro": "false",
        "filter_by": FILTER_BY,
        "recruitment_campaign_id": CAMPAIGN_ID,
    }
    r = session.get(LIST_ENDPOINT, headers=headers, params=params, timeout=30)
    
    # Thêm vào api.py để xem lỗi
    if r.status_code != 200:
        print(f"Response body: {r.text}") 
        raise RuntimeError(f"API error: {r.status_code}")
    
    return r.json()
