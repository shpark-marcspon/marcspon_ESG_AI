"""docx 읽기 덤프 명령(발주서 §3 S8, 처분 ⑬): 작은 지은 입력으로 돌아 JSON 꼴·종료 0, 거절 입력도 종료 0 + rejected."""

import json
from pathlib import Path

from esgapi.translation.tests.docx_support import p, tbl, tc, tr, with_body
from esgapi.translation.tools.docx_dump import main


def test_a_read_docx_dumps_the_text_before_and_after_normalizing(tmp_path: Path) -> None:
    source = tmp_path / "in.docx"
    source.write_bytes(with_body(p("****[PAGE 1]****") + tbl(tr(tc("가상")))))
    out = tmp_path / "out.json"
    assert main(["--in", str(source), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "status": "read",
        "text": "****[PAGE 1]****\n[MARKDOWN_TABLE]\n| 가상 |\n| --- |\n",
        "normalizedText": "**[PAGE 1]**\n[MARKDOWN_TABLE]\n| 가상 |\n| --- |\n",
        "skipped": {},
    }


def test_a_refused_docx_dumps_the_rejection_and_still_exits_zero(tmp_path: Path) -> None:
    source = tmp_path / "in.docx"
    source.write_bytes(b"not a zip")
    out = tmp_path / "out.json"
    assert main(["--in", str(source), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "status": "rejected",
        "kind": "not_a_zip",
        "where": "",
        "detail": "BadZipFile",
    }
