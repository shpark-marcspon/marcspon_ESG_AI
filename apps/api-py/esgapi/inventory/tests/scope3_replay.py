"""§4 의 재생: 저장소 밖 자료(esg-lab 의 실제 계수 표와 예제 148행)로 TS 와 견준다. pytest 가 모으지 않는 스크립트다.

    uv run python -m esgapi.inventory.tests.scope3_replay <esg-lab 의 절대 경로> [--only g2,g3,g4]

    G2  TS CLI `eval --provider mock` 을 그 자리에서 돌린 rows.json 과 파이썬의 순수 파이프라인이 전체 일치하는가
        (커밋 경계 ③ 의 것. scope3_replay_g2 에 있다)
    G3  TS CLI `recall`(낱말 방식 셋 × 추린 수 10·25·50)의 recall.json 과 파이썬의 추리기가 전체 일치하는가.
        분류 결과(범주, 영어 검색어)는 2026-10-01 실측의 다듬은 사본(tests/data/scope3-s25-rows.json)에서 온다
    G4  계수가 DB 에서 올 때처럼 표 순서를 id 의 코드 포인트 순으로 놓으면 재현율이 몇 / 113 인가
        (일치를 요구하지 않는다)
        (ㄱ) 후보 전부·id 순 — 순서만의 효과   (ㄴ) disputed 를 뺀 것·id 순 — 서버의 기본 경로

자료가 없으면 건너뛰지 않고 0 아닌 코드로 끝난다. AI 공급사 호출 0, esg-lab 의 파일 변경 0(산출물은 임시 폴더로만).
계수 표와 예제는 읽기만 한다(저장소에 베끼지 않는다).
"""

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from esgapi.core.calc.decimal import is_decimal_string
from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog, RawRecord
from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import ShortlistQuery
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import (
    LexicalV1Shortlister,
    LexicalV2Shortlister,
    Shortlister,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import (
    CandidateBasis,
    Factor,
    LicenseStatus,
    is_supported_category,
)
from esgapi.inventory.tests.scope3_catalog_support import (
    PRIOR_ROWS,
    Example,
    FloatTally,
    candidates_for,
    catalog_from,
    compare_with_ts,
    load_examples,
    load_json_keeping_floats,
    query_of,
    read_records,
)

NODE_BIN: Final = Path.home() / ".nvm/versions/node/v22.23.1/bin"
SIZES: Final = (10, 25, 50)
# TS 의 기대값(band-reports/H-retrieval.md 측정 A, 분모 113): 방식 → 추린 수 10·25·50 의 적중.
EXPECTED_HITS: Final = {
    "lexical-v1": (85, 100, 107),
    "lexical-v2": (105, 107, 109),
    "lexical-v2 (한글 두 글자 조각 없음)": (101, 105, 107),
}
EXPECTED_TARGETS: Final = 113


class ReplayFailed(Exception):
    """재생이 기대와 어긋났다."""


def say(text: str = "") -> None:
    sys.stdout.write(f"{text}\n")
    sys.stdout.flush()


def run_ts_cli(lab: Path, arguments: Sequence[str]) -> None:
    """esg-lab 의 Scope 3 CLI 를 돌린다. 출력 경로는 부르는 쪽이 임시 폴더로 준다."""
    env = dict(os.environ)
    if NODE_BIN.is_dir():
        env["PATH"] = f"{NODE_BIN}{os.pathsep}{env.get('PATH', '')}"
    pnpm = shutil.which("pnpm", path=env["PATH"])
    if pnpm is None:
        raise ReplayFailed("pnpm 이 없다(esg-lab 의 CLI 를 돌릴 수 없다)")
    done = subprocess.run(
        [pnpm, "-F", "scope3", "exec", "tsx", "src/cli.ts", *arguments],
        cwd=lab / "ts",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise ReplayFailed(f"TS CLI 가 {done.returncode} 로 끝났다: {done.stdout[-400:]} {done.stderr[-400:]}")


# ── 재현율(esg-lab `ts/scope3/src/eval/recall.ts` 의 옮김. 테스트 전용) ──


@dataclass(frozen=True, slots=True)
class RecallCall:
    basis: CandidateBasis
    candidates: list[Factor]
    query: ShortlistQuery


@dataclass(frozen=True, slots=True)
class RecallTarget:
    row_id: str
    item_name: str
    gold_ids: tuple[str, ...]
    calls: list[RecallCall]


def recall_targets(
    examples: Sequence[Example],
    prior: Sequence[dict[str, Any]],
    catalog: ListFactorCatalog,
    exclude: tuple[LicenseStatus, ...],
    *,
    check_totals: bool,
) -> list[RecallTarget]:
    """앞선 실행의 행별 판단에서 다시 추릴 호출을 만든다. 분모는 정답이 있고 기억에서 오지 않았고 추천 호출까지 간 행.

    `check_totals`: 후보 수가 앞선 실행이 남긴 수와 다르면 실패(계수 표나 설정이 달라진 것이다).
    이용 조건을 바꿔 재는 벌(G4 ㄴ)에서는 수가 달라지는 것이 당연하므로 끈다.
    """
    prior_by_id = {entry["rowId"]: entry for entry in prior}
    targets: list[RecallTarget] = []
    for example in examples:
        row = example.row
        entry = prior_by_id.get(row.row_id)
        if entry is None:
            raise ReplayFailed(f"앞선 실행의 결과에 행이 없다: {row.row_id}")
        if not example.gold.factor_ids or entry["source"] == "memory" or not entry["shortlists"]:
            continue
        category = entry["predictedCategory"]
        if not is_supported_category(category):
            raise ReplayFailed(f"추천 호출까지 간 행인데 범주가 없다: {row.row_id}")
        query = query_of(row, entry["keywords"] or [])
        calls: list[RecallCall] = []
        for call in entry["shortlists"]:
            candidates = candidates_for(catalog, row, category, call["basis"], exclude)
            if check_totals and len(candidates) != call["total"]:
                found = f"{len(candidates)} != {call['total']}"
                raise ReplayFailed(f"행 {row.row_id} 의 {call['basis']} 후보 수가 앞선 실행과 다르다: {found}")
            calls.append(RecallCall(call["basis"], candidates, query))
        targets.append(RecallTarget(row.row_id, row.item_name, example.gold.factor_ids, calls))
    return targets


def measure_recall(
    label: str, shortlister: Shortlister, targets: Sequence[RecallTarget], sizes: Sequence[int]
) -> dict[str, Any]:
    """한 방식으로 모든 호출을 다시 추려 추린 수별 재현율과 정답의 순위를 낸다(TS `MethodRecall` 의 JSON 꼴)."""
    rows: list[dict[str, Any]] = []
    for target in targets:
        gold = set(target.gold_ids)
        calls: list[dict[str, Any]] = []
        for call in target.calls:
            outcome = shortlister.shortlist(call.candidates, call.query, len(call.candidates))
            position = next((i for i, factor in enumerate(outcome.factors) if factor.id in gold), -1)
            scores = [entry.lexical.score if entry.lexical is not None else 0 for entry in outcome.evidence]
            own = scores[position] if position >= 0 else 0
            calls.append(
                {
                    "basis": call.basis,
                    "candidates": len(call.candidates),
                    "rank": None if position < 0 else position + 1,
                    "goldId": None if position < 0 else outcome.factors[position].id,
                    "lexical": (
                        None
                        if position < 0
                        else {
                            "score": own,
                            "higher": sum(1 for score in scores if score > own),
                            "tied": sum(1 for score in scores if score == own) - 1,
                        }
                    ),
                }
            )
        ranks = [call["rank"] for call in calls if call["rank"] is not None]
        best = min(ranks) if ranks else None
        rows.append({"rowId": target.row_id, "itemName": target.item_name, "bestRank": best, "calls": calls})
    by_size: list[dict[str, Any]] = []
    for size in sizes:
        missed = [
            {"rowId": row["rowId"], "itemName": row["itemName"], "bestRank": row["bestRank"]}
            for row in rows
            if not any(call["rank"] is not None and call["rank"] <= size for call in row["calls"])
        ]
        hits = len(rows) - len(missed)
        rate = None if not rows else hits / len(rows)
        by_size.append({"size": size, "hits": hits, "evaluated": len(rows), "rate": rate, "missed": missed})
    return {
        "label": label,
        "method": shortlister.method,
        "description": shortlister.description,
        "bySize": by_size,
        "rows": rows,
    }


def methods() -> list[tuple[str, Shortlister]]:
    """TS `recall` 명령의 낱말 방식 셋(같은 이름표, 같은 차례)."""
    return [
        ("lexical-v1", LexicalV1Shortlister()),
        ("lexical-v2", LexicalV2Shortlister(bigrams=True)),
        ("lexical-v2 (한글 두 글자 조각 없음)", LexicalV2Shortlister(bigrams=False)),
    ]


def hits_of(result: dict[str, Any]) -> tuple[int, ...]:
    return tuple(entry["hits"] for entry in result["bySize"])


def hit_rows(result: dict[str, Any], size: int) -> set[str]:
    missed = next(entry["missed"] for entry in result["bySize"] if entry["size"] == size)
    return {row["rowId"] for row in result["rows"]} - {row["rowId"] for row in missed}


# ── G3 ──


def g3(lab: Path, examples: Sequence[Example], records: Sequence[RawRecord]) -> list[dict[str, Any]]:
    say("== G3: TS `recall` 의 recall.json 과 전체 일치 (실제 표, 파일 순, 영어 검색어 경로) ==")
    with tempfile.TemporaryDirectory(prefix="scope3-g3-") as out:
        arguments = ["recall", str(lab / "data/scope3-examples"), "--from", str(PRIOR_ROWS)]
        run_ts_cli(lab, [*arguments, "--sizes", ",".join(map(str, SIZES)), "--out", out])
        theirs = load_json_keeping_floats(Path(out) / "recall.json")
    prior = json.loads(PRIOR_ROWS.read_text(encoding="utf-8"))
    targets = recall_targets(examples, prior, catalog_from(records, "file"), (), check_totals=True)
    calls = sum(len(target.calls) for target in targets)
    say(f"분모: 다시 추린 행 {len(targets)} (TS {theirs['targets']}), 호출 {calls} (TS {theirs['calls']})")
    if (len(targets), calls) != (theirs["targets"], theirs["calls"]) or len(targets) != EXPECTED_TARGETS:
        raise ReplayFailed("G3 의 분모가 TS 와 다르다")
    mine = [measure_recall(label, shortlister, targets, SIZES) for label, shortlister in methods()]
    tally = FloatTally()
    differences = compare_with_ts(mine, theirs["results"], tally, "results")
    for result in mine:
        hits = hits_of(result)
        say(f"  {result['label']}: {' · '.join(map(str, hits))} / {len(targets)}  (추린 수 10·25·50)")
        if hits != EXPECTED_HITS[result["label"]]:
            raise ReplayFailed(f"G3: {result['label']} 의 적중이 기대값 {EXPECTED_HITS[result['label']]} 과 다르다")
    say(f"  순위·정답 id·더 높은 후보 수·동점 수: 다른 자리 {len(differences)}")
    say(f"  {tally.line()}")
    if differences:
        for line in differences[:20]:
            say(f"    {line}")
        raise ReplayFailed(f"G3: TS 와 다른 자리 {len(differences)}")
    say("G3 일치")
    return mine


# ── G4 ──


def flips(base: dict[str, Any], other: dict[str, Any], unreachable: frozenset[str] = frozenset()) -> list[str]:
    """파일 순에서 적중이던 것이 빗나간 행과 그 반대. `unreachable`(정답이 후보에 없는 행)은 수만 적고 목록에서 뺀다."""
    lines: list[str] = []
    for size in SIZES:
        before, after = hit_rows(base, size), hit_rows(other, size)
        lost_all, gained = before - after, sorted(after - before)
        lost = sorted(lost_all - unreachable)
        if lost_all or gained:
            cannot = f" (그 밖에 정답이 후보에 없어 빗나간 행 {len(lost_all & unreachable)})" if unreachable else ""
            lines.append(f"추린 수 {size}: 적중 → 빗나감 {lost or '없음'}{cannot}, 빗나감 → 적중 {gained or '없음'}")
    return lines


def g4(examples: Sequence[Example], records: Sequence[RawRecord], by_file: list[dict[str, Any]]) -> None:
    say("== G4: 표 순서가 id 의 코드 포인트 순일 때(서버의 순서). 일치를 요구하지 않는다 ==")
    prior = json.loads(PRIOR_ROWS.read_text(encoding="utf-8"))
    catalog = catalog_from(records, "id")
    file_ids = [factor.id for factor in catalog_from(records, "file").all()]
    say(f"후보 {catalog.candidate_count} 건. 파일 순과 id 순이 같은 자리 {same_positions(file_ids)} / {len(file_ids)}")

    say("(ㄱ) 후보 전부(이용 조건으로 빼지 않음) · id 순 — 순서만의 효과")
    all_targets = recall_targets(examples, prior, catalog, (), check_totals=True)
    for (label, shortlister), base in zip(methods(), by_file, strict=True):
        result = measure_recall(label, shortlister, all_targets, SIZES)
        say(f"  {label}: {' · '.join(map(str, hits_of(result)))} / {len(all_targets)}  (파일 순 {hits_of(base)})")
        for line in flips(base, result):
            say(f"    {line}")

    say("(ㄴ) disputed 를 뺀 것 · id 순 — 서버의 기본 경로(ok,unverified)")
    excluded: tuple[LicenseStatus, ...] = ("disputed",)
    kept = sum(1 for factor in catalog.all() if factor.license_status != "disputed")
    default_targets = recall_targets(examples, prior, catalog, excluded, check_totals=False)
    empty_calls = sum(1 for target in default_targets for call in target.calls if not call.candidates)
    unreachable = [
        target.row_id
        for target in default_targets
        if not any(factor.id in set(target.gold_ids) for call in target.calls for factor in call.candidates)
    ]
    say(f"  후보 {kept} 건. 분모 {len(default_targets)} 행, 호출 {sum(len(t.calls) for t in default_targets)}")
    say(f"  후보가 0 이 된 호출(「후보 없음」, 순위 null 로 셈): {empty_calls}")
    say(f"  정답이 후보 집합에 하나도 없는 행(적중할 수 없다): {len(unreachable)} / {len(default_targets)}")
    for (label, shortlister), base in zip(methods(), by_file, strict=True):
        result = measure_recall(label, shortlister, default_targets, SIZES)
        hits = hits_of(result)
        reachable = len(default_targets) - len(unreachable)
        say(f"  {label}: {' · '.join(map(str, hits))} / {len(default_targets)}  (닿을 수 있는 행 {reachable} 가운데)")
        for line in flips(base, result, frozenset(unreachable)):
            say(f"    {line}")


def same_positions(file_ids: Sequence[str]) -> int:
    return sum(1 for a, b in zip(file_ids, sorted(file_ids), strict=True) if a == b)


# ── 표의 셈(★ 아) ──


def table_counts(records: Sequence[RawRecord]) -> None:
    catalog = catalog_from(records, "file")
    factors = catalog.all()
    negative = sum(1 for factor in factors if factor.value_raw.startswith("-"))
    longest = max(len(factor.value_raw) for factor in factors)
    by_license: dict[str, int] = {}
    for factor in factors:
        by_license[factor.license_status] = by_license.get(factor.license_status, 0) + 1
    # 자격 넷을 갖춘 줄 가운데 조립용 규칙과 갈릴 수 있는 표기의 수: 쉼표, 지수.
    qualified = [
        record
        for record in records
        if record.record_type == "emission_factor"
        and record.gas == "CO2e"
        and record.value is not None
        and record.scope3_categories
    ]
    comma = sum(1 for record in qualified if record.value_raw is not None and "," in record.value_raw)
    exponent = sum(1 for record in qualified if record.value_raw is not None and "e" in record.value_raw.lower())
    strict = sum(1 for record in qualified if is_decimal_string(record.value_raw))
    say(f"표: 낱줄 {len(records)}, 후보 {len(factors)} {dict(sorted(by_license.items()))}")
    say(f"  후보 자격을 갖춘 줄 {len(qualified)}: 엄격 십진 {strict}, 쉼표 {comma}, 지수 표기 {exponent}")
    say(f"  invalid_value_raw 로 빠진 줄 {len(catalog.rejected)}, 음수 {negative}")
    say(f"  후보의 value_raw 의 최장 {longest}자(상한 64)")
    say(f"  후보 id 의 최장 {max(len(factor.id) for factor in factors)}자")
    if catalog.rejected:
        raise ReplayFailed(f"후보 자격을 갖췄는데 value_raw 가 엄격 십진이 아닌 줄이 있다: {catalog.rejected[:5]}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("esg_lab", help="esg-lab 의 절대 경로")
    parser.add_argument("--only", default="g2,g3,g4", help="돌릴 것을 쉼표로(g2,g3,g4). 기본은 전부")
    options = parser.parse_args(argv)
    lab = Path(options.esg_lab)
    wanted = {name.strip() for name in str(options.only).split(",") if name.strip()}
    if not wanted or not wanted <= {"g2", "g3", "g4"}:
        say(f"--only 는 g2,g3,g4 가운데서 고른다: {options.only}")
        return 2
    factors_path = lab / "data/factors/factors.jsonl"
    examples_dir = lab / "data/scope3-examples"
    needed = [factors_path, examples_dir / "rows.synthetic.jsonl", lab / "ts/scope3/src/cli.ts", PRIOR_ROWS]
    missing = [str(path) for path in needed if not path.exists()]
    if missing:
        say(f"자료가 없다(건너뛰지 않는다): {missing}")
        return 2
    try:
        records = read_records(factors_path)
        examples = load_examples(examples_dir)
        say(f"예제 {len(examples)} 행")
        table_counts(records)
        if "g2" in wanted:
            # 파이프라인(커밋 경계 ③)을 쓰는 재생은 따로 둔다. 추리기만의 재생(g3,g4)이 그것 없이 돈다.
            importlib.import_module("esgapi.inventory.tests.scope3_replay_g2").g2(lab, examples, records)
        if wanted & {"g3", "g4"}:
            by_file = g3(lab, examples, records)
            if "g4" in wanted:
                g4(examples, records, by_file)
    except ReplayFailed as failure:
        say(f"실패: {failure}")
        return 1
    say(f"끝: {','.join(sorted(wanted))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
