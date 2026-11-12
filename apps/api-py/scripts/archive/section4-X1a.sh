#!/usr/bin/env bash
# 밴드 X1a(MARC-TICK-166: 실행 표의 자리를 runs 앱으로 — 동작 0 · openapi 바이트 0)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-X1a.sh --commit <1|2|3> [--with-containers] [--after-commit]
#         apps/api-py/scripts/section4-X1a.sh --commit <1|2|3> --step <n> [--with-containers]   단계 하나만
#   --commit 1 은 단계 1·3·4·5·6·9·10·11·12, 2 는 그에 2·7·8, 3 은 전부(13 은 --after-commit 일 때만).
#   --with-containers 가 없으면 컨테이너 단계(2·8)는 「안 돌림」으로 찍고 실패로 센다(조용한 초록 금지).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독 몫). AI 공급사 호출 0, 시험은 env -u OPENAI_API_KEY.
# 컨테이너는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것만 띄우고 내린다. build 는
#   scripts/with-build-lock.sh 로만(기계 전체 하나).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
#   git grep 의 종료 ≥2 와 양성 대조 0 은 실패로 센다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=7444685bb02db4771acef3a6ae6d29e5d4978ef1   # 워크트리를 세운 main(AD1 병합). api-py 는 165a044 와 같다
OUT="$ROOT/../X1a.out"                           # 워크트리 밖. collect-base.txt 가 여기 있다
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

T="$(mktemp -d /private/tmp/x1a.XXXXXX)"
case "$T" in /private/tmp/x1a.*) ;; *) exit 99 ;; esac
FAILS=0

