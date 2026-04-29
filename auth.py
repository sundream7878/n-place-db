import logging
import os
from sb_auth_manager import SupabaseAuthManager

# 로깅 설정
logger = logging.getLogger(__name__)

class LicenseExpiredError(Exception):
    """라이선스 기간이 만료되었을 때 발생하는 예외"""
    pass

class AuthManager:
    """
    [3Monster] 통합 인증 매니저 (Supabase 전용)
    sb_auth_manager.py를 사용하여 인증을 처리합니다.
    """
    
    @staticmethod
    def get_hwid() -> str:
        return SupabaseAuthManager.get_hwid()

    @classmethod
    def validate_and_bind_key(cls, key: str) -> tuple[bool, str]:
        return SupabaseAuthManager.validate_and_bind_key(key)

    @classmethod
    def check_license_status(cls) -> bool:
        return SupabaseAuthManager.check_license_status()

    @classmethod
    def get_collection_limit(cls):
        return SupabaseAuthManager.get_collection_limit()

    @classmethod
    def get_serial_key(cls):
        return SupabaseAuthManager.get_serial_key()

    @classmethod
    def save_local_license(cls, key: str):
        SupabaseAuthManager.save_local_license(key)

    @classmethod
    def create_license(cls, prefix: str = "CM", days: int = 30, collection_limit: int = None):
        return SupabaseAuthManager.create_license(prefix, days, collection_limit)

    @classmethod
    def is_trial_available(cls):
        return SupabaseAuthManager.is_trial_available()

    @classmethod
    def start_trial(cls):
        return SupabaseAuthManager.start_trial()
