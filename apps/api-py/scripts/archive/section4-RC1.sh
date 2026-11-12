#!/usr/bin/env bash
# 밴드 RC1 의 §4 자기검증(발주서 band-handoffs/RC1-order.md §4 — RF1 의 section4-RF1.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝에 SECTION4_FAIL=<n>. 경계는 둘이다.
# 사용(어디서든):
#   apps/api-py/scripts/section4-RC1.sh <1|2> --with-containers                 전부
#   apps/api-py/scripts/section4-RC1.sh <1|2> --step 1,2,3 --with-containers    고른 단계만
#   --with-containers   9 의 심은 파손에서 업무 층의 것도 심는다(없으면 「안 돌림」 줄이 생겨 9 가 실패한다)
#
# 단계(§4): 1 순수 · 2 업무(core·runs + 모듈 이어 돌기 시험)·보안(tests/security/test_runs·test_tenant_paths) ·
#   3 이어 돌기 겉 응답 바이트 BASE = HEAD(201·404 둘·409 둘·422·400 — id 만 가린 몸·상태·머리) · 4 generated 다시 뽑아
#   0바이트 차이 · 5 lint-imports kept = BASE · 6 makemigrations --check(0) · 7 수집(빠짐 = 그 경계의 걷은 시험 표) ·
#   8 약화 대조(- 줄의 assert·== 가 §2-2 표의 항목과 짝) · 9 심은 파손(① 10/10 · ② 14/14 — P14 는 검증 R1) · 10 verify.sh --fast ·
#   11 바뀐 경로 ⊆ 허용 · 12 0줄 경로(§1-3, 양성 대조) · 13 키 꼴 0 · 14 ② 요청 경로의 저장소 0(grep) ·
#   15 git status --porcelain 0(커밋 뒤에만 — 커밋 전에는 --step 으로 뺀다).
#
# 환경 변수:
#   RC1_BASE   기준 커밋(기본: 08c9080 = main merge band/AD2S — 49a1e0d 위 웹만)
#   RC1_OUT    산출물 자리(기본: 워크트리 곁의 RC1.out). collect-base.txt·lint-imports-base.txt·base-responses/·
#              probe/(겉 응답 시험과 그 실행기)가 여기 있어야 한다(구현 전에 BASE 에서 뜬 것)
#   RC1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(13 이 BASE..HEAD 의 메시지와 함께 본다)
# 2·3·6·9 는 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). 통합 층은 안 돌림.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${RC1_BASE:-08c9080}"
OUT="${RC1_OUT:-$SIDE/RC1.out}"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

case "${1:-}" in 1|2) BOUNDARY="$1"; shift ;; *) echo "첫 인자는 경계(1|2)"; exit 2 ;; esac
S4="$OUT/section4-$BOUNDARY"
mkdir -p "$S4"
STEPS="all"
WITH_CONTAINERS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    --with-containers) WITH_CONTAINERS="--with-containers"; shift ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "BOUNDARY=$BOUNDARY BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD)"

HELPER="$S4/rc1_helper.py"
cat > "$HELPER" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
BOUNDARY = int(sys.argv[3])
CMD = sys.argv[4]
ARGS = sys.argv[5:]


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed_files() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


# ── 11·12: 허용 경로(§1-2 ∪ §1-4)와 0줄 경로(§1-3) ─────────────────────────

P = r"^apps/api-py/"
E = P + r"esgapi/"
ALLOWED_PATHS = {
    E + r"runs/tasks\.py$": 1,
    E + r"runs/service/services/resume\.py$": 1,
    E + r"runs/tests/test_executor\.py$": 1,
    E + r"runs/tests/service/services/test_resume\.py$": 1,
    P + r"scripts/(section4|planted-breaks)-RC1\.sh$": 1,  # 9f 허락(246 노트)
    E + r"runs/service/actions/runs\.py$": 2,
    E + r"runs/tests/service/apis/test_runs\.py$": 2,
    E + r"core/tests/test_transaction_rules\.py$": 2,
    E + r"greenwash/tests/flows/test_binding_e0_coordinates_runs\.py$": 2,  # a2 허락(주석 한 줄)
}
ZERO_PATHS = [
    E + r"core/resources/", E + r"core/tests/resource_fakes\.py$", E + r"runs/models\.py$", E + r"[^/]+/migrations/",
    E + r"runs/service/(apis|schemas|selectors)/", E + r"runs/service/services/(runs|files)\.py$", E + r"runs/context\.py$",
    E + r"core/flows/", E + r"(translation|dataverify|inventory)/", E + r"greenwash/(?!tests/flows/test_binding_e0_coordinates_runs\.py$)",
    P + r"\.importlinter$", P + r"(pyproject\.toml|uv\.lock)$", P + r"generated/", P + r"gunicorn\.conf\.py$",
    P + r"tests/", P + r"tests_integration/", r"conftest\.py$", r"^apps/web/",
    P + r"scripts/(planted-breaks|verify|section4)\.sh$",
]


