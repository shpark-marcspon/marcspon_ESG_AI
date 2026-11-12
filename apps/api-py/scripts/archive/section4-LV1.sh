#!/usr/bin/env bash
# 밴드 LV1 의 §4 자기검증(발주서 band-handoffs/LV1-order.md §4 — RC1 의 section4-RC1.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝에 SECTION4_FAIL=<n>. 경계는 둘이다.
# 사용(어디서든):
#   apps/api-py/scripts/section4-LV1.sh <1|2> --with-containers                     전부(통합 빼고)
#   apps/api-py/scripts/section4-LV1.sh <1|2> --with-containers --with-integration  통합 ⓑ 까지(compose 전체를 띄워 둔 뒤)
#   apps/api-py/scripts/section4-LV1.sh <1|2> --step 1,2,3 --with-containers        고른 단계만
#
# 단계(§4): 1 순수 · 2 업무(runs·core·config·user + 모듈 「서버 그대로 = setup_error」 넷 + 그린워싱 live) — 키 변수 넷을
#   지운 채 · 3 같은 업무를 키 변수 넷을 **지어낸 값으로 둔 채** 한 번 더(mock 기본 = 키가 있어도 setup_error) ·
#   4 보안 tests/security 전부 · 5 겉 바이트 BASE = HEAD(/run-logs/metrics(② 새 칸 뺌)·/run-logs/{id}·POST /api/runs 201) ·
#   6 generated 다시 뽑기(① 0바이트 · ② aiProviderMock 칸만) · 7 lint-imports kept = BASE · 8 makemigrations --check ·
#   9 수집 = BASE − 걷음(P10 이름 바꿈) + 더함 · 10 심은 파손(① 12/12 · ② 14/14 · FINGERPRINT=same) · 11 verify.sh --fast ·
#   12 바뀐 경로 ⊆ 허용 · 13 0줄 경로(§1-3, 양성 대조) · 14 키 꼴 0(가지 diff·메시지 — sk- 꼴) · 15 바깥 연결 0(업무 로그의
#   고정물 줄 0 + 전량 로그의 api.openai.com 0) · 16 git status --porcelain 0(커밋 뒤에만) · 17 통합 ⓑ(--with-integration).
#   ★ 마크스폰 키 값의 grep 은 여기서 하지 않는다: 러너는 §7 전에 키 파일을 열지 않는다(러너 프롬프트 규율) — §7 의
#     실행 명령이 그 자리에서 수만 낸다(발주서 §7).
#
# 환경 변수:
#   LV1_BASE   기준 커밋(기본: 4e28a54 = main merge band/RC1)
#   LV1_OUT    산출물 자리(기본: 워크트리 곁의 LV1.out). collect-base.txt·lint-imports-base.txt·base-responses/·
#              probe/(겉 응답 시험과 그 실행기)가 여기 있어야 한다(구현 전에 BASE 에서 뜬 것)
#   LV1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(14 가 BASE..HEAD 의 메시지와 함께 본다)
# 2·3·4·5·8·10 은 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만).
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${LV1_BASE:-4e28a54}"
OUT="${LV1_OUT:-$SIDE/LV1.out}"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
NOKEYS="-u OPENAI_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY -u LLM_RUN_MODE -u LLM_RUN_MAX_USD"
# shellcheck disable=SC2086
api() { (cd "$API_PY" && env $NOKEYS uv run --frozen "$@"); }

case "${1:-}" in 1|2) BOUNDARY="$1"; shift ;; *) echo "첫 인자는 경계(1|2)"; exit 2 ;; esac
S4="$OUT/section4-$BOUNDARY"
mkdir -p "$S4"
STEPS="all"
WITH_CONTAINERS=""
WITH_INTEGRATION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    --with-containers) WITH_CONTAINERS="--with-containers"; shift ;;
    --with-integration) WITH_INTEGRATION=1; shift ;;
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

MODULE_TESTS="esgapi/translation/tests/flows/test_runs_translation.py esgapi/dataverify/tests/flows/test_runs_dataverify.py
esgapi/dataverify/tests/service/apis/test_dataverify.py esgapi/greenwash/tests/flows/test_binding_e0_settings_runs.py
esgapi/greenwash/tests/flows/test_binding_e0_live_runs.py"
SK_FAKE="sk-proj-LV1SENTINEL$(printf 'f%.0s' 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24)"

HELPER="$S4/lv1_helper.py"
cat > "$HELPER" <<'PY'
import json
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


