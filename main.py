import logging
import time
from typing import List

from crawler.safe_crawler import SafeCrawler
from crawler.searcher import Searcher
from crawler.extractor import Extractor
from crawler.local_db_handler import LocalDBHandler
from crawler.csv_handler import CSVHandler
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Skin Shop Blog Crawler...")
    
    # Initialize components
    crawler = SafeCrawler()
    searcher = Searcher(crawler)
    extractor = Extractor(crawler)
    db = LocalDBHandler(config.LOCAL_DB_PATH)
    csv_handler = CSVHandler()
    
    # Get all keywords
    all_keywords = []
    for category, keywords in config.KEYWORDS.items():
        all_keywords.extend(keywords)
        
    logger.info(f"Loaded {len(all_keywords)} keywords across {len(config.KEYWORDS)} categories.")
    
    # Fetch existing URLs to avoid processing them again
    existing_urls = set(db.fetch_existing_urls())
    logger.info(f"Skipping {len(existing_urls)} already collected URLs.")
    
    # 1. Search Phase
    found_urls = set()
    for keyword in all_keywords:
        # For demonstration/testing, maybe limit keywords or results per keyword
        # In production, we iterate all.
        urls = searcher.search_naver_blogs(keyword, limit=5) # Reduced limit for testing
        
        # Add Tistory search if needed
        # tiso_urls = searcher.search_tistory_blogs(keyword, limit=5)
        # urls.extend(tiso_urls)
        
        found_urls.update(urls)
        
        # Random delay between keyword searches to be safe
        time.sleep(3) 
        
    logger.info(f"Total unique blogs found in search: {len(found_urls)}")
    
    # 2. Filter Phase
    target_urls = [url for url in found_urls if url not in existing_urls]
    logger.info(f"New blogs to crawl: {len(target_urls)}")
    
    # 3. Extraction Phase
    success_count = 0
    for i, url in enumerate(target_urls):
        logger.info(f"Processing ({i+1}/{len(target_urls)}): {url}")
        
        data = extractor.extract_blog_data(url)
        
        if data:
            # Save to CSV
            csv_handler.append_data(data)
            
            # Save to DB
            saved_to_db = db.insert_lead(data)
            
            if saved_to_db:
                success_count += 1
            else:
                logger.warning(f"Failed to save to DB: {url}")
                
        # The extractor uses the crawler which already has random delays, 
        # but we can add a small extra pause here if needed.
        
    logger.info(f"Crawling finished. Successfully saved {success_count} new leads.")

if __name__ == "__main__":
    main()
