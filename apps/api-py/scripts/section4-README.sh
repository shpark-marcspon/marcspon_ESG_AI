#!/usr/bin/env bash
# 밴드 README(MARC-TICK-156) §4 의 자기검증. 개발 문서 docs/development.md 와 납품 README 의 백엔드 몫.
#   사용: apps/api-py/scripts/section4-README.sh [--step <n>] [--planted] [--after-commit] [--msg <커밋 메시지 파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>. --planted 는 심은 파손(끝 줄 PLANTED=<잡음>/<심음>,
#   FINGERPRINT=same|differ). --after-commit 은 12단계(커밋 뒤)만.
#   macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 heredoc 으로 python3 -I 에 넘긴다(readme_audit 는 uv run).
#
# 커밋 ① (README.md 가 BASE 그대로)에서는 1 을 「README.md diff 0」으로 갈음하고 7 은 건너뛴다(② 에서 켠다 — 표지
# `<!-- 웹 개발 글:` 이 있으면 ② 다).
# ★ 1단계(웹 블록 sha)와 7단계(READMEW 표지 수)는 이 밴드 시점의 대조다. 짝 밴드 READMEW 가 병합되면(웹 블록을 옮기고
#   표지 자리를 채우면) 영구히 빨갛다 — 그 뒤에는 돌리지 않는다(감독 처분 ⑰).
# 사실은 HEAD 트리(git ls-tree)와 작업 트리의 문서 셋에서 읽는다. 컨테이너·LLM·네트워크 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=605a199cf107390fe409557fa19ce570b82d265f
WEB_SHA=c56cbf06eb6e6aaa4ff277e37a7f6202b0d7a62ccc9d9d0b21f8299f28d7f71f
GW_SHA=b2209fd2417e14b5a67efd21190b99462488f9fe2412ecbc38f1fe2837b0d499
TSV="$ROOT/../README.out/dropped.tsv"
MARK='<!-- 웹 개발 글:'
NODE_BIN="$HOME/.nvm/versions/node/v22.23.1/bin"

ONLY=""
PLANTED=0
AFTER=0
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) PLANTED=1; shift ;;
    --after-commit) AFTER=1; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>] [--planted] [--after-commit] [--msg <파일>]" >&2; exit 2 ;;
  esac
done

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
phase2() { grep -qF -- "$MARK" README.md; }

# ── 파이썬 도움 코드 하나. 첫 인자가 갈래다 ──
PY_HELPER="$(mktemp -t s4readme.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import ast, json, re, subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
BASE = sys.argv[2]
MARK = "<!-- 웹 개발 글:"
GW_HEAD = "### 그린워싱 (greenwash)"
DOC = "docs/development.md"
INV = "apps/api-py/esgapi/inventory/README.md"
DOCSTRING_ONLY = [
    "apps/api-py/esgapi/core/calc/guards.py",
    "apps/api-py/esgapi/reference/calc/__init__.py",
    "apps/api-py/esgapi/reference/calc/electricity.py",
    "apps/api-py/esgapi/reference/tests/test_electricity.py",
    "apps/api-py/esgapi/reference/tests/test_calc_is_pure.py",
    "apps/api-py/esgapi/config/celery.py",
    "apps/api-py/esgapi/core/tests/test_celery_conf.py",
]


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def lines_of(path):
    return (ROOT / path).read_text(encoding="utf-8").split("\n")


def drop_gw(lines):
    """그린워싱 소절(머리부터 다음 ### 앞까지)을 뺀다(critic 1 B1: §4-4·4-5·4-9 대상 밖)."""
    if GW_HEAD not in lines:
        return lines
    s = lines.index(GW_HEAD)
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("### ")), len(lines))
    return lines[:s] + [""] * (e - s) + lines[e:]


def readme_body():
    lines = lines_of("README.md")
    marks = [i for i, l in enumerate(lines) if l.startswith(MARK)]
    return lines[: marks[0]] if marks else None


def targets():
    """(이름, 줄들). 줄 번호는 1부터 그대로 남긴다(뺀 줄은 빈 줄로)."""
    out = [(DOC, drop_gw(lines_of(DOC))), (INV, lines_of(INV))]
    body = readme_body()
    if body is not None:
        out.append(("README.md(납품 본문)", body))
    return out


