"""기본 판·NULL 글 판·옛 실행의 공급사 요청·결과가 BASE 와 바이트 같은지 재는 지문(RPA1 §4-6 — dataverify
tests/flows/texts_digest.py 의 꼴). 실호출 0 — 대본 심은 모의 공급사뿐.

지어낸 목차·쪽 글(support)로 `run_flow` 를 돌리고 경우마다 적는다: 호출마다 공급사 요청 몸 `ProviderRequest.to_json()`
(모델·system·user·max_output_tokens·temperature·스키마)의 sha, 그 몸에 없는 CallRequest 칸(경로 이름·시간 상한 —
call_fields)의 sha(부른 것·dry_run 위끝 잰 것 따로), 부른 수, 결과 dict(JSON)의 sha.

    hand · hand_mock     손 입력(support.inputs() — 그 트리의 코드 값)을 바로 넣음 · 모의 경로(mock=True)
    run_default          끼움(binding_v2.DraftingBinding)의 versions_with → inputs_with — 적용 판 없음(기본 판)
    run_null_texts       같은 길 — 적용 판이 저장 판이고 모델은 기본값의 정규형·글은 NULL(코드 글)
    run_old              같은 길 — versions 에서 AI 열쇠(aiSetting·aiSettingId·modelSettingsSha256·promptsSha256)를 뺀
                         옛 실행

이 파일은 BASE 에도 있는 것(support·test_binding_v2·draft_v2·binding_v2)만 처음에 import 한다. 끼움의 포트는
`inspect.signature` 로 가른다 — settings·models 가 없으면(BASE) 세 길이 다 판 없는 길이다. `scripts/section4-RPA1.sh`
가 이 파일을 BASE 트리(`git archive`)에 넣어 그쪽 흐름으로도 돌리고 두 지문을 견준다.

    uv run --frozen python -m esgapi.drafting.tests.flows.texts_digest [--dump <폴더>]
    uv run --frozen python -m esgapi.drafting.tests.flows.texts_digest --compare <기준 폴더> <새 폴더>

RPQ1 §4-6(선언 지문): --dump 는 경우마다 공급사 요청 몸 목록을 <경우>.json 에 뜬다. --compare 는 새 쪽 요청에서 선언한
바뀜만 되돌려 기준과 견준다 — 그 밖 칸이 하나라도 다르면 빨강.
RPS2 §3-6 의 선언(글 판 @3 — RPA4 의 선언을 갈음): S2(map) system·user 는 그대로 · S3(draft) system 은 MARKER_RULES 끝
꼬리 줄 `\n` + TABLE_LINE_RPS2 를 꼭 한 번 걷으면 BASE 와 같음 · S3 user 는 그대로.
--compare 는 새 트리에서만 부른다.
"""

import hashlib
import inspect
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from esgapi.core.flows.run import run_flow
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.drafting.flows import binding_v2, draft_v2
from esgapi.drafting.tests.flows import support
from esgapi.drafting.tests.flows.test_binding_v2 import A, NoArtifacts, source

CASES = ("hand", "hand_mock", "run_default", "run_null_texts", "run_old")
AI_KEYS = ("aiSetting", "aiSettingId", "modelSettingsSha256", "promptsSha256")
SETTING_ID = 3


def script(provider: Any) -> None:
    provider.enqueue_text(support.map_reply((2, ["ghg"]), (4, ["energy"]), (5, ["ghg"]), (1, [])))
    provider.enqueue_text(support.draft_reply(("가상 배출량 bullet", [2]), ("가상 감축 bullet", [5])))
    provider.enqueue_text(support.draft_reply(("가상 에너지 bullet", [4])))


class Models:
    """모델 설정 원천(실제 패키지 설정 — 가상 경로 0)."""

    def __init__(self, steps: Sequence[Any]) -> None:
        self._steps = steps

    def config(self) -> LlmConfig:
        return load_config(default_config_sources(synthetic=False))

    def steps(self) -> Sequence[Any]:
        return self._steps


class Store:
    def __init__(self, applied: Any, saved: Any) -> None:
        self._applied, self._saved = applied, saved

    def applied(self, company_id: int) -> Any:
        return self._applied

    def get(self, company_id: int, setting_id: int) -> Any:
        return self._saved


def spent_nothing(company_id: int, run_id: int) -> float:
    return 0.0


def binding(case: str) -> Any:
    found = source()
    ports: dict[str, Any] = {
        "projects": found,
        "max_usd": lambda: 5.0,
        "mock": lambda: False,
        "spent_usd": spent_nothing,
        "artifacts": NoArtifacts(),
        "bases": found,
    }
    if "settings" in inspect.signature(binding_v2.DraftingBinding.__init__).parameters:
        from esgapi.core.calc.ai_settings import defaults, to_input
        from esgapi.drafting.flows import prompt_model_v2

        models = Models(prompt_model_v2.MODELS)
        saved = binding_v2.SavedSetting(
            id=SETTING_ID,
            name="v1",
            model_settings=to_input(defaults(models.config(), models.steps())),
            prompts=None,
        )
        applied = saved if case == "run_null_texts" else binding_v2.DefaultSetting()
        ports |= {"settings": Store(applied, saved), "models": models}
    return binding_v2.DraftingBinding(**ports)


