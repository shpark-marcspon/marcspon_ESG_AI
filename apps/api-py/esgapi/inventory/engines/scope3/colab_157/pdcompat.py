"""코랩(pandas 2.x)과 우리(pandas 3.0.6)가 다르게 도는 자리를 맞추는 도우미(개정 2, `MARC-ENT-298`).

코랩 설치 줄(`:36`)은 판을 고정하지 않아 Colab 이 미리 깐 2.x 로 돌았을 것이다(추정). 옮긴 코랩 코드의
`astype(str)`·`.fillna(` 는 **모두** 여기를 거친다 — 엔진 안의 맨 `.astype(str)`·`.fillna(` 는 0 이다
(`tests/engines/scope3/colab_157/test_pdcompat.py` 가 AST 로 문다. 이 파일만 뺀다).

판 차이(스크래치 venv py3.13·numpy 2.5.4 탐침, 2026-10-19 — 시험 S8 이 기대값을 글자로 박아 다시 잰다).
「2.3.3 → 3.0.6 / 도우미」 꼴:
- object `["a", None, nan]` 의 `astype(str)`: `['a', 'None', 'nan']` → `['a', nan, nan]`.
  `colab_str` = 값마다 `str(v)` 를 object 로 → 두 판 다 `['a', 'None', 'nan']`(dtype object).
- `read_excel(dtype=str)` 빈 칸의 `astype(str)`: `'nan'` → NaN(`StringDtype(na_value=nan)`).
  `colab_str` → 두 판 다 `'nan'`.
- object `[1.0, nan]` 의 `fillna(0)`: `float64`(FutureWarning 과 함께 내림) → `object`.
  `colab_fillna` = `legacy_strings()` 안에서 `fillna(v).infer_objects()` → 두 판 다 `float64`.
- 글 값으로 짓는 열(`pd.Series(["a", None])`, `pd.DataFrame({"name": …})`, `read_excel` 의 글 열): `object` →
  `str`(`StringDtype(na_value=nan)` — 수를 넣으면 TypeError).
  `legacy_strings()` = `future.infer_string=False` 문맥 → `object`.
- 기본 문맥에서 글 object 의 `infer_objects()`·`map(str)`: `object` → `str`.
  위 두 도우미는 문맥과 무관하게 `object` 를 낸다.
- `int64` 열에 `df.loc[mask, 열] = <float 값>`(코랩 월 합 `:5957`): `float64` 로 올림(FutureWarning 과 함께) →
  TypeError(「Invalid value … for dtype 'int64'」 — 경계 ③ 탐침, 3.0.6 에서 잼). `colab_loc_set` = 받지 못하면 object 로
  넣고 `infer_objects()` → 두 판 다 `float64`.
- `legacy_strings()` 안의 맨 `astype(str)`: 3.0.6 도 `['a', 'None', 'nan']`, `str` 열의 빈 칸도 `'nan'`(2.x 와 같음).
  그래도 도우미를 쓴다 — 값이 부르는 문맥에 기대지 않게. 그래서 S8 은 기본 문맥과 이 문맥 둘에서 돌고,
  맨 `astype(str)` 은 기본 문맥 경우가 문다(P15).

다른 2→3 차이(체인 대입·`replace` 내림 등)를 만나면 같은 꼴로 여기에 더하고 S8 에 경우를 더한다.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pandas as pd

type FillValue = int | float | str


def colab_str(series: "pd.Series[Any]") -> "pd.Series[str]":
    """코랩의 `series.astype(str)` 을 pandas 2.x 꼴로: `None` → `'None'`, NaN → `'nan'`."""
    # `astype(object).map(str)` 은 기본 문맥에서 `str` dtype 을 낸다(map 이 글을 추론).
    # 2.x 는 object 라 object 로 짓는다.
    return pd.Series([str(value) for value in series], index=series.index, name=series.name, dtype=object)


def colab_fillna(series: "pd.Series[Any]", value: FillValue) -> "pd.Series[Any]":
    """코랩의 `series.fillna(value)` 를 pandas 2.x 꼴로: 채운 뒤 object 를 더 좁은 dtype 으로 내린다."""
    # 기본 문맥의 `infer_objects` 는 글 object 를 `str` 로 내린다(2.x 는 object 그대로) — 2.x 글 추론 문맥에서 내린다.
    with legacy_strings():
        return series.fillna(value).infer_objects()


def colab_loc_set(df: pd.DataFrame, mask: "pd.Series[bool]", column: str, values: "pd.Series[Any]") -> None:
    """코랩의 `df.loc[mask, column] = values` 를 pandas 2.x 꼴로: 열의 dtype 이 값을 못 받으면 TypeError 대신 올린다."""
    try:
        df.loc[mask, column] = values
    except TypeError:
        widened = df[column].astype(object)
        widened.loc[mask] = values
        with legacy_strings():
            df[column] = widened.infer_objects()  # 2.x 의 올림: int64 + float → float64


@contextmanager
def legacy_strings() -> Generator[None]:
    """pandas 2.x 의 글 추론(글 열 = `object`)으로 도는 문맥. 엔진의 바깥 입구(`pipeline.run`)가 셈 전체를 감싼다.

    pandas 3.0.6 의 `future.infer_string` 옵션(전역)을 그 안에서만 끈다. 동기 호출 하나 안에서만 쓴다(스레드 사이에
    옵션이 샌다 — 엔진은 동기다). 끝나면 앞 값으로 돌린다.
    """
    with pd.option_context("future.infer_string", False):
        yield
