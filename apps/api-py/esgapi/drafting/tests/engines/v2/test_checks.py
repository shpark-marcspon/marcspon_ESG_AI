"""출처 검사(engines/v2/checks.py — RP2b B5): ⓐ 준 블록 ⓑ 번호 범위 ⓒ 남은 출처 ⓓ 숫자가 출처 블록 글에. 순수 층.
블록은 지어낸 뷰를 재료로 지어 쓴다(material.given)."""

from typing import Any

from esgapi.core.tests.artifact_fakes import FakeArtifactView, block, fake_document, table
from esgapi.drafting.engines.v2 import checks, material


def given() -> dict[str, material.GivenBlock]:
    document = fake_document(
        "c" * 64,
        page_count=2,
        blocks=[
            block(
                "p1-b1",
                "가상 회사는 여러 가상 사업장에서 설비를 바꾸고 공정을 고쳐 온실가스 배출량을 1,200 톤 줄였다. "
                "감축률은 3.5%다 — 가상 회사의 지난해 가상 보고서와 견준 값이며 "
                "가상 사업장 전부의 합으로 다시 셈한 것이다.",
                page=1,
                order=1,
            ),
            block("p1-b2", "다른 블록의 숫자 777 이다.", page=1, order=2),
            block("p1-b3", "제목 2025", page=1, order=3, kind="heading"),
            block("p2-b1", kind="table", table_id="p2-t1", page=2, order=1),
        ],
        tables=[
            table(
                "p2-t1", [["구분", "2024"], ["사용량", "300"], ["재활용", "45"]], page=2, footnote_marks=[(2, 0, "9)")]
            )
        ],
    )
    return material.material([1, 2], FakeArtifactView.from_dicts(document)).given


def run(text: str, *sources: tuple[str, int | None]) -> tuple[dict[str, Any], list[str]]:
    bullet = {"text": text, "sources": [{"block": b, "s": s} for b, s in sources]}
    (checked,), warnings = checks.check([bullet], key="k", given=given(), document_id=31)
    return checked, [w["code"] for w in warnings]


def test_b5_a_given_block_and_sentence_in_range_is_kept() -> None:
    checked, codes = run("배출량 1,200 톤 감축", ("p1-b1", 0))
    assert checked == {
        "text": "배출량 1,200 톤 감축",
        "sources": [{"documentId": 31, "blockId": "p1-b1", "page": 1, "index": 0}],
        "unsupported": False,
    }
    assert codes == []


def test_b5_a_not_given_block_is_dropped() -> None:
    checked, codes = run("배출량 1,200 톤", ("p9-b9", 0), ("p1-b1", 0))
    assert [s["blockId"] for s in checked["sources"]] == ["p1-b1"] and codes == ["source_not_given"]


def test_b5_an_out_of_range_sentence_keeps_the_block_without_a_sentence() -> None:
    checked, codes = run("배출량 1,200 톤", ("p1-b1", 2))
    assert checked["sources"] == [{"documentId": 31, "blockId": "p1-b1", "page": 1, "index": None}]
    assert checked["unsupported"] is False and codes == ["sentence_out_of_range"]
    _, heading = run("제목 2025", ("p1-b3", 0))  # 제목은 번호가 없다 — s 는 null 이어야
    assert heading == ["sentence_out_of_range"]
    kept, none = run("제목 2025", ("p1-b3", None))
    assert kept["sources"][0]["index"] is None and none == []


def test_b5_no_source_left_is_unsupported() -> None:
    checked, codes = run("근거 없는 줄", ("p9-b9", 0))
    assert checked["sources"] == [] and checked["unsupported"] is True
    assert codes == ["source_not_given", "unsupported_bullet"]
    _, empty = run("근거 없는 줄")
    assert empty == ["unsupported_bullet"]


def test_b5_a_number_only_in_another_block_is_unsupported() -> None:
    """472 일부: 숫자 대조는 쪽 글이 아니라 출처 블록 글 — 같은 쪽 다른 블록에만 있는 777 은 근거가 아니다."""
    checked, codes = run("숫자 777", ("p1-b1", 0))
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]
    assert run("숫자 777", ("p1-b2", 0))[0]["unsupported"] is False


def test_b5_numbers_are_matched_against_the_whole_source_block() -> None:
    """번호가 0 이어도 숫자 대조는 블록 글의 합(문장 1 의 3.5 도 지남), 쉼표는 정규화."""
    assert run("감축률 3.5%, 1200 톤", ("p1-b1", 0))[0]["unsupported"] is False


