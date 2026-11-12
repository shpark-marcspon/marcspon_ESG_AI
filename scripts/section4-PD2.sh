#!/usr/bin/env bash
# 밴드 PD2 (MARC-TICK-55) 의 §4 자기검증. 줄마다 `EXIT=` 을 찍는다. 저장소 뿌리에서:
#
#   scripts/section4-PD2.sh            # 전부 (골든 다시 만들기 → 호스트 → 컨테이너 → verify.sh → 경계)
#   G=<앞선 실행의 G> scripts/section4-PD2.sh planted    # 심은 파손 (끝나면 작업 트리가 처음과 같은지 해시로 본다)
#
# 환경 변수: G(골든·산출을 둘 저장소 밖 폴더. 기본 mktemp), SKIP_VERIFY=1(전체 verify.sh 를 건너뛴다),
#            ONLY="gold host nopymupdf container verify bounds" 가운데 고른 단계만(기본 전부. 나눠 돌릴 때는 같은 G 를 준다),
#            LAB·REPORTS(esg-lab 과 공개 보고서 PDF 의 자리).
# 무효 조건: 골든은 esg-lab 2e2c2c4 와 pypdfium2 5.14.0 에 묶여 있다. 둘 중 하나가 바뀌면 「같다」는 다시 재야 한다.
#            verify.sh 는 네 문서를 재지 않는다(원본이 git 밖). 네 문서 골든은 이 스크립트만 지킨다.
set -u
cd "$(dirname "$0")/.."
ROOT=$PWD
LAB=${LAB:-/Users/leedongeon/Desktop/marcspon/esg-lab}
REPORTS=${REPORTS:-/Users/leedongeon/Desktop/marcspon/prework/reports}
PD1=2e2c2c4
BASE=6aaa84e
DOCS="kb_2025_kor kb_2025_databook_kor samsung_2026_kor cosmax_2025_kor"
P=services/parser
TOOLS="python3 $ROOT/$P/scripts/s4_tools.py"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
FAILED=0
ONLY=${ONLY:-gold host nopymupdf container verify bounds}
want() { case " $ONLY " in *" $1 "*) return 0;; esac; echo "── ($1 단계는 ONLY 에 없어 건너뛴다)"; return 1; }

# step <이름> <명령...> : 명령을 돌리고 `EXIT=<코드>  # <이름>` 을 찍는다.
step() {
  local name=$1; shift
  echo "── $name"
  "$@"
  local code=$?
  echo "EXIT=$code  # $name"
  [ $code -eq 0 ] || FAILED=$((FAILED + 1))
  return 0
}
in_parser() { (cd "$ROOT/$P" && "$@"); }
quiet() { "$@" > "$G/last.log" 2>&1 || { local c=$?; tail -25 "$G/last.log"; return $c; }; tail -${TAIL:-3} "$G/last.log"; }
# 컨테이너 단계 앞: 메모리 여유 20% 이상, 1분 부하 12 미만이 될 때까지 30초마다, 최대 10분.
wait_for_room() {
  [ "${WAIT_ROOM:-1}" = 0 ] && { echo "기계(기다림은 밖에서 함): $(memory_pressure | grep percentage) / $(uptime | sed 's/.*load/load/')"; return 0; }
  for _ in $(seq 20); do
    local free load
    free=$(memory_pressure | awk '/percentage/ {gsub("%",""); print $NF}')
    load=$(uptime | sed 's/.*load averages: //' | awk '{print int($1)}')
    [ "${free:-0}" -ge 20 ] && [ "${load:-99}" -lt 12 ] && break
    sleep 30
  done
  echo "기계: $(memory_pressure | grep percentage) / $(uptime | sed 's/.*load/load/')"
}

# ══ 심은 파손 ═══════════════════════════════════════════════════════════
if [ "${1:-}" = "planted" ]; then
  # 네 문서·정답이 필요한 파손(5, 6)은 G(앞선 전체 실행의 산출 폴더)가 있어야 잰다:  G=<폴더> scripts/section4-PD2.sh planted
  exec env REPORTS="$REPORTS" python3 "$ROOT/$P/scripts/planted.py"
fi

G=${G:-$(mktemp -d)}
mkdir -p "$G/gold" "$G/app" "$G/http" "$G/httpsplit" "$G/facts"
echo "산출 폴더 G=$G"
# 나눠 돌릴 때는 첫 실행이 적은 「앞」을 그대로 둔다.
[ -f "$G/lab-before" ] || git -C "$LAB" status --porcelain | shasum > "$G/lab-before"
[ -f "$G/pd1-before" ] || git -C "$LAB.worktrees/PD1" status --porcelain 2>/dev/null | shasum > "$G/pd1-before"

