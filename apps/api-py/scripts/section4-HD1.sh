#!/usr/bin/env bash
# 밴드 HD1 의 §4 자기검증(발주서 band-handoffs/HD1-order.md §4 — archive/section4-RX1b.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝 줄 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-HD1.sh [--commit 1|2|3] [--with-containers] [--planted] [--msg <파일>] [--step 1,2,…]
#     --commit n          경계(기본 3). 1 = 310·207(정적 시험), 2 = + runbundle(405 R1~R7·S2), 3 = + 모듈 줄(S1·S3·347 ①)
#     --with-containers   7 업무·보안 층과 RX1a·RX1b 정상 왕복(② 부터)
#     --planted           8 심은 파손(PLANTED=<잡음>/<분모> — ① 7 · ② 19 · ③ 24 누적)
#     --msg <파일>        9 커밋 메시지 초안의 트레일러
# 단계: 1 허용 경로·0줄 목록·지운 줄(C0)·청 줄 범위·R7 문장 · 2 lint-imports(BASE 18 그대로, 전부 KEPT) ·
#   3 core·runbundle·runs 순수 시험(N0 → N1) · 4 모듈 순수 전부 · 5 check_test_layout·pyright·ruff · 7 업무·보안·왕복 ·
#   6 금지 글(더한 줄 + 메시지 + 견본 bundle.json) · 8 심은 파손 · 9 트레일러 · 10 scripts/verify.sh --fast.
# 환경 변수: S4_OUT(기본 워크트리 곁의 HD1.out) · HD1_BASE(기본 aff154be).
# 컨테이너는 띄우지 않는다(compose esg-app-hd1 이 떠 있어야 한다 — 7·8 의 업무·보안). 공급사를 부르지 않는다(ENVX).
# 저장소 주소(7)는 저장소 맨 위 .env 에서 꺼내 RUNBUNDLE_S3_* 로 넘긴다(값을 찍지 않는다). 묶음 견본은 S4_OUT 에만.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${HD1_BASE:-aff154be}"
OUT="${S4_OUT:-$SIDE/HD1.out}"
S4="$OUT/section4"
FORBIDDEN="$SIDE/G1a.out/forbidden-words.txt"
mkdir -p "$S4"
envx() {
  env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
    -u LLM_RUN_MODE "$@"
}
api() { (cd "$API_PY" && envx uv run --frozen "$@"); }

COMMIT=3
WITH_CONTAINERS=""
PLANTED=""
MSG=""
STEPS="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:?--commit 뒤에 1|2|3}"; shift 2 ;;
    --with-containers) WITH_CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:?--msg 뒤에 파일}"; shift 2 ;;
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
LAST=$(date +%s)
# 줄 끝의 <n>s 는 앞 report 뒤 지난 초(① 검증 권고 R2)
report() {
  now=$(date +%s); echo "[$1] $2 EXIT=$3 $((now - LAST))s"; LAST=$now; [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}
env_value() { sed -n "s/^$1=//p" "$ROOT/.env" | tail -1; }
s3_env() {
  export RUNBUNDLE_S3_ENDPOINT="http://127.0.0.1:$(env_value STORAGE_PORT)"
  export RUNBUNDLE_S3_BUCKET="$(env_value S3_BUCKET)" RUNBUNDLE_S3_REGION="$(env_value S3_REGION)"
  export RUNBUNDLE_S3_ACCESS_KEY="$(env_value STORAGE_ACCESS_KEY)" RUNBUNDLE_S3_SECRET_KEY="$(env_value STORAGE_SECRET_KEY)"
}

echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD) COMMIT=$COMMIT"

HELPER="$S4/hd1_helper.py"
cat > "$HELPER" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

ROOT, BASE, COMMIT, CMD, ARGS = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5:]
P = r"^apps/api-py/"
E = P + r"esgapi/"
A = "apps/api-py/"
EA = A + "esgapi/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def changed() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