# 단계 안의 파이썬·SQL 은 파일로 둔다(단계의 셸 글이 홑따옴표 안이다).
cat > "$T/step4.py" <<'PY'
import ast, sys
T = sys.argv[1]
def parts(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    body = tree.body
    doc = ast.get_docstring(tree)
    if doc is not None:
        body = body[1:]
    imports = sorted(ast.unparse(n) for n in body if isinstance(n, (ast.Import, ast.ImportFrom)))
    rest = [ast.dump(n, include_attributes=False) for n in body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    return imports, rest
pairs = [
    (f"{T}/base-apis-runs.py", "esgapi/runs/service/apis/runs.py",
     {"from esgapi.core.service.schemas.runs import RunCreatedOut, RunIn, RunListQuery, RunOut, RunPageOut":
      "from esgapi.runs.service.schemas.runs import RunCreatedOut, RunIn, RunListQuery, RunOut, RunPageOut"}),
    (f"{T}/base-schemas-runs.py", "esgapi/runs/service/schemas/runs.py", {}),
]
bad = 0
for base, now, moved in pairs:
    bi, br = parts(base)
    ok_self = parts(base) == (bi, br)
    ni, nr = parts(now)
    want = sorted(moved.get(i, i) for i in bi)
    same_rest = br == nr
    same_imports = ni == want
    print(f"  {now}: 양성 대조(BASE=BASE) {ok_self} · 노드 {len(br)}/{len(nr)} 같음 {same_rest} · import 바뀜만 {same_imports}")
    if not (ok_self and same_rest and same_imports and br):
        bad += 1
sys.exit(1 if bad else 0)
PY
cat > "$T/step7.py" <<'PY'
import ast, difflib, re, subprocess, sys
base, listing, rev, commit = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
pairs = [p.split("=", 1) for p in rev.split("|")]
# 처분이 적은 자리: (파일 꼬리, 남아도 되는 줄의 무늬). 무늬는 바꿈을 거꾸로 댄 뒤의 글에 댄다.
ALLOWED = [
    ("esgapi/config/tests/test_settings.py", r'^\+ *"runs",$'),
    ("esgapi/core/tests/test_flows_core_names.py", r'^[-+]BUSINESS = \('),
    ("esgapi/reconcile/tests/test_tasks_registered.py", r'^[-+].*(열다섯|열여섯|== 1[56]$)'),
]
if commit >= 2:
    ALLOWED += [
        ("esgapi/core/tests/test_documents_models.py", r"."),  # 개정 2 B2 — 마이그레이션 단언 나눔, 손으로 본다
        # 분모 {"documents": 3, "jobs": 3} 를 지키려고 jobs 를 runs 자리에서 연다(§2-2)
        ("esgapi/core/tests/test_selector_scope.py", r'for name(, folder)? in \(|ESGAPI / (folder|"core/service/services")'),
    ]
if commit >= 3:
    ALLOWED += [
        ("tests/security/test_migrations.py", r"."),  # 왕복 차례·runs 단언 — 아래에서 손으로 본다
        ("esgapi/core/tests/isolation/test_foreign_keys.py", r"^[-+].*\b3[67]\b"),
    ]
def norm(text):
    tree = ast.parse(text)
    imports = set()
    drop = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports |= {("", a.name, a.asname) for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imports |= {(node.module, a.name, a.asname) for a in node.names}
        else:
            continue
        drop.update(range(node.lineno, node.end_lineno + 1))
    lines = [l for i, l in enumerate(text.splitlines(), 1) if i not in drop]
    while lines and not lines[-1].strip():
        lines.pop()
    # import 를 걷은 자리의 빈 줄 수는 보지 않는다(머리 docstring 뒤 첫 줄까지)
    return imports, [l for l in lines]
bad = 0
for path in open(listing).read().split():
    rel = path.removeprefix("apps/api-py/")
    try:
        old = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        print(f"  ★ {rel}: BASE 에 없는 새 시험 파일"); bad += 1; continue
    try:
        new = open(rel, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"  ★ {rel}: 지워졌다"); bad += 1; continue
    for a, b in pairs:
        new = new.replace(a, b)
    oi, ol = norm(old); ni, nl = norm(new)
    oc = [l for l in ol if l.strip()]; nc = [l for l in nl if l.strip()]
    diff = [d for d in difflib.unified_diff(oc, nc, lineterm="", n=0) if d[:1] in "+-" and d[:3] not in ("+++", "---")]
    # 차례만 바뀐 줄(지운 줄과 같은 글의 더한 줄 — 정렬된 손 목록에서 자리가 바뀜)은 짝지어 뺀다
    minus = [d[1:] for d in diff if d[0] == "-"]
    plus = [d[1:] for d in diff if d[0] == "+"]
    moved = []
    for line in list(minus):
        if line in plus:
            minus.remove(line); plus.remove(line); moved.append(line)
    diff = ["-" + l for l in minus] + ["+" + l for l in plus]
    for line in moved:
        print(f"      차례만: {line.strip()[:150]}")
    idiff = sorted(oi ^ ni)
    allowed = [pat for tail, pat in ALLOWED if rel.endswith(tail)]
    rest = [d for d in diff if not any(re.search(p, d) for p in allowed)]
    shown = [d for d in diff if d not in rest]
    print(f"  {rel}: 남은 줄 {len(diff)} (처분 자리 {len(shown)}) · import 차이 {len(idiff)}")
    for d in shown:
        print(f"      처분: {d[:150]}")
    for d in rest:
        print(f"    ★ {d[:150]}")
    for d in idiff:
        print(f"    ★ import {d}")
    bad += bool(rest or idiff)
sys.exit(1 if bad else 0)
PY
cat > "$T/grants.sql" <<'SQL'
SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants WHERE grantee = 'esg_app' ORDER BY 1, 2, 3;
SQL

# 바꿈 표(§4-7): HEAD 의 글을 BASE 의 글로 되돌리는 바꿈. 커밋마다 늘어난다.
REVERSE_1='esgapi.runs.service.=esgapi.core.service.|runs/service/=core/service/'
REVERSE_2="$REVERSE_1"'|esgapi.runs.models=esgapi.core.models|esgapi.runs.migrations=esgapi.core.migrations|runs/management/=core/management/|esgapi.runs.management.=esgapi.core.management.|from esgapi.runs import models as runs_models=from esgapi.core import models as core_models|runs_models.=core_models.'
REVERSE_3="$REVERSE_2"'|run_jobs=core_jobs'

wanted() { # <단계> — 이 커밋에서 도는 단계인가
  [ -z "$ONLY" ] || [ "$ONLY" = "$1" ] || return 1
  case "$COMMIT:$1" in
    *:1 | *:3 | *:4 | *:5 | *:6 | *:9 | *:10 | *:11 | *:12) return 0 ;;
    2:2 | 2:7 | 2:8 | 3:2 | 3:7 | 3:8) return 0 ;;
    *:13) [ "$AFTER" = 1 ] ;;
    *) return 1 ;;
  esac
}
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
export -f env_value changed
export ROOT BASE OUT A E T COMMIT

