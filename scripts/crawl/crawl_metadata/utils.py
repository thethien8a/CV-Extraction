import re
from urllib.parse import unquote

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
        "candidate_id": item.get("user_id"),
        "full_name": item.get("fullname") or item.get("full_name"),
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
        "cv_url": item.get("download_url"),
        "source": item.get("source"),
        "source_str": item.get("source_str"),
        "CV_Source":  "TopCV",
    }
