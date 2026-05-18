import asyncio
import requests
import json
import re
import os
import sys
import random
from playwright.async_api import async_playwright

# Add current dir to path to import config
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import config

async def fill_missing_links():
    url = config.SUPABASE_URL
    key = config.SUPABASE_KEY
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    # 1. Fetch shops in Bupyeong-dong
    query_url = f"{url}/rest/v1/t_crawled_shops?address=ilike.*부평동*&select=id,name,source_link,instagram_handle,talk_url,naver_blog_id,email"
    resp = requests.get(query_url, headers=headers)
    
    if resp.status_code != 200:
        print(f"[-] Failed to fetch shops: {resp.status_code}")
        return
    
    all_shops = resp.json()
    # Filter for missing info in Python
    # 인스타그램이 없거나, 주소 형식이 아니거나, 톡톡/블로그가 없는 경우 필터링
    shops = [s for s in all_shops if 
             not s.get('instagram_handle') or 
             not s.get('instagram_handle', '').startswith('http') or
             not s.get('talk_url') or 
             not s.get('naver_blog_id') or
             not s.get('naver_blog_id', '').startswith('http')]
    
    print(f"[*] Found {len(shops)} shops to check for missing/incomplete links in Bupyeong-dong (Filtered from {len(all_shops)} total).")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
        ]
        
        for shop in shops:
            shop_id = shop['id']
            name = shop['name']
            link = shop['source_link']
            
            if not link: continue
            
            # Stealth: Select random UA for each shop
            ua = random.choice(user_agents)
            context = await browser.new_context(
                user_agent=ua,
                viewport={"width": 412 if "iPhone" in ua else 1280, "height": 915 if "iPhone" in ua else 800}
            )
            
            # Ensure it's /home or /information
            info_link = link.replace("/home", "/information")
            
            print(f"[*] Checking [{name}] with UA: {ua[:30]}...")
            page = await context.new_page()
            
            try:
                # Stealth: Random delay before visit
                await asyncio.sleep(random.uniform(5.0, 10.0))
                # Try Home Page first
                await page.goto(link, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(10)
                
                # Scroll to trigger hydration
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(2)
                
                title = await page.title()
                print(f"    [*] Page Title: {title}")
                
                # Take debug screenshot for the first shop
                if shop_id == shops[0]['id']:
                    await page.screenshot(path="debug_fill_links.png")
                    print("    [*] Debug screenshot saved to debug_fill_links.png")
                
                def extract_from_state(state):
                    insta, talk, blog = "", "", ""
                    if not state: return insta, talk, blog
                    
                    # Deep search
                    for k, val in state.items():
                        if not isinstance(val, dict): continue
                        if "homepages" in val and val["homepages"]:
                            for hp in val["homepages"]:
                                if not isinstance(hp, dict): continue
                                hp_url = hp.get("url", "")
                                if "instagram.com" in hp_url:
                                    insta_handle = hp_url.strip("/").split("/")[-1].split("?")[0]
                                    if insta_handle:
                                        insta = f"https://www.instagram.com/{insta_handle}"
                                elif "blog.naver.com" in hp_url:
                                    blog_handle = hp_url.strip("/").split("/")[-1].split("?")[0]
                                    if blog_handle:
                                        blog = f"https://blog.naver.com/{blog_handle}"
                        if "talktalkUrl" in val and val["talktalkUrl"]:
                            talk = val["talktalkUrl"]
                    return insta, talk, blog

                insta, talk, blog = "", "", ""
                email = ""
                
                # Try direct script tag extraction
                content = await page.content()
                match = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.*?});</script>', content, re.DOTALL)
                if match:
                    try:
                        state_json = json.loads(match.group(1))
                        insta, talk, blog = extract_from_state(state_json)
                    except: pass
                
                if not insta or not talk or not blog:
                    # Try evaluate
                    state = await page.evaluate("() => window.__APOLLO_STATE__")
                    i2, t2, b2 = extract_from_state(state)
                    insta = insta or i2
                    talk = talk or t2
                    blog = blog or b2
                
                # Method 2: Global Regex Search on Page Content
                content = await page.content()
                if not insta:
                    match = re.search(r'instagram\.com/([a-zA-Z0-9._-]+)', content)
                    if match:
                        cand = match.group(1)
                        if cand not in ['p', 'reels', 'stories', 'explore']: # exclude common paths
                             insta = f"https://www.instagram.com/{cand}"
                
                if not talk:
                    match = re.search(r'talk\.naver\.com/([a-zA-Z0-9-]+)', content)
                    if match:
                        talk = match.group(0)
                        if not talk.startswith('http'): talk = f"https://{talk}"

                if not blog:
                    match = re.search(r'blog\.naver\.com/([a-zA-Z0-9-]+)', content)
                    if match: blog = f"https://blog.naver.com/{match.group(1)}"

                # Method 3: DOM Fallback
                if not insta:
                    insta_node = page.locator("a[href*='instagram.com']").first
                    if await insta_node.count() > 0:
                        insta_url = await insta_node.get_attribute("href")
                        insta_handle = insta_url.strip("/").split("/")[-1].split("?")[0]
                        if insta_handle:
                            insta = f"https://www.instagram.com/{insta_handle}"
                
                if not talk:
                    talk_node = page.locator("a[href*='talk.naver.com']").first
                    if await talk_node.count() > 0:
                        talk = await talk_node.get_attribute("href")

                # Method 4: Visit Information page if still missing
                if not insta or not talk or not blog:
                    print(f"    [!] SNS missing in Home, trying Information page...")
                    await page.goto(info_link, wait_until="networkidle", timeout=60000)
                    await asyncio.sleep(5)
                    content2 = await page.content()
                    i2, t2, b2 = extract_from_state(await page.evaluate("() => window.__APOLLO_STATE__"))
                    
                    if not insta:
                        if i2: insta = i2
                        else:
                            match = re.search(r'instagram\.com/([a-zA-Z0-9._-]+)', content2)
                            if match and match.group(1) not in ['p', 'reels', 'stories', 'explore']: 
                                insta = f"https://www.instagram.com/{match.group(1)}"
                        
                    if not talk:
                        if t2: talk = t2
                        else:
                            match = re.search(r'talk\.naver\.com/([a-zA-Z0-9-]+)', content2)
                            if match:
                                talk = match.group(0)
                                if not talk.startswith('http'): talk = f"https://{talk}"
                        
                    if not blog:
                         blog = blog or b2

                # Email Extraction
                desc_node = page.locator("div.v_GvP, div.C_m_a, ._1Y_N8, .place_section_content").first
                if await desc_node.count() > 0:
                    desc_text = await desc_node.text_content()
                    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', desc_text)
                    if emails:
                        email = emails[0]

                if insta or talk or blog or email:
                    print(f"    [+] Found: Insta={insta}, Talk={talk}, Blog={blog}, Email={email}")
                    # Update DB
                    update_data = {}
                    if insta: update_data["instagram_handle"] = insta
                    if talk: update_data["talk_url"] = talk
                    if blog: update_data["naver_blog_id"] = blog
                    if email: update_data["email"] = email
                    
                    upd_url = f"{url}/rest/v1/t_crawled_shops?id=eq.{shop_id}"
                    upd_resp = requests.patch(upd_url, headers=headers, json=update_data)
                    if upd_resp.status_code in [200, 204]:
                        print("    [+] DB Updated.")
                    else:
                        print(f"    [-] DB Update Failed: {upd_resp.status_code}")
                else:
                    print("    [-] No new info found on page.")
                    
            except Exception as e:
                print(f"    [-] Error: {e}")
            finally:
                await page.close()
                await asyncio.sleep(random.uniform(2.0, 4.0)) # Higher delay for safety
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(fill_missing_links())
