"""밴드 IR2a §4-7: 코랩 2부(셀 46·50·55·65·8)와 엔진·흐름의 글·읽기·요청 몸 대조(사본 0).

    사용(apps/api-py 에서): uv run --frozen python -I scripts/materiality_compare_ir2a.py <읽기판.md> <출력 자리>

받은 코랩의 읽기판에서 셀 46·50·55 의 system dedent 대입과 user f-문자열, 셀 50 의 정규화 try 블록, 셀 65 의
`_extract_json_object`·`normalize`, 셀 8 의 `responsesPromptRunner` 클래스를 실행 때 AST 로 떼어(출력 자리에만
ast.unparse 로 남긴다 — git 밖, MARC-ENT-310) 우리와 같은 값의 가짜 전역에서 돈다. 저장소에는 코랩 코드가 없다(줄
범위·이름만). 네트워크·키 0.

    ① system 셋: 코랩 글에서 바꾸는 자리(아래 SYSTEMS 의 줄 범위)만 엔진의 새 글로 갈음한 글 == 엔진 글. 새 글 가운데
       셀 50 [FINAL OUTPUT](R/2527-2580) 줄과 같지 않은 줄 수를 센다(목록은 출력 자리에만).
    ② user 셋 바이트 같음: 셀 46 은 .strip() 자리에 contracts 의 셀 50 꼴 글(③)을 넣어, 셀 50 은 그대로, 셀 55 는
       {fin_impact} 에 part2_render.pathway_table 의 표(⑧)를 넣어. 입력은 지은 예시(토픽 done·failed·not_run 셋 × 산업
       하나·둘 × valueChain 있음·없음).
    ③ 지어낸 답 글(정상·코드블록 감쌈·앞뒤 글·잘림·빈 글·목록): 글 → 객체는 셀 65 normalize 와(_raw_text ↔ 못
       읽음), 객체 → 행은 같은 객체를 셀 50 정규화 try 블록에 넣어 견준다. 셀 50 의 json.loads 만으로 못 읽는 답(감쌈·
       앞뒤 글)과 목록 답은 허용 차이(처분 ⑤ — 셀 65 를 따른다)로 따로 센다.
    ④ 요청 몸: 같은 글로 코랩 subtopic_impactdef_prompt 의 create kwargs ↔ 흐름(part2_155.run_part2_call 위
       core.llm + OpenAIProvider) 의 kwargs — 같아야: model·tools·temperature 없음·system 글. 허용: system 자리(코랩
       input 의 system 메시지 ↔ 흐름 instructions, 처분 ⑥ — latest 참이면 input 의 system 메시지로 같다)·
       max_output_tokens·store·timeout·user 글 ↔ input_text 목록. latest_event_mode 거짓·참 둘.

출력은 이름·수만(읽기판의 글을 싣지 않는다). 끝 줄 COLAB_DIFF=<다름 수>, 종료 코드는 그것이 0 일 때만 0.
"""

import ast
import json
import os
import re
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any, cast

from openai.types.responses import Response

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Tags
from esgapi.materiality.contracts import wire
from esgapi.materiality.engines.colab_155 import constants, part2_parsing, part2_prompts, part2_render
from esgapi.materiality.flows import colab_155, part2_155

EXAMPLES = Path(wire.__file__).resolve().parents[1] / "tests" / "data" / "examples"

SYSTEMS: dict[str, tuple[int, int, list[tuple[int, int]]]] = {
    "impact": (46, 2146, [(2153, 2153), (2214, 2215), (2225, 2270)]),
    "financial": (50, 2418, [(2546, 2545)]),
    "pathway": (55, 3003, [(3099, 3105)]),
}
"""이름 → (셀, dedent 대입 줄, 바꾸는 자리 [(첫 줄, 끝 줄)]). (n, n-1) 은 n 앞에 끼움(지우는 줄 없음)."""
CELL50_JSON = (2527, 2580)
"""새 JSON 절 줄의 견줄 원천(셀 50 [FINAL OUTPUT — JSON ONLY])."""
LANGUAGE_LINE = 2227
"""셀 46 의 출력 언어 문장 줄(갈음 범위 R/2225-2270 안 — 새 JSON 절에 글자째 남긴다)."""

