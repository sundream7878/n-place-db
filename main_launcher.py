import os
import sys
import time
import subprocess
import socket
import argparse
import logging
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main_launcher")

def is_port_in_use(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(('127.0.0.1', port)) == 0
    except: return False

def run_streamlit(port):
    env = os.environ.copy()
    env["STREAMLIT_STANDALONE"] = "1"
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_path, "admin_dashboard", "app.py")
    
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        candidates = [
            os.path.join(base_path, "admin_dashboard", "app.py"),
            os.path.join(base_path, "_internal", "admin_dashboard", "app.py"),
        ]
        app_path = next((c for c in candidates if os.path.exists(c)), None)

    if not app_path: return None

    cmd = [sys.executable, "-m", "streamlit", "run", app_path, "--server.port", str(port), "--server.headless", "true"]
    return subprocess.Popen(cmd, env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

def launch_app_browser(port):
    url = f"http://127.0.0.1:{port}"
    for _ in range(15):
        if is_port_in_use(port): break
        time.sleep(1)
    
    app_modes = [
        ["chrome.exe", f"--app={url}", "--window-size=1300,1050", "--window-position=0,0"], 
        ["msedge.exe", f"--app={url}", "--window-size=1300,1050", "--window-position=0,0"]
    ]
    for app_cmd in app_modes:
        try:
            subprocess.Popen(app_cmd)
            return
        except: continue
    import webbrowser
    webbrowser.open(url)

def run_crawler_engine(target, limit, keyword):
    """[NEW] Runs the actual crawler script with visible window."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    engine_path = os.path.join(base_path, "step1_refined_crawler.py")
    
    cmd = [sys.executable, engine_path, target, str(limit), keyword]
    logger.info(f"🚀 Starting Crawler Engine: {target} | Limit: {limit}")
    
    # [FIX] Removed CREATE_NO_WINDOW to ensure Playwright window appears
    # [FIX] Added cwd to ensure relative paths inside crawler work correctly
    proc = subprocess.Popen(cmd, cwd=base_path)
    
    # Save PID to file for control
    pid_file = os.path.join(config.LOCAL_LOG_PATH, "engine.pid")
    os.makedirs(config.LOCAL_LOG_PATH, exist_ok=True)
    with open(pid_file, "w") as f: f.write(str(proc.pid))
    
    return proc

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", help="Target area")
    parser.add_argument("--limit", type=int, default=10, help="Target count")
    parser.add_argument("--keyword", help="Target keyword")
    args = parser.parse_args()

    if args.target:
        # --- ENGINE MODE ---
        logger.info("⚙️ Launcher running in ENGINE MODE.")
        proc = run_crawler_engine(args.target, args.limit, args.keyword if args.keyword else "")
        # The crawler script handles its own progress logging to file/stdout
        # Wait for the engine to finish
        proc.wait()
    else:
        # --- LAUNCHER MODE ---
        logger.info("🚀 Launcher running in DASHBOARD MODE.")
        port = 8501
        while is_port_in_use(port): port += 1
        
        st_proc = run_streamlit(port)
        if st_proc:
            launch_app_browser(port)
            st_proc.wait()

if __name__ == "__main__":
    main()
