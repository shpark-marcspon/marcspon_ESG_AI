"""carrier 계약(RX1b ① — core/flows/carriers.py · runbundle export·import_)을 진짜 DB·가짜 저장소·가짜 carrier 로 잰다.

    T4 계약   versions·partial 이 carrier 로 간다 · Rewritten 의 길이·이름 어김, 선언 밖 자리 바뀜, carrier 의
              aiSettingId 바꿈 → 거절 · 앞 참조(Qb11)·묶음 안 failed 참조 → 거절 ·
              꾸민 모듈 행(사람·id·선언 밖 칸) → 쓰기 0 거절 ·
              옛 판 id 가 모듈끼리 같고 B 순번이 어긋나도 판 id 가 섞이지 않음(Qb6), 다른 모듈의 옛 판 id → 거절 ·
              지도 밖 id(UnknownId) → Refused(명령 종료 1·쓰기 0) · 판 이름 다시 시도가 다함(SettingCarrier 의
              넣기가 경합) → Refused·쓰기 0(r3)
    T9 닫힘·창 Qb8 carrier 참조가 failed·다른 모듈·남의 회사·없는 실행 → --runs 거절, 창은 건너뜀·「참조 밖」 셈 ·
              Qb9 사슬 가운데 failed 의 이어 가기 가능 여부가 A·B 같음 · Qb10 --max-runs 는 창의 모든 상태를 셈 ·
              R4 커밋 확인이 같은 묶음을 앞서 넣은 다른 넣기와 가름(새 id 로 봄)
★ 시험 모듈 둘(rxtest·rxtwo)은 시험 레지스트리에만(전역 0). 회사·사람·숫자는 전부 지어낸 것이다(synthetic).
"""

import functools
import json
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, cast

import pytest
from django.core.management import CommandError, call_command

from esgapi.core.flows.carriers import CarrierRegistry, IdMap, Rewritten, SettingCarrier
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.calc.bundle import Refused
from esgapi.runbundle.service.actions import export, import_
from esgapi.runbundle.service.actions.export import Exported, RunIds, Window
from esgapi.runbundle.service.actions.import_ import Imported
from esgapi.runbundle.tests.support import (
    FLOW2_ID,
    FLOW_ID,
    MODULE,
    MODULE2,
    RxCarrier,
    a_customer,
    flows,
    seed,
)
from esgapi.runs.service.selectors.bundle import taken_keys
from esgapi.runs.service.selectors.runs import find_run, resumed_alive, run_page, step_rows
from esgapi.runs.service.services.bundle import insert_run, insert_steps

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def registry(first: RxCarrier | None = None, second: RxCarrier | None = None) -> CarrierRegistry:
    found = CarrierRegistry()
    found.register(MODULE, first if first is not None else RxCarrier())
    found.register(MODULE2, second if second is not None else RxCarrier(next_setting=500))
    return found


def run_export(
    tmp_path: Path,
    storage: FakeStorage,
    company: int,
    selection: RunIds | Window,
    *,
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
        carriers=registry(),
        storage=storage,
    )


def export_to(
    tmp_path: Path, storage: FakeStorage, company: int, selection: RunIds | Window, *, name: str = "bundle.zip"
) -> Path:
    run_export(tmp_path, storage, company, selection, name=name)
    return tmp_path / name


def run_import(
    tmp_path: Path, storage: FakeStorage, path: Path, company: int, user: int, carriers: CarrierRegistry | None = None
) -> Imported:
    return import_.run(
        path=path,
        company_id=company,
        user_id=user,
        orphans_out=tmp_path / f"orphans-{path.stem}-{company}.txt",
        flows=flows(),
        carriers=carriers if carriers is not None else registry(),
        storage=storage,
    )


def a_run(
    company: int,
    user: int,
    *,
    module: str = MODULE,
    status: str = "done",
    options: dict[str, object] | None = None,
    versions: dict[str, object] | None = None,
    resumed_from: int | None = None,
    partial: dict[str, object] | None = None,
) -> int:
    run_id = insert_run(
        company_id=company,
        fields={
            "module": module,
            "flow_id": FLOW_ID if module == MODULE else FLOW2_ID,
            "options": options or {},
            "versions": versions or {},
            "status": status,
            "created_by_user_id": user,
            "resumed_from_run_id": resumed_from,
        },
    )
    insert_steps(
        company_id=company,
        run_id=run_id,
        steps=[
            {"name": "extract", "position": 0, "status": "done", "data": {"pages": 1}, "partial": None},
            {"name": "judge", "position": 1, "status": "done", "data": {"z": 1}, "partial": partial},
        ],
    )
    return run_id