diffs: dict[str, int] = {}
counts: dict[str, int] = {}
allowed: dict[str, int] = {}


def check(group: str, name: str, ours: Any, theirs: Any) -> None:
    counts[group] = counts.get(group, 0) + 1
    if ours != theirs:
        diffs[group] = diffs.get(group, 0) + 1
        print(f"  ★ {group} {name}: 다르다")


def cell_code(text: str, cell: int) -> tuple[str, int]:
    """읽기판에서 셀 하나의 코드와 그 첫 줄의 읽기판 줄 번호."""
    m = re.search(rf"^### 셀 {cell} · code\n\n(`{{3,4}})python\n(.*?)\n\1$", text, re.S | re.M)
    if not m:
        raise SystemExit(f"  ★ 읽기판에서 셀 {cell} 의 코드를 못 찾았다")
    return m.group(2), text[: m.start(2)].count("\n") + 1


class Pieces:
    """읽기판에서 뗀 조각(출력 자리에 ast.unparse 로 남긴다)."""

    def __init__(self, reading: str, out: str) -> None:
        self.text = Path(reading).read_text(encoding="utf-8")
        self.out = out
        os.makedirs(out, exist_ok=True)

    def tree(self, cell: int) -> tuple[ast.Module, int]:
        code, start = cell_code(self.text, cell)
        return ast.parse(code), start

    def assign(self, cell: int, name: str) -> tuple[ast.expr, int]:
        """셀 안의 `name = …` 첫 대입의 값 식과 그 읽기판 줄."""
        tree, start = self.tree(cell)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                self.keep(f"cell{cell}-{name}", node)
                return node.value, start + node.lineno - 1
        raise SystemExit(f"  ★ 셀 {cell} 에서 {name} 대입을 못 찾았다")

    def keep(self, label: str, node: ast.Module | ast.stmt) -> None:
        body = node if isinstance(node, ast.Module) else ast.Module(body=[node], type_ignores=[])
        Path(self.out, f"piece-{label}.py").write_text(ast.unparse(body) + "\n", encoding="utf-8")

    def evaluate(self, cell: int, name: str, scope: dict[str, Any]) -> tuple[str, int]:
        value, line = self.assign(cell, name)
        result = eval(compile(ast.Expression(value), f"cell{cell}", "eval"), {"dedent": dedent, **scope})  # noqa: S307
        return result, line

    def functions(self, cell: int, names: tuple[str, ...]) -> dict[str, Any]:
        tree, _ = self.tree(cell)
        nodes: list[ast.stmt] = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        module = ast.Module(body=nodes, type_ignores=[])
        self.keep(f"cell{cell}-functions", module)
        ns: dict[str, Any] = {"json": json}
        exec(compile(module, f"cell{cell}", "exec"), ns)  # noqa: S102 — 대조 대상(코랩 셀의 함수 정의만)을 돈다
        return {n: ns[n] for n in names}

    def normalizer(self) -> Any:
        """셀 50 의 정규화 try 블록(json.loads → impacts → context)을 함수로 감싸 돌린다."""
        tree, _ = self.tree(50)
        tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try) and "impacts" in ast.unparse(n)]
        (block,) = tries
        func = ast.FunctionDef(
            name="cell50_normalize",
            args=ast.arguments(
                posonlyargs=[], args=[ast.arg(arg="result")], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[
                *ast.parse("append_fin_impact = {'t': {'s': None}}\ntopic_each = 't'\nsub_name = 's'").body,
                block,
                ast.parse("return append_fin_impact['t']['s']").body[0],
            ],
            decorator_list=[],
            type_params=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[]))
        self.keep("cell50-normalize", module)
        ns: dict[str, Any] = {"json": json, "print": _quiet}
        exec(compile(module, "cell50", "exec"), ns)  # noqa: S102 — 대조 대상(셀 50 의 정규화 블록)을 돈다
        return ns["cell50_normalize"]


