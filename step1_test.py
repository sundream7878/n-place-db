import asyncio
import sys
from playwright.async_api import async_playwright

async def main():
    print("Test started", flush=True)
    try:
        async with async_playwright() as p:
            print("Playwright context created", flush=True)
            browser = await p.chromium.launch(headless=True)
            print("Browser launched", flush=True)
            page = await browser.new_page()
            print("Page created", flush=True)
            await page.goto("https://google.com")
            print("Goto finished", flush=True)
            await asyncio.sleep(5)
            print("Sleep finished", flush=True)
            await browser.close()
    except Exception as e:
        print(f"Exception: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
    print("Finished successfully", flush=True)
