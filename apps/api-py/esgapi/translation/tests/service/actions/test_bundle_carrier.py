# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""영문번역의 실행 묶음 carrier(RX1b ② — service/actions/bundle.py · apps.py 등록)를 진짜 DB·가짜 저장소·전역 등록부와
실제 실행기(모의 공급사 — test_runs_translation 의 world)로 잰다. 명령 export_runs·import_runs 를 이름으로 부른다.

    T2  저장 판 실행 둘(같은 판 — 첫 번역·재번역) → B 에 새 판 하나(다음 v<n>, 적용 안 함, 칸 바이트 같음), 두 실행
        versions 의 aiSettingId·aiSetting = 새 판, 그 판을 B 에서 적용해 지은 versions 와 같음, 운영 관리자 AI 설정 칸 =
        새 판. 넣는 동안 B 의 모델 원천이 달라도 판 모델 설정 바이트 == A(Q13)
    T3  재번역 짝의 뒤 하나만 골라도 앞이 따라옴(닫힘), B 의 options·result@1·단계 data(translate·report) 의
        retry.fromRunId = 새 앞 id(a1 덧붙임), 묶음 목록(batches)이 같음. rejected 재번역(앞이 failed·없는·남의 회사·
        다른 모듈 — ★k)은 --runs 거절·창은 건너뜀·「참조 밖 n」
    T6  carrier id_fields() == ★b 고정 표, 고정 표의 흐름 == REGISTRY 의 영문번역 흐름 전부
