"""정답 표에 대한 셀 단위 일치율을 표별·보고서별·양식별로 잰다."""

import json
from pathlib import Path

from .compare import score_tables
from .config import report_path
from .engine import open_pdf
from .tables import extract_tables

# 표 양식 구분은 사전 측정(PRJ11-RPT-4)의 것을 그대로 쓴다. 실제 괘선 구성은 보고 파일에 적었다.
FORMS = {
    "kb": "ruled_cells",  # 칸마다 괘선·배경이 있는 표
    "kb_databook": "ruled_cells",
    "cosmax": "horizontal_rules",  # 가로줄 위주의 표
    "samsung": "no_vertical_rules",  # 사전 측정에서 「괘선 없음」으로 분류된 표 (세로선 없음, 가로 토막은 있음)
}
METRICS = ("recall", "recall_strict", "recall_position", "numeric_recall")


class ScoreError(Exception):
    pass


def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _inter(a, b):
    return _area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def load_gold(gold_dir):
    gold_dir = Path(gold_dir)
    if not gold_dir.is_dir():
        raise ScoreError(f"정답 표 디렉터리가 없다: {gold_dir}")
    out = []
    for p in sorted(gold_dir.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "grid" in d and "bbox" in d:
            out.append(d)
    if not out:
        raise ScoreError(f"정답 표가 하나도 없다: {gold_dir}")
    return out


def pick(tables, gold_bbox):
    """정답 영역과 절반 이상 겹치는 추출 표를 위→아래로 이어 붙인다 (사전 측정의 page 조건과 같다)."""
    sel = [
        t
        for t in tables
        if t.grid
        and (_inter(t.bbox, gold_bbox) >= 0.5 * _area(t.bbox) or _inter(t.bbox, gold_bbox) >= 0.5 * _area(gold_bbox))
    ]
    sel.sort(key=lambda t: (t.bbox[1], t.bbox[0]))
    return sel


def score_gold(gold_dir, strategy="auto", engine=None, layout=1):
    """표별 결과 목록. 쪽 전체에서 표를 찾게 한 뒤 정답 영역과 겹치는 표만 비교한다 (표 위치를 알려 주지 않는다).

    layout: 표를 뽑는 분해 판(`document.LAYOUTS`). 기본 1 은 그대로다.
    """
    docs, results = {}, []
    try:
        for g in load_gold(gold_dir):
            path = report_path(g["report"])
            if not path.is_file():
                raise ScoreError(f"원본 PDF 가 없다: {path} (PARSER_REPORTS_DIR 로 위치를 지정)")
            doc = docs.get(g["report"])
            if doc is None:
                doc = docs[g["report"]] = open_pdf(path, engine)
            if layout == 1:
                tables = extract_tables(doc[g["page"] - 1], strategy)
            else:
                tables = extract_tables(doc[g["page"] - 1], strategy, layout=layout)
            sel = pick(tables, g["bbox"])
            s = score_tables(g["grid"], [r for t in sel for r in t.grid])
            results.append(
                {
                    "id": g["id"],
                    "report": g["report"],
                    "form": FORMS[g["report"]],
                    "page": g["page"],
                    "strategy": strategy,
                    "n_tables": len(sel),
                    "methods": sorted({t.method for t in sel}),
                    "statuses": sorted({t.status for t in sel}),
                    "tables_on_page": len(tables),
                    "failed_on_page": sum(1 for t in tables if t.status == "failed"),
                    **{k: v for k, v in s.items() if k != "wrong_rows"},
                    "wrong_rows": s["wrong_rows"],
                }
            )
    finally:
        for d in docs.values():
            d.close()
    return results


def aggregate(results, key):
    """key(report|form|None) 별 셀 가중 합계."""
    groups = {}
    for r in results:
        groups.setdefault(r[key] if key else "ALL", []).append(r)
    out = {}
    for name, rs in groups.items():
        gc = sum(r["gold_cells"] for r in rs)
        gn = sum(r["gold_numeric_cells"] for r in rs)
        out[name] = {
            "tables": len(rs),
            "gold_cells": gc,
            "recall": round(sum(r["correct"] for r in rs) / gc, 4),
            "recall_strict": round(sum(r["correct_strict"] for r in rs) / gc, 4),
            "recall_position": round(sum(r["correct_position"] for r in rs) / gc, 4),
            "numeric_recall": round(sum(r["correct_numeric"] for r in rs) / gn, 4) if gn else None,
        }
    return out


def _pct(v):
    return "—" if v is None else f"{v * 100:.1f}"


def format_report(results, title):
    lines = [
        f"## {title}",
        "",
        "관대 / 엄격 / 위치 / 숫자 일치율 (%), 분모는 정답의 비어 있지 않은 셀",
        "",
        "| 표 | 양식 | 정답 셀 | 추출 표 수 | 전략 | status | 관대 | 엄격 | 위치 | 숫자 |",
        "|---|---|---:|---:|---|---|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} (p{r['page']}) | {r['form']} | {r['gold_cells']} | {r['n_tables']} | "
            f"{','.join(r['methods']) or '—'} | {','.join(r['statuses']) or '표 없음'} | "
            + " | ".join(_pct(r[m]) for m in METRICS)
            + " |"
        )
    for label, key in (("보고서", "report"), ("양식", "form"), ("전체", None)):
        for name, a in sorted(aggregate(results, key).items()):
            lines.append(
                f"| **{label} {name}** ({a['tables']}개 표) | | {a['gold_cells']} | | | | "
                + " | ".join(_pct(a[m]) for m in METRICS)
                + " |"
            )
    return "\n".join(lines)
