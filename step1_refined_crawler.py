import asyncio
import random
import logging
import requests
import json
import csv
import sys
import os
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import config
from crawler.local_db_handler import LocalDBHandler
import time
from datetime import datetime

# [MODIFIED] Force stdout encoding to UTF-8 to prevent garbled text in dashboard
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
# Setup Logging
# [NEW] Clear log file securely BEFORE attaching handlers
try:
    if os.path.exists(config.ENGINE_LOG_FILE):
        open(config.ENGINE_LOG_FILE, 'w').close()
except: pass

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # [NEW] Add delay=False and use a custom flush or just standard FileHandler
        # We will manually flush important logs if needed, or use a handler that auto-flushes.
        logging.FileHandler(config.ENGINE_LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
# Force flush on FileHandler to ensure real-time dashboard updates
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.FileHandler):
        handler.flush = lambda h=handler: h.stream.flush() if h.stream else None

logger = logging.getLogger(__name__)

# Config
TABLE_NAME = "t_crawled_shops"
LOCAL_CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "crawled_shops_local.json"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
]

def get_random_ua():
    return random.choice(USER_AGENTS)

def save_to_db(shop_data):
    """
    Saves a single shop dict to a LOCAL JSON file first.
    Final sync happens at the end of the crawl.
    """
    try:
        # Save to SQLite
        db = LocalDBHandler(config.LOCAL_DB_PATH)
        db.insert_shop(shop_data)
        
        # Keep local JSON as backup if needed, but primarily use SQLite
        data_list = []
        if os.path.exists(LOCAL_CACHE_FILE):
            with open(LOCAL_CACHE_FILE, "r", encoding="utf-8") as f:
                try:
                    data_list = json.load(f)
                except: pass
        
        # Check for duplicate in local cache before adding
        new_url = shop_data.get('detail_url')
        if not any(d.get('detail_url') == new_url for d in data_list):
            data_list.append(shop_data)
        
        with open(LOCAL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
            
        logger.info(f"💾 Saved to SQLite: {shop_data.get('name')}")
        return True
    except Exception as e:
        logger.error(f"❌ DB save failed: {e}")
        return False

async def extract_detail_info(page, shop_data):
    """
    Visits the detail page and extracts rich information using Apollo State and DOM fallback.
    """
    try:
        url = shop_data['detail_url']
        logger.info(f"🔍 Visiting detail page: {shop_data['name']}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(random.uniform(3, 5))
        
        # 1. Extract via Apollo State (Most Accurate)
        state = await page.evaluate("window.__APOLLO_STATE__")
        if state:
            for key, val in state.items():
                if not isinstance(val, dict): continue
                
                # PlaceDetailBase contains the core info
                if "PlaceDetailBase" in key:
                    # Clean Name
                    if "name" in val and val["name"]:
                        raw_name = val["name"].strip()
                        shop_data["name"] = raw_name.replace("알림받기", "").strip()
                    
                    # Full Address
                    if "roadAddress" in val and val["roadAddress"]:
                        shop_data["address"] = val["roadAddress"]
                    elif "address" in val and val["address"]:
                        shop_data["address"] = val["address"]
                    
                    # Coordinates
                    if "coordinate" in val:
                        coord = val["coordinate"]
                        shop_data["longitude"] = float(coord.get("x", 0.0))
                        shop_data["latitude"] = float(coord.get("y", 0.0))
                    
                    # TalkTalk
                    if "talktalkUrl" in val and val["talktalkUrl"]:
                        shop_data["talk_url"] = val["talktalkUrl"].strip()
                    
                    # Category (for filtering)
                    if "category" in val and val["category"]:
                        shop_data["category"] = val["category"]
                    elif "categoryName" in val and val["categoryName"]:
                        shop_data["category"] = val["categoryName"]
                
                # Extract SNS Links from homepages section
                if "homepages" in val and val["homepages"]:
                    for hp in val["homepages"]:
                        if not isinstance(hp, dict): continue
                        hp_url = hp.get("url", "")
                        if "instagram.com" in hp_url:
                            # Normalize Instagram URL
                            insta_handle = hp_url.strip("/").split("/")[-1].split("?")[0]
                            if insta_handle and insta_handle not in ['p', 'reels', 'stories', 'explore']:
                                shop_data["instagram_handle"] = f"https://www.instagram.com/{insta_handle}"
                        elif "blog.naver.com" in hp_url:
                            shop_data["naver_blog_id"] = hp_url.strip()
                            # Fallback email from blog ID
                            if not shop_data.get("email"):
                                handle = hp_url.strip("/").split("/")[-1].split("?")[0]
                                if handle:
                                    shop_data["email"] = f"{handle}@naver.com"

        # 2. DOM Fallback & Advanced Extraction (Email from description)
        content = await page.content()
        
        # [NEW] Explicit mailto link check (Strong signal)
        if not shop_data.get("email"):
             try:
                mailto_link = page.locator("a[href^='mailto:']").first
                if await mailto_link.count() > 0:
                    href = await mailto_link.get_attribute("href")
                    if href:
                        shop_data["email"] = href.replace("mailto:", "").strip()
                        logger.info(f"📧 Found email via mailto: {shop_data['email']}")
             except: pass

        # Email Extraction from Description if not found yet
        if not shop_data.get("email"):
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', content)
            if emails:
                # Filter out image-like extensions in emails
                filtered_emails = [e for e in emails if not any(ext in e.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])]
                if filtered_emails:
                    shop_data["email"] = filtered_emails[0]
                    logger.info(f"📧 Found email in page content: {shop_data['email']}")

        # Owner Name (Representative)
        if not shop_data.get("owner_name"):
            owner_match = re.search(r'대표자\s*[:]\s*([가-힣]+)', content)
            if owner_match:
                shop_data["owner_name"] = owner_match.group(1)

        # 3. DOM Link Fallback (If Apollo failed)
        if not shop_data.get("instagram_handle") or not shop_data.get("naver_blog_id") or not shop_data.get("talk_url"):
            
            # Instagram Logic Improvement
            if not shop_data.get("instagram_handle"):
                # Strategy A: Regex search in full content (Fast)
                insta_match = re.search(r'href="(https://www\.instagram\.com/[^"]+)"', content)
                if insta_match:
                    candidate = insta_match.group(1).split("?")[0]
                    if not any(x in candidate for x in ['/p/', '/reels/', '/explore/', '/stories/']):
                         shop_data["instagram_handle"] = candidate
                
                # Strategy B: DOM Traversal (More robust for dynamic elements)
                if not shop_data.get("instagram_handle"):
                    try:
                        insta_links = await page.locator("a[href*='instagram.com']").all()
                        for link in insta_links:
                            href = await link.get_attribute("href")
                            if href:
                                clean_href = href.split("?")[0].strip()
                                if not any(x in clean_href for x in ['/p/', '/reels/', '/explore/', '/stories/']):
                                    shop_data["instagram_handle"] = clean_href
                                    break
                    except: pass
            
            # Naver Blog
            if not shop_data.get("naver_blog_id"):
                blog_match = re.search(r'href="(https://blog\.naver\.com/[^"]+)"', content)
                if blog_match:
                    shop_data["naver_blog_id"] = blog_match.group(1).split("?")[0]
                    # Also try to extract email from blog url
                    if not shop_data.get("email"):
                        handle = shop_data["naver_blog_id"].strip("/").split("/")[-1]
                        if handle: shop_data["email"] = f"{handle}@naver.com"

            # TalkTalk
            if not shop_data.get("talk_url"):
                talk_match = re.search(r'href="(https://talk\.naver\.com/[^"]+)"', content)
                if talk_match:
                    shop_data["talk_url"] = talk_match.group(1)

        return True
    except Exception as e:
        logger.warning(f"Failed to extract details for {shop_data.get('name')}: {e}")
        return False

async def install_playwright_browsers():
    """
    Attempts to install playwright browsers if they are missing.
    Useful for Streamlit Cloud environments.
    """
    import subprocess
    try:
        logger.info("📦 Checking Playwright browsers...")
        # Check if chromium is already available via playwright
        # We try a simple command to see if it works
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, check=True)
        logger.info("✅ Playwright browsers are ready.")
    except Exception as e:
        logger.warning(f"⚠️ Playwright install failed or already handled: {e}")

