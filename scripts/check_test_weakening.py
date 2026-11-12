"""시험을 끄거나 약하게 하는 꼴을 병합 전에 잰다(DG1, MARC-ISSUE-266). 표준 라이브러리만. 읽기만 한다.

    python3 -I scripts/check_test_weakening.py [--repo <폴더>] [--allow <파일>] [--allow-drop <경로>]… [--warn] <바닥 rev> <머리 rev>
    python3 -I scripts/check_test_weakening.py --self-test
    python3 -I scripts/check_test_weakening.py [--repo <폴더>] [--allow <파일>] --replay <n> [--replay-tip <rev>]

비교 바닥 = `git merge-base <바닥> <머리>`(= main...band). 머리 rev 의 트리를 읽는다 — 작업 트리·색인은 보지 않으니 main
체크아웃에서 남의 가지를 잴 수 있다. 갈래 넷:
  (a) 더한 끄는 꼴 — diff(-M) 의 `+` 줄. 파이썬은 tokenize 로 문자열·주석을 지운 나머지에서, 웹은 주석 줄과 따옴표 안을
      지운 나머지에서, 시험 실행 설정(test-*.sh·pyproject·vitest/playwright 설정·verify.sh)은 거르기 꼴만 찾는다.
  (b) 시험 몸 앞당김 return — 파이썬은 ast 로 `test_` 함수 안(안쪽 def·class·lambda 는 건너뜀)의 더한 줄 return,
      웹은 더한 줄 `return;` 이 it(·test( 콜백 몸 바로 아래 단인지 들여쓰기로 본다.
  (c) 파일별 시험 정의 수 줄어듦 — 바닥 경로 ↔ 머리 경로를 -M 으로 짝짓고 센다(이름 바꿈·옮김은 셈하지 않음).
      사라진 이름은 같이 찍지만 판정은 수로만 한다(웹 it 제목은 자주 바뀐다).
  (d) 웹 타입 단언 `Expect<` 수 줄어듦(정의 줄 `type Expect<` 는 뺀다).
허용 목록(기본: 머리 트리의 scripts/test-weakening-allow.txt, --replay 는 이 스크립트 옆의 지금 파일) 한 줄 =
`<경로>\\t<줄 글(앞뒤 빈칸 뗀 원문)>\\t<까닭 — 언제·누가 켜서 도는지>` 로 (a)·(b) 를 넘긴다. 까닭 칸이 비면 빨강.
바닥 이후 목록에 더해진 줄은 `새 허용` 으로 찍는다 — 감독이 까닭 칸을 읽는다. (c)·(d) 의 정당한 줄임은 감독이 짝 표를 본 뒤
`--allow-drop <머리 경로 또는 지운 바닥 경로>` 로 넘긴다(목록에 적지 않는다 — 밴드 한 번의 일).
끝 줄 `WEAKEN=PASS|FAIL red=<n> new_allow=<n> drops=<n> types=<n>`, 종료 0/1(인자·rev 오류 2, --warn 이면 늘 0).
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize
import warnings
from collections import Counter
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

ALLOW_PATH = "scripts/test-weakening-allow.txt"
SELF_PATHS = {"scripts/check_test_weakening.py", ALLOW_PATH}
RENAMES = ["-M"]
GIT = [
    "git",
    "-c", "core.quotepath=off",
    "-c", "diff.renames=false",
    "-c", "diff.noprefix=false",
    "-c", "diff.mnemonicPrefix=false",
    "-c", "diff.relative=false",
    "-c", "color.ui=false",
]

CONFIG_FILES = {
    "apps/api-py/pyproject.toml",
    "services/parser/pyproject.toml",
    "apps/web/vitest.config.ts",
    "apps/web/playwright.config.ts",
    "apps/web/e2e/live/playwright.config.ts",
    "apps/api-py/tests_integration/pytest.ini",
    "scripts/verify.sh",
}
PY_DISABLE = re.compile(
    r"\bor\s+True\b|\bif\s+(False|0)\s*:|pytest\.skip\b|pytest\.mark\.skip(if)?\b|\bskipif\b|xfail|importorskip"
    r"|unittest\.skip|\bmark\.skip(if)?\b|\bSkipTest\b|collect_ignore|\bassert\s+True\s*(,|$)"
)
WEB_DISABLE = re.compile(
    r"\b(it|test|describe)\.(skip|only|todo|fixme)\b|\bx(it|describe|test)\(|\|\|\s*true\b|if\s*\(\s*false\s*\)"
    r"|expect\(\s*true\s*\)|\.(skipIf|runIf)\b|\.concurrent\.(skip|only|todo)\b"
)
CONF_DISABLE = re.compile(
    r"--deselect|--ignore(-glob)?|(^|\s)-k\s|addopts|norecursedirs|testIgnore|exclude\s*:|grep\s*:"
)
PY_DEF = re.compile(r"^[ \t]*(?:async )?def (test_\w+)", re.M)
WEB_DEF = re.compile(r"^[ \t]*(?:it|test)(?:\.each\b[^(]*)?\(", re.M)
WEB_TITLE = re.compile(r"\s*['\"`]([^'\"`]*)")
WEB_QUOTED = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`(?:[^`\\]|\\.)*`")
WEB_RETURN = re.compile(r"^\s*return\s*;?\s*$")
WEB_CALLBACK = re.compile(r"(=>|\bfunction\b[^{]*)\s*\{\s*$")
WEB_TEST_CALL = re.compile(r"^\s*(it|test)(\.\w+)*(\([^)]*\))?\(")
EXPECT = re.compile(r"Expect<")
EXPECT_DEF = re.compile(r"\btype\s+Expect<")


class GitError(Exception):
    pass


def git(repo: str, *args: str) -> bytes:
    run = subprocess.run([*GIT, "-C", repo, *args], capture_output=True)
    if run.returncode:
        raise GitError(f"git {' '.join(args)}: {run.stderr.decode('utf-8', 'replace').strip()}")
    return run.stdout


class Blobs:
    """`git cat-file --batch` 하나로 <rev>:<경로> 를 읽는다. 바이트로 받아 errors="replace" 로 푼다(옛 이진 파일)."""

    def __init__(self, repo: str) -> None:
        self.proc = subprocess.Popen([*GIT, "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.cache: dict[tuple[str, str], str | None] = {}

    def get(self, rev: str, path: str | None) -> str | None:
        if path is None:
            return None
        key = (rev, path)
        if key not in self.cache:
            assert self.proc.stdin and self.proc.stdout
            self.proc.stdin.write(f"{rev}:{path}\n".encode())
            self.proc.stdin.flush()
            head = self.proc.stdout.readline().split()
            if len(head) != 3 or head[1] != b"blob":
                self.cache[key] = None
            else:
                data = self.proc.stdout.read(int(head[2]))
                self.proc.stdout.read(1)
                self.cache[key] = data.decode("utf-8", errors="replace")
        return self.cache[key]

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait()


def kind_of(path: str | None) -> str | None:
    if path is None or path in SELF_PATHS:
        return None
    if fnmatch(path, "apps/api-py/scripts/section4-*") or fnmatch(path, "apps/api-py/scripts/planted-breaks-*"):
        return None
    if path.startswith("apps/web/scripts/"):
        return None
    if path in CONFIG_FILES or fnmatch(path, "apps/api-py/scripts/test-*.sh"):
        return "conf"
    parts = path.split("/")
    name = parts[-1]
    if name.endswith(".py") and (
        "tests" in parts[:-1] or "tests_integration" in parts[:-1] or name == "conftest.py" or name.startswith("test_")
    ):
        return "py"
    if re.fullmatch(r"(apps/web|packages)/.+\.test\.tsx?", path) or re.fullmatch(r"apps/web/e2e/.+\.tsx?", path):
        return "web"
    return None


def name_pairs(repo: str, base: str, head: str) -> list[tuple[str | None, str | None]]:
    """(바닥 경로, 머리 경로). R 은 옛→새, D 는 머리 None, A 는 바닥 None."""
    toks = git(repo, "diff", *RENAMES, "--name-status", "-z", base, head).decode("utf-8", "replace").split("\0")
    pairs: list[tuple[str | None, str | None]] = []
    i = 0
    while i < len(toks) and toks[i]:
        status = toks[i][0]
        if status in "RC":
            pairs.append((toks[i + 1], toks[i + 2]))
            i += 3
        elif status == "D":
            pairs.append((toks[i + 1], None))
            i += 2
        elif status == "A":
            pairs.append((None, toks[i + 1]))
            i += 2
        else:
            pairs.append((toks[i + 1], toks[i + 1]))
            i += 2
    return pairs


HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def added_lines(repo: str, base: str, head: str) -> dict[str, dict[int, str]]:
    """머리 경로 → {머리 줄 번호: 더한 줄 글}."""
    text = git(
        repo, "diff", *RENAMES, "-U0", "--no-ext-diff", "--no-textconv", "--src-prefix=a/", "--dst-prefix=b/", base, head
    ).decode("utf-8", "replace")
    found: dict[str, dict[int, str]] = {}
    cur: str | None = None
    old_left = new_left = 0
    line_no = 0
    for line in text.split("\n"):
        if old_left > 0 or new_left > 0:
            if line.startswith("+"):
                if cur is not None:
                    found[cur][line_no] = line[1:]
                line_no += 1
                new_left -= 1
            elif line.startswith("-"):
                old_left -= 1
            continue
        if line.startswith("diff --git "):
            cur = None
        elif line.startswith("+++ "):
            dst = line[4:].rstrip("\t")
            cur = dst[2:] if dst.startswith("b/") else None
            if cur is not None:
                found.setdefault(cur, {})
        elif line.startswith("@@"):
            m = HUNK.match(line)
            if m:
                old_left = int(m.group(1)) if m.group(1) is not None else 1
                line_no = int(m.group(2))
                new_left = int(m.group(3)) if m.group(3) is not None else 1
    return found


def py_code_lines(text: str) -> list[str] | None:
    """줄마다 STRING·COMMENT(f/t-string 통째) 토큰을 빈칸으로 지운 글. 토큰화가 안 되면 None."""
    lines = text.split("\n")
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    depth = 0
    start: tuple[int, int] = (0, 0)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            name = tokenize.tok_name[tok.type]
            if name.endswith("STRING_START"):
                if depth == 0:
                    start = tok.start
                depth += 1
            elif name.endswith("STRING_END"):
                depth -= 1
                if depth == 0:
                    spans.append((start, tok.end))
            elif depth == 0 and tok.type in (tokenize.STRING, tokenize.COMMENT):
                spans.append((tok.start, tok.end))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return None
    out = list(lines)
    for (sr, sc), (er, ec) in spans:
        for r in range(sr, er + 1):
            if r - 1 >= len(out):
                break
            row = out[r - 1]
            s = sc if r == sr else 0
            e = ec if r == er else len(row)
            out[r - 1] = row[:s] + " " * max(e - s, 0) + row[e:]
    return out


def py_returns(text: str) -> set[int] | None:
    """`test_` 함수 안의 return 줄 번호(안쪽 def·class·lambda 는 건너뜀). ast 가 못 읽으면 None."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            stack: list[ast.AST] = list(node.body)
            while stack:
                n = stack.pop()
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    continue
                if isinstance(n, ast.Return):
                    found.add(n.lineno)
                stack.extend(ast.iter_child_nodes(n))
    return found


