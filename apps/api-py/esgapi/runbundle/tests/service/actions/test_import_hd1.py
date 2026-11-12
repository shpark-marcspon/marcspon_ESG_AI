"""넣기 다지기 HD1(runbundle/service/actions/import_.py)를 진짜 DB·가짜 저장소로 잰다(발주서 §3 T3~T9).

    T3 R1  ⑤ 앞에 zip 의 blob 을 바꿔치면 올린 뒤 실패 갈래(rolled_back)·행 0 · 옛 차례(bundle.json 이 앞) zip 도 넣힘
    T4 R2  실행 0 · 어느 실행도 쓰지 않는 문서 · 실행 없는 모듈의 행 → Refused·쓰기 0
    T5 R3  넣은 뒤 같은 묶음 dry-run → Refused, 처음 dry-run → 됨
    T6 R4  꼭 실을 칸 빠짐(넣기·dry-run 두 길) · position bool·float·글자 · 자릿수 넘는 정수 · 깊은 중첩 → 제 거절
           글·쓰기 0 · 안전망은 이음매로 문에 KeyError 를 심은 것 하나
    T8 R6  같은 바이트가 문서·실행 파일 둘 → 내보내기·넣기 됨(blob 하나, role shared), 정상 묶음 머리에 shared 0
    T9 S2  모듈 행의 runOldId 가 다른 모듈 실행 → Refused·쓰기 0
★ 값은 전부 지어낸 것이다(synthetic). 시험 입력 크기는 sys 의 상한에서 짓는다(상한 숫자를 지어내지 않음).
"""

import json
import os
import sys
import zipfile
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.core.flows.carriers import CarrierRegistry, ColumnKind
from esgapi.core.service.selectors.documents import find_document
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.calc.bundle import SHARED, Refused, loads
from esgapi.runbundle.service.actions import export, import_
from esgapi.runbundle.service.actions.export import RunIds
from esgapi.runbundle.service.actions.import_ import Imported, ImportFailed
from esgapi.runbundle.tests.service.actions.test_carrier_contract import a_run
from esgapi.runbundle.tests.support import (
    MODULE,
    MODULE2,
    RxCarrier,
    World,
    _run,  # pyright: ignore[reportPrivateUsage] — 같은 seed 꼴의 실행 하나(같은 바이트 문서·파일)
    a_customer,
    carriers,
    flows,
    seed,
)
from esgapi.runs.service.selectors.runs import run_page

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def exported(tmp_path: Path, storage: FakeStorage, world: World, *, registry: CarrierRegistry | None = None) -> Path:
    out = tmp_path / "bundle.zip"
    export.run(
        company_id=world.company,
        selection=RunIds((world.runs["r2"], world.runs["r4"])),
        out=out,
        app_commit="test",
        flows=flows(),
        carriers=registry if registry is not None else carriers(),
        storage=storage,
    )
    return out


def imported(
    tmp_path: Path,
    storage: FakeStorage,
    path: Path,
    company: int,
    user: int,
    *,
    dry_run: bool = False,
    registry: CarrierRegistry | None = None,
) -> Imported:
    return import_.run(
        path=path,
        company_id=company,
        user_id=user,
        orphans_out=tmp_path / f"orphans-{path.stem}-{company}-{user}.txt",
        dry_run=dry_run,
        flows=flows(),
        carriers=registry if registry is not None else carriers(),
        storage=storage,
    )


def run_count(company: int) -> int:
    return run_page(company_id=company, module=None, status=None, document_id=None, limit=1, offset=0).count


def forged(
    path: Path, out: Path, change: Callable[[dict[str, Any]], None], *, text: Callable[[str], str] = str
) -> Path:
    """bundle.json 을 고치고 머리 blobs 에 남은 항목만 싣는 꾸민 묶음(text 는 JSON 글자를 마지막에 한 번 더 고침)."""
    with zipfile.ZipFile(path) as source:
        header = cast("dict[str, Any]", json.loads(source.read("bundle.json")))
        change(header)
        keep = {f"blobs/{blob['sha256']}" for blob in header["blobs"]}
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target:
            target.writestr("bundle.json", text(json.dumps(header, ensure_ascii=False)).encode())
            for info in source.infolist():
                if info.filename in keep:
                    target.writestr(info.filename, source.read(info))
    return out


