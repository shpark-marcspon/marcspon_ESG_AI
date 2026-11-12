#!/usr/bin/env bash
# 밴드 G1d 의 심은 파손(발주서 band-handoffs/G1d-order.md §4-6 의 열넷). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-G1d.sh
#
# 판정(G1a 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 FAILED·ERROR 줄에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 끝에 심은 파일들의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 산출물: G1D_OUT(기본: 워크트리 곁의 G1d.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1D_OUT:-$(cd "$ROOT/.." && pwd)/G1d.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
F = Path("esgapi/greenwash/flows")
A, P, C = F / "adapters.py", F / "pdfium_locate.py", F / "colab.py"
TEST = "esgapi/greenwash/tests/flows/test_pdfium_locate.py"
CMD = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", TEST]

# (번호, 심는 것, 파일, [(옛 글, 새 글), …], 빨개져야 하는 것(FAILED/ERROR 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "원점 뒤집기를 뺌(pdfium 좌표 그대로)", P,
     [("    return [round(left - cx0, 2), round(cy1 - top, 2), round(right - cx0, 2), round(cy1 - bottom, 2)]",
       "    return [round(left, 2), round(bottom, 2), round(right, 2), round(top, 2)]")],
     ["test_the_upper_sentence_has_the_smaller_top_as_built"]),
    (2, "page 를 0부터로(−1 을 빼먹음)", A,
     [("        text = self._document(pdf).page(page - 1)", "        text = self._document(pdf).page(page)")],
     ["test_one_line_is_one_box_on_the_page_counted_from_one_with_a_top_left_origin"]),
    (3, "NFKC 를 뺌", F / "textnorm.py",
     [('    for c in unicodedata.normalize("NFKC", ch):', "    for c in ch:")],
     ["test_compatibility_forms_are_found_at_tier_one_by_nfkc"]),  # 합자는 casefold 가 이미 푼다(보고)
    (4, "공백 제거를 뺌", F / "textnorm.py",
     [("        if c in DROP or c.isspace():", "        if c in DROP:")],
     ["test_two_and_three_lines_give_a_box_per_line"]),
    (5, "잘림 꼬리 떼기를 뺌", A,
     [("        found = self._find(text, pl.strip_tail(sentence))", "        found = self._find(text, sentence)")],
     ["test_quotes_dashes_invisible_letters_and_the_truncation_tail_are_found_at_tier_one"]),
    (6, "여러 곳이면 첫째를 냄", A,
     [("            if len(hits) > 1:\n                return \"none_multiple\"\n", "")],
     ["test_the_same_sentence_twice_on_a_page_is_none"]),
    (7, "250자·10줄 가드를 뺌", A,
     [("        if len(sentence) > MAX_SENTENCE_CHARS:", "        if False:"),
      ("        if not lines or len(lines) > MAX_LINES:", "        if not lines:")],
     ["test_a_long_sentence_and_an_eleven_line_block_are_none"]),
    (8, "줄 묶기가 모든 글자를 상자 하나로", P,
     [("            if same_row and left >= cur[4] - 0.5 * h:", "            if True:")],
     ["test_two_and_three_lines_give_a_box_per_line"]),
    (9, "되읽기 확인을 뺌(늘 통과)", A,
     [("        if not pl.readback_ok(pl.norm_str(part, 2), back, READBACK_EXTRA_MAX):", "        if not back and False:")],
     ["test_a_box_that_reads_back_someone_elses_text_is_none"]),
    (10, "dry-run 에서도 locate 를 부름", C,
     [("    if coordinates is None or inputs.dry_run:", "    if coordinates is None:")],
     ["test_dry_run_does_not_call_coordinates"]),
    (11, "문서 캐시를 뺌(문장마다 엶)", A,
     [("        if self._doc is not None and pdf is self._bytes:", "        if False:"),
      ("        if self._doc is not None and key == self._key:", "        if False:")],
     ["test_the_same_bytes_open_the_document_once_and_new_bytes_close_the_old_one"]),
    (12, "예외를 잡지 않음", A,
     [("        except Exception as exc:", "        except ZeroDivisionError as exc:")],
     ["test_broken_bytes_and_a_page_out_of_range_are_none_and_counted"]),
    (13, "crop 원점을 빼고 mediabox 높이로 뒤집음", P,
     [("    return clipped\n", "    return media\n")],
     ["test_a_cropped_page_measures_from_the_crop_top_left"]),
    (14, "합자를 푼 같은 상자 글자를 건너뛰지 않음", P,
     [("        if (right - left <= 0 and top - bottom <= 0) or same:", "        if right - left <= 0 and top - bottom <= 0:")],
     ["test_a_ligature_is_found_and_its_split_letter_does_not_open_a_new_box"]),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다
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
