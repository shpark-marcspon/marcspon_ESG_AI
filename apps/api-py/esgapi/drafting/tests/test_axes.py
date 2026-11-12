"""축(RP1 §3 S6, AST): engines ↛ django·pydantic·core·입출력·시계 · contracts ↛ engines ·
flows ↛ django·settings·service ·
drafting 전부 ↛ 다른 업무 모듈(greenwash·translation·materiality·dataverify·inventory·reconcile·reference·runbundle).
RP2a §3 S10: drafting 전부 ↛ pypdf(쪽 글은 core 문서 산출물) · tools/blocks_text ↛ django·core 의 DB 쪽(뷰·계약만).
RP2b B12: engines 안의 esgapi 는 engines/v2 → engines/v1 하나만(core·tools·계약·흐름 0).
RP2c B7: flows/reuse 는 순수 — esgapi 는 drafting.contracts 하나만(django·core·service·engines 0).
RPA1 B10: flows/prompt_model_v2 의 esgapi 는 core.calc·core.contracts·core.llm.config·engines(v1 pages·texts, v2
material·texts)·flows.draft_v2 만."""

import ast
from pathlib import Path

import pytest

D = Path(__file__).resolve().parents[1]
OTHERS = ("greenwash", "translation", "materiality", "dataverify", "inventory", "reconcile", "reference", "runbundle")


def imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def product(folder: str) -> list[Path]:
    return sorted(p for p in (D / folder).rglob("*.py") if "tests" not in p.parts)


def bad(paths: list[Path], words: tuple[str, ...]) -> list[str]:
    return [f"{p.name}: {m}" for p in paths for m in imports(p) if any(m == w or m.startswith(w + ".") for w in words)]


def test_engines_are_standard_library_only() -> None:
    words = ("django", "pydantic", "esgapi", "io", "os", "pathlib", "time", "datetime", "random", "socket", "pypdf")
    v1 = "esgapi.drafting.engines.v1"
    found = [line for line in bad(product("engines"), words) if not line.endswith(f": {v1}") and f": {v1}." not in line]
    assert len(product("engines")) >= 7 and found == []
    assert {p.name for p in product("engines/v2")} >= {"sentences.py", "material.py", "checks.py", "places.py"}
    assert bad(product("engines/v1"), ("esgapi.drafting.engines.v2",)) == []  # v1 ↛ v2


def test_contracts_do_not_import_engines_and_flows_know_no_django() -> None:
    assert bad(product("contracts"), ("esgapi.drafting.engines", "esgapi.drafting.flows")) == []
    words = ("django", "esgapi.core.conf", "esgapi.drafting.service", "esgapi.drafting.models")
    assert len(product("flows")) >= 3 and bad(product("flows") + product("tools"), words) == []


def test_b7_flows_reuse_knows_only_the_contracts() -> None:
    found = {m for m in imports(D / "flows/reuse.py") if m == "esgapi" or m.startswith("esgapi.")}
    assert found and {m for m in found if not m.startswith("esgapi.drafting.contracts")} == set()
    assert bad([D / "flows/reuse.py"], ("django", "pydantic", "ninja")) == []


@pytest.mark.parametrize("module", OTHERS)
def test_drafting_imports_no_other_business_module(module: str) -> None:
    every = sorted(p for p in D.rglob("*.py"))
    assert bad(every, (f"esgapi.{module}",)) == []


def test_s10_drafting_reads_no_pdf_itself_and_blocks_text_is_pure() -> None:
    every = sorted(p for p in D.rglob("*.py"))
    assert bad(every, ("pypdf",)) == []
    words = ("django", "esgapi.core.documents.selectors", "esgapi.core.documents.services", "esgapi.core.models")
    assert bad([D / "tools/blocks_text.py"], words) == []
    assert bad(product("flows"), words[1:]) == []


def test_the_checker_catches_a_planted_import(tmp_path: Path) -> None:
    planted = tmp_path / "x.py"
    planted.write_text("import django\nfrom esgapi.greenwash.tools import pdftext_pypdf\n", encoding="utf-8")
    assert bad([planted], ("django",)) and bad([planted], ("esgapi.greenwash",))


def test_b10_prompt_model_imports_only_its_seven() -> None:
    allowed = {
        "esgapi.core.calc.ai_settings",
        "esgapi.core.contracts.ai_setting_shapes",
        "esgapi.core.llm.config",
        "esgapi.drafting.engines.v1",
        "esgapi.drafting.engines.v1.texts",
        "esgapi.drafting.engines.v2",
        "esgapi.drafting.engines.v2.texts",
        "esgapi.drafting.flows",
    }
    found = {m for m in imports(D / "flows/prompt_model_v2.py") if m == "esgapi" or m.startswith("esgapi.")}
    assert found and found <= allowed, found - allowed
