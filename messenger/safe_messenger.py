import asyncio
import random
import logging
import os
import sys
import json
from playwright.async_api import async_playwright

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

# Logging setup
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'instagram_dm.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Persistent Context Path
USER_DATA_DIR = os.path.join(os.getcwd(), "browser_session")

try:
    from crawler.db_handler import DBHandler
    db = DBHandler()
except Exception as e:
    logger.warning(f"DBHandler not available: {e}")
    db = None

async def download_session(platform):
    """Download session from Supabase and extract to USER_DATA_DIR."""
    state_path = os.path.join(USER_DATA_DIR, f"{platform}_state.json")
    
    if db and hasattr(db, 'load_session'):
        try:
            session_json = db.load_session(platform)
            if session_json:
                os.makedirs(USER_DATA_DIR, exist_ok=True)
                with open(state_path, 'w', encoding='utf-8') as f:
                    f.write(session_json)
                logger.info(f"Downloaded {platform} session from DB to {state_path}")
                return state_path
            else:
                logger.warning(f"No {platform} session found in DB.")
        except Exception as e:
            logger.error(f"Failed to download session from DB: {e}")
            
    # Fallback: check if local file exists
    if os.path.exists(state_path):
        logger.info(f"Using existing local {platform} session: {state_path}")
        return state_path
        
    return None

async def upload_session(page, platform):
    """Save current browser state to Supabase."""
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    state_path = os.path.join(USER_DATA_DIR, f"{platform}_state.json")
    await page.context.storage_state(path=state_path)
    if db and hasattr(db, 'save_session'):
        with open(state_path, 'r', encoding='utf-8') as f:
            db.save_session(platform, f.read())