def test_b5_a_table_source_is_matched_against_all_its_row_lines_with_footnotes() -> None:
    assert run("사용량 300", ("p2-t1", 0))[0]["unsupported"] is False  # 다른 행의 숫자도 지남
    assert run("재활용 45 (주 9)", ("p2-t1", 2))[0]["unsupported"] is False  # 각주 표시 「9)」 도 행 줄 안
    checked, codes = run("사용량 1,200", ("p2-t1", 1))  # 표 밖 숫자
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]
    _, empty_row = run("사용량 300", ("p2-t1", 5))
    assert empty_row == ["sentence_out_of_range"]


def test_b5_duplicates_collapse_and_sources_are_ordered() -> None:
    checked, codes = run(
        "1,200 톤과 300",
        ("p2-t1", 1),
        ("p1-b2", 0),
        ("p1-b1", 1),
        ("p1-b1", 1),
        ("p1-b1", None),
        ("p1-b1", 0),
        ("p1-b1", 9),
    )
    assert [(s["blockId"], s["index"]) for s in checked["sources"]] == [
        ("p1-b1", None),
        ("p1-b1", 0),
        ("p1-b1", 1),
        ("p1-b2", 0),
        ("p2-t1", 1),
    ]
    assert codes == ["sentence_out_of_range"] and checked["unsupported"] is False


def test_b5_warnings_carry_the_key_and_the_block_page() -> None:
    bullet = {"text": "x", "sources": [{"block": "p2-t1", "s": 7}]}
    _, warnings = checks.check([bullet], key="k", given=given(), document_id=31)
    assert warnings == [
        {
            "code": "sentence_out_of_range",
            "message": "근거 블록에 없는 문장 번호를 댔다(블록만 남김).",
            "key": "k",
            "page": 2,
        }
    ]


def test_numbers() -> None:
    """v1 test_number_normalisation·test_3_5_is_not_35 의 짝(걷은 engines/v1/checks 를 v2 가 잇는다)."""
    assert checks.numbers("1,200 톤, 3.5% 와 2030,") == {"1200", "3.5", "2030"}
    assert checks.numbers("3.5") == {"3.5"} and "35" not in checks.numbers("3.5")
    checked, codes = run("감축률 35%", ("p1-b1", 1))  # 출처 블록엔 3.5 뿐 — 35 는 근거가 아니다
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


# RPS2 — 짧은 블록일 때만 같은 쪽 표·앞뒤 블록까지(넓힘), 날짜 숫자, 정수 앞 0. 지어낸 쪽들(글·숫자 모두 가상).
LONG = (
    "가상 회사는 가상 사업장 전부에서 설비 점검과 공정 개선을 해 마다 이어 왔고 그 결과를 이 가상 보고서의 여러 절에 "
    "나누어 적었다. 이 문단은 숫자 없이 길게 쓴 가상 설명 글이며 짧은 블록 문턱보다 길게 일부러 늘려 쓴 것이다."
)
CUT = "가상 긴 글 4242 이다. " * 700  # 쪽 몫(PAGE_MAX_CHARS)을 넘어 재료에서 통째로 빠지는 블록


def wide_given(edge: int | None = None) -> dict[str, material.GivenBlock]:
    """쪽 1: 긴 문단 Lp · 제목 H · 표 T · 짧은 문단 S · 다음 문단 S+1 · 채움 X · 먼 문단 F. 쪽 2: 표 T2 · (쪽 1 끝 다음
    차례 번호의) 첫 글. 쪽 3: 짧은 글 · 잘려 빠지는 긴 글 · 그 다음 글. 쪽 4: 짧은 표 · 이웃 글. 쪽 5: 날짜·앞 0 글.
    쪽 7: 짧은 글 · 숫자 없는 이웃 · +2 자리 글 · 채움 · 먼 표. 쪽 8: SHORT_MAX 넘는 제목 · 이웃 글 · 점 날짜 글.
    edge 를 주면 쪽 6 에 글자 수 edge 인 문단 · 표."""
    blocks = [
        block("p1-b1", LONG, page=1, order=1),
        block("p1-b2", "가상 배출 현황", page=1, order=2, kind="heading"),
        block("p1-b3", kind="table", table_id="p1-t3", page=1, order=3),
        block("p1-b4", "가상 사업장의 올해 배출량은 약", page=1, order=4),
        block("p1-b5", "3.4톤 수준으로 줄었다.", page=1, order=5),
        block("p1-b6", "가상 채움 글이다.", page=1, order=6),
        block("p1-b7", "가상 목표 연도는 2025년이다.", page=1, order=7),
        block("p2-b1", kind="table", table_id="p2-t1", page=2, order=1),
        block("p2-b8", "다음 쪽 글 999", page=2, order=8),
        block("p3-b1", "가상 짧은 줄", page=3, order=1),
        block("p3-b2", CUT, page=3, order=2),
        block("p3-b3", "가상 뒤 글 5151", page=3, order=3),
        block("p4-b1", kind="table", table_id="p4-t1", page=4, order=1),
        block("p4-b2", "가상 이웃 글 7171", page=4, order=2),
        block("p5-b1", "가상 위원회 2025.05.22 시행", page=5, order=1),
        block("p5-b2", "가상 점검은 05월에 했다.", page=5, order=2),
        block("p7-b1", "가상 짧은 머리", page=7, order=1),
        block("p7-b2", "가상 다음 글", page=7, order=2),
        block("p7-b3", "가상 둘째 뒤 8181", page=7, order=3),
        block("p7-b4", "가상 채움 글이다.", page=7, order=4),
        block("p7-b5", kind="table", table_id="p7-t5", page=7, order=5),
        block("p8-b1", "가상 긴 제목 " + "가" * 70, page=8, order=1, kind="heading"),
        block("p8-b2", "가상 이웃 3131", page=8, order=2),
        block("p8-b3", "가상 날짜 2025.12.31 기준", page=8, order=3),
    ]
    tables = [
        table("p1-t3", [["구분", "2023", "2024"], ["가상 배출량", "410", "395"]], page=1),
        table("p2-t1", [["구분", "2025"], ["가상 값", "88"]], page=2),
        table("p4-t1", [["가상", "1"]], page=4),
        table("p7-t5", [["구분", "가상"], ["값", "9292"]], page=7),
    ]
    pages = [1, 2, 3, 4, 5, 7, 8]
    if edge is not None:
        blocks += [
            block("p6-b1", "가".ljust(edge, "나"), page=6, order=1),
            block("p6-b2", kind="table", table_id="p6-t1", page=6, order=2),
        ]
        tables.append(table("p6-t1", [["구분", "가상"], ["값", "6161"]], page=6))
        pages.append(6)
    document = fake_document("d" * 64, page_count=8, blocks=blocks, tables=tables)
    return material.material(pages, FakeArtifactView.from_dicts(document)).given