echo "── 밴드 X1a §4 · 커밋 $COMMIT · BASE ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"

# ── 1. 순수 층 ──
if wanted 1; then
  step 1 "순수 층 초록" '(cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$T/pure.txt" 2>&1; code=$?; tail -1 "$T/pure.txt"; exit $code)'
fi

# ── 3. 계약 바이트 0 ──
if wanted 3; then
  step 3 "0줄 경로(generated·web·greenwash·permissions·auth·documents 경로·tenancy·llm·flows·의존성·compose·rehearsal·README)" '
    P="$A/generated apps/web $E/greenwash $E/core/permissions.py $E/core/auth $E/core/service/apis/documents.py $E/core/tenancy $E/core/llm $E/core/flows $A/pyproject.toml $A/uv.lock compose.yaml $A/scripts/rehearsal.sh README.md"
    git diff --quiet "$BASE" -- $P; code=$?
    new="$(git ls-files --others --exclude-standard -- $P | wc -l | tr -d " ")"
    echo "  git diff EXIT=$code · 추적 안 된 새 파일 $new"
    [ "$code" = 0 ] && [ "$new" = 0 ]'
  step 3 "다시 뽑은 openapi 와 generated/openapi.json 의 cmp" '(cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi > "$T/openapi.json" 2> "$T/export.err"; code=$?; [ "$code" = 0 ] || { tail -3 "$T/export.err"; exit $code; }; cmp "$T/openapi.json" generated/openapi.json)'
  step 3 "config/tests/test_api_contract.py 초록" '(cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$T/contract.txt" 2>&1; code=$?; tail -1 "$T/contract.txt"; exit $code)'
fi

# ── 4. 옮긴 경로·꼴 파일: 모듈 docstring 과 import 밖의 노드가 같다 ──
if wanted 4; then
  step 4 "runs.py·schemas/runs.py 의 AST(모듈 docstring·import 밖) = BASE" '
    git show "$BASE:$E/core/service/apis/runs.py" > "$T/base-apis-runs.py" &&
    git show "$BASE:$E/core/service/schemas/runs.py" > "$T/base-schemas-runs.py" &&
    (cd "$A" && uv run --frozen python "$T/step4.py" "$T")'
fi

# ── 5. import 계약과 심은 파손 ──
if wanted 5; then
  step 5 "lint-imports: Contracts: 16 kept, 0 broken." '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; [ "$(tail -1 "$T/lint.txt")" = "Contracts: 16 kept, 0 broken." ] && exit $code; exit 1)'
  step 5 "scripts/planted-breaks.sh: PLANTED=46/46(BASE 43 + 차 하나 + 가 의 runs 둘), 지문 같음" '("$A/scripts/planted-breaks.sh" > "$T/planted.txt" 2>&1; code=$?; grep -v "맞음" "$T/planted.txt"; [ "$(tail -1 "$T/planted.txt")" = "PLANTED=46/46" ] && exit $code; exit 1)'
  step 5 "심은 경우 번호: BASE 의 것이 하나도 빠지지 않는다" '
    git show "$BASE:$A/scripts/planted-breaks.sh" | sed -n "s/^check \"\([0-9]*\)\..*/\1/p" | sort -n > "$T/pb-ids-base.txt"
    sed -n "s/^check \"\([0-9]*\)\..*/\1/p" "$A/scripts/planted-breaks.sh" | sort -n > "$T/pb-ids-now.txt"
    b="$(wc -l < "$T/pb-ids-base.txt" | tr -d " ")"; n="$(wc -l < "$T/pb-ids-now.txt" | tr -d " ")"
    gone="$(comm -23 "$T/pb-ids-base.txt" "$T/pb-ids-now.txt" | wc -l | tr -d " ")"
    echo "  BASE ${b}개 · 지금 ${n}개 · 빠진 것 ${gone}개 · 더한 것 $(comm -13 "$T/pb-ids-base.txt" "$T/pb-ids-now.txt" | tr "\n" " ")"
    [ "$b" -gt 0 ] && [ "$gone" = 0 ] && [ "$n" = $((b + 3)) ]'
  # 커밋 ③ 의 컨테이너 몫(P3 보안·P7·P8)은 Postgres 를 띄운 뒤(아래 「5c」)에 돈다
  if [ "$COMMIT" -ge 2 ] && ! { [ "$COMMIT" = 3 ] && [ "$CONTAINERS" = 1 ]; }; then
    step 5 "scripts/planted-breaks-X1a.sh (순수 몫)" '("$A/scripts/planted-breaks-X1a.sh" --commit "$COMMIT" > "$T/planted-x1a.txt" 2>&1; code=$?; cat "$T/planted-x1a.txt" | tail -14; exit $code)'
  fi
