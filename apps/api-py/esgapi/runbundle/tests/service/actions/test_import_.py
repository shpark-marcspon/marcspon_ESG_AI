"""넣기(import_runs — runbundle/service/actions/import_.py)를 진짜 DB·가짜 저장소로 잰다(발주서 §3).

    S7 왕복      회사 A 의 실행 넷(직접 r2·r4 + 닫힘 r1·r3)을 내보내 회사 B 에 넣으면 runs·core selector 가 정규형으로
                 같다(versions 날 값의 aiSettingId = 판 지도의 새 id). 문서 하나 = blob 하나
    S8 사슬      묶음 밖 앞 판(d0)에서 자른 A 의 사슬 = B 의 사슬, B 의 d3 앞 판은 None
    S9 두 번     둘째 넣기(같은 사람·다른 사람) 거절·행 수 그대로, 다른 회사로는 됨(동시는 transaction 시험)
    S10 시각     표 T(실행·단계·문서)는 원래 시각, 결과·파일·LLM 기록은 넣은 때, 보통 시각 칸은 그대로
    S11 다 아니면 0  ④ 마지막에서 던지면 행 0·put 0, n 번째 put 실패면 행 0·orphans = 올린 키 n−1
    S12 사람·회사  --user 남의 회사·없는 id, --company 없음 → 쓰기 0
    S13 실행기와  넣은 문서의 etag = 저장소 get 의 etag(object_changed 아님), 넣은 실행은 queued 가 아니다(잡지 않음)
★ 내보내기의 스냅숏(SET TRANSACTION)은 블록의 첫 문장이어야 해 transaction=True 다.
"""

import json
import os
import stat
import threading
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from django.db import OperationalError, connection, transaction
from pytest_django import DjangoAssertNumQueries

from esgapi.core.flows.binding import BindingRegistry
from esgapi.core.flows.carriers import CARRIERS, IdMap
from esgapi.core.flows.registry import REGISTRY
from esgapi.core.resources import queue as hooks
from esgapi.core.resources.ports.storage import (
    GetResult,
    HeadResult,
    ObjectBytes,
    ObjectStorage,
    PresignedUpload,
    PutResult,
    StorageUnavailable,
)
from esgapi.core.service.selectors.documents import find_document
from esgapi.core.service.selectors.llm_logs import rows_of_runs
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.calc.bundle import Refused, canonical_sha256, check_bundle, loads
from esgapi.runbundle.service.actions import export, import_
from esgapi.runbundle.service.actions._common import migration_graph, model_columns
from esgapi.runbundle.service.actions.export import RunIds
from esgapi.runbundle.service.actions.import_ import Imported, ImportFailed
from esgapi.runbundle.tests.support import (
    FLOW_ID,
    OLD,
    OLDER,
    RxBinding,
    RxCarrier,
    World,
    a_customer,
    carriers,
    cut_chain,
    flows,
    seed,
    snapshot,
)
from esgapi.runs.service.actions import runs as run_actions
from esgapi.runs.service.actions.runs import ResumeAlready
from esgapi.runs.service.selectors.bundle import bundle_rows
from esgapi.runs.service.selectors.runs import find_run, run_files, run_page, runs_of

pytestmark = pytest.mark.django_db(transaction=True)


def exported(tmp_path: Path, storage: FakeStorage, world: World) -> Path:
    out = tmp_path / "bundle.zip"
    export.run(
        company_id=world.company,
        selection=RunIds((world.runs["r2"], world.runs["r4"])),
        out=out,
        app_commit="test",
        flows=flows(),
        carriers=carriers(),
        storage=storage,
    )
    return out


def imported(
    tmp_path: Path, storage: ObjectStorage, path: Path, company: int, user: int, carrier: RxCarrier | None = None
) -> Imported:
    return import_.run(
        path=path,
        company_id=company,
        user_id=user,
        orphans_out=tmp_path / f"orphans-{company}-{user}.txt",
        flows=flows(),
        carriers=carriers(carrier),
        storage=storage,
    )


def labels_of(company: int, world: World, done: Imported) -> tuple[dict[str, int], dict[str, int]]:
    """B 의 이름표: 실행은 넣기의 지도, 문서는 넣은 실행의 문서 칸과 앞 판."""
    runs = {label: done.runs[old] for label, old in world.runs.items()}
    found = runs_of(company_id=company, run_ids=runs.values())
    documents = {
        "d2": found[runs["r2"]].document_id,
        "d3": found[runs["r3"]].document_id,
        "d1": found[runs["r4"]].document_id,
    }
    assert all(isinstance(value, int) for value in documents.values())
    return runs, {label: int(str(value)) for label, value in documents.items()}


