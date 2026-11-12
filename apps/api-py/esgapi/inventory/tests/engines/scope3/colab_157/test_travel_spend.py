"""S3 출장 Spend 손셈(C6-2) — `pipeline.run` 으로 시트를 돌려 줄마다 코랩을 손으로 따라 센 값과 견준다.

코랩 줄(읽기판): 표준화 `standardize_c6_spend_sheet`(`:6728` — 「출장항목」 → 「이동수단」, 「출장수단」 은 그 복사) →
갈래 `:6021-6051` → `calc_travel_spend_emission`(`:8641-8659`: 배출량 = 출장비용 × EF / 1000.0) → 후처리
`_fix_result_c6`(`:8821` — 같은 셈을 다시) · 계수 `_fix_lookup_travel_spend_candidate`(`:8576-8625`: 수동 표 → 점수
키워드 `100+len` · 「출장 항목」 30 · Title 20, 처음 가장 큰 줄 — 붙잡은 옛 판은 지어지지 않아 안 걸리면 null `:8628`) ·
정규화이동수단 `normalize_travel_mode`(`:8534`: 앞 표 → `detect_travel_mode_rule` `:1384` → AI `:8523`
(lru_cache — None 도 기억) → "car").
수동 표의 NAICS Title(「Scheduled Passenger Air Transportation」 등)은 코랩 상수에 박힌 공개 분류명이고
계수 값은 지어낸 것이다.
"""

from esgapi.inventory.engines.scope3.colab_157.pipeline import ProcessedSheet
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import (
    KRW_2025,
    USD,
    Replies,
    activity_metas,
    column,
    processed,
    run_sheets,
)

AIR = "Scheduled Passenger Air Transportation"
HOTEL = "Hotels (except Casino Hotels) and Motels"
TAXI = "Taxi Service"
# B 줄(앞): 긴 키워드 하나 + 출장 항목 30 + Title 20, A 줄(뒤): 짧은 키워드 둘 — 점수가 같아 앞 줄이 이긴다.
LONG = "가상" + "나" * 54
PAIR = ("가상갑", "가상을")
V_HEAD: list[Value] = ["출장 항목", "NAICS 코드", "NAICS Title", "한국어 매핑 키워드", USD, KRW_2025]
V_ROWS: dict[int, list[Value]] = {
    1: ["가상 출장 지출 계수 표"],
    3: V_HEAD,
    4: ["가상항공", 9201, AIR, "가상비행기", 9.21, 9.21e-05],
    5: ["가상숙박", 9202, HOTEL, "가상여관", 9.22, 9.22e-05],
    6: ["가상택시", 9203, TAXI, "가상콜", 9.23, 9.23e-05],
    7: ["가상회의", 9204, "Virtual Meeting Rooms", "가상세미나", 9.24, 9.24e-05],
    8: ["가상식비", 9205, "Virtual Food Services", "가상도시락", 9.25, 9.25e-05],
    9: ["가상긴항목", 9206, "Virtual Long Title", LONG, 9.26, 9.26e-05],
    10: ["가상둘", 9207, "Virtual Pair", ", ".join(PAIR), 9.27, 9.27e-05],
}
USD_ROWS: dict[int, list[Value]] = {n: row[:5] for n, row in V_ROWS.items()}
C6_HEAD: list[Value] = ["*사업장", "*출장항목", "연간 입력", "월별 지출금액", None]
C6_SUB: list[Value] = [None, None, "연간지출금액(원)", "1월", "2월"]
AI_TEXT = "가상출장경비"  # 「가상 출장 경비」 의 정규화 글(`_fix_norm`) — 앞 표·규칙 낱말 0


def travel(*rows: list[Value], book: dict[int, list[Value]] = V_ROWS, mock: Replies | None = None) -> ProcessedSheet:
    template = sheet("c6-2_출장비", {4: C6_HEAD, 5: C6_SUB, **{6 + i: row for i, row in enumerate(rows)}})
    (outcome,) = run_sheets([template], [sheet("출장_Spend", book)], mock=mock)
    return processed(outcome)


def factor_vias(done: ProcessedSheet) -> list[str | None]:
    return [next((s.via for s in m.steps if s.step == "factor"), None) for m in activity_metas(done)]


