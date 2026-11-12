"""데이터 검증 엔진(engines/colab_156)이 사례 JSON 에 대해 내는 값을 JSON 으로 쓴다.

esg-lab `py/dvcolab` 이 이 JSON 을 코랩과 견준다. 사용(apps/api-py 에서):

    uv run --frozen python scripts/dataverify_compare_dump.py --cases <사례.json> --out <엔진.json>

wheel 밖 개발 도구다(밴드 DV1c 감독 결정 ②, MARC-ENT-310). esg-lab 은 esg-app 을 import 하지 않으므로 엔진 결과는
이 파일로만 건넨다. 입력 꼴 `dvcolab.cases/1` 의 정본은 esg-lab `py/dvcolab/cases.py` 머리이고, 이 명령은 그 꼴을
읽기만 한다:
- `data`(지은 입력 dict), `tolerance`
- `calls`: `[{"id", "fn", "args": [...] | {...}, "data"?: {...}}]` — `fn` 은 tools 의 `tool_…`, `_run_local_tool`
  (args = [이름, 인자]), `split_themes`(args = [입력 dict]). `data` 칸이 있으면 그 사례만 그 입력을 쓴다.
- `prompts`: `[{"id", "kind": "plan" | "review" | "insight", "vars": {...}}]` — plan·insight 는 기업 정보 넷,
  review 는 `hints`. `data_split` 은 `data` 를 `split_themes` 한 것.

- `loops`(선택 칸, 밴드 DV1b): `[{"id", "stage", "maxSteps", "script": [...]}]` — 사례마다 정본 설정(models.json)과
  openai 자리의 모의 공급사(`MockProvider("openai")`, 경로 standard-openai-41)에 `script` 를 심고 흐름의 고리 함수
  `flows.colab_156.run_loop` 을 돈다(단계 함수가 쓰는 그 함수). 걸음은 max(1, maxSteps)(코랩은 0 이어도 한 번 부른다 —
  `engines/colab_156/loop.review_steps` 의 규칙). 프롬프트 글은 지은 짧은 글이고 비용 상한은 넉넉한 1.0(모의 사용량은
  가상)이다. 칸이 없으면 내는 꼴도 지금과 같다(loops 칸 없음).

내는 꼴 `dvcolab.result/1`: `calls` 마다 `{"id", "outcome": "ok" | "raise", "value"}`(raise 면 "<타입>: <글>"),
`prompts` 마다 `{"id", "system", "user"}`, `constants`, (loops 가 있으면) `loops` 마다
`{"id", "executed": [[이름, 인자 글]], "outputs": [결과 글], "providerCalls", "ending": "done" | "partial" | "failed",
"text"}`.
캐시는 사례마다 새 `ValueCache` 다. NaN·Infinity 는 json 기본 그대로(양쪽이 같은 파이썬 규칙).
I/O: 두 파일(입력·출력)과, loops 가 있을 때 core.llm 이 꾸러미 안에서 읽는 정본 설정·프롬프트 봉투. 공급사는 모의뿐이라
네트워크·키는 0 이다(`env -u OPENAI_API_KEY …` 아래에서 돌린다).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Tags, ToolLoopFailed, UrlCitation
from esgapi.dataverify.engines.colab_156 import dispatch, prompts, schemas, tools
from esgapi.dataverify.engines.colab_156.inputs import split_themes
from esgapi.dataverify.engines.colab_156.loop import report_text
from esgapi.dataverify.flows import colab_156

FORMAT_IN = "dvcolab.cases/1"
FORMAT_OUT = "dvcolab.result/1"
WITH_DATA_AND_CACHE = {
    "tool_value_of_by_name",
    "tool_sum_check_by_name",
    "tool_sum_n_check_by_names",
    "tool_ratio_check_by_name",
}
PLAIN = {"tool_sum_check", "tool_sum_n_check", "tool_ratio_check"}


def _invoke(call: dict[str, Any], data: Any, tolerance: Any) -> Any:
    fn: str = call["fn"]
    args: Any = call.get("args", [])
    positional: list[Any] = list(args) if isinstance(args, list) else []  # pyright: ignore[reportUnknownArgumentType]
    keywords: dict[str, Any] = dict(args) if isinstance(args, dict) else {}  # pyright: ignore[reportUnknownArgumentType]
    if fn in PLAIN:
        return getattr(tools, fn)(*positional, **keywords)
    if fn in WITH_DATA_AND_CACHE:
        return getattr(tools, fn)(data, *positional, **keywords, cache=tools.ValueCache())
    if fn == "tool_search_items":
        return tools.tool_search_items(data, *positional, **keywords)
    if fn == "_run_local_tool":
        name, tool_args = positional
        return dispatch._run_local_tool(name, tool_args, data=data, tolerance=tolerance, cache=tools.ValueCache())
    if fn == "split_themes":
        return split_themes(positional[0])
    raise SystemExit(f"모르는 fn: {fn!r}")


def _outcome(run: Callable[[], Any]) -> dict[str, Any]:
    try:
        value = run()
    except Exception as error:  # 예외도 견줄 값이다
        return {"outcome": "raise", "value": f"{type(error).__name__}: {error}"}
    return {"outcome": "ok", "value": value}


def _prompt(kind: str, variables: dict[str, Any], data_split: dict[str, Any]) -> tuple[str, str]:
    if kind == "review":
        return prompts.review_prompt(hints=variables["hints"], data_split=data_split)
    company = {key: variables[key] for key in ("company_name", "sasb_industry", "material_topics", "reporting_year")}
    if kind == "plan":
        return prompts.plan_prompt(**company, data_split=data_split)
    if kind == "insight":
        return prompts.insight_prompt(**company, data_split=data_split)
    raise SystemExit(f"모르는 kind: {kind!r}")


TAGS = Tags(tenant="tenant-synthetic", module="dataverify")


def _loop(case: dict[str, Any], data_split: dict[str, Any]) -> dict[str, Any]:
    mock = MockProvider("openai")
    for entry in case["script"]:
        if "calls" in entry:
            mock.enqueue_tool_calls(
                [(name, arguments) for name, arguments in entry["calls"]], text=entry.get("text", "")
            )
        else:
            citations = [
                UrlCitation(url=c["url"], title=c["title"], start_index=0, end_index=0)
                for c in entry.get("citations", [])
            ]
            mock.enqueue_text(entry["text"], citations=citations, hosted_calls=entry.get("hosted", 0))
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": mock},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    run = colab_156.run_loop(
        client,
        stage=case["stage"],
        system="가상 system",
        user="가상 user",
        data_split=data_split,
        max_steps=max(1, case["maxSteps"]),
        max_cost_usd=1.0,
        tags=TAGS,
    )
    result = run.result
    return {
        "id": case["id"],
        "executed": [[call.name, call.arguments] for step in result.steps for call in step.calls],
        "outputs": [output.output for step in result.steps for output in step.outputs],
        "providerCalls": len(mock.calls),
        "ending": result.kind,
        "text": None if isinstance(result, ToolLoopFailed) else report_text(result.text),
    }


def dump(cases: dict[str, Any]) -> dict[str, Any]:
    if cases.get("format") != FORMAT_IN:
        raise SystemExit(f"사례 꼴이 {FORMAT_IN} 가 아니다: {cases.get('format')!r}")
    data: Any = cases["data"]
    tolerance: Any = cases["tolerance"]
    calls: list[dict[str, Any]] = []
    for call in cases["calls"]:
        call_data = call.get("data", data)
        calls.append({"id": call["id"], **_outcome(lambda: _invoke(call, call_data, tolerance))})  # noqa: B023 — 바로 부른다
    data_split = split_themes(data)
    rendered: list[dict[str, Any]] = []
    hints: list[str] = []
    for entry in cases["prompts"]:
        system, user = _prompt(entry["kind"], entry["vars"], data_split)
        rendered.append({"id": entry["id"], "system": system, "user": user})
        if entry["kind"] == "review":
            hints = entry["vars"]["hints"]
    constants = {
        "TOOLS_RESPONSES": schemas.TOOLS_RESPONSES,
        "TOOLS_RESPONSES_websearch": schemas.TOOLS_RESPONSES_websearch,
        "MODEL_RESP": prompts.MODEL_RESP,
        "TOLERANCE": prompts.TOLERANCE,
        "PLAN_MAX_STEPS": prompts.PLAN_MAX_STEPS,
        "REVIEW_MAX_STEPS": prompts.review_max_steps(hints),
        "INSIGHT_MAX_STEPS": prompts.INSIGHT_MAX_STEPS,
    }
    out: dict[str, Any] = {
        "format": FORMAT_OUT,
        "side": "engine",
        "calls": calls,
        "prompts": rendered,
        "constants": constants,
    }
    if "loops" in cases:
        out["loops"] = [_loop(case, data_split) for case in cases["loops"]]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="데이터 검증 엔진의 값을 dvcolab 견줌용 JSON 으로 쓴다")
    parser.add_argument(
        "--cases", type=Path, required=True, help="사례 JSON(dvcolab.cases/1 — esg-lab dvcolab 이 낸다)"
    )
    parser.add_argument("--out", type=Path, required=True, help="엔진 결과 JSON(dvcolab.result/1)")
    args = parser.parse_args(argv)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    result = dump(cases)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    loops = f" · 고리 {len(result['loops'])}" if "loops" in result else ""
    print(f"사례 {len(result['calls'])} · 프롬프트 {len(result['prompts'])}{loops} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
