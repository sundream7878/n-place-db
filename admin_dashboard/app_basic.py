import os

# 🛡️ gRPC Stability Fix (Must be at the absolute top for Windows/Threaded envs)
# Triggering reload to clear import cache
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
os.environ["GRPC_POLL_STRATEGY"] = "poll"

import streamlit as st
import pandas as pd
import requests
import sys
import time
import json
import subprocess
import base64
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent dir to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config
import importlib
importlib.reload(config) # Force reload to ensure all attributes are available
from crawler.local_db_handler import LocalDBHandler
from crawler.db_handler import DBHandler
from auth import AuthManager

# --- Helper: Engine Monitoring ---
ENGINE_PID_FILE = os.path.join(config.LOCAL_LOG_PATH, "engine.pid")
ENGINE_LOG_FILE = os.path.join(config.LOCAL_LOG_PATH, "engine.log")
DEBUG_LOG_FILE = os.path.join(config.LOCAL_LOG_PATH, "app_debug.log")

def get_engine_pid():
    if os.path.exists(ENGINE_PID_FILE):
        try:
            with open(ENGINE_PID_FILE, "r") as f:
                pid = int(f.read().strip())
                # Check if process is alive (Windows)
                res = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {pid}', '/NH'], 
                    capture_output=True, 
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if str(pid) in res.stdout: return pid
        except: pass
    return None

def stop_engine():
    pid = get_engine_pid()
    if pid:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            if os.path.exists(ENGINE_PID_FILE): os.remove(ENGINE_PID_FILE)
            return True
        except: return False
    return False

def run_engine_cmd(target=None, count=None, mode="new"): # mode: "new", "resume", "recovery"
    try:
        my_env = os.environ.copy()
        my_env["PYTHONIOENCODING"] = "utf-8"
        my_env["PYTHONUNBUFFERED"] = "1"
        
        log_f = open(ENGINE_LOG_FILE, "a", encoding="utf-8")
        
        label_map = {"new": "NEW RUN", "resume": "RESUME", "recovery": "SMART RECOVERY"}
        label = label_map.get(mode, "UNKNOWN")
        
        log_f.write(f"\n--- ENGINE {label}: {time.strftime('%Y-%m-%d %H:%M:%S')} (Target: {target}) ---\n")
        log_f.flush()
        
        if mode == "recovery":
             args = [sys.executable, 'engine_recover_missing.py', str(target) if target else "서울"]
        else:
             # [MODIFIED] Enforce License Collection Limit
             requested_count = int(count) if count else 99999
             license_limit = AuthManager.get_collection_limit()
             
             if license_limit:
                 run_count = str(min(requested_count, license_limit))
                 logger.info(f"🛡️ License Limit Applied: {run_count} (Requested: {requested_count})")
             else:
                 run_count = str(requested_count)
             
             keyword = st.session_state.get('sb_keyword_v3', config.BASE_KEYWORD)
             exclude = st.session_state.get('sb_exclude_v1', "")
             args = [sys.executable, 'step1_refined_crawler.py', str(target) if target else "전체", run_count, keyword]
             if exclude:
                 args.extend(["--exclude", exclude])
             if mode == "resume": args.append("--resume")
        
        p = subprocess.Popen(
            args, stdout=log_f, stderr=log_f, env=my_env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        with open(ENGINE_PID_FILE, "w") as f: f.write(str(p.pid))
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"엔진 가동 실패: {e}")

# 1. Config & Setup
st.set_page_config(page_title="[카페 몬스터] 네이버 플레이스 수집기 Basic V1.0", page_icon="👹", layout="wide", initial_sidebar_state="expanded")

# Initialize session state for navigation and selection
if 'active_page' not in st.session_state:
    st.session_state['active_page'] = 'Shop Search'
if 'show_collector' not in st.session_state:
    st.session_state['show_collector'] = False
if 'last_selected_shop' not in st.session_state:
    st.session_state['last_selected_shop'] = None

# Initialize selection states for tracks
for track in ['A', 'B', 'C']:
    if f'sel_track_{track}' not in st.session_state:
        st.session_state[f'sel_track_{track}'] = {}

# Initialize pending updates for competitor analysis
if 'pending_update_districts' not in st.session_state:
    st.session_state['pending_update_districts'] = set()

# --- Template Persistence Logic REMOVED for Basic Version ---
    