def refused_with_no_writes(
    tmp_path: Path, storage: FakeStorage, path: Path, company: int, match: str, *, dry_run: bool = False
) -> None:
    puts = len(storage.put_calls)
    with pytest.raises(Refused, match=match):
        imported(tmp_path, storage, path, company, a_customer(company, "gasang-b"), dry_run=dry_run)
    assert run_count(company) == 0
    assert len(storage.put_calls) == puts
    assert not any(p.name.startswith("orphans") for p in tmp_path.iterdir())


# ── T3 R1 ──────────────────────────────────────────────────────────


def test_a_blob_swapped_before_the_puts_fails_after_rolling_back(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """read_bundle 이 sha 를 잰 뒤(바이트는 들지 않음) ⑤ 앞에서 zip 의 blob 하나를 같은 크기 다른 바이트로 바꾸면 ⑤ 가
    다시 읽어 대조하다 실패한다 — 행은 되돌려지고(rolled_back) 바꾼 바이트는 올라가지 않는다."""
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    original = import_.document_services.restore_document_times

    def swap_then_restore(**kwargs: Any) -> None:
        original(**kwargs)
        with zipfile.ZipFile(path) as source:
            members = [(info.filename, source.read(info)) for info in source.infolist()]
        temp = path.with_suffix(".swap")
        with zipfile.ZipFile(temp, "w") as target:
            for name, data in members:
                target.writestr(name, bytes(reversed(data)) if name.startswith("blobs/") else data)
        os.replace(temp, path)

    monkeypatch.setattr(import_.document_services, "restore_document_times", swap_then_restore)
    with pytest.raises(ImportFailed) as caught:
        imported(tmp_path, storage, path, b, a_customer(b, "gasang-b"))
    assert caught.value.rolled_back is True and caught.value.uploaded == 0
    assert run_count(b) == 0


def test_the_export_writes_bundle_json_last_and_the_old_order_still_goes_in(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """Q1: 내보내기는 bundle.json 을 마지막 항목으로 쓴다. 옛 차례(bundle.json 이 앞) 묶음도 넣힌다(이름으로 찾는다)."""
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    with zipfile.ZipFile(path) as source:
        names = source.namelist()
        members = {name: source.read(name) for name in names}
    assert names[-1] == "bundle.json" and len(names) == 1 + 5
    old = tmp_path / "old-order.zip"
    with zipfile.ZipFile(old, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name in ["bundle.json", *sorted(n for n in names if n != "bundle.json")]:
            target.writestr(name, members[name])
    assert len(imported(tmp_path, storage, old, b, a_customer(b, "gasang-b")).runs) == 4


# ── T4 R2 ──────────────────────────────────────────────────────────


def no_runs(header: dict[str, Any]) -> None:
    for table in ("core_documents", "run_runs", "run_steps", "run_results", "run_files", "core_llm_call_logs"):
        header["rows"][table] = []
        header["counts"][table] = 0
    header["blobs"] = []
    header["rows"]["modules"] = {}


def no_document_used(header: dict[str, Any]) -> None:
    for row in header["rows"]["run_runs"]:
        row["documentOldId"] = None


def module_without_runs(header: dict[str, Any]) -> None:
    header["rows"]["modules"]["rxtwo"] = {}


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (no_runs, "묶음에 실행이 없다"),
        (no_document_used, "어느 실행도 쓰지 않는 문서가 있다"),
        (module_without_runs, "실행이 없는 모듈의 행이 실렸다"),
    ],
    ids=["no_runs", "unused_document", "module_without_runs"],
)
def test_a_shape_the_export_cannot_make_is_refused(
    tmp_path: Path,
    storage: FakeStorage,
    companies: tuple[int, int],
    change: Callable[[dict[str, Any]], None],
    match: str,
) -> None:
    a, b = companies
    path = forged(exported(tmp_path, storage, seed(storage, a)), tmp_path / "forged.zip", change)
    refused_with_no_writes(tmp_path, storage, path, b, match)


# ── T5 R3 ──────────────────────────────────────────────────────────


def test_a_dry_run_after_the_import_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    path = exported(tmp_path, storage, seed(storage, a))
    user = a_customer(b, "gasang-b")
    first = imported(tmp_path, storage, path, b, user, dry_run=True)
    assert first.dry_run and first.counts["run_runs"] == 4 and run_count(b) == 0
    imported(tmp_path, storage, path, b, user)
    with pytest.raises(Refused, match="이 묶음은 이미 그 회사에 넣었다"):
        imported(tmp_path, storage, path, b, user, dry_run=True)


# ── T6 R4 ──────────────────────────────────────────────────────────


def drop(table: str, column: str) -> Callable[[dict[str, Any]], None]:
    def change(header: dict[str, Any]) -> None:
        header["tables"][table] = [name for name in header["tables"][table] if name != column]
        for row in header["rows"][table]:
            row.pop(column)

    return change


@pytest.mark.parametrize("dry_run", [False, True], ids=["import", "dry_run"])
@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("run_runs", "launch_key"),
        ("run_runs", "versions"),
        ("run_runs", "updated_at"),
        ("run_runs", "created_at"),
        ("run_runs", "flow_id"),
        ("run_steps", "created_at"),
        ("core_documents", "updated_at"),
    ],
)
def test_a_missing_required_column_is_refused_before_any_read(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], table: str, column: str, dry_run: bool
) -> None:
    """감독 C0 조건: 넣기·--dry-run 두 길 다 KeyError 자리(import_ :259·:357·:384 · gate :28)보다 앞에서 제 글로."""
    a, b = companies
    path = forged(exported(tmp_path, storage, seed(storage, a)), tmp_path / "forged.zip", drop(table, column))
    refused_with_no_writes(tmp_path, storage, path, b, f"{table} 에 꼭 실을 칸이 없다", dry_run=dry_run)