def hits(paths: set[str], patterns: list[str]) -> list[str]:
    return sorted(p for p in paths if any(re.search(a, p) for a in patterns))


if CMD == "zero":
    changed = changed_files()
    bad = hits(changed, ZERO_PATHS)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)} · 0줄 경로와 교집합 {bad}")
    planted = "apps/api-py/esgapi/core/tests/resource_fakes.py"
    positive = hits(changed | {planted}, ZERO_PATHS)
    print(f"  양성 대조(가짜 core/tests/resource_fakes.py) → {positive}")
    raise SystemExit(1 if bad or not changed or positive != [planted] else 0)

if CMD == "allowed":
    changed = changed_files()
    outside, early = [], []
    for p in sorted(changed):
        found = [b for pattern, b in ALLOWED_PATHS.items() if re.search(pattern, p)]
        if not found:
            outside.append(p)
        elif min(found) > BOUNDARY:
            early.append(p)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)}:")
    for p in sorted(changed):
        print(f"    {p}")
    print(f"  허용 밖: {outside}")
    print(f"  뒤 경계 몫이 미리 바뀜: {early}")
    planted = "apps/api-py/esgapi/runs/models.py"
    positive = [p for p in [planted] if not any(re.search(a, p) for a in ALLOWED_PATHS)]
    print(f"  양성 대조(가짜 runs/models.py) 허용 밖 → {positive}")
    raise SystemExit(1 if outside or early or not changed or not positive else 0)

# ── 7: 시험 수·이름(빠짐 = 그 경계의 걷은 시험 표 — §2-2) ──────────────────

TRES = "esgapi/runs/tests/service/services/test_resume.py"
TRUNS = "esgapi/runs/tests/service/apis/test_runs.py"
REMOVED = {
    1: set(),
    2: {
        TRES + "::test_each_source_is_copied_to_its_new_key",
        TRES + "::test_missing_and_too_large_sources_are_counted_and_the_rest_goes",
        TRES + "::test_a_refusing_or_unreachable_store_is_counted_without_raising",
        TRUNS + "::test_resume_sends_after_the_bytes_are_in_the_new_key",
        TRUNS + "::test_the_copy_hook_logs_missing_objects_and_still_sends",
        TRUNS + "::test_the_copy_hook_logs_the_copied_files_at_info",
        TRUNS + "::test_a_source_key_outside_the_company_is_not_copied",
        TRUNS + "::test_without_a_store_the_hook_copies_nothing_and_still_sends",
        TRUNS + "::test_a_store_that_raises_does_not_stop_the_message",
    },
}


def nodes(p: Path) -> set[str]:
    return {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}


if CMD == "collect":
    before, after = nodes(Path(ARGS[0])), nodes(Path(ARGS[1]))
    removed, added = before - after, sorted(after - before)
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {len(removed)} · 더함 {len(added)}"
          f" (BASE − 빠짐 + 더함 = {len(before) - len(removed) + len(added)})")
    for n in sorted(removed):
        print(f"    - {n}")
    for n in added:
        print(f"    + {n}")
    want = REMOVED[BOUNDARY]
    print(f"  빠짐이 표와 같은가: {removed == want} (표 밖 {sorted(removed - want)} · 남은 표 {sorted(want - removed)})")
    raise SystemExit(0 if removed == want and added else 1)

# ── 8: 약화 대조(- 줄의 assert·== 가 §2-2 표의 항목과 짝) ─────────────────────

