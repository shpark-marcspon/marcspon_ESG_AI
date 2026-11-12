"""core 의 모델 파일에 글자로 다시 적은 값(마이그레이션이 CHECK 로 굳힌 것)이 순수 상수와 같은가. 순수 층."""

from esgapi.core import models
from esgapi.core.calc import audit


def test_the_audit_values_in_the_model_match_the_pure_constants() -> None:
    assert models.AUDIT_EVENT_ACTIONS == audit.AUDIT_ACTIONS
    assert models.AUDIT_EVENT_RESULTS == audit.AUDIT_RESULTS
    assert models.AUDIT_ACTOR_KINDS == audit.ACTOR_KINDS
    assert models.AUDIT_DETAIL_MAX_OCTETS == audit.DETAIL_MAX_OCTETS
    assert len(models.AUDIT_EVENT_ACTIONS) == 9  # 분모(처분 ⑦ — AU1b 몫 다섯 포함)
