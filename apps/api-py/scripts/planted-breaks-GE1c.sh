#!/usr/bin/env bash
# 밴드 GE1c(MARC-TICK-591)의 심은 파손: 하나씩 심고, 이름으로 적어 둔 시험이 FAILED 줄에 있는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-GE1c.sh <경계 번호…>     예) planted-breaks-GE1c.sh 1 4 5
#         마지막 줄 PLANTED=<잡은 수>/<심은 수>
# DB 표시(db)가 붙은 줄은 compose(.env 의 Postgres)가 떠 있어야 한다(scripts/test-business.sh 로 돈다).
# 심기 전 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(git 0 — 죽어도 trap 이 되돌린다). 끝에서 파일 sha256 과
# `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 0번(심지 않음)으로 이름 적은 시험이 전부 초록인지 먼저 본다(처음부터 빨간 것을 「잡았다」고 세지 않게).
# 네트워크 0. bash 전용. 틀은 planted-breaks-GE1b.sh 그대로.
set -u
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."   # apps/api-py

G=esgapi/greenwash
PASSAGES=$G/engines/g1/passages.py
EVIDENCE=$G/engines/g1/evidence.py
FLOW=$G/flows/engine_g1.py
BINDING=$G/flows/binding_g1.py
PORT=$G/service/actions/engine_g1.py

T_CH=$G/tests/engines/g1/test_passages_charts.py
T_PAS=$G/tests/engines/g1/test_passages.py
T_EVI=$G/tests/engines/g1/test_evidence.py
T_FCH=$G/tests/flows/test_engine_g1_charts.py
T_BIN=$G/tests/flows/test_binding_g1.py
T_DCH=$G/tests/service/actions/test_engine_g1_charts.py
FILES=("$PASSAGES" "$EVIDENCE" "$FLOW" "$BINDING" "$PORT")
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
  pure "$T_CH" "$T_PAS" "$T_EVI" > "$log/0.pure" 2>&1 || { echo "0번 순수 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/0.pure"; exit 1; }

  plant "$PASSAGES" '    if labels is not None:
        keep, chart_members' '    if True:
        keep, chart_members'
  check 1 "T1 라벨 없음에도 a 를 돎" pure "$T_CH" test_t1_no_labels_is_byte_identical_to_base

  plant "$PASSAGES" '(f" · {w.series}" if w.series else "")' '""'
  check 2 "T2 계열 뺌" pure "$T_CH" test_t2_chart_text_shape_kind_and_place

  plant "$PASSAGES" '        if u.id in chart_at:
            out.append(chart_at[u.id])
        if u.id not in gone:
            out.append(u)' '        if u.id not in gone:
            out.append(u)
        if u.id in chart_at:
            out.append(chart_at[u.id])'
  check 3 "T2 도표 자리를 첫 그릇 뒤로" pure "$T_CH" test_t2_chart_goes_right_before_its_first_container

  plant "$PASSAGES" 'CHART_EAT_CHARS: Final = 200' 'CHART_EAT_CHARS: Final = 2000'
  check 4 "T3 먹는 문턱 2000" pure "$T_CH" 'test_t3_eats_containers_up_to_200_chars_and_tables\[201-False\]'

  plant "$PASSAGES" '            k = table_block.get(k, k)' '            k = k'
  check 5 "T4 표 칸 그릇 → 표 블록 짝 끔" pure "$T_CH" test_t4_table_cell_container_maps_to_the_table_block

  plant "$PASSAGES" '    if labels is not None:
        keep, chart_members, a_stat = chart_units(keep, labels, table_block or {}, {u.id for u in units})
        stat.update(a_stat)
