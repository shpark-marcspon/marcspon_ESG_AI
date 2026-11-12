#!/usr/bin/env bash
# 밴드 G1b-2a(MARC-TICK-201: 그린워싱 엑셀 보고서 GET·download 감사·목록 줄 문서 칸·검토 만들기 경합 좁힘)의
# 심은 파손(발주서 band-handoffs/G1b-2a-order.md §3, critic 라운드 2 R7 — 커밋 ① 에서 ①~⑨ = 9/9, ② 에서 ①~⑪ +
# 검증 1 권고 R1 의 ⑫ · 검증 2 B1 의 ⑬ = 13/13).
# 틀은 planted-breaks-G2c3.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로 되쓴다(git checkout·restore·stash 를
# 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G1b-2a.sh [--commit 1|2] [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 커밋 n 에는 커밋 n 까지의 파손만 심는다. 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로
# 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G1B2A_OUT(기본: 워크트리 곁의 G1b-2a.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1B2A_OUT:-$(cd "$ROOT/.." && pwd)/G1b-2a.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
COMMIT = 2
CONTAINERS = False
ONLY: set[str] | None = None
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2"):
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


AUDIT_START = "    # 감사 줄: 바이트를 지은 뒤·응답 앞(머리말 7)\n"
AUDIT_END = "    return Report(content=content, label=label)\n"
LABEL = "    label = CONFIRMED_LABEL if confirmed else FILE_NAME\n"
BUILD = "    content = xlsx.build("


def moved_audit(anchor: str) -> Callable[[str], str | None]:
    """감사 블록(label 줄과 함께)을 anchor 앞으로 옮긴다 — ⑧ 거절 앞 · ⑨ build 앞."""

    def plant(text: str) -> str | None:
        if text.count(AUDIT_START) != 1 or text.count(AUDIT_END) != 1 or text.count(anchor) != 1:
            return None
        block = text[text.index(AUDIT_START) : text.index(AUDIT_END)]
        text = text.replace(LABEL + block, "", 1)
        return text.replace(anchor, LABEL + block + anchor, 1)

    return plant