STALE = [
    ("inventory 옛 자리", r"inventory/calc/|inventory\.calc\b|(?<!tools[/.])xlsx_reader|(?<!tools[/.])scope3_sheets|inventory/flows/(shapes|scope12|scope3)\.py"),
    ("TS 뼈대", r"apps/server|packages/(core|db)\b|tests/integration|\bHono\b|BullMQ|drizzle|ioredis|--profile ts|test:integration|X-Tenant-Id|server\.Dockerfile|18080"),
    ("Redis", r"\bRedis\b|REDIS_URL|redis-cli"),
    ("registry", r"core/registry\.py|registry\.make|make\(포트"),
    ("accounts", r"(?<![\w.])accounts/|esgapi\.accounts|`accounts`"),
    ("쿠키 세션 길", r"esg_session|-[bc] /tmp/[^ ]*cookies|\.cookies\b"),
    ("파서 옛 갈래", r"sourceUrl|\b30000\b|TS worker"),
    ("접두 없는 호스트 경로·API_PY=", r"localhost:[0-9]+/(healthz|readyz|me|users|sites|auth|inventory|reference|documents|runs|greenwash)\b|API_PY=(?!\S*/api\b)"),
]
# 예외(파일:줄 → 까닭). 다섯 줄 이하.
EXCEPT = {}


def step4():
    base = git("show", f"{BASE}:README.md").split("\n")
    keep = [l if (1 <= n <= 318 or 1186 <= n <= 2072) and not (1845 <= n <= 1861) else "" for n, l in enumerate(base, 1)]
    bad = 0
    for name, pat in STALE:
        rx = re.compile(pat)
        b = sum(1 for l in keep if rx.search(l))
        hits = [(t, n, l) for t, lines in targets() for n, l in enumerate(lines, 1) if rx.search(l) and f"{t}:{n}" not in EXCEPT]
        for t in DOCSTRING_ONLY:
            hits += [(t, n, l) for n, l in enumerate(lines_of(t), 1) if rx.search(l) and f"{t}:{n}" not in EXCEPT]
        print(f"  {name}: BASE {b} → HEAD {len(hits)}" + ("" if b else "  ★ 양성 대조 0"))
        for t, n, l in hits:
            print(f"    ★ {t}:{n}: {l.strip()[:110]}")
        bad += len(hits) + (0 if b else 1)
    print(f"  예외 {len(EXCEPT)}줄")
    return 1 if bad else 0


# ── 5. DOCREFS ──
sys.path.insert(0, str(ROOT / "apps/api-py/scripts"))
import readme_audit as ra  # noqa: E402

SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
HTTP = re.compile(r"\b(GET|POST|PUT)\b[ ·`]*(/[A-Za-z0-9_\-/.{}]*)")
EXTRA_HTTP = {"/api/docs", "/api/openapi.json", "/parse", "/", "/api"}
# inventory/README.md(이 밴드는 :80~84 만 고친다)는 모듈 폴더 기준과 축 폴더 기준으로 적었다.
INV_PREFIXES = [
    "apps/api-py/esgapi/inventory/",
    "apps/api-py/esgapi/inventory/engines/",
    "apps/api-py/esgapi/inventory/tests/engines/",
]
INV_EXCUSED = {
    "outputs/": "「출력 폴더 outputs/ 는 없다」고 적은 자리(다음 판이 세운다)",
    "test_calc.py": "「같은 이름 test_calc.py 가 여럿」이라고 적은 자리",
    "scope3-classify/1.md": "prompts/ 안의 이름이라고 같은 칸이 말한다",
    "scope3-recommend/1.md": "prompts/ 안의 이름이라고 같은 칸이 말한다",
}
SETTINGS_KEYS = {"WEB_DIST_DIR": "apps/api-py/esgapi/config/settings/base.py"}


def fences(lines):
    inside, prose, fenced = False, [], []
    for l in lines:
        if l.lstrip().startswith("```"):
            inside = not inside
            continue
        (fenced if inside else prose).append(l)
    return prose, fenced


