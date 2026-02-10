import json
import os
import re
from typing import Any
import random   
from google import genai
from google.genai import types
from scripts.configs.config import MODEL_NAME, CV_INFO_JSON_SCHEMA
import asyncio

def extract_cv(minio_client, bucket_name, cv_id, candidate_id):
    object_key = f"cvs/{cv_id}/cvid_{cv_id}_canid_{candidate_id}.pdf"
    response = minio_client.get_object(bucket_name, object_key)
    pdf_bytes = response.read()
    response.close()
    response.release_conn()
    return pdf_bytes


def _get_genai_api_key() -> str:
    """Lấy API key từ env. Ưu tiên GOOGLE_API_KEY/GEMINI_API_KEY."""
    try:
        api_keys = os.getenv("LIST_API_KEY").split(",")
    except Exception as e:
        print(f"[ERROR] Failed to get API key: {e}")
        return ""
    
    api_key = random.choice(api_keys)
    
    return api_key


def _parse_json_text(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _remove_empty_values(data: Any) -> Any:
    if isinstance(data, dict):
        cleaned = {
            key: _remove_empty_values(value)
            for key, value in data.items()
            if value not in (None, "", [], {})
        }
        return {k: v for k, v in cleaned.items() if v not in (None, "", [], {})}

    if isinstance(data, list):
        cleaned_items = [_remove_empty_values(item) for item in data]
        return [item for item in cleaned_items if item not in (None, "", [], {})]

    return data

async def _process_one_cv(semaphore: asyncio.Semaphore, minio_client, bucket_name, cv_id, candidate_id):
    print(f"[INFO] Extracting CV {cv_id} for candidate {candidate_id}")
    
    pdf_bytes = extract_cv(minio_client, bucket_name, cv_id, candidate_id)
    print(f"[INFO] Got PDF bytes for CV {cv_id} for candidate {candidate_id}")
    
    async with semaphore:
        cv_info = await extract_cv_info(pdf_bytes)
    
    print(f"[INFO] Extracted CV info for cv_id={cv_id} and candidate_id={candidate_id}")
    return cv_id, candidate_id, cv_info

async def extract_cv_info(pdf_bytes: bytes, model_name: str = MODEL_NAME) -> dict[str, Any]:
    api_key = _get_genai_api_key()
    if not api_key:
        raise ValueError(
            "Không tìm thấy API key. Hãy set GOOGLE_API_KEY hoặc GEMINI_API_KEY (hoặc LIST_API_KEY)."
        )

    client = genai.Client(api_key=api_key)

    prompt = """
        Bạn là AI chuyên trích xuất CV. Hãy đọc file PDF CV (có thể tiếng Việt hoặc tiếng Anh)
        và trả về DUY NHẤT JSON object theo cấu trúc sau (nếu thiếu dữ liệu thì bỏ qua key đó):
        - goal_description
        - date_of_birth
        - contact_platforms: {facebook, linkedin}
        - address
        - education: [{name, institution, study_time: {start, end}}]
        - activities: [{name, organization, time, description}]
        - skills
        - certifications
        - prizes
        - languages
        - projects: [{name, time, description}]
        - references: [{name, role}]

        Quy tắc:
        1) Chỉ trả về JSON hợp lệ, không markdown, không giải thích.
        2) Key nào không có dữ liệu thì KHÔNG trả về.
        3) Không bịa thông tin.
    """

    response = await client.aio.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_json_schema=CV_INFO_JSON_SCHEMA,
        ),
    )

    if isinstance(response.parsed, dict):
        parsed_data = response.parsed
    else:
        parsed_data = _parse_json_text(response.text or "")

    cleaned_data = _remove_empty_values(parsed_data)
    
    return cleaned_data if isinstance(cleaned_data, dict) else {}