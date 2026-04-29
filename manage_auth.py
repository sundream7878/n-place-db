import os
import random
import string
from auth import AuthManager
try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

def generate_random_key(prefix="NP", length=8):
    """Generates a random product key like NP-A1B2-C3D4"""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"{prefix}-{part1}-{part2}"

def main():
    print("\n" + "="*50)
    print("   N-Place-DB Pro 일회용 제품 키 관리자")
    print("="*50)
    
    db = AuthManager._get_db()
    if not db:
        print("\n❌ 오류: Firebase 서버에 연결할 수 없습니다.")
        print("💡 config.py에 넣으신 'FIREBASE_SERVICE_ACCOUNT' 정보가 올바른지 확인해 주세요.")
        input("\n종료하려면 엔터키를 누르세요...")
        return

    while True:
        print("\n[메뉴 선택]")
        print("1. 신규 제품 키 생성 (대량 생성 가능)")
        print("2. 현재 사용 가능한(미사용) 키 목록 보기")
        print("3. 특정 키 사용 중단(Revoke/삭제)")
        print("Q. 종료")
        
        choice = input("\n작업을 선택하세요: ").strip().upper()
        
        if choice == '1':
            count_str = input("생성할 키 개수를 입력하세요 (기본 1): ").strip()
            count = int(count_str) if count_str.isdigit() else 1
            
            new_keys = []
            for _ in range(count):
                k = generate_random_key()
                new_keys.append(k)
                
                # [가이드 준수] licensese 컬렉션에 serial_key 필드로 저장
                db.collection(config.FIREBASE_AUTH_COLLECTION).add({
                    'serial_key': k,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'bound_value': None,
                    'status': 'active',
                    'collection_limit': 50000
                })
            
            # Save to local text file for convenience
            with open("new_generated_keys.txt", "a", encoding="utf-8-sig") as f:
                for k in new_keys:
                    f.write(f"{k}\n")
            
            print(f"\n✅ {len(new_keys)}개의 키가 생성되어 Firebase에 업로드되었습니다.")
            print(f"📄 'new_generated_keys.txt' 파일에도 저장되었습니다.")

        elif choice == '2':
            print("\n[미사용 키 목록]")
            # serial_key 필드로 조회
            docs = db.collection(config.FIREBASE_AUTH_COLLECTION).where('status', '==', 'active').stream()
            found = False
            for doc in docs:
                data = doc.to_dict()
                print(f"- {data.get('serial_key', 'UNKNOWN')} (ID: {doc.id})")
                found = True
            if not found: print("사용 가능한 키가 없습니다.")

        elif choice == '3':
            k_to_del = input("삭제할 키를 입력하세요: ").strip().upper()
            # serial_key 필드로 찾아서 삭제
            docs = db.collection(config.FIREBASE_AUTH_COLLECTION).where('serial_key', '==', k_to_del).limit(1).get()
            if docs:
                docs[0].reference.delete()
                print(f"✅ {k_to_del} 키가 정상적으로 삭제되었습니다.")
            else:
                print("⚠️ 해당 키를 찾을 수 없습니다.")

        elif choice == 'Q':
            break

if __name__ == "__main__":
    main()
