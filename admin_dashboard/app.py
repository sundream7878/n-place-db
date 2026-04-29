import streamlit as st
import pandas as pd
import os
import json
import time
import subprocess
import sys
import hashlib
import smtplib
import importlib
from streamlit_autorefresh import st_autorefresh
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# Ensure parent directory is in path to import config
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
importlib.reload(config) # [CRITICAL] Pick up newly added attributes

from sb_auth_manager import SupabaseAuthManager as AuthManager
from crawler.local_db_handler import LocalDBHandler as DBHandler

# --- 1. Setup & Functions ---
TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "templates.json")

def load_templates():
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {
        "email_profiles": {}, 
        "active_email_profile": "",
        "naver_user": "", "naver_pw": "", "insta_user": "", "insta_pw": "",
        "tpl_A": {"subject": "안녕하세요, {상호명} 원장님!", "body": "원장님 안녕하세요! 마케팅 몬스터입니다."},
        "tpl_B": "안녕하세요! 네이버 톡톡 메시지입니다.",
        "tpl_C": "인스타그램 DM 메시지입니다."
    }

def save_templates():
    data = {
        "email_profiles": st.session_state.get('email_profiles', {}),
        "active_email_profile": st.session_state.get('active_email_profile', ''),
        "naver_user": st.session_state.get('naver_user', ''),
        "naver_pw": st.session_state.get('naver_pw', ''),
        "insta_user": st.session_state.get('insta_user', ''),
        "insta_pw": st.session_state.get('insta_pw', ''),
        "tpl_A": st.session_state.get('tpl_A', {}),
        "tpl_B": st.session_state.get('tpl_B', ''),
        "tpl_C": st.session_state.get('tpl_C', '')
    }
    with open(TEMPLATE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    st.toast("설정이 저장되었습니다.")

def load_local_data():
    db_h = DBHandler(config.LOCAL_DB_PATH)
    data = db_h.get_all_shops()
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    # [NEW] Insert 'No' column at the very beginning
    df.insert(0, "No", range(1, len(df) + 1))
    
    # Map DB columns to UI Korean Labels
    mapping = {
        "name": "상호명", "address": "주소", "phone": "번호", 
        "email": "이메일", "instagram_handle": "인스타", 
        "talk_url": "톡톡링크", "detail_url": "플레이스링크"
    }
    df = df.rename(columns=mapping)
    return df

def get_engine_pid():
    pid_file = os.path.join(config.LOCAL_LOG_PATH, "engine.pid")
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            try:
                pid = int(f.read().strip())
                import psutil
                if psutil.pid_exists(pid): return pid
            except: pass
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
    # Directly call the crawler engine script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.abspath(os.path.join(base_dir, '..', 'step1_refined_crawler.py'))
    
    # Arguments: target, count, shop_type
    cmd = [sys.executable, script_path, target, str(limit), keyword]
    
    if filter_mode != "all":
        cmd.extend(["--filter-mode", filter_mode, "--filter-keyword", filter_keyword])
    
    # Launch directly without hiding anything to debug 'stuck' issues
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(script_path))
    
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
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # 최신 1000줄로 확장하여 전체 흐름 파악 가능하게 변경
                return "".join(lines[-n:])
        except: return "로그를 읽는 중 오류 발생"
    return "수집 로그가 아직 없습니다."

