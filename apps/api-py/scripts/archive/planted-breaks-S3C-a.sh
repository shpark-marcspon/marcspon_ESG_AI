#!/usr/bin/env bash
# S3C-a 의 심은 파손(발주서 §3 P1~P15·P6b, 경계 ② 검증 N1 의 P16): 엔진 판 colab_157 에 파손 하나를 심고, 그것을 물어야 할
#   시험(P1·P2 는 lint-imports 의 계약)이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S3C-a.sh --commit <2|3>
#   커밋 ② 는 그때 선 코드로 닿는 것만(P3·P7·P10·P14·P15). ③ 은 전부(P1~P16, P6b 는 셈 밖의 가려짐 줄).
# 심기 전의 파일을 임시 폴더에 베껴 두었다가 되돌린다(git 을 쓰지 않는다 — checkout·stash 0). 끝나면 작업 트리가 처음과 같아야 한다:
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1(scripts/planted-breaks.sh 의 꼴).
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 셈에서 빠진다(조용히 넘어가지 않는다).
# 줄마다  <id> <심은 것> → 빨강|초록 (<빨개진 시험 파일>)  을 낸다. 빨강 = 그 시험 파일의 pytest 종료 1(실패. 수집 실패 2 는 「죽음」).
#   계약 줄(P1·P2)의 빨강 = `lint-imports --contract <id>` 의 종료 1(그 계약 하나만 본다) — 「lint:<계약 id>」.
# 마지막 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>. ③ 은 그 앞에 GUARDED_P6B=green|red(가려짐 줄 — 셈 밖)와 FINGERPRINT=same|differs.
# 종료 0 은 「PLANTED 가 다 맞음 ∧ (③ 이면 P6b 초록) ∧ 지문이 같음」일 때뿐이다.
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 2|3) ;; *) echo "--commit 2 또는 3" >&2; exit 2 ;; esac

E=esgapi/inventory/engines/scope3/colab_157
T=esgapi/inventory/tests/engines/scope3/colab_157
I=esgapi/inventory/tests

backup="$(mktemp -d)"
touched=()
restore() {
  for f in "${touched[@]:-}"; do [ -n "$f" ] && cp "$backup/$(echo "$f" | tr / _)" "$f"; done
  touched=()
}
trap 'restore; rm -rf "$backup"' EXIT

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
fingerprint > "$backup/.fingerprint-before"

keep() { # <파일>
  cp "$1" "$backup/$(echo "$1" | tr / _)"; touched+=("$1")
}

replace_once() { # <파일> <옛 글자> <새 글자>   — 옛 글자가 정확히 한 번일 때만 바꾸고 0
  python3 -I - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}

append_lines() { # <파일> <글>
  printf '\n%s\n' "$2" >> "$1"
}

run_tests() { # <시험 파일…>  → 빨개진 파일을 , 로 이어 찍는다. 수집 실패(종료 2 이상)는 「죽음:<파일>」
  local red=() f code
  for f in "$@"; do
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -x "$f" > /dev/null 2>&1
    code=$?
    case "$code" in
      0) ;;
      1) red+=("$(basename "$f")") ;;
      *) red+=("죽음:$(basename "$f")") ;;
    esac
  done
  local IFS=,
  printf '%s' "${red[*]:-}"
}

run_lint() { # <계약 id>  → lint-imports 가 그 계약 하나만 볼 때 깨졌다고 하면(종료 1) 「lint:<id>」
  local code
  uv run --frozen lint-imports --contract "$1" > /dev/null 2>&1
  code=$?
  case "$code" in
    0) ;;
    1) printf 'lint:%s' "$1" ;;
    *) printf '죽음:lint' ;;
  esac
}

planted=0; expected=0; guarded=""
report() { # <id> <설명> <기대 빨강 파일(, 로)> <빨개진 것>
  local verdict="초록"
  [ -n "$4" ] && verdict="빨강"
  case "$4" in *죽음*) verdict="죽음" ;; esac
  local ok="다름"
  if [ "$verdict" = "빨강" ]; then
    ok="맞음"
    local want
    for want in ${3//,/ }; do
      case ",$4," in *",$want,"*) ;; *) ok="다름" ;; esac
    done
  fi
  planted=$((planted + 1))
  [ "$ok" = "맞음" ] && expected=$((expected + 1))
  printf '%s %s → %s (%s) %s\n' "$1" "$2" "$verdict" "${4:-없음}" "$ok"
}