def edited(path: Path, out: Path, change: Callable[[dict[str, Any]], None]) -> Path:
    """bundle.json 만 고친 묶음(꾸민 묶음 — 그 밖 항목 그대로)."""
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "bundle.json":
                header = cast("dict[str, Any]", json.loads(data))
                change(header)
                data = json.dumps(header, ensure_ascii=False).encode()
            target.writestr(info.filename, data)
    return out


def run_row(header: dict[str, Any], old: int) -> dict[str, Any]:
    return next(row for row in header["rows"]["run_runs"] if row["oldId"] == old)


def around_today() -> Window:
    """오늘(서울) 앞뒤 하루의 rxtest 창 — seed 의 실행은 2026-09 로 되돌려져 밖이다."""
    today = datetime.now(export.SEOUL).date()
    return Window(module=MODULE, first=today - timedelta(days=1), last=today + timedelta(days=1))


def run_count(company: int) -> int:
    return run_page(company_id=company, module=None, status=None, document_id=None, limit=1, offset=0).count


@dataclass(frozen=True)
class Two:
    company: int
    user: int
    x: int  # rxtest done, 판 7
    y: int  # rxtwo done, 판 7(옛 id 가 x 의 판과 같다)
    z: int  # rxtest done, 판 8


def two_modules(company: int) -> Two:
    user = a_customer(company, "gasang-two")
    x = a_run(company, user, versions={"aiSettingId": 7, "aiSetting": "v7"})
    y = a_run(company, user, module=MODULE2, versions={"aiSettingId": 7, "aiSetting": "v7"})
    z = a_run(company, user, versions={"aiSettingId": 8, "aiSetting": "v8"})
    return Two(company=company, user=user, x=x, y=y, z=z)


# ── T4 계약 ──────────────────────────────────────────────────────────