def send_email(user, pw, target, subject, body, smtp_server="smtp.naver.com", attachments=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = target
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        if attachments:
            for att in attachments:
                part = MIMEApplication(att['content'], Name=att['name'])
                part['Content-Disposition'] = f'attachment; filename="{att["name"]}"'
                msg.attach(part)
        
        with smtplib.SMTP_SSL(smtp_server, 465) as server:
            server.login(user, pw)
            server.send_message(msg)
        return True, None
    except Exception as e: return False, str(e)

def format_tpl(text, shop_name):
    if not text: return ""
    return text.replace("{상호명}", shop_name if shop_name else "원장님")

# --- UI Configuration ---
st.set_page_config(page_title=f"[{config.BRAND_NAME_KR}] Pro", page_icon="👹", layout="wide")

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
    // Force the browser window to top-left and resize it to wide layout
    window.parent.moveTo(0, 0);
    window.parent.resizeTo(1300, 1050);
    </script>
    """,
    height=0,
    width=0
)

# --- Global CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    .stApp { background-color: #F8FAFC; font-family: 'Pretendard', sans-serif; }
    
    .section-container {
        background: white; border: 1px solid #E2E8F0; border-radius: 15px; padding: 1.5rem; margin-bottom: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }
    .section-title { font-size: 1.1rem; font-weight: 800; color: #1E293B; margin-bottom: 1rem; display: flex; align-items: center; gap: 8px; }
    .input-label { font-size: 0.85rem; font-weight: 700; color: #64748B; margin-bottom: 5px; }
    .status-card { background: #F1F5F9; border-radius: 10px; padding: 1rem; border: 1px solid #E2E8F0; }
    .live-dot { height: 10px; width: 10px; background-color: #00E676; border-radius: 50%; display: inline-block; margin-right: 8px; box-shadow: 0 0 8px #00E676; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { transform: scale(0.95); opacity: 0.7; } 70% { transform: scale(1.1); opacity: 1; } 100% { transform: scale(0.95); opacity: 0.7; } }
    
    /* 로그 스크롤 박스 전용 스타일 */
    .log-container {
        background-color: #0F172A;
        color: #E2E8F0;
        padding: 15px;
        border-radius: 10px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.85rem;
        height: 400px;
        overflow-y: scroll;
        white-space: pre-wrap;
        line-height: 1.5;
        border: 1px solid #334155;
    }
    /* 버튼 글자 찌그러짐 방지 */
    .stButton button { white-space: nowrap !important; }

    /* [NEW] Sticky Header 스타일 */
    [data-testid="stHeader"] { background: rgba(255,255,255,0.8); backdrop-filter: blur(10px); }
    
    /* 상단 및 하단 기본 여백 조정 */
    .block-container { padding-top: 0rem !important; padding-bottom: 10rem !important; }
    [data-testid="stVerticalBlockBorderWrapper"] > div:nth-child(1) { margin-top: 0 !important; }
    
    /* 버튼이 바닥에 붙지 않도록 섹션 간격 조정 */
    .stButton { margin-top: 2rem !important; margin-bottom: 2rem !important; }

    /* [FIXED] 초강력 Sticky Header - 특정 클래스나 ID 없이 영역 기반으로 타겟팅 */
    [data-testid="stVerticalBlock"] > div:has(.nav-anchor) {
        position: sticky;
        top: 0; /* 최상단 밀착 */
        z-index: 1000;
        background-color: white;
        padding-top: 15px;
        padding-bottom: 15px;
        border-bottom: 3px solid #00E676;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .nav-anchor { display: none; } /* 앵커용 가상 요소 */
    </style>
    
    <script>
    // Aggressive Autocomplete Blocker
    document.addEventListener('DOMContentLoaded', function() {
        const inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
            input.setAttribute('autocomplete', 'new-password');
            input.setAttribute('spellcheck', 'false');
        });
        
        // Repeatedly check for new inputs (Streamlit re-renders)
        setInterval(() => {
            document.querySelectorAll('input').forEach(input => {
                if (input.getAttribute('autocomplete') !== 'new-password') {
                    input.setAttribute('autocomplete', 'new-password');
                    input.setAttribute('spellcheck', 'false');
                }
            });
        }, 1000);
    });
    </script>
""", unsafe_allow_html=True)

