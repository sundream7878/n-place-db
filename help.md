# N-Place-DB 수집기 기술 지원 요청서

## 1. 현재 상태 (v1.1.11)
- **증상**: 수집 엔진(`step1_refined_crawler.py`)이 실행되고 약 28분간 작동하며 "완료" 메시지까지 뜨지만, **실제 수집된 데이터는 0건**으로 기록됨.
- **실행 환경**: Windows 10, PyInstaller (`--onedir`, `--noconsole`) 빌드.

## 2. 핵심 문제점 (Technical Issues)

### A. 과도한 데이터 필터링 로직 (Filter Over-Aggression)
- `step1_refined_crawler.py`의 `Multi-Mode Filtering` 로직에서, 사용자가 별도의 필터 키워드를 입력하지 않으면 수집 키워드의 마지막 단어(예: '뷰티샵')를 강제로 필터로 사용함.
- 이로 인해 상호명에 '뷰티샵'이라는 단어가 정확히 포함되지 않은 모든 업체(예: '속초뷰티', '미모헤어' 등)가 수집 대상에서 제외됨.

### B. 로깅 스트림 NoneType 에러 (Frozen Mode Issue)
- `--noconsole` 옵션으로 빌드된 경우 `sys.stdout`이 `None`이 되어, `logging` 모듈이 `emit` 시점에 `AttributeError: 'NoneType' object has no attribute 'write'`를 발생시킴.
- `app.py`와 엔진에서 로그 리다이렉션을 시도했으나, 일부 핸들러가 여전히 표준 출력을 참조하여 크래시를 유발함.

### C. 상세 정보 추출 실패 (Detail Extraction Failure)
- `extract_detail_info` 함수가 네이버 플레이스의 변경된 DOM 구조나 IP 차단으로 인해 상세 정보를 가져오지 못할 경우, 이를 건너뛰는 예외 처리가 너무 강해 전체 데이터가 0건이 될 수 있음.

## 3. 해결을 위한 가이드라인
- **필터링 완화**: `filter_mode`가 'all'이 아닐 때만 작동하도록 하고, 자동 키워드 추출 로직을 삭제하거나 사용자에게 선택권을 주어야 함.
- **로깅 완전 침묵**: `logging.basicConfig`에서 모든 `StreamHandler`를 제거하고 오직 `FileHandler`만 사용하도록 강제해야 함.
- **DB 경로 동기화**: `BASE_PATH` 설정을 실행 파일 위치로 확실히 고정하여 엔진과 대시보드가 동일한 SQLite 파일을 바라보게 해야 함.

### D. 로그 파편화 및 대시보드 가시성 문제 (Log Fragmentation & UI Sync)
- **증상**: 대시보드 실시간 로그창이 비어 있고, 폴더에는 `engine_crash.log`, `dashboard_ui.log`, `fatal_crash.log` 등 불필요한 로그 파일이 다수 생성됨.
- **원인**: 
    1. `NoneType` 에러를 피하기 위해 로그 출력 대상을 파일로 리다이렉션하는 과정에서 엔진과 대시보드가 서로 다른 파일명을 참조함.
    2. 로깅 핸들러가 체계적으로 관리되지 않아 여러 파일에 분산 기록되어 사용자가 실제 수집 상황을 파악하기 어려움.
- **해결 방안**: 
    1. 모든 로그를 `data/app.log`로 단일화.
    2. 대시보드 UI(`app.py`)가 해당 파일을 실시간 스트리밍하도록 경로 고정.
    3. 불필요한 로그 생성 로직 및 파일 제거.

## 4. 마지막 실행 로그 요약
```
AttributeError: 'NoneType' object has no attribute 'write'
Message: '✅ Crawling finished successfully!'
INFO: Local SQLite DB initialized at ...\data\database.sqlite
(수집 개수: 0건, 소요 시간: 28분)
```