@pytest.mark.parametrize("value", [True, 1.5, "0"], ids=["bool", "float", "text"])
def test_a_position_that_is_not_an_int_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], value: object
) -> None:
    a, b = companies

    def change(header: dict[str, Any]) -> None:
        header["rows"]["run_steps"][0]["position"] = value

    path = forged(exported(tmp_path, storage, seed(storage, a)), tmp_path / "forged.zip", change)
    refused_with_no_writes(tmp_path, storage, path, b, "run_steps 의 position 은 정수여야 한다")


PLACE = "__hd1_place__"


def put_in_options(header: dict[str, Any]) -> None:
    header["rows"]["run_runs"][0]["options"]["hd1"] = PLACE


def test_an_integer_past_the_digit_limit_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    digits = "7" * (sys.get_int_max_str_digits() + 1)
    path = forged(
        exported(tmp_path, storage, seed(storage, a)),
        tmp_path / "forged.zip",
        put_in_options,
        text=lambda t: t.replace(f'"{PLACE}"', digits),
    )
    refused_with_no_writes(tmp_path, storage, path, b, "자릿수 상한을 넘는 정수")


def test_nesting_past_the_recursion_limit_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    depth = sys.getrecursionlimit()
    while True:  # 날 json.loads 가 RecursionError 를 내는 깊이(test_bundle_hd1 과 같은 잼)
        try:
            json.loads("[" * depth + "]" * depth)
        except RecursionError:
            break
        depth *= 2
    path = forged(
        exported(tmp_path, storage, seed(storage, a)),
        tmp_path / "forged.zip",
        put_in_options,
        text=lambda t: t.replace(f'"{PLACE}"', "[" * depth + "]" * depth),
    )
    refused_with_no_writes(tmp_path, storage, path, b, "중첩이 너무 깊다")


@pytest.mark.parametrize("error", [KeyError, TypeError, ValueError, RecursionError])
def test_the_safety_net_names_the_exception_only(
    tmp_path: Path,
    storage: FakeStorage,
    companies: tuple[int, int],
    monkeypatch: pytest.MonkeyPatch,
    error: type[Exception],
) -> None:
    """이음매: 문(check_shape)에 날 예외를 심는다 — 쓰기 앞 두 부름 밖으로 새면 이름만 실은 Refused 한 줄(값 0)."""
    a, b = companies
    path = exported(tmp_path, storage, seed(storage, a))

    def planted(_bundle: object) -> None:
        raise error("지어낸-값-hd1")

    monkeypatch.setattr(import_, "check_shape", planted)
    with pytest.raises(Refused) as caught:
        imported(tmp_path, storage, path, b, a_customer(b, "gasang-b"))
    assert str(caught.value) == f"묶음 꼴이 틀렸다({error.__name__})"
    assert run_count(b) == 0


