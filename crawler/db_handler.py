import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import config
from typing import List, Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)

class DBHandler:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBHandler, cls).__new__(cls)
            cls._instance.db_fs = None
            cls._instance.init_firebase()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def init_firebase(self):
        try:
            if not firebase_admin._apps:
                # Handle different types of service account info (dict or path)
                if isinstance(config.FIREBASE_SERVICE_ACCOUNT, dict):
                    cred = credentials.Certificate(config.FIREBASE_SERVICE_ACCOUNT)
                elif isinstance(config.FIREBASE_SERVICE_ACCOUNT, str) and os.path.exists(config.FIREBASE_SERVICE_ACCOUNT):
                    cred = credentials.Certificate(config.FIREBASE_SERVICE_ACCOUNT)
                else:
                    logger.warning("Firebase service account not configured correctly.")
                    return
                
                firebase_admin.initialize_app(cred)
            
            self.db_fs = firestore.client()
            logger.info("Firebase Firestore initialized successfully.")
        except Exception as e:
            logger.error(f"Firebase Init Error: {e}")
            self.db_fs = None

    def insert_shop(self, data: Dict) -> bool:
        if not self.db_fs: return False
        try:
            doc_id = data.get('source_link') or data.get('detail_url')
            if not doc_id: return False
            
            # Clean document ID for Firestore
            safe_id = doc_id.replace("/", "_").replace(".", "_")
            
            self.db_fs.collection(config.FIREBASE_COLLECTION).document(safe_id).set(data, merge=True)
            return True
        except Exception as e:
            logger.error(f"Firestore Insert Error: {e}")
            return False

    def batch_insert_shops(self, shops_list: List[Dict]) -> int:
        if not self.db_fs or not shops_list: return 0
        try:
            batch = self.db_fs.batch()
            count = 0
            for shop in shops_list:
                doc_id = shop.get('source_link') or shop.get('detail_url')
                if not doc_id: continue
                
                safe_id = doc_id.replace("/", "_").replace(".", "_")
                doc_ref = self.db_fs.collection(config.FIREBASE_COLLECTION).document(safe_id)
                batch.set(doc_ref, shop, merge=True)
                count += 1
                
                if count % 400 == 0: # Firestore batch limit is 500
                    batch.commit()
                    batch = self.db_fs.batch()
            
            batch.commit()
            return count
        except Exception as e:
            logger.error(f"Firestore Batch Error: {e}")
            return 0

    def get_doc_count(self, region: Optional[str] = None) -> int:
        if not self.db_fs: return 0
        try:
            query = self.db_fs.collection(config.FIREBASE_COLLECTION)
            if region:
                # Simple prefix search for region in address
                # Firestore doesn't support 'contains' well without specialized indexing, 
                # but 'address >= region' and 'address < region + \uf8ff' works for prefix.
                # However, for the dashboard stats, we usually use a simpler approach if possible.
                # Here we just fetch count of docs where region is in address (approximate)
                docs = query.where("address", ">=", region).where("address", "<", region + "\uf8ff").get()
                return len(docs)
            else:
                # Count aggregate is faster in newer firebase-admin but let's be safe
                docs = query.list_documents()
                # list_documents returns an iterator, we can't get len() directly easily without count()
                return len(list(docs))
        except Exception as e:
            logger.error(f"Firestore Count Error: {e}")
            return 0

    def fetch_existing_urls(self) -> List[str]:
        if not self.db_fs: return []
        try:
            docs = self.db_fs.collection(config.FIREBASE_COLLECTION).select(['source_link']).stream()
            return [doc.to_dict().get('source_link') for doc in docs if doc.to_dict().get('source_link')]
        except Exception as e:
            logger.error(f"Firestore Fetch URLs Error: {e}")
            return []
