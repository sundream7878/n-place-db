import logging
from auth import AuthManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_key(key):
    import config
    db = AuthManager._get_db()
    if not db:
        print("Failed to connect to Firebase.")
        return

    print("\n--- All Collections in Firestore ---")
    try:
        cols = db.collections()
        for c in cols:
            print(f"- {c.id}")
    except Exception as e:
        print(f"Error listing collections: {e}")

    print("\n--- Available Keys in 'licenses' ---")
    docs_licenses = db.collection("licenses").stream()
    found_lic = False
    for d in docs_licenses:
        data = d.to_dict()
        s_key = data.get('serial_key') or d.id
        print(f"- {s_key} (Status: {data.get('status', 'N/A')})")
        found_lic = True
    if not found_lic: print("Collection 'licenses' is empty.")

    print("\n--- Available Keys in 'product_keys' ---")
    docs_pk = db.collection("product_keys").stream()
    found_pk = False
    for d in docs_pk:
        data = d.to_dict()
        s_key = data.get('serial_key') or d.id
        print(f"- {s_key} (Status: {data.get('status', 'N/A')})")
        found_pk = True
    if not found_pk: print("Collection 'product_keys' is empty.")

    print(f"\nSearching for {key} specifically...")
    # Try all likely collections
    for coll in ["licensese", "licenses", "product_keys"]:
        docs = db.collection(coll).where("serial_key", "==", key).limit(1).get()
        if not docs:
            # Try ID search for product_keys
            doc = db.collection(coll).document(key).get()
            if doc.exists:
                docs = [doc]
        
        if docs:
            doc = docs[0]
            data = doc.to_dict()
            print(f"✅ Found in '{coll}'!")
            print(f"--- Data for Key: {key} (DocID: {doc.id}) ---")
            for k, v in data.items():
                print(f"{k}: {v} ({type(v)})")
            print("---------------------------")
            return
    
    print(f"❌ Key {key} not found anywhere.")

if __name__ == "__main__":
    diagnose_key("NP-VYNB-6229")
