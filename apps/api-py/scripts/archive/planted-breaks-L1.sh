#!/usr/bin/env bash
# 밴드 L1(MARC-TICK-85)의 심은 파손 열셋(1~10 은 발주서 §3-2, 11~13 은 검증자의 권고 1~3 — 감독의 fix 지시): 하나씩 심고, 그것을 잡아야 하는 계약·테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-L1.sh        마지막 줄 PLANTED=<잡은 수>/13
# 0번은 심지 않고 돌린다: 새 테스트 셋과 층 테스트가 전부 초록, 순수 계약이 KEPT 여야 한다(처음부터 빨간 것을 「잡았다」고
# 세지 않게).
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준:
#   테스트  pytest 가 0 이 아닌 코드로 끝나고 **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#           (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다).
#   계약    (9번) lint-imports --config purity 가 0 이 아닌 코드로 끝나고 BROKEN 줄이 있다 — 테스트의 FAILED 와 같이 본다.
# 컨테이너 0, 네트워크 0(진짜 SDK 클라이언트를 짓는 테스트 #24 는 소켓 문지기 아래에서 돈다). 순수 층만 돈다. bash 전용이다.
set -u
export PYTHONDONTWRITEBYTECODE=1   # 심은 파일의 바이트코드를 남기지 않는다(되돌린 뒤 낡은 .pyc 를 읽지 않게)
cd "$(dirname "$0")/../../.."

A=apps/api-py
L="$A/esgapi/core/llm"
EMBEDDING="$L/embedding.py"
MOCK="$L/providers/mock.py"
OPENAI="$L/providers/openai.py"
PURITY="$L/purity.importlinter"
T_CFG=esgapi/core/tests/llm/test_config_embedding.py
T_EMB=esgapi/core/tests/llm/test_embedding.py
T_OAI=esgapi/core/tests/llm/providers/test_openai_embedding.py
T_LAYERS=esgapi/core/tests/test_llm_layers.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$EMBEDDING" "$MOCK" "$OPENAI" "$PURITY")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

