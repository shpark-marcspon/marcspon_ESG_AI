#!/usr/bin/env bash
# 밴드 G1b-3(MARC-TICK-225: 그린워싱 검토 고침 — review@2·표시 표 칸 아홉·마이그레이션 0004·확정본 엑셀·목록 효력 등급·GW-05)의
# 심은 파손(발주서 band-handoffs/G1b-3-order.md §3 — 커밋 ① 에서 ①~⑨ + ⑦b(쓰기 회사 조건, 검증 1 B2) = 10,
# ② 에서 ⑩~⑮ 더함, ③ 에서 웹 ⑯~⑳ 더함).
# 틀은 planted-breaks-G1b-2a.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로 되쓴다(git checkout·restore·stash 를
# 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G1b-3.sh [--commit 1|2|3] [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 웹 층(커밋 3, ⑯~⑳)은 apps/web 에서 vitest 를 돌리고 JSON 보고의 실패를 「apps/web 기준 파일::시험 이름」으로 읽는다(컨테이너 없음).
# 커밋 n 에는 커밋 n 까지의 파손만 심는다. 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로
# 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G1B3_OUT(기본: 워크트리 곁의 G1b-3.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1B3_OUT:-$(cd "$ROOT/.." && pwd)/G1b-3.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
COMMIT = 3
CONTAINERS = False
ONLY: set[str] | None = None
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2", "3"):
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


def drop_constraint(name: str) -> Callable[[str], str | None]:
    """마이그레이션의 AddConstraint 블록 가운데 이름이 name 인 것 하나를 지운다(블록은 8칸 들여쓴 `),` 로 끝난다)."""
    opener = "        migrations.AddConstraint(\n"

    def plant(text: str) -> str | None:
        parts = text.split(opener)
        hits = [i for i, part in enumerate(parts) if i > 0 and f"name=\"{name}\"" in part.split("\n        ),\n")[0]]
        if len(hits) != 1:
            return None
        i = hits[0]
        rest = parts[i].split("\n        ),\n", 1)[1]  # 지운 블록 뒤 — 다음 블록 앞까지
        tail = "".join(opener + part for part in parts[i + 1 :])
        return opener.join(parts[:i]) + rest + tail

    return plant


G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
ACTIONS = G / "service/actions/review.py"
APIS = G / "service/apis/greenwash.py"
SELECTORS = G / "service/selectors/review.py"
SERVICES = G / "service/services/review.py"
M0004 = G / "migrations/0004_review_mark_edits.py"
TE = f"{T}/service/apis/test_greenwash_review_edits.py"
TRV = f"{T}/service/apis/test_greenwash_review.py"
TM = f"{T}/test_migrations_0004.py"
TS = "tests/security/test_greenwash.py"
XLSX = G / "outputs/xlsx.py"
CHECKS = G / "service/actions/checks.py"
TX = f"{T}/outputs/test_xlsx_edits.py"
TXR = f"{T}/outputs/test_xlsx_report.py"
TO = f"{T}/service/apis/test_greenwash_review_edits_outputs.py"
TC = f"{T}/service/apis/test_greenwash_checks.py"
# 웹(커밋 3): 심는 파일은 apps/api-py 기준, 겨눔 시험·노드는 apps/web 기준
WEB = Path("../web")
W_REVIEW = WEB / "src/entities/greenwash/model/review.ts"
W_HOOK = WEB / "src/entities/greenwash/hooks/useReview.ts"
W_SCREEN = WEB / "src/pages/greenwash-review/ui/ReviewScreen.tsx"
WT_MODEL = "src/entities/greenwash/model/review-edits.test.ts"
WT_HOOK = "src/entities/greenwash/hooks/review-edit.test.tsx"
WT_SCREEN = "src/pages/greenwash-review/ui/review-screen.test.tsx"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)
# 웹 층: 넷째 칸 = 돌릴 자리(apps/web). --outputFile 은 run_web() 이 붙인다.
WEB_LAYER = ("웹", ["pnpm", "exec", "vitest", "run", "--reporter=json"], False, str(WEB))

