#!/usr/bin/env bash
# RPA1 의 심은 파손(발주서 band-handoffs/RPA1-order.md §3 「심은 파손」): 파손 하나를 심고, 그것을 물어야 할 시험이
# 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RPA1.sh --commit <1|2>
#   경계별 배치: ① R1~R8(8) · ② R9~R16(누적 16).
# 틀은 planted-breaks-IR4.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(이 워크트리의 compose postgres 가 떠 있어야 한다).
# 심는 꼴(1차 실측 뒤): R6 새 ninja 꼴(StrictIn)을 클래스 인자 extra="ignore" 로 엶 · R7 중첩 TypedDict 는 바깥 FORBID 를 물려받아
#   with_config 뺌이 초록이라(RP2b R11) extra="allow" 로 엶 · R8 은 동작 하나(get)를 COMPANY 로.
# ② 1차 실측: R2·R5 의 옛 글자가 ② 코드(models_from·RunSettingStore.get)에도 생겨 「못 심음」 → 닻을 다음 줄·앞 줄까지
#   넓힘. R16 의 test_apps.py 는 순수 층이라 biz 실행(-m django_db)에선 고르지 않음 — 빨강은 B9 실행 기록 시험.
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
case "$COMMIT" in 1|2) ;; *) echo "--commit 1·2" >&2; exit 2 ;; esac

P=esgapi/drafting
F=$P/flows
T=$P/tests
FT=$T/flows
PM=$F/prompt_model_v2.py
SL=$P/service/selectors/ai_settings.py
AP=$P/service/apis/ai_settings.py
CT=$P/contracts/ai_setting_shapes.py
MG=$P/migrations/0002_ai_settings.py
ST=$T/service/services
AT=$T/service/apis
SEC=tests/security

backup="$(mktemp -d /private/tmp/rpa1-planted.XXXXXX)"
case "$backup" in /private/tmp/rpa1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈, § 로 여럿)
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
# ① R1 입력 글 자리 지킴 지움 · R2 temperature null 받음 · R3 texts_from(None) 이 v1 글 · R4 UPDATE 권한에 title ·
#   R5 판 읽기 회사 조건 빠짐(for_company → unscoped) · R6 새 ninja 꼴(적용 본문) extra 엶 · R7 중첩 계약 꼴(저장한
#   사람) extra="allow" · R8 판 하나 읽기를 OPERATOR → COMPANY
# ② R9 versions 에 AI 열쇠 안 실음 · R10 「글 ⇔ 열쇠」 대조를 모델 sha 뒤로 · R11 저장 판도 늘 DEFAULT_TEXTS ·
#   R12 S2 칸 temperature 무시(상수) · R13 S3 칸 위끝 무시(상수) · R14 저장 글엔 MARKER_RULES 꼬리 안 붙임 ·
#   R15 same_versions 가 AI 열쇠를 뺌 · R16 EXTRAS 에 drafting 안 닮
ROWS="R1|1|$PM|            if missing:\n                return PromptRefused(|            if False:\n                return PromptRefused(|$FT/test_prompt_model_v2.py
R2|1|$PM|        if step.temperature is None:\n            return ModelSettingRefused(|        if False:\n            return ModelSettingRefused(|$FT/test_prompt_model_v2.py
R3|1|$PM|    if accepted is None:\n        return DEFAULT_TEXTS|    if accepted is None:\n        from esgapi.drafting.engines.v1.texts import DEFAULT_TEXTS as V1_TEXTS\n\n        return V1_TEXTS|$FT/test_prompt_model_v2.py
R4|1|$MG|grant(f'\"{TABLE}\"', \"UPDATE (applied, applied_at)\")|grant(f'\"{TABLE}\"', \"UPDATE (applied, applied_at, title)\")|sec:$SEC/test_owner.py $SEC/test_drafting_ai_settings.py
R5|1|$SL|    \"\"\"판 하나.\"\"\"\n    row = DraftingAiSettingRow.for_company(company_id).filter(id=setting_id).first()|    \"\"\"판 하나.\"\"\"\n    row = DraftingAiSettingRow.unscoped.filter(id=setting_id).first()|sec:$SEC/test_drafting_ai_settings.py
R6|1|$AP|class DraftingAiSettingApply(StrictIn):|class DraftingAiSettingApply(StrictIn, extra=\"ignore\"):|$T/contracts/test_ai_setting_shapes.py
R7|1|$CT|@with_config(FORBID)\nclass DraftingAiSettingAuthor(TypedDict):|@with_config({\"extra\": \"allow\"})\nclass DraftingAiSettingAuthor(TypedDict):|$T/contracts/test_ai_setting_shapes.py
R8|1|esgapi/core/permissions.py|    \"drafting_ai_setting_get\": OPERATOR,|    \"drafting_ai_setting_get\": COMPANY,|biz:$AT/test_ai_settings.py
R9|2|$F/binding_v2.py|            \"documentEtag\": document.etag,\n            **self._ai_versions(company_id),\n|            \"documentEtag\": document.etag,\n|$FT/test_binding_v2_settings.py $FT/test_binding_v2.py
R10|2|$F/binding_v2.py|        if (found.prompts is not None) != checks_prompts:  # 다른 대조보다 먼저\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n§        texts = None if found.prompts is None else self._saved_texts(|§        if (found.prompts is not None) != checks_prompts:\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n        texts = None if found.prompts is None else self._saved_texts(|$FT/test_binding_v2_settings.py
R11|2|$F/binding_v2.py|        return pm.texts_from(texts), pm.models_from(model)|        return DEFAULT_TEXTS, pm.models_from(model)|biz:$FT/test_runs_drafting_settings.py
R12|2|$F/draft_v2.py|        temperature=model.temperature,\n    )\n\n\ndef draft_request(|        temperature=TEMPERATURE,\n    )\n\n\ndef draft_request(|$FT/test_draft_v2.py
R13|2|$F/draft_v2.py|        schema_name=\"bullets\",\n        max_output_tokens=model.max_output_tokens,|        schema_name=\"bullets\",\n        max_output_tokens=MAX_OUTPUT_TOKENS,|$FT/test_draft_v2.py
R14|2|$F/draft_v2.py|    system = v2_texts.draft_system(system)\n|    system = v2_texts.draft_system(system) if inputs.texts is DEFAULT_TEXTS else system\n|$FT/test_draft_v2.py
R15|2|$F/binding_v2.py|    return {k: v for k, v in left.items() if k not in FACT_KEYS} == {\n        k: v for k, v in right.items() if k not in FACT_KEYS\n|    ai = FACT_KEYS.union({\"aiSetting\", \"aiSettingId\", \"modelSettingsSha256\", \"promptsSha256\"})\n    return {k: v for k, v in left.items() if k not in ai} == {\n        k: v for k, v in right.items() if k not in ai\n|$FT/test_binding_v2_settings.py
R16|2|$P/apps.py|        EXTRAS.register(\"drafting\", RunSettingExtras())|        assert EXTRAS and RunSettingExtras|biz:$FT/test_runs_drafting_settings.py $T/test_apps.py"

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
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db ${tests#biz:} \
      > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider --create-db ${tests#sec:} \
      > "$backup/log" 2>&1
    code=$?
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
  fi
  if [ "$code" = 1 ]; then red=1; else red=0; fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=8 ;; 2) want=16 ;; esac  # ② 는 그 경계에서 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
