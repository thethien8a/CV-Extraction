import os
import time
import tempfile

import requests
from dotenv import load_dotenv

from scripts.utils.db import fetch_pending_cvs, get_conn, init_db, mark_download_status
from scripts.utils.minio_storage import ensure_bucket, get_minio_client

load_dotenv()


def download_to_temp(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, stream=True, timeout=60)
    response.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(tmp.name, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return tmp.name


def upload_to_minio(client, bucket, file_path, object_key):
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        client.put_object(
            bucket,
            object_key,
            f,
            size,
            content_type="application/pdf",
        )

def main():
    conn = get_conn()
    init_db(conn)
    client = get_minio_client()
    bucket = ensure_bucket(client)

    rows = fetch_pending_cvs(conn, limit=2000)
    print(f"[INFO] Found {len(rows)} pending CVs.")

    success_count = 0
    fail_count = 0

    for index, (cv_id, candidate_id, cv_url) in enumerate(rows, start=1):
        if not cv_url:
            print(f"[SKIP] cv_id={cv_id} không có cv_url.")
            continue

        filename = f"cvid_{cv_id}_canid_{candidate_id}.pdf"
        object_key = f"cvs/{cv_id}/{filename}"

        print(f"[DOWNLOADING] {index}/{len(rows)} cv_id={cv_id} filename={filename}")
        temp_path = None
        try:
            temp_path = download_to_temp(cv_url)
            upload_to_minio(client, bucket, temp_path, object_key)
            mark_download_status(
                conn,
                cv_id=cv_id,
                status="done"
            )
            success_count += 1
            print(f"[OK] cv_id={cv_id} uploaded={bucket}/{object_key}")
            time.sleep(1)
        except Exception as e:
            mark_download_status(
                conn,
                cv_id=cv_id,
                status="failed"
            )
            fail_count += 1
            print(f"[ERROR] cv_id={cv_id} url={cv_url} error={e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    conn.close()
    print(f"\n[DONE] success={success_count} failed={fail_count} total={len(rows)}")

if __name__ == "__main__":
    main()