def run_inputs(case: str) -> Any:
    bound = binding(case)
    options = {"projectId": 7}
    versions = bound.versions_with(options, company_id=A)
    if case == "run_old":
        versions = {key: value for key, value in versions.items() if key not in AI_KEYS}
    return bound.inputs_with(options, company_id=A, versions=versions)


def inputs_of(case: str) -> Callable[[], Any]:
    return support.inputs if case.startswith("hand") else (lambda: run_inputs(case))


def text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=repr)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def call_fields(request: Any) -> list[object]:
    """공급사 몸(to_json)에 없는 CallRequest 칸 — 경로 이름·시간 상한·스키마 재시도와 위끝·temperature(RPA1 감독
    처분 R-c)."""
    return [
        request.prompt,
        request.route,
        request.timeout_ms,
        request.max_output_tokens,
        request.temperature,
        request.max_schema_retries,
        request.schema_name,
    ]


def fingerprint(case: str, dump: Path | None = None) -> dict[str, str]:
    provider, spy, adapters = support.world(mock=case == "hand_mock")
    script(provider)
    done = run_flow(draft_v2.FLOW, inputs_of(case)(), adapters)
    assert provider.pending == 0, (case, provider.pending)
    if dump is not None:
        (dump / f"{case}.json").write_text(text([request.to_json() for request in provider.calls]), encoding="utf-8")
    return {
        "requests": sha(text([request.to_json() for request in provider.calls])),
        "call_requests": sha(text([call_fields(request) for request in spy.requests])),
        "dry_requests": sha(text([call_fields(request) for request in spy.dry])),
        "calls": str(len(provider.calls)),
        "results": sha(text([dict(found) for found in done.output.results])),
    }


TABLE_LINE_RPS2 = "- 표에서 가져온 숫자는 표 위 제목·라벨 블록이 아니라 그 표의 `[T <id>]` 와 행 번호로 댄다."
"""RPS2 의 MARKER_RULES 꼬리 줄(선언 — 걷으면 BASE)."""


def _once(text: str, old: str, new: str) -> str:
    """old 가 꼭 한 번 나올 때만 new 로(아니면 선언 밖 — ValueError)."""
    if text.count(old) != 1:
        raise ValueError(f"선언 밖: {old!r} 가 {text.count(old)}번")
    return text.replace(old, new)


def _with_text(blocks: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    (block,) = blocks  # 요청 몸의 system·user 는 블록 목록(text·…) — 이 흐름은 늘 하나
    return [{**block, "text": text}]


def undeclared(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """요청 몸 하나에서 선언한 바뀜(RPS2 — 글 판 @3)을 되돌린 값과 그 갈래(map·draft). 선언 밖이면 ValueError."""
    from esgapi.drafting.engines.v2.texts import DEFAULT_TEXTS

    ((system_block,), _) = body["system"], body["user"]
    system = system_block["text"]
    if system == DEFAULT_TEXTS.map_system:
        return "map", body
    back = _once(system, "\n" + TABLE_LINE_RPS2, "")
    if "[자료 표지]" not in back:
        raise ValueError(f"선언 밖 system: {system[:40]!r}")
    return "draft", {**body, "system": _with_text(body["system"], back)}


def compare(base: Path, new: Path) -> int:
    """선언 지문: 경우마다 호출 수·칸마다 견줌. 끝 줄 FINGERPRINT=declared|differs."""
    bad = 0
    for case in CASES:
        before, after = (json.loads((root / f"{case}.json").read_text(encoding="utf-8")) for root in (base, new))
        same = len(before) == len(after)
        seen = {"map": 0, "draft": 0}
        fields: set[str] = set()
        for old, body in zip(before, after, strict=False):
            kind, undone = undeclared(body)
            seen[kind] += 1
            fields |= {key for key in {*old, *undone} if old.get(key) != undone.get(key)}
        ok = same and not fields and seen["map"] > 0 and seen["draft"] > 0
        counts = f"map {seen['map']} · draft {seen['draft']}"
        print(f"{case}: 호출 {len(before)}→{len(after)} · {counts} · 다른 칸 {sorted(fields)}")
        bad += 0 if ok else 1
    print(f"FINGERPRINT={'declared' if bad == 0 else 'differs'}")
    return 1 if bad else 0


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["--compare"]:
        sys.exit(compare(Path(args[1]), Path(args[2])))
    dump = Path(args[1]) if args[:1] == ["--dump"] else None
    if dump is not None:
        dump.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        for key, value in fingerprint(case, dump).items():
            print(f"{case} {key} {value}")


if __name__ == "__main__":
    main()
