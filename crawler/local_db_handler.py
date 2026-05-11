import sqlite3
import os
import contextlib
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class LocalDBHandler:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # [PRO] Determine base path: Executable dir if frozen, else project root
            import sys
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                # Relative to this file's parent's parent
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_path, "data", "database.sqlite")
        else:
            self.db_path = db_path
            
        self._ensure_data_dir()
        self.init_db()

    def _ensure_data_dir(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def get_connection(self):
        return sqlite3.connect(self.db_path, timeout=20)

    def init_db(self):
        """Initializes the SQLite database and creates the shops table."""
        with contextlib.closing(self.get_connection()) as conn:
            with conn:
                cursor = conn.cursor()
                # 1. Create shops table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS shops (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        phone TEXT,
                        detail_url TEXT UNIQUE,
                        address TEXT,
                        latitude REAL,
                        longitude REAL,
                        email TEXT,
                        instagram_handle TEXT,
                        naver_blog_id TEXT,
                        talk_url TEXT,
                        owner_name TEXT,
                        keyword TEXT,
                        last_result_email TEXT,
                        last_msg_email TEXT,
                        last_result_insta TEXT,
                        last_msg_insta TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # [NEW] Check and Add columns if they don't exist (for existing DBs)
                cursor.execute("PRAGMA table_info(shops)")
                existing_cols = [row[1] for row in cursor.fetchall()]
                new_cols = [
                    ("last_result_email", "TEXT"), ("last_msg_email", "TEXT"),
                    ("last_result_insta", "TEXT"), ("last_msg_insta", "TEXT")
                ]
                for col_name, col_type in new_cols:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE shops ADD COLUMN {col_name} {col_type}")
                
                # 2. Explicit index for faster lookup on detail_url (Rule 3.1)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_detail_url ON shops (detail_url)")
                conn.commit()
                
        logger.info(f"Local SQLite DB initialized at {self.db_path}")

    def update_send_status(self, shop_id: int, track: str, result: str, msg: str) -> bool:
        """Updates the sending status and message for a specific shop using its ID."""
        col_res = "last_result_email" if track == 'email' else "last_result_insta"
        col_msg = "last_msg_email" if track == 'email' else "last_msg_insta"
        try:
            with contextlib.closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute(f"UPDATE shops SET {col_res} = ?, {col_msg} = ? WHERE id = ?", 
                                 (result, msg, shop_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating send status: {e}")
            return False

    def insert_shop(self, data: Dict) -> bool:
        """Inserts a single shop record, avoiding duplicates based on detail_url."""
        try:
            with contextlib.closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT OR IGNORE INTO shops (
                        name, phone, detail_url, address, latitude, longitude,
                        email, instagram_handle, naver_blog_id, talk_url, owner_name, keyword
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("name"),
                    data.get("phone"),
                    data.get("detail_url"),
                    data.get("address"),
                    data.get("latitude", 0.0),
                    data.get("longitude", 0.0),
                    data.get("email"),
                    data.get("instagram_handle"),
                    data.get("naver_blog_id"),
                    data.get("talk_url"),
                    data.get("owner_name"),
                    data.get("keyword")
                ))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error saving shop to SQLite: {e}")
            return False

    def batch_insert_shops(self, data_list: List[Dict]) -> int:
        """Inserts multiple shop records efficiently using a single transaction."""
        if not data_list: return 0
        try:
            with contextlib.closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.cursor()
                    # Optimized batch insert using executemany (Rule 3.2)
                values = [
                    (
                        d.get("name"), d.get("phone"), d.get("detail_url"), d.get("address"),
                        d.get("latitude", 0.0), d.get("longitude", 0.0), d.get("email"),
                        d.get("instagram_handle"), d.get("naver_blog_id"), d.get("talk_url"),
                        d.get("owner_name"), d.get("keyword")
                    ) for d in data_list
                ]
                cursor.executemany("""
                    INSERT OR IGNORE INTO shops (
                        name, phone, detail_url, address, latitude, longitude,
                        email, instagram_handle, naver_blog_id, talk_url, owner_name, keyword
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, values)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Error in batch insert: {e}")
            return 0

    def exists_by_url(self, detail_url: str) -> bool:
        """Check if a shop already exists by its URL (Rule 3.3)."""
        try:
            with contextlib.closing(self.get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM shops WHERE detail_url = ? LIMIT 1", (detail_url,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking existence: {e}")
            return False

    def fetch_existing_urls(self) -> List[str]:
        """Fetches all existing detail_urls to prevent redundant crawling."""
        try:
            with contextlib.closing(self.get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT detail_url FROM shops")
                urls = [row[0] for row in cursor.fetchall()]
                return urls
        except Exception as e:
            logger.error(f"Error fetching URLs from SQLite: {e}")
            return []

    def get_all_shops(self) -> List[Dict]:
        """Fetches all shop records as a list of dictionaries."""
        try:
            with contextlib.closing(self.get_connection()) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM shops ORDER BY id DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching shops from SQLite: {e}")
            return []

    def reset_all_statuses(self) -> bool:
        """Clears all sending status columns in the database."""
        try:
            with contextlib.closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE shops SET last_result_email = NULL, last_msg_email = NULL, last_result_insta = NULL, last_msg_insta = NULL")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error resetting statuses: {e}")
            return False

    def get_count(self) -> int:
        """Returns the total number of records in the shops table."""
        try:
            with contextlib.closing(self.get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM shops")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting count: {e}")
            return 0
