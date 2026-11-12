"""밴드 IR1b §4-7: 코랩 셀 8 러너와 흐름 materiality.colab@155 의 요청 몸 대조(사본 0).

    사용(apps/api-py 에서): uv run --frozen python -I scripts/materiality_compare_ir1b.py <읽기판.md> <출력 자리>

받은 코랩의 읽기판에서 셀 8 의 `responsesPromptRunner` 클래스 정의를 실행 때 AST 로 떼어(출력 자리에만 ast.unparse 로
남긴다 — git 밖, MARC-ENT-310) 가짜 `client`·`time` 이 든 이름공간에서 돈다. 저장소에는 코랩 코드가 없다(줄 범위·
이름만). 흐름 쪽은 core.llm 의 LlmClient + OpenAIProvider(같은 가짜 client) 로 `flows/colab_155.run_call` 을 부른다.
가짜 client 는 응답을 설치된 SDK 의 `Response.model_validate` 로 짓고 받은 kwargs 를 적는다. 네트워크·키 0.

    ① 단계 셋(규제·키워드·컨트로버시)마다 같은 글로 코랩 create 의 kwargs ↔ 흐름 create 의 kwargs 를 칸마다 —
       같아야: model·temperature·tools(user_location 포함)·tool_choice·system 메시지. 허용 목록(= 보고의 다른 자리 표):
       user 둘 ↔ 하나(흐름 글 == 접두 + "\\n\\n" + 가변 은 따로 단언), 글 ↔ input_text 목록,
       prompt_cache_key(흐름 없음), store(흐름 false), max_output_tokens(흐름 16,384),
       timeout(흐름 600초 — 코랩은 SDK 기본 600초).
    ② 첫 응답 incomplete(max_output_tokens)·둘째 completed: 코랩 create 2 == 흐름 공급사 호출 2, retrieve 는 코랩에서만
       ≥ 12(흐름은 store:false·폴링 없음).
    ③ 같은 SDK 응답(message 둘·url_citation)을 코랩 `_extract_text` 와 `OpenAIProvider.invoke` 에 넣어 글이 같다.

출력은 이름·수·EXIT 만(읽기판의 글을 싣지 않는다). 끝 줄 COLAB_DIFF=<다름 수>, 종료 코드는 그것이 0 일 때만 0.
"""

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

from openai.types.responses import Response

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import InvokeOptions, ProviderRequest, SystemSegment, Tags, TextPart
from esgapi.materiality.contracts import wire
from esgapi.materiality.engines.colab_155 import constants, prompts, whitelists
from esgapi.materiality.engines.colab_155.inputs import industry_text
from esgapi.materiality.flows import colab_155

CELL = 8
CLASS = "responsesPromptRunner"
ALLOWED = {"input", "prompt_cache_key", "store", "max_output_tokens", "timeout"}
"""칸 이름이 다를 수 있는 것(보고의 다른 자리 표). input 은 system 메시지와 user 글을 따로 견준다."""
SAME = ("model", "temperature", "tools", "tool_choice")
EXAMPLE = Path(colab_155.__file__).resolve().parents[1] / "tests" / "data" / "examples" / "input-sample.json"
USAGE = {
    "input_tokens": 10,
    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
    "output_tokens": 2,
    "output_tokens_details": {"reasoning_tokens": 0},
    "total_tokens": 12,
}

diffs: dict[str, int] = {}
counts: dict[str, int] = {}


def check(group: str, name: str, ours: Any, theirs: Any) -> None:
    counts[group] = counts.get(group, 0) + 1
    if ours != theirs:
        diffs[group] = diffs.get(group, 0) + 1
        print(f"  ★ {group} {name}: 다르다")


def response(
    status: str = "completed", *, texts: tuple[str, ...] = ("{}",), rid: str = "resp_1", **extra: Any
) -> Response:
    """지어낸 SDK 응답(글·URL 은 가상)."""
    output: list[dict[str, Any]] = [
        {"type": "web_search_call", "id": "ws_1", "status": "completed", "action": {"type": "search", "query": "q"}}
    ]
    for i, text in enumerate(texts):
        annotations = [
            {"type": "url_citation", "url": "https://example.com/v", "title": "가상", "start_index": 0, "end_index": 1}
        ]
        output.append(
            {
                "type": "message",
                "id": f"msg_{i}",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": annotations}],
            }
        )
    body: dict[str, Any] = {
        "id": rid,
        "object": "response",
        "created_at": 0,
        "model": "gpt-4o-2024-08-06",
        "status": status,
        "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
        "output": output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": USAGE,
        **extra,
    }
    return Response.model_validate(body)


