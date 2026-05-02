@echo off
echo [N-Place-DB] Packaging Standalone Executable...
echo Entry Point: NPlace_DB_Launcher.py
echo.

:: Execute the build script
python build_exe.py

echo.
echo [OK] All Done.
pause
