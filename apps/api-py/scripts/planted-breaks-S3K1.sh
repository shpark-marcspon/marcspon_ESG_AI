#!/usr/bin/env bash
# S3K1 의 심은 고장(발주서 band-handoffs/S3K1-order.md §3-5): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S3K1.sh --commit <1|2|3>
#   경계별 배치(누적): ① P1·P2·P4·P9·P12(5) · ② +P3·P5·P11(8) · ③ +P6·P7·P8·P10·P13~P20(20).
# 틀은 planted-breaks-K1b-2b.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
#   쓰지 않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
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
case "$COMMIT" in 1|2|3) ;; *) echo "--commit 1·2·3" >&2; exit 2 ;; esac

I=esgapi/inventory
B=$I/flows/binding_157.py
IT=$I/tests
TB=$IT/flows/test_binding_157.py
E2E=$IT/flows/test_binding_157_end_to_end.py
RA=$I/service/actions/scope3_runs.py
RP=$I/service/apis/scope3_runs.py
RT=$IT/service/apis/test_scope3_runs.py

backup="$(mktemp -d /private/tmp/s3k1-planted.XXXXXX)"
case "$backup" in /private/tmp/s3k1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 연도 위 끝(올해) 뺌 · P2 참거짓 통과(True == 1 은 1990 앞이라 아래 끝이 먼저 문다 — 둘을 함께 빼고 bool 칸만 본다) · P4 DEFAULTS 되돌림(llm-first) · P9 계수 책 없음을 통과시킴
#   · P12(표 밖 하나) Scope 3 carrier 등록 뺌 — 끼움 있는 모듈의 carrier 규칙(그린워싱 T7·core carriers 분모)
# ② P3 끼움 등록 뺌(422) · P5 OPERATOR_RUN_MODULES 에서 뺌 · P11 NoGeocoder 대신 「찾는」 지오코더 — 발주서의 「예외
#   지오코더」는 엔진이 코랩 `except: pass` 대로 삼켜 AI 직선거리와 같은 결과라 e2e 초록(단위 시험
#   test_adapters_read_the_book_through_the_port_with_no_geocoder 는 문다 — 검증 b5) → 찾으면 e2e 갈래가 geocode 로
# ③ P6 결과 경로 모듈 비교 뺌(보안 층 scope3_run_paths) · P7 company_of 대신 첫 회사 · P8 안 끝남 409 뺌 ·
#   P10 양식 바이트 끝 한 바이트 뒤집음(^1 — 끝 바이트가 0 이라 0 으로 바꾸면 그대로였다, 실측)
ROWS="P1|1|$B| or not YEAR_FIRST <= year <= today().year:| or not YEAR_FIRST <= year:|$TB
P2|1|$B| or isinstance(year, bool) or not YEAR_FIRST <= year <= today().year:| or not year <= today().year:|$TB::test_a_bad_year_is_rejected_by_key_name_only[bool]
P4|1|$I/flows/registration.py|\"inventory.scope3\": \"scope3.colab@157\"}|\"inventory.scope3\": \"scope3.llm-first@1\"}|$TB $IT/test_flows.py
P9|1|$B|        if isinstance(self.factor_book.read(), FileMissing):|        if False:|$TB
P12|1|$I/apps.py|        CARRIERS.register(\"inventory.scope3\", NO_ROWS)|        assert CARRIERS and NO_ROWS|$TB esgapi/greenwash/tests/service/actions/test_bundle_carrier.py::test_every_module_with_a_binding_has_a_carrier
P3|2|$I/apps.py|        BINDINGS.register(\n            FLOW_ID, Scope3ColabBinding(factor_book=scope3_files.FACTOR_BOOK, runs_enabled=scope3_runs_enabled)\n        )|        assert BINDINGS and Scope3ColabBinding and FLOW_ID and scope3_files|biz:$E2E
P5|2|esgapi/core/permissions.py|\"drafting\", \"inventory.scope3\"}|\"drafting\"}|biz:$E2E::test_the_operator_runs_scope3_in_the_work_company
P11|2|$B|factor_book=book, geocoder=NoGeocoder())|factor_book=book, geocoder=Finding())\nclass Finding:\n    def geocode(self, query: str) -> object:\n        from esgapi.inventory.engines.scope3.colab_157.ports import Coordinates\n        return Coordinates(37.0, 127.0 + len(query) / 100)|biz:$E2E::test_the_distance_sheet_takes_the_ai_straight_branch_with_no_geocoder
P6|3|$RA|    if run is None or run.module != MODULE:|    if run is None:|sec:tests/security/test_tenant_paths.py::test_a_scope3_run_path_hides_another_companys_run_and_other_modules
P7|3|$RP|    found = actions.run_result(company_id=company_of(principal), run_id=run_id)|    assert company_of(principal)\n    from esgapi.organization.models import Company\n    found = actions.run_result(company_id=Company.objects.order_by(\"pk\").first().pk, run_id=run_id)|biz:$RT::test_another_companys_view_and_a_missing_run_are_404
P8|3|$RA|    if run.status != \"done\":\n        return RunNotDone(run.status)\n||biz:$RT::test_a_run_not_done_is_409
P10|3|$RA|    return Unavailable() if isinstance(content, FileMissing) else content|    return Unavailable() if isinstance(content, FileMissing) else content[:-1] + bytes([content[-1] ^ 1])|biz:$RT::test_both_roles_download_the_packaged_template_with_three_headers
P13|3|$RA|    if run.status != \"done\":|    if run.status in (\"queued\", \"processing\"):|biz:$RT::test_a_failed_run_is_409_not_404
P14|3|$RA|    if not isinstance(body, dict):\n        return NotFound()\n||biz:$RT::test_a_done_run_without_a_colab_result_is_404
P15|3|$RA| if r.schema_version == RESULT_SHAPE||biz:$RT::test_a_done_run_without_a_colab_result_is_404
P16|3|esgapi/runs/service/selectors/runs.py|    row = _runs(company_id).filter(pk=run_id).first()\n    return None if row is None else run_of(row)|    row = RunRow.unscoped.filter(pk=run_id).first()\n    return None if row is None else run_of(row)|biz:$RT::test_a_queued_run_of_company_b_read_as_a_is_the_same_404_as_a_missing_id
P17|3|$B|        raise NotImplementedError(\"회사 꼬리표가 필요하다 — inputs_with 로 부른다\")|        return self.inputs_with(document, options, company_id=0, versions={})|$TB::test_inputs_without_a_company_are_refused
P18|3|$B|        if not self.runs_enabled():|        if False:|$TB::test_a_switched_off_binding_refuses_first_without_reading_the_book
P19|3|esgapi/config/env.py|.strip() or \"false\"\n    if scope3_runs_text|.strip() or \"true\"\n    if scope3_runs_text|esgapi/config/tests/test_env.py::test_scope3_runs_are_off_when_the_switch_is_absent_or_empty
P20|3|$I/apps.py|runs_enabled=scope3_runs_enabled)|runs_enabled=lambda: True)|biz:$E2E::test_a_switched_off_deployment_refuses_the_run_with_no_row"

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

case "$COMMIT" in 1) want=5 ;; 2) want=8 ;; 3) want=20 ;; esac  # 경계마다 더한다(②·③ 몫은 그 경계에서)
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
