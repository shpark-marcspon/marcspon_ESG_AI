"""engines/colab_155/whitelists.py: 판 셋의 출처 수(64·59·63), 셀 17 현행 = 셀 71 + 한국 공공 다섯 − EU 의 빈 「9.」 줄,
셀 73 의 겹친 줄 그대로, whitelist_for 가 sector 로 셀 71·73 을 고름(발주서 §3 S3, 처분 ⑥ 가)."""

import pytest

from esgapi.materiality.engines.colab_155 import whitelists


def sources(raw: str) -> list[str]:
    return [line for line in raw.split("\n") if "https://" in line]


def test_source_counts() -> None:
    assert len(sources(whitelists.WHITELIST_COLAB17)) == 64
    assert len(sources(whitelists.WHITELIST_CELL71)) == 59
    assert len(sources(whitelists.WHITELIST_CELL73)) == 63


def test_colab17_is_cell71_plus_five_public_sites_minus_the_empty_nine() -> None:
    colab17 = whitelists.WHITELIST_COLAB17.split("\n")
    cell71 = whitelists.WHITELIST_CELL71.split("\n")
    added = [line for line in colab17 if line not in cell71]
    removed = [line for line in cell71 if line not in colab17]
    assert [line.split(" https://")[0].strip() for line in added] == [
        "12. ALIO",
        "13. 공공데이터 포털",
        "14. 국가통계 포털",
        "15. 클린아이",
        "16. 재정경제부",
    ]
    assert removed == ["              9."]
    rebuilt = [line for line in cell71 if line not in removed]
    at = rebuilt.index("              11. 한국거래소(KRX) https://www.krx.co.kr/main/main.jsp") + 1
    assert rebuilt[:at] + added + rebuilt[at:] == colab17


def test_cell73_keeps_its_doubled_lines_and_gaps() -> None:
    lines = whitelists.WHITELIST_CELL73.split("\n")
    assert sum("https://www.law.go.kr/main.html" in line for line in lines) == 2
    assert sum("https://www.better.go.kr/zz.main.PortalMain" in line for line in lines) == 2
    assert sum("https://www.federalregister.gov/" in line for line in lines) == 2
    us = lines[lines.index("          2. 미국") : lines.index("          3. EU")]
    numbers = [line.strip().split(".")[0] for line in us[1:] if line.strip()]
    assert "9" not in numbers
    assert not lines[0].lstrip().startswith("#")  # 셀 73 머리의 지시 주석은 뺐다


@pytest.mark.parametrize(
    "raw", [whitelists.WHITELIST_COLAB17, whitelists.WHITELIST_CELL71, whitelists.WHITELIST_CELL73]
)
def test_each_block_is_raw_text_with_six_spaces(raw: str) -> None:
    lines = raw.split("\n")
    assert lines[-1] == ""  # 끝 줄바꿈 하나
    assert lines[0] == "      " + "=" * 69
    assert lines[1] == "      [8] 신뢰할 수 있는 출처 리스트"
    assert min(len(line) - len(line.lstrip(" ")) for line in lines if line.strip()) == 6


def test_whitelist_for_picks_by_sector() -> None:
    assert whitelists.whitelist_for("financial") == ("cell71", whitelists.WHITELIST_CELL71)
    assert whitelists.whitelist_for("non_financial") == ("cell73", whitelists.WHITELIST_CELL73)
    with pytest.raises(ValueError, match="sector"):
        whitelists.whitelist_for("public")
