"""골든 G1 (전체): esg-lab 의 TS CLI(f1b2c77, `eval --provider mock`)가 낸 `rows.json` 넷과 순수 파이프라인이 같은가.

파이썬 쪽: 가상 표(파일 순 = TS 의 표 순서) + 가상 예제 + 예제 폴더의 기억 + 모의 공급사(규칙 응답기)로 `run_pipeline`
을 돌려 TS 의 `rowDump` 꼴로 옮긴다. 견주는 것은 34행 전부의 값·키의 이름과 차례·null 과 「키 없음」의 구분이다.
점수(소수)만 상대 오차 1e-12 안에서 견준다(scope3_catalog_support 의 `compare_with_ts`).

★ 라: 설정 a 에서 모의 공급사가 받은 사용자 글자(`ITEM_JSON:`·`CANDIDATES_JSON:` 줄)가 TS 의 호출 기록과
글자까지 같은가.

순수 층: DB 도 Django 도 쓰지 않고, 소켓 문지기 아래에서 돈다(막힌 시도 0).
"""

import json
from typing import Any

import pytest

from esgapi.inventory.engines.scope3.llm_first_1.pipeline import PipelineResult, run_pipeline
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import Shortlister, lexical_shortlister
from esgapi.inventory.engines.scope3.llm_first_1.types import LicenseStatus
from esgapi.inventory.tests.scope3_catalog_support import (
    G1,
    G1_EXAMPLES,
    G1_GOLDEN,
    FloatTally,
    compare_with_ts,
    load_catalog,
    load_examples,
    load_json_keeping_floats,
)
from esgapi.inventory.tests.scope3_llm_support import harness, load_adjustments, load_memory, row_dump, user_texts

# (골든 폴더, 추리기, 추린 수, 뺀 이용 조건, 보정 계수를 쓰는가). make-golden.sh 의 run 줄과 하나씩 짝이다.
CONFIGS: list[tuple[str, Shortlister, int, tuple[LicenseStatus, ...], bool]] = [
    ("a-default", lexical_shortlister("lexical-v2"), 25, (), False),
    ("b-no-bigrams", lexical_shortlister("lexical-v2", bigrams=False), 25, (), False),
    ("c-lexical-v1", lexical_shortlister("lexical-v1"), 25, (), False),
    ("d-exclude-disputed", lexical_shortlister("lexical-v2"), 5, ("disputed",), True),
]


def replay(shortlister: Shortlister, size: int, exclude: tuple[LicenseStatus, ...], adjusted: bool) -> tuple[Any, Any]:
    examples = load_examples()
    setup = harness(
        load_catalog(),
        memory=load_memory(G1_EXAMPLES / "memory.synthetic.json"),
        heuristic=True,
        exclude=exclude,
        shortlist_size=size,
        shortlister=shortlister,
        adjustments=load_adjustments(G1 / "adjustments.synthetic.json") if adjusted else (),
    )
    result = run_pipeline([example.row for example in examples], setup.options)
    assert isinstance(result, PipelineResult)
    return row_dump(examples, result), setup


@pytest.mark.parametrize(
    ("name", "shortlister", "size", "exclude", "adjusted"), CONFIGS, ids=[config[0] for config in CONFIGS]
)
def test_the_pipeline_matches_the_ts_cli_row_by_row(
    name: str,
    shortlister: Shortlister,
    size: int,
    exclude: tuple[LicenseStatus, ...],
    adjusted: bool,
    blocked_network: list[object],
) -> None:
    golden = load_json_keeping_floats(G1_GOLDEN / name / "rows.json")
    mine, _ = replay(shortlister, size, exclude, adjusted)
    assert len(mine) == len(golden) == 34
    tally = FloatTally()
    assert compare_with_ts(mine, golden, tally) == []
    assert blocked_network == []


def test_the_goldens_cover_the_branches_the_heuristic_can_reach() -> None:
    """골든이 무엇을 재는지의 분모. 규칙 응답기로는 닿지 않는 갈래(분류 실패, 추천 실패, 맞는 것 없음, 범주 밖)는
    test_scope3_pipeline 이 심은 응답으로 잰다."""
    default = json.loads((G1_GOLDEN / "a-default" / "rows.json").read_text(encoding="utf-8"))
    excluded = json.loads((G1_GOLDEN / "d-exclude-disputed" / "rows.json").read_text(encoding="utf-8"))
    statuses = {row["status"] for row in default} | {row["status"] for row in excluded}
    assert statuses == {
        "recommended",
        "memory_factor_missing",
        "memory_category_mismatch",
        "memory_factor_excluded",
        "no_candidates",
    }
    calc = {row["calcStatus"] for row in default} | {row["calcStatus"] for row in excluded}
    assert calc == {"computed", "needs_distance", "needs_currency_adjustment", "not_calculated"}
    reasons = {row["basis"]["fallbackReason"] for row in default if row["basis"] is not None}
    assert reasons == {None, "unit_mismatch"}


def test_the_user_text_sent_to_the_provider_matches_the_ts_call_log() -> None:
    """★ 라: `JSON.stringify` 와 `jsrepr.js_json` 이 같은 글자를 내는가(한글, BMP 밖 글자, 전각, 따옴표)."""
    lines = (G1_GOLDEN / "a-default" / "user-texts.jsonl").read_text(encoding="utf-8").splitlines()
    theirs = [json.loads(line) for line in lines]
    _, setup = replay(lexical_shortlister("lexical-v2"), 25, (), False)
    mine = user_texts(setup.mock)
    # 분모: 호출 54 = 분류 28(기억에 없는 묶음마다 1회) + 추천 26(후보가 있던 묶음마다 1회).
    assert len(mine) == len(theirs) == 54
    assert mine == theirs
    assert sum(1 for text in mine if text.startswith("ITEM_JSON: ")) == 28
    assert sum(1 for text in mine if "\nCANDIDATES_JSON: " in text) == 26
