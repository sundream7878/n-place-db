import pandas as pd
import sqlite3
import os
from datetime import datetime
import config

def export_to_xlsx(db_path: str = None, output_dir: str = "exports"):
    """
    Exports all data from the SQLite 'shops' table to an Excel file.
    Returns the path to the created file, or None if failed.
    """
    if db_path is None:
        db_path = config.LOCAL_DB_PATH
        
    if not os.path.exists(db_path):
        return None

    try:
        # Connect and read
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM shops", conn)
        conn.close()

        if df.empty:
            return None

        # Prepare output
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crawled_shops_{timestamp}.xlsx"
        file_path = os.path.join(output_dir, filename)

        # Drop internal columns if any
        if 'id' in df.columns:
            df = df.drop(columns=['id'])

        # Save to Excel
        # Using utf-8-sig isn't needed for Excel (openpyxl handles it), 
        # but we ensure column names are readable.
        df.columns = [
            "상호명", "전화번호", "상세URL", "주소", "위도", "경도", 
            "이메일", "인스타그램", "네이버블로그", "톡톡URL", "대표자명", "검색키워드", "수집일시"
        ]
        
        df.to_excel(file_path, index=False, engine='openpyxl')
        return os.path.abspath(file_path)

    except Exception as e:
        print(f"Excel Export Error: {e}")
        return None

def export_to_csv(db_path: str = None, output_dir: str = "exports"):
    """
    Exports all data to a CSV file with utf-8-sig encoding for Excel compatibility.
    """
    if db_path is None:
        db_path = config.LOCAL_DB_PATH
        
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM shops", conn)
        conn.close()

        if df.empty:
            return None

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crawled_shops_{timestamp}.csv"
        file_path = os.path.join(output_dir, filename)

        if 'id' in df.columns:
            df = df.drop(columns=['id'])

        df.columns = [
            "상호명", "전화번호", "상세URL", "주소", "위도", "경도", 
            "이메일", "인스타그램", "네이버블로그", "톡톡URL", "대표자명", "검색키워드", "수집일시"
        ]
        
        # This is the key part the user requested
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        return os.path.abspath(file_path)

    except Exception as e:
        print(f"CSV Export Error: {e}")
        return None

if __name__ == "__main__":
    path = export_to_xlsx()
    if path:
        print(f"Export successful: {path}")
    else:
        print("Export failed.")
