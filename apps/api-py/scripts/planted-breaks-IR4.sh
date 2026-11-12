#!/usr/bin/env bash
# IR4 의 심은 파손(발주서 부록 §3-6): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-IR4.sh --commit <1|2|3>
#   경계별 배치: ① P1~P7 + 러너 몫 R1·R2(9) · ② P8~P15 + 러너 몫 R3·R4(누적 19) · ③ P16~P23 + 러너 몫 R5(누적 28).
# 틀은 planted-breaks-DVA1.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
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

M=esgapi/materiality
EN=$M/engines/colab_155
F=$M/flows
T=$M/tests
ET=$T/engines/colab_155
FT=$T/flows
PM=$F/prompt_model_155.py
SV=$M/service/services/ai_settings.py
SL=$M/service/selectors/ai_settings.py
ST=$T/service/services
AT=$T/service/apis
BN=$F/binding_155.py

backup="$(mktemp -d /private/tmp/ir4-planted.XXXXXX)"
case "$backup" in /private/tmp/ir4-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 render 를 순차 .replace · P2 render_raw 가 dedent 를 빠뜨림 · P3 render_raw 가 dedent 를 끼우기 앞에 · P4 규제
#   system 이 sector 반대 판 칸 · P5 part1_inputs 가 texts 를 빠뜨림(기본 글로) · P6 2부 요청에 temperature 를 실음
#   · P7 estimate_part2 가 texts 무시 · R1(러너) 결과 settings.temperature 가 상수 · R2(러너) 결과 part2.maxOutputTokens 가
#   상수
# ② P8 자리 검사 지움 · P9 {신뢰 출처 목록} 지킴 빠짐 · P10 메모 strip 빠짐(받은 글 그대로 저장) · P11 기본 글이면 NULL 로
#   접음 · P12 판 읽기 회사 조건 빠짐 · P13 analysis temperature 값 받음 · P14 research temperature null 받음 · P15
#   prompt-model 이 저장 메모 대신 DEFAULT_MEMOS · R3(러너, 업무 층) services.unusable 이 글 다시 받기를 건너뜀 · R4(러너,
#   보안 층) 칸 단위 UPDATE 를 표 단위로
# ③ P16 기본 판에 promptsSha256 · P17 글 sha 대조 지움 · P18 열쇠⇔글 검사를 모델 대조 뒤로 · P19 실행기 판 조회에 회사
#   조건 빠짐(첫 회사) · P20 inputs_with 가 늘 코드 값 · P21 옛 실행을 mismatch · P22 inputs_with 가 get 대신 applied
#   · P23 만들 때(versions_with) 저장 글 다시 받기를 건너뜀(services 쪽은 ② R3) · R5(러너) 판의 analysis 칸을 흐름에
#   넘기지 않음(코드 값)
ROWS="P1|1|$EN/prompts.py|    return pattern.sub(lambda match: values[match.group(0)], template)|    for slot, value in values.items():\n        template = template.replace(slot, value)\n    return template|$ET/test_texts.py
P2|1|$EN/prompts.py|    return dedent(render(template, values))|    return render(template, values)|$ET/test_texts.py
P3|1|$EN/prompts.py|    return dedent(render(template, values))|    return render(dedent(template), values)|$ET/test_texts.py
P4|1|$F/colab_155.py|{prompts.WHITELIST_SLOT: whitelist_text(texts, name)}|{prompts.WHITELIST_SLOT: whitelist_text(texts, \"cell71\" if name == \"cell73\" else \"cell73\")}|$FT/test_iro_155_texts.py
P5|1|$F/iro_155.py|        route=inputs.research.route,\n        texts=inputs.texts,|        route=inputs.research.route,\n        texts=colab_155.DEFAULT_TEXTS,|$FT/test_iro_155_texts.py
P6|1|$F/part2_155.py|        max_output_tokens=inputs.max_output_tokens,\n        timeout_ms=TIMEOUT_MS_PART2,\n    )|        max_output_tokens=inputs.max_output_tokens,\n        timeout_ms=TIMEOUT_MS_PART2,\n        temperature=0.1,\n    )|$FT/test_iro_155_texts.py $FT/test_part2_155.py
P7|1|$F/part2_155.py|    planned = _planned(\"impact\", impact_messages(part2_input, texts=inputs.texts))|    planned = _planned(\"impact\", impact_messages(part2_input, texts=replace(inputs.texts, impact_system=part2_prompts.IMPACT_SYSTEM, impact_input=part2_prompts.IMPACT_USER_RAW)))|$FT/test_iro_155_texts.py
R1|1|$F/colab_155.py|        \"temperature\": repr(inputs.temperature),|        \"temperature\": repr(constants.TEMPERATURE),|$FT/test_iro_155_texts.py
R2|1|$F/part2_155.py|        \"maxOutputTokens\": max_output_tokens,|        \"maxOutputTokens\": MAX_OUTPUT_TOKENS_PART2,|$FT/test_iro_155_texts.py
P8|2|$PM|            if missing:\n                return PromptRefused(|            if False:\n                return PromptRefused(|$FT/test_prompt_model_155.py
P9|2|$EN/texts.py|    \"regulation_system\": (p1.WHITELIST_SLOT,),\n    **{key: PLACEHOLDERS[key]|    **{key: PLACEHOLDERS[key]|$FT/test_prompt_model_155.py
P10|2|$SV|    stored_prompts = None if texts is None else prompts_input(texts)|    stored_prompts = prompts|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
P11|2|$SV|    stored_prompts = None if texts is None else prompts_input(texts)|    stored_prompts = (\n        None\n        if texts is None or prompt_model_155.texts_from(texts) == prompt_model_155.texts_from(None)\n        else prompts_input(texts)\n    )|biz:$ST/test_ai_settings.py $AT/test_ai_settings.py
P12|2|$SL|    row = MaterialityAiSettingRow.for_company(company_id).filter(id=setting_id).first()\n    return SettingMissing()|    row = MaterialityAiSettingRow.unscoped.filter(id=setting_id).first()\n    return SettingMissing()|biz:$AT/test_ai_settings.py $ST/test_ai_settings.py
P13|2|$PM|        if step.key == ANALYSIS and step.temperature is not None:|        if False:|$FT/test_prompt_model_155.py
P14|2|$PM|        if step.key == RESEARCH and step.temperature is None:|        if False:|$FT/test_prompt_model_155.py
P15|2|$PM|memo=DEFAULT_MEMOS[key] if found is None else found.memo,|memo=DEFAULT_MEMOS[key],|biz:$AT/test_ai_settings.py
R3|2|$SV|    texts = None if found.prompts is None else prompt_model_155.accept_prompts(found.prompts)|    texts = None|biz:$ST/test_ai_settings.py
R4|2|$M/migrations/0001_ai_settings.py|grant(f'\"{TABLE}\"', \"UPDATE (applied, applied_at)\")|grant(f'\"{TABLE}\"', \"UPDATE\")|sec:tests/security/test_owner.py tests/security/test_materiality_ai_settings.py
P16|3|$BN|            common = ai_versions(setting_id=None, model=self._defaults(), prompts=None)\n            return|            common = ai_versions(setting_id=None, model=self._defaults(), prompts=None)\n            common = {**common, \"promptsSha256\": \"\"}\n            return|$FT/test_binding_155_settings.py
P17|3|$BN|        if prompts_sha256(texts) != versions.get(\"promptsSha256\"):|        if False:|$FT/test_binding_155_settings.py
P18|3|$BN|        if (found.prompts is not None) != checks_prompts:  # 다른 대조보다 먼저\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n§        texts = None if found.prompts is None else self._saved_texts(|§        if (found.prompts is not None) != checks_prompts:\n            raise AiSettingMismatch(f\"AI 설정 판 {setting_id} 의 저장 프롬프트 글 유무가 실행을 만들 때와 다르다\")\n        texts = None if found.prompts is None else self._saved_texts(|$FT/test_binding_155_settings.py
P19|3|$SL|        row = MaterialityAiSettingRow.for_company(company_id).filter(id=setting_id).first()\n        return SettingNotFound(setting_id)|        row = MaterialityAiSettingRow.unscoped.filter(id=setting_id).first()\n        return SettingNotFound(setting_id)|biz:$FT/test_runs_materiality_settings.py
P20|3|$BN|        return pm.texts_from(texts), pm.models_from(model)|        return DEFAULT_TEXTS, CODE_MODELS|$FT/test_binding_155_settings.py
P21|3|$BN|            return DEFAULT_TEXTS, CODE_MODELS  # 열쇠 없는 옛 실행(IR4 앞) — 코드 값|            raise AiSettingMismatch(\"옛 실행\")|$FT/test_binding_155_settings.py
P22|3|$BN|        found = self.settings.get(company_id, setting_id)|        found = self.settings.applied(company_id)|$FT/test_binding_155_settings.py
P23|3|$BN|        texts = None if applied.prompts is None else pm.accept_prompts(applied.prompts)|        texts = None|$FT/test_binding_155_settings.py
R5|3|$BN|        research, analysis = models|        research, analysis = models[0], CODE_MODELS[1]|$FT/test_binding_155_settings.py"

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

case "$COMMIT" in 1) want=9 ;; 2) want=19 ;; 3) want=28 ;; esac  # ②③ 은 그 경계에서 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
