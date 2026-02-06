from crawler.db_handler import DBHandler
import config

db = DBHandler()
if db.db_fs:
    docs = db.db_fs.collection(config.FIREBASE_COLLECTION).stream()
    count = 0
    for doc in docs:
        addr = doc.to_dict().get('address', '')
        if '전라남도' in addr or '전남' in addr:
            print(f"Match: {addr}")
            count += 1
        if count > 20: break
    print(f"Total checked and found: {count}")
else:
    print("DB fail")