★ 문서·회사·숫자는 전부 지어낸 것이다(synthetic). 공급사는 모의뿐.
"""

import re
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from django.test import Client

from esgapi.core.flows.binding import BINDINGS
from esgapi.core.flows.carriers import CARRIERS
from esgapi.core.flows.registry import REGISTRY
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.services import bundle as run_bundle_services
from esgapi.translation.contracts.shapes import RESULT_SHAPE
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.service.actions import batches as batch_actions
from esgapi.translation.service.selectors import ai_settings as setting_selectors
from esgapi.translation.service.services import ai_settings as setting_services
from esgapi.translation.tests.engines.colab_158.support import ok
from esgapi.translation.tests.flows.support import SIMPLE_EN, options
from esgapi.translation.tests.flows.test_runs_translation import (
    NO_ISSUES,
    World,
    document,
    execute,
    new_run,
    run_of,
    scripted,
    world,
)
from tests.support.http import login

pytestmark = pytest.mark.django_db(transaction=True)
SHARED_FIXTURES = (world,)  # test_runs_translation 의 고정물을 이 모듈에서도 이름으로 찾게
WHEN = datetime(2026, 9, 2, 3, 4, 5, tzinfo=UTC)
FIXED: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {
    # ★b 고정 표(보고 band-reports/RX1b.md T1·T2·T4·T5·V1·V2)
    ("translation", "translation.colab@158"): {
        "versions": ("aiSettingId", "aiSetting"),
        "translation_ai_settings": ("oldId",),
        "options": ("retry.fromRunId",),
        "translation.result@1": ("settings.retry.fromRunId",),
        "step:translate": ("result.settings.retry.fromRunId",),
        "step:report": ("results[].settings.retry.fromRunId",),
    },
    # 밴드 TRD2 ★⑥: PDF 흐름은 워드 흐름과 같은 여섯 칸(layout@1·prepare 의 pdf 칸에 실행 id 0)
    ("translation", "translation.pdf@158"): {
        "versions": ("aiSettingId", "aiSetting"),
        "translation_ai_settings": ("oldId",),
        "options": ("retry.fromRunId",),
        "translation.result@1": ("settings.retry.fromRunId",),
        "step:translate": ("result.settings.retry.fromRunId",),
        "step:report": ("results[].settings.retry.fromRunId",),
    },
}


def a_setting(company_id: int, *, title: str = "가상 판", apply: bool = True) -> int:
    made = setting_services.create_setting(company_id=company_id, created_by_user_id=9, title=title, memo="가상 메모")
    assert isinstance(made, setting_services.Created), made
    if apply:
        applied = setting_services.apply_setting(company_id=company_id, setting_id=made.id, now=WHEN)
        assert isinstance(applied, setting_services.Applied)
    return made.id


def translated(client: Client, env: World, given: dict[str, Any]) -> int:
    env.mock.enqueue(ok(SIMPLE_EN)).enqueue(NO_ISSUES)
    run_id = new_run(client, env, given)
    execute(env, run_id)
    assert run_of(env, run_id).status == "done"
    return run_id


def a_pair(client: Client, env: World, monkeypatch: pytest.MonkeyPatch) -> tuple[int, int]:
    """첫 번역 → 그 실행을 앞으로 한 재번역(같은 원문 — 새 문서 행). 묶음 하나(batchId)."""
    scripted(monkeypatch, env)
    batch = "0b9a7c3e-6f1d-4c2b-9a8e-1d2c3b4a5f61"
    first = translated(client, env, options(batchId=batch))
    retry = translated(client, env, options(batchId=batch, retry={"fromRunId": first, "pages": [1]}))
    return first, retry


def a_user(company_id: int) -> int:
    from esgapi.user.service.services.user import create_customer_user
    from esgapi.user.service.utils.login import UserCreated

    made = create_customer_user(
        actor_kind="admin",
        company_id=company_id,
        username=f"gasang-tr-{company_id}",
        name="가상 사람",
        password="Gasang-Pw-2026!",
    )
    assert isinstance(made, UserCreated)
    return made.user_id


def export(tmp_path: Path, company: int, *args: str, name: str = "bundle.zip") -> str:
    printed = StringIO()
    call_command(
        "export_runs",
        "--company",
        str(company),
        *args,
        "--out",
        str(tmp_path / name),
        stdout=printed,
        stderr=StringIO(),
    )
    return printed.getvalue()


def imported(tmp_path: Path, b: int, user: int, name: str = "bundle.zip") -> dict[int, int]:
    printed = StringIO()
    call_command(
        "import_runs",
        str(tmp_path / name),
        "--company",
        str(b),
        "--user",
        str(user),
        "--orphans-out",
        str(tmp_path / f"o-{name}.txt"),
        stdout=printed,
    )
    return {int(old): int(new) for old, new in re.findall(r"실행 (\d+) → (\d+)", printed.getvalue())}


def retry_ids(company: int, run_id: int) -> dict[str, object]:
    found = run_selectors.find_run(company_id=company, run_id=run_id)
    assert found is not None
    results = {r.schema_version: r.body for r in run_selectors.run_results(company_id=company, run_id=run_id)}
    steps = {s.name: s.data for s in run_selectors.step_rows(company_id=company, run_id=run_id)}
    report: Any = steps["report"]
    return {
        "options": found.options["retry"]["fromRunId"],  # pyright: ignore[reportIndexIssue]
        "result@1": results[RESULT_SHAPE]["settings"]["retry"]["fromRunId"],  # pyright: ignore[reportIndexIssue, reportOptionalSubscript]
        "translate": steps["translate"]["result"]["settings"]["retry"]["fromRunId"],  # pyright: ignore[reportIndexIssue, reportOptionalSubscript]
        "report": [r["settings"]["retry"]["fromRunId"] for r in report["results"] if "settings" in r],
    }


def batch_view(company: int, runs: dict[int, str]) -> list[Any]:
    """묶음 목록을 이름표로(실행 id → 이름표, 문서·사람·회사 이름 → 꼴). runs 는 그 회사의 실행 id → 이름표."""
    page = batch_actions.batches(
        company_id=company, user_id=0, document_id=None, state=None, mine=False, limit=20, offset=0
    )

    def shape(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {k: shape(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [shape(v) for v in value]
        if key == "runId":
            return runs[value]
        if key in {"id", "userId", "name", "companyName"}:
            return key
        if key == "batchKey" and isinstance(value, str) and value.startswith("run-"):
            return f"run-{runs[int(value[4:])]}"
        return value

    return shape({k: v for k, v in page.items() if k != "companyName"})


def test_a_retry_brings_its_source_and_every_retry_id_is_rewritten(
    tmp_path: Path, client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3·T2(영문번역 몫)."""
    a, b = world.company_a, world.company_b
    setting_a = a_setting(a)
    first, retry = a_pair(client, world, monkeypatch)
    saved = run_of(world, first).versions
    assert (saved["aiSettingId"], saved["aiSetting"]) == (setting_a, "v1")  # ★d
    assert run_of(world, retry).versions == saved
    assert retry_ids(a, retry) == {"options": first, "result@1": first, "translate": first, "report": [first]}
    for title in ("가상 B 판 하나", "가상 B 판 둘"):  # B 의 순번이 A 와 어긋나게
        a_setting(b, title=title, apply=False)
    printed = export(tmp_path, a, "--runs", str(retry))  # 뒤 하나만 — 닫힘이 앞을 끈다
    assert "닫힘 1" in printed
    with monkeypatch.context() as patched:  # Q13: B 의 모델 원천이 달라도(받기를 다시 거치면 거절) 판 바이트 그대로
        narrower = tuple(setting_selectors.RunModelSource().steps())[:-1]

        def other_steps(self: setting_selectors.RunModelSource) -> object:
            return narrower

        patched.setattr(setting_selectors.RunModelSource, "steps", other_steps)
        runs = imported(tmp_path, b, a_user(b))
    assert sorted(runs) == [first, retry]
    assert retry_ids(b, runs[retry]) == {
        "options": runs[first],
        "result@1": runs[first],
        "translate": runs[first],
        "report": [runs[first]],
    }
    assert sorted(setting_selectors.setting_names(b)) == ["v1", "v2", "v3"]  # 판 하나만(Qb2)
    page = setting_selectors.ai_setting_page(company_id=b, limit=10, offset=0)
    (new_head,) = [item for item in page.items if item.name == "v3"]
    assert page.applied_id is None
    detail_a = setting_selectors.ai_setting_detail(company_id=a, setting_id=setting_a)
    detail_b = setting_selectors.ai_setting_detail(company_id=b, setting_id=new_head.id)
    assert isinstance(detail_a, setting_selectors.AiSetting) and isinstance(detail_b, setting_selectors.AiSetting)
    same = ("title", "memo", "model_settings", "prompts")
    assert {k: getattr(detail_b, k) for k in same} == {k: getattr(detail_a, k) for k in same}
    assert detail_b.applied is False
    for old in (first, retry):
        found = run_selectors.find_run(company_id=b, run_id=runs[old])
        assert found is not None and found.versions == {**saved, "aiSettingId": new_head.id, "aiSetting": "v3"}
        detail = operator_selectors.operator_run_detail(actor_kind="admin", company_id=b, run_id=runs[old])
        assert isinstance(detail, operator_selectors.OperatorRunDetail) and detail.run.ai_setting == (new_head.id, "v3")
    labels_a = {first: "앞", retry: "뒤"}
    labels_b = {runs[first]: "앞", runs[retry]: "뒤"}
    assert batch_view(b, labels_b) == batch_view(a, labels_a)
    setting_services.apply_setting(company_id=b, setting_id=new_head.id, now=WHEN)
    versions = BINDINGS.get(colab.FLOW_ID).versions_with(options(), company_id=b)  # pyright: ignore[reportAttributeAccessIssue]
    assert versions == {**saved, "aiSettingId": new_head.id, "aiSetting": "v3"}  # sha 셋이 새 판과 맞음


