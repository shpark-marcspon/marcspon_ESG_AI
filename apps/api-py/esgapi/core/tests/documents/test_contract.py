"""C1 — 계약 core.doc-artifact@1 의 꼴 검사와 EPOCH 지문(밴드 RP2a ①). 순수 층(DB 0).

지문 시험: EPOCH_PARSER_SHA[EPOCH] 가 지금 services/parser 의 소스·스키마 지문과 같은가. 파서를 고치면 빨개진다 —
고친 밴드가 같은 커밋에서 EPOCH 를 올리고 새 지문을 더한다(contract.py 머리말의 EPOCH 규칙).
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.documents.contract import (
    ARTIFACT_MAX_BYTES,
    CONTRACT,
    EPOCH,
    EPOCH_PARSER_SHA,
    NUL_REPLACEMENT,
    PARSER_TEXT_MAX,
    body_bytes,
    parser_info_of,
    scrub_nul,
    shape_problem,
)
from esgapi.core.tests.artifact_fakes import fake_document, fake_places

PARSER = Path(__file__).resolve().parents[6] / "services/parser"
SHA = "a" * 64


# 지문에 드는 맨 위 파일(QC3 — 응답을 싸는 자리와 의존 판).
ROOT_FILES = ("app.py", "pyproject.toml", "uv.lock")


def fingerprinted(root: Path) -> list[Path]:
    """contract.py 머리말의 지문 범위 — docparse/**/*.py·schemas/*.json·ROOT_FILES, 상대 경로(posix) 차례."""
    found = [*root.glob("docparse/**/*.py"), *root.glob("schemas/*.json"), *(root / n for n in ROOT_FILES)]
    return sorted((p for p in found if p.is_file()), key=lambda p: p.relative_to(root).as_posix())


def parser_fingerprint(root: Path) -> str:
    """contract.py 머리말의 셈(fingerprinted 의 파일마다 경로·NUL·바이트 수·NUL·바이트)."""
    files = fingerprinted(root)
    digest = hashlib.sha256()
    for path in files:
        data = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + str(len(data)).encode() + b"\0" + data)
    return digest.hexdigest()


def test_the_contract_names_and_limits() -> None:
    assert (CONTRACT, EPOCH, ARTIFACT_MAX_BYTES) == ("core.doc-artifact@1", 2, 32 * 1024 * 1024)
    assert sorted(EPOCH_PARSER_SHA) == list(range(1, EPOCH + 1))  # 판마다 지문 하나, 옛 줄을 지우지 않는다


def test_the_epoch_fingerprint_is_the_parser_of_now() -> None:
    assert PARSER.is_dir(), PARSER
    assert EPOCH_PARSER_SHA[EPOCH] == parser_fingerprint(PARSER)


def test_the_fingerprint_moves_when_the_parser_moves(tmp_path: Path) -> None:
    (tmp_path / "docparse").mkdir()
    (tmp_path / "schemas").mkdir()
    (tmp_path / "docparse/a.py").write_text("x = 1\n")
    (tmp_path / "schemas/s.json").write_text("{}")
    before = parser_fingerprint(tmp_path)
    (tmp_path / "docparse/a.py").write_text("x = 1  # 주석만\n")
    assert parser_fingerprint(tmp_path) != before


@pytest.mark.parametrize("name", ROOT_FILES)
def test_the_fingerprint_sees_the_root_files(tmp_path: Path, name: str) -> None:
    """지금 파서의 지문 범위를 tmp 에 베끼고 맨 위 파일 하나의 한 글자를 바꾸면 지문이 달라진다(저장소 0 바뀜)."""
    for path in fingerprinted(PARSER):
        copy = tmp_path / path.relative_to(PARSER)
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(path.read_bytes())
    assert (tmp_path / name).is_file() and parser_fingerprint(tmp_path) == EPOCH_PARSER_SHA[EPOCH]
    data = bytearray((tmp_path / name).read_bytes())
    data[0] = ord("#") if data[0] != ord("#") else ord("!")
    (tmp_path / name).write_bytes(bytes(data))
    assert parser_fingerprint(tmp_path) != EPOCH_PARSER_SHA[EPOCH]


@pytest.mark.parametrize("layout", [1, 2])
def test_both_layouts_pass_the_shape_check(layout: int) -> None:
    document, places = fake_document(SHA, layout=layout), fake_places(SHA, layout=layout)
    assert ("layout" in document["parser"]) == (layout == 2)  # 판 1 은 칸이 없다 = 1
    assert shape_problem(document, places, layout=layout, sha256=SHA) is None


def _broken(change: str) -> tuple[dict[str, Any], dict[str, Any]]:
    document, places = fake_document(SHA), fake_places(SHA)
    if change == "layout":
        del document["parser"]["layout"]
    elif change == "places_layout":
        places["parser"]["layout"] = 3
    elif change == "sha":
        document["source"]["sha256"] = "b" * 64
    elif change == "places_sha":
        places["source"]["sha256"] = "b" * 64
    elif change == "unit":
        places["unit"] = "codepoint"
    elif change == "pages":
        document["source"]["page_count"] = 0
    elif change == "blocks":
        document["blocks"] = {}
    return document, places


@pytest.mark.parametrize("change", ["layout", "places_layout", "sha", "places_sha", "unit", "pages", "blocks"])
def test_a_broken_shape_is_refused(change: str) -> None:
    document, places = _broken(change)
    assert shape_problem(document, places, layout=2, sha256=SHA) is not None


def test_missing_parts_are_refused() -> None:
    assert shape_problem(fake_document(SHA), None, layout=2, sha256=SHA) is not None
    assert shape_problem([], fake_places(SHA), layout=2, sha256=SHA) is not None


def test_body_bytes_is_compact_utf8() -> None:
    assert body_bytes({"a": "가"}, {}) == len('{"a":"가"}'.encode()) + 2


# ── NUL·이름 칸(QC3) ──


def test_scrub_nul_replaces_every_string_and_keeps_utf16_length() -> None:
    value = {"a\x00": ["x\x00y", {"t": "\x00\x00"}], "n": 3, "b": None, "c": "가"}
    clean, count = scrub_nul(value)
    assert count == 4 and "\x00" not in json.dumps(clean, ensure_ascii=False)
    assert clean == {"a\ufffd": ["x\ufffdy", {"t": "\ufffd\ufffd"}], "n": 3, "b": None, "c": "가"}
    assert len(NUL_REPLACEMENT.encode("utf-16-le")) == len("\x00".encode("utf-16-le")) == 2  # offset 이 안 밀린다
    assert value["a\x00"] == ["x\x00y", {"t": "\x00\x00"}]  # 사본 — 받은 것은 그대로
    assert scrub_nul({"t": "깨끗"}) == ({"t": "깨끗"}, 0)


def test_long_parser_texts_are_clipped_inside_the_column() -> None:
    document = fake_document(SHA)
    document["parser"] |= {"name": "n" * (PARSER_TEXT_MAX + 1), "version": "v" * PARSER_TEXT_MAX}
    info = parser_info_of(document, layout=2)
    assert info.name == "n" * (PARSER_TEXT_MAX - 1) + "…" and len(info.name) == PARSER_TEXT_MAX
    assert info.version == "v" * PARSER_TEXT_MAX  # 길이 안이면 그대로