def slug(head):
    s = head.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def step5():
    # 작업 트리의 파일(추적 + 추적 밖 새 파일). 커밋 뒤에는 HEAD 트리와 같다(12 의 porcelain 0).
    head_tree = set(git("ls-files", "-c", "-o", "--exclude-standard").split("\n")) - {""}
    entries = set()
    for p in head_tree:
        parts = p.split("/")
        entries.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    http_paths = {p for _, p, _ in ra.operations("HEAD")}
    env_text = "".join((ROOT / f).read_text(encoding="utf-8") for f in ("apps/api-py/esgapi/config/env.py", ".env.example", "compose.yaml"))
    code_text = "".join(
        (ROOT / f).read_text(encoding="utf-8") for f in head_tree if f.startswith("apps/api-py/esgapi/") and f.endswith(".py") and "/tests/" not in f
    )
    found = excused = missing = 0

    def miss(msg):
        nonlocal missing
        missing += 1
        print(f"  ★ 못 찾음: {msg}")

    for name, lines in targets():
        fname = "README.md" if name.startswith("README.md") else name
        here = str(Path(fname).parent) + "/" if "/" in fname else ""
        prefixes = ["", "apps/api-py/", "apps/api-py/esgapi/"] + (INV_PREFIXES if name == INV else [])
        prose, fenced = fences(lines)
        words = set()
        for l in prose:
            for s in SPAN.findall(l):
                for w in s.split():
                    w = w.strip("\"'(),;:").split("?")[0]
                    if "/" in w or w.endswith(ra.PATH_END):
                        words.add(w)
        # (a) 경로 꼴 낱말
        for w in sorted(words):
            if w.startswith("/"):
                continue
            bare = re.sub(r"(::\w+|:[0-9]+)$", "", w).rstrip("/")
            if any(p + bare in entries for p in prefixes):
                found += 1
            elif name == INV and "/" not in bare and len([f for f in head_tree if f.startswith(INV_PREFIXES[0]) and f.endswith("/" + bare)]) == 1:
                found += 1
            elif name == INV and w in INV_EXCUSED:
                excused += 1
                print(f"  표: {name} {w} — {INV_EXCUSED[w]}")
            elif any(re.match(shape, w) for shape, _ in ra.OUTSIDE):
                excused += 1
            else:
                miss(f"{name} (a) {w}")
        # (a) 링크
        for l in prose:
            for t in LINK.findall(l):
                if t.startswith(("http://", "https://", "#")):
                    continue
                path = str((Path(here) / t.split("#")[0]).as_posix())
                norm = str(Path(path).resolve().relative_to(ROOT)) if (ROOT / path).exists() else path
                (found := found + 1) if norm.rstrip("/") in entries else miss(f"{name} (a 링크) {t}")
        # (b) HTTP
        cands = {p for l in lines for _, p in HTTP.findall(l)} | {s.split("?")[0] for l in prose for s in SPAN.findall(l) if s.startswith("/") and " " not in s}
        for p in sorted(cands):
            q = p.rstrip(".")
            core = q.removeprefix("/api") or "/"
            if q in EXTRA_HTTP or core in http_paths or q in http_paths:
                found += 1
            else:
                miss(f"{name} (b) {p}")
        # (c) manage.py 명령
        for l in fenced:
            for c in re.findall(r"manage\.py ([a-z_]+)", l):
                ok = any(re.fullmatch(rf"apps/api-py/esgapi/\w+/management/commands/{c}\.py", f) for f in head_tree)
                (found := found + 1) if ok else miss(f"{name} (c) manage.py {c}")
        # (d) 스크립트
        for l in fenced:
            for s in re.findall(r"(?<![\w/.-])((?:apps/[\w-]+/)?scripts/[\w.-]+)", l):
                ok = any(p + s in head_tree for p in ("", "apps/api-py/"))
                (found := found + 1) if ok else miss(f"{name} (d) {s}")
        # (e) 환경 변수 표·설정 표
        sect = None
        for l in lines:
            if l.startswith("#"):
                sect = l
            if sect and ("환경 변수" in sect or sect.strip() == "## 설정") and l.startswith("|"):
                for k in re.findall(r"`([A-Z][A-Z0-9_]*(?:_[A-Z0-9*]+)*\*?)`", l):
                    if k in SETTINGS_KEYS:
                        found += 1
                        continue
                    ok = (k.rstrip("*") in env_text) if k.endswith("*") else re.search(rf"\b{re.escape(k)}\b", env_text)
                    (found := found + 1) if ok else miss(f"{name} (e) {k}")
        # (f) 오류 표의 code
        sect = None
        for l in lines:
            if l.startswith("#"):
                sect = l
            if sect and "오류" in sect and l.startswith("|"):
                for c in re.findall(r"`([A-Z][A-Z0-9_]+)`", l):
                    ok = f'"{c}"' in code_text or f'"{c.lower()}"' in code_text
                    (found := found + 1) if ok else miss(f"{name} (f) {c}")
        # (g) 앵커
        heads = {slug(l.lstrip("#")) for l in lines if l.startswith("#")}
        for l in prose:
            for a in re.findall(r"\]\(#([^)]+)\)", l):
                (found := found + 1) if a in heads else miss(f"{name} (g) #{a}")
    print(f"  표에 있음 {excused}")
    print(f"DOCREFS: 찾음 {found} / 표 {excused} / 못 찾음 {missing}")
    return 1 if missing else 0


