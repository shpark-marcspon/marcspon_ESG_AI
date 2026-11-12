#!/usr/bin/env bash
# 밴드 PRE1(MARC-TICK-159) §4 의 자기검증. 첫 내보내기 전 소 묶음: rehearsal.sh 걷음 · compose SESSION_SECRET 기본값 없앰 ·
# README 두 줄과 「설정」 한 문장 · .maricomrc.json 추적 뺌(커밋 ①), 낡은 머리 글(커밋 ②).
#   사용: apps/api-py/scripts/section4-PRE1.sh [--step <n>[,<n>…]] [--planted] [--compose] [--after-commit] [--msg <커밋 메시지 파일>]
#   단계마다 "[n] … EXIT=<코드>" 한 줄, 끝 줄 SECTION4_FAIL=<n>. --planted 는 심은 파손(끝 줄 PLANTED=<잡음>/<심음>,
#   FINGERPRINT=same|differ). --compose 는 13단계만(컨테이너를 띄운다), --after-commit 은 14·15단계(커밋 뒤)만.
#   --step 없이 돌리면 커밋 ① 꼴(pyproject 가 BASE 그대로)에서는 1·2·3·4·5·8·9·11·12·15, 커밋 ② 꼴에서는 13 밖 전부.
# 커밋 전에는 스테이징된 트리를 잰다(git show ":<경로>", git diff --cached). 심은 파손은 임시 인덱스(GIT_INDEX_FILE)와
# 작업 트리에 심고 원본 바이트로 되쓴다(checkout·stash 0). macOS /bin/bash 3.2 에서 돈다. 파이썬 도움 코드는 python3 -I.
# 실제 LLM 호출 0, 키 파일 0. .env 의 값은 찍지 않는다(키 이름·줄 수만).
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=d72ade2e71a6c548759967766e43ee480f4373a7
OUT="$ROOT/../PRE1.out"
NODE_BIN="$HOME/.nvm/versions/node/v22.23.1/bin"
MAIN="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
NEW_TEST=test_compose_gives_the_session_secret_no_default
mkdir -p "$OUT"

ONLY=""
PLANTED=0
COMPOSE=0
AFTER=0
MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="$2"; shift 2 ;;
    --planted) PLANTED=1; shift ;;
    --compose) COMPOSE=1; shift ;;
    --after-commit) AFTER=1; shift ;;
    --msg) MSG="$2"; shift 2 ;;
    *) echo "사용: $0 [--step <n>[,<n>…]] [--planted] [--compose] [--after-commit] [--msg <파일>]" >&2; exit 2 ;;
  esac
done

failed=0
report() {  # report <번호> <이름> <종료 코드>
  echo "[$1] $2 EXIT=$3"
  if [ "$3" != 0 ]; then failed=$((failed + 1)); fi
}
want() { case ",$ONLY," in ",,"|*",$1,"*) return 0 ;; esac; return 1; }
phase2() { ! git diff --cached --quiet "$BASE" -- apps/api-py/pyproject.toml; }
mktmp() {  # mktmp → 새 임시 폴더(경로를 단언한다)
  local d
  d="$(mktemp -d /private/tmp/pre1-s4.XXXXXX)" || return 99
  case "$d" in /private/tmp/pre1-s4.*) ;; *) return 99 ;; esac
  echo "$d"
}

# ── 파이썬 도움 코드 하나. 첫 인자가 갈래다 ──
PY_HELPER="$(mktemp -t s4pre1.XXXXXX)"
trap 'rm -f "$PY_HELPER"' EXIT
cat > "$PY_HELPER" <<'PYEOF'
import ast, re, subprocess, sys

BASE = sys.argv[2]
ARG = sys.argv[3] if len(sys.argv) > 3 else ""
C1 = [
    "apps/api-py/scripts/rehearsal.sh", "compose.yaml", ".env.example", "apps/api-py/esgapi/config/env.py",
    "apps/api-py/esgapi/config/tests/test_env.py", "README.md", "docs/development.md", ".gitignore", ".maricomrc.json",
    "apps/api-py/scripts/section4-PRE1.sh",
]
C2 = [
    "apps/api-py/pyproject.toml", "apps/api-py/esgapi/__init__.py", "apps/api-py/esgapi/core/__init__.py",
    "apps/api-py/esgapi/reference/__init__.py", "apps/api-py/esgapi/reconcile/__init__.py",
    "apps/api-py/esgapi/config/apps_list.py", "apps/api-py/.importlinter",
]
# 커밋 ① 의 줄 수(더함, 뺌). test_env.py 는 뺌만(주석 한 줄) — 더함은 시험 하나라 7 이 잰다.
LINES = {
    "compose.yaml": (2, 2), ".env.example": (1, 1), "apps/api-py/esgapi/config/env.py": (1, 1),
    "docs/development.md": (1, 1), ".gitignore": (2, 0), "README.md": (3, 1), "apps/api-py/pyproject.toml": (1, 1),
}
NUM = {1: "하나", 2: "둘", 3: "셋", 4: "넷", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열",
       11: "열하나", 12: "열둘", 13: "열셋", 14: "열넷", 15: "열다섯", 16: "열여섯", 17: "열일곱", 18: "열여덟"}
