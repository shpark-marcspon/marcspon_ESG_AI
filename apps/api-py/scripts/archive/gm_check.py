"""밴드 GM(파이썬 코드를 가이드의 자리로 옮긴다. 동작 변화 0)의 기계 검사.

    사용(apps/api-py 에서): uv run --frozen python scripts/gm_check.py <검사> [--upto <0~8>]

검사 여섯: moves · others · imports · strings · new · places. 하나라도 어긋나면 그 줄을 찍고 종료 1.
`--upto n` 은 커밋 ⓝ 까지의 옮김만 「끝났어야 한다」고 보고, 뒤의 것은 「아직 옛 자리」여야 한다고 본다(기본 8).

기준 커밋의 내용은 `git show 3a0fa3a:<경로>` 로만 읽는다. 표준 라이브러리만 쓴다.
자리의 대응표(옮김 36 · 걷음 17 · 새 `__init__.py` 23)와 import 의 대응은 이 파일에 자료로 한 번만 적는다.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

BASE = "3a0fa3a"
PREFIX = "apps/api-py/"  # 저장소 뿌리에서 본 이 꾸러미의 자리
E = "esgapi/"

# (옛 경로, 새 경로, 커밋). esgapi/ 아래의 경로다.
MOVES: tuple[tuple[str, str, int], ...] = (
    ("core/adapters/__init__.py", "core/resources/__init__.py", 1),
    ("core/adapters/llm.py", "core/resources/llm.py", 1),
    ("core/adapters/parser.py", "core/resources/parser.py", 1),
    ("core/adapters/storage.py", "core/resources/storage.py", 1),
    ("core/ports/__init__.py", "core/resources/ports/__init__.py", 1),
    ("core/ports/llm.py", "core/resources/ports/llm.py", 1),
    ("core/ports/parser.py", "core/resources/ports/parser.py", 1),
    ("core/ports/storage.py", "core/resources/ports/storage.py", 1),
    ("core/api.py", "core/service/apis/documents.py", 2),
    ("core/documents/__init__.py", "core/service/__init__.py", 2),
    ("core/documents/schemas.py", "core/service/schemas/documents.py", 2),
    ("core/documents/selectors.py", "core/service/selectors/documents.py", 2),
    ("core/documents/services.py", "core/service/services/documents.py", 2),
    ("core/documents/jobs.py", "core/service/services/jobs.py", 2),
    ("core/documents/hooks.py", "core/resources/queue.py", 2),
    ("accounts/api.py", "accounts/service/apis/accounts.py", 4),
    ("accounts/auth.py", "accounts/service/apis/auth.py", 4),
    ("accounts/schemas.py", "accounts/service/schemas/accounts.py", 4),
    ("accounts/selectors.py", "accounts/service/selectors/accounts.py", 4),
    ("accounts/services.py", "accounts/service/services/accounts.py", 4),
    ("accounts/permissions.py", "accounts/service/permissions/accounts.py", 4),
    ("accounts/tokens.py", "accounts/service/utils/tokens.py", 4),
    ("accounts/exchange.py", "accounts/service/utils/exchange.py", 4),
    ("accounts/entities.py", "accounts/service/utils/entities.py", 4),
    ("accounts/models.py", "accounts/models/__init__.py", 4),
    ("reference/api.py", "reference/service/apis/reference.py", 5),
    ("reference/schemas.py", "reference/service/schemas/reference.py", 5),
    ("reference/selectors.py", "reference/service/selectors/reference.py", 5),
    ("reference/services.py", "reference/service/services/reference.py", 5),
    ("reference/importer.py", "reference/admin/services/importer.py", 5),
    ("reference/models.py", "reference/models/__init__.py", 5),
    ("inventory/api.py", "inventory/service/apis/inventory.py", 6),
    ("inventory/schemas.py", "inventory/service/schemas/inventory.py", 6),
    ("inventory/services.py", "inventory/service/services/inventory.py", 6),
    ("reconcile/services/__init__.py", "reconcile/service/services/__init__.py", 7),
    ("reconcile/services/parse.py", "reconcile/service/services/parse.py", 7),
)

# 옛 경로가 다시 내보내기 한 줄로 남는 셋(도메인 뿌리의 api.py). 값은 그 도메인.
ROOT_API: dict[str, str] = {
    "accounts/api.py": "accounts",
    "reference/api.py": "reference",
    "inventory/api.py": "inventory",
}

# 걷는 17파일(커밋 ③).
REMOVED_STEP = 3
REMOVED_FILES: tuple[str, ...] = (
    *(
        f"{module}/{name}"
        for module in ("drafting", "greenwashing", "materiality", "translation")
        for name in ("__init__.py", "api.py", "apps.py", "tests/__init__.py")
    ),
    "reconcile/api.py",
)
REMOVED_MODULES: tuple[str, ...] = (
    "esgapi.drafting",
    "esgapi.greenwashing",
    "esgapi.materiality",
    "esgapi.translation",
    "esgapi.reconcile.api",
)

# 새로 생기는 빈 `__init__.py` 23. (경로, 커밋)
NEW_INITS: tuple[tuple[str, int], ...] = (
    ("core/service/apis/__init__.py", 2),
    ("core/service/schemas/__init__.py", 2),
    ("core/service/selectors/__init__.py", 2),
    ("core/service/services/__init__.py", 2),
    ("accounts/service/__init__.py", 4),
    ("accounts/service/apis/__init__.py", 4),
    ("accounts/service/schemas/__init__.py", 4),
    ("accounts/service/selectors/__init__.py", 4),
    ("accounts/service/services/__init__.py", 4),
    ("accounts/service/permissions/__init__.py", 4),
    ("accounts/service/utils/__init__.py", 4),
    ("reference/service/__init__.py", 5),
    ("reference/service/apis/__init__.py", 5),
    ("reference/service/schemas/__init__.py", 5),
    ("reference/service/selectors/__init__.py", 5),
    ("reference/service/services/__init__.py", 5),
    ("reference/admin/__init__.py", 5),
    ("reference/admin/services/__init__.py", 5),
    ("inventory/service/__init__.py", 6),
    ("inventory/service/apis/__init__.py", 6),
    ("inventory/service/schemas/__init__.py", 6),
    ("inventory/service/services/__init__.py", 6),
    ("reconcile/service/__init__.py", 7),
)

# 이 밴드가 새로 넣는 scripts/ 의 셋(apps/api-py 아래의 경로).
NEW_SCRIPTS: tuple[str, ...] = (
    "scripts/gm_check.py",
    "scripts/section4-GM.sh",
    "scripts/gm-nodeids-3a0fa3a.txt",
)

# 「import 아닌 줄」을 고쳐도 되는 닫힌 목록의 `.py`(발주서 §1-5. apps/api-py 아래의 경로).
LISTED: tuple[str, ...] = (
    "esgapi/core/registry.py",
    "esgapi/config/api.py",
    "esgapi/config/apps_list.py",
    "esgapi/core/tests/test_llm_layers.py",
    "esgapi/core/tests/test_registry.py",
    "esgapi/core/tests/test_parser_port.py",
    "esgapi/core/tests/test_jobs_hook.py",
    "esgapi/inventory/tests/test_scope3_is_pure.py",
    "esgapi/inventory/tests/test_s3sheets_is_pure.py",
    "esgapi/reconcile/tests/test_tasks_registered.py",
    "esgapi/config/tests/test_settings.py",
    "esgapi/config/tests/test_api_contract.py",
    "tests_integration/test_upload_flow.py",
    "tests_integration/test_parser_flow.py",
    "scripts/readme_audit.py",
)
# 걷는 다섯을 들이던 import 를 지워도 되는 한 파일.
MAY_DROP_REMOVED = "esgapi/config/api.py"

# `strings` 가 보는 옛 경로의 무늬(점·빗금 두 꼴). (커밋, 무늬)
_DOMAIN_LEAVES = "auth|entities|exchange|permissions|schemas|selectors|services|tokens|importer"
OLD_PATH_PATTERNS: tuple[tuple[int, str], ...] = (
    (1, r"(^|[^a-z_])core[./](adapters|ports)([^a-z_]|$)"),
    (2, r"(^|[^a-z_])core[./]documents([^a-z_]|$)"),
    (2, r"(^|[^a-z_])core[./]api([^a-z_]|$)"),
    (3, r"esgapi[./](drafting|greenwashing|materiality|translation)([^a-z_]|$)"),
    (3, r"(^|[^a-z_])reconcile[./]api([^a-z_]|$)"),
    (4, rf"(^|[^a-z_])accounts[./]({_DOMAIN_LEAVES})([^a-z_]|$)"),
    (5, rf"(^|[^a-z_])reference[./]({_DOMAIN_LEAVES})([^a-z_]|$)"),
    (6, rf"(^|[^a-z_])inventory[./]({_DOMAIN_LEAVES})([^a-z_]|$)"),
    (7, r"(^|[^a-z_])reconcile[./]services([^a-z_]|$)"),
)

Binding = tuple[str, str, str]  # (가리키는 것, 묶인 이름, 감싼 블록의 종류)


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 가 {done.returncode} 로 끝났다: {done.stderr.strip()}")
    return done.stdout


ROOT = Path(git("rev-parse", "--show-toplevel").strip())


def rgit(*args: str) -> str:
    return git("-C", str(ROOT), *args)


def lines_of(text: str) -> list[str]:
    return [line for line in text.splitlines() if line]


def base_files() -> set[str]:
    """기준 커밋의 파일 전부(저장소 뿌리에서 본 경로)."""
    return set(lines_of(rgit("ls-tree", "-r", "--name-only", BASE)))


def current_files() -> set[str]:
    """지금 트리의 파일 전부: 추적되는 것 + 추적 안 된 새 파일 가운데 디스크에 있는 것."""
    listed = lines_of(rgit("ls-files", "--cached", "--others", "--exclude-standard"))
    return {path for path in listed if (ROOT / path).is_file()}


def changed_files() -> set[str]:
    """기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 지운 것도 든다."""
    return set(lines_of(rgit("diff", "--name-only", BASE))) | set(
        lines_of(rgit("ls-files", "--others", "--exclude-standard"))
    )


def base_source(path: str) -> str:
    return rgit("show", f"{BASE}:{path}")


def current_source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def module_of(path: str) -> str:
    """apps/api-py 아래의 경로 → 점으로 이은 모듈 이름."""
    stem = path.removesuffix(".py").removesuffix("/__init__")
    return stem.replace("/", ".")


def moves_upto(upto: int) -> list[tuple[str, str]]:
    return [(old, new) for old, new, step in MOVES if step <= upto]


def module_map(upto: int) -> dict[str, str]:
    """옛 모듈 → 새 모듈(커밋 upto 까지). 뿌리 api 셋과 models 는 이름이 그대로라 들지 않는다."""
    found: dict[str, str] = {}
    for old, new in moves_upto(upto):
        if old in ROOT_API:
            continue
        before, after = module_of(E + old), module_of(E + new)
        if before != after:
            found[before] = after
    return found


def removed_modules(upto: int) -> tuple[str, ...]:
    return REMOVED_MODULES if upto >= REMOVED_STEP else ()


def under(name: str, roots: tuple[str, ...] | list[str]) -> str | None:
    """name 이 roots 가운데 하나이거나 그 아래면 가장 길게 맞는 것을 준다."""
    best: str | None = None
    for root in roots:
        if (name == root or name.startswith(root + ".")) and (best is None or len(root) > len(best)):
            best = root
    return best


def is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _strip(statements: list[ast.stmt]) -> list[ast.stmt]:
    return [statement for statement in statements if not isinstance(statement, ast.Import | ast.ImportFrom)]


def _strip_node(node: ast.AST) -> None:
    """한 노드의 문장 목록에서 import 문을, 모듈·클래스·함수면 docstring 도 걷는다."""
    if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
        body = node.body[1:] if node.body and is_docstring(node.body[0]) else node.body
        node.body = _strip(body)
    elif isinstance(node, ast.For | ast.AsyncFor | ast.While | ast.If):
        node.body, node.orelse = _strip(node.body), _strip(node.orelse)
    elif isinstance(node, ast.With | ast.AsyncWith | ast.ExceptHandler | ast.match_case):
        node.body = _strip(node.body)
    elif isinstance(node, ast.Try | ast.TryStar):
        node.body, node.orelse, node.finalbody = _strip(node.body), _strip(node.orelse), _strip(node.finalbody)


def normalized(source: str) -> str:
    """import 문(어디에 있든)과 docstring 을 걷은 AST 의 글."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        _strip_node(node)
    return ast.dump(tree, include_attributes=False)


