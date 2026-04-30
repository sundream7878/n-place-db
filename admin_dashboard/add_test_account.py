import sqlite3
import os
import sys

db_path = r'C:\CafeMonster\NPlace-DB\data\database.sqlite'
if not os.path.exists(db_path):
    print(f"ERROR: DB file not found at {db_path}")
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check table structure to match exactly
    cur.execute("PRAGMA table_info(shops)")
    cols = [col[1] for col in cur.fetchall()]
    print(f"Found columns: {cols}")
    
    # Insert test data (dalnala08)
    # We use a try-except to handle potential column mismatches
    try:
        cur.execute("INSERT INTO shops (name, instagram_handle, address, phone, email) VALUES (?, ?, ?, ?, ?)", 
                    ('✨ [대표님 테스트 계정]', 'dalnala08', '서울 테스트 센터', '010-0000-0000', 'test@test.com'))
        conn.commit()
        print("SUCCESS: Added test account 'dalnala08' to shops table.")
    except Exception as e:
        print(f"Insertion failed: {e}")
        # Try a more basic insert if columns are different
        if 'name' in cols:
            cur.execute("INSERT INTO shops (name) VALUES (?)", ('✨ [대표님 테스트 계정]',))
            # Find which column is for instagram
            for c in cols:
                if 'insta' in c.lower() or 'handle' in c.lower():
                    cur.execute(f"UPDATE shops SET {c} = ? WHERE name = ?", ('dalnala08', '✨ [대표님 테스트 계정]'))
            conn.commit()
            print("SUCCESS: Added test account using fallback method.")
            
    conn.close()
except Exception as e:
    print(f"Database error: {e}")