TOC = ["## 무엇인가", "## 구조", "## 갈아끼우는 구조", "## 빠른 시작", "## 설정", "## API", "## 의존성", "## 문서", "## 알아 둘 것"]


def step7():
    body = readme_body()
    if body is None:
        print("  README.md 에 표지가 없다(커밋 ① 꼴) — 7 은 ② 에서 켠다")
        return 0
    bad = 0
    heads = [l for l in body if l.startswith("## ")]
    if not (body and body[0].startswith("# ")):
        print("  ★ 첫 줄이 # 머리가 아니다"); bad += 1
    if heads != TOC:
        print(f"  ★ 목차 머리: {heads}"); bad += 1
    sect = None
    for n, l in enumerate(body, 1):
        if l.startswith("## "):
            sect = l
        for m in re.findall(r"MARC-(?:RPT|ISSUE|TICK|ENT)-[0-9]+", l):
            if sect != "## 알아 둘 것":
                print(f"  ★ 내부 번호 {m} — README.md:{n}"); bad += 1
        for w in re.findall(r"곧|조만간|예정일|완벽|강력|자동으로 다|예정|협의 중|합의 전|사업계획서|1차 범위|지라|주기로|알려 드립|뒤 만듭니다|확인 필요", l):
            print(f"  ★ 낱말 「{w}」 — README.md:{n}: {l.strip()[:80]}"); bad += 1
    marks = [n for n, l in enumerate(body, 1) if l.strip() == "<!-- READMEW 가 채운다 -->"]
    print(f"  READMEW 표지 {len(marks)} (기대 2): 줄 {marks}")
    if len(marks) != 2:
        bad += 1
    print(f"  목차 머리 {len(heads)}/9")
    return 1 if bad else 0


def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                node.body[0] = ast.Pass()
    return ast.dump(tree)


def step8():
    changed = [f for f in git("diff", "--name-only", BASE).split("\n") if f.endswith(".py")]
    bad = 0
    for f in changed:
        if f.endswith("scripts/readme_audit.py"):
            continue
        old = strip_docstrings(ast.parse(git("show", f"{BASE}:{f}")))
        new = strip_docstrings(ast.parse((ROOT / f).read_text(encoding="utf-8")))
        same = old == new
        print(f"  {f}: {'AST 같음' if same else '★ AST 다름'}")
        bad += 0 if same else 1
    print(f"  바뀐 .py(readme_audit 밖) {len(changed) - sum(f.endswith('readme_audit.py') for f in changed)}")
    return 1 if bad else 0


NUM = re.compile(r"[0-9]+(\.[0-9]+)? ?(%|USD|\$|원|kgCO2|tCO2|MJ|GWP)|단가")


def step9():
    diff = git("diff", "-U0", BASE, "--", "README.md", DOC) + "".join(
        "".join("+" + l + "\n" for l in lines_of(f)) for f in [f for f in git("ls-files", "-o", "--exclude-standard").split("\n") if f == DOC]
    )
    gw = set(drop_gw_lines())
    n = 0
    for l in diff.split("\n"):
        if l.startswith("+") and not l.startswith("+++") and NUM.search(l) and l[1:] not in gw:
            n += 1
            print(f"  수치 줄: {l[1:].strip()[:140]}")
    print(f"  수치 줄 {n} (출처 판정은 보고의 표)")
    return 0


def drop_gw_lines():
    lines = lines_of(DOC)
    if GW_HEAD not in lines:
        return []
    s = lines.index(GW_HEAD)
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("### ")), len(lines))
    return [l for l in lines[s:e] if l.strip()]