def _quiet(*args: object, **kwargs: object) -> None:
    """코랩의 print 를 삼킨다(읽기판의 글이 출력에 실리지 않게)."""


def expected_system(colab: str, ours: str, line0: int, spans: list[tuple[int, int]]) -> tuple[list[str], list[str]]:
    """코랩 글의 줄(index j ↔ 읽기판 line0 + j)에서 바꾸는 자리를 엔진 글의 해당 줄로 갈음한 줄 목록과, 갈음해 넣은 엔진
    줄들. 엔진 글에서 그 자리 밖은 코랩 줄과 차례대로 맞아야 하므로 앞·뒤에서 맞춰 바꾼 몫을 뗀다."""
    theirs, mine = colab.split("\n"), ours.split("\n")
    kept: list[tuple[int, int]] = []  # 코랩에서 남는 [a, b) 조각
    cursor = 0
    for first, last in spans:
        kept.append((cursor, first - line0))
        cursor = last - line0 + 1
    kept.append((cursor, len(theirs)))
    out: list[str] = []
    inserted: list[str] = []
    position = 0  # 엔진 줄의 자리
    for index, (a, b) in enumerate(kept):
        piece = theirs[a:b]
        if index == 0:
            start = 0
        elif index == len(kept) - 1:
            start = len(mine) - len(piece)
        else:  # 이 조각이 엔진 글에서 처음 나오는 자리(앞 조각 뒤)
            start = next(
                (o for o in range(position, len(mine) - len(piece) + 1) if mine[o : o + len(piece)] == piece), -1
            )
        if start < position:  # 못 찾음 — 엔진 줄을 그대로 실어 다르게 한다
            return [*mine, "(조각을 못 찾음)"], inserted
        new = mine[position:start]
        out += new + piece
        inserted += new
        position = start + len(piece)
    return out, inserted