ALLOWED_1 = [  # §1-2 ① — 310 · 207(온실가스 fb 허락) · 새 스크립트 둘(테스트 f0 알림)
    E + r"core/tests/test_selector_scope\.py$",
    E + r"inventory/tests/(test_scope3_is_pure|test_s3sheets_is_pure|test_flows|engines/scope3/colab_157/test_purity)\.py$",
    E + r"reference/tests/test_calc_is_pure\.py$",
    P + r"scripts/(section4|planted-breaks)-HD1\.sh$",
]
ALLOWED_2 = [  # §1-2 ② — runbundle 땅 · 분모 두 줄
    E + r"runbundle/",
    E + r"core/tests/(test_transaction_rules|isolation/test_static_rules)\.py$",
]
ALLOWED_3 = [  # §1-2 ③ — runs 새 selector · 머리말 글 · 청 줄 셋(영문번역 cd · 그린워싱 8e · 데이터 검증 cd)
    E + r"runs/service/selectors/runs\.py$",
    E + r"runs/models\.py$",
    E + r"runs/tests/service/selectors/test_runs\.py$",
    E + r"translation/service/actions/bundle\.py$",
    E + r"translation/tests/service/actions/test_bundle_carrier\.py$",
    E + r"greenwash/service/actions/bundle\.py$",
    E + r"greenwash/tests/service/actions/test_bundle_carrier\.py$",
    E + r"dataverify/service/actions/runs\.py$",
    E + r"dataverify/tests/service/apis/test_dataverify_runs\.py$",
]
ZERO = [  # §1-2 「0줄」
    E + r"runs/service/selectors/bundle\.py$", E + r"runs/service/services/", E + r"core/(service|flows|llm)/",
    E + r"(reconcile|materiality)/", E + r"[a-z_]+/migrations/", E + r"[a-z_]+/contracts/", E + r"[a-z_]+/service/apis/",
    E + r"config/", P + r"(tests|tests_integration|generated)/", r"(^|/)conftest\.py$",
    P + r"(\.importlinter|purity\.importlinter|pyproject\.toml|uv\.lock)$", r"^apps/web/", r"^infra/",
    r"(^|/)compose\.yaml$", r"^docs/", r"^scripts/verify\.sh$", P + r"scripts/(verify|planted-breaks|test-business)\.sh$",
    P + r"scripts/(archive/)?(section4|planted-breaks)-RX1[ab]\.sh$",
]
# 있는 시험의 지운 줄(C0 · ① 은 청 줄 — 바꾼 함수 몸). 정확한 줄 글.
MINUS_OK: dict[str, set[str]] = {
    EA + "core/tests/test_selector_scope.py": {
        "  core/tests/isolation/test_static_rules.py 가 제품 전체에서 본다). pk 조건이 빠진 것도 보지 않는다",
    },
    EA + "inventory/tests/test_flows.py": {
        '        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):',
        "            names = (",
        '                [node.module or ""]',
        "                if isinstance(node, ast.ImportFrom)",
        "                else [a.name for a in node.names]",
        "                if isinstance(node, ast.Import)",
        "                else []",
        "            )",
        '            hits += [f"{path.name}: {n}" for n in names if n.startswith(forbidden)]',
    },
    EA + "reference/tests/test_calc_is_pure.py": {
        "def _imports(tree: ast.AST) -> set[str]:",
        '            found.add(node.module or "")',
    },
}
for _f in ("inventory/tests/test_scope3_is_pure.py", "inventory/tests/test_s3sheets_is_pure.py",
           "inventory/tests/engines/scope3/colab_157/test_purity.py"):
    MINUS_OK[EA + _f] = {
        "def imported_modules(path: Path) -> set[str]:",
        "    names: set[str] = set()",
        '    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):',
        '    for node in every_node(ast.parse(path.read_text(encoding="utf-8"))):',
        "        if isinstance(node, ast.Import):",
        "            names.update(alias.name for alias in node.names)",
        "        elif isinstance(node, ast.ImportFrom) and node.module is not None:",
        "            names.add(node.module)",
        "    return names",
    }
