#!/usr/bin/env bash
# 밴드 GE1b(MARC-TICK-581)의 심은 파손: 하나씩 심고, 이름으로 적어 둔 시험이 FAILED 줄에 있는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-GE1b.sh <경계 번호…>     예) planted-breaks-GE1b.sh 1
#         마지막 줄 PLANTED=<잡은 수>/<심은 수>
# DB 표시(db)가 붙은 줄은 compose(.env 의 Postgres)가 떠 있어야 한다(scripts/test-business.sh 로 돈다).
# 심기 전 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(git 0 — 죽어도 trap 이 되돌린다). 끝에서 파일 sha256 과
# `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 0번(심지 않음)으로 이름 적은 시험이 전부 초록인지 먼저 본다(처음부터 빨간 것을 「잡았다」고 세지 않게).
# 네트워크 0. bash 전용.
set -u
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."   # apps/api-py

G=esgapi/greenwash
ENGINE=$G/flows/engine_g1.py
PASSAGES=$G/engines/g1/passages.py
EVIDENCE=$G/engines/g1/evidence.py
SHAPES2=$G/contracts/result2_shapes.py
RUNS=esgapi/runs/service/actions/runs.py

T_FIX=$G/tests/flows/test_engine_g1_fixes.py
T_PAS=$G/tests/engines/g1/test_passages.py
T_EVI=$G/tests/engines/g1/test_evidence.py
T_R2=$G/tests/contracts/test_result2_shapes.py
T_RETRY=esgapi/runs/tests/service/apis/test_runs_retry.py

EXAMPLE_N=$G/tests/data/contract-examples/result2/result2-normal.json
BINDING=$G/flows/binding_g1.py
T_BIND=$G/tests/flows/test_binding_g1.py
T_DOC=$G/tests/flows/test_engine_g1_document.py
REGISTRATION=$G/flows/registration.py
APPS=$G/apps.py
ENV=esgapi/config/env.py
CHECKS=$G/service/actions/checks.py
PORT=$G/service/actions/engine_g1.py
T_REG=$G/tests/flows/test_registration.py
T_ENV=esgapi/config/tests/test_env.py
T_SEG=esgapi/runs/tests/test_executor_segments.py
T_RUNS=$G/tests/service/actions/test_engine_g1_runs.py
T_SWITCH=$G/tests/service/actions/test_engine_g1_switch.py
T_RES2=$G/tests/service/actions/test_engine_g1_result2.py
FILES=("$ENGINE" "$PASSAGES" "$EVIDENCE" "$SHAPES2" "$RUNS" "$EXAMPLE_N" "$BINDING" "$REGISTRATION" "$APPS" "$ENV" "$CHECKS" "$PORT")
keep="$(mktemp -d)"
log="$(mktemp -d)"
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