# (파일 끝부분, 지운 줄, 경계, 짝으로 더한 줄 또는 None(걷은 시험 — 짝 시험은 보고 표), 항목)
MINUS: list[tuple[str, str, int, str | None, str]] = [
    (TRUNS, "assert world.storage.objects[copied.storage_key][0] == PAGES  # 바이트 같음", 2,
     "assert copied.storage_key not in world.storage.objects  # 바이트는 실행기 _plan 이 옮긴다(RC1)",
     "§2-2 표 :435 뒤집음 — 바이트 옮김은 executor 1·② 11 이 잡음"),
    (TRUNS, "assert world.storage.put_calls == [copied.storage_key]", 2,
     "assert world.storage.put_calls == []",
     "§2-2 표 :436 뒤집음 — put 은 executor 1(새 키 put)·② 9 가 잡음"),
    (TRUNS, "assert (len(world.storage.put_calls), len(callbacks), len(world.sent)) == (1, 1, 1)", 2,
     "assert (len(callbacks), len(world.sent)) == (1, 1)",
     "§2-2 표 :483 분모를 갈고리·쪽지 셈으로"),
]


def removed_tests_lines() -> set[tuple[str, str]]:
    """걷은 시험(REMOVED) 몸의 줄 — 그 시험째 걷음은 7 과 보고의 짝 표가 잰다."""
    out: set[tuple[str, str]] = set()
    for node in REMOVED[BOUNDARY]:
        path, name = node.split("::")
        text = git("show", f"{BASE}:apps/api-py/{path}")
        m = re.search(rf"^def {name}\(.*?(?=^(?:def |@|class |# ──|END))", text + "\nEND", flags=re.S | re.M)
        if m:
            out |= {("apps/api-py/" + path, line.strip()) for line in m.group(0).splitlines()}
    return out


if CMD == "weaken":
    diff = git("diff", "-U0", BASE, "--", "apps/api-py/esgapi/*/tests/*", "apps/api-py/tests")
    current = None
    rows = []
    plus: dict[str, set[str]] = {}
    for line in diff.splitlines():
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("-") and not line.startswith("---") and re.search(r"assert|==|len\(", line):
            rows.append((current, line[1:].strip()))
        elif line.startswith("+") and not line.startswith("+++"):
            plus.setdefault(current or "", set()).add(line[1:].strip())
    whole = removed_tests_lines()
    bad = 0
    for path, text in rows:
        if (path, text) in whole:
            print(f"  - {path}: {text}\n      → 걷은 시험의 몸(7·보고 짝 표)")
            continue
        hit = next(((item, pair) for f, t, b, pair, item in MINUS
                    if b <= BOUNDARY and path and path.endswith(f) and t == text), None)
        paired = hit is not None and (hit[1] is None or hit[1] in plus.get(path or "", set()))
        print(f"  - {path}: {text}\n      → {hit[0] if hit else '<항목 없음>'} · 짝 {'있음' if paired else '없음'}")
        bad += 0 if paired else 1
    print(f"  - 줄(assert·==·len() {len(rows)} · 항목·짝 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 13: 키 꼴 0 ───────────────────────────────────────────────────────

if CMD == "keys":
    pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    added = [l for l in git("diff", BASE).splitlines() if l.startswith("+")]
    for path in git("ls-files", "--others", "--exclude-standard").split():
        added += (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
    messages = git("log", "--format=%B", f"{BASE}..HEAD")
    if ARGS and ARGS[0]:
        messages += Path(ARGS[0]).read_text(encoding="utf-8")
    found = [l for l in added if pattern.search(l)] + [l for l in messages.splitlines() if pattern.search(l)]
    positive = bool(pattern.search("sk-" + "A" * 24))
    print(f"  더한 줄 {len(added)} · 메시지 {len(messages.splitlines())}줄 · 키 꼴 {len(found)} · 양성 대조 {positive}")
    raise SystemExit(1 if found or not added or not positive else 0)

# ── 3: 겉 응답(BASE 폴더 ↔ HEAD 폴더) ─────────────────────────────────────

if CMD == "responses":
    base, head = Path(ARGS[0]), Path(ARGS[1])
    names = sorted(p.name for p in base.iterdir() if p.suffix in (".status", ".masked", ".body"))
    bad = 0
    for name in names:
        a, b = (base / name).read_bytes(), (head / name).read_bytes() if (head / name).exists() else None
        same = a == b
        if name.endswith(".body") and not same:
            print(f"  {name}: 날 바이트 다름(id 차이 — .masked 로 견줌)")
            continue
        print(f"  {name}: {'같음' if same else '다름'}")
        bad += 0 if same else 1
    print(f"  견준 파일 {len(names)} · 다름 {bad}")
    raise SystemExit(1 if bad or len(names) < 21 else 0)

raise SystemExit(f"모르는 명령 {CMD}")
PY
helper() { api python "$HELPER" "$ROOT" "$BASE" "$BOUNDARY" "$@"; }

if want 1; then
  api pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$S4/1-pure.txt" 2>&1
  rc=$?
  tail -1 "$S4/1-pure.txt"
  report 1 "순수 층 초록(test_transaction_rules 25·durable 5·on_commit · test_static_rules opened 63 포함)" "$rc"
fi

if want 2; then
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider -n 2 \
    esgapi/runs esgapi/core \
    esgapi/greenwash/tests/flows/test_binding_e0_coordinates_runs.py \
    esgapi/dataverify/tests/flows/test_runs_dataverify.py) > "$S4/2-business.txt" 2>&1
  rc_b=$?
  tail -1 "$S4/2-business.txt"
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider \
    tests/security/test_runs.py tests/security/test_tenant_paths.py) > "$S4/2-security.txt" 2>&1
  rc_s=$?
  tail -1 "$S4/2-security.txt"
  rc=0; [ "$rc_b" = "0" ] && [ "$rc_s" = "0" ] || rc=1
  echo "  (모듈 이어 돌기 시험: greenwash e0 · dataverify runs · runs/test_runs_versions·test_runs_session · core/test_flows_run 은 esgapi/runs·core 안)"
  report 2 "업무(runs·core + 모듈 이어 돌기)·보안(test_runs·test_tenant_paths) 초록(업무 ${rc_b} 보안 ${rc_s})" "$rc"
