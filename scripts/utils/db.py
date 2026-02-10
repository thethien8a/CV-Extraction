import psycopg2
from psycopg2.extras import execute_values

from scripts.configs.config import (
    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
)


def get_conn():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )


def init_db(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cv_metadata (
                cv_id TEXT PRIMARY KEY,
                candidate_id TEXT,
                full_name TEXT,
                phone TEXT,
                email TEXT,
                campaign_id TEXT,
                campaign_title TEXT,
                job_id TEXT,
                applied_position TEXT,
                application_date TEXT,
                status_str TEXT,
                created_at_str TEXT,
                cv_last_update_time_str TEXT,
                cv_last_update_time TEXT,
                apply_id TEXT,
                apply_status TEXT,
                is_viewed BOOLEAN,
                cv_url TEXT,
                source TEXT,
                source_str TEXT,
                cv_status TEXT DEFAULT 'pending',
                first_fetched_at TIMESTAMPTZ DEFAULT NOW(),
                last_fetched_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            ALTER TABLE cv_metadata 
            ADD COLUMN IF NOT EXISTS first_fetched_at TIMESTAMPTZ DEFAULT NOW();
            """
        )
        cur.execute(
            """
            ALTER TABLE cv_metadata 
            ADD COLUMN IF NOT EXISTS last_fetched_at TIMESTAMPTZ DEFAULT NOW();
            """
        )
        cur.execute(
            """
            ALTER TABLE cv_metadata 
            ADD COLUMN IF NOT EXISTS has_extracted BOOLEAN DEFAULT FALSE;
            """
        )
        cur.execute(
            """
            ALTER TABLE cv_metadata 
            ADD COLUMN IF NOT EXISTS extracted_at TIMESTAMPTZ DEFAULT NULL;
            """
        )
    conn.commit()


def upsert_cv_rows(conn, rows):
    if not rows:
        return 0

    columns = [
        "cv_id",
        "candidate_id",
        "full_name",
        "phone",
        "email",
        "campaign_id",
        "campaign_title",
        "job_id",
        "applied_position",
        "application_date",
        "status_str",
        "created_at_str",
        "cv_last_update_time_str",
        "cv_last_update_time",
        "apply_id",
        "apply_status",
        "is_viewed",
        "cv_url",
        "source",
        "source_str"
    ]

    values = [
        [row.get(col) for col in columns]
        for row in rows
        if row.get("cv_id") is not None
    ]

    if not values:
        return 0

    insert_sql = f"""
        INSERT INTO cv_metadata ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (cv_id) DO UPDATE SET
            candidate_id = EXCLUDED.candidate_id,
            full_name = EXCLUDED.full_name,
            phone = EXCLUDED.phone,
            email = EXCLUDED.email,
            campaign_id = EXCLUDED.campaign_id,
            campaign_title = EXCLUDED.campaign_title,
            job_id = EXCLUDED.job_id,
            applied_position = EXCLUDED.applied_position,
            application_date = EXCLUDED.application_date,
            status_str = EXCLUDED.status_str,
            created_at_str = EXCLUDED.created_at_str,
            cv_last_update_time_str = EXCLUDED.cv_last_update_time_str,
            cv_last_update_time = EXCLUDED.cv_last_update_time,
            apply_id = EXCLUDED.apply_id,
            apply_status = EXCLUDED.apply_status,
            is_viewed = EXCLUDED.is_viewed,
            cv_url = EXCLUDED.cv_url,
            source = EXCLUDED.source,
            source_str = EXCLUDED.source_str,
            last_fetched_at = NOW();
    """

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values)
    conn.commit()
    return len(values)

def mark_download_status(conn, cv_id, status):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE cv_metadata
            SET cv_status = %s
            WHERE cv_id = %s;
            """,
            (status, cv_id),
        )
        conn.commit()

def fetch_pending_cvs(conn, limit=100):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cv_id, candidate_id, cv_url FROM cv_metadata
            WHERE cv_status = 'pending'
            ORDER BY created_at_str DESC
            LIMIT %s;
            """,
            (limit,),
        )
        return cur.fetchall()