#!/usr/bin/env bash
# RPS1 의 심은 파손(발주서 band-handoffs/RPS1-order.md §3 「심은 파손」): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RPS1.sh   (커밋 하나 — R1~R11)
# 틀은 planted-breaks-RP2b.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸의 낱말이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(이 워크트리의 compose postgres 가 떠 있어야 한다), 그 밖은 순수 층. 층마다 따로 돌리고
#   모든 층이 빨개야 빨강으로 센다(RPS1 — RP2c 틀의 「칸 통째 한 층」을 낱말마다로).
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

[ $# -eq 0 ] || { echo "인자 없음: $0" >&2; exit 2; }

backup="$(mktemp -d /private/tmp/rps1-planted.XXXXXX)"
case "$backup" in /private/tmp/rps1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, olds, news = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
pairs = list(zip(olds.split("§"), news.split("§"), strict=True))
for old, new in pairs:
    if text.count(old) != 1:
        print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
        sys.exit(1)
    text = text.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(text)
PYEOF
}

P=esgapi/drafting
PT=$P/tests
A=$P/service/actions/runs.py
B2=$PT/service/actions/test_runs.py
B3=$PT/service/apis/test_drafting.py
# 줄: <id>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
# R1 projectId 거름 지움 · R2 run_page 의 회사 조건 대신 company_id - 1(보안 층의 A — companies 가 A·B 를 잇달아 만든다, B5 양성 대조와 같은 꼴) · R3 잎 셈에서
# no_material 을 drafted 로 · R4 실행마다 run_results 부름 · R5 latestRun 을 가장 오래된 것으로 · R6 DraftingRunItem 의
# model_config = OUT 뺌(ninja 기본 — 열림) · R7 rejected 를 늘 false · R8 rebuild 없을 때 null
# 러너 몫: R9 queued 도 단계를 읽음(progress) · R10 지금 문서를 가장 먼저 단 것으로 · R11 지금 목차 판을 가장 작은 판으로
ROWS="R1|$A|    runs = [run for run in _scan(company_id) if _int(run.options.get(\"projectId\")) == project_id]|    runs = list(_scan(company_id))|$B2 biz:$B3 sec:tests/security/test_drafting.py
R2|$A|        company_id=company_id, module=MODULE,|        company_id=company_id - 1, module=MODULE,|sec:tests/security/test_drafting.py
R3|$A|    \"no_material\": \"noMaterial\",|    \"no_material\": \"drafted\",|$B2 biz:$B3
R4|$A|        summary = summaries.get(run.id)\n|        summary = summaries.get(run.id)\n        run_selectors.run_results(company_id=company_id, run_id=run.id)\n|biz:$B3
R5|$A|        if project_id in wanted and project_id not in latest:|        if project_id in wanted:|$B2 biz:$B3
R6|$P/service/schemas/projects.py|    model_config = OUT\n\n    id: int\n    status: Literal|    id: int\n    status: Literal|$PT/service/schemas/test_projects.py
R7|$A|    return cast(\"dict[str, object]\", status).get(\"status\") == \"rejected\", counts|    return False, counts|$B2
R8|$A|    if not isinstance(keys, list):\n        return []|    if not isinstance(keys, list):\n        return None  # type: ignore[return-value]|$B2 biz:$B3
R9|$A|[r.id for r in runs if r.status == \"processing\"]|[r.id for r in runs if r.status in (\"processing\", \"queued\")]|$B2
R10|$P/service/selectors/projects.py|        .order_by(\"project_id\", \"-id\")|        .order_by(\"project_id\", \"id\")|biz:$B3
R11|$P/service/selectors/projects.py|.filter(project_id=OuterRef(\"id\")).order_by(\"-revision\")|.filter(project_id=OuterRef(\"id\")).order_by(\"revision\")|biz:$B3"

planted=0
caught=0
bad=0
while IFS='|' read -r id file old new tests; do
  [ -n "$id" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  # 시험 칸의 낱말마다 층: 「biz:」 업무 · 「sec:」 보안 · 그 밖 순수. 층마다 따로 돌리고, 모든 층이 빨개야 빨강이다.
  pure=""; biz=""; sec=""
  for t in $tests; do
    case "$t" in biz:*) biz="$biz ${t#biz:}" ;; sec:*) sec="$sec ${t#sec:}" ;; *) pure="$pure $t" ;; esac
  done
  red=1; nfail=0; failed=""; codes=""
  for layer in pure biz sec; do
    eval "paths=\$$layer"
    [ -n "$paths" ] || continue
    case "$layer" in
      # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
      pure) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $paths > "$backup/log" 2>&1 ;;
      # shellcheck disable=SC2086
      biz) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider $paths > "$backup/log" 2>&1 ;;
      # shellcheck disable=SC2086
      sec) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider $paths > "$backup/log" 2>&1 ;;
    esac
    code=$?
    n="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
    names="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -3 | paste -sd' ' -)"
    # 빨강 = 종료 1 이고 FAILED 줄이 있음(ERROR 뿐인 종료 1 — DB 끊김 등 — 은 「죽음」이다)
    if [ "$code" != 1 ] || [ "${n:-0}" -eq 0 ]; then red=0; fi
    nfail=$((nfail + ${n:-0}))
    failed="$failed [$layer] ${names:-}"
    codes="$codes $layer=$code"
  done
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT${codes}) 빨강 ${nfail}개:${failed}"
done <<EOF
$ROWS
EOF

want=11
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
