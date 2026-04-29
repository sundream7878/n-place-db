import PyInstaller.__main__
import os
import shutil

def build():
    print("📦 N-Place-DB 통합 단일 실행파일(.exe) 생성 시작...")
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(root_dir, "dist", "N-Place-DB-Pro-Final")
    redist_file = os.path.join(root_dir, "dependencies", "vc_redist.x64.exe")
    
    # 1. 사전 체크
    if not os.path.exists(dist_dir):
        print(f"❌ 에러: {dist_dir} 폴더가 없습니다. 먼저 빌드를 완료해 주세요.")
        return
    
    if not os.path.exists(redist_file):
        print(f"❌ 에러: {redist_file} 파일이 없습니다. dependencies 폴더에 넣어주세요.")
        return

    # 2. PyInstaller 인자 설정
    # --onefile: 단일 파일 생성
    # --noconsole: 콘솔 숨김 (필요시 제거 가능)
    # --add-data "source;dest": 파일 포함. 
    #   'dist/N-Place-DB-Pro-Final' 전체를 'app_files'라는 이름으로 통합 EXE 안에 넣습니다.
    #   'vc_redist.x64.exe'도 루트에 넣습니다.
    
    args = [
        'wrapper.py',                        # 런처 스크립트
        '--name=N-Place-DB-Pro_Integrated',   # 최종 생성될 파일 이름
        '--onefile',                         # 단일 파일로 뭉치기
        '--noconsole',                       # 콘솔 창 안 띄우기 (에러 확인시 제거 가능)
        '--uac-admin',                       # 관리자 권한 요청 (VC++ 설치를 위해 필수)
        f'--add-data={dist_dir};app_files',  # 앱 전체 파일군
        f'--add-data={redist_file};.',       # VC++ 설치 파일
        '--clean'                            # 캐시 정리 후 빌드
    ]
    
    # 3. 빌드 실행
    try:
        print("🔨 패키징 중... (파일 용량이 커서 몇 분 정도 소요될 수 있습니다)")
        PyInstaller.__main__.run(args)
        
        output_exe = os.path.join(root_dir, "dist", "N-Place-DB-Pro_Integrated.exe")
        print(f"\n✅ 완성되었습니다! 'dist/N-Place-DB-Pro_Integrated.exe' 파일을 확인하세요.")
        print("이제 이 파일 하나만 구매자에게 보내시면 됩니다.")

    except Exception as e:
        print(f"\n❌ 빌드 중 오류 발생: {e}")

if __name__ == "__main__":
    build()
