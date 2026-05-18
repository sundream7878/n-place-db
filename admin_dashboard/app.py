import sys
import os
import logging

# [CRITICAL FIX] Root logger configuration to prevent NoneType stdout errors in frozen mode
if getattr(sys, 'frozen', False):
    try:
        # Use config.ENGINE_LOG_FILE for unification (data/app.log)
        log_file = config.ENGINE_LOG_FILE
        log_dir = os.path.dirname(log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        # Use FileHandler ONLY, NO StreamHandler (stdout is None)
        logging.basicConfig(
            handlers=[logging.FileHandler(log_file, encoding='utf-8', mode='a')],
            level=logging.INFO,
            force=True
        )
        # Redirection as secondary defense
        if sys.stdout is None or sys.stderr is None:
            log_fd = os.open(log_file, os.O_RDWR | os.O_CREAT | os.O_APPEND)
            if sys.stdout is None: os.dup2(log_fd, 1) # stdout
            if sys.stderr is None: os.dup2(log_fd, 2) # stderr
    except: pass

import streamlit as st
import importlib

# Ensure parent directory is in path to import config
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
importlib.reload(config)

# [FIX] Force close splash screen as soon as dashboard starts
try:
    import pyi_splash
    if pyi_splash.is_available():
        pyi_splash.close()
except:
    pass

# [가이드 준수] Wide Layout & Premium Branding
st.set_page_config(
    page_title=f"[{config.BRAND_NAME_KR}] Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# [가이드 준수] Ultra Wide Full-Width CSS (Force Immediate Expansion)
st.markdown("""
    <style>
    /* 메인 컨테이너 최대 확장 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 98% !important;
    }
    /* 앱 전체 너비 고정 */
    .stApp {
        width: 100% !important;
    }
    /* 불필요한 여백 및 푸터 제거 */
    footer {display: none !important;}
    header {display: none !important;}
    #MainMenu {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

import pandas as pd
import json
import time
import subprocess
import hashlib
import smtplib
from streamlit_autorefresh import st_autorefresh
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# Imports moved to top

from sb_auth_manager import SupabaseAuthManager as AuthManager
from crawler.local_db_handler import LocalDBHandler as DBHandler
import base64

# --- Security Utilities ---
def get_crypto_key():
    return AuthManager.get_hwid()

def encrypt_pw(pw):
    if not pw: return ""
    try:
        key = get_crypto_key().encode('utf-8')
        data = pw.encode('utf-8')
        res = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return base64.b64encode(res).decode('utf-8')
    except: return pw

def decrypt_pw(enc_pw):
    if not enc_pw: return ""
    try:
        key = get_crypto_key().encode('utf-8')
        data = base64.b64decode(enc_pw)
        res = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return res.decode('utf-8')
    except: return enc_pw

# --- 1. Setup & Functions ---
TEMPLATE_FILE = config.LOCAL_TEMPLATE_FILE

def load_templates():
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f: 
            data = json.load(f)
            # Decrypt profiles
            for email in data.get("email_profiles", {}):
                data["email_profiles"][email]["pw"] = decrypt_pw(data["email_profiles"][email].get("pw", ""))
            for insta in data.get("insta_profiles", {}):
                data["insta_profiles"][insta]["pw"] = decrypt_pw(data["insta_profiles"][insta].get("pw", ""))
            # Decrypt main fields
            data["naver_pw"] = decrypt_pw(data.get("naver_pw", ""))
            data["insta_pw"] = decrypt_pw(data.get("insta_pw", ""))
            return data
    return {
        "email_profiles": {
            "example@naver.com": {"pw": "", "smtp": "smtp.naver.com", "port": 465}
        }, 
        "active_email_profile": "chiu3@naver.com",
        "insta_profiles": {
            "jinwook.han7878": {"pw": decrypt_pw("KCxRKSh+DnkKGg==")}
        }, 
        "active_insta_profile": "jinwook.han7878",
        "naver_user": "", "naver_pw": "", "insta_user": "", "insta_pw": "",
        "tpl_A": {"subject": "안녕하세요, {상호명} 원장님!", "body": "원장님 안녕하세요! 마케팅 몬스터입니다.", "sender_name": "", "sender_names": []},
        "tpl_B": "안녕하세요! 네이버 톡톡 메시지입니다.",
        "tpl_C": "인스타그램 DM 메시지입니다.",
        "test_recipients_A": ["", "", ""],
        "test_recipients_C": ["", "", ""]
    }

def save_templates():
    # Deep copy to avoid encrypting session state UI values
    import copy
    email_p = copy.deepcopy(st.session_state.get('email_profiles', {}))
    insta_p = copy.deepcopy(st.session_state.get('insta_profiles', {}))
    
    # Encrypt passwords before saving to file
    for email in email_p: email_p[email]["pw"] = encrypt_pw(email_p[email].get("pw", ""))
    for insta in insta_p: insta_p[insta]["pw"] = encrypt_pw(insta_p[insta].get("pw", ""))

    # --- Ensure sender_name is saved to the history list if new ---
    tpl_A = st.session_state.get('tpl_A', {})
    current_name = tpl_A.get('sender_name', '').strip()
    history_names = tpl_A.get('sender_names', [])
    if current_name and current_name not in history_names:
        history_names.append(current_name)
        tpl_A['sender_names'] = history_names

    data = {
        "email_profiles": email_p,
        "active_email_profile": st.session_state.get('active_email_profile', ''),
        "insta_profiles": insta_p,
        "active_insta_profile": st.session_state.get('active_insta_profile', ''),
        "naver_user": st.session_state.get('naver_user', ''),
        "naver_pw": encrypt_pw(st.session_state.get('naver_pw', '')),
        "insta_user": st.session_state.get('insta_user', ''),
        "insta_pw": encrypt_pw(st.session_state.get('insta_pw', '')),
        "tpl_A": tpl_A,
        "tpl_B": st.session_state.get('tpl_B', ''),
        "tpl_C": st.session_state.get('tpl_C', ''),
        "test_recipients_A": st.session_state.get('test_recipients_A', ["", "", ""]),
        "test_recipients_C": st.session_state.get('test_recipients_C', ["", "", ""])
    }
    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    st.toast("✅ 설정이 안전하게 암호화되어 저장되었습니다.")

def load_local_data():
    db_h = DBHandler(config.LOCAL_DB_PATH)
    data = db_h.get_all_shops()
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # [NEW] Drop unwanted columns for a cleaner UI/Export (Rule 3.2)
    unwanted = ["latitude", "longitude", "talk_url", "owner_name"]
    df = df.drop(columns=[col for col in unwanted if col in df.columns], errors='ignore')
    
    # [NEW] Insert 'No' column at the very beginning
    df.insert(0, "No", range(1, len(df) + 1))
    
    # Map DB columns to UI Korean Labels
    mapping = {
        "name": "상호명", "address": "주소", "phone": "번호", 
        "email": "이메일", "instagram_handle": "인스타", 
        "detail_url": "플레이스링크",
        "last_result_email": "결과(E)", "last_msg_email": "로그(E)",
        "last_result_insta": "결과(I)", "last_msg_insta": "로그(I)"
    }
    df = df.rename(columns=mapping)
    return df

def get_engine_pid():
    pid_file = os.path.join(config.LOCAL_LOG_PATH, "engine.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                content = f.read().strip()
                if not content: return None
                pid = int(content)
                import psutil
                if psutil.pid_exists(pid): 
                    return pid
                else:
                    # [DEBUG] PID file exists but process is gone
                    return None
        except Exception as e:
            # [DEBUG] Error reading PID file
            return None
    return None

def stop_engine():
    pid = get_engine_pid()
    if pid:
        import psutil
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True): child.kill()
            parent.kill()
            st.success("엔진이 정지되었습니다.")
            return True
        except: pass
    return False

def run_engine_cmd(target, limit, keyword="", filter_mode="all", filter_keyword=""):
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen:
        # [FIX] In frozen (exe) mode, the exe itself acts as the Python launcher.
        # The launcher's __main__ block handles argv like 'step1_refined_crawler.py'
        # by running it via runpy.run_path from _internal folder.
        exe_path = sys.executable
        script_name = "step1_refined_crawler.py"
        cmd = [exe_path, script_name, target, str(limit), keyword]
        cwd = os.path.dirname(exe_path)  # dist/NPlace-DB-v2/
    else:
        # [DEV] In dev mode, call python interpreter directly
        base_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.abspath(os.path.join(base_dir, '..', 'step1_refined_crawler.py'))
        cmd = [sys.executable, script_path, target, str(limit), keyword]
        cwd = os.path.dirname(script_path)
    
    if filter_mode != "all":
        cmd.extend(["--filter-mode", filter_mode, "--filter-keyword", filter_keyword])
    
    my_env = os.environ.copy()
    my_env["PYTHONIOENCODING"] = "utf-8"
    my_env["PYTHONUNBUFFERED"] = "1"
    
    # [NEW] Force Playwright to look for browsers in the bundled directory if frozen
    if is_frozen:
        bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(exe_path))
        my_env["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(bundle_dir, "playwright", "driver", "package", ".local-browsers")
    
    
    # Launch without CREATE_NO_WINDOW so the log file approach works
    proc = subprocess.Popen(
        cmd, 
        cwd=cwd,
        env=my_env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    
    # Save PID to file for control
    pid_file = os.path.join(config.LOCAL_LOG_PATH, "engine.pid")
    os.makedirs(config.LOCAL_LOG_PATH, exist_ok=True)
    with open(pid_file, "w") as f: f.write(str(proc.pid))
    
    # Reset completion state
    st.session_state["completion_shown"] = False
    
    st.success("수집 엔진이 가동되었습니다. 잠시 후 N플레이스 창이 나타납니다.")
    time.sleep(1)

def get_crawler_progress():
    # Path relative to the dashboard script
    prog_path = config.PROGRESS_FILE
    if os.path.exists(prog_path):
        try:
            with open(prog_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def get_live_logs(n=1000):
    log_path = config.ENGINE_LOG_FILE
    
    combined_logs = []
    
    # 1. Check for logs
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                combined_logs.append("".join(lines[-n:]))
        except: 
            combined_logs.append("로그를 읽는 중 오류 발생")
            
    if not combined_logs:
        return "수집 로그가 아직 없습니다."
    return "\n".join(combined_logs)

from email.header import Header

def send_email(user, pw, target, subject, body, smtp_server="smtp.naver.com", smtp_port=465, attachments=None, sender_name=None):
    try:
        # [FIX] Force strip to prevent credential errors
        user = user.strip() if user else ""
        pw = pw.strip() if pw else ""
        
        msg = MIMEMultipart()
        # [FIX] Ensure valid RFC-5322 From address (Especially for Naver)
        from_addr = user
        if "@" not in from_addr and "naver.com" in smtp_server.lower():
            from_addr = f"{from_addr}@naver.com"
            
        if sender_name:
            msg['From'] = f"{Header(sender_name, 'utf-8').encode()} <{from_addr}>"
        else:
            msg['From'] = from_addr
        msg['To'] = target
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        if attachments:
            for att in attachments:
                part = MIMEApplication(att['content'], Name=att['name'])
                part['Content-Disposition'] = f'attachment; filename="{att["name"]}"'
                msg.attach(part)
        
        # [NEW] Multi-Port Support (SSL vs STARTTLS)
        try:
            port_val = int(smtp_port) if smtp_port else 465
        except:
            port_val = 465

        if port_val == 465:
            with smtplib.SMTP_SSL(smtp_server, port_val, timeout=15) as server:
                server.login(user, pw)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, port_val, timeout=15) as server:
                server.set_debuglevel(0)
                server.starttls()
                server.login(user, pw)
                server.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError as e:
        err_msg = str(e)
        if "535" in err_msg:
            return False, "로그인 실패 (535): 아이디/비번 불일치.\n\n[체크리스트]\n1. 네이버 '앱 암호'(16자리)를 사용 중인가요? (일반 비번 X)\n2. 네이버 메일 설정에서 'IMAP/SMTP'가 '사용함'인가요?\n3. 비번 끝에 ')' 같은 오타가 포함되지 않았나요?"
        return False, f"인증 오류: {err_msg}"
    except Exception as e:
        err_msg = str(e)
        if "553" in err_msg:
            return False, "발송 거절 (553): 발신자 주소 형식 오류.\n계정 아이디가 정확한 이메일 형식(예: abc@naver.com)인지 확인해 주세요."
        return False, err_msg

def test_smtp_connection(user, pw, smtp_server, smtp_port):
    try:
        user = user.strip()
        pw = pw.strip()
        port_val = int(smtp_port)
        
        if port_val == 465:
            with smtplib.SMTP_SSL(smtp_server, port_val, timeout=10) as server:
                server.login(user, pw)
        else:
            with smtplib.SMTP(smtp_server, port_val, timeout=10) as server:
                server.starttls()
                server.login(user, pw)
        return True, "✅ 연결 성공! 이 계정으로 메일을 보낼 수 있습니다."
    except smtplib.SMTPAuthenticationError as e:
        err_msg = str(e)
        if "535" in err_msg:
            return False, "❌ 인증 실패 (535): 아이디 또는 비밀번호가 틀립니다. 네이버 '앱 암호'를 확인해 주세요."
        return False, f"❌ 인증 오류: {err_msg}"
    except Exception as e:
        return False, f"❌ 연결 실패: {str(e)}"

def format_tpl(text, shop_name):
    if not text: return ""
    return text.replace("{상호명}", shop_name if shop_name else "원장님")

# --- UI Configuration ---
# st.set_page_config removed to avoid redundancy

# Init Session State
if 'active_page' not in st.session_state: st.session_state['active_page'] = 'Shop Search'
if 'last_selected_shop' not in st.session_state: st.session_state['last_selected_shop'] = None
if 'tpl_data_loaded' not in st.session_state:
    tpls = load_templates()
    for k, v in tpls.items(): st.session_state[k] = v
    st.session_state['tpl_data_loaded'] = True
if 'sel_track_A' not in st.session_state: st.session_state['sel_track_A'] = {}
if 'sel_track_B' not in st.session_state: st.session_state['sel_track_B'] = {}
if 'sel_track_C' not in st.session_state: st.session_state['sel_track_C'] = {}

# --- Window Resize & Position Enforcement ---
import streamlit.components.v1 as components
components.html(
    """
    <script>
    window.parent.moveTo(0, 0);
    window.parent.resizeTo(1300, 1050);
    </script>
    """,
    height=0, width=0
)

# --- Global CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;700;900&display=swap');
    
    .stApp { 
        background-color: #F1F5F9; 
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif; 
    }
    
    .section-container {
        background: white; 
        border: 1.5px solid #94A3B8; 
        border-radius: 15px; 
        padding: 1.2rem; 
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px -5px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease;
    }
    .section-container:hover { border-color: #00E676; transform: translateY(-1px); }

    .section-title { 
        font-size: 1.2rem; font-weight: 900; color: #0F172A; 
        margin-bottom: 0.8rem; display: flex; align-items: center; gap: 10px; 
    }
    .input-label { font-size: 0.9rem; font-weight: 800; color: #334155; margin-bottom: 6px; }

    .stProgress > div > div > div > div {
        background: linear-gradient(to right, #00E676, #00C853);
        height: 14px !important; border-radius: 10px;
    }

    [data-testid="stDataFrame"] {
        border: 1.5px solid #94A3B8; border-radius: 12px; overflow: hidden;
    }

    .status-card { 
        background: #F8FAFC; border-radius: 12px; padding: 1rem; 
        border: 1.5px solid #94A3B8; 
    }
    
    .log-container {
        background-color: #0F172A !important; 
        color: #38BDF8 !important; 
        padding: 20px !important; 
        border-radius: 15px !important;
        font-family: 'JetBrains Mono', 'Consolas', monospace !important; 
        font-size: 0.9rem !important; 
        height: 450px !important;
        max-height: 450px !important;
        overflow-y: auto !important; 
        white-space: pre-wrap !important; 
        border: 2px solid #1E293B !important;
        box-shadow: inset 0 2px 10px rgba(0,0,0,0.5) !important;
        position: relative !important;
        display: block !important;
    }
    
    /* [FIX] 전용 스크롤바 강제 적용 */
    .log-container::-webkit-scrollbar {
        width: 10px !important;
        display: block !important;
    }
    .log-container::-webkit-scrollbar-track {
        background: #1E293B !important;
        border-radius: 10px !important;
    }
    .log-container::-webkit-scrollbar-thumb {
        background: #475569 !important;
        border-radius: 10px !important;
        border: 2px solid #1E293B !important;
    }
    .log-container::-webkit-scrollbar-thumb:hover {
        background: #64748B !important;
    }
    

    .stButton button { 
        border-radius: 12px !important; font-weight: 800 !important;
        padding: 0.6rem 1.5rem !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }

    /* [NEW] 선명한 입력창 스타일 */
    .stTextInput input, .stTextArea textarea, [data-baseweb="select"] {
        border: 1.5px solid #94A3B8 !important; /* 선명한 회색 테두리 */
        border-radius: 10px !important;
        background-color: #FFFFFF !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, [data-baseweb="select"]:focus-within {
        border-color: #A855F7 !important; /* 보라색 네온 포커스 */
        box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.2) !important;
    }

    [data-testid="stHeader"] { background: rgba(255,255,255,0.9); backdrop-filter: blur(12px); }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    
    /* Global vertical gap reduction */
    [data-testid="stVerticalBlock"] {
        gap: 0.7rem !important;
    }
    
    [data-testid="stVerticalBlock"] > div:has(.nav-anchor) {
        position: sticky; top: 0; z-index: 1000;
        background-color: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px);
        padding: 8px 0; /* 압축된 패딩 */
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .nav-anchor { display: none; }
    </style>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const blocker = () => {
            document.querySelectorAll('input').forEach(input => {
                if (input.getAttribute('autocomplete') !== 'new-password') {
                    input.setAttribute('autocomplete', 'new-password');
                    input.setAttribute('spellcheck', 'false');
                }
            });
        };
        blocker();
        setInterval(blocker, 1000);
    });
    </script>
""", unsafe_allow_html=True)

# Header & Nav (Sticky Container)
with st.container():
    st.markdown('<div class="nav-anchor"></div>', unsafe_allow_html=True) # Sticky를 위한 앵커
    col_logo, col_nav = st.columns([1.8, 4], vertical_alignment="center")
    with col_logo:
        # Optimized Logo & Title Layout
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "MarketingMonster_logo.png")
        logo_base64 = base64.b64encode(open(logo_path, 'rb').read()).decode() if os.path.exists(logo_path) else ""
        
        st.markdown(f"""
            <div style="display:flex; align-items:center; gap:20px;">
                <img src="data:image/png;base64,{logo_base64}" width="110" style="margin-bottom:5px;">
                <div style="display:flex; flex-direction:column;">
                    <div style="display:flex; align-items:baseline; gap:8px;">
                    <div style="font-size:2.0rem; font-weight:900; background: linear-gradient(135deg, #A855F7 0%, #3B82F6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing:-1.5px; filter: drop-shadow(0 0 8px rgba(168, 85, 247, 0.3));">NPlace-DB</div>
                    <div style="font-size:0.75rem; font-weight:700; color:#94A3B8; background:#F8FAFC; padding:1px 6px; border-radius:5px; border:1px solid #E2E8F0;">v{config.CURRENT_VERSION}</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    with col_nav:
        nav_cols = st.columns(4)
        btns = ["🏠 수집/제어", "📧 이메일", "📸 인스타", "📖 가이드"]
        pages = ["Shop Search", "Track A", "Track C", "Guide"]
        for i, (lbl, p) in enumerate(zip(btns, pages)):
            if nav_cols[i].button(lbl, key=f"nav_v5_{p}", use_container_width=True, type="primary" if st.session_state['active_page'] == p else "secondary"):
                st.session_state['active_page'] = p
                st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
df = load_local_data()

# --- Settings Persistence ---
SETTINGS_FILE = config.SETTINGS_FILE

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_settings(new_settings):
    current = load_settings()
    current.update(new_settings)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        # Sync session state so UI reflects latest saved values
        st.session_state['user_settings'] = current
    except Exception as e:
        logger.error(f"Settings save failed: {e}")

# [NEW] Auto-save callbacks — called whenever widget value changes
def _autosave_keyword():
    val = st.session_state.get('monster_db_kw_input_v7', '')
    if val: # Only save if not empty to prevent accidental wipes
        save_settings({'keyword': val})

def _autosave_exclude():
    # Exclusion can be empty, so we just save
    save_settings({'exclude': st.session_state.get('main_ex_v5', '')})

def _autosave_filter_mode():
    save_settings({'filter_mode_ui': st.session_state.get('main_f_mode_v5', '전체(상호/업종/메뉴 포함)')})

def _autosave_provinces():
    val = st.session_state.get('main_prov_v5', [])
    if val:
        save_settings({'provinces': val})

def _autosave_districts():
    val = st.session_state.get('main_dist_v5', [])
    if val:
        save_settings({'districts': val})

# Initial Settings Load
if 'user_settings' not in st.session_state:
    st.session_state['user_settings'] = load_settings()
    us = st.session_state['user_settings']
    # Force initialize widget session states to saved values so they don't appear empty
    st.session_state['monster_db_kw_input_v7'] = us.get('keyword', config.BASE_KEYWORD)
    st.session_state['main_ex_v5'] = us.get('exclude', "")
    st.session_state['main_f_mode_v5'] = us.get('filter_mode_ui', "상호명 일치")
    st.session_state['main_prov_v5'] = us.get('provinces', [])
    
    # Check if saved provinces exist in config to prevent errors
    saved_provs = us.get('provinces', [])
    valid_provs = [p for p in saved_provs if p in config.REGIONS_LIST]
    st.session_state['main_prov_v5'] = valid_provs
    # [FIX] Restore saved districts as well
    st.session_state['main_dist_v5'] = us.get('districts', [])



def render_track(track_id, label, col_filter, cfg_name, df_in):
    st.markdown(f"#### 🚀 {label}")
    with st.expander(f"⚙️ {cfg_name} 및 템플릿 설정", expanded=True):
        c1, c2 = st.columns(2)
        # --- [NEW] Unified Multi-Profile Management (Email & Instagram) ---
        p_key = 'email_profiles' if track_id == 'A' else 'insta_profiles'
        a_key = 'active_email_profile' if track_id == 'A' else 'active_insta_profile'
        p_label = "📧 등록된 이메일 ID 프로필" if track_id == 'A' else "📸 등록된 인스타 ID 프로필"
        p_placeholder = "발송할 이메일을 선택하세요" if track_id == 'A' else "발송할 인스타 계정을 선택하세요"
        
        profiles = st.session_state.get(p_key, {})
        p_list = list(profiles.keys())
        
        c_sel, c_add = st.columns([3, 1])
        with c_sel:
            # [MOD] Auto-select first profile if none active
            active_p = st.session_state.get(a_key, '')
            if not active_p and p_list:
                active_p = p_list[0]
                st.session_state[a_key] = active_p

            sel_p = st.selectbox(p_label, options=p_list, 
                                 index=p_list.index(active_p) if active_p in p_list else None,
                                 placeholder=p_placeholder, key=f"{p_key}_selector")
            if sel_p: st.session_state[a_key] = sel_p

        with c_add:
            st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
            add_visible = st.session_state.get(f'show_add_v2_{track_id}', False)
            btn_txt = "❌ 닫기" if add_visible else "➕ 계정 추가"
            if st.button(btn_txt, key=f"btn_add_v2_{track_id}", use_container_width=True):
                st.session_state[f'show_add_v2_{track_id}'] = not add_visible
                st.rerun()

        if st.session_state.get(f'show_add_v2_{track_id}', False):
            with st.container(border=True):
                st.markdown(f"**✨ 새로운 {label} 계정 등록**")
                c1, c2 = st.columns(2)
                if track_id == 'A':
                    new_id = c1.text_input("발송용 네이버 이메일 ID", placeholder="아이디만 입력해도 됩니다", help="예: 'chiu3' 만 입력하면 자동으로 'chiu3@naver.com'이 됩니다.", key="new_email_id_v2")
                    new_pw = c2.text_input("🔑 비밀번호 (앱 암호)", type="password", help="네이버/Gmail은 반드시 '앱 암호'를 발급받아 입력해야 합니다.", key="new_email_pw_v2")
                    with c2:
                        st.caption("⚠️ **주의**: 일반 비밀번호가 아닌, 2단계 인증 설정 후 발급받은 **'앱 암호'**를 입력해 주세요.")
                    
                    # Auto-detect SMTP and Correct ID format
                    if new_id and "@" not in new_id:
                        new_id = f"{new_id.strip()}@naver.com"
                    
                    def_smtp, def_port = "smtp.naver.com", 465
                    if "@gmail.com" in new_id.lower(): def_smtp, def_port = "smtp.gmail.com", 465
                    elif "@daum.net" in new_id.lower() or "@hanmail.net" in new_id.lower(): def_smtp, def_port = "smtp.daum.net", 465
                    elif "@naver.com" in new_id.lower(): def_smtp, def_port = "smtp.naver.com", 465
                    
                    sc1, sc2 = st.columns(2)
                    sc1.text_input("SMTP 서버 (자동 감지)", value=def_smtp, disabled=True, key="auto_smtp")
                    sc2.number_input("SMTP 포트 (자동 감지)", value=def_port, disabled=True, key="auto_port")
                else:
                    new_id = c1.text_input("인스타그램 ID", placeholder="insta_id", key="new_insta_id")
                    new_pw = c2.text_input("비밀번호", type="password", key="new_insta_pw")
                
                if st.button("💾 이 계정 저장하기", use_container_width=True, key=f"save_new_{track_id}"):
                    if new_id and new_pw:
                        new_pw = new_pw.strip() # [FIX] Auto-strip
                        if track_id == 'A':
                            profiles[new_id] = {"pw": new_pw, "smtp": def_smtp, "port": def_port}
                        else:
                            profiles[new_id] = {"pw": new_pw}
                        st.session_state[p_key] = profiles
                        st.session_state[a_key] = new_id
                        save_templates()
                        st.success(f"'{new_id}' 계정이 등록되었습니다.")
                        time.sleep(1)
                        st.rerun()
                    else: st.error("ID와 비밀번호를 입력해 주세요.")
        
        # Show selected profile info
        active_p = st.session_state.get(a_key, '')
        if active_p and active_p in profiles:
            p_info = profiles[active_p]
            with st.container(border=True):
                c_info, c_manage = st.columns([4, 1.2], vertical_alignment="center")
                desc = f" ({p_info['smtp']})" if 'smtp' in p_info else ""
                c_info.info(f"✅ **발송 대기:** `{active_p}`{desc}")
                
                is_open = st.session_state.get(f'show_manage_{active_p}', False)
                btn_label = "❌ 관리창 닫기" if is_open else "🛠️ 계정 관리"
                if c_manage.button(btn_label, key=f"btn_manage_{active_p}", use_container_width=True):
                    st.session_state[f'show_manage_{active_p}'] = not is_open
                    st.rerun()
                
                if is_open:
                    st.markdown("---")
                    if track_id == 'A':
                        sc1, sc2 = st.columns(2)
                        sc1.text_input("⚙️ 서버 정보 (SMTP)", value=p_info.get('smtp', 'smtp.naver.com'), disabled=True, key=f"disp_smtp_{active_p}")
                        sc2.text_input("🔌 포트 (Port)", value=str(p_info.get('port', 465)), disabled=True, key=f"disp_port_{active_p}")
                    c_pw, c_test, c_save = st.columns([2.5, 1, 1], vertical_alignment="bottom")
                    new_pw_edit = c_pw.text_input("🔑 비밀번호 수정 (앱 암호)", value=p_info['pw'], type="password", help="네이버/Gmail 앱 암호 16자리를 입력하세요.", key=f"edit_pw_{active_p}")
                    st.caption("※ 네이버 일반 비밀번호를 입력하면 발송에 실패합니다.")
                    
                    if c_test.button("🔍 연결 테스트", key=f"test_conn_{active_p}", use_container_width=True):
                        if track_id == 'A':
                            with st.spinner("서버 연결 확인 중..."):
                                ok, msg = test_smtp_connection(active_p, new_pw_edit, p_info.get('smtp', 'smtp.naver.com'), p_info.get('port', 465))
                                if ok: st.success(msg)
                                else: st.error(msg)
                        else:
                            st.info("인스타 연결 테스트는 준비 중입니다. 발송 시작 시 확인됩니다.")

                    if c_save.button("💾 저장", key=f"save_pw_{active_p}", use_container_width=True):
                        profiles[active_p]['pw'] = new_pw_edit.strip() # [FIX] Auto-strip
                        st.session_state[p_key] = profiles
                        save_templates()
                        st.success("비밀번호가 수정되었습니다.")
                        st.session_state[f'show_manage_{active_p}'] = False
                        time.sleep(0.5)
                        st.rerun()
                    
                    if st.button("🗑️ 이 프로필 영구 삭제", use_container_width=True, key=f"del_p_{active_p}", type="secondary"):
                        del profiles[active_p]
                        st.session_state[p_key] = profiles
                        st.session_state[a_key] = ""
                        save_templates()
                        st.rerun()

        # [NEW] Test Recipient Setup (Rule 3.3)
        st.markdown("---")
        t_key = f"test_recipients_{track_id}"
        st.markdown(f"**🧪 테스트 수신자 설정 (최대 3명)**")
        st.caption("설정 후 아래 저장 버튼을 누르면 목록 상단에 '✨ [테스트]' 업체로 등록됩니다.")
        
        # Load from session state (which was loaded from file in load_templates)
        t_recs = st.session_state.get(t_key, ["", "", ""])
        
        tc1, tc2, tc3 = st.columns(3)
        placeholder = "수신 이메일 주소" if track_id == 'A' else "인스타그램 ID"
        v1 = tc1.text_input("테스트 수신자 1", value=t_recs[0], placeholder=placeholder, key=f"tr1_{track_id}")
        v2 = tc2.text_input("테스트 수신자 2", value=t_recs[1], placeholder=placeholder, key=f"tr2_{track_id}")
        v3 = tc3.text_input("테스트 수신자 3", value=t_recs[2], placeholder=placeholder, key=f"tr3_{track_id}")
        
        if st.button("🧪 테스트 수신자 적용 및 저장", key=f"btn_test_save_{track_id}", use_container_width=True):
            st.session_state[t_key] = [v1, v2, v3]
            save_templates()
            st.success("테스트 수신자가 저장되었습니다. 목록에 즉시 반영됩니다.")
            time.sleep(0.5)
            st.rerun()

        st.markdown("---")
        if track_id == 'A':
            # [MOD] Space Optimization: Subject and Save Button on same line
            c_subj, c_save = st.columns([4, 1.2], vertical_alignment="bottom")
            with c_subj:
                st.session_state['tpl_A']['subject'] = st.text_input("메일 제목", value=st.session_state['tpl_A']['subject'])
            with c_save:
                if st.button("설정 및 템플릿 저장", key=f"save_{track_id}", use_container_width=True): save_templates()
                
            st.session_state['tpl_A']['body'] = st.text_area("메일 내용", value=st.session_state['tpl_A']['body'], height=250)
            
            # [NEW] Sender Name Customization with History List
            history = st.session_state['tpl_A'].get('sender_names', [])
            current_n = st.session_state['tpl_A'].get('sender_name', '')
            
            c_sel, c_del = st.columns([4, 1], vertical_alignment="bottom")
            with c_sel:
                # Add current if not in history for the options
                opts = ["✨ 직접 입력 / 새 이름 추가"] + history
                default_idx = history.index(current_n) + 1 if current_n in history else 0
                selected_opt = st.selectbox("발신인 이름 선택", options=opts, index=default_idx)
            
            with c_del:
                if st.button("🗑️ 삭제", key="del_sender_name", use_container_width=True, disabled=(selected_opt.startswith("✨"))):
                    if selected_opt in history:
                        history.remove(selected_opt)
                        st.session_state['tpl_A']['sender_names'] = history
                        save_templates()
                        st.rerun()

            if selected_opt.startswith("✨"):
                st.session_state['tpl_A']['sender_name'] = st.text_input("새 발신인 이름 입력", 
                                                                        value=current_n if current_n not in history else "",
                                                                        placeholder="예: 마케팅몬스터 CS팀")
            else:
                st.session_state['tpl_A']['sender_name'] = selected_opt
                st.info(f"선택됨: **{selected_opt}**")

            st.caption("💡 추천 트렌드: [업체명] 담당자, [공지] 브랜드명, 이름 (직함) 등")
            st.caption("💡 {상호명} 입력 시 업체명이 자동으로 치환됩니다.")
        else:
            # [MOD] Instagram Space Optimization: Subject (Header) and Save Button on same line
            c_header, c_save = st.columns([4, 1.2], vertical_alignment="bottom")
            with c_header:
                st.markdown("**DM 메시지 내용**")
            with c_save:
                if st.button("설정 및 템플릿 저장", key=f"save_{track_id}", use_container_width=True): save_templates()

            st.session_state[f'tpl_{track_id}'] = st.text_area("DM 메시지 내용", label_visibility="collapsed", value=st.session_state.get(f'tpl_{track_id}', ''), height=200)
            st.caption("💡 {상호명} 입력 시 업체명이 자동으로 치환됩니다.")
            
            # [NEW] Beautiful Instagram DM Marketing Strategy Expander
            with st.expander("💡 인스타 DM 마케팅 성공률 300% 올리는 노하우 & 계정 관리 가이드"):
                st.markdown("""
                ### 🚀 스팸 폴더(요청함)를 피하고 오픈율을 극대화하는 계정 관리 전략
                
                인스타그램은 스팸을 방지하기 위해 매우 엄격한 필터링 시스템을 가지고 있습니다. **처음 발송을 시작하시기 전에 아래 가이드를 반드시 숙지해 주세요!**
                
                ---
                
                #### 1. 🛡️ 발송 계정 최적화 (Warm-up)
                * **활동 이력(Trust Score)이 가장 중요합니다:**
                    * 가입 후 거의 사용하지 않은 신규 계정(예: 수집 전용 계정)은 인스타 필터링 봇의 최우선 타겟입니다.
                    * **평소 다른 사람들과 디엠을 나누고, 스크롤을 내리며 좋아요를 누르던 활동적인 실사용 계정**(예: 부인분 계정)일수록 스팸 차단 필터를 가볍게 통과합니다.
                * **사람처럼 보이도록 셋팅하기 (필수):**
                    * 프로필 사진을 반드시 등록하세요 (기본 아이콘 X).
                    * 프로필 소개란에 한 줄 소개(예: "로컬 비즈니스 마케팅 컨설턴트")를 작성해 주세요.
                    * 일반 사진 게시물을 최소 2~3개 이상 등록하여 유령 계정이 아님을 증명하세요.
                
                #### 2. 📝 메시지 개인화 및 맞춤형 인사 (Personalization)
                * **기계적인 자동 발송처럼 보이지 않게 작성하기:**
                    * `{상호명}` 태그를 섞어서 발송하세요. 인스타 AI 필터는 대량의 동일 메시지를 감지하여 스팸으로 분류합니다. `{상호명}`이 들어가면 각 타겟마다 메시지가 달라지므로 차단 확률이 급격히 낮아집니다.
                    * *추천 예시: "안녕하세요 {상호명} 원장님! 피드 구경하다가 너무 멋져서 정중히 제안드리고자 연락드렸습니다..."*
                
                #### 3. 📩 "메시지 요청(Requests)"의 특성 이해
                * 서로 팔로우 관계가 아닌 상태에서 DM을 보내면, 상대방의 일반 편지함이 아닌 **[메시지 요청]** 폴더로 들어갑니다.
                * **오픈율이 매우 높습니다:** 자영업자/원장님들은 인스타 DM을 통해 실제 고객 문의가 끊임없이 들어오기 때문에, 모르는 계정의 [요청]도 **"혹시 고객 예약 문의인가?"** 하고 거의 100% 열어봅니다.
                * 따라서 첫 문장에 바로 "홍보", "광고" 보다는 **"안녕하세요 {상호명} 원장님! 문의/협업 제안 드립니다."** 처럼 자연스럽게 접근하는 것이 절대적으로 유리합니다.
                
                #### 4. 🔗 네이버 톡톡과 병행 추천
                * 인스타 DM이 없거나 닫힌 업체는 **네이버 톡톡**을 병행해 보세요. 
                * 톡톡은 사장님의 '네이버 스마트플레이스' 앱으로 즉각적인 실시간 푸시 알림이 가기 때문에 도달율과 즉각적인 오픈율이 거의 **100%**에 달합니다.
                """)

    # [DIAGNOSIS] Show DB status to user
    # --- [1] Data Loading & Variable Initialization ---
    df_fresh = load_local_data()
    total_db_rows = len(df_fresh)
    db_path = config.LOCAL_DB_PATH
    
    # Ensure t_df is ALWAYS defined
    if not df_fresh.empty and col_filter in df_fresh.columns:
        t_df = df_fresh[df_fresh[col_filter].notna() & (df_fresh[col_filter] != "")].copy()
    else:
        t_df = pd.DataFrame()

    # [NEW] Append Test Recipients for Display ONLY (Rule 3.3)
    t_key = f"test_recipients_{track_id}"
    recs = st.session_state.get(t_key, ["", "", ""])
    test_rows = []
    for i, val in enumerate(recs):
        if val:
            row = {
                "id": f"test_{i}",
                "상호명": f"✨ [테스트] 수신자 {i+1}",
                "주소": "테스트 전용",
                "번호": "010-0000-0000",
                col_filter: val,
                "결과(E)": "None", "로그(E)": "None", "결과(I)": "None", "로그(I)": "None"
            }
            test_rows.append(row)
    
    if test_rows:
        tdf_test = pd.DataFrame(test_rows)
        if t_df.empty: t_df = tdf_test
        else: t_df = pd.concat([tdf_test, t_df], ignore_index=True)

    if not t_df.empty:
        # Decide label based on current selection
        track_sel_map = st.session_state.get(f'sel_track_{track_id}', {})
        selected_count_pre = sum(1 for i in t_df.index if track_sel_map.get(str(i), False))
        
        all_selected = (selected_count_pre == len(t_df)) and (len(t_df) > 0)
        btn_label = "⬜ 전체 해제" if all_selected else "✅ 전체 선택"
        
        # [MOD] Header + Select All button on the same line (Rule: Space Optimization)
        h_col1, h_col2 = st.columns([3, 1], vertical_alignment="bottom")
        header_pos = h_col1.empty()
        
        if h_col2.button(btn_label, key=f"toggle_all_{track_id}", use_container_width=True):
            new_state = not all_selected
            for i in t_df.index: st.session_state[f'sel_track_{track_id}'][str(i)] = new_state
            st.rerun()


        st.caption(f"💡 {col_filter} 정보가 있는 업체만 표시됩니다. (전체 {total_db_rows}건 중 {len(t_df)}건)")

        t_df['선택'] = [st.session_state[f'sel_track_{track_id}'].get(str(i), False) for i in t_df.index]
        
        # Determine columns to show based on track
        display_cols = ['선택', '상호명', col_filter, '주소']
        if track_id == 'A': display_cols += ['결과(E)', '로그(E)']
        else: display_cols += ['결과(I)', '로그(I)']
        
        # [NEW] Versioned Key to force UI refresh with fresh DB data
        # This prevents the "disappearing results" issue after rerun
        editor_version = st.session_state.get(f'editor_ver_{track_id}', 0)
        
        # [NEW] Table Placeholder for real-time updates
        table_placeholder = st.empty()
        with table_placeholder:
            edited = st.data_editor(t_df[display_cols], 
                                    hide_index=True, 
                                    use_container_width=True, 
                                    key=f"editor_v{editor_version}_{track_id}")
        
        # [FIXED] Detect changes and sync back to session state immediately
        # This prevents the "disappearing checkbox" issue by ensuring the session state matches the UI
        current_sel = list(edited['선택'])
        old_sel = list(t_df['선택'])
        if current_sel != old_sel:
            for idx, val in zip(t_df.index, current_sel):
                st.session_state[f'sel_track_{track_id}'][str(idx)] = val
            st.rerun() # Force rerun to update the count header and stabilize UI
            
        # Update header placeholder with NEW count (from edited dataframe)
        new_count = len(edited[edited['선택'] == True])
        header_pos.markdown(f"**🎯 대상 리스트 ({len(t_df)}건 중 {new_count}건 선택됨)**")
        
        # --- [NEW] Persistent Results Initialization ---
        res_key = f"last_results_{track_id}"
        if res_key not in st.session_state:
            st.session_state[res_key] = {"total": 0, "success": 0, "fail": 0, "log": "발송 이력이 없습니다.", "active": False}
        
        # --- [NEW] Persistent Status Dashboard (Always Visible) ---
        res = st.session_state[res_key]
        if res['total'] > 0 or res['active']:
            st.markdown(f'<div class="section-title" style="margin-top:1.5rem;">📊 {label} 발송 현황 및 결과</div>', unsafe_allow_html=True)
            sc1, sc2, sc3 = st.columns(3, gap="small")
            sc1.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #E2E8F0;"><p class="input-label">🎯 발송 대상</p><h3 style="margin:0;">{res["total"]} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
            sc2.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #00E676;"><p class="input-label" style="color:#00E676;">✅ 발송 성공</p><h3 style="margin:0; color:#00E676;">{res["success"]} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
            sc3.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #EF4444;"><p class="input-label" style="color:#EF4444;">❌ 발송 실패</p><h3 style="margin:0; color:#EF4444;">{res["fail"]} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
            
            if not res['active']:
                st.info(f"🎉 {label} 발송이 완료되었습니다. (성공: {res['success']}건 / 실패: {res['fail']}건)")
                with st.expander("📝 마지막 발송 로그 보기"):
                    st.code(res['log'])

        # [REFIXED] Start Button & Dashboard Layout
        btn_label_final = "📧 이메일 발송 시작" if track_id == 'A' else "📸 인스타 발송 시작"
        if st.button(btn_label_final, type="primary", use_container_width=True):
            selected_all = t_df[t_df['선택'] == True]
            
            # [SMART RETRY] Filter out already successful items
            res_col = '결과(E)' if track_id == 'A' else '결과(I)'
            selected = selected_all[selected_all[res_col] != 'Success']
            skipped_count = len(selected_all) - len(selected)
            
            if selected_all.empty: 
                st.warning("선택된 대상이 없습니다.")
            elif selected.empty and skipped_count > 0:
                st.info(f"✅ 선택된 {skipped_count}건 모두 이미 발송 성공 상태입니다. (재발송 불필요)")
            else:
                if skipped_count > 0:
                    st.toast(f"💡 이미 성공한 {skipped_count}건을 제외하고 발송을 시작합니다.")
                active_p = st.session_state.get(a_key, '')
                profiles = st.session_state.get(p_key, {})
                if not active_p or active_p not in profiles:
                    st.error(f"발송 {label} 계정을 먼저 선택하거나 등록해 주세요.")
                else:
                    p_info = profiles[active_p]
                    u, p = active_p, p_info['pw']
                    
                    st.markdown("---")
                    # --- [NEW] Real-time Status Update Area ---
                    st.markdown(f'<div class="section-title" style="margin-top:1rem;">🚀 현재 작업 실시간 진행 정보</div>', unsafe_allow_html=True)
                    sc1, sc2, sc3 = st.columns(3, gap="small")
                    total_slot = sc1.empty()
                    success_slot = sc2.empty()
                    fail_slot = sc3.empty()
                    
                    # Initial UI setup
                    total_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #E2E8F0;"><p class="input-label">🎯 작업 대상</p><h3 style="margin:0;">{len(selected)} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                    success_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #00E676;"><p class="input-label" style="color:#00E676;">✅ 성공</p><h3 style="margin:0; color:#00E676;">0 <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                    fail_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #EF4444;"><p class="input-label" style="color:#EF4444;">❌ 실패</p><h3 style="margin:0; color:#EF4444;">0 <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                    
                    # Progress Bar Area
                    p_container = st.container(border=True)
                    p_info_area = p_container.empty()
                    p_bar = p_container.progress(0.0)
                    
                    log_container = st.container(border=True)
                    log_container.caption(f"📝 {label} 상세 활동 로그")
                    log_placeholder = log_container.empty()
                    log_text = ""
                    
                    success = 0
                    fail = 0
                    
                    if track_id == 'A':
                        smtp_host = p_info.get('smtp', 'smtp.naver.com')
                        
                        # Reset State for New Job
                        st.session_state[res_key] = {"total": len(selected), "success": 0, "fail": 0, "log": "이메일 엔진 가동 중...", "active": True}
                        
                        for idx, (_, s) in enumerate(selected.iterrows()):
                            # Update Progress
                            pct = (idx + 1) / len(selected)
                            p_info_area.markdown(f"**전체 발송 진행률** <span style='float:right; color:#3B82F6; font-weight:800;'>{idx+1} / {len(selected)} ({pct*100:.1f}%)</span>", unsafe_allow_html=True)
                            p_bar.progress(pct)
                            
                            current_target = s['상호명']
                            temp_log = f"⏳ `{current_target}` 발송 시도 중...\n" + log_text
                            log_placeholder.code(temp_log)
                            
                            ok, err = send_email(u, p, s['이메일'], 
                                               st.session_state['tpl_A']['subject'], 
                                               format_tpl(st.session_state['tpl_A']['body'], s['상호명']), 
                                               smtp_server=smtp_host,
                                               smtp_port=p_info.get('port', 465),
                                               sender_name=st.session_state['tpl_A'].get('sender_name', ''))
                            
                            # [NEW] Update DB Real-time using ID (Skip for virtual test rows)
                            if not str(s['id']).startswith('test_'):
                                db_h = DBHandler(config.LOCAL_DB_PATH)
                                db_h.update_send_status(s['id'], 'email', 
                                                      '성공' if ok else '실패', 
                                                      '발송완료' if ok else err)
                            
                            # [NEW] Update Table UI Real-time
                            t_df.loc[s.name, '결과(E)'] = '성공' if ok else '실패'
                            t_df.loc[s.name, '로그(E)'] = '발송완료' if ok else err
                            with table_placeholder:
                                st.data_editor(t_df[display_cols], hide_index=True, use_container_width=True, key=f"editor_live_A_{idx}_{track_id}")
                            
                            if ok: success += 1
                            else: fail += 1
                            
                            # Update Session State
                            st.session_state[res_key]['success'] = success
                            st.session_state[res_key]['fail'] = fail
                            
                            # Update Cards
                            success_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #00E676;"><p class="input-label" style="color:#00E676;">✅ 발송 성공</p><h3 style="margin:0; color:#00E676;">{success} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                            fail_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #EF4444;"><p class="input-label" style="color:#EF4444;">❌ 발송 실패</p><h3 style="margin:0; color:#EF4444;">{fail} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                            
                            status_txt = f"✅ `{current_target}` 발송 성공" if ok else f"❌ `{current_target}` 발송 실패 ({err})"
                            log_text = f"{status_txt}\n" + log_text
                            st.session_state[res_key]['log'] = log_text
                            log_placeholder.code(log_text)
                        
                        st.session_state[res_key]['active'] = False
                        st.success(f"🎊 모든 이메일 작업이 완료되었습니다! (성공: {success}, 실패: {fail})")
                        st.toast("✅ 데이터베이스 동기화 완료")
                        
                        # Increment editor version to force fresh load from DB
                        st.session_state[f'editor_ver_{track_id}'] = st.session_state.get(f'editor_ver_{track_id}', 0) + 1
                        
                        time.sleep(2) # Give user time to see the success message
                        st.rerun() 
                    else:
                        # --- Track C: Instagram DM (Real Engine Connection) ---
                        targets_data = selected.to_json(orient='records', force_ascii=False)
                        msg = st.session_state.get('tpl_C', '안녕하세요!')
                        creds = f"{u}:{p}"
                        
                        # Reset State for New Job
                        st.session_state[res_key] = {"total": len(selected), "success": 0, "fail": 0, "log": "엔진 시동 중...", "active": True}
                        
                        log_path = config.INSTA_LOG_FILE
                        with open(log_path, 'w', encoding='utf-8') as f: 
                            f.write(f"--- {label} 발송 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                        
                        is_frozen = getattr(sys, 'frozen', False)
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        
                        if is_frozen:
                            exe_path = sys.executable
                            bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(exe_path))
                            # Script is in _internal/messenger or messenger
                            script_path = os.path.join(bundle_dir, 'messenger', 'safe_messenger.py')
                            if not os.path.exists(script_path):
                                script_path = os.path.join(os.path.dirname(exe_path), '_internal', 'messenger', 'safe_messenger.py')
                        else:
                            script_path = os.path.join(base_dir, '..', 'messenger', 'safe_messenger.py')
                            
                        cmd = [sys.executable, script_path, targets_data, msg, 'insta', 'NONE', creds]
                        
                        my_env = os.environ.copy()
                        my_env["PYTHONIOENCODING"] = "utf-8"
                        my_env["PYTHONUNBUFFERED"] = "1"
                        # [FIX] Point to system-level ms-playwright browser install.
                        # The bundled playwright driver does not include browsers;
                        # they live in %LOCALAPPDATA%\ms-playwright on the user's machine.
                        system_pw_path = os.path.join(
                            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                            "ms-playwright"
                        )
                        if os.path.exists(system_pw_path):
                            my_env["PLAYWRIGHT_BROWSERS_PATH"] = system_pw_path

                        proc = subprocess.Popen(
                            cmd, 
                            cwd=os.path.dirname(script_path), 
                            env=my_env,
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                        )
                        
                        last_line_idx = 0
                        while proc.poll() is None:
                            if os.path.exists(log_path):
                                with open(log_path, 'r', encoding='utf-8') as f:
                                    lines = f.readlines()
                                    if len(lines) > last_line_idx:
                                        new_content = lines[last_line_idx:]
                                        for line in new_content:
                                            l_str = line.strip()
                                            if not l_str: continue
                                            
                                            # [NEW] Update DB Real-time for Insta
                                            if "[RESULT]" in l_str:
                                                parts = [p.strip() for p in l_str.split("|")]
                                                if len(parts) >= 4:
                                                    status = parts[1] # Success or Fail
                                                    target_name = parts[2]
                                                    err_info = parts[4] if len(parts) > 4 else "발송완료"
                                                    
                                                    if status == "Success": success += 1
                                                    else: fail += 1
                                                    
                                                    # Find shop in selected to get detail_url
                                                    match_row = selected[selected['상호명'] == target_name]
                                                    if not match_row.empty:
                                                        s_id = match_row.iloc[0]['id']
                                                        if not str(s_id).startswith('test_'):
                                                            db_h = DBHandler(config.LOCAL_DB_PATH)
                                                            db_h.update_send_status(s_id, 'insta', status, err_info)
                                                        
                                                        # [NEW] Update Table UI Real-time for Insta
                                                        t_df.loc[match_row.index[0], '결과(I)'] = '성공' if status == 'Success' else '실패'
                                                        t_df.loc[match_row.index[0], '로그(I)'] = err_info
                                                        with table_placeholder:
                                                            st.data_editor(t_df[display_cols], hide_index=True, use_container_width=True, key=f"editor_live_I_{success+fail}_{track_id}")
                                            
                                            st.session_state[res_key]['success'] = success
                                            st.session_state[res_key]['fail'] = fail
                                            log_text = f"⚙️ {l_str}\n" + log_text
                                            st.session_state[res_key]['log'] = log_text
                                            
                                            total_count = len(selected)
                                            curr_idx = min(success + fail, total_count)
                                            pct = curr_idx / total_count if total_count > 0 else 0
                                            p_info_area.markdown(f"**전체 발송 진행률** <span style='float:right; color:#3B82F6; font-weight:800;'>{curr_idx} / {total_count} ({pct*100:.1f}%)</span>", unsafe_allow_html=True)
                                            p_bar.progress(pct)
                                            
                                            success_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #00E676;"><p class="input-label" style="color:#00E676;">✅ 발송 성공</p><h3 style="margin:0; color:#00E676;">{success} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                                            fail_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #EF4444;"><p class="input-label" style="color:#EF4444;">❌ 발송 실패</p><h3 style="margin:0; color:#EF4444;">{fail} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                                            log_placeholder.code(log_text)
                                            
                                        last_line_idx = len(lines)
                            time.sleep(1)
                        
                        # Final log drain after process exit to capture the last written logs
                        if os.path.exists(log_path):
                            with open(log_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                if len(lines) > last_line_idx:
                                    new_content = lines[last_line_idx:]
                                    for line in new_content:
                                        l_str = line.strip()
                                        if not l_str: continue
                                        
                                        # [NEW] Update DB Real-time for Insta
                                        if "[RESULT]" in l_str:
                                            parts = [p.strip() for p in l_str.split("|")]
                                            if len(parts) >= 4:
                                                status = parts[1] # Success or Fail
                                                target_name = parts[2]
                                                err_info = parts[4] if len(parts) > 4 else "발송완료"
                                                
                                                if status == "Success": success += 1
                                                else: fail += 1
                                                
                                                # Find shop in selected to get detail_url
                                                match_row = selected[selected['상호명'] == target_name]
                                                if not match_row.empty:
                                                    s_id = match_row.iloc[0]['id']
                                                    if not str(s_id).startswith('test_'):
                                                        db_h = DBHandler(config.LOCAL_DB_PATH)
                                                        db_h.update_send_status(s_id, 'insta', status, err_info)
                                                    
                                                    # [NEW] Update Table UI Real-time for Insta
                                                    t_df.loc[match_row.index[0], '결과(I)'] = '성공' if status == 'Success' else '실패'
                                                    t_df.loc[match_row.index[0], '로그(I)'] = err_info
                                                    with table_placeholder:
                                                        st.data_editor(t_df[display_cols], hide_index=True, use_container_width=True, key=f"editor_live_I_{success+fail}_{track_id}_final")
                                        
                                        log_text = f"⚙️ {l_str}\n" + log_text
                                        st.session_state[res_key]['success'] = success
                                        st.session_state[res_key]['fail'] = fail
                                        st.session_state[res_key]['log'] = log_text
                                        
                                        total_count = len(selected)
                                        curr_idx = min(success + fail, total_count)
                                        pct = curr_idx / total_count if total_count > 0 else 0
                                        p_info_area.markdown(f"**전체 발송 진행률** <span style='float:right; color:#3B82F6; font-weight:800;'>{curr_idx} / {total_count} ({pct*100:.1f}%)</span>", unsafe_allow_html=True)
                                        p_bar.progress(pct)
                                        
                                        success_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #00E676;"><p class="input-label" style="color:#00E676;">✅ 발송 성공</p><h3 style="margin:0; color:#00E676;">{success} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                                        fail_slot.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #EF4444;"><p class="input-label" style="color:#EF4444;">❌ 발송 실패</p><h3 style="margin:0; color:#EF4444;">{fail} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
                                        log_placeholder.code(log_text)
                        
                        st.session_state[res_key]['active'] = False
                        st.session_state[res_key]['log'] = log_text
                        st.success(f"🎊 모든 작업이 완료되었습니다! (성공: {success}, 실패: {fail})")
                        st.toast("✅ 데이터베이스 동기화 완료")
                        
                        # Increment editor version to force fresh load from DB
                        st.session_state[f'editor_ver_{track_id}'] = st.session_state.get(f'editor_ver_{track_id}', 0) + 1
                        
                        time.sleep(2)
                        st.rerun() # Refresh to show permanent results
    
        # --- [REFINED] Global Reset Feature (Inside Expander to reduce clutter) ---
        st.markdown("---")
        with st.expander("🛠️ 데이터 및 발송 결과 관리"):
            c1, c2 = st.columns([3, 1])
            c1.caption("⚠️ 모든 업체의 발송 결과(성공/실패)와 로그를 비우고 처음부터 다시 시작하려면 리셋하세요.")
            if c2.button("🧹 발송 결과 전체 초기화", use_container_width=True, key=f"btn_reset_{track_id}", type="secondary"):
                # Use direct SQL to be 100% sure even if class import is cached/stale
                try:
                    import sqlite3
                    conn = sqlite3.connect(config.LOCAL_DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE shops SET last_result_email = NULL, last_msg_email = NULL, last_result_insta = NULL, last_msg_insta = NULL")
                    conn.commit()
                    conn.close()
                    
                    # Force UI Refresh
                    st.session_state[f'editor_ver_A'] = st.session_state.get(f'editor_ver_A', 0) + 1
                    st.session_state[f'editor_ver_C'] = st.session_state.get(f'editor_ver_C', 0) + 1
                    
                    # Clear counters and logs in session state
                    for k in list(st.session_state.keys()):
                        if k.startswith("job_res_"):
                            st.session_state[k] = {"total": 0, "success": 0, "fail": 0, "log": "", "active": False}
                    
                    st.success("✅ 모든 발송 결과와 카운트가 초기화되었습니다.")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 초기화 중 오류 발생: {e}")
    else: 
        st.info(f"{col_filter} 정보가 포함된 데이터가 없습니다.")

if st.session_state['active_page'] == 'Shop Search':
    # --- 1. Settings Panel (Top) ---
    st.markdown('<div class="section-title">⚙️ 수집 및 필터 설정</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3, gap="medium")
    u_set = st.session_state['user_settings']
    
    with c1:
        with st.container(border=True):
            st.markdown('<p class="input-label">🔍 키워드 설정 (콤마 구분)</p>', unsafe_allow_html=True)
            
            # [FIX] Enhanced Datalist & Unique ID to block unrelated browser history
            kw_history = u_set.get('kw_history', [])
            history_options = "".join([f'<option value="{kw}">' for kw in kw_history[::-1][:15]])
            st.markdown(f'<datalist id="monster_kw_datalist">{history_options}</datalist>', unsafe_allow_html=True)
            
            # Use a highly unique key to differentiate from other web inputs
            s_keyword = st.text_input("수집 키워드", key="monster_db_kw_input_v7", placeholder="예: 뷰티샵, 네일샵, 피부관리", label_visibility="collapsed", on_change=_autosave_keyword)
            
            # Robust JS to link datalist and force app-specific history
            st.components.v1.html(
                f"""
                <script>
                    const applySmartHistory = () => {{
                        const input = window.parent.document.querySelector('input[aria-label="수집 키워드"]');
                        if (input) {{
                            input.setAttribute('list', 'monster_kw_datalist');
                            input.setAttribute('autocomplete', 'on');
                            // Rename to block global history from other sites
                            input.setAttribute('name', 'monster_nplace_unique_kw');
                            input.setAttribute('id', 'monster_nplace_unique_kw');
                        }}
                    }}
                    setTimeout(applySmartHistory, 500);
                    setInterval(applySmartHistory, 2000); // Maintain state
                </script>
                """,
                height=0,
            )

            st.markdown('<p class="input-label" style="margin-top:10px;">🚫 제외 키워드 (콤마 구분)</p>', unsafe_allow_html=True)
            s_exclude = st.text_input("제외 키워드", placeholder="예: 태닝, 마사지", key="main_ex_v5", label_visibility="collapsed", on_change=_autosave_exclude)
            
            st.markdown('<p class="input-label" style="margin-top:10px;">🎯 2차 필터링 조건</p>', unsafe_allow_html=True)
            f_mode_opts = ["전체(상호/업종/메뉴 포함)", "상호명 일치", "업종명 일치"]
            saved_f_mode = u_set.get('filter_mode_ui', "전체(상호/업종/메뉴 포함)")
            s_f_mode_ui = st.selectbox("필터 모드", f_mode_opts, key="main_f_mode_v5", label_visibility="collapsed", on_change=_autosave_filter_mode)
            # [REMOVED] 필터 키워드 입력창 제거 (검색 키워드 자동 참조)
        
    with c2:
        with st.container(border=True):
            st.markdown('<p class="input-label">📍 지역 설정</p>', unsafe_allow_html=True)
            saved_provs = u_set.get('provinces', [])
            s_provinces = st.multiselect("대상 시/도", config.REGIONS_LIST, key="main_prov_v5", label_visibility="collapsed", on_change=_autosave_provinces)
            
            s_target = ""
            if s_provinces:
                all_districts = []
                for p in s_provinces:
                    if p in config.CITY_MAP:
                        for d in config.CITY_MAP[p].keys(): all_districts.append(f"[{p}] {d}")
                
                saved_dists = u_set.get('districts', [])
                s_dist_opts = sorted(all_districts)
                s_dist_defaults = [d for d in saved_dists if d in s_dist_opts]
                selected_dists = st.multiselect("상세 구역 선택 (정밀 수집)", options=s_dist_opts, key="main_dist_v5", on_change=_autosave_districts)
                targets = []
                dist_provinces = set()
                for sd in selected_dists:
                    p_name = sd.split("]")[0][1:]
                    d_name = sd.split("]")[1].strip()
                    targets.append(f"{p_name} {d_name}")
                    dist_provinces.add(p_name)
                for p in s_provinces:
                    if p not in dist_provinces: targets.append(p)
                s_target = ",".join(targets)
            else:
                st.caption("수집할 시/도를 먼저 선택해 주세요.")

        # --- [INTEGRATED] Engine Control moved here ---
        with st.container(border=True):
            st.markdown('<p class="input-label">🚀 엔진 컨트롤</p>', unsafe_allow_html=True)
            
            # 1. Explicit Save Button
            if st.button("💾 현재 설정 저장", use_container_width=True, key="save_settings_btn"):
                # Update history
                new_hist = u_set.get('kw_history', [])
                if s_keyword and s_keyword not in new_hist:
                    new_hist.append(s_keyword)
                    new_hist = new_hist[-10:] # Keep last 10
                
                save_settings({
                    'keyword': s_keyword,
                    'exclude': s_exclude,
                    'filter_mode_ui': s_f_mode_ui,
                    'filter_keyword': "",
                    'provinces': s_provinces,
                    'districts': selected_dists if s_provinces else [],
                    'kw_history': new_hist
                })
                st.success("✅ 설정이 안전하게 저장되었습니다!")
                time.sleep(1)
                st.rerun()

            
            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
            
            # [FIXED] Persistent starting state until PID is detected
            pid = get_engine_pid()
            if pid:
                st.session_state['engine_starting'] = False
            
            if st.session_state.get('engine_starting', False) and not pid:
                st.button("⏳ 엔진 시동 중...", disabled=True, use_container_width=True)
                time.sleep(1) # Wait for PID file creation
                st.rerun()
            elif pid:
                if st.button("🔴 엔진 가동 정지", use_container_width=True, key="stop_btn_v5"):
                    if stop_engine(): st.rerun()
                st.markdown(f'<div style="text-align:center; padding:10px; background:#F1F5F9; border-radius:10px; border:1px solid #E2E8F0;"><p style="margin:0; font-size:0.7rem; color:#64748B; font-weight:800;">ID: {pid} 엔진 작동 중</p></div>', unsafe_allow_html=True)
            else:
                if st.button("🟢 데이터 수집 시작", type="primary", use_container_width=True, key="start_btn_v5"):
                    if s_keyword and s_target:
                        # Update history
                        new_hist = u_set.get('kw_history', [])
                        if s_keyword and s_keyword not in new_hist:
                            new_hist.append(s_keyword)
                            new_hist = new_hist[-10:]
                        
                        st.session_state['engine_starting'] = True
                        save_settings({
                            'keyword': s_keyword, 'exclude': s_exclude, 'filter_mode_ui': s_f_mode_ui,
                            'filter_keyword': "", 'provinces': s_provinces, 'districts': selected_dists if s_provinces else [],
                            'kw_history': new_hist
                        })
                        limit = AuthManager.get_collection_limit()
                        is_paid = AuthManager.check_license_status() and AuthManager.get_serial_key() != "TRIAL-MODE"
                        final_limit = limit if limit else (99999 if is_paid else 50)
                        filter_mode_map = {"전체(상호/업종/메뉴 포함)": "all", "상호명 일치": "name", "업종명 일치": "category"}
                        f_mode = filter_mode_map.get(s_f_mode_ui, "all")
                        st.session_state['completion_shown'] = False
                        st.session_state['celebration_fired'] = False # [NEW] Reset celebration flag
                        run_engine_cmd(s_target, final_limit, s_keyword, filter_mode=f_mode, filter_keyword=s_keyword)
                        st.rerun()
                    else: st.warning("키워드와 지역을 설정해 주세요.")

    with c3:
        with st.container(border=True):
            st.markdown('<p class="input-label">🗄️ 데이터/DB 관리</p>', unsafe_allow_html=True)
            
            db_path = config.LOCAL_DB_PATH
            exists = os.path.exists(db_path)
            
            # File Info
            st.markdown(f"<div style='font-size:0.75rem; color:#64748B;'><b>경로:</b> {db_path}</div>", unsafe_allow_html=True)
            if exists:
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                mtime = datetime.fromtimestamp(os.path.getmtime(db_path)).strftime('%Y-%m-%d %H:%M')
                st.markdown(f"<div style='font-size:0.75rem; color:#64748B;'>파일: 존재함 · 크기: {size_mb:.2f}MB · 수정: {mtime}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='font-size:0.75rem; color:#EF4444;'>파일: 없음 (수집 시 자동 생성)</div>", unsafe_allow_html=True)
            
            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
            
            # Stats
            db_count = len(df) if not df.empty else 0
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown(f"<div class='status-card' style='text-align:center;'><p class='input-label'>총 업체수</p><h3 style='margin:0;'>{db_count}</h3></div>", unsafe_allow_html=True)
            with sc2:
                # Last saved time from DB if possible
                last_time = "-"
                if not df.empty and 'updated_at' in df.columns:
                     try: last_time = pd.to_datetime(df['updated_at']).max().strftime('%H:%M')
                     except: pass
                st.markdown(f"<div class='status-card' style='text-align:center;'><p class='input-label'>마지막 저장</p><h3 style='margin:0; font-size:1.1rem;'>{last_time}</h3></div>", unsafe_allow_html=True)

            if st.button("🧹 DB 초기화 (전체 삭제)", use_container_width=True, key="reset_db_btn"):
                if exists:
                    # 1. Backup & Remove DB
                    backup_path = db_path + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    os.rename(db_path, backup_path)
                    
                    # 2. Reset Progress Info (Using Config Path)
                    if os.path.exists(config.PROGRESS_FILE):
                        try: os.remove(config.PROGRESS_FILE)
                        except: pass
                    
                    # 3. Clear Engine Logs (Using Config Path)
                    if os.path.exists(config.ENGINE_LOG_FILE):
                        try:
                            with open(config.ENGINE_LOG_FILE, "w", encoding="utf-8") as f: f.write("")
                        except: pass
                        
                    st.success("데이터 및 현황이 초기화되었습니다. (전체 리셋 완료)")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info("초기화할 DB 파일이 없습니다.")
    # --- 2. Live Monitoring Section ---
    st.markdown('<div class="section-title" style="margin-top:1rem;">📊 실시간 수집 상세 현황</div>', unsafe_allow_html=True)
    prog = get_crawler_progress() or {}
    
    # [NEW] Track engine state transition
    if pid: st.session_state['engine_active_last'] = True

    # [NEW] Robust Completion Detection (Monster Rule 3.3)
    is_explicit_done = (prog.get("status") == "completed")
    # Percentage fallback
    is_pct_done = (prog.get("success_count", 0) >= prog.get("estimated_total", 1) and prog.get("estimated_total", 0) > 0)
    # Transition fallback: Engine stopped after being active, and we have data
    is_stopped_after_active = (pid is None and st.session_state.get('engine_active_last', False) and prog.get("success_count", 0) > 0)
    
    is_completed = is_explicit_done or is_pct_done or is_stopped_after_active

    if is_completed and not st.session_state.get("completion_shown", False):
        # [NEW] Reset transition flag on completion
        st.session_state['engine_active_last'] = False
        # [NEW] Celebration fires only ONCE per collection session
        if not st.session_state.get("celebration_fired", False):
            st.balloons()
            st.snow()
            st.session_state["celebration_fired"] = True
            
            # Force Scroll to Top so the modal is visible (only on first fire)
            st.components.v1.html(
                "<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);</script>",
                height=0
            )
        
        # [NEW] Premium Completion Modal
        with st.container(border=True):
            col1, col2 = st.columns([0.1, 0.9])
            with col1: st.title("🎉")
            with col2:
                st.markdown(f"### 수집이 모두 완료되었습니다!")
                st.markdown(f"**총 {prog.get('success_count', 0)}건**의 데이터가 성공적으로 수집 및 저장되었습니다.")
                st.info("아래 [실시간 수집 데이터 현황] 우측의 '📥 엑셀 다운로드' 버튼을 눌러 결과를 확인하세요.")
                if st.button("✅ 확인 (닫기)", type="primary", use_container_width=True):
                    st.session_state["completion_shown"] = True
                    st.rerun()
        st.markdown("---")

    
    is_completed = prog.get("status") == "completed"
    # 2.1 Four Status Cards
    sc1, sc2, sc3, sc4 = st.columns(4, gap="small")
    with sc1:
        total_val = prog.get("success_count", 0) if is_completed else prog.get("estimated_total", 0)
        total_disp = f"{total_val} <span style='font-size:0.8rem; color:#94A3B8;'>건</span>" if total_val > 0 else "<span style='font-size:1.2rem;'>계산 중...</span>"
        st.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #E2E8F0;"><p class="input-label">최종 수집 대상 수</p><h3 style="margin:0;">{total_disp}</h3></div>' if is_completed else f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #E2E8F0;"><p class="input-label">예상 대상 수 (추정)</p><h3 style="margin:0;">{total_disp}</h3></div>', unsafe_allow_html=True)
    with sc2:
        st.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #00E676;"><p class="input-label" style="color:#00E676;">현재 수집 개수</p><h3 style="margin:0; color:#00E676;">{prog.get("success_count", 0)} <span style="font-size:0.8rem; color:#94A3B8;">건</span></h3></div>', unsafe_allow_html=True)
    with sc3:
        st.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #3B82F6;"><p class="input-label">총 소요 시간</p><h3 style="margin:0;">{prog.get("elapsed_time", "0초")}</h3></div>', unsafe_allow_html=True)
    with sc4:
        st.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #F59E0B;"><p class="input-label" style="color:#F59E0B;">예상 남은 시간</p><h3 style="margin:0; color:#F59E0B;">{prog.get("remaining_time", "0초")}</h3></div>', unsafe_allow_html=True)

    # 2.2 Progress & Detailed Metrics
    with st.container(border=True):
        total = prog.get("estimated_total", 0)
        current = prog.get("success_count", 0)
        pct = 100.0 if is_completed else ((current / total * 100) if total > 0 else 0.0)
        
        col_p1, col_p2 = st.columns([4, 1])
        col_p1.markdown(f"**전체 완료율 (추정)**")
        total_str = str(total) if total > 0 else "?"
        disp_total = current if is_completed else total_str
        col_p2.markdown(f"<div style='text-align:right; color:#00E676; font-weight:800;'>{current} / {disp_total} ({pct:.1f}%)</div>", unsafe_allow_html=True)
        st.progress(pct/100 if pct <= 100 else 1.0)
        
        col_m1, col_m2 = st.columns(2)
        avg_time = prog.get("avg_time_per_item", "0.0")
        stage = prog.get("current_stage", "엔진 준비 중...")
        col_m1.markdown(f"<span style='color:#64748B; font-size:0.85rem;'>개당 평균 소요: **{avg_time}초/건**</span>", unsafe_allow_html=True)
        col_m2.markdown(f"<div style='text-align:right; color:#64748B; font-size:0.85rem;'>현재 수집 구간: **{stage}**</div>", unsafe_allow_html=True)
        
        st.markdown("<p style='font-size:0.75rem; color:#94A3B8; margin-top:5px;'>* 총 예상 대상 수는 추정치이며, 수집이 진행될수록 정확도가 올라갑니다. (초기 추정)</p>", unsafe_allow_html=True)

    # 2.3 [NEW] Live Log Monitor with Scroll & Copy
    with st.expander("📝 실시간 엔진 로그 (전체 모니터링)", expanded=pid is not None):
        logs = get_live_logs(1000)
        
        c_log1, c_log2 = st.columns([4, 1.2])
        with c_log1:
            st.caption("🔄 수집 중: 5초마다 자동 갱신됩니다.")
        with c_log2:
            if st.button("📋 로그 복사 및 고객센터", use_container_width=True):
                # JavaScript를 이용한 클립보드 복사 (Streamlit용 꼼수)
                st.write(f'<script>navigator.clipboard.writeText(`{logs}`);</script>', unsafe_allow_html=True)
                st.toast("로그가 클립보드에 복사되었습니다!")
                time.sleep(1)
                # 허브 앱 고객센터로 이동 (이메일 파라미터 포함)
                support_url = f"https://3monster-hub.netlify.app/#/support?email={st.session_state.get('email_user', '')}"
                st.markdown(f'<a href="{support_url}" target="_blank" id="go_support">이동 중...</a>', unsafe_allow_html=True)
                st.write(f'<script>document.getElementById("go_support").click();</script>', unsafe_allow_html=True)

        # 스크롤 가능한 로그 박스 출력
        st.markdown(f'<div class="log-container">{logs}</div>', unsafe_allow_html=True)
        
        # [FIXED] More visible and robust status signaling (Monster Rule 3.2)
        if pid:
            st.markdown(f'<div style="display:flex; align-items:center; gap:8px; margin-top:8px;"><div class="live-dot"></div><span style="color:#00E676; font-weight:800; font-size:0.85rem;">실시간 수집 중: 5초마다 자동 갱신</span></div>', unsafe_allow_html=True)
        else:
            st.caption("🔄 엔진이 정지 상태입니다.")

    # [NEW] Moved st_autorefresh outside expander to ensure global dashboard updates
    if pid:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=5000, limit=None, key="engine_autorefresh_global_v1")

    st.markdown("---")
    if not df.empty:
        # [NEW] Table Header & Download Button at Top-Right
        t_col1, t_col2 = st.columns([3, 1])
        with t_col1:
            st.markdown('<h3 style="margin:0; padding-top:10px; color:#1E293B;">📊 실시간 수집 데이터 현황</h3>', unsafe_allow_html=True)
        with t_col2:
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 엑셀(CSV) 다운로드",
                data=csv_data,
                file_name=f"NPlace_DB_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="top_dl_btn"
            )
        
        st.dataframe(df[['No', '상호명', '주소', '번호', '이메일', '인스타']], hide_index=True, use_container_width=True, height=600)
    else: 
        st.info("데이터가 없습니다.")

elif st.session_state['active_page'] == 'Track A': render_track('A', '이메일 마케팅', '이메일', '메일 서버', df)
elif st.session_state['active_page'] == 'Track C': render_track('C', '인스타 DM 마케팅', '인스타', 'DM 서버', df)
elif st.session_state['active_page'] == 'Guide':
    st.markdown('<div class="section-title">📖 NPlace-DB 공식 가이드</div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.subheader(" 이메일 마케팅 설정 (네이버 SMTP)")
        
        st.error("""
        **[중요] 로그인 실패(535) 해결 방법**  
        네이버 비밀번호를 그대로 입력하면 보안상 발송이 차단됩니다. 반드시 아래 **2단계 가이드**를 따라 **'앱 암호'**를 발급받아 입력해 주세요!
        """)
        
        st.markdown("""
        이메일 발송 기능을 사용하려면 본인의 네이버 계정에서 **SMTP 사용 설정**과 **앱 암호 발급**이 반드시 필요합니다.
        
        #### **1단계: 네이버 메일 SMTP 설정 활성화**
        1. PC에서 [네이버 메일]에 접속합니다.
        2. 왼쪽 메뉴 하단의 **[환경설정]** (톱니바퀴 아이콘)을 클릭합니다.
        3. 상단 탭에서 **[POP3/IMAP 설정]**을 클릭합니다.
        4. **[IMAP/SMTP 설정]** 탭으로 이동합니다.
        5. 'IMAP/SMTP 사용' 항목을 **[사용함]**으로 변경하고 확인을 누릅니다.
        
        #### **2단계: 네이버 앱 암호 발급 (필수)**
        일반 비밀번호는 보안상 차단될 수 있으므로, 반드시 '앱 암호'를 생성해야 합니다.
        1. [네이버 내정보] -> [보안설정] 메뉴로 이동합니다.
        2. **[2단계 인증]** 항목 우측의 **[관리]** 버튼을 클릭합니다. (2단계 인증이 안 되어 있다면 먼저 설정해 주세요.)
        3. 이동한 페이지의 **맨 아래쪽**으로 스크롤을 내리면 **[비밀번호 관리 (앱 암호)]** 섹션이 나타납니다.
        4. 종류 선택에서 '직접 입력'을 누르고 **'NPlaceDB'**라고 입력한 뒤 **[생성]**을 클릭합니다.
        5. 생성된 **16자리 영문 앱 암호**를 복사하여 프로그램의 '비밀번호' 칸에 입력하세요.
        
        ---
        #### **기타 SMTP 설정 안내**
        *   **Gmail**: 구글 계정 설정에서 '앱 비밀번호' 생성이 필수입니다.
        *   **Daum/Hanmail**: 카카오 통합 계정 설정에서 앱 비밀번호를 생성해야 합니다.
        """)
        
        st.divider()
        st.subheader(" 인스타 DM 마케팅 가이드")
        st.markdown("""
        인스타그램 마케팅 엔진은 **진짜 브라우저**를 띄워 자동으로 전송하는 고성능 엔진입니다.
        
        #### **1단계: 인스타 계정 등록**
        1. **[인스타]** 탭 상단의 **[계정 추가]**를 눌러 본인의 인스타 ID와 비밀번호를 등록하세요.
        2. 여러 개의 계정을 등록하고 **드롭다운 메뉴**를 통해 발송 주체를 자유롭게 바꿀 수 있습니다.
        
        #### **2단계: 첫 실행 시 로그인 인증**
        1. 발송 시작을 누르면 백그라운드에서 브라우저가 실행됩니다.
        2. **처음 사용하는 계정**일 경우, 인스타 보안 정책에 따라 **로그인 인증**이 필요할 수 있습니다. 
        3. 실시간 로그창의 안내를 확인하며, 필요시 브라우저 창에서 직접 로그인을 완료해 주세요. (한 번 로그인하면 세션이 저장되어 다음부터는 자동으로 진행됩니다.)
        
        #### **3단계: [실전 노하우] 스팸 폴더를 피하고 성공율 300% 올리는 노하우**
        *   **발송 계정 최적화 (Warm-up)**:
            *   가입 후 거의 사용하지 않은 신규 계정(예: 수집 전용 계정)은 인스타 필터링 봇의 최우선 타겟입니다.
            *   **평소 다른 사람들과 디엠을 나누고, 스크롤을 내리며 좋아요를 누르던 활동적인 실사용 계정**일수록 스팸 차단 필터를 가볍게 통과합니다.
            *   계정에 **프로필 사진을 등록**하고, 소개란을 채우며, 일반 사진 게시물을 2~3개 올려 신뢰성 있는 계정으로 만드세요.
        *   **메시지 개인화**:
            *   동일한 메시지만 계속 대량 발송하면 인스타 필터링 봇에 걸립니다. 본문에 `{상호명}` 태그를 섞어서 발송하면 각 업체마다 내용이 바뀌므로 스팸 차단 확률이 극적으로 줄어듭니다.
        *   **"메시지 요청(Requests)"의 특성**:
            *   서로 팔로우 관계가 아닌 상태에서 DM을 보내면 상대방의 일반 편지함이 아닌 **[메시지 요청]** 폴더로 들어갑니다.
            *   자영업자/원장님들은 인스타 DM을 통해 실제 고객 문의가 끊임없이 들어오기 때문에, 모르는 계정의 [요청]도 **"혹시 고객 예약 문의인가?"** 하고 거의 100% 열어봅니다.
            *   따라서 첫 문장에 바로 "홍보", "광고" 보다는 **"안녕하세요 {상호명} 원장님! 문의/협업 제안 드립니다."** 처럼 자연스럽게 접근하는 것이 절대적으로 유리합니다.
        *   **네이버 톡톡과 병행 추천**:
            *   인스타 DM이 없거나 닫힌 업체는 **네이버 톡톡**을 병행해 보세요. 톡톡은 사장님의 '네이버 스마트플레이스' 앱으로 즉각적인 실시간 푸시 알림이 가기 때문에 도달율과 즉각적인 오픈율이 거의 **100%**에 달합니다.
        """)
        
        st.divider()
        st.subheader(" 데이터 저장 위치 및 관리")
        st.markdown(f"""
        본 프로그램의 모든 데이터와 설정은 아래 경로에 안전하게 저장됩니다.
        
        *   **수집 데이터베이스 (DB)**: 
            `{config.LOCAL_DB_PATH}`
            *   *설명: 수집된 업체 정보 및 발송 결과(성공/실패/로그)가 실시간으로 저장되는 SQLite 파일입니다.*
        *   **마케팅 템플릿 및 계정**: 
            `{os.path.abspath(TEMPLATE_FILE)}`
            *   *설명: 저장하신 이메일/인스타 메시지 내용과 계정 정보가 암호화되어 저장됩니다.*
        *   **수집 엔진 로그**: 
            `{config.ENGINE_LOG_FILE}`
            *   *설명: 수집 과정에서 발생하는 상세 로그가 기록됩니다.*
            
        > **[TIP]**: 다른 PC로 데이터를 옮기고 싶으시다면 위 `data` 폴더 전체를 복사하여 동일한 위치에 붙여넣으시면 됩니다.
        """)
        
        st.divider()
        st.subheader(" PC 권장 사양 및 환경")
        st.markdown("""
        *   **CPU**: Intel Core i5 / AMD Ryzen 5 이상
        *   **RAM**: 8GB 이상 (16GB 권장)
        *   **OS**: Windows 10/11 (64bit)
        *   **Browser**: 최신 버전의 Google Chrome 설치 필수
        """)

