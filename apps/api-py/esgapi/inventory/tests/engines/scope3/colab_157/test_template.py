"""템플릿 읽기(코랩 셀 19·23·24)의 손셈과 시트 대응 21키(S3 의 바닥 — 시트 갈래 자체는 test_pipeline.py).

읽기는 엔진이 실제로 도는 문맥(`legacy_strings` — `pipeline.run` 이 건다)에서 부른다(경계 ② 검증 N1): 기본 문맥에서는
「입력방식」 같은 지은 글 열이 pandas 3 의 `str` 이 된다.
"""

from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.engines.scope3.colab_157.template import (
    KNOWN_TEMPLATE_HEADERS,
    SHEET_PROCESSOR_MAP,
    TEMPLATE_ROW,
    detect_template_header_row,
    is_new_template,
    match_sheet_processor,
    read_template_rows,
    read_template_sheet,
    sum_monthly_spend,
)
from esgapi.inventory.tests.engines.scope3.colab_157.support import sheet
from esgapi.inventory.tests.engines.scope3.colab_157.test_frames import C1_ROWS


def test_known_headers_are_the_union_of_the_four_definitions() -> None:
    # 읽기판 네 정의(33·55·10·67개)의 합집합 = 106 — 읽기판 블록을 `ast.literal_eval` 로 따로 세어 맞춤(2026-10-19).
    assert len(KNOWN_TEMPLATE_HEADERS) == 106
    for word in ("법인명", "판매량", "구매 월", "재활용 비중(%)(선택)"):  # :2076 · :2293 · :3451 · :5681 에서 하나씩
        assert word in KNOWN_TEMPLATE_HEADERS


def test_the_sheet_map_keeps_all_twenty_one_keys_in_colab_order() -> None:
    keys = list(SHEET_PROCESSOR_MAP)
    assert len(keys) == 21
    assert keys[:2] == ["c1_구매품서비스", "c2_자본재"] and keys[-1] == "c15_투자"
    assert [p.band for p in SHEET_PROCESSOR_MAP.values()].count("S3C-a") == 2


def test_match_exact_then_contains_then_first_four_letters() -> None:
    assert match_sheet_processor("C1_구매품서비스") is SHEET_PROCESSOR_MAP["c1_구매품서비스"]
    assert match_sheet_processor(" C2_자본재 ") is SHEET_PROCESSOR_MAP["c2_자본재"]
    # 앞 4글자 겹침: 「c1_구」 로 시작하면 C1 — 코랩 그대로(이름이 조금 달라도 잡힌다)
    assert match_sheet_processor("c1_구매내역(가상)") is SHEET_PROCESSOR_MAP["c1_구매품서비스"]
    # dict 차례: 「c13-1_…」 은 「c1_구…」 의 앞 4글자 「c1_구」 와 다르고, 「c13-」 키보다 앞선 키가 먼저 걸린다
    assert match_sheet_processor("c13-9_가상") is SHEET_PROCESSOR_MAP["c13-1_에너지사용량 아는경우"]
    assert match_sheet_processor("배출계수_드롭다운") is None
    assert match_sheet_processor("드롭다운_매핑검토") is None


def test_new_template_is_a_sheet_starting_with_c_and_a_digit() -> None:
    assert is_new_template(["표지", "C1_구매품서비스"])
    assert not is_new_template(["01_구매_Template", "cover"])


def test_header_row_detection_and_template_read_on_a_c1_sheet() -> None:
    c1 = sheet("C1_구매품서비스", C1_ROWS)
    with legacy_strings():
        assert detect_template_header_row(c1) == 3  # 4행(0부터 3) — * 칸 넷 × 2 + 아는 머리글
        df = read_template_sheet(c1)
        rows = read_template_rows(c1)
    assert list(df.columns) == [
        "국가", "사업장", "품목군", "상세 품목명/서비스명", "거래처명(선택)",
        "연간지출금액(원)", "1월", "2월", "비고(선택)", "입력방식",
    ]  # fmt: skip
    assert len(df) == 3  # 가운데 빈 줄(8행)은 걷힌다
    assert df["입력방식"].tolist() == ["연간", "월별", "연간"]
    assert df["입력방식"].dtype == object  # 2.x 꼴(기본 문맥이면 str)
    # 같은 frame 에 엑셀 줄 번호 열을 더한 것(가운데 빈 8행은 빠진다)
    assert rows.drop(columns=[TEMPLATE_ROW]).equals(df)
    assert rows[TEMPLATE_ROW].tolist() == [6, 7, 9]


def test_monthly_rows_sum_into_the_spend_column() -> None:
    with legacy_strings():
        df = read_template_sheet(sheet("C1_구매품서비스", C1_ROWS)).rename(columns={"연간지출금액(원)": "구매금액"})
        out = sum_monthly_spend(df, "구매금액")
    assert out["구매금액"].tolist()[1] == 9.5 + 9000
    assert out["구매금액"].tolist()[0] == 9100000