edit() { # <파일> <있던 글자> <바꿀 글자> [all]   all 이 없으면 글자가 정확히 한 번 있어야 한다(아니면 종료 3)
  python3 - "$1" "$2" "$3" "${4:-one}" <<'PY'
import sys
path, old, new, mode = sys.argv[1:5]
text = open(path, encoding="utf-8").read()
n = text.count(old)
if (mode == "one" and n != 1) or n == 0:
    sys.exit(f"심을 자리가 {n}곳이다: {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
pure() { PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run --frozen pytest -q -rfp -p no:cacheprovider -m "not django_db and not security" "$@"; }
db() { PYTHONPYCACHEPREFIX="$(mktemp -d)" scripts/test-business.sh -q -rfp -p no:cacheprovider "$@"; }

total=0; ok=0
# check <번호> <설명> <pure|db> <시험 파일> <빨개질 시험 이름>
check() {
  local n="$1" what="$2" layer="$3" file="$4" name="$5"
  total=$((total + 1))
  if [ "$layer" = db ]; then db "$file" > "$log/$n.test" 2>&1; else pure "$file" > "$log/$n.test" 2>&1; fi
  local code=$?
  if [ "$code" -ne 0 ] && grep -E "^(FAILED|ERROR) .*::$name" "$log/$n.test" >/dev/null; then
    ok=$((ok + 1)); echo "  [$n] 빨강 — $what ← $name"
  else
    echo "  [$n] 못 잡음(종료 $code) — $what ← $name"; grep -E "^(FAILED|ERROR)" "$log/$n.test" | head -3 | sed 's/^/      /'
  fi
  restore_files
}
plant() { edit "$@" || { echo "심지 못함 — 멈춘다" >&2; exit 3; }; }

boundary_1() {
  echo "── 경계 ① ──"
  echo "  [0] 심지 않음"
  pure "$T_FIX" "$T_PAS" "$T_EVI" "$T_R2" > "$log/0.pure" 2>&1 || { echo "0번 순수 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/0.pure"; exit 1; }
  db "$T_RETRY" > "$log/0.db" 2>&1 || { echo "0번 DB 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/0.db"; exit 1; }

  plant "$RUNS" '        versions = json.loads(json.dumps(versions, cls=field.encoder))' '        pass'
  check 1 "645-1 정규화 뺌" db "$T_RETRY" test_a_tuple_version_is_the_same_version_after_the_jsonb_round_trip

  plant "$PASSAGES" 'max(REPEAT_MIN_PAGES, REPEAT * page_count)' 'REPEAT * page_count'
  check 2 "642-1 문턱 하한 뺌" pure "$T_PAS" test_a_one_to_three_page_document_keeps_its_paragraphs

  plant "$EVIDENCE" '    if not index.passages:  # 642-1' '    if False:  # 642-1'
  check 3 "642-1 단락 0 의 부르기 0 뺌" pure "$T_EVI" test_no_passages_is_empty_without_a_call

  plant "$EVIDENCE" '        if not ps and vectors.size == 0:' '        if False:'
  check 4 "642-1 빈 index 를 그대로 Index 로" pure "$T_EVI" test_no_passages_is_empty_without_a_call

  plant "$ENGINE" '            return jd.JudgeReply(answer=None, failure=BUDGET_CODE)' '            return jd.JudgeReply(answer=None, failure="judge_failed")'
  check 5 "642-2 판정 상한을 judge_failed 로" pure "$T_FIX" test_a_judge_over_the_budget_is_budget_exceeded_not_judge_failed

  plant "$ENGINE" '    if isinstance(got, ev.Failed) and got.code == BUDGET_CODE:' '    if False:'
  check 6 "642-2 근거 찾기 상한을 evidence_search_failed 로" pure "$T_FIX" test_the_budget_name_survives_into_the_item

  plant "$ENGINE" '        over = items[-1]["errorCode"] == BUDGET_CODE' '        over = False'
  check 7 "642-2 구획 안 멈춤 뺌(남은 후보 부름)" pure "$T_FIX" test_the_budget_is_named_and_the_rest_of_the_segment_is_not_called

  plant "$SHAPES2" '    "budget_exceeded",
]' ']'
  check 8 "642-2 errorCode budget_exceeded 뺌" pure "$T_FIX" test_the_budget_is_named_and_the_rest_of_the_segment_is_not_called

  plant "$ENGINE" '    idx = ev.Index(built, vectors_of(carried))' '    idx = ev.Index(built, np.asarray(adapters.embedding.embed_documents([p.text for p in built.passages]), dtype=np.float32))'
  check 9 "642-3 이어 받기 벡터 옮김 끔(다시 임베딩)" pure "$T_FIX" test_a_resumed_judge_step_skips_the_done_segment_and_reads_the_carried_vectors

  plant "$ENGINE" '                "keySha256": e["keySha256"],
                "status": "done",' '                "keySha256": "0" * 64,
                "status": "done",'
  check 10 "D7 keySha256 다른 값" pure "$T_FIX" test_each_result_segment_carries_the_fanout_key_sha

  plant "$SHAPES2" 'GreenwashResult2Verdict' 'Verdict' all
  check 11 "D7 접두 하나 뺌" pure "$T_FIX" test_the_result2_components_are_prefixed_and_meet_no_result1_name

  plant "$SHAPES2" 'GreenwashResult2Verdict' 'Verdict' all
  check 12 "D7 접두 하나 뺌 → 고정 스키마" pure "$T_R2" test_the_json_schema_is_pinned_byte_for_byte

  plant "$ENGINE" '    if not all(isinstance(v, list | tuple) for v in given_parts.values()):' '    if False:'
  check 13 "642-7 parts 꼴 거절 뺌" pure "$T_FIX" test_parts_that_are_not_page_lists_are_refused_as_value_errors

  plant "$ENGINE" '        if texts
        else np.zeros((0, 0), dtype=np.float32)' '        if True
        else np.zeros((0, 0), dtype=np.float32)'
  check 14 "642-1 index 단락 0 에도 임베딩 부름(검증 1 P3 꼴)" pure "$T_FIX" test_a_document_with_no_passages_runs_to_done_without_embedding

  plant "$EXAMPLE_N" '"keySha256": "93c13dc54b3abb5bc93b0c8b5e77bf1a2b6f6a3b1c8842b868221a80c5bba55e"' '"keySha256": "8ddce6b6aa5ea2cd4a3b2e0e8c3b9f8c1e9a4b6f2d7c0a1e3f5b7d9c2e4a6a7a"'
  check 15 "D7 예시 keySha256 이 열쇠 sha 가 아님(검증 1 B1 꼴)" pure "$T_R2" test_the_examples_fit_and_start_with_schema_version
}

