#!/usr/bin/env bash
# TR3b 의 심은 파손(발주서 §3-5, 1~19 + 15b·15c + 12b = 22): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-TR3b.sh --commit <1|2|3>
#   경계별 배치: ① 1~5(5 — runs selector) · ② + 6~13·12b·16~19(18 — 목록·하나 보기) · ③ + 14·15·15b·15c(22 — zip).
#   12 는 ★D 로 뜻이 바뀜(「step_lines_of 를 앞 회차까지 부름」 — 감독 65 허락), 12b 는 3-2-7 처분 (가)(runs_of 를 끊지
#   않고 통째 부름 — 감독 65 조건 ⓓ).
# 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지 않는다 — checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 옛 글·새 글에 「§」가 있으면 그것으로 나눈 짝마다 바꾼다(한 파손이 여러 자리를 바꾸는 것).
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층
#   (scripts/test-business.sh — 이 워크트리의 compose postgres 가 떠 있어야 한다), 「sec:」로 시작하면 보안 층
#   (scripts/test-security.sh — 같은 postgres).
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

TR=esgapi/translation
T=$TR/tests

backup="$(mktemp -d /private/tmp/tr3b-planted.XXXXXX)"
case "$backup" in /private/tmp/tr3b-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈. 새 글이 「@rm」이면 파일을 지운다)
  if [ "$3" = "@rm" ]; then rm "$1"; return 0; fi
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
S=esgapi/runs/service/selectors/runs.py
ST=esgapi/runs/tests/service/selectors/test_runs.py
B=$TR/service/actions/batches.py
AR=$TR/service/actions/archive.py
ROWS="1|1|$S|    rows = _runs(company_id).filter(module=module)|    rows = RunRow.unscoped.filter(module=module)|biz:$ST
2|1|$S|        \"created_by_user_id\",\n        batch_key=|        \"created_by_user_id\",\n        \"options\",\n        batch_key=|biz:$ST
3|1|$S|    return Coalesce(wrapped, KeyTextTransform(key, \"options\"))|    return Coalesce(wrapped, wrapped)|biz:$ST
4|1|$S|\"total\", \"started_at\", \"finished_at\")|\"total\", \"started_at\", \"finished_at\", \"data\")|biz:$ST
5|1|$S|    if schema_versions is not None:|    if False:|biz:$ST
6|2|$B|run_ids=done, schema_versions={DIGEST_SHAPE})|run_ids=done)|biz:$T/service/actions/test_batches.py
7|2|$B|groups.setdefault((key.document_id, batch_key),|groups.setdefault((0, batch_key),|biz:$T/service/actions/test_batches.py
8|2|$B|return [self.runs[p][0] for p in PARTS if p in self.runs]§latest, *earlier = g.runs[part]|return [self.runs[p][-1] for p in PARTS if p in self.runs]§*earlier, latest = g.runs[part]|biz:$T/service/actions/test_batches.py
9|2|$B|        and (state is None or _state(g.latest(), digests) == state)\n§    page = kept[offset : offset + limit]|§    page = [g for g in kept[offset : offset + limit] if state is None or _state(g.latest(), digests) == state]|biz:$T/service/actions/test_batches.py
10|2|$B|documents[g.document_id].uploaded_by == str(user_id)|g.newest.created_by_user_id == user_id|biz:$T/service/actions/test_batches.py
11|2|$B|\"count\": len(kept),|\"count\": len(groups),|biz:$T/service/actions/test_batches.py
12|2|$B|steps = run_selectors.step_lines_of(company_id=company_id, run_ids=latest_ids)|steps = run_selectors.step_lines_of(company_id=company_id, run_ids=[k.id for g in groups for ks in g.runs.values() for k in ks])|biz:$T/service/actions/test_batches.py
12b|2|$B|RUNS_OF_CHUNK: Final = 15|RUNS_OF_CHUNK: Final = 10**6|biz:$T/service/actions/test_batches.py
13|2|$B|found = next((g for g in groups if g.key == batch_key), None)|found = next((g for g in groups if g.key == batch_key or any(f\"run-{k.id}\" == batch_key for ks in g.runs.values() for k in ks)), None)|biz:$T/service/actions/test_batches.py
16|2|$B|    keys = keys[:RUNS_MAX]\n|    keys = keys[:RUNS_MAX]\n    if document_id is not None:\n        keys = keys + run_selectors.run_keys(company_id=company_id, module=\"greenwash\", document_id=document_id, limit=RUNS_MAX)\n|biz:$T/service/actions/test_batches.py
17|2|$TR/service/apis/translation.py|    found = batch_actions.batch(company_id=company_of(principal), document_id=document_id, batch_key=batch_key)|    found = next((f for c in range(1, 1000) if not isinstance(f := batch_actions.batch(company_id=c, document_id=document_id, batch_key=batch_key), batch_actions.NotFound)), batch_actions.NotFound())|sec:tests/security/test_translation.py tests/security/test_tenant_paths.py
18|2|esgapi/core/permissions.py|    \"translation_batches_list\": COMPANY,|    \"translation_batches_list\": CUSTOMER,|sec:tests/security/test_translation.py tests/security/test_tenant_paths.py
19|2|$B|    keys = run_selectors.run_keys(company_id=company_id, module=MODULE, document_id=document_id, limit=RUNS_MAX + 1)|    keys = tuple(run_selectors.RunKey(r.id, r.document_id, r.status, r.created_at, r.finished_at, r.created_by_user_id, r.options.get(\"batchId\"), r.options.get(\"part\")) for r, _ in run_selectors.run_page(company_id=company_id, module=MODULE, status=None, document_id=document_id, limit=RUNS_MAX + 1, offset=0).runs)|biz:$T/service/actions/test_batches.py
14|3|$AR|    for key in found.group.latest():|    for key in [k for ks in found.group.runs.values() for k in ks]:|biz:$T/service/actions/test_archive.py
15|3|$AR|            if data is None:\n                missing += 1\n|            if data is None:\n                return batches.NotFound()\n|biz:$T/service/actions/test_archive.py
15b|3|$TR/service/apis/translation.py|    response[\"X-Archive-Missing\"] = str(found.missing)\n||biz:$T/service/actions/test_archive.py
15c|3|$AR|rows.append((f\"{key.part}-{name}\", key.id, row))|rows.append((f\"{key.part}-translation.docx\", key.id, row))|biz:$T/service/actions/test_archive.py"

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
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록. -x 없이 — 어느 파일이 빨개졌는지 줄마다 본다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록. -x 없이 — 어느 파일이 빨개졌는지 줄마다 본다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -x -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
    if [ "$code" = 1 ]; then red=1; else red=0; fi
  fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | head -6 | paste -sd' ' -)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests) ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=5 ;; 2) want=18 ;; 3) want=22 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
