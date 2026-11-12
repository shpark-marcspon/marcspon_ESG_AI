"""데이터 검증 코랩 셀 3(읽기판 R/53-58)의 테마 거르기 — 「환경」 테마만 남긴다(처분 ⑥).

코랩대로 「환경」이 없으면 빈 dict 다(흐름이 경고 no_target_theme 으로 알린다 — DV1b). 받은 항목 목록은 복사하지 않고
그대로 넘긴다(코랩도 같은 목록을 가리킨다). 코랩과 다른 자리: 셀의 맨 몸을 함수로 감쌌고 print 를 지웠다.
"""

from collections.abc import Mapping
from typing import Any, Final

THEMES: Final = ("환경",)
"""검증하는 테마(코랩 셀 3 의 「환경」 하나). 결과 꼴의 scope.themes 가 이것을 남긴다."""


def split_themes(data: Mapping[str, Any]) -> dict[str, Any]:
    data_split: dict[str, Any] = {}

    if "환경" in data:
        data_split["환경"] = data["환경"]

    return data_split