G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
REPORT = G / "service/actions/report.py"
XLSX = G / "outputs/xlsx.py"
CHECKS = G / "service/actions/checks.py"
REVIEW_SVC = G / "service/services/review.py"
TR = f"{T}/service/apis/test_greenwash_report.py"
TX = f"{T}/outputs/test_xlsx_report.py"
TS = "tests/security/test_greenwash.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# ② 실행 읽기를 그 실행의 회사로(세션의 회사 조건을 남의 회사로 바꿔 끼움 — 보안 층이 잡는다)
FOREIGN = (
    "    from django.db import connection as _planted\n"
    "    with _planted.cursor() as _cursor:\n"
    '        _cursor.execute("SELECT company_id FROM run_runs WHERE id = %s", [run_id])\n'
    "        _owner = _cursor.fetchone()\n"
    "    company_id = int(_owner[0]) if _owner else company_id\n"
)
RESULT_DOC = '    """규칙 1·2. 끝난 E0 그린워싱 실행의 결과 본문."""\n'
NOT_FOUND = {TR + "::test_a_missing_or_foreign_run_is_404"}

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(검사 커밋, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", 1, "flow_id 거르기 지움",
     [(REPORT, swap("run.module != MODULE or run.flow_id != E0_FLOW", "run.module != MODULE"))],
     [(1, BUSINESS, [TR], NOT_FOUND)]),
    ("2", 1, "실행 읽기의 회사 조건을 남의 회사로(그 실행의 회사)",
     [(REPORT, swap(RESULT_DOC, RESULT_DOC + FOREIGN))],
     [(1, BUSINESS, [TR], NOT_FOUND),
      (1, SECURITY, [TS], {TS + "::test_another_companys_report_is_not_found_and_not_audited["})]),
    ("3", 1, "NO_REPORT 검사 지움",
     [(REPORT, swap('    if result.get("dryRun") is not None:\n        return NoReport()\n', ""))],
     [(1, BUSINESS, [TR], {TR + "::test_a_dry_run_has_no_report"})]),
    ("4", 1, "NOT_CONFIRMED 검사 지움",
     [(REPORT, swap('    if review is None or review.state != "confirmed":\n        return NotConfirmed()\n', ""))],
     [(1, BUSINESS, [TR], {TR + "::test_the_confirmed_copy_needs_a_confirmed_review",
                           TR + "::test_an_old_compare_base_query_is_ignored"})]),
    ("5", 1, "확정본 엑셀이 전 문장(adopted 를 넘기지 않음)",
     [(REPORT, swap("        adopted = found\n", "        adopted = None\n"))],
     [(1, BUSINESS, [TR], {TR + "::test_the_confirmed_report_holds_only_the_adopted"})]),
    ("6", 1, "확정본 요약을 다시 세지 않음",
     [(XLSX, swap('    counts = {**result["counts"], "total": len(items), "byLevel": by_level, "byPart": by_part}\n',
                  '    counts = result["counts"]\n'))],
     [(1, PURE, [TX], {TX + "::test_the_confirmed_summary_is_recounted_over_every_part",
                       TX + "::test_nothing_adopted_leaves_the_header_only"}),
      (1, BUSINESS, [TR], {TR + "::test_the_confirmed_report_holds_only_the_adopted"})]),
    ("7", 1, "byPart 다시 세움 지움",
     [(REPORT, swap("xlsx.build(in_part_order(result), ", "xlsx.build(result, "))],
     [(1, BUSINESS, [TR], {TR + "::test_the_summary_parts_follow_the_result_parts_after_the_db"})]),
    ("8", 1, "감사를 거절 앞에서 씀",
     [(REPORT, moved_audit("    result = _result(company_id, run_id)\n"))],
     [(1, BUSINESS, [TR], {TR + "::test_a_missing_or_foreign_run_is_404", TR + "::test_a_dry_run_has_no_report"})]),
    ("9", 1, "감사를 build 앞으로",
     [(REPORT, moved_audit(BUILD))],
     [(1, BUSINESS, [TR], {TR + "::test_a_build_failure_writes_no_audit"})]),
    ("10", 2, "checks reportYear None",
     [(CHECKS, swap('            "reportYear": d.report_year,\n', '            "reportYear": None,\n'))],
     [(2, BUSINESS, [TR], {TR + "::test_the_checks_row_reads_the_document_cells"})]),
    ("11", 2, "create_review 의 IntegrityError 다시 넓힘",
     [(REVIEW_SVC, swap("        if _broken(err) != REVIEW_UNIQUE:\n            raise\n", "        pass\n"))],
     [(2, BUSINESS, [TR], {TR + "::test_create_review_reraises_another_integrity_error["})]),
    ("12", 2, "보고서의 added_terms 를 비움(검증 R1)",
     [(REPORT, swap('added_terms=frequency_extras(result["extraTerms"])', "added_terms=()"))],
     [(2, BUSINESS, [TR], {TR + "::test_the_report_is_the_xlsx_of_the_result"})]),
    ("13", 2, "REVIEW_UNIQUE 이름 틀리게(검증 2 B1)",
     [(REVIEW_SVC, swap('REVIEW_UNIQUE = "greenwash_reviews_company_run_uniq"', 'REVIEW_UNIQUE = "greenwash_reviews_uniq"'))],
     [(2, BUSINESS, [TR], {TR + "::test_a_second_create_review_on_the_real_unique_is_passed"})]),
]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def checks_of(plant):
    return [c for c in plant[4] if c[0] <= COMMIT]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def hit(want: str, failed: set[str]) -> bool:
    return any(f.startswith(want) for f in failed) if want.endswith("[") else want in failed


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for _, layer, targets, _ in checks_of(p):
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, _commit, what, edits, _ in PLANTS:
    plant = next(p for p in PLANTS if p[0] == number)
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, edit in edits:
            text = f.read_text(encoding="utf-8")
            new = edit(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"[{number}] 심기 실패(파일이 바뀌지 않음) — 못 잡은 것으로 센다 — {what}")
            planted += 1
            continue
        ran = 0
        all_hit = True
        for _, layer, targets, expected in checks_of(plant):
            label = f"[{number}/{layer[0]}]"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            ran += 1
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            missing = sorted(w for w in expected if not hit(w, failed))
            ok = code != 0 and not missing
            all_hit = all_hit and ok
            print(f"{label} {'잡음' if ok else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        if ran:
            planted += 1
            caught += 1 if all_hit else 0
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
for f in files:
    print(f"  {f} {hashlib.sha256(f.read_bytes()).hexdigest()}")
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