# ── 12·13: 허용 경로(§1-2 ∪ §1-4 — 249 노트의 허락)와 0줄 경로(§1-3) ─────────────────

P = r"^apps/api-py/"
E = P + r"esgapi/"
ALLOWED_PATHS = {
    E + r"config/env\.py$": 1,
    E + r"runs/context\.py$": 1,
    E + r"runs/tests/test_context\.py$": 1,
    E + r"runs/tests/test_context_live\.py$": 1,
    E + r"runs/tests/test_live_secrets\.py$": 1,
    E + r"core/tests/test_env_llm_run_mode\.py$": 1,
    E + r"greenwash/tests/flows/test_binding_e0_live_runs\.py$": 1,  # 그린워싱 a2 허락(249 노트)
    P + r"scripts/(section4|planted-breaks)-LV1\.sh$": 1,  # 테스트 73 허락(249 노트)
    r"^compose\.yaml$": 1,  # 테스트 73 허락 — 두 줄
    r"^\.env\.example$": 1,  # 백엔드 줄기 22 몫 — 두 줄
    E + r"user/service/(schemas|apis)/run_logs\.py$": 2,
    E + r"user/tests/.*run_logs.*\.py$": 2,
    P + r"generated/": 2,
    r"^README\.md$": 2,
    r"^docs/development\.md$": 2,
    r"^apps/web/src/entities/run-log/api/testing\.ts$": 2,  # 플랫폼-웹 8e 허락(249 노트) — 지표 가짜 한 줄
}
ZERO_PATHS = [
    E + r"core/llm/", E + r"core/resources/", E + r"core/models\.py$", E + r"[^/]+/migrations/",
    E + r"runs/service/", E + r"runs/calc/", E + r"runs/tests/test_executor\.py$", E + r"runs/tasks\.py$",
    E + r"(translation|dataverify|inventory|organization|reference|reconcile)/",
    E + r"greenwash/(?!tests/flows/test_binding_e0_live_runs\.py$)",
    P + r"\.importlinter$", P + r"(pyproject\.toml|uv\.lock)$",
    P + r"tests/", P + r"tests_integration/", r"conftest\.py$", r"^apps/web/(?!src/entities/run-log/api/testing\.ts$)", r"^infra/",
    P + r"scripts/(planted-breaks|verify|section4)\.sh$", r"^scripts/verify\.sh$",
]


def hits(paths: set[str], patterns: list[str]) -> list[str]:
    return sorted(p for p in paths if any(re.search(a, p) for a in patterns))


if CMD == "zero":
    changed = changed_files()
    bad = hits(changed, ZERO_PATHS)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)} · 0줄 경로와 교집합 {bad}")
    planted = "apps/api-py/esgapi/core/llm/client.py"
    positive = hits(changed | {planted}, ZERO_PATHS)
    print(f"  양성 대조(가짜 core/llm/client.py) → {positive}")
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
    planted = "apps/api-py/esgapi/runs/tasks.py"
    positive = [p for p in [planted] if not any(re.search(a, p) for a in ALLOWED_PATHS)]
    print(f"  양성 대조(가짜 runs/tasks.py) 허용 밖 → {positive}")
    # compose·.env.example 은 더한 줄만(두 줄씩, 지운 줄 0)
    lines_bad = []
    for path, want in (("compose.yaml", 2), (".env.example", 5)):
        if path in changed:
            diff = git("diff", "-U0", BASE, "--", path).splitlines()
            minus = [l for l in diff if l.startswith("-") and not l.startswith("---")]
            plus = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
            print(f"  {path}: + {len(plus)} · - {len(minus)} (기대 + {want} · - 0)")
            if minus or len(plus) != want:
                lines_bad.append(path)
    web = "apps/web/src/entities/run-log/api/testing.ts"
    if web in changed:  # 허락은 +1/−0 한 줄 `aiProviderMock: true,`
        diff = git("diff", "-U0", BASE, "--", web).splitlines()
        minus = [l for l in diff if l.startswith("-") and not l.startswith("---")]
        plus = [l[1:].strip() for l in diff if l.startswith("+") and not l.startswith("+++")]
        print(f"  {web}: + {plus} · - {len(minus)} (기대 ['aiProviderMock: true,'] · 0)")
        if minus or plus != ["aiProviderMock: true,"]:
            lines_bad.append(web)
    raise SystemExit(1 if outside or early or not changed or not positive or lines_bad else 0)