# ② C0(감독 통과 뒤 채움) — RB/tests 의 바뀐 줄 · 분모 두 줄
MINUS_OK_2: dict[str, set[str]] = {  # 감독 「C0 통과」(375 노트 10-29) 표 1~5
    EA + "runbundle/tests/service/actions/test_import_.py": {
        "from esgapi.runbundle.service.actions.export import RunIds, migration_graph, model_columns",
    },
    EA + "runbundle/tests/service/actions/test_import_zip.py": {
        '    bundle, blobs = read_bundle(write(tmp_path / "b.zip", members()), 10_000)',
        '    assert blobs == BLOBS and bundle.bundle_id == good()["bundleId"]',
    },
    EA + "core/tests/test_transaction_rules.py": {"    assert len(files) == 52, ["},
    EA + "core/tests/isolation/test_static_rules.py": {
        '    "find_company_by_id": frozenset({"user/service/apis/users.py", "runbundle/service/actions/export.py"}),',
    },
}
MINUS_RE_2: dict[str, list[str]] = {}
# 청 줄의 BASE 범위(@@ 덩이가 이 안에서만). (시작, 끝) — 끝 포함. 더하기만인 곳은 넣는 자리.
RANGES = {
    EA + "translation/service/actions/bundle.py": [(22, 22), (53, 55)],
    EA + "greenwash/service/actions/bundle.py": [(95, 102)],
    # :75-87 _items — 새 투영 셈은 _items 바로 뒤 빈 두 줄(BASE :88-89) 다음에 넣힘(git 의 덩이 맞춤)
    EA + "dataverify/service/actions/runs.py": [(1, 15), (33, 35), (75, 89), (115, 136), (149, 163)],
    EA + "runs/models.py": [(60, 63)],
    EA + "core/tests/test_transaction_rules.py": [(326, 353)],
    EA + "core/tests/isolation/test_static_rules.py": [(65, 66)],
}
ADD_ONLY = {EA + "greenwash/service/actions/bundle.py"}
# runs selector: run_page·run_of 줄 0(BASE 179-200 · 260-296)
FORBIDDEN_RANGES = {EA + "runs/service/selectors/runs.py": [(179, 200), (260, 296)]}
FREE_MINUS = (EA + "runbundle/service/", EA + "runbundle/calc/", EA + "runbundle/management/",
              EA + "runs/service/selectors/runs.py", EA + "translation/service/", EA + "greenwash/service/",
              EA + "dataverify/service/", EA + "runs/models.py", A + "scripts/section4-HD1.sh",
              A + "scripts/planted-breaks-HD1.sh")


def hunks(f: str) -> list[tuple[int, int]]:
    out = []
    for line in git("diff", "-U0", BASE, "--", f).splitlines():
        m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", line)
        if m:
            out.append((int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)))
    return out


def inside(start: int, count: int, ranges: list[tuple[int, int]]) -> bool:
    if count == 0:  # 넣기만: start 줄 뒤에 넣음
        return any(s - 1 <= start <= e for s, e in ranges)
    return any(s <= start and start + count - 1 <= e for s, e in ranges)


def overlaps(start: int, count: int, ranges: list[tuple[int, int]]) -> bool:
    last = start + max(count, 1) - 1
    return any(not (last < s or start > e) for s, e in ranges)


