import os
try:
    from dotenv import load_dotenv
    # Load environment variables (Local development)
    load_dotenv()
except ImportError:
    # On Streamlit Cloud, variables are managed via Secrets, so dotenv is optional
    pass

# [카페 몬스터] 통합 브랜드 및 기술 규격 적용

# Local Database Settings (SQLite) - CafeMonster Standard Path
PRODUCT_ID = "NPlace-DB"
CURRENT_VERSION = "1.1.0"
LOCAL_BASE_PATH = f"C:\\CafeMonster\\{PRODUCT_ID}"
LOCAL_DB_PATH = os.path.join(LOCAL_BASE_PATH, "data", "database.sqlite")
LOCAL_LOG_PATH = os.path.join(LOCAL_BASE_PATH, "data", "log")
PROGRESS_FILE = os.path.join(LOCAL_LOG_PATH, "progress.json")
ENGINE_LOG_FILE = os.path.join(LOCAL_BASE_PATH, "crawler_place.log")

# Ensure base directories exist
os.makedirs(LOCAL_LOG_PATH, exist_ok=True)
os.makedirs(os.path.join(LOCAL_BASE_PATH, "data"), exist_ok=True)

# [마케팅 몬스터] 통합 브랜드 및 기술 규격 적용
BRAND_NAME_KR = "NPlace_DB"
SERVICE_NAME_KR = "NPlace-DB (네이버 플레이스 수집)"

# EXCLUSION SETTINGS
DEFAULT_EXCLUDED_KEYWORDS = []

# UI Branding Colors (Standard)
COLOR_DEEP_BLUE = "#1A237E"
COLOR_ELECTRIC_PURPLE = "#6200EE"
COLOR_NEON_GREEN = "#00E676"
COLOR_DARK_BG = "#0B0E23" # Deep Dark for Premium Look

