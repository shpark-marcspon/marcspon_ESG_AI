"""실행 묶음의 구획 표(RM1c ② — T10·T12·T13): 펼침 실행을 내보내 다른 회사로 넣고 되읽는다. 업무 층(진짜 DB·가짜
저장소). 펼침 흐름은 시험 레지스트리에만 단 `rxtest.fan@1`(제품 등록 0). ★ 값은 전부 지어낸 것이다(synthetic).
"""

import json
import zipfile
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import segment_key_fields, segment_key_sha256
from esgapi.core.service.selectors.llm_logs import rows_of_runs
from esgapi.core.service.services import llm_logs as llm_services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.calc.bundle import SEGMENTS, Refused
from esgapi.runbundle.service.actions import export, import_
from esgapi.runbundle.service.actions.export import RunIds
from esgapi.runbundle.service.actions.import_ import Imported
from esgapi.runbundle.tests import support
from esgapi.runbundle.tests.calc.test_gate_segments import FAN, FAN_ID, key
from esgapi.runbundle.tests.support import FLOW, FLOW2, MODULE, OLD, OLDER, a_customer, carriers, seed
from esgapi.runs.calc.segments import data_octets
from esgapi.runs.service.selectors.bundle import bundle_rows
from esgapi.runs.service.services import bundle as bundle_services

pytestmark = pytest.mark.django_db(transaction=True)

COUNT = 3
STEP_DATA: tuple[tuple[str, dict[str, object]], ...] = (
    ("prepare", {"count": COUNT}),
    ("spread", {"segments": []}),
    ("gather", {"results": []}),
)


def registry() -> FlowRegistry:
    found = FlowRegistry()
    for flow in (FLOW, FLOW2, FAN):
        found.register(flow)
    found.set_default(MODULE, FLOW.id)
    return found


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def fan_run(storage: FakeStorage, company: int, user: int, *, resumed_from: int | None = None) -> int:
    """done 펼침 실행 하나(구획 셋 — done 둘·failed 하나, data 열쇠 차례는 정렬 아님)."""
    document = cast("Callable[..., int]", getattr(support, "_document"))(  # noqa: B009 — support 의 틀
        storage, company, f"펼침 {resumed_from}", None, b"%PDF-1.4 gasang fan"
    )
    run_id = bundle_services.insert_run(
        company_id=company,
        fields={
            "document_id": document,
            "module": MODULE,
            "flow_id": FAN_ID,
            "options": {},
            "versions": {"flow": FAN_ID},
            "purpose": "service",
            "status": "done",
            "attempts": 1,
            "stalled_attempts": 0,
            "progress_attempt": 1,
            "created_by_user_id": user,
            "started_at": OLDER,
            "finished_at": OLD,
            "resumed_from_run_id": resumed_from,
        },
    )
    bundle_services.insert_steps(
        company_id=company,
        run_id=run_id,
        steps=[
            {"name": name, "position": position, "status": "done", "data": data, "partial": None, "done": 1, "total": 1}
            for position, (name, data) in enumerate(STEP_DATA)
        ],
    )
    rows: list[dict[str, object]] = []
    for position in range(COUNT):
        k = key(position + 1)
        failed = position == 1
        data = None if failed else {"zeta": position, "alpha": {"b": 2, "a": 1}}
        rows.append(
            {
                "step": "spread",
                "position": position,
                "kind": k.kind,
                "key": segment_key_fields(k),
                "key_sha256": segment_key_sha256(k),
                "status": "failed" if failed else "done",
                "attempts": 0 if position == 2 else 1,  # 끝 것은 옮겨 온 구획
                "data": data,
                "error_code": "step_error" if failed else None,
                "started_at": OLDER,
                "finished_at": OLD,
                "data_octets": None if data is None or position == 2 else data_octets(data),
            }
        )
    bundle_services.insert_segments(company_id=company, run_id=run_id, segments=rows)
    llm_services.insert_rows(
        company_id=company,
        rows=[
            {
                **cast("Callable[..., dict[str, object]]", getattr(support, "_log"))(  # noqa: B009
                    company, run_id, f"seg-{run_id}", "spread"
                ),
                "segment": segment_key_sha256(key(1)),
                "cost_usd": Decimal("0.00012345"),
            }
        ],
        run_map={run_id: run_id},
    )
    return run_id


