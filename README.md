# topcv-analysis-lakehouse

## Stack
- Python scripts
- PostgreSQL for metadata
- MinIO for PDF storage

## Run services (PostgreSQL + MinIO)
```powershell
docker compose up -d
```

## Environment variables (default in config)
- `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`

## Run crawlers
```powershell
python scripts/crawl/crawl_metadata/crawl.py
python scripts/crawl/crawl_cv/get_cv.py
```