fi

if want 3; then
  mkdir -p "$S4/3-head-responses"
  "$OUT/probe/run-probe.sh" "$API_PY" "$S4/3-head-responses" > "$S4/3-probe.txt" 2>&1
  rc_p=$?
  tail -1 "$S4/3-probe.txt"
  helper responses "$OUT/base-responses" "$S4/3-head-responses" > "$S4/3-responses.txt" 2>&1
  rc_r=$?
  cat "$S4/3-responses.txt"
  rc=0; [ "$rc_p" = "0" ] && [ "$rc_r" = "0" ] || rc=1
  report 3 "이어 돌기 겉 응답 BASE = HEAD(시험 ${rc_p} 대조 ${rc_r})" "$rc"
fi

if want 4; then
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" env -u OPENAI_API_KEY scripts/gen-ts-types.sh) > "$S4/4-gen.txt" 2>&1
  rc_g=$?
  git -C "$ROOT" diff --exit-code --stat -- apps/api-py/generated > "$S4/4-generated-diff.txt" 2>&1
  rc_d=$?
  cat "$S4/4-generated-diff.txt"
  rc=0; [ "$rc_g" = "0" ] && [ "$rc_d" = "0" ] || rc=1
  report 4 "generated 다시 뽑아 0바이트 차이(뽑기 ${rc_g} 차이 ${rc_d})" "$rc"
fi

if want 5; then
  api lint-imports > "$S4/5-lint-imports.txt" 2>&1
  rc_l=$?
  last="$(grep -E '^Contracts:' "$S4/5-lint-imports.txt" | tail -1)"
  base_last="$(grep -E '^Contracts:' "$OUT/lint-imports-base.txt" 2>/dev/null | tail -1)"
  echo "  지금: $last · BASE: ${base_last:-<없음>}"
  rc=0
  [ "$rc_l" = "0" ] && [ -n "$base_last" ] && [ "$last" = "$base_last" ] || rc=1
  report 5 "import 계약 kept = BASE" "$rc"
fi

if want 6; then
  (cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business env -u OPENAI_API_KEY \
    uv run --frozen python manage.py makemigrations --check --dry-run) > "$S4/6-makemigrations.txt" 2>&1
  rc=$?
  cat "$S4/6-makemigrations.txt"
  report 6 "makemigrations --check --dry-run" "$rc"
fi

