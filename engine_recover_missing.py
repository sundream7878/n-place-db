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
    logger.info("🚀 Starting Comprehensive Recovery for Seoul...")
    
    # 1. Load Regions
    regions_file = os.path.join(os.path.dirname(__file__), 'crawler', 'regions.json')
    with open(regions_file, 'r', encoding='utf-8') as f:
        city_map = json.load(f)
        
    seoul_data = city_map.get("서울", {})
    
    # 2. Exclude districts that are already well-populated
    # Gangnam has 700+, others have >100. We want to target the ones with very low counts.
    # Based on analysis: Mapo, Seodaemun, Yongsan, Yeongdeungpo, Eunpyeong, Seongdong, Dongjak, Jongno, Seocho
    # Basically everything EXCEPT Gangnam, Gangseo, Gangdong, Gwangjin, Jungnang, Songpa, Gwanak, Gangbuk, Guro, Jung-gu
    
    # Safe list to SKIP (Well populated > 100)
    # Note: Jung-gu has 121, but let's include it if we want to be sure, but it seems fine.
    skip_districts = [
        "강남구", "강서구", "강동구", "광진구", "중랑구", 
        "송파구", "관악구", "강북구", "구로구", "중구"
    ]
    
    recovery_keywords = []
    
    sorted_districts = sorted(seoul_data.keys())
    
    for district in sorted_districts:
        if district in skip_districts:
            logger.info(f"⏭️ Skipping {district} (Already sufficient data)")
            continue
            
        dongs = seoul_data[district]
        logger.info(f"📌 Preparing keywords for {district} ({len(dongs)} dongs)...")
        for dong in dongs:
            # Construct keyword: "서울 [District] [Dong] 피부관리샵"
            keyword = f"서울 {district} {dong} 피부관리샵"
            recovery_keywords.append(keyword)

    logger.info(f"📋 Total Keywords to process: {len(recovery_keywords)}")
    
    # 3. Run Crawler with Custom Keywords
    # Set target_count to high number to ensure we get everything
    # Resume=True allows checking checkpoint to skip already finished keywords
    await run_crawler(custom_keywords=recovery_keywords, target_count=99999, resume=True)

    logger.info("✅ Comprehensive Recovery Crawl Finished.")
    
    # 4. Optional: Run Competitor Extraction
    logger.info("🔄 Running Competitor Extraction...")
    try:
        from extract_competitors import run_competitor_extraction
        run_competitor_extraction()
    except Exception as e:
        logger.error(f"⚠️ Competitor extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
