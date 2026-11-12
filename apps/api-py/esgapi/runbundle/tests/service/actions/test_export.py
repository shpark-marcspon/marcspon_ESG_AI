"""내보내기(export_runs — runbundle/service/actions/export.py)를 진짜 DB·가짜 저장소로 잰다(발주서 §3).

    S5 고르기   --runs·--module --from --to(서울 날짜 양끝 포함). --runs 로 고른 실행이 failed·queued·processing 이면
                거절, 창은 done 만 고르고 나머지는 상태별로 센다(RX1b Qb10). 이어 가기 사슬이 끈 failed 앞 실행은 실림·
                queued 앞 실행은 거절, carrier 참조가 done 아님을 가리키면 --runs 거절(Qb8), --max-runs
    S6 닫힘     이어 간 앞 실행·carrier 가 가리킨 실행을 더한다(수가 찍힘), 남의 회사 실행은 0
    S14 비밀    지어낸 비밀번호·아이디·이름이 묶음에 0
    ★c         블록 첫 문장 뒤 transaction_isolation = repeatable read · transaction_read_only = on
    그 밖       carrier 없는 모듈 거절(닫힌 기본), --out 이 있으면 거절·0600, 저장소 바이트가 행과 다르면 거절
★ 스냅숏(SET TRANSACTION)은 블록의 첫 문장이어야 해 transaction=True 다.
"""

import stat
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.core.flows.carriers import CarrierRegistry
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.calc.bundle import Refused, check_bundle, loads
from esgapi.runbundle.service.actions import _pg, export
from esgapi.runbundle.service.actions.export import Exported, RunIds, Window
from esgapi.runbundle.tests.support import PASSWORD, carriers, flows, seed
from esgapi.runs.service.services.bundle import insert_run, restore_times

pytestmark = pytest.mark.django_db(transaction=True)


def run_export(
    tmp_path: Path,
    storage: FakeStorage,
    company: int,
    selection: RunIds | Window,
    *,
    registry: CarrierRegistry | None = None,
    max_runs: int = 200,
    name: str = "bundle.zip",
) -> Exported:
    return export.run(
        company_id=company,
        selection=selection,
        out=tmp_path / name,
        app_commit="test",
        max_runs=max_runs,
        flows=flows(),
        carriers=registry if registry is not None else carriers(),
        storage=storage,
    )


