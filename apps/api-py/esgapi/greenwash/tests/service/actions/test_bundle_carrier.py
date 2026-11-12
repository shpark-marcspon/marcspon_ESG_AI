"""그린워싱의 실행 묶음 carrier(RX1b ② — service/actions/bundle.py · apps.py 등록)를 진짜 DB·가짜 저장소·전역 등록부
(REGISTRY·CARRIERS — apps.py 가 단 것)로 잰다. 명령 export_runs·import_runs 를 이름으로 부른다(runbundle import 0).

    T1  검토 confirmed·표시 adopted/excluded·고침 셋 → B 에서 find_review·mark_rows·mark_tallies 같음, 사람 = --user,
        때 그대로, 표 T 시각(created_at·updated_at)도 그대로
    T2  저장 판 실행 둘(같은 판) → B 에 새 판 하나(다음 v<n>, 적용 안 함, 칸 바이트 같음 — 판정 sha 그대로,
        criteria.version = 새 이름), 두 실행 versions 의 aiSettingId·aiSetting = 새 판, 그 판을 B 에서 적용해 지은
        versions 와 같음(sha 셋이 맞음), 운영 관리자 AI 설정 칸 = 새 판. 기본 판 실행은 None·DEFAULT_TITLE 그대로. 넣는
        동안 B 의 모델 원천이 A 와 달라도 판 모델 설정 바이트 == A(받기를 다시 거치지 않음 — Q13)
    T6  carrier id_fields() == ★b 고정 표, 고정 표의 흐름 == REGISTRY 의 그린워싱 흐름 전부
    T7  끼움(BINDINGS)이 있는 모듈 넷이 모두 CARRIERS 에 있다
    r1  받는 회사에 같은 실행의 검토가 이미 있으면 carrier 의 넣기가 거절(쓰기 0 — 덮지 않는다, 감독 8e 조건 ②)
    r2  A 의 판 criteria.version 이 판 이름과 다르면(★l 어긋남) 내보내기 거절(종료 1·파일 0)
    B1~B5(GCB1) 재판단 실행 둘·근거 고침 → 재판단 실행만 골라 내보냄(닫힘이 원 실행을 끔) → B 의 기준 판단·count·
        근거 고침·재판단 칸이 새 id 로 같음 · fromRunId 자리 셋만 새 id(그 밖 바이트 같음) ·
        colab judge 단계 data 그대로 · 원 실행만 고르면 거절(종료 1·파일 0) · 꾸민 재판단 칸은 쓰기 앞 거절
    AST 모듈 넷의 service/actions/bundle.py 는 자기 모듈 models 를 import 하지 않는다
★ 회사·사람·문서·숫자는 전부 지어낸 것이다(synthetic). 공급사 호출 0.
"""

import ast
import re
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.core.management import CommandError, call_command

from esgapi.core.flows.binding import BINDINGS
from esgapi.core.flows.carriers import CARRIERS, CarrierRefused, IdMap, UnknownId
from esgapi.core.flows.registry import REGISTRY
from esgapi.core.service.services import documents as document_services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.greenwash.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.greenwash.service.actions import review as review_actions
from esgapi.greenwash.service.selectors import ai_settings as setting_selectors
from esgapi.greenwash.service.selectors import review as review_selectors
from esgapi.greenwash.service.services import ai_settings as setting_services
from esgapi.greenwash.service.services import review as review_services
from esgapi.greenwash.tests.service import seed
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.services import bundle as run_bundle_services
from esgapi.user.service.services.user import create_customer_user
from esgapi.user.service.utils.login import UserCreated
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db(transaction=True)

ESGAPI = Path(__file__).resolve().parents[4]
OPTIONS: dict[str, Any] = {"parts": {"ceo": [1], "company": [2], "climate": [3, 4]}}
WHEN = datetime(2026, 9, 2, 3, 4, 5, tzinfo=UTC)
EARLIER = datetime(2026, 9, 1, 1, 2, 3, tzinfo=UTC)
PDF = b"%PDF-1.4 gasang greenwash report"
FIXED: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {
    # ★b 고정 표(보고 band-reports/RX1b.md) — 그 흐름의 실행에서 묶음이 옮기는 id·판 이름 자리
    ("greenwash", "greenwash.colab@E0"): {
        "versions": ("aiSettingId", "aiSetting"),
        "greenwash_ai_settings": ("oldId",),
        "greenwash_reviews": ("runOldId",),
        "greenwash_review_marks": ("runOldId", "evidence_basis_run_id", "rejudge_run_ids[]"),
    },
    ("greenwash", "greenwash.rewrite@R1"): {},  # 끼움 없음 — 실행이 생길 길 0(★h)
    # 재판단(GRJ1): versions 는 원 실행의 것을 베끼므로 판 id 자리가 E0 와 같다. 검토·표시 행은 원 실행에 붙는다.
    # 원 실행 id fromRunId 는 자리 셋(GCB1)
    ("greenwash", "greenwash.rejudge@E0"): {
        "versions": ("aiSettingId", "aiSetting"),
        "options": ("fromRunId",),
        "greenwash.rejudge@1": ("fromRunId",),
        "step:judge": ("results[].fromRunId",),
    },
    # 2차 엔진(GE1b ③): versions 는 판 열쇠(sha·경로·판 번호)뿐이라 옮길 id 0 · 산출물 표는 묶음에 없음(B3)
    ("greenwash", "greenwash.engine@G1"): {},
}


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)