def wide(
    text: str, block_id: str, given: dict[str, material.GivenBlock] | None = None
) -> tuple[dict[str, Any], list[str]]:
    bullet = {"text": text, "sources": [{"block": block_id, "s": None}]}
    (checked,), warnings = checks.check([bullet], key="k", given=given or wide_given(), document_id=31)
    return checked, [w["code"] for w in warnings]


def test_rps2_the_fake_page_is_what_the_tests_assume() -> None:
    found = wide_given()
    assert len(found["p1-b1"].text) > 120 and found["p1-b2"].kind == "heading"
    assert "p3-b2" not in found and {"p3-b1", "p3-b3"} <= set(found)  # 잘려 빠진 블록
    assert len(found["p1-b4"].text) <= checks.SHORT_MAX


def test_rps2_w1_a_heading_source_takes_the_numbers_of_a_table_on_its_page_and_sources_stay() -> None:
    checked, codes = wide("가상 배출량 410 에서 395 로", "p1-b2")
    assert checked == {
        "text": "가상 배출량 410 에서 395 로",
        "sources": [{"documentId": 31, "blockId": "p1-b2", "page": 1, "index": None}],
        "unsupported": False,
    }
    assert codes == []


def test_rps2_w2_a_short_paragraph_takes_the_next_block_of_a_broken_line() -> None:
    assert wide("배출량은 약 3.4톤", "p1-b4")[0]["unsupported"] is False


def test_rps2_w3_the_short_limit_is_inclusive() -> None:
    at = wide_given(checks.SHORT_MAX)
    assert len(at["p6-b1"].text) == checks.SHORT_MAX
    assert wide("가상 값 6161", "p6-b1", at)[0]["unsupported"] is False
    over = wide_given(checks.SHORT_MAX + 1)
    checked, codes = wide("가상 값 6161", "p6-b1", over)
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


def test_rps2_n1_a_long_block_stays_strict() -> None:
    """긴 Lp 를 짚으면 같은 쪽 표(395)도, 이웃 제목도 보지 않는다."""
    checked, codes = wide("가상 배출량 395", "p1-b1")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]
    assert wide("가상 배출량 395", "p1-b2")[0]["unsupported"] is False  # 같은 수가 짧은 제목을 짚으면 지남


def test_rps2_a_short_block_takes_its_neighbour_number_in_the_old_page() -> None:
    """B1 짝: 옛 바탕의 짧은 문단 p1-b2 를 짚으면 앞 이웃(긴 문단 p1-b1)의 1,200 은 받는다 — 긴 p1-b1 을 짚은 777 은
    그대로 근거 아님(test_b5_a_number_only_in_another_block_is_unsupported)."""
    assert run("1,200 톤", ("p1-b2", 0))[0]["unsupported"] is False
    assert run("숫자 777", ("p1-b1", 0))[0]["unsupported"] is True