fi

# ── 6. 시험 수·이름 ──
if wanted 6; then
  step 6 "수집한 노드 id = BASE(collect-base.txt)" '
    test -s "$OUT/collect-base.txt" || { echo "  collect-base.txt 가 없다"; exit 1; }
    (cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi tests tests_integration > "$T/collect-now.txt" 2>&1); code=$?
    grep "::" "$OUT/collect-base.txt" > "$T/ids-base.txt"; grep "::" "$T/collect-now.txt" > "$T/ids-now.raw"
    # 매개변수 id 에 파일 자리가 든 노드 둘(손 목록이 아니라 glob 의 id)은 커밋 ② 부터 자리가 바뀐다 — 이름 바꿈 표
    if [ "$COMMIT" -ge 2 ]; then
      renamed="$(grep -c -E "\[runs/service/(selectors|services)/jobs\.py\]" "$T/ids-now.raw")"
      sed -E "s#\[runs/service/(selectors|services)/jobs\.py\]#[core/service/\1/jobs.py]#" "$T/ids-now.raw" > "$T/ids-now.txt"
      echo "  이름 바꿈 표로 되돌린 노드 ${renamed}개(기대 2: test_selectors_scope_every_read·test_every_write_sits_inside_a_block 의 jobs 자리)"
      [ "$renamed" = 2 ] || exit 1
      if [ "$COMMIT" -ge 3 ]; then
        # 표 이름이 매개변수 id 에 든 보안 노드 셋(test_documents.py 의 DELETE·TRUNCATE·권한)
        tables="$(grep -c -E "\[.*run_jobs.*\]" "$T/ids-now.txt")"
        sed -i "" -E "s#run_jobs#core_jobs#g" "$T/ids-now.txt"
        echo "  표 이름 바꿈(run_jobs → core_jobs)으로 되돌린 노드 ${tables}개(기대 3)"
        [ "$tables" = 3 ] || exit 1
      fi
    else
      cp "$T/ids-now.raw" "$T/ids-now.txt"
    fi
    for layer in esgapi/ tests/security/ tests_integration/; do
      echo "  $layer 앞 $(grep -c "^$layer" "$T/ids-base.txt") · 뒤 $(grep -c "^$layer" "$T/ids-now.txt")"
    done
    tail -1 "$OUT/collect-base.txt" | sed "s/^/  앞: /"; tail -1 "$T/collect-now.txt" | sed "s/^/  뒤: /"
    # 수집 차례는 파일 자리를 따른다(이름 바꾼 노드가 다른 자리에 선다) — 정렬해 견준다
    diff <(sort "$T/ids-base.txt") <(sort "$T/ids-now.txt") > "$T/ids.diff"; d=$?
    head -20 "$T/ids.diff"
    [ "$code" = 0 ] && [ "$d" = 0 ] && [ -s "$T/ids-base.txt" ]'
fi

# ── 7. 시험 고침의 종류(역치환 대조) ──
if wanted 7; then
  eval "REV=\$REVERSE_$COMMIT"
  export REV
  step 7 "바뀐 시험 파일: 바꿈 표를 거꾸로 대고 import 를 정렬하면 BASE 와 같다(남는 차이는 처분이 적은 자리뿐)" '
    changed | grep -E "^$A/(esgapi/[a-z_]+/tests/|tests/|tests_integration/)" > "$T/tests-changed.txt"
    echo "  바뀐 시험 파일 $(wc -l < "$T/tests-changed.txt" | tr -d " ")개"
    (cd "$A" && uv run --frozen python "$T/step7.py" "$BASE" "$T/tests-changed.txt" "$REV" "$COMMIT")'
