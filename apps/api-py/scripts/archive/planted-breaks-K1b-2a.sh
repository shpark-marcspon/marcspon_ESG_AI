#!/usr/bin/env bash
# K1b-2a 의 심은 고장(발주서 band-handoffs/K1b-2a-order.md §3-8): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K1b-2a.sh --commit <1|2|3|4>
#   경계별 배치: ① P1~P5(5) · ② P6~P13(누적 13 — 검증 ② B1·B2 로 둘 더함) · ③ 셋(누적 16) · ④ 셋(누적 19).
#   발주서 §3-8 의 P12~P17 은 여기서 P14~P19 다(번호가 둘 밀림).
# 틀은 planted-breaks-IR4.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(둘 다 이 워크트리의 compose postgres 가 떠 있어야 한다).
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
case "$COMMIT" in 1|2|3|4) ;; *) echo "--commit 1·2·3·4" >&2; exit 2 ;; esac

I=esgapi/inventory
MG=$I/migrations
IT=$I/tests
U=$I/service/utils/ghg_pool.py
SV=$I/service/services/ghg_pool.py
SE=$I/service/selectors/ghg_pool.py
AC=$I/service/actions/ghg_pool.py

backup="$(mktemp -d /private/tmp/k1b2a-planted.XXXXXX)"
case "$backup" in /private/tmp/k1b2a-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈, § 로 여러 자리)
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
# ① P1 ghg_nodes_root_is_scope 뺌(늘 참으로) · P2 기본 하나 부분 unique 의 deleted_at IS NULL 뺌 · P3 판·가스 grant 에 UPDATE
#   · P4 default_factor_unit 이 켬·끔을 바꿈 · P5 켠 가스 GWP 0 허용
# ② P6 단 규칙 검사 뺌 · P7 고치기가 옛 판을 UPDATE(새 판 넣기 앞에 옛 판들의 이름을 고침) · P8 기본 승계 뺌
#   · P9 nodes_in_use 안 부름 · P10 잎 지움이 계수를 안 지움 · P11 create_factor 의 @transaction.atomic 뺌(둘째 services
#   부름 insert_factor_version 에 심은 실패 — 감독 보정) · P12 잎을 부모로 잎을 받음(검증 ② B2) · P13 lock_nodes 의
#   FOR UPDATE 뺌(같은 잎 첫 계수 둘 → 23505, 검증 ② B1)
# ③ P14 열둘 중 하나(factors_get)를 COMPANY 로 · P15 test_tenant_paths 표에서 새 경로 하나(ghg-options) 뺌
#   · P16 응답 Decimal 을 float 로(1E-12 꼴 지수 표기가 나간다)
# ④ P17 씨앗이 노드의 seed_key 를 안 봄(두 번 → 다시 만들려다 거절) · P18 씨앗 GWP 를 다른 세트에서 · P19 묶음 분모가
#   달라도 넣음
ROWS="P1|1|$MG/0001_ghg_pool.py|models.Q((\"level\", \"scope\"), (\"parent__isnull\", True)),|models.Q((\"level\", \"scope\")), models.Q((\"level\", \"activity\")),|biz:$IT/test_models.py
P2|1|$MG/0001_ghg_pool.py|condition=models.Q((\"deleted_at__isnull\", True), (\"is_default\", True)),|condition=models.Q((\"is_default\", True)),|biz:$IT/test_models.py
P3|1|$MG/0001_ghg_pool.py|grant('\"ghg_factor_versions\", \"ghg_factor_gases\"', \"SELECT, INSERT\"),|grant('\"ghg_factor_versions\", \"ghg_factor_gases\"', \"SELECT, INSERT, UPDATE\"),|sec:tests/security/test_owner.py
P4|1|$U|    return \"kg/TJ\" if ncv_enabled else f\"kg/{input_unit}\"|    return f\"kg/{input_unit}\" if ncv_enabled else \"kg/TJ\"|$IT/service/utils/test_ghg_pool.py
P5|1|$U|            if gwp is None or gwp <= 0:|            if gwp is None or gwp < 0:|$IT/service/utils/test_ghg_pool.py
P6|2|$SV|                if parent.level != want_parent:\n                    return Invalid({\"parentId\": f\"{level} 은 {want_parent} 아래에 만든다\"})\n||biz:$IT/service/services/test_ghg_pool.py
P7|2|$SV|        row = GhgFactorVersion.objects.create(|        GhgFactorVersion.objects.filter(factor_id=factor_id).update(name=values.name)\n        row = GhgFactorVersion.objects.create(|biz:$IT/service/actions/test_ghg_pool.py
P8|2|$AC|    for heir in _first_alive_per_node(orphaned):|    for heir in _first_alive_per_node(set()):|biz:$IT/service/actions/test_ghg_pool.py
P9|2|$AC|    used = nodes_in_use(wanted)|    used: frozenset[int] = frozenset()|biz:$IT/service/actions/test_ghg_pool.py
P10|2|$AC|    factors = [factor.id for factor in selectors.alive_factors_of(leaves)]|    factors: list[int] = []|biz:$IT/service/actions/test_ghg_pool.py
P11|2|$AC|@transaction.atomic\ndef create_factor(|def create_factor(|biz:$IT/service/actions/test_ghg_pool.py
P12|2|$AC|    if parent.level != \"activity\":|    if parent.level not in (\"activity\", \"facility\"):|biz:$IT/service/actions/test_ghg_pool.py
P13|2|$SE|    rows = _alive_nodes().select_for_update().filter(pk__in=sorted(ids)).order_by(\"id\")|    rows = _alive_nodes().filter(pk__in=sorted(ids)).order_by(\"id\")|biz:$IT/service/actions/test_ghg_pool_race.py
P14|3|esgapi/core/permissions.py|    \"inventory_admin_ghg_factors_get\": OPERATOR,|    \"inventory_admin_ghg_factors_get\": COMPANY,|esgapi/core/tests/test_permissions.py::test_the_table_is_these_needs esgapi/core/tests/test_permissions.py::test_a_customer_is_refused_every_operator_cell
P15|3|tests/security/test_tenant_paths.py|    (\"GET\", \"/inventory/admin/ghg-options\"): \"bearer\",\n||sec:tests/security/test_tenant_paths.py::test_every_operation_is_in_the_table
P16|3|$I/service/apis/ghg_pool.py|        ncv=None if found.ncv is None else decimal_text(found.ncv),|        ncv=None if found.ncv is None else str(float(found.ncv)),|biz:$IT/service/apis/test_ghg_pool.py
P17|4|$AC|    if key in known:\n        report.existing[\"node\"] += 1\n        return known[key]\n||biz:$IT/service/actions/test_ghg_pool_seed.py
P18|4|$AC|    gwp = gwp_values(gwp_set_id)|    gwp = gwp_values(\"ipcc-ar5-100y-kr-nid-2025\")|biz:$IT/service/actions/test_ghg_pool_seed.py
P19|4|$U|    if len(denominators) != 1:|    if False:|$IT/service/utils/test_ghg_pool_seed.py"

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
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 전량 verify 와 겹치지 않는다
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
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

case "$COMMIT" in 1) want=5 ;; 2) want=13 ;; 3) want=16 ;; 4) want=19 ;; esac  # ②③④ 는 그 경계에서 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
