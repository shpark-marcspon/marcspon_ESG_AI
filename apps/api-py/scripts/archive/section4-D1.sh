#!/usr/bin/env bash
# 밴드 D1(MARC-TICK-102: pypdfium2 5.14.0 을 api-py 에 더한다. 코드는 0줄)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-D1.sh                  커밋 ① 뒤(이 스크립트는 아직 커밋 전)
#         apps/api-py/scripts/section4-D1.sh --after-commit   같은 것 + 커밋된 모습(작업 트리 0줄, 커밋, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 컨테이너 층은 돌리지 않는다(감독이 병합 뒤 main 전량). AI 공급사 호출 0. 네트워크는 uv·pnpm 의 설치뿐.
# bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 발주서 §4 의 여덟 밖에 더한 것: (나) 잠금 머리가 기준과 같음, (자) 잠금의 pypdfium2 블록이 services/parser 의
#   것과 같음(★5), (차) 잠금에 linux aarch64·x86_64 와 macOS arm64 휠이 있음(★4).
set -u
cd "$(dirname "$0")/../../.."
B=ee18aaa   # 기준 커밋(발주서: 워크트리를 만들 때의 main)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
case "$MODE" in "" | --after-commit) ;; *) echo "사용: $0 [--after-commit]" >&2; exit 2 ;; esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
A=apps/api-py
PY="$A/pyproject.toml"
LOCK="$A/uv.lock"
PLOCK=services/parser/uv.lock
export A PY LOCK PLOCK T B

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -x \
    -e 'apps/api-py/pyproject.toml' \
    -e 'apps/api-py/uv.lock' \
    -e 'apps/api-py/scripts/section4-D1.sh'
}

echo "── 밴드 D1 §4 · ${MODE:-커밋 ① 뒤} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

echo; echo "── 가. 잠금이 pyproject 와 맞음(이미지와 같은 uv 0.7.13 으로)"
run '(cd "$A" && uvx --from "uv==0.7.13" uv lock --check 2>&1 | tail -1; exit ${PIPESTATUS[0]})'

echo; echo "── 나. 잠금은 더하기만: 기준 대비 지운 version·name 줄 0, 더한 꾸러미 1, 지운 줄 0, 머리 같음"
run 'v="$(git diff -U0 "$B" -- "$LOCK" | grep -c -E "^-version")"; n="$(git diff -U0 "$B" -- "$LOCK" | grep -c -E "^-name")"; a="$(git diff -U0 "$B" -- "$LOCK" | grep -E "^\+name")"; echo "  -version $v · -name $n · +name: $a"; [ "$v" = 0 ] && [ "$n" = 0 ] && [ "$a" = "+name = \"pypdfium2\"" ]'
run 'git diff -U0 "$B" -- "$LOCK" | grep -E "^-[^-]" > "$T/lock-minus.txt"; cat "$T/lock-minus.txt"; echo "  지운 줄: $(wc -l < "$T/lock-minus.txt" | tr -d " ")"; test ! -s "$T/lock-minus.txt"'
# 잠금 머리(version·revision)가 기준과 같다: 이미지의 uv(docker/api-py.Dockerfile 의 0.7.13)가 쓰는 꼴. 호스트 uv 가 새 꼴로 다시 쓰면 빨강.
run 'git show "$B:$LOCK" | head -2 > "$T/head-base.txt"; head -2 "$LOCK" > "$T/head-now.txt"; sed "s/^/  /" "$T/head-now.txt"; cmp "$T/head-base.txt" "$T/head-now.txt"'

echo; echo "── 다. pyproject 의 그 줄이 pypdfium2==5.14.0, 그 밖에 지운 줄 0"
run 'grep -n -E "^[[:space:]]+\"pypdfium2==5\.14\.0\",([[:space:]]|$)" "$PY"'
run 'n="$(git diff -U0 "$B" -- "$PY" | grep -c -E "^-[^-]")"; echo "  pyproject 에서 지운 줄: $n"; [ "$n" = 0 ]'

echo; echo "── 라. 설치된 판이 5.14.0, pdfium 바이너리가 실제로 로드되어 PDF 의 쪽 수를 읽음"
run '(cd "$A" && uv run --frozen python -I -c "
import io
import importlib.metadata as m
import pypdfium2 as pdfium
print(\"  판\", m.version(\"pypdfium2\"), \"·\", pdfium.version.PYPDFIUM_INFO, \"· pdfium\", pdfium.version.PDFIUM_INFO)
assert m.version(\"pypdfium2\") == \"5.14.0\" and str(pdfium.version.PYPDFIUM_INFO) == \"5.14.0\"
new = pdfium.PdfDocument.new()
for _ in range(3):
    new.new_page(595, 842)
buf = io.BytesIO()
new.save(buf)
made = len(pdfium.PdfDocument(buf.getvalue()))
res = pdfium.PdfDocument(\"tests_integration/data/ruled-table.pdf\")
text = res[0].get_textpage().get_text_range()
print(\"  즉석 PDF 쪽\", made, \"· ruled-table.pdf 쪽\", len(res), \"· 첫 쪽 글자\", len(text))
assert made == 3 and len(res) >= 1 and text.strip()
")'

echo; echo "── 마. 빠른 게이트(뿌리에서)"
run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -6; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'

echo; echo "── 바. 휠"
run '"$A/scripts/check-wheel.sh" 2>&1 | tail -3; exit ${PIPESTATUS[0]}'

echo; echo "── 사. 경계: 허용 경로 밖 0, generated/ 가 기준과 같고 다시 뽑아도 같음"
run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
run 'git diff --quiet "$B" -- "$A/generated"'
run '(cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

echo; echo "── 자. 잠금의 pypdfium2 블록이 services/parser 의 것과 같음(판·sdist·휠 해시)"
run 'python3 -I -c "
import os, tomllib
def blk(p):
    with open(p, \"rb\") as f:
        return [x for x in tomllib.load(f)[\"package\"] if x[\"name\"] == \"pypdfium2\"][0]
a, b = blk(os.environ[\"LOCK\"]), blk(os.environ[\"PLOCK\"])
print(\"  판\", a[\"version\"], \"/\", b[\"version\"], \"· 휠\", len(a[\"wheels\"]), \"/\", len(b[\"wheels\"]), \"· 딸린 것\", a.get(\"dependencies\", []))
assert a == b and a[\"version\"] == \"5.14.0\" and not a.get(\"dependencies\")
"'

echo; echo "── 차. 잠금에 이미지(linux aarch64·x86_64)와 macOS arm64 휠이 있음(소스 빌드로 떨어지지 않음)"
run 'python3 -I -c "
import os, tomllib
with open(os.environ[\"LOCK\"], \"rb\") as f:
    p = [x for x in tomllib.load(f)[\"package\"] if x[\"name\"] == \"pypdfium2\"][0]
names = [w[\"url\"].rsplit(\"/\", 1)[1] for w in p[\"wheels\"]]
for tag in (\"manylinux_2_17_x86_64\", \"manylinux_2_17_aarch64\", \"macosx_13_0_arm64\"):
    hit = [n for n in names if tag in n]
    print(\" \", tag, hit)
    assert hit
"'

if [ "$MODE" = --after-commit ]; then
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 2'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-102" "Derives-from: MARC-TICK-74"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
fi

echo
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