fi

# ── 2·8. 컨테이너 ──
gate() { # 기계 문: 자기 밖 esg-app* 프로젝트 ≤ 2, 빌드 중 0, free ≥ 20%, 1분 부하 < 24. 60초 간격, 최대 30분.
  local tries=0 free load others building me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d " ")"
    building="$(ps -axo command | grep -E "compose.*build|buildx|docker build" | grep -v -c grep)"
    free="$(memory_pressure 2> /dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "$others" -le 2 ] && [ "$building" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 자기 밖 esg-app* 프로젝트 $others · 빌드 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: 자기 밖 $others · 빌드 중 $building · free ${free:-?}% · 부하 ${load:-?})"; return 1; }
    tries=$((tries + 1))
    sleep 60
  done
}
export -f gate
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
export PROJECT
OWNER="$(env_value POSTGRES_OWNER_USER)"
export OWNER

postgres_up() {
  step "2·8" "Postgres 한 벌 띄우기($PROJECT)" '
    test -n "$PROJECT" && test "$PROJECT" != esg-app || exit 1
    grep -q "^SESSION_SECRET=." .env || { echo "  .env 에 SESSION_SECRET 이 없다"; exit 1; }
    gate || exit 1
    docker compose up -d --wait postgres 2>&1 | tail -3; exit "${PIPESTATUS[0]}"'
}

if [ "$CONTAINERS" = 1 ] && { wanted 2 || wanted 8; }; then
  postgres_up
fi

if wanted 2; then
  if [ "$CONTAINERS" = 1 ]; then
    step 2 "업무 층(core·reconcile·config)" '"$A/scripts/test-business.sh" -p no:cacheprovider esgapi/core esgapi/reconcile esgapi/config > "$T/business.txt" 2>&1; code=$?; tail -1 "$T/business.txt"; exit $code'
    step 2 "보안 층 전부" '"$A/scripts/test-security.sh" -p no:cacheprovider > "$T/security.txt" 2>&1; code=$?; tail -1 "$T/security.txt"; exit $code'
    if [ "$COMMIT" = 3 ] && wanted 5; then
      step 5c "scripts/planted-breaks-X1a.sh --with-containers (P1~P9)" '("$A/scripts/planted-breaks-X1a.sh" --commit 3 --with-containers > "$T/planted-x1a.txt" 2>&1; code=$?; cat "$T/planted-x1a.txt" | tail -20; exit $code)'
    fi
  else
    not_run 2 "업무·보안·통합 층" "--with-containers 없음"
  fi
fi

