import os
import sys
import time
import subprocess
import socket
import threading
import webbrowser
import signal

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)  # 타임아웃 추가
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_streamlit(port):
    """Runs the Streamlit server as a subprocess."""
    # Add a flag to tell streamlit it's running in standalone launcher mode
    env = os.environ.copy()
    env["STREAMLIT_STANDALONE"] = "1"
    
    # Resolve the correct path to app_basic.py (PyInstaller _MEIPASS support)
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_path, "admin_dashboard", "app_basic.py")
    
    cmd = [
        sys.executable, "-m", "streamlit", "run", 
        app_path, 
        "--server.port", str(port), 
        "--server.address", "127.0.0.1",  # 명시적으로 주소 지정
        "--server.headless", "true",
        "--global.developmentMode", "false"
    ]
    
    return subprocess.Popen(cmd, env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def launch_app_browser(port):
    """Launches the system browser in App Mode (no address bar)."""
    url = f"http://127.0.0.1:{port}"
    
    # Wait for the server to be ready
    for _ in range(30):
        if is_port_in_use(port):
            break
        time.sleep(1)
    
    # Try Chrome/Edge app mode first
    # Position: (0, 0), Size: (900, 1000)
    app_modes = [
        ["chrome.exe", f"--app={url}", "--window-position=0,0", "--window-size=1000,980"],
        ["msedge.exe", f"--app={url}", "--window-position=0,0", "--window-size=1000,980"],
    ]
    
    success = False
    for app_cmd in app_modes:
        try:
            # Check if browser exists by trying to run with --version or similar safely
            subprocess.Popen(app_cmd)
            success = True
            break
        except FileNotFoundError:
            continue
            
    if not success:
        # Fallback to default browser if app mode fails
        webbrowser.open(url)

def get_port(default_port):
    port = default_port
    print(f"🔍 포트 체크 시작: {port}...")
    try:
        while is_port_in_use(port):
            print(f"⚠️ 포트 {port} 사용 중, 다음 포트 시도...")
            port += 1
            if port > 65535:
                port = 1024
    except Exception as e:
        print(f"❌ 포트 체크 중 오류: {e}")
    return port

def main():
    import codecs
    if sys.stdout and getattr(sys.stdout, 'encoding', None) is not None:
        if sys.stdout.encoding.lower() != 'utf-8':
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
        
    print("🚀 N-Place-DB Basic 시작 중... (데이터수집 전용)")
    
    port = get_port(8502)
    print(f"📡 접속 포트: {port}")
    
    # 1. Start Streamlit Server
    st_proc = run_streamlit(port)
    
    # 2. Launch Browser in App Mode
    launch_app_browser(port)
    
    print("✅ 프로그램이 실행되었습니다. 창을 닫으면 종료됩니다.")
    
    try:
        # Keep the launcher alive until the server is killed or manually interrupted
        # In a real packaged scenario, we might want to monitor the browser window 
        # but tracking a browser process reliably is tricky. 
        # For now, we wait for the ST process.
        st_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 프로그램 종료 중...")
        st_proc.terminate()

if __name__ == "__main__":
    main()
