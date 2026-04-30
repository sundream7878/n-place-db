@echo off
setlocal
title NPlace-DB Launcher

echo ======================================================
echo   NPlace-DB 프로그램 시작 중...
echo ======================================================
echo.

:: 1. 필수 런타임 (Visual C++ Redistributable 2015-2022) 확인
echo [1/2] 필수 시스템 구성 요소 확인 중...
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v "Installed" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 일부 시스템에서 Visual C++ 런타임이 필요할 수 있습니다.
    echo [!] 프로그램 실행에 전용 DLL을 포함시켰으나, 오류 발생 시 아래 파일을 설치해 주세요.
    
    if exist "_internal\vc_redist.x64.exe" (
        echo [안내] _internal 폴더의 vc_redist.x64.exe를 설치하면 해결됩니다.
    ) else (
        echo [안내] 수동 설치 링크: https://aka.ms/vs/17/release/vc_redist.x64.exe
    )
    echo.
    echo (계속하려면 아무 키나 누르세요... 곧 프로그램이 실행됩니다.)
    timeout /t 3 >nul
) else (
    echo [OK] 시스템 구성 요소가 이미 설치되어 있습니다.
)

:: 2. 프로그램 실행
echo.
echo [2/2] 프로그램을 실행하는 중입니다...

:: 실행 파일 경로 설정 (dist 폴더 내의 실행 파일 위치에 맞게 조정)
if exist "NPlace-DB.exe" (
    start "" "NPlace-DB.exe"
) else if exist "dist\NPlace-DB\NPlace-DB.exe" (
    start "" "dist\NPlace-DB\NPlace-DB.exe"
) else (
    echo [오류] 실행 파일을 찾을 수 없습니다.
    echo 폴더 구성을 확인해 주세요.
    pause
    exit /b 1
)

echo ✅ 완료! 이 창은 3초 후 자동으로 닫힙니다.
timeout /t 3 >nul
exit
