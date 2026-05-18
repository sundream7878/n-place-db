import asyncio
import random
import requests
import json
import re
import sys
import os
from playwright.async_api import async_playwright

# Add current dir to path to import config
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import config

async def force_fill_specific_shops():
    url = config.SUPABASE_URL
    key = config.SUPABASE_KEY
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    # 누락된 업체 리스트 (브라우저 잠입 확인 결과)
    target_shops = [
        {"name": "비본어게인 스파", "place_id": "1730532483"},
        {"name": "올풋샵 마사지 부평점", "place_id": "1190120434"},
        {"name": "톤스파앤바디", "place_id": "1748678819"},
        {"name": "약손명가 부평점", "place_id": "12035255"},
        {"name": "데자뷰메디스킨 인천점", "place_id": "1469292427"}
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        for shop in target_shops:
            name = shop['name']
            pid = shop['place_id']
            detail_url = f"https://m.place.naver.com/place/{pid}/home"
            info_url = f"https://m.place.naver.com/place/{pid}/information"
            
            print(f"[*] Processing: {name} ({pid})...")
            page = await context.new_page()
            
            try:
                await page.goto(detail_url, wait_until="networkidle")
                await asyncio.sleep(5)
                
                content = await page.content()
                state = await page.evaluate("() => window.__APOLLO_STATE__")
                
                insta, talk, blog, email = "", "", "", ""
                
                def extract_sns(data, html_content):
                    i, t, b = "", "", ""
                    if data:
                        for k, v in data.items():
                            if not isinstance(v, dict): continue
                            if "homepages" in v and v["homepages"]:
                                for hp in v["homepages"]:
                                    if not isinstance(hp, dict): continue
                                    hurl = hp.get("url", "")
                                    if "instagram.com" in hurl:
                                        handle = hurl.strip("/").split("/")[-1].split("?")[0]
                                        if handle: i = f"https://www.instagram.com/{handle}"
                                    elif "blog.naver.com" in hurl:
                                        handle = hurl.strip("/").split("/")[-1].split("?")[0]
                                        if handle: b = f"https://blog.naver.com/{handle}"
                            if v.get("talktalkUrl"): t = v["talktalkUrl"].strip()
                    
                    # Regex Fallback on HTML
                    if not i:
                        m = re.search(r'instagram\.com/([a-zA-Z0-9._-]+)', html_content)
                        if m and m.group(1) not in ['p', 'reels', 'stories', 'explore']:
                            i = f"https://www.instagram.com/{m.group(1)}"
                    if not t:
                        m = re.search(r'talk\.naver\.com/([a-zA-Z0-9-]+)', html_content)
                        if m: 
                            tmp_t = f"https://{m.group(0)}" if not m.group(0).startswith('http') else m.group(0)
                            if not tmp_t.endswith("/ch"):
                                t = tmp_t
                    if not b:
                        m = re.search(r'blog\.naver\.com/([a-zA-Z0-9-]+)', html_content)
                        if m: b = f"https://blog.naver.com/{m.group(1)}"
                    return i, t, b

                insta, talk, blog = extract_sns(state, content)
                
                # Fallback to Info Page
                if not (insta and talk and blog):
                    await page.goto(info_url, wait_until="networkidle")
                    await asyncio.sleep(5)
                    content2 = await page.content()
                    state2 = await page.evaluate("() => window.__APOLLO_STATE__")
                    i2, t2, b2 = extract_sns(state2, content2)
                    insta = insta or i2
                    talk = talk or t2
                    blog = blog or b2
                
                # Email Extraction from Description (New in this script)
                content_for_email = await page.content()
                desc_node = page.locator("div.v_GvP, div.C_m_a, ._1Y_N8, .place_section_content").first
                if await desc_node.count() > 0:
                    desc_text = await desc_node.text_content()
                    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', desc_text)
                    if emails:
                        email = emails[0]
                
                # Fallback for Email using Blog ID
                if not email and blog and "blog.naver.com" in blog:
                    handle = blog.strip("/").split("/")[-1].split("?")[0]
                    if handle:
                        email = f"{handle}@naver.com"
                        print(f"    [+] Generated fallback email from blog: {email}")
                
                # Update DB - Find by name or source_link first to avoid 409
                print(f"    [+] Found for {name}: Insta={insta}, Talk={talk}, Blog={blog}, Email={email}")
                
                # Check exist
                check_url = f"{url}/rest/v1/t_crawled_shops?source_link=like.*{pid}*&select=id"
                check_resp = requests.get(check_url, headers=headers)
                
                p_data = {
                    "instagram_handle": insta,
                    "talk_url": talk,
                    "naver_blog_id": blog,
                    "email": email
                }
                
                if check_resp.status_code == 200 and check_resp.json():
                    sid = check_resp.json()[0]['id']
                    upd_url = f"{url}/rest/v1/t_crawled_shops?id=eq.{sid}"
                    resp = requests.patch(upd_url, headers=headers, json=p_data)
                    print(f"    [+] DB Updated (PATCH) for {name}.")
                else:
                    # POST new
                    p_data["name"] = name
                    p_data["source_link"] = detail_url
                    p_data["address"] = "부평동" # Placeholder if not found
                    upd_url = f"{url}/rest/v1/t_crawled_shops"
                    resp = requests.post(upd_url, headers=headers, json=p_data)
                    print(f"    [+] DB Created (POST) for {name}.")

            except Exception as e:
                print(f"    [-] Error processing {name}: {e}")
            finally:
                await page.close()
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(force_fill_specific_shops())
