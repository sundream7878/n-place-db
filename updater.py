import os
import sys
import requests
import logging
import subprocess
from datetime import datetime
from sb_auth_manager import SupabaseAuthManager
import config

logger = logging.getLogger(__name__)

class MonsterUpdater:
    """
    [3Monster] 표준 자동 업데이트 엔진 (Monster Updater v1.0)
    수파베이스와 연동하여 개별 앱의 버전을 관리하고 업데이트를 수행합니다.
    """
    
    CURRENT_VERSION = config.CURRENT_VERSION # config에서 버전 정보를 가져옵니다.
    PRODUCT_ID = config.PRODUCT_ID # config에서 제품명을 가져옵니다.
    
    @classmethod
    def check_for_updates(cls):
        """서버에서 최신 버전을 확인합니다."""
        client = SupabaseAuthManager._get_client()
        if not client:
            logger.error("업데이트 확인 실패: 서버 연결 불가")
            return None

        try:
            response = client.table("app_versions") \
                .select("*") \
                .eq("product_id", cls.PRODUCT_ID) \
                .order("version", desc=True) \
                .limit(1) \
                .execute()

            if response.data:
                latest = response.data[0]
                latest_version = latest['version']
                
                if cls._is_newer(latest_version, cls.CURRENT_VERSION):
                    logger.info(f"🚀 새 업데이트 발견: {cls.CURRENT_VERSION} -> {latest_version}")
                    return latest
            return None
        except Exception as e:
            logger.error(f"업데이트 확인 중 오류: {e}")
            return None

    @staticmethod
    def _is_newer(latest, current):
        """버전 문자열 비교 (예: 1.1.0 > 1.0.9)"""
        try:
            l_parts = [int(p) for p in latest.split('.')]
            c_parts = [int(p) for p in current.split('.')]
            return l_parts > c_parts
        except:
            return latest > current

    @classmethod
    def download_update(cls, download_url, target_filename="update_package.zip"):
        """새 버전을 다운로드합니다."""
        try:
            logger.info(f"📥 업데이트 다운로드 시작: {download_url}")
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            with open(target_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"✅ 다운로드 완료: {target_filename}")
            return True
        except Exception as e:
            logger.error(f"다운로드 중 오류 발생: {e}")
            return False

    @classmethod
    def apply_update_and_restart(cls, update_package_path="update_package.zip"):
        """
        다운로드된 파일을 적용하고 앱을 재시작합니다.
        실행 중인 EXE는 직접 교체가 안 되므로 배치 파일을 생성하여 처리합니다.
        """
        try:
            current_exe = sys.executable
            app_dir = os.path.dirname(current_exe)
            
            # 배치 파일 경로
            bat_path = os.path.join(app_dir, "monster_update_helper.bat")
            
            # 새 실행 파일 이름 (ZIP이 아니라 단일 파일 다운로드 가정 시)
            # 만약 ZIP이라면 압축 해제 로직이 추가로 필요합니다.
            new_exe = os.path.join(app_dir, "Place-DB-Pro_new.exe")
            
            # ZIP 압축 해제 처리 (압축된 배포일 경우)
            if update_package_path.endswith('.zip'):
                import zipfile
                logger.info("📦 압축 해제 중...")
                with zipfile.ZipFile(update_package_path, 'r') as zip_ref:
                    zip_ref.extractall(app_dir)
                os.remove(update_package_path)
            
            # 배치 파일 내용 생성
            # 1. 2초 대기 (프로세스 종료 대기)
            # 2. 기존 파일 삭제
            # 3. 새 파일이 있다면 이름 변경
            # 4. 앱 재시작
            # 5. 배치 파일 자가 삭제
            bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
if exist "{current_exe}" del /f /q "{current_exe}"
if exist "{new_exe}" move /y "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="cp949") as f:
                f.write(bat_content)
                
            logger.info("🔄 업데이트 헬퍼 생성 완료. 프로세스를 종료하고 업데이트를 적용합니다.")
            subprocess.Popen([bat_path], shell=True)
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"업데이트 적용 중 오류 발생: {e}")
            return False
