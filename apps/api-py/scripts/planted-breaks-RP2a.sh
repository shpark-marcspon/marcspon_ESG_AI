#!/usr/bin/env bash
# RP2a 의 심은 파손(발주서 band-handoffs/RP2a-order.md §3 「심은 파손」): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RP2a.sh --boundary <1|2>
#   경계별 배치: ① P1~P11(11) · ② + Q1~Q9(누적 20).
# 틀은 planted-breaks-RP1.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(이 워크트리의 compose postgres 가 떠 있어야 한다).
#   「lint+」로 시작하면 lint-imports 도 돌리고 둘 다 빨개야(lint 종료 ≠ 0) 빨강으로 센다.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --boundary) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1|2) ;; *) echo "--boundary 1·2" >&2; exit 2 ;; esac

backup="$(mktemp -d /private/tmp/rp2a-planted.XXXXXX)"
case "$backup" in /private/tmp/rp2a-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈)
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

D=esgapi/core/documents
CT=esgapi/core/tests
T=$CT/documents
P=esgapi/drafting
PT=$P/tests
# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
# ① P1 uses 찾기 무시 · P2 ⓑ 찾기에서 회사 뺌(unscoped) · P3 selectors 의 uses⋈문서 회사 조건 지움 · P4 ⓑ 찾기에서 EPOCH 뺌
#   · P5 상한 검사 지움 · P6 산출물 INSERT 경합의 다시 읽기 지움 · P7 next_block 차례 뒤집음 · P8 boxes 끝을 code point 로
#   · P9 꼴 검사의 sha 대조 지움 · P10 page_count 먼저 보기 지움 · P11 EPOCH_PARSER_SHA 한 글자
# ② Q1 늘 새로 분해(포트 우회 — 부를 때마다 파서) · Q2 머리글·꼬리말 포함 · Q3 표 행 뺌 · Q4 draft 단계에서 뷰 두 번
#   · Q5 흉내 이스케이프 지움 · Q6 versions_with etag None 통과 · Q7 too_many_pages 를 실패로 · Q8 잠깐 장애를 실패로
#   · Q9 drafting 이 esgapi.translation.tools import — 심는 자리는 drafting 의 selector(.importlinter 의 모듈끼리 계약은
#     service.services·selectors 만 문다: tools 에 심으면 lint 가 초록이라 축 시험만 빨개진다. 심기는 되쓰므로 0줄)
ROWS="P1|1|$D/services.py|    if found is not None:\n        return found|    if False:\n        return found|biz:$T/test_services.py
P2|1|$D/selectors.py|        DocumentArtifactRow.for_company(company_id)\n        .filter(contract=CONTRACT, source_sha256|        DocumentArtifactRow.unscoped\n        .filter(contract=CONTRACT, source_sha256|biz:$T/test_services.py $T/test_selectors.py
P3|1|$D/selectors.py|    documents = DocumentRow.for_company(company_id).filter(pk=OuterRef(\"document_id\"))\n    return DocumentArtifactUseRow.for_company(company_id).filter(Exists(documents))|    documents = DocumentRow.unscoped.filter(pk=OuterRef(\"document_id\"))\n    return DocumentArtifactUseRow.unscoped.filter(Exists(documents))|$CT/test_selector_scope.py $CT/isolation/test_static_rules.py
P4|1|$D/selectors.py|        .filter(contract=CONTRACT, source_sha256=sha256, layout=layout, epoch=EPOCH)|        .filter(contract=CONTRACT, source_sha256=sha256, layout=layout)|biz:$T/test_services.py
P5|1|$D/services.py|    ready = size <= ARTIFACT_MAX_BYTES|    ready = True|biz:$T/test_services.py
P6|1|$D/services.py|            except IntegrityError:  # 같은 열쇠를|            except ValueError:  # 같은 열쇠를|biz:$T/test_services.py
P7|1|$D/structure.py|        self._next = dict(pairwise(body))|        self._next = dict(pairwise(reversed(body)))|$T/test_structure.py
P8|1|$D/view.py|        end = min(end, utf16_length(self._container_text(container_id)))|        end = min(end, len(self._container_text(container_id)))|$T/test_view.py
P9|1|$D/contract.py|        if source.get(\"sha256\") != sha256:|        if False:|$T/test_contract.py
P10|1|$D/services.py|    if source.page_count is not None and source.page_count > max_pages:  # ⓒ1|    if False:  # ⓒ1|biz:$T/test_services.py
P11|1|$D/contract.py|    1: \"bd3ae4f1|    1: \"cd3ae4f1|$T/test_contract.py
Q1|2|$P/service/actions/run_sources.py|        return artifact_services.ensure_artifact(|        self.parser().parse(b\"\", file_name=\"x\", layout=PARSER_LAYOUT)\n        return artifact_services.ensure_artifact(|biz:$PT/flows/test_runs_drafting.py
Q2|2|$P/tools/blocks_text.py|    for block in view.body_blocks(page):|    for block in view.blocks(page):|$PT/tools/test_blocks_text.py
Q3|2|$P/tools/blocks_text.py|        if any(cell.strip() for cell in cells):|        if False:|$PT/tools/test_blocks_text.py
Q4|2|$P/flows/draft_v1.py|    leaf_to_pages, _, _ = _page_map(inputs, found, map_data)|    leaf_to_pages, _, _ = _page_map(inputs, _read_pages(inputs, adapters, carried), map_data)|$PT/flows/test_draft_v1.py
Q5|2|$P/engines/v1/pages.py|(escape_heads(t.strip()) for t in texts)|(t.strip() for t in texts)|$PT/engines/v1/test_pages.py $PT/flows/test_draft_v1.py
Q6|2|$P/flows/binding_v1.py| or not document.uploaded or document.etag is None:| or not document.uploaded:|$PT/flows/test_binding_v1.py
Q7|2|$P/flows/draft_v1.py|frozenset({\"too_many_pages\", \"too_large\", \"parse_timeout\"})|frozenset({\"too_large\", \"parse_timeout\"})|$PT/flows/test_draft_v1.py
Q8|2|$P/flows/draft_v1.py|    except ArtifactInvalid:\n        raise ArtifactFailed|    except Exception:\n        raise ArtifactFailed|$PT/flows/test_draft_v1.py
Q9|2|$P/service/selectors/projects.py|from esgapi.drafting.models import|from esgapi.translation.tools import pdf_tags as _planted\nfrom esgapi.drafting.models import|lint+$PT/test_axes.py"

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
  lint_red=1
  lint_note=""
  if [ "${tests#lint+}" != "$tests" ]; then
    tests="${tests#lint+}"
    if uv run --frozen lint-imports > "$backup/lint" 2>&1; then lint_red=0; fi
    lint_note="lint-imports $([ "$lint_red" = 1 ] && echo 빨강 || echo ★초록), "
  fi
  if [ "${tests#biz:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
  else
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
  fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  # 빨강 = 종료 1 이고 FAILED 줄이 있음(ERROR 뿐인 종료 1 — DB 끊김 등 — 은 「죽음」이다)
  if [ "$code" = 1 ] && [ "${nfail:-0}" -gt 0 ] && [ "$lint_red" = 1 ]; then red=1; else red=0; fi
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, ${lint_note}$tests) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=11 ;; 2) want=20 ;; esac
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