# --- 2.2 Data Logic ---
def load_data():
    # st.write("DEBUG: load_data() starting...")
    f_df = pd.DataFrame()
    mandatory_cols = ["상호명", "주소", "플레이스링크", "번호", "이메일", "인스타", "톡톡링크", "블로그ID"]
    
    # 1. Load from Firebase
    max_retries = 2
    for attempt in range(max_retries):
        try:
            db = DBHandler()
            if db.db_fs:
                with st.spinner(f"데이터를 불러오는 중입니다... (시도 {attempt+1}/{max_retries})"):
                    data_list = []
                    try:
                        # Strategy A: Fast Stream
                        docs = db.db_fs.collection(config.FIREBASE_COLLECTION).stream()
                        for doc in docs:
                            d = doc.to_dict()
                            d['ID'] = doc.id
                            data_list.append(d)
                    except Exception as e:
                        # Strategy B: Robust Get Fallback (Handles '_UnaryStreamMultiCallable' errors)
                        logger.warning(f"Firebase Stream failed: {e}. Falling back to .get()...")
                        docs = db.db_fs.collection(config.FIREBASE_COLLECTION).get()
                        for doc in docs:
                            d = doc.to_dict()
                            d['ID'] = doc.id
                            data_list.append(d)
                    
                    if data_list:
                        f_df = pd.DataFrame(data_list)
                    break # Success
            else:
                if attempt < max_retries - 1:
                    DBHandler.reset_instance()
                    time.sleep(1)
                    continue
        except Exception as e:
            logger.error(f"Firebase 로드 실패 (시도 {attempt+1}): {e}")
            if attempt < max_retries - 1:
                DBHandler.reset_instance()
                time.sleep(1)
            else:
                if "firebase_admin" in str(e):
                    st.warning("Firebase 모듈을 확인 중입니다. 잠시 후 새로고침 해주세요.")

    # 2. Rename and Normalize Columns
    rename_map = {
        "id": "ID", "name": "상호명", "email": "이메일", "address": "주소", "phone": "번호", 
        "talktalk": "톡톡링크", "instagram": "인스타", "source_link": "플레이스링크",
        "blog_id": "블로그ID", "owner_name": "대표자", "talk_url": "톡톡링크", 
        "instagram_handle": "인스타", "naver_blog_id": "블로그ID"
    }
    f_df = f_df.rename(columns=rename_map)
    
    # 2.1 Merge duplicate columns (e.g., from multiple sources like 'name' and '상호명' mapping to same label)
    if not f_df.empty:
        # Get list of duplicated column names
        cols = f_df.columns
        unique_cols = cols.unique()
        if len(cols) != len(unique_cols):
            new_df = pd.DataFrame(index=f_df.index)
            for col in unique_cols:
                # Find all columns with this name
                col_data = f_df.loc[:, f_df.columns == col]
                if col_data.shape[1] > 1:
                    # Merge multiple columns: start with the first, fill with subsequent
                    merged = col_data.iloc[:, 0]
                    for i in range(1, col_data.shape[1]):
                        merged = merged.fillna(col_data.iloc[:, i])
                    new_df[col] = merged
                else:
                    new_df[col] = col_data
            f_df = new_df
    
    # Ensure mandatory columns exist even if empty
    for col in mandatory_cols:
        if col not in f_df.columns:
            f_df[col] = ""

    if f_df.empty: 
        return f_df[mandatory_cols + (["ID"] if "ID" in f_df.columns else [])]

    # 3. Deduplicate rows and Reset Index
    combined = f_df.drop_duplicates(subset=['상호명', '플레이스링크'], keep='last').reset_index(drop=True)
    
    def n_i(v):
        if v is None: return ""
        # Handle cases where Firestore returns a list/array
        if not isinstance(v, (str, bytes)) and hasattr(v, '__iter__'):
            try:
                v = next(iter(v), "")
            except:
                v = ""
        
        # Direct check to avoid ValueError: truth value of a Series is ambiguous
        if pd.isna(v): return ""
        
        v_str = str(v).strip()
        if not v_str or v_str.lower() in ["none", "nan", ""]: return ""
        if v_str.startswith("http"): return v_str
        return f"https://www.instagram.com/{v_str.replace('@', '').strip()}/"
    
    if '인스타' in combined.columns: 
        combined['인스타'] = combined['인스타'].apply(n_i)
    
    # 3.1 Normalize other link columns
    def normalize_link(v):
        if pd.isna(v) or v is None: return ""
        v_str = str(v).strip()
        if v_str.lower() in ["none", "nan", ""]: return ""
        return v_str

    for col in ['플레이스링크', '톡톡링크', '블로그ID']:
        if col in combined.columns:
            combined[col] = combined[col].apply(normalize_link)
    
    return combined
