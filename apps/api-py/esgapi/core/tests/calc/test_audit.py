"""감사 기록의 값과 꼴 검사(core/calc/audit.py — AU1a). 순수 층: DB 없이 경계의 짝을 잰다."""

from typing import Any

import pytest

from esgapi.core.calc.audit import (
    ACTOR_KINDS,
    AUDIT_ACTIONS,
    AUDIT_RESULTS,
    DETAIL_MAX_OCTETS,
    LABEL_MAX,
    TARGET_KINDS,
    EventRefused,
    audit_detail,
    check_event,
    detail_octets,
)

GOOD: dict[str, Any] = {
    "company_id": 1,
    "actor_kind": "service",
    "actor_user_id": 7,
    "action": "setting_change",
    "event": "user_updated",
    "result": "success",
    "reason": None,
    "target_kind": "user",
    "target_id": 8,
    "target_label": "kim",
    "changed_fields": ("name", "is_active"),
}


def check(**overrides: Any) -> EventRefused | None:
    return check_event(**{**GOOD, **overrides})


def test_the_values_are_the_nine_actions_and_their_companions() -> None:
    assert AUDIT_ACTIONS == (
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
    assert AUDIT_RESULTS == ("success", "failure")
    assert ACTOR_KINDS == ("admin", "service", "command", "anonymous")
    assert TARGET_KINDS == ("user", "document", "run", "report", "greenwash_item", "ai_setting", "run_log_export")
    assert (LABEL_MAX, DETAIL_MAX_OCTETS) == (255, 1024)


def test_a_good_event_passes() -> None:
    assert check() is None  # 분모: 아래의 거절은 칸 하나만 바꾼 것이다
    assert check(company_id=None, actor_kind="admin", actor_user_id=3) is None  # 운영 관리자 쪽(회사 없음)
    assert check(company_id=None, actor_kind="anonymous", actor_user_id=None, target_kind=None, target_id=None,
                 target_label=None, changed_fields=None, result="failure", reason="unknown_user") is None  # fmt: skip
    assert check(company_id=None, actor_kind="command", actor_user_id=None) is None


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"action": "export"}, "action"),
        ({"result": "partial"}, "result"),
        ({"actor_kind": "root"}, "actor_kind"),
        ({"actor_kind": "service", "company_id": None}, "company_id"),  # 고객사 사람의 줄은 회사가 있다(N2)
        ({"company_id": 0}, "company_id"),
        ({"company_id": True}, "company_id"),
        ({"actor_user_id": -1}, "actor_user_id"),
        ({"target_id": 0}, "target_id"),
        ({"event": "User_updated"}, "event"),  # 대문자
        ({"event": ""}, "event"),  # 빈 글자
        ({"event": "a" * 41}, "event"),  # 41자
        ({"reason": "Wrong"}, "reason"),
        ({"target_kind": "invoice"}, "target_kind"),  # 모르는 갈래
        ({"target_label": "가" * (LABEL_MAX + 1)}, "target_label"),  # 256자
        ({"changed_fields": ("Name",)}, "changed_fields"),  # 대문자 이름
    ],
)
def test_one_field_outside_the_shape_is_refused_by_name(overrides: dict[str, Any], field: str) -> None:
    assert check(**overrides) == EventRefused(field)


def test_the_edges_pass_on_the_inside() -> None:
    assert check(event="a" * 40) is None  # 40자
    assert check(reason="wrong_password", result="failure") is None
    assert check(target_label="가" * LABEL_MAX) is None  # 255자
    assert check(changed_fields=()) is None  # 멱등 수정 — 바뀐 칸 0


def test_the_detail_size_is_the_jsonb_text_bytes_with_its_edge() -> None:
    assert audit_detail(None) == {}
    assert audit_detail(("name",)) == {"changed_fields": ["name"]}
    assert detail_octets({"changed_fields": ["a", "b"]}) == len('{"changed_fields": ["a", "b"]}')
    # 경계 짝: 이름 꼴(40자)을 지키며 바이트를 채운다. 1024 는 지나고 1025 는 거절.
    names = ["a" * 40] * 22  # 22 × 40 + 쉼표·따옴표 — 남은 바이트를 아래에서 맞춘다
    base = detail_octets({"changed_fields": names})
    room = DETAIL_MAX_OCTETS - base
    assert 4 < room < 44  # 맞출 자리가 남았다(분모 — 이름 하나가 들어갈 만큼)
    fits = (*names, "a" * (room - 4))  # 새 이름 하나가 `, ""` 넷과 그 글자를 더한다
    assert detail_octets(audit_detail(fits)) == DETAIL_MAX_OCTETS
    assert check(changed_fields=fits) is None
    over = (*names, "a" * (room - 3))
    assert detail_octets(audit_detail(over)) == DETAIL_MAX_OCTETS + 1
    assert check(changed_fields=over) == EventRefused("detail")


@pytest.mark.parametrize("module", ["greenwash", "inventory.scope3", "a", "a" * 64, None])
def test_a_module_id_passes(module: str | None) -> None:
    assert check(module=module) is None


@pytest.mark.parametrize("module", ["Bad", "a_b", "a" * 65, "", "1a", "a.", "greenwash.Scope3"])
def test_a_module_outside_the_shape_is_refused(module: str) -> None:
    assert check(module=module) == EventRefused("module")


def test_the_module_rides_in_the_detail_and_counts_in_its_size() -> None:
    assert audit_detail(("applied",), "greenwash") == {"changed_fields": ["applied"], "module": "greenwash"}
    assert audit_detail(None, "greenwash") == {"module": "greenwash"}
    assert audit_detail(("applied",)) == {"changed_fields": ["applied"]}  # 분모: module 없으면 칸 0
    # 이름 칸만으로 1024 에 꼭 맞춘 detail 에 module 을 더하면 넘는다
    names = ["a" * 40] * 22
    room = DETAIL_MAX_OCTETS - detail_octets({"changed_fields": names})
    fits = (*names, "a" * (room - 4))
    assert check(changed_fields=fits) is None
    assert check(changed_fields=fits, module="greenwash") == EventRefused("detail")


def test_a_refusal_carries_no_value() -> None:
    refused = check(target_label="s3cret-" + "x" * LABEL_MAX)
    assert refused == EventRefused("target_label")
    assert "s3cret" not in repr(refused)
