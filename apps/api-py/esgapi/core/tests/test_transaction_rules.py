"""트랜잭션의 자리 규칙(EDK 리뉴얼 꼴, 밴드 E1b). 순수 층: 소스를 AST 로만 본다(돌리지 않는다).

    쓰기는 service 의 블록 안 · 여러 표는 actions 의 @transaction.atomic · on_commit 은 블록 안 · 바깥 호출은 블록 밖
    · 요청마다의 트랜잭션 없음

「블록」 = 같은 함수 안의 `with transaction.atomic(…)` 의 몸, 또는 `@transaction.atomic`·`@transaction.atomic(…)` 으로
꾸민 함수의 몸. 블록 안에서만 불리는 `_` 도우미의 몸도 블록 안으로 친다(되짚어 가며).
대상 A = 쓰는 층(`*/service/services`·`*/admin/services`·`*/service/actions` 의 파일),
대상 B = 제품 전부(tests·migrations 밖).

★ 허용 목록 두 줄: 워커 서비스(`jobs.py` — 부르는 쪽의 durable 블록 안에서만 돈다. 함수가 in_atomic_block 을 보고
  던진다)와 두 표에 쓰는 `confirm_upload`. 옛 분해 일감 길은 그대로 둔다(MARC-ENT-349) — 데이터 검증 서버 밴드가
  걷는다(sid:MARC-ISSUE-233).

무효 조건(이 검사가 못 보는 것): 다른 이름에 담은 매니저·메서드(`save = row.save; save()`), 날 SQL, dict 의 `.update(`·
`.get(` 와의 혼동(그래서 저장소 `get` 은 바깥 호출 목록에 없다 — 구멍), 블록이 **옳은 범위**를 감싸는가(업무·보안 층),
블록이 진짜로 커밋하는가(보안 층), 다른 파일의 함수를 거친 바깥 호출(블록 안에서 바깥 호출을 품은 함수를 부르는 것).
"""

import ast
from pathlib import Path

import pytest

ESGAPI = Path(__file__).resolve().parents[2]
WRITES = frozenset(
    {"create", "update", "save", "delete", "bulk_create", "bulk_update", "update_or_create", "get_or_create"}
)
OUTSIDE_CALLS = frozenset(
    {
        "head",
        "parse",
        "call",
        "call_tools",
        "enqueue_job",
        "send_task",
        "delay",
        "apply_async",
        "send_email",
        "urlopen",
        "classify_group",
        # X1b-1: 실행기의 큐 넣기·저장소 쓰기·흐름 돌리기
        "enqueue_run",
        "put",
        "run_flow",
        # X1b-2a: 올림 확인의 PDF 재기(자식 프로세스 — 포트 PdfProbe 의 메서드)
        "probe",
        # RM1b: 구획 쪽지 넣기·구획 돌리기·구획 계획 다시 셈
        "enqueue_segment",
        "run_segment",
        "plan_segments",
    }
)
MODEL_ROOTS = frozenset({"for_company", "objects", "unscoped"})
# X1 이 지운다: 부르는 쪽(워커)의 durable 블록 안에서만 도는 서비스. 지킴이(in_atomic_block 을 보고 던짐)를 품어야 한다.
WORKER_SERVICES = frozenset({"runs/service/services/jobs.py", "runs/service/services/runs.py"})
# 한 블록에서 두 표(DocumentRow·JobRow)에 쓴다. 데이터 검증 서버 밴드가 걷는다(sid:MARC-ISSUE-233, MARC-ENT-349).
TWO_TABLE_FUNCTIONS = frozenset(
    {
        ("core/service/services/documents.py", "confirm_upload"),
        # RP2a ①: 산출물·uses 를 한 블록에서 넣는다(INSERT 마다 세이브포인트 — 결정 MARC-ENT-514 의 8)
        ("core/documents/services.py", "ensure_artifact"),
    }
)
# 블록 안에서 저장소 put 을 하는 함수(RX1a — 운영자 명령 import_runs 의 다 아니면 0: 행을 다 넣은 뒤 같은 블록
# 끝에서 바이트를 올리고, 실패하면 행이 되돌려지고 올린 키는 --orphans-out 으로 나간다. Q7, MARC-ENT-440).
# 요청·워커 경로가 아니다.
PUT_IN_BLOCK_FUNCTIONS = frozenset({("runbundle/service/actions/import_.py", "_put_all")})