def test_rps2_n2_a_wrong_year_is_not_let_through_by_a_far_block_or_another_page() -> None:
    """562 D 꼴: 표 머리는 2023·2024 뿐 — 2025 는 먼 블록(±k 밖)과 다른 쪽 표에만."""
    checked, codes = wide("2025년 가상 배출량 395", "p1-b2")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


def test_rps2_n3_neighbours_do_not_cross_the_page() -> None:
    """쪽 1 끝 블록(차례 7)의 다음 차례 번호 8 은 쪽 2 에만 있다 — 보지 않는다."""
    checked, codes = wide("가상 999", "p1-b7")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


def test_rps2_n4_a_neighbour_cut_from_the_material_is_not_read_and_the_walk_stops_there(monkeypatch: Any) -> None:
    checked, codes = wide("가상 4242", "p3-b1")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]
    monkeypatch.setattr(checks, "NEIGHBOURS", 2)  # 빠진 자리(차례 2)를 건너 차례 3 으로 가지 않는다
    assert wide("가상 5151", "p3-b1")[0]["unsupported"] is True


def test_rps2_n5_a_table_source_is_not_widened_even_if_short() -> None:
    checked, codes = wide("가상 7171", "p4-t1")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


def test_rps2_n6_a_number_nowhere_near_is_unsupported() -> None:
    checked, codes = wide("가상 배출량 512", "p1-b2")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


def test_rps2_d1_a_date_reads_as_year_month_day() -> None:
    for text in ("2025.05.22", "2025-05-22", "2025/05/22", "2025.05.22.", "시행 2025.5.22 부터"):
        assert checks.numbers(text) == {"2025", "5", "22"}, text
    assert wide("2025년 가상 위원회", "p5-b1")[0]["unsupported"] is False
    checked, codes = wide("2026년 가상 위원회", "p5-b1")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


def test_rps2_d2_decimals_and_version_numbers_are_not_dates() -> None:
    assert checks.numbers("3.4") == {"3.4"}
    assert checks.numbers("2025.05") == {"2025.05"}  # 두 조각은 소수 그대로
    assert checks.numbers("1.2.3.4") == {"1.2", "3.4"}  # 판 번호 꼴 — 날짜 아님
    assert checks.numbers("2025.05.22.7") == {"2025.05", "22.7"}
    assert checks.numbers("2025.05-22") == {"2025.05", "22"}  # 구분자가 다르면 날짜 아님


def test_rps2_d3_leading_zeros_of_whole_numbers_are_dropped() -> None:
    assert checks.numbers("05월 007") == {"5", "7"}
    assert checks.numbers("0") == {"0"} and checks.numbers("0.5") == {"0.5"} and checks.numbers("05.5") == {"05.5"}
    assert wide("가상 점검 5월", "p5-b2")[0]["unsupported"] is False


def test_rps2_v1_a_block_two_places_away_is_not_read_with_k_1() -> None:
    """검증 V1: 넓힘은 앞뒤 NEIGHBOURS(1) 자리까지 — +2 자리에만 있는 수는 근거 아님."""
    assert checks.NEIGHBOURS == 1
    checked, codes = wide("가상 8181", "p7-b1")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]


def test_rps2_v3_a_table_beyond_the_neighbours_on_the_same_page_is_read() -> None:
    """검증 V3: 같은 쪽 표는 ±k 밖이어도 본다(차례 1 의 짧은 글 ↔ 차례 5 의 표)."""
    checked, codes = wide("가상 값 9292", "p7-b1")
    assert checked["unsupported"] is False and codes == []


def test_rps2_v2_a_heading_is_widened_even_when_longer_than_the_short_limit() -> None:
    """검증 V2: 제목은 글자 수와 상관없이 짧은 블록."""
    assert len(wide_given()["p8-b1"].text) > checks.SHORT_MAX
    assert wide("가상 3131", "p8-b1")[0]["unsupported"] is False


def test_rps2_r1_a_dotted_source_date_also_gives_its_year_month() -> None:
    """검증 R1(감독 정함): 출처 「2025.12.31」 은 「2025.12」 토막도 — bullet 「2025.12」(두 조각 = 소수)가 BASE 처럼
    지남."""
    assert checks.numbers("2025.12.31", source=True) == {"2025", "12", "31", "2025.12"}
    assert checks.numbers("2025.12.31") == {"2025", "12", "31"}  # bullet 쪽은 토막 없음
    assert checks.numbers("2025-12-31", source=True) == {"2025", "12", "31"}  # 점 날짜만
    assert wide("가상 2025.12 기준", "p8-b3")[0]["unsupported"] is False
    assert wide("2025.05 가상 위원회", "p5-b1")[0]["unsupported"] is False  # 출처 「2025.05.22」
    checked, codes = wide("2025.11 가상 위원회", "p5-b1")
    assert checked["unsupported"] is True and codes == ["number_not_in_source"]
