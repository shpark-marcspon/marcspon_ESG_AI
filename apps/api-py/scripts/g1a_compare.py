"""밴드 G1a 의 대조 도구. esg-lab 을 import 하지 않는다 — 파일·JSON 만 읽는다.

    uv run python scripts/g1a_compare.py ast <GW1 폴더>            engines/e0/ 열 파일 ↔ GW1 의 같은 파일, 정규화한 AST
    uv run python scripts/g1a_compare.py ast-sha256 <GW1 폴더>     GW1 쪽 정규화 AST 의 sha256(파일마다 한 줄)
    uv run python scripts/g1a_compare.py mock <gw1.json> <flow.json>     대조 A: GW1 결과 ↔ greenwash.result@1
    uv run python scripts/g1a_compare.py dryrun <gw1.json> <flow.json>   대조 C: dry_run(GW1) ↔ dryRun(흐름) 칸

출력: 다른 것마다 `DIFF <자리>: …` 한 줄, 끝에 `SAME=<같은 수>/<견준 수>`. 다르면 종료 코드 1.

GW1 결과는 snake, 흐름 결과는 camelCase 다(GC3). GW1 쪽은 읽자마자 calls·messages 를 뗀 나머지를 제품의 경계
esgapi.greenwash.contracts.wire.result_to_wire 로 사상해서 견준다(두 번째 사상을 짓지 않는다). calls·messages 는
원값으로 견준다.
"""

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from esgapi.greenwash.contracts.wire import result_to_wire

FILES = (
    "heuristics",
    # "checker" 는 GL1(MARC-TICK-112)에서 이어 돌기 꼭지를 달아 GW1 과 다르다 — 고정 밖
    "prompts",
    "parts",
    "wordcount",
    "chunking",
    "retrieval",
    "dryrun",
    "pdftext",
    "ports",
)
CALC = Path(__file__).resolve().parents[1] / "esgapi" / "greenwash" / "engines" / "e0"
OURS = "esgapi.greenwash.engines.e0"


class _Normalize(ast.NodeTransformer):
    """import 의 모듈 이름: esgapi.greenwash.engines.e0.<x> → greenwash.<x>,
    esgapi.greenwash.engines.e0 → greenwash(정확히 같을 때만)."""

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        if node.module == OURS:
            node.module = "greenwash"
        elif node.module is not None and node.module.startswith(OURS + "."):
            node.module = "greenwash." + node.module.removeprefix(OURS + ".")
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        for alias in node.names:
            if alias.name == OURS or alias.name.startswith(OURS + "."):
                alias.name = "greenwash" + alias.name.removeprefix(OURS)
        return node


def normalized_dump(path: Path) -> str:
    tree = _Normalize().visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return ast.dump(tree, include_attributes=False)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cmd_ast(gw1: Path) -> int:
    same = 0
    for name in FILES:
        ours, theirs = normalized_dump(CALC / f"{name}.py"), normalized_dump(gw1 / f"{name}.py")
        if ours == theirs:
            same += 1
            print(f"same {name}.py {sha(theirs)}")
        else:
            print(f"DIFF {name}.py: 정규화 AST 가 다르다")
    print(f"SAME={same}/{len(FILES)}")
    return 0 if same == len(FILES) else 1


def cmd_ast_sha256(gw1: Path) -> int:
    for name in FILES:
        print(f"{name}.py {sha(normalized_dump(gw1 / f'{name}.py'))}")
    return 0


def load(path: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(Path(path).read_text(encoding="utf-8")))


class _Tally:
    def __init__(self) -> None:
        self.compared = 0
        self.diffs: list[str] = []

    def eq(self, where: str, a: object, b: object) -> None:
        self.compared += 1
        if a != b:
            left, right = json.dumps(a, ensure_ascii=False)[:200], json.dumps(b, ensure_ascii=False)[:200]
            self.diffs.append(f"DIFF {where}: GW1={left} 흐름={right}")

    def done(self) -> int:
        for line in self.diffs:
            print(line)
        print(f"SAME={self.compared - len(self.diffs)}/{self.compared}")
        return 0 if not self.diffs else 1