def load_local_data():
    """Loads data from the local SQLite database."""
    mandatory_cols = ["ID", "상호명", "주소", "플레이스링크", "번호", "이메일", "인스타", "톡톡링크", "블로그ID"]
    try:
        db_local = LocalDBHandler(config.LOCAL_DB_PATH)
        shops = db_local.get_all_shops()
        if not shops:
            return pd.DataFrame(columns=mandatory_cols)
            
        df = pd.DataFrame(shops)
        
        # Normalize columns for consistency with Web UI
        rename_map = {
            "id": "ID", "name": "상호명", "email": "이메일", "address": "주소", "phone": "번호", 
            "talk_url": "톡톡링크", "instagram": "인스타", "instagram_handle": "인스타", "detail_url": "플레이스링크",
            "owner_name": "대표자", "naver_blog_id": "블로그ID"
        }
        df = df.rename(columns=rename_map)
        
        # [FIX] Deduplicate columns (prevents blank dashboard when '인스타' exists twice)
        if not df.empty:
            cols = df.columns
            unique_cols = cols.unique()
            if len(cols) != len(unique_cols):
                new_df = pd.DataFrame(index=df.index)
                for col in unique_cols:
                    col_data = df.loc[:, df.columns == col]
                    if col_data.shape[1] > 1:
                        merged = col_data.iloc[:, 0]
                        for i in range(1, col_data.shape[1]):
                            merged = merged.fillna(col_data.iloc[:, i])
                        new_df[col] = merged
                    else:
                        new_df[col] = col_data
                df = new_df

        # Ensure mandatory columns
        for col in mandatory_cols:
            if col not in df.columns: df[col] = ""
            
        return df
    except Exception as e:
        logger.error(f"Local SQLite 로드 실패: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. View Router
# ---------------------------------------------------------

df = load_local_data()

# --- Sidebar: Crawler Command Center ---

with st.sidebar:
    # 1. CafeMonster Premium Logo
    # Fixed height container to ensure line synchronization with main area tabs
    logo_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png')
    if os.path.exists(logo_path):
        st.image(logo_path, width=80)

    st.markdown("""
        <div style="margin-top: -10px; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #00E676; display: flex; flex-direction: column; justify-content: flex-end;">
            <div style="font-size: 1.9rem; font-weight: 900; color: #00E676; letter-spacing: -0.05em; line-height: 1.0; font-family: 'Pretendard', sans-serif;">
                카페 몬스터<br>
                <span style="font-size: 1.15rem; color: #2D3748; opacity: 0.9; font-weight: 800;">BASIC</span>
            </div>
            <div style="font-size: 0.72rem; color: #718096; font-weight: 700; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.08em;">
                대한민국 No.1 카페 마케팅 솔루션
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### 👹 추출 엔진 제어")

    # [NEW] License Status Check (Strict)
    try:
        if not AuthManager.check_license_status():
            st.error("🛑 라이선스가 만료되었거나 유효하지 않습니다.")
            st.info("기간 만료 또는 중복 로그인 등으로 인해 접근이 제한되었습니다. 관리자에게 문의하세요.")
            if st.button("인증 파일 리셋 (재로그인)"):
                try:
                    target_license = os.path.join(config.LOCAL_BASE_PATH, "data", "license.dat")
                    if os.path.exists(target_license):
                        os.remove(target_license)
                    st.rerun()
                except: pass
            st.stop() # Stop further execution
        key = AuthManager.get_serial_key()
        if key and (key.startswith('TEST-') or "-TEST-" in key):
            st.warning("⚠️ 테스트 라이선스 사용 중")
            st.caption("• 최대 100건 수집 가능\n• 1일(24시간) 동안 사용 가능")
            if st.button("정식 라이선스 문의"):
                  st.info("관리자에게 문의하여 정식 라이선스로 업그레이드하세요.")
    except Exception as e:
        logger.error(f"Test notice error: {e}")



    st.caption("네이버 플레이스 실시간 정보 데이터베이스")
    st.write("")
    
    # Keyword Selection/Input
    s_keyword = st.text_input("수집 키워드 (상호/업종 등)", value=config.BASE_KEYWORD, key="sb_keyword_v3", placeholder="예: 미용실, 식당, 피부샵 등")
    
    # Excluded Keywords
    s_exclude = st.text_input("수집 제외 키워드 (콤마 분리)", value="", key="sb_exclude_v1", placeholder="예: 태닝, 마사지, 왁싱")
    
    # [MODIFIED] Advanced Multi-Region & District Selection System
    s_provinces = st.multiselect("수집 대상 지역 (시/도)", config.REGIONS_LIST, default=[], key="sb_city_multi_v2")
    s_province = s_provinces[0] if s_provinces else "전체"
    
    s_target = ""
    if not s_provinces:
        st.warning("최소 한 개의 지역을 선택해주세요.")
    else:
        # 1. Collect all districts from selected provinces
        all_districts_options = []
        province_district_map = {} # To track which district belongs to which province
        
        for prov in s_provinces:
            if prov in config.CITY_MAP:
                for dist in config.CITY_MAP[prov].keys():
                    option_label = f"[{prov}] {dist}"
                    all_districts_options.append(option_label)
                    province_district_map[option_label] = (prov, dist)
        
        all_districts_options.sort()
        
        # 2. Multi-select for Districts
        selected_dist_labels = st.multiselect(
            "세부 구역 선택 (선택 시 해당 구만 정밀 수집 / 미선택 시 해당 시/도 전체 수집)",
            options=all_districts_options,
            key="sb_district_multi_v2"
        )
        
        # 3. Construct target string based on rules
        final_targets = []
        
        # Track which provinces had at least one district selected
        provinces_with_dist_selected = set()
        for label in selected_dist_labels:
            prov, dist = province_district_map[label]
            final_targets.append(f"{prov} {dist}")
            provinces_with_dist_selected.add(prov)
        
        # For provinces where NO district was selected, add the province name itself (Whole Region crawl)
        for prov in s_provinces:
            if prov not in provinces_with_dist_selected:
                final_targets.append(prov)
        
        # [가이드 준수] 정확한 타겟 문자열 조합 (콤마 분리)
        if isinstance(final_targets, list):
            s_target = ",".join(final_targets)
        else:
            s_target = str(final_targets)
            
        if not s_target:
            s_target = ""


    st.markdown(f"""
<div style="background: #f1f5f9; padding: 10px; border-radius: 8px; border-left: 4px solid #6366f1; margin-bottom: 20px;">
    <div style="font-size: 0.7rem; color: #64748b; font-weight: 600; text-transform: uppercase;">선택된 수집 대상</div>
    <div style="font-size: 0.95rem; font-weight: 700; color: #1e293b; margin-top: 2px;">{s_target}</div>
</div>""", unsafe_allow_html=True)

    # Engine Status UI
    running_pid = get_engine_pid()
    
    def get_crawler_progress():
        if os.path.exists(ENGINE_LOG_FILE):
            try:
                with open(ENGINE_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    
                    start_idx = 0
                    for i, line in enumerate(reversed(lines)):
                        if "ENGINE NEW RUN" in line or "ENGINE RESUME" in line or "ENGINE SMART RECOVERY" in line:
                            start_idx = len(lines) - 1 - i
                            break
                            
                    # Look for the new PROGRESS_JSON first
                    for line in reversed(lines[start_idx:]):
                        if "PROGRESS_JSON:" in line:
                            json_str = line.split("PROGRESS_JSON:")[-1].strip()
                            try:
                                data = json.loads(json_str)
                                return data
                            except: pass
                    
                    # Fallback to legacy progress
                    for line in reversed(lines[start_idx:]):
                        if "Progress:" in line:
                            parts = line.split("Progress:")[-1].strip().split("/")
                            if len(parts) == 2:
                                return {"success_count": int(parts[0]), "estimated_total": int(parts[1]), "legacy": True}
            except: pass
        return None

    prog_data = get_crawler_progress()
    
    # Check if streamlit has fragment support (v1.33+)
    has_fragment = hasattr(st, "fragment")

    def render_status_content():
        running_pid = get_engine_pid()
        prog_data = get_crawler_progress()
        
        if running_pid:
            st.markdown(f"""
    <div style="background: white; padding: 12px; border-radius: 12px; color: var(--text-main); font-size: 0.85rem; font-weight: 600; margin-bottom: 12px; border: 1px solid var(--primary);">
        <span class="live-dot"></span> 엔진 가동 중 (PID: {running_pid})
    </div>""", unsafe_allow_html=True)
            
            if prog_data:
                if prog_data.get("legacy"):
                    curr = prog_data["success_count"]
                    total = prog_data["estimated_total"]
                    pct = min(curr / total, 1.0) if total > 0 else 0
                    st.progress(pct, text=f"수집 진행률: {curr}/{total}")
                else:
                    # New Real-Time Summary UI
                    n = prog_data.get("success_count", 0)
                    m = prog_data.get("estimated_total", 0)
                    elapsed = prog_data.get("elapsed_sec", 0)
                    eta = prog_data.get("eta_sec", 0)
                    avg_sec = prog_data.get("avg_sec_per_item", 0)
                    segment = prog_data.get("current_segment", "대기 중")
                    confidence = prog_data.get("estimation_confidence", "계산 중...")
                    ratio = prog_data.get("completion_ratio", 0)
                    
                    def format_time(seconds):
                        if seconds < 60: return f"{seconds}초"
                        m, s = divmod(seconds, 60)
                        if m < 60: return f"{m}분 {s}초"
                        h, m = divmod(m, 60)
                        return f"{h}시간 {m}분"
                    
                    # 4 Cards Layout
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.markdown(f"""
                        <div style="padding: 10px; border-radius: 10px; background: #f8fafc; border: 1px solid #e2e8f0; text-align: center;">
                            <div style="font-size: 0.7rem; color: #64748b; font-weight: 600;">예상 대상 수 (추정)</div>
                            <div style="font-size: 1.2rem; font-weight: 800; color: #0f172a;">{m:,} <span style="font-size: 0.8rem; color: #94a3b8; font-weight: 500;">건</span></div>
                        </div>""", unsafe_allow_html=True)
                    with c2:
                         st.markdown(f"""
                        <div style="padding: 10px; border-radius: 10px; background: #f0fdf4; border: 1px solid #bbf7d0; text-align: center;">
                            <div style="font-size: 0.7rem; color: #166534; font-weight: 600;">현재 수집 개수</div>
                            <div style="font-size: 1.2rem; font-weight: 800; color: #15803d;">{n:,} <span style="font-size: 0.8rem; color: #86efac; font-weight: 500;">건</span></div>
                        </div>""", unsafe_allow_html=True)
                    with c3:
                         st.markdown(f"""
                        <div style="padding: 10px; border-radius: 10px; background: #f8fafc; border: 1px solid #e2e8f0; text-align: center;">
                            <div style="font-size: 0.7rem; color: #64748b; font-weight: 600;">총 소요시간</div>
                            <div style="font-size: 1.1rem; font-weight: 800; color: #0f172a;">{format_time(elapsed)}</div>
                        </div>""", unsafe_allow_html=True)
                    with c4:
                         st.markdown(f"""
                        <div style="padding: 10px; border-radius: 10px; background: #fffcf5; border: 1px solid #fef08a; text-align: center;">
                            <div style="font-size: 0.7rem; color: #854d0e; font-weight: 600;">예상 남은 시간</div>
                            <div style="font-size: 1.1rem; font-weight: 800; color: #a16207;">{format_time(eta)}</div>
                        </div>""", unsafe_allow_html=True)
                    
                    st.write("")
                    
                    # Progress Bar with minimum width width logic handling inside HTML
                    display_ratio = ratio * 100
                    bar_width = max(display_ratio, 1.2) # Minimum visible width
                    
                    st.markdown(f"""
                    <div style="margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span style="font-size: 0.85rem; font-weight: 700; color: #1e293b;">전체 완료율 (추정)</span>
                            <span style="font-size: 0.85rem; font-weight: 800; color: #00E676;">{n:,} / {m:,} ({display_ratio:.1f}%)</span>
                        </div>
                        <div style="width: 100%; background-color: #e2e8f0; border-radius: 999px; height: 10px; overflow: hidden;">
                            <div style="background-color: #00E676; height: 100%; width: {bar_width}%; border-radius: 999px; transition: width 0.5s ease-in-out;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Subtext
                    st.markdown(f"""
                    <div style="font-size: 0.75rem; color: #64748b; margin-top: 4px; display: flex; justify-content: space-between;">
                        <span>개당 평균 소요: <strong style="color: #475569;">{avg_sec}초/건</strong></span>
                        <span>현재 수집 구간: <strong style="color: #475569;">{segment}</strong></span>
                    </div>
                    <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 4px; text-align: right;">
                        * 총 예상 대상 수는 추정치이며, 수집이 진행될수록 정확도가 올라갑니다. ({confidence})
                    </div>
                    """, unsafe_allow_html=True)
                    
            else:
                st.info("크롤러 초기화 중...")
                
            if st.button("엔진 정지", use_container_width=True, key="btn_sb_stop"):
                if stop_engine():
                    st.toast("엔진이 정지되었습니다.")
                    st.rerun()
            

        else:
            st.markdown(f"""
    <div style="background: white; padding: 12px; border-radius: 12px; color: var(--text-muted); font-size: 0.85rem; font-weight: 600; margin-bottom: 12px; border: 1px solid var(--border);">
        엔진 대기 상태
    </div>""", unsafe_allow_html=True)
            
            if st.button("데이터 수집 시작", type="primary", use_container_width=True, key="btn_sb_run"):
                # Safety check again before starting
                if AuthManager.check_license_status():
                    # Check limit for default count if not set
                    limit = AuthManager.get_collection_limit()
                    default_count = limit if limit else 99999
                    # 🛡️ 엔진 호출 시 문자열 타입 강제 (리스트 전달 방지)
                    safe_target = str(s_target) if s_target else "전체"
                    run_engine_cmd(safe_target, default_count, mode="new")
                else:
                    st.error("라이선스 검증에 실패했습니다. 수집을 시작할 수 없습니다.")
                    
            st.info(f"현재 상태: {st.session_state.get('crawler_status', '대기 중')}")

            # ---------------------------------------------------------
            # [NEW] Error Log Export & Support Feature
            # ---------------------------------------------------------
            st.markdown("<hr style='margin: 15px 0px 10px 0px;'>", unsafe_allow_html=True)
            st.markdown("💡 **고객 원격 지원**", unsafe_allow_html=True)
            st.caption("프로그램 오류 발생 시, 아래 버튼을 눌러 로그를 다운로드 받아 관리자에게 전달해주세요.")
            
            if st.button("오류 로그 추출 (바탕화면 저장)", use_container_width=True, key="btn_export_logs"):
                import zipfile
                from datetime import datetime
                
                import winreg
                def get_desktop_path():
                    try:
                        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
                        return winreg.QueryValueEx(key, "Desktop")[0]
                    except:
                        return os.path.join(os.path.expanduser("~"), "Desktop")
                        
                desktop_path = get_desktop_path()
                zip_filename = f"CafeMonster_ErrorLog_{datetime.now().strftime('%m%d_%H%M')}.zip"
                zip_filepath = os.path.join(desktop_path, zip_filename)
                
                files_to_zip = []
                if os.path.exists(ENGINE_LOG_FILE): files_to_zip.append(ENGINE_LOG_FILE)
                if os.path.exists(DEBUG_LOG_FILE): files_to_zip.append(DEBUG_LOG_FILE)
                
                if files_to_zip:
                    try:
                        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for file in files_to_zip:
                                zipf.write(file, os.path.basename(file))
                        st.success(f"✅ 추출 성공!\n\n바탕화면에 **`{zip_filename}`** 파일이 생성되었습니다. 이 파일을 카카오톡 등으로 관리자에게 전달해주세요.")
                    except Exception as e:
                        st.error(f"❌ 추출 실패: {e}")
                else:
                    st.warning("추출할 에러 로그가 아직 없습니다.")


    # Apply Fragment if available
    if has_fragment:
        st.fragment(run_every=5)(render_status_content)()
    else:
        render_status_content()
        # Fallback for older streamlit versions
        if running_pid and st.checkbox("진행상황 자동 갱신 (전체 새로고침)", value=True, key="chk_auto_refresh_fallback"):
            time.sleep(5)
            st.rerun()
        
        # --- CRAWLER SETTINGS (DELAYS) ---
        st.write("---")
        st.markdown("**수집 속도 설정**")
        SETTINGS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'crawler_settings.json'))
        
        def load_crawler_settings():
            default = {"min_delay": 27, "max_delay": 55, "inter_keyword_min": 40, "inter_keyword_max": 80}
            if os.path.exists(SETTINGS_FILE):
                try:
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        return json.load(f)
                except: return default
            return default

        def save_crawler_settings(settings):
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)

        c_settings = load_crawler_settings()
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            new_min = st.number_input("최소 대기(초)", min_value=5, max_value=300, value=int(c_settings.get("min_delay", 27)), step=1)
        with col_d2:
            new_max = st.number_input("최대 대기(초)", min_value=10, max_value=600, value=int(c_settings.get("max_delay", 55)), step=1)
        
        if new_min >= new_max:
            st.warning("최소 시간이 최대 시간보다 길 수 없습니다.")
        
        if st.button("수집 속도 설정 저장", use_container_width=True):
            # Also scale inter-keyword delays accordingly (approx 1.5x of base delay)
            save_crawler_settings({
                "min_delay": new_min,
                "max_delay": new_max,
                "inter_keyword_min": int(new_min * 1.5),
                "inter_keyword_max": int(new_max * 1.5)
            })
            st.toast("수집 속도 설정이 저장되었습니다.")

            
    st.write("---")
    
    st.write("---")
    
    # --- 데이터 수집 요약 섹션 ---
    st.markdown('<div style="font-size: 1.15rem; font-weight: 700; color: #0f172a; margin-bottom: 12px;">수집 현황 요약</div>', unsafe_allow_html=True)
    
    # --- Dashboard UI Enhancements (Mint & White Theme) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        
        :root {
            --primary: #2DCE89;
            --primary-hover: #24b378;
            --bg-main: #F7F9FC;
            --card-bg: #FFFFFF;
            --text-main: #2D3748;
            --text-muted: #718096;
            --border: #E2E8F0;
        }

        /* Streamlit Overrides */
        .stApp { background-color: var(--bg-main); font-family: 'Inter', sans-serif; }
        
        [data-testid="stSidebar"] {
            background-color: var(--card-bg);
            border-right: 1px solid var(--border);
        }

        .stButton>button {
            border-radius: 12px;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            transition: all 0.25s ease;
            border: 1px solid var(--border);
        }
        
        .stButton>button[kind="primary"] {
            background-color: var(--primary);
            color: white;
            border: none;
        }
        
        .stButton>button[kind="primary"]:hover {
            background-color: var(--primary-hover);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(45, 206, 137, 0.2);
        }

        /* Custom Cards */
        .stat-card {
            background-color: var(--card-bg);
            padding: 1.5rem;
            border-radius: 20px;
            border: 1px solid var(--border);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
            margin-bottom: 1rem;
        }

        .compact-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.25rem;
            margin-bottom: 0.6rem;
            transition: all 0.2s ease;
        }
        
        .compact-card:hover {
            border-color: var(--primary);
            box-shadow: 0 8px 24px rgba(45, 206, 137, 0.08);
        }

        .detailed-panel {
            background: var(--card-bg);
            border-radius: 24px;
            padding: 2rem;
            border: 1px solid var(--border);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
        }

        /* Status Indicator */
        .live-dot {
            height: 8px;
            width: 8px;
            background-color: var(--primary);
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
            box-shadow: 0 0 10px var(--primary);
            animation: pulse-mint 2s infinite;
        }

        @keyframes pulse-mint {
            0% { transform: scale(0.95); opacity: 0.7; }
            70% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.7; }
        }

        /* Navigation Styling */
        .nav-title {
            font-size: 1.8rem;
            font-weight: 800;
            color: var(--primary);
            letter-spacing: -0.02em;
            margin-top: -4px; /* Adjust vertical alignment with buttons */
        }
        
        /* Cleanup Streamlit Widgets */
        div[data-testid="stHeader"] { background: transparent; }
        .stTabs [data-baseweb="tab-list"] { background-color: transparent; }
        </style>
    """, unsafe_allow_html=True)

    # 실시간 모니터링 한 줄 정렬 (여백 활용)
    col_stat_title, col_empty, col_stat_toggle = st.columns([1.5, 1, 1.2])
    with col_stat_title:
        st.markdown('<div style="font-size: 0.85rem; font-weight: 600; color: #64748b; margin-top: 10px; width: 200px;">데이터베이스 수집 현황</div>', unsafe_allow_html=True)
    with col_stat_toggle:
        live_mode = st.toggle("실시간 모니터링", value=False, key="live_mon_toggle_final")
    
    stats_placeholder = st.empty()

    # Optimized Stats Fetching
    @st.cache_resource
    def get_db_handler():
        return DBHandler()

    db = get_db_handler()
    
    def render_elegant_stats(metrics, is_live=True):
        cards_html = ""
        for i, (label, count, color) in enumerate(metrics):
            # Highlight the first card (National Total) with Mint Gradient
            bg_style = "background: linear-gradient(135deg, #2DCE89 0%, #24b378 100%);" if i == 0 else "background: white;"
            label_color = "rgba(255,255,255,0.9)" if i == 0 else "var(--text-muted)"
            value_color = "white" if i == 0 else "var(--text-main)"
            border_style = "border: none;" if i == 0 else "border: 1px solid var(--border);"
            
            cards_html += f"""