# ── T8 R6 ──────────────────────────────────────────────────────────


def test_the_same_bytes_as_a_document_and_a_run_file_travel_as_one_shared_blob(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    world = seed(storage, a)
    d1 = find_document(company_id=a, document_id=world.documents["d1"])
    assert d1 is not None
    same, _etag = storage.objects[d1.storage_key]
    run = _run(
        storage,
        a,
        world.user,
        document=d1.id,
        status="done",
        options={},
        versions={},
        files=((None, "copy.pdf", same),),
    )
    out = tmp_path / "shared.zip"
    export.run(
        company_id=a,
        selection=RunIds((run,)),
        out=out,
        app_commit="test",
        flows=flows(),
        carriers=carriers(),
        storage=storage,
    )
    with zipfile.ZipFile(out) as bundle:
        header = cast("dict[str, Any]", loads(bundle.read("bundle.json")))
        assert len([n for n in bundle.namelist() if n.startswith("blobs/")]) == 1
    assert [blob["role"] for blob in header["blobs"]] == [SHARED]
    assert len(imported(tmp_path, storage, out, b, a_customer(b, "gasang-b")).runs) == 1
    normal = exported(tmp_path, storage, world)
    with zipfile.ZipFile(normal) as bundle:
        roles = {blob["role"] for blob in cast("dict[str, Any]", loads(bundle.read("bundle.json")))["blobs"]}
    assert roles == {"document", "run_file"}  # 정상 묶음 머리 그대로(shared 0) — 옛 묶음 꼴로 넣힌다
    assert len(imported(tmp_path, storage, normal, b, a_customer(b, "gasang-b2")).runs) == 4


# ── T9 S2 ──────────────────────────────────────────────────────────


@dataclass
class MarksCarrier(RxCarrier):
    """모듈 행에 runOldId 칸(그 모듈 실행)을 싣는 시험 carrier — 그린워싱 검토·표시 꼴."""

    def export_rows(
        self, company_id: int, run_ids: Collection[int], versions: Mapping[int, Mapping[str, object]]
    ) -> dict[str, list[dict[str, object]]]:
        marks: list[dict[str, object]] = [{"runOldId": run_id} for run_id in sorted(run_ids)]
        return super().export_rows(company_id, run_ids, versions) | {"marks": marks}

    def columns(self) -> Mapping[str, Mapping[str, ColumnKind]]:
        return {**super().columns(), "marks": {"runOldId": "id"}}

    def id_fields(self) -> Mapping[str, tuple[str, ...]]:
        return {**super().id_fields(), "marks": ("runOldId",)}


def two_carriers() -> CarrierRegistry:
    found = CarrierRegistry()
    found.register(MODULE, MarksCarrier())
    found.register(MODULE2, RxCarrier(next_setting=500))
    return found


def test_a_module_row_pointing_at_another_modules_run_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    user = a_customer(a, "gasang-two")
    mine, other = a_run(a, user), a_run(a, user, module=MODULE2)
    path = tmp_path / "two.zip"
    export.run(
        company_id=a,
        selection=RunIds((mine, other)),
        out=path,
        app_commit="test",
        flows=flows(),
        carriers=two_carriers(),
        storage=storage,
    )
    good = imported(tmp_path, storage, path, a, a_customer(a, "gasang-again"), registry=two_carriers())
    assert len(good.runs) == 2  # 정상 묶음(그 모듈 실행을 가리킴)은 넣힌다 — 보낸 회사 자신으로

    def point_elsewhere(header: dict[str, Any]) -> None:
        header["rows"]["modules"][MODULE]["marks"][0]["runOldId"] = other

    forged_path = forged(path, tmp_path / "forged.zip", point_elsewhere)
    puts = len(storage.put_calls)
    with pytest.raises(Refused, match="그 모듈 실행이 아닌 실행을 가리킨다"):
        imported(tmp_path, storage, forged_path, b, a_customer(b, "gasang-b"), registry=two_carriers())
    assert run_count(b) == 0 and len(storage.put_calls) == puts