FOLD = (
    '        level = edit["level"] if edit["level"] != ai.get("level") else None\n'
    '        bullets = bullets if bullets != ai.get("reasonBullets") else None\n'
    '        fix = fix if fix != ai.get("fixParagraph") else None\n'
)
FOLDED = TE + "::test_values_equal_to_the_ai_fold_to_no_edit"
OWN_COLUMNS = TE + "::test_marks_and_edits_replace_only_their_own_columns"

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(검사 커밋, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", 1, "정규화(AI 견줌) 지움",
     [(ACTIONS, swap(FOLD, '        level = edit["level"]\n'))],
     [(1, BUSINESS, [TE], {FOLDED})]),
    ("2", 1, "marks 갈아 넣기가 고침 칸을 NULL(edits 생략에도 고침 갈아 넣기)",
     [(ACTIONS, swap("        if edits is not None:\n            new |= _edited_columns(",
                     "        if True:\n            new |= _edited_columns("))],
     [(1, BUSINESS, [TE], {OWN_COLUMNS})]),
    ("3", 1, "edits 갈아 넣기가 decision 을 NULL",
     [(ACTIONS, swap("        decision, reason = wanted.get(index, (None, None))\n",
                     "        decision, reason = wanted.get(index, (None, None)) if edits is None else (None, None)\n"))],
     [(1, BUSINESS, [TE], {OWN_COLUMNS})]),
    ("4", 1, "edits None 을 [] 로(경로)",
     [(APIS, swap("        edits=body.edits,\n", "        edits=body.edits or [],\n"))],
     [(1, BUSINESS, [TE], {OWN_COLUMNS})]),
    ("5", 1, "같은 값이어도 그 칸의 때·사람을 새로(칸 하나 바꿔도 세 칸 다 바뀜)",
     [(ACTIONS, swap("        if new == old:\n            return old, at, by\n", ""))],
     [(1, BUSINESS, [TE], {TE + "::test_each_column_keeps_its_own_time_and_person"})]),
    ("6", 1, "확정 뒤 edits 를 받음",
     [(ACTIONS, swap('    if review is not None and review.state == "confirmed":\n        return ReviewLocked()\n',
                     '    if review is not None and review.state == "confirmed" and edits is None:\n'
                     "        return ReviewLocked()\n"))],
     [(1, BUSINESS, [TE], {TE + "::test_edits_on_the_confirm_put_are_saved_then_locked"})]),
    ("7", 1, "고침 읽기(mark_rows)의 회사 조건을 지움(남의 회사 행까지)",
     [(SELECTORS, swap(
         '    rows = GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id).order_by("item_index")\n'
         "    return {\n        r.item_index: MarkRow(",
         '    rows = GreenwashReviewMarkRow.unscoped.filter(run_id=run_id).order_by("item_index")\n'
         "    return {\n        r.item_index: MarkRow("))],
     [(1, BUSINESS, [TRV], {TRV + "::test_another_companys_review_rows_on_the_same_run_id_do_not_leak"})]),
    ("7b", 1, "표시·고침 쓰기(write_marks UPDATE)의 회사 조건을 지움(검증 1 B2)",
     [(SERVICES, swap(
         "            GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id, item_index=index).update(**columns)",
         "            GreenwashReviewMarkRow.unscoped.filter(run_id=run_id, item_index=index).update(**columns)"))],
     [(1, BUSINESS, [TE], {TE + "::test_a_write_touches_only_my_companys_rows"}),
      (1, SECURITY, [TS], {TS + "::test_my_writes_leave_another_companys_row_on_the_same_item"})]),
    ("8", 1, "0004 의 칸 CHECK 하나(level_edit) 지움",
     [(M0004, drop_constraint("greenwash_review_marks_level_edit_check"))],
     [(1, BUSINESS, [TM], {TM + "::test_the_four_checks_hold_for_the_owner[level-value-only]",
                           TM + "::test_0004_keeps_old_rows_and_reads_them_as_review_at_2"})]),
    ("9", 1, "상태·조기 반환을 정규화 앞 값(보낸 edits)으로",
     [(ACTIONS, swap("        if not wanted and not wanted_edits and not confirm:",
                     "        if not wanted and not edits and not confirm:")),
      (ACTIONS, swap("    elif (wanted or wanted_edits) and review.state", "    elif (wanted or edits) and review.state"))],
     [(1, BUSINESS, [TE], {FOLDED})]),
    ("10", 2, "확정본 엑셀의 사유·수정 방향이 AI 값(고침을 안 덮음)",
     [(XLSX, swap('"reasonBullets": item["reasonBullets"] if bullets is None else list(bullets),',
                  '"reasonBullets": item["reasonBullets"],')),
      (XLSX, swap('"fixParagraph": item["fixParagraph"] if fix is None else fix,', '"fixParagraph": item["fixParagraph"],'))],
     [(2, PURE, [TX], {TX + "::test_edited_values_lead_and_the_ai_values_follow_only_for_edited_columns"}),
      (2, BUSINESS, [TO], {TO + "::test_the_confirmed_workbook_carries_the_edits_and_the_ai_judgement"})]),
    ("11", 2, "확정본 요약을 AI 등급으로 셈(고친 등급을 안 덮음)",
     [(XLSX, swap('"level": item["level"] if level is None else level,', '"level": item["level"],'))],
     [(2, PURE, [TX], {TX + "::test_the_summary_counts_the_edited_levels_across_both_parts"})]),
    ("12", 2, "edits None 인데 칸 넷을 붙임",
     [(XLSX, swap("_put(sentences, SENTENCE_HEADER if edits is None else SENTENCE_HEADER + EDIT_HEADER)",
                  "_put(sentences, SENTENCE_HEADER + EDIT_HEADER)"))],
     [(2, PURE, [TX, TXR], {TX + "::test_no_edits_is_the_confirmed_workbook_without_the_edit_columns",
                            TXR + "::test_the_confirmed_workbook_holds_only_the_adopted_sentences"})]),
    ("13", 2, "「고친 문장」 줄을 「판」 뒤로",
     [(XLSX, swap("    if edits is not None:\n        edited = sum(", "    if adopted is not None:\n        _put(settings, (\"판\", "
                  "f\"확정본 — 채택 {len(result['items'])} / 전체 {total}\"))\n    if edits is not None:\n        edited = sum(")),
      (XLSX, swap("        _put(settings, (\"고친 문장\", str(edited)))\n    if adopted is not None:\n"
                  "        _put(settings, (\"판\", f\"확정본 — 채택 {len(result['items'])} / 전체 {total}\"))\n",
                  "        _put(settings, (\"고친 문장\", str(edited)))\n"))],
     [(2, PURE, [TX], {TX + "::test_the_edited_count_row_sits_right_before_the_version_row"})]),
    ("14", 2, "목록 levelCounts 를 AI 셈으로",
     [(CHECKS, swap("effective_level_counts(result, tally.edited_levels if tally is not None else {})",
                    "effective_level_counts(result, {})"))],
     [(2, BUSINESS, [TO], {TO + "::test_the_list_counts_the_effective_levels"})]),
    ("15", 2, "목록이 실행마다 표시·고침을 읽음(N+1)",
     [(CHECKS, swap("            tally = tallies.get(run.id)\n",
                    "            tally = review_selectors.mark_tallies(company_id=company_id, run_ids={run.id}).get(run.id)\n"))],
     [(2, BUSINESS, [TO, TC], {TO + "::test_the_list_query_count_stays_k_with_edited_runs",
                               TC + "::test_the_query_count_is_a_constant_k_whatever_the_run_count"})]),
    ("16", 3, "웹 보이는 등급 = AI(고친 등급을 안 봄)",
     [(W_REVIEW, swap("      shownLevel: edit?.level?.value ?? item.level,\n", "      shownLevel: item.level,\n"))],
     [(3, WEB_LAYER, [WT_MODEL, WT_SCREEN],
       {WT_MODEL + "::고친 칸은 고친 값, 안 고친 칸은 AI 값. AI 원본(item)은 그대로",
        WT_MODEL + "::등급 탭은 보이는 등급으로 거른다(High → Low 로 고친 문장은 Low 탭에)",
        WT_SCREEN + "::목록·tally·탭은 보이는 등급(고친 값 ?? AI): 고친 줄에 「고침」, 「… · 고친 문장 n」, Low 탭에 High → Low 로 고친 문장"})]),
    ("17", 3, "웹 칸을 벗어날 때(blur) 처리기가 PUT 을 안 부름(처리기 안에서 우회)",
     [(W_SCREEN, swap("    const saved = await onEdit(change);\n", "    const saved = true;\n"))],
     [(3, WEB_LAYER, [WT_SCREEN],
       {WT_SCREEN + "::판정 사유 [고치기] → 「고치는 중 · 칸을 벗어나면 저장돼요」 글 칸 → 칸을 벗어나면 PUT 하나(줄 = 항목, 「- 」·빈 줄 뗌) → 닫히고 「고침」",
        WT_SCREEN + "::수정 방향: 글을 안 바꾸고 칸을 벗어나면 PUT 0·닫힘, 바꾸면 PUT 하나(서버가 앞뒤 공백을 지움)"})]),
    ("18", 3, "웹 markUpdate 가 edits: [] 를 실음(채택·제외가 고침을 다 지움)",
     [(W_REVIEW, swap("  return { marks };\n", "  return { marks, edits: [] };\n"))],
     [(3, WEB_LAYER, [WT_MODEL],
       {WT_MODEL + "::markUpdate·confirmUpdate 는 edits 칸을 싣지 않는다(생략 = 서버의 고침 그대로)"})]),
    ("19", 3, "웹 확정 전 stale 이 marks 만 견줌",
     [(W_HOOK, swap("      if (!sameReview(again.review, current)) return stop('stale');\n",
                    "      if (!sameMarks(again.review.marks, current.marks)) return stop('stale');\n"))],
     [(3, WEB_LAYER, [WT_HOOK],
       {WT_HOOK + "::다시 읽은 검토의 고친 값이 다르면 PUT 하지 않고 stale",
        WT_HOOK + "::다시 읽은 쪽에만 고침이 있어도 stale"})]),
    ("20", 3, "웹 앞 저장 중에 온 고침(busy 거절)을 다시 안 보냄",
     [(W_HOOK, swap("      return new Promise<boolean>((resolve) => {\n",
                    "      return Promise.resolve(false);\n      return new Promise<boolean>((resolve) => {\n"))],
     [(3, WEB_LAYER, [WT_HOOK],
       {WT_HOOK + "::앞 저장 중에 온 고침은 버리지 않고 앞 저장이 끝난 뒤 한 번만 보낸다 — 본문은 앞 저장 뒤의 검토(표시 포함)에서",
        WT_HOOK + "::앞 저장이 실패해도 기다린 고침은 한 번 보낸다"})]),
]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


