import sys
from auth import AuthManager

def main():
    print("========================================")
    print("   3Monster 통합 라이선스 발행기 (Hub)   ")
    print("========================================\n")
    
    print("1. n플레이스 PRO (기한 30일, 수집 무제한)")
    print("2. n플레이스 BASIC (기한 30일, 수집 500건 제한)")
    print("3. 테스트용 (기한 1일, 수집 100건 제한)")
    print("4. 커스텀 생성\n")
    
    choice = input("발행할 라이선스 타입을 선택하세요: ").strip()
    
    prefix = "CM"
    days = 30
    limit = None
    
    if choice == "1":
        prefix = "PRO"
    elif choice == "2":
        prefix = "BASIC"
        limit = 500
    elif choice == "3":
        prefix = "TEST"
        days = 1
        limit = 100
    elif choice == "4":
        prefix = input("접두어(Prefix) 입력: ").strip().upper()
        try:
            days = int(input("유효 기간(일): ").strip())
            limit_in = input("수집 제한(없으면 엔터): ").strip()
            limit = int(limit_in) if limit_in else None
        except ValueError:
            print("숫자 형식이 올바르지 않습니다.")
            return
    else:
        print("잘못된 선택입니다.")
        return

    print(f"\n⏳ 서버에 라이선스 등록 중... ({prefix}, {days}일)")
    success, result = AuthManager.create_license(prefix, days, limit)
    
    if success:
        print(f"\n✅ 성공! 신규 라이선스가 발행되었습니다.")
        print(f"----------------------------------------")
        print(f" 시리얼 키 : {result}")
        print(f" 유효 기간 : {days}일")
        print(f" 수집 제한 : {limit if limit else '무제한'}")
        print(f"----------------------------------------")
        print("\n이 번호를 고객에게 전달하면 첫 실행 시 PC에 귀속됩니다.")
    else:
        print(f"\n❌ 실패: {result}")

if __name__ == "__main__":
    main()
