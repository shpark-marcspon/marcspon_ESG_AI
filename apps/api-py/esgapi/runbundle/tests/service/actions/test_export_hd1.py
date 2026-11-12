"""내보내기 다지기 HD1(runbundle/service/actions/export.py)를 진짜 DB·가짜 저장소로 잰다(발주서 §3 T3·T4·★b).

    T3 R1  풀린 합(blob + bundle.json) > 넣기 기본 상한(이음매로 작게 — 처음 내보낸 묶음의 합에서 짓는다) → Refused ·
           --out·임시 파일 0(blob 만으로 넘음 · bundle.json 을 더해 넘음 두 갈래) · 쓰는 도중 문서·파일 바이트가 행과
           다르면 Refused · --out·.part 0
    T4 R2  고른 실행이 없으면 실행 0 묶음을 짓지 않는다(★h — BASE 그대로)
    ★b     정상 내보내기의 머리 tables 는 꼭 실을 칸(REQUIRED_COLUMNS)을 늘 싣는다(model_columns 에서)
★ 값은 전부 지어낸 것이다(synthetic).
"""

from pathlib import Path

import pytest

from esgapi.core.service.selectors.documents import find_document
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.calc.bundle import REQUIRED_COLUMNS, TABLES, Refused
from esgapi.runbundle.service.actions import _common, export
from esgapi.runbundle.service.actions.export import Exported, RunIds
from esgapi.runbundle.tests.support import World, carriers, flows, seed


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


def run_export(tmp_path: Path, storage: FakeStorage, world: World, *, name: str = "bundle.zip") -> Exported:
    return export.run(
        company_id=world.company,
        selection=RunIds((world.runs["r2"], world.runs["r4"])),
        out=tmp_path / name,
        app_commit="test",
        flows=flows(),
        carriers=carriers(),
        storage=storage,
    )


def test_the_export_always_carries_the_required_columns() -> None:
    """감독 C0 조건: 정상 내보내기의 tables(_tables(model_columns())) ⊇ REQUIRED_COLUMNS — 표마다(DB 0)."""
    tables = export._tables(_common.model_columns())  # pyright: ignore[reportPrivateUsage]
    assert set(tables) == set(TABLES)
    missing = {table: sorted(REQUIRED_COLUMNS[table] - set(tables[table])) for table in TABLES}
    assert missing == {table: [] for table in TABLES}


@pytest.mark.django_db(transaction=True)
def test_a_bundle_past_the_import_default_limit_is_not_written(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    world = seed(storage, companies[0])
    first = run_export(tmp_path, storage, world, name="first.zip")
    total = first.json_bytes + first.blob_bytes  # 상한을 지어내지 않고 처음 묶음의 풀린 합에서
    monkeypatch.setattr(export, "DEFAULT_MAX_BYTES", total - 1)
    with pytest.raises(Refused, match="넣기 기본 상한을 넘는다"):
        run_export(tmp_path, storage, world, name="over.zip")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["first.zip"]  # --out·.part 0
    monkeypatch.setattr(export, "DEFAULT_MAX_BYTES", first.blob_bytes - 1)  # blob 만으로 넘음(bundle.json 앞에서)
    with pytest.raises(Refused, match="넣기 기본 상한을 넘는다"):
        run_export(tmp_path, storage, world, name="over.zip")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["first.zip"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("which", ["document", "file"])
def test_bytes_that_differ_while_writing_leave_no_file(
    tmp_path: Path, storage: FakeStorage, companies: tuple[int, int], which: str
) -> None:
    """흘려 쓰는 도중의 거절(문서 바이트 다름 · 파일 sha 다름)도 임시 파일을 지운다 — 거절은 파일 0(M3)."""
    world = seed(storage, companies[0])
    if which == "file":
        key = next(key for key in storage.objects if key.endswith("/out/out.json"))
        storage.put(key, b'{"ok":"no"}')  # 크기는 같고 sha 가 다르다 — 문서 넷을 쓴 뒤의 거절
    else:
        d1 = find_document(company_id=world.company, document_id=world.documents["d1"])  # r4 의 문서(묶음 안)
        assert d1 is not None
        storage.put(d1.storage_key, storage.objects[d1.storage_key][0] + b" more")  # 크기가 행과 다르다
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(Refused, match="바이트가 행과 다르다"):
        export.run(
            company_id=world.company,
            selection=RunIds((world.runs["r2"], world.runs["r4"])),
            out=out / "bundle.zip",
            app_commit="test",
            flows=flows(),
            carriers=carriers(),
            storage=storage,
        )
    assert list(out.iterdir()) == []


@pytest.mark.django_db(transaction=True)
def test_no_runs_picked_makes_no_bundle(tmp_path: Path, storage: FakeStorage, companies: tuple[int, int]) -> None:
    world = seed(storage, companies[0])
    with pytest.raises(Refused, match="고른 실행이 모두 참조 밖이다"):
        export.run(
            company_id=world.company,
            selection=RunIds(()),
            out=tmp_path / "empty.zip",
            app_commit="test",
            flows=flows(),
            carriers=carriers(),
            storage=storage,
        )
    assert list(tmp_path.iterdir()) == []