<div style="padding: 1.25rem; border-radius: 16px; {bg_style} {border_style} box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
    <div style="font-size: 0.7rem; font-weight: 700; color: {label_color}; text-transform: uppercase; letter-spacing:0.05em;">{label}</div>
    <div style="font-size: 1.6rem; font-weight: 800; color: {value_color}; margin-top: 0.25rem;">{count:,}</div>
</div>"""

        status_html = f'<div class="live-indicator"><span class="live-dot"></span>실시간 수신 중</div>' if is_live else '<div style="font-size:0.75rem; color:#94a3b8; font-weight:600;">○ 정적 데이터 모드</div>'

        return f"""
<div style="margin-bottom: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px;">
        <div style="font-size: 0.9rem; font-weight: 600; color: #64748b;">DATABASE SUMMARY</div>
        {status_html}
    </div>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
        {cards_html}
    </div>
    <div style="margin-top: 8px; text-align: right; font-size: 0.70rem; color: #94a3b8;">최종 업데이트: {time.strftime('%H:%M:%S')}</div>
</div>"""

    # Dynamic Region Monitoring
    def get_top_regions(dataframe, current_sel):
        if dataframe.empty:
            return ["서울", "경기", "인천"]
        
        # Calculate counts per region from '주소' column
        temp_df = dataframe.copy()
        temp_df['region_key'] = temp_df['주소'].apply(lambda x: x.split()[0] if isinstance(x, str) and x.strip() else "기타")
        counts = temp_df['region_key'].value_counts()
        
        top_list = counts.head(5).index.tolist()
        
        # Ensure selected province is in the list
        if current_sel != "전체" and current_sel not in top_list:
            top_list = [current_sel] + top_list[:4]
        
        return top_list

    target_regions = get_top_regions(df, s_province)
    l_prov = 0

    if live_mode:
        try:
            while True:
                metrics = []
                total = db.get_doc_count()
                metrics.append(("전국 전체 합계", total, "indigo"))
                for reg in target_regions:
                    c = db.get_doc_count(reg)
                    if reg == s_province: l_prov = c
                    metrics.append((f"{reg} 지역 현황", c, "slate"))
                
                stats_placeholder.markdown(render_elegant_stats(metrics[:6], True), unsafe_allow_html=True)
                time.sleep(5)
        except: pass
    else:
        # Optimization: Use loaded DataFrame for static view
        try:
            total = len(df)
            metrics = [("전국 전체 합계", total, "indigo")]
            
            temp_df = df.copy()
            temp_df['region_key'] = temp_df['주소'].apply(lambda x: x.split()[0] if isinstance(x, str) and x.strip() else "기타")
            counts = temp_df['region_key'].value_counts()
            
            for reg in target_regions:
                c = int(counts.get(reg, 0))
                if reg == s_province: l_prov = c
                metrics.append((f"{reg} 지역 현황", c, "slate"))
                
            stats_placeholder.markdown(render_elegant_stats(metrics[:6], False), unsafe_allow_html=True)
        except: pass

    # Clean Detailed Distribution
    if not df.empty:
        temp_df = df.copy()
        temp_df['city_stat'] = temp_df['주소'].apply(lambda x: x.split()[0] if isinstance(x, str) and x.strip() else "기타")
        city_data = temp_df[temp_df['city_stat'] == s_province]
        
        st.markdown(f"#### 📍 {s_province} 상세 분포")
        
        if not city_data.empty:
            dist_counts = city_data.groupby(city_data['주소'].apply(lambda x: x.split()[1] if isinstance(x, str) and len(x.split()) > 1 else "상세불명")).size().reset_index(name='count').sort_values('count', ascending=False)
            
            with st.container(height=280, border=True):
                for _, row in dist_counts.iterrows():
                    d_name = row.iloc[0]
                    st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border);">
    <span style="font-size: 0.9rem; font-weight: 500; color: var(--text-main);">{d_name}</span>
    <span style="background: #F0FFF4; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; font-weight: 700; color: var(--primary);">{row['count']}</span>
</div>""", unsafe_allow_html=True)
        else:
            st.info(f"현재 뷰에서 {s_province}에 대한 상세 데이터가 없습니다.")

    
    
    st.write("---")