# --- [인증 및 클라우드 설정] ---
# Firebase 서비스 계정 설정
FIREBASE_SERVICE_ACCOUNT = {
  "type": "service_account",
  "project_id": "n-place-db",
  "private_key_id": "dd7a1423801fc0c12fbe6e402650e040b80fbaf0",
  "private_key": ("-----BEGIN PRIVATE KEY-----\n"
                  "MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQD/BT6kKxrpmfpc\n"
                  "+ypwA7PHLqqgngtvv0jhsnPDPwBh0ZeenizzqVIU/4hOsCl3pjXmKC/Jo45L/kxA\n"
                  "FSdtVJ6v3fRYXA7/+0M6LbiDCA/bH2zVVzjdjzQySKKd7mCfPI3NCJhMBUt8/DjJ\n"
                  "FvsD7wl3/dlmlrQmVoLJdoYmWwo1g0tCThMZz1fCG9yfZv7BzzQH40mUk2W5Go7S\n"
                  "m7zJSkApHpjq/PgtHhrm9wLnE6Wd5aM9Ow7qf5qHbBlvmypFSQ+o4fGrPta0fARP\n"
                  "/+/f/cgGz/vLd8UbuZEloUTrv1A1LjEy+WFiK2I4ar5VuGqZSuMcj1A/1DIF2QJw\n"
                  "pB/AQ7YBAgMBAAECggEABGfRSgxqlcWGCIwtkqt7CW0EypXgXwkAF9IO45Js4xkN\n"
                  "VFKpi84NhR+tpE+xGl2MidIrkoFY/cwXV3YQwnfsmTTYOfHhL8qQlz/fSPg0hJW5\n"
                  "j21HJgtex02aQuiG0nQSg7ZrIckSTEbz2Nl6SE+dVhgpuiF5XD4wr+KfH6jWoiT+\n"
                  "gwJKWBc+MO03ow/Dv4j7UeB09GPRj7eFGRIZgBDz4DTWmWIB74fl/aV0egY/HcQt\n"
                  "7dxawFUKZdbSZQNt02WQpvavQo5+zXj+5/9f/x8mvB14fVzY92gHafPCI+x7s2wo\n"
                  "6qXBPrLJt0SpxHqt1t+/JLcSA52JSIr5eQgV9TSXfwKBgQD/xUzVqSivol5D02nF\n"
                  "LiOMkdYGKnEJZx8IyDDr6X9cYcjFYZIrEQ7kwYmRdI1gMDZ9baEfZR68+4iMqtOd\n"
                  "sc/nH7l0alQ6AqdUTriaVGftcb18oiNExAsoL40B2BmYXeqqOBhbdwQGJCbwjXAI\n"
                  "1Jp4nqTOtuhOFFvbnxLFQVyTowKBgQD/P8W6xbnZt8k6N7ezKLQqkIUkeLHN0m9p\n"
                  "aqjxn5YkhlECQUMotxlOcYcKrsV57AQCfX69IWg8zkeD6XzavP12Wb+iZRzNxNUX\n"
                  "ferkYBmi0odzLWY28swcAtDSNEFexdjDDqATuN+WZ3cCxi82Cm0a6HF7idopy4TC\n"
                  "uT9GrrcKCwKBgBelewwJ3pwWS9bDdfTn5ht55Cqfw+GVqhXaxEMbTE4TMEenVKcs\n"
                  "pY7aochT2To6Wt9PwmSvqZ7ZNm+i33ul083PbgroRa8zTZsKyCBki1M1f8pFBzO1\n"
                  "WD633rZ77ynaDPb9xqq2HyYeM4dr3B7E4R8js6L04BdP5Ioyc77O4ys3AoGASiLg\n"
                  "sGXbnCPoW3NxdKT+51oAgd5YblqPp4OmPD/I4STuBISmF/5OaF1LBsxKaSYm5/5B\n"
                  "QHeiif60ANlhPTslNynMIkPSAOYJqoAVKG3NJGCXnNlz1cPhisU6l8M7tWYrlkP6\n"
                  "NKA+uLWmeHTNo5mVpPocc/BPIFKPZeteOI5odY8CgYAx2hhq4YdX5/Kj7vF172qu\n"
                  "HnjJ8ftrShkJQD68iz9SdREQ6n54CyRKJ+JvJK2KxGhtw+ISf6Okr78HMnru8GL1\n"
                  "wTtDrWRW4wWLhX/vv2QrPAR6pn5E0aZOloeZ0wvN8PS235M9IWmduDVqJFUupfqn\n"
                  "kVxhbMREmz717BplgRvbug==\n"
                  "-----END PRIVATE KEY-----\n"),
  "client_email": "firebase-adminsdk-fbsvc@n-place-db.iam.gserviceaccount.com",
  "client_id": "117331856806527264180",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40n-place-db.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

FIREBASE_COLLECTION = "collected_shops" # 수집 데이터 저장소
FIREBASE_AUTH_COLLECTION = "licenses"   # 라이선스 관리 컬렉션 (가이드 준수)

# --- [Supabase 설정] ---
SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "https://suwinftalfgybvrnzruz.supabase.co")
SUPABASE_KEY = os.getenv("VITE_SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN1d2luZnRhbGZneWJ2cm56cnV6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYzMDQ3OTEsImV4cCI6MjA5MTg4MDc5MX0.OJAE_djjwIxR1pDNVx45HprOcAtU8gZopGJx8hvJMt4")
# ------------------------------


# Output Settings
OUTPUT_CSV = "확장_피부샵_원장_데이터.csv"

# Crawling Settings
MIN_DELAY = 10
MAX_DELAY = 30
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# User Agents for Rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
]

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
BASE_KEYWORD = ""

# Major Korean Regions (State -> Districts -> Dongs mapping)
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

REGIONS_LIST = list(CITY_MAP.keys()) if CITY_MAP else ["서울", "인천", "경기"]
