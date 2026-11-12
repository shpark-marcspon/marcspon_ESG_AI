"""옮겨 온 꾸러미가 제자리에 섰는지 (원본에 없던 테스트. 원본 PDF 없이 돈다).

스키마 사본이 원본과 같은 글자인지, 환경 변수 없이도 읽히는지, 테스트용 PDF 도구의 글자 너비가 엔진의 걸음과 같은지,
열지 못하는 PDF 가 오류로 끝나는지, 산출에 적히는 분해기의 이름과 판이 그대로인지를 본다.
"""

import hashlib
import json
import os
import subprocess
import sys

import pytest

import docparse
from docparse import config
from docparse.cli import main
from docparse.document import ParseError, parse_pdf, parse_pdf_places

from . import pdfbuild
from .conftest import put, seam

# 두 스키마 파일의 sha256(처음은 esg-lab `schemas/` 커밋 2e2c2c4 의 것, 밴드 TRD1 이 선택 칸을 더한 판). 정본이 된 뒤(밴드 PX)에도
# 스키마를 고치면 빨개져서, 고칠 때 schemas/README.md 의 값(과 필수 칸을 바꾸면 schema_version)을 같이 고치게 한다.
SCHEMA_SHA256 = {
    "document.schema.json": "92eda2aa54470964ddc3a6cce941c7b0db20d35df5e89ccf7fcbd25bdd0520bf",
    "char-places.schema.json": "5212aa467c3a33c9676dad1f918e225474a1908367f0c3277eb84cbd0934dcb0",
    "chart-labels.schema.json": "f2b7a3f437ef10a4d3aa9b606997635bec222e48ece9e13fe43d864b96b8c3f4",  # 밴드 CHL1
}
ENV_NAMES = ("PARSER_GOLD_DIR", "PARSER_REPORTS_DIR")


# ── 1. 스키마 사본 ──────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(SCHEMA_SHA256))
def test_schema_copy_is_byte_identical_to_the_original(name):
    path = config.PARSER_ROOT / "schemas" / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == SCHEMA_SHA256[name]


def test_config_points_at_the_schema_copies():
    assert config.SCHEMA_PATH == config.PARSER_ROOT / "schemas" / "document.schema.json"
    assert config.PLACES_SCHEMA_PATH == config.PARSER_ROOT / "schemas" / "char-places.schema.json"
    assert config.CHARTS_SCHEMA_PATH == config.PARSER_ROOT / "schemas" / "chart-labels.schema.json"


def test_schemas_readme_records_both_hashes():
    readme = (config.PARSER_ROOT / "schemas" / "README.md").read_text(encoding="utf-8")
    for name, digest in SCHEMA_SHA256.items():
        assert digest in readme, f"schemas/README.md 에 {name} 의 sha256 이 없다"


# ── 2. 환경 변수 없이 ───────────────────────────────────────────────────


