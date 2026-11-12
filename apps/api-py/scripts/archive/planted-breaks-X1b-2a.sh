#!/usr/bin/env bash
# 밴드 X1b-2a 의 심은 파손(발주서 band-handoffs/X1b-2-order.md §3-2, 개정 1·2 — 2a 몫 P1~P15·P23~P28, 가지 리뷰 fix ④ 의 P29~P31). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로
# 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-X1b-2a.sh [--commit 1|2|3|4] [--with-containers] [--only P1,P4]
#
# (-q 를 품은 층 명령에 -vv 를 더해 PASSED 줄이 찍히게 한다 — -v 하나면 -q 와 맞비겨 초록 노드를 못 본다.)
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 「잡음」= 심은 뒤 그 층의 pytest 가 0 아닌 종료이고, 빨개져야 할
# 시험 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 「초록이어야 함」 노드가 있으면 그것이 통과로
# 찍혀야 한다.
# 커밋 n 에는 커밋 n 까지의 P 만 심는다. 업무·보안·통합 층(컨테이너가 필요)은 --with-containers 일 때만 — 아니면
# 「안 돌림」으로 찍고 잡은 수·심은 수에 넣지 않는다(조용한 초록 0).
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지
# 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 보안 층은 부를 때마다 테스트 DB 를 새로 만들어 마이그레이션한다(심은 마이그레이션이 그대로 들어간다).
# 산출물: X1B2A_OUT(기본: 워크트리 곁의 X1b-2a.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${X1B2A_OUT:-$(cd "$ROOT/.." && pwd)/X1b-2a.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
COMMIT = 4
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2", "3", "4"):
        COMMIT, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def cut(pattern: str) -> Callable[[str], str | None]:
    """정규식(DOTALL)에 정확히 한 번 맞는 자리를 지운다."""

    def plant(text: str) -> str | None:
        found = list(re.finditer(pattern, text, flags=re.S))
        return text[: found[0].start()] + text[found[0].end() :] if len(found) == 1 else None

    return plant


def swap_all(old: str, new: str, count: int) -> Callable[[str], str | None]:
    """old 가 정확히 count 번 있을 때 전부 바꾼다."""

    def plant(text: str) -> str | None:
        return text.replace(old, new) if text.count(old) == count else None

    return plant


CORE_MIGRATION = Path("esgapi/core/migrations/0001_initial.py")
VERSIONS = Path("esgapi/core/calc/versions.py")
CALC_DOCS = Path("esgapi/core/calc/documents.py")
SVC_DOCS = Path("esgapi/core/service/services/documents.py")
SEL_DOCS = Path("esgapi/core/service/selectors/documents.py")
PDF = Path("esgapi/core/resources/pdf.py")
T_VERSIONS = "esgapi/core/tests/calc/test_versions.py"
T_CALC = "esgapi/core/tests/calc/test_documents.py"
T_PDF = "esgapi/core/tests/resources/test_pdf.py"
T_SVC = "esgapi/core/tests/service/services/test_documents.py"
T_SEL = "esgapi/core/tests/service/selectors/test_documents.py"
SCOPE = "esgapi/core/tests/test_selector_scope.py"
TXN = "esgapi/core/tests/test_transaction_rules.py"
API_DOCS = Path("esgapi/core/service/apis/documents.py")
SCHEMA_DOCS = Path("esgapi/core/service/schemas/documents.py")
T_API = "esgapi/core/tests/service/apis/test_documents.py"
T_CHAIN = "tests/security/test_documents_chain.py"
PERMS = "esgapi/core/tests/test_permissions.py"
SEL_RUNS = Path("esgapi/runs/service/selectors/runs.py")
T_RUNS = "esgapi/runs/tests/service/apis/test_runs.py"
FIXTURES = Path("../web/src/entities/run-log/api/mock/fixtures.ts")

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)
# 웹: apps/web 의 tsc(scripts/verify.sh --fast 의 L1 과 같은 typecheck). 「빨간 노드」는 tsc 오류 줄의 <파일>:TS<번호>.
NODE_BIN = os.path.expanduser("~/.nvm/versions/node/v22.23.1/bin")
WEB = ("웹", ["pnpm", "--dir", "../web", "typecheck"], False)