SHARED = ("source", "config", "models", "promptVersion", "parts", "pages", "candidateStats", "wordCounts")
UNMAPPED = ("calls", "messages")
"""GW1 결과에서 result_to_wire 를 걸지 않는 칸 — 원값으로 견준다."""
ITEM_KEYS = (
    "page",
    "parts",
    "sentence",
    "level",
    "riskTags",
    "confirmedInEvidence",
    "missingFields",
    "reasonBullets",
    "fixParagraph",
    "evidencePages",
    "evidenceInternal",
)


def gw1_wire(gw1: dict[str, Any]) -> dict[str, Any]:
    """GW1 결과(snake) → calls·messages 를 뗀 나머지를 result_to_wire 로 사상한 것."""
    return result_to_wire({k: v for k, v in gw1.items() if k not in UNMAPPED})


def cmd_mock(gw1_path: str, flow_path: str) -> int:
    """대조 A 의 칸 대응(발주서 §3-2). 제외: GW1 의 schema_version·provider·synthetic·calls,
    흐름의 schemaVersion·counts·report. dryRun·exampleSentence 는 null 임만, span ↔ position 은 둘 다 null."""
    raw, flow = load(gw1_path), load(flow_path)
    gw1 = gw1_wire(raw)
    t = _Tally()
    for key in SHARED:
        t.eq(key, gw1.get(key), flow.get(key))
    t.eq("items.length", len(gw1.get("items", [])), len(flow.get("items", [])))
    for i, (a, b) in enumerate(zip(gw1.get("items", []), flow.get("items", []), strict=False)):
        for key in ITEM_KEYS:
            t.eq(f"items[{i}].{key}", a.get(key), b.get(key))
        t.eq(f"items[{i}].span↔position", a.get("span"), b.get("position"))
        t.eq(f"items[{i}].exampleSentence", None, b.get("exampleSentence"))
    t.eq("dryRun", None, flow.get("dryRun"))
    t.eq("schemaVersion", "greenwash.result@1", flow.get("schemaVersion"))
    if "messages" in raw and "messages" in flow:  # 도움 코드가 덧붙인 메시지 해시 열(GW1 CLI 의 출력에는 없다)
        t.eq("messages", raw.get("messages"), flow.get("messages"))
    if "calls" in raw and "calls" in flow:
        t.eq("calls", raw["calls"], flow["calls"])
    return t.done()


def cmd_dryrun(gw1_path: str, flow_path: str) -> int:
    gw1, flow = gw1_wire(load(gw1_path)), load(flow_path)
    t = _Tally()
    raw_a, raw_b = gw1.get("dryRun"), flow.get("dryRun")
    if not isinstance(raw_a, dict) or not isinstance(raw_b, dict):
        t.eq("dryRun", cast("object", raw_a), cast("object", raw_b))
        return t.done()
    a, b = cast("dict[str, Any]", raw_a), cast("dict[str, Any]", raw_b)
    for key in sorted(set(a) | set(b)):
        t.eq(f"dryRun.{key}", a.get(key), b.get(key))
    text = json.dumps(a, ensure_ascii=False)
    if '"unmeasured"' in text:
        t.diffs.append("DIFF dryRun: 토큰을 못 쟀다(unmeasured) — 통과로 치지 않는다")
    return t.done()


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "ast":
        return cmd_ast(Path(argv[1]))
    if len(argv) >= 2 and argv[0] == "ast-sha256":
        return cmd_ast_sha256(Path(argv[1]))
    if len(argv) >= 3 and argv[0] == "mock":
        return cmd_mock(argv[1], argv[2])
    if len(argv) >= 3 and argv[0] == "dryrun":
        return cmd_dryrun(argv[1], argv[2])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
