import logging
import os
import requests
from supabase import create_client, Client
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict, List, Optional

# 🛡️ gRPC Stability Fix for Streamlit/Threaded envs
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
os.environ["GRPC_POLL_STRATEGY"] = "poll"

try:
    from .. import config
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import config

logger = logging.getLogger(__name__)

class DBHandler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBHandler, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Allows resetting the Singleton instance if communication failure is detected."""
        cls._instance = None
        logger.warning("DBHandler instance has been reset.")

    def __init__(self):
        if self.initialized: return
        self.db_fs = None # Firestore Client
        self.init_firebase()
        self.initialized = True
        
    def init_firebase(self):
        """Initialize Firebase Admin SDK."""
        try:
            if not firebase_admin._apps:
                # config.FIREBASE_SERVICE_ACCOUNT can be a dict (from secrets) or a string (file path)
                cred_info = config.FIREBASE_SERVICE_ACCOUNT
                
                # If it's a dict, use it directly. If it's a string, treat it as a path.
                if isinstance(cred_info, str):
                    if not os.path.exists(cred_info):
                        logger.warning(f"Firebase key file not found at {cred_info}. Skipping initialization.")
                        return
                    cred = credentials.Certificate(cred_info)
                else:
                    cred = credentials.Certificate(cred_info)
                
                firebase_admin.initialize_app(cred)
            self.db_fs = firestore.client()
            self.init_error = None
            logger.info("Firebase Firestore initialized successfully")
        except Exception as e:
            logger.error(f"Firebase initialization failed: {e}")
            self.db_fs = None
            self.init_error = str(e)
            
    def insert_shop(self, data: Dict) -> bool:
        """Insert or update shop in Firebase Firestore."""
        if not self.db_fs:
            return False
        try:
            doc_id = self._generate_doc_id(data)
            if not doc_id: return False
            
            self.db_fs.collection(config.FIREBASE_COLLECTION).document(doc_id).set(data, merge=True)
            logger.info(f"Successfully saved shop to Firebase: {data.get('name') or data.get('상호명')}")
            return True
        except Exception as e:
            logger.error(f"Error saving shop to Firebase: {e}")
            return False

    def _generate_doc_id(self, data: Dict) -> Optional[str]:
        """Generate a sanitized document ID from shop data."""
        key = data.get("detail_url") or data.get("source_link") or data.get("blog_url") or data.get("플레이스링크")
        if not key: return None
        return str(key).replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_")

    def batch_insert_shops(self, data_list: List[Dict]) -> int:
        """
        Uploads multiple shops to Firebase using WriteBatch for efficiency.
        Automatically handles chunking (500 limit).
        """
        if not self.db_fs or not data_list:
            return 0
            
        total_uploaded = 0
        batch_size = 500
        
        for i in range(0, len(data_list), batch_size):
            chunk = data_list[i : i + batch_size]
            batch = self.db_fs.batch()
            
            chunk_count = 0
            for item in chunk:
                doc_id = self._generate_doc_id(item)
                if not doc_id: continue
                
                doc_ref = self.db_fs.collection(config.FIREBASE_COLLECTION).document(doc_id)
                batch.set(doc_ref, item, merge=True)
                chunk_count += 1
            
            try:
                batch.commit()
                total_uploaded += chunk_count
                logger.info(f"🚀 Batch committed: {chunk_count} shops. (Total: {total_uploaded})")
            except Exception as e:
                logger.error(f"❌ Batch commit failed: {e}")
                
        return total_uploaded

    def insert_shop_fs(self, data: Dict) -> bool:
        """Alias for backward compatibility."""
        return self.insert_shop(data)

    def insert_lead(self, data: Dict) -> bool:
        """Alias for lead insertion."""
        return self.insert_shop(data)

    def insert_lead_fs(self, data: Dict) -> bool:
        """Alias for lead insertion."""
        return self.insert_shop(data)

    def fetch_existing_urls(self) -> List[str]:
        """Fetch existing shop URLs from Firebase."""
        if not self.db_fs:
                return []
        try:
            docs = self.db_fs.collection(config.FIREBASE_COLLECTION).stream()
            urls = []
            for doc in docs:
                d = doc.to_dict()
                url = d.get("detail_url") or d.get("source_link") or d.get("blog_url") or d.get("플레이스링크")
                if url: urls.append(url)
            return urls
        except Exception as e:
            logger.error(f"Error fetching URLs: {e}")
            return []

    def save_session(self, platform: str, session_data: str) -> bool:
        """Save browser session data to Firebase."""
        if not self.db_fs:
            return False
        try:
            data = {
                "platform": platform,
                "session_json": session_data,
                "updated_at": firestore.SERVER_TIMESTAMP
            }
            self.db_fs.collection(config.FIREBASE_SESSION_COLLECTION).document(platform).set(data)
            logger.info(f"Saved session for {platform} to Firebase")
            return True
        except Exception as e:
            logger.error(f"Error saving session to Firebase: {e}")
            return False

    def save_session_fs(self, platform: str, session_data: str) -> bool:
        return self.save_session(platform, session_data)

    def load_session(self, platform: str) -> Optional[str]:
        """Load browser session data from Firebase."""
        if not self.db_fs:
            return None
        try:
            doc = self.db_fs.collection(config.FIREBASE_SESSION_COLLECTION).document(platform).get()
            if doc.exists:
                return doc.to_dict().get('session_json')
            return None
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return None

    def get_doc_count(self, province: str = None) -> int:
        """
        Get real-time document count using Aggregation Query (Cost-Effective).
        If province is provided, filters by address prefix.
        """
        if not self.db_fs: return 0
        try:
            coll = self.db_fs.collection(config.FIREBASE_COLLECTION)
            
            if province and province != "전체":
                from google.cloud.firestore_v1.base_query import FieldFilter
                # Prefix query for address using FieldFilter to avoid warnings
                query = coll.where(filter=FieldFilter("address", ">=", province)) \
                            .where(filter=FieldFilter("address", "<=", province + "\uf8ff"))
                count_query = query.count()
            else:
                count_query = coll.count()
            
            results = count_query.get()
            # result[0][0].value is standard for some versions, but let's be robust
            return int(results[0][0].value)
        except Exception as e:
            # Fallback for old SDK versions or index errors
            # logger.warning(f"Aggregation failed ({e}). usage fallback stream count...")
            return 0
