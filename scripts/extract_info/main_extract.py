import asyncio
from scripts.extract_info.get_cv import get_metadata_to_extract
from scripts.extract_info.extract_cv import _process_one_cv
from scripts.utils.db import get_conn
from scripts.utils.minio_storage import get_minio_client
from scripts.configs.config import MINIO_BUCKET, MAX_CONCURRENCY, BATCH_SIZE
from dotenv import load_dotenv
from scripts.extract_info.utils import _chunked
from scripts.extract_info.load import load_data_to_db_bulk, mark_extraction_status_bulk

load_dotenv()

async def main_extract():
    conn = get_conn()
    minio_client = get_minio_client()
    bucket_name = MINIO_BUCKET
    
    metadata_to_extract = get_metadata_to_extract(conn)
    print(f"[INFO] Found {len(metadata_to_extract)} metadata to extract")
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    total_batches = (len(metadata_to_extract) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_idx, metadata_chunk in enumerate(_chunked(metadata_to_extract, BATCH_SIZE), start=1):
        print(
            f"[INFO] Processing batch {batch_idx}/{total_batches} "
            f"(size={len(metadata_chunk)})"
        )

        tasks = [
            _process_one_cv(semaphore, minio_client, bucket_name, cv_id, candidate_id)
            for cv_id, candidate_id in metadata_chunk
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cv_rows = []
        status_rows = []
        failed_count = 0

        for result in results:
            if isinstance(result, Exception):
                failed_count += 1
                print(f"[ERROR] Failed to extract CV: {result}")
                continue

            cv_id, candidate_id, cv_info = result
            cv_rows.append((cv_id, cv_info))
            status_rows.append((cv_id, candidate_id))

        if cv_rows:
            load_data_to_db_bulk(conn, cv_rows, "cv_details")
        if status_rows:
            mark_extraction_status_bulk(conn, status_rows)

        print(
            f"[INFO] Batch {batch_idx} done: success={len(status_rows)}, "
            f"failed={failed_count}"
        )
        print("-" * 30)

    conn.close()
    print(f"[INFO] Closed connection to database")


if __name__ == "__main__":
    asyncio.run(main_extract())