def test_modules_import_without_path_env_vars():
    # 새 인터프리터에서 읽는다: 이미 읽힌 모듈을 다시 읽으면(`importlib.reload`) 예외 클래스가 새로 생겨
    # 같은 실행의 다른 테스트가 쥐고 있는 `MissingPathError` 와 어긋난다.
    env = {k: v for k, v in os.environ.items() if k not in ENV_NAMES}
    code = (
        "import os, docparse.config, docparse.cli, docparse.score\n"
        "assert not any(k in os.environ for k in ('PARSER_GOLD_DIR', 'PARSER_REPORTS_DIR'))\n"
        "print('ok')\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=config.PARSER_ROOT, env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


@pytest.mark.parametrize(
    "call, env_name",
    [
        (lambda: config.reports_dir(), "PARSER_REPORTS_DIR"),
        (lambda: config.gold_dir(), "PARSER_GOLD_DIR"),
        (lambda: config.report_path("kb"), "PARSER_REPORTS_DIR"),
    ],
    ids=["reports_dir", "gold_dir", "report_path"],
)
def test_path_functions_fail_with_the_env_var_name(monkeypatch, call, env_name):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(config.MissingPathError, match=env_name):
        call()


def test_empty_env_var_counts_as_missing(monkeypatch):
    monkeypatch.setenv("PARSER_REPORTS_DIR", "")
    with pytest.raises(config.MissingPathError, match="PARSER_REPORTS_DIR"):
        config.reports_dir()


def test_path_functions_follow_the_env_vars(monkeypatch, tmp_path):
    monkeypatch.setenv("PARSER_REPORTS_DIR", str(tmp_path / "r"))
    monkeypatch.setenv("PARSER_GOLD_DIR", str(tmp_path / "g"))
    assert config.reports_dir() == tmp_path / "r" and config.gold_dir() == tmp_path / "g"
    assert config.report_path("kb") == tmp_path / "r" / "kb_2025_kor.pdf"


def test_score_command_without_reports_env_is_an_error(monkeypatch, tmp_path, capsys):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    gold = tmp_path / "gold"
    gold.mkdir()
    fake = {"id": "fake", "report": "kb", "page": 1, "bbox": [0, 0, 10, 10], "grid": [["a", "1"]]}
    (gold / "fake.json").write_text(json.dumps(fake), encoding="utf-8")
    assert main(["score", "--gold", str(gold)]) == 2
    assert "PARSER_REPORTS_DIR" in capsys.readouterr().err


# ── 3. pdfbuild 의 너비표와 엔진의 걸음 ─────────────────────────────────

ASCII_GLYPHS = [chr(c) for c in range(0x21, 0x7F)]


def test_width_table_covers_printable_ascii():
    assert all(c in pdfbuild.HELV_WIDTHS for c in ASCII_GLYPHS) and len(ASCII_GLYPHS) == 94


def test_helvetica_width_table_matches_engine_advance():
    """글 객체 하나로 「<글자>H」 를 놓으면 H 의 원점은 앞 글자의 걸음만큼 간 자리다. 그 걸음이 너비표와 같다."""
    size, x = 10, 50
    doc = pdfbuild.Doc()
    for c in ASCII_GLYPHS:
        doc.new_page(width=200, height=100).insert_text((x, 50), c + "H", fontsize=size)
    opened = seam(doc)
    wrong = {}
    for i, c in enumerate(ASCII_GLYPHS):
        chars = [
            ch
            for b in opened[i].get_text_blocks(chars=True)
            for ln in b["lines"]
            for s in ln["spans"]
            for ch in s["chars"]
        ]
        assert [ch["c"] for ch in chars] == [c, "H"], (c, chars)
        advance = chars[1]["bbox"][0] - x  # H 의 상자 왼쪽은 H 의 원점이다 (H 는 원점 왼쪽으로 나오지 않는다)
        expected = pdfbuild.HELV_WIDTHS[c] * size / 1000
        if abs(advance - expected) > 0.002:
            wrong[c] = (round(advance, 4), expected)
    assert not wrong, f"너비표와 엔진의 걸음이 다르다 (엔진, 너비표): {wrong}"


def test_text_length_is_the_sum_of_the_width_table():
    assert pdfbuild.text_length("1,304", fontsize=8) == pytest.approx((556 + 278 + 556 + 556 + 556) * 8 / 1000)


# ── 4. 열지 못하는 PDF ──────────────────────────────────────────────────


def _one_page_doc():
    doc = pdfbuild.Doc()
    put(doc.new_page(width=300, height=200), 40, 60, "synthetic text page")
    return doc


def test_password_protected_pdf_is_a_parse_error(tmp_path):
    pdf = tmp_path / "locked.pdf"
    _one_page_doc().save(pdf, user_pw="synthetic-user", owner_pw="synthetic-owner")
    with pytest.raises(ParseError, match="암호"):
        parse_pdf(pdf)


def test_same_pdf_without_password_parses(tmp_path):
    # 위 테스트가 「암호 때문에」 실패한 것임을 가르는 짝: 암호만 빼면 읽힌다.
    pdf = tmp_path / "open.pdf"
    _one_page_doc().save(pdf)
    assert [b["text"] for b in parse_pdf(pdf)["blocks"]] == ["synthetic text page"]


@pytest.mark.parametrize(
    "data", [b"", b"this is not a pdf\n", b"%PDF-1.4\n%%EOF\n"], ids=["empty", "text", "header_only"]
)
def test_broken_bytes_are_a_parse_error(tmp_path, data):
    pdf = tmp_path / "broken.pdf"
    pdf.write_bytes(data)
    with pytest.raises(ParseError):
        parse_pdf(pdf)


def test_truncated_pdf_is_a_parse_error(tmp_path):
    whole = _one_page_doc().tobytes()
    pdf = tmp_path / "truncated.pdf"
    pdf.write_bytes(whole[:40])
    with pytest.raises(ParseError):
        parse_pdf(pdf)


# ── 5. 분해기의 이름과 판 ───────────────────────────────────────────────


def test_parser_name_and_version_are_pinned(tmp_path):
    assert docparse.__version__ == "0.1.0"
    pdf = tmp_path / "one.pdf"
    _one_page_doc().save(pdf)
    doc, places = parse_pdf_places(pdf)
    # 스키마가 이름을 못 박았고 골든 산출에도 이 값이 적혀 있다. 바뀌면 골든과 달라진다.
    assert doc["parser"] == {
        "name": "docparse",
        "version": "0.1.0",
        "table_strategy": "auto",
        "llm_used": False,
        "ocr_used": False,
    }
    assert places["parser"] == {"name": "docparse", "version": "0.1.0", "table_strategy": "auto"}
    assert parse_pdf(pdf, strategy="text")["parser"]["table_strategy"] == "text"
