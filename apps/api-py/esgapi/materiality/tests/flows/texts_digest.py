"""기본 글·코드 모델 값의 공급사 요청·결과·엑셀 둘·어림이 BASE 와 바이트 같은지 재는 지문(IR4 §4-6). 실호출 0 —
모의 공급사뿐. dataverify `tests/flows/texts_digest.py` 의 꼴.

지어낸 입력 넷(산업 하나·셋(여러 줄 설명) · sector 둘 · latestEventMode 참·거짓 · 서브토픽 없는 토픽 하나)을 모의
공급사 대본으로 `iro_155.FLOW` 에 돌리고 경우마다 적는다: 호출마다 공급사 요청 몸 `ProviderRequest.to_json()`(모델·
system·user·tools·max_output_tokens·temperature), 결과 dict 들(JSON), 엑셀 둘은 `load_workbook` 으로 다시 읽은 시트별
칸 값의 JSON(바이트가 아님 — `book.save` 가 만든 시각을 싣는다), `estimate_iro` 의 결과.

이 파일은 BASE 에도 있는 것(support·colab_155·part2_155·iro_155)만 import 한다. 입력은 `dataclasses.fields` 로 있는
칸만 채운다 — 새 칸(texts·research·analysis)은 `getattr` 로 읽고 BASE 에 없는 칸은 건너뛴다. `scripts/section4-IR4.sh`
가 이 파일을 BASE 트리(`git archive`)에 넣어 그쪽 흐름으로도 돌리고 두 지문을 견준다.

실행 길(M4 — ③ 부터): 끼움이 지은 입력을 같은 대본으로 돌린 공급사 요청 지문을 셋 적는다. BASE 는 셋 다
`MaterialityBinding().inputs(options, company_id=1)`(인자 없는 생성 — 판 길이 없다), HEAD 는 포트 넣은 끼움의
`inputs_with(…, versions=…)` 로 기본 판 · NULL 글 저장 판(모델 = 명세 기본값) · 열쇠 없는 옛 versions. 어느 쪽인지는
`inspect.signature` 로 가른다(HEAD 전용 import 는 그 갈래 안에서만). 「오늘」은 binding_155.clock 을 고정해 읽는다.

    uv run --frozen python -m esgapi.materiality.tests.flows.texts_digest
"""

import dataclasses
import hashlib
import inspect
import io
import json
from datetime import UTC, datetime
from typing import Any

from openpyxl import load_workbook

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.materiality.flows import binding_155, colab_155, iro_155, part2_155
from esgapi.materiality.tests.flows import support

PATHS = ("default_setting", "null_text_setting", "old_versions")
CLOCK = datetime(2025, 6, 30, 3, 0, tzinfo=UTC)
CASES = ("one_non_financial_call", "three_financial_latest", "three_non_financial_autofill", "one_financial_autofill")


def received(case: str) -> dict[str, Any]:
    body = support.received2(latest="latest" in case)
    body["sector"] = "financial" if "_financial" in case and "non_financial" not in case else "non_financial"
    if case.startswith("three"):
        body["industries"] = [
            {"standard": "SASB", "industryName": f"가상 산업 {n}", "description": f"가상 설명 {n}\n  가상 둘째 줄"}
            for n in range(1, 4)
        ]
    else:
        body["industries"] = body["industries"][:1]
    if case.endswith("autofill"):  # 둘째 토픽은 서브토픽 없음 → 토픽 설명으로 지어 넣음(자리 셋 그대로)
        body["subtopicsByTopic"] = {"가상토픽 하나": body["subtopicsByTopic"]["가상토픽 하나"]}
    return body


def given(case: str) -> Any:
    """경우의 입력 — 있는 칸만 채운다(BASE 에는 texts·research·analysis 가 없다)."""
    values: dict[str, Any] = {
        "received": received(case),
        "tags": support.TAGS,
        "max_cost_usd": support.COST,
        "today": support.TODAY,
        "texts": getattr(colab_155, "DEFAULT_TEXTS", None),
        "research": getattr(colab_155, "CODE_RESEARCH", None),
        "analysis": getattr(part2_155, "CODE_ANALYSIS", None),
    }
    names = {field.name for field in dataclasses.fields(iro_155.IroInputs)}
    return iro_155.IroInputs(**{name: value for name, value in values.items() if name in names})


def sheets(content: bytes) -> list[Any]:
    book = load_workbook(io.BytesIO(content))
    return [[name, [list(row) for row in book[name].iter_rows(values_only=True)]] for name in book.sheetnames]


def text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=repr)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def run_requests(inputs: Any) -> tuple[MockProvider, Any]:
    """그 입력을 같은 대본으로 돌린다(③ 의 실행 길 지문도 이것을 부른다)."""
    mock = MockProvider("openai")
    support.script_iro(mock, inputs.received)
    done = support.run_iro(inputs, support.spy2(mock))
    assert mock.pending == 0, mock.pending
    return mock, done


def fingerprint(case: str) -> dict[str, str]:
    mock, done = run_requests(given(case))
    estimate_mock = MockProvider("openai")
    estimates = [
        iro_155.estimate_iro(given(case), support.spy2(estimate_mock)),
        iro_155.estimate_iro(given(case), support.spy2(estimate_mock), assumed_searches_per_call=3, assumed_fin_rows=4),
    ]
    assert estimate_mock.calls == []
    return {
        "requests": sha(text([request.to_json() for request in mock.calls])),
        "calls": str(len(mock.calls)),
        "results": sha(text([dict(found) for found in done.output.results])),
        "xlsx": sha(text([[file.name, file.media_type, sheets(file.content)] for file in done.output.files])),
        "estimate": sha(text(estimates)),
    }


def binding_inputs() -> list[tuple[str, Any]]:
    """실행 길 셋의 (이름, 끼움이 지은 입력) — 머리말."""
    binding_155.clock = lambda: CLOCK  # type: ignore[assignment]  # 지문만 — 두 트리가 같은 「오늘」을 읽게
    options = support.options(received("one_non_financial_call"))
    made = binding_155.MaterialityBinding
    if not inspect.signature(made).parameters:  # BASE — 판 길이 없다
        one = made().inputs(options, company_id=1)  # pyright: ignore[reportCallIssue]  # BASE 의 꼴
        return [(path, one) for path in PATHS]
    from esgapi.core.calc.ai_settings import defaults, to_input  # HEAD 에만 있다
    from esgapi.materiality.flows import prompt_model_155
    from esgapi.materiality.tests.flows.settings_store import FakeStore, FileModels

    models = FileModels()
    null_text = binding_155.SavedSetting(
        id=1, name="v1", model_settings=to_input(defaults(models.config(), prompt_model_155.MODELS)), prompts=None
    )
    found: list[tuple[str, Any]] = []
    for path in PATHS:
        store = FakeStore(saved={1: [null_text]}, applied_id={1: 1} if path == "null_text_setting" else {})
        b = made(settings=store, models=models)
        versions = b.versions(options) if path == "old_versions" else b.versions_with(options, company_id=1)
        found.append((path, b.inputs_with(options, company_id=1, versions=versions)))
    return found


def main() -> None:
    for case in CASES:
        for key, value in fingerprint(case).items():
            print(f"{case} {key} {value}")
    for path, inputs in binding_inputs():
        mock, done = run_requests(inputs)
        print(f"run_{path} requests {sha(text([request.to_json() for request in mock.calls]))}")
        print(f"run_{path} results {sha(text([dict(found) for found in done.output.results]))}")


if __name__ == "__main__":
    main()
