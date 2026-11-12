#!/usr/bin/env bash
# 밴드 X1b-2b(MARC-TICK-194: 이어서 재실행 resumeFromRunId·단계 산출 data·partial 의 열쇠 차례·옛 일감 길 글·
# MARC-ISSUE-177 시험 옮김)의 §4 자기검증(발주서 band-handoffs/X1b-2b-order.md §4, 개정 1).
#   사용: apps/api-py/scripts/section4-X1b-2b.sh --commit <1|2|3> [--with-containers] [--after-commit] [--step <n>]
#   --with-containers 가 없으면 컨테이너 단계(2 의 업무·보안·통합 층, 10, 13)는 「안 돌림」으로 찍고 실패로 센다.
#   --after-commit 이면 12 가 「작업 트리 0줄」을 본다(아니면 「스테이징 밖의 바뀜·새 파일 0」 — 커밋 전).
# 환경 변수: X1B2B_MSG(쓸 커밋 메시지 파일 — 12 가 키 꼴을 본다).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독 몫). AI 공급사 호출 0, 시험은 env -u OPENAI_API_KEY.
# 컨테이너는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것만 띄운다. build 는
#   scripts/with-build-lock.sh 로만. 띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
#   git grep 의 종료 ≥2 와 양성 대조 0 은 실패로 센다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE="$(git rev-parse --verify '732acf7^{commit}')" || exit 2   # 워크트리를 세운 main(merge band/G2c2)
OUT="$ROOT/../X1b-2b.out"                        # 워크트리 밖. collect-base.txt·lint-imports-base.txt 가 여기 있다
A=apps/api-py
E="$A/esgapi"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0; AFTER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --after-commit) AFTER=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3> [--step <n>] [--with-containers] [--after-commit]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac

T="$(mktemp -d /private/tmp/x1b2b.XXXXXX)"
case "$T" in /private/tmp/x1b2b.*) ;; *) exit 99 ;; esac
FAILS=0

# ── 단계 안의 파이썬(파일로 둔다 — 단계의 셸 글이 홑따옴표 안이다) ──
cat > "$T/helper.py" <<'PY'
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
COMMIT = int(sys.argv[3])
CMD = sys.argv[4]
ARGS = sys.argv[5:]
API = "apps/api-py/"
E = API + "esgapi/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def at_base(rel: str) -> str:
    return git("show", f"{BASE}:{rel}")