def test_a_default_setting_run_keeps_its_versions(
    tmp_path: Path, client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = world.company_a, world.company_b
    scripted(monkeypatch, world)
    run_id = translated(client, world, options())
    default = run_of(world, run_id).versions
    assert (default["aiSettingId"], default["aiSetting"]) == (None, "기본 설정")  # ★d
    export(tmp_path, a, "--runs", str(run_id))
    runs = imported(tmp_path, b, a_user(b))
    found = run_selectors.find_run(company_id=b, run_id=runs[run_id])
    assert found is not None and found.versions == default
    assert setting_selectors.setting_names(b) == ()


@pytest.mark.parametrize("kind", ["failed", "missing", "company", "module"])
def test_a_rejected_retry_is_refused_or_skipped(
    tmp_path: Path, client: Client, world: World, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """★k·T3: 흐름이 거절(rejected retry_source_not_found)한 재번역 — 묶음은 그 앞을 싣지 못한다(Qb8)."""
    a = world.company_a
    scripted(monkeypatch, world)
    plain = translated(client, world, options())
    if kind == "failed":
        source = run_bundle_services.insert_run(
            company_id=a,
            fields={
                "module": "translation",
                "flow_id": colab.FLOW_ID,
                "options": options(),
                "versions": {},
                "status": "failed",
                "created_by_user_id": 9,
                "document_id": document(world, a),
            },
        )
    elif kind == "missing":
        source = plain + 10_000
    elif kind == "company":
        login(client, tenant_id="tenant-b")
        source = new_run(client, world, options())  # 회사 B 의 실행(만들기만)
        login(client)
    else:
        source = run_bundle_services.insert_run(
            company_id=a,
            fields={
                "module": "greenwash",
                "flow_id": "greenwash.colab@E0",
                "options": {},
                "versions": {},
                "status": "done",
                "created_by_user_id": 9,
                "document_id": document(world, a),
            },
        )
    world.mock.enqueue(ok(SIMPLE_EN)).enqueue(NO_ISSUES)
    rejected = new_run(client, world, options(retry={"fromRunId": source, "pages": [1]}))
    execute(world, rejected)
    found = run_of(world, rejected)
    assert found.status == "done"
    body = {r.schema_version: r.body for r in run_selectors.run_results(company_id=a, run_id=rejected)}[RESULT_SHAPE]
    assert body["rejection"]["kind"] == "retry_source_not_found"  # pyright: ignore[reportIndexIssue, reportOptionalSubscript]
    with pytest.raises(CommandError, match="같은 모듈 done 이 아니다") as caught:
        export(tmp_path, a, "--runs", str(rejected))
    assert caught.value.returncode == 1
    today = datetime.now(UTC).date()
    printed = export(
        tmp_path,
        a,
        "--module",
        "translation",
        "--from",
        str(today - timedelta(days=1)),
        "--to",
        str(today + timedelta(days=1)),
        name="window.zip",
    )
    assert "참조 밖 1" in printed and "실행 1(닫힘 0)" in printed  # rejected 만 건너뛰고 plain 을 싣는다


def test_the_id_fields_are_the_fixed_table_and_cover_every_flow() -> None:
    """T6."""
    carrier = CARRIERS.get("translation")
    assert carrier is not None
    union: dict[str, tuple[str, ...]] = {}
    for places in FIXED.values():
        union |= places
    assert dict(carrier.id_fields()) == union
    assert {flow for _module, flow in FIXED} == {flow.id for flow in REGISTRY.flows_of("translation")}


# ── HD1 S1(405 노트 s1): 꾸민 묶음의 fromRunId — 영문번역 cd[9a83f1] 허락(더하기만) ─────────────────


def s1_rewrite(options: dict[str, object]) -> object:
    from esgapi.core.flows.carriers import IdMap
    from esgapi.translation.service.actions.bundle import TranslationCarrier

    found = TranslationCarrier().rewrite(
        options=options,
        versions={},
        results=[],
        steps=[],
        partials=[],
        ids=IdMap(run={7: 70}, document={}, ai_setting={}),
    )
    return found.options


@pytest.mark.parametrize(
    "value", ["123", 5.0, True, False, [], {}], ids=["text", "float", "true", "false", "list", "dict"]
)
def test_a_forged_from_run_id_is_refused(value: object) -> None:
    """HD1 S1: 정수 아닌 fromRunId(bool 도 — 조건 ①)는 그대로 싣지 않고 CarrierRefused."""
    from esgapi.core.flows.carriers import CarrierRefused

    with pytest.raises(CarrierRefused, match="fromRunId 가 정수 실행 id 가 아니다"):
        s1_rewrite({"retry": {"fromRunId": value, "pages": [1]}})


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ({"retry": {"fromRunId": 7, "pages": [1]}}, {"retry": {"fromRunId": 70, "pages": [1]}}),
        ({"retry": {"fromRunId": None}}, {"retry": {"fromRunId": None}}),
        ({"retry": {"pages": [1]}}, {"retry": {"pages": [1]}}),
        ({"retry": ["fromRunId"]}, {"retry": ["fromRunId"]}),
        ({}, {}),
    ],
    ids=["int", "none", "no_place", "not_a_dict", "no_retry"],
)
def test_a_good_or_absent_from_run_id_keeps_its_way(given: dict[str, object], expected: dict[str, object]) -> None:
    """HD1 S1 조건 ②: int 는 지도, None·자리 없음·목록 아님 갈래는 BASE 그대로."""
    assert s1_rewrite(given) == expected


