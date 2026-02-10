from psycopg2.extras import Json, execute_values


def load_data_to_db(conn, data, table_name):
    return load_data_to_db_bulk(conn, [(data["cv_id"], data["data"])], table_name)


def load_data_to_db_bulk(conn, rows, table_name):
    if not rows:
        return True

    with conn.cursor() as cur:
        cur.execute(
            f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    cv_id TEXT PRIMARY KEY,
                    data JSONB
                );
            """
        )
    
        prepared_rows = [(cv_id, Json(cv_data)) for cv_id, cv_data in rows]
        execute_values(
            cur,
            f"""
                INSERT INTO {table_name} (cv_id, data) VALUES (%s, %s)
                ON CONFLICT (cv_id) DO UPDATE SET data = EXCLUDED.data;
            """,
            prepared_rows,
            template="(%s, %s)",
        )

        conn.commit()

    return True


def mark_extraction_status(conn, cv_id, candidate_id):
    return mark_extraction_status_bulk(conn, [(cv_id, candidate_id)])


def mark_extraction_status_bulk(conn, rows):
    if not rows:
        return True

    with conn.cursor() as cur:
        execute_values(
            cur,
            f"""
                UPDATE cv_metadata AS m
                SET has_extracted = TRUE, extracted_at = NOW()
                FROM (VALUES %s) AS v(cv_id, candidate_id)
                WHERE m.cv_id = v.cv_id AND m.candidate_id = v.candidate_id;
            """,
            rows,
            template="(%s, %s)",
        )
        conn.commit()

    return True