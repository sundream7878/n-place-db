import asyncio
import os
import sys
import json
import logging

# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from step1_refined_crawler import run_crawler

# Setup specific logger for recovery
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Recovery")

async def main():
    logger.info("🚀 Starting Focused Recovery for Eunpyeong-gu and Yongsan-gu...")
    
    # 1. Load Regions
    regions_file = os.path.join(os.path.dirname(__file__), 'crawler', 'regions.json')
    with open(regions_file, 'r', encoding='utf-8') as f:
        city_map = json.load(f)
        
    seoul_data = city_map.get("서울", {})
    
    # 2. Target Districts
    targets = ["은평구", "용산구"]
    recovery_keywords = []
    
    for district in targets:
        if district in seoul_data:
            dongs = seoul_data[district]
            logger.info(f"📌 Preparing keywords for {district} ({len(dongs)} dongs)...")
            for dong in dongs:
                # Construct keyword: "서울 [District] [Dong] 피부관리샵"
                keyword = f"서울 {district} {dong} 피부관리샵"
                recovery_keywords.append(keyword)
        else:
            logger.error(f"❌ District {district} not found in regions.json!")

    logger.info(f"📋 Total Keywords to process: {len(recovery_keywords)}")
    
    # 3. Run Crawler with Custom Keywords
    # Set target_count to high number to ensure we get everything
    await run_crawler(custom_keywords=recovery_keywords, target_count=99999, resume=False)

    logger.info("✅ Recovery Crawl Finished.")
    
    # 4. Optional: Run Competitor Extraction
    logger.info("🔄 Running Competitor Extraction...")
    try:
        from extract_competitors import run_competitor_extraction
        run_competitor_extraction()
    except Exception as e:
        logger.error(f"⚠️ Competitor extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
