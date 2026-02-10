def get_metadata_to_extract(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cv_id, candidate_id FROM cv_metadata WHERE has_extracted = FALSE
            """
        )
        return cur.fetchall()