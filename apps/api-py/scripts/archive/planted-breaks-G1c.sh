#!/usr/bin/env bash
# 밴드 G1c 의 심은 파손(발주서 band-handoffs/G1c-order.md §4-6 의 열둘 + 감독 결정의 13). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-G1c.sh
#
# 판정(G1a 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 FAILED·ERROR 줄에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 끝에 심은 파일들의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 산출물: G1C_OUT(기본: 워크트리 곁의 G1c.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1C_OUT:-$(cd "$ROOT/.." && pwd)/G1c.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests/flows"
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider"]
EXTRA = PYTEST + [f"{T}/test_extra_terms.py"]

# (번호, 심는 것, 파일, 옛 글, 새 글, 돌릴 명령, 빨개져야 하는 것(FAILED/ERROR 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "judge 에서 re.escape 를 뺌", G / "flows/colab.py",
     "[re.escape(term) for term in inputs.extra_terms]", "[term for term in inputs.extra_terms]",
     EXTRA, ["test_symbols_are_escaped_before_the_env_regex"]),
    (2, "judge 의 finally 되돌림을 뺌(점검 갈래)", G / "flows/colab.py",
     "        if inputs.extra_terms:\n            set_env_keywords(None, False)",
     "        if inputs.extra_terms and inputs.dry_run:\n            set_env_keywords(None, False)",
     EXTRA, ["test_two_runs_in_a_row_the_second_is_e0", "test_the_global_is_restored_when_judge_is_interrupted"]),
    (3, "dry-run 갈래의 되돌림을 뺌", G / "flows/colab.py",
     "        if inputs.extra_terms:\n            set_env_keywords(None, False)",
     "        if inputs.extra_terms and not inputs.dry_run:\n            set_env_keywords(None, False)",
     EXTRA, ["test_the_global_is_restored_when_the_dry_run_fails"]),
    (4, "중복 제거를 뺌", G / "flows/colab.py",
     "        if key not in seen:\n", "        if True:\n",
     EXTRA, ["test_terms_are_trimmed_and_deduplicated_by_the_key"]),
    (5, "30개 상한을 31로", G / "flows/colab.py",
     "EXTRA_TERMS_MAX: Final = 30\n", "EXTRA_TERMS_MAX: Final = 31\n",
     EXTRA, ["test_the_length_and_count_limits"]),
    (6, "빈도 목록에서 기본 단어를 거르지 않음(두 번 셈)", G / "flows/gw1.py",
     "    return [t for t in extra_terms if term_key(t) not in base]", "    return list(extra_terms)",
     EXTRA, ["test_a_default_word_is_accepted_but_counted_once"]),
    (7, "wordcount 에 extra 를 더하지 않음", G / "flows/colab.py",
     "    terms = [*GREEN_TERMS, *frequency_extras(inputs.extra_terms)]", "    terms = [*GREEN_TERMS]",
     EXTRA, ["test_an_extra_word_keeps_its_sentence_and_is_counted"]),
    (8, "judge(점검 갈래)에 extra 를 넘기지 않음", G / "flows/colab.py",
     "_scan_pages(docs, manual_pages, adapters, carried, ctx, config)",
     "_scan_pages(docs, manual_pages, adapters, carried, ctx, dict(SCAN_CONFIG))",
     EXTRA, ["test_an_extra_word_keeps_its_sentence_and_is_counted"]),
    (9, "결과 꼴(ScanResult)에서 extra_terms 칸을 뺌", G / "flows/shapes.py",
     '근거를 찾아도 되는 쪽과 같다."""\n    extra_terms: ExtraTerms\n', '근거를 찾아도 되는 쪽과 같다."""\n',
     PYTEST + [f"{T}/test_shapes.py"], ["test_the_json_schema_is_pinned"]),
    (10, "엑셀 단어 빈도의 「추가」 표시를 빼먹음", G / "flows/xlsx.py",
     '(row["term"], int(row["count"]), ADDED if row["term"] in added else None)',
     '(row["term"], int(row["count"]), None)',
     EXTRA, ["test_results_with_extra_words_fit_the_shape_and_the_workbook"]),
    (11, "dry-run 갈래에 extra 를 넘기지 않음", G / "flows/colab.py",
     "dry_run(docs, manual_pages, manual_pages, config, counter)",
     "dry_run(docs, manual_pages, manual_pages, dict(SCAN_CONFIG), counter)",
     EXTRA, ["test_dry_run_rule_candidates_grow_with_the_extra_word"]),
    (12, "괄호·따옴표 단어 거절을 뺌", G / "flows/colab.py",
     "    if any(EXTRA_TERM_REFUSED.search(term) for term in stripped):\n", "    if False:\n",
     EXTRA, ["test_brackets_and_quotes_are_refused"]),
    (13, "글자·숫자 없는 단어 거절을 뺌(감독 결정, 검증 지적 1)", G / "flows/colab.py",
     "    if not all(any(c.isalnum() for c in term_key(term)) for term in stripped):\n", "    if False:\n",
     EXTRA, ["test_terms_without_a_letter_or_digit_are_refused"]),
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
    """pytest 의 FAILED·ERROR 줄(되돌림 파손은 autouse 지킴의 뒷정리 ERROR 로도 나온다)."""
    return [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]


cmds = {tuple(p[5]) for p in PLANTS}
zero_ok = True
for i, cmd in enumerate(sorted(cmds)):
    code, _ = run(list(cmd), LOGS / f"00-{i}.log")
    zero_ok = zero_ok and code == 0
print(f"[0] 아무것도 안 심음: {'전부 초록' if zero_ok else '빨강이 있다'} ({len(cmds)} 명령)")

caught = 0
for num, what, path, old, new, cmd, want in PLANTS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {text.count(old)} 번) — 못 잡은 것으로 센다")
        continue
    try:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        code, out = run(cmd, LOGS / f"{num:02d}.log")
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