async def run_crawler(target_area=None, target_count=10, resume=False, custom_keywords=None, shop_type=None, app_mode=False, exclude_keywords=None, filter_mode='all', filter_keyword=''):
    # Proactively try to install browsers in Cloud environments
    is_cloud = os.environ.get("STREAMLIT_RUNTIME_ENV") or "/home/appuser" in os.getcwd() or os.environ.get("STREAMLIT_SERVER_BASE_URL")
    if is_cloud:
        logger.info("☁️ Cloud environment detected. Ensuring Playwright browsers...")
        await install_playwright_browsers()

    # 0. Setup Excludes
    exclude_list = config.DEFAULT_EXCLUDED_KEYWORDS.copy()
    if exclude_keywords:
        if isinstance(exclude_keywords, str):
            dynamic_excludes = [x.strip() for x in exclude_keywords.split(",") if x.strip()]
            exclude_list.extend(dynamic_excludes)
        elif isinstance(exclude_keywords, list):
            exclude_list.extend(exclude_keywords)
    
    if exclude_list:
        logger.info(f"🚫 Active Exclusion Keywords ({len(exclude_list)}): {exclude_list}")
    
    # [NEW] Filter Settings
    # filter_mode: 'all', 'name', 'category'
    if not filter_mode: filter_mode = 'all'
    logger.info(f"🔍 Filter Mode: {filter_mode} | Target: {filter_keyword if filter_keyword else 'None'}")
    
    # Target Keywords (Deep Scan Support)
    base_keyword = shop_type if shop_type else "" # 기본값 제거
    
    if custom_keywords:
        logger.info(f"🎯 Custom Keywords Provided: {len(custom_keywords)} keywords")
        keywords = custom_keywords
    elif target_area:
        # [MODIFIED] Advanced Target Analysis & Sanitization
        target_area = str(target_area).strip("[]").replace("'", "").replace('"', "")
        targets = [t.strip() for t in target_area.split(",") if t.strip()]
        logger.info(f"🎯 Parsing Multi-Target: {targets}")
        
        all_keywords = []
        for t in targets:
            # Check if it's "Province District" (e.g., "서울 강남구")
            if " " in t:
                parts = t.split()
                province = parts[0]
                district = " ".join(parts[1:])
                
                if province in config.CITY_MAP and district in config.CITY_MAP[province]:
                    # 1. Granular District Mode -> Expand to Dong-level
                    dongs = config.CITY_MAP[province][district]
                    all_keywords.extend([f"{province} {district} {dong} {base_keyword}" for dong in dongs])
                    logger.info(f"   + [정밀수집] '{t}' -> {len(dongs)}개 상세 키워드 생성 (동 단위)")
                else:
                    all_keywords.append(f"{t} {base_keyword}")
                    logger.info(f"   + [일반수집] '{t}' (지도 데이터 미매칭)")
            
            elif t in config.CITY_MAP:
                # 2. Whole Province Mode (e.g., "인천") -> Expand ALL districts/dongs
                prov_keywords = []
                districts = config.CITY_MAP[t]
                for dist, dongs in districts.items():
                    for dong in dongs:
                        prov_keywords.append(f"{t} {dist} {dong} {base_keyword}")
                all_keywords.extend(prov_keywords)
                logger.info(f"   + [전체수집] '{t}' -> {len(prov_keywords)}개 전체 키워드 생성 (도시 전체)")
            
            else:
                # 3. Generic Fallback
                all_keywords.append(f"{t} {base_keyword}")
                logger.info(f"   + [개별수집] '{t}'")
        
        # Unique list preservation order
        seen = set()
        keywords = []
        for kw in all_keywords:
            if kw not in seen:
                keywords.append(kw)
                seen.add(kw)
        
        logger.info(f"📂 최종 수집 대상 키워드: {len(keywords)}개")

    else:
        keywords = [f"서울 강남구 {base_keyword}"] 

    checkpoint_file = os.path.join(os.getcwd(), "crawler_checkpoint.json")
    start_index = 0
    
    if resume and os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                checkpoint_data = json.load(f)
                last_keyword = checkpoint_data.get("last_keyword")
                if last_keyword in keywords:
                    start_index = keywords.index(last_keyword) + 1
                    logger.info(f"⏭️ Resuming from index {start_index} (Last: {last_keyword})")
                else:
                    logger.info("ℹ️ Checkpoint keyword not found in current set. Starting from scratch.")
        except Exception as e:
            logger.error(f"⚠️ Error loading checkpoint: {e}")

    total_saved = 0
    total_skipped = 0 # New: Track skipped for ETA
    total_errors = 0  # New: Track errors
    start_time = time.time() # New: Track start time
    
    # [NEW] Adaptive Estimation Tracking Variables
    total_keywords_processed = 0
    total_shops_discovered = 0
    # [NEW] Realistic initial estimation for unlimited mode
    if target_count > 90000:
        estimated_total = 0 # Will trigger '계산 중...' in UI
        eta_sec = "계산 중..."
    else:
        estimated_total = target_count # Initial estimate for trial/limited
        eta_sec = "추정 불가"
    
    # --- Emit Initial Progress JSON ---
    initial_data = {
        "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
        "success_count": 0,
        "skip_count": 0,
        "error_count": 0,
        "elapsed_sec": 0,
        "estimated_total": estimated_total,
        "completion_ratio": 0.0,
        "avg_sec_per_item": 0.0,
        "remaining_time": eta_sec,
        "estimation_confidence": "초기 추정",
        "current_segment": "엔진 준비 중..."
    }
    print(f"PROGRESS_JSON: {json.dumps(initial_data, ensure_ascii=False)}", flush=True)

    keywords_to_run = keywords[start_index:]
    # --- LOAD DYNAMIC SETTINGS ---
    SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crawler_settings.json')
    # [ACCELERATED] Faster delays for commercial readiness
    min_delay, max_delay = 7, 15
    kw_min, kw_max = 15, 30
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                min_delay = 7
                max_delay = 15
                kw_min = 10
                kw_max = 20
                if shop_type is None: shop_type = settings.get("shop_type")
                if app_mode is False: app_mode = settings.get("app_mode", False)
                if not filter_mode: filter_mode = settings.get("filter_mode", "all")
                if not filter_keyword: filter_keyword = settings.get("filter_keyword", "")
                logger.info(f"⚙️ Normalized Settings for Speed: Detail {min_delay}-{max_delay}s")
        except Exception as e:
            logger.warning(f"Failed to load dynamic settings: {e}")
    else:
        logger.info(f"⚙️ Using Fast Defaults: {min_delay}-{max_delay}s")

    # Ensure log directory exists
    os.makedirs(config.LOCAL_LOG_PATH, exist_ok=True)
    progress_file = config.PROGRESS_FILE

    # Initialize Local DB Handler (Rule 3.3 Optimization)
    db = LocalDBHandler(config.LOCAL_DB_PATH)
    logger.info("📡 DB existence check engine initialized (Memory Efficient Mode)")
    for h in logging.getLogger().handlers: h.flush()

    # [FIXED] Non-blocking Cleanup to prevent infinite hang (Monster Rule 3.2)
    if sys.platform == "win32":
        import subprocess
        try:
            logger.info("🧹 Cleaning up old browser/driver processes (Non-blocking)...")
            for h in logging.getLogger().handlers: h.flush()
            # os.system 대신 Popen으로 실행 후 기다리지 않음
            subprocess.Popen("taskkill /f /im node.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen("taskkill /f /im chrome.exe /fi \"memusage lt 50000\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen("taskkill /f /im msedge.exe /fi \"memusage lt 50000\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # 타임아웃 0.5초만 주고 바로 다음으로 패스
            time.sleep(0.5) 
        except: pass

    browser = None 
    try:
        async with async_playwright() as p:

            # Cloud-Compatible Browser Launch Logic
            browser = None

            launch_args = [
                "--disable-blink-features=AutomationControlled", 
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-position=1300,0",
                "--window-size=450,1050"
            ]
            if app_mode:
                launch_args.append("--app=https://m.place.naver.com")
            
            # [NEW] IMMEDIATE START SIGNALING
            summary_data = {
                "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
                "success_count": 0,
                "skip_count": 0,
                "error_count": 0,
                "elapsed_sec": 0,
                "elapsed_time": "00:00:00",
                "estimated_total": target_count,
                "completion_ratio": 0.0,
                "avg_time_per_item": 0.0,
                "remaining_time": "--:--:--",
                "estimation_confidence": "초기화 중",
                "current_stage": "엔진 최적화 및 브라우저 기동 중..."
            }
            try:
                with open(progress_file, "w", encoding="utf-8") as f:
                    json.dump(summary_data, f, ensure_ascii=False, indent=2)
                print(f"PROGRESS_JSON: {json.dumps(summary_data, ensure_ascii=False)}", flush=True)
            except: pass

            # Strategy 1: Try system chromium (for Streamlit Cloud / Linux)
            if os.path.exists("/usr/bin/chromium"):
                try:
                    logger.info("🌐 Using system chromium at /usr/bin/chromium")
                    browser = await p.chromium.launch(
                        executable_path="/usr/bin/chromium",
                        headless=False,
                        args=launch_args
                    )
                except Exception as e:
                    logger.warning(f"System chromium failed: {e}")
            
            # Strategy 2: Fallback to System Chrome/Edge
            if not browser:
                try:
                    logger.info("🌐 Launching System Chrome/Edge (Headed)...")
                    try:
                        browser = await p.chromium.launch(headless=False, args=launch_args, channel="chrome", timeout=30000)
                    except Exception:
                        browser = await p.chromium.launch(headless=False, args=launch_args, channel="msedge", timeout=30000)
                except Exception as e:
                    logger.warning(f"⚠️ Headed launch failed: {e}. Trying bundled fallback...")

            # Strategy 3: Fallback to Playwright's bundled browser
            if not browser:
                try:
                    logger.info("🌐 Using Playwright bundled browser")
                    browser = await p.chromium.launch(
                        headless=False,
                        args=launch_args
                    )
                except Exception as e:
                    logger.error(f"Failed to launch browser: {e}")
                    raise
            
            # User-Agent Rotation (Using our expanded list)
            user_agent = get_random_ua()
            logger.info(f"🎭 Using User-Agent: {user_agent}")
            
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": random.randint(375, 414), "height": random.randint(667, 915)},
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                permissions=["geolocation"]
            )
            
            # Disable webdriver flag proactively
            # await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await context.new_page()
            
            # 🕵️ ACTIVATE STEALTH MODE
            logger.info("🕵️ Activating Playwright Stealth Mode...")
            await Stealth().apply_stealth_async(page)

            
            # Helper for Audit Logging
            def log_audit(keyword, count, status):
                try:
                    file_exists = os.path.isfile("crawl_audit.csv")
                    with open("crawl_audit.csv", "a", encoding="utf-8-sig", newline="") as f:
                        writer = csv.writer(f)
                        if not file_exists:
                            writer.writerow(["Timestamp", "Keyword", "Shops_Found", "Status"])
                        writer.writerow([
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            keyword,
                            count,
                            status
                        ])
                except Exception as e:
                    logger.error(f"Audit Log Error: {e}")

            keyword_count = 0
            for keyword in keywords_to_run:
                if total_saved >= target_count: break
                
                keyword_count += 1
                # ☕ Coffee Break: Shortened to ~70s as requested
                if keyword_count > 0 and keyword_count % random.randint(5, 7) == 0:
                    long_pause = random.uniform(60, 80)
                    logger.info(f"☕ Taking a safety break... (Safety Pause: {long_pause:.1f}s)")
                    await asyncio.sleep(long_pause)
                
                # 🚦 Inter-Keyword Delay
                if keyword_count > 1:
                    kw_delay = random.uniform(kw_min, kw_max)
                    logger.info(f"⏳ Waiting {kw_delay:.1f}s before next keyword search...")
                    await asyncio.sleep(kw_delay)
                    
                # Retry Loop for Robustness
                max_retries = 2
                shops_found_in_keyword = 0
                
                for attempt in range(max_retries):
                    logger.info(f"🔍 Searching: {keyword} (Attempt {attempt+1}/{max_retries})")
                    url = f"https://m.place.naver.com/place/list?query={keyword}"
                    
                    try:
                        await page.goto(url, wait_until="networkidle")
                        await asyncio.sleep(random.uniform(5, 8))
                        
                        # Block Detection
                        content = await page.content()
                        if "서비스 이용이 제한되었습니다" in content or "과도한 접근 요청" in content:
                            logger.error("🛑 IP Blocked by Naver. Stopping crawler to prevent further damage.")
                            log_audit(keyword, 0, "BLOCKED")
                            print("🛑 CRITICAL: IP BLOCK DETECTED. PLEASE STOP AND WAIT.", flush=True)
                            # Do not close browser here, let finally handle it.
                            return
                        
                        # Check for Map View and switch to list if necessary (Stronger detection)
                        # Naver often shows map first on mobile
                        list_view_selectors = [
                            "a:has-text('목록보기')", "button:has-text('목록보기')",
                            "a:has-text('목록')", "button:has-text('목록')",
                            "._list_view_button", "[data-nclicks-code='listview']"
                        ]
                        
                        for lv_sel in list_view_selectors:
                            btn = page.locator(lv_sel).first
                            if await btn.count() > 0 and await btn.is_visible():
                                logger.info(f"🗺️ Map view detected via '{lv_sel}'. Switching to list view...")
                                await btn.click()
                                await asyncio.sleep(random.uniform(3, 5))
                                break
        
                        # Scroll to load more (Human-like)
                        logger.info("🖱️ Scrolling with human-like pattern...")
                        last_height = 0
                        for i in range(40): 
                            # Random scroll distance
                            scroll_amount = random.randint(400, 900)
                            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                            
                            # Occasional jitter or micro-pause
                            if random.random() > 0.7:
                                await asyncio.sleep(random.uniform(0.5, 1.2))
                            else:
                                await asyncio.sleep(random.uniform(1.5, 2.5))
                            
                            new_height = await page.evaluate("document.body.scrollHeight")
                            if new_height == last_height: 
                                # Try one more time with a longer wait and a bigger scroll
                                await asyncio.sleep(2.5)
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                new_height = await page.evaluate("document.body.scrollHeight")
                                if new_height == last_height: break
                            last_height = new_height
                            if i % 10 == 0: logger.info(f"  .. scrolled {i} times")
                        
                        # Wait for items (Expanded list of potential selectors)
                        selectors = [
                            "li.VLTHu", "li[data-id]", "li.item_root", "li.UE77Y", 
                            "div.UE77Y", "li.rY_pS", "div.rY_pS", "ul > li"
                        ]
                        list_items = []
                        for sel in selectors:
                            items = await page.locator(sel).all()
                            # Filter for items that actually look like results (have links)
                            valid_items = []
                            for it in items:
                                if await it.locator("a[href*='/place/']").count() > 0:
                                    valid_items.append(it)
                            
                            if len(valid_items) > 1: # Found a list
                                list_items = valid_items
                                logger.info(f"✅ Found list using selector: {sel}")
                                break
                        
                        if not list_items:
                            # Final fallback: any anchor with /place/ inside a list-like structure
                            list_items = await page.locator("a[href*='/place/']").all()
        
                        shops_found_in_keyword = len(list_items)
                        logger.info(f"🔍 Found {shops_found_in_keyword} potential shops.")
                        
                        # RETRY DECISION
                        if shops_found_in_keyword == 0:
                            if attempt < max_retries - 1:
                                logger.warning(f"⚠️ Zero results found for '{keyword}'. Retrying in 60s...")
                                log_audit(keyword, 0, f"RETRY_WAIT_{attempt+1}")
                                await asyncio.sleep(60)
                                continue
                            else:
                                logger.error(f"❌ Zero results found for '{keyword}' after retries.")
                                log_audit(keyword, 0, "ZERO_RESULTS_FINAL")
                                break # Move to next keyword
                        
                        # SUCCESS - Log and Proceed
                        log_audit(keyword, shops_found_in_keyword, "SUCCESS")
                        
                        # [NEW] Track for Adaptive Moving Average Estimation
                        total_keywords_processed += 1
                        total_shops_discovered += shops_found_in_keyword
                        
                        # --- PROGRESS ESTIMATION LOGIC (LEVEL B/C) ---
                        # Update estimated total based on shops found in this keyword
                        try:
                            current_idx = keywords_to_run.index(keyword)
                            remaining_kws = len(keywords_to_run[current_idx+1:])
                            avg_shops_per_kw = total_shops_discovered / total_keywords_processed
                            predicted_total = int(total_saved + (shops_found_in_keyword * 1.0) + (remaining_kws * avg_shops_per_kw))
                            
                            if target_count >= 90000:
                                # Unlimited mode: use full prediction
                                estimated_total = max(predicted_total, total_saved + 1)
                            else:
                                # [FIXED] Smart Capping: If prediction is less than the limit (e.g. 50), show the lower number.
                                # If it's more, cap it at the limit.
                                estimated_total = min(predicted_total, target_count)
                                # But never lower than what we already found/saved
                                estimated_total = max(estimated_total, total_saved + 1)
                        except:
                            if target_count >= 90000:
                                estimated_total = total_saved + shops_found_in_keyword
                            else:
                                estimated_total = min(total_saved + shops_found_in_keyword, target_count)
                                estimated_total = max(estimated_total, total_saved + 1)
                        
                        # [NEW] REPORT LIST DISCOVERY IMMEDIATELY
                        prog_data = {
                            "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
                            "success_count": total_saved,
                            "skip_count": total_skipped,
                            "error_count": total_errors,
                            "elapsed_sec": int(time.time() - start_time),
                            "estimated_total": estimated_total,
                            "completion_ratio": round(total_saved / estimated_total, 4) if estimated_total > 0 else 0,
                            "avg_time_per_item": 0.0,
                            "remaining_time": "추정 중...",
                            "estimation_confidence": "리스트 분석 중",
                            "current_stage": f"🔍 [{keyword}] {shops_found_in_keyword}개 업체 발견! 수집 시작..."
                        }
                        with open(progress_file, "w", encoding="utf-8") as f:
                            json.dump(prog_data, f, ensure_ascii=False, indent=2)
                        print(f"PROGRESS_JSON: {json.dumps(prog_data, ensure_ascii=False)}", flush=True)
                        # Lower bound constraint (Only if unbounded)
                        if target_count >= 90000:
                            estimated_total = max(estimated_total, total_saved + 1)
                        # -----------------------------------------------

                        shops_to_visit = []
                        for li in list_items:
                            if len(shops_to_visit) >= (target_count - total_saved): break
                            
                            try:
                                # 1. Detect if li is the link itself or a container
                                link_node = None
                                tag_name = await li.evaluate("el => el.tagName.toLowerCase()")
                                href = await li.get_attribute("href")
                                
                                if tag_name == "a" and href and "/place/" in href:
                                    link_node = li
                                else:
                                    # Search for the primary place link inside container
                                    potential_links = li.locator("a[href*='/place/']")
                                    if await potential_links.count() > 0:
                                        link_node = potential_links.first
        
                                if link_node:
                                    href = await link_node.get_attribute("href")
                                    match = re.search(r'/place/(\d+)', href)
                                    if not match: continue
                                    place_id = match.group(1)
                                    detail_url = f"https://m.place.naver.com/place/{place_id}/home"
                                    
                                    # ⚡ SMART SKIP CHECK (Rule 3.3 Optimized)
                                    if db.exists_by_url(detail_url):
                                        total_skipped += 1
                                        continue # Skip without logging to reduce noise
                                    
                                    # [ENHANCED] Get Name with Error Check
                                    raw_name = await li.locator("span.TYaxf, span.place_bluelink, span.YwYLL").first.text_content()
                                    if not raw_name or "일시적인 오류" in raw_name or "다시 시도" in raw_name:
                                        logger.warning("⚠️ Naver returned an error message instead of a shop name. Skipping item.")
                                        continue
                                        
                                    name = raw_name.replace("알림받기", "").replace("N예약", "").strip()
                                    
                                    # 🚫 KEYWORD FILTERING
                                    # User requested to exclude specific types of shops
                                    if any(ex in name for ex in exclude_list):
                                        logger.info(f"🚫 Filtering out '{name}' (Excluded Keyword).")
                                        total_skipped += 1
                                        continue
                                    
                                    phone = ""
                                    try:
                                        tel_link = li.locator("a[href^='tel:']").first
                                        if await tel_link.count() > 0:
                                            tel_href = await tel_link.get_attribute("href")
                                            phone = tel_href.replace("tel:", "").strip()
                                    except: pass
                                    
                                    # Deduplicate in the current batch AND check existing again (double check)
                                    if not any(s['detail_url'] == detail_url for s in shops_to_visit):
                                        shops_to_visit.append({
                                            "name": name if name else f"Shop_{place_id}",
                                            "phone": phone,
                                            "detail_url": detail_url,
                                            "source_link": detail_url,
                                            "keyword": keyword
                                        })
                            except Exception as e: 
                                logger.debug(f"Error parsing list item: {e}")
                                continue

        
                        logger.info(f"📍 Scheduled {len(shops_to_visit)} new shops for detail extraction.")
        
                        # [FIX] Update progress after scanning the list, so dashboard reflects skipped duplicates
                        processed_items = total_saved + total_skipped
                        elapsed_sec = int(time.time() - start_time)
                        avg_sec = elapsed_sec / processed_items if processed_items > 0 else 0
                        remain = max(0, estimated_total - processed_items)
                        
                        def format_sec(s):
                            return f"{s // 3600:02}:{(s % 3600) // 60:02}:{s % 60:02}"

                        completion_ratio = processed_items / estimated_total if estimated_total > 0 else 0
                        
                        summary_data = {
                            "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
                            "success_count": total_saved,
                            "skip_count": total_skipped,
                            "error_count": total_errors,
                            "elapsed_sec": elapsed_sec,
                            "elapsed_time": format_sec(elapsed_sec),
                            "estimated_total": estimated_total,
                            "completion_ratio": round(completion_ratio, 4),
                            "avg_time_per_item": round(avg_sec, 2),
                            "remaining_time": format_sec(int(remain * avg_sec)),
                            "estimation_confidence": "안정 추정" if completion_ratio > 0.4 else "중간 추정" if completion_ratio > 0.1 else "초기 추정",
                            "current_stage": f"📍 [{keyword}] 리스트 확인 완료. 남은 추출 진행 중..."
                        }
                        try:
                            with open(progress_file, "w", encoding="utf-8") as f:
                                json.dump(summary_data, f, ensure_ascii=False, indent=2)
                        except: pass
        
                        # Visit each shop's detail page
                        for shop_idx, shop_data in enumerate(shops_to_visit):
                            if total_saved >= target_count: break
                            
                            # [NEW] REPORT CURRENT TARGET IMMEDIATELY
                            current_prog = {
                                "success_count": total_saved,
                                "estimated_total": estimated_total,
                                "current_stage": f"📍 [{keyword}] {shop_idx+1}/{len(shops_to_visit)}: {shop_data.get('name')} 분석 중..."
                            }
                            # Simple merge for UI update
                            try:
                                with open(progress_file, "r", encoding="utf-8") as f:
                                    full_prog = json.load(f)
                                full_prog.update(current_prog)
                                with open(progress_file, "w", encoding="utf-8") as f:
                                    json.dump(full_prog, f, ensure_ascii=False, indent=2)
                                print(f"PROGRESS_JSON: {json.dumps(full_prog, ensure_ascii=False)}", flush=True)
                            except: pass
                            
                            shop_data.update({
                                "owner_name": "",
                                "address": "",
                                "latitude": 0.0,
                                "longitude": 0.0,
                                "email": "",
                                "instagram_handle": "",
                                "naver_blog_id": "",
                                "talk_url": ""
                            })
        
                            if await extract_detail_info(page, shop_data):
                                try:
                                    if shop_data.get("name") and shop_data.get("address"):
                                        # 🛡️ FINAL DEFENSE: Keyword Filtering Check (Detail Level)
                                        # Re-check name in case detail extraction found a fuller name containing forbidden keywords
                                        if any(ex in shop_data['name'] for ex in exclude_list):
                                            logger.warning(f"🛡️ Filtered out shop at detail level: {shop_data['name']} (Exclusion)")
                                            total_skipped += 1
                                            continue
                                        
                                        # [FIXED] Address Verification: Strict Boundary Control (Monster Rule 3.2)
                                        addr = shop_data.get('address', '')
                                        is_valid_addr = False
                                        
                                        # Use 'targets' variable (Fixed NameError from target_areas)
                                        for t_area in targets:
                                            # 유연한 매칭: '경기도' <-> '경기', '서울특별시' <-> '서울' 등 지원
                                            clean_t = t_area.replace("특별시", "").replace("광역시", "").replace("자치시", "").replace("도", "").strip()
                                            tokens = clean_t.split()
                                            
                                            if len(tokens) >= 2:
                                                core_region = " ".join(tokens[-2:]) 
                                                if core_region in addr or clean_t in addr:
                                                    is_valid_addr = True
                                                    break
                                            else:
                                                if clean_t in addr:
                                                    is_valid_addr = True
                                                    break
                                        
                                        if not is_valid_addr:
                                            logger.info(f"🚫 Filtered out (Out of Bounds): {shop_data['name']} ({addr}) | Target: {targets}")
                                            total_skipped += 1
                                            continue
                                        
                                        # [NEW] Multi-Mode Filtering Logic
                                        if filter_mode != 'all' and filter_keyword:
                                            passed = False
                                            if filter_mode == 'name':
                                                if filter_keyword in shop_data['name']: passed = True
                                            elif filter_mode == 'category':
                                                cat = shop_data.get('category', '')
                                                if filter_keyword in cat: passed = True
                                            
                                            if not passed:
                                                logger.info(f"🛡️ Filtered out by Mode '{filter_mode}': {shop_data['name']}")
                                                total_skipped += 1
                                                continue

                                        if save_to_db(shop_data):
                                            total_saved += 1
                                            logger.info(f"✅ Saved ({total_saved}/{target_count}): {shop_data.get('name')}")
                                            
                                            # [FIXED] Force immediate progress report WITH ETA (Monster Rule 3.2)
                                            try:
                                                elapsed_sec = int(time.time() - start_time)
                                                processed = total_saved + total_skipped
                                                avg_sec = elapsed_sec / processed if processed > 0 else 0
                                                remain = max(0, estimated_total - processed)
                                                
                                                def format_sec(s):
                                                    return f"{s // 3600:02}:{(s % 3600) // 60:02}:{s % 60:02}"

                                                summary_data.update({
                                                    "success_count": total_saved,
                                                    "skip_count": total_skipped,
                                                    "elapsed_sec": elapsed_sec,
                                                    "elapsed_time": format_sec(elapsed_sec),
                                                    "avg_time_per_item": round(avg_sec, 2),
                                                    "remaining_time": format_sec(int(remain * avg_sec)),
                                                    "completion_ratio": round(total_saved / estimated_total, 4) if estimated_total > 0 else 0,
                                                    "current_stage": f"✅ [{keyword}] {shop_idx+1}/{len(shops_to_visit)}: {shop_data.get('name')} 추출 및 저장 완료!"
                                                })
                                                with open(progress_file, "w", encoding="utf-8") as f:
                                                    json.dump(summary_data, f, ensure_ascii=False, indent=2)
                                            except: pass
                                    else:
                                        logger.warning(f"⏩ Skipping shop {shop_data.get('name')} due to missing critical info (Address).")
                                finally:
                                    # Always update progress for general stats
                                    elapsed_sec = int(time.time() - start_time)
                                    # Calculate avg_sec using (saved + skipped) to show accurate speed
                                    processed_items = total_saved + total_skipped
                                    avg_sec = elapsed_sec / processed_items if processed_items > 0 else 0
                                    remain = max(0, estimated_total - processed_items)
                                    eta_sec = int(remain * avg_sec)
                                    
                                    def format_sec(s):
                                        return f"{s // 3600:02}:{(s % 3600) // 60:02}:{s % 60:02}"

                                    completion_ratio = processed_items / estimated_total if estimated_total > 0 else 0
                                    confidence = "초기 추정" if completion_ratio < 0.1 else "중간 추정" if completion_ratio < 0.4 else "안정 추정"
                                        
                                    summary_data = {
                                        "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_time)),
                                        "success_count": total_saved,
                                        "skip_count": total_skipped,
                                        "error_count": total_errors,
                                        "elapsed_sec": elapsed_sec,
                                        "elapsed_time": format_sec(elapsed_sec),
                                        "estimated_total": estimated_total,
                                        "completion_ratio": round(completion_ratio, 4),
                                        "avg_time_per_item": round(avg_sec, 2),
                                        "remaining_time": format_sec(eta_sec),
                                        "estimation_confidence": confidence,
                                        "current_stage": f"🔄 [{keyword}] {shop_idx+1}/{len(shops_to_visit)}: 추출 및 검증 완료"
                                    }
                                    try:
                                        with open(progress_file, "w", encoding="utf-8") as f:
                                            json.dump(summary_data, f, ensure_ascii=False, indent=2)
                                        print(f"PROGRESS_JSON: {json.dumps(summary_data, ensure_ascii=False)}", flush=True)
                                    except: pass
                            
                            # [FAST] Aggressive delay for commercial speed
                            sleep_time = random.uniform(min_delay, max_delay)
                            logger.info(f"⏳ Waiting {sleep_time:.1f}s before next shop detail...")
                            await asyncio.sleep(sleep_time)

                            # 🧘 Micro safety break every 10 items
                            if total_saved > 0 and total_saved % 10 == 0:
                                micro_break = random.uniform(60, 80)
                                logger.info(f"🧘 Session break for safety... (Pause: {micro_break:.1f}s)")
                                await asyncio.sleep(micro_break)
                        
                        # If we reached here, the keyword attempt was successful
                        break 

                    except Exception as e:
                         logger.error(f"Error processing keyword {keyword}: {e}")
                         log_audit(keyword, 0, f"ERROR_{type(e).__name__}")
                         total_errors += 1

                # ✅ Save checkpoint after each successful keyword (DONG)
                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump({"last_keyword": keyword, "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
                logger.info(f"💾 Checkpoint saved: {keyword}")

        logger.info(f"✅ Crawling Session Finished. Total locally cached: {total_saved}")
        
        # Save final checkpoint as finished
        if keywords_to_run:
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump({"last_keyword": keywords_to_run[-1], "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
                
        # [NEW] Write completion status to progress.json
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                prog_data = json.load(f)
            prog_data["status"] = "completed"
            prog_data["current_stage"] = "🎉 수집이 완료되었습니다!"
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump(prog_data, f, ensure_ascii=False, indent=2)
            print(f"PROGRESS_JSON: {json.dumps(prog_data, ensure_ascii=False)}", flush=True)
        except: pass

    except Exception as e:
        logger.error(f"Error in run_crawler session: {e}")
    finally:
        # 🚀 FINAL SYNC REMOVED (Migrated to SQLite)
        logger.info("🏁 Crawling session finished. Data is safely stored in SQLite.")
        
        if browser:
            await browser.close()
            logger.info("🌐 Browser closed.")

if __name__ == "__main__":
    # Move immediate progress signaling to the ABSOLUTE START of execution
    # Argument parsing
    # Argument parsing
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target in ["None", "전체", "전체 지역"]: target = None
    
    raw_count = sys.argv[2] if len(sys.argv) > 2 else "10"
    try:
        count = int(raw_count) if raw_count not in ["None", ""] else 10
    except:
        count = 10
        
    # Handle shop_type (3rd argument)
    shop_type = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None
    
    resume_mode = "--resume" in sys.argv
    app_mode = "--app" in sys.argv
    
    # 📢 THIS IS THE MOST CRITICAL LINE FOR DASHBOARD FEEDBACK
    print(f"Progress: 0/{count}", flush=True)
    
    # Check Environment
    is_cloud = os.environ.get("STREAMLIT_RUNTIME_ENV") or "/home/appuser" in os.getcwd() or os.environ.get("STREAMLIT_SERVER_BASE_URL")
    if is_cloud:
        print(f"DEBUG: Running on Cloud Environment. Python: {sys.executable}", flush=True)
    
    exclude_val = None
    filter_mode_arg = 'all'
    filter_kw_arg = ''
    for i, arg in enumerate(sys.argv):
        if arg == "--exclude" and i + 1 < len(sys.argv):
            exclude_val = sys.argv[i+1]
        elif arg == "--filter-mode" and i + 1 < len(sys.argv):
            filter_mode_arg = sys.argv[i+1]
        elif arg == "--filter-keyword" and i + 1 < len(sys.argv):
            filter_kw_arg = sys.argv[i+1]

    try:
        asyncio.run(run_crawler(target, count, resume=resume_mode, shop_type=shop_type, app_mode=app_mode, exclude_keywords=exclude_val, filter_mode=filter_mode_arg, filter_keyword=filter_kw_arg))
        
        # 🎯 AUTOMATIC COMPETITOR EXTRACTION DISABLED (Manual control requested)
        # print("Progress: Finalizing...", flush=True)
        # logger.info("🎯 Crawling complete. Automatic competitor extraction is disabled.")
        
        logger.info("✅ Crawling finished successfully!")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}", flush=True)
        logger.error(f"Engine crashed: {e}")
        sys.exit(1)