def run_count(company: int) -> int:
    return run_page(company_id=company, module=None, status=None, document_id=None, limit=1, offset=0).count


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def test_a_round_trip_reads_the_same(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    carrier = RxCarrier()
    done = imported(tmp_path, storage, path, b, a_customer(b, "gasang-b"), carrier)
    assert sorted(done.runs) == sorted(world.runs.values())
    runs, documents = labels_of(b, world, done)
    (setting,) = carrier.imported_settings
    before = snapshot(a, world.runs, {k: v for k, v in world.documents.items() if k != "d0"}, {7: "S"})
    after = snapshot(b, runs, documents, {int(str(setting["id"])): "S"})
    assert after == cut_chain(before)
    raw = find_run(company_id=b, run_id=runs["r3"])
    assert raw is not None and raw.versions["aiSettingId"] == setting["id"]  # S7: versions 날 값
    assert raw.versions["aiSetting"] == f"v{setting['id']}"  # RX1b: 판 이름은 carrier 가 새 이름으로
    with zipfile.ZipFile(path) as archive:
        carried = check_bundle(loads(archive.read("bundle.json")))
    shas = {int(str(row["oldId"])): canonical_sha256(row) for row in carried.rows["run_runs"]}
    keyed = {
        int(str(row["id"])): row["idempotency_sha256"] for row in bundle_rows(company_id=b, run_ids=runs.values()).runs
    }
    assert {old: keyed[new] for old, new in done.runs.items()} == shas  # 넣은 실행의 sha = 묶음 행의 정규형 sha
    with zipfile.ZipFile(path) as bundle:
        blobs = [name for name in bundle.namelist() if name.startswith("blobs/")]
    assert len(blobs) == 3 + 2  # 문서 셋(d1·d2·d3) + 파일 바이트 둘(pages.json 은 r1·r2 가 같은 바이트 — blob 하나)


def test_the_chain_is_cut_at_the_first_document_outside(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    world = seed(storage, a)
    done = imported(tmp_path, storage, exported(tmp_path, storage, world), b, a_customer(b, "gasang-b"))
    _runs, documents = labels_of(b, world, done)
    d3 = find_document(company_id=b, document_id=documents["d3"])
    d2 = find_document(company_id=b, document_id=documents["d2"])
    assert d3 is not None and d3.previous_document_id is None
    assert d2 is not None and d2.previous_document_id == documents["d1"]


def test_times_of_table_t_come_back_and_the_rest_are_now(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    done = imported(tmp_path, storage, path, b, a_customer(b, "gasang-b"))
    runs, documents = labels_of(b, world, done)
    rows = bundle_rows(company_id=b, run_ids=runs.values())
    assert {(row["created_at"], row["updated_at"]) for row in rows.runs + rows.steps} == {(OLDER, OLD)}
    assert {(row["started_at"], row["finished_at"]) for row in rows.runs} == {(OLDER, OLD)}
    source = bundle_rows(company_id=a, run_ids=world.runs.values())
    seeded = source.files[0]["created_at"]
    assert isinstance(seeded, datetime)
    assert all(isinstance(at := row["created_at"], datetime) and at > seeded for row in rows.files + rows.results)
    for document_id in documents.values():
        document = find_document(company_id=b, document_id=document_id)
        assert document is not None and (document.created_at, document.uploaded_at) == (OLDER, OLD)
    logs = rows_of_runs(company_id=b, run_ids=runs.values())
    assert len(logs) == 3 and {row["ts"] for row in logs} == {OLD}
    assert all(isinstance(at := row["created_at"], datetime) and at > OLD for row in logs)


def test_a_bundle_goes_in_once_per_company(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    first, second = a_customer(b, "gasang-b"), a_customer(b, "gasang-b2")
    imported(tmp_path, storage, path, b, first)
    counted = run_count(b)
    puts = len(storage.put_calls)
    for user in (first, second):  # 같은 사람·다른 사람 둘 다
        with pytest.raises(Refused, match="이미"):
            imported(tmp_path, storage, path, b, user)
    assert run_count(b) == counted
    assert len(storage.put_calls) == puts
    third = a_customer(a, "gasang-a2")
    assert len(imported(tmp_path, storage, path, a, third).runs) == 4  # 다른 회사(여기선 보낸 회사 자신)로는 된다


@pytest.mark.parametrize(
    "who",
    ["other_company_user", "missing_user", "missing_company"],
    ids=["other_user", "missing_user", "missing_company"],
)
def test_people_and_companies_are_checked(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], who: str
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    company, user = {
        "other_company_user": (b, world.user),
        "missing_user": (b, 999_999),
        "missing_company": (999_999, world.user),
    }[who]
    puts = len(storage.put_calls)
    with pytest.raises(Refused):
        imported(tmp_path, storage, path, company, user)
    assert run_count(b) == 0
    assert len(storage.put_calls) == puts


class _FailingCarrier(RxCarrier):
    def import_rows(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]], ids: IdMap
    ) -> None:
        raise RuntimeError("지어낸 실패: ④ 의 마지막 표")


def test_a_failure_before_the_puts_leaves_no_rows_and_no_objects(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    puts = len(storage.put_calls)
    with pytest.raises(RuntimeError, match="지어낸 실패"):
        imported(tmp_path, storage, path, b, a_customer(b, "gasang-b"), _FailingCarrier())
    assert run_count(b) == 0
    assert len(storage.put_calls) == puts
    assert not any(p.name.startswith("orphans") for p in tmp_path.iterdir())  # 미리 만든 빈 파일도 지운다


@dataclass
class _NthPutFails:
    """저장소 포트: n 번째 put 만 실패하고 나머지는 base 로 넘긴다."""

    base: FakeStorage
    nth: int
    put_calls: list[str] = field(default_factory=list[str])

    def presign_upload(self, key: str, *, content_length: int) -> PresignedUpload:
        return self.base.presign_upload(key, content_length=content_length)

    def head(self, key: str) -> HeadResult:
        return self.base.head(key)

    def get(self, key: str, *, max_bytes: int) -> GetResult:
        return self.base.get(key, max_bytes=max_bytes)

    def put(self, key: str, *, content: bytes, media_type: str) -> PutResult:
        self.put_calls.append(key)
        if len(self.put_calls) == self.nth:
            return StorageUnavailable("지어낸 실패")
        return self.base.put(key, content=content, media_type=media_type)


def test_the_nth_put_failing_writes_the_n_minus_1_keys_and_no_rows(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    failing = _NthPutFails(storage, nth=3)
    puts = len(storage.put_calls)
    user = a_customer(b, "gasang-b")
    with pytest.raises(ImportFailed) as caught:
        imported(tmp_path, failing, path, b, user)
    assert caught.value.uploaded == 2
    head, *orphans = (tmp_path / f"orphans-{b}-{user}.txt").read_text().splitlines()
    assert head == import_.ROLLED_BACK_HEAD
    assert orphans == failing.put_calls[:2] == storage.put_calls[puts:]
    assert all(f"/{b}/" in key for key in orphans)  # 키만(바이트 0) — 받는 회사의 키
    assert run_count(b) == 0


def test_the_executor_sees_the_same_object(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    a, b = companies
    world = seed(storage, a)
    done = imported(tmp_path, storage, exported(tmp_path, storage, world), b, a_customer(b, "gasang-b"))
    runs, documents = labels_of(b, world, done)
    for document_id in documents.values():
        document = find_document(company_id=b, document_id=document_id)
        assert document is not None and document.etag is not None
        got = storage.get(document.storage_key, max_bytes=10_000)
        assert isinstance(got, ObjectBytes) and got.etag == document.etag  # runs/tasks.py 의 object_changed 아님
    for run_id in runs.values():
        run = find_run(company_id=b, run_id=run_id)
        assert run is not None and run.status in {"done", "failed"}  # queued 아님 — 잡기·다시 넣기 대상 아님
        for file in run_files(company_id=b, run_id=run_id):
            assert file.storage_key.startswith(f"runs/{b}/{run_id}/")
            assert isinstance(storage.get(file.storage_key, max_bytes=10_000), ObjectBytes)


def test_two_imports_at_once_let_one_in(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    """S9(동시): 같은 묶음을 두 스레드가 같이 넣으면(다른 사람) advisory 잠금이 줄 세워 하나만 들어가고 뒤의 것은
    앞의 커밋을 보고 거절된다. 고아 0(거절은 put 앞이다)."""
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    users = [a_customer(b, "gasang-b1"), a_customer(b, "gasang-b2")]
    start = threading.Barrier(2)
    outcomes: list[str] = []

    def one(user: int) -> None:
        try:
            start.wait()
            imported(tmp_path, storage, path, b, user)
            outcomes.append("들어감")
        except Refused:
            outcomes.append("거절")
        finally:
            connection.close()

    threads = [threading.Thread(target=one, args=(user,)) for user in users]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert sorted(outcomes) == ["거절", "들어감"]
    assert run_count(b) == 4
    assert not any(p.name.startswith("orphans") for p in tmp_path.iterdir())


def test_resuming_an_imported_failed_run_is_already_resumed(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """S18: 넣은 failed 앞 실행(r1)을 같은 문서·흐름·options 로 이어 돌리면 묶음 안 done 자식(r2)이 막는다 —
    ResumeAlready, 새 실행 0, 큐 넣기 0(옮겨 온 체크포인트로 새 호출이 나갈 길 0)."""
    a, b = companies
    world = seed(storage, a)
    user = a_customer(b, "gasang-b")
    done = imported(tmp_path, storage, exported(tmp_path, storage, world), b, user)
    runs, documents = labels_of(b, world, done)
    bindings = BindingRegistry()
    bindings.register(FLOW_ID, RxBinding())
    monkeypatch.setattr(run_actions, "REGISTRY", flows())
    monkeypatch.setattr(run_actions, "BINDINGS", bindings)
    calls: list[dict[str, object]] = []

    def spy(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(hooks, "enqueue_run", spy)
    previous = find_run(company_id=b, run_id=runs["r1"])
    assert previous is not None and previous.status == "failed"
    before = run_count(b)
    result = run_actions.create_run(
        company_id=b,
        actor_kind="service",
        actor_user_id=user,
        module="rxtest",
        flow_id=FLOW_ID,
        document_id=documents["d2"],
        options=previous.options,
        resume_from=runs["r1"],
        now=datetime.now(UTC),
    )
    assert isinstance(result, ResumeAlready)
    assert run_count(b) == before and calls == []


def test_the_gates_read_no_database(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    """S4: 마이그레이션 그래프·모델 칸 읽기는 DB 쿼리 0(MigrationLoader(None) — B1)."""
    with django_assert_num_queries(0):
        leaves, nodes = migration_graph()
        columns = model_columns()
    assert ("runs", "0001_initial") in nodes and leaves["runs"]
    assert set(columns) == {
        "core_documents",
        "run_runs",
        "run_steps",
        "run_results",
        "run_files",
        "core_llm_call_logs",
        "run_segments",  # RM1c: 일곱째 표
    }


def test_the_global_registries_are_untouched(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    """S17: 시험은 자기 레지스트리를 인자로 넘긴다 — 전역 REGISTRY·CARRIERS 는 시험 앞과 같다(rxtest 0)."""
    flows_before, carriers_before = REGISTRY.modules(), CARRIERS.modules()
    a, b = companies
    world = seed(storage, a)
    imported(tmp_path, storage, exported(tmp_path, storage, world), b, a_customer(b, "gasang-b"))
    assert (REGISTRY.modules(), CARRIERS.modules()) == (flows_before, carriers_before)
    assert "rxtest" not in REGISTRY.modules() and "rxtest" not in CARRIERS.modules()  # 전역은 모듈 넷(RX1b)뿐


def _with_status(path: Path, out: Path, status: str) -> Path:
    """묶음의 첫 실행 행 상태만 바꾼 묶음(나머지 항목·머리 그대로)."""
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "bundle.json":
                header = cast("dict[str, Any]", json.loads(data))
                header["rows"]["run_runs"][0]["status"] = status
                data = json.dumps(header, ensure_ascii=False).encode()
            target.writestr(info.filename, data)
    return out


@pytest.mark.parametrize("status", ["queued", "processing"])
def test_an_unfinished_run_in_the_bundle_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], status: str
) -> None:
    """② 검증 B1: 묶음에 끝나지 않은 실행이 실려 오면(손으로 고친 묶음) 쓰기 앞 문에서 거절 — 행 0·put 0."""
    a, b = companies
    world = seed(storage, a)
    path = _with_status(exported(tmp_path, storage, world), tmp_path / "edited.zip", status)
    puts = len(storage.put_calls)
    with pytest.raises(Refused, match="끝난 실행"):
        imported(tmp_path, storage, path, b, a_customer(b, "gasang-b"))
    assert run_count(b) == 0 and len(storage.put_calls) == puts


class _CommitFails:
    """import_ 의 transaction.atomic 만 감싼다: 진짜 블록을 나온 뒤(committed=True) 또는 되돌린 뒤 예외를 낸다 —
    커밋 단계의 애매한 실패(COMMIT 중 연결 끊김 등)를 흉내 낸다. 전역 django.db.transaction 은 그대로."""

    def __init__(self, *, committed: bool) -> None:
        self.committed = committed

    def atomic(self, **kwargs: Any) -> "_CommitFailsBlock":
        return _CommitFailsBlock(transaction.atomic(**kwargs), committed=self.committed)


class _CommitFailsBlock:
    def __init__(self, inner: Any, *, committed: bool) -> None:
        self.inner, self.committed = inner, committed

    def __enter__(self) -> object:
        return self.inner.__enter__()

    def __exit__(self, kind: Any, value: Any, trace: Any) -> bool:
        if kind is not None:
            return bool(self.inner.__exit__(kind, value, trace))
        if self.committed:
            self.inner.__exit__(None, None, None)
        else:
            planted = RuntimeError("지어낸 롤백")
            self.inner.__exit__(RuntimeError, planted, None)
        raise OperationalError("지어낸 커밋 단계 오류")


def test_an_ambiguous_commit_that_did_commit_leaves_no_orphans(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """③ S1: 커밋 뒤에 예외가 나도 새 연결로 열쇠를 다시 보아 커밋됐으면 고아 0 · Imported.commit_error."""
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    monkeypatch.setattr(import_, "transaction", _CommitFails(committed=True))
    done = imported(tmp_path, storage, path, b, a_customer(b, "gasang-b"))
    assert done.commit_error == "OperationalError" and len(done.runs) == 4
    assert run_count(b) == 4
    assert not any(p.name.startswith("orphans") for p in tmp_path.iterdir())


def test_an_ambiguous_commit_that_rolled_back_writes_the_orphans(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """③ S1 의 짝: 커밋 단계 예외 뒤 다시 보니 열쇠가 없으면(되돌려짐) 올린 키 전부를 orphans 에."""
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    puts = len(storage.put_calls)
    user = a_customer(b, "gasang-b")
    monkeypatch.setattr(import_, "transaction", _CommitFails(committed=False))
    with pytest.raises(ImportFailed) as caught:
        imported(tmp_path, storage, path, b, user)
    assert caught.value.rolled_back is True and caught.value.written is True
    head, *orphans = (tmp_path / f"orphans-{b}-{user}.txt").read_text().splitlines()
    assert head == import_.ROLLED_BACK_HEAD
    assert orphans == storage.put_calls[puts:] and len(orphans) == caught.value.uploaded > 0
    assert run_count(b) == 0


def test_the_orphans_file_is_made_before_the_block(tmp_path: Path) -> None:
    """③ S2: --orphans-out 은 O_EXCL 0600 으로 미리 — 있으면 거절, 쓰기가 실패하면 False(명령이 stderr 로)."""
    path = tmp_path / "orphans.txt"
    fd = import_.open_orphans(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(Refused, match="이미 있다"):
        import_.open_orphans(path)
    os.close(fd)
    assert import_.write_orphans(fd, import_.ROLLED_BACK_HEAD, ["runs/1/2/out/x"]) is False


def test_an_ambiguous_commit_that_cannot_be_rechecked_is_marked_do_not_delete(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """③ 검증 B2: 커밋 단계 예외 뒤 다시 보기도 실패하면 「확인 불가 키(지우지 말 것)」 머리로 적고 rolled_back None —
    「행 되돌림·지워도 됨」 머리와 다르다(커밋됐을 수 있는 객체를 지울 목록에 올리지 않는다)."""
    a, b = companies
    world = seed(storage, a)
    path = exported(tmp_path, storage, world)
    puts = len(storage.put_calls)
    user = a_customer(b, "gasang-b")
    monkeypatch.setattr(import_, "transaction", _CommitFails(committed=True))

    def unreachable(**_kwargs: object) -> object:
        raise OperationalError("지어낸 다시 보기 실패")

    monkeypatch.setattr(import_, "runs_of", unreachable)
    with pytest.raises(ImportFailed) as caught:
        imported(tmp_path, storage, path, b, user)
    assert caught.value.rolled_back is None and caught.value.head == import_.UNKNOWN_HEAD
    assert "커밋 여부 확인 불가 — 지우기 전에 확인" in str(caught.value)
    head, *keys = (tmp_path / f"orphans-{b}-{user}.txt").read_text().splitlines()
    assert head == import_.UNKNOWN_HEAD != import_.ROLLED_BACK_HEAD
    assert keys == storage.put_calls[puts:] and keys
    assert run_count(b) == 4  # 실제로는 커밋됐다 — 그래서 지우면 안 된다