if CMD == "paths":
    files = sorted(changed())
    allowed = ALLOWED_1 + (ALLOWED_2 if COMMIT >= 2 else []) + (ALLOWED_3 if COMMIT >= 3 else [])
    outside = [f for f in files if not any(re.search(p, f) for p in allowed)]
    zero = [f for f in files if any(re.search(p, f) for p in ZERO)]
    tracked = set(git("ls-files").split())
    bad_minus, bad_range, add_only, forbidden = [], [], [], []
    minus_ok = {**MINUS_OK, **MINUS_OK_2}
    for f in files:
        if f not in tracked:
            continue
        for start, count in hunks(f):
            if f in RANGES and not inside(start, count, RANGES[f]):
                bad_range.append(f"{f}: -{start},{count}")
            if f in ADD_ONLY and count > 0:
                add_only.append(f"{f}: -{start},{count}")
            if f in FORBIDDEN_RANGES and overlaps(start, count, FORBIDDEN_RANGES[f]):
                forbidden.append(f"{f}: -{start},{count}")
        if f.startswith(FREE_MINUS):
            continue
        minus = [l[1:] for l in git("diff", BASE, "--", f).splitlines() if l.startswith("-") and not l.startswith("---")]
        ok = minus_ok.get(f, set())
        pats = MINUS_RE_2.get(f, [])
        bad_minus += [f"{f}: {l}" for l in minus if l not in ok and not any(re.search(p, l) for p in pats)]
    models_out = []
    if EA + "runs/models.py" in files:
        models_out = [h for h in hunks(EA + "runs/models.py") if not inside(*h, [(60, 63)])]
    r7 = ""
    if COMMIT >= 2:
        pg = (ROOT / EA / "runbundle/service/actions/_pg.py").read_text(encoding="utf-8")
        base_pg = git("show", f"{BASE}:{EA}runbundle/service/actions/_pg.py")
        rx = re.compile(r"READ COMMITTED.*\n?.*REPEATABLE READ", re.S)
        r7 = f" · R7 문장 {'있음' if rx.search(pg) else '없음'}(BASE {'있음' if rx.search(base_pg) else '없음 — 양성 대조'})"
        if not rx.search(pg) or rx.search(base_pg):
            bad_range.append("R7 문장")
    print(f"  바뀐 파일 {len(files)} · outside={len(outside)} {outside}")
    print(f"  0줄 경로 {zero}{r7}")
    print(f"  허락 밖 지운 줄 {len(bad_minus)} · 청 범위 밖 덩이 {bad_range} · 더하기만 어김 {add_only}"
          f" · run_page·run_of 덩이 {forbidden} · models 머리말 밖 {models_out}")
    for line in bad_minus:
        print(f"    {line}")
    sys.exit(0 if not (outside or zero or bad_minus or bad_range or add_only or forbidden or models_out) else 1)

if CMD == "secrets":
    words = [w.strip() for w in Path(ARGS[0]).read_text(encoding="utf-8").splitlines() if w.strip()]
    msg = Path(ARGS[1]) if len(ARGS) > 1 and ARGS[1] else None
    added: list[str] = []
    data_files = []
    tracked = set(git("ls-files").split())
    for f in sorted(changed()):
        if re.search(r"\.(zip|pdf|xlsx|csv|ipynb|docx)$", f):
            data_files.append(f)
        path = ROOT / f
        if not path.is_file():
            continue
        if f in tracked:
            diff = git("diff", BASE, "--", f)
            added += [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
        else:
            added += path.read_text(encoding="utf-8").splitlines()
    texts = list(added)
    if msg is not None and msg.is_file():
        texts += msg.read_text(encoding="utf-8").splitlines()
    samples = [Path(s) for s in ARGS[2:] if Path(s).is_file()]
    import zipfile
    for sample in samples:
        with zipfile.ZipFile(sample) as bundle:
            texts.append(bundle.read("bundle.json").decode())
    keys = sum(bool(re.search(r"sk-[A-Za-z0-9_-]{16,}", t)) for t in texts)
    paths = sum(bool(re.search(r"marcspon-openai\.env|manufac-erp/spike/\.env", t)) for t in texts)
    names = sum(any(w in t for w in words) for t in texts)
    # 양성 대조: 같은 정규식이 지어낸 키 꼴을 잡는다
    assert re.search(r"sk-[A-Za-z0-9_-]{16,}", "sk-" + "A" * 20)
    print(f"  key_like={keys} key_paths={paths} forbidden_word_lines={names} words={len(words)} data_files={data_files}"
          f" added_lines={len(added)} msg={'있음' if msg is not None and msg.is_file() else '없음'} samples={len(samples)}")
    sys.exit(0 if keys == 0 and paths == 0 and names == 0 and not data_files and words else 1)

if CMD == "trailers":
    text = Path(ARGS[0]).read_text(encoding="utf-8")
    need = ["Ticket: MARC-TICK-375", "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
            "Constraint: 모듈 실행 결과·정상 입력의 동작 0 바뀜 — 꾸민 입력의 거절 꼴과 내부 읽기만(MARC-ENT-442)",
            "Directive: 묶음 상한은 넣기 기본 상한 상수 하나에서 — 새 숫자는 감독 처분 뒤(운영 규칙 4)"]
    need += {1: ["Concerns: MARC-ISSUE-310", "Concerns: MARC-ISSUE-207"],
             2: ["Concerns: MARC-ISSUE-405"],
             3: ["Concerns: MARC-ISSUE-405", "Concerns: MARC-ISSUE-347"]}[COMMIT]
    missing = [n for n in need if n not in text]
    print(f"  빠진 트레일러 {missing}")
    sys.exit(0 if not missing else 1)

sys.exit(f"모르는 CMD {CMD}")
PY
helper() { (cd "$ROOT" && python3 -I "$HELPER" "$ROOT" "$BASE" "$COMMIT" "$@"); }

if want 1; then
  helper paths > "$S4/1.log" 2>&1; e=$?; cat "$S4/1.log"; report 1 "허용 경로·0줄·지운 줄·청 범위·R7" "$e"
fi

if want 2; then
  api lint-imports > "$S4/2.log" 2>&1; e=$?
  kept=$(grep -c " KEPT" "$S4/2.log"); broken=$(grep -c " BROKEN" "$S4/2.log")
  summary=$(grep "Contracts:" "$S4/2.log")
  echo "  $summary · KEPT 줄 $kept · BROKEN 줄 $broken"
  case "$summary" in *"18 kept, 0 broken"*) ;; *) e=1 ;; esac
  report 2 "lint-imports(BASE 18 그대로 — 전부 KEPT)" "$e"