def step11():
    msg = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    text = git("diff", BASE)
    # 이 스크립트 자신은 뺀다: 찾는 꼴을 글자로 품는다.
    self_path = "apps/api-py/scripts/section4-README.sh"
    untracked = [f for f in git("ls-files", "-o", "--exclude-standard").split("\n") if f and f != self_path]
    text = git("diff", BASE, "--", ".", f":(exclude){self_path}")
    added = [l for l in text.split("\n") if l.startswith("+")] + [l for f in untracked for l in lines_of(f)]
    if msg:
        added += Path(msg).read_text(encoding="utf-8").split("\n")
    bad = 0
    for name, pat in [("키 꼴", r"sk-[A-Za-z0-9_-]{20,}"), ("받은 자료", r"(?<![\w-])(received/|received-derived/|records/)"), ("LLM 키 값", r"LLM_[A-Z]+_API_KEY=[^ \s]")]:
        hits = [l for l in added if re.search(pat, l)]
        print(f"  {name}: {len(hits)}")
        for l in hits[:5]:
            print(f"    ★ {l.strip()[:100]}")
        bad += len(hits)
    print(f"  커밋 메시지: {'봄' if msg else '없음(--msg 로 준다)'}")
    return 1 if bad else 0


print_ = None
sys.exit({"4": step4, "5": step5, "7": step7, "8": step8, "9": step9, "11": step11}[sys.argv[1]]())
PYEOF

py() { python3 -I "$PY_HELPER" "$1" "$BASE" "${2:-}"; }
audit() { (cd apps/api-py && uv run --frozen python scripts/readme_audit.py "$@"); }

step1() {
  if ! phase2; then
    git diff --quiet "$BASE" -- README.md
    local c=$?
    echo "  커밋 ① 꼴: README.md diff 0 으로 갈음 (diff EXIT=$c)"
    return $c
  fi
  local got neg
  got=$(awk -v m="$MARK" 'f{print} index($0,m)==1{f=1}' README.md | shasum -a 256 | cut -d' ' -f1)
  neg=$(git show "$BASE:README.md" | awk -v m="$MARK" 'f{print} index($0,m)==1{f=1}' | shasum -a 256 | cut -d' ' -f1)
  echo "  표지 뒤 sha256 $got (기대 $WEB_SHA)"
  echo "  양성 대조: BASE 에 같은 자르기 → $neg (표지가 없어 빈 입력 — 기대와 달라야 한다)"
  [ "$got" = "$WEB_SHA" ] && [ "$neg" != "$WEB_SHA" ]
}

ALLOWED='^(README\.md|docs/development\.md|apps/api-py/scripts/readme_audit\.py|apps/api-py/scripts/section4-README\.sh|apps/api-py/esgapi/inventory/README\.md|apps/api-py/esgapi/core/calc/guards\.py|apps/api-py/esgapi/reference/calc/__init__\.py|apps/api-py/esgapi/reference/calc/electricity\.py|apps/api-py/esgapi/reference/tests/test_electricity\.py|apps/api-py/esgapi/reference/tests/test_calc_is_pure\.py|apps/api-py/esgapi/config/celery\.py|apps/api-py/esgapi/core/tests/test_celery_conf\.py)$'

step2() {
  local bad=0 c outside untracked hunks
  git diff --quiet "$BASE" -- apps/web services infra packages compose.yaml docker .dockerignore scripts .env.example \
    apps/api-py/generated apps/api-py/esgapi/greenwash apps/api-py/esgapi/core/llm/data apps/api-py/pyproject.toml \
    apps/api-py/uv.lock apps/api-py/.importlinter
  c=$?
  echo "  0줄 경로 diff EXIT=$c"; [ $c = 0 ] || bad=1
  outside=$( { git diff --name-only "$BASE"; git ls-files -o --exclude-standard; } | grep -Ev "$ALLOWED")
  echo "  허용 경로 밖(추적 diff + 추적 밖 새 파일): $(printf '%s' "$outside" | grep -c .)"
  [ -z "$outside" ] || { echo "$outside" | sed 's/^/    ★ /'; bad=1; }
  c=$( { git diff --name-only "$BASE" -- apps/api-py/scripts; git ls-files -o --exclude-standard apps/api-py/scripts; } | grep -Ev 'scripts/(readme_audit\.py|section4-README\.sh)$' | grep -c .)
  echo "  apps/api-py/scripts 안의 다른 파일: $c"; [ "$c" = 0 ] || bad=1
  hunks=$(git diff -U0 "$BASE" -- apps/api-py/esgapi/inventory/README.md | grep '^@@')
  echo "  inventory/README.md 덩이: ${hunks:-없음}"
  if [ -n "$hunks" ] && ! echo "$hunks" | awk '{split($2,a,/[-,]/); s=a[2]; n=(a[3]==""?1:a[3]); if (s<80 || s+n-1>84) bad=1} END{exit bad}'; then
    echo "  ★ inventory/README.md 가 :80~84 밖을 고쳤다"; bad=1
  fi
  return $bad
}