type Function = ast.FunctionDef | ast.AsyncFunctionDef


def target_files() -> list[Path]:
    found = [
        *ESGAPI.glob("*/service/services/*.py"),
        *ESGAPI.glob("*/admin/services/*.py"),
        *ESGAPI.glob("*/service/actions/*.py"),
        *ESGAPI.glob("core/documents/services.py"),  # RP2a ① 문서 산출물의 짓는 길
    ]
    return sorted(path for path in found if path.name != "__init__.py")


def product_files() -> list[Path]:
    return sorted(path for path in ESGAPI.rglob("*.py") if "tests" not in path.parts and "migrations" not in path.parts)


def relative(path: Path) -> str:
    return path.relative_to(ESGAPI).as_posix()


def _is_atomic(node: ast.expr) -> bool:
    """`transaction.atomic` 이나 `transaction.atomic(…)` 인가."""
    target = node.func if isinstance(node, ast.Call) else node
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "atomic"
        and isinstance(target.value, ast.Name)
        and target.value.id == "transaction"
    )


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _model_of(call: ast.Call) -> str | None:
    """쓰는 호출의 사슬 뿌리 모델 이름(`<Name>.for_company(…)`·`<Name>.objects`·
    `<Name>.unscoped`). 아니면 None."""
    node: ast.expr = call.func
    last_attr: str | None = None
    while True:
        if isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Attribute):
            last_attr = node.attr
            node = node.value
        elif isinstance(node, ast.Subscript):
            node = node.value
        else:
            break
    if isinstance(node, ast.Name) and last_attr in MODEL_ROOTS:
        return node.id
    return None


class Tree:
    def __init__(self, source: str) -> None:
        self.tree = ast.parse(source)
        self.parent: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node

    def calls(self) -> list[ast.Call]:
        return [node for node in ast.walk(self.tree) if isinstance(node, ast.Call)]

    def functions(self) -> list[Function]:
        return [node for node in ast.walk(self.tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]

    def in_block(self, node: ast.AST) -> bool:
        """같은 함수 안의 `with transaction.atomic(…)` 의 몸(항목 자리는 몸이 아니다)이거나, 꾸민 함수의 몸인가."""
        child = node
        while child in self.parent:
            above = self.parent[child]
            if isinstance(above, ast.Lambda):
                return False
            if isinstance(above, ast.FunctionDef | ast.AsyncFunctionDef):
                return child in above.body and any(_is_atomic(d) for d in above.decorator_list)
            if (
                isinstance(above, ast.With | ast.AsyncWith)
                and child in above.body
                and any(_is_atomic(item.context_expr) for item in above.items)
            ):
                return True
            child = above
        return False

    def function_of(self, node: ast.AST) -> Function | None:
        child = node
        while child in self.parent:
            child = self.parent[child]
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                return child
        return None

    def only_called_in_blocks(self, function: Function, seen: frozenset[str] = frozenset()) -> bool:
        """`_` 로 시작하고, 이 파일에서 그 함수를 부르는 자리가 하나 이상이며 전부 블록 안(되짚어 가며)인가."""
        if not function.name.startswith("_") or function.name in seen:
            return False
        sites = [c for c in self.calls() if isinstance(c.func, ast.Name) and c.func.id == function.name]
        return bool(sites) and all(self.protected(site, seen | {function.name}) for site in sites)

    def protected(self, node: ast.AST, seen: frozenset[str] = frozenset()) -> bool:
        if self.in_block(node):
            return True
        function = self.function_of(node)
        return function is not None and self.only_called_in_blocks(function, seen)

    def writes(self) -> list[ast.Call]:
        return [c for c in self.calls() if isinstance(c.func, ast.Attribute) and c.func.attr in WRITES]


def unprotected_writes(source: str) -> list[str]:
    tree = Tree(source)
    return [f"{call.lineno}:{_called_name(call)}" for call in tree.writes() if not tree.protected(call)]


def has_worker_guard(source: str) -> bool:
    """`if not connection.in_atomic_block: raise …` 꼴의 지킴이가 있는가."""
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.If)
            and any(isinstance(s, ast.Raise) for s in node.body)
            and any(isinstance(n, ast.Attribute) and n.attr == "in_atomic_block" for n in ast.walk(node.test))
        ):
            return True
    return False


