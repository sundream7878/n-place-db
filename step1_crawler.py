import asyncio
import csv
import os
import random
import json
from playwright.async_api import async_playwright
import config
from crawler.db_handler import DBHandler

# Ensure output directory exists if needed (current working dir)
OUTPUT_FILE = config.RAW_DATA_FILE

try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

async def run_crawler():
    print(f"[*] Starting Naver Place Crawler (Robust Mode - Headless: {config.HEADLESS_MODE})...")
    
    # Existing data check
    existing_urls = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Detail_Url'):
                        existing_urls.add(row['Detail_Url'])
            print(f"[*] Loaded {len(existing_urls)} existing shops to skip.")
        except: pass
    else:
        with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Address', 'Dong', 'Phone', 'Link', 'Owner_Name', 'Latitude', 'Longitude', 'Detail_Url', 'Keyword'])

    # Batched processing
    BATCH_SIZE = 3
    
    for i in range(0, len(config.TARGET_KEYWORDS), BATCH_SIZE):
        batch = config.TARGET_KEYWORDS[i:i+BATCH_SIZE]
        print(f"\n[batch] Processing keywords {i+1} to {min(i+BATCH_SIZE, len(config.TARGET_KEYWORDS))}")
        
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                async with async_playwright() as p:
                    # Launch options
                    browser = await p.chromium.launch(
                        headless=config.HEADLESS_MODE, # Use True for stability
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                        ]
                    )
                    
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
                        viewport={"width": 390, "height": 844},
                        device_scale_factor=3,
                        is_mobile=True,
                        has_touch=True,
                        locale="ko-KR",
                        timezone_id="Asia/Seoul"
                    )
                    
                    page = await context.new_page()
                    if stealth_async:
                        await stealth_async(page)
                    else:
                        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    
                    for keyword in batch:
                        print(f"\n[+] Processing Keyword: {keyword}")
                        url = config.NAVER_PLACE_URL.format(keyword)
                        
                        try:
                            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                            await asyncio.sleep(random.uniform(2.0, 3.0))
                            
                            # Initial Wait
                            try:
                                await page.wait_for_selector("li, a[href*='/place/']", timeout=10000)
                            except: pass

                            # 1. SCROLL & COLLECT LINKS
                            collected_urls = set()
                            scroll_count = config.SCROLL_COUNT
                            
                            for s_idx in range(scroll_count):
                                await page.keyboard.press("End")
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                await asyncio.sleep(random.uniform(1.0, 2.0))
                                
                                hrefs = await page.evaluate("""() => {
                                    return Array.from(document.querySelectorAll('a')).map(a => a.href)
                                }""")
                                
                                for href in hrefs:
                                    if '/place/' in href and not '/my/' in href and not '/review/' in href:
                                        clean_link = href.split('?')[0]
                                        if clean_link not in existing_urls:
                                            collected_urls.add(clean_link)
                                
                                try:
                                    await page.click("a:has-text('더보기')", timeout=500)
                                    await asyncio.sleep(0.5)
                                except: pass
                            
                            print(f"    -> Found {len(collected_urls)} unique shops.")
                            
                            # Save Intermediate
                            if collected_urls:
                                with open("intermediate_links.csv", "a", encoding="utf-8-sig", newline="") as f:
                                    w = csv.writer(f)
                                    for u in collected_urls:
                                        w.writerow([u, keyword])

                            # 2. VISIT DETAILS
                            for shop_url in collected_urls:
                                if shop_url in existing_urls: continue
                                try:
                                    await page.goto(shop_url, timeout=20000, wait_until="domcontentloaded")
                                    await asyncio.sleep(1.0)
                                    
                                    # Extract Data
                                    shop_data = {
                                        'Name': '', 'Address': '', 'Dong': '', 'Phone': '', 
                                        'Link': '', 'Owner_Name': '', 'Latitude': 0, 'Longitude': 0,
                                        'Detail_Url': shop_url, 'Keyword': keyword
                                    }
                                    
                                    # Script Data Extraction
                                    try:
                                        data_json = await page.evaluate("""() => {
                                            const script = document.querySelector('script[type="application/ld+json"]');
                                            return script ? script.innerText : null;
                                        }""")
                                        
                                        if data_json:
                                            import json
                                            d = json.loads(data_json)
                                            if isinstance(d, list): d = d[0]
                                            
                                            shop_data['Name'] = d.get('name', '')
                                            shop_data['Phone'] = d.get('telephone', '')
                                            addr = d.get('address', {})
                                            if isinstance(addr, dict):
                                                shop_data['Address'] = addr.get('streetAddress', '')
                                            else:
                                                shop_data['Address'] = str(addr)
                                                
                                            if 'geo' in d:
                                                shop_data['Latitude'] = d['geo'].get('latitude')
                                                shop_data['Longitude'] = d['geo'].get('longitude')
                                                
                                            if shop_data['Address']:
                                                for part in shop_data['Address'].split():
                                                    if part.endswith('동') or part.endswith('가'):
                                                        shop_data['Dong'] = part
                                                        break
                                    except: pass
                                    
                                    # Fallback DOM
                                    if not shop_data['Name']:
                                        try: shop_data['Name'] = await page.evaluate("document.querySelector('#_title') ? document.querySelector('#_title').innerText : document.title")
                                        except: pass

                                    # Save
                                        # Save to CSV
                                        with open(OUTPUT_FILE, 'a', encoding='utf-8-sig', newline='') as f:
                                            writer = csv.DictWriter(f, fieldnames=shop_data.keys())
                                            writer.writerow(shop_data)
                                        
                                        # Save to Firebase
                                        db = DBHandler()
                                        db.insert_shop_fs({
                                            "name": shop_data['Name'],
                                            "address": shop_data['Address'],
                                            "phone": shop_data['Phone'],
                                            "source_link": shop_data['Detail_Url'],
                                            "latitude": shop_data['Latitude'],
                                            "longitude": shop_data['Longitude'],
                                            "keyword": shop_data['Keyword']
                                        })
                                        
                                        existing_urls.add(shop_url)
                                        
                                except Exception as e:
                                    # print(f"    [Err] Detail {shop_url}: {e}")
                                    continue
                                    
                        except Exception as e:
                            print(f"[-] Error processing keyword {keyword}: {e}")
                            
                    await browser.close()
                    break # Success
                    
            except Exception as e:
                print(f"[CRITICAL] Batch failed: {e}. Retrying...")
                retry_count += 1
                await asyncio.sleep(5)

    print(f"\n[*] Custom Crawler finished.")

if __name__ == "__main__":
    asyncio.run(run_crawler())
