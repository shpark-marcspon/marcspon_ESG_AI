"""`pipeline.run` 이 BASE 와 같은지 재는 지문(TR2 §3-1-5). 지어낸 문서 다섯(test_plan 의 흐름 넷 + 같은 번호
조각)을 모의 공급사로 돌려 `asdict(run(...))` 와 호출 열(자리·system·user·max_tokens·모델·경로)의 sha256 을 낸다.

`scripts/section4-TR2.sh` 가 이 파일을 BASE 트리(`git archive`)에 넣어 그쪽 엔진으로도 돌리고 두 지문을 견준다 —
이 파일은 BASE 에도 있는 것(support·test_plan)만 import 한다. TR2 가 조각에 더한 열쇠 `remaining_korean` 하나는
지문에서 빼고, 열쇠 길 집합(`keys`)을 따로 내 BASE 와의 차이가 그 하나뿐임을 견준다.

    uv run --frozen python -m esgapi.translation.tests.engines.colab_158.run_digest

밴드 TR3a(경로 셋이 openai 로 — MARC-ENT-402)가 더한 것: 호출 열에서 모델·경로를 뺀 지문 `callsText`(공급사와 무관한
몫 — BASE 와 같아야 한다)와 흐름 한 벌의 지문 `flow`(옵션 → 흐름 끝까지: 주 결과에서 settings.routes 를 뺀 sha256 과
Word 파일마다 이름·내용 지문). Word 바이트는 지은 시각을 싣는다(zip 항목 시각·docProps/core.xml) — 내용 지문은 zip
항목마다 (이름, 내용)이고 core.xml 의 시각만 가린다. 답은 공급사 둘 다에 같은 함수로 심는다(어느 쪽이 불리든 같은
답 — BASE 는 anthropic, 이쪽은 openai). `calls`(모델·경로 포함)는 경로가 바뀌어 BASE 와 다르다 — section4-TR3a.sh
가 그것만 다름을 본다.
"""

import dataclasses
import hashlib
import io
import json
import re
import sys
import zipfile
from typing import Any, cast

from esgapi.core.flows.run import run_flow as run_whole_flow
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import Completed, ProviderRequest, Usage
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.tests.engines.colab_158.support import client, make_input, ok, run_flow
from esgapi.translation.tests.engines.colab_158.test_plan import FLOWS
from esgapi.translation.tests.flows.support import binding, document, options

DUPLICATE = (
    "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다.\n[PAGE 1]\n[BLOCK 1]\n가상 다시\n"
    "[PAGE 2]\n[BLOCK 1]\nvirtual english only"
)
"""같은 번호 조각 둘 — 셀 52~67 이 경고(duplicate_pages)를 낸다(뒤 몸의 경고를 지문에 싣는 흐름)."""
CASES = {
    **{case: FLOWS[case] for case in ("a_b", "glossary_repair", "korean_left_w7", "table_fallback")},
    "duplicate_pages": (
        make_input(DUPLICATE),
        [ok("[BLOCK 1]\nVirtual title\nVirtual body."), ok("[BLOCK 1]\nVirtual again"), ok("[]"), ok("[]")],
    ),
}
ADDED = "remaining_korean"


def _paths(value: object, prefix: str, out: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in cast("dict[str, object]", value).items():
            path = f"{prefix}.{key}"
            out.add(path)
            _paths(item, path, out)
    elif isinstance(value, list | tuple):
        for item in cast("list[object]", value):
            _paths(item, f"{prefix}[]", out)


def _drop_added(run: dict[str, object]) -> dict[str, object]:
    for variant in cast("list[dict[str, list[dict[str, object]]]]", run["variants"]):
        for fragment in variant["fragments"]:
            fragment.pop(ADDED, None)
    return run


def digest() -> dict[str, object]:
    out: dict[str, object] = {}
    keys: set[str] = set()
    for case in CASES:
        inputs, replies = CASES[case]
        flow = run_flow(inputs, replies)
        run = dataclasses.asdict(flow.run)
        _paths(run, "run", keys)
        calls = [[c.site, c.system, c.user, c.max_tokens, c.model, c.route] for c in flow.calls]
        out[case] = {
            "run": _sha(_drop_added(run)),
            "calls": _sha(calls),
            "callsText": _sha([call[:4] for call in calls]),
        }
    out["keys"] = sorted(keys)
    out["flow"] = flow_digest()
    return out


FLOW_TEXT = "\n".join(
    f"[PAGE {n}]\n[BLOCK 1]\n가상 제목 {n}\n가상 본문입니다. 가상 설비를 점검합니다." for n in (1, 2, 3)
)
USAGE = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=0, cache_write_tokens=0)


def _answer(request: ProviderRequest) -> Completed:
    """검수면 이슈 하나(자동수정이 돌게), 그 밖이면 user 의 [BLOCK n] 줄 수만큼의 영문(지어낸 것)."""
    system = "".join(segment.text for segment in request.system)
    if system == prompts.QA_SYSTEM_PROMPT:
        issue = {"issue_type": "GRAMMAR", "severity": "LOW", "original_span": "", "suggestion": "x", "reason": "y"}
        return Completed(text=json.dumps([issue]), usage=USAGE)
    return Completed(text="[BLOCK 1]\nVirtual title\nVirtual body.", usage=USAGE)


def flow_digest() -> dict[str, object]:
    """옵션(A/B·자동수정 켬) → 흐름 끝까지. 주 결과(settings.routes 뺌)·Word 바이트의 지문."""
    providers = {"anthropic": MockProvider("anthropic"), "openai": MockProvider("openai")}
    for provider in providers.values():
        for _ in range(500):
            provider.enqueue(_answer)
    given = options(style={"compareAb": True, "single": "B"}, ceoPageLimit=None)
    inputs = binding(max_usd=100.0).inputs_with(document(FLOW_TEXT), given, company_id=1, versions={})
    ran = run_whole_flow(
        colab.FLOW,
        inputs,
        colab.TranslationAdapters(llm=client(providers), tenant="1", mock=False, spent_usd=lambda: 0.0),
    )
    result = cast("dict[str, Any]", ran.output.results[0])
    masked = {**result, "settings": {k: v for k, v in result["settings"].items() if k != "routes"}}
    return {
        "result": _sha(masked),
        "routes": result["settings"]["routes"],
        "files": [[f.name, _docx_sha(f.content)] for f in ran.output.files],
    }


def _docx_sha(content: bytes) -> str:
    """docx 의 내용 지문: zip 항목마다 (이름, sha256) — core.xml 의 dcterms 시각은 가린다."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        parts: list[list[str]] = []
        for info in archive.infolist():
            data = archive.read(info.filename)
            if info.filename == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:(created|modified)[^>]*>)[^<]*", rb"\1-", data)
            parts.append([info.filename, hashlib.sha256(data).hexdigest()])
    return _sha(parts)


def _sha(value: object) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, default=list)
    return hashlib.sha256(body.encode()).hexdigest()


if __name__ == "__main__":
    json.dump(digest(), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
