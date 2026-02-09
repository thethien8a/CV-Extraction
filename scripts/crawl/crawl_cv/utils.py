import os
import tempfile
import requests


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