def test_the_manual_table_and_the_formula() -> None:
    done = travel(
        ["가상사업장", "가상 항공권", 9100000],
        ["가상사업장", "가상 호텔 숙박", 9200000],
        ["가상사업장", "가상 택시비", 9300000],
    )
    frame = done.frame
    assert column(frame, "출장비용") == [9100000.0, 9200000.0, 9300000.0]
    assert column(frame, "EF_DB") == [AIR, HOTEL, TAXI]
    assert column(frame, "NAICS") == ["9201", "9202", "9203"]
    assert column(frame, "배출계수") == [9.21e-05, 9.22e-05, 9.23e-05]
    expected = [9100000 * 9.21e-05 / 1000.0, 9200000 * 9.22e-05 / 1000.0, 9300000 * 9.23e-05 / 1000.0]
    assert column(frame, "배출량(tCO2e)") == expected
    assert column(frame, "배출량") == expected
    assert column(frame, "배출계수단위") == ["kgCO2e/KRW"] * 3
    assert column(frame, "계산식")[0] == (
        "배출량(tCO2e) = 출장비용(KRW) × EF(kgCO2e/KRW) / 1000 = 9.1e+06 × 9.21e-05 / 1000 = 0.83811"
    )
    assert column(frame, "정규화이동수단") == ["flight", "lodging", "taxi"]
    assert factor_vias(done) == ["manual"] * 3
    metas = activity_metas(done)
    assert [(m.mode.value, m.mode.origin) if m.mode else None for m in metas] == [
        ("flight", "rule"),
        ("lodging", "rule"),
        ("taxi", "rule"),
    ]
    assert {m.origin for m in metas} == {"rule"}
    assert {m.factor.column for m in metas} == {KRW_2025}


# 책 v1.1(S3V1 Q7): EF 같은 줄을 합쳐 Title 이 「A / B」 꼴 — 수동 표 Title 이 조각 하나와 같으면 걸린다.
JOINED_AIR = f"Virtual Charter Air / {AIR}"
JOINED_ROWS: dict[int, list[Value]] = {
    1: ["가상 출장 지출 계수 표"],
    3: V_HEAD,
    4: ["가상항공", "9211/9201", JOINED_AIR, "가상비행기", 9.31, 9.31e-05],
    5: ["가상택시", 9203, f"{TAXI} Plus", "가상콜", 9.33, 9.33e-05],
}


def test_the_manual_table_hits_a_piece_of_a_joined_title() -> None:
    """조각(` / ` 로 나눔)과 같으면 수동 갈래 — 조각을 품기만 한 글(「Taxi Service Plus」)은 점수 갈래로 간다."""
    done = travel(["가상사업장", "가상 항공권", 9100000], ["가상사업장", "가상 택시비", 9300000], book=JOINED_ROWS)
    assert column(done.frame, "EF_DB") == [JOINED_AIR, f"{TAXI} Plus"]
    assert column(done.frame, "NAICS") == ["9211/9201", "9203"]
    assert column(done.frame, "배출계수") == [9.31e-05, 9.33e-05]
    assert factor_vias(done) == ["manual", "scored"]


def test_the_scores_keyword_item_title() -> None:
    """키워드 `100+len` > 「출장 항목」 30 > Title 20. 이동수단은 규칙에 안 걸려 AI(실패) → car."""
    done = travel(
        ["가상사업장", "가상여관 가상회의 virtual food services", 9100000],  # 가상숙박 104 · 가상회의 30 · 가상식비 20
        ["가상사업장", "가상회의 virtual food services", 9200000],  # 가상회의 30 · 가상식비 20
        ["가상사업장", "virtual food services", 9300000],  # 가상식비 20
    )
    assert column(done.frame, "EF_DB") == [HOTEL, "Virtual Meeting Rooms", "Virtual Food Services"]
    assert column(done.frame, "배출량(tCO2e)") == [
        9100000 * 9.22e-05 / 1000.0,
        9200000 * 9.24e-05 / 1000.0,
        9300000 * 9.25e-05 / 1000.0,
    ]
    assert factor_vias(done) == ["scored"] * 3


