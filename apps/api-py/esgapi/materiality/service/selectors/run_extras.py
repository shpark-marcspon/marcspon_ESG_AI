"""읽기. 운영 관리자 실행 기록(AD-04)의 중대성평가 IRO 몫 — AI 설정 판(밴드 IR4 ③, 데이터 검증 run_extras 의
판별 복사). 쓰지 않는다.

runs 의 등록부(esgapi.runs.extras 의 EXTRAS)에 apps.py 의 ready() 가 RunExtrasSource 를 「materiality」 로 단다.
runs 는 중대성평가를 모른다.

    RunSettingExtras.reviewable_q()          늘 거짓 — 중대성평가 IRO 에는 검토 화면이 없다(검토 칸은 늘 null)
    RunSettingExtras.states(c, ids)          빈 것(위와 같은 까닭 — 쿼리 0)
    RunSettingExtras.run_ids_in(c, s)        빈 부분 쿼리
    RunSettingExtras.ai_setting(v)           versions 의 (aiSettingId, aiSetting) — 순수(그린워싱 run_extras 의 규칙)

★ 조회마다 회사 조건을 적는다(MaterialityAiSettingRow.for_company — core/tests/test_selector_scope.py). run_ids_in 은
  행을 읽지 않는 빈 부분 쿼리지만 같은 규칙으로 짓는다.
"""

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Any

from django.db.models import Q

if TYPE_CHECKING:
    from django.db.models.query import ValuesQuerySet  # 타입 검사기에만 있는 꼴(django-stubs)

from esgapi.materiality.models import MaterialityAiSettingRow


class RunSettingExtras:
    """runs.extras.RunExtrasSource 의 중대성평가 IRO 몫."""

    def reviewable_q(self) -> Q:
        return Q(pk__in=[])

    def states(self, company_id: int, run_ids: Collection[int]) -> dict[int, str]:
        return {}

    def run_ids_in(self, company_id: int, states: Collection[str]) -> "ValuesQuerySet[Any, Any]":
        return MaterialityAiSettingRow.for_company(company_id).none().values("id")

    def ai_setting(self, versions: Mapping[str, object]) -> tuple[int | None, str] | None:
        """versions 의 aiSetting(판 이름)·aiSettingId(판 id — 기본 판은 None, flows/binding_155.py).

        이름이 글자가 아니면 None(IR4 앞 실행 — 열쇠 없음). id 가 없거나 None 이면 (None, 이름), bool 아닌 int 면
        (id, 이름), 그 밖이면 None.
        """
        name = versions.get("aiSetting")
        if not isinstance(name, str):
            return None
        setting_id = versions.get("aiSettingId")
        if setting_id is None:
            return (None, name)
        if isinstance(setting_id, int) and not isinstance(setting_id, bool):
            return (setting_id, name)
        return None