fi

if want 3; then
  api pytest -q -p no:cacheprovider -m "not django_db" esgapi/core/tests esgapi/runbundle esgapi/runs/tests \
    > "$S4/3.log" 2>&1; e=$?
  # N0(BASE aff154be 의 같은 명령): 2066 passed — 보고에 적은 수(BASE 체크아웃 0, ① 이 더한 2 를 뺀 값)
  echo "  N0=2066 N1=$(tail -1 "$S4/3.log")"
  report 3 "core·runbundle·runs 순수 시험" "$e"
fi

if want 4; then
  api pytest -q -p no:cacheprovider -m "not django_db" -n 4 esgapi > "$S4/4.log" 2>&1; e=$?
  echo "  $(tail -1 "$S4/4.log")"
  report 4 "모듈 순수 전부(esgapi, not django_db)" "$e"
fi

if want 5; then
  e=0
  api python scripts/check_test_layout.py > "$S4/5a.log" 2>&1 || e=1; tail -1 "$S4/5a.log"
  pyr=$(cd "$ROOT" && { git diff --name-only "$BASE"; git ls-files --others --exclude-standard; } \
    | sed -n 's#^apps/api-py/\(.*\.py\)$#\1#p' | sort -u | while read -r f; do [ -f "$API_PY/$f" ] && echo "$f"; done)
  # shellcheck disable=SC2086
  api pyright $pyr > "$S4/5b.log" 2>&1 || e=1; tail -1 "$S4/5b.log"
  api ruff check esgapi tests scripts > "$S4/5c.log" 2>&1 || e=1; tail -1 "$S4/5c.log"
  api ruff format --check esgapi tests scripts > "$S4/5d.log" 2>&1 || e=1; tail -1 "$S4/5d.log"
  report 5 "자리·pyright(바뀐 파일)·ruff" "$e"
fi

