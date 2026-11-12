"""docx 읽기 덤프(처분 ⑬ — esg-lab 대조 도구 TR1-o 가 부른다): docx 파일 → `read_docx` → JSON. 실호출 0, 네트워크 0.

    uv run --frozen python -m esgapi.translation.tools.docx_dump --in <docx> --out <json>

출력 = 읽힘 {"status": "read", "text": <정규화 전 글>, "normalizedText": <normalize_structured_tags 한 번 뒤 글>,
"skipped": {태그: 수}} · 거절 {"status": "rejected", "kind", "where", "detail"}. 거절도 종료 0 이다(갈래는 JSON 이
말한다).
TR1-o 는 같은 docx 로 코랩 셀 7 을 돌려 `normalizedText` 를 그 파일 글과 견준다(코랩은 셀 7 에서 정규화를 한 번 한다).
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from esgapi.translation.engines.colab_158.structured import normalize_structured_tags
from esgapi.translation.tools.docx_reader import DocxRejected, read_docx


def dump(data: bytes) -> dict[str, Any]:
    result = read_docx(data)
    if isinstance(result, DocxRejected):
        return {"status": "rejected", "kind": result.kind, "where": result.where, "detail": result.detail}
    return {
        "status": "read",
        "text": result.text,
        "normalizedText": normalize_structured_tags(result.text),
        "skipped": dict(result.skipped),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docx_dump", description="docx → 구조 글 JSON(실호출 0)")
    parser.add_argument("--in", dest="source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    source: Path = args.source
    out: Path = args.out
    out.write_text(json.dumps(dump(source.read_bytes()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