def test_setting_maps_stay_per_module(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    """옛 판 id 7 이 두 모듈에 다 있고 B 의 순번이 모듈마다 다르다(rxtest 901~ · rxtwo 501~) — 판 id 가 섞이면
    빨강(Q17)."""
    a, b = companies
    two = two_modules(a)
    path = tmp_path / "bundle.zip"
    export.run(
        company_id=a,
        selection=RunIds((two.x, two.y, two.z)),
        out=path,
        app_commit="test",
        flows=flows(),
        carriers=registry(),
        storage=storage,
    )
    first, second = RxCarrier(), RxCarrier(next_setting=500)
    done = run_import(tmp_path, storage, path, b, a_customer(b, "gasang-b"), registry(first, second))
    assert [s["name"] for s in first.imported_settings] == ["v7", "v8"]
    assert [s["name"] for s in second.imported_settings] == ["v7"]
    found = {old: find_run(company_id=b, run_id=new) for old, new in done.runs.items()}
    versions = {old: (run.versions["aiSettingId"], run.versions["aiSetting"]) for old, run in found.items() if run}
    assert versions == {two.x: (901, "v901"), two.z: (902, "v902"), two.y: (501, "v501")}


def test_another_modules_setting_id_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """rxtwo 실행이 rxtest 에만 있는 옛 판 8 을 가리키는 꾸민 묶음 — 한 지도로 합쳤다면 통과했을 꼴. 쓰기 0."""
    a, b = companies
    two = two_modules(a)
    path = tmp_path / "bundle.zip"
    export.run(
        company_id=a,
        selection=RunIds((two.x, two.y, two.z)),
        out=path,
        app_commit="test",
        flows=flows(),
        carriers=registry(),
        storage=storage,
    )

    def point_y_at_8(header: dict[str, Any]) -> None:
        run_row(header, two.y)["versions"]["aiSettingId"] = 8

    forged = edited(path, tmp_path / "forged.zip", point_y_at_8)
    with pytest.raises(Refused, match="지도에 없다"):
        run_import(tmp_path, storage, forged, b, a_customer(b, "gasang-b"))
    assert run_count(b) == 0


@pytest.mark.parametrize(
    "extra",
    [{"confirmed_by_user_id": 5}, {"id": 99}, {"company_id": 2}, {"note": "선언 밖"}],
    ids=["person", "id", "company", "undeclared"],
)
def test_forged_module_rows_are_refused_before_writing(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], extra: dict[str, object]
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = export_to(tmp_path, storage, a, RunIds((world.runs["r3"],)))

    def add(header: dict[str, Any]) -> None:
        header["rows"]["modules"][MODULE]["rxtest_settings"][0] |= extra

    forged = edited(path, tmp_path / "forged.zip", add)
    puts = len(storage.put_calls)
    carrier = RxCarrier()
    with pytest.raises(Refused, match="칸"):
        run_import(tmp_path, storage, forged, b, a_customer(b, "gasang-b"), registry(carrier))
    assert run_count(b) == 0 and len(storage.put_calls) == puts and carrier.imported_settings == []


@dataclass
class Spy(RxCarrier):
    """받은 versions·partial 을 적고, partial 의 runRef 를 실행 지도로 다시 쓴다(선언 "partial:judge")."""

    seen: list[tuple[Mapping[str, object], tuple[tuple[str, object], ...]]] = field(
        default_factory=list[tuple[Mapping[str, object], tuple[tuple[str, object], ...]]]
    )

    def rewrite(
        self,
        *,
        options: Mapping[str, object],
        versions: Mapping[str, object],
        results: Sequence[tuple[str, object]],
        steps: Sequence[tuple[str, object]],
        partials: Sequence[tuple[str, object]],
        ids: IdMap,
    ) -> Rewritten:
        self.seen.append((versions, tuple(partials)))
        found = super().rewrite(
            options=options, versions=versions, results=results, steps=steps, partials=partials, ids=ids
        )
        renamed: list[tuple[str, object]] = []
        for name, partial in found.partials:
            value: object = partial
            if isinstance(partial, dict):
                fields = cast("dict[str, object]", partial)
                if isinstance(ref := fields.get("runRef"), int):
                    value = {**fields, "runRef": ids.run_id(ref)}
            renamed.append((name, value))
        return Rewritten(
            options=found.options,
            versions=found.versions,
            results=found.results,
            steps=found.steps,
            partials=tuple(renamed),
        )

    def id_fields(self) -> Mapping[str, tuple[str, ...]]:
        return {**super().id_fields(), "partial:judge": ("runRef",)}


def test_versions_and_partials_go_through_the_carrier(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, b = companies
    user = a_customer(a, "gasang-a")
    first = a_run(a, user, status="failed", partial={"runRef": None, "done": [1]})
    head = a_run(a, user, resumed_from=first, partial=None)
    # partial 에 묶음 안 실행 id(first)를 품은 failed 실행 하나 더(사슬 — head 가 이어 감)
    pointing = a_run(a, user, status="failed", partial={"runRef": first, "done": [1, 2]})
    tail = a_run(a, user, resumed_from=pointing)
    path = export_to(tmp_path, storage, a, RunIds((head, tail)))
    spy = Spy()
    done = run_import(tmp_path, storage, path, b, a_customer(b, "gasang-b"), registry(spy))
    assert [partials for _versions, partials in spy.seen] == [
        (("extract", None), ("judge", {"runRef": None, "done": [1]})),
        (("extract", None), ("judge", None)),
        (("extract", None), ("judge", {"runRef": first, "done": [1, 2]})),
        (("extract", None), ("judge", None)),
    ]
    judge = step_rows(company_id=b, run_id=done.runs[pointing])[1]
    assert judge.partial == {"runRef": done.runs[first], "done": [1, 2]}


@dataclass
class DropsAStep(RxCarrier):
    def rewrite(self, **kwargs: Any) -> Rewritten:
        found = super().rewrite(**kwargs)
        return Rewritten(
            options=found.options,
            versions=found.versions,
            results=found.results,
            steps=found.steps[:-1],
            partials=found.partials,
        )


@dataclass
class TouchesOptions(RxCarrier):
    def rewrite(self, **kwargs: Any) -> Rewritten:
        found = super().rewrite(**kwargs)
        return Rewritten(
            options={**found.options, "zeta": 99},
            versions=found.versions,
            results=found.results,
            steps=found.steps,
            partials=found.partials,
        )


@dataclass
class TouchesSettingId(RxCarrier):
    """있던 정수 aiSettingId 를 같은 모듈 지도 안의 다른 옛 판으로 바꾼다(7 ↔ 8) — 가리면 조용히 다른 판이 된다."""

    def rewrite(self, **kwargs: Any) -> Rewritten:
        found = super().rewrite(**kwargs)
        old = found.versions.get("aiSettingId")
        swapped = {7: 8, 8: 7}.get(old, old) if isinstance(old, int) else old
        return Rewritten(
            options=found.options,
            versions={**found.versions, "aiSettingId": swapped},
            results=found.results,
            steps=found.steps,
            partials=found.partials,
        )


@pytest.mark.parametrize(
    ("carrier", "match"),
    [
        (DropsAStep(), "길이·이름·차례"),
        (TouchesOptions(), "선언 밖 자리\\(options\\)"),
    ],
    ids=["steps", "options"],
)
def test_a_carrier_that_breaks_the_contract_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], carrier: RxCarrier, match: str
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = export_to(tmp_path, storage, a, RunIds((world.runs["r2"], world.runs["r4"])))
    puts = len(storage.put_calls)
    with pytest.raises(Refused, match=match):
        run_import(tmp_path, storage, path, b, a_customer(b, "gasang-b"), registry(carrier))
    assert run_count(b) == 0 and len(storage.put_calls) == puts


@pytest.mark.parametrize("target", ["later", "failed"])
def test_references_in_a_forged_bundle_are_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], target: str
) -> None:
    """Qb11 앞 참조(옛 id 가 더 큰 실행) · Qb8 묶음 안 failed 를 가리킴 — 둘 다 쓰기 앞에서 거절."""
    a, b = companies
    world = seed(storage, a)
    path = export_to(tmp_path, storage, a, RunIds((world.runs["r2"], world.runs["r4"])))

    def point(header: dict[str, Any]) -> None:
        if target == "later":
            run_row(header, world.runs["r3"])["options"] = {"retryFromRunId": world.runs["r4"]}
        else:
            run_row(header, world.runs["r4"])["options"] = {"retryFromRunId": world.runs["r1"]}

    forged = edited(path, tmp_path / "forged.zip", point)
    with pytest.raises(Refused, match="앞 참조" if target == "later" else "done 이 아닌"):
        run_import(tmp_path, storage, forged, b, a_customer(b, "gasang-b"))
    assert run_count(b) == 0


