#!/usr/bin/env bash
# 밴드 RX1a 의 §4 자기검증(발주서 band-handoffs/RX1a-order.md §4 — RF1 의 section4-RF1.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝 줄 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-RX1a.sh [--commit 1|2] [--with-containers] [--planted] [--msg <파일>] [--step 1,2,…]
#     --commit n          경계(기본 2). 1 이면 runbundle·.importlinter 단계(2·카 이름·7)를 빼고 ① 의 허용 경로로 본다
#     --with-containers   6 업무·보안 층, 7 versitygw 왕복(ROUNDTRIP_DIFF=)
#     --planted           8 심은 파손(--with-containers 와 함께 — PLANTED=<잡음>/27)
#     --msg <파일>        9 커밋 메시지 초안의 트레일러
# 단계: 1 허용 경로·.importlinter `^-` 0·0줄 경로·셈 시험의 지운 줄 · 2 lint-imports(BASE + 1, 전부 KEPT) · 3 순수 시험
#   (N0 → N1) · 4 check_test_layout·pyright·ruff check·ruff format --check · 6 업무·보안 · 7 왕복(견본을 짓는다) ·
#   5 금지 글(더한 줄 + 묶음 견본 — 7 뒤에 돈다) · 8 심은 파손 · 9 트레일러 · 10 scripts/verify.sh --fast.
# 환경 변수: S4_OUT(기본 워크트리 곁의 RX1a.out) · RX1A_BASE(기본 c2cfe984).
# 컨테이너는 띄우지 않는다(compose esg-app-rx1a 가 떠 있어야 한다 — 6·7·8). 공급사를 부르지 않는다(키를 지운 환경).
# 저장소 주소(7·8 의 S16)는 저장소 맨 위 .env 에서 꺼내 RUNBUNDLE_S3_* 로 넘긴다(값을 찍지 않는다).
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${RX1A_BASE:-c2cfe984}"
OUT="${S4_OUT:-$SIDE/RX1a.out}"
S4="$OUT/section4"
FORBIDDEN="$SIDE/G1a.out/forbidden-words.txt"
mkdir -p "$S4"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen "$@"); }

COMMIT=2
WITH_CONTAINERS=""
PLANTED=""
MSG=""
STEPS="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:?--commit 뒤에 1|2}"; shift 2 ;;
    --with-containers) WITH_CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:?--msg 뒤에 파일}"; shift 2 ;;
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { echo "[$1] $2 EXIT=$3"; [ "$3" = "0" ] || FAIL=$((FAIL + 1)); }
env_value() { sed -n "s/^$1=//p" "$ROOT/.env" | tail -1; }
s3_env() {
  export RUNBUNDLE_S3_ENDPOINT="http://127.0.0.1:$(env_value STORAGE_PORT)"
  export RUNBUNDLE_S3_BUCKET="$(env_value S3_BUCKET)" RUNBUNDLE_S3_REGION="$(env_value S3_REGION)"
  export RUNBUNDLE_S3_ACCESS_KEY="$(env_value STORAGE_ACCESS_KEY)" RUNBUNDLE_S3_SECRET_KEY="$(env_value STORAGE_SECRET_KEY)"
}

echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD) COMMIT=$COMMIT"

HELPER="$S4/rx1a_helper.py"
cat > "$HELPER" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

ROOT, BASE, COMMIT, CMD, ARGS = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5:]
P = r"^apps/api-py/"
E = P + r"esgapi/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


