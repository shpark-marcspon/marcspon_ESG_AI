#!/usr/bin/env bash
# 골든을 다시 만든다: esg-lab 의 TS 엔진(ts/ghg-calc 의 cli.ts calc)이 낸 JSON 을 그대로 받아 적는다.
#   사용: ESG_LAB=<esg-lab 저장소의 경로> esgapi/inventory/tests/data/golden/make-golden.sh [받아 적을 폴더]
#   받아 적을 폴더를 안 주면 이 폴더에 덮어쓴다. 다른 폴더를 주고 `diff -r` 로 견주면 골든이 그 명령의 출력인지 확인된다.
# esg-lab 의 파일은 고치지 않는다(읽고 실행만 한다). node 22 와 pnpm 이 PATH 에 있어야 한다.
# 계수·환산·GWP 표는 esg-lab 의 원본을 읽는다(패키지의 사본과 글자까지 같다: ../../../data/README.md 의 sha256).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${ESG_LAB:?ESG_LAB=<esg-lab 저장소의 경로> 를 준다}"
ESG_LAB="$(cd "$ESG_LAB" && pwd)"
OUT="$(mkdir -p "${1:-$HERE}" && cd "${1:-$HERE}" && pwd)"
DATA="$ESG_LAB/data/ghg-calc"
IN="$HERE/inputs"

echo "esg-lab HEAD: $(git -C "$ESG_LAB" rev-parse --short HEAD)  (골든을 만든 것은 f1b2c77)"
echo "esg-lab 의 고쳐진 파일 수: $(git -C "$ESG_LAB" status --porcelain | wc -l | tr -d ' ')"

# 입력(활동 데이터 파일)은 esg-lab 에서 옮겨 둔 사본에서 만든다.
python3 "$HERE/make_inputs.py"

SYNTHETIC=(--factors "$DATA/examples/factors.synthetic.json")
PACKAGE=(--factors "$DATA/unit-conversions.json" --factors "$DATA/gwp-sets.json" --factors "$DATA/factors.kr-ets-sample.json")
ALL=("${PACKAGE[@]}" "${SYNTHETIC[@]}")

calc() { # <골든 이름> <기대 종료 코드> <cli.ts calc 의 인자…>
  local name="$1" expected="$2" status=0
  shift 2
  (cd "$ESG_LAB/ts/ghg-calc" && pnpm tsx src/cli.ts calc "$@") > "$OUT/$name" || status=$?
  # 종료 코드: 0 전부 성공 / 1 실패한 행 있음 / 2 입력이나 사용법 오류
  [ "$status" = "$expected" ] || { echo "★ $name: 종료 코드 $status (기대 $expected)" >&2; exit 1; }
  echo "$name  exit=$status  $(wc -c < "$OUT/$name" | tr -d ' ') bytes"
}

# (가) esg-lab 의 예제 그대로
calc a-example.json 0 "$DATA/examples/activity.synthetic.json" "${SYNTHETIC[@]}"
# (나) 검산 사례 H01~H14, GWP 세트마다
for set in kr-ets-decree-annex2 ipcc-ar5-100y-kr-nid-2025 synthetic-gwp; do
  calc "b-handcalc.$set.json" 0 "$IN/handcalc.$set.activity.json" "${ALL[@]}"
done
# (나′) 패키지 자료만
calc b2-package-default.json 0 "$IN/package-default.activity.json" "${PACKAGE[@]}"
# (다) 순수 층 전용: 모르는 배출원 유형
calc c-unknown-source.json 1 "$IN/unknown-source.activity.json" "${SYNTHETIC[@]}"
# (라) 엔드포인트 전용: 계수가 없는 연료
calc d-failed-row.json 1 "$IN/failed-row.activity.json" "${SYNTHETIC[@]}"
# (마) 묶음의 순서
calc e-ordering.json 0 "$IN/ordering.activity.json" "${SYNTHETIC[@]}" --group-by orgUnit,period,scope,sourceType

# (바) 틀린 기준정보 표: 문제 목록은 표준 오류로 나오고 종료 코드는 2 다. 표준 출력은 비어 있어야 한다.
status=0
(cd "$ESG_LAB/ts/ghg-calc" && pnpm tsx src/cli.ts calc "$DATA/examples/activity.synthetic.json" --factors "$IN/invalid-tables.json") \
  > "$OUT/.stdout.tmp" 2> "$OUT/f-invalid-tables.stderr.txt" || status=$?
[ "$status" = 2 ] && [ ! -s "$OUT/.stdout.tmp" ] || { echo "★ f-invalid-tables: 종료 코드 $status" >&2; exit 1; }
rm -f "$OUT/.stdout.tmp"
echo "f-invalid-tables.stderr.txt  exit=$status  $(wc -l < "$OUT/f-invalid-tables.stderr.txt" | tr -d ' ') lines"
