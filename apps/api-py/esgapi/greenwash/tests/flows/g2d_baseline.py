"""밴드 G2d ②-0 바닥 기준물 — 판의 실행을 끼움 versions_with → inputs_with → run_flow 로 끝까지 돌려 {결과 JSON 전체,
versions, 메시지 해시, 엑셀 셀 덤프} 를 짓는다(순수 층 — DB·실제 공급사·키 0). 바닥 코드로 뽑아 커밋한 것
(tests/data/g2d-baseline/<갈래>.json)과, 판 단어(G2d ③)가 들어온 뒤 같은 함수로 다시 지은 것이 같아야 한다(사용자 조건 —
기본 판·단어 칸 없는 판의 결과는 그대로).

갈래 다섯(처분 G2d-order-review-2.md B1·ⓔ). 판 고정값은 tests/data/g2d-baseline/fixtures.json:
    a-default            기본 판(적용 판 없음)
    b-saved-code-text    저장 판·저장 프롬프트 글 없음(binding_e0.versions_with 의 일찍 돌아가기)
    c-saved-text         저장 판·저장 프롬프트 글 있음
    d-old-run-no-model-key  b 의 판, versions 에서 dropKeys 를 뺀 옛 실행(inputs_with 의 모델 열쇠 없는 갈래)
    e-default-dry-run    기본 판, dry_run(결과만 — 공급사 0·엑셀 없음)

공급사는 모의(MockProvider)다 — 판의 묶음(저장 글·고친 기준표·코드 글)으로 대본을 고르는 ScriptedChat 을 다리
(LlmChatBridge) 뒤에 둔다(test_criteria_flow·test_binding_e0_prompts 의 꼴). 글은 전부 지어낸 것이다.
"""

import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, cast

from openpyxl import load_workbook

from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.flows.binding import DocumentInput
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, PromptPack, default_prompts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding, SavedSetting
from esgapi.greenwash.flows.criteria_e0 import eval_pack
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows import test_criteria_flow as flow_cases
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore, FakeStore

DATA: Final = Path(__file__).resolve().parents[1] / "data" / "g2d-baseline"
BRANCHES: Final = (
    "a-default",
    "b-saved-code-text",
    "c-saved-text",
    "d-old-run-no-model-key",
    "e-default-dry-run",
)
PROVIDER_QUEUE: Final = 40
"""모의 공급사 큐(표본 네 쪽의 실행은 요청 12)."""
DOCUMENT: Final = DocumentInput(content=s.SAMPLE_BYTES, media_type="application/pdf", file_name=s.SAMPLE_NAME)


def fixtures() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((DATA / "fixtures.json").read_text(encoding="utf-8")))


def saved_setting(*, prompts: bool) -> SavedSetting:
    fx = fixtures()
    setting = cast("dict[str, Any]", fx["setting"])
    return SavedSetting(
        id=cast("int", setting["id"]),
        name=cast("str", setting["name"]),
        criteria=cast("GreenwashCriteria", setting["criteria"]),
        model_settings=cast("AiModelSettingsIn", setting["modelSettings"]),
        prompts=cast("AiPromptsIn", fx["savedPrompts"]) if prompts else None,
        terms=None,
    )


def binding_of(branch: str) -> GreenwashBinding:
    if branch in ("a-default", "e-default-dry-run"):
        return GreenwashBinding(models=s.REAL_MODELS, store=DefaultOnlyStore())
    company = cast("int", fixtures()["companyId"])
    saved = saved_setting(prompts=branch == "c-saved-text")
    return GreenwashBinding(
        models=s.REAL_MODELS, store=FakeStore(saved={company: [saved]}, applied_id={company: saved.id})
    )


def pack_of(inputs: colab.GreenwashInputs) -> PromptPack:
    """실행이 쓰는 묶음 — 저장 글 > 고친 기준표의 EVAL > 코드 글(대본이 프롬프트 종류를 가릴 때 쓴다)."""
    if inputs.prompts is not None:
        return inputs.prompts
    if inputs.criteria is not None:
        return eval_pack(inputs.criteria, PROMPT_VERSION)
    return default_prompts(PROMPT_VERSION)


def cells(content: bytes) -> dict[str, list[list[Any]]]:
    """엑셀 셀 값 전체(tests/outputs/test_xlsx_report.read 꼴 — zip 바이트는 만들 때마다 달라 셀로 견준다)."""
    book = load_workbook(io.BytesIO(content), read_only=True)
    return {name: [list(row) for row in book[name].iter_rows(values_only=True)] for name in book.sheetnames}


def build(branch: str) -> dict[str, Any]:
    """갈래 하나의 기준물 dict(파일에 쓰는 꼴 그대로)."""
    fx = fixtures()
    company = cast("int", fx["companyId"])
    options = cast("dict[str, object]", fx["options"])
    binding = binding_of(branch)
    versions = binding.versions_with(options, company_id=company)
    if branch == "d-old-run-no-model-key":
        versions = {k: v for k, v in versions.items() if k not in cast("list[str]", fx["dropKeys"])}
    inputs = binding.inputs_with(DOCUMENT, options, company_id=company, versions=versions)
    if branch == "e-default-dry-run":
        forbidden = s.Forbidden()
        run = s.run(
            replace(inputs, dry_run=True),
            s.adapters(llm=forbidden, embedding=forbidden, tokens=s.char_counter()),
        )
        assert forbidden.calls == 0
        return {"branch": branch, "versions": versions, "result": s.result_of(run), "messages": [], "workbook": None}
    mock = flow_cases.scripted_provider(PROVIDER_QUEUE, pack_of(inputs))
    run = s.run(inputs, s.adapters(llm=flow_cases.bridge(mock, MemorySink())))
    (book,) = run.output.files
    return {
        "branch": branch,
        "versions": versions,
        "result": s.result_of(run),
        "messages": flow_cases.provider_hashes(mock.calls),
        "workbook": cells(book.content),
    }


def dump(found: dict[str, Any]) -> bytes:
    """파일 바이트(정렬 없음 — 결과 칸 차례도 기준물이다)."""
    return (json.dumps(found, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def stored(branch: str) -> bytes:
    return (DATA / f"{branch}.json").read_bytes()