def a_user(company_id: int, username: str) -> int:
    made = create_customer_user(
        actor_kind="admin",
        company_id=company_id,
        username=username,
        name=f"가상 {username}",
        password="Gasang-Pw-2026!",
    )
    assert isinstance(made, UserCreated)
    return made.user_id


def a_document(storage: FakeStorage, company_id: int) -> int:
    key = f"companies/{company_id}/documents/00000000-0000-4000-8000-00000000g001/original"
    document_id = document_services.import_document(
        company_id=company_id,
        uploaded_by="1",
        storage_key=key,
        file_name=seed.FILE_NAME,
        size_bytes=len(PDF),
        sha256=None,
        status="uploaded",
        uploaded_at=EARLIER,
        report_year=2025,
        previous_document_id=None,
        page_count=4,
        has_text=True,
    )
    document_services.set_imported_etag(company_id=company_id, document_id=document_id, etag=storage.put(key, PDF))
    return document_id


def a_setting(company_id: int, user: int, *, title: str = "가상 판", apply: bool = True) -> int:
    made = setting_services.create_setting(
        company_id=company_id, created_by_user_id=user, title=title, memo="가상 메모"
    )
    assert isinstance(made, setting_services.Created), made
    if apply:
        applied = setting_services.apply_setting(company_id=company_id, setting_id=made.id, now=WHEN)
        assert isinstance(applied, setting_services.Applied)
    return made.id


def versions_now(company_id: int) -> dict[str, object]:
    return BINDINGS.get(colab.FLOW_ID).versions_with(OPTIONS, company_id=company_id)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]


def a_run(
    company_id: int,
    user: int,
    document: int,
    versions: dict[str, object],
    *,
    judge_data: dict[str, object] | None = None,
) -> int:
    run_id = run_bundle_services.insert_run(
        company_id=company_id,
        fields={
            "document_id": document,
            "module": "greenwash",
            "flow_id": colab.FLOW_ID,
            "options": OPTIONS,
            "versions": versions,
            "status": "done",
            "created_by_user_id": user,
            "started_at": EARLIER,
            "finished_at": WHEN,
        },
    )
    run_bundle_services.insert_steps(
        company_id=company_id,
        run_id=run_id,
        steps=[
            {
                "name": name,
                "position": i,
                "status": "done",
                "data": judge_data if judge_data is not None and name == "judge" else {"pages": 1},
                "partial": None,
                "done": 1,
                "total": 1,
            }
            for i, name in enumerate(colab.FLOW.steps)
        ],
    )
    body = seed.example("result-normal")
    run_bundle_services.insert_results(
        company_id=company_id,
        run_id=run_id,
        results=[{"position": 0, "schema_version": body["schemaVersion"], "body": body}],
    )
    return run_id


def a_review(company_id: int, run_id: int, user: int) -> None:
    review_services.create_review(company_id=company_id, run_id=run_id)
    review_services.write_marks(
        company_id=company_id,
        run_id=run_id,
        inserts={
            0: {"decision": "adopted"},
            1: {"edited_level": "Low", "level_edited_at": EARLIER, "level_edited_by_user_id": user},
            2: {
                "decision": "excluded",
                "exclude_reason": "가상 근거 있음",
                "edited_reason_bullets": ["가상 사유 하나"],
                "reasons_edited_at": EARLIER,
                "reasons_edited_by_user_id": user,
                "edited_fix_paragraph": "가상 수정 방향",
                "fix_edited_at": WHEN,
                "fix_edited_by_user_id": user,
            },
        },
        updates={},
    )
    review_services.set_state(
        company_id=company_id, run_id=run_id, state="confirmed", confirmed_at=WHEN, confirmed_by_user_id=user
    )


def round_trip(tmp_path: Path, a: int, runs: list[int], b: int, user_b: int) -> dict[int, int]:
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
        str(user_b),
        "--orphans-out",
        str(tmp_path / "o.txt"),
        stdout=printed,
    )
    return {int(old): int(new) for old, new in re.findall(r"실행 (\d+) → (\d+)", printed.getvalue())}


def strip(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{k: v for k, v in row.items() if k != "run_id"} for row in rows]


def without_people(rows: dict[int, review_selectors.MarkRow]) -> dict[int, tuple[object, ...]]:
    return {
        index: (
            r.decision,
            r.exclude_reason,
            r.edited_level,
            r.level_edited_at,
            r.edited_reason_bullets,
            r.reasons_edited_at,
            r.edited_fix_paragraph,
            r.fix_edited_at,
        )
        for index, r in rows.items()
    }