class FakeResponses:
    def __init__(self, replies: list[Response]) -> None:
        self.replies = list(replies)
        self.created: list[dict[str, Any]] = []
        self.retrieved = 0
        self.by_id: dict[str, Response] = {}

    def create(self, **kwargs: Any) -> Response:
        self.created.append(kwargs)
        reply = self.replies.pop(0)
        self.by_id[reply.id] = reply
        return reply

    def retrieve(self, response_id: str) -> Response:
        self.retrieved += 1
        return self.by_id[response_id]


class FakeClient:
    def __init__(self, replies: list[Response]) -> None:
        self.responses = FakeResponses(replies)


class FakeTime:
    def __init__(self) -> None:
        self.slept = 0

    def sleep(self, seconds: float) -> None:
        self.slept += 1


def runner_class(reading: str, out: str) -> Any:
    """읽기판 셀 8 코드에서 클래스 정의만 떼어 돌린 이름공간의 클래스(뗀 조각은 out 에만)."""
    text = Path(reading).read_text(encoding="utf-8")
    m = re.search(rf"^### 셀 {CELL} · code\n\n(`{{3,4}})python\n(.*?)\n\1$", text, re.S | re.M)
    if not m:
        raise SystemExit(f"  ★ 읽기판에서 셀 {CELL} 의 코드를 못 찾았다")
    tree = ast.parse(m.group(2))
    (node,) = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == CLASS]
    module = ast.Module(body=[node], type_ignores=[])
    os.makedirs(out, exist_ok=True)
    Path(out, f"piece-cell{CELL}.py").write_text(ast.unparse(module) + "\n", encoding="utf-8")
    start = text[: m.start(2)].count("\n") + 1
    print(
        f"  셀 {CELL} 클래스 R/{start + node.lineno - 1}-{start + (node.end_lineno or node.lineno) - 1}(뗀 조각 {out})"
    )
    return module


def _quiet(*args: object, **kwargs: object) -> None:
    """코랩의 print 를 삼킨다(읽기판의 글이 출력에 실리지 않게)."""


def colab_runner(module: Any, client: FakeClient, clock: FakeTime) -> Any:
    """뗀 클래스를 가짜 client·time 이 든 빈 이름공간에서 정의하고 인스턴스 하나를 돌려준다."""
    ns: dict[str, Any] = {"client": client, "time": clock, "print": _quiet}
    exec(compile(module, f"cell{CELL}", "exec"), ns)  # noqa: S102 — 대조 대상(코랩 셀 8 의 클래스 정의만)을 돈다
    return ns[CLASS]()


def colab_run(module: Any, replies: list[Response], **kwargs: Any) -> tuple[FakeClient, FakeTime, Any]:
    client, clock = FakeClient(replies), FakeTime()
    return client, clock, colab_runner(module, client, clock).run_web_search_prompt(**kwargs)


def flow_run(
    replies: list[Response], received: dict[str, Any], phase: Any, system: str, prefix: str, variable: str
) -> tuple[FakeClient, Any]:
    client = FakeClient(replies)
    llm = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": OpenAIProvider(client=cast("Any", client))},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    inputs = colab_155.MaterialityInputs(
        received=received,
        tags=Tags(tenant="t-synthetic", module="materiality"),
        max_cost_usd=5.0,
        texts=colab_155.DEFAULT_TEXTS,
        temperature=constants.TEMPERATURE,
        max_output_tokens=colab_155.CODE_RESEARCH.max_output_tokens,
    )
    called = colab_155.run_call(
        llm, phase=phase, topic=None, system=system, prefix=prefix, variable=variable, inputs=inputs, spent=0.0
    )
    return client, called