def bindings(source: str, module: str, *, is_package: bool) -> set[Binding]:
    """import 가 묶는 (가리키는 것, 묶인 이름, 감싼 블록의 종류를 바깥에서 안으로)."""
    found: set[Binding] = set()
    package_parts = module.split(".") if is_package else module.split(".")[:-1]

    def walk(node: ast.AST, chain: tuple[str, ...]) -> None:
        here = (*chain, type(node).__name__)
        for child in ast.iter_child_nodes(node):
            where = ">".join(here)
            if isinstance(child, ast.Import):
                for alias in child.names:
                    found.add((alias.name, alias.asname or alias.name.split(".")[0], where))
            elif isinstance(child, ast.ImportFrom):
                origin = child.module or ""
                if child.level:
                    kept = package_parts[: len(package_parts) - (child.level - 1)]
                    origin = ".".join([*kept, origin] if origin else kept)
                for alias in child.names:
                    found.add((f"{origin}.{alias.name}", alias.asname or alias.name, where))
            else:
                walk(child, here)

    walk(ast.parse(source), ())
    return found


def translate(target: str, mapping: dict[str, str]) -> str:
    root = under(target, list(mapping))
    return target if root is None else mapping[root] + target[len(root) :]


def py_under_package(paths: set[str]) -> list[str]:
    """apps/api-py 아래의 `.py`(저장소 뿌리에서 본 경로)."""
    return sorted(path for path in paths if path.startswith(PREFIX) and path.endswith(".py"))


