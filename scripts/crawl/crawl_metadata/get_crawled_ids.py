from scripts.utils.db import get_conn
from dotenv import load_dotenv

load_dotenv()


def get_crawled_ids():
    try:
        conn = get_conn()

        cursor = conn.cursor()

        cursor.execute("SELECT cv_id FROM cv_metadata")

        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        
        crawled_ids = [row[0] for row in rows]

        return crawled_ids
    except Exception as e:
        print(f"Error getting crawled IDs: {e}")
        return []
        