' ''
  plant "$PASSAGES" '    return res, dict(absorbed), stat, chart_members' '    if labels is not None:
        res, chart_members, a_stat = chart_units(res, labels, table_block or {}, {u.id for u in units})
        stat.update(a_stat)
    return res, dict(absorbed), stat, chart_members'
  check 6 "T5 a 를 c 뒤로" pure "$T_CH" test_t5_footnote_after_a_chart_attaches_to_the_chart

  plant "$PASSAGES" '        own = [b for m in p.members for b in chart_members.get(m, [m])]' '        own = list(p.members)'
  check 7 "T6 도표 id 를 members 에" pure "$T_CH" test_t6_chart_members_are_body_blocks_and_pass_fold_and_check

  plant "$PASSAGES" '        members[cid] = sorted(eat or conts, key=at.__getitem__)' '        members[cid] = sorted(eat, key=at.__getitem__)'
  check 8 "T6 먹은 것 0 의 그릇 대체 끔" pure "$T_CH" test_t6_a_chart_that_eats_nothing_keeps_all_its_containers

  plant "$PASSAGES" '    for w in labels.values():
        if not w.category:
            continue' '    for w in labels.words:  # type: ignore[attr-defined]
        if False:
            continue'
  check 9 "T7 values() 대신 words 전부" pure "$T_CH" test_t7_only_categorised_value_words_make_lines

  plant "$PASSAGES" '        chart_at[conts[0]] = Unit(cid, "table", first.page, first.section_id, text, rows)' '        chart_at.setdefault(conts[0], Unit(cid, "table", first.page, first.section_id, text, rows))'
  check 10 "T8 덮어쓰기를 앞 것 남김으로" pure "$T_CH" test_t8_two_charts_on_the_same_first_container_keep_the_last

  plant "$PASSAGES" '    stat["a 덮인 도표"] = built - len(chart_at)' '    stat["a 덮인 도표"] = 0'
  check 11 "T8 덮인 도표 셈 0 박음" pure "$T_CH" test_t8_two_charts_on_the_same_first_container_keep_the_last

  plant "$EVIDENCE" '    got = index.within_budget(order, budget)' '    got = index.within_budget(order)'
  check 12 "T9 예산 인자 무시" pure "$T_EVI" test_t9_budget_argument_bounds_the_evidence_chars

  plant "$PASSAGES" '        if w.chart not in title_of:' '        if False:'
  check 13 "어긋남: 없는 도표 낱말 건너뜀 끔" pure "$T_CH" test_a_word_of_an_unknown_chart_is_skipped_and_counted

  plant "$PASSAGES" '        elif sep and head not in known and head not in table_block:' '        elif False:'
  check 14 "어긋남: 블록 없는 표 셈 끔" pure "$T_CH" test_a_word_in_a_table_without_a_block_is_skipped_and_counted

  plant "$PASSAGES" '        elif not sep and head not in known:' '        elif False:'
  check 15 "어긋남: 없는 그릇 셈 끔" pure "$T_CH" test_a_word_in_an_unknown_container_is_skipped_and_counted

  plant "$PASSAGES" '        p.members = own + [a for m in p.members for a in absorbed.get(m, [])]' '        p.members = own'
  check 16 "T5 붙은 각주를 도표 구성에서 뺌" pure "$T_CH" test_t5_footnote_after_a_chart_attaches_to_the_chart

  plant "$PASSAGES" ' or keep[at[k]].kind == "table"]' ']'
  check 17 "검증 1 B1 표 그릇 먹음 뺌" pure "$T_CH" test_a_table_container_over_200_chars_is_still_eaten

  plant "$PASSAGES" '    title_of = {c.id: c.title or "" for c in labels.charts}' '    title_of = {c.id: c.title for c in labels.charts}'
  check 18 "검증 1 B2 제목 없음을 None 글로" pure "$T_CH" test_a_chart_without_a_title_starts_with_an_empty_title_line

  plant "$PASSAGES" '        members[cid] = sorted(eat or conts, key=at.__getitem__)' '        members[cid] = list(eat or conts)'
  check 19 "검증 1 R1 members 를 낱말 차례로" pure "$T_CH" test_chart_members_follow_reading_order_not_word_order
}