def main() -> int:
    reading, out = sys.argv[1], sys.argv[2]
    pieces = Pieces(reading, out)
    readout = pieces.text.split("\n")

    # ① system 셋
    engine = {
        "impact": part2_prompts.IMPACT_SYSTEM,
        "financial": part2_prompts.FINANCIAL_SYSTEM,
        "pathway": part2_prompts.PATHWAY_SYSTEM,
    }
    names = {"impact": "system_prompt_subtopic_impact", "financial": "system_prompt_subtopic_impact"}
    names["pathway"] = "system_prompt_fin_impact_pathway"
    cell50_json = {line.strip() for line in readout[CELL50_JSON[0] - 1 : CELL50_JSON[1]]}
    new_lines: list[str] = []
    for key, (cell, line0, spans) in SYSTEMS.items():
        colab, line = pieces.evaluate(cell, names[key], {})
        check("①system", f"{key} 대입 줄", line, line0)
        expected, inserted = expected_system(colab, engine[key], line0, spans)
        check("①system", f"{key} 바꾸는 자리 밖 바이트", engine[key], "\n".join(expected))
        fresh = [s for s in inserted if s.strip() and s.strip() not in cell50_json]
        if (
            key == "impact"
        ):  # 셀 46 [최종 Output Format] 1 의 출력 언어 문장(R/2227)을 JSON 절에 「- 」 꼴로(감독 처분 ⑤)
            language = readout[LANGUAGE_LINE - 1].strip().removeprefix("1. ")
            check("①system", "impact 출력 언어 문장(R/2227)", inserted.count(f"- {language}"), 1)
        new_lines += [f"{key}: {s}" for s in fresh]
        print(
            f"  ① {key}: 셀 {cell} R/{line0} · 갈음 {len(spans)}곳 · 넣은 줄 {len(inserted)} · "
            f"셀 50 JSON 절 밖 줄 {len(fresh)}"
        )
    Path(out, "new-sentences.txt").write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # ② user 셋
    received = json.loads((EXAMPLES / "input-sample.json").read_text(encoding="utf-8"))
    result = json.loads((EXAMPLES / "result-sample.json").read_text(encoding="utf-8"))
    fin_rows: list[dict[str, Any]] = [
        {
            "impact_definition": "가상 정의 | 하나\n둘째 줄",
            "impact_type": "리스크",
            "risk_type": "리스크-평판",
            "context": {
                "controversies": [{"title": "가상 사건", "summary": "가상 요약", "url": "https://example.com/c"}],
                "regulations": [{"title": "가상 규정", "summary": None, "url": "https://example.com/r"}],
            },
        },
        {"impact_definition": "가상 기회", "impact_type": "기회", "risk_type": None, "context": {}},
    ]
    for industries in (1, 2):
        for chain in (True, False):
            given = {**received, "industries": received["industries"][:industries]}
            if not chain:
                given["valueChain"] = None
            part2_input, _ = wire.part2_input_from_result(given, result)
            value_chain = part2_input["valueChain"] or []
            for t in part2_input["topics"]:
                scope = {
                    "company": part2_input["company"],
                    "industry": part2_input["industry"],
                    "value_chain": value_chain,
                    "topic_each": t["topic"],
                    "sub_name": f"{t['topic']} 서브",
                    "sub_desc": "가상 서브 설명",
                }
                sub_name = f"{t['topic']} 서브"
                args = (
                    part2_input["company"],
                    part2_input["industry"],
                    value_chain,
                    t["topic"],
                    sub_name,
                    "가상 서브 설명",
                )
                theirs46, _ = pieces.evaluate(
                    46,
                    "user_input",
                    {**scope, "controversies": t["controversyText"], "regulation_updates": t["regulationText"]},
                )
                ours46 = part2_prompts.impact_user(*args, t["controversyText"], t["regulationText"])
                check("②user", f"46 산업{industries} 사슬{chain} {t['topic']}", ours46, theirs46)
                theirs50, _ = pieces.evaluate(
                    50,
                    "user_input",
                    {**scope, "controversies_text": t["controversyText"], "regulation_text": t["regulationText"]},
                )
                ours50 = part2_prompts.financial_user(*args, t["controversyText"], t["regulationText"])
                check("②user", f"50 산업{industries} 사슬{chain} {t['topic']}", ours50, theirs50)
                table = part2_render.pathway_table(t["topic"], sub_name, fin_rows)
                theirs55, _ = pieces.evaluate(55, "user_input", {**scope, "fin_impact": table})
                check("②user", f"55 {t['topic']}", part2_prompts.pathway_user(table), theirs55)
                for text in (ours46, ours50):
                    check("②user", "기간 값 없음", received["dateRange"] in text, False)

    # ③ 답 읽기
    found = pieces.functions(65, ("_extract_json_object", "normalize"))
    normalize = found["normalize"]
    cell50 = pieces.normalizer()
    body = {
        "topic": "가상",
        "impacts": [
            {"impact_definition": "가상 하나", "impact_type": "리스크", "context": {"regulations": "글"}},
            "글 원소",
            {"impact_definition": "가상 둘", "context": None},
            {"impact_definition": "가상 셋", "context": ["목록"]},
        ],
    }
    plain = json.dumps(body, ensure_ascii=False)
    cases = {
        "정상": (plain, True),
        "들여쓴 정상": (json.dumps(body, ensure_ascii=False, indent=2), True),
        "impacts 없음": (json.dumps({"topic": "가상"}), True),
        "impacts 글": (json.dumps({"impacts": "가상"}), True),
        "코드블록": ("```json\n" + plain + "\n```", False),
        "앞뒤 글": ("가상 앞 글 " + plain + " 가상 뒤 글", False),
        "잘림": (plain[: len(plain) // 2], True),
        "빈 글": ("", True),
        "목록": ("[1, 2]", False),
    }
    for name, (text, loads_ok) in cases.items():
        theirs: Any = normalize({"t": {"s": text}})["t"]["s"]
        parsed, _ = part2_parsing.parse_part2(text)
        if name == "목록":
            allowed["③ 목록 답(코랩 list 그대로 ↔ 못 읽음)"] = 1
            check("③읽기", f"{name} 우리 못 읽음", parsed, None)
            continue
        unread = isinstance(theirs, dict) and "_raw_text" in cast("dict[str, Any]", theirs)
        theirs_obj = cast("Any", None if unread else theirs)
        check("③읽기", f"{name} 글 → 객체(셀 65)", parsed, theirs_obj)
        if parsed is None:
            continue
        rows, _ = part2_parsing.read_rows(parsed, part2_parsing.IMPACTS)
        colab_rows = cell50({"output_text": text})
        if not loads_ok:
            allowed[f"③ {name}(셀 50 json.loads 실패 → [] ↔ 셀 65 로 읽음)"] = 1
            check("③읽기", f"{name} 셀 50 은 빈 목록", colab_rows, [])
            colab_rows = cell50({"output_text": json.dumps(parsed, ensure_ascii=False)})
        check("③읽기", f"{name} 객체 → 행(셀 50)", rows if rows is not None else [], colab_rows)

    request_body(pieces, received, result)

    for k in sorted(counts):
        print(f"  {k}: 견줌 {counts[k]} · 다름 {diffs.get(k, 0)}")
    for k in sorted(allowed):
        print(f"  허용 차이: {k}")
    total = sum(diffs.values())
    print(f"COLAB_DIFF={total}")
    return int(total != 0)


USAGE = {
    "input_tokens": 10,
    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
    "output_tokens": 2,
    "output_tokens_details": {"reasoning_tokens": 0},
    "total_tokens": 12,
}
ALLOWED_KEYS = {"max_output_tokens", "store", "timeout"}
"""흐름에만 있어도 되는 칸(보고의 다른 자리 표): 출력 상한·store·timeout. system 자리(instructions)는 latest 거짓일
때만 더 허용하고, input 은 길이(코랩 2 ↔ 흐름 거짓 1·참 2)와 system 메시지·user 글을 따로 견준다."""


def sdk_response(status: str = "completed", *, texts: tuple[str, ...] = ("{}",)) -> Any:
    """지어낸 SDK 응답(글은 가상)."""

    output: list[dict[str, Any]] = [
        {
            "type": "message",
            "id": f"msg_{i}",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
        for i, text in enumerate(texts)
    ]
    body: dict[str, Any] = {
        "id": "resp_1",
        "object": "response",
        "created_at": 0,
        "model": "gpt-4.1-2025-04-14",
        "status": status,
        "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
        "output": output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": USAGE,
    }
    return Response.model_validate(body)


class FakeResponses:
    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.created: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.created.append(kwargs)
        return self.replies.pop(0)


class FakeClient:
    def __init__(self, replies: list[Any]) -> None:
        self.responses = FakeResponses(replies)


def colab_runner(pieces: Pieces, client: FakeClient) -> Any:
    """셀 8 의 responsesPromptRunner 클래스 정의만 떼어 가짜 client 가 든 이름공간에서 정의한 인스턴스."""
    tree, _ = pieces.tree(8)
    (node,) = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "responsesPromptRunner"]
    module = ast.Module(body=[node], type_ignores=[])
    pieces.keep("cell8-runner", module)
    ns: dict[str, Any] = {"client": client, "print": _quiet}
    exec(compile(module, "cell8", "exec"), ns)  # noqa: S102 — 대조 대상(셀 8 의 클래스 정의만)을 돈다
    return ns["responsesPromptRunner"]()


def flow_call(replies: list[Any], phase: Any, system: str, user: str, latest: bool) -> tuple[FakeClient, Any]:

    client = FakeClient(replies)
    llm = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": OpenAIProvider(client=cast("Any", client))},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    inputs = part2_155.Part2Inputs(
        tags=Tags(tenant="t-synthetic", module="materiality"),
        max_cost_usd=5.0,
        texts=colab_155.DEFAULT_TEXTS,
        max_output_tokens=part2_155.CODE_ANALYSIS.max_output_tokens,
    )
    called = part2_155.run_part2_call(
        llm, phase=phase, topic="t", subtopic="s", system=system, user=user, inputs=inputs, latest=latest, spent=0.0
    )
    return client, called


def request_body(pieces: Pieces, received: dict[str, Any], result: dict[str, Any]) -> None:
    """④ 요청 몸 + (b) 답 글: 같은 글로 코랩 셀 8 subtopic_impactdef_prompt ↔ 흐름 run_part2_call."""

    part2_input, _ = wire.part2_input_from_result(received, result)
    t = part2_input["topics"][0]
    vc = part2_input["valueChain"] or []
    args = (part2_input["company"], part2_input["industry"], vc, t["topic"], "가상 서브", "가상 설명")
    messages = {
        "impact": (
            part2_prompts.IMPACT_SYSTEM,
            part2_prompts.impact_user(*args, t["controversyText"], t["regulationText"]),
        ),
        "financial": (
            part2_prompts.FINANCIAL_SYSTEM,
            part2_prompts.financial_user(*args, t["controversyText"], t["regulationText"]),
        ),
        "pathway": (part2_prompts.PATHWAY_SYSTEM, part2_prompts.pathway_user("| Topic |\n|---|")),
    }
    for latest in (False, True):
        for phase, (system, user) in messages.items():
            theirs_client = FakeClient([sdk_response()])
            colab_runner(pieces, theirs_client).subtopic_impactdef_prompt(system, user, constants.MODEL_PART2, latest)
            ours_client, _ = flow_call([sdk_response()], phase, system, user, latest)
            (theirs,) = theirs_client.responses.created
            (ours,) = ours_client.responses.created
            label = f"{phase} latest={latest}"
            check("④몸", f"{label} model", ours.get("model"), theirs.get("model"))
            check("④몸", f"{label} tools", ours.get("tools"), theirs.get("tools"))
            check("④몸", f"{label} temperature 없음", ("temperature" in ours, "temperature" in theirs), (False, False))
            check("④몸", f"{label} tool_choice 없음", "tool_choice" in ours, False)
            allowed = ALLOWED_KEYS | ({"instructions"} if not latest else set[str]())
            extra = sorted((set(ours) ^ set(theirs)) - allowed - {"model", "tools"})
            check("④몸", f"{label} input 길이", (len(theirs["input"]), len(ours["input"])), (2, 2 if latest else 1))
            check("④몸", f"{label} 허용 목록 밖 칸 {extra}", extra, [])
            check("④몸", f"{label} 코랩 system", theirs["input"][0], {"role": "system", "content": system})
            check("④몸", f"{label} 코랩 user", theirs["input"][1], {"role": "user", "content": user})
            ours_system = ours["input"][0] if latest else {"role": "system", "content": ours.get("instructions")}
            check("④몸", f"{label} 흐름 system 글", ours_system, theirs["input"][0])
            check(
                "④몸",
                f"{label} 흐름 user",
                ours["input"][-1],
                {"role": "user", "content": [{"type": "input_text", "text": user}]},
            )
            check(
                "④몸",
                f"{label} 허용 칸 값",
                (ours.get("store"), ours.get("max_output_tokens"), ours.get("timeout")),
                (False, part2_155.MAX_OUTPUT_TOKENS_PART2, part2_155.TIMEOUT_MS_PART2 / 1000),
            )

    # (b) 답 글: 끝남(message 둘)·잘림(incomplete) — 코랩 output_text ↔ 흐름 답 글
    system, user = messages["impact"]
    for status, texts in (("completed", ("가상 앞 글 ", '{"impacts": []}')), ("incomplete", ('{"impacts": [', "{"))):
        theirs_client = FakeClient([sdk_response(status, texts=texts)])
        got = colab_runner(pieces, theirs_client).subtopic_impactdef_prompt(system, user, constants.MODEL_PART2, False)
        _, called = flow_call([sdk_response(status, texts=texts)], "impact", system, user, False)
        check("④글", f"{status} 답 글", called.text, got["output_text"])
        check("④글", f"{status} 잘림 표시", called.truncated, status == "incomplete")


if __name__ == "__main__":
    sys.exit(main())
