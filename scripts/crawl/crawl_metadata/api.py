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
    return r.json()
