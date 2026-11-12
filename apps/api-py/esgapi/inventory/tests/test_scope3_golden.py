"""골든 G1 (추리기만): esg-lab 의 TS CLI(f1b2c77, `eval --provider mock`)가 낸 `rows.json` 의 `shortlists` 와 같은가.

견주는 것은 추천 호출마다의 `total`·`shownIds`·`evidence`(순위, 겹친 낱말, 점수)다. id·순위·겹친 낱말은 글자까지,
점수는 상대 오차 1e-12 안에서(`Math.log` 와 `math.log` 의 마지막 자리가 다를 수 있다. scope3_catalog_support).
질의는 골든의 `predictedCategory`·`keywords` 와 묶음의 첫 행에서 다시 짠다(파이프라인 없이 추리기만 잰다.
전체 일치는 test_scope3_golden_full).
골든과 그것을 만든 명령은 tests/data/scope3/ 에 있다(README.md, make-golden.sh). 순수 층: DB 도 Django 도 쓰지 않는다.

무효 조건: 모의 응답기는 영어 검색어를 내지 않는다(`keywords: []`). 검색어 경로는 여기가 아니라 단위 테스트와
§4 의 G3(실제 표)이 잰다.
"""

from typing import Any

import pytest

from esgapi.inventory.engines.scope3.llm_first_1.normalize import group_rows
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import Shortlister, lexical_shortlister
from esgapi.inventory.engines.scope3.llm_first_1.types import LicenseStatus
from esgapi.inventory.tests.scope3_catalog_support import (
    G1_GOLDEN,
    FloatTally,
    candidates_for,
    compare_with_ts,
    load_catalog,
    load_examples,
    load_json_keeping_floats,
    query_of,
)

# (골든 폴더, 추리기, 추린 수, 뺀 이용 조건). make-golden.sh 의 run 줄과 하나씩 짝이다.
CONFIGS: list[tuple[str, Shortlister, int, tuple[LicenseStatus, ...]]] = [
    ("a-default", lexical_shortlister("lexical-v2"), 25, ()),
    ("b-no-bigrams", lexical_shortlister("lexical-v2", bigrams=False), 25, ()),
    ("c-lexical-v1", lexical_shortlister("lexical-v1"), 25, ()),
    ("d-exclude-disputed", lexical_shortlister("lexical-v2"), 5, ("disputed",)),
]


# 분모: 행마다 실린 추천 호출의 수의 합(기억에서 온 행 셋과 후보가 없던 행 둘은 호출이 없다. 34행 가운데 29행에 하나씩).
EXPECTED_CALLS = {"a-default": 29, "b-no-bigrams": 29, "c-lexical-v1": 29, "d-exclude-disputed": 29}


@pytest.mark.parametrize(("name", "shortlister", "size", "exclude"), CONFIGS, ids=[config[0] for config in CONFIGS])
def test_shortlists_match_the_ts_cli(
    name: str, shortlister: Shortlister, size: int, exclude: tuple[LicenseStatus, ...]
) -> None:
    golden: list[dict[str, Any]] = load_json_keeping_floats(G1_GOLDEN / name / "rows.json")
    catalog = load_catalog()  # 파일 순 = TS 의 표 순서
    examples = [example.row for example in load_examples()]
    # 묶음의 판단은 묶음의 첫 행으로 한다. 같은 묶음의 행들은 같은 추린 목록을 나눠 갖는다.
    rows = {member.row_id: group.rows[0] for group in group_rows(examples) for member in group.rows}
    assert len(golden) == len(rows) == 34

    calls = 0
    tally = FloatTally()
    for entry in golden:
        row = rows[entry["rowId"]]
        for trace in entry["shortlists"]:
            calls += 1
            candidates = candidates_for(catalog, row, entry["predictedCategory"], trace["basis"], exclude)
            outcome = shortlister.shortlist(candidates, query_of(row, entry["keywords"]), size)
            mine = {
                "basis": trace["basis"],
                "method": outcome.method,
                "total": outcome.total,
                "shownIds": [factor.id for factor in outcome.factors],
                "evidence": [evidence.to_json() for evidence in outcome.evidence],
                "failure": None,
            }
            assert compare_with_ts(mine, trace, tally) == [], (name, entry["rowId"], trace["basis"])
    # 분모: 추천 호출의 수(기억에서 온 행과 후보가 없던 행은 호출이 없다).
    assert calls == EXPECTED_CALLS[name]
    # lexical-v1 의 점수는 정수라 소수가 없다. BM25 는 점수마다 하나씩 있다.
    assert (tally.total > 0) == (shortlister.method == "lexical-v2")


def test_the_golden_table_orders_differ_between_file_and_id() -> None:
    """가상 표는 파일 순과 id 순이 다르게 지었다(동점이 표 순서로 갈리는 것을 잴 수 있게)."""
    by_file = [factor.id for factor in load_catalog(order="file").all()]
    by_id = [factor.id for factor in load_catalog(order="id").all()]
    assert sorted(by_file) == by_id != by_file
    assert by_file.index("syn:ab") < by_file.index("syn:a_b")
    assert by_id.index("syn:a_b") < by_id.index("syn:ab")