# ── 9: 시험 수·이름(빠짐 = 그 경계의 걷은 시험 표) ──────────────────

TCTX = "esgapi/runs/tests/test_context.py"
REMOVED = {
    1: {TCTX + "::test_the_runner_builds_only_mock_clients_even_when_keys_exist"},  # P10 이름 바꿈(발주서 Q9)
    2: {TCTX + "::test_the_runner_builds_only_mock_clients_even_when_keys_exist"},
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

# ── 14: 키 꼴 0 ───────────────────────────────────────────────────────

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

# ── 5: 겉 응답(BASE 폴더 ↔ HEAD 폴더). ② 는 metrics 의 aiProviderMock 칸을 빼고 견준다 ──────────

NEW_FIELD = "aiProviderMock"

if CMD == "responses":
    base, head = Path(ARGS[0]), Path(ARGS[1])
    names = sorted(p.name for p in base.iterdir() if p.suffix in (".status", ".masked"))
    bad = 0
    for name in names:
        a = (base / name).read_bytes()
        b = (head / name).read_bytes() if (head / name).exists() else None
        note = ""
        if b is not None and BOUNDARY == 2 and name.startswith("metrics") and name.endswith(".masked"):
            got = json.loads(b)
            field = got.pop(NEW_FIELD, "<없음>")
            note = f" ({NEW_FIELD}={field} 뺌)"
            bad += 0 if field is True else 1
            b = json.dumps(got, ensure_ascii=False, sort_keys=True).encode()
        same = a == b
        print(f"  {name}: {'같음' if same else '다름'}{note}")
        bad += 0 if same else 1
    print(f"  견준 파일 {len(names)} · 다름 {bad}")
    raise SystemExit(1 if bad or len(names) < 12 else 0)  # 응답 여섯 × (상태·가린 몸)

# ── 6: generated 차이(② 는 그 칸 하나) ───────────────────────────────

if CMD == "generated":
    diff = git("diff", "-U0", "--", "apps/api-py/generated")
    plus = [l[1:].strip() for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    minus = [l[1:].strip() for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    print(f"  generated 의 작업 트리 차이(HEAD 대비) + {len(plus)} · - {len(minus)}")
    base_diff = git("diff", "--stat", BASE, "--", "apps/api-py/generated")
    print("  BASE 대비:\n" + "\n".join("    " + l for l in base_diff.splitlines()))
    bad_base: list[str] = []
    if BOUNDARY == 2:  # BASE 대비 차이는 aiProviderMock 칸 하나(+ 원천 sha 한 줄)
        ok = re.compile(r"aiProviderMock|Aiprovidermock|AI 호출이 모의 공급사|\"type\": \"boolean\"|^\}?,?$|^/\*\*$|^\*/$|^\"failureRate\",?$")
        full = git("diff", "-U0", BASE, "--", "apps/api-py/generated/openapi.json", "apps/api-py/generated/api.d.ts")
        for l in full.splitlines():
            if (l.startswith("+") and not l.startswith("+++")) or (l.startswith("-") and not l.startswith("---")):
                text = l[1:].strip()
                if not ok.search(text):
                    bad_base.append(l)
        print(f"  BASE 대비 그 칸 밖의 줄: {bad_base}")
        positive = not ok.search('"costUsd": 1')
        print(f"  양성 대조(다른 칸의 줄은 밖으로 잡힘): {positive}")
        bad_base += [] if positive else ["<양성 대조 실패>"]
    raise SystemExit(1 if plus or minus or bad_base else 0)

raise SystemExit(f"모르는 명령 {CMD}")
PY
helper() { api python "$HELPER" "$ROOT" "$BASE" "$BOUNDARY" "$@"; }

if want 1; then
  api pytest -q -p no:cacheprovider -n 4 -m "not django_db and not security" esgapi > "$S4/1-pure.txt" 2>&1
  rc=$?
  tail -1 "$S4/1-pure.txt"
  report 1 "순수 층 초록" "$rc"
fi

business() { # business <로그> <env 앞부분…>
  local log="$1"; shift
  # shellcheck disable=SC2086
  (cd "$API_PY" && "$@" scripts/test-business.sh -p no:cacheprovider -n 4 \
    esgapi/runs esgapi/core esgapi/config esgapi/user $MODULE_TESTS) > "$log" 2>&1
}

if want 2; then
  # shellcheck disable=SC2086
  business "$S4/2-business-nokeys.txt" env $NOKEYS
  rc=$?
  tail -1 "$S4/2-business-nokeys.txt"
  report 2 "업무(runs·core·config·user + 모듈 setup_error 넷 + 그린워싱 live) 키 변수 없이" "$rc"
fi

if want 3; then
  # shellcheck disable=SC2086
  business "$S4/3-business-fakekeys.txt" env $NOKEYS OPENAI_API_KEY="$SK_FAKE" LLM_OPENAI_API_KEY="$SK_FAKE" \
    LLM_ANTHROPIC_API_KEY=LV1PLAINSENTINEL LLM_GEMINI_API_KEY=LV1PLAINSENTINEL
  rc=$?
  tail -1 "$S4/3-business-fakekeys.txt"
  report 3 "같은 업무를 키 변수 넷을 지어낸 값으로 둔 채(LLM_RUN_MODE 없음 = mock)" "$rc"
fi

if want 4; then
  # shellcheck disable=SC2086
  (cd "$API_PY" && env $NOKEYS scripts/test-security.sh -p no:cacheprovider) > "$S4/4-security.txt" 2>&1
  rc=$?
  tail -1 "$S4/4-security.txt"
  report 4 "보안 층 tests/security 전부" "$rc"
fi

if want 5; then
  rm -rf "$S4/5-head-responses"
  mkdir -p "$S4/5-head-responses"
  "$OUT/probe/run-probe.sh" "$API_PY" "$S4/5-head-responses" > "$S4/5-probe.txt" 2>&1
  rc_p=$?
  tail -1 "$S4/5-probe.txt"
  helper responses "$OUT/base-responses" "$S4/5-head-responses" > "$S4/5-responses.txt" 2>&1
  rc_r=$?
  cat "$S4/5-responses.txt"
  rc=0; [ "$rc_p" = "0" ] && [ "$rc_r" = "0" ] || rc=1
  report 5 "겉 응답 BASE = HEAD(시험 ${rc_p} 대조 ${rc_r})" "$rc"
fi

if want 6; then
  # shellcheck disable=SC2086
  (cd "$API_PY" && PATH="$NODE_PATH_DIR:$PATH" env $NOKEYS scripts/gen-ts-types.sh) > "$S4/6-gen.txt" 2>&1
  rc_g=$?
  helper generated > "$S4/6-generated.txt" 2>&1
  rc_d=$?
  cat "$S4/6-generated.txt"
  rc=0; [ "$rc_g" = "0" ] && [ "$rc_d" = "0" ] || rc=1
  report 6 "generated 다시 뽑아 작업 트리 차이 0(뽑기 ${rc_g} 차이 ${rc_d})" "$rc"
fi

if want 7; then
  api lint-imports > "$S4/7-lint-imports.txt" 2>&1
  rc_l=$?
  last="$(grep -E '^Contracts:' "$S4/7-lint-imports.txt" | tail -1)"
  base_last="$(grep -E '^Contracts:' "$OUT/lint-imports-base.txt" 2>/dev/null | tail -1)"
  echo "  지금: $last · BASE: ${base_last:-<없음>}"
  rc=0
  [ "$rc_l" = "0" ] && [ -n "$base_last" ] && [ "$last" = "$base_last" ] || rc=1
  report 7 "import 계약 kept = BASE" "$rc"
fi

if want 8; then
  # shellcheck disable=SC2086
  (cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business env $NOKEYS \
    uv run --frozen python manage.py makemigrations --check --dry-run) > "$S4/8-makemigrations.txt" 2>&1
  rc=$?
  cat "$S4/8-makemigrations.txt"
  report 8 "makemigrations --check --dry-run" "$rc"
fi

if want 9; then
  if [ ! -s "$OUT/collect-base.txt" ]; then
    echo "  $OUT/collect-base.txt 가 없다(경계 ① 전에 BASE 에서 떠 둘 것)"
    report 9 "시험 수·이름" 1
  else
    api pytest --collect-only -q -p no:cacheprovider esgapi tests > "$S4/9-collect-now.txt" 2>&1
    rc_c=$?
    helper collect "$OUT/collect-base.txt" "$S4/9-collect-now.txt" > "$S4/9-collect.txt" 2>&1
    rc_n=$?
    head -5 "$S4/9-collect.txt"; grep -E '빠짐이 표와' "$S4/9-collect.txt"
    rc=0; [ "$rc_c" = "0" ] && [ "$rc_n" = "0" ] || rc=1
    report 9 "시험 수·이름(빠짐 = 걷은 시험 표)" "$rc"
  fi
fi

if want 10; then
  LV1_OUT="$OUT" "$API_PY/scripts/planted-breaks-LV1.sh" "$BOUNDARY" $WITH_CONTAINERS > "$S4/10-planted.txt" 2>&1
  rc_p=$?
  grep -E '^(P[0-9]+ =>|O[0-9]+ =>|P0=|PLANTED=|FINGERPRINT=)' "$S4/10-planted.txt"
  expect="PLANTED=12/12"; [ "$BOUNDARY" = "2" ] && expect="PLANTED=14/14"
  got="$(grep -E '^PLANTED=' "$S4/10-planted.txt" | tail -1)"
  skipped="$(grep -c '안 돌림' "$S4/10-planted.txt")"
  fp="$(grep -E '^FINGERPRINT=' "$S4/10-planted.txt" | tail -1)"
  echo "  기대 ${expect} · 받음 ${got} · 「안 돌림」 ${skipped}줄 · ${fp}"
  rc=0; [ "$rc_p" = "0" ] && [ "$got" = "$expect" ] && [ "$skipped" = "0" ] && [ "$fp" = "FINGERPRINT=same" ] || rc=1
  report 10 "심은 파손(${expect} 정확히)" "$rc"
fi

if want 11; then
  # shellcheck disable=SC2086
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" env $NOKEYS scripts/verify.sh --fast) > "$S4/11-verify-fast.txt" 2>&1
  rc=$?
  last="$(tail -1 "$S4/11-verify-fast.txt")"
  echo "  $last"
  [ "$last" = "VERIFY_FAST=PASS" ] || rc=1
  report 11 "게이트 verify.sh --fast" "$rc"
fi

if want 12; then
  helper allowed > "$S4/12-allowed.txt" 2>&1
  rc=$?
  cat "$S4/12-allowed.txt"
  report 12 "허용 경로(추적 안 된 새 파일 포함, 양성 대조, compose·.env.example 더한 줄만)" "$rc"
fi

if want 13; then
  helper zero > "$S4/13-zero.txt" 2>&1
  rc=$?
  cat "$S4/13-zero.txt"
  report 13 "0줄 경로(추적 안 된 새 파일 포함, 양성 대조)" "$rc"
fi

if want 14; then
  helper keys "${LV1_COMMIT_MSG_FILE:-}" > "$S4/14-keys.txt" 2>&1
  rc=$?
  cat "$S4/14-keys.txt"
  report 14 "키 꼴 0" "$rc"
fi

if want 15; then
  logs="$(ls "$S4"/2-business-nokeys.txt "$S4"/3-business-fakekeys.txt "$S4"/1-pure.txt "$S4"/4-security.txt \
    "$S4"/11-verify-fast.txt 2>/dev/null)"
  # shellcheck disable=SC2086
  guard="$(cat $logs | grep -c '바깥 연결')"
  # shellcheck disable=SC2086
  openai_host="$(cat $logs | grep -c 'api.openai.com')"
  pos="$(printf 'OSError: LV1 시험: 바깥 연결 금지\n' | grep -c '바깥 연결')"
  echo "  로그 $(printf '%s\n' "$logs" | grep -c .)개 · 고정물 줄 ${guard} · api.openai.com ${openai_host} · 양성 대조 ${pos}"
  rc=0; [ "$guard" = "0" ] && [ "$openai_host" = "0" ] && [ "$pos" = "1" ] && [ -n "$logs" ] || rc=1
  report 15 "바깥 연결 0(시험 로그)" "$rc"
fi

if want 16; then
  porcelain="$(git -C "$ROOT" status --porcelain)"
  n=0; [ -z "$porcelain" ] || n=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
  echo "  git status --porcelain ${n}줄"
  rc=0; [ "$n" = "0" ] || rc=1
  report 16 "작업 트리 깨끗(커밋 뒤)" "$rc"
fi

if want 17 && [ -n "$WITH_INTEGRATION" ]; then
  # shellcheck disable=SC2086
  (cd "$API_PY" && env $NOKEYS scripts/test-integration.sh -p no:cacheprovider tests_integration/test_run_flow.py) \
    > "$S4/17-integration.txt" 2>&1
  rc=$?
  tail -1 "$S4/17-integration.txt"
  report 17 "통합 test_run_flow(ⓑ setup_error 그대로 — 키 없이, LLM_RUN_MODE 없음)" "$rc"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
