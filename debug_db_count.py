
import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawler import db_handler

def test_count():
    try:
        print("Initializing DBHandler...")
        db = db_handler.DBHandler()
        
        print("Testing Total Count...")
        total = db.get_doc_count()
        print(f"Total Count Result: {total}")
        
        print("Testing Province Count (전남)...")
        prov = db.get_doc_count("전남")
        print(f"Province Count Result: {prov}")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_count()