boundary_4() {
  echo "── 경계 ④ ──"
  echo "  [0] 심지 않음"
  pure "$T_FCH" "$T_EVI" "$T_BIN" > "$log/0.pure4" 2>&1 || { echo "0번 순수 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/0.pure4"; exit 1; }
  db "$T_DCH" > "$log/0.db4" 2>&1 || { echo "0번 DB 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/0.db4"; exit 1; }

  plant "$FLOW" '    except ChartLabelsUnavailable:
        return None, "unavailable"' '    except Exception:
        return None, "unavailable"'
  check 20 "T11 NotLoaded 삼킴" pure "$T_FCH" test_t11_a_view_without_labels_loaded_fails_extract_by_name

  plant "$FLOW" '    except ChartLabelsUnavailable:
        return None, "unavailable"' '    except ZeroDivisionError:
        return None, "unavailable"'
  check 21 "T11 Unavailable 을 실패로" pure "$T_FCH" test_t11_chart_label_states_all_run

  plant "$FLOW" '            "chartLabels": state,' '            "chartLabels": "used",'
  check 22 "T12 상태 글 고정" pure "$T_FCH" test_t12_without_labels_the_extract_stat_has_no_chart_keys

  plant "$FLOW" '    return build_passages(view, chart_labels=chart_labels_of(view)[0])' '    return build_passages(view, chart_labels=None)'
  check 23 "T12 뒤 단계가 라벨을 안 읽음" pure "$T_FCH" test_t12_extract_names_the_state_and_counts_the_chart_unit

  plant "$PORT" 'places=False, charts=True' 'places=False, charts=False'
  check 24 "T14 포트 charts=False" db "$T_DCH" test_t14_an_epoch_2_artifact_with_an_empty_label_field_is_unavailable_and_done

  plant "$EVIDENCE" 'BUDGET_CHARS: Final = 12000' 'BUDGET_CHARS: Final = 8000'
  check 25 "T15 예산 8000 으로" pure "$T_FCH" test_t15_the_frozen_budget_goes_to_every_evidence_search

  plant "$FLOW" '    if data.get("passagesSha256") != passages_sha256(built):' '    if False:'
  check 26 "M2 단락 sha 견줌 끔" pure "$T_FCH" test_m2_changed_passages_with_the_same_count_are_a_named_failure

  plant "$FLOW" '    if data.get("evidenceBudget") != ev.BUDGET_CHARS:' '    if False:'
  check 27 "M2 예산 견줌 끔" pure "$T_FCH" test_m2_a_changed_evidence_budget_is_a_named_failure

  plant "$FLOW" '    built = built_of(view)
    check_built(built, carried)' '    built = built_of(view)'
  check 28 "M2 구획의 견줌 뺌" pure "$T_FCH" test_m2_changed_passages_are_caught_by_a_judge_segment_too

  plant "$FLOW" 'json.dumps(rows, ensure_ascii=False)' 'json.dumps(len(rows))'
  check 29 "M2 sha 를 단락 수로" pure "$T_FCH" test_m2_changed_passages_with_the_same_count_are_a_named_failure

  plant "$BINDING" '            "engine": "G1",' '            "engine": "G1",
            "evidenceBudget": 12000,'
  check 30 "T18 판 열쇠에 열쇠 더함" pure "$T_BIN" test_the_version_keys_are_fixed_and_stable

  plant "$PORT" '    def view(self, ref: ArtifactRef) -> DocArtifactView:
        document_id = self._document_id()' '    def view(self, ref: ArtifactRef) -> DocArtifactView:
        self._document_id()
        document_id = self._document_id()'
  check 31 "T16 657 쿼리 하나 더" db "$T_DCH" test_t16_the_port_queries_of_one_segment_are_pinned_for_657

  plant "$EVIDENCE" '            if used > budget:
                break' '            if used > budget:
                used -= self.length[p]
                continue'
  check 32 "642-5 처분 break → 넘는 단락 건너뜀" pure "$T_EVI" test_a_first_passage_over_the_char_budget_leaves_the_evidence_empty
}

boundary_5() {
  echo "── 경계 ⑤ ──"
  echo "  [0] 심지 않음"
  pure "$T_FCH" > "$log/0.pure5" 2>&1 || { echo "0번 순수 시험이 빨갛다 — 멈춘다" >&2; tail -20 "$log/0.pure5"; exit 1; }

  plant "$FLOW" '    rows = [[p.text, p.members] for p in built.passages]' '    rows = sorted([p.text, p.members] for p in built.passages)'
  check 33 "⑤ 정렬한 해시(차례 안 묾)" pure "$T_FCH" test_m2_only_the_order_changed_changes_the_hash

  plant "$FLOW" '    rows = [[p.text, p.members] for p in built.passages]' '    rows = [[p.text] for p in built.passages]'
  check 34 "⑤ 해시에서 members 뺌" pure "$T_FCH" test_m2_only_the_members_changed_is_a_named_failure
}

for b in "$@"; do
  case "$b" in
    1) boundary_1 ;;
    4) boundary_4 ;;
    5) boundary_5 ;;
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
