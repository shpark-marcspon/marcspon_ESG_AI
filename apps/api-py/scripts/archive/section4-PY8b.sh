#!/usr/bin/env bash
# 밴드 PY8b(MARC-TICK-59, 마무리의 문서 쪽)의 §4 자기검증. 줄마다 "EXIT=<종료 코드>" 를 낸다. 전부 0 이어야 한다.
#   사용: apps/api-py/scripts/section4-PY8b.sh            전체(README + MARC-RPT-12 초안)
#         apps/api-py/scripts/section4-PY8b.sh readme     README 쪽만(초안 줄을 뺀다)
#         apps/api-py/scripts/section4-PY8b.sh uploaded   올린 뒤: 다시 읽은 MARC-RPT-12 가 초안과 같은가(maricom 을 부른다)
#         apps/api-py/scripts/section4-PY8b.sh planted    심은 파손 일곱(마지막 줄 PLANTED=7/7)
# 문서 밴드다: 컨테이너도 Node 도 쓰지 않는다. 코드 쪽 사실은 전부 BASE 커밋의 트리에서 읽는다(scripts/readme_audit.py).
# 초안과 「뺀 것」 목록은 저장소 밖(작업 폴더의 band-reports)에 있다. 자리가 다르면 BAND_REPORTS 로 준다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
BASE=c53201d
D="${BAND_REPORTS:?BAND_REPORTS=<band-reports 폴더의 경로> 를 준다}"
PH='(PY8a 병합 뒤 감독이 채움)'
Z='/^## 문서 뷰어 (apps\/web)/,/^## Python API (apps\/api-py)/p'
PY='/^## Python API (apps\/api-py)/,$p'
AUDIT='cd apps/api-py && uv run python scripts/readme_audit.py'
export BASE D PH Z PY

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}

# ── 검사마다 한 줄. 심은 파손(planted)이 같은 줄을 조용히 다시 돌린다 ──
C_COMPARE="$AUDIT compare $BASE $D/PY8b-readme-dropped.tsv"
C_PATHS="$AUDIT paths --rev $BASE"
C_FORWARD="$AUDIT forward --rev $BASE"
C_ZONE='diff <(git show $BASE:README.md | sed -n "$Z") <(sed -n "$Z" README.md)'                       # 프론트 구역 바이트 그대로
C_FACTS='F="$('"$AUDIT"' facts $BASE | grep "^|")" ; test "$(printf "%s\n" "$F" | wc -l)" -ge 21 && printf "%s\n" "$F" | while IFS= read -r l; do grep -q -F -x -- "$l" $D/PY8b-rpt12-draft.md || { echo "없음: $l"; exit 1; }; done'
C_REV3='diff <(diff $D/PY8b-rpt12-rev3.md $D/PY8b-rpt12-draft.md | sed -n "s/^< //p") $D/PY8b-rpt12-changed.txt'   # rev3 에서 사라진 줄 = 열거한 줄(순서째)

if [ "$MODE" = planted ]; then
  backup="$(mktemp -d)"
  cp README.md "$backup/README.md"; cp "$D/PY8b-readme-dropped.tsv" "$backup/dropped.tsv"; cp "$D/PY8b-rpt12-draft.md" "$backup/draft.md"
  before="$(git status --porcelain)"
  restore() { cp "$backup/README.md" README.md; cp "$backup/dropped.tsv" "$D/PY8b-readme-dropped.tsv"; cp "$backup/draft.md" "$D/PY8b-rpt12-draft.md"; }
  trap 'restore; rm -r "$backup"' EXIT
  red() { # 빨간 검사의 이름을 이어 낸다. 하나도 없으면 「없음」
    local out=""
    for name in COMPARE PATHS FORWARD ZONE FACTS REV3; do
      local var="C_$name"
      ( eval "${!var}" ) >/dev/null 2>&1 || out="$out$name "
    done
    printf '%s' "${out:-없음 }"
  }
  edit() { # <파일> <옛 글자> <새 글자>: 처음 나오는 한 곳만 바꾼다. 없으면 실패
    python3 -c 'import sys; p,a,b=sys.argv[1:]; s=open(p,encoding="utf-8").read(); assert a in s, a; open(p,"w",encoding="utf-8").write(s.replace(a,b,1))' "$@"
  }
  total=0; ok=0
  check() { # <설명> <기대>
    local got; got="$(red)"
    total=$((total + 1))
    if [ "$got" = "$2 " ]; then ok=$((ok + 1)); mark="맞음"; else mark="★ 다름(기대 $2)"; fi
    printf '%-74s → %s %s\n' "$1" "$got" "$mark"
    restore
  }
  check "0. 심지 않음" "없음"
  python3 -c 'import sys; p=sys.argv[1]; s=open(p,encoding="utf-8").read(); assert "`LLM_RPM`" in s; open(p,"w",encoding="utf-8").write(s.replace("`LLM_RPM`","LLM_RPM"))' README.md
  check "1. 새 Python 절에서 환경 변수 이름 \`LLM_RPM\` 의 백틱을 전부 벗긴다" "FORWARD"
  edit README.md '`user_in_other_tenant`' 'user-in-other-tenant'
  check "2. 옛 글에 있던 오류 code \`user_in_other_tenant\` 를 지운다" "COMPARE"
  printf '\n없는 경로: `esgapi/core/calc/decimal.py`\n' >> README.md
  check "3. 그 rev 에 없는 경로 esgapi/core/calc/decimal.py 를 적는다" "PATHS"
  edit README.md '## 문서 뷰어 (apps/web)