def check_moves(upto: int) -> list[str]:
    bad: list[str] = []
    now, base = current_files(), base_files()
    for old, new, step in MOVES:
        old_path, new_path = PREFIX + E + old, PREFIX + E + new
        if old_path not in base:
            bad.append(f"기준에 옛 경로가 없다: {old}")
            continue
        if step > upto:
            if old_path not in now:
                bad.append(f"아직 옮길 차례가 아닌데(커밋 {step}) 옛 경로가 없다: {old}")
            if new_path in now:
                bad.append(f"아직 옮길 차례가 아닌데(커밋 {step}) 새 경로가 있다: {new}")
            continue
        if new_path not in now:
            bad.append(f"새 경로가 없다: {new}")
            continue
        if old in ROOT_API:
            if old_path not in now:
                bad.append(f"뿌리 api.py 가 남아 있어야 한다: {old}")
        elif old_path in now:
            bad.append(f"옛 경로가 남아 있다: {old}")
        if normalized(base_source(old_path)) != normalized(current_source(new_path)):
            bad.append(f"import 문과 docstring 을 뺀 AST 가 기준과 다르다: {old} → {new}")
    for name in REMOVED_FILES:
        path = PREFIX + E + name
        if upto >= REMOVED_STEP and path in now:
            bad.append(f"걷은 파일이 남아 있다: {name}")
        if upto < REMOVED_STEP and path not in now:
            bad.append(f"아직 걷을 차례가 아닌데 없다: {name}")
    done = len(moves_upto(upto))
    print(
        f"  옮김 {done}/{len(MOVES)} (커밋 {upto} 까지) · 걷음 {len(REMOVED_FILES) if upto >= REMOVED_STEP else 0}/17"
    )
    return bad


