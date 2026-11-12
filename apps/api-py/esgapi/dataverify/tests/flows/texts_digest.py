"""기본 글·기본 temperature 의 공급사 요청·결과·엑셀·어림이 BASE 와 바이트 같은지 재는 지문(DVA1 §4-6). 실호출 0 —
모의 공급사뿐.

지어낸 입력 넷(대상 테마 있음 · 없음 · 계산 Plan 이 산식 0개 · web_search 끔)을 모의 공급사 대본으로 `run_flow` 에
돌리고 경우마다 적는다: 호출마다 공급사 요청 몸 `ProviderRequest.to_json()`(모델·system·user·tools·
max_output_tokens·temperature·되실은 도구 결과), 결과 dict 들(JSON), 엑셀은 `load_workbook` 으로 다시 읽은 시트별 칸
값의 JSON(바이트가 아님 — outputs/xlsx.py 의 만든 시각이 바이트에 든다), `estimate` 의 결과(산식 수 모름·넷).

이 파일은 BASE 에도 있는 것(support·colab_156·prompts)만 import 한다. 입력은 `dataclasses.fields` 로 있는 칸만
채운다 — 새 칸(texts·temperature)은 `getattr` 로 읽고 BASE 에 없는 칸은 건너뛴다. `scripts/section4-DVA1.sh` 가
이 파일을 BASE 트리(`git archive`)에 넣어 그쪽 흐름으로도 돌리고 두 지문을 견준다.

    uv run --frozen python -m esgapi.dataverify.tests.flows.texts_digest
"""

import dataclasses
import hashlib
import io
import json
from typing import Any

from openpyxl import load_workbook

from esgapi.core.flows.run import run_flow
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import UrlCitation
from esgapi.dataverify.engines.colab_156 import prompts
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.tests.flows import support

S1_2022 = '{"대분류": "온실가스 배출량", "중분류": "직접 배출량", "소분류": "Scope 1", "단위": "tCO2eq", "year": 2022}'
SUM_ARGS = (
    '{"total": ["온실가스 배출량", "총 배출량", "Scope 1+2", "tCO2eq"], '
    '"a": ["온실가스 배출량", "직접 배출량", "Scope 1", "tCO2eq"], '
    '"b": ["온실가스 배출량", "간접 배출량", "Scope 2", "tCO2eq"], "years": ["2022", "2023"]}'
)
INSIGHT = """## 가상 인사이트

| 영역 | 지표 | 관찰 | 리스크 | 해석 |
|---|---|---|---|---|
| 환경 | 가상 지표 A | 가상 관찰 A | 가상 리스크 A | 가상 해석 A |
"""
CITATIONS = (UrlCitation(url="https://example.com/synthetic-a", title="가상 출처 A", start_index=0, end_index=1),)
CASES = ("with_theme", "no_theme", "zero_formulas", "web_search_off")


def given(case: str) -> Any:
    """경우의 입력 — 있는 칸만 채운다(BASE 에는 texts·temperature 가 없다)."""
    values: dict[str, Any] = {
        "received": support.received(environment=case != "no_theme"),
        "tags": support.TAGS,
        "max_cost_usd": colab_156.StageCosts(plan=1.0, review=1.0, insight=1.0),
        "web_search": case != "web_search_off",
        "texts": getattr(prompts, "DEFAULT_TEXTS", None),
        "temperature": getattr(colab_156, "TEMPERATURE", None),
    }
    names = {field.name for field in dataclasses.fields(colab_156.DataverifyInputs)}
    return colab_156.DataverifyInputs(**{name: value for name, value in values.items() if name in names})


def scripted(case: str) -> MockProvider:
    mock = MockProvider("openai")
    if case == "no_theme":
        return mock
    if case == "zero_formulas":
        mock.enqueue_text("[]")
        mock.enqueue_text("가상 검토(산식 없음)")
    else:
        mock.enqueue_tool_calls([("value_of_by_name", S1_2022)])
        mock.enqueue_text("['가상 산식 1', '가상 산식 2']")
        mock.enqueue_tool_calls([("sum_check_by_name", SUM_ARGS), ("search_items", '{"소분류_contains": "Scope"}')])
        mock.enqueue_text("  가상 검토 리포트\n")
    if case == "web_search_off":
        mock.enqueue_text(INSIGHT)
    else:
        mock.enqueue_text(INSIGHT, citations=CITATIONS, hosted_calls=1)
    return mock


def sheets(content: bytes) -> list[Any]:
    book = load_workbook(io.BytesIO(content))
    return [[name, [list(row) for row in book[name].iter_rows(values_only=True)]] for name in book.sheetnames]


def text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=repr)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fingerprint(case: str) -> dict[str, str]:
    mock = scripted(case)
    done = run_flow(colab_156.FLOW, given(case), colab_156.DataverifyAdapters(llm=support.spy(mock)))
    assert mock.pending == 0, (case, mock.pending)
    estimate_mock = MockProvider("openai")
    estimates = [
        colab_156.estimate(given(case), support.spy(estimate_mock)),
        colab_156.estimate(given(case), support.spy(estimate_mock), hints_count=4),
    ]
    assert estimate_mock.calls == []
    return {
        "requests": sha(text([request.to_json() for request in mock.calls])),
        "calls": str(len(mock.calls)),
        "results": sha(text([dict(found) for found in done.output.results])),
        "xlsx": sha(text([[file.name, file.media_type, sheets(file.content)] for file in done.output.files])),
        "estimate": sha(text(estimates)),
    }


def main() -> None:
    for case in CASES:
        for key, value in fingerprint(case).items():
            print(f"{case} {key} {value}")


if __name__ == "__main__":
    main()
