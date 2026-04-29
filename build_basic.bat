@echo off
echo [Place-DB Basic] Packaging Standalone Executable...

:: Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Installing PyInstaller...
    pip install pyinstaller
)

:: Build Command
python -m PyInstaller -y --onedir --noconsole ^
    --name "Place-DB-Basic" ^
    --add-data "crawler;crawler" ^
    --add-data "data;data" ^
    --add-data "admin_dashboard;admin_dashboard" ^
    --add-data "assets;assets" ^
    --add-data "messenger;messenger" ^
    --add-data "step1_refined_crawler.py;." ^
    --add-data "engine_recover_missing.py;." ^
    --hidden-import customtkinter ^
    --hidden-import wmi ^
    --hidden-import openpyxl ^
    --copy-metadata streamlit ^
    --collect-all streamlit ^
    --collect-all customtkinter ^
    --collect-all playwright ^
    --collect-all playwright_stealth ^
    --hidden-import messenger ^
    --hidden-import messenger.email_sender ^
    --hidden-import messenger.safe_messenger ^
    gui_main_basic.py

echo.
echo [OK] Build Complete! Check the 'dist\Place-DB-Basic' folder for Place-DB-Basic.exe.