# ══ 1. 골든: esg-lab 2e2c2c4 를 저장소 밖에 풀어 `--engine pdfium` 으로 ══
if want gold; then
unpack_lab() { rm -rf "$G/lab" && mkdir -p "$G/lab" && git -C "$LAB" archive $PD1 py schemas data/gold | tar -x -C "$G/lab"; }
step "esg-lab $PD1 을 저장소 밖($G/lab)에 푼다" unpack_lab
step "골든 쪽 venv (실험실 도구. esg-app 의 것이 아니다)" quiet bash -c "cd '$G/lab/py' && uv sync --frozen"
for d in $DOCS; do
  step "골든 $d" quiet bash -c "cd '$G/lab/py' && DOCPARSE_REPORTS_DIR='$REPORTS' uv run python -m docparse parse '$REPORTS/$d.pdf' --out '$G/gold/$d' --places --engine pdfium"
done
step "골든 여덟의 sha256 == PD1 기록 여덟" $TOOLS sha "$G/gold"

fi

# ══ 2. 호스트: 단위·HTTP·옛 계약, 정답 15표, 네 문서 ══════════════════
if want host; then
step "parser venv" quiet uv sync --project $P --frozen
step "단위·HTTP·옛 계약 (원본 없이. verify.sh 가 도는 것과 같은 명령)" quiet env -u PARSER_REPORTS_DIR -u PARSER_GOLD_DIR uv run --project $P --frozen pytest -q $P
step "정답 15표 1,496칸의 하한 (reports)" quiet env PARSER_REPORTS_DIR="$REPORTS" PARSER_GOLD_DIR="$G/lab/data/gold" uv run --project $P --frozen pytest -q $P -m reports
no_env_fails() { ! env -u PARSER_REPORTS_DIR -u PARSER_GOLD_DIR uv run --project $P --frozen pytest -q $P -m reports > "$G/noenv.log" 2>&1; tail -1 "$G/noenv.log"; ! grep -q " passed" "$G/noenv.log" && grep -q "PARSER_GOLD_DIR\|PARSER_REPORTS_DIR" "$G/noenv.log"; }
step "원본·정답이 없으면 reports 테스트는 건너뛰지 않고 실패한다 (통과 0)" no_env_fails
step "골든 쪽 점수" quiet bash -c "cd '$G/lab/py' && DOCPARSE_REPORTS_DIR='$REPORTS' uv run python -m docparse score --gold '$G/lab/data/gold' --json '$G/gold/score.json' --engine pdfium"
step "앱 쪽 점수" quiet env PARSER_REPORTS_DIR="$REPORTS" bash -c "cd '$ROOT/$P' && uv run --frozen python -m docparse score --gold '$G/lab/data/gold' --json '$G/app/score.json'"
step "점수의 같음: 앱 score.json == 골든 score.json (JSON 값)" $TOOLS score "$G/app/score.json" "$G/gold/score.json"
for d in $DOCS; do
  step "앱(호스트) $d" quiet bash -c "cd '$ROOT/$P' && uv run --frozen python -m docparse parse '$REPORTS/$d.pdf' --out '$G/app/$d' --places"
done
step "호스트 산출 대 골든: 여덟 파일 JSON 값, 수의 표, U+0007" $TOOLS same "$G/app" "$G/gold"
for d in $DOCS; do
  step "값 후보 $d (esg-lab ts 의 facts 를 실행만)" quiet bash -c "cd '$LAB/ts' && pnpm -F reconcile exec tsx src/cli.ts facts '$G/app/$d/document.json' --out '$G/facts/$d'"
done
step "값 후보의 수 2,938 · 1,292 · 2,049 · 2,476" $TOOLS facts "$G/facts"

fi

# ══ 3. pymupdf 가 없는가 (잠금, 소스) ═════════════════════════════════
if want nopymupdf; then
no_lock_word() { ! grep -qiE 'pymupdf|fitz' $P/pyproject.toml $P/uv.lock; }
step "pyproject.toml·uv.lock 에 낱말 pymupdf·fitz 0" no_lock_word
no_import() { test -z "$(grep -rnE '^\s*(import|from)\s+(pymupdf|fitz)\b' $P --include='*.py' --exclude-dir=.venv)"; }
step "services/parser 의 *.py 에 import pymupdf·fitz 0 (.venv 제외)" no_import
no_installed() { in_parser uv run --frozen python -c "import importlib.util as u, sys; bad=[n for n in ('pymupdf','fitz') if u.find_spec(n)]; print('호스트 venv 에 설치된 것:', bad); sys.exit(1 if bad else 0)"; }
step "호스트 venv(dev 포함)에 pymupdf·fitz 0" no_installed
step "파일마다 원본($PD1)과의 diff 줄 수. 규칙·엔진 열하나는 0" $TOOLS difflines "$LAB" $PD1 $P/docparse