def test_an_unknown_id_is_a_refusal_with_exit_1(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    world = seed(storage, a)
    path = export_to(tmp_path, storage, a, RunIds((world.runs["r3"],)))

    def unknown(header: dict[str, Any]) -> None:
        run_row(header, world.runs["r3"])["versions"]["aiSettingId"] = 99

    forged = edited(path, tmp_path / "forged.zip", unknown)
    user = a_customer(b, "gasang-b")
    with pytest.raises(Refused, match="지도에 없다"):
        run_import(tmp_path, storage, forged, b, user)
    monkeypatch.setattr(  # 명령은 기본값(전역 등록부)으로 부른다 — 시험 등록부를 끼운 run 으로(test_import_runs 꼴)
        import_, "run", functools.partial(import_.run, flows=flows(), carriers=registry(), storage=storage)
    )
    with pytest.raises(CommandError) as caught:
        call_command(
            "import_runs",
            str(forged),
            "--company",
            str(b),
            "--user",
            str(user),
            "--orphans-out",
            str(tmp_path / "orphans-cmd.txt"),
            stdout=StringIO(),
            stderr=StringIO(),
        )
    assert caught.value.returncode == 1 and str(caught.value).startswith("거절: ")  # Refused 갈래(날 예외 아님)
    assert run_count(b) == 0


# ── T9 닫힘·창 ────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["failed", "module", "company", "missing"])
def test_a_carrier_reference_outside_is_refused_or_skipped(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], kind: str
) -> None:
    a, b = companies
    world = seed(storage, a)
    other = a_run(b, a_customer(b, "gasang-b"))
    targets = {
        "failed": world.runs["r1"],
        "module": a_run(a, world.user, module=MODULE2),
        "company": other,
        "missing": other + 1000,
    }
    pointing = a_run(a, world.user, options={"retryFromRunId": targets[kind]})
    a_run(a, world.user)  # 창에 같이 드는 done 하나(plain)
    with pytest.raises(Refused, match="같은 모듈 done 이 아니다"):
        run_export(tmp_path, storage, a, RunIds((pointing,)))
    with pytest.raises(Refused, match="같은 모듈 done 이 아니다"):  # 섞여 있어도 --runs 는 통째 거절
        run_export(tmp_path, storage, a, RunIds((world.runs["r4"], pointing)), name="mixed.zip")
    done = run_export(tmp_path, storage, a, around_today(), name="window.zip")  # 오늘 만든 rxtest: pointing·plain
    assert (done.runs, done.closure, done.out_of_reference) == (1, 0, 1)  # pointing 만 건너뛰고 plain 을 싣는다