NODE_BIN = Path.home() / ".nvm/versions/node/v22.23.1/bin"


def run_web(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    """웹 층: apps/web 에서 vitest(JSON 보고). 실패 = 「apps/web 기준 파일::시험 이름」."""
    _, cmd, _, where = layer
    cwd = Path(where).resolve()
    report = log.with_suffix(".json")
    report.unlink(missing_ok=True)
    env = {**os.environ}
    if NODE_BIN.is_dir():
        env["PATH"] = f"{NODE_BIN}:{env.get('PATH', '')}"
    done = subprocess.run([*cmd, f"--outputFile={report}", *targets], capture_output=True, text=True,
                          check=False, env=env, cwd=cwd)
    log.write_text(done.stdout + done.stderr, encoding="utf-8")
    failed: set[str] = set()
    passed = total = 0
    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        passed, total = data.get("numPassedTests", 0), data.get("numTotalTests", 0)
        for result in data.get("testResults", []):
            rel = os.path.relpath(result["name"], cwd)
            for case in result.get("assertionResults", []):
                if case.get("status") == "failed":
                    failed.add(f"{rel}::{case['title']}")
    return done.returncode, failed, f'vitest {passed}/{total} passed'


def checks_of(plant):
    return [c for c in plant[4] if c[0] <= COMMIT]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    if len(layer) > 3:
        return run_web(layer, targets, log)
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
