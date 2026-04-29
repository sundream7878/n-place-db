import config
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_advanced_keyword_generation(target_area):
    base_keyword = "" # 기본값 제거
    all_keywords = []
    
    logger.info(f"입력 타겟: {target_area}")

    targets = [t.strip() for t in target_area.split(",") if t.strip()]
    
    for t in targets:
        if " " in t:
            # 1. 특정 구 정밀 모드
            parts = t.split()
            province = parts[0]
            district = " ".join(parts[1:])
            
            if province in config.CITY_MAP and district in config.CITY_MAP[province]:
                dongs = config.CITY_MAP[province][district]
                all_keywords.extend([f"{province} {district} {dong} {base_keyword}" for dong in dongs])
                logger.info(f"   [구 정밀] '{t}' -> {len(dongs)}개 키워드 생성")
            else:
                all_keywords.append(f"{t} {base_keyword}")
        
        elif t in config.CITY_MAP:
            # 2. 시/도 전체 모드
            prov_keywords = []
            districts = config.CITY_MAP[t]
            for dist, dongs in districts.items():
                for dong in dongs:
                    prov_keywords.append(f"{t} {dist} {dong} {base_keyword}")
            all_keywords.extend(prov_keywords)
            logger.info(f"   [시/도 전체] '{t}' -> {len(prov_keywords)}개 키워드 생성")
        else:
            all_keywords.append(f"{t} {base_keyword}")

    # 중복 제거
    keywords = list(dict.fromkeys(all_keywords))
    logger.info(f"📂 최종 총 키워드 수: {len(keywords)}")
    return keywords

if __name__ == "__main__":
    # 테스트 케이스: 서울 강남구(정밀) + 인천(전체)
    test_target = "서울 강남구,인천"
    generated_keywords = verify_advanced_keyword_generation(test_target)
    
    print("\n--- 검증 결과 상세 ---")
    print(f"입력 문자열: {test_target}")
    print(f"생성된 총 키워드: {len(generated_keywords)}")
    
    # 셈플 확인
    seoul_kws = [kw for kw in generated_keywords if "서울 강남구" in kw]
    incheon_kws = [kw for kw in generated_keywords if "인천" in kw and "서울" not in kw]
    
    print(f"서울 강남구 관련 키워드 샘플 (총 {len(seoul_kws)}개):")
    for kw in seoul_kws[:3]: print(f" - {kw}")
    
    print(f"인천(전체) 관련 키워드 샘플 (총 {len(incheon_kws)}개):")
    for kw in incheon_kws[:3]: print(f" - {kw}")

    # 성공 조건: 서울 강남구 전용 키워드 존재 AND 인천의 여러 구 키워드 존재
    has_gangnam = len(seoul_kws) > 0
    # 인천 전체이므로 부평구, 계양구 등 다양한 구가 포함되어야 함
    different_districts_in_incheon = set(kw.split()[1] for kw in incheon_kws)
    
    if has_gangnam and len(different_districts_in_incheon) > 1:
        print("\n✅ 검증 성공: 정밀 수집 구역과 전체 수집 구역이 올바르게 확장되었습니다.")
    else:
        print("\n❌ 검증 실패: 키워드 확장 로직에 문제가 있습니다.")