def test_a_bundle_with_a_text_from_run_id_is_refused_with_no_writes(
    tmp_path: Path, client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HD1 S1: 손으로 고친 묶음(options retry.fromRunId 가 글자) — 넣기가 거절(종료 1)하고 B 에 실행 0."""
    import json
    import zipfile

    a, b = world.company_a, world.company_b
    _first, retry = a_pair(client, world, monkeypatch)
    export(tmp_path, a, "--runs", str(retry), name="good.zip")
    with zipfile.ZipFile(tmp_path / "good.zip") as source, zipfile.ZipFile(tmp_path / "bundle.zip", "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "bundle.json":
                header = json.loads(data)
                for row in header["rows"]["run_runs"]:
                    if row["oldId"] == retry:
                        row["options"]["retry"]["fromRunId"] = str(row["options"]["retry"]["fromRunId"])
                data = json.dumps(header, ensure_ascii=False).encode()
            target.writestr(info.filename, data)
    before = run_selectors.run_page(company_id=b, module=None, status=None, document_id=None, limit=1, offset=0).count
    with pytest.raises(CommandError, match="fromRunId 가 정수 실행 id 가 아니다") as caught:
        imported(tmp_path, b, a_user(b))
    assert caught.value.returncode == 1
    after = run_selectors.run_page(company_id=b, module=None, status=None, document_id=None, limit=1, offset=0).count
    assert after == before == 0
