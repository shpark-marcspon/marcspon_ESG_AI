"""bilingual.py(코랩 셀 52) — 손으로 지은 기대값(발주서 §3 S1 의 attach_korean_originals)."""

from esgapi.translation.engines.colab_158.bilingual import attach_korean_originals, first_diff_line

SOURCE = "\n".join(
    [
        "[PAGE 1]",
        "[BLOCK 1]",
        "기후변화 대응 전략",
        "가상 회사는 온실가스를 관리합니다.",
        "[TABLE 1]",
        "에너지 사용량",
        "| 항목 | 2025 |",
        "| --- | --- |",
        "| 전력 | 1 |",
        "[VISUAL 1]",
        "title: 배출 추이",
        "legend: 연도",
        "[PAGE 2]",
        "[BLOCK 2]",
        "ESG Management",
        "ESG 경영 체계",
    ]
)
TRANSLATED = "\n".join(
    [
        "[PAGE 1]",
        "[BLOCK 1]",
        "Climate Action Strategy",
        "ABC Corp manages GHG emissions.",
        "[TABLE 1]",
        "Energy Use",
        "| Item | 2025 |",
        "| --- | --- |",
        "| Electricity | 1 |",
        "[VISUAL 1]",
        "title: Emission Trend",
        "legend: Year",
        "",
        "[PAGE 2]",
        "[BLOCK 2]",
        "ESG Management",
        "ESG Management System",
        "",
        "[PAGE 3]",
        "[BLOCK 1]",
        "No source page",
    ]
)


def test_titles_get_the_korean_original_once() -> None:
    """R/4012-4063: BLOCK 첫 실질 줄·TABLE 제목·VISUAL title 에만. 원문에 이미 영문으로 있던 제목(쪽 2 — 국문보다 영문이
    먼저)은 병기하지 않는다(R/3688-3727). 원문에 없는 쪽은 그대로. 쪽 사이는 빈 줄 하나."""
    assert attach_korean_originals(TRANSLATED, SOURCE) == "\n".join(
        [
            "[PAGE 1]",
            "[BLOCK 1]",
            "Climate Action Strategy (기후변화 대응 전략)",
            "ABC Corp manages GHG emissions.",
            "[TABLE 1]",
            "Energy Use (에너지 사용량)",
            "| Item | 2025 |",
            "| --- | --- |",
            "| Electricity | 1 |",
            "[VISUAL 1]",
            "title: Emission Trend (배출 추이)",
            "legend: Year",
            "",
            "[PAGE 2]",
            "[BLOCK 2]",
            "ESG Management",
            "ESG Management System",
            "",
            "[PAGE 3]",
            "[BLOCK 1]",
            "No source page",
        ]
    )


def test_first_diff_line_skips_long_and_equal_lines() -> None:
    """R/3762-3792: 태그·pipe·국문 없는 줄·80자 넘는 줄·번역 첫 줄과 같은 줄은 건너뛴다."""
    lines = ["[CAPTION]", "| 가 |", "English", "가" * 81, "같은 줄", "제목 후보"]
    assert first_diff_line(lines, "같은 줄") == "제목 후보"
    assert first_diff_line(["English only"], "x") == ""
