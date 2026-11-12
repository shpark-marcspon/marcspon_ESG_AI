"""D10 `scope3colab_dump` 의 거리판(S3C-b2a·b2b): esg-lab S3C-o3 거리판 입력(c1ac9c4 `synthetic.py`·답 파일)을 같은 줄로
다시 지어 돌린다 — 열쇠·item·갈래(`branch`)·칸, 기록한 지오코더 물음, 답 차례 어긋남, 갈래·kind 어긋남, C6 이어 세기·C7
열쇠(T8).

순수 층(DB·네트워크 0). 입력은 o3 의 거리판 템플릿(C4-1 → C6-1 → C7 → C9-1, 안내 한 줄·머리글 둘)과 같은 줄이고 답은
`answers.distance.synthetic.json`(32)·`answers.distance-transport.synthetic.json`(23 = 앞 32 의 1-9·19-32)과 같은
글이다. 기대 줄의 수는 o3 코랩 쪽 결과(esg-lab `run --input distance-transport`·`--input distance` 의 `colab.json`,
2026-10-20)를 `Decimal` 로 옮겨 적었다 — 실제 대조(병합 조건)는 밴드 보고의 §3-4.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157.activity import (
    ActivityAmount,
    ActivityFactor,
    ActivityMeta,
    ColabActivityKind,
)
from esgapi.inventory.engines.scope3.colab_157.pipeline import ProcessedSheet
from esgapi.inventory.engines.scope3.colab_157.template import match_sheet_processor
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    C9_DIST_MAIN,
    DIST_MAIN,
    DIST_SUB,
    MONTH_NAMES,
    Value,
    annual,
    monthly,
    sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS
from esgapi.inventory.tests.scope3colab_dump import (
    BRANCH_FIELDS,
    SHEET_FIELDS,
    DumpFailed,
    RecordingGeocoder,
    dump,
    main,
    rows_of,
)
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

C6_MAIN: list[Value] = [
    "*국가", "*출장주체", "*교통수단", "*인원수", "출발지", "도착지", "편도거리(km)(선택)", "연간 입력",
    "월별 이동횟수",
    *([None] * 11), "비고(선택)",
]  # fmt: skip
C6_SUB: list[Value] = [*([None] * 7), "연간이동횟수", *MONTH_NAMES, None]
C7_MAIN: list[Value] = [
    "*국가", "*사업장", "*교통수단", "*인원수", "출발지", "도착지", "편도거리(km)(선택)", "연간 입력", "월별 근무일수",
    *([None] * 11), "비고(선택)",
]  # fmt: skip
C7_SUB: list[Value] = [*([None] * 7), "연간근무일수", *MONTH_NAMES, None]

# o3 synthetic.py 의 거리판 줄(같은 값)
C4_1_ROWS: list[list[Value]] = [
    annual(["가상국", "가상사업장A", "가상트럭", "가상수지 원료", "ton", "가상시가", "가상시나", 91], 9.1),
    annual(["가상국", "가상사업장A", "가상화물차", "가상상자 자재", "kg", "가상시가", "가상시다", None], 9200),
    annual(["가상국", "가상사업장B", "가상트럭", "가상부품 자재", "ton", "가상시라", "가상시마", None], 9.3),
    annual(["가상국", "가상사업장B", "가상트럭", "가상서랍 자재", "가상팔레트", "가상시가", "가상시나", 94], 9.4),
    annual(["가상국", "가상사업장A", "가상수레", "가상부속 세트", "kg", "가상시가", "가상시나", 95], 9500),
    monthly(
        ["가상국", "가상사업장A", "가상화물차", "가상의자 자재", "kg", "가상시가", "가상시다", None], {2: 960, 8: 970}
    ),
]
C9_1_ROWS: list[list[Value]] = [
    annual(["가상국", "가상사업장A", "가상항공 화물", "가상의자 완제품", "kg", "가상시파", "가상시하", None], 9100),
    annual(["가상국", "가상사업장B", "가상항공", "가상책상 완제품", "kg", "가상공항가", "ZZQ", None], 9200),
    monthly(["가상국", "가상사업장B", "가상해상 운송", "가상선반 완제품", "ton", None, None, 999], {4: 9.1, 9: 9.2}),
]
C6_1_ROWS: list[list[Value]] = [
    [*["가상국", "가상본부", "가상버스", 9, "가상시사", "가상시아", 99], 9, *([None] * 12)],
    [*["가상국", "가상본부", "가상비행기", 9, "가상시자", "가상시차", None], 9, *([None] * 12)],
    [*["가상국", "가상지사", "가상이동", 9, "가상시사", "가상시아", 9.9], None, *([None] * 2), 9, None, None, None, 9],
    [*["가상국", "가상지사", "가상기차", 9, "가상시가", "가상시다", None], 9, *([None] * 12)],
]
C7_ROWS: list[list[Value]] = [
    [*["가상국", "가상사업장A", "가상승용차", 9, "가상시카", "가상시타", None], 99, *([None] * 12)],
    [*["가상국", "가상사업장B", "가상지하철", 9, None, None, 9.9], None, 9, 9, *([None] * 10)],
    [*["가상국", "가상사업장A", "가상버스 지하철", 9, "가상시가", "가상시다", None], 99, *([None] * 12)],
]

# answers.distance.synthetic.json(32) — (글, expect)
DISTANCE_ANSWERS: list[tuple[str, str]] = [
    ('{"factor": 9.5}', "입력 단위: 가상팔레트\n목표(기준) 단위: kg"),
    ("Synthetic Ga", "변환하라.\n\n    가상시가\n"),
    ("Synthetic Da", "변환하라.\n\n    가상시다\n"),
    ('{"distance_km": 92}', "출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR"),
    ("Synthetic Ra", "변환하라.\n\n    가상시라\n"),
    ("Synthetic Ma", "변환하라.\n\n    가상시마\n"),
    ('{"distance_km": 901}', "출발지: 가상시라\n도착지: 가상시마\n국가 힌트: KR"),
    ('{"distance_km": 99}', "출발지: 가상시라\n도착지: 가상시마\n운송수단: 도로(트럭)"),
    ('{"mode": "rail"}', "텍스트: 가상수레 입고 가상부속 세트\n"),
    ('{"mode": "train"}', "입력값: 가상이동\n"),
    ('{"airport_name": "Synthetic Ja Airport", "iata": ""}', "지역: 가상시자\n국가 힌트: KR"),
    ('{"airport_name": "Synthetic Cha Airport", "iata": ""}', "지역: 가상시차\n국가 힌트: KR"),
    ("Synthetic Ja Airport", "변환하라.\n\n    Synthetic Ja Airport\n"),
    ("Synthetic Cha Airport", "변환하라.\n\n    Synthetic Cha Airport\n"),
    ('{"distance_km": 93}', "출발지: Synthetic Ja Airport\n도착지: Synthetic Cha Airport\n국가 힌트: KR"),
    ("Synthetic Ka", "변환하라.\n\n    가상시카\n"),
    ("Synthetic Ta", "변환하라.\n\n    가상시타\n"),
    ('{"distance_km": 94}', "출발지: 가상시카\n도착지: 가상시타\n국가 힌트: KR"),
    ("Synthetic Pa", "변환하라.\n\n    가상시파\n"),
    ("Synthetic Ha", "변환하라.\n\n    가상시하\n"),
    ('{"distance_km": 902}', "출발지: 가상시파\n도착지: 가상시하\n국가 힌트: KR"),
    ('{"distance_km": 999}', "출발지: 가상시파\n도착지: 가상시하\n운송수단: 도로(트럭)"),
    ('{"airport_name": "Synthetic Pa Airport", "iata": ""}', "지역: 가상시파\n국가 힌트: 가상국"),
    ('{"airport_name": "Synthetic Ha Airport", "iata": ""}', "지역: 가상시하\n국가 힌트: 가상국"),
    ("Synthetic Pa Airport", "변환하라.\n\n    Synthetic Pa Airport\n"),
    ("Synthetic Ha Airport", "변환하라.\n\n    Synthetic Ha Airport\n"),
    ('{"distance_km": 95}', "출발지: Synthetic Pa Airport\n도착지: Synthetic Ha Airport\n국가 힌트: 가상국"),
    ("Synthetic Airport Ga", "변환하라.\n\n    가상공항가\n"),
    ("Synthetic Zzq", "변환하라.\n\n    ZZQ\n"),
    ('{"distance_km": 903}', "출발지: 가상공항가\n도착지: ZZQ\n국가 힌트: KR"),
    ('{"distance_km": 998}', "출발지: 가상공항가\n도착지: ZZQ\n운송수단: 도로(트럭)"),
    ('{"distance_km": 96}', "출발지: 가상공항가\n도착지: ZZQ\n국가 힌트: 가상국"),
]
TRANSPORT_ANSWERS = DISTANCE_ANSWERS[0:9] + DISTANCE_ANSWERS[18:32]  # 23
# o3 run.json `geocode_queries`(distance-transport) — 끝 넷은 행 국가(가상국)라 `, KR` 없음
TRANSPORT_GEOCODE_QUERIES = [
    "Synthetic Ga, KR", "Synthetic Da, KR", "Synthetic Ra, KR", "Synthetic Ma, KR", "Synthetic Pa, KR",
    "Synthetic Ha, KR", "Synthetic Pa Airport", "Synthetic Ha Airport", "Synthetic Airport Ga, KR",
    "Synthetic Zzq, KR", "Synthetic Airport Ga", "Synthetic Zzq",
]  # fmt: skip
# o3 run.json `geocode_queries`(distance, 16) — C4-1 넷 뒤에 C6-1 공항 둘·C7 둘(늘 KR), 그다음 C9-1
DISTANCE_GEOCODE_QUERIES = [
    *TRANSPORT_GEOCODE_QUERIES[0:4], "Synthetic Ja Airport, KR", "Synthetic Cha Airport, KR", "Synthetic Ka, KR",
    "Synthetic Ta, KR", *TRANSPORT_GEOCODE_QUERIES[4:],
]  # fmt: skip
# o3 코랩 쪽 결과(colab.json) — (열쇠, row, item, 갈래, 칸 다섯: 월운송량·화물중량(kg)·운송거리(km)·배출계수(거리기반)·
# 배출량(tCO2e))
COLAB_ROWS: list[tuple[str, int, str, str, tuple[str | None, ...]]] = [
    ("C4", 1, "가상수지 원료", "Distance", ("9.1", "9100", "91", "0.0911", "0.07543991")),
    ("C4", 2, "가상상자 자재", "Distance", ("9200", "9200", "119.6", "0.0911", "0.100239152")),
    ("C4", 3, "가상부품 자재", "Distance", ("9.3", "9300", "99", "0.0911", "0.08387577")),
    ("C4", 4, "가상서랍 자재", "Distance", ("9.4", "89.3", "94", "0.0911", "0.00076471162")),
    ("C4", 5, "가상부속 세트", "Distance", ("9500", "9500", "95", "0.0913", "0.08239825")),
    ("C4", 6, "가상의자 자재", "Distance", ("1930", "1930", "119.6", "0.0911", "0.0210284308")),
    ("C9", 1, "가상의자 완제품", "Distance", ("9100", "9100", None, "0.915", "0.8622090750000001")),
    ("C9", 2, "가상책상 완제품", "Distance", ("9200", "9200", None, "0.915", "0.8808595200000001")),
    ("C9", 3, "가상선반 완제품", "Distance", ("18.3", "18300", "999", "0.0914", "1.67094738")),
]
C6_FORMULA = "배출량(tCO2e) = 이동거리 × 왕복계수 × 인원수 × 이동횟수 × EF / 1000 = "
C7_FORMULA = "배출량(tCO2e) = 평균통근거리 × 왕복계수 × 근무일수 × 직원수 × EF / 1000 = "
# o3 코랩 쪽 결과(`--input distance` 의 colab.json) 가운데 C6·C7 — (열쇠, row, item, 갈래, 칸 여덟: 거리·인원·
# 횟수(C7 은 근무일수)·거리왕복계수·정규화이동수단·배출계수·배출량(tCO2e)·계산식). C6 은 월별 줄(3번)이 먼저, C7 도
# 월별(2번)이 먼저.
COLAB_TRAVEL_ROWS: list[tuple[str, int, str, str | None, tuple[str | None, ...]]] = [
    ("C6", 1, "가상이동", "Distance", ("9.9", "9", "18", "2", "train", "0.0922", "0.2957407200000001",
                                     C6_FORMULA + "9.9 × 2 × 9 × 18 × 0.0922 / 1000 = 0.295741")),
    ("C6", 2, "가상버스", "Distance", ("99", "9", "9", "2", "bus", "0.0923", "1.4803074",
                                     C6_FORMULA + "99 × 2 × 9 × 9 × 0.0923 / 1000 = 1.48031")),
    ("C6", 3, "가상비행기", "Distance", ("101.37", "9", "9", "2", "flight", "0.0921", "1.512460674",
                                       C6_FORMULA + "101.37 × 2 × 9 × 9 × 0.0921 / 1000 = 1.51246")),
    ("C6", 4, "가상기차", "Distance", ("110.4", "9", "9", "2", "train", "0.0922", "1.64897856",
                                     C6_FORMULA + "110.4 × 2 × 9 × 9 × 0.0922 / 1000 = 1.64898")),
    ("C7", 1, "가상지하철", None, ("9.9", "9", "18", "2", "subway", "0.0926", "0.29702376",
                                  C7_FORMULA + "9.9 × 2 × 18 × 9 × 0.0926 / 1000 = 0.297024")),
    ("C7", 2, "가상승용차", None, ("122.2", "9", "99", "2", "car", "0.0924", "20.12106096",
                                  C7_FORMULA + "122.2 × 2 × 99 × 9 × 0.0924 / 1000 = 20.1211")),
    ("C7", 3, "가상버스 지하철", None, ("119.6", "9", "99", "2", "bus", "0.09245", "19.70360964",
                                     C7_FORMULA + "119.6 × 2 × 99 × 9 × 0.09245 / 1000 = 19.7036")),
]  # fmt: skip


# o3 거리판 계수 책의 `운송`(synthetic.py `TRANSPORT_ROWS` — 제목 한 줄, 둘째 줄 머리글)
O3_TRANSPORT_EF = sheet(
    "운송",
    {
        1: ["가상 계수 책 — synthetic(지은 값, 출처 없음)"],
        2: ["운송수단", "표준코드", "배출계수\n(kgCO2eq/ton·km)", "비고"],
        3: ["가상 도로", "road", 0.0911],
        4: ["가상 택배", "parcel", 0.0912],
        5: ["가상 철도", "rail", 0.0913],
        6: ["가상 해상", "sea", 0.0914],
        7: ["가상 항공", "air", 0.915],
        8: ["가상 벌크", "sea_bulk", 0.0916],
        9: ["가상 내륙수로", "inland_water", 0.0917],
    },
)
# o3 거리판 계수 책의 `출장_통근`(synthetic.py `TRAVEL_COMMUTE_ROWS` — 제목 한 줄, 둘째 줄 머리글)
O3_TRAVEL_EF = sheet(
    "출장_통근",
    {
        1: ["가상 계수 책 — synthetic(지은 값, 출처 없음)"],
        2: ["이동수단", "표준코드", "EF\n(kgCO2eq/인·km)", "비고"],
        3: ["가상 항공", "flight", 0.0921],
        4: ["가상 기차", "train", 0.0922],
        5: ["가상 버스", "bus", 0.0923],
        6: ["가상 승용차", "car", 0.0924],
        7: ["가상 택시", "taxi", 0.0925],
        8: ["가상 지하철", "subway", 0.0926],
    },
)


def guide_sheet(name: str, main_head: list[Value], sub: list[Value], rows: list[list[Value]]) -> Sheet:
    """o3 `_template_sheet` 꼴: 안내 한 줄, 머리글 둘, 데이터는 4행부터."""
    return sheet(name, {1: [f"가상 안내 — {name}"], 2: main_head, 3: sub, **{4 + i: r for i, r in enumerate(rows)}})


def distance_template(with_c6_c7: bool) -> tuple[Sheet, ...]:
    c4 = guide_sheet("C4-1_운송거리", DIST_MAIN, DIST_SUB, C4_1_ROWS)
    c9 = guide_sheet("C9-1_운송거리", C9_DIST_MAIN, DIST_SUB, C9_1_ROWS)
    if not with_c6_c7:
        return (c4, c9)
    c6 = guide_sheet("C6-1_출장거리", C6_MAIN, C6_SUB, C6_1_ROWS)
    c7 = guide_sheet("C7_임직원통근", C7_MAIN, C7_SUB, C7_ROWS)
    return (c4, c6, c7, c9)


def write_inputs(tmp_path: Path, template: tuple[Sheet, ...], answers: list[tuple[str, str]]) -> tuple[Path, ...]:
    paths = (tmp_path / "template.xlsx", tmp_path / "book.xlsx", tmp_path / "answers.json")
    paths[0].write_bytes(xlsx_bytes(workbook(*template)))
    paths[1].write_bytes(xlsx_bytes(workbook(sheet("구매_USEPA", BOOK_ROWS), O3_TRANSPORT_EF, O3_TRAVEL_EF)))
    body = {"synthetic": True, "answers": [{"text": t, "expect": e} for t, e in answers]}
    paths[2].write_text(json.dumps(body, ensure_ascii=False), "utf-8")
    return paths


def number(text: str | None) -> Decimal | None:
    return None if text is None else Decimal(text)


def test_the_transport_input_matches_the_colab_rows_and_geocoder_queries(tmp_path: Path) -> None:
    template, book, answers = write_inputs(tmp_path, distance_template(False), TRANSPORT_ANSWERS)
    geocoder = RecordingGeocoder()
    data = dump(template, book, answers, 2025, geocoder)
    assert geocoder.queries == TRANSPORT_GEOCODE_QUERIES
    got = [
        (r["sheet"], r["row"], r["item"], r.get("branch"), tuple(number(v) for v in r["fields"].values()))
        for r in data["rows"]
    ]
    assert got == [(k, n, item, b, tuple(number(v) for v in values)) for k, n, item, b, values in COLAB_ROWS]
    assert {tuple(r["fields"]) for r in data["rows"]} == {
        tuple(name for name, _, _ in BRANCH_FIELDS[("C4", "Distance")])
    }
    assert all(list(r) == ["sheet", "row", "item", "branch", "fields"] for r in data["rows"])


def typed(key: str, branch: str | None, values: Any) -> tuple[Decimal | str | None, ...]:
    """숫자 칸(표의 #)은 `Decimal`, 글 칸은 글 그대로 — esg-lab 견줌과 같은 같음."""
    table = BRANCH_FIELDS[(key, branch)] if branch is not None else SHEET_FIELDS[key]
    return tuple(number(v) if numeric else v for (_, _, numeric), v in zip(table, values, strict=True))


def test_the_distance_template_with_32_answers_matches_the_colab_rows_and_geocoder_queries(tmp_path: Path) -> None:
    """S3C-b2b(B1): 넷 채운 거리판 + 거리판 답 32 — C6-1·C7 을 돌려 16줄, 답 32 를 다 쓰고 지오코더 물음 16 = o3."""
    template, book, answers = write_inputs(tmp_path, distance_template(True), DISTANCE_ANSWERS)
    geocoder = RecordingGeocoder()
    data = dump(template, book, answers, 2025, geocoder)  # 답이 남거나 모자라면 DumpFailed
    assert geocoder.queries == DISTANCE_GEOCODE_QUERIES
    assert len(data["rows"]) == 16 and data["not_compared"] == []
    transport = [
        (r["sheet"], r["row"], r["item"], r.get("branch"), tuple(number(v) for v in r["fields"].values()))
        for r in data["rows"]
        if r["sheet"] in ("C4", "C9")
    ]
    assert transport == [(k, n, item, b, tuple(number(v) for v in values)) for k, n, item, b, values in COLAB_ROWS]
    travel = [
        (r["sheet"], r["row"], r["item"], r.get("branch"), typed(r["sheet"], r.get("branch"), r["fields"].values()))
        for r in data["rows"]
        if r["sheet"] in ("C6", "C7")
    ]
    assert travel == [(k, n, item, b, typed(k, b, values)) for k, n, item, b, values in COLAB_TRAVEL_ROWS]
    assert [r["sheet"] for r in data["rows"]] == ["C4"] * 6 + ["C6"] * 4 + ["C7"] * 3 + ["C9"] * 3


def test_the_distance_template_with_23_answers_misses_at_call_10(tmp_path: Path, capsys: Any) -> None:
    """`:308` 경우(S3C-b2b B1): 넷 채운 거리판 + 운송판 답 23 — 부름 10 이 C6-1 의 이동수단 AI 인데 답 10 은 C9-1 의
    도시 정규화라 어긋난다."""
    template, book, answers = write_inputs(tmp_path, distance_template(True), TRANSPORT_ANSWERS)
    assert main(["--template", str(template), "--factor-book", str(book), "--answers", str(answers)]) == 2
    captured = capsys.readouterr()
    assert (captured.out, captured.err.startswith("도구 실패: DumpFailed(")) == ("", True)
    with pytest.raises(DumpFailed) as failed:
        dump(template, book, answers, 2025)
    assert str(failed.value).startswith(
        "부름 10: 프롬프트에 '변환하라.\\n\\n    가상시파\\n' 가 없다(부름 차례가 어긋남); "
    )


def one_sheet(meta_kind: str, method: str | None) -> ProcessedSheet:
    processor = match_sheet_processor("c4-1_운송거리")
    assert processor is not None
    meta = ActivityMeta(
        4,
        "transport_distance" if meta_kind == "distance" else "transport_spend",
        None,
        ActivityAmount(9.1, "ton", 9100.0, "kg", None),
        ActivityFactor("운송", None, 0.0911, "kgCO2e/ton-km", None, "road"),
        None,
        None,
        None,
        (),
    )
    frame = pd.DataFrame([{"자재명": "가상 품목", "계산방식": method}])
    return ProcessedSheet("c4-1_운송거리", processor, frame, (meta,))


@pytest.mark.parametrize(("kind", "method"), [("distance", "Spend"), ("spend", "Distance")])
def test_a_branch_and_kind_mismatch_fails(kind: str, method: str) -> None:
    with pytest.raises(DumpFailed, match="어긋난다"):
        rows_of((one_sheet(kind, method),), workbook())


def test_a_spend_row_has_no_branch_key_and_a_distance_row_without_method_is_distance() -> None:
    spend = rows_of((one_sheet("spend", "Spend"),), workbook())["rows"][0]
    distance = rows_of((one_sheet("distance", None),), workbook())["rows"][0]
    assert ("branch" in spend, distance["branch"]) == (False, "Distance")
    assert list(distance["fields"]) == [name for name, _, _ in BRANCH_FIELDS[("C4", "Distance")]]


def travel_sheet(name: str, kind: ColabActivityKind, records: list[dict[str, Any]]) -> ProcessedSheet:
    processor = match_sheet_processor(name)
    assert processor is not None
    meta = ActivityMeta(
        4, kind, None, ActivityAmount(9.0, "km", 9.0, "km", None), ActivityFactor("출장_통근", None, 0.922, "kgCO2e/km",
        None, "train"), None, None, None, ()
    )  # fmt: skip
    return ProcessedSheet(name, processor, pd.DataFrame(records), tuple(meta for _ in records))


def test_t8_c6_rows_continue_from_c6_1_to_c6_2_and_c7_is_its_own_key() -> None:
    """T8(S3C-o3 표 1·2·3): C6-1 거리 줄 → C6-2 지출 줄로 row 를 이어 세고(템플릿 시트 차례), 거리 줄만 `Distance`.
    C7 은 열쇠 `C7`(Category7)·item 「이동수단」·갈래 키 없음(결과에 「계산방식」 열이 없다)."""
    c6_1 = travel_sheet(
        "c6-1_출장거리",
        "travel_distance",
        [{"이동수단": "가상기차", "계산방식": "Distance"}, {"이동수단": "가상버스", "계산방식": "Distance"}],
    )
    c6_2 = travel_sheet("c6-2_출장비", "travel_spend", [{"출장수단": "가상 택시비", "계산방식": "Spend"}])
    c7 = travel_sheet("c7_임직원통근", "commute", [{"이동수단": "가상지하철", "교통수단": "가상지하철"}])
    rows = rows_of((c6_1, c6_2, c7), workbook())["rows"]
    assert [(r["sheet"], r["row"], r["item"], r.get("branch")) for r in rows] == [
        ("C6", 1, "가상기차", "Distance"),
        ("C6", 2, "가상버스", "Distance"),
        ("C6", 3, "", None),  # 합친 C6 의 품목 열은 「이동수단」(값이 든 첫 후보) — C6-2 줄에는 그 열이 없다
        ("C7", 1, "가상지하철", None),
    ]
    assert [list(r["fields"]) for r in rows] == [
        *[[name for name, _, _ in BRANCH_FIELDS[("C6", "Distance")]]] * 2,
        [name for name, _, _ in SHEET_FIELDS["C6"]],
        [name for name, _, _ in SHEET_FIELDS["C7"]],
    ]
    assert [name for name, _, _ in BRANCH_FIELDS[("C6", "Distance")]] == [
        "이동거리(km)", "출장인원", "이동횟수", "거리왕복계수", "정규화이동수단", "배출계수", "배출량(tCO2e)", "계산식",
    ]  # fmt: skip
    assert [name for name, _, _ in SHEET_FIELDS["C7"]] == [
        "평균통근거리(km)", "직원수", "근무일수", "거리왕복계수", "정규화이동수단", "배출계수", "배출량(tCO2e)",
        "계산식",
    ]  # fmt: skip
    assert ("C7", "Distance") not in BRANCH_FIELDS


def test_t8_a_commute_row_with_a_distance_method_fails() -> None:
    """C7(`commute`)은 갈래가 없다 — frame 에 「계산방식」 Distance 가 있으면 kind 와 어긋나 도구 실패."""
    c7 = travel_sheet("c7_임직원통근", "commute", [{"이동수단": "가상지하철", "계산방식": "Distance"}])
    with pytest.raises(DumpFailed, match="C7: 「계산방식」 'Distance' 와 줄 kind 'commute' 가 어긋난다"):
        rows_of((c7,), workbook())