ALLOWED_1 = [
    E + r"core/flows/carriers\.py$",
    E + r"core/service/(selectors|services)/(llm_logs|documents)\.py$",
    E + r"core/tests/(isolation/test_static_rules|test_selector_scope|test_transaction_rules|test_documents_models)\.py$",
    E + r"core/tests/flows/(__init__|test_carriers)\.py$",
    E + r"core/tests/service/(selectors|services)/test_(llm_logs|documents_bundle)\.py$",
    E + r"runs/service/(selectors|services)/bundle\.py$",
    E + r"runs/tests/service/(selectors|services)/test_bundle\.py$",
]
ALLOWED_2 = [
    E + r"runbundle/",
    P + r"\.importlinter$",
    E + r"config/apps_list\.py$",
    P + r"tests/security/test_run_bundles\.py$",
    P + r"scripts/(section4|planted-breaks)-RX1a\.sh$",
    # 감독 e5 허락(10-28): 앱 목록·계약 수·zipfile 목록의 셈 줄만
    E + r"config/tests/test_settings\.py$",
    E + r"reconcile/tests/test_tasks_registered\.py$",
    E + r"inventory/tests/test_s3sheets_is_pure\.py$",
]
GRANTED = {
    "apps/api-py/esgapi/reconcile/tests/test_tasks_registered.py",
    "apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure.py",
}
ZERO = [
    E + r"(greenwash|translation|dataverify|materiality|inventory|reconcile|reference|user|organization)/",
    E + r"runs/(models|tasks|context|extras)\.py$", E + r"runs/(migrations|calc|service/apis|service/schemas)/",
    E + r"core/(models\.py|migrations/|llm/|resources/)", E + r"core/flows/(binding|registry|run|types|__init__)\.py$",
    P + r"(tests_integration/|tests/support/|generated/)", r"(^|/)conftest\.py$", P + r"tests/security/seed\.py$",
    r"^apps/web/", P + r"(pyproject\.toml|uv\.lock)$", P + r"scripts/(verify|planted-breaks)\.sh$", r"^scripts/verify\.sh$",
    r"^infra/", E + r"config/api\.py$",
]
# 셈 시험·공유 파일에서 지워도 되는 줄(C0 표 + 감독 허락 — 보고 「C0 줄 표」·「C0 덧붙임」)
MINUS_OK = {
    "apps/api-py/esgapi/core/tests/isolation/test_static_rules.py": {
        '    {"config/api.py", "core/isolation/foreign_keys.py", "core/isolation/grants.py"}',
        '    "find_company_by_id": frozenset({"user/service/apis/users.py"}),',
        "    assert opened == 85",
    },
    "apps/api-py/esgapi/core/tests/test_selector_scope.py": {
        "    # 파일·끝내기·결과 · X1b-2a 문서 고치기(PATCH)의 update 하나)",
        '    assert opened == {"documents": 4, "jobs": 3, "audit": 1, "runs": 6}',
    },
    "apps/api-py/esgapi/core/tests/test_transaction_rules.py": {
        "    assert len(files) == 37, [",
        '        found_inside, found_outside = outside_calls(path.read_text(encoding="utf-8"))',
        '        inside += [f"{relative(path)}:{c}" for c in found_inside]',
        "    }  # 셈 3 → 9",
    },
    "apps/api-py/esgapi/core/tests/test_documents_models.py": {
        '    written = "".join(inspect.getsource(module) for module in (services, hooks))',
    },
    "apps/api-py/esgapi/core/service/services/documents.py": {"from collections.abc import Callable"},
    "apps/api-py/esgapi/reconcile/tests/test_tasks_registered.py": {
        '    """`.importlinter` 계약 (라)가 `esgapi.*.tasks` 를 문다(이름에도 tasks 가 있다). 계약은 모두 열일곱이다."""',
        '    assert len([name for name in parser.sections() if name.startswith("importlinter:contract:")]) == 17',
    },
}

if CMD == "paths":
    files = sorted(changed())
    allowed = ALLOWED_1 + (ALLOWED_2 if COMMIT >= 2 else [])
    outside = [f for f in files if not any(re.search(p, f) for p in allowed)]
    zero = [f for f in files if any(re.search(p, f) for p in ZERO) and not (COMMIT >= 2 and f in GRANTED)]
    lint_minus = [l for l in git("diff", BASE, "--", "apps/api-py/.importlinter").splitlines() if l.startswith("-") and not l.startswith("---")]
    bad_minus = []
    for f in files:
        minus = [l[1:] for l in git("diff", BASE, "--", f).splitlines() if l.startswith("-") and not l.startswith("---")]
        if f in MINUS_OK:
            bad_minus += [f"{f}: {l}" for l in minus if l not in MINUS_OK[f]]
        elif minus and not f.startswith("apps/api-py/esgapi/runbundle/"):
            bad_minus += [f"{f}: {l}" for l in minus]
    print(f"  바뀐 파일 {len(files)} · outside={len(outside)} {outside}")
    print(f"  0줄 경로 {zero} · .importlinter ^- {len(lint_minus)}")
    print(f"  허락 밖 지운 줄 {len(bad_minus)}")
    for line in bad_minus:
        print(f"    {line}")
    sys.exit(0 if not outside and not zero and not lint_minus and not bad_minus else 1)

