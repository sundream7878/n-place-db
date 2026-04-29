import hashlib
import os
import uuid
import logging
from datetime import datetime
from supabase import create_client, Client
import config
from crawler.local_db_handler import LocalDBHandler

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupabaseAuthManager:
    """수파베이스 기반 라이선스 인증 매니저 (충돌 방지를 위해 이름 변경됨)"""
    
    LICENSE_FILE = os.path.join(config.LOCAL_BASE_PATH, "data", "license.dat")
    _client: Client = None
    _collection_limit = None
    _serial_key = None

    @classmethod
    def _get_client(cls) -> Client:
        """수파베이스 클라이언트를 초기화하고 반환합니다."""
        if cls._client is None:
            try:
                cls._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                logger.info("✅ Supabase 클라이언트 초기화 완료")
            except Exception as e:
                logger.error(f"❌ Supabase 초기화 실패: {e}")
        return cls._client

    @staticmethod
    def get_hwid() -> str:
        """uuid.getnode() 기반의 표준 HWID 추출"""
        try:
            node_id = str(uuid.getnode())
            hwid = hashlib.sha256(node_id.encode()).hexdigest()[:16].upper()
            return hwid
        except Exception as e:
            logger.error(f"Error extracting HWID: {e}")
            return "UNKNOWN_HWID"

    @classmethod
    def validate_and_bind_key(cls, key: str) -> tuple[bool, str]:
        """수파베이스 기반 라이선스 검증 및 HWID 바인딩"""
        client = cls._get_client()
        if not client:
            return False, "서버 연결 실패 (Supabase)"

        try:
            hwid = cls.get_hwid()
            logger.info(f"🔍 라이선스 검증(Supabase): {key} (HWID: {hwid})")

            response = client.table("licenses") \
                .select("*") \
                .eq("serial_key", key) \
                .limit(1) \
                .execute()

            if not response.data:
                logger.warning(f"⚠️ 키를 찾지 못함: {key}")
                return False, "존재하지 않는 제품 키입니다."

            data = response.data[0]
            logger.info(f"✅ 서버 데이터 로드 성공: {data}")
            cls._serial_key = key
            
            status = str(data.get("status", "")).lower()
            if status not in ["active", "used", "unused"]:
                return False, f"유효하지 않은 키 상태입니다 ({status})"

            expire_date_str = data.get("expire_date")
            if expire_date_str:
                try:
                    expire_date = datetime.fromisoformat(expire_date_str.replace('Z', '+00:00'))
                    now = datetime.now(expire_date.tzinfo) if expire_date.tzinfo else datetime.now()
                    if expire_date < now:
                        return False, "라이선스 사용 기간이 만료되었습니다."
                except: pass

            cls._collection_limit = data.get("collection_limit")
            bound_value = data.get("bound_value")
            
            if bound_value:
                if bound_value == hwid:
                    cls.save_local_license(key)
                    return True, "인증 성공"
                return False, "다른 PC에 이미 등록된 라이선스입니다."
            else:
                update_response = client.table("licenses") \
                    .update({
                        "bound_value": hwid,
                        "status": "used"
                    }) \
                    .eq("serial_key", key) \
                    .execute()
                
                if update_response.data:
                    cls.save_local_license(key)
                    return True, "인증 및 기기 등록 성공"
                return False, "서버 바인딩 업데이트 실패"

        except Exception as e:
            logger.error(f"🚨 검증 중 오류 발생: {e}")
            return False, f"서버 통신 오류: {e}"

    @classmethod
    def is_trial_available(cls) -> bool:
        """서버(Supabase) 및 로컬 DB를 모두 체크하여 체험판 가능 여부를 판단합니다."""
        client = cls._get_client()
        hwid = cls.get_hwid()
        
        # 1. 서버(Supabase) 체크 (파일 삭제 시에도 차단)
        if client:
            try:
                response = client.table("trial_logs") \
                    .select("used_count") \
                    .eq("hwid", hwid) \
                    .execute()
                
                if response.data:
                    used_count = response.data[0].get("used_count", 0)
                    if used_count >= 50:
                        logger.warning(f"🚫 서버 기록: HWID {hwid} 체험판 한도 소진")
                        return False
            except Exception as e:
                logger.error(f"서버 체험판 조회 실패: {e}")

        # 2. 로컬 DB 체크 (누적 수집량)
        try:
            db = LocalDBHandler()
            count = db.get_count()
            return count < 50
        except Exception as e:
            logger.error(f"Local trial availability check error: {e}")
            return False

    @classmethod
    def start_trial(cls) -> tuple[bool, str]:
        """키 없이 즉시 체험판 모드로 시작합니다. (Monster Rule 1.3 - Lifetime 50 items)"""
        try:
            if not cls.is_trial_available():
                return False, "체험판 수집 한도(50건)를 모두 소진하셨습니다. 정식 라이선스를 이용해 주세요."
            
            # 서버에 체험판 시작 기록 (HWID 기반)
            client = cls._get_client()
            if client:
                try:
                    hwid = cls.get_hwid()
                    client.table("trial_logs").upsert({
                        "hwid": hwid,
                        "status": "active",
                        "last_started_at": datetime.now().isoformat()
                    }).execute()
                except Exception as e:
                    logger.error(f"서버 체험판 기록 실패: {e}")

            cls._serial_key = "TRIAL-MODE"
            cls._collection_limit = 50 # 체험판은 총 50건으로 제한 (생애 1회)
            logger.info("⚡ 체험판 모드로 진입합니다. (생애 1회 한정: 50건)")
            return True, "체험판 모드로 시작합니다."
        except Exception as e:
            logger.error(f"체험판 시작 오류: {e}")
            return False, str(e)

    @classmethod
    def save_local_license(cls, key: str):
        hwid = cls.get_hwid()
        signature = hashlib.sha256(f"{key}-{hwid}-CAFE-MONSTER".encode()).hexdigest()
        os.makedirs(os.path.dirname(cls.LICENSE_FILE), exist_ok=True)
        with open(cls.LICENSE_FILE, "w", encoding="utf-8-sig") as f:
            f.write(f"{key}:{signature}")

    @classmethod
    def check_license_status(cls) -> bool:
        # [NEW] Environment-based Trial Mode Detection (for cross-process sync)
        if os.environ.get("NPLACE_TRIAL_MODE") == "1":
            cls._serial_key = "TRIAL-MODE"
            cls._collection_limit = 50
            return True

        # [NEW] Trial Mode Bypass (Monster Rule 1.3)
        if cls._serial_key == "TRIAL-MODE":
            return True
            
        if not os.path.exists(cls.LICENSE_FILE): return False
        try:
            with open(cls.LICENSE_FILE, "r", encoding="utf-8-sig") as f:
                content = f.read().strip()
                if ":" not in content: return False
                key, stored_sig = content.split(":")
            hwid = cls.get_hwid()
            if stored_sig != hashlib.sha256(f"{key}-{hwid}-CAFE-MONSTER".encode()).hexdigest():
                return False
            success, _ = cls.validate_and_bind_key(key)
            return success
        except: return False

    @classmethod
    def create_license(cls, prefix: str = "CM", days: int = 30, collection_limit: int = None) -> tuple[bool, str]:
        """수파베이스 DB에 새로운 라이선스 키를 생성하고 등록합니다. (Monster 전용)"""
        client = cls._get_client()
        if not client: return False, "서버 연결 실패"

        import secrets
        import string
        from datetime import timedelta

        # 1. 랜덤 시리얼 키 생성 (CM-PRO-XXXX-XXXX 형식)
        suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        serial_key = f"{prefix}-{suffix[:4]}-{suffix[4:]}"
        
        expire_date = (datetime.now() + timedelta(days=days)).isoformat()

        try:
            # 2. 수파베이스 테이블에 삽입
            data = {
                "serial_key": serial_key,
                "status": "unused",
                "expire_date": expire_date,
                "collection_limit": collection_limit,
                "created_at": datetime.now().isoformat()
            }
            
            response = client.table("licenses").insert(data).execute()
            
            if response.data:
                logger.info(f"✨ 새 라이선스 발행 성공: {serial_key}")
                return True, serial_key
            return False, "DB 삽입 실패"
        except Exception as e:
            logger.error(f"라이선스 생성 중 오류: {e}")
            return False, str(e)

    @classmethod
    def get_collection_limit(cls): return cls._collection_limit
    @classmethod
    def get_serial_key(cls): return cls._serial_key
