"""engines/colab_156/inputs.split_themes 가 「환경」 테마만 남기는가(발주서 DV1a §3 S6, 코랩 셀 3 — R/50-59).

기대값은 손으로 적는다: 남는 테마 이름 목록. 남은 목록은 받은 목록 그 객체다(복사 0). 코랩 셀 3 과의 견줌은 esg-lab
`py/dvcolab`(MARC-ENT-310).
"""

from typing import Any

import pytest

from esgapi.dataverify.engines.colab_156.inputs import THEMES, split_themes
from esgapi.dataverify.tests.engines.colab_156.support import environment

SOCIAL: list[dict[str, Any]] = [{"테마": "사회", "values": {}}]


@pytest.mark.parametrize(
    ("data", "kept"),
    [
        ({"환경": environment()}, ["환경"]),
        ({"환경": environment(), "사회": SOCIAL}, ["환경"]),
        ({"사회": SOCIAL, "환경": []}, ["환경"]),  # 빈 목록도 남는다
        ({"사회": SOCIAL}, []),
        ({"지배구조": [], "사회": SOCIAL}, []),
        ({}, []),
        ({" 환경": environment()}, []),  # 이름이 글자째 같아야 한다
    ],
)
def test_split_themes_by_hand(data: dict[str, Any], kept: list[str]) -> None:
    got = split_themes(data)
    assert list(got) == kept
    for theme in kept:
        assert got[theme] is data[theme]  # 목록을 복사하지 않는다


def test_only_the_environment_theme_is_kept() -> None:
    assert THEMES == ("환경",)
    assert list(split_themes({"사회": SOCIAL, "환경": [], "지배구조": []})) == ["환경"]
    assert split_themes({"사회": SOCIAL}) == {}
