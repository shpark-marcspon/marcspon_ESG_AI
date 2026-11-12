#!/usr/bin/env bash
# DVA1 의 심은 파손(발주서 부록 §3-6): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-DVA1.sh --commit <1|2|3>
#   경계별 배치: ① P1~P6·P21 + 러너 몫 R1·R2(9) · ② P7~P13·P22·P23 + 러너 몫 R3(10 — 누적 19)
#   · ③ P14~P20 + 러너 몫 R4(8 — 누적 27).
# 틀은 planted-breaks-TR4.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
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

D=esgapi/dataverify
EN=$D/engines/colab_156
FL=$D/flows/colab_156.py
T=$D/tests
ET=$T/engines/colab_156
FT=$T/flows
ST=$T/service/services
AT=$T/service/apis
PM=$D/flows/prompt_model_156.py
SV=$D/service/services/ai_settings.py
SL=$D/service/selectors/ai_settings.py
BN=$D/flows/binding_156.py

backup="$(mktemp -d /private/tmp/dva1-planted.XXXXXX)"
case "$backup" in /private/tmp/dva1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 render 를 순차 .replace · P2 검토 지시 글의 {{ 그대로 · P3 _review 가 DEFAULT_TEXTS · P4 끈 인사이트가 TEMPERATURE
#   상수 · P5 estimate 가 texts 무시 · P6 {최대 걸음 − 4} 값을 n−2 · P21 _plan 이 texts= 를 빠뜨림
#   · R1(러너) 결과 settings.temperature 가 상수 · R2(러너) ASCII 변형 자리를 받지 않음
# ② P7 입력 글 자리 검사 지움 · P8 자리 검사를 지시 글에도 · P9 메모 strip 빠짐(받은 글 그대로 저장) · P10 기본 글이면
#   NULL 로 접음 · P11 판 읽기 회사 조건 빠짐 · P12 처리 값 글자 12 · P13 temperature null 받음 · P22 prompt-model 이
#   저장 메모 대신 DEFAULT_MEMOS · P23 services.unusable 이 글 다시 받기를 건너뜀 · R3(러너) 칸 단위 UPDATE 를 표 단위로
# ③ P14 기본 판에 promptsSha256 · P15 글 sha 대조 지움 · P16 열쇠⇔글 검사를 모델 대조 뒤로 · P17 실행기 판 조회에
#   회사 조건 빠짐 · P18 inputs_with 가 늘 코드 값 · P19 옛 실행을 mismatch · P20 inputs_with 가 get 대신 applied
#   · R4(러너) 판의 위끝(max_output_tokens)을 흐름에 넘기지 않음
ROWS="P1|1|$EN/prompts.py|    return pattern.sub(lambda match: table[match.group(0)], template)|    for spelling, value in table.items():\n        template = template.replace(spelling, value)\n    return template|$ET/test_texts.py
P2|1|$EN/prompts.py|     - value_of_by_name 이 { \"value\": \"N/A\" } 를|     - value_of_by_name 이 {{ \"value\": \"N/A\" }} 를|$ET/test_texts.py
P3|1|$FL|prompts.review_prompt(hints=formulas, data_split=data_split, texts=inputs.texts)|prompts.review_prompt(hints=formulas, data_split=data_split, texts=prompts.DEFAULT_TEXTS)|$FT/test_flow_texts.py
P4|1|$FL|            timeout_ms=TIMEOUT_MS,\n            temperature=inputs.temperature,\n        )\n        end = ended_call|            timeout_ms=TIMEOUT_MS,\n            temperature=TEMPERATURE,\n        )\n        end = ended_call|$FT/test_flow_texts.py
P5|1|$FL|    plan_system, plan_user = prompts.plan_prompt(**company, data_split=data_split, texts=inputs.texts)|    plan_system, plan_user = prompts.plan_prompt(**company, data_split=data_split)|$FT/test_flow_texts.py
P6|1|$EN/prompts.py|STEPS_MINUS_4: str(max_steps - 4)|STEPS_MINUS_4: str(max_steps - 2)|$ET/test_texts.py
P21|1|$FL|prompts.plan_prompt(**_company(inputs.received), data_split=data_split, texts=inputs.texts)|prompts.plan_prompt(**_company(inputs.received), data_split=data_split)|$FT/test_flow_texts.py
R1|1|$FL|\"temperature\": repr(inputs.temperature) if ran else None,|\"temperature\": repr(TEMPERATURE) if ran else None,|$FT/test_flow_texts.py
R2|1|$EN/prompts.py|ALIASES: Final[Mapping[str, str]] = {\"{최대 걸음 - 4}\": STEPS_MINUS_4, \"{최대 걸음 - 2}\": STEPS_MINUS_2}|ALIASES: Final[Mapping[str, str]] = {}|$ET/test_texts.py
P7|2|$PM|            if missing:\n                return PromptRefused(|            if False:\n                return PromptRefused(|$FT/test_prompt_model_156.py
P8|2|$PM|prompts.missing_slots(prompt.text, prompts.REQUIRED.get(FIELDS[prompt.key], ()))|prompts.missing_slots(prompt.text, prompts.REQUIRED.get(FIELDS[prompt.key], prompts.PLACEHOLDERS[step.key]))|$FT/test_prompt_model_156.py
P9|2|$SV|    stored_prompts = None if texts is None else prompts_input(texts)|    stored_prompts = prompts|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
P10|2|$SV|    stored_prompts = None if texts is None else prompts_input(texts)|    stored_prompts = (\n        None\n        if texts is None or prompt_model_156.texts_from(texts) == prompt_model_156.texts_from(None)\n        else prompts_input(texts)\n    )|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
P11|2|$SL|    row = DataverifyAiSettingRow.for_company(company_id).filter(id=setting_id).first()\n    return SettingMissing()|    row = DataverifyAiSettingRow.unscoped.filter(id=setting_id).first()\n    return SettingMissing()|biz:$AT/test_ai_settings.py $ST/test_ai_settings.py
P12|2|$PM|{\"key\": \"plan_steps\", \"label\": \"계산 계획 걸음\", \"value\": prompts.PLAN_MAX_STEPS}|{\"key\": \"plan_steps\", \"label\": \"계산 계획 걸음\", \"value\": 12}|$FT/test_prompt_model_156.py
P13|2|$PM|        if step.temperature is None:\n            return ModelSettingRefused(|        if False:\n            return ModelSettingRefused(|$FT/test_prompt_model_156.py
P22|2|$PM|memo=DEFAULT_MEMOS[key] if found is None else found.memo,|memo=DEFAULT_MEMOS[key],|biz:$AT/test_ai_settings.py
P23|2|$SV|    texts = None if found.prompts is None else prompt_model_156.accept_prompts(found.prompts)|    texts = None|biz:$ST/test_ai_settings.py
R3|2|$D/migrations/0001_ai_settings.py|grant(f'\"{TABLE}\"', \"UPDATE (applied, applied_at)\")|grant(f'\"{TABLE}\"', \"UPDATE\")|sec:tests/security/test_owner.py tests/security/test_dataverify_ai_settings.py
P14|3|$BN|            common = ai_versions(setting_id=None, model=self._defaults(), prompts=None)\n            return|            common = ai_versions(setting_id=None, model=self._defaults(), prompts=None)\n            common = {**common, \"promptsSha256\": \"\"}\n            return|$FT/test_binding_156_settings.py
P15|3|$BN|        if prompts_sha256(texts) != versions.get(\"promptsSha256\"):|        if False:|$FT/test_binding_156_settings.py
P16|3|$BN|        if (found.prompts is not None) != checks_prompts:  # 다른 대조보다 먼저\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n§        texts = None if found.prompts is None else self._saved_texts(|§        if (found.prompts is not None) != checks_prompts:\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n        texts = None if found.prompts is None else self._saved_texts(|$FT/test_binding_156_settings.py
P17|3|$SL|        row = DataverifyAiSettingRow.for_company(company_id).filter(id=setting_id).first()\n        return SettingNotFound(setting_id)|        row = DataverifyAiSettingRow.unscoped.filter(id=setting_id).first()\n        return SettingNotFound(setting_id)|biz:$FT/test_runs_dataverify_settings.py
P18|3|$BN|        return pm.texts_from(texts), pm.models_from(model)|        return prompts.DEFAULT_TEXTS, CODE_MODEL|$FT/test_binding_156_settings.py
P19|3|$BN|            return prompts.DEFAULT_TEXTS, CODE_MODEL  # 열쇠 없는 옛 실행(DVA1 앞) — 코드 값|            raise AiSettingMismatch(\"옛 실행\")|$FT/test_binding_156_settings.py
P20|3|$BN|        found = self.settings.get(company_id, setting_id)|        found = self.settings.applied(company_id)|$FT/test_binding_156_settings.py
R4|3|$BN|            max_output_tokens=model.max_output_tokens,\n|            max_output_tokens=colab_156.MAX_OUTPUT_TOKENS,\n|$FT/test_binding_156_settings.py"

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

case "$COMMIT" in 1) want=9 ;; 2) want=19 ;; 3) want=27 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
