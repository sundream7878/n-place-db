@echo off
echo [N-Place-DB Pro] Launching Web Dashboard...
pip show streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Installing Streamlit...
    pip install streamlit
)
streamlit run admin_dashboard/app.py
pause
