import sqlite3
db_path = r'C:\CafeMonster\NPlace-DB\data\database.sqlite'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("UPDATE shops SET instagram_handle = ? WHERE name = ?", 
            ('https://www.instagram.com/dalnala08/', '✨ [대표님 테스트 계정]'))
conn.commit()
conn.close()
print('SUCCESS: Updated test account to full URL')
