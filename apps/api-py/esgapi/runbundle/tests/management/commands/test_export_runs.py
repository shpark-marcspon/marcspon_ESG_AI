"""export_runs 명령: 쓰는 법이 틀리면 2, 거절이면 1(파일 0), 쓰면 0 과 한 줄(값·키·사람 0). 실제 등록부(전역 CARRIERS
— 이 밴드 뒤 0)로는 모듈 실행이 거절된다(닫힌 기본). 시험 레지스트리는 export.run 을 부분 적용으로 갈아 끼워 넘긴다.
★ 값은 전부 지어낸 것이다(synthetic).
"""

import functools
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runbundle.service.actions import export
from esgapi.runbundle.tests.support import carriers, flows, seed

pytestmark = pytest.mark.django_db(transaction=True)


def run(*args: str) -> tuple[str, str]:
    out, err = StringIO(), StringIO()
    call_command("export_runs", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    "args",
    [
        ["--company", "x", "--runs", "1", "--out", "o.zip"],
        ["--company", "1", "--out", "o.zip"],
        ["--company", "1", "--runs", "1", "--module", "m", "--from", "2026-10-01", "--to", "2026-10-02", "--out", "o"],
        ["--company", "1", "--runs", "1,x", "--out", "o.zip"],
        ["--company", "1", "--module", "m", "--from", "2026-13-01", "--to", "2026-10-02", "--out", "o.zip"],
        ["--company", "1", "--runs", "1", "--out", "o.zip", "--max-runs", "0"],
    ],
    ids=["회사 꼴", "고름 없음", "고름 둘", "runs 꼴", "날짜 꼴", "max-runs"],
)
def test_usage_errors_exit_2(args: list[str]) -> None:
    with pytest.raises(CommandError) as caught:
        run(*args)
    assert caught.value.returncode == 2


def test_a_real_module_has_no_carrier_yet(
    tmp_path: Path, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = FakeStorage()
    world = seed(storage, companies[0])
    monkeypatch.setattr(export.document_services, "default_storage", lambda: storage)
    out = tmp_path / "b.zip"
    with pytest.raises(CommandError) as caught:
        run("--company", str(world.company), "--runs", str(world.runs["r3"]), "--out", str(out))
    assert caught.value.returncode == 1 and "carrier" in str(caught.value)
    assert not out.exists()


def test_a_bundle_is_written_and_summarised(
    tmp_path: Path, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = FakeStorage()
    world = seed(storage, companies[0])
    monkeypatch.setattr(
        export, "run", functools.partial(export.run, flows=flows(), carriers=carriers(), storage=storage)
    )
    monkeypatch.delenv("APP_COMMIT", raising=False)
    out = tmp_path / "b.zip"
    stdout, stderr = run(
        "--company", str(world.company), "--runs", f"{world.runs['r2']},{world.runs['r4']}", "--out", str(out)
    )
    assert out.exists() and "APP_COMMIT" in stderr
    assert "실행 4(닫힘 2)" in stdout and "sha256=" in stdout and "run_runs=4" in stdout
    assert "gasang" not in stdout and "companies/" not in stdout
    with pytest.raises(CommandError) as caught:  # 있으면 거절
        run("--company", str(world.company), "--runs", str(world.runs["r3"]), "--out", str(out))
    assert caught.value.returncode == 1


def test_an_unexpected_error_is_one_line_and_exit_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """② 검증 R3: 거절 밖 예외는 한 줄 + 종료 1(파일 0), --verbose 면 그대로 올라간다."""

    def broken(**_kwargs: object) -> object:
        raise TypeError("지어낸 꼴 오류")

    monkeypatch.setattr(export, "run", broken)
    out = tmp_path / "b.zip"
    with pytest.raises(CommandError) as caught:
        run("--company", "1", "--runs", "1", "--out", str(out))
    assert caught.value.returncode == 1 and str(caught.value) == "거절(쓰기 0) — TypeError: 지어낸 꼴 오류"
    assert not out.exists()
    with pytest.raises(TypeError):
        run("--company", "1", "--runs", "1", "--out", str(out), "--verbose")