NEW_TEST = "test_compose_gives_the_session_secret_no_default"


def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True).stdout


def staged(path):
    return git("show", f":{path}")


def at_base(path):
    return git("show", f"{BASE}:{path}")


def phase2():
    return subprocess.run(["git", "diff", "--cached", "--quiet", BASE, "--", "apps/api-py/pyproject.toml"]).returncode != 0


def added_removed(path):
    out = git("diff", "--cached", "-U0", BASE, "--", path)
    add = [l[1:] for l in out.split("\n") if l.startswith("+") and not l.startswith("+++")]
    rem = [l[1:] for l in out.split("\n") if l.startswith("-") and not l.startswith("---")]
    return add, rem


def step1():
    allowed = C1 + (C2 if phase2() else [])
    changed = [p for p in git("diff", "--cached", "--name-only", BASE).split("\n") if p]
    bad = 0
    print(f"  바뀐 경로 {len(changed)}")
    for p in changed:
        if p not in allowed:
            bad += 1
            print(f"  ★ 허용 밖: {p}")
    untracked = [p for p in git("ls-files", "-o", "--exclude-standard").split("\n") if p]
    for p in untracked:
        bad += 1
        print(f"  ★ 추적 밖 새 파일(스테이징 안 됨): {p}")
    for p, (a, r) in LINES.items():
        if p not in changed:
            continue
        add, rem = added_removed(p)
        ok = (len(add), len(rem)) == (a, r)
        print(f"  {p}: +{len(add)} -{len(rem)} (기대 +{a} -{r}){'' if ok else ' ★'}")
        bad += 0 if ok else 1
    if "apps/api-py/esgapi/config/tests/test_env.py" in changed:
        add, rem = added_removed("apps/api-py/esgapi/config/tests/test_env.py")
        ok = len(rem) == 1 and rem[0].startswith("LOCAL_SECRET = ")
        print(f"  test_env.py: -{len(rem)} (기대 -1, LOCAL_SECRET 줄의 주석){'' if ok else ' ★'}")
        bad += 0 if ok else 1
    return 1 if bad else 0


STALE = [
    ("apps/api-py/pyproject.toml", "업무 모듈 여덟"),
    ("apps/api-py/esgapi/__init__.py", "계약 여섯"),
    ("apps/api-py/esgapi/__init__.py", "업무 모듈 넷"),
    ("apps/api-py/esgapi/__init__.py", "accounts"),
    ("apps/api-py/esgapi/core/__init__.py", "accounts"),
    ("apps/api-py/esgapi/reference/__init__.py", "아직 비어 있다"),
    ("apps/api-py/esgapi/reference/__init__.py", "accounts"),
    ("apps/api-py/esgapi/reconcile/__init__.py", "아직 비어 있다"),
    ("apps/api-py/esgapi/reconcile/__init__.py", "accounts"),
    ("apps/api-py/esgapi/config/apps_list.py", r"models\.py 를 만들고"),
    ("apps/api-py/.importlinter", "모듈 넷의 이름"),
]


def step6():
    bad = 0
    for path, pat in STALE:
        now = len(re.findall(pat, staged(path)))
        base = len(re.findall(pat, at_base(path)))
        ok = now == 0 and base >= 1
        print(f"  {path} 「{pat}」: 지금 {now} / BASE {base}{'' if ok else ' ★'}")
        bad += 0 if ok else 1
    dirs = [d.rsplit("/", 1)[-1] for d in git("ls-tree", "-d", "--name-only", "HEAD", "apps/api-py/esgapi/").split("\n") if d]
    mods = [d for d in dirs if d not in ("config", "core")]
    contracts = len(re.findall(r"(?m)^\[importlinter:contract:", staged("apps/api-py/.importlinter")))
    print(f"  센 값: 업무 모듈 {len(mods)}({' · '.join(mods)}), 계약 {contracts}")
    m, c = NUM.get(len(mods), "?"), NUM.get(contracts, "?")
    for path, word in [
        ("apps/api-py/esgapi/__init__.py", f"업무 모듈 {m}"),
        ("apps/api-py/esgapi/__init__.py", f"계약 {c}"),
        ("apps/api-py/pyproject.toml", f"업무 모듈 {m}"),
        ("apps/api-py/.importlinter", f"모듈 {m}의 이름"),
    ]:
        n = staged(path).count(word)
        print(f"  {path} 「{word}」: {n}{'' if n >= 1 else ' ★'}")
        bad += 0 if n >= 1 else 1
    names = " · ".join(sorted(mods))
    n = staged("apps/api-py/esgapi/__init__.py").count(names)
    print(f"  esgapi/__init__.py 의 이름 목록 「{names}」: {n}{'' if n >= 1 else ' ★'}")
    bad += 0 if n >= 1 else 1
    return 1 if bad else 0