def test_reviews_marks_and_edits_come_back_with_the_importer_as_the_person(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """T1."""
    a, b = companies
    user_a, user_b = a_user(a, "gasang-gw-a"), a_user(b, "gasang-gw-b")
    document = a_document(storage, a)
    a_setting(a, user_a)
    first, second = a_run(a, user_a, document, versions_now(a)), a_run(a, user_a, document, versions_now(a))
    a_review(a, first, user_a)
    runs = round_trip(tmp_path, a, [first, second], b, user_b)
    new = runs[first]
    review_a, review_b = (
        review_selectors.find_review(company_id=a, run_id=first),
        review_selectors.find_review(company_id=b, run_id=new),
    )
    assert review_a is not None and review_b is not None
    assert (review_b.state, review_b.confirmed_at, review_b.confirmed_by_user_id) == ("confirmed", WHEN, user_b)
    marks_a, marks_b = (
        review_selectors.mark_rows(company_id=a, run_id=first),
        review_selectors.mark_rows(company_id=b, run_id=new),
    )
    assert without_people(marks_b) == without_people(marks_a)
    people = {
        (i, r.level_edited_by_user_id, r.reasons_edited_by_user_id, r.fix_edited_by_user_id) for i, r in marks_b.items()
    }
    assert people == {(0, None, None, None), (1, user_b, None, None), (2, None, user_b, user_b)}
    tally_a = review_selectors.mark_tallies(company_id=a, run_ids=[first])[first]
    assert review_selectors.mark_tallies(company_id=b, run_ids=[new]) == {new: tally_a}
    assert review_selectors.find_review(company_id=b, run_id=runs[second]) is None  # 검토 없는 실행은 없음 그대로
    rows_a = review_selectors.bundle_review_rows(company_id=a, run_ids=[first])
    rows_b = review_selectors.bundle_review_rows(company_id=b, run_ids=[new])
    assert strip(rows_b.reviews) == strip(rows_a.reviews)  # 표 T 시각(created_at·updated_at)까지
    assert strip(rows_b.marks) == strip(rows_a.marks)


def test_a_saved_setting_comes_back_once_as_a_new_unapplied_setting(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """T2(그린워싱 몫)."""
    a, b = companies
    user_a, user_b = a_user(a, "gasang-gw-a"), a_user(b, "gasang-gw-b")
    document = a_document(storage, a)
    setting_a = a_setting(a, user_a)
    saved = versions_now(a)
    assert saved["aiSettingId"] == setting_a and saved["aiSetting"] == "v1"  # ★d: 판 이름 = criteria.version
    first, second = a_run(a, user_a, document, saved), a_run(a, user_a, document, saved)
    setting_services.apply_setting(company_id=a, setting_id=None, now=WHEN)
    default = versions_now(a)
    # ★d: 기본 판 — 그린워싱은 aiSetting = 기본 기준표의 판(criteria.version, G5), DEFAULT_TITLE 이 아니다
    assert (default["aiSettingId"], default["aiSetting"]) == (None, default_criteria()["version"])
    assert default_criteria()["version"] != DEFAULT_TITLE
    third = a_run(a, user_a, document, default)
    old_style = {k: v for k, v in saved.items() if k != "aiSettingId"}  # ★d: aiSettingId 없는 옛 실행(기준표 판 이름)
    fourth = a_run(a, user_a, document, old_style)
    for title in ("가상 B 판 하나", "가상 B 판 둘"):  # B 의 순번이 A 와 어긋나게(B 에 v1·v2 가 있다)
        a_setting(b, user_b, title=title, apply=False)
    applied_before = setting_selectors.ai_setting_page(company_id=b, limit=10, offset=0).applied_id
    with monkeypatch.context() as patched:  # Q13: B 의 모델 원천을 A 와 다르게 — 받기를 다시 거치면 거절된다
        narrower = tuple(setting_selectors.RunModelSource().steps())[:-1]  # (to_input 은 다시 받아도 같은 값이라

        def other_steps(self: setting_selectors.RunModelSource) -> object:  # 바이트가 달라질 길은 거절뿐)
            return narrower

        patched.setattr(setting_selectors.RunModelSource, "steps", other_steps)
        runs = round_trip(tmp_path, a, [first, second, third, fourth], b, user_b)
    names = setting_selectors.setting_names(b)
    assert sorted(names) == ["v1", "v2", "v3"]  # 판은 하나만 더해졌다(Qb2)
    page = setting_selectors.ai_setting_page(company_id=b, limit=10, offset=0)
    (new_head,) = [item for item in page.items if item.name == "v3"]
    assert page.applied_id == applied_before is None  # 적용 판·기본 판 그대로
    detail_a = setting_selectors.ai_setting_detail(company_id=a, setting_id=setting_a)
    detail_b = setting_selectors.ai_setting_detail(company_id=b, setting_id=new_head.id)
    assert isinstance(detail_a, setting_selectors.AiSetting) and isinstance(detail_b, setting_selectors.AiSetting)
    assert (detail_b.applied, detail_b.created_by_user_id) == (False, user_b)
    same = ("title", "memo", "model_settings", "prompts", "terms", "eval_prompt_sha256")
    assert {k: getattr(detail_b, k) for k in same} == {k: getattr(detail_a, k) for k in same}
    assert detail_b.criteria == {**detail_a.criteria, "version": "v3"}  # criteria.version 만 새 이름
    for old in (first, second):
        found = run_selectors.find_run(company_id=b, run_id=runs[old])
        assert found is not None
        assert found.versions == {**saved, "aiSettingId": new_head.id, "aiSetting": "v3"}
        detail = operator_selectors.operator_run_detail(actor_kind="admin", company_id=b, run_id=runs[old])
        assert isinstance(detail, operator_selectors.OperatorRunDetail)
        assert detail.run.ai_setting == (new_head.id, "v3")
    for old, versions in ((third, default), (fourth, old_style)):
        found = run_selectors.find_run(company_id=b, run_id=runs[old])
        assert found is not None and found.versions == versions
    applied = setting_services.apply_setting(company_id=b, setting_id=new_head.id, now=WHEN)
    assert isinstance(applied, setting_services.Applied)
    assert versions_now(b) == {**saved, "aiSettingId": new_head.id, "aiSetting": "v3"}  # sha 셋이 새 판과 맞음


def test_the_id_fields_are_the_fixed_table_and_cover_every_flow() -> None:
    """T6."""
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None
    union: dict[str, tuple[str, ...]] = {}
    for places in FIXED.values():
        union |= places
    assert dict(carrier.id_fields()) == union
    assert {flow for _module, flow in FIXED} == {flow.id for flow in REGISTRY.flows_of("greenwash")}


def test_every_module_with_a_binding_has_a_carrier() -> None:
    """T7: 끼움 있는 모듈 여섯(drafting 은 RPA1 까지 carrier 없음)의 다섯이 CARRIERS 에. 끼움 없는 모듈은 거절."""
    bound = {REGISTRY.get(flow_id).module for flow_id in BINDINGS.flow_ids()}
    assert bound == {"dataverify", "drafting", "greenwash", "inventory.scope3", "materiality", "translation"}
    assert set(CARRIERS.modules()) == bound - {"drafting"}  # RP1: drafting 은 끼움만, carrier 는 RPA1


@pytest.mark.parametrize("module", ["greenwash", "translation", "dataverify", "materiality"])
def test_a_module_carrier_does_not_import_its_own_models(module: str) -> None:
    """AST(Q11): actions 의 자기 models import 는 lint 가 안 막는다(.importlinter 무시 줄) — 이 시험이 지킨다. 모듈 넷의
    service/actions/bundle.py 가 있으면 그 파일, 없으면(데이터 검증·중대성평가 — apps.py 등록) apps.py 를 본다."""
    path = ESGAPI / module / "service" / "actions" / "bundle.py"
    if not path.exists():
        path = ESGAPI / module / "apps.py"
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names += [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        elif isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
    assert names  # 분모: 읽은 import 가 있다
    assert not [
        name for name in names if name == f"esgapi.{module}.models" or name.startswith(f"esgapi.{module}.models.")
    ]


def test_an_existing_review_of_the_same_run_is_not_overwritten(
    storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """r1: 꾸민 지도(옛 실행 → B 에 이미 검토가 있는 실행)로 carrier 의 넣기를 부르면 거절, 검토·표시 그대로."""
    _a, b = companies
    user_b = a_user(b, "gasang-gw-b")
    run_b = a_run(b, user_b, a_document(storage, b), {})
    a_review(b, run_b, user_b)
    before = (
        review_selectors.find_review(company_id=b, run_id=run_b),
        review_selectors.mark_rows(company_id=b, run_id=run_b),
    )
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None and before[0] is not None and len(before[1]) == 3  # 분모: 검토·표시가 있다
    rows: dict[str, list[dict[str, object]]] = {
        "greenwash_reviews": [
            {"runOldId": 7, "state": "pending", "confirmed_at": None, "created_at": WHEN, "updated_at": WHEN}
        ],
        "greenwash_review_marks": [],
    }
    with pytest.raises(CarrierRefused, match="이미 있다"):
        carrier.import_rows(b, user_b, rows, IdMap(run={7: run_b}, document={}, ai_setting={}))
    after = (
        review_selectors.find_review(company_id=b, run_id=run_b),
        review_selectors.mark_rows(company_id=b, run_id=run_b),
    )
    assert after == before


def test_a_setting_whose_criteria_version_is_not_its_name_is_not_exported(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """r2(★l 지킴): 판의 criteria.version ≠ 이름(주인 역할로 꾸민 행)이면 그 판을 쓴 실행의 내보내기는 거절."""
    a, _b = companies
    user_a = a_user(a, "gasang-gw-a")
    setting = a_setting(a, user_a)
    run_id = a_run(a, user_a, a_document(storage, a), versions_now(a))
    row = GreenwashAiSettingRow.for_company(a).get(id=setting)
    GreenwashAiSettingRow.for_company(a).filter(id=setting).update(criteria={**row.criteria, "version": "v9"})
    out = tmp_path / "bundle.zip"
    with pytest.raises(CommandError) as caught:
        call_command(
            "export_runs",
            "--company",
            str(a),
            "--runs",
            str(run_id),
            "--out",
            str(out),
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert caught.value.returncode == 1 and "criteria.version" in str(caught.value)
    assert not out.exists()


# ── HD1 S3(405 노트 s3): 꾸민 묶음의 검토·표시 겹침 — 그린워싱 8e 허락(더하기만) ─────────────────


def s3_review(old: int) -> dict[str, object]:
    return {"runOldId": old, "state": "pending", "confirmed_at": None, "created_at": WHEN, "updated_at": WHEN}


def s3_mark(old: int, index: object) -> dict[str, object]:
    return {
        "runOldId": old,
        "item_index": index,
        "decision": "adopted",
        "exclude_reason": None,
        "edited_level": None,
        "level_edited_at": None,
        "edited_reason_bullets": None,
        "reasons_edited_at": None,
        "edited_fix_paragraph": None,
        "fix_edited_at": None,
        "evidence_removed": None,
        "evidence_added": None,
        "evidence_edited_at": None,
        "evidence_basis_run_id": None,
        "rejudge_run_ids": None,
        "created_at": WHEN,
        "updated_at": WHEN,
    }


S3_CASES: dict[str, tuple[list[dict[str, object]], list[dict[str, object]], str]] = {
    "two_reviews": ([s3_review(7), s3_review(7)], [], "검토가 같은 실행에 둘 이상"),
    "two_marks": ([s3_review(7)], [s3_mark(7, 0), s3_mark(7, 0)], "표시가 같은 실행·항목에 둘 이상"),
    "mark_without_review": ([s3_review(7)], [s3_mark(8, 0)], "표시가 검토 없는 실행을 가리킨다"),
    "index_list": ([s3_review(7)], [s3_mark(7, [0])], "item_index 가 정수가 아니다"),
    "index_bool": ([s3_review(7)], [s3_mark(7, True)], "item_index 가 정수가 아니다"),
    "index_text": ([s3_review(7)], [s3_mark(7, "0")], "item_index 가 정수가 아니다"),
}


@pytest.mark.parametrize("case", list(S3_CASES))
def test_a_forged_review_bundle_is_refused_before_writing(
    storage: FakeStorage, companies: tuple[int, int], case: str
) -> None:
    """HD1 S3: 갈래마다 CarrierRefused(IntegrityError·TypeError 날것 0)이고 검토·표시 쓰기 0(받은 rows 만 본다)."""
    _a, b = companies
    user_b = a_user(b, "gasang-gw-b")
    document = a_document(storage, b)
    runs = {7: a_run(b, user_b, document, {}), 8: a_run(b, user_b, document, {})}
    reviews, marks, match = S3_CASES[case]
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None
    rows: dict[str, list[dict[str, object]]] = {"greenwash_reviews": reviews, "greenwash_review_marks": marks}
    with pytest.raises(CarrierRefused, match=match):
        carrier.import_rows(b, user_b, rows, IdMap(run=runs, document={}, ai_setting={}))
    written = review_selectors.bundle_review_rows(company_id=b, run_ids=runs.values())
    assert (written.reviews, written.marks) == ([], [])


def test_a_good_review_bundle_still_goes_in(storage: FakeStorage, companies: tuple[int, int]) -> None:
    """HD1 S3 조건 ②: 겹침 없는 정상 꼴(검토 둘·표시 각 항목 하나)은 그대로 넣힌다."""
    _a, b = companies
    user_b = a_user(b, "gasang-gw-b")
    document = a_document(storage, b)
    runs = {7: a_run(b, user_b, document, {}), 8: a_run(b, user_b, document, {})}
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None
    rows: dict[str, list[dict[str, object]]] = {
        "greenwash_reviews": [s3_review(7), s3_review(8)],
        "greenwash_review_marks": [s3_mark(7, 0), s3_mark(7, 1), s3_mark(8, 0)],
    }
    carrier.import_rows(b, user_b, rows, IdMap(run=runs, document={}, ai_setting={}))
    written = review_selectors.bundle_review_rows(company_id=b, run_ids=runs.values())
    assert len(written.reviews) == 2 and len(written.marks) == 3


# ── GCB1: 재판단 실행과 근거 고침(MARC-ISSUE-616) ─────────────────────────────────────────────


REJUDGE_FLOW = "greenwash.rejudge@E0"
PIECE: dict[str, object] = {"text": "지어낸 근거 조각 — 산정 범위는 가상 사업장 둘이다", "page": 2}
JUDGE_DATA: dict[str, object] = {"results": [{"sentence": "가상 문장", "level": "Mid"}]}  # colab judge 꼴의 지어낸 data


def a_colab_run(company_id: int, user: int, document: int, versions: dict[str, object]) -> int:
    """a_run 과 같고 judge 단계 data 만 results 꼴(재판단 judge 와 같은 단계 이름 — rewrite 가 건드리지 않아야)."""
    return a_run(company_id, user, document, versions, judge_data=JUDGE_DATA)


def a_rejudge(
    company_id: int,
    user: int,
    from_run: int,
    index: int,
    level: str,
    versions: dict[str, object],
    *,
    status: str = "done",
    prompt_version: str | None = None,
) -> tuple[int, dict[str, object]]:
    """원 실행 문장 하나의 done 재판단 실행(문서 없음) — options·결과·judge 단계 data 에 fromRunId. prompt_version 을
    주면 옵션에 promptVersion 칸(GRS1)을 싣는다 — 없으면 그 칸 앞의 옛 옵션."""
    options: dict[str, object] = {
        "fromRunId": from_run,
        "itemIndex": index,
        "sentence": "가상 문장 하나",
        "lowOnly": False,
        "kept": ["가상 칩"],
        "added": [PIECE],
        "maxCharsPerChunk": 450,
        "maxCharsEvidenceTotal": 1600,
    }
    if prompt_version is not None:
        options["promptVersion"] = prompt_version
    body: dict[str, object] = {
        "schemaVersion": "greenwash.rejudge@1",
        "fromRunId": from_run,
        "itemIndex": index,
        "sentence": "가상 문장 하나",
        "kept": ["가상 칩"],
        "added": [PIECE],
        "outcome": "judged",
        "item": {
            "level": level,
            "riskTags": ["가상 태그"],
            "confirmedInEvidence": ["가상 칩"],
            "missingFields": [],
            "reasonBullets": [f"가상 사유 {level}"],
            "fixParagraph": "가상 수정 방향",
            "evidencePages": [2],
            "evidenceInternal": "",
        },
    }
    run_id = run_bundle_services.insert_run(
        company_id=company_id,
        fields={
            "document_id": None,
            "module": "greenwash",
            "flow_id": REJUDGE_FLOW,
            "options": options,
            "versions": versions,
            "status": status,
            "created_by_user_id": user,
            "started_at": EARLIER,
            "finished_at": WHEN if status in ("done", "failed") else None,
        },
    )
    if status != "done":
        return run_id, body
    run_bundle_services.insert_steps(
        company_id=company_id,
        run_id=run_id,
        steps=[
            {
                "name": "judge",
                "position": 0,
                "status": "done",
                "data": {"results": [body]},
                "partial": None,
                "done": 1,
                "total": 1,
            }
        ],
    )
    run_bundle_services.insert_results(
        company_id=company_id,
        run_id=run_id,
        results=[{"position": 0, "schema_version": body["schemaVersion"], "body": body}],
    )
    return run_id, body


def rejudged_world(storage: FakeStorage, a: int, user_a: int) -> tuple[int, int, int]:
    """원 실행(문장 넷) + 문장 0 의 done 재판단 둘(둘째가 기준) + 근거 고침(기준 = 둘째). (원, 첫째, 둘째)."""
    a_setting(a, user_a)
    versions = versions_now(a)
    original = a_colab_run(a, user_a, a_document(storage, a), versions)
    a_review(a, original, user_a)
    first, _ = a_rejudge(a, user_a, original, 0, "Mid", versions)
    second, _ = a_rejudge(a, user_a, original, 0, "Low", versions, prompt_version="2025-07-01-v0")  # 새 칸(GRS1)
    for rejudge in (first, second):
        review_services.append_rejudge(company_id=a, run_id=original, item_index=0, rejudge_run_id=rejudge)
    review_services.write_marks(
        company_id=a,
        run_id=original,
        inserts={},
        updates={
            0: {
                "evidence_removed": [0],
                "evidence_added": [PIECE],
                "evidence_edited_at": EARLIER,
                "evidence_edited_by_user_id": user_a,
                "evidence_basis_run_id": second,
            }
        },
    )
    return original, first, second


def judged(company_id: int, run_id: int) -> tuple[list[review_actions.Basis], dict[int, review_actions.RejudgeLine]]:
    found = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body: dict[str, Any] = next(r.body for r in found if r.schema_version == "greenwash.result@1")  # pyright: ignore[reportAssignmentType]
    items: list[dict[str, Any]] = body["items"]
    return review_actions.judgments(
        company_id, run_id, items, review_selectors.mark_rows(company_id=company_id, run_id=run_id)
    )


def test_rejudge_runs_and_evidence_edits_come_back_on_the_new_ids(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """B1: 재판단 실행 둘만 골라도 닫힘이 원 실행을 끈다. B 의 기준 판단·재판단 줄·근거 고침·재판단 칸이
    새 id 로 같다."""
    a, b = companies
    user_a, user_b = a_user(a, "gasang-gw-a"), a_user(b, "gasang-gw-b")
    original, first, second = rejudged_world(storage, a, user_a)
    runs = round_trip(tmp_path, a, [first, second], b, user_b)
    assert set(runs) == {original, first, second}  # 분모: 닫힘이 원 실행을 더했다
    new = runs[original]
    row_a = review_selectors.mark_rows(company_id=a, run_id=original)[0]
    row_b = review_selectors.mark_rows(company_id=b, run_id=new)[0]
    assert row_b.rejudge_run_ids == [runs[first], runs[second]]
    assert row_b.evidence_basis_run_id == runs[second]
    assert (row_b.evidence_removed, row_b.evidence_added, row_b.evidence_edited_at) == ([0], [PIECE], EARLIER)
    assert (row_a.evidence_edited_by_user_id, row_b.evidence_edited_by_user_id) == (user_a, user_b)
    bases_a, lines_a = judged(a, original)
    bases_b, lines_b = judged(b, new)
    assert (lines_a[0].count, lines_a[0].status) == (lines_b[0].count, lines_b[0].status) == (2, "done")
    assert bases_a[0].run_id == second and bases_b[0].run_id == runs[second]
    assert bases_b[0].item == bases_a[0].item and bases_b[0].item["level"] == "Low"  # 기준 = 둘째(Low)
    assert (bases_b[0].outcome, bases_b[0].added) == (bases_a[0].outcome, bases_a[0].added)
    assert [basis.item for basis in bases_b[1:]] == [basis.item for basis in bases_a[1:]]  # 재판단 없는 문장 그대로
    assert review_actions.evidence_now(row_b, bases_b[0]) == ([0], [PIECE])  # 기준이 같아 지운 칩이 살아 있다
    assert strip(review_selectors.bundle_review_rows(company_id=b, run_ids=[new]).marks) != []
    tally_b = review_selectors.mark_tallies(company_id=b, run_ids=[new])[new]
    assert tally_b.rejudges == {0: [runs[first], runs[second]]}


def steps_of(company_id: int, run_id: int) -> list[tuple[str, Any]]:
    return [(step.name, step.data) for step in run_selectors.step_rows(company_id=company_id, run_id=run_id)]


def test_only_the_from_run_id_places_are_rewritten(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """B2·B3: 재판단 실행의 options·결과·judge 단계 data 는 fromRunId 만 새 원 실행 id, 그 밖 같음. colab 실행의 judge
    단계 data(같은 이름)는 그대로."""
    a, b = companies
    user_a, user_b = a_user(a, "gasang-gw-a"), a_user(b, "gasang-gw-b")
    original, first, second = rejudged_world(storage, a, user_a)
    runs = round_trip(tmp_path, a, [original, first, second], b, user_b)
    new_original = runs[original]
    for old in (first, second):
        run_a = run_selectors.find_run(company_id=a, run_id=old)
        run_b = run_selectors.find_run(company_id=b, run_id=runs[old])
        assert run_a is not None and run_b is not None
        assert (run_a.options["fromRunId"], run_b.options["fromRunId"]) == (original, new_original)
        assert run_b.options == {**run_a.options, "fromRunId": new_original}
        # GRS1: 옛 옵션(first — promptVersion 없음)도 새 칸 실린 옵션(second)도 그대로 운반된다
        assert run_b.options.get("promptVersion") == (None if old == first else "2025-07-01-v0")
        (result_a,) = run_selectors.run_results(company_id=a, run_id=old)
        (result_b,) = run_selectors.run_results(company_id=b, run_id=runs[old])
        body_a: dict[str, Any] = result_a.body  # pyright: ignore[reportAssignmentType]
        assert result_b.body == {**body_a, "fromRunId": new_original}
        (step_a,) = steps_of(a, old)
        (step_b,) = steps_of(b, runs[old])
        assert step_b == (step_a[0], {"results": [{**step_a[1]["results"][0], "fromRunId": new_original}]})
    steps_a = steps_of(a, original)
    steps_b = steps_of(b, new_original)
    assert steps_b == steps_a and ("judge", JUDGE_DATA) in steps_b  # B3: colab judge data 바이트 그대로


def test_the_original_run_alone_is_not_exported(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """B4(감독 §8 Q-B1 (가)): 원 실행만 고르면 표시가 묶음 밖 done 재판단 실행을 가리켜 거절 — 종료 1, 글에 원·빠진 id,
    파일 0."""
    a, _b = companies
    user_a = a_user(a, "gasang-gw-a")
    original, first, second = rejudged_world(storage, a, user_a)
    for picked, missing in (([original], [first, second]), ([original, first], [second])):
        out = tmp_path / f"bundle-{len(picked)}.zip"
        with pytest.raises(CommandError) as caught:
            call_command(
                "export_runs",
                "--company",
                str(a),
                "--runs",
                ",".join(map(str, picked)),
                "--out",
                str(out),
                stdout=StringIO(),
                stderr=StringIO(),
            )
        assert caught.value.returncode == 1
        assert f"실행 {original} 의 재판단 실행 {missing} 이 묶음에 없다" in str(caught.value)
        assert not out.exists()


def test_unfinished_rejudge_ids_are_left_out_of_a_window_export(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """B4b(감독 §8 Q-B1 (나)): 문장 0 에 실패 재판단, 문장 1 에 도는 중 재판단이 더 있어도 창 내보내기는 지나간다(done
    만 고름). 그 id 는 내보낼 때 목록에서 빠지고(문장 1 은 null), 들인 뒤 done 재판단의 count·기준 판단은 A 와 같다."""
    a, b = companies
    user_a, user_b = a_user(a, "gasang-gw-a"), a_user(b, "gasang-gw-b")
    original, first, second = rejudged_world(storage, a, user_a)
    versions = versions_now(a)
    failed, _ = a_rejudge(a, user_a, original, 0, "High", versions, status="failed")
    running, _ = a_rejudge(a, user_a, original, 1, "High", versions, status="processing")
    review_services.append_rejudge(company_id=a, run_id=original, item_index=0, rejudge_run_id=failed)
    review_services.append_rejudge(company_id=a, run_id=original, item_index=1, rejudge_run_id=running)
    today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Seoul")).date()
    out = tmp_path / "window.zip"
    call_command(
        "export_runs",
        "--company",
        str(a),
        "--module",
        "greenwash",
        "--from",
        str(today - timedelta(days=1)),
        "--to",
        str(today + timedelta(days=1)),
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
        str(user_b),
        "--orphans-out",
        str(tmp_path / "o.txt"),
        stdout=printed,
    )
    runs = {int(old): int(new) for old, new in re.findall(r"실행 (\d+) → (\d+)", printed.getvalue())}
    assert set(runs) == {original, first, second}  # 분모: 끝나지 않은 재판단 둘은 실리지 않았다
    new = runs[original]
    marks_b = review_selectors.mark_rows(company_id=b, run_id=new)
    assert marks_b[0].rejudge_run_ids == [runs[first], runs[second]]  # 실패 id 는 빠짐
    assert marks_b[1].rejudge_run_ids is None  # 도는 중 id 하나뿐이라 null
    assert marks_b[0].evidence_basis_run_id == runs[second]
    bases_a, lines_a = judged(a, original)
    bases_b, lines_b = judged(b, new)
    assert lines_a[0] == review_actions.RejudgeLine(status="failed", count=2)  # A 의 마지막 상태 = 실패
    assert lines_b[0] == review_actions.RejudgeLine(status="done", count=2)  # B: 앞 done 기준 — count 같음
    assert 1 in lines_a and 1 not in lines_b
    assert bases_b[0].item == bases_a[0].item and bases_b[0].run_id == runs[second]
    assert [basis.item for basis in bases_b] == [basis.item for basis in bases_a]


REJUDGE_CASES: dict[str, tuple[dict[str, object], str]] = {
    "unknown_id": ({"rejudge_run_ids": [99]}, ""),  # 지도 밖 — UnknownId
    "text": ({"rejudge_run_ids": ["8"]}, "양의 정수 목록이 아니다"),
    "bool": ({"rejudge_run_ids": [True]}, "양의 정수 목록이 아니다"),
    "zero": ({"rejudge_run_ids": [0]}, "양의 정수 목록이 아니다"),
    "not_list": ({"rejudge_run_ids": 8}, "양의 정수 목록이 아니다"),
    "overlap": ({"rejudge_run_ids": [8, 8]}, "같은 실행이 둘 이상"),
    "basis_outside": ({"rejudge_run_ids": [8], "evidence_basis_run_id": 7}, "재판단 실행이 아니다"),
    "basis_without_list": ({"evidence_basis_run_id": 8}, "재판단 실행이 아니다"),
    "basis_text": ({"rejudge_run_ids": [8], "evidence_basis_run_id": "8"}, "재판단 실행이 아니다"),
}


@pytest.mark.parametrize("case", list(REJUDGE_CASES))
def test_a_forged_rejudge_mark_is_refused_before_writing(
    storage: FakeStorage, companies: tuple[int, int], case: str
) -> None:
    """B5: 꾸민 재판단 칸은 쓰기 앞 거절(CarrierRefused, 지도 밖은 UnknownId) — 검토·표시 쓰기 0."""
    _a, b = companies
    user_b = a_user(b, "gasang-gw-b")
    document = a_document(storage, b)
    runs = {7: a_run(b, user_b, document, {}), 8: a_run(b, user_b, document, {})}
    columns, match = REJUDGE_CASES[case]
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None
    rows: dict[str, list[dict[str, object]]] = {
        "greenwash_reviews": [s3_review(7)],
        "greenwash_review_marks": [{**s3_mark(7, 0), **columns}],
    }
    expected = UnknownId if case == "unknown_id" else CarrierRefused
    with pytest.raises(expected, match=match or None):
        carrier.import_rows(b, user_b, rows, IdMap(run=runs, document={}, ai_setting={}))
    written = review_selectors.bundle_review_rows(company_id=b, run_ids=runs.values())
    assert (written.reviews, written.marks) == ([], [])


@pytest.mark.parametrize("forged", ["5", True, None], ids=["text", "bool", "null"])
def test_a_forged_from_run_id_is_refused_by_the_rewrite(forged: object) -> None:
    """검증 R1: 꾸민 options fromRunId(글자·bool·null)는 rewrite 가 CarrierRefused 로 거절(그대로 싣지 않는다)."""
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None
    with pytest.raises(CarrierRefused, match="fromRunId 가 정수 실행 id 가 아니다"):
        carrier.rewrite(
            options={"fromRunId": forged, "itemIndex": 0},
            versions={},
            results=(),
            steps=(),
            partials=(),
            ids=IdMap(run={5: 50}, document={}, ai_setting={}),
        )


def test_a_good_rejudge_mark_goes_in_on_the_new_ids(storage: FakeStorage, companies: tuple[int, int]) -> None:
    """B5 짝: 바른 재판단 칸(목록·기준이 목록 안)은 새 id 로 들어간다."""
    _a, b = companies
    user_b = a_user(b, "gasang-gw-b")
    document = a_document(storage, b)
    runs = {7: a_run(b, user_b, document, {}), 8: a_run(b, user_b, document, {}), 9: a_run(b, user_b, document, {})}
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None
    rows: dict[str, list[dict[str, object]]] = {
        "greenwash_reviews": [s3_review(7)],
        "greenwash_review_marks": [
            {
                **s3_mark(7, 0),
                "evidence_removed": [],
                "evidence_added": [PIECE],
                "evidence_edited_at": WHEN,
                "evidence_basis_run_id": 9,
                "rejudge_run_ids": [8, 9],
            }
        ],
    }
    carrier.import_rows(b, user_b, rows, IdMap(run=runs, document={}, ai_setting={}))
    row = review_selectors.mark_rows(company_id=b, run_id=runs[7])[0]
    assert (row.rejudge_run_ids, row.evidence_basis_run_id) == ([runs[8], runs[9]], runs[9])
    assert (row.evidence_edited_at, row.evidence_edited_by_user_id) == (WHEN, user_b)


def test_the_referenced_run_is_the_from_run_id_only() -> None:
    """referenced_runs: 정수 fromRunId 만(bool·글자·없음은 ()) — colab·G1 options 에는 그 열쇠가 없다."""
    carrier = CARRIERS.get("greenwash")
    assert carrier is not None
    assert carrier.referenced_runs({"fromRunId": 5, "itemIndex": 0}) == (5,)
    assert [carrier.referenced_runs(o) for o in ({"fromRunId": True}, {"fromRunId": "5"}, OPTIONS, {})] == [()] * 4
