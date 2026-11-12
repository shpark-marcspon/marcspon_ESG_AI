"""데이터 검증 코랩 셀 7 의 Responses 고리(읽기판 R/631-791)에서 도구 실행에 붙는 규칙 — 고리 자체는 없다(밴드 DV1b).

고리는 core.llm 의 `LlmClient.call_tools` 이고(흐름 flows/colab_156.py 가 부른다), 여기는 코랩에서 가져오는 규칙만
담는다:
- 인자: 받은 글을 `json.loads` 로 읽고, 어떤 예외든 빈 객체 `{}` 로 둔다(R/555). 읽힌 값이 객체가 아니어도(목록·수·null)
  그대로 분배기에 넘긴다 — 분배기의 오류 글이 그 갈래를 말한다. 주입한 판별이 참이면 다시 던짐(코랩과 다른 자리).
- 도구 결과: 분배기(dispatch._run_local_tool)의 dict 를 `json.dumps(…, ensure_ascii=False)` 의 기본 구분자(", "·": ")로
  글자로 바꿔 모델에 돌려준다(R/743).
- 걸음: 계산 검토의 SET_MAX_STEPS = len(HINTS)*3(셀 14 R/1050). HINTS 는 계산 Plan 의 답을 `ast.literal_eval` 로 읽은 것
  (셀 14 R/1043).
- 리포트 글: strip(R/541).

코랩과 다른 자리(보고 「다른 자리」 표):
- 도구 결과 글자에 상한(`max_output_chars`)을 둔다. 넘으면 결과 대신 {"error": "tool output too large: …"} 를 돌려준다
  (코랩은 상한 없음 — 감독 처분 ③).
- 이름이 web_search 인 함수 호출도 분배기로 가 「unknown tool」 글을 돌려준다. 코랩은 건너뛰고 결과를 싣지 않는다
  (R/731). 우리 함수 도구 목록에 그 이름이 없어 실제로는 닿지 않는 갈래다(결과를 빼면 다음 걸음이 call_id 의 짝을
  잃는다).
- HINTS 가 목록·튜플이 아니거나 원소가 글자가 아니면 읽기 실패(None)로 접는다(코랩은 셀 14 가 예외로 멈추거나 dict 의
  열쇠를 잇는다 — 감독 처분 ⑨).
- 걸음 수에 천장(`cap`)을 둔다. 천장은 흐름이 정한다(엔진은 코랩에 없는 상수를 갖지 않는다 — 감독 처분 ②).
- 빈 리포트 글은 빈 글 그대로다(코랩은 응답 JSON 통째를 리포트로 쓴다 — 우리는 공급사 응답을 결과에 싣지 않는다).
- 인자 읽기·분배기·HINTS 읽기에서 주입한 판별(`reraise`)이 참인 예외는 값으로 바꾸지 않고 다시 던진다(Celery soft
  limit — 흐름이 core 의 soft_deadline_in 으로 짓는다, MARC-ISSUE-414). 기본값 `never` 는 코랩 그대로.

순수하다: core·계약·흐름을 모른다(tests/engines/colab_156/test_purity.py).
"""

import ast
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from esgapi.dataverify.engines.colab_156.dispatch import _run_local_tool, never
from esgapi.dataverify.engines.colab_156.prompts import review_max_steps
from esgapi.dataverify.engines.colab_156.tools import ValueCache


@dataclass(frozen=True, slots=True)
class ToolRecord:
    """도구 실행 한 번. seq 는 이 실행기 안의 차례(1부터), args 는 읽은 인자, output 은 모델에 돌려준 dict 다
    (상한을 넘었으면 그 error dict)."""

    seq: int
    name: str
    args: Any
    output: dict[str, Any]


class ToolRunner:
    """도구 실행기 — core 의 `ToolExecutor` 꼴 `(이름, 인자 글) -> 결과 글`. 단계마다 하나를 짓는다
    (캐시 `ValueCache` 하나).

    records          실행한 차례대로의 기록(검사 기록 `wire.to_check` 의 재료)
    unparsable_args  인자 글을 JSON 으로 읽지 못해 `{}` 로 둔 수
    too_large        결과 글자가 상한을 넘어 error 글로 바꾼 수

    reraise 는 인자 읽기·분배기에서 다시 던질 예외의 판별(기본 `never` — 코랩 그대로).
    """

    def __init__(
        self,
        *,
        data: Mapping[str, Any],
        tolerance: Any,
        max_output_chars: int,
        reraise: Callable[[BaseException], bool] = never,
    ) -> None:
        self._data = data
        self._tolerance = tolerance
        self._max_output_chars = max_output_chars
        self._reraise = reraise
        self._cache = ValueCache()
        self.records: list[ToolRecord] = []
        self.unparsable_args = 0
        self.too_large = 0

    def __call__(self, name: str, arguments: str) -> str:
        args: Any = {}
        parsed = False
        try:  # 어떤 예외든 빈 객체(R/555) — 판별이 참인 것만 다시 던진다
            args = json.loads(arguments)
            parsed = True
        except Exception as error:
            if self._reraise(error):
                raise
        if not parsed:
            self.unparsable_args += 1
        output = _run_local_tool(
            name, args, data=self._data, tolerance=self._tolerance, cache=self._cache, reraise=self._reraise
        )
        text = json.dumps(output, ensure_ascii=False)
        if len(text) > self._max_output_chars:
            output = {"error": f"tool output too large: {len(text)} chars > {self._max_output_chars}"}
            text = json.dumps(output, ensure_ascii=False)
            self.too_large += 1
        self.records.append(ToolRecord(seq=len(self.records) + 1, name=name, args=args, output=output))
        return text


def parse_hints(text: str, *, reraise: Callable[[BaseException], bool] = never) -> list[str] | None:
    """계산 Plan 의 답 → HINTS(산식 목록). `ast.literal_eval` 이 목록·튜플을 내고 원소가 모두 글자일 때만 그 목록,
    아니면 None(읽기 실패 — 예외·dict·수·글자 아닌 원소). 판별 `reraise` 가 참인 예외는 다시 던진다."""
    value: Any = None
    read = False
    try:
        value = ast.literal_eval(text)
        read = True
    except Exception as error:
        if reraise(error):
            raise
    if not read:
        return None
    if not isinstance(value, list | tuple):
        return None
    elements = cast("list[object] | tuple[object, ...]", value)
    hints = [element for element in elements if isinstance(element, str)]
    return hints if len(hints) == len(elements) else None


@dataclass(frozen=True, slots=True)
class ReviewSteps:
    """계산 검토의 고리 걸음. loop_steps 는 고리에 거는 값(1 이상), capped 는 len(HINTS)*3 이 천장을 넘었는지."""

    loop_steps: int
    capped: bool


def review_steps(hints: Sequence[str], cap: int) -> ReviewSteps:
    """고리 걸음 = max(1, min(len(HINTS)*3, cap)). 코랩은 0 이어도 첫 호출을 한다(걸음 하나). 프롬프트의 걸음 글은
    review_prompt 가 천장 없이 len*3 으로 짓는다."""
    wanted = review_max_steps(hints)
    return ReviewSteps(loop_steps=max(1, min(wanted, cap)), capped=wanted > cap)


def report_text(text: str) -> str:
    """리포트 글 = 받은 글의 strip(R/541). 비면 빈 글 그대로."""
    return text.strip()
