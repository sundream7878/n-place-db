import firebase_admin
from firebase_admin import credentials, firestore
import config
from collections import Counter
import pprint

def analyze_counts():
    print("📊 Analyzing Shop Distribution by District...")
    
    # Initialize Firebase
    if not firebase_admin._apps:
        cred = credentials.Certificate(config.FIREBASE_SERVICE_ACCOUNT)
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    docs = db.collection(config.FIREBASE_COLLECTION).stream()
    
    district_counts = Counter()
    total = 0
    
    for doc in docs:
        total += 1
        data = doc.to_dict()
        addr = data.get("address", "")
        
        # Parse 'Seoul [District]'
        parts = addr.split()
        if len(parts) >= 2 and parts[0].startswith("서울"):
            district = parts[1]
            district_counts[district] += 1
            
    print(f"\n✅ Total Shops: {total}")
    print("\n📍 District Breakdown:")
    
    # Sort by count descending
    sorted_districts = district_counts.most_common()
    for dist, count in sorted_districts:
        print(f"{dist}: {count}")

    # Check against expected list
    import json
    import os
    regions_file = os.path.join(os.getcwd(), 'crawler', 'regions.json')
    if os.path.exists(regions_file):
        with open(regions_file, 'r', encoding='utf-8') as f:
            city_map = json.load(f)
            seoul_dongs = city_map.get("서울", {})
            expected_districts = set(seoul_dongs.keys())
            
            found_districts = set(district_counts.keys())
            missing = expected_districts - found_districts
            
            print(f"\n⚠️ Completely Missing Districts: {missing}")

if __name__ == "__main__":
    analyze_counts()
