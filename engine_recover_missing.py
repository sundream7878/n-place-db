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
logger = logging.getLogger("RecoveryAll")

async def main():
    # 0. Handle Arguments
    target_province = "서울"
    if len(sys.argv) > 1:
        target_province = sys.argv[1].split()[0] # Take first part (e.g., "부산" from "부산 수영구")
    
    logger.info(f"🚀 Starting Comprehensive Recovery for {target_province}...")
    
    # 1. Load Regions
    regions_file = os.path.join(os.path.dirname(__file__), 'crawler', 'regions.json')
    if not os.path.exists(regions_file):
        logger.error(f"❌ Regions file not found: {regions_file}")
        return

    with open(regions_file, 'r', encoding='utf-8') as f:
        city_map = json.load(f)
        
    prov_data = city_map.get(target_province, {})
    if not prov_data:
        logger.error(f"❌ No data found for province: {target_province}")
        return
    
    # 2. Preparation
    skip_districts = [] # No longer skipping for general recovery unless specified
    recovery_keywords = []
    
    sorted_districts = sorted(prov_data.keys())
    
    for district in sorted_districts:
        dongs = prov_data[district]
        logger.info(f"📌 Preparing keywords for {target_province} {district} ({len(dongs)} dongs)...")
        for dong in dongs:
            # Construct keyword: "[Province] [District] [Dong]"
            keyword = f"{target_province} {district} {dong}".strip()
            recovery_keywords.append(keyword)

    logger.info(f"📋 Total Keywords to process: {len(recovery_keywords)}")
    
    # 3. Run Crawler with Custom Keywords
    await run_crawler(custom_keywords=recovery_keywords, target_count=99999, resume=True)

    logger.info("✅ Comprehensive Recovery Crawl Finished.")
    
    # 4. Optional: Run Competitor Extraction (DISABLED - Manual Trigger Only)
    # logger.info("🔄 Running Competitor Extraction...")
    # try:
    #     from extract_competitors import run_competitor_extraction
    #     run_competitor_extraction()
    # except Exception as e:
    #     logger.error(f"⚠️ Competitor extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