async def human_delay(min_sec=2, max_sec=5):
    """Realistic human-like delay."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def slow_type(element, text):
    """Type text slowly, like a human."""
    for char in text:
        await element.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.2))

async def send_talktalk_message(page, talk_url, message):
    """Automates sending a Naver TalkTalk message."""
    logger.info(f"Opening TalkTalk: {talk_url}")
    await page.goto(talk_url, wait_until="networkidle")
    await human_delay(3, 6)
    
    # 1. Look for the message input area
    # Note: Selector might change, using common ones for TalkTalk
    input_selector = "textarea, div[contenteditable='true'], .chat_input_area"
    input_area = page.locator(input_selector).first
    
    if await input_area.count() > 0:
        await input_area.click()
        await human_delay(1, 2)
        await slow_type(input_area, message)
        await human_delay(1, 2)
        
        # 2. Look for the send button
        send_btn = page.locator("button:has-text('전송'), button.btn_send").first
        if await send_btn.count() > 0:
            await send_btn.click()
            logger.info("TalkTalk Message Sent!")
            return True
        else:
            logger.error("Could not find TalkTalk send button")
    else:
        logger.error("Could not find TalkTalk input area. Is the user logged in?")
    return False

async def send_instagram_dm(page, insta_url, message, image_path=None):
    """Automates sending an Instagram DM with robust pop-up handling and optional image."""
    logger.info(f"Opening Instagram Target: {insta_url}")
    try:
        # domcontentloaded is faster and less prone to background noise than networkidle
        await page.goto(insta_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        logger.warning(f"Initial navigation to {insta_url} slow, attempting to proceed anyway: {e}")
        # If it failed to load completely in 45s, it might still have enough content to find the button

        
    await human_delay(4, 7)
    
    # --- HANDLING COMMON POP-UPS ---
    # Dialogs like 'Turn on Notifications' or 'Save Info' can block interactions
    not_now_selectors = [
        "//button[text()='Not Now']",
        "//button[text()='나중에 하기']",
        "button._a9--._ap3a._aade", # Common class for notify not now
        "//button[contains(., '나중에')]"
    ]
    
    # Check for modals 3 times with delays
    for _ in range(2):
        for selector in not_now_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    logger.info(f"Closing pop-up using selector: {selector}")
                    await loc.click()
                    await human_delay(1, 2)
            except:
                continue

    # 1. Click "Message" button on profile
    msg_btn_selectors = [
        "//div[@role='button' and (text()='Message' or text()='메시지 보내기')]",
        "//button[text()='Message' or text()='메시지 보내기']",
        "div[role='button']:has-text('메시지 보내기')",
        "button:has-text('Message')",
        "div[role='button']:has-text('Message')",
        "button:has-text('메시지 보내기')",
        "[aria-label='Message']",
        "[aria-label='메시지 보내기']",
        "a:has-text('Message')", 
        "a:has-text('메시지 보내기')",
        "div._ab8w._ab94._ab99._ab9f._ab9m._ab9p._ab9-._aba8._abcm button" # specific class chain fallback
    ]

    
    msg_btn = None
    for selector in msg_btn_selectors:
        try:
            loc = page.locator(selector).first
            if await loc.count() > 0 and await loc.is_visible():
                msg_btn = loc
                logger.info(f"Found Message button directly: {selector}")
                break
        except:
            continue

    # --- NEW: Handling hidden Message button behind '...' menu ---
    if not msg_btn:
        logger.info("Message button not found directly. Checking '...' (Options) menu...")
        # Common selectors for the '...' menu button
        options_btn_selectors = [
            "svg[aria-label='옵션']",
            "svg[aria-label='Options']",
            "div[role='button']:has(svg[aria-label='옵션'])",
            "div[role='button']:has(svg[aria-label='Options'])",
            "button:has(svg[aria-label='옵션'])",
            "button:has(svg[aria-label='Options'])",
            "//div[@role='button']//svg[@aria-label='옵션']",
            "//div[@role='button']//svg[@aria-label='More options']"
        ]
        
        for selector in options_btn_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    logger.info(f"Found Options menu button: {selector}")
                    await loc.click()
                    await human_delay(2, 4)
                    
                    # Now look for Message button in the menu
                    menu_msg_selectors = [
                        "button:has-text('메시지 보내기')",
                        "button:has-text('Send Message')",
                        "//button[text()='메시지 보내기']",
                        "//button[text()='Message']",
                        "div[role='button']:has-text('메시지 보내기')"
                    ]
                    for m_selector in menu_msg_selectors:
                        m_loc = page.locator(m_selector).first
                        if await m_loc.count() > 0 and await m_loc.is_visible():
                            msg_btn = m_loc
                            logger.info(f"Found Message button in menu: {m_selector}")
                            break
                    if msg_btn: break
            except:
                continue

    if msg_btn:
        logger.info("Clicking Message button...")
        try:
            await msg_btn.click()
        except:
            # Sometime it's blocked by a div, force click via JS
            await msg_btn.evaluate("b => b.click()")
            
        await human_delay(5, 8)
        
        # Check for login wall (like previous screenshot)
        if "login" in page.url or await page.locator("input[name='username']").count() > 0:
            logger.warning("Still seeing login screen! Login might have failed.")
            return False

        # Check for another potential 'Not Now' after navigation
        for selector in not_now_selectors:
            try:
                loc = page.locator(selector).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click()
                    await human_delay(1, 2)
            except:
                continue

        # 2. Look for the chat input
        chat_input_selectors = [
            "div[role='textbox'][aria-label*='메시지']",
            "div[role='textbox'][aria-label*='Message']",
            "div[contenteditable='true'][aria-label*='메시지']",
            "div[contenteditable='true'][aria-label*='Message']",
            "textarea[placeholder*='메시지']",
            "textarea[placeholder*='Message']",
            "div[aria-placeholder*='메시지']",
            "div[aria-placeholder*='Message']",
            "div.xat24cr.xdj266r.xdpx789" # Dynamic class fallback
        ]

        
        chat_input = None
        for selector in chat_input_selectors:
            try:
                loc = page.locator(selector).last 
                if await loc.count() > 0:
                    chat_input = loc
                    logger.info(f"Found chat input with selector: {selector}")
                    break
            except:
                continue

        if chat_input:
            logger.info("Typing message...")
            try:
                await chat_input.click()
                await human_delay(1, 2)
                await slow_type(chat_input, message)
                await human_delay(1, 2)
                
                # 3. Send message 
                logger.info("Sending message (Pressing Enter)...")
                await chat_input.press("Enter")
                await human_delay(1, 2)
                
                # Check for an explicit "Send" button and click it if it remains
                send_button_selectors = ["button:has-text('Send')", "button:has-text('보내기')", "//div[text()='Send']", "//div[text()='보내기']"]
                for s_sel in send_button_selectors:
                    try:
                        s_btn = page.locator(s_sel).first
                        if await s_btn.count() > 0 and await s_btn.is_visible():
                            logger.info(f"Clicking explicit Send button: {s_sel}")
                            await s_btn.click()
                            break
                    except: pass
                
                await human_delay(2, 4)

                
                # --- IMAGE UPLOAD ---
                if image_path and os.path.exists(image_path):
                    logger.info(f"Attaching image: {image_path}")
                    try:
                        # Target the hidden file input
                        file_input = page.locator("input[type='file']").last
                        await file_input.set_input_files(image_path)
                        await human_delay(5, 10) # Wait for upload to complete
                        logger.info("Image attached. Pressing Enter to send image...")
                        
                        # Press Enter to send the attached image
                        await page.keyboard.press("Enter")
                        await human_delay(3, 5)
                        
                        # Fallback: Sometimes a 'Send' button appears for media
                        send_btn = page.locator("button:has-text('Send'), button:has-text('보내기')").first
                        if await send_btn.count() > 0 and await send_btn.is_visible():
                            await send_btn.click()
                            await human_delay(2, 4)
                            
                        logger.info("Image send action triggered.")
                    except Exception as e:
                        logger.error(f"Failed to attach image: {e}")

                logger.info("Instagram DM flow completed successfully.")
                return True
            except Exception as e:
                logger.error(f"Error during message typing/sending: {e}")
        else:
            logger.error("Could not find Instagram chat input box.")
            try: await page.screenshot(path=os.path.join(USER_DATA_DIR, "debug_insta_no_input.png"))
            except: pass
    else:
        logger.error("Could not find 'Message' button on profile. Profile might be private or UI changed.")
        try: await page.screenshot(path=os.path.join(USER_DATA_DIR, "debug_insta_no_msg_btn.png"))
        except: pass
    return False

async def login_instagram(page, username, password):
    """Handles Instagram login with intelligent session check."""
    logger.info("Checking Instagram login status... (PLEASE DO NOT CLOSE THE BROWSER WINDOW)")
    try:
        # Check homepage
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
        await human_delay(3, 5)

        
        # --- PHASE 1: Determine initial state ---
        # We look for definite signs of being logged in vs logged out
        logged_in_indicators = ["svg[aria-label='Home']", "svg[aria-label='홈']", "svg[aria-label='Search']", "svg[aria-label='검색']"]
        login_form_indicators = ["input[name='username']", "button:has-text('Log in')", "button:has-text('로그인')"]
        
        is_logged_in = False
        is_at_login_form = False
        
        # Wait up to 10 seconds to see which one appears first
        for _ in range(5):
            for sel in logged_in_indicators:
                if await page.locator(sel).count() > 0:
                    is_logged_in = True
                    break
            if is_logged_in: break
            
            for sel in login_form_indicators:
                if await page.locator(sel).count() > 0:
                    is_at_login_form = True
                    break
            if is_at_login_form: break
            await asyncio.sleep(2)

        # --- PHASE 2: Action based on state ---
        if is_logged_in:
            logger.info("Instagram session VALID. Already logged in.")
            return True
            
        logger.info("Instagram login REQUIRED. Waiting for user or attempting auto-fill...")
        
        # Try auto-fill if we see the fields
        if await page.locator("input[name='username']").count() > 0:
            try:
                await page.locator("input[name='username']").fill(username)
                await page.locator("input[name='password']").fill(password)
                await page.locator("button[type='submit']").click()
                logger.info("Auto-fill attempted. Waiting for you to complete any challenges...")
            except: pass

        # --- PHASE 3: Continuous Detection Loop (User takes over) ---
        logger.info(">>> PLEASE FINISH LOGIN IN THE BROWSER WINDOW. Waiting for success detection (3m)...")
        
        login_detected = False
        for i in range(36): # 180 seconds
            await asyncio.sleep(5)
            # Check for logged-in indicators again
            for sel in logged_in_indicators:
                if await page.locator(sel).count() > 0:
                    login_detected = True
                    break
            if login_detected:
                logger.info("Instagram login SUCCESS detected via user action!")
                break
            
            if i % 6 == 0 and i > 0:
                logger.info(f"Waiting for login... ({i*5}s elapsed)")

        if not login_detected:
            logger.error("Login TIMEOUT. Flow aborted.")
            return False
            
        # Post-login cleanup
        logger.info("Login confirmed. Cleaning up pop-ups...")
        await human_delay(3, 5)
        # Handle "Save Info" etc.
        for _ in range(2):
            for sel in ["//button[text()='Save Info']", "//button[text()='정보 저장']", "//button[text()='Not Now']", "//button[text()='나중에 하기']"]:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.click()
                        await human_delay(1, 2)
                except: pass
        
        return True
    except Exception as e:
        logger.error(f"Error during Instagram login check: {e}")
        return False


async def login_naver(page, username, password):
    """Handles Naver login including potential verification."""
    logger.info("Attempting Naver login...")
    await page.goto("https://nid.naver.com/nidlogin.login")
    await human_delay(2, 4)
    
    # Use evaluate to avoid bot detection for input
    await page.evaluate(f'document.getElementById("id").value="{username}"')
    await page.evaluate(f'document.getElementById("pw").value="{password}"')
    await page.locator(".btn_login").click()
    await human_delay(5, 10)
    
    if "nidlogin.login" in page.url:
        logger.warning("Naver login verification required! Check your phone.")
        # Wait for user to confirm on phone or enter code if we had a UI
        # For now, we wait up to 60s for the URL to change
        for _ in range(12):
            await asyncio.sleep(5)
            if "nidlogin.login" not in page.url:
                return True
        return False
    return True


async def main(target_list_json, message, method="both", naver_creds=None, insta_creds=None, image_path=None):
    """
    Args:
        target_list_json: JSON string of shops to message
        message: The message body
        method: 'talk', 'insta', or 'both'
        naver_creds: (user, pw)
        insta_creds: (user, pw)
        image_path: Optional path to an image to send
    """
    targets = json.loads(target_list_json)
    is_cloud = os.path.exists("/mount/src")
    logger.info(f"Starting auto-messenger. Cloud: {is_cloud}, Targets: {len(targets)}, Method: {method}")
    
    async with async_playwright() as p:
        # Load existing sessions if available
        n_state = await download_session("naver")
        i_state = await download_session("insta")
        
        # Launch browser
        browser = await p.chromium.launch(headless=is_cloud)
        
        # Determine which state to load
        # FIX: We should ideally merge states if we want to use BOTH in one context.
        # For now, let's use a smarter way: load Instagram if we prefer Instagram, or Naver if we prefer TalkTalk.
        # Better: Launch with one, and we'll manually handle the other cookies if needed.
        # But Playwright storage_state is easiest.
        
        selected_state = i_state if method == "insta" else n_state
        if not selected_state:
            selected_state = n_state or i_state
            
        context_args = {
            "viewport": {'width': 1280, 'height': 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if selected_state and os.path.exists(selected_state):
            logger.info(f"Loading session state: {selected_state}")
            context_args["storage_state"] = selected_state
        else:
            logger.warning("Starting browser without session state (logged out).")

        context = await browser.new_context(**context_args)
        page = await context.new_page()

        # Step 1: Login Check/Perform
        if method in ["talk", "both"] and naver_creds:
            n_user, n_pw = naver_creds
            if await login_naver(page, n_user, n_pw):
                await upload_session(page, "naver")
        
        if method in ["insta", "both"] and insta_creds:
            i_user, i_pw = insta_creds
            if await login_instagram(page, i_user, i_pw):
                await upload_session(page, "insta")

        for idx, shop in enumerate(targets):
            logger.info(f"[{idx+1}/{len(targets)}] Targeting: {shop['상호명']}")
            success = False
            
            # --- Naver TalkTalk ---
            if method in ["talk", "both"] and shop.get('톡톡링크'):
                # Ensure we are logged in - simple check
                success = await send_talktalk_message(page, shop['톡톡링크'], message)
            
            # --- Instagram DM ---
            if method == "insta" or (method == "both" and not success):
                if shop.get('인스타'):
                    # Personalized message replacement
                    personalized_msg = message.replace("{상호명}", shop.get('상호명', '원장님'))
                    success = await send_instagram_dm(page, shop['인스타'], personalized_msg, image_path=image_path)
            
            if success:
                if idx < len(targets) - 1:
                    wait_time = random.uniform(60, 120) 
                    logger.info(f"Waiting {wait_time:.1f}s before next send...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.info("Last target reached. No wait needed.")
            else:
                logger.warning(f"Failed to send to {shop['상호명']} via {method}")
                if idx < len(targets) - 1:
                    await human_delay(5, 10)
                
        await browser.close()
        logger.info("Auto-messenger task complete.")

if __name__ == "__main__":
    import json
    # Usage: python safe_messenger.py targets_json message method [naver_u:p] [insta_u:p]
    if len(sys.argv) < 3:
        print("Usage: python safe_messenger.py '<json_targets>' 'message' [method] [naver_u:p] [insta_u:p]")
        sys.exit(1)
        
    targets_json = sys.argv[1]
    msg = sys.argv[2]
    send_method = sys.argv[3] if len(sys.argv) > 3 else "both"
    
    n_creds = None
    if len(sys.argv) > 4 and ":" in sys.argv[4]:
        n_creds = tuple(sys.argv[4].split(":", 1))
        
    i_creds = None
    if len(sys.argv) > 5 and ":" in sys.argv[5]:
        i_creds = tuple(sys.argv[5].split(":", 1))
    
    img_path = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != "NONE" else None
    
    asyncio.run(main(targets_json, msg, send_method, n_creds, i_creds, image_path=img_path))
