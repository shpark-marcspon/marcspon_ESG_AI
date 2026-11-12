#!/usr/bin/env bash
# TR4 의 심은 파손(발주서 §3-6): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-TR4.sh --commit <1|2|3>
#   경계별 배치: ① P1~P6 + 러너 몫 R1(7) · ② + P7~P12·P19 + 러너 몫 R2·R3·R4(17) · ③ + P13~P18 + 러너 몫 R5·R6·R7(26).
# 틀은 planted-breaks-TR3a.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(이 워크트리의 compose postgres 가 떠 있어야 한다).
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

TR=esgapi/translation
EN=$TR/engines/colab_158
T=$TR/tests
ET=$T/engines/colab_158
FT=$T/flows
ST=$T/service/services
AT=$T/service/apis

backup="$(mktemp -d /private/tmp/tr4-planted.XXXXXX)"
case "$backup" in /private/tmp/tr4-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# P1 계획이 DEFAULT_TEXTS · P2 tone_for 늘 general · P3 {page_num} 첫 번만 · P4 검수가 상수 그대로 · P5 dry_run 이 models
#   무시 · P6 위끝을 칸 값으로 · R1(러너) 결과 settings.routes 가 칸을 무시(늘 그 밖 파트 칸)
# ② R2(러너, 검증 ① 권고 1) 흐름 engine_input 이 texts 를 빠뜨림(엔진 기본값으로 돎) · P7 프롬프트 거절 무시 · P8 메모
#   strip 빠짐 · P9 기본 글이면 NULL 로 접음 · P10 판 읽기 회사 조건 빠짐 · P11 처리 값 글자 24 · P12 MODEL_FIELDS
#   ceo·other 뒤바꿈 · P19 temperature 받음(0.2 는 참이라 지나감 — 0 만 막는 꼴)
#   · R3(러너, 73 조건 (다)) 앱 역할 GRANT UPDATE 를 표 전체로 · R4(검증 ② B1) 저장 판 칸 메모를 늘 기본 메모로
# ③ P13 기본 판에 promptsSha256 · P14 (저장 판) 모델 sha 대조 지움 · P15 「저장 글⇔열쇠」 검사를 모델 대조 뒤로 · P16 적용
#   판 조회에 첫 회사(회사 조건 없이 id 차례 첫 적용 판) · P17 inputs_with 늘 DEFAULT_MODELS · P18 옛 실행을 mismatch
#   · R5(러너, 검증 ② M2) 저장 글 다시 받기의 거절을 무시(거절 값으로 sha 를 셈) · R6·R7(검증 ③ B1) 적용(services
#   unusable)·prompt-model 읽기(actions)의 저장 글 다시 받기 거절을 무시
ROWS="P1|1|$EN/plan.py|    texts = inputs.texts\n    sp = texts.page_system|    from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS as texts\n\n    sp = texts.page_system|$ET/test_texts.py
P2|1|$EN/texts.py|        return {\"ceo_message\": self.ceo_message_tone, \"story\": self.story_tone}.get(part, self.general_tone)|        return self.general_tone|$ET/test_texts.py
P3|1|$EN/texts.py|        return self.autofix_korean.replace(PAGE_NUM_SLOT, str(page_num))|        return self.autofix_korean.replace(PAGE_NUM_SLOT, str(page_num), 1)|$ET/test_texts.py
P4|1|$EN/review.py|    reply = gateway.complete(\"review\", \"review\", system, |    reply = gateway.complete(\"review\", \"review\", prompts.QA_SYSTEM_PROMPT, |$ET/test_texts.py
P5|1|$TR/tools/llm_bridge.py|            report = self.client.dry_run(self._request(call.site, call.role, call.system, call.user, call.max_tokens))|            report = self.client.dry_run(\n                LlmBridge(self.client, part=self.part, tenant=self.tags.tenant or \"\")._request(\n                    call.site, call.role, call.system, call.user, call.max_tokens\n                )\n            )|$ET/test_texts.py
P6|1|$TR/tools/llm_bridge.py|            max_output_tokens=min(max_tokens, model.max_output_tokens),|            max_output_tokens=model.max_output_tokens,|$ET/test_texts.py
R1|1|$TR/flows/colab_158.py|model_for(role, inputs.part, inputs.models).route|model_for(role, \"general\", inputs.models).route|$FT/test_colab_158_models.py
R2|2|$TR/flows/colab_158.py|        texts=inputs.texts,\n    )|    )|$FT/test_colab_158_models.py
P7|2|$TR/service/services/ai_settings.py|    if isinstance(texts, PromptRefused):\n        return PromptsRefused(texts.code, texts.message, texts.field)\n    stored = to_input(model)|    if isinstance(texts, PromptRefused):\n        texts = None\n    stored = to_input(model)|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
P8|2|$TR/service/services/ai_settings.py|    stored_prompts = None if texts is None else prompts_input(texts)|    stored_prompts = prompts|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
P9|2|$TR/service/services/ai_settings.py|    stored_prompts = None if texts is None else prompts_input(texts)|    stored_prompts = (\n        None\n        if texts is None or prompt_model_158.texts_from(texts) == prompt_model_158.texts_from(None)\n        else prompts_input(texts)\n    )|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
P10|2|$TR/service/selectors/ai_settings.py|    row = TranslationAiSettingRow.for_company(company_id).filter(id=setting_id).first()\n    return SettingMissing()|    row = TranslationAiSettingRow.unscoped.filter(id=setting_id).first()\n    return SettingMissing()|biz:$AT/test_ai_settings.py $ST/test_ai_settings.py
P11|2|$TR/flows/prompt_model_158.py|gates.TABLE_BATCH_SIZE)|24)|$FT/test_prompt_model_158.py
P12|2|$TR/flows/prompt_model_158.py|    \"translate_ceo\": \"translate_ceo\",\n    \"translate_other\": \"translate_other\",|    \"translate_ceo\": \"translate_other\",\n    \"translate_other\": \"translate_ceo\",|$FT/test_prompt_model_158.py
P19|2|$TR/flows/prompt_model_158.py|        if step.temperature is not None:|        if step.temperature is not None and not step.temperature:|$FT/test_prompt_model_158.py
R3|2|$TR/migrations/0001_ai_settings.py|grant(f'\"{TABLE}\"', \"UPDATE (applied, applied_at)\")|grant(f'\"{TABLE}\"', \"UPDATE\")|sec:tests/security/test_owner.py tests/security/test_translation_ai_settings.py
R4|2|$TR/flows/prompt_model_158.py|memo=DEFAULT_MEMOS[key] if found is None else found.memo,|memo=DEFAULT_MEMOS[key],|biz:$AT/test_ai_settings.py
P13|3|$TR/flows/binding_158.py|        return {**self.versions(options), \"aiSetting\": DEFAULT_TITLE, **common}|        return {**self.versions(options), \"aiSetting\": DEFAULT_TITLE, **common, \"promptsSha256\": \"0\" * 64}|$FT/test_binding_158_settings.py
P14|3|$TR/flows/binding_158.py|        if model_settings_sha256(model) != versions.get(\"modelSettingsSha256\"):|        if False:|$FT/test_binding_158_settings.py
P15|3|$TR/flows/binding_158.py|        if (found.prompts is not None) != checks_prompts:  # 다른 대조보다 먼저\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n§        texts = None if found.prompts is None else self._saved_texts(|§        if (found.prompts is not None) != checks_prompts:\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n        texts = None if found.prompts is None else self._saved_texts(|$FT/test_binding_158_settings.py
P16|3|$TR/service/selectors/ai_settings.py|        row = TranslationAiSettingRow.for_company(company_id).filter(applied=True).first()\n        return DefaultSetting()|        row = TranslationAiSettingRow.unscoped.filter(applied=True).order_by(\"id\").first()\n        return DefaultSetting()|biz:$FT/test_runs_translation_settings.py
P17|3|$TR/flows/binding_158.py|        return pm.texts_from(texts), pm.models_from(model)|        return pm.texts_from(texts), DEFAULT_MODELS|$FT/test_binding_158_settings.py
P18|3|$TR/flows/binding_158.py|            return DEFAULT_TEXTS, DEFAULT_MODELS  # 열쇠 없는 옛 실행|            raise AiSettingMismatch(\"옛 실행\")  # 열쇠 없는 옛 실행|$FT/test_binding_158_settings.py
R5|3|$TR/flows/binding_158.py|        texts = pm.accept_prompts(saved)\n        if isinstance(texts, PromptRefused):|        texts = pm.accept_prompts(saved)\n        if False:|$FT/test_binding_158_settings.py
R6|3|$TR/service/services/ai_settings.py|    texts = None if found.prompts is None else prompt_model_158.accept_prompts(found.prompts)\n    if isinstance(texts, PromptRefused):\n        return SettingUnusable(texts.code, found.name)\n|    texts = None if found.prompts is None else prompt_model_158.accept_prompts(found.prompts)\n|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
R7|3|$TR/service/actions/ai_settings.py|    if isinstance(prompts, PromptRefused):\n        return services.SettingUnusable(prompts.code, found.name)\n    return prompt_model_158.prompt_model(|    if isinstance(prompts, PromptRefused):\n        prompts = None\n    return prompt_model_158.prompt_model(|biz:$AT/test_ai_settings.py"

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

case "$COMMIT" in 1) want=7 ;; 2) want=17 ;; 3) want=26 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