def two_table_writers(source: str, *, action: bool = False, exempt_helpers: bool = True) -> dict[str, list[str]]:
    """서로 다른 모델 둘 이상에 쓰는 함수 → 그 모델들. 여러 표의 자리는 actions 파일의 `@transaction.atomic` 함수다
    (그것은 걸지 않는다). 면제 (b): 블록 안에서만 불리는 `_` 도우미(그 블록 하나가 여러 표를 묶는다).
    """
    tree = Tree(source)
    by_function: dict[Function, set[str]] = {}
    for call in tree.writes():
        model = _model_of(call)
        function = tree.function_of(call)
        if model is not None and function is not None:
            by_function.setdefault(function, set()).add(model)
    return {
        function.name: sorted(models)
        for function, models in by_function.items()
        if len(models) >= 2
        and not (action and any(_is_atomic(d) for d in function.decorator_list))
        and not (exempt_helpers and tree.only_called_in_blocks(function))
    }


def _outermost_block(tree: Tree, node: ast.AST) -> ast.AST | None:
    """그 마디를 감싼 같은 함수 안의 가장 바깥 블록(`with transaction.atomic(…)` 이나 꾸민 함수). 없으면 None."""
    found: ast.AST | None = None
    child = node
    while child in tree.parent:
        above = tree.parent[child]
        if isinstance(above, ast.Lambda):
            return found
        if isinstance(above, ast.FunctionDef | ast.AsyncFunctionDef):
            return above if child in above.body and any(_is_atomic(d) for d in above.decorator_list) else found
        if (
            isinstance(above, ast.With | ast.AsyncWith)
            and child in above.body
            and any(_is_atomic(item.context_expr) for item in above.items)
        ):
            found = above
        child = above
    return found


def split_block_writers(source: str) -> list[str]:
    """쓰기가 서로 다른 블록 둘 이상에 나뉜 함수(한 일을 트랜잭션 둘로 쪼갠 꼴 — K2a 검증 권고 5).
    두 표의 허용 함수(TWO_TABLE_FUNCTIONS)를 블록 둘로 쪼개도 two_table_writers 는 이름만 보아 지나간다 —
    이것이 문다."""
    tree = Tree(source)
    blocks: dict[Function, set[ast.AST]] = {}
    for call in tree.writes():
        function = tree.function_of(call)
        block = _outermost_block(tree, call)
        if function is not None and block is not None:
            blocks.setdefault(function, set()).add(block)
    return sorted(function.name for function, found in blocks.items() if len(found) >= 2)


def helpers_exempted_from_the_two_table_rule(source: str) -> list[str]:
    with_exemption = two_table_writers(source)
    return sorted(name for name in two_table_writers(source, exempt_helpers=False) if name not in with_exemption)


def hooks(source: str) -> tuple[int, list[int]]:
    """(`transaction.on_commit(` 의 수, 그 가운데 블록 밖의 줄)."""
    tree = Tree(source)
    found = [c for c in tree.calls() if isinstance(c.func, ast.Attribute) and c.func.attr == "on_commit"]
    return len(found), [call.lineno for call in found if not tree.in_block(call)]


def outside_calls(source: str) -> tuple[list[str], list[str]]:
    """바깥 호출 이름의 (블록 안 자리, 블록 밖 자리) — `<줄>:<이름>`.

    블록 안에서만 불리는 `_` 도우미의 몸도 「안」이다(쓰기 규칙과 같은 되짚기).
    """
    tree = Tree(source)
    inside: list[str] = []
    outside: list[str] = []
    for call in tree.calls():
        name = _called_name(call)
        if name in OUTSIDE_CALLS:
            (inside if tree.protected(call) else outside).append(f"{call.lineno}:{name}")
    return inside, outside


