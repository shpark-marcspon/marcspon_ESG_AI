"""S8 도우미: `pdcompat` 의 도우미마다 pandas 2.x 꼴 기대값을 **글자로 박은** 경우 표(개정 2, `MARC-ENT-298`).

기대값은 스크래치 venv 의 pandas 2.3.3 탐침 값이다(2026-10-19 — 발주서 개정 2 절·critic 2 탐침과 같음). 도우미 경우는
pandas 3.0.6 기본 문맥과 엔진 문맥(`legacy_strings`) 둘에서 돈다(경계 ① 검증 N2). 같은 표에서 맨 `astype(str)`·맨
`fillna` 가 3.0.6 에서 **다름**도 단언한다 — 판 차이가 사라지면(판 올림 등) 이 시험이 알린다. 끝으로 엔진
폴더(`pdcompat.py` 밖)에 맨 `.astype(str)`·`.fillna(` 가 0 임을 AST 로 문다.
"""

import ast
import math
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import esgapi.inventory.engines.scope3.colab_157 as package
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_fillna, colab_loc_set, colab_str, legacy_strings

FOLDER = Path(package.__file__).parent
NAN = math.nan

# 두 문맥: pandas 3.0.6 기본(글 열 = `str`)과 엔진이 도는 문맥(`legacy_strings` — 글 열 = object). 도우미는 둘에서
# 같은 값·dtype 을 내야 한다. 맨 `astype(str)` 은 엔진 문맥에선 2.x 와 같은 값을 내므로, 도우미를 맨 꼴로 바꾼
# 파손(P15)은 기본 문맥 경우가 문다.
CONTEXTS: dict[str, Callable[[], AbstractContextManager[None]]] = {
    "default": nullcontext,
    "legacy_strings": legacy_strings,
}

# 입력은 모듈을 읽을 때(기본 문맥) 한 번 짓는다 — 문맥 안에서 지으면 `dtype="str"` 의 뜻이 바뀐다.
STR_CASES: list[tuple[str, "pd.Series[Any]", list[str]]] = [
    ("object None·NaN", pd.Series(["a", None, NAN], dtype=object), ["a", "None", "nan"]),
    ("read_excel(dtype=str) 의 빈 칸(object)", pd.Series(["가상", NAN], dtype=object), ["가상", "nan"]),
    ("read_excel(dtype=str) 의 빈 칸(3.0.6 str)", pd.Series(["가상", NAN], dtype="str"), ["가상", "nan"]),
    ("수·글 섞임", pd.Series([9, 9.5, "가상", NAN], dtype=object), ["9", "9.5", "가상", "nan"]),
    ("float 열", pd.Series([9.0, NAN]), ["9.0", "nan"]),
]
FILL_CASES: list[tuple[str, "pd.Series[Any]", int | float | str, list[object], str]] = [
    ("object [1.0, nan] → float64", pd.Series([1.0, NAN], dtype=object), 0, [1.0, 0.0], "float64"),
    ("글 칸 채움 → object", pd.Series(["가상", NAN], dtype=object), "", ["가상", ""], "object"),
    ("float64 그대로", pd.Series([9.5, NAN]), 0, [9.5, 0.0], "float64"),
]


@pytest.mark.parametrize("context", sorted(CONTEXTS))
def test_colab_str_matches_pandas_2_astype_str(context: str) -> None:
    assert len(STR_CASES) == 5
    with CONTEXTS[context]():
        for name, series, want in STR_CASES:
            got = colab_str(series)
            assert got.tolist() == want, name
            assert got.dtype == object, name


def test_bare_astype_str_differs_on_pandas_3() -> None:
    """3.0.6 기본 문맥의 맨 `astype(str)` 은 None·NaN 을 결측으로 둔다(2.3.3 은 'None'·'nan') — 도우미가 필요한 까닭."""
    bare = pd.Series(["a", None, NAN], dtype=object).astype(str).tolist()
    assert bare[0] == "a"
    assert all(isinstance(v, float) and math.isnan(v) for v in bare[1:])
    assert pd.Series(["가상", NAN], dtype="str").astype(str).tolist()[1] != "nan"