plant_replace() { # <id> <설명> <파일> <옛> <새> <기대 빨강 파일(, 로)> <시험 파일…>
  local id="$1" what="$2" file="$3" old="$4" new="$5" want="$6"; shift 6
  keep "$file"
  if ! replace_once "$file" "$old" "$new"; then
    printf '%s %s → 못 심음(옛 글자가 한 번이 아니다)\n' "$id" "$what"; planted=$((planted + 1)); restore; return
  fi
  report "$id" "$what" "$want" "$(run_tests "$@")"
  restore
}

plant_append() { # <id> <설명> <파일> <글> <기대 빨강 파일(, 로)> <시험 파일…>
  local id="$1" what="$2" file="$3" lines="$4" want="$5"; shift 5
  keep "$file"
  append_lines "$file" "$lines"
  report "$id" "$what" "$want" "$(run_tests "$@")"
  restore
}

# ── 커밋 ② 부터 닿는 것 ──
plant_append P3 "frames.py 에 import io" "$E/frames.py" "import io  # 심은 파손 P3" \
  test_purity.py "$T/test_purity.py"

plant_replace P7 "match_sheet_processor 의 앞 4글자 겹침 줄을 지움" "$E/template.py" \
  "        if key in n or n.startswith(key[:4]):" "        if key in n:" \
  test_template.py "$T/test_template.py"

plant_replace P10 "frames.py 가 끝 빈 줄을 남김" "$E/frames.py" \
  "    data = data[: last_with_data + 1]" "    data = data[:]" \
  test_frames.py "$T/test_frames.py"

plant_append P14 "frames.py 에 pd.read_excel(data) 한 줄(import io 없이)" "$E/frames.py" \
  "def _planted_p14(data: bytes) -> object:  # 심은 파손 P14
    return pd.read_excel(data)" \
  test_purity.py "$T/test_purity.py"

# P15 는 S8(기본 문맥 경우)이 문다. S2 는 엔진 문맥(legacy_strings) 안에서만 견주므로 맨 astype(str) 도 2.x 값을 내 초록일 수
# 있다(경계 ① 검증 N2) — 그래서 기대 빨강에 S8 만 두고 S2 의 결과는 같은 줄에 찍는다.
plant_replace P15 "pdcompat.colab_str 본문을 s.astype(str) 로" "$E/pdcompat.py" \
  "    return pd.Series([str(value) for value in series], index=series.index, name=series.name, dtype=object)" \
  "    return series.astype(str)" \
  test_pdcompat.py "$T/test_pdcompat.py" "$T/test_frames.py"