if want 7; then
  if [ -n "$WITH_CONTAINERS" ] && [ "$COMMIT" -ge 2 ]; then
    e=0
    targets="esgapi/runbundle esgapi/runs esgapi/core"
    [ "$COMMIT" -ge 3 ] && targets="$targets esgapi/dataverify esgapi/greenwash esgapi/translation"
    start=$(date +%s)
    # shellcheck disable=SC2086
    (cd "$API_PY" && envx scripts/test-business.sh -p no:cacheprovider -n 4 $targets) > "$S4/7a.log" 2>&1 || e=1
    echo "  업무 $(tail -1 "$S4/7a.log") $(( $(date +%s) - start ))s"
    rm -f "$OUT/roundtrip.txt" "$OUT/sample-bundle.zip" "$OUT/module-roundtrip.txt" "$OUT/module-sample-bundle.zip"
    (s3_env; export RUNBUNDLE_ROUNDTRIP_OUT="$OUT/roundtrip.txt" RUNBUNDLE_SAMPLE_OUT="$OUT/sample-bundle.zip" \
       RUNBUNDLE_MODULE_ROUNDTRIP_OUT="$OUT/module-roundtrip.txt" RUNBUNDLE_MODULE_SAMPLE_OUT="$OUT/module-sample-bundle.zip"
     cd "$API_PY" && envx scripts/test-security.sh -p no:cacheprovider -rs \
       tests/security/test_run_bundles.py::test_a_round_trip_through_the_real_storage \
       tests/security/test_run_bundles.py::test_module_runs_round_trip_through_the_real_storage) > "$S4/7b.log" 2>&1 || e=1
    line=$(cat "$OUT/roundtrip.txt" 2>/dev/null || echo "ROUNDTRIP_DIFF=없음")
    mline=$(cat "$OUT/module-roundtrip.txt" 2>/dev/null || echo "ROUNDTRIP_DIFF=없음")
    echo "  왕복 $(tail -1 "$S4/7b.log") · RX1a 시험 모듈 $line · RX1b 모듈 넷 $mline"
    [ "$line" = "ROUNDTRIP_DIFF=0" ] && [ "$mline" = "ROUNDTRIP_DIFF=0" ] || e=1
    start=$(date +%s)
    (s3_env; cd "$API_PY" && envx scripts/test-security.sh -p no:cacheprovider) > "$S4/7c.log" 2>&1 || e=1
    echo "  보안 $(tail -1 "$S4/7c.log") $(( $(date +%s) - start ))s"
    report 7 "업무·왕복 둘·보안 층" "$e"
  elif [ "$COMMIT" -ge 2 ]; then
    report 7 "업무·왕복·보안(안 돌림 — --with-containers 없음)" 1
  fi
fi

# 6 은 7(견본을 짓는다) 뒤에 돈다
if want 6; then
  samples=""
  [ -n "$WITH_CONTAINERS" ] && samples="$OUT/sample-bundle.zip $OUT/module-sample-bundle.zip"
  # shellcheck disable=SC2086
  helper secrets "$FORBIDDEN" "$MSG" $samples > "$S4/6.log" 2>&1; e=$?; cat "$S4/6.log"
  report 6 "금지 글·키 꼴·키 경로·데이터 파일·견본" "$e"
fi

if want 8 && [ -n "$PLANTED" ]; then
  (s3_env; HD1_OUT="$OUT" HD1_BASE="$BASE" "$API_PY/scripts/planted-breaks-HD1.sh" --commit "$COMMIT" \
     ${WITH_CONTAINERS:+--with-containers}) > "$S4/8.log" 2>&1; e=$?
  grep -E "=> |^P0=|^BASE_CONTROL=|^EXTRA=|^FINGERPRINT=|^PLANTED=" "$S4/8.log"
  report 8 "심은 파손(분모 ① 7 · ② 19 · ③ 24)" "$e"
fi

if want 9 && [ -n "$MSG" ]; then
  helper trailers "$MSG" > "$S4/9.log" 2>&1; e=$?; cat "$S4/9.log"; report 9 "트레일러" "$e"
fi

if want 10; then
  (cd "$ROOT" && envx scripts/verify.sh --fast) > "$S4/10.log" 2>&1; e=$?
  tail -1 "$S4/10.log"
  grep -q "^VERIFY_FAST=PASS" "$S4/10.log" || e=1
  report 10 "verify.sh --fast" "$e"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