' '## 문서 뷰어 (apps/web)
심은 글자
'
  check "4. 문서 뷰어 구역에 한 줄을 끼운다" "ZONE"
  python3 -c 'import sys; p=sys.argv[1]; L=open(p,encoding="utf-8").read().split("\n"); c=L[1].split("\t"); c[3]=""; L[1]="\t".join(c); open(p,"w",encoding="utf-8").write("\n".join(L))' "$D/PY8b-readme-dropped.tsv"
  check "5. 뺀 것 목록의 첫 줄에서 근거를 비운다" "COMPARE"
  edit "$D/PY8b-rpt12-draft.md" '| 경로 13 · 동작 14 |' '| 경로 12 · 동작 14 |'
  check "6. 초안에서 facts 한 줄의 수를 바꾼다(경로 13 → 12)" "FACTS"
  edit "$D/PY8b-rpt12-draft.md" '│   │   └── tests/
' ''
  check "7. 초안에서 rev3 의 겹친 줄(│   │   └── tests/) 하나를 지운다" "REV3"
  same=1
  [ "$(git status --porcelain)" = "$before" ] && cmp -s README.md "$backup/README.md" && cmp -s "$D/PY8b-rpt12-draft.md" "$backup/draft.md" \
    && cmp -s "$D/PY8b-readme-dropped.tsv" "$backup/dropped.tsv" && same=0
  echo "심기 전과 같은가(git status · README · 초안 · tsv): EXIT=$same"
  echo "PLANTED=$((ok - 1))/$((total - 1))"   # 0번(심지 않음)은 세지 않는다
  [ "$ok" -eq "$total" ] && [ "$same" -eq 0 ]
  exit $?
fi

if [ "$MODE" = uploaded ]; then
  run 'cd "$D/.." && maricom report get sid:MARC-RPT-12 --full -f json | python3 -c '"'"'import json,sys; d=json.load(sys.stdin); b=d["document"]["body"]; ok = b["revision"]==4 and b["content"]["text"].rstrip("\n")==open(sys.argv[1]).read().rstrip("\n") and d["title"].endswith("(참고, 결정 아님)"); print("revision", b["revision"], "title", d["title"]); sys.exit(0 if ok else 1)'"'"' $D/PY8b-rpt12-draft.md'
  exit 0
fi

echo "── $(date '+%Y-%m-%d %H:%M:%S') · 모드 $MODE · 기준 $BASE · HEAD $(git rev-parse --short HEAD)"
run 'cd apps/api-py && uv sync --frozen'
run 'cd apps/api-py && uv run ruff check scripts/readme_audit.py && uv run ruff format --check scripts/readme_audit.py'
run 'cd apps/api-py && uv run pyright scripts/readme_audit.py'
run 'test "$(wc -l < apps/api-py/scripts/readme_audit.py)" -le 400'
run "$AUDIT facts $BASE"
run "$C_COMPARE"
run "$C_PATHS"
run "$C_FORWARD"
run "$C_ZONE"
run 'test "$(sed -n "$PY" README.md | grep -c -F "$PH")" -ge 3'                                          # 자리표시 셋 이상
run '! grep -n -E "지금 채워진 것은 \`accounts\` 의 한 줄기다|표는 아직 없다|아직 비어 있다|빈 모듈 여섯" README.md'   # 틀려 있던 문장
if [ "$MODE" != readme ]; then
  run "$C_FACTS"                                                                                         # facts 의 줄이 초안에 글자 그대로
  run "$C_REV3"
  run 'test "$(wc -m < $D/PY8b-rpt12-draft.md)" -lt 100000'
  run '! grep -n -E "앞당|일정보다|단축|사전 구현 덕|완료 예정|남은 기간" <(sed -n "$PY" README.md) $D/PY8b-rpt12-draft.md'   # 운영 규칙 5
else
  run '! grep -n -E "앞당|일정보다|단축|사전 구현 덕|완료 예정|남은 기간" <(sed -n "$PY" README.md)'
fi
# 허용 경로 밖 0. 가지에서만 뜻이 있다(병합 뒤 main 에서는 다른 밴드의 파일이 섞인다).
run 'test -z "$({ git diff --name-only "$BASE"; git ls-files -o --exclude-standard; } | sort -u | grep -v -E "^(README\.md|apps/api-py/scripts/(section4-PY8b\.sh|readme_audit\.py))$")"'
