import os
try:
    from dotenv import load_dotenv
    # Load environment variables (Local development)
    load_dotenv()
except ImportError:
    # On Streamlit Cloud, variables are managed via Secrets, so dotenv is optional
    pass

# Supabase Settings
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "t_crawled_shops" # Standard table name for leads
LEADS_TABLE = "t_crawled_shops"    # Unified name

# Apify Settings
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

# Firebase Settings
FIREBASE_KEY_PATH = os.path.join(os.path.dirname(__file__), "firebase_key.json")
FIREBASE_COLLECTION = "crawled_shops"
FIREBASE_SESSION_COLLECTION = "browser_sessions"

# Load Firebase Service Account Info
FIREBASE_SERVICE_ACCOUNT = None

# 1. Try to load from Streamlit Secrets (Recommended for Cloud)
try:
    import streamlit as st
    if "firebase" in st.secrets:
        # Convert st.secrets proxy to a real dict
        FIREBASE_SERVICE_ACCOUNT = dict(st.secrets["firebase"])
except:
    pass

# 2. Try to load from Environment Variable (Single JSON String)
if not FIREBASE_SERVICE_ACCOUNT:
    env_key = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if env_key:
        try:
            import json
            FIREBASE_SERVICE_ACCOUNT = json.loads(env_key)
        except:
            pass

# 3. Fallback to local file path (Local Development)
if not FIREBASE_SERVICE_ACCOUNT:
    FIREBASE_SERVICE_ACCOUNT = FIREBASE_KEY_PATH

# Output Settings
OUTPUT_CSV = "확장_피부샵_원장_데이터.csv"

# Crawling Settings
MIN_DELAY = 20
MAX_DELAY = 70
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# User Agents for Rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
]

# Search Keywords by Category
# Search Keywords by Category
KEYWORDS = {
    "acne_whitening": [
        "여드름 관리 후기", "성인 여드름 관리", "부산 피부미백 관리", 
        "대구 리프팅 케어", "주름 개선 관리", "고주파 관리"
    ],
    "basic_care": [
        "민감성 피부 관리 후기", "피부 수분 관리", "블랙헤드 제거 후기", 
        "인천 피부 재생 관리", "LDM 관리"
    ],
    "business": [
        "피부샵 창업", "1인 피부샵 운영", "피부샵 마케팅", 
        "피부샵 운영 노하우", "에스테티션 일상", "피부샵 매출 올리기"
    ],
    "consumer": [
        "피부샵 추천", "내돈내산 피부샵 후기", "결혼 전 피부관리"
    ]
}

# ==========================================
# [Module 1] Lumi-Link Crawler Settings
# ==========================================

# Target URL
NAVER_PLACE_URL = "https://m.place.naver.com/place/list?query={}"

# File Paths
RAW_DATA_FILE = "raw_shops_with_coords.csv"
ENRICHED_DATA_FILE = "enriched_target_list.csv"
FINAL_TARGET_FILE = "final_target_selection.csv"

# Crawler Config
SCROLL_COUNT = 10  # Number of times to scroll down the list (Adjust as needed)
HEADLESS_MODE = False # Set to False for debugging visibility

# Target Locations/Keywords for Module 1
# Base Keyword
BASE_KEYWORD = "피부관리샵"

# Major Korean Regions (State -> Districts -> Dongs mapping)
# Loaded from a separate JSON for clean maintenance.
regions_file = os.path.join(os.path.dirname(__file__), 'crawler', 'regions.json')
CITY_MAP = {}
if os.path.exists(regions_file):
    try:
        import json
        with open(regions_file, 'r', encoding='utf-8') as f:
            CITY_MAP = json.load(f)
    except Exception as e:
        print(f"Error loading regions.json: {e}")

def get_deep_keywords(target_city: str) -> list:
    """
    Get a list of keywords expanded to Dong level for a given city.
    Example: '서울' -> ['서울 강남구 역삼동 피부관리샵', ...]
    """
    if target_city not in CITY_MAP:
        return [f"{target_city} {BASE_KEYWORD}"]
    
    keywords = []
    districts = CITY_MAP[target_city]
    for district, dongs in districts.items():
        for dong in dongs:
            keywords.append(f"{target_city} {district} {dong} {BASE_KEYWORD}")
    return keywords

# DEPRECATED: Standard REGIONS list for dashboard selectbox population
# Updated to load dynamically from regions.json
REGIONS_LIST = list(CITY_MAP.keys()) if CITY_MAP else ["서울", "인천", "경기"]