def now(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── 옮김(⑰ — 커밋 ③): 통째로 옮기는 둘, 쪼개 옮기는 하나 ──
WHOLE_MOVES = {
    "esgapi/core/tests/test_jobs_services.py": "esgapi/runs/tests/service/services/test_jobs.py",
    "esgapi/core/tests/service/apis/test_runs.py": "esgapi/runs/tests/service/apis/test_runs_session.py",
}
SPLIT_FROM = "esgapi/core/tests/test_selectors_tenant.py"
SPLIT_TO = "esgapi/runs/tests/service/selectors/test_jobs.py"
SPLIT_FUNCS: list[str] = [  # 옮긴 함수 여섯(BASE :186·:204·:225·:242·:270·:303)
    "test_the_lock_reads_name_the_tenant_and_lock",
    "test_a_job_is_claimed_only_under_its_tenant",
    "test_a_job_is_finished_only_under_its_tenant",
    "test_done_does_not_write_another_tenants_document",
    "test_stale_jobs_and_requeue_see_one_tenant",
    "test_every_statement_on_the_two_tables_names_the_tenant",
]
# 옮긴 함수가 쓰는 도우미·상수(복사 — ast.dump 같음). 그 가운데 core 에서 지운 것(옮긴 함수만 쓰던 것)
SPLIT_HELPERS: list[str] = ["NOW", "LEASE_S", "MAX", "BROKER", "no_enqueue", "seed", "refuse_foreign_job", "job_row",
                            "sha256_of", "claim", "pytestmark"]
SPLIT_DROPPED: list[str] = ["LEASE_S", "MAX", "BROKER", "job_row", "sha256_of", "claim"]

# ── 사라져도 되는 노드 id → 짝(새 id). 커밋마다 ──
PAIRS: dict[int, dict[str, str]] = {
    1: {},
    2: {  # §2-5 ② — 501 짝 바꿈
        "esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_create]":
            "esgapi/core/tests/service/apis/test_runs.py::test_resuming_a_missing_run_is_404_after_auth",
        "esgapi/runs/tests/service/apis/test_runs.py::test_create_refusals_write_nothing[resume-expected9]":
            "esgapi/runs/tests/service/apis/test_runs.py::test_create_refusals_write_nothing[resume_missing-expected9]",
    },
    3: {},
}


def pairs_upto(after: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    if COMMIT >= 3:
        for old, new in WHOLE_MOVES.items():
            for n in list(BEFORE):
                if n.startswith(old + "::"):
                    out[n] = new + n[len(old):]
        for n in list(BEFORE):
            if n.startswith(SPLIT_FROM + "::") and n.split("::", 1)[1].split("[")[0] in SPLIT_FUNCS:
                out[n] = SPLIT_TO + n[len(SPLIT_FROM):]
    for c in range(1, COMMIT + 1):  # 앞 커밋의 짝이 옮김보다 앞선다
        out.update(PAIRS[c])
    if COMMIT >= 3:
        # 앞 커밋의 짝이 옮긴 파일 안이면 옮긴 자리로
        for old, new in list(out.items()):
            for src, dst in WHOLE_MOVES.items():
                if new.startswith(src + "::"):
                    out[old] = dst + new[len(src):]
    return out


if CMD == "collect":
    BEFORE = set(Path(ARGS[0]).read_text().splitlines())
    after = set(Path(ARGS[1]).read_text().splitlines())
    pairs = pairs_upto(after)
    removed, added = sorted(BEFORE - after), sorted(after - BEFORE)
    bad = [n for n in removed if n not in pairs or pairs[n] not in after]
    print(f"  BASE {len(BEFORE)} · 지금 {len(after)} · 빠짐 {len(removed)}(짝 없음 {len(bad)}) · 더함 {len(added)}")
    sec_b = sum(n.startswith("tests/security/") for n in BEFORE)
    sec_a = sum(n.startswith("tests/security/") for n in after)
    print(f"    tests/security 앞 {sec_b} · 뒤 {sec_a}")
    for n in removed:
        print(f"    - {n}  →  {pairs.get(n, '★ 짝 없음')}{'' if n not in bad else '   ★'}")
    paired_new = set(pairs.values())
    for n in added:
        print(f"    + {n}{'   (짝)' if n in paired_new else ''}")
    raise SystemExit(1 if bad or sec_a < sec_b else 0)

# ── 7: 약화 대조 ──
# 지운 줄 가운데 assert·==·len(·parametrize 를 품은 것마다 (파일 끝부분, 지운 줄의 정규식, 커밋)과 짝.
WEAKEN_OK: list[tuple[str, str, int]] = [
    # ② §2-5
    ("core/tests/isolation/test_static_rules.py", r"^    assert opened == 59$", 2),  # → 60
    ("core/tests/test_transaction_rules.py", r"^    assert len\(files\) == 20, \[$", 2),  # → 21
    # ② core/tests/service/apis/test_runs.py: CONTRACT_ONLY 1 → 0 — 501 함수 지움(짝: 앞 실행 없음 404), 403 시험의 두 줄
    ("core/tests/service/apis/test_runs.py", r'parametrize\("operation_id", sorted\(CONTRACT_ONLY\)\)', 2),
    ("core/tests/service/apis/test_runs.py", r'CONTRACT_ONLY\[operation_id\]\)\) == \(501, "NOT_IMPLEMENTED"\)', 2),
    ("core/tests/service/apis/test_runs.py", r'CONTRACT_ONLY\["runs_create"\]\)\) == \(403, "FORBIDDEN"\)', 2),
    ("core/tests/service/apis/test_runs.py", r'CONTRACT_ONLY\["runs_create"\]\)\.status_code == 501', 2),
    # ② runs/tests/service/apis/test_runs.py:254 — 끝 단언 501 → (404, NOT_FOUND)
    ("runs/tests/service/apis/test_runs.py", r'^    \) == \(501, "NOT_IMPLEMENTED"\)$', 2),
]
TOKENS = re.compile(r"assert|==|len\(|parametrize")

if CMD == "weaken":
    diff = git("diff", "-M", BASE, "--", API + "esgapi/*/tests/*", API + "esgapi/*/tests/**", API + "tests")
    current = None
    hits: list[tuple[str, str]] = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current = line.split(" b/", 1)[1]
            continue
        if line.startswith("---") or not line.startswith("-"):
            continue
        if current is None or (COMMIT >= 3 and current.endswith(SPLIT_FROM)):
            continue  # 쪼개 옮긴 파일은 split-move 단계가 잰다
        text = line[1:]
        if TOKENS.search(text):
            # 통째 옮긴 파일은 옛 이름으로 짝을 찾는다(옮김 몸 0 은 rename 단계가 잰다)
            path = next((API + src for src, dst in WHOLE_MOVES.items() if current == API + dst), current)
            hits.append((path, text))
    bad = 0
    for path, text in hits:
        ok = any(path.endswith(f) and re.search(rx, text) and c <= COMMIT for f, rx, c in WEAKEN_OK)
        bad += not ok
        print(f"  {'짝' if ok else '★ 짝 없음'} {path}: {text.strip()[:140]}")
    print(f"  지운 줄(셈 낱말) {len(hits)} · 짝 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 7(커밋 ③): 쪼갠 옮김 ──
def top_level(src: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in ast.parse(src).body:
        name = getattr(n, "name", None)
        if name is None and isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            name = n.targets[0].id
        if name is not None:
            out[name] = ast.dump(n)
    return out


if CMD == "split-move":
    # 통째 옮긴 둘: 커밋 ② 의 옛 자리 바이트 = 지금 새 자리 바이트(git diff -M 몸 0), 옛 자리는 없음
    c2 = git("log", "--format=%H", "-1", "--grep", "X1b-2b ②", f"{BASE}..HEAD").strip()
    whole_bad = 0
    for src, dst in WHOLE_MOVES.items():
        same = bool(c2) and git("show", f"{c2}:{API}{src}") == now(API + dst)
        gone = not (ROOT / API / src).exists()
        whole_bad += not (same and gone)
        print(f"  통째 {src} → {dst}: 바이트 같음 {same} · 옛 자리 없음 {gone}")
    base = top_level(at_base(API + SPLIT_FROM))
    core = top_level(now(API + SPLIT_FROM))
    moved = top_level(now(API + SPLIT_TO))
    bad = 0
    for name in SPLIT_FUNCS + SPLIT_HELPERS:
        same = base.get(name) is not None and base.get(name) == moved.get(name)
        bad += not same
        print(f"  {name}: 새 파일 ast.dump {'같음' if same else '★ 다름·없음'}")
    # core 에서 사라진 것 = 옮긴 함수 + 지운 도우미뿐, 남은 것은 몸 같음
    gone = sorted(set(base) - set(core))
    want = sorted(SPLIT_FUNCS + SPLIT_DROPPED)
    changed = sorted(k for k in core if k in base and core[k] != base[k])
    extra_new = sorted(set(moved) - set(SPLIT_FUNCS) - set(SPLIT_HELPERS))
    print(f"  core 에서 사라진 것 {gone}")
    print(f"  core 에 남아 바뀐 것 {changed} · 새 파일의 군것 {extra_new}")
    planted = top_level("def f():\n    return 1\n") != top_level("def f():\n    return 2\n")
    print(f"  양성 대조(몸이 다르면 다름) {planted}")
    raise SystemExit(
        0 if not whole_bad and not bad and gone == want and not changed and not extra_new and planted else 1
    )

# ── 8: 실행기 대조 ──
if CMD == "bodies":
    rel = E + "runs/service/selectors/runs.py"
    names = {"step_output", "_step_of", "step_rows", "run_files"}

    def funcs(src: str) -> dict[str, str]:
        return {n.name: ast.dump(n) for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name in names}

    b, h = funcs(at_base(rel)), funcs(now(rel))
    for n in sorted(names):
        print(f"  {n}: BASE {'있음' if n in b else '없음'} · 같음 {b.get(n) == h.get(n)}")
    raise SystemExit(0 if len(b) == 4 and b == h else 1)

# ── 5(커밋 ③): 걷은 ignore 셋마다 양성 대조 ──
REMOVED_IGNORES = [
    "esgapi.runs.service.selectors.jobs",
    "esgapi.runs.service.services.jobs",
    "esgapi.runs.management.commands.requeue_jobs",
]
KEPT_IGNORE = "esgapi.runs.models"  # :34 — 233 이 걷는다(남음)

if CMD == "lint-positive":
    target = ROOT / API / "esgapi/core/tests/test_selectors_tenant.py"
    original = target.read_bytes()
    env = {**__import__("os").environ, "COLUMNS": "400"}

    def lint() -> str:
        done = subprocess.run(["uv", "run", "--frozen", "lint-imports", "--no-cache"], cwd=ROOT / API,
                              capture_output=True, text=True, env=env, check=False)
        return done.stdout + done.stderr

    bad = 0
    try:
        for module, want_broken in [(m, True) for m in REMOVED_IGNORES] + [(KEPT_IGNORE, False)]:
            target.write_bytes(original + f"import {module}  # noqa: E402, F401\n".encode())
            out = lint()
            broken = re.search(r"^가\. .* BROKEN\b", out, flags=re.M) is not None
            ok = broken is want_broken
            bad += not ok
            line = next((x for x in out.splitlines() if x.startswith("Contracts:")), "")
            print(f"  core 시험 + import {module} → 가 {'BROKEN' if broken else 'KEPT'}"
                  f"(기대 {'BROKEN' if want_broken else 'KEPT — 남긴 줄'}) · {line}{'' if ok else '   ★'}")
    finally:
        target.write_bytes(original)
    print(f"  되돌림 바이트 같음 {target.read_bytes() == original}")
    raise SystemExit(1 if bad or target.read_bytes() != original else 0)

# ── 3(커밋 ②): openapi ──
def leaves(x: object, path: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(x, dict):
        for k, v in x.items():
            out.update(leaves(v, f"{path}/{str(k).replace('~', '~0').replace('/', '~1')}"))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out.update(leaves(v, f"{path}/{i}"))
    else:
        out[path] = x
    return out


ALLOWED_OPENAPI = [r"^/paths/~1runs/post/responses/501/"]

if CMD == "openapi-diff":
    b = leaves(json.loads(at_base(API + "generated/openapi.json")))
    h = leaves(json.loads(now(API + "generated/openapi.json")))
    changed = sorted(k for k in set(b) | set(h) if b.get(k, "<없음>") != h.get(k, "<없음>"))
    allowed = [re.compile(p) for p in ALLOWED_OPENAPI]
    outside = [k for k in changed if not any(a.search(k) for a in allowed)]
    print(f"  바뀐 잎 {len(changed)} · 목록 밖 {len(outside)}")
    for k in changed:
        print(f"    {'+' if k not in b else '-' if k not in h else '~'} {k}{'   ★ 목록 밖' if k in outside else ''}")
    raise SystemExit(1 if outside or not changed else 0)

if CMD == "sha":
    text = (ROOT / API / "generated/openapi.json").read_bytes()
    want = (ROOT / API / "generated/api.d.ts.source-sha256").read_text().strip()
    got = hashlib.sha256(text).hexdigest()
    print(f"  openapi sha256 {got} · 적힌 값 {want}")
    raise SystemExit(0 if got == want else 1)

raise SystemExit(f"모르는 명령 {CMD}")
PY

wanted() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
step() { # <n> <설명> <셸 글>
  local n="$1" desc="$2" code
  shift 2
  echo
  echo "[$n] $desc"
  (eval "$*")
  code=$?
  echo "[$n] $desc EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
not_run() { # <n> <설명> <까닭>
  echo
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
changed() { { git diff --no-renames --name-only "$BASE"; git ls-files --others --exclude-standard; } | sort -u; }
helper() { (cd "$A" && uv run --frozen python "$T/helper.py" "$ROOT" "$BASE" "$COMMIT" "$@"); }
gate() { # 기계 문: 빌드 중 0, free ≥ 20%, 1분 부하 < 24. 60초 간격, 최대 30분.
  local tries=0 free load building
  while :; do
    building="$(ps -axo command | grep -E "^[^ ]*/?(docker|docker-compose)( .*)? (build|buildx)( |$)" | grep -v -c grep)"
    free="$(memory_pressure 2> /dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(sysctl -n vm.loadavg | awk '{print $2}')"
    if [ "$building" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 빌드 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: 빌드 중 $building · free ${free:-?}% · 부하 ${load:-?})"; return 1; }
    tries=$((tries + 1))
    sleep 60
  done
}
export -f env_value changed helper gate
export ROOT BASE OUT A E T COMMIT

echo "── 밴드 X1b-2b §4 · 커밋 $COMMIT · BASE ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"

# ── 1. 순수 층 ──
if wanted 1; then
  step 1 "순수 층 초록" '(cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$T/pure.txt" 2>&1; code=$?; tail -1 "$T/pure.txt"; exit $code)'
fi

# ── 3. 계약 ──
if wanted 3; then
  if [ "$COMMIT" = 2 ]; then
    step 3 "다시 뽑은 openapi 와 generated/openapi.json 의 cmp" '(cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi > "$T/openapi.json" 2> "$T/export.err"; code=$?; [ "$code" = 0 ] || { tail -3 "$T/export.err"; exit $code; }; cmp "$T/openapi.json" generated/openapi.json)'
    step 3 "api.d.ts.source-sha256 = openapi 의 sha256" 'helper sha'
    step 3 "openapi 의 바뀐 자리 = 처분 ⑱ 하나(runs_create 의 501 빠짐)" 'helper openapi-diff'
  else
    # ① 은 BASE 와, ③ 은 커밋 ② 와 0바이트(③ 커밋 전이면 ② = HEAD)
    step 3 "generated 0바이트(커밋 ${COMMIT})" '
      ref="$BASE"
      if [ "$COMMIT" = 3 ]; then ref="$(git log --format=%H -1 --grep "X1b-2b ②" "$BASE"..HEAD)"; [ -n "$ref" ] || { echo "  커밋 ② 를 못 찾음"; exit 1; }; fi
      git diff --quiet "$ref" -- "$A/generated"; code=$?
      new="$(git ls-files --others --exclude-standard -- "$A/generated" | wc -l | tr -d " ")"
      echo "  ${ref:0:7} 대비 git diff EXIT=$code · 새 파일 $new"; [ "$code" = 0 ] && [ "$new" = 0 ]'
  fi
fi

# ── 4. 0줄 ──
if wanted 4; then
  step 4 "0줄 경로(§1-8·§4-4)·마이그레이션 0" '
    P="apps/web packages $E/greenwash $E/reconcile $E/inventory $E/reference $E/organization $E/user $E/dataverify $E/translation $E/runs/tasks.py $E/runs/context.py $E/runs/calc $E/runs/service/services/runs.py $E/config/api.py $A/pyproject.toml $A/uv.lock compose.yaml infra docker .env.example scripts/worktree-env.sh README.md docs $A/scripts/planted-breaks.sh $A/tests_integration $A/tests/support $A/conftest.py $A/tests/conftest.py $A/tests/security/conftest.py"
    git diff --quiet "$BASE" -- $P; code=$?
    new="$(git ls-files --others --exclude-standard -- $P | wc -l | tr -d " ")"
    echo "  git diff EXIT=$code · 추적 안 된 새 파일 $new"
    # core 제품: grants.py(커밋 ③, 머리 글)밖 0줄
    core="$(changed | grep "^$E/core/" | grep -v "^$E/core/tests/" | grep -v -x -F "$E/core/isolation/grants.py")"
    [ "$COMMIT" -ge 3 ] || core="$(changed | grep "^$E/core/" | grep -v "^$E/core/tests/")"
    echo "  core 제품 바뀐 파일: [${core}]"
    mig="$(changed | grep "/migrations/")"
    echo "  migrations 바뀐 파일: [${mig}]"
    (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER=postgres://x:y@127.0.0.1:1/z uv run --frozen python manage.py makemigrations --check --dry-run > "$T/makemigrations.txt" 2>&1); mm=$?
    grep -v -E "RuntimeWarning|warnings.warn" "$T/makemigrations.txt" | sed "s/^/  makemigrations: /"
    [ "$code" = 0 ] && [ "$new" = 0 ] && [ -z "$core" ] && [ -z "$mig" ] && [ "$mm" = 0 ] && grep -q "^No changes detected$" "$T/makemigrations.txt"'
fi

# ── 5. import 계약 ──
if wanted 5; then
  step 5 "lint-imports → Contracts: 17 kept, 0 broken" '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; now="$(grep -E "^Contracts:" "$T/lint.txt" | tail -1)"; echo "  지금: $now"; [ "$code" = 0 ] && [ "$now" = "Contracts: 17 kept, 0 broken." ])'
  if [ "$COMMIT" = 3 ]; then
    step 5 "양성 대조: 걷은 ignore 셋마다 core 시험에 runs import 를 심으면 BROKEN" 'helper lint-positive'
  fi
fi

# ── 6. 시험 수·이름 ──
if wanted 6; then
  step 6 "수집한 노드 id: 사라진 것 = 짝 목록뿐(짝의 새 id 가 있다)" '
    test -s "$OUT/collect-base.txt" || { echo "  collect-base.txt 가 없다"; exit 1; }
    (cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi tests 2>&1 | grep "::" | sort > "$T/collect-now.txt")
    helper collect "$OUT/collect-base.txt" "$T/collect-now.txt"'
fi

# ── 7. 약화 대조 ──
if wanted 7; then
  step 7 "시험 diff 의 - 줄(assert·==·len(·parametrize)마다 §2-5 항목·옮김과 짝" 'helper weaken'
  if [ "$COMMIT" = 3 ]; then
    step 7 "옮김: 통째 둘은 바이트 같음, 쪼갠 test_selectors_tenant.py 는 함수·도우미마다 ast.dump 가 BASE 와 같음" 'helper split-move'
  fi
fi

# ── 8. 실행기 대조 ──
if wanted 8; then
  step 8 "step_output·_step_of·step_rows·run_files 몸의 AST = BASE · 실행기 넷 0줄" 'helper bodies'
fi

# ── 9. 빠른 게이트 ──
if wanted 9; then
  step 9 "scripts/verify.sh --fast 끝 줄 VERIFY_FAST=PASS" 'start=$(date +%s); scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; tail -1 "$T/fast.log"; echo "  $(( $(date +%s) - start ))초"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
fi

# ── 11. 허용 경로 ──
if wanted 11; then
  step 11 "BASE 대비 바뀐 파일이 §4-11 허용 목록 안(커밋까지의 몫)" '
    changed > "$T/changed.txt"
    grep -v -E \
      -e "^$E/runs/models\.py$" \
      -e "^$E/runs/tests/" \
      -e "^$A/scripts/(section4|planted-breaks)-X1b-2b\.sh$" \
      "$T/changed.txt" > "$T/outside.txt"
    if [ "$COMMIT" -ge 2 ]; then
      grep -v -E \
        -e "^$E/runs/service/(actions|apis|selectors)/runs\.py$" \
        -e "^$E/runs/service/services/resume\.py$" \
        -e "^$E/core/tests/" \
        -e "^$E/config/tests/test_api_contract\.py$" \
        -e "^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$" \
        -e "^$A/tests/security/(test_runs|test_tenant_paths)\.py$" \
        "$T/outside.txt" > "$T/outside2.txt"; mv "$T/outside2.txt" "$T/outside.txt"
    fi
    if [ "$COMMIT" -ge 3 ]; then
      grep -v -E \
        -e "^$E/core/isolation/grants\.py$" \
        -e "^$A/\.importlinter$" \
        -e "^$A/scripts/test-layout-allow\.txt$" \
        "$T/outside.txt" > "$T/outside2.txt"; mv "$T/outside2.txt" "$T/outside.txt"
    fi
    echo "  바뀐 파일 $(wc -l < "$T/changed.txt" | tr -d " ")개 · 허용 밖 $(wc -l < "$T/outside.txt" | tr -d " ")개"
    sed "s/^/    /" "$T/changed.txt"
    sed "s/^/  ★ /" "$T/outside.txt"
    [ -s "$T/changed.txt" ] && [ ! -s "$T/outside.txt" ]'
  step 11 "㉔ 제품에 data__·partial__ 열쇠 조회 0(양성 대조 1)" '
    git grep -nE "\b(data|partial)__[a-z]" -- "$E/**" ":!*/tests/*" ":!*/migrations/*" > "$T/dunder.txt"; g=$?
    printf "x = RunStepRow.objects.filter(data__size=1)\n" > "$T/plant-dunder.py"
    p="$(grep -c -E "\b(data|partial)__[a-z]" "$T/plant-dunder.py")"
    echo "  git grep EXIT=$g(1 = 없음) · $(wc -l < "$T/dunder.txt" | tr -d " ")줄 · 양성 대조 $p"
    cat "$T/dunder.txt"
    [ "$g" = 1 ] && [ "$p" = 1 ]'
fi

# ── 12. 키 꼴 0 · 작업 트리 ──
if wanted 12; then
  step 12 "diff 의 더한 줄·새 파일과 커밋 메시지에 sk- 키 꼴 0(양성 대조 1)" '
    pat="sk-[A-Za-z0-9_-]{20,}"
    a="$(git diff "$BASE" | grep "^+" | grep -c -E "$pat")"
    u=0; for f in $(git ls-files --others --exclude-standard); do u=$((u + $(grep -c -E "$pat" "$f"))); done
    b="$(git log --format=%B "$BASE"..HEAD | grep -c -E "$pat")"
    c=0; [ -n "${X1B2B_MSG:-}" ] && c="$(grep -c -E "$pat" "$X1B2B_MSG")"
    p="$(printf "sk-%s\n" AAAAAAAAAAAAAAAAAAAAAAAA | grep -c -E "$pat")"
    echo "  diff ${a}줄 · 새 파일 ${u}줄 · 커밋 메시지 ${b}줄 · 쓸 메시지(${X1B2B_MSG:-없음}) ${c}줄 · 양성 대조 ${p}"
    [ "$a$u$b$c" = 0000 ] && [ "$p" = 1 ]'
  if [ "$AFTER" = 1 ]; then
    step 12 "git status --porcelain 0줄" 'n="$(git status --porcelain | wc -l | tr -d " ")"; echo "  ${n}줄"; [ "$n" = 0 ]'
  else
    step 12 "커밋 전: 스테이징 밖의 바뀜·새 파일 0" '
      s="$(git diff --cached --name-only | wc -l | tr -d " ")"
      w="$(git status --porcelain | grep -c -v -E "^[MADR] ")"
      echo "  스테이징 ${s}파일 · 스테이징 밖 ${w}줄"; git status --porcelain | grep -v -E "^[MADR] " | sed "s/^/  ★ /"
      [ "$w" = 0 ]'
  fi
fi

# ── 2·10·13. 컨테이너 ──
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
export PROJECT

if [ "$CONTAINERS" = 1 ] && { wanted 2 || wanted 10 || wanted 13; }; then
  step "2·10" "Postgres 한 벌($PROJECT)" '
    test -n "$PROJECT" && test "$PROJECT" != esg-app || exit 1
    gate || exit 1
    docker compose up -d --wait postgres 2>&1 | tail -2; exit "${PIPESTATUS[0]}"'
fi

if wanted 2; then
  if [ "$CONTAINERS" = 1 ]; then
    step 2 "업무 층(runs·core·config·greenwash·reconcile·user)" '(cd "$A" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db esgapi/runs esgapi/core esgapi/config esgapi/greenwash esgapi/reconcile esgapi/user > "$T/business.txt" 2>&1; code=$?; tail -1 "$T/business.txt"; exit $code)'
    step 2 "보안 층 전부" '(cd "$A" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider > "$T/security.txt" 2>&1; code=$?; tail -1 "$T/security.txt"; exit $code)'
    if [ "$COMMIT" = 2 ] || [ -n "${X1B2B_INTEGRATION:-}" ]; then
      step 2 "통합 층(이미지는 with-build-lock.sh 로 짓고 compose 전부를 띄운다)" '
        gate || exit 1
        EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || exit 1
        export EDK_JWT_PUBLIC_KEY CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
        scripts/with-build-lock.sh docker compose build > "$T/build.txt" 2>&1; code=$?; tail -2 "$T/build.txt"; [ "$code" = 0 ] || exit $code
        docker compose up -d --wait > "$T/up.txt" 2>&1; code=$?; tail -3 "$T/up.txt"; [ "$code" = 0 ] || exit $code
        start=$(date +%s)
        (cd "$A" && scripts/test-integration.sh -p no:cacheprovider > "$T/integration.txt" 2>&1); code=$?
        tail -1 "$T/integration.txt"
        echo "  통합 층 $(( $(date +%s) - start ))초"; exit $code'
    else
      echo; echo "[2] 통합 층 — 커밋 ${COMMIT} 에선 안 돌림(발주서 §4-2: ② 와 보고 직전 — X1B2B_INTEGRATION=1 이면 돈다)"
    fi
  else
    not_run 2 "업무·보안·통합 층" "--with-containers 없음"
  fi
fi

# ── 10. 감싼 꼴의 크기 ──
if wanted 10; then
  if [ "$CONTAINERS" = 1 ]; then
    step 10 "감싼/맨 꼴 octet_length(시험 산출 하나)" '(cd "$A" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider -s "esgapi/runs/tests/test_models.py::test_the_wrapped_size_next_to_the_plain_one" > "$T/octets.txt" 2>&1; code=$?; grep -E "^.*OCTETS" "$T/octets.txt" | sed "s/^[.F]*/  /"; tail -1 "$T/octets.txt"; exit $code)'
  else
    not_run 10 "감싼 꼴의 크기" "--with-containers 없음"
  fi
fi

# ── 13. 심은 파손 ──
if wanted 13; then
  if [ "$CONTAINERS" = 1 ]; then
    step 13 "심은 파손(커밋 ${COMMIT} 까지의 P) PLANTED=n/n · FINGERPRINT=same" '
      "$A/scripts/planted-breaks-X1b-2b.sh" --commit "$COMMIT" --with-containers > "$T/planted.txt" 2>&1; code=$?
      grep -E "^(P[0-9]+|PLANTED=|FINGERPRINT=)" "$T/planted.txt"
      grep -q "안 돌림" "$T/planted.txt" && { echo "  ★ 안 돌린 경우가 있다"; exit 1; }
      exit $code'
  else
    not_run 13 "심은 파손" "--with-containers 없음"
  fi
fi

echo
echo "── 기록: $T"
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
