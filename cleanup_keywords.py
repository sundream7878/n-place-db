
import firebase_admin
from firebase_admin import credentials, firestore
import logging
import os
import json

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Cleanup")

# Config
try:
    import config
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import config

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(config.FIREBASE_SERVICE_ACCOUNT)
        firebase_admin.initialize_app(cred)
    return firestore.client()

def run_cleanup():
    db = init_firebase()
    collection_ref = db.collection(config.FIREBASE_COLLECTION)
    
    EXCLUDED_KEYWORDS = [
        "태닝", "타이", "마사지", "장애인", "왁싱", "풋샵", 
        "하노이", "아로마", "중국", "경락", "발", "약손", "시암"
    ]
    
    logger.info("🔍 Scanning for shops to delete...")
    logger.info(f"🚫 Keywords: {EXCLUDED_KEYWORDS}")
    
    docs = collection_ref.stream()
    deleted_count = 0
    
    batch = db.batch()
    batch_count = 0
    
    for doc in docs:
        data = doc.to_dict()
        name = data.get("name") or data.get("상호명") or ""
        
        # Check if name contains any excluded keyword
        if any(ex in name for ex in EXCLUDED_KEYWORDS):
            logger.info(f"🗑️ Deleting: {name}")
            batch.delete(doc.reference)
            batch_count += 1
            deleted_count += 1
            
        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            
    if batch_count > 0:
        batch.commit()
        
    logger.info(f"✅ Cleanup complete. Deleted {deleted_count} shops.")

if __name__ == "__main__":
    run_cleanup()
