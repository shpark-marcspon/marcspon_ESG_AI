"""보안 층의 자료 심기. 주인 역할의 연결(owner 고정물)로 행을 넣고 커밋한다(앱에는 이 길이 없다).

표의 칸을 아는 INSERT 글은 이 파일에만 둔다. 칸이나 표가 바뀌면(K1u-b 의 core 표 company_id, X1 의 실행 표) 이 파일만
고친다. 테스트는 아래 함수를 부른다: 회사 둘, 사업장, 문서, 일감, 호출 기록 줄.
회사 id 는 식별 열이라 표를 비워도 되돌아가지 않는다 — 박지 말고 add_companies 가 돌려준 값을 쓴다.
core 의 세 표(문서·일감·기록)의 id 도 식별 열이다: 넣은 행의 id 는 DB 가 짓고 함수가 돌려준다. 회사 칸은 company_id
(문서·일감은 company 를 가리키는 외래 키, 기록은 외래 키가 아닌 숫자 칸).
"""

import uuid
from datetime import datetime
from typing import Any

import psycopg

Owner = psycopg.Connection[tuple[Any, ...]]

# 쓸 수 있는 회사(is_active) 둘. 기본값(false)이면 교환이 전부 403 이다. subdomain 이 토큰의 tenant_id 다.
COMPANIES_INSERT = (
    "INSERT INTO company (name, business_licence_number, subdomain, is_active, created_at, updated_at) VALUES "
    "('가 회사', '000-00-00001', 'tenant-a', true, now(), now()), "
    "('나 회사', '000-00-00002', 'tenant-b', true, now(), now()) "
    "RETURNING subdomain, id"
)
SITE_INSERT = "INSERT INTO sites (company_id, name, created_at) VALUES (%s, %s, now())"
DOCUMENT_INSERT = (
    "INSERT INTO core_documents (company_id, uploaded_by, file_name, storage_key, size_bytes, status, "
    "created_at, updated_at) VALUES (%s, 'seed', %s, %s, %s, %s, now(), now()) RETURNING id"
)
JOB_INSERT = (
    "INSERT INTO run_jobs (company_id, document_id, kind, status, attempts, summary, lease_expires_at, "
    "created_at, updated_at) VALUES (%s, %s, 'parse', %s, %s, %s::jsonb, %s, now(), now()) RETURNING id"
)
# 호출 기록 한 줄. 싱크를 거치지 않는 날 INSERT 다(앱 역할의 연결로 거절을 잴 때도 이 글을 쓴다).
LOG_INSERT = (
    "INSERT INTO core_llm_call_logs (company_id, module, ts, call_id, attempt, prompt_id, "
    "prompt_version, template_hash, request_hash, cost_usd, duration_ms, result_kind, warnings, has_error_status, "
    "has_previous_error_status, created_at) "
    "VALUES (%s, %s, now(), 'call-raw', 0, 't/plain@1', 1, 'a', 'b', %s, 1, 'success', "
    "'[]'::jsonb, false, false, now())"
)


def add_companies(owner: Owner) -> tuple[int, int]:
    """회사 둘(subdomain tenant-a·tenant-b)을 등록한다(마크스폰 관리자가 하는 일). A·B 의 id 를 돌려준다."""
    ids = {subdomain: int(company_id) for subdomain, company_id in owner.execute(COMPANIES_INSERT).fetchall()}
    return ids["tenant-a"], ids["tenant-b"]


def add_site(owner: Owner, company_id: int, name: str) -> None:
    owner.execute(SITE_INSERT, [company_id, name])


def add_document(
    owner: Owner, company_id: int, *, file_name: str = "a.pdf", size_bytes: int = 100, status: str = "awaiting_upload"
) -> int:
    """문서 행 하나. 저장소에는 아무것도 없다(올림 확인을 거치지 않은 행이다). 문서 id(DB 가 지은 숫자)를 돌려준다.
    키의 UUID 는 문서 id 가 아니다(제품의 storage_key 와 같은 꼴)."""
    key = f"companies/{company_id}/documents/{uuid.uuid4()}/original"
    row = owner.execute(DOCUMENT_INSERT, [company_id, file_name, key, size_bytes, status]).fetchone()
    assert row is not None
    return int(row[0])


def add_job(
    owner: Owner,
    company_id: int,
    document_id: int,
    *,
    status: str = "queued",
    attempts: int = 0,
    summary: str = "{}",
    lease_expires_at: datetime | None = None,
) -> int:
    """일감 행 하나. 회사가 문서의 것과 다르면 DB 가 거절한다(같은 회사 외래 키, 23503). 일감 id 를 돌려준다."""
    row = owner.execute(JOB_INSERT, [company_id, document_id, status, attempts, summary, lease_expires_at]).fetchone()
    assert row is not None
    return int(row[0])


def add_log(owner: Owner, company_id: int, module: str, cost_usd: str) -> None:
    """호출 기록 한 줄을 커밋해 둔다(다른 프로세스가 쓴 행인 셈이다)."""
    owner.execute(LOG_INSERT, [company_id, module, cost_usd])


# 회사 하나(K2c — companyId 를 생략한 사용자 관리 경로의 「하나뿐인 회사」). 쓸 수 있는 회사로 넣는다.
COMPANY_INSERT = (
    "INSERT INTO company (name, business_licence_number, subdomain, is_active, created_at, updated_at) "
    "VALUES (%s, %s, %s, true, now(), now()) RETURNING id"
)


def add_company(owner: Owner, subdomain: str, *, name: str = "홀로 회사", licence: str = "000-00-00003") -> int:
    """회사 하나를 등록한다(add_companies 를 부르지 않는 테스트에서 — 회사 표에 이 행 하나뿐). 회사 id 를 돌려준다."""
    row = owner.execute(COMPANY_INSERT, [name, licence, subdomain]).fetchone()
    assert row is not None
    return int(row[0])
