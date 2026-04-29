import os
import shutil
import json
import glob

def cleanup():
    print("N-Place-DB Pro 배포 준비 (데이터 초기화) 시작...")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Clear Logs
    print("- 로그 파일 삭제 중...")
    for log_file in glob.glob(os.path.join(root_dir, "*.log")):
        try:
            os.remove(log_file)
            print(f"  Deleted: {os.path.basename(log_file)}")
        except Exception as e:
            print(f"  Error deleting {log_file}: {e}")

    # 2. Clear Database & License (CafeMonster Standard Path)
    print("- 데이터베이스 및 라이선스 삭제 중 (C:/CafeMonster)...")
    cafe_data_dir = "C:\\CafeMonster\\Crawler\\data"
    db_file = os.path.join(cafe_data_dir, "database.sqlite")
    license_file = os.path.join(cafe_data_dir, "license.dat")
    checkpoint_file = os.path.join(root_dir, "crawler_checkpoint.json")
    
    for f in [db_file, license_file, checkpoint_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"  Deleted: {os.path.basename(f)}")
            except Exception as e:
                print(f"  Error deleting {f}: {e}")

    # 3. Clear Browser Sessions
    print("- 브라우저 세션 정보 삭제 중...")
    session_dir = os.path.join(root_dir, "browser_session")
    if os.path.exists(session_dir):
        try:
            shutil.rmtree(session_dir)
            os.makedirs(session_dir)
            print("  Wiped: browser_session/")
        except Exception as e:
            print(f"  Error wiping sessions: {e}")

    # 4. Clear Exports & CSV Data
    print("- 내보내기 폴더 및 CSV 데이터 삭제 중...")
    exports_dir = os.path.join(root_dir, "exports")
    if os.path.exists(exports_dir):
        try:
            shutil.rmtree(exports_dir)
            os.makedirs(exports_dir)
            print("  Wiped: exports/")
        except Exception as e:
            print(f"  Error wiping exports: {e}")
            
    # Delete specific CSVs that might be in root
    csv_patterns = [
        "확장_*.csv",
        "raw_shops_*.csv",
        "enriched_*.csv",
        "final_*.csv",
        "crawl_audit.csv"
    ]
    for pattern in csv_patterns:
        for f in glob.glob(os.path.join(root_dir, pattern)):
            try:
                os.remove(f)
                print(f"  Deleted: {os.path.basename(f)}")
            except: pass

    # 5. Reset Templates (Personal Credentials)
    print("- 템플릿 및 계정 정보 초기화 중...")
    tpl_path = os.path.join(root_dir, "admin_dashboard", "templates.json")
    if os.path.exists(tpl_path):
        default_tpl = {
            "tpl_A": {
                "subject": "[제안] 비즈니스 협업 제안드립니다.",
                "body": "안녕하세요 {상호명} 원장님,\n\n협업 제안 드립니다..."
            },
            "tpl_C": "안녕하세요 {상호명} 원장님, 메시지 드립니다!",
            "email_user": "",
            "email_pw": "",
            "insta_user": "",
            "insta_pw": ""
        }
        try:
            with open(tpl_path, "w", encoding="utf-8") as f:
                json.dump(default_tpl, f, ensure_ascii=False, indent=4)
            print("  Reset: templates.json")
        except Exception as e:
            print(f"  Error resetting templates: {e}")

    # 6. Clear Python Cache
    print("- 파이썬 캐시 정리 중...")
    for pycache in glob.glob(os.path.join(root_dir, "**/__pycache__"), recursive=True):
        try:
            shutil.rmtree(pycache)
        except: pass
    print("  Cleaned: __pycache__")
    
    # 7. Finalize Distribution Files
    print("- 배포 필수 파일 복사 중 (Launcher & Dependencies)...")
    
    # Check for Pro or Basic dist folders
    targets = [
        ("NPlace-DB", "NPlace-DB-실행.bat"),
        ("Place-DB-Pro", "Place-DB-Pro-실행.bat"),
        ("Place-DB-Basic", "Place-DB-Basic-실행.bat")
    ]
    
    for folder_name, launcher_target in targets:
        dist_final_dir = os.path.join(root_dir, "dist", folder_name)
        if os.path.exists(dist_final_dir):
            try:
                # Copy Launcher & README
                # Determine which local launcher to copy
                launcher_src = "Place-DB-Pro-실행.bat" if "Pro" in folder_name else "Place-DB-Basic-실행.bat"
                if not os.path.exists(os.path.join(root_dir, launcher_src)):
                    launcher_src = "Place-DB-Pro-실행.bat" # Fallback if only one exists locally
                
                shutil.copy2(os.path.join(root_dir, launcher_src), 
                             os.path.join(dist_final_dir, launcher_target))
                shutil.copy2(os.path.join(root_dir, "README_USER.md"), 
                             os.path.join(dist_final_dir, "사용방법_필독.md"))
                
                # Copy Dependencies folder
                dep_target = os.path.join(dist_final_dir, "dependencies")
                if os.path.exists(dep_target): shutil.rmtree(dep_target)
                shutil.copytree(os.path.join(root_dir, "dependencies"), dep_target)
                
                print(f"  Copied Launcher & Dependencies to: {dist_final_dir}")
            except Exception as e:
                print(f"  [{folder_name}] Error finalizing dist files: {e}")
        else:
            print(f"  [{folder_name}] Dist directory not found. Skipping.")

    print("\n✅ 배포 준비 완료! 이제 'build_exe.py' 실행 후 'prepare_dist.py'를 다시 실행하여 마무리하세요.")

if __name__ == "__main__":
    cleanup()
