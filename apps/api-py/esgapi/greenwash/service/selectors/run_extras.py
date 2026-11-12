"""읽기. 운영 관리자 실행 기록(AD-04)의 그린워싱 몫 — 검토 상태와 AI 설정 판(AD4S). 쓰지 않는다.

runs 의 등록부(esgapi.runs.extras 의 EXTRAS)에 apps.py 의 ready() 가 RunReviewSource 를 「greenwash」 로 단다. runs 는
그린워싱을 모른다 — 검토를 보이는 실행의 술어와 검토 표는 여기 하나다.

    review_shown(status, result)        점검 결과 화면(actions/checks.py)이 검토를 보이는가 — 파이썬 술어
    reviewable_q()                      같은 뜻의 실행 행 Q(운영 관리자 목록의 거르기·값 채우기)
    RunReviewSource.states(c, ids)      실행 id → 검토 상태(reviews_of — 쿼리 하나)
    RunReviewSource.run_ids_in(c, s)    검토 상태가 s 안인 실행 id 의 부분 쿼리
    RunReviewSource.ai_setting(v)       versions 의 (aiSettingId, aiSetting) — 순수

★ 두 술어는 같은 뜻이다(tests/service/selectors/test_run_extras.py 가 다섯 꼴로 견준다): done 이고, 결과 꼴
  greenwash.result@1 의 결과가 있고, 그 결과의 dryRun 이 null 이거나 없다. 결과는 dryRun 키가 늘 있고 점검 실행은 JSON
  null 이다(contracts/shapes.py) — Django 의 `__isnull=True` 는 키 없음만 맞히니 `=None`(JSON null)과 OR 한다.
  무효 조건: reviewable_q 는 결과 본문이 dict 인지 못 본다(_result_of 는 dict 가 아니면 결과 없음으로 본다). 본문은 꼴
  검사를 지나 저장되니 dict 아닌 결과는 없다고 본다.
  무효 조건 둘: _result_of 는 그 꼴 결과의 첫 행만, reviewable_q 는 그 꼴 결과 아무 행이나 본다 — 한 실행에 같은 꼴
  결과가 둘 이상이면 어긋날 수 있다(지금 흐름은 결과 하나).
★ 결과 꼴 이름은 contracts/shapes.py 를 import 하지 않고 글자로 둔다(이 파일은 apps.py 의 ready() 길에서 들어온다 —
  pydantic 꼴 짓기를 시작에 싣지 않는다, flows/registration.py 머리. flows/rewrite_r1.py 와 같은 꼴).
  시험이 SHAPE 와 견준다.
★ 조회마다 회사 조건을 적는다(GreenwashReviewRow.for_company — core/tests/test_selector_scope.py).
"""

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Q

if TYPE_CHECKING:
    from django.db.models.query import ValuesQuerySet  # 타입 검사기에만 있는 꼴(django-stubs)

from esgapi.greenwash.models import GreenwashReviewRow
from esgapi.greenwash.service.selectors.review import reviews_of

RESULT_SHAPE: Final = "greenwash.result@1"  # contracts/shapes.py 의 SHAPE(머리말 — 시험이 견준다)


def review_shown(status: str, result: Mapping[str, object] | None) -> bool:
    """결과 화면이 검토를 보이는가. result = 그 실행의 greenwash.result@1 본문(없으면 None)."""
    return status == "done" and result is not None and result.get("dryRun") is None


def reviewable_q() -> Q:
    """review_shown 과 같은 뜻의 실행 행(run_runs) 조건. 한 filter() 에 넣는다(결과 행 하나가 둘 다 맞아야 한다)."""
    return Q(status="done", results__schema_version=RESULT_SHAPE) & (
        Q(results__body__dryRun=None) | Q(results__body__dryRun__isnull=True)
    )


class RunReviewSource:
    """runs.extras.RunExtrasSource 의 그린워싱 몫."""

    def reviewable_q(self) -> Q:
        return reviewable_q()

    def states(self, company_id: int, run_ids: Collection[int]) -> dict[int, str]:
        return {run_id: review.state for run_id, review in reviews_of(company_id=company_id, run_ids=run_ids).items()}

    def run_ids_in(self, company_id: int, states: Collection[str]) -> "ValuesQuerySet[Any, Any]":
        return GreenwashReviewRow.for_company(company_id).filter(state__in=list(states)).values("run_id")

    def ai_setting(self, versions: Mapping[str, object]) -> tuple[int | None, str] | None:
        """versions 의 aiSetting(판 이름)·aiSettingId(판 id — 기본 판은 None, flows/binding_e0.py).

        이름이 글자가 아니면 None. id 가 없거나 None 이면 (None, 이름), bool 아닌 int 면 (id, 이름), 그 밖이면 None.
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
