"""실행 기록 칸 원천의 등록부(runs/extras.py — AD4S)를 잰다. 순수 층(DB 없음). 감사 module 꼴 대조(M4)도 여기다.

재는 것: 두 번 달면 예외(같은 객체여도) · 없는 모듈은 None · 단 차례 · 프로세스의 EXTRAS 에 그린워싱이 달려 있다(이름은
등록부가 준 글자로만 — runs 는 업무 모듈을 import 하지 않는다).
"""

from collections.abc import Collection, Mapping
from typing import Any

import pytest
from django.db.models import Q

from esgapi.core.calc.audit import MODULE_ID, MODULE_MAX
from esgapi.runs.extras import EXTRAS, ExtrasRegistry, ExtrasRegistryError
from esgapi.runs.models import RunRow
from esgapi.runs.service.schemas.runs import MODULE_PATTERN


class FakeSource:
    def reviewable_q(self) -> Q:
        return Q(status="done")

    def states(self, company_id: int, run_ids: Collection[int]) -> Mapping[int, str]:
        return {}

    def run_ids_in(self, company_id: int, states: Collection[str]) -> Any:
        return []

    def ai_setting(self, versions: Mapping[str, object]) -> tuple[int | None, str] | None:
        return None


def test_a_module_takes_one_source() -> None:
    registry = ExtrasRegistry()
    source = FakeSource()
    registry.register("alpha", source)
    with pytest.raises(ExtrasRegistryError):
        registry.register("alpha", source)  # 같은 객체여도
    assert registry.get("alpha") is source
    assert registry.get("beta") is None


def test_modules_are_in_registration_order() -> None:
    registry = ExtrasRegistry()
    assert registry.modules() == ()
    registry.register("beta", FakeSource())
    registry.register("alpha", FakeSource())
    assert registry.modules() == ("beta", "alpha")


def test_the_audit_module_id_is_the_runs_module_id() -> None:
    """core 의 감사 module 꼴(core/calc/audit.py — runs 를 import 하지 못해 베낌)이 runs 의 모듈 id 꼴과 같다
    (AD4S ③)."""
    assert MODULE_ID.pattern == MODULE_PATTERN
    assert RunRow._meta.get_field("module").max_length == MODULE_MAX == 64


def test_the_process_registry_has_the_greenwash_source() -> None:
    """앱이 ready() 에서 단다(INSTALLED_APPS 의 업무 모듈 — 지금은 그린워싱 하나)."""
    assert EXTRAS.modules() == ("greenwash", "translation", "dataverify", "materiality", "drafting")  # TR4 ③ 영문번역
    # · DVA1 ③ 데이터 검증 AI 설정 칸(플랫폼-서버 e5 허락 — 차례 = INSTALLED_APPS)
    # · IR4 ③ 중대성평가 IRO AI 설정 칸(플랫폼-서버 e5 허락)