if wanted 8; then
  if [ "$CONTAINERS" = 1 ]; then
    step 8 "스키마 대조: BASE 트리와 지금 트리로 빈 DB 둘에 migrate → pg_dump --schema-only 견줌" '
      set -e
      D="$T/base-tree"; mkdir -p "$D"
      case "$D" in /private/tmp/x1a.*) ;; *) exit 99 ;; esac
      git archive "$BASE" "$A" | tar -x -C "$D"
      PY="$ROOT/$A/.venv/bin/python"
      host="127.0.0.1:$(env_value POSTGRES_PORT)"
      pw="$(env_value POSTGRES_OWNER_PASSWORD)"
      url_for() { echo "postgres://$OWNER:$pw@$host/$1"; }
      URL_BASE="$(url_for x1a_schema_base)"; URL_HEAD="$(url_for x1a_schema_head)"
      for db in x1a_schema_base x1a_schema_head; do
        docker compose exec -T postgres psql -q -U "$OWNER" -d postgres -c "DROP DATABASE IF EXISTS $db" -c "CREATE DATABASE $db" > /dev/null
      done
      set +e
      (cd "$D/$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_BASE" "$PY" -c "import esgapi,sys; print(\"  BASE esgapi:\", esgapi.__file__)" && cd "$D/$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_BASE" "$PY" manage.py migrate --no-input > "$T/migrate-base.txt" 2>&1); c1=$?
      (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_HEAD" "$PY" manage.py migrate --no-input > "$T/migrate-head.txt" 2>&1); c2=$?
      echo "  migrate BASE EXIT=$c1 · HEAD EXIT=$c2"
      [ "$c1" = 0 ] && [ "$c2" = 0 ] || { tail -5 "$T/migrate-base.txt" "$T/migrate-head.txt"; exit 1; }
      for side in base head; do
        docker compose exec -T postgres pg_dump -U "$OWNER" --schema-only --no-owner "x1a_schema_$side" | grep -v -E "^(--|$|SET |SELECT pg_catalog.set_config|\\\\(un)?restrict )" > "$T/dump-$side.raw"
        docker compose exec -T postgres psql -At -U "$OWNER" -d "x1a_schema_$side" -f - < "$T/grants.sql" > "$T/grants-$side.raw"
      done
      wc -l "$T/dump-base.raw" "$T/dump-head.raw" "$T/grants-base.raw" "$T/grants-head.raw" | sed "s/^/  /"
      if [ "$COMMIT" -ge 3 ]; then
        # 개정 2 B3: Django 가 짓는 이름의 8hex 해시(표 이름이 든다)를 지우고, HEAD 에 run_jobs → core_jobs 를 댄다
        for side in base head; do
          sed -E "s/_[0-9a-f]{8}(_|[^0-9a-z_]|$)/\1/g" "$T/dump-$side.raw" > "$T/dump-$side.nohash"
          grep -o -E "[a-z_]*_[0-9a-f]{8}(_[a-z_]*)?" "$T/dump-$side.raw" | grep -E "_[0-9a-f]{8}(_|$)" | sort -u > "$T/hashed-$side.txt"
          echo "  $side: 해시를 지운 줄 $(diff "$T/dump-$side.raw" "$T/dump-$side.nohash" | grep -c "^>") · 해시 든 이름 $(wc -l < "$T/hashed-$side.txt" | tr -d " ")개(목록 $T/hashed-$side.txt)"
        done
        echo "  바꿈 전 차이(해시 지운 뒤) — run_jobs·core_jobs 밖 줄:"
        diff <(sort "$T/dump-base.nohash") <(sort "$T/dump-head.nohash") | grep "^[<>]" | grep -v -E "core_jobs|run_jobs" | head -10
        outside=$(diff <(sort "$T/dump-base.nohash") <(sort "$T/dump-head.nohash") | grep "^[<>]" | grep -c -v -E "core_jobs|run_jobs")
        echo "  이름 밖 차이 줄 $outside"
        sed "s/run_jobs/core_jobs/g" "$T/dump-head.nohash" > "$T/dump-head.cmp"; cp "$T/dump-base.nohash" "$T/dump-base.cmp"
        sed "s/run_jobs/core_jobs/g" "$T/grants-head.raw" > "$T/grants-head.cmp"; cp "$T/grants-base.raw" "$T/grants-base.cmp"
        echo "  run_jobs 가 HEAD 덤프에 $(grep -c run_jobs "$T/dump-head.raw")줄, core_jobs 가 HEAD 덤프에 $(grep -c core_jobs "$T/dump-head.raw")줄"
        [ "$outside" = 0 ] || exit 1
        [ "$(grep -c core_jobs "$T/dump-head.raw")" = 0 ] || exit 1
      else
        cp "$T/dump-base.raw" "$T/dump-base.cmp"; cp "$T/dump-head.raw" "$T/dump-head.cmp"
        cp "$T/grants-base.raw" "$T/grants-base.cmp"; cp "$T/grants-head.raw" "$T/grants-head.cmp"
      fi
      diff <(sort "$T/dump-base.cmp") <(sort "$T/dump-head.cmp") > "$T/dump.diff"; d1=$?
      diff <(sort "$T/grants-base.cmp") <(sort "$T/grants-head.cmp") > "$T/grants.diff"; d2=$?
      echo "  스키마 차이(정렬) $(grep -c "^[<>]" "$T/dump.diff") 줄 · 앱 역할 표 권한 차이 $(grep -c "^[<>]" "$T/grants.diff") 줄 · 권한 행 $(wc -l < "$T/grants-head.raw" | tr -d " ")"
      head -20 "$T/dump.diff" "$T/grants.diff"
      grep -c "jobs" "$T/grants-head.raw" | sed "s/^/  앱 역할의 일감 표 권한 행 /"
      (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_HEAD" "$PY" manage.py makemigrations --check --dry-run > "$T/makemigrations.txt" 2>&1); c3=$?
      sed "s/^/  /" "$T/makemigrations.txt"
      for db in x1a_schema_base x1a_schema_head; do
        docker compose exec -T postgres psql -q -U "$OWNER" -d postgres -c "DROP DATABASE IF EXISTS $db" > /dev/null
      done
      [ "$d1" = 0 ] && [ "$d2" = 0 ] && [ "$c3" = 0 ] && [ -s "$T/dump-base.raw" ] && [ -s "$T/grants-base.raw" ]'
  else
    not_run 8 "스키마 대조" "--with-containers 없음"
  fi
fi

if [ "$COMMIT" = 3 ] && wanted 2 && [ "$CONTAINERS" = 1 ]; then
  step 2 "통합 층(이미지는 with-build-lock.sh 로 짓고 compose 전부를 띄운다)" '
    gate || exit 1
    EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || exit 1
    export EDK_JWT_PUBLIC_KEY CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
    scripts/with-build-lock.sh docker compose build > "$T/build.txt" 2>&1; code=$?; tail -2 "$T/build.txt"; [ "$code" = 0 ] || exit $code
    docker compose up -d --wait > "$T/up.txt" 2>&1; code=$?; tail -3 "$T/up.txt"; [ "$code" = 0 ] || exit $code
    "$A/scripts/test-integration.sh" -p no:cacheprovider > "$T/integration.txt" 2>&1; code=$?; tail -1 "$T/integration.txt"; exit $code'
fi

if [ "$CONTAINERS" = 1 ] && { wanted 2 || wanted 8; }; then
  step "2·8" "내 벌만 내리기($PROJECT)" '
    docker compose down -v --remove-orphans 2>&1 | tail -2; code=${PIPESTATUS[0]}
    for img in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/"); do docker image rm "$img" > /dev/null 2>&1; done
    echo "  남은 이미지 $(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"
    n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"
    v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"
    echo "  남은 컨테이너 $n · 볼륨 $v"
    [ "$code" = 0 ] && [ "$n$v" = 00 ]'
fi

# ── 9. runs 로 향하는 의존 0 ──
if wanted 9; then
  step 9 "다른 앱의 마이그레이션·모델이 runs 를 가리키지 않는다(양성 대조 먼저)" '
    if [ "$COMMIT" -ge 2 ]; then
      pos="$(git grep -n -E "\(\"core\", \"0001_initial\"\)" -- "$E/runs/migrations/*.py")"; c=$?
      posf="$(git grep -n -F "to=\"core.documentrow\"" -- "$E/runs/migrations/*.py")"; cf=$?
    else
      pos="$(git grep -n -E "\(\"organization\", \"0001_initial\"\)" -- "$E/core/migrations/*.py")"; c=$?
      posf="$(git grep -n -F "\"organization.Company\"" -- "$E/core/models.py")"; cf=$?
    fi
    echo "  양성(의존): ${pos:-없음} (git grep EXIT=$c)"; echo "  양성(FK 글자): ${posf:-없음} (git grep EXIT=$cf)"
    [ "$c" = 0 ] && [ "$cf" = 0 ] || exit 1
    neg="$(git grep -n -E "\(\"runs\"," -- "$E/*/migrations/*.py" ":!$E/runs/**")"; n=$?
    negf="$(git grep -n -E "\"runs\.[A-Za-z]" -- "$E/*/models.py" "$E/*/models/*.py" "$E/*/migrations/*.py" ":!$E/runs/**")"; nf=$?
    echo "  runs 밖의 (\"runs\", 의존: ${neg:-0줄} (EXIT=$n) · \"runs. 모델 글자: ${negf:-0줄} (EXIT=$nf)"
    [ "$n" = 1 ] && [ "$nf" = 1 ]'
