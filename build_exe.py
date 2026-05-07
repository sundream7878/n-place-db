import PyInstaller.__main__
import os
import shutil

def build():
    print("N-Place-DB Pro Build Start...")
    
    # 1. Resilient Cleanup
    try:
        if os.path.exists("build"): shutil.rmtree("build", ignore_errors=True)
        if os.path.exists("dist"): shutil.rmtree("dist", ignore_errors=True)
        print("Cleanup done (ignoring locks).")
    except Exception as e:
        print(f"Warning during cleanup: {e}")
    
    # 2. PyInstaller Arguments
    args = [
        'NPlace_DB_Launcher.py',              # Entry point
        '--name=NPlace-DB',     # Output name
        '--onefile',            # Single EXE
        '--noconsole',          # No console window
        '--collect-all=streamlit',
        '--collect-all=pycryptodome',
        '--collect-all=customtkinter',
        '--add-data=admin_dashboard;admin_dashboard',
        '--add-data=messenger;messenger',
        '--add-data=crawler;crawler',
        '--add-data=assets;assets',
        '--add-data=config.py;.',
        '--add-data=admin_dashboard/templates.json;.',
        '--collect-all=playwright_stealth',
        '--collect-all=streamlit_autorefresh', # [FIX] Include missing module
        '--splash=C:\\Users\\chiuk\\.gemini\\antigravity\\brain\\cf677746-2969-4ce9-bc2c-073b4f4c1b30\\nplace_db_official_splash_1778128328952.png', # [NEW] Official Logo Splash
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
        print("\nBuild Complete! Check 'dist/NPlace-DB.exe'.")
    except Exception as e:
        print(f"\nBuild Failed: {e}")

if __name__ == "__main__":
    build()
