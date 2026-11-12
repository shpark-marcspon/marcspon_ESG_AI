"""넣기의 zip 문(import_.read_bundle) — S2: DB 없이 파일만 읽는다.

목록 밖 항목·`../x`·`/abs`·겹침·풀린 크기 상한·blob sha·크기 다름·NaN·Infinity → Refused, 읽은 바이트 ≤ 상한.
★ 값은 전부 지어낸 것이다(synthetic).
"""

import json
import zipfile
from contextlib import nullcontext
from pathlib import Path

import pytest

from esgapi.runbundle.calc.bundle import Refused
from esgapi.runbundle.service.actions.import_ import read_bundle
from esgapi.runbundle.tests.calc.test_bundle import DOC, FILE, good

BLOBS = {DOC: b"doc", FILE: b"file"}


def write(path: Path, members: list[tuple[str, bytes]]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, data in members:
            bundle.writestr(name, data)
    return path


def members(text: bytes | None = None) -> list[tuple[str, bytes]]:
    head = text if text is not None else json.dumps(good()).encode()
    return [("bundle.json", head), *((f"blobs/{sha}", data) for sha, data in BLOBS.items())]


def test_a_good_zip_reads(tmp_path: Path) -> None:
    bundle = read_bundle(write(tmp_path / "b.zip", members()), 10_000)
    assert {b.sha256: b.size for b in bundle.blobs} == {
        sha: len(d) for sha, d in BLOBS.items()
    } and bundle.bundle_id == good()["bundleId"]


@pytest.mark.parametrize(
    "extra",
    [("extra.txt", b"x"), ("../x", b"x"), ("/abs", b"x"), (f"blobs/{FILE}", b"file")],
    ids=["outside", "dotdot", "absolute", "duplicate"],
)
def test_members_outside_the_list_are_refused(tmp_path: Path, extra: tuple[str, bytes]) -> None:
    with pytest.warns(UserWarning) if extra[0] == f"blobs/{FILE}" else nullcontext():
        path = write(tmp_path / "b.zip", [*members(), extra])
    with pytest.raises(Refused):
        read_bundle(path, 10_000)


def test_two_bundle_json_are_refused(tmp_path: Path) -> None:
    with pytest.warns(UserWarning):
        path = write(tmp_path / "b.zip", [*members(), ("bundle.json", b"{}")])
    with pytest.raises(Refused):
        read_bundle(path, 10_000)


def test_bytes_that_differ_from_the_header_are_refused(tmp_path: Path) -> None:
    swapped = [("bundle.json", members()[0][1]), (f"blobs/{DOC}", b"dog"), (f"blobs/{FILE}", b"file")]
    with pytest.raises(Refused, match="sha"):
        read_bundle(write(tmp_path / "b.zip", swapped), 10_000)
    longer = [("bundle.json", members()[0][1]), (f"blobs/{DOC}", b"docs"), (f"blobs/{FILE}", b"file")]
    with pytest.raises(Refused, match="크기"):
        read_bundle(write(tmp_path / "c.zip", longer), 10_000)


def test_the_unpacked_size_is_capped(tmp_path: Path) -> None:
    path = write(tmp_path / "b.zip", members())
    total = sum(info.file_size for info in zipfile.ZipFile(path).infolist())
    read_bundle(path, total)
    with pytest.raises(Refused, match="상한"):
        read_bundle(path, total - 1)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_json_constants_are_refused(tmp_path: Path, constant: str) -> None:
    text = json.dumps(good()).replace('"cost_usd": "0.1"', f'"cost_usd": {constant}').encode()
    assert constant.encode() in text
    with pytest.raises(Refused):
        read_bundle(write(tmp_path / "b.zip", members(text)), 10_000)


def test_not_a_zip_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "b.zip"
    path.write_bytes(b"not a zip")
    with pytest.raises(Refused):
        read_bundle(path, 10_000)
