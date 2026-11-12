"""값 후보의 종류. TS `named.test.ts` 의 「값 후보의 종류」 8건의 뜻을 옮겼다.

(8번째의 「요청 글은 종류와 무관하다」 한 줄은 옮기지 않았다: 요청 글 조립 `renderDocumentWithIds` 가 이 밴드에 없다.)
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.kinds import KindContext, classify_kinds, is_non_value, kind_of
from esgapi.reconcile.calc.types import VALUE_KINDS, DocModel, Fact, FactWhere, GridHeader, ValueKind
from esgapi.reconcile.tests.support import HEADER, BlockSpec, TableSpec, synthetic_document


def summary() -> DocModel:
    return synthetic_document(
        "s",
        [TableSpec("p1-t1", page=1, cells=[["구분", "2023", "2024"], ["자본비율", "12.5%", "13.1%"]], header=HEADER)],
        [
            BlockSpec("p1-b1", "주요 성과", bbox=(40, 90, 120, 104)),
            BlockSpec("p1-b2", "자본비율", bbox=(60, 120, 110, 130)),
            BlockSpec("p1-b3", "13.1%", bbox=(50, 131, 120, 156), kind="heading"),
            BlockSpec("p1-b4", "총자산", bbox=(160, 120, 200, 130)),
            BlockSpec("p1-b5", "742조 원", bbox=(150, 131, 215, 156), kind="heading"),
            BlockSpec("p1-b6", "안전 점검", bbox=(400, 300, 440, 310)),
            BlockSpec("p1-b7", "30.0", bbox=(40, 305, 56, 313)),
            BlockSpec("p1-b8", "20.0", bbox=(40, 345, 56, 353)),
            BlockSpec("p1-b9", "10.0", bbox=(40, 385, 56, 393)),
            BlockSpec("p2-b1", "큰 제목", page=2, bbox=(40, 100, 200, 140)),
            BlockSpec("p2-b2", "58.4%", page=2, bbox=(40, 141, 100, 160)),
            BlockSpec("p2-b3", "전년에는 1,204명이었다.", page=2, bbox=(300, 100, 420, 110)),
            BlockSpec("p2-b4", "1,251명", page=2, bbox=(300, 111, 380, 136)),
        ],
    )


def kinds_of(document: DocModel) -> dict[str, ValueKind]:
    found = extract_document(document, "s", titles="own", kinds=True).kinds
    assert found is not None
    return dict(found)


def kind_in(text: str, raw: str, nth: int = 1) -> ValueKind:
    document = synthetic_document("s", [], [BlockSpec("p1-b1", text)])
    extraction = extract_document(document, "s", titles="own", kinds=True)
    matching = [fact for fact in extraction.facts if fact.raw == raw]
    assert len(matching) >= nth, f"값 후보가 아니다: {raw} ({text})"
    assert extraction.kinds is not None
    return extraction.kinds[matching[nth - 1].id]


def test_value_measured_amounts_ratios_targets_thresholds() -> None:
    assert kind_in("2024년 배출량은 39,604 tCO2eq 이다.", "39,604") == "value"
    assert kind_in("임직원은 1,251명이다.", "1,251") == "value"
    assert kind_in("감축률은 17.9% 이며 목표는 42% 감축이다.", "42%") == "value"
    assert kind_in("영업점은 414개소이다.", "414") == "value"
    assert kind_in("이사 9명 중 3명이 전문가다.", "3") == "value"
    assert kind_in("총자산은 742조 원이다.", "742") == "value"


def test_identifier_standard_numbers_parts_of_names_footnotes_clauses_pages() -> None:
    assert kind_in("검증은 ABCD 4100 에 따라 수행하였다.", "4100") == "identifier"
    assert kind_in("검증은 ABCD 4100에서 정한 절차를 따랐다.", "4100") == "identifier"
    assert kind_in("내부 배출량(Scope 1&2)은 줄었다.", "2") == "identifier"
    assert kind_in("Scope 1, 2, 3 배출량을 쓴다.", "3") == "identifier"
    assert kind_in("집약도*1 를 관리한다.", "1") == "identifier"
    assert kind_in("문단 14(1)에 따라 공시한다.", "14") == "identifier"
    assert kind_in("세부 현황은 50 페이지에서 확인한다.", "50") == "identifier"
    assert kind_in("32 소비자 보호", "32") == "identifier"
    # 반례: 약어 뒤라도 단위가 붙은 수는 값이다.
    assert kind_in("ABCD 7.8조 원 증가", "7.8") == "value"
    assert kind_in("ABCD 3명", "3") == "value"


def test_duration_years_months_and_the_counterexample_of_a_fractional_year() -> None:
    assert kind_in("장기(10년) 시점의 영향", "10") == "duration"
    assert kind_in("최근 3개년 자료를 실었다.", "3") == "duration"
    assert kind_in("복귀 후 12개월 이상 근속", "12") == "duration"
    assert kind_in("평균 근속은 16.1년이다.", "16.1") == "value"


def test_count_parts_and_set_frequencies_and_the_counterexamples() -> None:
    assert kind_in("보고서를 3종으로 나누어 낸다.", "3") == "count"
    assert kind_in("4대 핵심요소를 중심으로", "4") == "count"
    assert kind_in("5개 주제를 선정하였다.", "5") == "count"
    assert kind_in("교육을 연 1회 이상 실시한다.", "1") == "count"
    assert kind_in("국내 영업점 1,449 개", "1,449") == "value"
    assert kind_in("위원회를 총 3회 개최하였다.", "3") == "value"


def test_scale_likert_per_unit_evenly_stacked_blocks_and_axis_ticks_in_one_cell() -> None:
    assert kind_in("파급효과를 5점 척도로 평가", "5") == "scale"
    assert kind_in("근로자 10,000명당 사망자 수", "10,000") == "scale"
    kinds = kinds_of(summary())
    assert [kinds["p1-b7#n1"], kinds["p1-b8#n1"], kinds["p1-b9#n1"]] == ["scale", "scale", "scale"]
    assert kinds["p1-b3#n1"] == "value"
    assert kinds["p2-b2#n1"] == "value"
    chart = synthetic_document(
        "s",
        [
            TableSpec(
                "p1-t1",
                cells=[["300.0 200.0 100.0", "157.2 149.8"], ["600 400", "18.2 18.1"]],
                header=GridHeader((), (), "none"),
            )
        ],
    )
    chart_kinds = kinds_of(chart)
    assert chart_kinds["p1-t1:r0c0#n2"] == "scale"
    assert chart_kinds["p1-t1:r1c0#n1"] == "scale"
    assert chart_kinds["p1-t1:r0c1#n1"] == "value"
    assert chart_kinds["p1-t1:r1c1#n2"] == "value"


def test_year_label_is_a_comma_less_year_in_a_numeric_cell() -> None:
    document = synthetic_document(
        "s", [TableSpec("p1-t1", cells=[["구분", "기준", "실적"], ["목표 연도", "2030", "2,030"]], header=HEADER)]
    )
    kinds = kinds_of(document)
    assert kinds["p1-t1:r1c1"] == "year_label"  # 연도 표시 (심은 파손 1 이 표시를 지우면 value 가 된다)
    assert kinds["p1-t1:r1c2"] == "value"
    assert is_non_value("year_label") is True
    assert is_non_value("value") is False


def test_turning_kinds_on_keeps_every_candidate() -> None:
    """종류 옵션을 끄면 값 후보 목록이 기존과 같고, 켜도 값 후보는 버려지지 않는다. (심은 파손 7)"""
    document = summary()
    off = extract_document(document, "s", titles="own")
    on = extract_document(document, "s", titles="own", kinds=True)
    assert off.kinds is None
    assert on.kinds is not None
    assert off.facts == on.facts
    assert off.non_values == on.non_values
    assert extract_document(document, "s", titles="own", kinds=False) == off
    # 「값이 아님」으로 갈린 자리도 값 후보 목록에 그대로 있다.
    assert "p1-b7#n1" in [fact.id for fact in off.facts]
    assert on.kinds["p1-b7#n1"] == "scale"
    assert sorted(on.kinds) == sorted(fact.id for fact in on.facts)
    assert classify_kinds(document, off) == on.kinds


def test_kind_of_only_separates_year_like_in_numeric_cells() -> None:
    where = FactWhere(1, None, "t", 1, 1, None, None, None)
    base = Fact(
        "x", "s", "table_cell", where, "39,604", "39604", 0, "none", False, None, (), (), "ok", None, None, False
    )
    assert kind_of(base, KindContext("39,604", 0, 6, ())) == "value"
    year = Fact(
        "x",
        "s",
        "table_cell",
        where,
        "2030",
        "2030",
        0,
        "none",
        False,
        None,
        ("year_like",),
        (),
        "ok",
        None,
        None,
        False,
    )
    assert kind_of(year, KindContext("2030", 0, 4, ())) == "year_label"


# ── 갈래마다 하나 이상, 그리고 언어 차이의 본보기 ────────────────────────────


def test_every_value_kind_is_reachable() -> None:
    document = synthetic_document(
        "s",
        [TableSpec("p1-t1", cells=[["구분", "값"], ["연도", "2030"]], header=HEADER)],
        [BlockSpec("p1-b1", "배출량 1,200톤, ABCD 4100 에 따라, 3개년, 5개 주제, 5점 척도")],
    )
    assert set(kinds_of(document).values()) == set(VALUE_KINDS)


def test_the_column_key_rounds_half_up_like_math_round() -> None:
    """세로줄 열쇠는 `Math.round(x / 2)`: 0.5 를 위로 올린다. (심은 파손 8 이 파이썬 round() 로 바꾼다)

    왼쪽 끝 101.0 / 2 = 50.5 → JS 51, 파이썬 round 50(짝수로). 셋이 한 세로줄이어야 눈금이다.
    """
    document = synthetic_document(
        "s",
        [],
        [
            BlockSpec("p1-b1", "10", bbox=(101.0, 300, 110.0, 310)),
            BlockSpec("p1-b2", "20", bbox=(102.0, 320, 121.0, 330)),
            BlockSpec("p1-b3", "30", bbox=(102.4, 340, 133.3, 350)),
        ],
    )
    assert list(kinds_of(document).values()) == ["scale", "scale", "scale"]


def test_a_period_then_a_newline_is_not_the_end_of_the_text() -> None:
    """`/[.。] ?$/` 의 `$` 는 문자열의 끝뿐이다. 파이썬의 `$` 는 끝 줄바꿈 앞에서도 맞는다. (심은 파손 20)"""
    assert kind_in("문장의 끝.\n7", "7") == "value"
    assert kind_in("글 끝. 9", "9") == "identifier"


def test_standard_header_makes_a_bare_number_an_identifier() -> None:
    document = synthetic_document(
        "s", [TableSpec("p1-t1", cells=[["지표", "GRI 번호"], ["가", "405 에 해당하는 항목"]], header=HEADER)]
    )
    assert kinds_of(document)["p1-t1:r1c1#n1"] == "identifier"