if want 7; then
  if [ ! -s "$OUT/collect-base.txt" ]; then
    echo "  $OUT/collect-base.txt 가 없다(경계 ① 전에 BASE 에서 떠 둘 것)"
    report 7 "시험 수·이름" 1
  else
    api pytest --collect-only -q -p no:cacheprovider esgapi tests > "$S4/7-collect-now.txt" 2>&1
    rc_c=$?
    helper collect "$OUT/collect-base.txt" "$S4/7-collect-now.txt" > "$S4/7-collect.txt" 2>&1
    rc_n=$?
    cat "$S4/7-collect.txt"
    rc=0; [ "$rc_c" = "0" ] && [ "$rc_n" = "0" ] || rc=1
    report 7 "시험 수·이름(빠짐 = 걷은 시험 표)" "$rc"
  fi
fi

if want 8; then
  helper weaken > "$S4/8-weaken.txt" 2>&1
  rc=$?
  cat "$S4/8-weaken.txt"
  report 8 "약화 대조(- 줄마다 항목과 짝)" "$rc"
fi

if want 9; then
  "$API_PY/scripts/planted-breaks-RC1.sh" "$BOUNDARY" $WITH_CONTAINERS > "$S4/9-planted.txt" 2>&1
  rc_p=$?
  grep -E '^(P[0-9]+ =>|P0=|PLANTED=|FINGERPRINT=)' "$S4/9-planted.txt"
  expect="PLANTED=10/10"; [ "$BOUNDARY" = "2" ] && expect="PLANTED=14/14"
  got="$(grep -E '^PLANTED=' "$S4/9-planted.txt" | tail -1)"
  skipped="$(grep -c '안 돌림' "$S4/9-planted.txt")"
  fp="$(grep -E '^FINGERPRINT=' "$S4/9-planted.txt" | tail -1)"
  echo "  기대 ${expect} · 받음 ${got} · 「안 돌림」 ${skipped}줄 · ${fp}"
  rc=0; [ "$rc_p" = "0" ] && [ "$got" = "$expect" ] && [ "$skipped" = "0" ] && [ "$fp" = "FINGERPRINT=same" ] || rc=1
  report 9 "심은 파손(${expect} 정확히)" "$rc"
fi

if want 10; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/10-verify-fast.txt" 2>&1
  rc=$?
  last="$(tail -1 "$S4/10-verify-fast.txt")"
  echo "  $last"
  [ "$last" = "VERIFY_FAST=PASS" ] || rc=1
  report 10 "게이트 verify.sh --fast" "$rc"
fi

if want 11; then
  helper allowed > "$S4/11-allowed.txt" 2>&1
  rc=$?
  cat "$S4/11-allowed.txt"
  report 11 "허용 경로(추적 안 된 새 파일 포함, 양성 대조)" "$rc"
fi

if want 12; then
  helper zero > "$S4/12-zero.txt" 2>&1
  rc=$?
  cat "$S4/12-zero.txt"
  report 12 "0줄 경로(추적 안 된 새 파일 포함, 양성 대조)" "$rc"
fi

if want 13; then
  helper keys "${RC1_COMMIT_MSG_FILE:-}" > "$S4/13-keys.txt" 2>&1
  rc=$?
  cat "$S4/13-keys.txt"
  report 13 "키 꼴 0" "$rc"
fi

if want 14; then
  if [ "$BOUNDARY" = "2" ]; then
    n="$(grep -nE 'default_storage|resume\.' "$API_PY/esgapi/runs/service/actions/runs.py" | wc -l | tr -d ' ')"
    grep -nE 'default_storage|resume\.' "$API_PY/esgapi/runs/service/actions/runs.py"
    pos="$(printf 'x = documents.default_storage()\n' | grep -cE 'default_storage|resume\.')"
    echo "  actions/runs.py 의 default_storage|resume. ${n}줄 · 양성 대조 ${pos}"
    rc=0; [ "$n" = "0" ] && [ "$pos" = "1" ] || rc=1
  else
    echo "  경계 ① 은 요청 갈고리를 그대로 둔다(겹침 무해 — ① 시험 11)"
    rc=0
  fi
  report 14 "요청 경로 저장소 0(② grep)" "$rc"
fi

if want 15; then
  porcelain="$(git -C "$ROOT" status --porcelain)"
  n=0; [ -z "$porcelain" ] || n=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
  echo "  git status --porcelain ${n}줄"
  rc=0; [ "$n" = "0" ] || rc=1
  report 15 "작업 트리 깨끗(커밋 뒤)" "$rc"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
