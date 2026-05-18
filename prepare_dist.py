import os
import shutil
import json
import glob
import config

def cleanup():
    v = config.CURRENT_VERSION
    print(f"N-Place-DB Pro (v{v}) 배포 준비 및 자동 ZIP 압축 시작...")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Clear Logs
    print("- 로그 파일 삭제 중...")
    for log_file in glob.glob(os.path.join(root_dir, "*.log")):
        try:
            os.remove(log_file)
            print(f"  Deleted: {os.path.basename(log_file)}")
        except Exception as e:
            print(f"  Error deleting {log_file}: {e}")

    # 2. Clear Database & License
    print("- 로컬 데이터베이스 삭제 중 (배포용 클린 버전)...")
    db_file = os.path.join(root_dir, "data", "database.sqlite")
    checkpoint_file = os.path.join(root_dir, "crawler_checkpoint.json")
    
    for f in [db_file, checkpoint_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"  Deleted: {os.path.basename(f)}")
            except Exception as e:
                print(f"  Error deleting {f}: {e}")

    # 3. Clear Browser Sessions
    print("- 브라우저 세션 정보 삭제 중...")
    session_dir = os.path.join(root_dir, "messenger", "browser_session")
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

    # 5. Reset Templates (Personal Credentials for Security)
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
    
    # 7. Package Compiled Folder in dist/
    dist_folder_name = f"NPlace-DB-v{v}"
    dist_final_dir = os.path.join(root_dir, "dist", dist_folder_name)
    
    if os.path.exists(dist_final_dir):
        try:
            print(f"- 배포 필수 파일 복사 및 생성 중 ({dist_folder_name})...")
            
            # [A] Create Dynamic Version-Correct Batch Launcher
            launcher_path = os.path.join(dist_final_dir, "NPlace-DB-실행.bat")
            launcher_content = f"""@echo off
setlocal
title NPlace-DB Launcher

echo ======================================================
echo   NPlace-DB 프로그램 시작 중...
echo ======================================================
echo.

:: 1. 필수 런타임 (Visual C++ Redistributable 2015-2022) 확인
echo [1/2] 필수 시스템 구성 요소 확인 중...
reg query "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64" /v "Installed" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 일부 시스템에서 Visual C++ 런타임이 필요할 수 있습니다.
    echo.
    echo [안내] 수동 설치 링크: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    echo (계속하려면 아무 키나 누르세요... 곧 프로그램이 실행됩니다.)
    timeout /t 3 >nul
) else (
    echo [OK] 시스템 구성 요소가 이미 설치되어 있습니다.
)

:: 2. 프로그램 실행
echo.
echo [2/2] 프로그램을 실행하는 중입니다...

if exist "NPlace-DB-v{v}.exe" (
    start "" "NPlace-DB-v{v}.exe"
) else (
    echo [오류] 실행 파일을 찾을 수 없습니다.
    echo 폴더 구성을 확인해 주세요.
    pause
    exit /b 1
)

echo ✅ 완료! 이 창은 3초 후 자동으로 닫힙니다.
timeout /t 3 >nul
exit
"""
            with open(launcher_path, "w", encoding="euc-kr") as lf:
                lf.write(launcher_content)
            print("  Created: NPlace-DB-실행.bat")

            # [B] Copy docs/ folder (clean documents)
            dist_docs_dir = os.path.join(dist_final_dir, "docs")
            if os.path.exists(dist_docs_dir):
                shutil.rmtree(dist_docs_dir)
            shutil.copytree(os.path.join(root_dir, "docs"), dist_docs_dir)
            print("  Copied: docs/ folder")

            # [C] Create Clean 사용방법_필독.md pointing to in-app guide
            readme_path = os.path.join(dist_final_dir, "사용방법_필독.md")
            readme_content = f"""# 사용방법 안내
프로그램 실행 후 메인 화면의 **[가이드]** 탭에 상세한 사용 방법과 노하우가 내장되어 있습니다.

1. **'NPlace-DB-실행.bat'**을 더블 클릭하여 실행합니다.
2. 상단 메뉴의 **[가이드]** 탭을 눌러 사용 설명 및 마케팅 꿀팁을 확인해 주세요!
"""
            with open(readme_path, "w", encoding="utf-8") as rf:
                rf.write(readme_content)
            print("  Created: 사용방법_필독.md")

            # [D] Copy dependencies folder
            dep_src = os.path.join(root_dir, "dependencies")
            dep_target = os.path.join(dist_final_dir, "dependencies")
            if os.path.exists(dep_src):
                if os.path.exists(dep_target):
                    shutil.rmtree(dep_target)
                shutil.copytree(dep_src, dep_target)
                print("  Copied: dependencies/ folder")
            
            # 8. [ZIP ARCHIVE] Automatically Compress to .zip (Monster standard!)
            print(f"- 배포 폴더 자동 압축 시작 (dist/{dist_folder_name}.zip)...")
            zip_out_path = os.path.join(root_dir, "dist", dist_folder_name)
            shutil.make_archive(
                base_name=zip_out_path,
                format="zip",
                root_dir=os.path.join(root_dir, "dist"),
                base_dir=dist_folder_name
            )
            print(f"✅ 압축 완료! 최종 배포 파일: dist/{dist_folder_name}.zip")
            
        except Exception as e:
            print(f"❌ 배포 프로세스 진행 중 오류 발생: {e}")
    else:
        print(f"❌ [{dist_folder_name}] 컴파일된 빌드 폴더를 찾을 수 없습니다. 먼저 build_exe.py를 실행하세요.")

if __name__ == "__main__":
    cleanup()
