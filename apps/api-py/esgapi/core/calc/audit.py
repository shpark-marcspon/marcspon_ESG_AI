"""감사 기록(표 core_audit_events — core/models.py 의 AuditEventRow)의 값과 꼴 검사. 순수하다(`.importlinter` 계약 다의
`esgapi.*.calc`).

    AUDIT_ACTIONS   화면 배지가 되는 행동 아홉. AU1a 가 부르는 것은 넷(login·logout·upload·setting_change)이고
                    나머지 다섯(run·download·adopt·exclude·confirm)은 뒤 밴드가 부르는 자리만 더한다(MARC-ENT-291).
    check_event     쓰기 전에 꼴을 본다(던지지 않는다 — 부르는 쪽이 업무 블록 안일 수 있다, K-B4).

★ 값을 고치면 core/models.py 의 같은 튜플(마이그레이션이 CHECK 로 굳힌 값)도 고치고 새 마이그레이션을 낸다.
  둘이 같은지는 core/tests/test_models.py 가 견준다.
"""

import json
import re
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.core.calc.ids import is_company_id

AuditAction = Literal["login", "logout", "upload", "run", "download", "setting_change", "adopt", "exclude", "confirm"]
AUDIT_ACTIONS: Final[tuple[AuditAction, ...]] = (
    "login",
    "logout",
    "upload",
    "run",
    "download",
    "setting_change",
    "adopt",
    "exclude",
    "confirm",
)
AuditResult = Literal["success", "failure"]
AUDIT_RESULTS: Final[tuple[AuditResult, ...]] = ("success", "failure")
# 누가 했는가: 운영 관리자 · 고객사 사용자 · 관리 명령(셸을 쥔 사람 — 사람 id 없음) ·
# 누구인지 모름(모르는 아이디의 로그인)
ActorKind = Literal["admin", "service", "command", "anonymous"]
ACTOR_KINDS: Final[tuple[ActorKind, ...]] = ("admin", "service", "command", "anonymous")
# 대상의 갈래(글자 칸이라 CHECK 는 없다 — 여기 상수만). AU1a 가 쓰는 것은 user·document 둘.
TARGET_KINDS: Final = ("user", "document", "run", "report", "greenwash_item", "ai_setting", "run_log_export")
# 사건 이름·실패 까닭·바뀐 칸 이름의 꼴. 로그의 이름 칸(core/observability/jsonlog.py 의 NAME)과 같은 꼴이다.
NAME: Final = re.compile(r"[a-z][a-z_]{0,39}")
LABEL_MAX: Final = 255  # target_label 의 글자 수(칸 varchar(255))
# 그 줄이 어느 모듈의 일인가(detail 의 module — AD4S). runs 의 모듈 id 꼴
# (runs/service/schemas/runs.py 의 MODULE_PATTERN)과 같은 글자이고 길이 상한은 RunRow.module 의 64 다.
# core 는 runs 를 import 하지 못해(계약 가) 베꼈다 — runs/tests/test_extras.py 가 견준다.
MODULE_ID: Final = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)*$")
MODULE_MAX: Final = 64
DETAIL_MAX_OCTETS: Final = 1024  # 어림(근거 없는 수) — detail 의 jsonb 글자 바이트. DB 의 CHECK 와 같다


@dataclass(frozen=True, slots=True)
class EventRefused:
    """꼴 밖이라 쓰지 않는다. field 는 어긋난 칸의 이름뿐이다(값은 싣지 않는다 — 비밀이 섞였을 수 있다)."""

    field: str


def audit_detail(changed_fields: tuple[str, ...] | None, module: str | None = None) -> dict[str, list[str] | str]:
    """detail 칸(jsonb)에 싣는 것. 이름 있는 칸만 — 바뀐 칸의 이름 목록(값 0)과 모듈 id(AD4S)."""
    detail: dict[str, list[str] | str] = {} if changed_fields is None else {"changed_fields": list(changed_fields)}
    if module is not None:
        detail["module"] = module
    return detail


def detail_octets(detail: dict[str, list[str] | str]) -> int:
    """PostgreSQL 이 jsonb 를 글자로 내는 꼴(`{"a": [1, 2]}` — 쌍점·쉼표 뒤 빈칸)의 UTF-8 바이트 수."""
    return len(json.dumps(detail, ensure_ascii=False, separators=(", ", ": ")).encode())


def _id_or_none(value: object) -> bool:
    return value is None or is_company_id(value)  # 사람·대상 id 도 양의 정수 꼴이다


def check_event(
    *,
    company_id: int | None,
    actor_kind: str,
    actor_user_id: int | None,
    action: str,
    event: str,
    result: str,
    reason: str | None,
    target_kind: str | None,
    target_id: int | None,
    target_label: str | None,
    changed_fields: tuple[str, ...] | None,
    module: str | None = None,
) -> EventRefused | None:
    """꼴이 맞으면 None, 아니면 처음 어긋난 칸. DB 의 CHECK 가 막을 것을 미리 본다(DB 오류를 블록 안에서 내지 않게)."""
    checks: tuple[tuple[str, bool], ...] = (
        ("company_id", _id_or_none(company_id)),
        ("actor_kind", actor_kind in ACTOR_KINDS),
        ("actor_user_id", _id_or_none(actor_user_id)),
        # 고객사 사람의 줄은 회사가 있다(DB 의 CHECK core_audit_events_service_company_check 와 같다)
        ("company_id", not (actor_kind == "service" and company_id is None)),
        ("action", action in AUDIT_ACTIONS),
        ("event", NAME.fullmatch(event) is not None),
        ("result", result in AUDIT_RESULTS),
        ("reason", reason is None or NAME.fullmatch(reason) is not None),
        ("target_kind", target_kind is None or target_kind in TARGET_KINDS),
        ("target_id", _id_or_none(target_id)),
        ("target_label", target_label is None or len(target_label) <= LABEL_MAX),
        ("changed_fields", changed_fields is None or all(NAME.fullmatch(name) for name in changed_fields)),
        ("module", module is None or (len(module) <= MODULE_MAX and MODULE_ID.fullmatch(module) is not None)),
        ("detail", detail_octets(audit_detail(changed_fields, module)) <= DETAIL_MAX_OCTETS),
    )
    return next((EventRefused(field) for field, ok in checks if not ok), None)
