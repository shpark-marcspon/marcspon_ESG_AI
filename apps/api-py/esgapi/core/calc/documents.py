"""올린 문서와 그 문서에 걸린 일감의 순수 규칙: 상태와 전이, 저장소 키, 파일 이름, 누가 올릴 수 있는가, 쪽 재기의 한도.

순수하다(django·ninja·psycopg 를 모른다. `.importlinter` 계약 다). DB 없이 테스트된다.
TS 뼈대의 packages/core/src/document.ts 는 다섯 상태를 한 표에 두었다. 여기서는 둘로 갈랐다:
문서는 「올라왔는가」만 알고, 그 문서로 하는 일(분해 …)의 진행은 일감이 안다(문서 하나에 일감이 여럿일 수 있다).

    문서   awaiting_upload ──▶ uploaded(끝)
    일감   queued ──▶ processing ──▶ done(끝) | failed(끝)
                        └──▶ processing   (재시도·이어받기)

★ 상태의 값은 DB 의 CHECK 에도 굳어 있다(core/migrations/0001). 값을 더하면 새 마이그레이션을 같이 낸다
  (esgapi/core/tests/test_documents_calc.py 가 이 튜플과 모델의 제약을 견준다).
★ 이 밴드(W1a)가 실제로 밟는 전이는 문서의 하나와 「일감을 queued 로 만든다」뿐이다. processing 부터는 워커(W1b)가
  밟는다. 표는 지금 다 세워 둔다.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal, get_args

from esgapi.core.calc.ids import is_company_id

# ── 상태와 전이 ───────────────────────────────────────────────────────

DocumentStatus = Literal["awaiting_upload", "uploaded"]
DOCUMENT_STATUSES: Final[tuple[DocumentStatus, ...]] = get_args(DocumentStatus)
DOCUMENT_TRANSITIONS: Final[dict[DocumentStatus, tuple[DocumentStatus, ...]]] = {
    "awaiting_upload": ("uploaded",),
    "uploaded": (),
}

JobStatus = Literal["queued", "processing", "done", "failed"]
JOB_STATUSES: Final[tuple[JobStatus, ...]] = get_args(JobStatus)
JOB_TRANSITIONS: Final[dict[JobStatus, tuple[JobStatus, ...]]] = {
    "queued": ("processing",),
    "processing": ("processing", "done", "failed"),
    "done": (),
    "failed": (),
}

# 일감의 종류. DB 에는 CHECK 를 걸지 않았다(뒤 모듈 밴드가 종류를 더할 때 core 의 마이그레이션을 다시 쓰지 않게).
# 값은 서비스가 이 튜플로 거른다. 지금은 분해 하나다.
JobKind = Literal["parse"]
JOB_KINDS: Final[tuple[JobKind, ...]] = get_args(JobKind)


def can_transition_document(current: DocumentStatus, to: DocumentStatus) -> bool:
    return to in DOCUMENT_TRANSITIONS[current]


def can_transition_job(current: JobStatus, to: JobStatus) -> bool:
    return to in JOB_TRANSITIONS[current]


def is_document_finished(status: DocumentStatus) -> bool:
    return DOCUMENT_TRANSITIONS[status] == ()


def is_job_finished(status: JobStatus) -> bool:
    return JOB_TRANSITIONS[status] == ()


def is_document_status(value: object) -> bool:
    return isinstance(value, str) and value in DOCUMENT_STATUSES


def is_job_status(value: object) -> bool:
    return isinstance(value, str) and value in JOB_STATUSES


# ── 저장소 키 ─────────────────────────────────────────────────────────

# 회사 id 를 글자로 받는 자리(큐 쪽지·LLM 기록의 꼬리표·관리 명령의 --tenant)의 꼴: 십진 숫자, 0 으로 시작하지
# 않음, 19자까지. 0·음수·"01"·"1.0"·빈 글자·빈칸은 아니다. \Z 로 끝을 본다($ 는 끝의 줄바꿈 앞에서도 맞는다).
COMPANY_ID_TEXT: Final = re.compile(r"[1-9][0-9]{0,18}\Z")
_UUID_SHAPE: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


@dataclass(frozen=True, slots=True)
class StorageKey:
    key: str


@dataclass(frozen=True, slots=True)
class BadTenantId:
    """회사 id 가 키의 토막이 될 꼴(양의 정수)이 아니다. 키를 짓지 않았다. 이름은 옛 그대로(이름 바꾸기는 C1)."""


def storage_key(company_id: int, key_id: str) -> StorageKey | BadTenantId:
    """원본의 저장소 키: `companies/<company_id>/documents/<key_id>/original`.

    ★ 파일 이름을 받지 않는다. 사용자가 적은 글자가 키에 들어가는 길이 없다(경로 조작, 이름에 든 개인 정보).
    ★ key_id 는 문서 id 가 아니다: 키마다 따로 지은 UUID(소문자·줄표 꼴)다(문서 id 는 숫자라 셀 수 있다 — 키는
      미리 서명된 주소 안에서만 보인다). 꼴이 아니면 호출이 틀린 것이라 던진다.
    """
    if not is_company_id(company_id):
        return BadTenantId()
    if _UUID_SHAPE.match(key_id) is None:
        raise ValueError("key_id 는 소문자·줄표 꼴의 UUID 여야 한다")
    return StorageKey(f"companies/{company_id}/documents/{key_id}/original")


# ── 파일 이름 ─────────────────────────────────────────────────────────

MAX_FILE_NAME_CHARS: Final = 255
# 제어 글자(U+0000~U+001F, U+007F). NUL 은 PostgreSQL 의 글자 칸에 못 들어가고(넣으면 DB 오류 → 503),
# 줄바꿈·탭은 기록과 헤더를 깨뜨린다.
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]")


def is_valid_file_name(name: str) -> bool:
    """1~255자이고 제어 글자가 없다. 표시용 글자일 뿐이다(키에 안 들어간다). 확장자·형식은 보지 않는다."""
    return 1 <= len(name) <= MAX_FILE_NAME_CHARS and _CONTROL.search(name) is None


# 파일 이름 검색 글자(목록의 q)에 NUL 이 없다는 무늬(X1b-2a). NUL 은 PostgreSQL 의 글자 비교에 못 들어간다(500).
NO_NUL_PATTERN: Final = r"^[^\x00]*$"

# ── 보고 연도(X1b-2a) ─────────────────────────────────────────────────
# 계약의 범위 = core_documents 의 CHECK(core/models.py). 둘 다 어림이다.
REPORT_YEAR_MIN: Final = 1900  # 어림
REPORT_YEAR_MAX: Final = 2100  # 어림


# ── 쪽 수와 글자 층 재기(X1b-2a) ─────────────────────────────────────
# 올림 확인이 원본을 한 번 열어 쪽 수와 「앞 몇 쪽에 글자 층이 있는가」를 잰다(core/resources/pdf.py — 자식 프로세스).
# 다섯 다 어림이다(근거 없는 수). 쪽 수 n 은 디자인 e0·검증 73 의 「앞 몇 쪽 — 예 3」을 옮긴 것이다(sid:MARC-TICK-73).
# 전 쪽 기준의 판정은 그린워싱 실행의 no_text_layer 가 따로 한다(두 판정이 다른 것은 뜻한 것이다).
TEXT_PROBE_PAGES: Final = 3  # 어림
PDF_PROBE_TIMEOUT_S: Final = 5  # 어림 — 자식 프로세스의 벽시계 한도(초). CPU 한도는 이 값을 올림
PDF_PROBE_MEMORY_BYTES: Final = 512 * 1024 * 1024  # 어림 — 자식 프로세스의 주소 공간 한도(RLIMIT_AS)
# 어림 — 자식이 쪽마다 돌려주는 글의 앞 글자 수. 판정(has_text)은 공백 아닌 글자 하나면 되므로
# strip() 뒤 몇 자면 넉넉하다
PDF_PROBE_TEXT_CHARS: Final = 16
# 어림 — 부모가 읽는 자식 출력(stdout·stderr 각각)의 상한(바이트). 쪽 n 개 × 16자의 JSON 은 몇백 바이트다.
# 넘으면 값 null(PdfUnreadable("error")). 자식의 RLIMIT_FSIZE 는 이 값의 두 배(임시 파일이 디스크를 채우지 않게)
PDF_PROBE_OUTPUT_BYTES: Final = 64 * 1024


def has_text(page_texts: Iterable[str]) -> bool:
    """쪽들의 글 가운데 공백 밖 글자가 하나라도 있으면 True. 공백은 `str.strip()` 의 것(NBSP·줄바꿈 포함)이다."""
    return any(text.strip() for text in page_texts)