def web_code(line: str) -> str:
    s = line.lstrip()
    if s.startswith(("//", "/*", "*")):
        return ""
    s = WEB_QUOTED.sub("''", line)
    return re.sub(r"\s//.*$", "", s)


def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def web_early_return(lines: list[str], idx: int) -> bool:
    """lines[idx] 의 return 이 it(·test( 콜백 몸 바로 아래 단인가 — 바로 위 단이 콜백 여는 줄이고, 그 줄이나 그 위 단이 it(·test(."""
    parents: list[str] = []
    level = indent(lines[idx])
    for j in range(idx - 1, -1, -1):
        row = lines[j]
        if not row.strip():
            continue
        if indent(row) < level:
            parents.append(row)
            level = indent(row)
            if len(parents) == 2:
                break
    if not parents or not WEB_CALLBACK.search(web_code(parents[0])):
        return False
    return any(WEB_TEST_CALL.match(p) for p in parents)


def py_defs(text: str | None) -> list[str]:
    """ast 로 이름이 `test_` 인 함수(문자열 속 `def test_` 는 세지 않음). 못 읽으면 줄 정규식."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text or "")
    except (SyntaxError, ValueError):
        return PY_DEF.findall(text or "")
    return [
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    ]


def web_mask(text: str) -> str:
    """주석(`/* */`·`//`)과 '…'·"…" 안을 빈칸으로(줄바꿈은 남김). 따옴표는 줄 끝에서 닫는다(정규식 리터럴 대비).

    백틱 템플릿은 지우지 않는다 — 정규식 리터럴 속 백틱(apps/web/src/app/guards/kit-imports.test.ts)이 템플릿을 열어
    뒤의 it( 를 통째로 지웠다(재검증 1 B1). 템플릿 속에 숨긴 시험은 그래서 셈에 남는다.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("/*", i):
            close = text.find("*/", i + 2)
            lo, hi = i, (n if close < 0 else close + 2)
        elif text.startswith("//", i):
            close = text.find("\n", i)
            lo, hi = i, (n if close < 0 else close)
        elif c in "'\"":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            lo, hi = i + 1, min(j, n)
            hi_next = min(j + 1, n)
            for k in range(lo, hi):
                if out[k] != "\n":
                    out[k] = " "
            i = hi_next
            continue
        else:
            i += 1
            continue
        for k in range(lo, hi):
            if out[k] != "\n":
                out[k] = " "
        i = hi
    return "".join(out)


def web_defs(text: str | None) -> list[str]:
    """주석·따옴표 안을 지운 뒤 센다. 이름(첫 인자 글)은 원문에서 읽는다."""
    raw = text or ""
    found = []
    for m in WEB_DEF.finditer(web_mask(raw)):
        title = WEB_TITLE.match(raw, m.end())
        found.append(title.group(1) if title else "?")
    return found


def expect_count(text: str | None) -> int:
    return sum(len(EXPECT.findall(row)) - len(EXPECT_DEF.findall(row)) for row in (text or "").split("\n"))


@dataclass
class Allow:
    entries: dict[tuple[str, str], str] = field(default_factory=dict)
    invalid: list[tuple[int, str]] = field(default_factory=list)


def parse_allow(text: str | None) -> Allow:
    allow = Allow()
    for n, raw in enumerate((text or "").split("\n"), 1):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 3 or not fields[2].strip():
            allow.invalid.append((n, line))
            continue
        allow.entries[(fields[0].strip(), fields[1].strip())] = fields[2].strip()
    return allow


@dataclass
class Result:
    red: int = 0
    drops: int = 0
    types: int = 0
    new_allow: int = 0
    lines: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.red == 0


def short(text: str) -> str:
    return text.strip()[:120]


def names(gone: list[str]) -> str:
    """사라진 이름 앞 셋, 하나에 40자까지(웹 it 제목은 길다)."""
    return ", ".join(n if len(n) <= 40 else n[:39] + "…" for n in gone[:3])


def check(repo: str, base_rev: str, head_rev: str, allow_text: str | None = None, allow_drop: tuple[str, ...] = (),
          blobs: Blobs | None = None) -> Result:
    """allow_text 가 None 이면 머리 트리의 허용 목록을 쓴다."""
    res = Result()
    out = res.lines.append
    head = git(repo, "rev-parse", "--verify", f"{head_rev}^{{commit}}").decode().strip()
    tip = git(repo, "rev-parse", "--verify", f"{base_rev}^{{commit}}").decode().strip()
    base = git(repo, "merge-base", tip, head).decode().strip()
    own = blobs is None
    blobs = blobs or Blobs(repo)
    try:
        out(f"비교 바닥 {base[:10]} (merge-base {base_rev} {head_rev}) · 머리 {head[:10]}")
        if allow_text is None:
            allow_text = blobs.get(head, ALLOW_PATH)
        allow = parse_allow(allow_text)
        before = parse_allow(blobs.get(base, ALLOW_PATH))
        counts = Counter()

        def red(gate: str, msg: str) -> None:
            counts[gate] += 1
            res.red += 1
            out(f"★ {gate} {msg}")

        for n, line in allow.invalid:
            red("허용", f"허용 목록 {n}째 줄 까닭 칸(셋째)이 없다 — 켜는 법 없는 허용: {short(line)}")

        added = added_lines(repo, base, head)
        for path in sorted(added):
            kind = kind_of(path)
            if kind is None or not added[path]:
                continue
            text = blobs.get(head, path) or ""
            rows = text.split("\n")
            hits: list[tuple[str, int]] = []
            if kind == "py":
                code = py_code_lines(text)
                if code is None:
                    out(f"· 읽기 실패 {path} — 토큰화 못 함, 줄 정규식으로")
                for ln, raw in sorted(added[path].items()):
                    seen = code[ln - 1] if code is not None and ln - 1 < len(code) else raw
                    if code is None and raw.lstrip().startswith("#"):
                        continue
                    if PY_DISABLE.search(seen.rstrip()):
                        hits.append(("a", ln))
                returns = py_returns(text)
                if returns is None:
                    out(f"· 읽기 실패 {path} — ast 못 함, (b) 건너뜀")
                else:
                    hits.extend(("b", ln) for ln in sorted(returns) if ln in added[path])
            elif kind == "web":
                for ln, raw in sorted(added[path].items()):
                    if WEB_DISABLE.search(web_code(raw)):
                        hits.append(("a", ln))
                    if WEB_RETURN.match(raw) and ln - 1 < len(rows) and web_early_return(rows, ln - 1):
                        hits.append(("b", ln))
            else:
                for ln, raw in sorted(added[path].items()):
                    s = raw.lstrip()
                    if s.startswith(("#", "//")):
                        continue
                    if CONF_DISABLE.search(raw):
                        hits.append(("a", ln))
            for gate, ln in hits:
                raw = added[path].get(ln, "")
                if (path, raw.strip()) in allow.entries:
                    out(f"· 허용 {gate} {path}:{ln} {short(raw)}")
                else:
                    red(gate, f"{path}:{ln} {short(raw)}")

        for old, new in name_pairs(repo, base, head):
            kind = kind_of(new) or kind_of(old)
            if kind not in ("py", "web"):
                continue
            before_text, after_text = blobs.get(base, old), blobs.get(head, new)
            defs = py_defs if kind == "py" else web_defs
            b_names, h_names = defs(before_text), defs(after_text)
            gone = list((Counter(b_names) - Counter(h_names)).elements())
            where = new if new is not None else f"{old} (지움)"
            if old is not None and new is not None and old != new:
                where = f"{old} → {new}"
            passed = (new is not None and new in allow_drop) or (old is not None and old in allow_drop)
            if len(h_names) < len(b_names):
                msg = f"{where} {len(b_names)}→{len(h_names)} 사라진: {names(gone) or '-'}"
                if passed:
                    out(f"· 넘김 c {msg} (--allow-drop)")
                else:
                    res.drops += 1
                    red("c", msg)
            elif gone:
                out(f"· 보기 이름 {where} {len(b_names)}→{len(h_names)} 사라진: {names(gone)}")
            if kind == "web":
                b_types, h_types = expect_count(before_text), expect_count(after_text)
                if h_types < b_types:
                    msg = f"{where} Expect< {b_types}→{h_types}"
                    if passed:
                        out(f"· 넘김 d {msg} (--allow-drop)")
                    else:
                        res.types += 1
                        red("d", msg)

        fresh = [(k, v) for k, v in allow.entries.items() if k not in before.entries]
        res.new_allow = len(fresh)
        out("갈래 " + " ".join(f"{g}={counts[g]}" for g in ("a", "b", "c", "d", "허용")))
        out(f"새 허용 {len(fresh)}")
        for (path, text), why in fresh:
            out(f"  + {path} | {short(text)} | {why}")
        verdict = "PASS" if res.passed else "FAIL"
        out(f"WEAKEN={verdict} red={res.red} new_allow={res.new_allow} drops={res.drops} types={res.types}")
    finally:
        if own:
            blobs.close()
    return res


def replay(repo: str, n: int, main: str, allow_text: str | None) -> int:
    started = time.monotonic()
    merges = git(repo, "rev-list", "--first-parent", "--merges", "-n", str(n), main).decode().split()
    blobs = Blobs(repo)
    red_merges = 0
    try:
        for m in merges:
            subject = git(repo, "log", "-1", "--format=%s", m).decode("utf-8", "replace").strip()
            res = check(repo, f"{m}^1", f"{m}^2", allow_text, blobs=blobs)
            if not res.passed:
                red_merges += 1
                print(f"✗ {m[:8]} {subject[:70]} red={res.red} drops={res.drops} types={res.types}")
                for line in res.lines:
                    if line.startswith("★"):
                        print(f"    {line}")
    finally:
        blobs.close()
    print(f"REPLAY red_merges={red_merges}/{len(merges)} {time.monotonic() - started:.1f}s")
    return 0


# ---------- 자기 시험 ----------

BASE_FILES = {
    "apps/api-py/tests/security/conftest.py": (
        "import pytest\n\n\n@pytest.fixture\ndef admin_only(user):\n    if user.is_admin:\n        return user\n"
        "    raise PermissionError(\"no\")\n"
    ),
    "apps/api-py/tests_integration/test_flow.py": "def test_flow():\n    result = 1\n    assert result == 1\n",
    "apps/api-py/esgapi/m/tests/test_a.py": (
        "import pytest\n\n\ndef helper():\n    return 1\n\n\ndef test_one():\n    def act():\n        return helper()\n\n"
        "    assert act() == 1\n\n\ndef test_two():\n    value = helper()\n    assert value == 1\n    assert value > 0\n"
    ),
    "apps/web/src/x/a.test.ts": (
        "import { describe, expect, it } from 'vitest';\n\ntype Expect<T extends true> = T;\n"
        "type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;\n\n"
        "describe('x', () => {\n  it('one', () => {\n    expect(1).toBe(1);\n  });\n\n  it('two', () => {\n"
        "    expect(2).toBe(2);\n  });\n\n  it.each([1, 2])('n %i', (n) => {\n    expect(n).toBeGreaterThan(0);\n  });\n});\n\ntype _T1 = Expect<Equal<1, 1>>;\ntype _T2 = Expect<Equal<2, 2>>;\n"
        "type _T3 = Expect<Equal<3, 3>>;\n"
    ),
    "apps/web/src/x/b.test.ts": (
        "import { expect, it } from 'vitest';\n\nconst FROM = /from\\s+[\"'`]([^\"'`]+)[\"'`]/g;\n\n"
        "it('b one', () => {\n  expect(FROM).toBeTruthy();\n});\n\nit('b two', () => {\n  expect(1).toBe(1);\n});\n"
    ),
    "apps/api-py/scripts/test-business.sh": "#!/usr/bin/env bash\nuv run pytest esgapi -q\n",
}
TA = "apps/api-py/esgapi/m/tests/test_a.py"
WA = "apps/web/src/x/a.test.ts"
SKIPIF = '@pytest.mark.skipif(True, reason="x")'


def _sub(old: str, new: str, path: str = TA):
    def edit(files: dict[str, str | None]) -> None:
        text = files[path]
        assert text is not None and old in text, (path, old)
        files[path] = text.replace(old, new, 1)
    return edit


def _allow(reason: str):
    def edit(files: dict[str, str | None]) -> None:
        files[ALLOW_PATH] = f"# 자기 시험\n{TA}\t{SKIPIF}\t{reason}\n"
    return edit


def _move(files: dict[str, str | None]) -> None:
    text = files[TA]
    assert text is not None
    files[TA] = None
    files["apps/api-py/esgapi/n/tests/test_a.py"] = text.replace("def test_two", "def test_deux")


def _add(path: str, text: str):
    def edit(files: dict[str, str | None]) -> None:
        files[path] = text
    return edit


SKIP_TWO = _sub("def test_two", f"{SKIPIF}\ndef test_two")
DROP_TWO = _sub("\n\ndef test_two():\n    value = helper()\n    assert value == 1\n    assert value > 0\n", "\n")

# (이름, 고침들, --allow-drop, 기대 PASS, 기대 글들)
PLANTED = [
    ("P1", [_sub("if user.is_admin:", "if user.is_admin or True:", "apps/api-py/tests/security/conftest.py")], (), False, ["★ a"]),
    ("P2", [_sub("    assert result == 1", "    if False:\n        assert result == 1", "apps/api-py/tests_integration/test_flow.py")],
     (), False, ["★ a"]),
    ("P3", [_sub("def test_one():\n", 'def test_one():\n    pytest.skip("x")\n')], (), False, ["★ a"]),
    ("P4", [SKIP_TWO], (), False, ["★ a"]),
    ("P5", [SKIP_TWO, _allow("자기 시험 — SELF=1 로 러너가 켠다")], (), True, ["new_allow=1"]),
    ("P6", [SKIP_TWO, _allow("")], (), False, ["★ 허용"]),
    ("P7", [_sub("def test_two", "@pytest.mark.xfail\ndef test_two")], (), False, ["★ a"]),
    ("P8", [_sub("def test_two():\n", "def test_two():\n    return\n")], (), False, ["★ b"]),
    ("P9", [DROP_TWO], (), False, ["★ c", "drops=1", "test_two"]),
    ("P10", [DROP_TWO], (TA,), True, ["drops=0"]),
    ("P11", [_sub("it('one'", "it.skip('one'", WA), _sub("it('two'", "it.only('two'", WA)], (), False,
     ["it.skip('one'", "it.only('two'"]),
    ("P12", [_sub("type _T2 = Expect<Equal<2, 2>>;\n", "", WA)], (), False, ["★ d", "types=1"]),
    ("P13", [_sub("pytest esgapi -q", "pytest esgapi -q --deselect x", "apps/api-py/scripts/test-business.sh")], (),
     False, ["★ a"]),
    ("P14", [_move], (), True, ["drops=0"]),
    ("P15", [_add("apps/api-py/esgapi/m/tests/support_x.py", "import pytest\n\n\ndef need():\n    pytest.skip(\"x\")\n")],
     (), False, ["★ a apps/api-py/esgapi/m/tests/support_x.py"]),
    ("P16", [_sub("def test_two():\n    value = helper()\n    assert value == 1\n    assert value > 0\n",
                  "_OFF = \'\'\'\ndef test_two():\n    value = helper()\n    assert value == 1\n    assert value > 0\n\'\'\'\n")],
     (), False, ["★ c", "test_two"]),
    ("P17", [_sub("  it('two', () => {\n    expect(2).toBe(2);\n  });\n", "  /*\n  it('two', () => {\n    expect(2).toBe(2);\n  });\n  */\n", WA)],
     (), False, ["★ c", "two"]),
    ("P18", [_sub("import pytest\n", "import pytest\nfrom pytest import mark\n"), _sub("def test_two", "@mark.skip\ndef test_two")],
     (), False, ["★ a", "@mark.skip"]),
    ("P19", [_sub("import pytest\n", "import unittest\n\nimport pytest\n"),
             _sub("def test_one():\n", 'def test_one():\n    raise unittest.SkipTest("v")\n')], (), False, ["★ a", "SkipTest"]),
    ("P20", [_sub("});\n\ntype _T1", "  it.skipIf(true)('three', () => {});\n});\n\ntype _T1", WA)], (), False, ["★ a", "skipIf"]),
    ("P21", [_sub("  it.each([1, 2])('n %i', (n) => {\n    expect(n).toBeGreaterThan(0);\n  });\n", "", WA)], (), False,
     ["★ c", "drops=1"]),
    ("P22", [_sub("\n\nit('b two', () => {\n  expect(1).toBe(1);\n});\n", "\n", "apps/web/src/x/b.test.ts")], (), False,
     ["★ c", "b two"]),
]
PASSING = [
    ("G1", [_sub("def test_two():\n", 'def test_two():\n    # pytest.skip("x")\n')], (), True, []),
    ("G2", [_sub("    assert value > 0\n", '    assert value > 0\n    code = "if entry:".replace("if entry:", "if False:")\n'
                 '    assert code\n')], (), True, []),
    ("G3", [_sub("    assert value > 0\n", "    assert value > 0\n    kept = [True]\n    assert True in kept\n")], (), True, []),
    ("G4", [_sub("    assert value > 0\n", "    assert value > 0\n\n    def act():\n        return 2\n\n    assert act() == 2\n")],
     (), True, []),
    ("G5", [_add("apps/api-py/scripts/section4-ZZ.sh", "#!/usr/bin/env bash\ngrep -c xfail x\n")], (), True, []),
    ("G6", [_sub("});\n\ntype _T1", "});\n\ntest.describe('g', () => {});\n\ntype _T1", WA)], (), True, []),
]


def self_test() -> int:
    tmp = tempfile.mkdtemp(prefix="weaken-self-")
    ident = ["-c", "user.name=self-test", "-c", "user.email=self-test@example.invalid", "-c", "commit.gpgsign=false",
             "-c", "core.hooksPath=/dev/null", "-c", "init.defaultBranch=main"]

    def g(*args: str) -> str:
        return git(tmp, *ident, *args).decode().strip()

    def write(files: dict[str, str | None]) -> None:
        for rel, text in files.items():
            p = Path(tmp, rel)
            if text is None:
                if p.exists():
                    p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    try:
        g("init", "-q")
        write(dict(BASE_FILES))
        g("add", "-A")
        g("commit", "-q", "-m", "base")
        base = g("rev-parse", "HEAD")
        tallies = {}
        for label, cases in (("PLANTED", PLANTED), ("PASSING", PASSING)):
            ok = 0
            for name, edits, drop, want_pass, wants in cases:
                g("checkout", "-q", "-f", "--detach", base)
                g("clean", "-q", "-f", "-d")
                files: dict[str, str | None] = dict(BASE_FILES)
                for edit in edits:
                    edit(files)
                write(files)
                g("add", "-A")
                g("commit", "-q", "-m", name)
                res = check(tmp, base, g("rev-parse", "HEAD"), allow_drop=drop)
                body = "\n".join(res.lines)
                good = res.passed == want_pass and all(w in body for w in wants)
                ok += good
                print(f"{'ok ' if good else 'NG '} {name} {res.lines[-1]}")
                if not good:
                    for line in res.lines:
                        print(f"      {line}")
            tallies[label] = (ok, len(cases))
        # --warn: 끝 줄은 FAIL 그대로, 종료 0 (P1 을 다시 심음)
        g("checkout", "-q", "-f", "--detach", base)
        files = dict(BASE_FILES)
        PLANTED[0][1][0](files)
        write(files)
        g("commit", "-q", "-a", "-m", "warn")
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = main(["--repo", tmp, "--warn", base, "HEAD"])
        warn_ok = code == 0 and buf.getvalue().rstrip().split("\n")[-1].startswith("WEAKEN=FAIL")
        print(f"{'ok ' if warn_ok else 'NG '} WARN P1 --warn 종료 {code}")
        for label, (ok, total) in tallies.items():
            print(f"{label}={ok}/{total}")
        print(f"WARN={'ok' if warn_ok else 'NG'}")
        return 0 if warn_ok and all(ok == total for ok, total in tallies.values()) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="시험을 끄거나 약하게 하는 꼴을 main...band 에서 잰다.")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--allow", default=None, help="허용 목록 파일(기본: 머리 트리의 scripts/test-weakening-allow.txt)")
    ap.add_argument("--allow-drop", action="append", default=[], help="(c)·(d) 줄어듦을 넘길 머리 경로 또는 지운 바닥 경로")
    ap.add_argument("--warn", action="store_true", help="끝 줄은 같고 종료 0")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--replay", type=int, default=None)
    ap.add_argument("--replay-tip", default="main", help="--replay 가 첫 부모 병합을 셀 꼭대기(기본 main)")
    ap.add_argument("base", nargs="?")
    ap.add_argument("head", nargs="?")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    try:
        repo = args.repo or git(".", "rev-parse", "--show-toplevel").decode().strip()
        allow_text = Path(args.allow).read_text(encoding="utf-8", errors="replace") if args.allow else None
        if args.replay is not None:
            if allow_text is None:
                allow_text = (Path(__file__).resolve().parent / Path(ALLOW_PATH).name).read_text(encoding="utf-8")
            return replay(repo, args.replay, args.replay_tip, allow_text)
        if not args.base or not args.head:
            ap.print_usage(sys.stderr)
            return 2
        res = check(repo, args.base, args.head, allow_text, tuple(args.allow_drop))
    except (GitError, OSError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    print("\n".join(res.lines))
    return 0 if res.passed or args.warn else 1


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        sys.exit(main(sys.argv[1:]))