# Header & Nav (Sticky Container)
with st.container():
    st.markdown('<div class="nav-anchor"></div>', unsafe_allow_html=True) # Sticky를 위한 앵커
    col_logo, col_nav = st.columns([1.8, 4], vertical_alignment="center")
    with col_logo:
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "MarketingMonster_logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=180)
        
        st.markdown("""
            <div style="display:flex; flex-direction:column; gap:0px; margin-top:-10px;">
                <div style="font-size:2.2rem; font-weight:900; color:#00E676; letter-spacing:-1.5px;">NPlace_DB</div>
                <div style="font-size:0.8rem; color:#64748B; font-weight:800; letter-spacing:0.05em; margin-top:-5px;">대한민국 NO.1 마케팅 솔루션</div>
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
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'crawler_settings.json')

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
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except: pass

# Initial Settings Load
if 'user_settings' not in st.session_state:
    st.session_state['user_settings'] = load_settings()

def render_track(track_id, label, col_filter, cfg_name, df_in):
    st.markdown(f"#### 🚀 {label}")
    with st.expander(f"⚙️ {cfg_name} 및 템플릿 설정", expanded=True):
        c1, c2 = st.columns(2)
        if track_id == 'A':
            st.warning("⚠️ 발송 전 반드시 [📖 가이드] 메뉴에서 **네이버 SMTP 설정법**을 확인해 주세요!")
            
            # --- [NEW] Improved Multi-Profile Management ---
            profiles = st.session_state.get('email_profiles', {})
            p_list = list(profiles.keys())
            
            c_sel, c_add = st.columns([3, 1])
            with c_sel:
                active_p = st.session_state.get('active_email_profile', '')
                sel_p = st.selectbox("📧 등록된 발송 프로필 선택", options=p_list, 
                                     index=p_list.index(active_p) if active_p in p_list else None,
                                     placeholder="발송할 계정을 선택하세요", key="email_profile_selector")
                if sel_p: st.session_state['active_email_profile'] = sel_p

            with c_add:
                st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
                show_add = st.checkbox("➕ 새 계정 추가", value=False if p_list else True)

            if show_add:
                with st.container(border=True):
                    st.markdown("**✨ 새로운 발송 계정 등록**")
                    c1, c2 = st.columns(2)
                    new_id = c1.text_input("발송용 이메일 ID", placeholder="example@naver.com", key="new_email_id_v2")
                    new_pw = c2.text_input("비밀번호 (앱 암호)", type="password", key="new_email_pw_v2")
                    
                    # Auto-detect SMTP
                    def_smtp, def_port = "smtp.naver.com", 465
                    if "@gmail.com" in new_id.lower(): def_smtp, def_port = "smtp.gmail.com", 465
                    elif "@daum.net" in new_id.lower() or "@hanmail.net" in new_id.lower(): def_smtp, def_port = "smtp.daum.net", 465
                    elif "@naver.com" in new_id.lower(): def_smtp, def_port = "smtp.naver.com", 465
                    
                    sc1, sc2 = st.columns(2)
                    sc1.text_input("SMTP 서버 (자동 감지)", value=def_smtp, disabled=True, key="auto_smtp")
                    sc2.number_input("SMTP 포트 (자동 감지)", value=def_port, disabled=True, key="auto_port")
                    
                    if st.button("💾 이 계정 저장하기", use_container_width=True):
                        if new_id and new_pw:
                            profiles[new_id] = {"pw": new_pw, "smtp": def_smtp, "port": def_port}
                            st.session_state['email_profiles'] = profiles
                            st.session_state['active_email_profile'] = new_id
                            save_templates()
                            st.success(f"'{new_id}' 계정이 등록되었습니다.")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("ID와 비밀번호를 입력해 주세요.")
            
            # Show selected profile info
            active_p = st.session_state.get('active_email_profile', '')
            if active_p and active_p in profiles:
                p_info = profiles[active_p]
                with st.container(border=True):
                    c_info, c_manage = st.columns([4, 1.2], vertical_alignment="center")
                    c_info.info(f"✅ **발송 대기:** `{active_p}` ({p_info['smtp']})")
                    
                    # [FIXED] Toggle button label based on state
                    is_open = st.session_state.get(f'show_manage_{active_p}', False)
                    btn_label = "❌ 관리창 닫기" if is_open else "🛠️ 계정 관리"
                    if c_manage.button(btn_label, key=f"btn_manage_{active_p}", use_container_width=True):
                        st.session_state[f'show_manage_{active_p}'] = not is_open
                        st.rerun()
                    
                    if is_open:
                        st.markdown("---")
                        c_pw, c_btn = st.columns([3, 1], vertical_alignment="bottom")
                        new_pw_edit = c_pw.text_input("🔑 비밀번호(앱 암호) 수정", value=p_info['pw'], type="password", key=f"edit_pw_{active_p}")
                        if c_btn.button("💾 저장", key=f"save_pw_{active_p}", use_container_width=True):
                            profiles[active_p]['pw'] = new_pw_edit
                            st.session_state['email_profiles'] = profiles
                            save_templates()
                            st.success("비밀번호가 수정되었습니다.")
                            st.session_state[f'show_manage_{active_p}'] = False
                            time.sleep(0.5)
                            st.rerun()
                        
                        if st.button("🗑️ 이 프로필 영구 삭제", use_container_width=True, key=f"del_p_{active_p}", type="secondary"):
                            del profiles[active_p]
                            st.session_state['email_profiles'] = profiles
                            st.session_state['active_email_profile'] = ""
                            save_templates()
                            st.rerun()

            st.markdown("---")
            st.session_state['tpl_A']['subject'] = st.text_input("메일 제목", value=st.session_state['tpl_A']['subject'])
            st.session_state['tpl_A']['body'] = st.text_area("본문 ({상호명} 치환)", value=st.session_state['tpl_A']['body'], height=200)

        elif track_id == 'B':
            st.session_state['naver_user'] = c1.text_input("Naver ID", value=st.session_state.get('naver_user',''))
            st.session_state['naver_pw'] = c2.text_input("비밀번호", type="password", value=st.session_state.get('naver_pw',''))
            st.session_state['tpl_B'] = st.text_area("톡톡 메시지", value=st.session_state.get('tpl_B',''), height=200)
        else:
            st.session_state['insta_user'] = c1.text_input("Insta ID", value=st.session_state.get('insta_user',''))
            st.session_state['insta_pw'] = c2.text_input("비밀번호", type="password", value=st.session_state.get('insta_pw',''))
            st.session_state['tpl_C'] = st.text_area("DM 메시지", value=st.session_state.get('tpl_C',''), height=200)
        
        if st.button("설정 및 템플릿 저장", key=f"save_{track_id}", use_container_width=True): save_templates()

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
    
    if not t_df.empty:
        # [NEW] Smart Toggle Selection Button
        sel_col1, sel_col2, sel_spacer = st.columns([1, 1.5, 4])
        if sel_col1.button("🔄 데이터 갱신", key=f"refresh_{track_id}", use_container_width=True):
            st.session_state[f'sel_track_{track_id}'] = {} # Reset selection
            st.rerun()

        # Decide label based on current selection
        track_sel_map = st.session_state.get(f'sel_track_{track_id}', {})
        selected_count_pre = sum(1 for i in t_df.index if track_sel_map.get(str(i), False))
        
        all_selected = (selected_count_pre == len(t_df)) and (len(t_df) > 0)
        btn_label = "⬜ 전체 선택 해제" if all_selected else "✅ 전체 선택"
        
        if sel_col2.button(btn_label, key=f"toggle_all_{track_id}", use_container_width=True):
            new_state = not all_selected
            for i in t_df.index: st.session_state[f'sel_track_{track_id}'][str(i)] = new_state
            st.rerun()

        # [REFIXED] Use placeholder to avoid "one-step behind" count issue
        header_pos = st.empty()
        st.caption(f"💡 {col_filter} 정보가 있는 업체만 표시됩니다. (전체 {total_db_rows}건 중 {len(t_df)}건)")

        t_df['선택'] = [st.session_state[f'sel_track_{track_id}'].get(str(i), False) for i in t_df.index]
        edited = st.data_editor(t_df[['선택', '상호명', col_filter, '주소']], 
                                hide_index=True, 
                                use_container_width=True, 
                                key=f"editor_v2_{track_id}")
        
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
        
        # [REFIXED] Start Button & Dashboard Layout
        btn_label_final = "📧 이메일 발송 시작" if track_id == 'A' else "🚀 DM 발송 시작"
        if st.button(btn_label_final, type="primary", use_container_width=True):
            selected = t_df[t_df['선택'] == True]
            if selected.empty: 
                st.warning("선택된 대상이 없습니다.")
            else:
                if track_id == 'A':
                    active_p = st.session_state.get('active_email_profile', '')
                    profiles = st.session_state.get('email_profiles', {})
                    if not active_p or active_p not in profiles:
                        st.error("발송 계정 프로필을 먼저 선택하거나 등록해 주세요.")
                    else:
                        p_info = profiles[active_p]
                        u, p = active_p, p_info['pw']
                        smtp_host = p_info['smtp']
                        
                        st.markdown("---")
                        # --- [NEW] Live Status Dashboard (Inside Button Block) ---
                        status_cols = st.columns(3)
                        total_slot = status_cols[0].empty()
                        success_slot = status_cols[1].empty()
                        fail_slot = status_cols[2].empty()
                        
                        log_container = st.container(border=True)
                        log_container.caption("📝 발송 실시간 로그")
                        log_placeholder = log_container.empty()
                        log_text = ""
                        
                        success = 0
                        fail = 0
                        prog = st.progress(0)
                        
                        for idx, (_, s) in enumerate(selected.iterrows()):
                            total_slot.metric("🎯 총 대상", f"{len(selected)}건")
                            success_slot.metric("✅ 성공", f"{success}건")
                            fail_slot.metric("❌ 실패", f"{fail}건")
                            
                            current_target = s['상호명']
                            temp_log = f"⏳ `{current_target}` 발송 중...\n" + log_text
                            log_placeholder.code(temp_log)
                            
                            ok, err = send_email(u, p, s['이메일'], 
                                               st.session_state['tpl_A']['subject'], 
                                               format_tpl(st.session_state['tpl_A']['body'], s['상호명']), 
                                               smtp_server=smtp_host)
                            
                            if ok:
                                success += 1
                                log_text = f"✅ `{current_target}` 발송 성공\n" + log_text
                            else:
                                fail += 1
                                log_text = f"❌ `{current_target}` 발송 실패 ({err})\n" + log_text
                            
                            log_placeholder.code(log_text)
                            prog.progress((idx+1)/len(selected))
                            
                        st.success(f"🎊 모든 작업이 완료되었습니다! (성공: {success}, 실패: {fail})")
                else:
                    st.info("DM 엔진은 백그라운드 subprocess로 실행됩니다. (구현 가이드 준수)")
    else: 
        st.info(f"{col_filter} 정보가 포함된 데이터가 없습니다.")

if st.session_state['active_page'] == 'Shop Search':
    # --- 1. Settings Panel (Top) ---
    st.markdown('<div class="section-title">⚙️ 수집 및 필터 설정</div>', unsafe_allow_html=True)
    
    # [HACK] Disable browser autocomplete by adding a hidden dummy input
    st.markdown('<input type="text" style="display:none;" autocomplete="off">', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3, gap="medium")
    u_set = st.session_state['user_settings']
    
    with c1:
        with st.container(border=True):
            st.markdown('<p class="input-label">🔍 키워드 설정</p>', unsafe_allow_html=True)
            s_keyword = st.text_input("수집 키워드", value=u_set.get('keyword', config.BASE_KEYWORD), key="main_kw_v5", label_visibility="collapsed")
            st.markdown('<p class="input-label" style="margin-top:10px;">🚫 제외 키워드 (콤마 구분)</p>', unsafe_allow_html=True)
            s_exclude = st.text_input("제외 키워드", value=u_set.get('exclude', ""), placeholder="예: 태닝, 마사지", key="main_ex_v5", label_visibility="collapsed")
            
            st.markdown('<p class="input-label" style="margin-top:10px;">🎯 2차 필터링 조건</p>', unsafe_allow_html=True)
            f_mode_opts = ["전체(상호/업종/메뉴 포함)", "상호명 일치", "업종명 일치"]
            saved_f_mode = u_set.get('filter_mode_ui', "전체(상호/업종/메뉴 포함)")
            s_f_mode_ui = st.selectbox("필터 모드", f_mode_opts, index=f_mode_opts.index(saved_f_mode) if saved_f_mode in f_mode_opts else 0, key="main_f_mode_v5", label_visibility="collapsed")
            s_f_keyword = st.text_input("필터 키워드", value=u_set.get('filter_keyword', ""), placeholder="필터링할 단어 입력", key="main_f_kw_v5", label_visibility="collapsed", help="선택한 모드(상호/업종)에 이 단어가 포함된 것만 최종 수집합니다.")
        
    with c2:
        with st.container(border=True):
            st.markdown('<p class="input-label">📍 지역 설정</p>', unsafe_allow_html=True)
            saved_provs = u_set.get('provinces', [])
            s_provinces = st.multiselect("대상 시/도", config.REGIONS_LIST, default=saved_provs if all(p in config.REGIONS_LIST for p in saved_provs) else [], key="main_prov_v5", label_visibility="collapsed")
            
            s_target = ""
            if s_provinces:
                all_districts = []
                for p in s_provinces:
                    if p in config.CITY_MAP:
                        for d in config.CITY_MAP[p].keys(): all_districts.append(f"[{p}] {d}")
                
                saved_dists = u_set.get('districts', [])
                s_dist_opts = sorted(all_districts)
                s_dist_defaults = [d for d in saved_dists if d in s_dist_opts]
                selected_dists = st.multiselect("상세 구역 선택 (정밀 수집)", options=s_dist_opts, default=s_dist_defaults, key="main_dist_v5")
                
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
                save_settings({
                    'keyword': s_keyword,
                    'exclude': s_exclude,
                    'filter_mode_ui': s_f_mode_ui,
                    'filter_keyword': s_f_keyword,
                    'provinces': s_provinces,
                    'districts': selected_dists if s_provinces else []
                })
                st.toast("✅ 설정이 안전하게 저장되었습니다!")
                time.sleep(0.5)
            
            st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
            
            # [FIXED] Immediate UI Lock to prevent double-click
            if 'engine_starting' not in st.session_state: st.session_state['engine_starting'] = False

            pid = get_engine_pid()
            if pid:
                st.session_state['engine_starting'] = False
                if st.button("🔴 엔진 가동 정지", use_container_width=True, key="stop_btn_v5"):
                    if stop_engine(): st.rerun()
                st.markdown(f'<div style="text-align:center; padding:10px; background:#F1F5F9; border-radius:10px; border:1px solid #E2E8F0;"><p style="margin:0; font-size:0.7rem; color:#64748B; font-weight:800;">ID: {pid} 엔진 작동 중</p></div>', unsafe_allow_html=True)
            elif st.session_state['engine_starting']:
                st.button("⏳ 엔진 시동 중...", disabled=True, use_container_width=True)
                time.sleep(1)
                st.rerun()
            else:
                if st.button("🟢 데이터 수집 시작", type="primary", use_container_width=True, key="start_btn_v5"):
                    if s_keyword and s_target:
                        st.session_state['engine_starting'] = True
                        save_settings({
                            'keyword': s_keyword, 'exclude': s_exclude, 'filter_mode_ui': s_f_mode_ui,
                            'filter_keyword': s_f_keyword, 'provinces': s_provinces, 'districts': selected_dists if s_provinces else []
                        })
                        limit = AuthManager.get_collection_limit()
                        is_paid = AuthManager.check_license_status() and AuthManager.get_serial_key() != "TRIAL-MODE"
                        final_limit = limit if limit else (99999 if is_paid else 50)
                        filter_mode_map = {"전체(상호/업종/메뉴 포함)": "all", "상호명 일치": "name", "업종명 일치": "category"}
                        f_mode = filter_mode_map.get(s_f_mode_ui, "all")
                        st.session_state['completion_shown'] = False # [NEW] Reset completion flag
                        run_engine_cmd(s_target, final_limit, s_keyword, filter_mode=f_mode, filter_keyword=s_f_keyword)
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
    st.markdown('<div class="section-title" style="margin-top:1rem;">📊 실시간 수집 상세 현황</div>', unsafe_allow_html=True)
    prog = get_crawler_progress() or {}
    
    # [FIXED] Reliable Completion Notification (Monster Rule 3.2)
    if prog.get("status") == "completed" and not st.session_state.get("completion_shown", False):
        st.balloons()
        st.success("🎉 데이터 수집이 완료되었습니다! 아래 [실시간 수집 데이터 현황] 우측의 버튼을 눌러 결과를 다운로드하세요.")
        st.session_state["completion_shown"] = True

    
    # 2.1 Four Status Cards
    sc1, sc2, sc3, sc4 = st.columns(4, gap="small")
    with sc1:
        total_val = prog.get("estimated_total", 0)
        total_disp = f"{total_val} <span style='font-size:0.8rem; color:#94A3B8;'>건</span>" if total_val > 0 else "<span style='font-size:1.2rem;'>계산 중...</span>"
        st.markdown(f'<div class="section-container" style="text-align:center; padding:1rem; border-top: 4px solid #E2E8F0;"><p class="input-label">예상 대상 수 (추정)</p><h3 style="margin:0;">{total_disp}</h3></div>', unsafe_allow_html=True)
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
        pct = (current / total * 100) if total > 0 else 0.0
        
        col_p1, col_p2 = st.columns([4, 1])
        col_p1.markdown(f"**전체 완료율 (추정)**")
        total_str = str(total) if total > 0 else "?"
        col_p2.markdown(f"<div style='text-align:right; color:#00E676; font-weight:800;'>{current} / {total_str} ({pct:.1f}%)</div>", unsafe_allow_html=True)
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
            # st_autorefresh가 작동하지 않을 경우를 대비한 세이프티
            time.sleep(0.1) 
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=5000, limit=None, key="engine_autorefresh_v2")
        else:
            st.caption("🔄 엔진이 정지 상태입니다.")

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
        
        st.dataframe(df[['No', '상호명', '주소', '번호', '이메일', '인스타', '톡톡링크']], hide_index=True, use_container_width=True, height=600)
    else: 
        st.info("데이터가 없습니다.")

elif st.session_state['active_page'] == 'Track A': render_track('A', '이메일 마케팅', '이메일', '메일 서버', df)
elif st.session_state['active_page'] == 'Track C': render_track('C', '인스타 DM 마케팅', '인스타ID', 'DM 서버', df)
elif st.session_state['active_page'] == 'Guide':
    st.markdown('<div class="section-title">📖 NPlace-DB 공식 가이드</div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.subheader("📧 이메일 마케팅 설정 (네이버 SMTP)")
        st.markdown("""
        이메일 발송 기능을 사용하려면 본인의 네이버 계정에서 **SMTP 사용 설정**과 **앱 암호 발급**이 반드시 필요합니다.
        
        #### **1단계: 네이버 메일 SMTP 설정 활성화**
        1. PC에서 [네이버 메일]에 접속합니다.
        2. 왼쪽 메뉴 하단의 **[환경설정]** (톱니바퀴 아이콘)을 클릭합니다.
        3. 상단 탭에서 **[POP3/IMAP 설정]**을 클릭합니다.
        4. **[IMAP/SMTP 설정]** 탭으로 이동합니다.
        5. 'IMAP/SMTP 사용' 항목을 **[사용함]**으로 변경하고 확인을 누릅니다.
        
        *   💡 **안내**: SMTP 서버/포트 정보는 네이버 기본값(`smtp.naver.com` / `465`)으로 이미 세팅되어 있으니 **그대로 두시면 됩니다.**
        
        #### **2단계: 네이버 앱 암호 발급 (보안)**
        일반 비밀번호는 보안상 차단될 수 있으므로, 반드시 '앱 암호'를 생성해야 합니다.
        1. [네이버 내정보] -> [보안설정] 메뉴로 이동합니다.
        2. **[2단계 인증]** 항목 우측의 **[관리]** 버튼을 클릭합니다.
        3. 이동한 페이지의 **맨 아래쪽**으로 스크롤을 내리면 **[비밀번호 관리 (앱 암호)]** 섹션이 나타납니다.
        4. 종류 선택에서 '직접 입력'을 누르고 **'마케팅몬스터'** 또는 **'NPlaceDB'**라고 입력한 뒤 **[생성]**을 클릭합니다. (하이픈 '-' 등 특수문자는 제외해 주세요.)
        *   💡 여기서 입력하는 이름은 본인 확인용이며, **메일을 받는 상대방에게는 노출되지 않습니다.**
        5. 생성된 **16자리 영문 앱 암호**를 복사하여 프로그램의 '비밀번호' 칸에 입력하세요.
        
        ---
        #### **기타 SMTP 설정 안내**
        *   **Gmail**: 구글 계정 설정에서 '앱 비밀번호' 생성이 필요하며, SMTP 서버는 `smtp.gmail.com`, 포트는 `465`를 사용합니다.
        *   **Outlook**: `smtp-mail.outlook.com` 서버를 사용합니다.
        """)
        
        st.divider()
        st.subheader("🖥️ PC 권장 사양 및 환경")
        st.markdown("""
        *   **CPU**: Intel Core i5 / AMD Ryzen 5 이상
        *   **RAM**: 8GB 이상 (16GB 권장)
        *   **OS**: Windows 10/11 (64bit)
        *   **Browser**: 최신 버전의 Google Chrome 설치 필수
        """)

