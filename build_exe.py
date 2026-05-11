import PyInstaller.__main__
import os
import shutil
import config

def build():
    v = config.CURRENT_VERSION
    print(f"N-Place-DB Build Start (v{v})...")

    
    # 1. Resilient Cleanup
    try:
        if os.path.exists("build"): shutil.rmtree("build", ignore_errors=True)
        # Clean up previous versions in dist
        if os.path.exists("dist"):
            for d in os.listdir("dist"):
                if d.startswith("NPlace-DB"):
                    shutil.rmtree(os.path.join("dist", d), ignore_errors=True)
                    
        print("Cleanup done (including pycache).")
    except Exception as e:
        print(f"Warning during cleanup: {e}")
    
    # 2. PyInstaller Arguments
    args = [
        'NPlace_DB_Launcher.py',              
        f'--name=NPlace-DB-v{v}',  # [FIX] Use version number for unique build
        '--onedir',             

        '--noconsole',          
        '--noconfirm',          
        '--collect-all=streamlit',
        '--collect-all=pycryptodome',
        '--collect-all=customtkinter',
        '--collect-all=numpy',
        '--collect-all=pandas',
        '--add-data=admin_dashboard;admin_dashboard',
        '--add-data=messenger;messenger',
        '--add-data=crawler;crawler',
        '--add-data=assets;assets',
        '--add-data=config.py;.',
        '--add-data=admin_dashboard/templates.json;.',
        # [FIX] Engine scripts must be included as data files so runpy.run_path() can find them
        '--add-data=step1_refined_crawler.py;.',
        '--add-data=engine_recover_missing.py;.',
        '--add-data=auth.py;.',
        '--add-data=auth_gui.py;.',
        '--add-data=sb_auth_manager.py;.',
        '--add-data=updater.py;.',
        '--add-data=exporter.py;.',
        '--add-data=main_launcher.py;.',
        '--collect-all=playwright_stealth',
        '--collect-all=streamlit_autorefresh',
        '--splash=C:\\Users\\chiuk\\.gemini\\antigravity\\brain\\cf677746-2969-4ce9-bc2c-073b4f4c1b30\\nplace_db_official_splash_1778128328952.png',
        '--hidden-import=step1_refined_crawler',
        '--hidden-import=engine_recover_missing',
        '--hidden-import=streamlit.runtime.scriptrunner.magic_funcs',
        '--hidden-import=email.mime.text',
        '--hidden-import=email.mime.multipart',
        '--hidden-import=email.mime.application',
        '--hidden-import=pandas._libs.tslibs.timedeltas',
        '--hidden-import=pandas._libs.tslibs.np_datetime',
        '--hidden-import=pandas._libs.tslibs.nattype',
        '--hidden-import=numpy.core._multiarray_umath',
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