step3() {
  local got base
  got=$(awk '/^### 그린워싱 \(greenwash\)$/{f=1} f&&/^### /&&!/^### 그린워싱/{exit} f' docs/development.md | shasum -a 256 | cut -d' ' -f1)
  base=$(git show "$BASE:README.md" | sed -n '1845,1861p' | shasum -a 256 | cut -d' ' -f1)
  echo "  development.md 소절 $got · BASE :1845~1861 $base (기대 $GW_SHA)"
  [ "$got" = "$GW_SHA" ] && [ "$base" = "$GW_SHA" ]
}

step6() {
  local bad=0 out c
  out=$(audit paths --rev HEAD); c=$?
  echo "  $(echo "$out" | tail -1) (EXIT=$c, BASE 못 찾음 42)"; echo "$out" | grep '★' | sed 's/^/    /'
  [ $c = 0 ] || bad=1
  out=$(audit forward --rev HEAD); c=$?
  echo "$out" | sed 's/^/  /'; [ $c = 0 ] || bad=1
  if [ -f "$TSV" ]; then
    out=$(audit compare "$BASE" "$TSV"); c=$?
    echo "$out" | sed 's/^/  /'; [ $c = 0 ] || bad=1
    echo "  tsv $TSV $(grep -c . "$TSV")줄"
  else
    echo "  ★ tsv 없음: $TSV"; bad=1
  fi
  out=$(audit facts HEAD); c=$?
  echo "  facts EXIT=$c · inventory/calc 행 $(echo "$out" | grep -c '| inventory/calc |') · 빈 값 행 $(echo "$out" | grep -c '|  |')"
  [ $c = 0 ] || bad=1
  echo "$out" | grep -q '| inventory/calc |' && bad=1
  echo "$out" | grep -q '|  |' && bad=1
  return $bad
}

step10() {
  local out c
  out=$(PATH="$NODE_BIN:$PATH" scripts/verify.sh --fast 2>&1); c=$?
  echo "$out" | grep -E 'EXIT=[1-9]' | sed 's/^/  ★ /'
  echo "  $(echo "$out" | tail -1)"
  [ $c = 0 ] && echo "$out" | tail -1 | grep -q '^VERIFY_FAST=PASS$'
}

step12() {
  local bad=0 n h
  n=$(git status --porcelain | grep -c .)
  echo "  git status --porcelain ${n}줄"; [ "$n" = 0 ] || bad=1
  n=$(git rev-list --count "$BASE"..HEAD)
  echo "  BASE 뒤 커밋 $n (기대 3: ① ② 와 병합 전 리뷰 고침 ③)"; [ "$n" = 3 ] || bad=1
  for h in $(git rev-list "$BASE"..HEAD); do
    for t in Ticket Concerns Derives-from; do
      if ! git log -1 --format=%B "$h" | grep -q "^$t: MARC-"; then echo "  ★ $h 에 $t 없음"; bad=1; fi
    done
  done
  return $bad
}

run() {  # run <번호> <이름> <함수>
  want "$1" || return 0
  "$3"
  report "$1" "$2" $?
}

