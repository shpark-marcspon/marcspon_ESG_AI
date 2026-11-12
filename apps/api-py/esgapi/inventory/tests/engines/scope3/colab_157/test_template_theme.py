"""시트 대응 21키의 (키, 카테고리, 테마) — 코랩 `:5641-5663` 에 뒤 셀의 `update` 를 얹은 값.

c8-1~3·c13-1~3 → energy(`:7109-7124`), c11 → sold_product_use(`:7786-7789`, `MARC-ISSUE-193` 6).
나머지는 `:5641` 그대로.
"""

from esgapi.inventory.engines.scope3.colab_157.template import SHEET_PROCESSOR_MAP

EXPECTED: list[tuple[str, str, str, str]] = [
    ("c1_구매품서비스", "c1", "Category1", "purchase"),
    ("c2_자본재", "c2", "Category2", "purchase"),
    ("c3_연료에너지", "c3", "Category3", "energy"),
    ("c4-1_운송거리", "c4_dist", "Category4", "transport"),
    ("c4-2_운송금액", "c4_spend", "Category4", "transport"),
    ("c5_사업장폐기물", "c5", "Category5", "waste"),
    ("c6-1_출장거리", "c6_dist", "Category6", "travel"),
    ("c6-2_출장비", "c6_spend", "Category6", "travel"),
    ("c7_임직원통근", "c7", "Category7", "travel"),
    ("c8-1_에너지사용량 아는 경우", "c8_energy", "Category8", "energy"),
    ("c8-2_면적", "c8_area", "Category8", "energy"),
    ("c8-3_인원", "c8_person", "Category8", "energy"),
    ("c9-1_운송거리", "c9_dist", "Category9", "transport"),
    ("c9-2_운송금액", "c9_spend", "Category9", "transport"),
    ("c11_판매제품사용", "c11", "Category11", "sold_product_use"),
    ("c12_판매제품폐기", "c12", "Category12", "product_eol"),
    ("c13-1_에너지사용량 아는경우", "c13_energy", "Category13", "energy"),
    ("c13-2_면적", "c13_area", "Category13", "energy"),
    ("c13-3_인원", "c13_person", "Category13", "energy"),
    ("c14_프랜차이즈", "c14", "Category14", "franchise"),
    ("c15_투자", "c15", "Category15", "investment"),
]


def test_all_twenty_one_themes_after_the_colab_updates() -> None:
    got = [(name, p.key, p.category, p.theme) for name, p in SHEET_PROCESSOR_MAP.items()]
    assert got == EXPECTED