def puts_in_named_functions(source: str, name: str) -> set[str]:
    """PUT_IN_BLOCK_FUNCTIONS 의 함수 몸 안 put 부름 가운데 블록 안인 것(`<줄>:put`). 그 밖의 함수·이름은 빈 집합."""
    functions = {function for path, function in PUT_IN_BLOCK_FUNCTIONS if path == name}
    if not functions:
        return set()
    tree = Tree(source)
    return {
        f"{call.lineno}:put"
        for call in tree.calls()
        if _called_name(call) == "put"
        and (function := tree.function_of(call)) is not None
        and function.name in functions
        and tree.protected(call)
    }


def undecorated_writing_actions(source: str) -> list[str]:
    """쓰기 호출을 품은 공개 함수가 `@transaction.atomic` 으로 꾸며져 있지 않으면 그 이름."""
    tree = Tree(source)
    found: list[str] = []
    for function in tree.functions():
        if function.name.startswith("_") or any(_is_atomic(d) for d in function.decorator_list):
            continue
        if any(tree.function_of(call) is function for call in tree.writes()):
            found.append(function.name)
    return found


def problems(source: str, *, action: bool = False) -> list[str]:
    """한 파일의 규칙 위반 전부(자기 시험이 쓴다)."""
    total, outside_hooks = hooks(source)
    found = [f"쓰기 {w}" for w in unprotected_writes(source)]
    found += [f"두 표 {name}" for name in two_table_writers(source, action=action)]
    found += [f"블록 밖 on_commit {line}" for line in outside_hooks] if total else []
    found += [f"블록 안 바깥 호출 {c}" for c in outside_calls(source)[0]]
    found += [f"꾸밈 없는 action {name}" for name in undecorated_writing_actions(source)] if action else []
    return found