if [ "$PLANTED" = 1 ]; then
  fp() { { git status --porcelain; git diff; git ls-files -o --exclude-standard | xargs -I{} shasum -a 256 {} 2>/dev/null; } | shasum -a 256 | cut -d' ' -f1; }
  before=$(fp)
  SAVE="$(mktemp -d -t s4plant.XXXXXX)"
  caught=0; planted=0
  save() { mkdir -p "$SAVE/$(dirname "$1")"; cp -p "$1" "$SAVE/$1"; }
  restore() { cp -p "$SAVE/$1" "$1"; }
  plant() {  # plant <이름> <파일> <심는 파이썬 한 줄(변수 s 를 바꾼다)> <확인 명령…>
    local name="$1" file="$2" code="$3"; shift 3
    save "$file"
    python3 -I -c "import sys;p=sys.argv[1];s=open(p,encoding='utf-8').read();$code;open(p,'w',encoding='utf-8').write(s)" "$file"
    planted=$((planted + 1))
    if "$@" > "$SAVE/out.txt" 2>&1; then echo "  ★ $name: 안 빨개짐"; else caught=$((caught + 1)); echo "  $name: 빨개짐"; fi
    restore "$file"
  }
  # 둘 다 빨개야 잡음이다(하나라도 통과하면 0 을 돌려 「안 빨개짐」).
  red4and6() { if py 4 >/dev/null; then return 0; fi; if audit paths --rev HEAD >/dev/null; then return 0; fi; return 1; }
  red4and5() { if py 4 >/dev/null; then return 0; fi; if py 5 >/dev/null; then return 0; fi; return 1; }
  red6fwd() { audit forward --rev HEAD >/dev/null; }
  red3() { step3 >/dev/null; }
  red6cmp() { audit compare "$BASE" "$TSV" >/dev/null; }
  red4() { py 4 >/dev/null; }
  red8() { py 8 >/dev/null; }
  red1() { step1 >/dev/null; }
  red7() { py 7 >/dev/null; }
  plant P1 docs/development.md "s=s.replace('## Python API (apps/api-py)\n','## Python API (apps/api-py)\n\n\`esgapi/inventory/calc/\`\n',1)" red4and6
  plant P2 docs/development.md "s=s+'\n\`apps/server/src/api.ts\`\n'" red4and5
  plant P3 docs/development.md "s=''.join(l for l in s.splitlines(True) if not (l.startswith('| POST |') and '\`/auth/login\`' in l))" red6fwd
  plant P5 docs/development.md "i=s.index('### 그린워싱 (greenwash)');s=s[:i+40]+('가' if s[i+40]!='가' else '나')+s[i+41:]" red3
  plant P6 "$TSV" "s=''.join(s.splitlines(True)[1:])" red6cmp
  plant P8 apps/api-py/esgapi/core/calc/guards.py "s=s+'\nx = 1\n'" red8
  if phase2; then
    plant P4 README.md "i=s.index('$MARK');j=s.index('\n',i)+50;s=s[:j]+('A' if s[j]!='A' else 'B')+s[j+1:]" red1
    plant P7 README.md "i=s.index('$MARK');s=s[:i]+'curl -s http://localhost:18081/healthz\n\n'+s[i:]" red4
    plant P9 README.md "i=s.index('## 무엇인가');s=s[:i]+'MARC-TICK-1\n\n'+s[i:]" red7
  else
    echo "  P4 · P7 · P9: 안 심음 — README.md 가 커밋 ① 꼴(표지 없음). ② 에서 심는다"
  fi
  rm -rf "$SAVE"
  after=$(fp)
  echo "PLANTED=$caught/$planted"
  if [ "$before" = "$after" ]; then echo "FINGERPRINT=same"; else echo "FINGERPRINT=differ"; exit 1; fi
  [ "$caught" = "$planted" ]; exit $?
fi

if [ "$AFTER" = 1 ]; then
  ONLY=12
  run 12 "커밋 뒤: 작업 트리 깨끗함 · 커밋 셋 · 트레일러" step12
  echo "SECTION4_FAIL=$failed"
  exit $((failed > 0))
fi

s1() { step1; }
s4() { py 4; }
s5() { py 5; }
s7() { py 7; }
s8() { py 8; }
s9() { py 9; }
s11() { py 11 "$MSG"; }
run 1 "웹 범위 바이트 그대로" s1
run 2 "0줄 경로 diff 0 · 허용 경로 밖 0" step2
run 3 "그린워싱 소절 바이트 같음" step3
run 4 "낡은 글 0줄" s4
run 5 "문서가 가리키는 것이 있다(DOCREFS)" s5
run 6 "readme_audit paths·forward·compare·facts" step6
run 7 "납품 README 의 꼴" s7
run 8 "코드 토큰 0(AST)" s8
run 9 "수치 줄 목록" s9
run 10 "게이트 verify.sh --fast" step10
run 11 "원본·비밀 꼴 0" s11
echo "SECTION4_FAIL=$failed"
exit $((failed > 0))
