#!/usr/bin/env bash
# 밴드 PB1 의 심은 파손(발주서 band-handoffs/PB1-order.md §3). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든): services/parser/scripts/planted-breaks-PB1.sh
#
# 판정(G1c 꼴): 0번(아무것도 안 심음)은 초록. 심을 때마다 먼저 산출(짓개의 PDF 해시·분해 산출 해시·고정 JSON 해시)이
# 실제로 달라지는지 본다(안 달라지면 못 잡은 것으로 센다). 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」의
# 낱말이 다 든 FAILED·ERROR 줄이 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 끝에 심은 파일들의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 산출물: PB1_OUT(기본: 워크트리 곁의 PB1.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${PB1_OUT:-$(cd "$ROOT/.." && pwd)/PB1.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "tests/test_baseline.py"]
FIXED = Path("tests/baseline/synthetic.sha256.json")
A2 = "test_a2_parse_places_matches_baseline[synthetic]"

# (번호, 심는 것, 파일, 옛 글, 새 글, 빨개져야 하는 것(한 FAILED/ERROR 줄에 다 들어야 하는 낱말 묶음 — 묶음 하나라도))
PLANTS = [
    (1, "정규화에서 source.file_name 바꾸기를 뺌", Path("scripts/parser_baseline.py"),
     '        out["source"] = {**out["source"], "file_name": FILE_NAME_PLACEHOLDER}\n',
     '        out["source"] = {**out["source"]}\n',
     [["test_a3_other_file_name_gives_same_hashes[synthetic]"]]),
    (2, "고정 JSON 의 문서 해시 한 글자", FIXED, None, None, [[A2, "document"]]),
    (3, "분해기: 블록 font_size 반올림 1 → 2 자리", Path("docparse/document.py"),
     '"font_size": round(it["size"], 1)', '"font_size": round(it["size"], 2)', [[A2, "document.blocks"]]),
    (4, "짓개의 글 한 글자", Path("tests/baseline_doc.py"),
     '"Synthetic Baseline Report"', '"Synthetic Baseline Reporx"', [["test_a1_builder_pdf_bytes[synthetic]"]]),
    (5, "분해기: 괘선 표의 가로 병합 갈래를 끔", Path("docparse/tables_lines.py"),
     "                if _h_continuous(hs, ys[i], xs[j + 1]) or _h_continuous(hs, ys[i + 1], xs[j + 1]):\n",
     "                if False:\n", [[A2, "document.tables"]]),
]

# 고정 JSON 의 synthetic 판 「document」 해시의 첫 글자를 바꾼다.
fixed_text = FIXED.read_text(encoding="utf-8")
doc_hash = __import__("json").loads(fixed_text)["variants"]["synthetic"]["document"]
flipped = ("0" if doc_hash[0] != "0" else "1") + doc_hash[1:]
PLANTS[1] = (*PLANTS[1][:3], f'"document": "{doc_hash}"', f'"document": "{flipped}"', PLANTS[1][5])

# 산출의 지문: 짓개 PDF 의 해시, 그 PDF(이름 probe-name.pdf)를 분해한 산출의 해시, 고정 JSON 파일의 해시.
PROBE = r"""
import hashlib, importlib.util, json, sys, tempfile
from pathlib import Path
from tests import baseline_doc
from docparse.document import parse_pdf_places
spec = importlib.util.spec_from_file_location("pb", "scripts/parser_baseline.py")
pb = importlib.util.module_from_spec(spec); spec.loader.exec_module(pb)
data = baseline_doc.build()
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "probe-name.pdf"; p.write_bytes(data)
    out = pb.hashes(*parse_pdf_places(p))
print(json.dumps({"pdf": hashlib.sha256(data).hexdigest(), "out": out,
                  "fixed": hashlib.sha256(Path("tests/baseline/synthetic.sha256.json").read_bytes()).hexdigest()}))
"""

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd, log):
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem), "COLUMNS": "1000"}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def probe(log):
    code, out = run(["uv", "run", "--frozen", "python", "-c", PROBE], log)
    return out.strip().splitlines()[-1] if code == 0 and out.strip() else f"probe-failed:{code}"


def red_lines(text):
    return [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]


code, _ = run(PYTEST, LOGS / "00.log")
zero_ok = code == 0
before = probe(LOGS / "00-probe.log")
print(f"[0] 아무것도 안 심음: {'초록' if zero_ok else '빨강이 있다'} (지문 {'있음' if not before.startswith('probe-failed') else before})")

caught = 0
for num, what, path, old, new, want in PLANTS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {text.count(old)} 번) — 못 잡은 것으로 센다")
        continue
    try:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        after = probe(LOGS / f"{num:02d}-probe.log")
        code, out = run(PYTEST, LOGS / f"{num:02d}.log")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
    changed = after != before and not after.startswith("probe-failed")
    reds = red_lines(out)
    hit = [w for w in want if any(all(x in line for x in w) for line in reds)]
    ok = changed and code != 0 and bool(hit)
    caught += ok
    print(
        f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (산출 {'달라짐' if changed else '안 달라짐'}, 종료 {code}, "
        f"빨간 줄 {len(reds)}, 기대한 것 {hit or want})"
    )
    for line in reds:
        print(f"    {line[:300]}")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