@pytest.mark.parametrize("path", target_files(), ids=relative)
def test_every_write_sits_inside_a_block(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if relative(path) in WORKER_SERVICES:
        # 허용된 파일은 그 일을 실제로 한다: 블록 밖에서 불리면 던지는 지킴이가 있고, 쓰기가 있다(빈 허용 금지).
        assert has_worker_guard(source)
        assert unprotected_writes(source) != []
        return
    assert unprotected_writes(source) == []


def test_a_function_that_writes_two_tables_is_named() -> None:
    files = target_files()
    assert len(files) == 83, [
        relative(path) for path in files
    ]  # 분모(K2a: user 의 services/login.py·actions/password.py · UA1: actions/account.py · AU1a: services/audit.py ·
    # X1b-1: runs 의 services/runs.py·actions/runs.py · G1b: greenwash 의 services/review.py·actions/{review,checks}.py)
    # G2c2: greenwash 의 services/ai_settings.py(② 에서 actions/ai_settings.py 하나 더)
    # X1b-2b: runs 의 services/resume.py(이어 돌기의 파일 옮김 — 실행기 _plan 이 부른다(RC1), 쓰기 0)
    # G1b-2a: greenwash 의 actions/report.py
    # TR2: translation 의 actions/retry_source.py(앞 실행 읽기 — 쓰기 0)
    # TR2 +1: translation 의 actions/result.py(결과 읽기 — 쓰기 0)
    # RF1 +1: runs 의 services/files.py(출력 파일 바이트 읽기 — 저장소만, 쓰기 0)
    # TR4 +2: translation 의 services/ai_settings.py·actions/ai_settings.py
    # DV1e +1: dataverify 의 actions/result.py(결과 읽기 — 쓰기 0)
    # TR3a +1: translation 의 actions/glossary.py(용어집 엑셀 읽기·양식 — 상태 없음, 쓰기 0)
    # TR3b +1: translation 의 actions/batches.py(묶음 목록·하나 보기 — 쓰기 0) · ③ +1: actions/archive.py(zip — 쓰기 0)
    # DV1g +1: dataverify 의 actions/runs.py(실행 목록 — 쓰기 0)
    # IR3b +1: materiality 의 actions/result.py(결과 읽기 — 쓰기 0)
    # DVA1 +2: dataverify 의 services/ai_settings.py·actions/ai_settings.py
    # IR3c +1: materiality 의 actions/runs.py(실행 목록 — 쓰기 0)
    # TRP6 +1: translation 의 actions/pages.py(문서 쪽 수 — 쓰기 0)
    # TRS3 +1: translation 의 actions/layout.py(읽기 — 쓰기 0)
    # RX1a ① +2: core 의 services/llm_logs.py · runs 의 services/bundle.py(실행 묶음 넣기 — 표마다 함수 하나)
    # RX1a ② +3: runbundle 의 actions/{_pg,export,import_}.py(모델을 부르지 않는다 — selectors·services 로만)
    # IRW2 +1: materiality 의 actions/value_chain.py(가치사슬 엑셀 읽기 — 상태 없음, 쓰기 0)
    # IR4 +2: materiality 의 services/ai_settings.py·actions/ai_settings.py
    # RX1b +2: greenwash·translation 의 actions/bundle.py(실행 묶음 carrier — 쓰기는 services 로만)
    # K1b-1 ① +1: organization 의 services/branches.py(본사 세우기 — 표 하나, ② 에서 actions/branches.py 하나 더)
    # K1b-1 ② +2: organization 의 actions/branches.py(표마다 services 를 부름) · services/facility_codes.py(표 하나)
    # K1b-2a ② +2: inventory 의 services/ghg_pool.py(표마다 함수 하나) · actions/ghg_pool.py(표마다 services 를 부름)
    # HD1 ② +1: runbundle 의 actions/_common.py(공용 조각 — 모델 메타·마이그레이션 그래프·회사 있음, 쓰기 0)
    # K1b-2b ② +2: inventory 의 services/index_selection.py·actions/index_selection.py
    # GRJ1 +1: greenwash 의 actions/rejudge.py(재판단 만들기 — create_run + 문장 행 붙이기)
    # S12a ② +2: inventory 의 services/entries.py(표마다 함수 하나)·actions/entries.py(표마다 services 를 부름)
    # DVX1 +1: dataverify 의 actions/edk.py(EDK 엑셀 읽기·양식 — 상태 없음, 쓰기 0)
    # RP1 ① +1: drafting 의 services/projects.py(표마다 함수 하나 — 목차 판의 셋은 put_outline 블록 안 `_` 도우미)
    # RP1 ② +1: drafting 의 actions/run_sources.py(실행기 포트 몸 — 읽기만, 쓰기 0)
    # RP1 ③ +2: drafting 의 actions/projects.py(목차 판 묶음 — 쓰기는 services 를 부름)·actions/result.py(읽기만)
    # RP2a ① +1: core 의 documents/services.py(산출물·uses 두 표 — TWO_TABLE_FUNCTIONS 의 ensure_artifact)
    # RP2d +1: drafting 의 actions/download.py(결과 docx — 쓰기 0, 짓기는 outputs/docx.py)
    # RP2c +1: drafting 의 actions/changes.py(목차 차이 — 읽기만, 쓰기 0)
    # RPA1 +2: drafting 의 services/ai_settings.py·actions/ai_settings.py
    # RPS1 +1: drafting 의 actions/runs.py(읽기만, 쓰기 0)
    # S3K1 +1: inventory 의 actions/scope3_runs.py(결과 읽기·양식 — 쓰기 0)
    # S12a-3 ① +1: inventory 의 actions/dashboard.py(대시보드 읽기 — 쓰기 0)
    # S12b-1 ② +1: inventory 의 actions/scope12_excel.py(엑셀 내려받기 둘 — 읽기만, 쓰기 0)
    # S3D1 ① +1: inventory 의 actions/scope3_excel.py(Scope 3 데이터 엑셀 — 읽기만, 쓰기 0)
    # S12b-2 ② +1: inventory 의 actions/scope12_upload.py(올리기 — 쓰기는 entries.save_rows 뿐)
    # S3K2a ① +2: inventory 의 services/scope3_state.py(표 하나 — 빈 행·잠금·풀기)·actions/scope3_state.py
    # IRS3 ① +1: materiality 의 services/edits.py(표마다 함수 하나 — ② 에서 actions/edits.py 하나 더)
    # IRS3 ② +1: materiality 의 actions/edits.py(@transaction.atomic — 쓰기는 services 를 부름)
    # IRS3 ③ +1: materiality 의 actions/report.py(고친 판 엑셀 — 쓰기는 감사 record_event 하나)
    # S3K2b-1 ① +2: inventory 의 services/scope3_edits.py·actions/scope3_edits.py(줄 편집 사건 — 표 하나)
    # GE1b ③ +1: greenwash 의 actions/engine_g1.py(2차 엔진 문서 포트 — 쓰기는 core 짓는 길만, 블록 0)
    named: set[tuple[str, str]] = set()
    exempted: set[tuple[str, str]] = set()
    for path in files:
        if relative(path) in WORKER_SERVICES:
            continue
        source = path.read_text(encoding="utf-8")
        action = "/service/actions/" in relative(path)
        named |= {(relative(path), name) for name in two_table_writers(source, action=action)}
        exempted |= {(relative(path), name) for name in helpers_exempted_from_the_two_table_rule(source)}
    assert named == TWO_TABLE_FUNCTIONS
    # 분모: 허용한 함수가 실제로 두 표에 쓴다.
    documents = (ESGAPI / "core/service/services/documents.py").read_text(encoding="utf-8")
    assert two_table_writers(documents)["confirm_upload"] == ["DocumentRow", "JobRow"]
    # 면제 (b) 로 지나가는 것은 정확히 이 둘이다(둘 다 import_factors 의 블록 안에서만 불린다).
    assert exempted == {
        ("reference/admin/services/importer.py", "_flush"),
        ("reference/admin/services/importer.py", "_import_mapping"),
    }


def test_after_commit_work_is_registered_inside_a_block() -> None:
    counted = {relative(path): hooks(path.read_text(encoding="utf-8")) for path in product_files()}
    assert sum(total for total, _ in counted.values()) == 2  # 분모: 올림 확인의 하나 + 실행 만들기의 하나
    assert counted["core/service/services/documents.py"][0] == 1
    assert counted["runs/service/actions/runs.py"][0] == 1
    assert {name: outside for name, (_, outside) in counted.items() if outside} == {}


def test_no_outside_call_inside_a_block() -> None:
    inside: list[str] = []
    outside: set[str] = set()
    allowed_puts = 0
    for path in product_files():
        source = path.read_text(encoding="utf-8")
        found_inside, found_outside = outside_calls(source)
        exempt = puts_in_named_functions(source, relative(path))
        allowed_puts += len(exempt)
        inside += [f"{relative(path)}:{c}" for c in found_inside if c not in exempt]
        outside |= {f"{relative(path)}:{c.split(':')[1]}" for c in found_outside}
    assert inside == []
    assert allowed_puts == len(PUT_IN_BLOCK_FUNCTIONS) == 1  # 분모: 이름 붙은 함수가 실제로 블록 안 put 을 품는다
    # 분모: 블록 밖에서 바깥 호출이 실제로 보인다(검사가 그 이름을 문다).
    assert outside >= {
        "core/service/services/documents.py:head",
        # Scope 3 분류 호출(밴드 CU1 이 업무 층에서 classify_group 으로 옮김)
        "inventory/engines/scope3/llm_first_1/pipeline.py:call",
        "inventory/service/services/inventory.py:classify_group",  # 업무 층의 Scope 3 분류(그 안에서 call)
        "runs/management/commands/requeue_jobs.py:enqueue_job",
        # X1b-1: 실행기의 흐름 돌리기와 실행 다시 넣기(둘 다 블록 밖)
        "runs/tasks.py:run_flow",
        "runs/management/commands/requeue_runs.py:enqueue_run",
    }


def test_worker_services_make_no_outside_call() -> None:
    """워커 서비스(WORKER_SERVICES)는 꾸밈 없이 부르는 쪽(태스크)의 durable 블록 안에서만 돈다 — in_block 은 같은 함수
    안의 블록만 보므로 그 몸 안의 바깥 호출을 못 본다. 그래서 그 파일에는 바깥 호출 이름의 부름이 어디에도 0 이다
    (블록 안팎·안쪽 함수 모두 — X1b-1, 발주서 개정 5 F2)."""
    found: dict[str, list[str]] = {}
    read = 0
    for name in sorted(WORKER_SERVICES):
        tree = ast.parse((ESGAPI / name).read_text(encoding="utf-8"))
        read += 1
        calls = [
            f"{node.lineno}:{_called_name(node)}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and _called_name(node) in OUTSIDE_CALLS
        ]
        if calls:
            found[name] = calls
    assert found == {}
    assert read == len(WORKER_SERVICES) == 2  # 분모: 읽은 파일 수


def test_no_request_wide_transaction() -> None:
    middleware = ast.parse((ESGAPI / "core/tenancy/middleware.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(middleware) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(middleware) if isinstance(n, ast.Attribute)}
    names |= {a.asname or a.name for n in ast.walk(middleware) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "get_response" in names  # 분모
    assert names & {"transaction", "atomic", "set_rollback"} == set()

    settings = ast.parse((ESGAPI / "config/settings/base.py").read_text(encoding="utf-8"))
    atomic_requests = [
        value
        for node in ast.walk(settings)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == "ATOMIC_REQUESTS"
    ]
    assert len(atomic_requests) == 1
    assert isinstance(atomic_requests[0], ast.Constant) and atomic_requests[0].value is False

    durable: dict[str, int] = {}
    for path in product_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.keyword)
                and node.arg == "durable"
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
            ):
                durable[relative(path)] = durable.get(relative(path), 0) + 1
    assert durable == {
        "reconcile/tasks.py": 2,
        "runs/management/commands/requeue_jobs.py": 1,
        # X1b-1: 실행기의 잡기·끝내기·사건 셋(단계 시작·체크포인트·단계 끝남) + 실행 다시 넣기
        # RM1a: 구획 사건 넷(계획·구획 시작·끝·실패)
        # RM1b: 구획 쪽지 잡기·끝냄
        "runs/tasks.py": 11,
        "runs/management/commands/requeue_runs.py": 1,
        # RX1a: 실행 묶음의 내보내기 스냅숏 블록 · 넣기 블록(잠금 → 행 → put → etag → 커밋)
        "runbundle/service/actions/export.py": 1,
        "runbundle/service/actions/import_.py": 1,
    }  # 셈 3 → 9 → 11 → 15(RM1a +4)


def test_no_function_splits_its_writes_across_two_blocks() -> None:
    files = target_files()
    assert {
        relative(path): found for path in files if (found := split_block_writers(path.read_text(encoding="utf-8")))
    } == {}
    # 분모: 블록 안의 쓰기가 실제로 보인다(블록 하나의 함수들)
    documents = (ESGAPI / "core/service/services/documents.py").read_text(encoding="utf-8")
    assert unprotected_writes(documents) == [] and Tree(documents).writes()
    # 자기 시험: 두 표 함수를 블록 둘로 쪼갠 꼴 · 꾸민 함수 안의 with 는 한 블록 · 블록 하나에 쓰기 둘은 지난다
    split = (
        "def confirm_upload(d):\n"
        "    with transaction.atomic():\n        DocumentRow.for_company(c).filter(pk=d).update(status='u')\n"
        "    with transaction.atomic():\n        JobRow.for_company(c).create(document_id=d)\n"
    )
    assert split_block_writers(split) == ["confirm_upload"]
    assert two_table_writers(split) == {"confirm_upload": ["DocumentRow", "JobRow"]}  # 이름은 허용 목록이 받는다
    nested = (
        "@transaction.atomic\ndef reset(r):\n    r.save()\n"
        "    with transaction.atomic():\n        R.of_user(1).update(x=1)\n"
    )
    assert split_block_writers(nested) == []
    one = "def f():\n    with transaction.atomic():\n        a.save()\n        b.save()\n"
    assert split_block_writers(one) == []


def test_actions_that_write_open_one_transaction() -> None:
    actions = [path for path in target_files() if "/service/actions/" in relative(path)]
    assert len(actions) >= 1  # 분모: 읽은 actions 파일(지금 쓰는 것은 0 — 자기 시험이 받친다)
    assert {
        relative(path): found
        for path in actions
        if (found := undecorated_writing_actions(path.read_text(encoding="utf-8")))
    } == {}


# (소스, actions 파일인가). actions 파일만 「공개 함수의 쓰기는 꾸밈」 규칙을 더 본다.
GOOD = [
    # 블록 안의 쓰기
    ("def f():\n    with transaction.atomic():\n        X.objects.create()\n", False),
    # @transaction.atomic 으로 꾸민 action 이 두 표에 쓴다
    ("@transaction.atomic\ndef act(t):\n    X.for_company(t).create()\n    Y.for_company(t).create()\n", True),
    # 블록 밖의 head 뒤에 블록
    ("def f(s):\n    h = s.head('k')\n    with transaction.atomic():\n        X.objects.filter().update(e=h)\n", False),
    # 블록 안의 on_commit
    ("def f():\n    with transaction.atomic():\n        X.objects.create()\n        transaction.on_commit(g)\n", False),
]
BAD = [
    # 블록 밖의 쓰기
    ("def f():\n    X.objects.create()\n", False),
    # 블록 밖에서도 불리는 도우미
    ("def _w(g):\n    g.save()\n\ndef f():\n    with transaction.atomic():\n        _w(1)\n    _w(2)\n", False),
    # 블록 밖의 on_commit
    ("def f():\n    with transaction.atomic():\n        pass\n    transaction.on_commit(g)\n", False),
    # 블록 안의 LLM 호출
    ("def f(client, r):\n    with transaction.atomic():\n        client.call(r)\n", False),
    # 블록 안의 저장소 head
    ("def f(storage):\n    with transaction.atomic():\n        storage.head('k')\n", False),
    # 블록 안의 큐 넣기
    ("def f():\n    with transaction.atomic():\n        enqueue_job(tenant_id='t', job_id='j', kind='parse')\n", False),
    # 한 함수가 두 모델에 쓴다
    (
        "def f(t):\n    with transaction.atomic():\n        X.for_company(t).create()\n        Y.objects.create()\n",
        False,
    ),
    # 꾸밈 없는 쓰는 action
    ("def act(t):\n    X.for_company(t).create()\n", True),
    # 꾸민 action 안의 LLM 호출
    ("@transaction.atomic(using='default')\ndef act(client, r):\n    client.call(r)\n", True),
    # 쓰기는 안쪽 블록 안이지만 action 자체는 꾸밈이 없다(꾸밈 규칙만 문다)
    ("def act(t):\n    with transaction.atomic():\n        X.for_company(t).create()\n", True),
    # 블록 안에서만 불리는 도우미가 바깥 호출을 품는다
    ("def _h(s):\n    return s.head('k')\n\ndef f(s):\n    with transaction.atomic():\n        _h(s)\n", False),
    # 블록 안의 도구 호출 고리
    ("def f(client, r, ex):\n    with transaction.atomic():\n        client.call_tools(r, ex)\n", False),
]
# BAD 의 차례대로, 그 소스가 걸려야 하는 규칙(problems 의 글 머리).
BAD_RULES = [
    "쓰기",
    "쓰기",
    "블록 밖 on_commit",
    "블록 안 바깥 호출",
    "블록 안 바깥 호출",
    "블록 안 바깥 호출",
    "두 표",
    "꾸밈 없는 action",
    "블록 안 바깥 호출",
    "꾸밈 없는 action",
    "블록 안 바깥 호출",
    "블록 안 바깥 호출",
]


def test_the_checker_catches_what_it_should() -> None:
    assert [problems(source, action=action) for source, action in GOOD] == [[], [], [], []]
    found = [problems(source, action=action) for source, action in BAD]
    assert len(found) == len(BAD_RULES)
    # 각 소스가 「제 규칙」으로 걸린다(다른 규칙이 대신 빨갛게 해서 지나가는 일을 막는다).
    assert [
        any(p.startswith(rule) for p in problems_of) for problems_of, rule in zip(found, BAD_RULES, strict=True)
    ] == [True] * len(BAD_RULES), found
    assert problems(BAD[9][0], action=True) == ["꾸밈 없는 action act"]  # 꾸밈 규칙 홀로
    # 면제 (b) 를 빼고 돌리면 기준의 두 도우미가 걸린다(면제가 없으면 importer 가 빨갛다는 것).
    importer = (ESGAPI / "reference/admin/services/importer.py").read_text(encoding="utf-8")
    assert sorted(two_table_writers(importer, exempt_helpers=False)) == ["_flush", "_import_mapping"]
    assert two_table_writers(importer) == {}
    # 지킴이가 없는 파일은 지킴이가 없다고 답한다(P9 의 받침).
    assert not has_worker_guard(GOOD[0][0])
