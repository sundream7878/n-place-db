import sys
import os

# 현재 디렉토리를 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sb_auth_manager import SupabaseAuthManager
import config

def test_supabase_connection():
    print("=== Supabase Connection & License Test (Fixed) ===")
    print(f"URL: {config.SUPABASE_URL}")
    print(f"HWID: {SupabaseAuthManager.get_hwid()}")
    
    print("\n[테스트 1] 존재하지 않는 키 검증")
    success, msg = SupabaseAuthManager.validate_and_bind_key("NON-EXISTENT-KEY")
    print(f"결과: {'성공' if success else '실패'} (메시지: {msg})")

if __name__ == "__main__":
    test_supabase_connection()
