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

async def research_shop(shop_id):
    from crawler.db_handler import DBHandler
    db = DBHandler()
    
    # 1. Fetch shop info from Firebase
    # We need to find the document. If shop_id is the document ID, we use it.
    # But since shop_id from dashboard might be from Supabase, let's search by ID field if available, 
    # or Assume the caller provides a key that insert_shop_fs can use.
    # In app.py, st.session_state['last_selected_shop'] is the whole dict.
    
    # Let's use Firestore to find the doc
    docs = db.db_fs.collection(config.FIREBASE_COLLECTION).where("id", "==", int(shop_id) if shop_id.isdigit() else shop_id).stream()
    shop = None
    for d in docs:
        shop = d.to_dict()
        shop['_doc_id'] = d.id
        break
    
    if not shop:
        # Fallback: maybe shop_id is the document ID itself
        doc_ref = db.db_fs.collection(config.FIREBASE_COLLECTION).document(shop_id)
        doc = doc_ref.get()
        if doc.exists:
            shop = doc.to_dict()
            shop['_doc_id'] = doc.id
    
    if not db.db_fs:
        print("[-] Firebase Firestore not initialized. Check your credentials/secrets.")
        sys.exit(1)
        
    if not shop:
        print(f"[-] Shop not found in Firebase: {shop_id}")
        sys.exit(1)
    
    name = shop.get('name') or shop.get('상호명')
    link = shop.get('source_link') or shop.get('플레이스링크')
    
    if not link:
        print(f"[-] No source_link for {name}. Cannot re-search.")
        return
    
    print(f"[*] Re-searching [{name}]...")
    
    async with async_playwright() as p:
        # Using headless=True for background execution
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        try:
            # Visit Home Page
            await page.goto(link, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            
            # Extract SNS and Email (similar logic to fill_missing_links.py)
            content = await page.content()
            
            insta, talk, blog, email = "", "", "", ""
            
            # Try Apollo State first
            try:
                state = await page.evaluate("() => window.__APOLLO_STATE__")
                if state:
                    for k, val in state.items():
                        if not isinstance(val, dict): continue
                        if "homepages" in val and val["homepages"]:
                            for hp in val["homepages"]:
                                if not isinstance(hp, dict): continue
                                hp_url = hp.get("url", "")
                                if "instagram.com" in hp_url:
                                    insta_handle = hp_url.strip("/").split("/")[-1].split("?")[0]
                                    if insta_handle: insta = f"https://www.instagram.com/{insta_handle}"
                                elif "blog.naver.com" in hp_url:
                                    blog_handle = hp_url.strip("/").split("/")[-1].split("?")[0]
                                    if blog_handle: blog = f"https://blog.naver.com/{blog_handle}"
                        if "talktalkUrl" in val and val["talktalkUrl"]:
                            talk = val["talktalkUrl"]
            except: pass

            # Regex Fallbacks
            if not insta:
                match = re.search(r'instagram\.com/([a-zA-Z0-9._-]+)', content)
                if match and match.group(1) not in ['p', 'reels', 'stories', 'explore']:
                    insta = f"https://www.instagram.com/{match.group(1)}"
            if not talk:
                match = re.search(r'talk\.naver\.com/([a-zA-Z0-9-]+)', content)
                if match:
                    talk = match.group(0)
                    if not talk.startswith('http'): talk = f"https://{talk}"
            if not blog:
                match = re.search(r'blog\.naver\.com/([a-zA-Z0-9-]+)', content)
                if match: blog = f"https://blog.naver.com/{match.group(1)}"

            # Email Extraction
            desc_text = await page.evaluate("() => document.body.innerText")
            emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', desc_text)
            if emails: email = emails[0]

            # Update DB
            update_data = {}
            if insta: update_data["instagram_handle"] = insta
            if talk: update_data["talk_url"] = talk
            if blog: update_data["naver_blog_id"] = blog
            if email: update_data["email"] = email
            
            if update_data:
                print(f"    [+] Found: {update_data}")
                # Update Firebase (New)
                full_data = shop.copy()
                if '_doc_id' in full_data: del full_data['_doc_id']
                full_data.update(update_data)
                db.insert_shop_fs(full_data)
                
                print("    [+] Firebase DB Updated successfully.")
            else:
                print("    [-] No new information found.")
                
        except Exception as e:
            print(f"    [-] Error during research: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python research_single_shop.py <shop_id>")
    else:
        asyncio.run(research_shop(sys.argv[1]))
