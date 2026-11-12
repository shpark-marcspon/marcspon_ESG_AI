#!/usr/bin/env bash
# 밴드 DVE1 의 심은 파손(발주서 §3 이 정본 P1~P7 + 러너 P8): 하나씩 심고, 이름으로 적은 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-DVE1.sh --part <1|2>   1 = P1~P5·P8(커밋 1), 2 = P6·P7(커밋 2)
#   마지막 줄 PLANTED=<잡은 수>/<심은 수>
# 0번은 심지 않고 돌린다(겨냥한 시험이 전부 초록). 심기 전 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(git 을
# 쓰지 않는다. trap 도 되돌린다). 끝에서 sha256 과 `git status --porcelain` 이 처음과 같은지 본다 — 다르면 종료 1.
# 「잡음」: 시험이 0 이 아닌 코드로 끝나고 이름으로 적은 시험이 FAILED 줄에 있다. 「green:」 은 PASSED 줄에 있어야 한다.
# P6·P7 은 같은 심기를 BASE(568fb2cb)의 시험 파일로도 돌려 초록인 것을 적는다(N1 이 잡는 구멍). 공급사 호출 0.
set -u
cd "$(dirname "$0")/../../.."
PART="${2:-}"
case "${1:-}:$PART" in --part:1 | --part:2) ;; *) echo "사용: $0 --part <1|2>" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1
B=568fb2cb
A=apps/api-py
DV="$A/esgapi/dataverify"
DISPATCH="$DV/engines/colab_156/dispatch.py"
LOOP="$DV/engines/colab_156/loop.py"
FLOW="$DV/flows/colab_156.py"
SUMMARY="$A/esgapi/reconcile/calc/job_summary.py"
T_SUMMARY_PATH="$A/esgapi/reconcile/tests/test_job_summary.py"
T_DISPATCH=esgapi/dataverify/tests/engines/colab_156/test_dispatch.py
T_LOOP=esgapi/dataverify/tests/engines/colab_156/test_loop.py
T_FLOW=esgapi/dataverify/tests/flows/test_colab_156_soft_deadline.py
T_SUMMARY=esgapi/reconcile/tests/test_job_summary.py
N1=test_the_summary_rules_import_neither_celery_nor_django

