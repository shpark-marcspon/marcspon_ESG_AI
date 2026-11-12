#!/usr/bin/env bash
# TR3a 의 심은 파손(발주서 §3-5, 1~18 + 8b + 감독 처분 ★B 의 8c·8d + 순수성 8e(온실가스 67 권고) + 내용으로 고르기
#   (검증 B1·B2 뒤 감독 처분)의 8f·8g + 검증 R5·R6 의 8h·8i + 가지 리뷰 처분(10-23)의 8j~8n = 31): 파손 하나를 심고,
#   그것을 물어야 할 시험이 빨개지는지 본다. 8 은 「XML 로 보임」 판정을 끔(대상 0), 8b 는 모든 항목을 훑음(바이너리
#   머리 거절)이다. 8j UCS-4 BOM 줄 뺌 · 8k 속성 셈 뺌 · 8l 표지 간격 상한 뺌 · 8m UTF-16LE 의 앞 공백 꼴 뺌 ·
#   8n 처리 지시 handler 뺌(가지 리뷰 둘째 — 주석·처리 지시 셈).
#   사용: apps/api-py/scripts/planted-breaks-TR3a.sh --commit <1|2>
#   경계별 배치: ① 1~15·8b~8g(21) · ② + 16·17·18·8h~8n(31 — 가지 리뷰 뒤 커밋 ③·④ 도 이 배치로 잰다).
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다. 새 글이 「@rm」이면 파일을
#   지운다(되쓰기로 돌아온다).
# 옛 글·새 글에 「§」가 있으면 그것으로 나눈 짝마다 바꾼다(한 파손이 여러 자리를 지우는 것 — 5a).
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층
#   (scripts/test-business.sh — 이 워크트리의 compose postgres 가 떠 있어야 한다), 「sec:」로 시작하면 보안 층
#   (scripts/test-security.sh — 같은 postgres). run 지문(BASE 대조)은 section4-TR3a.sh 6 이 잰다.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0(② 의 django_db 줄은 compose 의 DB 를 쓴다).
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1|2) ;; *) echo "--commit 1·2" >&2; exit 2 ;; esac

TR=esgapi/translation
T=$TR/tests
FT=$T/flows

