#!/usr/bin/env bash
# RP1 의 심은 파손(발주서 §3 「심은 파손」): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RP1.sh --commit <1|2|3>
#   경계별 배치: ① P7·P8·P12 + 러너 몫 R1 + 검증 몫 V1·V5(6) · ② + P1~P6·P9~P11b·P15 + 검증 몫 X1·X2·X3·X6(15, 누적 21) · ③ + P13·P14·P16·P7s(4, 누적 25).
# 틀은 planted-breaks-IR4.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(이 워크트리의 compose postgres 가 떠 있어야 한다).
#   「lint+」로 시작하면 lint-imports 도 돌리고 둘 다 빨개야(lint 종료 ≠ 0) 빨강으로 센다.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1|2|3) ;; *) echo "--commit 1·2·3" >&2; exit 2 ;; esac

D=esgapi/drafting
T=$D/tests
SL=$D/service/selectors/projects.py
SA=$D/service/actions/projects.py  # ③ R1 — put_outline 묶음이 services 에서 옮겨 옴
E=$D/engines/v1
F=$D/flows/draft_v1.py
TE=$T/engines/v1
TF=$T/flows

backup="$(mktemp -d /private/tmp/rp1-planted.XXXXXX)"
case "$backup" in /private/tmp/rp1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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

# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
# ① P7 selector 회사 조건 지움(unscoped) · P8 목차 depth 검사 지움 · P12 결과 꼴에 칸 더함(고정 스키마 그대로)
#   · R1(러너) put_outline 의 같은 sha 멱등 지움 · V1·V5(검증 B1) 지금 문서·지금 목차의 프로젝트 조건 지움
# ② P1 checks ⓐ 지움 · P2 숫자 대조 지움 · P3 쪽 0부터 · P4 위끝 ⓐ 지움 · P5 _Guard 지움 · P6 inputs_with sha 다시 셈 지움
#   · P9 S2 마지막 묶음 버림 · P10 mock 갈래 지움 · P11 엔진 import django(lint+축) · P11b 흐름이 greenwash.tools import(축만 —
#   모듈 사이 계약은 .importlinter 에 없다, no-foreign-models 는 models 만) · P15 resume 무시
#   · 검증 ② B1·B2: X1 엔진 import urllib.request(test_purity) · X2 ⓑ 를 잎 전부로 · X3 draft 가드 상한 = max_usd · X6 ⓑ 에서 앞 지출 뺌
# ③ P13 문서 달기가 문서 회사를 안 봄(문서의 회사로 읽음 → 보안 ⓑ) · P14 lock_project 의 select_for_update 지움(보안 ⓗ 겹친 PUT)
#   · P16 결과 경로의 module 검사 지움(S14-2b) · P7s P7 과 같은 심기를 보안 층으로(보안 ⓐ)
ROWS="P7|1|$SL|    row = DraftingProject.for_company(company_id).filter(id=project_id).first()|    row = DraftingProject.unscoped.filter(id=project_id).first()|biz:$T/service/services/test_projects.py
P8|1|$D/contracts/wire.py|        elif depth != depth_of[parent] + 1:|        elif False:|$T/contracts/test_wire.py
P12|1|$D/contracts/shapes.py|    mapping: DraftingMapping\n    settings: DraftingSettings|    mapping: DraftingMapping\n    extra: str\n    settings: DraftingSettings|$T/contracts/test_shapes.py
R1|1|$SA|    if current is not None and current.sha256 == sha:|    if False:|biz:$T/service/services/test_projects.py
V1|1|$SL|    row = DraftingProjectDocument.for_company(company_id).filter(project_id=project_id).order_by(\"-id\").first()|    row = DraftingProjectDocument.for_company(company_id).order_by(\"-id\").first()|biz:$T/service/services/test_projects.py
V5|1|$SL|    row = DraftingOutline.for_company(company_id).filter(project_id=project_id).order_by(\"-revision\").first()|    row = DraftingOutline.for_company(company_id).order_by(\"-revision\").first()|biz:$T/service/services/test_projects.py
P1|2|$E/checks.py|            if page not in given:|            if False:|$TE/test_checks.py $TF/test_draft_v1.py
P2|2|$E/checks.py|            if not numbers(bullet[\"text\"]) <= found:|            if False:|$TE/test_checks.py $TF/test_draft_v1.py
P3|2|$E/pages.py|start=1)|start=0)|$TE/test_pages.py $TF/test_draft_v1.py
P4|2|$F|    if bound > inputs.max_usd:\n        rejected =|    if False:\n        rejected =|$TF/test_draft_v1.py
P5|2|$F|        if self.adapters.spent_usd() >= self.cap:|        if False:|$TF/test_draft_v1.py
P6|2|$D/flows/binding_v1.py|        if wire.outline_sha256(found.outline) != sha or found.sha256 != sha:|        if False:|$TF/test_binding_v1.py
P9|2|$E/pages.py|    return found\n\n\ndef batch_text|    return found[:-1]\n\n\ndef batch_text|$TE/test_pages.py $TF/test_draft_v1.py
P10|2|$F|    return Routes(map=MOCK_ROUTE, draft=MOCK_ROUTE) if adapters.mock else inputs.routes|    return inputs.routes|$TF/test_draft_v1.py
P11|2|$E/pages.py|from collections.abc import Sequence\n|import django\nfrom collections.abc import Sequence\n|lint+$T/test_axes.py
P11b|2|$F|from esgapi.drafting.contracts import shapes, wire\n|import esgapi.greenwash.tools\nfrom esgapi.drafting.contracts import shapes, wire\n|$T/test_axes.py
P15|2|$F|    if ctx.resume is None:\n        return []|    if True:\n        return []|$TF/test_draft_v1.py
X1|2|$E/pages.py|from collections.abc import Sequence\n|import urllib.request\nfrom collections.abc import Sequence\n|$TE/test_purity.py
X2|2|$F|    for key, path, requirement in leaves[len(answers) :]:|    for key, path, requirement in leaves:|$TF/test_draft_v1.py
X3|2|$F|    guard = _Guard(adapters, min(inputs.max_usd, bound))\n    texts =|    guard = _Guard(adapters, inputs.max_usd)\n    texts =|$TF/test_draft_v1.py
X6|2|$F|    spent = adapters.spent_usd()\n    bound = spent +|    spent = 0.0\n    bound = spent +|$TF/test_draft_v1.py
P13|3|$SA|from esgapi.core.service.selectors import documents as document_selectors\n§    found = document_selectors.find_document(company_id=company_id, document_id=document_id)|from esgapi.core.models import DocumentRow\nfrom esgapi.core.service.selectors import documents as document_selectors\n§    found = document_selectors.find_document(company_id=DocumentRow.unscoped.get(pk=document_id).company_id, document_id=document_id)|sec:tests/security/test_drafting.py
P14|3|$SL|        .select_for_update()\n||sec:tests/security/test_drafting.py
P16|3|$D/service/actions/result.py|    if run is None or run.module != MODULE:|    if run is None:|biz:$T/service/apis/test_drafting.py
P7s|3|$SL|    row = DraftingProject.for_company(company_id).filter(id=project_id).first()|    row = DraftingProject.unscoped.filter(id=project_id).first()|sec:tests/security/test_drafting.py"

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  lint_red=1
  lint_note=""
  if [ "${tests#lint+}" != "$tests" ]; then
    tests="${tests#lint+}"
    if uv run --frozen lint-imports > "$backup/lint" 2>&1; then lint_red=0; fi
    lint_note="lint-imports $([ "$lint_red" = 1 ] && echo 빨강 || echo ★초록), "
  fi
  if [ "${tests#biz:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
  fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  # 빨강 = 종료 1 이고 FAILED 줄이 있음(ERROR 뿐인 종료 1 — DB 끊김 등 — 은 「죽음」이다)
  if [ "$code" = 1 ] && [ "${nfail:-0}" -gt 0 ] && [ "$lint_red" = 1 ]; then red=1; else red=0; fi
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, ${lint_note}$tests) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=6 ;; 2) want=21 ;; 3) want=25 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