# ---------------------------------------------------------
# 1.1 UI CSS (V13: Ultimate Minimalism & Top-Ref)
# ---------------------------------------------------------
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    :root {{
        --primary: #9d7dfa;
        --bg: #ffffff;
        --text-main: #1e293b;
        --text-muted: #94a3b8;
        --border: #f1f5f9;
        --radius: 16px;
    }}

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background: white; }}

    /* Fix Title Alignment with Tabs */
    .app-title {{
        font-weight: 800;
        font-size: 1.62rem;
        color: #1e293b;
        white-space: nowrap;
        padding-top: 10px; /* Aligns with navigation buttons */
    }}

    /* Tighten Layout Space */
    .block-container {{
        padding-top: 3rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }}
    
    hr {{ margin: 0.5rem 0 !important; }}
    
    hr {{ margin: 0.5rem 0 !important; }}

    /* Minimal CSS to allow Streamlit defaults for sidebar/header */

    /* Header Navigation Buttons (Targeting first horizontal block in main) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) button {{
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0px 8px !important;
        color: #94a3b8 !important; /* Muted default */
        transition: color 0.2s !important;
    }}
    
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) button:hover {{
        color: #1e293b !important;
        background: transparent !important;
    }}

    div[data-testid="stHorizontalBlock"]:nth-of-type(1) button p {{
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding-bottom: 1px !important;
    }}


    /* Detail Panel Alignment (Calibrated to Table Header Top Border) */
    .detailed-panel {{
        background: white;
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem;
        margin-top: 48px !important; /* Perfect match for data table vertical start */
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    }}




    /* Container Styling */
    div.stBlock, [data-testid="stExpander"] {{
        background: white;
        border: 1px solid #f8fafc;
        border-radius: var(--radius);
        padding: 2rem;
    }}

    /* Data Table */
    div.stDataFrame {{
        border: 1px solid #f1f5f9;
        border-radius: 14px;
        overflow: hidden;
    }}

    /* Primary Buttons */
    .stButton > button[kind="primary"] {{
        background: var(--primary);
        border: none;
        border-radius: 10px;
        font-weight: 700;
        padding: 0.6rem 1.5rem;
    }}
    
    /* Header Micro Refresh Button */
    .micro-ref-btn button, .research-btn button {{
        background: transparent !important;
        color: var(--text-muted) !important;
        border: 1px solid #f1f5f9 !important;
        padding: 4px 12px !important;
        font-size: 0.75rem !important;
        border-radius: 8px !important;
        height: auto !important;
        min-height: 0 !important;
        transition: all 0.2s ease !important;
        white-space: nowrap !important;
    }}
    
    .micro-ref-btn button:hover, .research-btn button:hover {{
        background: #f8fafc !important;
        color: var(--primary) !important;
        border-color: var(--primary) !important;
    }}
    
    /* Delete Button Style (Precision Alignment) */
    .delete-btn button {{
        background: #fee2e2 !important;
        color: #ef4444 !important;
        border: none !important;
        padding: 0px 15px !important;
        height: 32px !important;
        line-height: 32px !important;
        font-size: 0.85rem !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin-top: 4px !important; /* Fine-tune vertical center */
    }}


    
    /* Compact Card Styling */
    .compact-card {{
        background: white;
        border: 1px solid #f1f5f9;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.4rem;
        transition: all 0.2s ease;
    }}
    .compact-card:hover {{
        border-color: var(--primary);
        box-shadow: 0 4px 12px rgba(157, 125, 250, 0.05);
    }}
