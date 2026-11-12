# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""데이터 검증의 실행 묶음 carrier(RX1b ② — apps.py 의 SettingCarrier 등록)를 진짜 DB·가짜 저장소·전역 등록부와 실제
실행기(모의 공급사 — test_runs_dataverify 의 world)로 잰다. 명령 export_runs·import_runs 를 이름으로 부른다.

    T2  저장 판 실행 둘(같은 판) → B 에 새 판 하나(다음 v<n>, 적용 안 함, 칸 바이트 같음), 두 실행 versions 의
        aiSettingId·aiSetting = 새 판, 그 판을 B 에서 적용해 지은 versions 와 같음(sha 셋이 맞음), 운영 관리자 AI 설정
        칸 = 새 판. 넣는 동안 B 의 모델 원천이 달라도 판 모델 설정 바이트 == A(Q13)
    T5  문서 없는 실행 — 저장 판·기본 판 실행의 결과·단계 data 바이트가 A 와 같음, 기본 판 versions 그대로
    T6  carrier id_fields() == ★b 고정 표(판 말고 0), 고정 표의 흐름 == REGISTRY 의 dataverify 흐름 전부
★ 입력·회사·숫자는 전부 지어낸 것이다(synthetic). 공급사는 모의뿐.
"""

import json
import re
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import Client

from esgapi.core.flows.binding import BINDINGS
from esgapi.core.flows.carriers import CARRIERS
from esgapi.core.flows.registry import REGISTRY
from esgapi.dataverify.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.dataverify.flows import colab_156 as flow
from esgapi.dataverify.service.selectors import ai_settings as setting_selectors
from esgapi.dataverify.service.services import ai_settings as setting_services
from esgapi.dataverify.tests.flows.support import options
from esgapi.dataverify.tests.flows.test_runs_dataverify import World, done_run, world
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.user.service.services.user import create_customer_user
from esgapi.user.service.utils.login import UserCreated

pytestmark = pytest.mark.django_db(transaction=True)
SHARED_FIXTURES = (world,)  # test_runs_dataverify 의 고정물을 이 모듈에서도 이름으로 찾게
WHEN = datetime(2026, 9, 2, 3, 4, 5, tzinfo=UTC)
B_SETTINGS_FIRST = 3  # B 에 미리 둔 판 수(A 와 순번이 어긋나게)
FIXED: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {
    # ★b 고정 표(보고 band-reports/RX1b.md — 판 말고 행 id 0)
    ("dataverify", "dataverify.colab@156"): {
        "versions": ("aiSettingId", "aiSetting"),
        "dataverify_ai_settings": ("oldId",),
    },
}


def a_setting(company_id: int, *, title: str = "가상 판", apply: bool = True) -> int:
    made = setting_services.create_setting(company_id=company_id, created_by_user_id=9, title=title, memo="가상 메모")
    assert isinstance(made, setting_services.Created), made
    if apply:
        applied = setting_services.apply_setting(company_id=company_id, setting_id=made.id, now=WHEN)
        assert isinstance(applied, setting_services.Applied)
    return made.id


def a_user(company_id: int) -> int:
    made = create_customer_user(
        actor_kind="admin",
        company_id=company_id,
        username=f"gasang-dv-{company_id}",
        name="가상 사람",
        password="Gasang-Pw-2026!",
    )
    assert isinstance(made, UserCreated)
    return made.user_id


def round_trip(tmp_path: Path, a: int, runs: list[int], b: int, user: int) -> dict[int, int]:
    out = tmp_path / "bundle.zip"
    call_command(
        "export_runs",
        "--company",
        str(a),
        "--runs",
        ",".join(map(str, runs)),
        "--out",
        str(out),
        stdout=StringIO(),
        stderr=StringIO(),
    )
    printed = StringIO()
    call_command(
        "import_runs",
        str(out),
        "--company",
        str(b),
        "--user",
        str(user),
        "--orphans-out",
        str(tmp_path / "o.txt"),
        stdout=printed,
    )
    return {int(old): int(new) for old, new in re.findall(r"실행 (\d+) → (\d+)", printed.getvalue())}


def body_bytes(company: int, run_id: int) -> tuple[bytes, bytes]:
    results = [(r.schema_version, r.body) for r in run_selectors.run_results(company_id=company, run_id=run_id)]
    steps = [(s.name, s.data, s.partial) for s in run_selectors.step_rows(company_id=company, run_id=run_id)]
    return json.dumps(results, ensure_ascii=False).encode(), json.dumps(steps, ensure_ascii=False).encode()


def test_saved_and_default_setting_runs_come_back(
    tmp_path: Path, client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T2·T5(데이터 검증 몫)."""
    a, b = world.company_a, world.company_b
    setting_a = a_setting(a)
    first = done_run(client, world, monkeypatch, options())
    second = done_run(client, world, monkeypatch, options())
    saved = run_selectors.find_run(company_id=a, run_id=first)
    assert saved is not None
    assert (saved.versions["aiSettingId"], saved.versions["aiSetting"]) == (setting_a, "v1")  # ★d
    setting_services.apply_setting(company_id=a, setting_id=None, now=WHEN)
    third = done_run(client, world, monkeypatch, options())
    default = run_selectors.find_run(company_id=a, run_id=third)
    assert default is not None
    assert (default.versions["aiSettingId"], default.versions["aiSetting"]) == (None, DEFAULT_TITLE)  # ★d
    for n in range(B_SETTINGS_FIRST):
        a_setting(b, title=f"가상 B 판 {n}", apply=False)
    with monkeypatch.context() as patched:  # Q13: B 의 모델 원천이 달라도(받기를 다시 거치면 거절) 판 바이트 그대로
        narrower = tuple(setting_selectors.RunModelSource().steps())[:-1]

        def other_steps(self: setting_selectors.RunModelSource) -> object:
            return narrower

        patched.setattr(setting_selectors.RunModelSource, "steps", other_steps)
        runs = round_trip(tmp_path, a, [first, second, third], b, a_user(b))
    new_name = f"v{B_SETTINGS_FIRST + 1}"
    assert len(setting_selectors.setting_names(b)) == B_SETTINGS_FIRST + 1  # 판 하나만(Qb2)
    page = setting_selectors.ai_setting_page(company_id=b, limit=10, offset=0)
    (new_head,) = [item for item in page.items if item.name == new_name]
    assert page.applied_id is None
    detail_a = setting_selectors.ai_setting_detail(company_id=a, setting_id=setting_a)
    detail_b = setting_selectors.ai_setting_detail(company_id=b, setting_id=new_head.id)
    assert isinstance(detail_a, setting_selectors.AiSetting) and isinstance(detail_b, setting_selectors.AiSetting)
    same = ("title", "memo", "model_settings", "prompts")
    assert {k: getattr(detail_b, k) for k in same} == {k: getattr(detail_a, k) for k in same}
    assert detail_b.applied is False
    for old in (first, second):
        found = run_selectors.find_run(company_id=b, run_id=runs[old])
        assert found is not None
        assert found.versions == {**saved.versions, "aiSettingId": new_head.id, "aiSetting": new_name}
        detail = operator_selectors.operator_run_detail(actor_kind="admin", company_id=b, run_id=runs[old])
        assert isinstance(detail, operator_selectors.OperatorRunDetail)
        assert detail.run.ai_setting == (new_head.id, new_name)
    found = run_selectors.find_run(company_id=b, run_id=runs[third])
    assert found is not None and found.versions == default.versions
    for old in (first, second, third):
        assert body_bytes(b, runs[old]) == body_bytes(a, old)  # T5: 결과·단계 바이트 같음
    setting_services.apply_setting(company_id=b, setting_id=new_head.id, now=WHEN)
    rebuilt = BINDINGS.documentless(flow.FLOW_ID).versions_with(options(), company_id=b)  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
    assert rebuilt == {**saved.versions, "aiSettingId": new_head.id, "aiSetting": new_name}  # sha 셋이 새 판과 맞음


def test_the_id_fields_are_the_fixed_table_and_cover_every_flow() -> None:
    """T6."""
    carrier = CARRIERS.get("dataverify")
    assert carrier is not None
    union: dict[str, tuple[str, ...]] = {}
    for places in FIXED.values():
        union |= places
    assert dict(carrier.id_fields()) == union
    assert {flow_id for _module, flow_id in FIXED} == {found.id for found in REGISTRY.flows_of("dataverify")}