boundary_2() {
  echo "── 경계 ② ──"
  echo "  [0] 심지 않음"
  pure "$T_BIND" "$T_DOC" > "$log/0b.pure" 2>&1 || { echo "0번 ② 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/0b.pure"; exit 1; }

  plant "$BINDING" '        if not self.runs_enabled():' '        if False:'
  check 21 "D4 스위치 거짓을 받아 줌" pure "$T_BIND" test_the_switch_off_refuses_every_option_set_with_its_sentence

  plant "$BINDING" '    if any(options.get(k) is not None for k in NULL_ONLY):' '    if False:'
  check 22 "칸만 셋을 값째 받아 줌" pure "$T_BIND" test_unknown_keys_and_filled_null_only_fields_are_refused

  plant "$BINDING" '            "epoch": EPOCH,
' ''
  check 23 "판 열쇠 epoch 뺌" pure "$T_BIND" test_the_version_keys_are_fixed_and_stable

  plant "$BINDING" '        if made != now:' '        if False:'
  check 24 "돌 때 판 대조 끔" pure "$T_BIND" test_a_changed_key_is_a_versions_mismatch

  plant "$ENGINE" '    lines = inputs.criteria' '    lines = default_criterion_lines()'
  check 25 "③ 기준 줄 대신 기본 줄 박음" pure "$T_DOC" test_a_changed_criterion_line_changes_the_judge_request

  plant "$ENGINE" '        ck.category_in_list(judged.category, categories),' '        ck.category_in_list(judged.category, CATEGORIES),'
  check 26 "③ 카테고리 검사에 상수" pure "$T_DOC" test_categories_reach_the_prompt_and_the_category_check

  plant "$ENGINE" '        check_criteria(self.criteria, self.categories)' '        pass'
  check 27 "③ 칸 꼴 검사 뺌" pure "$T_DOC" test_the_third_layer_fields_refuse_bad_shapes

  plant "$ENGINE" '!= (data["sha256"], data["parserVersion"]):' '!= (ref.source_sha256, ref.parser.version):'
  check 28 "B3 산출물 sha 견줌 끔" pure "$T_DOC" test_a_changed_artifact_after_extract_is_a_named_failure

  plant "$ENGINE" '        raise G1DocumentFailed(got.code)' '        pass'
  check 29 "B3 거절·못 읽음을 이름 없이" pure "$T_DOC" test_a_refused_or_unreadable_document_fails_extract_and_reads_nothing_after
}