def export_runs(tmp_path: Path, storage: FakeStorage, company: int, run_ids: tuple[int, ...], name: str) -> Path:
    out = tmp_path / name
    export.run(
        company_id=company,
        selection=RunIds(run_ids),
        out=out,
        app_commit="test",
        flows=registry(),
        carriers=carriers(),
        storage=storage,
    )
    return out


def import_to(tmp_path: Path, storage: FakeStorage, path: Path, company: int, user: int) -> Imported:
    return import_.run(
        path=path,
        company_id=company,
        user_id=user,
        orphans_out=tmp_path / f"orphans-{company}-{path.stem}.txt",
        flows=registry(),
        carriers=carriers(),
        storage=storage,
    )


def header_of(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        return cast("dict[str, object]", json.loads(archive.read("bundle.json")))


def rows_of(header: dict[str, object], table: str) -> list[dict[str, object]]:
    return cast("dict[str, list[dict[str, object]]]", header["rows"])[table]


def comparable(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """구획 행의 바이트 견줌 꼴(옛 실행 id 는 회사마다 다르다 — 그 밖은 같아야 한다)."""
    return [{name: value for name, value in row.items() if name != "runOldId"} for row in rows]


def rewrite(path: Path, out: Path, change: Callable[[dict[str, object]], None]) -> Path:
    """bundle.json 만 바꾼 묶음(나머지 항목 그대로)."""
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "bundle.json":
                head = cast("dict[str, object]", json.loads(data))
                change(head)
                data = json.dumps(head, ensure_ascii=False, separators=(",", ":")).encode()
            target.writestr(info, data)
    return out


# ── T10 싣기·되넣기 ───────────────────────────────────────────────────


def test_a_fanout_run_carries_its_segments_into_another_company(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    user_a, user_b = a_customer(a, "gasang-a"), a_customer(b, "gasang-b")
    source = fan_run(storage, a, user_a)
    path = export_runs(tmp_path, storage, a, (source,), "fan.zip")
    head = header_of(path)
    carried = rows_of(head, SEGMENTS)
    assert len(carried) == COUNT and cast("dict[str, int]", head["counts"])[SEGMENTS] == COUNT
    assert [row["position"] for row in carried] == list(range(COUNT))
    never = {"id", "company_id", "run_id", "lease_expires_at", "created_at", "updated_at"}
    assert not never & set(cast("dict[str, list[str]]", head["tables"])[SEGMENTS])
    assert all(not never & set(row) for row in carried)
    assert {row["runOldId"] for row in carried} == {source}

    done = import_to(tmp_path, storage, path, b, user_b)
    new = done.runs[source]
    assert new != source
    before = bundle_rows(company_id=a, run_ids=[source]).segments
    after = bundle_rows(company_id=b, run_ids=[new]).segments
    fields = ("step", "position", "kind", "key", "key_sha256", "status", "attempts", "data", "error_code")
    assert [tuple(row[f] for f in fields) for row in after] == [tuple(row[f] for f in fields) for row in before]
    assert [row["data_octets"] for row in after] == [row["data_octets"] for row in before]  # NULL 은 NULL 그대로
    assert {row["company_id"] for row in after} == {b} and {row["run_id"] for row in after} == {new}
    assert {row["lease_expires_at"] for row in after} == {None}
    assert [list(cast("dict[str, object]", row["data"])) for row in after if row["data"] is not None] == [
        ["zeta", "alpha"]
    ] * 2  # 열쇠 차례 그대로(정렬 아님)
    logs = rows_of_runs(company_id=b, run_ids=[new])
    assert [row["segment"] for row in logs] == [segment_key_sha256(key(1))]  # 호출 기록의 구획 sha 그대로


def test_a_retry_run_brings_its_previous_run_along(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """고른 다시 실행(resumed_from = done 앞 실행)의 닫힘은 앞 실행을 싣고, 넣은 쪽에서 사슬이 새 id 로 잇는다."""
    a, b = companies
    user_a, user_b = a_customer(a, "gasang-a"), a_customer(b, "gasang-b")
    previous = fan_run(storage, a, user_a)
    retried = fan_run(storage, a, user_a, resumed_from=previous)
    path = export_runs(tmp_path, storage, a, (retried,), "retry.zip")
    head = header_of(path)
    assert sorted(cast("int", row["oldId"]) for row in rows_of(head, "run_runs")) == sorted((previous, retried))
    assert sorted({cast("int", row["runOldId"]) for row in rows_of(head, SEGMENTS)}) == sorted((previous, retried))
    done = import_to(tmp_path, storage, path, b, user_b)
    runs = bundle_rows(company_id=b, run_ids=[done.runs[retried]]).runs
    assert runs[0]["resumed_from_run_id"] == done.runs[previous]
    assert len(bundle_rows(company_id=b, run_ids=[done.runs[previous]]).segments) == COUNT


# ── T12 옛 묶음 · 일부만 · 장벽 묶음 ───────────────────────────────────────


def strip_segments(head: dict[str, object], parts: tuple[str, ...] = ("tables", "rows", "counts")) -> None:
    for part in parts:
        cast("dict[str, object]", head[part]).pop(SEGMENTS)


def test_a_barrier_bundle_differs_from_the_old_shape_by_an_empty_segment_table_only(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = export_runs(tmp_path, storage, a, (world.runs["r2"], world.runs["r4"]), "barrier.zip")
    head = header_of(path)
    assert rows_of(head, SEGMENTS) == [] and cast("dict[str, int]", head["counts"])[SEGMENTS] == 0
    assert cast("dict[str, list[str]]", head["tables"])[SEGMENTS]  # 칸 목록은 싣는다(받는 쪽 문이 본다)
    old = rewrite(path, tmp_path / "old.zip", strip_segments)  # 옛 꼴 = 표 여섯(다른 칸은 하나도 다르지 않다)
    done = import_to(tmp_path, storage, old, b, a_customer(b, "gasang-b"))
    assert len(done.runs) == len(rows_of(head, "run_runs"))
    assert SEGMENTS not in done.counts  # 옛 묶음은 구획 표를 세지 않는다


@pytest.mark.parametrize("part", ["tables", "rows", "counts"])
def test_a_bundle_missing_the_segment_table_in_one_part_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], part: str
) -> None:
    a, b = companies
    source = fan_run(storage, a, a_customer(a, "gasang-a"))
    path = export_runs(tmp_path, storage, a, (source,), "fan.zip")
    broken = rewrite(path, tmp_path / f"broken-{part}.zip", lambda head: strip_segments(head, (part,)))
    with pytest.raises(Refused, match="일부"):
        import_to(tmp_path, storage, broken, b, a_customer(b, "gasang-b"))
    assert bundle_rows(company_id=b, run_ids=[source]).runs == []


def test_a_tampered_segment_row_is_refused_with_nothing_written(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    source = fan_run(storage, a, a_customer(a, "gasang-a"))
    path = export_runs(tmp_path, storage, a, (source,), "fan.zip")

    def tamper(head: dict[str, object]) -> None:
        rows_of(head, SEGMENTS)[0]["key_sha256"] = "0" * 64

    broken = rewrite(path, tmp_path / "tampered.zip", tamper)
    user_b = a_customer(b, "gasang-b")
    with pytest.raises(Refused, match="다시 센"):
        import_to(tmp_path, storage, broken, b, user_b)
    assert not any(f"companies/{b}/" in name for name in storage.objects)  # 저장소 쓰기는 문 뒤 — 거절이면 0


# ── T13 되내보내기 ─────────────────────────────────────────────────────


def test_an_imported_run_exports_the_same_segment_bytes(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    source = fan_run(storage, a, a_customer(a, "gasang-a"))
    first = export_runs(tmp_path, storage, a, (source,), "first.zip")
    done = import_to(tmp_path, storage, first, b, a_customer(b, "gasang-b"))
    second = export_runs(tmp_path, storage, b, (done.runs[source],), "second.zip")
    one, two = rows_of(header_of(first), SEGMENTS), rows_of(header_of(second), SEGMENTS)
    assert text(one) == text(two)


def text(rows: list[dict[str, object]]) -> str:
    return json.dumps(comparable(rows), ensure_ascii=False, separators=(",", ":"))
