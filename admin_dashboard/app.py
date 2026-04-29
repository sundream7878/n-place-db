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
        "email_user": "", "email_pw": "", "naver_user": "", "naver_pw": "", "insta_user": "", "insta_pw": "",
        "tpl_A": {"subject": "안녕하세요, {상호명} 원장님!", "body": "원장님 안녕하세요! 마케팅 몬스터입니다."},
        "tpl_B": "안녕하세요! 네이버 톡톡 메시지입니다.",
        "tpl_C": "인스타그램 DM 메시지입니다."
    }

def save_templates():
    data = {
        "email_user": st.session_state.get('email_user', ''),
        "email_pw": st.session_state.get('email_pw', ''),
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

# Header & Nav
with st.container():
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
        nav_cols = st.columns(5)
        btns = ["🏠 수집/제어", "📧 이메일", "💬 톡톡", "📸 인스타", "📖 가이드"]
        pages = ["Shop Search", "Track A", "Track B", "Track C", "Guide"]
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
            st.session_state['email_user'] = c1.text_input("Naver 이메일", value=st.session_state.get('email_user',''))
            st.session_state['email_pw'] = c2.text_input("비밀번호 (앱 암호)", type="password", value=st.session_state.get('email_pw',''))
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

    t_df = df_in[df_in[col_filter].notna() & (df_in[col_filter] != "")].copy()
    if not t_df.empty:
        st.markdown(f"**대상 리스트 ({len(t_df)}건)**")
        t_df['선택'] = [st.session_state[f'sel_track_{track_id}'].get(i, False) for i in t_df.index]
        edited = st.data_editor(t_df[['선택', '상호명', col_filter, '주소']], hide_index=True, use_container_width=True)
        # [FIXED] Use direct index 'i' instead of positional 't_df.index[i]' to avoid IndexError
        for i, row in edited.iterrows(): 
            st.session_state[f'sel_track_{track_id}'][i] = row['선택']
        
        if st.button(f"🚀 {label} 엔진 가동", type="primary", use_container_width=True):
            selected = t_df[t_df['선택'] == True]
            if selected.empty: st.warning("선택된 대상이 없습니다.")
            else:
                if track_id == 'A':
                    u, p = st.session_state['email_user'], st.session_state['email_pw']
                    if not u or not p: st.error("계정을 설정해 주세요.")
                    else:
                        success = 0
                        prog = st.progress(0)
                        for idx, (_, s) in enumerate(selected.iterrows()):
                            ok, _ = send_email(u, p, s['이메일'], st.session_state['tpl_A']['subject'], format_tpl(st.session_state['tpl_A']['body'], s['상호명']))
                            if ok: success += 1
                            prog.progress((idx+1)/len(selected))
                        st.success(f"{success}건 발송 성공")
                else:
                    st.info("DM 엔진은 백그라운드 subprocess로 실행됩니다. (구현 가이드 준수)")
    else: st.info(f"{col_filter} 정보가 포함된 데이터가 없습니다.")

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
elif st.session_state['active_page'] == 'Track B': render_track('B', '네이버 톡톡 DM', '톡톡링크', '네이버 계정', df)
elif st.session_state['active_page'] == 'Track C': render_track('C', '인스타그램 DM', '인스타', '인스타 계정', df)
elif st.session_state['active_page'] == 'Guide':
    st.markdown('<div class="section-title">📖 NPlace-DB 공식 가이드</div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("""
        ### 🖥️ PC 권장 사양 및 환경
        NPlace-DB는 실제 브라우저를 구동하여 수집하는 방식으로, 안정적인 동작을 위해 다음 사양을 권장합니다.
        
        *   **CPU**: Intel Core i5 / AMD Ryzen 5 이상 (멀티 프로세싱 권장)
        *   **RAM**: 8GB 이상 (16GB 권장, 브라우저 다중 실행 시 메모리 사용량이 증가합니다.)
        *   **OS**: Windows 10/11 (64bit)
        *   **Network**: 유선 랜 연결 권장 (무선 WiFi 사용 시 끊김 현상으로 인해 수집 누락이 발생할 수 있습니다.)
        *   **Browser**: 최신 버전의 Google Chrome 또는 Microsoft Edge가 설치되어 있어야 합니다.
        
        ---
        
        ### 🔍 수집 필터 상세 설명
        1.  **전체(상호/업종/메뉴 포함)**: 네이버 검색 결과 리스트에 노출되는 모든 업체를 수집합니다. 네이버 인공지능이 키워드와 연관이 있다고 판단한 모든 데이터(메뉴 이름, 업체 설명 등)가 포함됩니다.
        2.  **상호명 일치**: 수집된 데이터 중 상호명에 설정한 '필터 키워드'가 포함된 경우만 최종 저장합니다.
        3.  **업종명 일치**: 수집된 데이터 중 네이버가 정의한 업종(카테고리)에 '필터 키워드'가 포함된 경우만 최종 저장합니다.
        
        ---
        
        ### ☕ 안전 휴식(Safety Break) 안내
        프로그램은 네이버의 자동 수집 차단 시스템을 회피하기 위해 다음과 같이 휴식합니다.
        *   키워드 5~7개 검색 시마다 약 **1분 10초** 휴식.
        *   업체 10곳 수집 시마다 약 **1분 10초** 휴식.
        *   해당 시간에는 엔진이 멈춘 것처럼 보일 수 있으나, 아이피 차단 방지를 위한 정상적인 동작입니다.
        """)