total=0; ok=0
edit() { # <파일> <있던 글자> <바꿀 글자> [<있던 글자> <바꿀 글자> …]   글자마다 정확히 한 번 있어야 한다(아니면 종료 3)
  python3 - "$@" <<'PY'
import sys
path, pairs = sys.argv[1], sys.argv[2:]
text = open(path, encoding="utf-8").read()
for old, new in zip(pairs[::2], pairs[1::2]):
    if text.count(old) != 1:
        sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
    text = text.replace(old, new)
open(path, "w", encoding="utf-8").write(text)
PY
}
# 테스트 파일 여럿을 한 글자열로 받는다(빈칸으로 가른다).
pure_tests() { (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider -m "not django_db and not security" $1); }
purity() { (cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache --config esgapi/core/llm/purity.importlinter); }
# <번호와 설명> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 테스트 이름…>
judge() {
  local name="$1" file="$2" code="$3" caught=0 wanted
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED|BROKEN|^Contracts' "$file" | sed 's/^/    /' | cut -c1-200 | head -8
  [ "$code" -ne 0 ] || caught=1
  for wanted in "$@"; do
    grep -q "^FAILED .*$wanted" "$file" || { caught=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$caught" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
# <번호> <설명> <파일> <있던 글자> <바꿀 글자> <테스트 파일들> <FAILED 줄에 있어야 하는 테스트 이름…>
plant() {
  local number="$1" what="$2" file="$3" old="$4" new="$5" tests="$6" code
  shift 6
  edit "$file" "$old" "$new" || exit 3
  pure_tests "$tests" > "$log/$number.txt" 2>&1; code=$?
  judge "$number. $what" "$log/$number.txt" "$code" "$@"
}

# ── 0. 심지 않고: 전부 초록 ──
pure_tests "$T_CFG $T_EMB $T_OAI $T_LAYERS" > "$log/0.txt" 2>&1; code=$?
purity > "$log/0-purity.txt" 2>&1; pcode=$?
tail -1 "$log/0.txt" | sed 's/^/    /'; tail -1 "$log/0-purity.txt" | sed 's/^/    /'
if [ "$code" -ne 0 ] || tail -1 "$log/0.txt" | grep -q -E 'failed|error' || [ "$pcode" -ne 0 ]; then
  echo "0. 심지 않았는데 빨갛다 → ★ 멈춘다" >&2; tail -20 "$log/0.txt" "$log/0-purity.txt" >&2; exit 1
fi
echo "0. 심지 않고 → 전부 초록"

# ── 모의 벡터 ──
plant 1 "mock_vector 의 % dim → % (dim - 1)" "$MOCK" \
  '"big") % dim]' '"big") % (dim - 1)]' \
  "$T_EMB" test_mock_vectors_are_the_same_as_gw1

# ── 클라이언트 ──
plant 2 "묶음 크기를 요청의 batch_size 대신 늘 모델 값으로" "$EMBEDDING" \
  'size = cast("object", limit if request.batch_size is None else request.batch_size)' 'size = cast("object", limit)' \
  "$T_EMB" test_inputs_are_split_into_batches_in_order_with_one_record_per_batch test_batch_size_defaults_to_the_model_limit_and_is_checked
plant 3 "기록에 embedding_inputs= 를 빼먹음" "$EMBEDDING" \
  $'                        embedding_inputs=len(batch),\n' '' \
  "$T_EMB" test_inputs_are_split_into_batches_in_order_with_one_record_per_batch test_a_record_line_carries_the_embedding_fields_and_no_input_text
# 4번은 import 줄도 같이 고친다(RecordBody).
edit "$EMBEDDING" \
  'from esgapi.core.llm.log import MISSING, CallLogSink, CallRecord, Missing, sha256_json' \
  'from esgapi.core.llm.log import MISSING, CallLogSink, CallRecord, Missing, RecordBody, sha256_json' \
  '                        body=None,' \
  '                        body=RecordBody(request=provider_request.to_json(), response_text=None),' || exit 3
pure_tests "$T_EMB" > "$log/4.txt" 2>&1; code=$?
judge "4. 기록에 본문(입력 글자)을 싣는다" "$log/4.txt" "$code" test_a_record_line_carries_the_embedding_fields_and_no_input_text
plant 5 "모양 검사에서 차원 줄을 지운다" "$EMBEDDING" \
  $'    for vector in vectors:\n        if len(vector) != dimensions:\n            return f"임베딩 응답의 모양이 다르다: 차원 {len(vector)} != 설정 {dimensions}"\n' '' \
  "$T_EMB" 'test_a_wrongly_shaped_answer_is_a_provider_error_but_its_cost_is_kept\[dimension-255\]'
plant 6 "공급사 오류 뒤에도 다음 묶음을 부른다" "$EMBEDDING" \
  $'                return EmbedProviderFailed(\n                    status=response.status,' \
  $'                _ = EmbedProviderFailed(\n                    status=response.status,' \
  "$T_EMB" test_a_provider_error_stops_at_that_batch

# ── OpenAI 어댑터 ──
plant 7 "build_request 에서 encoding_format 을 뺀다" "$OPENAI" \
  ', "encoding_format": "float"}' '}' \
  "$T_OAI" test_the_request_asks_for_floats_and_does_not_send_dimensions
plant 8 "data 를 index 로 정렬하지 않는다" "$OPENAI" \
  'ordered = sorted(response.data, key=lambda item: item.index)' 'ordered = list(response.data)' \
  "$T_OAI" test_vectors_follow_the_index_and_tokens_and_model_come_from_the_answer

# ── 층 ──
edit "$EMBEDDING" $'\nimport math\n' $'\nimport django\nimport math\n' || exit 3
{ purity; echo "PURITY_EXIT=$?"; pure_tests "$T_LAYERS"; } > "$log/9.txt" 2>&1; code=$?
if ! grep -q "^PURITY_EXIT=[1-9]" "$log/9.txt" || ! grep -q "BROKEN" "$log/9.txt"; then
  echo "    (lint-imports --config purity 가 BROKEN 이 아니다)"; code=0
fi
judge "9. embedding.py 가 django 를 import" "$log/9.txt" "$code" test_only_setup_imports_django_inside_the_call_layer
plant 10 "purity.importlinter 에서 esgapi.core.llm.embedding 줄을 지운다" "$PURITY" \
  $'    esgapi.core.llm.embedding\n' '' \
  "$T_LAYERS" test_purity_contract_lists_every_module_of_the_call_layer

# ── 검증자의 권고(V1·V7·index) ──
plant 11 "embed_query 가 따로 부르고 실패면 [] (검증자 V1)" "$EMBEDDING" \
  '        return self.embed_documents([text])[0]' \
  $'        result = self._client.embed(EmbedRequest(inputs=(text,), route=self._route, tags=self._tags))\n        return list(result.vectors[0]) if isinstance(result, Embedded) else []' \
  "$T_EMB" test_the_client_port_raises_the_failure_branch
plant 12 "usage 가 없으면 토큰 0 을 지어낸다 (검증자 V7)" "$OPENAI" \
  'getattr(usage, "prompt_tokens", None)' 'getattr(usage, "prompt_tokens", 0)' \
  "$T_OAI" test_an_answer_without_usage_reports_no_tokens_and_is_recorded_without_cost
plant 13 "index 검사를 끈다" "$OPENAI" \
  'if indexes != list(range(len(ordered))):' 'if False:' \
  "$T_OAI" 'test_overlapping_or_missing_indexes_are_a_non_retryable_error\[indexes0\]' 'test_overlapping_or_missing_indexes_are_a_non_retryable_error\[indexes1\]'

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! cmp -s "$keep/.sums-before" "$keep/.sums-after" || ! cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "★ 되돌린 뒤의 파일이 처음과 다르다(sha256 이나 git status)" >&2
  diff "$keep/.sums-before" "$keep/.sums-after" >&2
  exit 1
fi
echo "되돌림 확인: sha256 $(wc -l < "$keep/.sums-after" | tr -d ' ')개 같음 · git status 같음"
echo "PLANTED=$ok/$total"
[ "$ok" -eq 13 ] && [ "$total" -eq 13 ]
