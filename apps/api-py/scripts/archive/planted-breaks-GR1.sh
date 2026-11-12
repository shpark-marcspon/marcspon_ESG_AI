#!/usr/bin/env bash
# 밴드 GR1 의 심은 파손(발주서 band-handoffs/GR1-order.md §3 의 열넷). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-GR1.sh
#
# 판정(G1c·G1d 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 FAILED·ERROR 줄에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 끝에 심은 파일의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 산출물: GR1_OUT(기본: 워크트리 곁의 GR1.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${GR1_OUT:-$(cd "$ROOT/.." && pwd)/GR1.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
C = Path("esgapi/greenwash/flows/compare.py")
TESTS = ["esgapi/greenwash/tests/flows/test_compare.py", "esgapi/greenwash/tests/flows/test_textnorm.py"]
CMD = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", *TESTS]
EXAMPLES = "test_the_contract_examples_are_reproduced"

# (번호, 심는 것, 파일, [(옛 글, 새 글), …], 빨개져야 하는 것(FAILED/ERROR 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "열쇠에 page 를 넣음", C,
     [('    return (text, tuple(cast("list[str]", item["parts"])))',
       '    return (text, tuple(cast("list[str]", item["parts"])), item["page"])  # pyright: ignore')],
     ["test_the_same_sentence_on_a_shifted_page_is_a_pair"]),
    (2, "열쇠에서 parts 를 뺌", C,
     [('    return (text, tuple(cast("list[str]", item["parts"])))', "    return (text, ())")],
     ["test_the_same_sentence_with_other_parts_is_not_a_pair"]),
    (3, "adopted 거르기를 뺌", C,
     [("if run.adopted is None or i in run.adopted]", "if True]")],
     ["test_a_confirmed_side_compares_only_its_adopted_sentences",
      "test_a_sentence_the_confirmed_base_excluded_is_new_when_the_unconfirmed_target_flags_it"]),
    (4, "not_flagged 와 deleted 를 맞바꿈", C,
     [('return "resolved_not_flagged" if _in_scope(found, target.scanned)', 'return "resolved_deleted" if _in_scope(found, target.scanned)'),
      ('return "resolved_deleted" if _found(needle, base.norm_pages)', 'return "resolved_not_flagged" if _found(needle, base.norm_pages)')],
     [EXAMPLES, "test_resolved_deleted", "test_resolved_not_flagged"]),
    (5, "undetermined 갈래를 뺌(늘 deleted)", C,
     [('    return "resolved_deleted" if _found(needle, base.norm_pages) else "resolved_undetermined"',
       '    return "resolved_deleted"')],
     [EXAMPLES, "test_resolved_undetermined"]),
    (6, "out_of_scope 갈래를 뺌(base 쪽)", C,
     [('return "resolved_not_flagged" if _in_scope(found, target.scanned) else "out_of_scope"', 'return "resolved_not_flagged"')],
     [EXAMPLES, "test_out_of_scope_on_the_base_side"]),
    (7, "out_of_scope 갈래를 뺌(target 쪽)", C,
     [("    if found and not _in_scope(found, base.scanned):", "    if False:")],
     [EXAMPLES, "test_out_of_scope_on_the_target_side"]),
    (8, "②·③ 블록 차례를 바꿈", C,
     [("    pairs = matched + base_only + target_only", "    pairs = matched + target_only + base_only")],
     [EXAMPLES]),
    (9, "counts 의 한 키를 0 으로 박음", C,
     [('{o: sum(1 for p in pairs if p["outcome"] == o) for o in OUTCOMES}',
       '{**{o: sum(1 for p in pairs if p["outcome"] == o) for o in OUTCOMES}, "new": 0}')],
     [EXAMPLES, "test_new"]),
    (10, "빈 열쇠 거름을 뺌(빈 글도 짝지음)", C,
     [("    if not text:\n        return None  # 빈 글은 어디에나 있다 — 짝짓지 않는다\n", "")],
     ["test_an_empty_normalized_sentence_is_not_an_error"]),
    (11, "2단을 1단으로", C,
     [("TIER: Final = 2", "TIER: Final = 1")],
     ["test_a_missing_period_and_a_middle_dot_for_a_comma_are_the_same_key_only_at_tier_two"]),
    (12, "compare.py 가 pdfium_locate 에서 들임", C,
     [("from esgapi.greenwash.flows.textnorm import norm_str, strip_tail",
       "from esgapi.greenwash.flows.pdfium_locate import norm_str, strip_tail")],
     ["test_importing_compare_pulls_in_no_pdfium_django_or_ninja"]),
    (13, "dry-run 검사를 뺌", C,
     [('    if run.result["dryRun"] is not None:', "    if False:")],
     ["test_bad_inputs_raise[dry-run]"]),
    (14, "여러 쪽에서 찾았을 때 「모두 점검 쪽」을 요구함", C,
     [("    return any(page in scanned for page in found)", "    return all(page in scanned for page in found)")],
     ["test_found_on_several_target_pages_one_of_them_scanned_is_not_flagged",
      "test_found_on_several_base_pages_one_of_them_scanned_is_new"]),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다.
    # 파손 12 의 새 프로세스(-c)도 이 환경을 물려받는다.
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]


code, _ = run(CMD, LOGS / "00.log")
zero_ok = code == 0
print(f"[0] 아무것도 안 심음: {'전부 초록' if zero_ok else '빨강이 있다'}")

caught = 0
for num, what, path, edits, want in PLANTS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    counts = [text.count(old) for old, _ in edits]
    if counts != [1] * len(edits):
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {counts} 번) — 못 잡은 것으로 센다")
        continue
    for old, new in edits:
        text = text.replace(old, new, 1)
    try:
        path.write_text(text, encoding="utf-8")
        code, out = run(CMD, LOGS / f"{num:02d}.log")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
    reds = red_lines(out)
    hit = [w for w in want if any(w in line for line in reds)]
    ok = code != 0 and bool(hit)
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (종료 {code}, 빨간 줄 {len(reds)}, 기대한 것 {hit or want})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