FAILURES = T_SVC + "::test_every_probe_failure_confirms_with_null_values_and_the_same_company"

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음, 초록이어야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "core 0001 의 core_documents_previous_uniq 를 지움(모델은 그대로 — DB 에만 없음)",
     [(CORE_MIGRATION, cut(r"\n {20}models\.UniqueConstraint\(\n(?:(?! {20}\)).)*? {20}\),(?=\n {16}\],)"))],
     [(BUSINESS, [T_SVC], {T_SVC + "::test_a_racing_fork_is_stopped_by_the_unique_constraint"}, set())]),
    ("P2", 1, "사슬 판정이 순환을 보지 않음(ChainCycle 갈래 둘을 지움)",
     [(VERSIONS, swap_all("        return ChainCycle()\n", "        pass\n", 2))],
     [(PURE, [T_VERSIONS], {
         T_VERSIONS + "::test_linking_back_into_your_own_later_versions_is_a_cycle[1-2-pairs0]",
         T_VERSIONS + "::test_linking_back_into_your_own_later_versions_is_a_cycle[1-3-pairs1]",
     }, set()),
      (BUSINESS, [T_SVC], {T_SVC + "::test_the_update_refuses_self_fork_and_cycle"}, set())]),
    ("P3", 1, "has_text 가 공백도 글자로 셈(strip() 지움)",
     [(CALC_DOCS, swap("any(text.strip() for text in page_texts)", "any(text for text in page_texts)"))],
     [(PURE, [T_CALC], {
         T_CALC + "::test_has_text_counts_only_non_space_characters[pages2-False]",
     }, set())]),
    ("P4", 1, "올림 확인이 PDF 재기 실패를 409(NotUploaded)로 냄 — 올림을 막음",
     [(SVC_DOCS, swap(
         "        page_count, text_layer = _measured(storage, document, found)  # ③' — 블록 밖\n",
         "        page_count, text_layer = _measured(storage, document, found)  # ③' — 블록 밖\n"
         "        if page_count is None:\n            return NotUploaded()\n"))],
     [(BUSINESS, [T_SVC], {T_SVC + "::test_bytes_that_are_not_a_pdf_still_confirm_with_unknown_values"}, set())]),
    ("P5", 1, "올림 확인의 get·probe 를 ④ 블록 안으로",
     [(SVC_DOCS, swap(
         "        page_count, text_layer = _measured(storage, document, found)  # ③' — 블록 밖\n", "")),
      (SVC_DOCS, swap(
         "    with transaction.atomic():\n        if found is not None:\n",
         "    with transaction.atomic():\n        if found is not None:\n"
         "            page_count, text_layer = _measured(storage, document, found)\n"))],
     [(PURE, [TXN], {TXN + "::test_no_outside_call_inside_a_block"}, set()),
      (BUSINESS, [T_SVC], {T_SVC + "::test_the_probe_runs_outside_any_transaction_and_only_once"}, set())]),
    ("P6", 1, "목록 selector 를 회사 조건 없이(DocumentRow.objects)",
     [(SEL_DOCS, swap('    rows = _documents(company_id).filter(status="uploaded")\n',
                      '    rows = DocumentRow.objects.filter(status="uploaded")\n'))],
     [(PURE, [SCOPE], {SCOPE + "::test_selectors_scope_every_read[core/service/selectors/documents.py]"}, set()),
      (BUSINESS, [T_SEL], {T_SEL + "::test_the_list_shows_only_this_companys_uploaded_documents_newest_first"}, set())]),
    ("P23", 1, "자식 프로세스의 시간 한도를 걷음(timeout= 지움)",
     [(PDF, swap("                timeout=PDF_PROBE_TIMEOUT_S,\n", ""))],
     [(PURE, [T_PDF], {T_PDF + "::test_a_child_that_hangs_is_killed_within_the_limit"}, set()),
      (BUSINESS, [T_SVC], {FAILURES + "[timeout]"}, set())]),
    ("P24", 1, "쪽 0 을 PdfProbed(0, False) 로 냄(empty 갈래 걷음)",
     [(PDF, cut(r"    if pages < 1:\n        return PdfUnreadable\(\"empty\"\)[^\n]*\n"))],
     [(PURE, [T_PDF], {T_PDF + "::test_zero_pages_is_empty_not_a_value"}, set()),
      (BUSINESS, [T_SVC], {FAILURES + "[empty]"}, set())]),
    ("P25", 1, "어댑터가 pypdfium2 를 부모 프로세스에서 import",
     [(PDF, swap("import json\nimport logging\n", "import json\nimport logging\n\nimport pypdfium2  # noqa: F401\n"))],
     [(PURE, [T_PDF], {T_PDF + "::test_the_parent_never_imports_pdfium"}, set())]),
    # ── 커밋 ② ──
    ("P7", 2, "PATCH 가 previousDocumentId 를 회사 조건 없이 잠가 찾음(DocumentRow.unscoped)",
     [(SVC_DOCS, swap(
         "            locked = {i: selectors.lock_document(company_id=company_id, document_id=i) for i in ids}\n",
         "            locked = {\n                i: selectors.lock_document(company_id=company_id, document_id=i)\n"
         "                if i == document_id\n                else DocumentRow.unscoped.select_for_update().filter(pk=i).first()\n"
         "                for i in ids\n            }\n"))],
     [(SECURITY, [T_CHAIN], {T_CHAIN + "::test_another_companys_document_cannot_be_patched_chained_or_downloaded"}, set()),
      (BUSINESS, [T_API], {T_API + "::test_patch_of_another_companys_document_or_previous_is_404"}, set())]),
    ("P8", 2, "원본 내려받기의 record_event 를 지움",
     [(API_DOCS, cut(r"    record_event\(\n        at=now\(\),\n.*?\n    \)\n(?=    response = HttpResponse)"))],
     [(BUSINESS, [T_API], {T_API + "::test_the_original_comes_back_as_a_pdf_attachment_with_one_audit_line"}, set())]),
    ("P9", 2, "원본 내려받기가 uploaded 아닌 문서도 냄(상태 검사 지움)",
     [(API_DOCS, swap('    if document.status != "uploaded":\n        raise _not_uploaded()\n', ""))],
     [(BUSINESS, [T_API], {T_API + "::test_the_original_of_a_document_not_yet_uploaded_is_409"}, set())]),
    ("P10", 2, "원본 내려받기가 ETag 를 견주지 않음",
     [(API_DOCS, swap("    if got.etag != document.etag:", "    if False:"))],
     [(BUSINESS, [T_API], {T_API + "::test_the_original_changed_after_the_confirm_is_409"}, set())]),
    ("P11", 2, "latestOnly 거르기를 무시",
     [(SEL_DOCS, swap("    if latest_only:\n", "    if False:\n"))],
     [(BUSINESS, [T_API], {T_API + "::test_latest_only_keeps_the_last_of_each_chain"}, set())]),
    ("P12", 2, "q 의 NUL 막는 pattern 을 지움",
     [(SCHEMA_DOCS, swap("        pattern=NO_NUL_PATTERN,\n", ""))],
     [(BUSINESS, [T_API], {T_API + "::test_a_nul_in_q_is_refused_not_a_500"}, set())]),
    ("P13", 2, "_document_out 이 hasText 를 늘 None 으로",
     [(API_DOCS, swap("        hasText=document.has_text,\n", "        hasText=None,\n"))],
     [(BUSINESS, [T_API], {T_API + "::test_the_confirm_answers_with_the_measured_page_count_and_text_layer"}, set())]),
    ("P14", 2, "경로 documents_update 의 첫 문장 permitted(...) 를 지움",
     [(API_DOCS, swap('    principal = permitted(request, "core_documents_update")\n',
                      "    principal = request.auth  # 심은 파손\n"))],
     [(PURE, [PERMS], {PERMS + "::test_each_route_checks_its_own_operation_id_first"}, set())]),
    ("P26", 2, "만들기가 previousDocumentId 를 받음(422 PREVIOUS_VIA_PATCH 갈래 걷음)",
     [(API_DOCS, cut(r"    if body\.previousDocumentId is not None:[^\n]*\n        raise ApplicationError\([^\n]*\n"))],
     [(BUSINESS, [T_API], {T_API + f"::test_a_create_with_previous_is_422_and_writes_nothing[{w}]"
                           for w in ("mine", "unknown", "theirs")}, set())]),
    ("P27", 2, "원본 머리를 f'attachment; filename=\"{name}\"' 로",
     [(API_DOCS, swap("    response[\"Content-Disposition\"] = disposition\n",
                      "    response[\"Content-Disposition\"] = f'attachment; filename=\"{document.file_name}\"'\n"))],
     [(BUSINESS, [T_API], {
         T_API + "::test_the_original_comes_back_as_a_pdf_attachment_with_one_audit_line",
         T_API + "::test_an_ascii_name_is_quoted_in_the_header",
     }, set())]),
    # ── 커밋 ③ ──
    ("P15", 3, "목록 줄 selector 가 documentName 에 다른 칸(flow_id)",
     [(SEL_RUNS, swap('F("document__file_name")', 'F("flow_id")'))],
     [(BUSINESS, [T_RUNS], {T_RUNS + "::test_list_is_newest_first_filtered_paged_and_only_mine"}, set())]),
    ("P28", 3, "fixtures.ts 한 객체(id 106)의 맨 위 documentName 줄을 지움",
     [(FIXTURES, cut(r"\n    documentName: '평가 문서 1',(?=\n    id: 106,)"))],
     [(WEB, [], {"src/entities/run-log/api/mock/fixtures.ts:TS2741"}, set())]),
    # ── 커밋 ④(가지 리뷰 fix — 감독 c1) ──
    ("P29", 4, "부모가 자식 출력의 상한을 보지 않음(len(stdout) > limit 갈래 걷음)",
     [(PDF, swap("        if len(stdout) > limit:\n", "        if False:\n"))],
     [(PURE, [T_PDF], {T_PDF + "::test_output_past_the_limit_is_error_and_never_read_whole"}, set())]),
    ("P30", 4, "자식이 부모 환경을 물려받음(env={} 지움)",
     [(PDF, swap("                    env={},\n", ""))],
     [(PURE, [T_PDF], {T_PDF + "::test_the_child_inherits_no_environment"}, set())]),
    ("P31", 4, "자식이 쪽 글을 통째 냄(strip()[:k] 지움)",
     [(PDF, swap(".get_text_range().strip()[:k] for i", ".get_text_range() for i"))],
     [(PURE, [T_PDF], {T_PDF + "::test_the_child_hands_back_only_the_head_of_each_page"}, set())]),
]

PLANTS = [p for p in PLANTS if p[1] <= COMMIT and (ONLY is None or p[0] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], set[str], str]:
    name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    if layer is WEB:
        env["PATH"] = NODE_BIN + os.pathsep + env.get("PATH", "")
        done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
        text = done.stdout + done.stderr
        log.write_text(text, encoding="utf-8")
        failed = {f"{m[0]}:{m[1]}" for m in re.findall(r"^(\S+?)\(\d+,\d+\): error (TS\d+)", text, flags=re.M)}
        last = text.strip().splitlines()[-1] if text.strip() else ""
        return done.returncode, failed, set(), last
    done = subprocess.run([*cmd, "-vv", *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    passed = set(re.findall(r"^(\S+::\S+(?:\[[^\]]*\])?) PASSED", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, passed, last


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, _commit, what, edits, checks in PLANTS:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
            planted += 1
            continue
        for layer, targets, expected, green in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            planted += 1
            code, failed, passed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed and green <= passed
            caught += 1 if hit else 0
            missing = sorted(expected - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
            for node in sorted(green):
                print(f"    {'PASSED' if node in passed else '★ 초록 아님'} {node}  (초록이어야 함)")
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