keep="$(mktemp -d)"
log="${DVE1_OUT:-$(mktemp -d)}"
mkdir -p "$log"
FILES=("$DISPATCH" "$LOOP" "$FLOW" "$SUMMARY" "$T_SUMMARY_PATH")
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
edit() { # <파일> <있던 글자> <바꿀 글자>
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
tests() { (cd "$A" && PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run --frozen pytest -q -rfp -p no:cacheprovider -m "not django_db" "$@"); }
# <번호와 설명> <로그> <종료 코드> <red:이름|green:이름 …>
judge() {
  local name="$1" file="$2" code="$3" missed=0 want kind
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED|^ERROR' "$file" | sed 's/^/    /' | cut -c1-230 | head -8
  [ "$code" -ne 0 ] || missed=1
  for want in "$@"; do
    kind="${want%%:*}"; want="${want#*:}"
    case "$kind" in
      red) grep '^FAILED ' "$file" | grep -q -F "$want" || { missed=1; echo "    (FAILED 줄에 없다: $want)"; } ;;
      green) grep '^PASSED ' "$file" | grep -q -F "$want" || { missed=1; echo "    (PASSED 줄에 없다: $want)"; } ;;
    esac
  done
  if [ "$missed" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
# BASE 시험 파일로는 초록(못 잡음)인 것을 적는다 — 세지 않는다
base_green() { # <설명> <로그> <종료 코드>
  if [ "$3" = 0 ] && grep '^PASSED ' "$2" | grep -q -F "$N1"; then echo "    $1 → BASE 시험으로는 초록(구멍 확인)"; else echo "    $1 → ★ BASE 시험으로 초록이 아니다"; tail -8 "$2" | sed 's/^/    | /'; fi
  restore_files
}
zero() {
  if [ "$2" != 0 ] || tail -1 "$1" | grep -q -E 'failed|error'; then
    echo "0. 심지 않았는데 빨갛다 → ★ 멈춘다" >&2; tail -20 "$1" >&2; exit 1
  fi
  echo "0. 심지 않음 → 초록 ($(tail -1 "$1"))"
}

part1() {
  tests "$T_DISPATCH" "$T_LOOP" "$T_FLOW" > "$log/P0-1.txt" 2>&1; zero "$log/P0-1.txt" $?

  # P1. run_loop 이 실행기에 판별을 주입하지 않는다.
  edit "$FLOW" ', reraise=_soft_deadline'$'\n''    )' $'\n''    )' || exit 3
  tests "$T_FLOW" > "$log/P1.txt" 2>&1; code=$?
  judge "P1. run_loop 의 ToolRunner(reraise=) 를 뺌" "$log/P1.txt" "$code" \
    red:test_a_soft_limit_in_a_review_tool_leaves_the_flow_as_flow_step_failed \
    green:test_a_value_error_in_a_review_tool_is_still_a_runtime_error_check

  # P2. 기본 판별 never 가 참 → 기본값이 코랩 그대로가 아니다.
  edit "$DISPATCH" $'    """다시 던질지의 기본 판별 — 늘 거짓(코랩 그대로: 어떤 예외든 error dict)."""\n    return False' \
    $'    """다시 던질지의 기본 판별 — 늘 거짓(코랩 그대로: 어떤 예외든 error dict)."""\n    return True' || exit 3
  tests "$T_DISPATCH" > "$log/P2.txt" 2>&1; code=$?
  judge "P2. never 가 True" "$log/P2.txt" "$code" \
    red:test_weakness_1_sum_check_on_a_non_number_is_a_runtime_error \
    red:test_the_default_never_keeps_the_colab_runtime_error

  # P3. 분배기의 Exception 갈래에서 다시 던지기를 뺀다.
  edit "$DISPATCH" $'    except Exception as e:\n        if reraise(e):\n            raise\n' $'    except Exception as e:\n' || exit 3
  tests "$T_DISPATCH" "$T_LOOP" > "$log/P3.txt" 2>&1; code=$?
  judge "P3. dispatch 의 except Exception 머리 if reraise(e): raise 를 뺌" "$log/P3.txt" "$code" \
    red:test_an_injected_reraise_lets_the_tool_error_out_as_the_same_object \
    red:test_an_injected_reraise_lets_a_tool_error_out_of_the_runner

  # P4. 인자 읽기를 suppress 와 같은 꼴로(판별을 보지 않고 늘 삼킴).
  edit "$LOOP" $'        except Exception as error:\n            if self._reraise(error):\n                raise\n        if not parsed:' \
    $'        except Exception:\n            pass\n        if not parsed:' || exit 3
  tests "$T_LOOP" > "$log/P4.txt" 2>&1; code=$?
  judge "P4. ToolRunner 인자 읽기가 늘 삼킴(suppress 꼴)" "$log/P4.txt" "$code" \
    red:test_an_injected_reraise_lets_an_argument_read_error_out

  # P5. _plan 의 parse_hints 에 판별을 주입하지 않는다.
  edit "$FLOW" 'parse_hints(raw, reraise=_soft_deadline)' 'parse_hints(raw)' || exit 3
  tests "$T_FLOW" > "$log/P5.txt" 2>&1; code=$?
  judge "P5. _plan 의 parse_hints(reraise=) 를 뺌" "$log/P5.txt" "$code" \
    red:test_a_soft_limit_while_reading_hints_leaves_the_flow_at_plan \
    green:test_a_value_error_while_reading_hints_is_still_unparsable

  # P8(러너). 분배기의 TypeError 갈래에서 다시 던지기를 뺀다.
  edit "$DISPATCH" $'    except TypeError as te:\n        if reraise(te):\n            raise\n' $'    except TypeError as te:\n' || exit 3
  tests "$T_DISPATCH" > "$log/P8.txt" 2>&1; code=$?
  judge "P8. dispatch 의 except TypeError 머리 if reraise(te): raise 를 뺌" "$log/P8.txt" "$code" \
    red:test_an_injected_reraise_also_covers_the_type_error_branch
}

part2() {
  tests "$T_SUMMARY" > "$log/P0-2.txt" 2>&1; zero "$log/P0-2.txt" $?
  local anchor=$'from esgapi.reconcile.calc.types import DocModel, Extraction, PlaceIndex\n'
  # 함수 몸 안 import — ast.walk 가 보고, 시험이 job_summary 를 import 할 때 celery 를 싣지 않는다.
  local absolute=$'\n\ndef _planted() -> None:\n    from esgapi.config import celery  # noqa: F401\n'
  local relative=$'\n\ndef _planted() -> None:\n    from ...config import celery  # noqa: F401\n'

  # P6. 절대 꼴 from esgapi.config import celery
  edit "$SUMMARY" "$anchor" "$anchor$absolute" || exit 3
  tests "$T_SUMMARY" > "$log/P6.txt" 2>&1; code=$?
  judge "P6. job_summary.py 에 from esgapi.config import celery" "$log/P6.txt" "$code" "red:$N1"
  edit "$SUMMARY" "$anchor" "$anchor$absolute" || exit 3
  git show "$B:$T_SUMMARY_PATH" > "$T_SUMMARY_PATH"
  tests "$T_SUMMARY" -k "$N1" > "$log/P6-base.txt" 2>&1; code=$?
  base_green "P6 + BASE 시험" "$log/P6-base.txt" "$code"

  # P7. 상대 꼴 from ...config import celery
  edit "$SUMMARY" "$anchor" "$anchor$relative" || exit 3
  tests "$T_SUMMARY" > "$log/P7.txt" 2>&1; code=$?
  judge "P7. job_summary.py 에 from ...config import celery" "$log/P7.txt" "$code" "red:$N1"
  edit "$SUMMARY" "$anchor" "$anchor$relative" || exit 3
  git show "$B:$T_SUMMARY_PATH" > "$T_SUMMARY_PATH"
  tests "$T_SUMMARY" -k "$N1" > "$log/P7-base.txt" 2>&1; code=$?
  base_green "P7 + BASE 시험" "$log/P7-base.txt" "$code"
}

[ "$PART" = 1 ] && part1 || part2
restore_files
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! cmp -s "$keep/.sums-before" "$keep/.sums-after" || ! cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "★ 되돌린 뒤 파일·git status 가 처음과 다르다" >&2; exit 1
fi
echo "되돌림 확인: sha256·git status 처음과 같음 (로그 $log)"
echo "PLANTED=$ok/$total"
[ "$ok" = "$total" ]