backup="$(mktemp -d /private/tmp/tr3a-planted.XXXXXX)"
case "$backup" in /private/tmp/tr3a-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈. 새 글이 「@rm」이면 파일을 지운다)
  if [ "$3" = "@rm" ]; then rm "$1"; return 0; fi
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
X=$TR/tools/glossary_xlsx.py
ROWS="1|1|$TR/contracts/options_shapes.py|r\"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$\"|r\"^.+$\"|$FT/test_binding_158.py
2|1|$TR/contracts/options_shapes.py|    base: NotRequired[Annotated[list[GlossaryPair], Field(max_length=GLOSSARY_PAIRS_MAX)]]|    base: NotRequired[list[GlossaryPair]]|$FT/test_binding_158.py
3|1|$TR/outputs/digest.py|    elif failed or any(v[\"reviewStatus\"] != \"reviewed\" for v in summaries):|    elif failed:|$T/outputs/test_digest.py
4|1|$TR/outputs/digest.py| if miss[\"pageNum\"] in targets),|),|$T/outputs/test_digest.py
5|1|$TR/outputs/digest.py|found[\"bilingual\"] if found[\"bilingual\"] in built else None§found[\"qa\"] if found[\"qa\"] in built else None§found[\"autofix\"] if found[\"autofix\"] in built else None|found[\"bilingual\"]§found[\"qa\"]§found[\"autofix\"]|$T/outputs/test_digest.py
6|1|$TR/flows/colab_158.py|[dict(checked), dict(summary)]|[dict(checked)]|$FT/test_colab_158.py
7|1|$TR/flows/colab_158.py|[dict(checked), dict(summary)]|[dict(summary), dict(checked)]|$FT/test_colab_158.py
8|1|$X|        if _looks_like_xml(entry):|        if False:|$T/tools/test_glossary_xlsx.py
8b|1|$X|    return data.startswith(_XML_SIGNATURES) or any(pattern.match(data) for pattern in _SPACE_THEN_LT)|    return True|$T/tools/test_glossary_xlsx.py
8f|1|$X|        + b\")*\"|        + b\"){0}\"|$T/tools/test_glossary_xlsx.py
8g|1|$X|    b\"\\xfe\\xff\",  # UTF-16 BE BOM\n    b\"\\xff\\xfe\",  # UTF-16 LE BOM\n||$T/tools/test_glossary_xlsx.py
8c|1|$X|        if depth[0] > MAX_XML_DEPTH:|        if False:|$T/tools/test_glossary_xlsx.py
8d|1|$X|        if elements[0] > MAX_XML_ELEMENTS:|        if False:|$T/tools/test_glossary_xlsx.py
8e|1|$X|        _check_entries(archive, sizes)\n|        _check_entries(archive, sizes)\n        if False:\n            archive.extractall()\n|$T/tools/test_glossary_xlsx_purity.py
9|1|$X|    parser.StartDoctypeDeclHandler = on_doctype\n    parser.EntityDeclHandler = on_entity\n||$T/tools/test_glossary_xlsx.py
10|1|$X|        if entry.file_size > MAX_ENTRY_BYTES:|        if False:|$T/tools/test_glossary_xlsx.py
11|1|$X|                if scanned > MAX_SCANNED_ROWS:|                if False:|$T/tools/test_glossary_xlsx.py
12|1|$X|                if head != HEADER:|                if False:|$T/tools/test_glossary_xlsx.py
13|1|$X|            if ko in first_row:|            if False:|$T/tools/test_glossary_xlsx.py
14|1|$X|            if len(pairs) == MAX_PAIRS:|            if False:|$T/tools/test_glossary_xlsx.py
15|1|$TR/apps.py|            max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS,\n||biz:$FT/test_runs_translation.py
8h|2|$X|\"utf-16-le\", \"utf-16-be\", \"utf-32-le\"|\"utf-16-le\", \"utf-32-le\"|$T/tools/test_glossary_xlsx.py
8i|2|$X|        if depth[0] > MAX_XML_DEPTH:|        if depth[0] > 10**9:|$T/tools/test_glossary_xlsx.py
8j|2|$X|    b\"\\x00\\x00\\xfe\\xff\",  # UCS-4 BE BOM\n    b\"\\xff\\xfe\\x00\\x00\",  # UCS-4 LE BOM\n||$T/tools/test_glossary_xlsx.py
8k|2|$X|        count(1 + len(attributes))|        count(1)|$T/tools/test_glossary_xlsx.py
8l|2|$X|            if min(len(data), start + _CHUNK) - last[0] > MAX_XML_SPAN:|            if False:|$T/tools/test_glossary_xlsx.py
8m|2|$X|    for codec in (\"utf-8\", \"utf-16-le\", |    for codec in (\"utf-8\", |$T/tools/test_glossary_xlsx.py
8n|2|$X|    parser.ProcessingInstructionHandler = on_node\n||$T/tools/test_glossary_xlsx.py
16|2|$TR/service/apis/translation.py|    return dict(glossary_actions.read(request.body))|    found = glossary_actions.read(request.body)\n    if not found[\"ok\"]:\n        raise ApplicationError(\"invalid_input\", \"invalid_glossary\", \"용어집을 읽지 못했다\")\n    return dict(found)|biz:esgapi/core/tests/test_permissions_wiring.py $FT/test_glossary_paths.py
17|2|$TR/service/actions/glossary.py|    \"\"\"xlsx 바이트 → 짝 목록(ok true) 또는 거절 갈래(ok false). 어떤 바이트도 예외 대신 갈래다.\"\"\"\n|    \"\"\"xlsx 바이트 → 짝 목록(ok true) 또는 거절 갈래(ok false). 어떤 바이트도 예외 대신 갈래다.\"\"\"\n    from esgapi.core.service.services import documents\n\n    documents.default_storage().put(\"glossary/raw.xlsx\", data)\n|biz:$FT/test_glossary_paths.py
18|2|esgapi/core/permissions.py|    \"translation_glossary_read\": COMPANY,|    \"translation_glossary_read\": CUSTOMER,|sec:tests/security/test_translation.py tests/security/test_tenant_paths.py"

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
  if [ "${tests#biz:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록. -x 없이 — 어느 파일이 빨개졌는지 줄마다 본다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록. -x 없이 — 어느 파일이 빨개졌는지 줄마다 본다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -x -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | head -6 | paste -sd' ' -)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests) ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=21 ;; 2) want=31 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