boundary_3() {
  echo "── 경계 ③ ──"
  echo "  [0] 심지 않음"
  pure "$T_REG" "$T_ENV" "$T_DOC" > "$log/30.pure" 2>&1 || { echo "0번 순수 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/30.pure"; exit 1; }
  db "$T_RUNS" "$T_SWITCH" "$T_SEG" > "$log/30.db" 2>&1 || { echo "0번 DB 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/30.db"; exit 1; }

  plant "$REGISTRATION" '{"greenwash": "greenwash.colab@E0"}' '{"greenwash": "greenwash.engine@G1"}'
  check 31 "T15 DEFAULTS → G1" pure "$T_REG" test_registration_into_a_fresh_registry

  plant "$REGISTRATION" ', engine_g1.g1_flow())' ')'
  check 32 "T15 전역 등록 뺌(펼침 흐름 집합)" db "$T_SEG" test_every_product_flow_is_barrier_only_but_the_g1_engine

  plant "$APPS" '                runs_enabled=g1_runs_enabled,' '                runs_enabled=lambda: True,'
  check 33 "T25 끼움 스위치를 늘 켬" db "$T_SWITCH" test_a_g1_run_is_refused_while_the_switch_is_off_and_e0_is_untouched

  plant "$ENV" 'env.get("GREENWASH_G1_RUNS_ENABLED", "").strip() or "false"' 'env.get("GREENWASH_G1_RUNS_ENABLED", "").strip() or "true"'
  check 34 "T25 env 기본 true" pure "$T_ENV" test_greenwash_g1_runs_are_off_when_the_switch_is_absent_or_empty

  plant "$CHECKS" ' if run.flow_id == colab.FLOW_ID)' ')'
  check 35 "T19 1차 목록 거름 뺌" db "$T_SWITCH" test_g1_runs_leave_the_first_engine_list_byte_for_byte

  plant "$CHECKS" ' if run.flow_id == colab.FLOW_ID)' ')'
  plant "$CHECKS" '        if run.document_id is None:  # 문서 없는' '        if run.document_id is None or run.flow_id != colab.FLOW_ID:  # 문서 없는'
  check 36 "T19 거름을 고리 안(:178)으로" db "$T_SWITCH" test_g1_runs_leave_the_first_engine_list_byte_for_byte

  plant "$PORT" '            layout=binding_g1.PARSER_LAYOUT,' '            layout=1,'
  check 37 "포트 산출물 판 1" db "$T_RUNS" test_a_g1_run_goes_from_post_to_a_stored_result2

  plant "$PORT" '        return "" if found is None else found.file_name' '        return ""'
  check 38 "포트 파일 이름 뺌" db "$T_RUNS" test_a_g1_run_goes_from_post_to_a_stored_result2

  plant "$PORT" 'artifact_id=ref.id, places=False' 'artifact_id=ref.id + 1, places=False'
  check 39 "포트 뷰가 다른 산출물" db "$T_RUNS" test_a_g1_run_goes_from_post_to_a_stored_result2

  plant "$ENGINE" '(ref.source_sha256, ref.parser.version) !=' '(ref.source_sha256, data["parserVersion"]) !='
  check 40 "B3 parserVersion 견줌 끔(검증 2 Q1)" pure "$T_DOC" test_a_changed_artifact_after_extract_is_a_named_failure
}

boundary_4() {
  echo "── 경계 ④ ──"
  echo "  [0] 심지 않음"
  pure "$T_RES2" > "$log/40.pure" 2>&1 || { echo "0번 순수 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/40.pure"; exit 1; }
  db "$T_RES2" > "$log/40.db" 2>&1 || { echo "0번 DB 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/40.db"; exit 1; }

  plant "$PORT" ' or run.flow_id != E.FLOW_ID:' ':'
  check 41 "T20 result2 흐름 거름 뺌(E0 실행 읽음)" db "$T_RES2" test_first_engine_foreign_missing_and_bodiless_runs_are_404

  plant "$PORT" '    return r2.RESULT2.dump_python(r2.RESULT2.validate_python(body), mode="json")' '    return body'
  check 42 "T20 다시 직렬화 뺌(jsonb 차례 그대로)" db "$T_RES2" test_a_done_g1_run_returns_its_stored_result_in_the_shape_order

  plant "$PORT" ' or run.module != MODULE' ''
  check 43 "⑤ result2 module 거름 뺌(다른 모듈의 G1 흐름 실행 읽음)" db "$T_RES2" test_first_engine_foreign_missing_and_bodiless_runs_are_404
}

for b in "$@"; do
  case "$b" in
    1) boundary_1 ;;
    2) boundary_2 ;;
    3) boundary_3 ;;
    4) boundary_4 ;;
    *) echo "모르는 경계: $b" >&2; exit 2 ;;
  esac
done

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! cmp -s "$keep/.sums-before" "$keep/.sums-after" || ! cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "되돌린 뒤 파일·상태가 처음과 다르다 — PLANTED 를 내지 않는다" >&2
  exit 1
fi
echo "로그: $log"
echo "PLANTED=$ok/$total"
[ "$ok" -eq "$total" ]