def _special_paths(upto: int) -> tuple[set[str], set[str]]:
    """(옮김의 옛 자리, 옮김의 새 자리 + 새 `__init__` + 뿌리 api + scripts 셋). 저장소 뿌리에서 본 경로."""
    olds = {PREFIX + E + old for old, _ in moves_upto(upto)}
    news = {PREFIX + E + new for _, new in moves_upto(upto)}
    news |= {PREFIX + E + path for path, step in NEW_INITS if step <= upto}
    news |= {PREFIX + path for path in NEW_SCRIPTS}
    return olds, news


def check_others(upto: int) -> list[str]:
    bad: list[str] = []
    now, base = current_files(), base_files()
    olds, news = _special_paths(upto)
    removed = {PREFIX + E + name for name in REMOVED_FILES} if upto >= REMOVED_STEP else set[str]()
    listed = {PREFIX + path for path in LISTED}
    compared = 0
    for path in py_under_package(changed_files()):
        if path in olds or path in news or path in removed:
            continue
        if path not in now:
            bad.append(f"대응표에 없는 파일이 지워졌다: {path}")
            continue
        if path not in base:
            bad.append(f"대응표에 없는 새 파일이다: {path}")
            continue
        if path in listed:
            diff = [
                line
                for line in rgit("diff", "-U0", BASE, "--", path).splitlines()
                if re.match(r"^[+-][^+-]|^[+-]$", line)
            ]
            print(f"── 닫힌 목록의 파일 {path.removeprefix(PREFIX)} (바뀐 줄 {len(diff)})")
            for line in diff:
                print(f"    {line}")
            continue
        compared += 1
        if normalized(base_source(path)) != normalized(current_source(path)):
            bad.append(f"import 문·docstring·주석 말고 바뀐 것이 있다: {path}")
    print(f"  닫힌 목록 밖에서 바뀐 .py {compared}개의 AST 를 기준과 견줬다")
    return bad