def header(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as bundle:
        found = loads(bundle.read("bundle.json"))
    assert isinstance(found, dict)
    return cast("dict[str, object]", found)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def test_the_closure_adds_the_runs_pointed_at(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    world = seed(storage, companies[0])
    done = run_export(tmp_path, storage, world.company, RunIds((world.runs["r2"], world.runs["r4"])))
    assert (done.runs, done.closure) == (4, 2)  # r1(이어 간 앞 실행 — failed 를 기록으로) · r3(carrier)
    bundle = check_bundle(header(tmp_path / "bundle.zip"))
    assert sorted(int(str(row["oldId"])) for row in bundle.rows["run_runs"]) == sorted(world.runs.values())
    assert done.counts["core_documents"] == 3 and done.counts["core_llm_call_logs"] == 3
    assert bundle.source_company_id == world.company and bundle.migrations  # 기록만


def test_another_companys_runs_are_not_found(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    world = seed(storage, companies[0])
    with pytest.raises(Refused, match="없는 실행"):
        run_export(tmp_path, storage, companies[1], RunIds((world.runs["r2"],)))
    assert not (tmp_path / "bundle.zip").exists()


@pytest.mark.parametrize("label", ["r1"], ids=["failed"])
def test_a_directly_picked_run_must_be_done(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], label: str
) -> None:
    world = seed(storage, companies[0])
    with pytest.raises(Refused, match="done 이 아니다"):
        run_export(tmp_path, storage, world.company, RunIds((world.runs[label],)))


@pytest.mark.parametrize("status", ["queued", "processing"])
def test_unfinished_runs_are_refused_directly_and_in_the_closure(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], status: str
) -> None:
    world = seed(storage, companies[0])
    open_run = insert_run(
        company_id=world.company,
        fields={
            "module": "rxtest",
            "flow_id": "rxtest.flow@1",
            "options": {},
            "versions": {},
            "status": status,
            "created_by_user_id": world.user,
        },
    )
    with pytest.raises(Refused, match="done 이 아니다"):
        run_export(tmp_path, storage, world.company, RunIds((open_run,)))
    pointing = insert_run(
        company_id=world.company,
        fields={
            "module": "rxtest",
            "flow_id": "rxtest.flow@1",
            "options": {"retryFromRunId": open_run},
            "versions": {},
            "status": "done",
            "created_by_user_id": world.user,
        },
    )
    with pytest.raises(Refused, match="같은 모듈 done 이 아니다"):  # carrier 참조는 done 만(RX1b Qb8)
        run_export(tmp_path, storage, world.company, RunIds((pointing,)))
    resumed = insert_run(
        company_id=world.company,
        fields={
            "module": "rxtest",
            "flow_id": "rxtest.flow@1",
            "options": {},
            "versions": {},
            "status": "done",
            "created_by_user_id": world.user,
            "resumed_from_run_id": open_run,
        },
    )
    with pytest.raises(Refused, match="끝나지 않았다"):  # 이어 가기 사슬
        run_export(tmp_path, storage, world.company, RunIds((resumed,)), name="resumed.zip")


def test_max_runs_counts_the_closure(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    world = seed(storage, companies[0])
    with pytest.raises(Refused, match="max-runs"):
        run_export(tmp_path, storage, world.company, RunIds((world.runs["r2"], world.runs["r4"])), max_runs=3)
    with pytest.raises(Refused, match="max-runs"):
        run_export(tmp_path, storage, world.company, RunIds((world.runs["r2"], world.runs["r4"])), max_runs=1)


def test_the_window_is_seoul_days_inclusive(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    world = seed(storage, companies[0])
    seoul = [
        # 서울 10-02 00:00 = UTC 10-01 15:00 — 첫날 들어감 · 서울 10-03 23:59:59 = UTC 10-03 14:59:59 — 끝날 들어감
        (world.runs["r3"], "2026-10-01T15:00:00+00:00"),
        (world.runs["r4"], "2026-10-03T14:59:59+00:00"),
        (world.runs["r2"], "2026-10-03T15:00:00+00:00"),  # 서울 10-04 00:00 — 밖
        (world.runs["r1"], "2026-10-01T14:59:59+00:00"),  # 서울 10-01 23:59:59 — 밖
    ]
    for run_id, at in seoul:
        moment = datetime.fromisoformat(at)
        restore_times(company_id=world.company, table="run_runs", times={run_id: (moment, moment)})
    done = run_export(
        tmp_path, storage, world.company, Window(module="rxtest", first=date(2026, 10, 2), last=date(2026, 10, 3))
    )
    assert (done.runs, done.closure) == (2, 0)  # r3·r4(r4 가 끄는 r3 은 이미 고름)
    with pytest.raises(Refused, match="done 실행이 없다"):
        run_export(
            tmp_path,
            storage,
            world.company,
            Window(module="other", first=date(2026, 10, 2), last=date(2026, 10, 3)),
            name="other.zip",
        )
    wide = run_export(  # 창 안의 failed(r1)는 건너뛰고 센다(RX1b Qb10 — 창은 done 만 고른다)
        tmp_path,
        storage,
        world.company,
        Window(module="rxtest", first=date(2026, 10, 1), last=date(2026, 10, 3)),
        name="wide.zip",
    )
    assert (wide.runs, wide.closure, wide.skipped, wide.out_of_reference) == (2, 0, {"failed": 1}, 0)


def test_a_module_without_a_carrier_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    world = seed(storage, companies[0])
    with pytest.raises(Refused, match="carrier"):
        run_export(tmp_path, storage, world.company, RunIds((world.runs["r3"],)), registry=CarrierRegistry())


def test_the_out_file_is_private_and_never_overwritten(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    world = seed(storage, companies[0])
    run_export(tmp_path, storage, world.company, RunIds((world.runs["r3"],)))
    path = tmp_path / "bundle.zip"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    before = path.read_bytes()
    with pytest.raises(Refused, match="이미 있다"):
        run_export(tmp_path, storage, world.company, RunIds((world.runs["r3"],)))
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["bundle.zip"]  # 임시 파일이 남지 않는다


def test_bytes_that_differ_from_the_row_are_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    world = seed(storage, companies[0])
    key = next(key for key in storage.objects if key.endswith("/out/out.json"))
    storage.put(key, b'{"ok":"no"}')  # 크기(11)는 같고 sha 가 다르다
    with pytest.raises(Refused, match="바이트가 행과 다르다"):
        run_export(tmp_path, storage, world.company, RunIds((world.runs["r2"],)))


def test_no_secret_or_person_reaches_the_bundle(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    world = seed(storage, companies[0])
    run_export(tmp_path, storage, world.company, RunIds((world.runs["r2"], world.runs["r4"])))
    with zipfile.ZipFile(tmp_path / "bundle.zip") as bundle:
        text = bundle.read("bundle.json").decode()
    for planted in (PASSWORD, "gasang-a", "가상 gasang-a", "storage_key", "uploaded_by", "created_by_user_id"):
        assert planted not in text, planted
    assert f'"companies/{world.company}/' not in text and f'"runs/{world.company}/' not in text  # 키 0


def test_the_snapshot_is_repeatable_read_and_read_only(companies: tuple[int, int]) -> None:
    from django.db import transaction

    with CaptureQueriesContext(connection) as queries, transaction.atomic(durable=True):
        _pg.read_only_snapshot()
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_isolation")
            isolation = cursor.fetchone()
            cursor.execute("SHOW transaction_read_only")
            read_only = cursor.fetchone()
    assert (isolation, read_only) == (("repeatable read",), ("on",))
    # ★c: 블록 앞에 Django 가 낸 것은 BEGIN 하나 — SET TRANSACTION 이 트랜잭션의 첫 질의라 먹는다
    assert [query["sql"].split()[0] for query in queries.captured_queries[:2]] == ["BEGIN", "SET"]


def test_the_snapshot_refuses_outside_a_block() -> None:
    with pytest.raises(RuntimeError):
        _pg.read_only_snapshot()
    with pytest.raises(RuntimeError):
        _pg.lock_bundle(1, "00000000-0000-4000-8000-000000000000")
