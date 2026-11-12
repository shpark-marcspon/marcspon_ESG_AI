"""회귀 테스트: 정답 표 15개에 대한 일치율이 실측 하한을 지킨다.

하한은 정답 폴더의 `floors.json` (esg-lab 의 밴드가 2026-10-01 에 실측한 값). 원본 PDF 와 정답 표는 저장소 밖에 있다
(`PARSER_REPORTS_DIR`, `PARSER_GOLD_DIR`). 그래서 전부 `reports` 표시가 붙고, 파일은 테스트가 돌 때에만 읽는다.
매개변수의 이름(표 id, 양식)은 아래에 고정 목록으로 적었고 `test_fixed_ids_match_gold_dir` 가 정답 폴더의 것과 견준다.
- auto 전략: 양식별 하한 + 표별 하한
- text 전략(괘선을 쓰지 않음): 표별 하한. 삼성전자 표 5개는 세로선이 없는 표의 기준 사례다.
"""

import json

import pytest

from docparse.score import aggregate, load_gold, score_gold

from .conftest import require_gold, require_reports

pytestmark = pytest.mark.reports

# 정답 표 15개의 id (정답 폴더의 파일 이름 차례). 정답 폴더가 바뀌면 `test_fixed_ids_match_gold_dir` 가 빨개진다.
SAMSUNG_IDS = ["sam_p64_segment", "sam_p64_valuedist", "sam_p66_diversity", "sam_p70_energy", "sam_p70_ewaste"]
OTHER_IDS = [
    "cos_p142_ghg",
    "cos_p142_ghg_cont",
    "cos_p142_scope3",
    "cos_p149_headcount",
    "cos_p171_sites",
    "kb_p50_financed",
    "kb_p51_gics",
    "kbd_p20_energy",
    "kbd_p22_scope3",
    "kbd_p41_hiring",
]
GOLD_IDS = OTHER_IDS + SAMSUNG_IDS
FORMS = ["horizontal_rules", "no_vertical_rules", "ruled_cells"]

_CACHE = {}


@pytest.fixture
def floors():
    gold = require_gold()
    if "floors" not in _CACHE:
        _CACHE["floors"] = json.loads((gold / "floors.json").read_text(encoding="utf-8"))
    return _CACHE["floors"]


@pytest.fixture
def scores():
    """한 번만 잰다."""
    require_reports()
    gold = require_gold()
    if "scores" not in _CACHE:
        _CACHE["scores"] = {s: score_gold(gold, s) for s in ("auto", "text")}
    return _CACHE["scores"]


# 번역 판(밴드 TRD1)도 같은 하한을 지킨다. 판마다 한 번만 잰다(기본 판은 위의 `scores` 그대로).
LAYOUTS = (1, 2)


@pytest.fixture
def scores_by_layout(scores, request):
    layout = request.param
    if layout == 1:
        return scores
    gold = require_gold()
    key = f"scores@{layout}"
    if key not in _CACHE:
        _CACHE[key] = {s: score_gold(gold, s, layout=layout) for s in ("auto", "text")}
    return _CACHE[key]


def _check(result, floor, label, metrics):
    below = {m: (result[m], floor[m]) for m in metrics if result[m] < floor[m] - 1e-9}
    assert not below, f"{label}: 일치율이 하한 아래다 (실측, 하한) {below}"


def test_fixed_ids_match_gold_dir(floors):
    """이 파일에 적은 고정 목록이 정답 폴더의 것과 같다 (목록이 낡으면 매개변수가 표를 빠뜨린다)."""
    gold = load_gold(require_gold())
    assert [g["id"] for g in gold] == GOLD_IDS
    assert [g["id"] for g in gold if g["report"] == "samsung"] == SAMSUNG_IDS
    assert sorted(floors["auto"]["by_form"]) == FORMS


def test_gold_set_is_complete(floors):
    gold = load_gold(require_gold())
    ids = [g["id"] for g in gold]
    assert len(ids) == 15 and len([g for g in gold if g["report"] == "samsung"]) == 5
    assert set(floors["auto"]["by_table"]) == set(ids) == set(floors["text"]["by_table"])


@pytest.mark.parametrize("scores_by_layout", LAYOUTS, indirect=True, ids=lambda v: f"layout{v}")
@pytest.mark.parametrize("form", FORMS)
def test_auto_strategy_keeps_floor_per_form(scores_by_layout, floors, form):
    _check(
        aggregate(scores_by_layout["auto"], "form")[form],
        floors["auto"]["by_form"][form],
        f"auto/{form}",
        floors["metrics"],
    )


@pytest.mark.parametrize("scores_by_layout", LAYOUTS, indirect=True, ids=lambda v: f"layout{v}")
@pytest.mark.parametrize("table_id", GOLD_IDS)
def test_auto_strategy_keeps_floor_per_table(scores_by_layout, floors, table_id):
    r = next(x for x in scores_by_layout["auto"] if x["id"] == table_id)
    assert r["n_tables"] >= 1, f"{table_id}: 정답 영역에서 표를 찾지 못했다"
    _check(r, floors["auto"]["by_table"][table_id], f"auto/{table_id}", floors["metrics"])


@pytest.mark.parametrize("scores_by_layout", LAYOUTS, indirect=True, ids=lambda v: f"layout{v}")
@pytest.mark.parametrize("table_id", SAMSUNG_IDS)
def test_text_strategy_keeps_floor_on_samsung_tables(scores_by_layout, floors, table_id):
    """글자 정렬 기반 전략만으로 삼성전자 표를 읽는다. 이 전략을 무력화하면 빨개진다."""
    r = next(x for x in scores_by_layout["text"] if x["id"] == table_id)
    assert r["n_tables"] >= 1 and r["methods"] == ["text"], f"{table_id}: 글자 정렬 기반 표가 없다"
    _check(r, floors["text"]["by_table"][table_id], f"text/{table_id}", floors["metrics"])


@pytest.mark.parametrize("scores_by_layout", LAYOUTS, indirect=True, ids=lambda v: f"layout{v}")
@pytest.mark.parametrize("table_id", OTHER_IDS)
def test_text_strategy_keeps_floor_on_other_tables(scores_by_layout, floors, table_id):
    r = next(x for x in scores_by_layout["text"] if x["id"] == table_id)
    _check(r, floors["text"]["by_table"][table_id], f"text/{table_id}", floors["metrics"])


def test_extracted_numbers_exist_verbatim_in_text_layer():
    """추출된 숫자 셀은 그 쪽 텍스트 계층에 같은 문자열로 있어야 한다 (값을 고치거나 만들지 않는다)."""
    import re

    from docparse.compare import is_num, norm
    from docparse.config import report_path
    from docparse.engine import open_pdf
    from docparse.tables import extract_tables

    require_reports()
    checked = 0
    for g in load_gold(require_gold()):
        with open_pdf(report_path(g["report"])) as doc:
            page = doc[g["page"] - 1]
            words = {w[4].strip() for w in page.get_words()}
            for t in extract_tables(page, "auto"):
                for row in t.grid:
                    for cell in row:
                        if cell and is_num(norm(cell)) and " " not in cell:
                            # 낱말과 완전히 같거나, 낱말이 「값 + 각주 표시」인 경우만 허용한다
                            assert cell in words or any(
                                w.startswith(cell) and re.fullmatch(r"(\d{1,2}\))+|\*+", w[len(cell) :]) for w in words
                            ), (g["id"], cell)
                            checked += 1
    assert checked > 1000