def test_bare_astype_str_inside_legacy_strings_is_pandas_2() -> None:
    """엔진 문맥 안의 맨 `astype(str)` 은 2.x 값을 낸다 — 그래서 S8·P15 는 기본 문맥 경우가 있어야 문다."""
    with legacy_strings():
        assert pd.Series(["a", None, NAN], dtype=object).astype(str).tolist() == ["a", "None", "nan"]


@pytest.mark.parametrize("context", sorted(CONTEXTS))
def test_colab_fillna_downcasts_like_pandas_2(context: str) -> None:
    assert len(FILL_CASES) == 3
    with CONTEXTS[context]():
        for name, series, value, want, dtype in FILL_CASES:
            got = colab_fillna(series, value)
            assert got.tolist() == want, name
            assert str(got.dtype) == dtype, name


@pytest.mark.parametrize("context", sorted(CONTEXTS))
def test_bare_fillna_keeps_object_on_pandas_3(context: str) -> None:
    with CONTEXTS[context]():
        assert str(pd.Series([1.0, NAN], dtype=object).fillna(0).dtype) == "object"


@pytest.mark.parametrize("context", sorted(CONTEXTS))
def test_colab_loc_set_upcasts_like_pandas_2(context: str) -> None:
    """코랩 월 합의 `df.loc[월별, "구매금액"] = 합`: int64 열에 float 을 넣으면 2.x 는 float64 로 올린다."""
    with CONTEXTS[context]():
        df = pd.DataFrame({"구매금액": [9100000, 9200]})
        mask = pd.Series([False, True])
        colab_loc_set(df, mask, "구매금액", pd.Series([NAN, 9009.5]))
        assert df["구매금액"].tolist() == [9100000.0, 9009.5]
        assert str(df["구매금액"].dtype) == "float64"
        same = pd.DataFrame({"구매금액": [9.5, NAN]})
        colab_loc_set(same, pd.Series([False, True]), "구매금액", pd.Series([NAN, 9.25]))
        assert same["구매금액"].tolist()[1] == 9.25  # 받을 수 있으면 그대로 넣는다


@pytest.mark.parametrize("context", sorted(CONTEXTS))
def test_bare_loc_set_raises_on_pandas_3(context: str) -> None:
    """3.0.6 의 맨 `df.loc[...] = float` 은 int64 열에서 TypeError(2.3.3 은 FutureWarning 과 함께 올림).

    도우미 `colab_loc_set` 의 까닭이다.
    """
    with CONTEXTS[context]():
        df = pd.DataFrame({"구매금액": [9100000, 9200]})
        with pytest.raises(TypeError, match="int64"):
            df.loc[pd.Series([False, True]), "구매금액"] = pd.Series([NAN, 9009.5])


def test_legacy_strings_builds_object_text_columns() -> None:
    assert str(pd.Series(["a", None]).dtype) == "str"
    with legacy_strings():
        assert pd.Series(["a", None]).dtype == object
        assert pd.DataFrame({"name": ["가상"]})["name"].dtype == object
    assert str(pd.Series(["a", None]).dtype) == "str"  # 문맥 밖으로 새지 않는다


def bare_uses(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "fillna":
                found.append("fillna")
            if node.func.attr == "astype" and any(
                (isinstance(a, ast.Name) and a.id == "str") or (isinstance(a, ast.Constant) and a.value == "str")
                for a in node.args
            ):
                found.append("astype(str)")
    return found


def test_engine_has_no_bare_astype_str_or_fillna() -> None:
    files = [path for path in sorted(FOLDER.glob("*.py")) if path.name != "pdcompat.py"]
    assert len(files) >= 7
    for path in files:
        assert bare_uses(ast.parse(path.read_text(encoding="utf-8"))) == [], path.name
    # 양성 대조: 규칙이 심은 줄을 잡는다
    assert bare_uses(ast.parse("s.astype(str)\ns.fillna(0)\n")) == ["astype(str)", "fillna"]
    assert bare_uses(ast.parse('s.astype("str")\n')) == ["astype(str)"]  # 경계 ② 검증 N6