def test_the_window_counts_every_status_for_max_runs(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    a, _b = companies
    user = a_customer(a, "gasang-a")
    for status in ("done", "done", "failed", "queued"):
        a_run(a, user, status=status)
    window = around_today()
    with pytest.raises(Refused, match="max-runs"):
        run_export(tmp_path, storage, a, window, max_runs=3)  # done 은 둘이지만 넷을 센다
    done = run_export(tmp_path, storage, a, window, max_runs=4, name="four.zip")
    assert (done.runs, done.skipped) == (2, {"failed": 1, "queued": 1})


def test_a_failed_run_in_the_middle_of_a_chain_resumes_the_same_in_b(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """Qb9: f1 → f2 → d(done). runs 의 규칙은 바로 아래 자식만 본다 — f1 은 아래가 failed 라 A 에서 이어 갈 수 있고 B 도
    같다(옮겨 오며 막거나 넓히지 않음). f2 는 아래가 done 이라 둘 다 막힘."""
    a, b = companies
    user = a_customer(a, "gasang-a")
    f1 = a_run(a, user, status="failed")
    f2 = a_run(a, user, status="failed", resumed_from=f1)
    d = a_run(a, user, resumed_from=f2)
    path = export_to(tmp_path, storage, a, RunIds((d,)))
    done = run_import(tmp_path, storage, path, b, a_customer(b, "gasang-b"))
    before = [resumed_alive(company_id=a, run_id=run) for run in (f1, f2)]
    after = [resumed_alive(company_id=b, run_id=done.runs[run]) for run in (f1, f2)]
    assert before == after == [False, True]


def test_the_commit_check_tells_another_import_of_the_same_bundle_apart(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """R4(RX1a 검증): 같은 묶음을 앞서 다른 넣기가 B 에 커밋했어도, 이 넣기가 지은 새 id 가 없으면 커밋 안 됨(False).
    묶음 열쇠로 보면(회귀) 앞선 넣기의 열쇠가 있어 True 가 된다."""
    a, b = companies
    world = seed(storage, a)
    path = export_to(tmp_path, storage, a, RunIds((world.runs["r3"],)))
    first = run_import(tmp_path, storage, path, b, a_customer(b, "gasang-b"))
    keys = [import_.idempotency_key(first.bundle_id, old) for old in first.runs]
    assert taken_keys(company_id=b, keys=keys)  # 앞선 넣기의 열쇠는 있다
    ours = [max(first.runs.values()) + 1000]  # 이 넣기가 지었다가 되돌려진 id(없음)
    assert import_._committed(b, ours) is False  # pyright: ignore[reportPrivateUsage]
    assert import_._committed(b, list(first.runs.values())) is True  # pyright: ignore[reportPrivateUsage]


def test_a_carrier_that_swaps_the_setting_id_is_refused(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """§1-10: aiSettingId 는 runbundle 만 쓴다. carrier 가 정수 7 을 지도 안의 8 로 바꾸면(둘 다 지도에 있어
    UnknownId 가 아니다) 바이트 견줌이 거절한다 — 가리면(Q18) 실행이 다른 판을 가리킨 채 들어간다."""
    a, b = companies
    two = two_modules(a)
    path = export_to(tmp_path, storage, a, RunIds((two.x, two.z)))
    puts = len(storage.put_calls)
    with pytest.raises(Refused, match="선언 밖 자리\\(versions\\)"):
        run_import(tmp_path, storage, path, b, a_customer(b, "gasang-b"), registry(TouchesSettingId()))
    assert run_count(b) == 0 and len(storage.put_calls) == puts


@dataclass(frozen=True)
class FakeSetting:
    id: int
    name: str
    memo: str
    created_by_user_id: int


def test_an_exhausted_setting_name_is_a_refusal(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]
) -> None:
    """r3: 받는 쪽 판 넣기가 이름 경합으로 다 실패(NameConflict 꼴 — (id, 이름) 아닌 값)하면 CarrierRefused → Refused,
    실행·판 쓰기 0."""
    a, b = companies
    two = two_modules(a)
    inserted: list[dict[str, object]] = []

    def read(*, company_id: int, setting_id: int) -> FakeSetting:
        return FakeSetting(id=setting_id, name=f"v{setting_id}", memo="가상", created_by_user_id=1)

    def conflict(company_id: int, *, row: dict[str, object], user_id: int) -> object:
        inserted.append(row)
        return None  # 다시 시도가 다함

    settings = SettingCarrier(table="rxtwo_settings", shape=FakeSetting, read_settings=read, insert_setting=conflict)
    found = CarrierRegistry()
    found.register(MODULE, RxCarrier())
    found.register(MODULE2, settings)
    path = tmp_path / "bundle.zip"
    export.run(
        company_id=a,
        selection=RunIds((two.y,)),
        out=path,
        app_commit="test",
        flows=flows(),
        carriers=found,
        storage=storage,
    )
    with pytest.raises(Refused, match="이름 다시 시도가 다함"):
        run_import(tmp_path, storage, path, b, a_customer(b, "gasang-b"), found)
    assert inserted == [{"name": "v7", "memo": "가상"}] and run_count(b) == 0