if CMD == "secrets":
    words = [w.strip() for w in Path(ARGS[0]).read_text(encoding="utf-8").splitlines() if w.strip()]
    added: list[str] = []
    data_files = []
    for f in sorted(changed()):
        if re.search(r"\.(zip|pdf|xlsx|csv|ipynb)$", f):
            data_files.append(f)
        path = ROOT / f
        if not path.is_file():
            continue
        diff = git("diff", BASE, "--", f) if f in set(git("ls-files").split()) else ""
        added += [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")] if diff else path.read_text(encoding="utf-8").splitlines()
    sample = Path(ARGS[1]) if len(ARGS) > 1 else None
    texts = list(added)
    if sample is not None and sample.is_file():
        import zipfile
        with zipfile.ZipFile(sample) as bundle:
            texts.append(bundle.read("bundle.json").decode())
    keys = sum(bool(re.search(r"sk-[A-Za-z0-9_-]{16,}", t)) for t in texts)
    names = sum(any(w in t for w in words) for t in texts)
    planted = 0
    if sample is not None and sample.is_file():
        planted = sum(s in texts[-1] for s in ("Gasang-Pw-2026!", "gasang-a", "uploaded_by", "created_by_user_id", "storage_key"))
    print(f"  key_like={keys} forbidden_word_lines={names} words={len(words)} data_files={data_files} added_lines={len(added)}"
          f" sample={'있음' if sample is not None and sample.is_file() else '없음'} planted_in_sample={planted}")
    sys.exit(0 if keys == 0 and names == 0 and not data_files and words and planted == 0 else 1)

if CMD == "trailers":
    text = Path(ARGS[0]).read_text(encoding="utf-8")
    need = ["Ticket: MARC-TICK-309", "Derives-from: MARC-ENT-440", "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"]
    if COMMIT >= 2:
        need += ["Directive: 넣기의 차례(잠금 → 행 → put → etag → 커밋)를 바꾸지 않는다", "Rejected: 저장소 포트 delete"]
    missing = [n for n in need if n not in text]
    print(f"  빠진 트레일러 {missing}")
    sys.exit(0 if not missing else 1)

sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$ROOT" && python3 -I "$HELPER" "$ROOT" "$BASE" "$COMMIT" "$@"); }

if want 1; then
  helper paths > "$S4/1.log" 2>&1; e=$?; cat "$S4/1.log"; report 1 "허용 경로·0줄·지운 줄" "$e"
fi

if want 2; then
  api lint-imports > "$S4/2.log" 2>&1; e=$?
  kept=$(grep -c " KEPT" "$S4/2.log"); broken=$(grep -c " BROKEN" "$S4/2.log")
  summary=$(grep "Contracts:" "$S4/2.log")
  echo "  $summary · KEPT 줄 $kept · BROKEN 줄 $broken"
  want_n=17; [ "$COMMIT" -ge 2 ] && want_n=18
  case "$summary" in *"$want_n kept, 0 broken"*) ;; *) e=1 ;; esac
  if [ "$COMMIT" -ge 2 ]; then grep -q "runbundle 은 업무 모듈과" "$S4/2.log" || e=1; fi
  report 2 "lint-imports(BASE 17 + $((COMMIT - 1)))" "$e"
fi

if want 3; then
  targets="esgapi/core/tests/flows esgapi/core/tests/isolation"
  [ "$COMMIT" -ge 2 ] && targets="esgapi/runbundle $targets"
  # shellcheck disable=SC2086
  api pytest -q -p no:cacheprovider -m "not django_db" $targets > "$S4/3.log" 2>&1; e=$?
  # N0: BASE 에는 esgapi/runbundle·core/tests/flows 가 없다 — 그 몫은 0, isolation 은 BASE 와 같은 시험 수(셈만 바뀜)
  echo "  N1=$(tail -1 "$S4/3.log") (N0 몫: runbundle·flows 0 + isolation 같은 수)"
  report 3 "순수 시험" "$e"
fi