def messages(received: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """(단계, system, 접두, 가변) — 첫 토픽, 키워드 없음."""
    industry = wire.engine_industry(received)
    topics = wire.engine_topics(received)
    t = topics[0]
    _, raw = whitelists.whitelist_for(received["sector"])
    loc, lang = received["geoScope"], received["mainLanguage"]
    return [
        (
            "regulation",
            prompts.regulation_system(raw),
            prompts.REGULATION_USER_PREFIX,
            prompts.regulation_user(t["topic"], t["description"], industry_text(industry), loc, lang),
        ),
        (
            "keywords",
            prompts.KEYWORDS_SYSTEM,
            prompts.KEYWORDS_USER_PREFIX,
            prompts.keywords_user(industry, received["dateRange"], lang, topics),
        ),
        (
            "controversy",
            prompts.CONTROVERSY_SYSTEM,
            prompts.CONTROVERSY_USER_PREFIX,
            prompts.controversy_user(t["topic"], t["description"], industry, loc, lang, "(키워드 없음)"),
        ),
    ]


def main() -> int:
    reading, out = sys.argv[1], sys.argv[2]
    module = runner_class(reading, out)
    received = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    # ① 요청 몸
    for phase, system, prefix, variable in messages(received):
        theirs_client, _, _ = colab_run(
            module,
            [response()],
            user_location=received["userLocation"],
            system_prompt=system,
            user_prompt_prefix=prefix,
            user_prompt_variable=variable,
            model=constants.MODEL,
            prompt_cache_key=constants.CACHE_KEYS[phase],
        )
        ours_client, _ = flow_run([response()], received, phase, system, prefix, variable)
        (theirs,) = theirs_client.responses.created
        (ours,) = ours_client.responses.created
        for key in SAME:
            check("①몸", f"{phase} {key}", ours.get(key), theirs.get(key))
        extra = sorted((set(ours) ^ set(theirs)) - ALLOWED)
        check("①몸", f"{phase} 허용 목록 밖 칸 {extra}", extra, [])
        check("①몸", f"{phase} system", ours["input"][0], theirs["input"][0])
        check("①몸", f"{phase} system 이 코랩 글", theirs["input"][0], {"role": "system", "content": system})
        check("①몸", f"{phase} user 코랩 둘", [m["content"] for m in theirs["input"][1:]], [prefix, variable])
        check(
            "①몸",
            f"{phase} user 흐름 하나",
            ours["input"][1:],
            [{"role": "user", "content": [{"type": "input_text", "text": prefix + "\n\n" + variable}]}],
        )
        check(
            "①몸",
            f"{phase} 허용 칸 값",
            (ours.get("store"), ours.get("max_output_tokens"), ours.get("timeout"), "prompt_cache_key" in ours),
            (False, colab_155.MAX_OUTPUT_TOKENS, colab_155.TIMEOUT_MS / 1000, False),
        )
        check("①몸", f"{phase} 코랩 캐시 키", theirs.get("prompt_cache_key"), constants.CACHE_KEYS[phase])

    # ② incomplete → 재시도
    phase, system, prefix, variable = messages(received)[0]
    first, second = response("incomplete", texts=("{",), rid="resp_a"), response(rid="resp_b")
    theirs_client, clock, out_theirs = colab_run(
        module,
        [first, second],
        user_location=received["userLocation"],
        system_prompt=system,
        user_prompt_prefix=prefix,
        user_prompt_variable=variable,
        model=constants.MODEL,
        prompt_cache_key=constants.CACHE_KEYS[phase],
    )
    ours_client, called = flow_run(
        [response("incomplete", texts=("{",), rid="resp_a"), response(rid="resp_b")],
        received,
        phase,
        system,
        prefix,
        variable,
    )
    check("②재시도", "create 수", len(ours_client.responses.created), len(theirs_client.responses.created))
    check("②재시도", "create 2", len(theirs_client.responses.created), 2)
    check("②재시도", "흐름 retrieve 0", ours_client.responses.retrieved, 0)
    check("②재시도", "코랩 retrieve ≥ 12", theirs_client.responses.retrieved >= constants.POLL_TRIES, True)
    check("②재시도", "둘 다 둘째 글", called.text, out_theirs["output_text"])
    check("②재시도", "흐름 같은 몸 두 번", ours_client.responses.created[0], ours_client.responses.created[1])
    calls = len(ours_client.responses.created)
    print(f"  ② 코랩 retrieve {theirs_client.responses.retrieved} · sleep {clock.slept} · 흐름 공급사 호출 {calls}")

    # ③ 글 잇기(message 둘·url_citation)
    for texts in (("가상 앞 글 ", '{"a": 1}'), ("하나",), ("", "둘째만")):
        two = response(texts=texts)
        theirs_text = colab_runner(module, FakeClient([]), FakeTime())._extract_text(two)
        request = ProviderRequest(
            api_model_id="gpt-4o",
            system=(SystemSegment(text="s", cache=False),),
            user=(TextPart(text="u"),),
            max_output_tokens=10,
        )
        got = OpenAIProvider(client=cast("Any", FakeClient([two]))).invoke(request, InvokeOptions(timeout_ms=1000))
        check("③글", f"message {len(texts)}", getattr(got, "text", None), theirs_text)

    for k in sorted(counts):
        print(f"  {k}: 견줌 {counts[k]} · 다름 {diffs.get(k, 0)}")
    total = sum(diffs.values())
    print(f"COLAB_DIFF={total}")
    return int(total != 0)


if __name__ == "__main__":
    sys.exit(main())