def test_a_score_tie_goes_to_the_earlier_row() -> None:
    """긴 키워드 줄(앞)과 짧은 키워드 둘 줄(뒤)의 점수가 같다 — `max` 는 처음 가장 큰 줄을 고른다."""
    assert 100 + len(LONG) + 30 + 20 == 2 * (100 + len(PAIR[0]))  # 앞 줄 = 뒤 줄 = 206
    done = travel(["가상사업장", f"{LONG} 가상긴항목 virtual long title {PAIR[0]} {PAIR[1]}", 9100000])
    assert column(done.frame, "EF_DB") == ["Virtual Long Title"]
    assert column(done.frame, "배출량(tCO2e)") == [9100000 * 9.26e-05 / 1000.0]


def test_no_hit_is_null_without_a_factor_step() -> None:
    done = travel(["가상사업장", "가상 무엇", 9100000])
    frame = done.frame
    assert (column(frame, "EF_DB"), column(frame, "NAICS"), column(frame, "배출계수")) == ([None], [None], [None])
    assert (column(frame, "배출량(tCO2e)"), column(frame, "계산식")) == ([None], [""])
    meta = activity_metas(done)[0]
    assert (factor_vias(done), meta.origin, meta.factor.value, meta.factor.title) == ([None], None, None, None)


def test_without_a_krw_column_the_usd_factor_multiplies_krw() -> None:
    """코랩 그대로(결함 후보): 원화 열이 없으면 `_get_spend_ef_col` 이 USD 열을 주고 원화 금액에 곱한다."""
    done = travel(["가상사업장", "가상 항공권", 9100000], book=USD_ROWS)
    assert column(done.frame, "배출계수") == [9.21]
    assert column(done.frame, "배출량(tCO2e)") == [9100000 * 9.21 / 1000.0]
    assert column(done.frame, "배출계수단위") == ["kgCO2e/KRW"]
    assert activity_metas(done)[0].factor.column == USD


def test_monthly_spend_is_summed() -> None:
    done = travel(["가상사업장", "가상 택시", None, 9100, 9200])
    assert column(done.frame, "출장비용") == [9100.0 + 9200.0]
    assert column(done.frame, "배출량(tCO2e)") == [(9100.0 + 9200.0) * 9.23e-05 / 1000.0]


def test_normalized_modes_rule_fix_rule_ai_and_empty() -> None:
    """앞 표(「항공」) · `detect_travel_mode_rule`(「셔틀」 → bus) · AI(같은 글 두 줄 — 부름 한 번) · 빈 칸 → car.

    빈 칸은 NaN 이 `출장수단 or 이동수단` 에서 이겨 정규화 글이 "" — AI 를 부르지 않고 car.
    """
    mock = Replies(lambda text: '{"mode": "taxi"}' if f"입력값: {AI_TEXT}" in text else None)
    done = travel(
        ["가상사업장", "가상 항공권", 9100000],
        ["가상사업장", "가상 셔틀", 9200000],
        ["가상사업장", "가상 출장 경비", 9300000],
        ["가상사업장", "가상 출장 경비", 9400000],
        ["가상사업장", None, 9500000],
        mock=mock,
    )
    assert column(done.frame, "정규화이동수단") == ["flight", "bus", "taxi", "taxi", "car"]
    metas = activity_metas(done)
    assert [(m.mode.value, m.mode.origin) if m.mode else None for m in metas] == [
        ("flight", "rule"),
        ("bus", "rule"),
        ("taxi", "ai"),
        ("taxi", "ai"),
        ("car", "estimate"),
    ]
    assert [s.via for m in metas for s in m.steps if s.step == "mode"] == [
        "rule_fix",
        "rule",
        "ai",
        "ai",
        "default_car",
    ]
    assert len(mock.texts) == 1  # 두 줄 × 두 번(셈 + 후처리) — 캐시가 한 번으로
    assert f"입력값: {AI_TEXT}" in mock.texts[0]


def test_an_ai_failure_is_cached_as_none() -> None:
    """AI 가 세 번(JSON 재시도) 다 실패하면 None — lru_cache 처럼 None 도 기억해 다음 줄·후처리는 부르지 않는다."""
    mock = Replies()  # 늘 실패
    done = travel(["가상사업장", "가상 출장 경비", 9100000], ["가상사업장", "가상 출장 경비", 9200000], mock=mock)
    assert column(done.frame, "정규화이동수단") == ["car", "car"]
    assert [s.via for m in activity_metas(done) for s in m.steps if s.step == "mode"] == ["default_car"] * 2
    assert len(mock.texts) == 3
    assert all(f"입력값: {AI_TEXT}" in text for text in mock.texts)
