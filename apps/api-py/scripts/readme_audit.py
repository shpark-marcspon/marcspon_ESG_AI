"""docs/development.md 의 Python 절을 코드와 견주는 대조 도구(밴드 PY8b, MARC-TICK-59). 표준 라이브러리만 쓴다.

코드 쪽 사실(facts·paths·forward 와 compare 의 stale)은 <rev> 의 트리에서만 읽는다(git ls-tree · show · grep <rev>).
작업 트리에서 읽는 것은 DOC(docs/development.md)와 compare 의 `elsewhere:<파일>` 까닭이 가리키는 파일이다.
「새 쪽」은 DOC 의 `## Python API (apps/api-py)` 줄부터 끝까지다(밴드 README 가 뿌리 README.md 에서 옮겼다).

  facts <rev>                그 rev 에서 센 수를 `| 이름 | 값 | 센 법 |` 줄로 낸다
  compare <rev> <뺀 것.tsv>  옛 Python 절(rev 의 뿌리 README.md) − 새 Python 절(DOC)의 토큰. 빠진 것이 다 tsv 에
  paths --rev <rev>          새 Python 절과 「파서의 문서 분해」 소절의 경로가 그 rev 의 트리에 있는가
  forward --rev <rev>        코드에 있는 것(동작·env 키·표·관리 명령·모듈·계약)이 새 Python 절에 다 있는가
"""

import json
import re
import subprocess
import sys
import tomllib
from collections import Counter
from functools import cache
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[3]
API = "apps/api-py/"
PKG = API + "esgapi/"
PARSER = "services/parser/"
DOC = "docs/development.md"
PY_HEAD = "## Python API (apps/api-py)"
PARSER_HEAD = "## 파서의 문서 분해 (services/parser)"
WEB_HEAD = "## 문서 뷰어 (apps/web)"
WEB_MARK = "<!-- 웹 개발 글:"
PLACEHOLDER = "(PY8a 병합 뒤 감독이 채움)"

SPAN = re.compile(r"`([^`\n]+)`")
PATH_END = (".py", ".sh", ".json", ".jsonl", ".md", ".toml", ".yaml", ".importlinter")
UPPER = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?![A-Za-z0-9_])")
HTTP = re.compile(r"\b(GET|POST)\b[ |`]*(/[A-Za-z0-9_\-/.{}]*)")
SNAKE = re.compile(r"[a-z]+(?:_[a-z0-9]+)+")
CITIZEN = re.compile(r"MARC-(?:RPT|ISSUE|TICK)-\d+")
DECORATOR = re.compile(r"^@\w+\.(?:get|post|put|patch|delete)\(", re.MULTILINE)

# paths 모드: 소절마다 더 보는 앞머리. 소절의 낱말이 그 모듈 폴더 기준으로 적혀 있다(그린워싱 소절은 바이트 그대로
# 옮긴 검증 트랙의 글이라 고치지 않는다). 이 소절들에서만 아래 세 꼴(맨 파일 이름 · <경로>.<속성> · HTTP 조각)도 푼다.
SECTION_PREFIXES: dict[str, tuple[str, ...]] = {"### 그린워싱 (greenwash)": (PKG + "greenwash/",)}

# paths 모드: 그 rev 의 트리에 없어야 맞는 것. (꼴, 까닭). 앞에서부터 처음 맞는 줄을 쓴다.
OUTSIDE: tuple[tuple[str, str], ...] = (
    (r".*[<>*…$|{@]", "자리표시·묶음 꼴이거나 @ 가 든 이름(패키지 · 프롬프트 id)이다"),
    (r"(apps/api-py/)?\.(dev-keys|lab-golden)(/|$)", "git 밖: 연습용 키 쌍과 골든의 TS 덤프(.gitignore)"),
    (r"/tmp/", "git 밖: 컨테이너나 호스트의 임시 파일"),  # noqa: S108
    (r"band-reports/", "저장소 밖: 작업 폴더의 보고 파일"),
    (r"(ts|py|out|data/factors)(/|$)", "esg-lab 저장소의 경로"),
    (r"(document|char-places|factors|cookies|lab-digest)\.(json|jsonl|txt)$", "실행할 때 생기거나 바깥에서 오는 파일"),
    (r"((models|services|selectors|api|schemas|apps|admin)\.py|calc/)$", "모듈마다 있는 뼈대 파일·폴더의 이름"),
    (r"application/(pdf|json)$", "MIME 이름"),
    (r"/(api/(docs|openapi\.json)|parse)?$", "OpenAPI 계약 밖의 HTTP 경로: ninja 의 문서 둘, 파서의 /parse, 뿌리"),
    (r"https?://", "주소"),
)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