fi

# ── 10. 빠른 게이트 ──
if wanted 10; then
  step 10 "scripts/verify.sh --fast 끝 줄 VERIFY_FAST=PASS" 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
fi

# ── 11. 허용 경로 ──
if wanted 11; then
  step 11 "BASE 대비 바뀐 파일이 허용 목록 안" '
    changed > "$T/changed.txt"
    grep -v -E \
      -e "^$E/runs/" \
      -e "^$E/core/service/(apis|schemas)/runs\.py$" \
      -e "^$E/core/service/(selectors|services)/jobs\.py$" \
      -e "^$E/core/management/commands/requeue_jobs\.py$" \
      -e "^$E/core/(models|__init__)\.py$" \
      -e "^$E/core/migrations/0001_initial\.py$" \
      -e "^$E/core/service/(selectors|services)/documents\.py$" \
      -e "^$E/core/service/__init__\.py$" \
      -e "^$E/core/isolation/(foreign_keys|managers)\.py$" \
      -e "^$E/core/calc/jobs\.py$" \
      -e "^$E/config/(api|apps_list|celery|env)\.py$" \
      -e "^$E/reconcile/(tasks|calc/job_summary)\.py$" \
      -e "^$A/\.importlinter$" \
      -e "^$E/config/tests/test_settings\.py$" \
      -e "^$E/core/tests/test_flows_core_names\.py$" \
      -e "^$E/reconcile/tests/test_tasks_registered\.py$" \
      -e "^$A/scripts/(planted-breaks|section4-X1a|planted-breaks-X1a)\.sh$" \
      "$T/changed.txt" > "$T/outside0.txt"
    # 시험: BASE 에서 §0-1 의 재는 법으로 잰 시험 파일 목록(개정 2 N4)
    P="JobRow|core_jobs|core\.service\.(selectors|services)(\.| import .*)jobs|core\.calc\.jobs|core\.calc import .*jobs|jobs_of|job_of\b|core\.service\.apis\.runs|core\.service\.schemas\.runs|apis/runs|schemas/runs|JOB_KINDS|JOB_STATUSES|JobStatus|JOB_ROW_STATUSES|requeue_jobs|enqueue_job|run_parse_job"
    git grep -l -E "$P" "$BASE" -- "$E" "$A/tests" "$A/tests_integration" > "$T/measured.raw"; g=$?
    [ "$g" = 0 ] || { echo "  git grep EXIT=$g"; exit 1; }
    sed "s/^$BASE://" "$T/measured.raw" | grep -E "/tests/|^$A/tests_integration/" > "$T/measured-tests.txt"
    echo "  잰 시험 파일 $(wc -l < "$T/measured-tests.txt" | tr -d " ")개(BASE)"
    grep -v -x -F -f "$T/measured-tests.txt" "$T/outside0.txt" > "$T/outside.txt"
    echo "  바뀐 파일 $(wc -l < "$T/changed.txt" | tr -d " ")개 · 허용 밖 $(wc -l < "$T/outside.txt" | tr -d " ")개"
    sed "s/^/  ★ /" "$T/outside.txt"
    [ ! -s "$T/outside.txt" ]'
fi

# ── 12. 키 꼴 0 ──
if wanted 12; then
  step 12 "diff 의 더한 줄과 커밋 메시지에 sk- 키 꼴 0" '
    a="$(git diff "$BASE" | grep "^+" | grep -c -E "sk-[A-Za-z0-9_-]{20,}")"
    b="$(git log --format=%B "$BASE"..HEAD | grep -c -E "sk-[A-Za-z0-9_-]{20,}")"
    c=0; [ -n "${X1A_MSG:-}" ] && c="$(grep -c -E "sk-[A-Za-z0-9_-]{20,}" "$X1A_MSG")"
    echo "  diff ${a}줄 · 커밋 메시지 ${b}줄 · 쓸 메시지(${X1A_MSG:-없음}) ${c}줄"
    [ "$a$b$c" = 000 ]'
fi

# ── 13. 작업 트리 ──
if wanted 13; then
  step 13 "git status --porcelain 0줄" 'n="$(git status --porcelain | wc -l | tr -d " ")"; echo "  ${n}줄"; [ "$n" = 0 ]'
fi

echo
echo "── 기록: $T"
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