if [ "$COMMIT" = "3" ]; then
  # ── 커밋 ③ 몫 ──
  keep "$E/purchase.py"
  append_lines "$E/purchase.py" "import esgapi.inventory.engines.scope3.llm_first_1.types  # 심은 파손 P1"
  report P1 "purchase.py 가 판 llm_first_1 을 import" "lint:inventory-scope3-versions-apart" \
    "$(run_lint inventory-scope3-versions-apart)"
  restore

  keep "$E/serialize.py"
  append_lines "$E/serialize.py" "from esgapi.inventory.contracts import shapes  # 심은 파손 P2"
  report P2 "serialize.py 가 계약 shapes 를 import" "lint:inventory-engine-not-contracts" \
    "$(run_lint inventory-engine-not-contracts)"
  restore

  plant_replace P4 "키워드 점수 80 + 길이 → 81 + 길이" "$E/purchase.py" \
    "                score += 80 + min(len(kn), 20)" "                score += 81 + min(len(kn), 20)" \
    test_purchase.py "$T/test_purchase.py"

  plant_replace P5 "구매_USEPA 원화 열을 보고연도 −1 로" "$E/factor_book.py" \
    "    krw_col = find_precomputed_krw_ef_col(raw, year)" "    krw_col = find_precomputed_krw_ef_col(raw, year - 1)" \
    test_factor_book.py "$T/test_factor_book.py"

  plant_replace P6 "후처리(_fix_result_c1_c2)의 배출량 / 1000.0 을 지움" "$E/purchase.py" \
    '        out["배출량(tCO2e)"] = out["배출량(kgCO2e)"] / 1000.0' '        out["배출량(tCO2e)"] = out["배출량(kgCO2e)"]' \
    test_purchase.py "$T/test_purchase.py"

  # P6b: 셈(calc_category1_2_detail)의 / 1000 을 지워도 후처리가 구매금액 × 계수 / 1000 으로 덮는다 — 초록이 기대(셈 밖).
  keep "$E/purchase.py"
  if replace_once "$E/purchase.py" \
    "    emission_t = (emission_kg / 1000.0) if emission_kg is not None else None" \
    "    emission_t = (emission_kg) if emission_kg is not None else None"; then
    p6b="$(run_tests "$T/test_purchase.py")"
    guarded="green"; [ -n "$p6b" ] && guarded="red"
    printf 'P6b 셈의 / 1000.0 을 지움(후처리가 덮어 가려짐) → %s (%s) 기대 초록\n' "$guarded" "${p6b:-없음}"
  else
    guarded="못 심음"; echo "P6b → 못 심음(옛 글자가 한 번이 아니다)"
  fi
  restore

  plant_replace P8 "not_yet_supported 갈래를 조용한 건너뜀으로" "$E/pipeline.py" \
    "            outcomes.append(NotYetSupportedSheet(sheet.name, processor))
            continue" "            continue" \
    test_pipeline.py "$T/test_pipeline.py"

  plant_replace P9 "LLM 그룹 이름 실패를 Unknown 대신 None 으로" "$E/purchase.py" \
    '        return "Unknown", outcome  # 코랩' '        return None, outcome  # 코랩' \
    test_purchase.py "$T/test_purchase.py"

  plant_replace P11 "LLM 그룹 이름을 지난 줄의 originSteps.group 을 rule 로" "$E/purchase.py" \
    '            return PurchaseGroup(key, llm_group, reason, family, category, "ai", "group_llm", llm)' \
    '            return PurchaseGroup(key, llm_group, reason, family, category, "rule", "group_llm", llm)' \
    test_purchase.py "$T/test_purchase.py"

  plant_replace P12 "고정 스키마에서 칸 하나(spendNote 의 required)를 지움" \
    "$I/data/flow-shapes/scope3.colab.result@1.schema.json" '        "spendNote",
' "" \
    test_flow_shapes.py "$I/test_flow_shapes.py"

  plant_replace P13 "DEFAULTS 의 Scope 3 기본을 코랩 흐름으로" esgapi/inventory/flows/registration.py \
    '"inventory.scope3": "scope3.llm-first@1"' '"inventory.scope3": "scope3.colab@157"' \
    test_flows.py "$I/test_flows.py"

  plant_replace P16 "pipeline.run 의 legacy_strings 감쌈을 지움(경계 ② 검증 N1)" "$E/pipeline.py" \
    "    with legacy_strings():
        return _run(" "    if True:
        return _run(" \
    test_purchase.py "$T/test_purchase.py"
fi

restore
fingerprint > "$backup/.fingerprint-after"
same="same"
if ! cmp -s "$backup/.fingerprint-before" "$backup/.fingerprint-after"; then
  same="differs"
  echo "작업 트리가 처음과 다르다:"
  diff "$backup/.fingerprint-before" "$backup/.fingerprint-after"
fi
[ -n "$guarded" ] && echo "GUARDED_P6B=$guarded"
echo "FINGERPRINT=$same"
echo "PLANTED=$expected/$planted"
[ "$COMMIT" = "3" ] && [ "$guarded" != "green" ] && exit 1
[ "$expected" -eq "$planted" ] && [ "$same" = "same" ] && exit 0
exit 1