if want 4; then
  e=0
  api python scripts/check_test_layout.py > "$S4/4a.log" 2>&1 || e=1; tail -1 "$S4/4a.log"
  pyr="esgapi/core/flows esgapi/core/service esgapi/runs/service"
  [ "$COMMIT" -ge 2 ] && pyr="esgapi/runbundle tests/security/test_run_bundles.py $pyr"
  # shellcheck disable=SC2086
  api pyright $pyr > "$S4/4b.log" 2>&1 || e=1; tail -1 "$S4/4b.log"
  api ruff check esgapi tests > "$S4/4c.log" 2>&1 || e=1; tail -1 "$S4/4c.log"
  api ruff format --check esgapi tests > "$S4/4d.log" 2>&1 || e=1; tail -1 "$S4/4d.log"
  report 4 "자리·pyright·ruff" "$e"
fi

if want 6; then
  if [ -n "$WITH_CONTAINERS" ]; then
    e=0
    targets="esgapi/core esgapi/runs"
    [ "$COMMIT" -ge 2 ] && targets="esgapi/runbundle $targets"
    start=$(date +%s)
    # shellcheck disable=SC2086
    (cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider -n 2 $targets) > "$S4/6a.log" 2>&1 || e=1
    echo "  업무 $(tail -1 "$S4/6a.log") $(( $(date +%s) - start ))s"
    start=$(date +%s)
    (s3_env; cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$S4/6b.log" 2>&1 || e=1
    echo "  보안 $(tail -1 "$S4/6b.log") $(( $(date +%s) - start ))s"
    report 6 "업무·보안 층" "$e"
  else
    report 6 "업무·보안 층(안 돌림 — --with-containers 없음)" 1
  fi
fi

if want 7 && [ "$COMMIT" -ge 2 ]; then
  if [ -n "$WITH_CONTAINERS" ]; then
    rm -f "$OUT/roundtrip.txt" "$OUT/sample-bundle.zip"
    (s3_env; export RUNBUNDLE_ROUNDTRIP_OUT="$OUT/roundtrip.txt" RUNBUNDLE_SAMPLE_OUT="$OUT/sample-bundle.zip"
     cd "$API_PY" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider -rs \
       tests/security/test_run_bundles.py::test_a_round_trip_through_the_real_storage) > "$S4/7.log" 2>&1; e=$?
    tail -1 "$S4/7.log"
    line=$(cat "$OUT/roundtrip.txt" 2>/dev/null || echo "ROUNDTRIP_DIFF=없음")
    echo "$line"
    [ "$line" = "ROUNDTRIP_DIFF=0" ] || e=1
    report 7 "versitygw 왕복" "$e"
  else
    echo "ROUNDTRIP_DIFF=안 돌림"
    report 7 "versitygw 왕복(안 돌림 — --with-containers 없음)" 1
  fi
fi

# 5 는 7(견본을 짓는다) 뒤에 돈다 — --with-containers 인데 견본이 없으면 실패(② 검증 R1)
if want 5; then
  helper secrets "$FORBIDDEN" "$OUT/sample-bundle.zip" > "$S4/5.log" 2>&1; e=$?; cat "$S4/5.log"
  if [ -n "$WITH_CONTAINERS" ] && [ "$COMMIT" -ge 2 ] && [ ! -f "$OUT/sample-bundle.zip" ]; then
    echo "  견본 없음 — 7 의 왕복이 짓는다"; e=1
  fi
  report 5 "금지 글·키 꼴·데이터 파일·견본의 비밀" "$e"
fi

if want 8 && [ -n "$PLANTED" ]; then
  (s3_env; RX1A_OUT="$OUT" "$API_PY/scripts/planted-breaks-RX1a.sh" ${WITH_CONTAINERS:+--with-containers}) > "$S4/8.log" 2>&1; e=$?
  grep -E "=> |^P0=|^FINGERPRINT=|^PLANTED=" "$S4/8.log"
  report 8 "심은 파손" "$e"
fi

if want 9 && [ -n "$MSG" ]; then
  helper trailers "$MSG" > "$S4/9.log" 2>&1; e=$?; cat "$S4/9.log"; report 9 "트레일러" "$e"
fi

if want 10; then
  (cd "$ROOT" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast) > "$S4/10.log" 2>&1; e=$?
  tail -1 "$S4/10.log"
  grep -q "^VERIFY_FAST=PASS" "$S4/10.log" || e=1
  report 10 "verify.sh --fast" "$e"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
