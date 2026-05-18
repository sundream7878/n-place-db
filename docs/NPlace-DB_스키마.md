# 제목: N-Place-DB 로컬 데이터베이스 스키마 정의서
- **버전**: v1.1.46
- **일시**: 2026-05-18 14:45

---

## 1. 데이터베이스 개요 (Database Overview)
- **종류**: SQLite3
- **기본 경로**: `data/database.sqlite` (프로그램 설치 루트 기준)
- **목적**: 수집된 네이버 플레이스 업체 정보의 누적 관리 및 이메일/인스타 발송 결과(결과 플래그, 에러 로그)의 보존.

---

## 2. 테이블 정의 (Table Definition)

### 📌 `shops` 테이블
네이버 플레이스 수집 데이터 및 발송 결과가 실시간 적재되는 단일 코어 테이블입니다.

| 컬럼명 (Column) | 데이터 타입 (Type) | NULL 여부 | 제약 조건 (Constraint) | 설명 (Description) |
| :--- | :---: | :---: | :---: | :--- |
| **`id`** | INTEGER | PRIMARY KEY | AUTOINCREMENT | 고유 레코드 식별 번호 (1부터 순차 증가) |
| **`name`** | TEXT | NULL | | 수집된 플레이스 업체명 (상호명) |
| **`phone`** | TEXT | NULL | | 업체 전화번호 (예: 010-XXXX-XXXX, 02-XXX-XXXX) |
| **`detail_url`** | TEXT | NOT NULL | UNIQUE | 플레이스 상세 페이지 고유 주소 (예: `https://place.naver.com/12345`) |
| **`address`** | TEXT | NULL | | 업체 등록 지번/도로명 주소 |
| **`email`** | TEXT | NULL | | 수집된 대표/담당자 이메일 주소 |
| **`instagram_handle`** | TEXT | NULL | | 수집된 인스타그램 아이디 / 주소 |
| **`naver_blog_id`** | TEXT | NULL | | 수집된 네이버 블로그 ID |
| **`keyword`** | TEXT | NULL | | 수집 당시의 검색 키워드 |
| **`last_result_email`** | TEXT | NULL | | 최근 이메일 발송 결과 (`Success`, `Fail`, `None`) |
| **`last_msg_email`** | TEXT | NULL | | 최근 이메일 발송 로그/에러 상세 메시지 |
| **`last_result_insta`** | TEXT | NULL | | 최근 인스타 DM 발송 결과 (`Success`, `Fail`, `None`) |
| **`last_msg_insta`** | TEXT | NULL | | 최근 인스타 DM 발송 로그/에러 상세 메시지 |
| **`created_at`** | TIMESTAMP | NULL | DEFAULT CURRENT_TIMESTAMP | 레코드 수집 및 생성 일시 (UTC 기준 자동 적재) |

---

## 3. 인덱스 정의 (Indexes Definition)

### ⚡ `idx_detail_url`
- **대상 필드**: `detail_url`
- **목적**: 대용량 데이터 수집 과정에서 실시간 중복 체크 (`INSERT OR IGNORE` 및 `exists_by_url`) 동작 수행 시 조회 병목 현상을 방지하기 위한 B-Tree 인덱스.
- **SQL DDL**:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_detail_url ON shops (detail_url);
  ```

---

## 4. 테이블 생성 DDL (Data Definition Language)
```sql
CREATE TABLE IF NOT EXISTS shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    phone TEXT,
    detail_url TEXT UNIQUE,
    address TEXT,
    email TEXT,
    instagram_handle TEXT,
    naver_blog_id TEXT,
    keyword TEXT,
    last_result_email TEXT,
    last_msg_email TEXT,
    last_result_insta TEXT,
    last_msg_insta TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