def check_imports(upto: int) -> list[str]:
    bad: list[str] = []
    now, base = current_files(), base_files()
    mapping = module_map(upto)
    gone = removed_modules(upto)
    new_of = {PREFIX + E + new: PREFIX + E + old for old, new in moves_upto(upto)}
    root_api = {PREFIX + E + old for old, _ in moves_upto(upto) if old in ROOT_API}
    compared = 0
    for path in py_under_package(changed_files()):
        if path not in now or path in root_api:
            continue
        origin = new_of.get(path, path)
        if origin not in base:
            continue  # 새 `__init__` 과 scripts 는 `new` 가 본다
        before = bindings(
            base_source(origin),
            module_of(origin.removeprefix(PREFIX)),
            is_package=origin.endswith("/__init__.py"),
        )
        after = bindings(
            current_source(path),
            module_of(path.removeprefix(PREFIX)),
            is_package=path.endswith("/__init__.py"),
        )
        expected: set[Binding] = set()
        for target, name, where in before:
            if under(target, gone) is not None and path == PREFIX + MAY_DROP_REMOVED:
                continue
            expected.add((translate(target, mapping), name, where))
        compared += 1
        for target, name, where in sorted(expected - after):
            bad.append(f"{path}: 있어야 할 import 가 없다 — {target} 를 {name} 으로 ({where})")
        for target, name, where in sorted(after - expected):
            bad.append(f"{path}: 대응표에 없는 import 다 — {target} 를 {name} 으로 ({where})")
    stale = [*mapping, *gone]
    scanned = 0
    for path in py_under_package(now):
        scanned += 1
        found = bindings(
            current_source(path), module_of(path.removeprefix(PREFIX)), is_package=path.endswith("/__init__.py")
        )
        for target, name, _ in sorted(found):
            if under(target, stale) is not None:
                bad.append(f"{path}: 옛 모듈을 가리키는 import 가 남았다 — {target} 를 {name} 으로")
    print(f"  바뀐 .py {compared}개의 import 를 대응표로 견줬다 · 트리의 .py {scanned}개에서 옛 모듈을 찾았다")
    return bad


def check_strings(upto: int) -> list[str]:
    bad: list[str] = []
    patterns = [re.compile(pattern) for step, pattern in OLD_PATH_PATTERNS if step <= upto]
    scanned = 0
    for path in py_under_package(current_files()):
        if "/migrations/" in path or path == PREFIX + "scripts/gm_check.py":
            continue
        if path == PREFIX + "scripts/readme_audit.py" and upto < 8:
            continue  # 커밋 ⑧ 이 고치는 파일이다
        scanned += 1
        tree = ast.parse(current_source(path))
        docstrings: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and is_docstring(first):
                docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or id(node) in docstrings:
                continue
            for pattern in patterns:
                if pattern.search(node.value):
                    shown = node.value if len(node.value) < 120 else node.value[:120] + "…"
                    bad.append(f"{path}:{node.lineno}: 문자열에 옛 경로가 남았다 — {shown!r}")
                    break
    print(f"  .py {scanned}개의 docstring 아닌 문자열에서 옛 경로의 무늬 {len(patterns)}개를 찾았다")
    return bad