@cache
def tree(rev: str) -> tuple[str, ...]:
    return tuple(p for p in git("ls-tree", "-r", "-z", "--name-only", rev).split("\0") if p)


@cache
def entries(rev: str) -> frozenset[str]:
    """그 rev 의 파일과, 파일의 앞머리 폴더 전부."""
    out: set[str] = set()
    for path in tree(rev):
        parts = path.split("/")
        out.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    return frozenset(out)


@cache
def show(rev: str, path: str) -> str:
    return git("show", f"{rev}:{path}")


def as_dict(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def cut(text: str, head: str, *, to_end: bool) -> list[str]:
    """`head` 줄부터 파일 끝까지, 또는 다음 `## ` 줄 앞까지."""
    lines = text.split("\n")
    start = lines.index(head)
    end = len(lines) if to_end else next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    return lines[start:end]


def readme() -> str:
    return (ROOT / DOC).read_text(encoding="utf-8")


def new_section() -> list[str]:
    return cut(readme(), PY_HEAD, to_end=True)


def split_fences(lines: list[str]) -> tuple[list[str], list[str]]:
    """(풀어 쓴 줄, 코드 울타리 안의 줄)."""
    prose: list[str] = []
    fenced: list[str] = []
    inside = False
    for line in lines:
        if line.lstrip().startswith("```"):
            inside = not inside
        else:
            (fenced if inside else prose).append(line)
    return prose, fenced


def spans_of(lines: list[str]) -> list[str]:
    return [span for line in split_fences(lines)[0] for span in SPAN.findall(line)]


def tokens(lines: list[str]) -> dict[str, set[str]]:
    """토큰 여섯 갈래. (a) 울타리 안의 줄 (b) 경로 꼴 (c) 대문자 이름 (d) HTTP 경로 (e) 뱀 꼴 낱말 (f) 시민 번호."""
    text = "\n".join(lines)
    spans = spans_of(lines)
    commands: set[str] = set()
    for line in re.sub(r"\\\n\s*", " ", "\n".join(split_fences(lines)[1])).split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            commands.add(" ".join(re.sub(r"\s+# .*$", "", stripped).split()))
    return {
        "a": commands,
        "b": {s for s in spans if "/" in s or s.endswith(PATH_END)},
        "c": set(UPPER.findall(text)),
        "d": {f"{method} {path}" for method, path in HTTP.findall(text)} | {s for s in spans if s.startswith("/")},
        "e": {s for s in spans if SNAKE.fullmatch(s)},
        "f": set(CITIZEN.findall(text)),
    }


# ── 그 rev 의 코드에서 읽는 것 ──


def package_files(rev: str) -> list[str]:
    return [path.removeprefix(PKG) for path in tree(rev) if path.startswith(PKG)]


def modules(rev: str) -> list[str]:
    return sorted(p.split("/")[0] for p in package_files(rev) if p.count("/") == 1 and p.endswith("/__init__.py"))


def operations(rev: str) -> list[tuple[str, str, str]]:
    """(메서드, 경로, operationId). generated/openapi.json 의 paths."""
    document = as_dict(json.loads(show(rev, API + "generated/openapi.json")))
    out: list[tuple[str, str, str]] = []
    for path, item in as_dict(document.get("paths")).items():
        for method, operation in as_dict(item).items():
            out.append((method.upper(), path, str(as_dict(operation).get("operationId"))))
    return out


def env_keys(rev: str) -> list[str]:
    return sorted(set(re.findall(r'"([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)"', show(rev, PKG + "config/env.py"))))


def db_tables(rev: str) -> dict[str, list[str]]:
    pkg = package_files(rev)
    found_in = {m: [p for p in (f"{m}/models.py", f"{m}/models/__init__.py") if p in pkg] for m in modules(rev)}
    texts = {m: "".join(show(rev, PKG + p) for p in paths) for m, paths in found_in.items() if paths}
    found = {m: re.findall(r'db_table\s*=\s*"([^"]+)"', text) for m, text in texts.items()}
    return {m: names for m, names in found.items() if names}


def stems(rev: str, pattern: str) -> list[str]:
    """PKG 아래에서 정규식에 맞는 파일의 첫 묶음(이름)을 모은다."""
    names = {m.group(1) for p in package_files(rev) if (m := re.fullmatch(pattern, p))}
    return sorted(names - {"__init__"})


def commands(rev: str) -> dict[str, list[str]]:
    return {m: found for m in modules(rev) if (found := stems(rev, rf"{m}/management/commands/(\w+)\.py"))}


def contract_letters(rev: str) -> list[str]:
    return re.findall(r"^name = (.)\. ", show(rev, API + ".importlinter"), re.MULTILINE)


def package_listing(rev: str, folder: str) -> str:
    """폴더 바로 아래의 모듈 이름들 + 아래 폴더마다 (이름들)."""
    parts = [" ".join(stems(rev, rf"{folder}/(\w+)\.py"))]
    for sub in sorted(set(stems(rev, rf"{folder}/(\w+)/[^/]+")) - {"tests"}):
        names = {Path(p).stem for p in package_files(rev) if p.startswith(f"{folder}/{sub}/")}
        parts.append(f"{sub}/({' '.join(sorted(names - {'__init__', 'README'}))})")
    return " + ".join(part for part in parts if part)


def facts(rev: str) -> list[tuple[str, str, str]]:
    files, pkg, mods, ops = tree(rev), package_files(rev), modules(rev), operations(rev)
    grep = [
        line.removeprefix(f"{rev}:{PKG}").rsplit(":", 1) for line in git("grep", "-c", "", rev, "--", PKG).splitlines()
    ]
    counts = {path: int(count) for path, count in grep}
    api_files = {
        m: [p for p in pkg if p == f"{m}/api.py" or re.fullmatch(rf"{m}/service/apis/\w+\.py", p)] for m in mods
    }
    api_text = {m: "".join(show(rev, PKG + p) for p in paths) for m, paths in api_files.items() if paths}
    routes = {m: len(DECORATOR.findall(text)) for m, text in api_text.items()}
    explicit = sum(text.count("operation_id=") for text in api_text.values())
    tables = db_tables(rev)
    migrations = {m: found for m in mods if (found := stems(rev, rf"{m}/migrations/(\d\w+)\.py"))}
    sizes: list[str] = []
    tests: list[str] = []
    for m in mods:
        code = [p for p in pkg if p.startswith(f"{m}/") and p.endswith(".py") and "/tests/" not in p]
        sizes.append(f"{m} {len(code)}·{sum(counts.get(p, 0) for p in code):,}(경로 {routes.get(m, 0)})")
        tests.append(f"{m} {sum(1 for p in pkg if re.fullmatch(rf'{m}/(?:.+/)?tests/(?:.+/)?test_\w+\.py', p))}")
    security = sorted(m.group(1) for f in files if (m := re.fullmatch(rf"{API}tests/security/(test_\w+)\.py", f)))
    integration = [f for f in files if re.fullmatch(rf"{API}tests_integration/test_\w+\.py", f)]
    prompts = sorted(m.group(1) for p in pkg if (m := re.fullmatch(r"(\w+/prompts/[\w-]+/\d+\.md)", p)))
    compose = show(rev, "compose.yaml").split("\nservices:\n")[1].split("\nvolumes:\n")[0]
    services = re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", compose, re.MULTILINE)
    once = sorted(set(re.findall(r"([a-z][a-z0-9-]*): \{ condition: service_completed_successfully \}", compose)))
    project = as_dict(tomllib.loads(show(rev, API + "pyproject.toml")))
    runtime = [str(d) for d in as_list(as_dict(project.get("project")).get("dependencies"))]
    dev = [str(d).split("==")[0] for d in as_list(as_dict(project.get("dependency-groups")).get("dev"))]
    parser_project = as_dict(tomllib.loads(show(rev, PARSER + "pyproject.toml")))
    parser_deps = [str(d) for d in as_list(as_dict(parser_project.get("project")).get("dependencies"))]
    docparse = [f for f in files if f.startswith(PARSER + "docparse/")]
    engines = sorted(Path(f).stem for f in docparse if "/engine/" in f and not f.endswith("__init__.py"))
    verify = show(rev, "scripts/verify.sh")
    steps = re.findall(r"^(?:if ! )?step (.*)$", verify, re.MULTILINE)
    scripts = [f for f in files if re.fullmatch(rf"{API}scripts/[^/]+", f)]

    rows: list[tuple[str, str, str]] = []

    def add(name: str, value: str, how: str = "파일 목록") -> None:
        rows.append((name, value, how))

    def per_module(table: dict[str, list[str]]) -> str:
        return " / ".join(f"{m} {'·'.join(found)}" for m, found in table.items())

    letters, keys = contract_letters(rev), env_keys(rev)
    ports, resources = stems(rev, r"core/resources/ports/(\w+)\.py"), stems(rev, r"core/resources/(\w+)\.py")
    # 구현 = ports/ 에 같은 이름이 있는 것. 포트가 없는 것(queue)은 구현 줄에 섞지 않고 따로 적는다.
    adapters, portless = [n for n in resources if n in ports], [n for n in resources if n not in ports]
    in_py, in_scripts = (sum(s.startswith(head) for s in steps) for head in ("in_api_py", "apps/api-py/scripts"))
    add("기준", git("rev-parse", rev).strip(), "git rev-parse")
    add("OpenAPI 의 경로와 동작", f"경로 {len({p for _, p, _ in ops})} · 동작 {len(ops)}", "generated/openapi.json")
    add(
        "모듈별 동작",
        " · ".join(f"{m} {n}" for m, n in routes.items() if n),
        "모듈마다 api.py·service/apis/*.py 의 경로 장식자 수",
    )
    add(
        "operationId",
        f"명시 {explicit} · ninja 자동 {len(ops) - explicit}",
        "api.py·service/apis/*.py 의 operation_id= 줄 수, 나머지",
    )
    add(
        "표(db_table)",
        f"{sum(map(len, tables.values()))}: {per_module(tables)}",
        "모듈마다 models.py·models/__init__.py 의 db_table",
    )
    add("마이그레이션", per_module(migrations), "모듈마다 migrations/ 의 파일")
    add("import-linter 계약", f"{len(letters)}: {'·'.join(letters)}", ".importlinter 의 name")
    add("config/env.py 가 읽는 키", f"{len(keys)}: {' '.join(keys)}", "파일 안의 큰따옴표 대문자 낱말")
    add("compose 서비스", f"{len(services)}: {' '.join(services)} (일회성: {' '.join(once)})", "compose.yaml")
    add("모듈 폴더(esgapi/)", f"{len(mods)}. 테스트 아닌 .py 파일·줄: {' / '.join(sizes)}", "파일 목록 + git grep -c")
    add("테스트 파일(test_*.py)", " · ".join(tests), "모듈마다 tests/ 아래")
    add("보안 층 테스트 파일", f"tests/security {len(security)}: {' '.join(security)}")
    add("통합 테스트 파일", f"tests_integration {len(integration)}")
    add("core/llm", package_listing(rev, "core/llm"))
    add("core/resources/ports · core/resources", f"{' '.join(ports)} · {' '.join(adapters)}")
    add("core/resources 의 그 밖(포트 없음)", " ".join(portless))
    add("관리 명령", per_module(commands(rev)), "모듈마다 management/commands/")
    add("프롬프트", " · ".join(prompts), "모듈마다 prompts/ 아래의 이름/판.md")
    for axis in ("engines", "contracts", "tools", "flows"):
        add(f"inventory/{axis}", package_listing(rev, f"inventory/{axis}"))
    add("reference/calc", package_listing(rev, "reference/calc"))
    add("reconcile/calc", package_listing(rev, "reconcile/calc"))
    add("reconcile/service/services", package_listing(rev, "reconcile/service/services"))
    add("파서(services/parser)의 분해기", f"docparse 파일 {len(docparse)} · 엔진 {' '.join(engines)}")
    add("파서의 의존성", " ".join(parser_deps), "services/parser/pyproject.toml")
    add("의존성(apps/api-py) 실행", f"{len(runtime)}: {' '.join(runtime)}", "pyproject.toml")
    add("의존성(apps/api-py) dev", f"{len(dev)}: {' '.join(dev)}", "pyproject.toml")
    steps_text = f"step {len(steps)}(in_api_py {in_py} · apps/api-py/scripts {in_scripts})"
    add("scripts/verify.sh", f"{verify.count(chr(10))}줄 · {steps_text}", "파일의 step 줄")
    add("apps/api-py/scripts", f"{len(scripts)}: {' '.join(Path(f).name for f in scripts)}")
    return rows


# ── 모드 ──


def reason_problem(rev: str, row: list[str], new_text: str) -> str | None:
    """까닭 갈래의 기계 확인. 걸리면 문장, 통과면 None."""
    kind, token, reason, evidence = row
    target = reason.removeprefix("elsewhere:")
    if reason == "stale":
        ok, why = evidence.split()[0].rstrip("/") in entries(rev), "근거의 첫 낱말이 그 rev 의 트리에 없다"
    elif reason == "pending-PY8a":
        ok, why = True, ""
    elif reason == "example":
        ok, why = kind in "bc" and evidence in new_text, "(b)·(c) 가 아니거나 근거(대응 글자)가 새 Python 절에 없다"
    elif reason == "elsewhere:README.md":
        ok, why = token in readme_front(), "작업 트리 README.md 의 웹 블록 앞에 토큰이 없다"
    elif reason.startswith("elsewhere:"):
        path = ROOT / target
        ok = path.is_file() and token in path.read_text(encoding="utf-8")
        why = "그 파일이 작업 트리에 없거나 토큰이 그 안에 없다"
    else:
        ok, why = False, "모르는 까닭 갈래"
    return None if ok else f"{reason}: {why}"


def readme_front() -> str:
    """작업 트리 뿌리 README.md 에서 웹 블록 앞. 줄 번호가 아니라 표지·머리글로 찾는다(처분 ⑯·⑰).

    웹 블록 앞에 표지 주석(WEB_MARK 로 시작하는 줄)이 있으면 그 줄 앞만, 없으면 WEB_HEAD 줄 앞만 본다(웹 블록 안의
    토큰을 근거로 삼지 않는다). 둘 다 없으면(짝 밴드가 웹 블록을 apps/web 쪽으로 옮긴 뒤) 앞 구역 제한을 건너뛰고
    파일 전체를 돌려주며, 그 사실을 한 줄 찍는다(조용히 통과하지 않게).
    바꾼 뜻: 옛 갈래는 근거의 L<n> 줄 번호가 WEB_HEAD 줄 앞인지 봤다. 이제 근거의 줄 번호는 보지 않는다.
    """
    lines = (ROOT / "README.md").read_text(encoding="utf-8").split("\n")
    marks = [i for i, line in enumerate(lines) if line.startswith(WEB_MARK) or line == WEB_HEAD]
    if not marks:
        if not _WEB_SKIP_SAID:
            _WEB_SKIP_SAID.append(True)
            print(f"elsewhere:README.md: 웹 블록(표지·{WEB_HEAD})이 README.md 에 없다 — 파일 전체에서 찾는다")
        return "\n".join(lines)
    return "\n".join(lines[: marks[0]])


_WEB_SKIP_SAID: list[bool] = []


def run_compare(rev: str, tsv: str) -> int:
    old = tokens(cut(show(rev, "README.md"), PY_HEAD, to_end=True))
    lines = new_section()
    new, new_text = tokens(lines), "\n".join(lines)
    raw = [line.split("\t") for line in Path(tsv).read_text(encoding="utf-8").split("\n") if line.strip()]
    rows = [row for row in raw if row[0] != "갈래"]
    problems = [f"tsv 의 칸이 넷이 아니다: {row}" for row in rows if len(row) != 4]
    rows = [row for row in rows if len(row) == 4]
    listed = Counter((row[0], row[1]) for row in rows)
    reasons: Counter[str] = Counter()
    for kind in "abcdef":
        dropped = old[kind] - new[kind]
        print(f"({kind}) 옛 {len(old[kind])} · 남은 {len(old[kind] & new[kind])} · 뺀 {len(dropped)}")
        if kind != "a":
            problems += [f"tsv 에 없다: ({kind}) {token}" for token in sorted(dropped) if (kind, token) not in listed]
    for row in rows:
        kind, token, reason, evidence = row
        if kind == "a" or kind not in old or token not in old[kind] - new[kind]:
            problems.append(f"tsv 에 안 쓰인 줄: ({kind}) {token}")
        elif listed[(kind, token)] > 1:
            problems.append(f"tsv 에 두 번 나온다: ({kind}) {token}")
        elif not evidence.strip():
            problems.append(f"근거가 비었다: ({kind}) {token}")
        elif problem := reason_problem(rev, row, new_text):
            problems.append(f"({kind}) {token} — {problem}")
        reasons[reason.split(":")[0]] += 1
    placeholders = sum(PLACEHOLDER in line for line in lines)
    if reasons["pending-PY8a"] and placeholders < reasons["pending-PY8a"]:
        problems.append(f"pending-PY8a {reasons['pending-PY8a']}줄인데 새 Python 절의 자리표시 줄은 {placeholders}")
    print("까닭 갈래별: " + (" · ".join(f"{name} {n}" for name, n in sorted(reasons.items())) or "없음"))
    for problem in problems:
        print(f"★ {problem}")
    print(f"COMPARE={'OK' if not problems else 'FAIL'} (문제 {len(problems)})")
    return 1 if problems else 0


def path_words(lines: list[str]) -> set[str]:
    """(b) 토큰. 빈칸이 든 것은 낱말로 갈라 경로 꼴인 낱말만 남긴다."""
    words = {word.strip("\"'(),;:").split("?")[0] for span in spans_of(lines) for word in span.split()}
    return {word for word in words if "/" in word or word.endswith(PATH_END)}


def subsections(lines: list[str]) -> list[tuple[str, list[str]]]:
    """(소절 머리, 그 소절의 줄). 머리는 `### ` 줄이고, 첫 `### ` 앞은 머리가 빈 글자다."""
    out: list[tuple[str, list[str]]] = [("", [])]
    for line in lines:
        if line.startswith("### "):
            out.append((line, []))
        out[-1][1].append(line)
    return out


def section_match(rev: str, word: str, prefixes: tuple[str, ...]) -> str | None:
    """소절 앞머리 아래의 세 꼴. 찾음이면 "found", 표면 "excused", 아니면 None.

    맨 파일 이름(`/` 없는 *.py): 앞머리 아래에서 같은 이름의 파일이 하나뿐이면 찾음(둘 이상이면 못 찾음).
    <경로>.<속성>: 마지막 `.` 앞에 `.py` 를 붙인 파일이 앞머리 아래에 있으면 찾음.
    HTTP 조각: openapi paths 가운데 그 조각으로 시작하거나 끝나는 경로가 있으면 표.
    """
    if "/" not in word and word.endswith(".py"):
        hits = [p for p in tree(rev) for pre in prefixes if p.startswith(pre) and p.rsplit("/", 1)[-1] == word]
        return "found" if len(hits) == 1 else None
    stem, dot, _ = word.rpartition(".")
    if (
        dot
        and "/" in stem
        and not word.endswith(PATH_END)
        and any(pre + stem + ".py" in entries(rev) for pre in prefixes)
    ):
        return "found"
    fragment = word.rstrip("/")
    if any(
        p.startswith(fragment if fragment.startswith("/") else "/" + fragment) or p.endswith(fragment)
        for _, p, _ in operations(rev)
    ):
        return "excused"
    return None


def run_paths(rev: str) -> int:
    words: dict[str, tuple[str, ...]] = {}
    for head, lines in [*subsections(new_section()), ("", cut(readme(), PARSER_HEAD, to_end=False))]:
        for word in path_words(lines):
            words[word] = words.get(word, ()) + SECTION_PREFIXES.get(head, ())
    http_paths = {path for _, path, _ in operations(rev)}
    found, excused, missing = 0, 0, 0
    for word, extra in sorted(words.items()):
        bare = word.rstrip("/")
        special = section_match(rev, word, extra) if extra else None
        known = word in http_paths or any((prefix + bare) in entries(rev) for prefix in ("", API, PKG, *extra))
        if known or special == "found":
            found += 1
        elif special == "excused":
            excused += 1
            print(f"표: {word} — 소절 앞머리의 HTTP 조각(openapi paths 의 앞이나 끝)")
        elif reason := next((why for shape, why in OUTSIDE if re.match(shape, word)), None):
            excused += 1
            print(f"표: {word} — {reason}")
        else:
            missing += 1
            print(f"★ 못 찾음: {word}")
    print(f"PATHS: 찾음 {found} / 표에 있음 {excused} / 못 찾음 {missing}")
    return 1 if missing else 0


def run_forward(rev: str) -> int:
    lines = new_section()
    text, fenced = "\n".join(lines), split_fences(lines)[1]

    def quoted(name: str) -> bool:
        return f"`{name}`" in text

    def module_named(name: str) -> bool:
        return quoted(f"{name}/") or any(re.search(rf"(?<![\w/.-]){name}/", line) for line in fenced)

    def operation_named(method: str, path: str) -> bool:
        return any(re.search(rf"\b{method}\b", line) and f"`{path}`" in line for line in lines)

    checks: list[tuple[str, list[tuple[str, bool]]]] = [
        ("동작", [(f"{m} {p}", operation_named(m, p)) for m, p, _ in operations(rev)]),
        ("env 키", [(key, quoted(key)) for key in env_keys(rev)]),
        ("표", [(t, quoted(t)) for found in db_tables(rev).values() for t in found]),
        ("관리 명령", [(c, quoted(c)) for found in commands(rev).values() for c in found]),
        ("모듈", [(m, module_named(m)) for m in modules(rev)]),
        ("계약", [(letter, f"**{letter}.**" in text) for letter in contract_letters(rev)]),
    ]
    failed = 0
    for name, items in checks:
        absent = [item for item, ok in items if not ok]
        failed += len(absent)
        print(f"{name} {len(items) - len(absent)}/{len(items)}" + (f"  ★ 없음: {' '.join(absent)}" if absent else ""))
    print(f"FORWARD={'OK' if not failed else 'FAIL'}")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    match argv:
        case ["facts", rev]:
            print("\n".join(f"| {name} | {value} | {how} |" for name, value, how in facts(rev)))
            return 0
        case ["compare", rev, tsv]:
            return run_compare(rev, tsv)
        case ["paths", "--rev", rev]:
            return run_paths(rev)
        case ["forward", "--rev", rev]:
            return run_forward(rev)
        case _:
            print(__doc__)
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
