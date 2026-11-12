"""운영 관리자 실행 기록의 영문번역 몫(service/selectors/run_extras.py — 밴드 TR4 ③, 감독 처분 Q7)을 잰다(순수).

AI 설정 판 읽기 꼴(그린워싱 run_extras 와 같은 규칙) · 검토 칸 없음(reviewable_q 늘 거짓·states 빈 것). 업무 층(실행
기록의 칸 값·검토 거르기 0)은 tests/flows/test_runs_translation_settings.py.
"""

import pytest
from django.db.models import Q

from esgapi.translation.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.translation.service.selectors.run_extras import RunSettingExtras

SOURCE = RunSettingExtras()


@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        ({"aiSetting": "v3", "aiSettingId": 12}, (12, "v3")),  # 저장 판
        ({"aiSetting": DEFAULT_TITLE, "aiSettingId": None}, (None, DEFAULT_TITLE)),  # 기본 판(binding_158 — id None)
        ({"aiSetting": DEFAULT_TITLE}, (None, DEFAULT_TITLE)),  # id 열쇠 없음
        ({"engine": "colab_158"}, None),  # TR4 앞의 실행 — 판 열쇠 없음
        ({"aiSetting": 3, "aiSettingId": 12}, None),  # 이름이 글자가 아님
        ({"aiSetting": "v3", "aiSettingId": "12"}, None),  # id 가 글자
        ({"aiSetting": "v3", "aiSettingId": True}, None),  # id 가 bool
    ],
    ids=["saved", "default", "no_id_key", "old_run", "name_not_text", "id_text", "id_bool"],
)
def test_the_ai_setting_is_read_from_the_versions(versions: dict[str, object], expected: object) -> None:
    assert SOURCE.ai_setting(versions) == expected


def test_there_is_no_review_column() -> None:
    assert SOURCE.reviewable_q() == Q(pk__in=[])
    assert SOURCE.states(1, [1, 2]) == {}
