"""import_runs 명령: 쓰는 법이 틀리면 2, 거절이면 1(쓰기 0), 넣으면 0 과 옛 → 새 실행 지도, --dry-run 은 셈만.
실제 등록부(전역 REGISTRY·CARRIERS)로는 시험 흐름의 묶음이 문 ⓑ 에서 거절된다. ★ 값은 전부 지어낸 것이다(synthetic).
"""

import functools
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from esgapi.core.flows.carriers import UnknownId
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.service.actions import export, import_
from esgapi.runbundle.service.actions.export import RunIds
from esgapi.runbundle.service.actions.import_ import Imported, ImportFailed
from esgapi.runbundle.tests.support import World, a_customer, carriers, flows, seed
from esgapi.runs.service.selectors.runs import run_page

pytestmark = pytest.mark.django_db(transaction=True)


def run(*args: str) -> tuple[str, str]:
    out, err = StringIO(), StringIO()
    call_command("import_runs", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def bundle(tmp_path: Path, storage: FakeStorage, world: World) -> Path:
    out = tmp_path / "b.zip"
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


def count(company: int) -> int:
    return run_page(company_id=company, module=None, status=None, document_id=None, limit=1, offset=0).count


@pytest.mark.parametrize(
    "args",
    [
        ["b.zip", "--company", "x", "--user", "1", "--orphans-out", "o"],
        ["b.zip", "--company", "1", "--user", "-1", "--orphans-out", "o"],
        ["b.zip", "--company", "1", "--user", "1", "--orphans-out", "o", "--max-bytes", "0"],
    ],
    ids=["회사 꼴", "사람 꼴", "max-bytes"],
)
def test_usage_errors_exit_2(args: list[str]) -> None:
    with pytest.raises(CommandError) as caught:
        run(*args)
    assert caught.value.returncode == 2


def test_the_real_registries_refuse_a_test_flow(tmp_path: Path, companies: tuple[int, int]) -> None:
    storage = FakeStorage()
    a, b = companies
    path = bundle(tmp_path, storage, seed(storage, a))
    user = a_customer(b, "gasang-b")
    with pytest.raises(CommandError) as caught:
        run(str(path), "--company", str(b), "--user", str(user), "--orphans-out", str(tmp_path / "o.txt"))
    assert caught.value.returncode == 1 and "흐름" in str(caught.value)
    assert count(b) == 0


def test_dry_run_then_import(tmp_path: Path, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    storage = FakeStorage()
    a, b = companies
    world = seed(storage, a)
    path = bundle(tmp_path, storage, world)
    user = a_customer(b, "gasang-b")
    monkeypatch.setattr(
        import_, "run", functools.partial(import_.run, flows=flows(), carriers=carriers(), storage=storage)
    )
    args = [str(path), "--company", str(b), "--user", str(user), "--orphans-out", str(tmp_path / "o.txt")]
    stdout, _err = run(*args, "--dry-run")
    assert stdout.startswith("(dry-run)") and "run_runs=4" in stdout and count(b) == 0
    stdout, _err = run(*args)
    assert count(b) == 4 and stdout.count(" → ") == 4
    assert not (tmp_path / "o.txt").exists()
    with pytest.raises(CommandError) as caught:
        run(*args)
    assert caught.value.returncode == 1 and "이미" in str(caught.value)


def test_an_unexpected_error_is_one_line_and_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """② 검증 R3: 거절 밖 예외(지도 밖 id 등 — 블록이 되돌림)는 한 줄 + 종료 1, --verbose 면 그대로 올라간다."""

    def broken(**_kwargs: object) -> Imported:
        raise UnknownId("실행 7 이 묶음의 지도에 없다")

    monkeypatch.setattr(import_, "run", broken)
    args = [str(tmp_path / "b.zip"), "--company", "1", "--user", "1", "--orphans-out", str(tmp_path / "o.txt")]
    with pytest.raises(CommandError) as caught:
        run(*args)
    assert (
        caught.value.returncode == 1 and str(caught.value) == "거절(쓰기 0) — UnknownId: 실행 7 이 묶음의 지도에 없다"
    )
    with pytest.raises(UnknownId):
        run(*args, "--verbose")


def test_keys_go_to_stderr_when_the_orphans_file_was_not_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """③ S2: 올린 뒤 실패에 orphans 쓰기도 실패했으면(또는 커밋 여부를 모르면) 키만 stderr 로 + 종료 1."""

    def broken(**_kwargs: object) -> Imported:
        raise ImportFailed(["runs/7/8/out/out.json"], written=False, rolled_back=True)

    monkeypatch.setattr(import_, "run", broken)
    err = StringIO()
    args = [str(tmp_path / "b.zip"), "--company", "1", "--user", "1", "--orphans-out", str(tmp_path / "o.txt")]
    with pytest.raises(CommandError) as caught:
        call_command("import_runs", *args, stdout=StringIO(), stderr=err)
    assert caught.value.returncode == 1 and "stderr" in str(caught.value) and "쓰기 0" not in str(caught.value)
    assert err.getvalue().strip().splitlines() == [import_.ROLLED_BACK_HEAD, "runs/7/8/out/out.json"]


def test_unknown_commit_keys_go_to_stderr_under_their_own_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """③ 검증 B1: 커밋 여부 확인 불가 갈래는 파일에 적었어도 stderr 에 「확인 불가 키(지우지 말 것)」 머리로 낸다."""

    def unknown(**_kwargs: object) -> Imported:
        raise ImportFailed(["runs/7/8/out/out.json"], written=True, rolled_back=None)

    monkeypatch.setattr(import_, "run", unknown)
    err = StringIO()
    args = [str(tmp_path / "b.zip"), "--company", "1", "--user", "1", "--orphans-out", str(tmp_path / "o.txt")]
    with pytest.raises(CommandError) as caught:
        call_command("import_runs", *args, stdout=StringIO(), stderr=err)
    assert caught.value.returncode == 1 and "커밋 여부 확인 불가 — 지우기 전에 확인" in str(caught.value)
    assert err.getvalue().strip().splitlines() == [import_.UNKNOWN_HEAD, "runs/7/8/out/out.json"]


def test_a_confirmed_commit_with_an_error_warns_and_exits_0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """③ S1: 커밋 단계 예외 뒤 커밋이 확인되면 경고 한 줄, 종료 0, 지도는 그대로 찍는다."""

    def committed(**_kwargs: object) -> Imported:
        return Imported(
            bundle_id="b", dry_run=False, counts={"run_runs": 1}, runs={3: 30}, commit_error="OperationalError"
        )

    monkeypatch.setattr(import_, "run", committed)
    out, err = StringIO(), StringIO()
    args = [str(tmp_path / "b.zip"), "--company", "1", "--user", "1", "--orphans-out", str(tmp_path / "o.txt")]
    call_command("import_runs", *args, stdout=out, stderr=err)
    assert "커밋됐다" in err.getvalue() and "실행 3 → 30" in out.getvalue()
