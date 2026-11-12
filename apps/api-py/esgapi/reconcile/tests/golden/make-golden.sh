#!/usr/bin/env bash
# 골든의 TS 쪽 덤프를 만든다: esg-lab 의 규칙(TS)을 그대로 불러 네 보고서 + 지은 문서의 구획을 JSON 으로 낸다.
#   사용: apps/api-py/esgapi/reconcile/tests/golden/make-golden.sh [--input <폴더>] [--out <폴더>]
#     --input  문서마다 <문서>/document.json · char-places.json 이 든 폴더. 기본은 esg-lab 의 밴드 C1 산출(git 밖, pymupdf 엔진)
#     --out    덤프를 둘 폴더. 기본은 apps/api-py/.lab-golden/ts (git 밖)
#   esg-lab 의 자리는 환경 변수 ESG_LAB (꼭 준다).
# esg-lab 은 읽고 실행만 한다. 그 안에 파일을 두지 않는다(tsx 의 캐시는 OS 의 임시 폴더에 생긴다). 설치(pnpm install)도 하지 않는다.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
api_py="$(cd "$here/../../../.." && pwd)"
ESG_LAB="${ESG_LAB:?ESG_LAB=<esg-lab 저장소의 경로> 를 준다}"
export ESG_LAB
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
input="$ESG_LAB/out/band-C1/places"
out="$api_py/.lab-golden/ts"
while [ $# -gt 0 ]; do
  case "$1" in
    --input) input="$(cd "$2" && pwd)"; shift 2 ;;
    --out) mkdir -p "$2"; out="$(cd "$2" && pwd)"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
DOCS="kb_2025_kor kb_2025_databook_kor samsung_2026_kor cosmax_2025_kor"

[ -d "$ESG_LAB/ts/node_modules" ] || { echo "esg-lab 의 ts/node_modules 가 없다. 설치는 이 스크립트가 하지 않는다(감독에게 알린다)" >&2; exit 3; }
mkdir -p "$out"
tsx() { (cd "$ESG_LAB/ts" && pnpm -s -F reconcile exec tsx "$here/dump.mts" "$@"); }

for doc in $DOCS; do
  for file in document.json char-places.json; do
    [ -f "$input/$doc/$file" ] || { echo "입력이 없다: $input/$doc/$file (다시 만드는 법은 README.md)" >&2; exit 4; }
  done
  tsx --doc "$input/$doc/document.json" --places "$input/$doc/char-places.json" --id "$doc" > "$out/$doc.json"
  echo "TS 덤프  $doc  $(wc -c < "$out/$doc.json" | tr -d ' ') B"
done
tsx --doc "$here/synthetic/document.json" --places "$here/synthetic/char-places.json" --cases "$here/synthetic/cases.json" --id synthetic > "$out/synthetic.json"
echo "TS 덤프  synthetic  $(wc -c < "$out/synthetic.json" | tr -d ' ') B"
echo "esg-lab HEAD $(git -C "$ESG_LAB" rev-parse --short HEAD) · node $(node -v) · 유니코드 $(node -p process.versions.unicode)"