fi

# ══ 4. 컨테이너 ══════════════════════════════════════════════════════
if want container; then
wait_for_room
compose_up() { docker compose build parser > "$G/build.log" 2>&1 || { tail -30 "$G/build.log"; return 1; }; grep -iE 'pypdfium2|Building|sdist' "$G/build.log" | head -5; docker compose up -d --wait parser 2>&1 | tail -2; }
step "parser 이미지를 짓고 띄운다" compose_up
step "이미지 안 venv 의 python 으로 본 설치 목록 (pymupdf·fitz·pytest 0. 이 목록이 라이선스 표의 분모)" docker compose exec -T parser python -c "import importlib.util as u,importlib.metadata as m,sys; bad=[n for n in ('pymupdf','fitz','pytest') if u.find_spec(n)]; print(sys.executable, sys.version.split()[0]); print(sorted(d.metadata['Name']+'=='+d.version for d in m.distributions())); print('있어서는 안 되는 것:', bad); sys.exit(1 if bad else 0)"
not_root_no_tests() { local uid; uid=$(docker compose exec -T parser id -u | tr -d '\r'); echo "uid=$uid"; test "$uid" != 0 && ! docker compose exec -T parser test -e /app/tests && ! docker compose exec -T parser test -e /app/test_app.py && docker compose exec -T parser ls /app; }
step "루트가 아니고 /app 에 tests·test_app.py 가 없다" not_root_no_tests
step "컨테이너 안의 pdfium 판과 플랫폼" docker compose exec -T parser python -c "import pypdfium2 as p, platform; print('pypdfium2', p.PYPDFIUM_INFO, '/ pdfium', p.PDFIUM_INFO, '/', platform.platform(), platform.machine())"
step "호스트의 pdfium 판과 플랫폼" in_parser uv run --frozen python -c "import pypdfium2 as p, platform; print('pypdfium2', p.PYPDFIUM_INFO, '/ pdfium', p.PDFIUM_INFO, '/', platform.platform(), platform.machine())"
post() { docker compose run --rm --no-deps -T -v "$REPORTS:/reports:ro" -v "$ROOT/$P/scripts:/s:ro" parser python /s/post_pdf.py http://parser:8000/parse "/reports/$1.pdf" > "$G/http/$1.json"; }
for d in $DOCS; do
  step "컨테이너 HTTP $d (응답은 표준 출력으로. 쓰기 마운트 없음)" post "$d"
done
step "HTTP 답에 document·charPlaces 가 넷 다 있다" $TOOLS split "$G/http" "$G/httpsplit"
step "컨테이너 HTTP 산출 대 골든: 여덟 파일 JSON 값, 수의 표, U+0007" $TOOLS same "$G/httpsplit" "$G/gold"
refusals() {
  local out bad=0
  printf 'not a pdf at all' > "$G/notpdf.bin"; : > "$G/empty.bin"
  check() {  # <이름> <기대 상태와 code> <파일> [content-type]
    out=$(docker compose run --rm --no-deps -T -v "$G:/g:ro" -v "$ROOT/$P/scripts:/s:ro" parser python /s/post_pdf.py http://parser:8000/parse "/g/$3" ${4:+"$4"} 2>&1)
    echo "$1: $(echo "$out" | tr '\n' ' ' | cut -c1-200)"
    echo "$out" | grep -q "status=${2%% *}" && echo "$out" | grep -q "\"code\":\"${2##* }\"" || bad=1
  }
  check "PDF 아님" "422 not_a_pdf" notpdf.bin
  check "빈 본문" "422 empty_body" empty.bin
  check "text/plain" "415 unsupported_media_type" notpdf.bin text/plain
  return $bad
}
step "컨테이너의 거절 갈래 셋 (옛 계약 JSON 은 verify.sh 의 flow 가 잰다)" refusals
step "컨테이너 healthz 가 분해 중에도 답했는가: 지금 상태 healthy" bash -c "docker compose ps parser --format '{{.Health}}' | grep -x healthy"
licenses() {
  docker compose exec -T parser python -c "
import importlib.metadata as m, re
for d in sorted(m.distributions(), key=lambda d: d.metadata['Name'].lower()):
    md = d.metadata
    lic = md.get('License-Expression') or (md.get('License') or '').splitlines()[0:1] or [c.split(' :: ')[-1] for c in md.get_all('Classifier', []) if c.startswith('License')]
    files = sorted(str(f) for f in (d.files or []) if '/licenses/' in str(f) or re.search(r'(LICEN[CS]E|COPYING|NOTICE)', str(f).split('/')[-1]))
    print(md['Name'], md['Version'], '|', lic, '|', [f.split('dist-info/')[-1] for f in files])
import pathlib
hits = []
for f in sorted(pathlib.Path(str(p.locate())) for p in (m.distribution('pypdfium2').files or []) if '/licenses/' in str(p)):
    for n, line in enumerate(f.read_text(errors='replace').splitlines(), 1):
        if re.search(r'GPL|General Public', line):
            hits.append(f'{f.name}:{n}: {line.strip()[:160]}')
print('pypdfium2 licenses/ 안에서 낱말 GPL 이 든 줄:', len(hits))
print('\n'.join(hits[:40]))
"
}
step "이미지 안 의존성의 License 줄과 licenses/ 파일 (판정이 아니라 기록)" licenses
step "컨테이너를 내린다" bash -c "docker compose down -v 2>&1 | tail -1"

fi

# ══ 5. 전체 확인과 경계 ═══════════════════════════════════════════════
if want verify; then
if [ "${SKIP_VERIFY:-}" = 1 ]; then
  echo "── scripts/verify.sh 는 SKIP_VERIFY=1 이라 건너뛰었다 (EXIT 줄 없음 = 안 돌린 게이트)"
else
  wait_for_room
  TAIL=12 step "scripts/verify.sh (Node 22)" quiet scripts/verify.sh
  step "verify.sh 뒤 이 워크트리의 컨테이너를 내린다" bash -c "docker compose down -v 2>&1 | tail -1"
fi
fi

if want bounds; then
lab_untouched() { git -C "$LAB" status --porcelain | shasum | diff - "$G/lab-before" && git -C "$LAB.worktrees/PD1" status --porcelain 2>/dev/null | shasum | diff - "$G/pd1-before"; }
step "esg-lab 과 esg-lab.worktrees/PD1 의 git status 가 앞뒤로 같다" lab_untouched
step "있는 통합 파일 0줄" test -z "$(git diff --name-only --diff-filter=MDR $BASE -- tests/integration)$(git status --porcelain -- tests/integration | grep -v '^??')"
step "apps·packages 는 새 파일도 0" test -z "$(git diff --name-only $BASE -- apps packages)$(git status --porcelain -- apps packages)"
ALLOWED='^(services/parser/|docker/parser\.Dockerfile$|compose\.yaml$|scripts/verify\.sh$|scripts/section4-PD2\.sh$|tests/integration/|README\.md$)'
step "커밋된 것 가운데 허용 경로 밖 0" test -z "$(git diff --name-only $BASE HEAD | grep -v -E "$ALLOWED")"
step "작업 트리에서 허용 경로 밖 0" test -z "$(git status --porcelain | cut -c4- | grep -v -E "$ALLOWED")"
shared_lines() {
  # compose.yaml 은 parser: 블록 안, verify.sh 는 parser 단계의 한 줄만 바뀔 수 있다. 바뀐 줄을 찍고 그 밖이면 실패.
  local bad=0 lines
  lines=$(git diff -U0 $BASE -- scripts/verify.sh | grep -E '^[+-][^+-]' || true)
  [ -n "$lines" ] && echo "verify.sh 의 바뀐 줄: $lines"
  echo "$lines" | grep -v -E 'services/parser|^$' | grep -q . && bad=1
  python3 - "$BASE" <<'PY' || bad=1
import re, subprocess, sys
diff = subprocess.run(["git", "diff", "-U0", sys.argv[1], "--", "compose.yaml"], capture_output=True, text=True).stdout
new = open("compose.yaml", encoding="utf-8").read().splitlines()
start = next(i for i, l in enumerate(new, 1) if l.rstrip() == "  parser:")
end = next((i for i, l in enumerate(new[start:], start + 1) if l and not l.startswith("    ") and not l.startswith("  #") and l.strip()), len(new) + 1)
bad = 0
for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
    first, count = int(m.group(1)), int(m.group(2) or 1)
    inside = start <= first and first + max(count, 1) - 1 < end
    print(f"compose.yaml 의 바뀐 자리 {first}~{first + max(count, 1) - 1}: parser 블록({start}~{end - 1}) {'안' if inside else '밖'}")
    bad += not inside
print("compose.yaml 의 바뀐 덩이:", len(re.findall(r"^@@", diff, re.M)))
sys.exit(1 if bad else 0)
PY
  return $bad
}
step "compose.yaml·verify.sh 의 바뀐 줄이 parser 블록·parser 단계 안뿐" shared_lines

fi

echo "══ 실패한 줄: $FAILED"
exit $((FAILED > 0))
