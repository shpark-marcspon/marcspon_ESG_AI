"""셀 단위 일치율 계산 (사전 측정 `prework/scripts/compare_cells.py` 를 옮긴 것).

정답 격자(gold)와 추출 격자(pred)를 행 → 셀 순으로 정렬해 맞는 셀 수를 센다.

정규화: NFKC, 공백 제거, 천 단위 쉼표 제거, 대시 통일, 글자 뒤 각주 번호 `1)` 제거.
행 정렬: 비어 있지 않은 셀을 `|` 로 이은 문자열의 유사도(difflib, 0.5 이상)로 순서를 보존해 짝짓는다.

지표 (분모는 모두 「정답의 비어 있지 않은 셀 수」):
  recall           관대 일치. 짝지은 행 안에서 비어 있지 않은 셀의 순서열이 맞으면 맞음. 열 위치는 보지 않는다.
  recall_strict    엄격 일치. 관대 일치 + 추출 행의 비어 있지 않은 셀 수가 정답 행보다 많으면 그 행은 0점.
  recall_position  위치 일치. 짝지은 행에서 같은 열 번호의 셀이 같아야 맞음 (사전 측정에는 없던 지표).
  numeric_recall   숫자 셀만의 관대 일치.
  precision        관대 일치로 맞은 셀 / 추출의 비어 있지 않은 셀.
"""

import difflib
import re
import unicodedata

FOOTNOTE_RE = re.compile(r"(?<=[^\d(.,\-+%])\d{1,2}\)$")  # 셀 끝의 '비율1)' 같은 각주 표시(공백 제거 뒤 적용)
NUM_RE = re.compile(r"^[\(\-+△▲▽▼]?\d[\d.]*%?\)?$")


def norm(cell, strip_footnote=True):
    if cell is None:
        return ""
    s = unicodedata.normalize("NFKC", str(cell))
    s = re.sub(r"\s+", "", s)
    if strip_footnote:
        s = FOOTNOTE_RE.sub("", s)
    s = s.replace(",", "")
    s = re.sub(r"[‐‑‒–—―−]", "-", s)
    return s


def norm_grid(grid, strip_footnote=True):
    out = []
    for row in grid or []:
        r = [norm(c, strip_footnote) for c in row]
        if any(r):
            out.append(r)
    return out


def is_num(s):
    return bool(NUM_RE.match(s))


def _row_key(row):
    return "|".join(c for c in row if c)


def align_rows(gold, pred, min_ratio=0.5):
    """gold 행마다 대응하는 pred 행 번호(없으면 None). 순서를 보존하는 DP 정렬."""
    gk = [_row_key(r) for r in gold]
    pk = [_row_key(r) for r in pred]
    n, m = len(gk), len(pk)
    sim = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            if gk[i] == pk[j]:
                sim[i][j] = 1.0
            else:
                r = difflib.SequenceMatcher(None, gk[i], pk[j], autojunk=False).ratio()
                sim[i][j] = r if r >= min_ratio else 0.0
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = max(dp[i + 1][j], dp[i][j + 1], (sim[i][j] + dp[i + 1][j + 1]) if sim[i][j] else 0.0)
    pairs: list[int | None] = [None] * n
    i = j = 0
    while i < n and j < m:
        if sim[i][j] and abs(dp[i][j] - (sim[i][j] + dp[i + 1][j + 1])) < 1e-9:
            pairs[i] = j
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def match_cells(grow, prow, strict_position=False):
    """짝지은 행에서 gold 의 비어 있지 않은 셀별 정오(bool 목록)."""
    if strict_position:
        return [k < len(prow) and prow[k] == g for k, g in enumerate(grow) if g]
    g = [c for c in grow if c]
    p = [c for c in prow if c]
    flags = [False] * len(g)
    sm = difflib.SequenceMatcher(None, g, p, autojunk=False)
    for a, _b, size in sm.get_matching_blocks():
        for k in range(size):
            flags[a + k] = True
    return flags


def score_tables(gold_grid, pred_grid, strip_footnote=True):
    gold = norm_grid(gold_grid, strip_footnote)
    pred = norm_grid(pred_grid, strip_footnote)
    gold_cells = sum(1 for r in gold for c in r if c)
    pred_cells = sum(1 for r in pred for c in r if c)
    gold_num = sum(1 for r in gold for c in r if c and is_num(c))
    correct = correct_num = correct_strict = correct_pos = 0
    rows_matched = 0
    wrong = []
    if gold and pred:
        pairs = align_rows(gold, pred)
        for i, j in enumerate(pairs):
            if j is None:
                wrong.append({"gold_row": i, "reason": "행 대응 없음", "gold": gold[i]})
                continue
            rows_matched += 1
            flags = match_cells(gold[i], pred[j])
            pos_flags = match_cells(gold[i], pred[j], strict_position=True)
            gcells = [c for c in gold[i] if c]
            clean_row = len([c for c in pred[j] if c]) <= len(gcells)
            for c, ok in zip(gcells, flags, strict=False):
                if ok:
                    correct += 1
                    if clean_row:
                        correct_strict += 1
                    if is_num(c):
                        correct_num += 1
            correct_pos += sum(pos_flags)
            if not all(flags) or not all(pos_flags) or not clean_row:
                wrong.append({"gold_row": i, "pred_row": j, "gold": gold[i], "pred": pred[j]})
    else:
        wrong = [{"gold_row": i, "reason": "행 대응 없음", "gold": r} for i, r in enumerate(gold)]

    def ratio(a, b):
        return round(a / b, 4) if b else None

    return {
        "gold_cells": gold_cells,
        "pred_cells": pred_cells,
        "correct": correct,
        "recall": ratio(correct, gold_cells),
        "precision": ratio(correct, pred_cells),
        "correct_strict": correct_strict,
        "recall_strict": ratio(correct_strict, gold_cells),
        "correct_position": correct_pos,
        "recall_position": ratio(correct_pos, gold_cells),
        "gold_numeric_cells": gold_num,
        "correct_numeric": correct_num,
        "numeric_recall": ratio(correct_num, gold_num),
        "gold_rows": len(gold),
        "pred_rows": len(pred),
        "rows_matched": rows_matched,
        "wrong_rows": wrong,
    }
