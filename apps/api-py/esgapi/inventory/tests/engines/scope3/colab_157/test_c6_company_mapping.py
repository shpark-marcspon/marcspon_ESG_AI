"""C6-2 회사별 매핑과 후처리의 파일 왕복(검증 ② 블로커 — 심은 W7·W4b·W6 을 무는 손셈).

코랩 줄(읽기판): 표준화 `standardize_c6_spend_sheet`(`:6728-6746`)가 「출장항목」 → 「이동수단」 으로 바꾸고
「출장수단」 을 그 **복사**로 지은 **뒤에** 회사별 매핑(`:5982-5985`, 「상세 교통수단명(선택)」 열이 있을 때만)이
「이동수단」 의 빈 칸을 채운다 — 「출장수단」 은 빈 채로 남는다(결함 후보 ㉠). 후처리 `_fix_result_c6`(`:8821`)는
결과 파일을 다시 읽은 줄로 셈하고(`COLS_TO_DROP` 과 **전부 빈 열**이 지워진 파일 — `:6237-6241`), 이동수단은
`row.get("출장수단") or row.get("이동수단")` 차례로 다시 정규화한다.

    한 줄 시트: 출장항목 빈 칸 · 상세명이 매핑에 걸림 → 갈래 셈의 품목 글은 ""(NaN 이 참) 이라 계수 없음.
        왕복에서 「출장수단」 이 전부 빈 열이라 지워져 품목 글 = 매핑된 「이동수단」 → 수동 표의 항공 계수 · flight.
    두 줄 시트: 둘째 줄이 「출장항목」 을 채워 「출장수단」 열이 남는다 → 첫 줄은 NaN 이 참으로 이겨 품목 글 ""·car.
"""

from esgapi.inventory.engines.scope3.colab_157.pipeline import ProcessedSheet
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import (
    activity_metas,
    column,
    processed,
    run_sheets,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_travel_spend import AIR, TAXI, V_ROWS

HEAD: list[Value] = ["*사업장", "*출장항목", "상세 교통수단명(선택)", "연간 입력"]
SUB: list[Value] = [None, None, None, "연간지출금액(원)"]
COMPANY = sheet("기업정보", {7: [None, None, "가상회사"]})
MAPPING = sheet(
    "회사별_교통수단매핑",
    {
        1: ["회사", "상세명", "교통수단"],
        2: ["가상회사", "가상상세비행", "가상 항공권"],
        3: ["가상다른회사", "가상상세비행", "가상 버스"],
    },
)


def c6(*rows: list[Value]) -> ProcessedSheet:
    template = sheet("c6-2_출장비", {4: HEAD, 5: SUB, **{6 + i: row for i, row in enumerate(rows)}})
    outcomes = run_sheets([template, COMPANY, MAPPING], [sheet("출장_Spend", V_ROWS)])
    return processed(outcomes[0])


def test_the_mapping_fills_only_the_renamed_column_and_the_round_trip_finds_it() -> None:
    done = c6(["가상사업장", None, "가상상세비행", 9100000])
    frame = done.frame
    assert column(frame, "이동수단") == ["가상 항공권"]  # 매핑이 채움(:5982)
    assert column(frame, "출장수단") == [None]  # 표준화의 복사가 매핑보다 앞(결함 후보 ㉠)
    assert column(frame, "EF_DB") == [AIR]  # 왕복에서 「출장수단」 열이 지워져 「이동수단」 이 품목 글
    assert column(frame, "배출계수") == [9.21e-05]
    assert column(frame, "배출량(tCO2e)") == [9100000 * 9.21e-05 / 1000.0]
    assert column(frame, "정규화이동수단") == ["flight"]
    (meta,) = activity_metas(done)
    assert [(s.step, s.origin, s.via) for s in meta.steps] == [
        ("mapping", "rule", "company_mapping"),
        ("factor", "rule", "manual"),
        ("mode", "rule", "rule_fix"),
    ]
    assert meta.origin == "rule"


def test_a_filled_copy_column_survives_the_round_trip_and_nan_wins() -> None:
    done = c6(["가상사업장", None, "가상상세비행", 9100000], ["가상사업장", "가상 택시비", None, 9300000])
    frame = done.frame
    assert column(frame, "이동수단") == ["가상 항공권", "가상 택시비"]
    assert column(frame, "출장수단") == [None, "가상 택시비"]
    # 첫 줄: 「출장수단」 열이 남아 NaN 이 참으로 이김 → 품목 글 "" → 계수 없음, 이동수단 "" → car(AI 0)
    assert column(frame, "EF_DB") == [None, TAXI]
    assert column(frame, "배출량(tCO2e)") == [None, 9300000 * 9.23e-05 / 1000.0]
    assert column(frame, "정규화이동수단") == ["car", "taxi"]
    first, second = activity_metas(done)
    assert [s.step for s in first.steps] == ["mapping", "mode"]
    assert first.mode is not None and (first.mode.value, first.mode.origin) == ("car", "estimate")
    assert first.origin is None  # factor 단계가 없다
    assert [s.step for s in second.steps] == ["factor", "mode"]
