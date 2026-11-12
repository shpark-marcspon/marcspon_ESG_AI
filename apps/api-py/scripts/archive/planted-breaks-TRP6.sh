#!/usr/bin/env bash
# TRP6 의 심은 파손(발주서 §3-7, P1~P13 + 러너 몫 P14): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-TRP6.sh --commit <1|2|3>
#   경계별 배치: ① P1~P9·P12~P15(13 — 서버) · ② + P10·P11(15 — 웹) · ③ + P16~P18(18 — 가지 리뷰 상한).
#   P16 깊이 상한 뺌 · P17 EOCD 검사 뺌 · P18 `>` 없이 이어진 바이트 검사 뺌 → 3-1 가지 리뷰 ③ 시험 빨강.
#   P15(검증 B1): 저장소 설정 없음 갈래를 지움 → 3-2 `test_without_a_configured_storage_the_count_is_null` 빨강.
#   P2 는 감독 답 1 로 「앞몫 둘(정규화·file_roundtrip) 다 뺌」(P2′ — file_roundtrip 만 빼면 정규화가 \r 를 이미 바꾼다).
#   P14(러너 몫): 몸 직속이 아닌 w:p(표 칸·sdt 안)의 글도 셈 → 3-1-2 표 칸·sdt · 3-1-3 (ㄴ) 빨강.
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 옛 글·새 글에 「§」가 있으면 그것으로 나눈 짝마다 바꾼다. 글 안의 「\n」 두 글자는 줄바꿈이다. 새 글이 「@base」면
#   그 파일을 기준(3d7dd5c9)의 것으로 바꾼다(P9).
# 시험 칸은 빈칸으로 나눈 「<층>:<경로>」 목록이다 — pure(uv pytest)·biz(scripts/test-business.sh)·sec
#   (scripts/test-security.sh — biz·sec 은 이 워크트리의 compose postgres 가 떠 있어야 한다)·web(vitest, ②). 층마다 한 번
#   돌리고 **층마다 빨개야**(종료 1) 그 줄이 빨강이다(수집 실패 2 는 「죽음」 — 빨강이 아니다).
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

BASE_COMMIT=3d7dd5c9
TR=esgapi/translation
WEB=../web

backup="$(mktemp -d /private/tmp/trp6-planted.XXXXXX)"
case "$backup" in /private/tmp/trp6-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- .. | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>
  if [ "$3" = "@base" ]; then git show "$BASE_COMMIT:apps/api-py/$1" > "$1"; return $?; fi
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

run_layer() {  # run_layer <층> <경로…> → 종료 코드
  local layer="$1"; shift
  case "$layer" in
    pure) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider "$@" ;;
    biz) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider "$@" ;;
    sec) env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider "$@" ;;
    web) (cd "$WEB" && PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" pnpm exec vitest run "$@") ;;
    *) echo "모르는 층: $layer"; return 2 ;;
  esac
}

# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험>
PT=$TR/tools/page_tags.py
PA=$TR/service/actions/pages.py
TT=$TR/tests/tools/test_page_tags.py
TB=$TR/tests/service/actions/test_pages.py
TS=tests/security/test_translation.py
ROWS=""
read -r -d '' ROWS <<'ROWEOF' || true
P1|1|PT|    largest = max(pages)|    largest = len(pages)|pure:TT
P2|1|PT|    for line in file_roundtrip(text).split(§        match = PAGE_TAG_LINE_RE.match(normalize_structured_tags(_LONG_BLANKS.sub("    ", line)).strip())|    for line in (text).split(§        match = PAGE_TAG_LINE_RE.match(line.strip())|pure:TT
P3|1|PA|    document = document_selectors.find_document(company_id=company_id, document_id=document_id)|    document = next((d for c in range(1, 1000) if (d := document_selectors.find_document(company_id=c, document_id=document_id)) is not None), None)|biz:TB sec:TS
P4|1|PA|import logging\n§    if not isinstance(got, ObjectBytes):|import logging\n\nfrom esgapi.core.exceptions import ApplicationError\n§    if type(got).__name__ == "StorageUnavailable":\n        raise ApplicationError("unavailable", "storage_unavailable", "저장소에 닿지 못했다")\n    if not isinstance(got, ObjectBytes):|biz:TB
P5|1|PA|    counted = page_tags.page_count(got.data)|    if got.data.startswith(b"%PDF-"):\n        return Pages(document_id, document.page_count, None)\n    counted = page_tags.page_count(got.data)|biz:TB
P6|1|PA|    if document.etag is not None and got.etag != document.etag:|    if False:|biz:TB
P7|1|PA|    if document.status != "uploaded":\n        return _unknown(document_id, "not_uploaded")\n||biz:TB
P8|1|esgapi/core/permissions.py|    "translation_document_pages": COMPANY,\n||pure:esgapi/core/tests/test_permissions.py biz:esgapi/core/tests/test_permissions_wiring.py
P9|1|generated/openapi.json||@base|pure:esgapi/config/tests/test_api_contract.py
P12|1|PT|        if data.startswith(b"PK\x03\x04"):\n            return _docx(data)|        if data.startswith(b"PK\x03\x04"):\n            from esgapi.translation.flows.colab_158 import read_document\n\n            return _result(_tags_of(getattr(read_document(data), "text", "")))|pure:TT biz:TB sec:TS
P13|1|PT|                if kind is None or kind == "textWrapping":|                if True:|pure:TT
P14|1|PT|        if len(stack) == 2 and name == _P and stack[1] == _BODY and stack[0] == _DOCUMENT:§        elif self.parts is not None and len(stack) in (4, 5) and tuple(stack) in _RUN_PATHS:§        if len(self.stack) == 2 and self.parts is not None:|        if name == _P:§        elif self.parts is not None and stack[-1] == _R:§        if name == _P and self.parts is not None:|pure:TT
P15|1|PA|    if storage is None:\n        return _unknown(document_id, "storage_unconfigured")\n||biz:TB
P10|2|../web/src/entities/translation/api/server.ts|await pagesOf(id, |(|web:src/entities/translation/api/server.test.ts web:src/pages/translation-new/ui/NewTranslationScreen.test.tsx
P11|2|../web/src/entities/translation/api/server.ts|      return fallback;\n    } finally {|      throw refuse('rejected', 'pages failed');\n    } finally {|web:src/entities/translation/api/server.test.ts web:src/pages/translation-new/ui/NewTranslationScreen.test.tsx
P16|3|PT|        if len(stack) >= MAX_DEPTH:\n            raise _Stop("unsafe")\n||pure:TT
P17|3|PT|    if (refused := _central_directory_refusal(data)) is not None:\n        return PageTags(None, refused)\n||pure:TT
P18|3|PT|                if run + (len(chunk) if first < 0 else first) > MAX_TAG_RUN:\n                    raise _Stop("unsafe")\n||pure:TT
ROWEOF

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  case "$file" in PT) file=$PT ;; PA) file=$PA ;; esac
  tests="$(echo "$tests" | sed "s|:TT|:$TT|g; s|:TB|:$TB|g; s|:TS|:$TS|g")"
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  red=1
  codes=""
  failed=""
  for layer in pure biz sec web; do
    paths="$(echo "$tests" | tr ' ' '\n' | sed -n "s|^$layer:||p" | paste -sd' ' -)"
    [ -n "$paths" ] || continue
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    run_layer "$layer" $paths > "$backup/log" 2>&1
    code=$?
    codes="$codes $layer=$code"
    [ "$code" = 1 ] || red=0
    failed="$failed $(grep -o -E '^FAILED [^ ]*|FAIL +[^ ]*' "$backup/log" 2>/dev/null | sed -E 's/^FAIL(ED)? +//' | head -4 | paste -sd' ' -)"
  done
  [ -n "$codes" ] || { red=0; echo "$id ★ 돌린 시험이 없다"; bad=$((bad + 1)); }
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT$codes)$failed"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=13 ;; 2) want=15 ;; 3) want=18 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
