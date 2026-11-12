"""실패 쪽만 다시의 앞 실행 읽기(끼움 flows/binding_158 의 RetrySourceStore 구현 — 밴드 TR2).

runs 의 selectors(find_run·run_results)로만 읽는다 — 둘 다 회사 조건이 붙어 남의 회사 실행은 없는 실행이다. 남의
도메인(runs)을 엮으므로 Selector 가 아니라 Action 이다(core/tests/test_selector_scope.py — 표를 직접 열지 않는
Selector 는 없다. greenwash service/actions/report.py 꼴). 갈래:
    RetryFound     module translation · status done · 결과 translation.result@1 이 있고 그 status 가 done
                   → base = 문체 → variants[].translatedText(자동수정 전), sourceSha256 = document.sourceSha256,
                     labels = settings.variants, ai_key = 그 실행 versions 의 판 열쇠(colab.ai_key — 옛 실행은 None.
                     흐름이 이번 실행의 것과 견준다, MARC-ISSUE-326)
    RetryNotDone   그 회사·영문번역 실행이지만 끝나지 않음(queued·processing·failed)
    RetryNotFound  그 밖(없음·남의 회사·다른 모듈·결과 없음·결과가 거절·sourceSha256 없는 옛 꼴) — 거름(flow_id·adapter,
                   PDF 끼움만 — 밴드 TRS3 G7)을 주면 앞 실행의 흐름 id 가 다르거나 versions.adapter 가 다른 판이어도
                   (어댑터 판이 바뀌면 태그·쪽 지도가 달라질 수 있다). 거름 없는 워드 끼움은 그대로다
권한 없는 입구다 — 부르는 쪽(실행기의 끼움)이 실행의 회사를 넘긴다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.translation.contracts.shapes import RESULT_SHAPE
from esgapi.translation.flows.colab_158 import RetryFound, RetryNotDone, RetryNotFound, RetrySource, ai_key

MODULE: Final = "translation"


@dataclass(frozen=True, slots=True, kw_only=True)
class RunRetrySource:
    """RetrySourceStore 의 구현(apps.py 가 꽂는다). flow_id·adapter 를 주면 그 흐름·그 어댑터 판의 앞 실행만 찾는다."""

    flow_id: str | None = None
    adapter: str | None = None

    def base(self, company_id: int, run_id: int) -> RetrySource:
        run = run_selectors.find_run(company_id=company_id, run_id=run_id)
        if run is None or run.module != MODULE:
            return RetryNotFound()
        if self.flow_id is not None and run.flow_id != self.flow_id:
            return RetryNotFound()
        if self.adapter is not None and run.versions.get("adapter") != self.adapter:
            return RetryNotFound()
        if run.status != "done":
            return RetryNotDone(run.status)
        results = run_selectors.run_results(company_id=company_id, run_id=run_id)
        body = next((r.body for r in results if r.schema_version == RESULT_SHAPE), None)
        if not isinstance(body, Mapping):
            return RetryNotFound()
        result = cast("Mapping[str, Any]", body)
        sha = result.get("document", {}).get("sourceSha256")
        if result.get("status") != "done" or not isinstance(sha, str):
            return RetryNotFound()
        variants = cast("list[Mapping[str, Any]]", result["variants"])
        return RetryFound(
            base={str(v["label"]): str(v["translatedText"]) for v in variants},
            source_sha256=sha,
            labels=tuple(str(label) for label in result["settings"]["variants"]),
            ai_key=ai_key(run.versions),
        )