def strip_docstrings(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return tree


def step7():
    bad = 0
    changed = [p for p in git("diff", "--cached", "--name-only", "--diff-filter=AM", BASE, "--", "*.py").split("\n") if p]
    for p in changed:
        if p.endswith("config/tests/test_env.py"):
            base = ast.parse(at_base(p)).body
            now = ast.parse(staged(p)).body
            base_names = {n.name for n in base if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
            new = [n for n in now if isinstance(n, ast.FunctionDef) and n.name not in base_names]
            rest = [ast.dump(n) for n in now if n not in new]
            ok = [n.name for n in new] == [NEW_TEST] and rest == [ast.dump(n) for n in base]
            print(f"  {p}: 더한 최상위 함수 {[n.name for n in new]}, 나머지 dump 같음 {rest == [ast.dump(n) for n in base]}{'' if ok else ' ★'}")
        else:
            same = ast.dump(strip_docstrings(ast.parse(at_base(p)))) == ast.dump(strip_docstrings(ast.parse(staged(p))))
            ok = same
            print(f"  {p}: docstring 밖 AST 같음 {same}{'' if ok else ' ★'}")
        bad += 0 if ok else 1
    print(f"  잰 .py {len(changed)}")
    if not changed:
        print("  ★ 잰 파일 0(양성 대조 0)")
        return 1
    return 1 if bad else 0


SPAN = re.compile(r"`([^`\n]+)`")
PATHLIKE = re.compile(r"\.(ya?ml|jsonl?|py|md|toml|example|sh|txt)$")
FORBID = re.compile(r"납품 전|까지 채웁|채우겠|곧|조만간|예정|완벽|강력")
MARC = re.compile(r"MARC-(RPT|ISSUE|TICK|ENT)-[0-9]+")


def section(lines, head):
    if head not in lines:
        return []
    i = lines.index(head)
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    return lines[i:j]


def path_missing(words):
    miss = []
    for w in words:
        if subprocess.run(["git", "cat-file", "-e", f"HEAD:{w}"], capture_output=True).returncode != 0:
            miss.append(w)
    return miss


def readme_paths(lines):
    out = []
    for l in lines:
        for s in SPAN.findall(l):
            if " " not in s and ("/" in s or PATHLIKE.search(s)):
                out.append(s)
    return out


def step8():
    bad = 0
    lines = staged("README.md").split("\n")
    know = section(lines, "## 알아 둘 것")
    conf = section(lines, "## 설정")
    checks = [
        ("「알아 둘 것」의 「서드파티 라이선스 목록은 정리 중」", sum("서드파티 라이선스 목록은 정리 중" in l for l in know), 1),
        ("「알아 둘 것」의 factors.kr.jsonl", sum("factors.kr.jsonl" in l for l in know), 1),
        ("README 전체의 factors.kr.jsonl", sum("factors.kr.jsonl" in l for l in lines), 1),
        ("「라이선스 조건 확인은 진행 중」", sum("라이선스 조건 확인은 진행 중" in l for l in lines), 0),
        ("「설정」의 「기본값을 두지 않습니다」", sum("기본값을 두지 않습니다" in l and "SESSION_SECRET" in l for l in conf), 1),
    ]
    base_old = at_base("README.md").count("라이선스 조건 확인은 진행 중")
    checks.append(("BASE 의 「라이선스 조건 확인은 진행 중」(양성 대조)", base_old, 1))
    for name, got, want in checks:
        print(f"  {name}: {got} (기대 {want}){'' if got == want else ' ★'}")
        bad += 0 if got == want else 1
    add = added_removed("README.md")[0] + added_removed("docs/development.md")[0]
    hits = [l for l in add if FORBID.search(l) or MARC.search(l)]
    for l in hits:
        print(f"  ★ 약속·일정 낱말 또는 번호: {l[:80]}")
    bad += len(hits)
    print(f"  더한 줄 {len(add)}, 약속·일정·번호 {len(hits)}")
    words = readme_paths(added_removed("README.md")[0])
    miss = path_missing(words)
    print(f"  README 더한 줄의 경로 {len(words)}: {', '.join(words)} / 없음 {len(miss)}")
    for w in miss:
        print(f"  ★ 없는 경로: {w}")
    bad += len(miss)
    ctrl = path_missing(readme_paths(["`apps/api-py/esgapi/reference/data/factors.kr.json`"]))
    print(f"  양성 대조(없는 경로 하나): 없음 {len(ctrl)}{'' if len(ctrl) == 1 else ' ★'}")
    bad += 0 if len(ctrl) == 1 else 1
    if not words:
        print("  ★ 잰 경로 0")
        bad += 1
    return 1 if bad else 0


def step12():
    pats = [
        re.compile("sk" + r"-[A-Za-z0-9_-]{20,}"),
        re.compile(re.escape("recei" + "ved/")),
        re.compile(re.escape("received" + "-derived/")),
        re.compile(re.escape("rec" + "ords/")),
        re.compile("LLM_[A-Z]+_API" + r"_KEY=[^ ]"),
        re.compile(re.escape("local-only-" + "session-secret")),
    ]
    bad = 0
    diff = git("diff", "--cached", BASE)
    path, base_code = None, set()
    scanned = 0
    for l in diff.split("\n"):
        if l.startswith("+++ "):
            path = l[6:] if l.startswith("+++ b/") else None
            base_code = set()
            if path:
                try:
                    base_code = {x.split("  #")[0].rstrip() for x in at_base(path).split("\n")}
                except subprocess.CalledProcessError:
                    base_code = set()
            continue
        if not l.startswith("+") or l.startswith("+++"):
            continue
        scanned += 1
        body = l[1:]
        for p in pats:
            if p.search(body):
                if body.split("  #")[0].rstrip() in base_code:
                    print(f"  (예외) {path}: 코드 부분이 BASE 와 같은 줄 — 주석만 바뀜")
                    continue
                bad += 1
                print(f"  ★ {path}: 「{p.pattern}」")
    if ARG:
        text = open(ARG, encoding="utf-8").read()
        for p in pats:
            if p.search(text):
                bad += 1
                print(f"  ★ 커밋 메시지: 「{p.pattern}」")
        print(f"  커밋 메시지 잼: {ARG}")
    print(f"  잰 더한 줄 {scanned}")
    return 1 if bad or not scanned else 0


sys.exit({"1": step1, "6": step6, "7": step7, "8": step8, "12": step12}[sys.argv[1]]())
PYEOF
py() { python3 -I "$PY_HELPER" "$1" "$BASE" "${2:-}"; }
audit() { (cd apps/api-py && uv run --frozen python scripts/readme_audit.py "$@"); }

step1() {
  py 1
  local a=$?
  git diff --cached --quiet "$BASE" -- apps/web apps/api-py/esgapi/greenwash apps/api-py/esgapi/core/auth \
    apps/api-py/esgapi/core/permissions.py apps/api-py/esgapi/core/tenancy apps/api-py/uv.lock infra scripts docker \
    services packages apps/api-py/generated
  local z=$?
  echo "  0줄 경로 diff EXIT=$z"
  git diff --cached --quiet "$BASE" -- ':(glob)apps/api-py/esgapi/*/service/apis/**'
  local s=$?
  echo "  service/apis diff EXIT=$s"
  [ "$a" = 0 ] && [ "$z" = 0 ] && [ "$s" = 0 ]
}

step2() {
  local bad=0 hits rc base_n
  if git ls-files --error-unmatch apps/api-py/scripts/rehearsal.sh >/dev/null 2>&1; then
    echo "  ★ rehearsal.sh 가 인덱스에 있다"; bad=1
  fi
  if [ -e apps/api-py/scripts/rehearsal.sh ]; then echo "  ★ rehearsal.sh 파일이 있다"; bad=1; fi
  hits="$(git grep --cached -n 'rehearsal\.sh')"
  rc=$?
  if [ "$rc" -ge 2 ]; then echo "  ★ git grep 실패 EXIT=$rc"; bad=1; fi
  local outside
  outside="$(printf '%s\n' "$hits" | grep -v -e '^apps/api-py/scripts/archive/' -e '^apps/api-py/scripts/section4\.sh:5:' \
    -e '^apps/api-py/scripts/section4-EN1\.sh:459:' -e '^apps/api-py/scripts/section4-XC\.sh:8:' \
    -e '^apps/api-py/scripts/section4-PRE1\.sh:' -e '^$')"
  echo "  rehearsal.sh 를 부르는 줄: $(printf '%s\n' "$hits" | grep -c .) / 닫힌 기록·이 스크립트 밖 $(printf '%s' "$outside" | grep -c .)"
  [ -z "$outside" ] || { printf '  ★ %s\n' "$outside"; bad=1; }
  base_n="$(git grep -n 'rehearsal\.sh' "$BASE" -- apps/api-py/scripts/rehearsal.sh | grep -c .)"
  echo "  양성 대조(BASE 의 rehearsal.sh 안): ${base_n}"
  [ "$base_n" -ge 1 ] || bad=1
  git grep -n x -- . ':!apps/api-py/scripts/rehearsal.sh' >/dev/null
  rc=$?
  echo "  없는 파일의 제외 pathspec 으로 git grep EXIT=$rc(0 이면 깨지지 않음)"
  [ "$rc" = 0 ] || bad=1
  return $bad
}

step3() {
  local bad=0 n block base_n
  n="$(git show :compose.yaml | grep -c 'local-only')"
  echo "  스테이징된 compose 의 local-only: ${n}"
  [ "$n" = 0 ] || bad=1
  block="$(git show :compose.yaml | awk '/^  api-py:$/{f=1;next} /^  migrate-py:$/{f=0} f')"
  n="$(printf '%s\n' "$block" | grep -c -E '^      SESSION_SECRET: \$\{SESSION_SECRET:\?[^}]+\}$')"
  echo "  api-py 덩어리의 \${SESSION_SECRET:?…} 줄: ${n}"
  [ "$n" = 1 ] || bad=1
  base_n="$(git show "$BASE:compose.yaml" | grep -c 'local-only')"
  echo "  양성 대조(BASE 의 local-only): ${base_n}"
  [ "$base_n" -ge 1 ] || bad=1
  return $bad
}

step4() {
  local bad=0 D rc errn
  D="$(mktmp)" || return 99
  git show :compose.yaml > "$D/compose.yaml"
  git show "$BASE:compose.yaml" > "$D/compose.base.yaml"
  grep -v '^SESSION_SECRET=' .env > "$D/env"
  echo "  .env 키 줄 $(grep -c '^[A-Z_]*=' .env), 뺀 env 키 줄 $(grep -c '^[A-Z_]*=' "$D/env")"
  env -u SESSION_SECRET docker compose -f "$D/compose.yaml" --project-directory "$ROOT" config -q >/dev/null 2>"$D/err1"
  rc=$?
  echo "  .env 그대로: config EXIT=$rc"
  [ "$rc" = 0 ] || bad=1
  env -u SESSION_SECRET docker compose -f "$D/compose.yaml" --project-directory "$ROOT" --env-file "$D/env" config -q >/dev/null 2>"$D/err2"
  rc=$?
  errn="$(grep -c SESSION_SECRET "$D/err2")"
  echo "  SESSION_SECRET 뺀 env: config EXIT=$rc, 오류 글의 SESSION_SECRET 줄 ${errn}"
  [ "$rc" != 0 ] && [ "$errn" -ge 1 ] || bad=1
  env -u SESSION_SECRET docker compose -f "$D/compose.base.yaml" --project-directory "$ROOT" --env-file "$D/env" config -q >/dev/null 2>"$D/err3"
  rc=$?
  echo "  양성 대조(BASE compose, 뺀 env): config EXIT=$rc(0 이면 기본값으로 조용히 채움)"
  [ "$rc" = 0 ] || bad=1
  case "$D" in /private/tmp/pre1-s4.*) rm -rf "$D" ;; esac
  return $bad
}

step5() {
  local f n=0 all=0
  for f in "$MAIN/.env" "$MAIN".worktrees/*/.env; do
    [ -f "$f" ] || continue
    all=$((all + 1))
    if ! grep -q '^SESSION_SECRET=' "$f"; then
      n=$((n + 1))
      echo "  SESSION_SECRET 없음: $f"
    fi
  done
  echo "  .env ${all}개 가운데 SESSION_SECRET 없는 것 ${n}개(정보)"
  return 0
}

step9() {
  local bad=0 out rc
  out="$(audit paths --rev HEAD 2>&1)"
  rc=$?
  printf '%s\n' "$out" | grep '^PATHS:'
  printf '%s\n' "$out" | grep -q '^PATHS:.*못 찾음 0$' && [ "$rc" = 0 ] || { echo "  ★ paths EXIT=$rc"; bad=1; }
  out="$(audit forward --rev HEAD 2>&1)"
  rc=$?
  printf '%s\n' "$out" | grep -E '계약 [0-9]+/[0-9]+|^FORWARD='
  printf '%s\n' "$out" | grep -q '^FORWARD=OK$' && [ "$rc" = 0 ] || { echo "  ★ forward EXIT=$rc"; bad=1; }
  out="$(bash apps/api-py/scripts/section4-README.sh --step 5 2>&1)"
  rc=$?
  printf '%s\n' "$out" | grep '^DOCREFS:'
  printf '%s\n' "$out" | grep -q '^DOCREFS:.*못 찾음 0$' && [ "$rc" = 0 ] || { echo "  ★ DOCREFS EXIT=$rc"; bad=1; }
  return $bad
}

step10() {
  local bad=0 rc d
  (cd apps/api-py && uv lock --check --offline) >/dev/null 2>&1
  rc=$?
  echo "  uv lock --check --offline EXIT=$rc"
  [ "$rc" = 0 ] || bad=1
  git diff --cached --quiet "$BASE" -- apps/api-py/uv.lock
  rc=$?
  echo "  uv.lock diff EXIT=$rc"
  [ "$rc" = 0 ] || bad=1
  d="$(git show :apps/api-py/pyproject.toml | python3 -I -c 'import tomllib,sys; print(tomllib.loads(sys.stdin.read())["project"]["description"])')"
  echo "  description: $d"
  [ "$d" = "Python(Django + django-ninja) API. 본 저장소의 바닥: config · core · 업무 모듈 여섯." ] || bad=1
  return $bad
}

step11() {
  local bad=0 rc last
  PATH="$NODE_BIN:$PATH" scripts/verify.sh --fast > "$OUT/verify-fast.txt" 2>&1
  rc=$?
  last="$(tail -n 1 "$OUT/verify-fast.txt")"
  echo "  verify.sh --fast EXIT=$rc · 끝 줄 $last · 전문 $OUT/verify-fast.txt"
  [ "$rc" = 0 ] && [ "$last" = "VERIFY_FAST=PASS" ] || bad=1
  grep -E 'Contracts: [0-9]+ kept' "$OUT/verify-fast.txt" | head -n 1 | sed 's/^/  /'
  grep -q -E 'Contracts: 15 kept, 0 broken' "$OUT/verify-fast.txt" || { echo "  ★ lint-imports 15 kept 줄 없음"; bad=1; }
  (cd apps/api-py && uv run --frozen pytest -q esgapi/config/tests/test_env.py -k "$NEW_TEST") > "$OUT/new-test.txt" 2>&1
  rc=$?
  echo "  새 시험 -k: EXIT=$rc · $(tail -n 1 "$OUT/new-test.txt")"
  [ "$rc" = 0 ] && grep -q '1 passed' "$OUT/new-test.txt" || bad=1
  return $bad
}

envkey() { grep "^$1=" .env | head -n 1 | cut -d= -f2-; }

step13() {
  local bad=0 rc proj port code n
  proj="$(envkey COMPOSE_PROJECT_NAME)"
  port="$(envkey API_PY_PORT)"
  echo "  프로젝트 ${proj} · API_PY_PORT ${port} · .env 의 SESSION_SECRET 줄 $(grep -c '^SESSION_SECRET=' .env)"
  [ -n "$proj" ] && [ -n "$port" ] || return 2
  # shellcheck disable=SC1091
  . scripts/lib/lock.sh
  container_door "$proj"
  rc=$?
  echo "  문 EXIT=$rc"
  [ "$rc" = 0 ] || return "$rc"
  scripts/with-build-lock.sh docker compose build > "$OUT/compose-build.txt" 2>&1
  rc=$?
  echo "  build EXIT=$rc · 전문 $OUT/compose-build.txt"
  [ "$rc" = 0 ] || bad=1
  if [ "$bad" = 0 ]; then
    docker compose up -d --wait > "$OUT/compose-up.txt" 2>&1
    rc=$?
    echo "  up --wait EXIT=$rc · 전문 $OUT/compose-up.txt"
    [ "$rc" = 0 ] || bad=1
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/api/healthz")"
    echo "  /api/healthz ${code}"
    [ "$code" = 200 ] || bad=1
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/api/readyz")"
    echo "  /api/readyz ${code}"
    [ "$code" = 200 ] || bad=1
    n="$(docker compose logs api-py 2>&1 | grep -c 'SESSION_SECRET 이 로컬 전용')"
    echo "  api-py 로그의 로컬 전용 경고 ${n}"
    [ "$n" -ge 1 ] || bad=1
  fi
  docker compose down -v --remove-orphans > "$OUT/compose-down.txt" 2>&1
  echo "  down EXIT=$?"
  docker image rm "${proj}/api-py:local" "${proj}/parser:local" > "$OUT/compose-rmi.txt" 2>&1
  echo "  image rm EXIT=$?"
  n="$(docker compose ls -q | grep -c "^${proj}$")"
  echo "  정리 뒤 남은 프로젝트 ${n}"
  [ "$n" = 0 ] || bad=1
  return $bad
}

step15() {  # step15 [head]
  local bad=0 n out ctx
  if [ "${1:-}" = head ]; then
    n="$(git ls-tree HEAD .maricomrc.json | grep -c .)"
    echo "  HEAD 트리의 .maricomrc.json: ${n}"
  else
    n="$(git ls-files --cached .maricomrc.json | grep -c .)"
    echo "  인덱스의 .maricomrc.json: ${n}"
  fi
  [ "$n" = 0 ] || bad=1
  n="$(git ls-tree "$BASE" .maricomrc.json | grep -c .)"
  echo "  양성 대조(BASE 트리): ${n}"
  [ "$n" = 1 ] || bad=1
  if [ -f .maricomrc.json ] && [ "$(git hash-object .maricomrc.json)" = "$(git rev-parse "$BASE:.maricomrc.json")" ]; then
    echo "  작업 트리의 파일 있음 · 내용 BASE blob 과 같음"
  else
    echo "  ★ 작업 트리의 파일이 없거나 내용이 다르다"; bad=1
  fi
  git check-ignore -q .maricomrc.json
  n=$?
  echo "  check-ignore EXIT=$n"
  [ "$n" = 0 ] || bad=1
  # 커밋 전(git rm --cached 뒤)에는 「D  」와 「!! 」 두 줄, 커밋 뒤에는 「!! 」 한 줄(critic 1, 발주서 §4-15)
  out="$(git status --porcelain --ignored -- .maricomrc.json | tr '\n' '|')"
  echo "  status --ignored: ${out}"
  # 커밋 ① 뒤(HEAD 에 이미 없다)의 커밋 전 검증도 한 줄이다
  if [ "${1:-}" = head ] || [ -z "$(git ls-tree HEAD .maricomrc.json)" ]; then
    [ "$out" = "!! .maricomrc.json|" ] || bad=1
  else
    [ "$out" = "D  .maricomrc.json|!! .maricomrc.json|" ] || bad=1
  fi
  if [ "${1:-}" = head ]; then out="$(git diff -U0 "$BASE" HEAD -- .gitignore)"; else out="$(git diff --cached -U0 "$BASE" -- .gitignore)"; fi
  n="$(printf '%s\n' "$out" | grep -c '^-[^-]')"
  echo "  .gitignore 뺀 줄 ${n}, .maricomrc.json 더한 줄 $(printf '%s\n' "$out" | grep -c '^+\.maricomrc\.json$')"
  [ "$n" = 0 ] && printf '%s\n' "$out" | grep -q '^+\.maricomrc\.json$' || bad=1
  ctx="$(maricom context 2>&1)"
  if printf '%s\n' "$ctx" | grep -q 'Project'; then
    printf '%s\n' "$ctx" | grep 'Project' | head -n 1 | sed 's/^/  maricom context: /'
    printf '%s\n' "$ctx" | grep 'Project' | grep -q '마크스폰 ESG AI 솔루션' || bad=1
  else
    echo "  maricom context: 못 잼(서버가 답하지 않음 — FAIL 로 세지 않는다): $(printf '%s\n' "$ctx" | head -n 1)"
  fi
  return $bad
}

step14() {
  local bad=0 n c
  n="$(git status --porcelain | grep -c .)"
  echo "  git status --porcelain ${n}줄"
  [ "$n" = 0 ] || bad=1
  n="$(git rev-list --count "$BASE"..HEAD)"
  echo "  BASE..HEAD 커밋 ${n}"
  [ "$n" = 2 ] || bad=1
  for c in $(git rev-list --reverse "$BASE"..HEAD); do
    local msg t miss=""
    msg="$(git log -1 --format=%B "$c")"
    for t in 'Ticket: MARC-TICK-159' 'Derives-from: MARC-ENT-273' 'Concerns: MARC-TICK-71'; do
      printf '%s\n' "$msg" | grep -qx "$t" || miss="$miss [$t]"
    done
    if printf '%s\n' "$msg" | head -n 1 | grep -q 'PRE1 ①'; then
      for t in 'Derives-from: MARC-ENT-274' 'Derives-from: MARC-ENT-275'; do
        printf '%s\n' "$msg" | grep -qx "$t" || miss="$miss [$t]"
      done
    fi
    echo "  $(git log -1 --format='%h %s' "$c" | cut -c1-60)… 빠진 트레일러:${miss:- 없음}"
    [ -z "$miss" ] || bad=1
  done
  return $bad
}

run() {  # run <번호> <이름> <함수> [인자]
  want "$1" || return 0
  "$3" "${4:-}"
  report "$1" "$2" $?
}

if [ "$PLANTED" = 1 ]; then
  fp() { { git status --porcelain; git diff; git diff --cached; git ls-files -o --exclude-standard | xargs -I{} shasum -a 256 {} 2>/dev/null; } | shasum -a 256 | cut -d' ' -f1; }
  before=$(fp)
  SAVE="$(mktmp)" || exit 99
  REAL_INDEX="$(git rev-parse --path-format=absolute --git-path index)"
  caught=0; planted=0
  plant() {  # plant <이름> <파일> <심는 파이썬 한 줄(변수 s 를 바꾼다)> <확인 명령…>
    local name="$1" file="$2" code="$3" blob
    shift 3
    mkdir -p "$SAVE/$(dirname "$file")"
    cp -p "$file" "$SAVE/$file"
    cp -p "$REAL_INDEX" "$SAVE/index"
    python3 -I -c "import sys;p=sys.argv[1];s=open(p,encoding='utf-8').read();$code;open(p,'w',encoding='utf-8').write(s)" "$file"
    blob="$(git hash-object -w "$file")"
    GIT_INDEX_FILE="$SAVE/index" git update-index --cacheinfo "100644,$blob,$file"
    planted=$((planted + 1))
    if GIT_INDEX_FILE="$SAVE/index" "$@" > "$SAVE/out.txt" 2>&1; then echo "  ★ $name: 안 빨개짐"; else caught=$((caught + 1)); echo "  $name: 빨개짐"; fi
    cp -p "$SAVE/$file" "$file"
    rm -f "$SAVE/index"
  }
  # 둘 다 빨개야 잡음이다(하나라도 통과하면 0 을 돌려 「안 빨개짐」).
  newtest() { (cd apps/api-py && uv run --frozen pytest -q esgapi/config/tests/test_env.py -k "$NEW_TEST") >/dev/null 2>&1; }
  red3t() { if step3 >/dev/null; then return 0; fi; if newtest; then return 0; fi; return 1; }
  red4t() { if step4 >/dev/null; then return 0; fi; if newtest; then return 0; fi; return 1; }
  red6() { py 6 >/dev/null; }
  red7() { py 7 >/dev/null; }
  red8() { py 8 >/dev/null; }
  red15() { step15 >/dev/null; }
  docrefs() { bash apps/api-py/scripts/section4-README.sh --step 5 >/dev/null 2>&1; }
  BASE_LINE="$(git show "$BASE:compose.yaml" | grep '^      SESSION_SECRET: ')"
  export BASE_LINE
  plant P1 compose.yaml "import os,re;s=re.sub(r'(?m)^      SESSION_SECRET: .*\$',lambda m:os.environ['BASE_LINE'],s,count=1)" red3t
  plant P2 compose.yaml "import re;s=re.sub(r'(?m)^      SESSION_SECRET: .*\$','      SESSION_SECRET: \${SESSION_SECRET}',s,count=1)" red4t
  plant P3 README.md "s=s.replace('서드파티 라이선스 목록은 정리 중입니다.','서드파티 라이선스 목록은 정리 중입니다. 납품 전까지 채웁니다.',1)" red8
  plant P4 README.md "s=s.replace('factors.kr.jsonl\`','factors.kr.json\`',1)" red8
  # P4 를 DOCREFS 에도 심어 본다(README 를 읽는가): 빨개지면 읽는다.
  cp -p README.md "$SAVE/README.md"
  python3 -I -c "import sys;p=sys.argv[1];s=open(p,encoding='utf-8').read();s=s.replace('factors.kr.jsonl\`','factors.kr.json\`',1);open(p,'w',encoding='utf-8').write(s)" README.md
  if docrefs; then echo "  P4 → DOCREFS: 안 빨개짐(DOCREFS 는 README.md 를 읽지 않는다 — 8 의 경로 대조가 잰다)"; else echo "  P4 → DOCREFS: 빨개짐(README.md 를 읽는다)"; fi
  cp -p "$SAVE/README.md" README.md
  if phase2; then
    plant P5 apps/api-py/esgapi/reconcile/__init__.py "s=s+'\nx = 1\n'" red7
    plant P6 apps/api-py/esgapi/reference/__init__.py "i=s.index('\n');s=s[:3]+'아직 비어 있다: 뒤 밴드가 채운다(뼈대는 accounts 와 같다).'+s[i:] if s.startswith('\"\"\"') else s" red6
  else
    echo "  P5 · P6: 안 심음 — 커밋 ① 꼴(pyproject 가 BASE 그대로). ② 에서 심는다"
  fi
  echo "  P7: 안 심음 — 처분 ①-가(rehearsal.sh 를 걷음)"
  plant P8 .gitignore "s=s.replace('\n.maricomrc.json\n','\n',1)" red15
  case "$SAVE" in /private/tmp/pre1-s4.*) rm -rf "$SAVE" ;; esac
  after=$(fp)
  echo "PLANTED=$caught/$planted"
  if [ "$before" = "$after" ]; then echo "FINGERPRINT=same"; else echo "FINGERPRINT=differ"; exit 1; fi
  [ "$caught" = "$planted" ]; exit $?
fi

if [ "$COMPOSE" = 1 ]; then
  ONLY=13
  run 13 "compose 를 띄워 잰다(healthz·readyz·경고)" step13
  echo "SECTION4_FAIL=$failed"
  exit $((failed > 0))
fi

if [ "$AFTER" = 1 ]; then
  ONLY=14,15
  run 14 "커밋 뒤: 작업 트리 깨끗함 · 커밋 둘 · 트레일러" step14
  run 15 "커밋 뒤: .maricomrc.json 추적 밖 · 무시됨 · 로컬 그대로" step15 head
  echo "SECTION4_FAIL=$failed"
  exit $((failed > 0))
fi

if [ -z "$ONLY" ]; then
  if phase2; then ONLY=1,2,3,4,5,6,7,8,9,10,11,12,15; else ONLY=1,2,3,4,5,8,9,11,12,15; fi
fi
s6() { py 6; }
s7() { py 7; }
s8() { py 8; }
s12() { py 12 "$MSG"; }
run 1 "허용 경로 밖 0 · 0줄 경로 diff 0" step1
run 2 "rehearsal.sh 걷음" step2
run 3 "compose 글자(local-only 0 · :? 꼴)" step3
run 4 "compose 보간(빠진 SESSION_SECRET 에 멈춤)" step4
run 5 ".env 셈(정보)" step5
run 6 "낡은 글 0 · 새 글의 수" s6
run 7 "코드 토큰 0(AST)" s7
run 8 "README 두 줄과 「설정」 문장" s8
run 9 "readme_audit paths·forward · DOCREFS" step9
run 10 "uv lock · description" step10
run 11 "게이트 verify.sh --fast · 새 시험" step11
run 12 "원본·비밀 꼴 0" s12
run 13 "compose 를 띄워 잰다(healthz·readyz·경고)" step13
run 15 ".maricomrc.json 추적 밖 · 무시됨 · 로컬 그대로" step15
echo "SECTION4_FAIL=$failed"
exit $((failed > 0))
