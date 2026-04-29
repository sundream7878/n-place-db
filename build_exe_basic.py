import PyInstaller.__main__
import os
import shutil

def build():
    print("🔨 CafeMonster Basic 빌드 시작...")
    
    # 1. Clean previous builds
    if os.path.exists("build"): shutil.rmtree("build")
    if os.path.exists("dist"): shutil.rmtree("dist")
    
    # 2. PyInstaller Arguments
    args = [
        'gui_main_basic.py',              # Entry point
        '--name=CafeMonster_PlaceDB_Basic_v1.0',     # [가이드 준수] PlaceDB 식별자 사용

        '--onefile',                 # Pack into single EXE
        '--noconsole',               # Hide console window (Web UI will handle the display)
        '--collect-all=streamlit',   # Essential for streamlit apps
        '--collect-all=pycryptodome',
        '--collect-all=customtkinter',
        '--add-data=admin_dashboard;admin_dashboard', # Include templates/static
        '--add-data=messenger;messenger',
        '--add-data=crawler;crawler',
        '--add-data=config.py;.',
        '--collect-all=playwright_stealth',
        # 'admin_dashboard/templates.json' is removed as it's not used in Basic
        '--hidden-import=step1_refined_crawler',
        '--hidden-import=engine_recover_missing',
        '--hidden-import=streamlit.runtime.scriptrunner.magic_funcs',
        '--hidden-import=email.mime.text',
        '--hidden-import=email.mime.multipart',
        '--hidden-import=email.mime.application',
        '--clean'
    ]
    
    # 3. Execute Build
    try:
        PyInstaller.__main__.run(args)
        print("\n✅ 빌드 완료! 'dist/CafeMonster_PlaceDB_Basic_v1.0.exe' 파일을 확인하세요.")

    except Exception as e:
        print(f"\n❌ 빌드 중 오류 발생: {e}")

if __name__ == "__main__":
    build()
