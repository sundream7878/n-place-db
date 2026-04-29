import os
import sys
import subprocess
import winreg
import time

def is_vc_redist_installed():
    """Checks if Microsoft Visual C++ 2015-2022 Redistributable (x64) is installed."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64")
        value, _ = winreg.QueryValueEx(key, "Installed")
        return value == 1
    except FileNotFoundError:
        return False
    except Exception:
        return False

def get_base_path():
    """Returns the base path for bundled files (PyInstaller _MEIPASS)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def main():
    base_path = get_base_path()
    
    # 1. Check and Install VC++ Redistributable
    if not is_vc_redist_installed():
        redist_path = os.path.join(base_path, "vc_redist.x64.exe")
        if os.path.exists(redist_path):
            print("필수 시스템 구성 요소(Visual C++)가 발견되지 않았습니다.")
            print("자동 설치를 시작합니다. 관리자 권한 허용이 필요할 수 있습니다...")
            try:
                # Run silently and wait
                subprocess.run([redist_path, "/quiet", "/norestart"], check=True)
                print("설치 완료!")
            except subprocess.CalledProcessError:
                print("설치 중 오류가 발생했습니다. 수동 설치를 권장합니다.")
        else:
            print("설치 파일(vc_redist.x64.exe)이 번들 안에 없습니다.")

    # 2. Launch the main application
    # The main app is located inside the 'app_files' directory in our bundle
    app_exe = os.path.join(base_path, "app_files", "N-Place-DB-Pro-Final.exe")
    
    if os.path.exists(app_exe):
        print("프로그램을 실행하는 중...")
        # Working directory should be the app_files folder so it can find its data/log files
        app_dir = os.path.dirname(app_exe)
        
        # We use Popen instead of run/call so we don't keep the console open if not needed
        # But since this is a wrapper, we might want to wait for it or just exit.
        # If we use --noconsole for the wrapper, it won't show anything.
        try:
            subprocess.Popen([app_exe], cwd=app_dir)
            print("실행 성공! 이 창은 곧 닫힙니다.")
            time.sleep(2)
        except Exception as e:
            print(f"실행 중 오류 발생: {e}")
            input("엔터 키를 눌러 종료하세요...")
    else:
        print(f"실행 파일(N-Place-DB-Pro-Final.exe)을 찾을 수 없습니다: {app_exe}")
        input("엔터 키를 눌러 종료하세요...")

if __name__ == "__main__":
    main()