def check_new(upto: int) -> list[str]:
    bad: list[str] = []
    now, base = current_files(), base_files()
    _, expected = _special_paths(upto)
    fresh = now - base
    for path in sorted(fresh - expected):
        bad.append(f"대응표에 없는 새 경로다: {path}")
    for path in sorted(expected - fresh):
        bad.append(f"있어야 할 새 경로가 없다: {path}")
    for name, step in NEW_INITS:
        path = PREFIX + E + name
        if step > upto or path not in now:
            continue
        body = ast.parse(current_source(path)).body
        if not (len(body) == 0 or (len(body) == 1 and is_docstring(body[0]))):
            bad.append(f"새 __init__.py 는 비었거나 docstring 하나여야 한다: {name}")
    for old, _, step in MOVES:
        path = PREFIX + E + old
        if old not in ROOT_API or step > upto or path not in now:
            continue
        domain = ROOT_API[old]
        body = ast.parse(current_source(path)).body
        statement = body[1] if len(body) == 2 and is_docstring(body[0]) else None
        shape_ok = (
            isinstance(statement, ast.ImportFrom)
            and statement.level == 0
            and statement.module == f"esgapi.{domain}.service.apis.{domain}"
            and [(alias.name, alias.asname) for alias in statement.names] == [("router", "router")]
        )
        if not shape_ok:
            bad.append(f"뿌리 api.py 는 docstring 과 「router as router」 다시 내보내기 한 줄뿐이어야 한다: {old}")
    print(f"  기준에 없던 경로 {len(fresh)}개 (기대 {len(expected)}개. 끝 모습은 62)")
    return bad


def check_places(upto: int) -> list[str]:
    del upto  # 자리의 꼴은 어느 커밋에서나 같아야 한다
    bad: list[str] = []
    files = sorted(
        path.removeprefix(PREFIX)
        for path in current_files()
        if path.startswith(PREFIX + E) and "__pycache__" not in path
    )
    base = sorted(path.removeprefix(PREFIX) for path in base_files() if path.startswith(PREFIX + E))

    def folders(paths: list[str]) -> dict[str, set[str]]:
        found: dict[str, set[str]] = {}
        for path in paths:
            parent = Path(path).parent
            found.setdefault(str(parent), set()).add(Path(path).name)
            for ancestor in parent.parents:
                if str(ancestor) not in (".", ""):
                    found.setdefault(str(ancestor), set())
        return found

    now_folders, base_folders = folders(files), folders(base)
    bare_before = {folder for folder, names in base_folders.items() if "__init__.py" not in names}
    surfaces = 0
    for folder, names in sorted(now_folders.items()):
        parts = Path(folder).parts
        if "actions" in parts:
            bad.append(f"actions/ 폴더가 있다: {folder}")
        if "__init__.py" not in names and folder not in bare_before:
            bad.append(f"__init__.py 가 없는 폴더다: {folder}")
        is_layer = len(parts) >= 2 and parts[-2] in ("service", "admin")
        if is_layer:
            surfaces += 1
            if not any(name.endswith(".py") and name != "__init__.py" for name in names):
                bad.append(f"빈 층 폴더다(__init__.py 말고 .py 가 없다): {folder}")
    print(f"  esgapi 의 폴더 {len(now_folders)}개 · 표면 아래의 층 폴더 {surfaces}개")
    return bad


CHECKS = {
    "moves": check_moves,
    "others": check_others,
    "imports": check_imports,
    "strings": check_strings,
    "new": check_new,
    "places": check_places,
}


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 3) or argv[0] not in CHECKS or (len(argv) == 3 and argv[1] != "--upto"):
        print(f"사용: gm_check.py <{'|'.join(CHECKS)}> [--upto <0~8>]", file=sys.stderr)
        return 2
    upto = int(argv[2]) if len(argv) == 3 else 8
    bad = CHECKS[argv[0]](upto)
    for line in bad:
        print(f"★ {line}")
    print(f"GM_CHECK {argv[0]} --upto {upto}: 어긋난 것 {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
