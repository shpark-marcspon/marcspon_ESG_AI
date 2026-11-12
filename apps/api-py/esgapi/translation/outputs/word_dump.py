"""Word 쓰기 덤프(처분 ⑬ — esg-lab 대조 도구 TR1-o 가 부른다). 코랩과 같은 원시 입력 → Word + 읽기 JSON. 실호출 0,
네트워크 0. docx 를 직접 import 하지 않는다(짓기는 docx_bilingual·docx_qa, 읽기는 readback).

    uv run --frozen python -m esgapi.translation.outputs.word_dump bilingual --text <txt> --out <docx>
    uv run --frozen python -m esgapi.translation.outputs.word_dump qa --sections <json> --variant <라벨> --out <docx>

`--sections` 는 코랩 `all_sections` 꼴의 JSON 목록: `[{"page_num": n, "content": "…", "issues": [{"issue_type",
"severity", "original_span", "suggestion", "reason"}…]}…]`(이슈 키는 코랩 dict 그대로).
지으면 `<docx>` 와 같은 자리 `<docx>.read.json`(`{"status": "built", …readback}`)을 쓰고, 짓다 실패하면 `<docx>` 없이
`<docx>.read.json` 에 `{"status": "failed", "message"}`. 둘 다 종료 0 이다(갈래는 JSON 이 말한다).
TR1-o 는 같은 입력으로 코랩 `translated_to_docx`(셀 54)·`build_qa_docx`(셀 63)를 돌려 같은 readback 꼴과 견준다.
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from esgapi.translation.outputs.docx_bilingual import render_bilingual
from esgapi.translation.outputs.docx_qa import QaIssue, QaSection, render_qa
from esgapi.translation.outputs.failures import WordFailed
from esgapi.translation.outputs.readback import read_word


def sections_from_json(raw: Any) -> list[QaSection]:
    items: list[dict[str, Any]] = raw
    return [
        QaSection(
            page_num=int(item["page_num"]),
            content=str(item["content"]),
            issues=[QaIssue(**issue) for issue in item["issues"]],
        )
        for item in items
    ]


def write(content: bytes | WordFailed, out: Path) -> None:
    read_json = out.with_name(out.name + ".read.json")
    if isinstance(content, WordFailed):
        payload: dict[str, Any] = {"status": "failed", "message": content.message}
    else:
        out.write_bytes(content)
        payload = {"status": "built", **read_word(content)}
    read_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="word_dump", description="코랩 원시 입력 → Word + 읽기 JSON(실호출 0)")
    commands = parser.add_subparsers(dest="command", required=True)
    bilingual = commands.add_parser("bilingual", help="병기 txt → 병기 Word(셀 54)")
    bilingual.add_argument("--text", required=True, type=Path)
    bilingual.add_argument("--out", required=True, type=Path)
    qa = commands.add_parser("qa", help="all_sections JSON → 검수 Word(셀 63)")
    qa.add_argument("--sections", required=True, type=Path)
    qa.add_argument("--variant", required=True)
    qa.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    out: Path = args.out
    if args.command == "bilingual":
        text_path: Path = args.text
        write(render_bilingual(text_path.read_text(encoding="utf-8")), out)
    else:
        sections_path: Path = args.sections
        variant: str = args.variant
        sections = sections_from_json(json.loads(sections_path.read_text(encoding="utf-8")))
        write(render_qa(sections, variant), out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
