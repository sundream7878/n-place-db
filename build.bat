@echo off
echo [N-Place-DB Pro] Packaging Standalone Executable...

:: Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Installing PyInstaller...
    pip install pyinstaller
)

:: Build Command
:: --onedir: Create a directory with an executable (Fast Startup)
:: --noconsole: Hide terminal window
:: --icon: Add custom icon if available
:: --add-data: Include dependencies or default config
python -m PyInstaller -y --onedir --noconsole ^
    --name "NPlace-DB" ^
    --add-data "crawler;crawler" ^
    --add-data "data;data" ^
    --add-data "admin_dashboard;admin_dashboard" ^
    --add-data "assets;assets" ^
    --add-data "messenger;messenger" ^
    --add-data "step1_refined_crawler.py;." ^
    --add-data "engine_recover_missing.py;." ^
    --add-data "NPlace-DB-실행.bat;." ^
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
    gui_main.py

echo.
echo [OK] Build Complete! Check the 'dist\NPlace-DB' folder for NPlace-DB.exe.