</style>
""", unsafe_allow_html=True)

# --- 1.2 Header Navigation ---
with st.container():
    # Adjusted columns: No more title here, just menu
    h_cols = st.columns([1, 1, 1, 3.4], vertical_alignment="center")
            
    pages = ["Shop Search", "Guide"]
    labels = ["데이터수집 및 분석", "📖 사용 가이드"]
    
    # Active Tab Highlighting
    active_idx = 1
    
    st.markdown(f"""
    <style>
    /* Robust Navigation Highlighting */
    /* 1. Target the button marked as 'primary' in the main navigation area */
    div[data-testid="stAppViewMain"] div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"] {{
        background-color: #00E676 !important; /* Solid Neon Green */
        color: #1e293b !important; /* Dark text for contrast */
        border: none !important;
        border-bottom: 4px solid #004D40 !important; /* Darker bottom border */
        border-radius: 8px !important;
        font-weight: 900 !important;
        box-shadow: 0 4px 15px rgba(0, 230, 118, 0.4) !important;
        transition: all 0.3s ease !important;
    }}
    
    /* 2. Style for non-active buttons in navigation */
    div[data-testid="stAppViewMain"] div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"] {{
        background-color: transparent !important;
        color: #94a3b8 !important;
        border: 1px solid transparent !important;
        font-weight: 600 !important;
    }}
    
    div[data-testid="stAppViewMain"] div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"]:hover {{
        color: #1e293b !important;
        background-color: #f8fafc !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    for i, (p, label) in enumerate(zip(pages, labels)):
        with h_cols[i]: 
            is_active = (st.session_state['active_page'] == p)
            if st.button(label, key=f"nav_{p}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state['active_page'] = p
                st.rerun()

    # Profile placeholder removed

# Custom Divider Line for perfect horizontal alignment across sidebar and main area
st.markdown('<div style="margin-top: -16px; border-bottom: 2px solid #E2E8F0; margin-bottom: 25px;"></div>', unsafe_allow_html=True)

# Helper for Page Header

# --- Helper: Page Header with Ref Button ---
def render_page_header(title, key):
    st.markdown(f"#### {title}")

# --- Helper: Render Filter Bar (v14) ---
def render_filters_v14(df_input, key):
    df_input = df_input.copy()
    if df_input.empty:
        st.info("표시할 데이터가 없습니다.")
        return df_input

    # Ensure required columns for filtering exist and handle NaN
    for col in ['주소', '상호명']:
        if col not in df_input.columns:
            df_input[col] = ""
        else:
            df_input[col] = df_input[col].fillna("").astype(str)

    with st.container(border=False):
        c1, c2, c3 = st.columns([1, 1, 2.5])
        with c1:
            df_input['시/도'] = df_input['주소'].apply(lambda x: x.split()[0] if x.strip() else "")
            sel_city = st.selectbox("지역 (시/도)", ["전체"] + sorted(list(df_input['시/도'].unique())), key=f"{key}_city_v14")
        with c2:
            d_list = ["전체"]
            if sel_city != "전체":
                # Safely get district (second word of address)
                dist_series = df_input[df_input['시/도'] == sel_city]['주소'].apply(
                    lambda x: x.split()[1] if len(x.split()) > 1 else ""
                )
                d_list = ["전체"] + sorted(list(dist_series.unique()))
            sel_dist = st.selectbox("지역 (군/구)", d_list, key=f"{key}_dist_v14")
        with c3:
            s_q = st.text_input("업체명 검색", key=f"{key}_q_v14", placeholder="업체명을 입력하세요...")
            
    filtered = df_input.copy()
    if sel_city != "전체": filtered = filtered[filtered['시/도'] == sel_city]
    if sel_dist != "전체": filtered = filtered[filtered['주소'].str.contains(sel_dist, na=False)]
    if s_q: filtered = filtered[filtered['상호명'].str.contains(s_q, case=False, na=False)]
    return filtered

# --- Helper: Personalize Message ---
def format_tpl(text, shop_name):
    if not text: return ""
    return text.replace("{상호명}", shop_name if shop_name else "원장님")

# --- Helper: Copy Only (JS) ---
def copy_to_clipboard(text):
    js = f"""
    <script>
    navigator.clipboard.writeText(`{text}`).then(() => {{
        parent.postMessage({{type: 'streamlit:toast', message: '메시지가 복사되었습니다!'}}, '*');
    }});
    </script>
    """
    st.components.v1.html(js, height=0)


# (Crawler UI Removed from footer)

# ---------------------------------------------------------
# 4. Final Rendering (Router)
# ---------------------------------------------------------
page = st.session_state['active_page']

if page == 'Shop Search':
    render_page_header("데이터수집 및 분석", "shop_search_idx")
    
    # Action Buttons: Refresh & Export
    col_act1, col_act2, col_act3 = st.columns([1, 1, 4])
    with col_act1:
        if st.button("새로고침 🔄", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col_act3:
        if st.button("CSV💾", use_container_width=True, help="엑셀에서 한글이 깨질 경우 이 버튼을 사용하세요."):
            from exporter import export_to_csv
            path = export_to_csv()
            if path:
                st.success("CSV 생성 완료")
                with open(path, "rb") as f:
                    st.download_button("다운로드 (.csv)", f, file_name=os.path.basename(path), mime="text/csv", use_container_width=True)

    f_df = render_filters_v14(df, "search_final")
    
    m_col, d_col = st.columns([1.6, 1]) if st.session_state['last_selected_shop'] is not None else (st.container(), None)

    # Initialize session state for multi-selection tracking
    if 'prev_rows' not in st.session_state:
        st.session_state['prev_rows'] = []

    with m_col:
        h_col1, h_col2, h_col3 = st.columns([1.1, 2.2, 2.8], vertical_alignment="center")
        h_col1.markdown('<p style="font-size:0.85rem; color:var(--text-muted); margin:0; font-weight:600;">수집 데이터 리스트</p>', unsafe_allow_html=True)
        
        # Visibility Logic: Show buttons if selected
        has_selection = st.session_state['last_selected_shop'] is not None or (st.session_state.get('prev_rows') and len(st.session_state['prev_rows']) > 0)
        
        if has_selection:
            with h_col2:
                st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                sel_rows = st.session_state.get('prev_rows', [])
                sel_count = len(sel_rows)
                
                btn_label = f"✕ {sel_count}개 삭제" if sel_count > 1 else "✕ 삭제"
                if st.button(btn_label, key="btn_del_basic"):
                    db_h = DBHandler()
                    if db_h.db_fs:
                        if sel_count > 1:
                            shops_to_del = [f_df.iloc[r] for r in sel_rows]
                            for s in shops_to_del:
                                try: db_h.db_fs.collection(config.FIREBASE_COLLECTION).document(s.get('ID')).delete()
                                except: pass
                            st.success(f"{sel_count}개 삭제 완료")
                        else:
                            shop_to_del = st.session_state['last_selected_shop']
                            try: db_h.db_fs.collection(config.FIREBASE_COLLECTION).document(shop_to_del.get('ID')).delete()
                            except: pass
                            st.success("삭제 완료")
                        
                        st.cache_data.clear()
                        st.session_state['last_selected_shop'] = None
                        st.session_state['prev_rows'] = []
                        time.sleep(1)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        if not f_df.empty:
            selection = st.dataframe(
                f_df[['상호명', '주소', '번호', '이메일', '인스타', '톡톡링크']].reset_index(drop=True),
                width='stretch', hide_index=True, selection_mode="multi-row", on_select="rerun", height=600
            )
            s_rows = selection.get("selection", {}).get("rows", [])
        else:
            st.info("조건에 맞는 데이터가 없습니다. 수집을 먼저 진행해주세요.")
            s_rows = []
        
        # Selection Logic
        if s_rows:
            newly_added = [r for r in s_rows if r not in st.session_state['prev_rows']]
            if newly_added:
                st.session_state['last_selected_shop'] = f_df.iloc[newly_added[-1]]
            elif st.session_state['last_selected_shop'] is not None:
                current_id = st.session_state['last_selected_shop'].get('ID')
                if current_id and not any(f_df.iloc[r].get('ID') == current_id for r in s_rows):
                    st.session_state['last_selected_shop'] = f_df.iloc[s_rows[-1]]
            st.session_state['prev_rows'] = s_rows
            if d_col is None: st.rerun()
        else:
            st.session_state['prev_rows'] = []
            if st.session_state['last_selected_shop'] is not None:
                st.session_state['last_selected_shop'] = None
                st.rerun()

    if d_col is not None and st.session_state['last_selected_shop'] is not None:
        shop = st.session_state['last_selected_shop']
        with d_col:
            st.markdown(f"""
            <div class="detailed-panel">
                <h5 style="margin-top:0; color:var(--primary); font-weight:800; font-size:1.2rem;">{shop['상호명']} 상세 정보</h5>
                <p style="font-size:0.9rem; color:var(--text-muted); margin-bottom:1.2rem;">{shop['주소']}</p>
                <div style="background:#F8FAFC; border-radius:16px; padding:1.25rem; border:1px solid var(--border); margin-bottom:1.5rem;">
                    <p style="font-size:0.9rem; margin-bottom:8px; color:var(--text-main);"><b>전화번호:</b> {shop['번호']}</p>
                    <p style="font-size:0.9rem; margin-bottom:0; color:var(--text-main);"><b>이메일:</b> {shop.get('이메일', '-')}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            # Link buttons
            insta_url = str(shop.get('인스타', '')).strip()
            talk_url = str(shop.get('톡톡링크', '')).strip()
            place_url = str(shop.get('플레이스링크', '')).strip()

            if insta_url and insta_url.startswith("http"):
                c1.link_button("인스타그램", insta_url, use_container_width=True)
            else:
                c1.button("인스타그램 없음", disabled=True, use_container_width=True)

            if talk_url and talk_url.startswith("http"):
                c2.link_button("네이버 톡톡", talk_url, use_container_width=True)
            else:
                c2.button("네이버 톡톡 없음", disabled=True, use_container_width=True)

            if place_url and place_url.startswith("http"):
                c3.link_button("네이버 플레이스", place_url, use_container_width=True, type="primary")
            else:
                c3.button("플레이스 링크없음", disabled=True, use_container_width=True)
            
            st.write("<div style='margin-bottom:15px; border-bottom:1px solid var(--border);'></div>", unsafe_allow_html=True)
elif page == 'Guide':
    render_page_header("📖 카페 몬스터 사용 가이드", "guide_idx")

    st.markdown("### 🚀 빠른 시작 가이드")
    st.markdown("카페 몬스터의 강력한 데이터 수집 기능을 활용하는 방법입니다.")
    st.markdown("---")
    
    st.markdown("#### 1. 검색 대상 및 타겟 설정")
    st.markdown("- 좌측의 사이드바에서 **수집 키워드**를 입력합니다. (예: 미용실, 식당)")
    st.markdown("- 수집을 원하지 않는 상호/업종이 있다면 **수집 제외 키워드**에 입력합니다.")
    st.markdown("- 타겟으로 할 **지역 (시/도)**를 복수로 선택할 수 있습니다.")
    st.markdown("- 특정 구/군의 데이터만 원한다면 **세부 구역 선택**에서 추가로 선택합니다.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("#### 2. 수집 엔진 가동")
    st.markdown("- 모든 설정을 마친 후 사이드바 하단의 **데이터 수집 시작** 버튼을 클릭합니다.")
    st.markdown("- 엔진이 가동되면 예상 대상 수 및 현재까지 수집된 데이터 개수가 실시간으로 표시됩니다.")
    st.markdown("- 중간에 정지하고 싶다면 **엔진 정지** 버튼을 누릅니다. (수집 엔진은 백그라운드에서 안전하게 중단됩니다.)")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("#### 3. 데이터 관리 및 추출")
    st.markdown("- **데이터수집 및 분석** 탭에서 수집 완료된 데이터를 확인하고 더 세부적으로 검색(필터링)할 수 있습니다.")
    st.markdown("- 원하지 않는 데이터는 목록에서 클릭하여 선택한 후, ✕ 삭제 버튼을 눌러 목록에서 지울 수 있습니다.")
    st.markdown("- 화면 상단의 **CSV 다운로드 버튼**을 누르면 전체 데이터가 다운로드됩니다.")
    st.markdown("- ⚠️ **주의:** 브라우저 다운로드 폴더에 저장되거나, 최초 프로그램 창에서 'CSV 저장' 버튼을 누르면 프로그램 폴더 내 `exports/` 안에 엑셀/CSV 파일이 저장됩니다.")
