"""명령줄 진입점: parse, score, render."""

import argparse
import json
import sys
from pathlib import Path

from .document import (
    LAYOUTS,
    ParseError,
    parse_pdf,
    parse_pdf_charts,
    parse_pdf_places,
    validate,
    validate_charts,
    validate_places,
)
from .render import render_pages
from .score import ScoreError, aggregate, format_report, score_gold
from .tables import STRATEGIES


def parse_pages(spec):
    """'3,10-12' → [3, 10, 11, 12]"""
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def cmd_parse(a):
    pages = parse_pages(a.pages) if a.pages else None
    places = labels = None
    # 판은 2 일 때만 넘긴다: 기본 판의 부르는 꼴은 그대로다.
    extra = {"layout": a.layout} if a.layout != 1 else {}
    if a.charts:
        # 도표 라벨은 판 2 에만(밴드 CHL1). 같은 열린 PDF 로 분해와 라벨을 낸다.
        if a.layout != 2:
            raise ParseError("--charts 는 --layout 2 에만 쓴다")
        doc, places, labels = parse_pdf_charts(
            a.pdf, pages=pages, strategy=a.strategy, dedupe_overdrawn=a.dedupe_overdrawn, want_places=a.places
        )
    elif a.places:
        doc, places = parse_pdf_places(
            a.pdf, pages=pages, strategy=a.strategy, dedupe_overdrawn=a.dedupe_overdrawn, **extra
        )
    else:
        doc = parse_pdf(a.pdf, pages=pages, strategy=a.strategy, dedupe_overdrawn=a.dedupe_overdrawn, **extra)
    errors = validate(doc)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "document.json"
    target.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    if places is not None:
        # 곁 파일. document.json 은 이 옵션과 무관하게 같은 글자다.
        errors = errors + [f"char-places: {e}" for e in validate_places(places)]
        (out / "char-places.json").write_text(
            json.dumps(places, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    if labels is not None:
        # 곁 파일(밴드 CHL1). document.json·char-places.json 은 이 옵션과 무관하게 같은 글자다.
        errors = errors + [f"chart-labels: {e}" for e in validate_charts(labels)]
        (out / "chart-labels.json").write_text(
            json.dumps(labels, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    rendered = []
    if a.render:
        rendered = render_pages(a.pdf, out / "pages", pages=pages, dpi=a.dpi)
    by_status = {}
    for t in doc["tables"]:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
    by_method = {}
    for t in doc["tables"]:
        by_method[t["method"]] = by_method.get(t["method"], 0) + 1
    summary = (
        {}
        if places is None
        else {
            "char_places": {
                "out": str(out / "char-places.json"),
                "containers": len(places["containers"]),
                "unlinked": len(places["unlinked"]),
            }
        }
    )
    if labels is not None:
        summary["chart_labels"] = {
            "out": str(out / "chart-labels.json"),
            "charts": len(labels["charts"]),
            "words": len(labels["words"]),
            "unlinked": len(labels["unlinked"]),
        }
    print(
        json.dumps(
            {
                "out": str(target),
                "pages_parsed": len(doc["pages"]),
                "page_count": doc["source"]["page_count"],
                "pages_without_text_layer": [p["page"] for p in doc["pages"] if p["text_layer"] == "none"],
                "sections": len(doc["sections"]),
                "blocks": len(doc["blocks"]),
                "tables": len(doc["tables"]),
                "tables_by_status": by_status,
                "tables_by_method": by_method,
                "rendered_pages": len(rendered),
                "schema_valid": not errors,
                "schema_errors": errors[:20],
                **summary,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 1 if errors else 0


def cmd_score(a):
    strategies = [a.strategy] if a.strategy else ["auto", "text"]
    titles = {
        "auto": "전략 auto (괘선 기반 → 실패 시 글자 정렬 기반)",
        "lines": "전략 lines (괘선 기반만)",
        "text": "전략 text (글자 정렬 기반만, 괘선을 쓰지 않음)",
    }
    dump = {}
    for s in strategies:
        results = score_gold(a.gold, s, **({"layout": a.layout} if a.layout != 1 else {}))
        print(format_report(results, titles[s]))
        print()
        dump[s] = {
            "tables": results,
            "by_report": aggregate(results, "report"),
            "by_form": aggregate(results, "form"),
            "all": aggregate(results, None)["ALL"],
        }
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def cmd_render(a):
    files = render_pages(a.pdf, a.out, pages=parse_pages(a.pages) if a.pages else None, dpi=a.dpi)
    print(json.dumps({"rendered_pages": len(files), "out": str(a.out), "dpi": a.dpi}, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="docparse", description="PDF → 섹션·문단·표 JSON (LLM·OCR 없음)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse", help="PDF 를 분해해 <out>/document.json 을 쓴다")
    p.add_argument("pdf")
    p.add_argument("--out", required=True)
    p.add_argument("--pages", help="예: 60-70,142 (기본: 전 쪽)")
    p.add_argument("--strategy", choices=STRATEGIES, default="auto")
    p.add_argument("--render", action="store_true", help="쪽 PNG 도 <out>/pages/ 에 쓴다")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument(
        "--places",
        action="store_true",
        help="글자 자리(표의 칸·글 블록의 글자마다 좌표)도 <out>/char-places.json 에 쓴다. document.json 은 그대로다",
    )
    p.add_argument(
        "--dedupe-overdrawn",
        action="store_true",
        help="같은 글자가 같은 자리에 또 그려진 것을 한 번만 뽑는다 (기본 끔. 끄면 산출이 그대로다)",
    )
    p.add_argument(
        "--layout",
        type=int,
        choices=LAYOUTS,
        default=1,
        help="분해 판 (기본 1: 산출 그대로. 2: 번역 판 — 머리글·꼬리말 띠, 내용 해시 키 따위. README 「분해 판」)",
    )
    p.add_argument(
        "--charts",
        action="store_true",
        help="도표 라벨(도표 속 숫자마다 값·눈금, 범주, 계열)도 <out>/chart-labels.json 에 쓴다. --layout 2 에만",
    )
    p.set_defaults(fn=cmd_parse)
    s = sub.add_parser("score", help="정답 표에 대한 셀 단위 일치율")
    s.add_argument("--gold", required=True)
    s.add_argument("--strategy", choices=STRATEGIES, help="기본: auto 와 text 를 둘 다 잰다")
    s.add_argument("--json", help="결과를 JSON 으로도 쓴다")
    s.add_argument("--layout", type=int, choices=LAYOUTS, default=1, help="표를 이 분해 판으로 뽑아 잰다 (기본 1)")
    s.set_defaults(fn=cmd_score)
    r = sub.add_parser("render", help="쪽을 PNG 로 렌더링한다")
    r.add_argument("pdf")
    r.add_argument("--out", required=True)
    r.add_argument("--pages")
    r.add_argument("--dpi", type=int, default=200)
    r.set_defaults(fn=cmd_render)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (ParseError, ScoreError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
