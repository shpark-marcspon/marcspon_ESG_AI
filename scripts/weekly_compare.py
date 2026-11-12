"""정기 실행(scripts/weekly.sh)의 변이 생존을 지난 회와 diff 글자로 견주고 summary.md 를 쓴다. 표준 라이브러리만.

    python3 -I scripts/weekly_compare.py --self-test
    python3 -I scripts/weekly_compare.py --run <결과 자리> --history <결과들의 뿌리> --integration "<한 줄>"
        [--targets "<대상 수 한 줄>"] [--results <mutmut-results.txt> --diffs <diff 파일> --known <알려진 생존> --targets-hash <h> --wall <초>]

열쇠 = (모듈.함수, diff 의 `-`/`+` 줄들). 함수는 변이 이름에서 `__mutmut_<n>` 을 뗀 것이다 — 번호는 함수가 바뀌면 밀리므로
열쇠에 넣지 않는다. diff 의 머리줄(`--- <파일>`·`+++ <파일>`)과 `@@` 줄, 앞뒤 글(공백으로 시작하는 줄)은 열쇠에서 뺀다.
같은 열쇠가 여럿이면 개수까지(다중집합) 견준다. 시간초과(timeout)는 견주기에서 빼고 따로 센다 — 무한 반복 변이는 같은
코드에서도 회마다 killed·timeout 이 갈려 「새 생존」 소음이 된다(T2 의 작은 실행에서 겪음, 감독 처분 2026-10-16).
「지난 회」 = 결과들의 뿌리에서 이번보다 앞이고, 대상 목록의 해시가 같고, mutmut 이 끝까지 돈(meta.txt 의 mutmut_done=1)
가장 최근 회. 없으면 「첫 회 — 기준」 이고 새 생존을 세지 않는다.
「알려진 생존」 파일: 블록마다 `### <모듈.함수> <가|나|다> <한 줄 까닭>` 과 diff 줄. 생존마다 그 분류를 붙이기만 한다(판정하지 않는다).
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

SURVIVING = ("survived", "timeout", "suspicious")
CLASSES = ("가", "나", "다")
HEADER = re.compile(r"^(---|\+\+\+) \S+\.py$")
NUMBER = re.compile(r"__mutmut_\d+$")

Key = tuple[str, tuple[str, ...]]


def strip_number(name: str) -> str:
    return NUMBER.sub("", name)


def diff_lines(body: list[str]) -> tuple[str, ...]:
    return tuple(
        line for line in body if line[:1] in ("-", "+") and not HEADER.match(line) and not line.startswith("@@")
    )


def blocks(text: str) -> list[tuple[list[str], list[str]]]:
    """`### …` 머리마다 (머리의 낱말들, 몸의 줄들)."""
    out: list[tuple[list[str], list[str]]] = []
    for line in text.splitlines():
        if line.startswith("### "):
            out.append((line[4:].split(), []))
        elif out:
            out[-1][1].append(line)
    return out


def key_of(head: list[str], body: list[str]) -> Key:
    func = strip_number(head[0])
    key = (func, diff_lines(body))
    return key


def parse_known(text: str) -> dict[Key, str]:
    known: dict[Key, str] = {}
    for head, body in blocks(text):
        if not head:
            continue
        mark = head[1].strip("[]") if len(head) > 1 else ""
        known[key_of(head, body)] = mark if mark in CLASSES else "?"
    return known


def status_in_head(head: list[str]) -> str:
    """survivors.txt 의 머리(`### <함수>\t<이름>\t<상태>\t<분류>`)의 상태. 다른 꼴(diff 파일·씨앗)이면 빈 글."""
    return head[2] if len(head) >= 4 else ""


def parse_survivors(text: str) -> Counter[Key]:
    """survivors.txt(이 스크립트가 쓴 것) 또는 diff 파일을 열쇠의 다중집합으로. 시간초과는 빼고 센다(견주기 밖)."""
    return Counter(key_of(head, body) for head, body in blocks(text) if head and status_in_head(head) != "timeout")


def timeouts_in(text: str) -> int:
    return sum(1 for head, _ in blocks(text) if head and status_in_head(head) == "timeout")


def show(key: Key) -> str:
    return f"{key[0]} | " + " ⏎ ".join(key[1])


def compare(prev: Counter[Key], cur: Counter[Key]) -> tuple[Counter[Key], Counter[Key]]:
    """(새 생존, 사라진 생존)."""
    return cur - prev, prev - cur


# ── 실행 ─────────────────────────────────────────────────────────────


def read_meta(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k.strip()] = v.strip()
    return meta


def previous_run(history: Path, current: str, targets_hash: str) -> Path | None:
    best = None
    for d in sorted(p for p in history.iterdir() if p.is_dir()) if history.is_dir() else []:
        if d.name >= current:
            continue
        meta = read_meta(d / "meta.txt")
        if meta.get("targets_hash") == targets_hash and meta.get("mutmut_done") == "1" and (d / "survivors.txt").is_file():
            best = d
    return best


def statuses(results: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in results.splitlines():
        if ": " in line:
            name, status = line.strip().rsplit(": ", 1)
            out[name] = status
    return out


def run(args: dict[str, str]) -> int:
    res = Path(args["--run"])
    integration = args.get("--integration", "기본값 판 통합: 안 돌림")
    lines = [integration]
    if "--targets" in args:
        lines.append(args["--targets"])  # 대상 수와 지난 회(scripts/weekly.sh 의 check_fewer) — 맨 위 둘째 줄
    detail: list[str] = []
    if "--results" not in args:
        lines += ["새 생존: 안 돌림 (mutmut 국면 없음)", "사라진 생존: 안 돌림", "합계: mutmut 안 돌림", "분류 없는 생존: 안 돌림", "시간초과: 안 돌림"]
    else:
        status_of = statuses(Path(args["--results"]).read_text(encoding="utf-8"))
        diff_blocks = blocks(Path(args["--diffs"]).read_text(encoding="utf-8"))
        known_path = Path(args["--known"])
        known = parse_known(known_path.read_text(encoding="utf-8")) if known_path.is_file() else {}
        current: list[tuple[Key, str, str]] = []
        broken = []
        for head, body in diff_blocks:
            if any(line.startswith("!! ") for line in body):
                broken.append(head[0])
            current.append((key_of(head, body), head[0], status_of.get(head[0], "?")))
        current.sort()
        with (res / "survivors.txt").open("w", encoding="utf-8") as f:
            for key, name, status in current:
                f.write(f"### {key[0]}\t{name}\t{status}\t{known.get(key, '-')}\n")
                for line in key[1]:
                    f.write(line + "\n")
        # 시간초과는 견주기에서 뺀다(같은 코드에서도 killed↔timeout 이 회마다 갈린다 — 감독 처분 2026-10-16). 따로 센다
        cur = Counter(key for key, _, status in current if status != "timeout")
        timeouts = sum(1 for _, _, status in current if status == "timeout")
        timeout_line = f"시간초과: {timeouts} (견주기 밖 — 첫 회)"
        prev_dir = previous_run(Path(args["--history"]), res.name, args["--targets-hash"])
        counts = Counter(status_of.values())
        other = sum(v for k, v in counts.items() if k not in ("killed", *SURVIVING))
        unclassified = sum(1 for key, _, _ in current if key not in known)
        if prev_dir is None:
            lines.append("새 생존: 세지 않음 (첫 회 — 기준. 같은 대상 목록의 지난 회 없음)")
            lines.append("사라진 생존: 세지 않음 (첫 회)")
            new: Counter[Key] = Counter()
            gone: Counter[Key] = Counter()
        else:
            prev_text = (prev_dir / "survivors.txt").read_text(encoding="utf-8")
            prev = parse_survivors(prev_text)
            new, gone = compare(prev, cur)
            timeout_line = f"시간초과: {timeouts} (지난 회 {timeouts_in(prev_text)} · 견주기 밖)"
            lines.append(f"새 생존: {sum(new.values())} (지난 회 {prev_dir.name} 대비)")
            lines.append(f"사라진 생존: {sum(gone.values())} (지난 회 {prev_dir.name} 대비)")
        lines.append(
            f"합계: 변이 {len(status_of)} · 죽음 {counts['killed']} · 시간초과 {counts['timeout']} · 의심 {counts['suspicious']}"
            f" · 생존 {counts['survived']} · 그 밖 {other} · 벽시계 {args.get('--wall', '?')}초"
        )
        lines.append(
            f"분류 없는 생존: {unclassified} / {len(current)} (알려진 생존 "
            + (f"{known_path} 의 {len(known)} 블록)" if known_path.is_file() else f"없음 — {known_path})")
        )
        lines.append(timeout_line)
        detail.append(f"## 새 생존 ({sum(new.values())})")
        detail += [f"- {show(k)} [{known.get(k, '분류 없음')}] × {n}" for k, n in sorted(new.items())] or ["- 없음"]
        detail.append(f"\n## 사라진 생존 ({sum(gone.values())})")
        detail += [f"- {show(k)} × {n}" for k, n in sorted(gone.items())] or ["- 없음"]
        if broken:
            detail.append(f"\n## diff 를 못 뽑은 변이 ({len(broken)})")
            detail += [f"- {name}" for name in broken]
        detail.append(f"\n## 생존 전부 ({len(current)}, 열쇠 차례)")
        detail += [f"- [{known.get(k, '분류 없음')}] {status} {name} | " + " ⏎ ".join(k[1]) for k, name, status in current]
    (res / "summary.md").write_text("\n".join(lines + [""] + detail) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


# ── 자기 시험 ────────────────────────────────────────────────────────

A = "### esgapi.m.x_f__mutmut_{n}\n--- esgapi/m.py\n+++ esgapi/m.py\n@@ -1,3 +1,3 @@\n def f():\n-    return a and b\n+    return a or b\n"
A_SEED = "### esgapi.m.x_f 나 같은 뜻\n-    return a and b\n+    return a or b\n"
B = "### esgapi.m.x_g__mutmut_{n}\n-    x = 1\n+    x = 2\n"
A_IN_G = "### esgapi.m.x_g__mutmut_{n}\n-    return a and b\n+    return a or b\n"


def self_test() -> int:
    def ms(*parts: str) -> Counter[Key]:
        return parse_survivors("".join(parts))

    checks: list[tuple[str, bool]] = []
    new, gone = compare(ms(A.format(n=3)), ms(A.format(n=3), B.format(n=1)))
    checks.append(("① 새 것 하나", sum(new.values()) == 1 and sum(gone.values()) == 0 and next(iter(new))[0] == "esgapi.m.x_g"))
    new, gone = compare(ms(A.format(n=3), B.format(n=1)), ms(A.format(n=3)))
    checks.append(("② 사라진 것 하나", sum(new.values()) == 0 and sum(gone.values()) == 1))
    new, gone = compare(ms(A.format(n=3), A.format(n=4)), ms(A.format(n=3)))
    checks.append(("③ 같은 열쇠 둘 → 하나: 새 0·사라진 1", sum(new.values()) == 0 and sum(gone.values()) == 1))
    new, gone = compare(ms(A.format(n=3)), ms(A.format(n=9)))
    checks.append(("④ 번호만 바뀐 것은 같음", sum(new.values()) == 0 and sum(gone.values()) == 0))
    known = parse_known(A_SEED)
    cur = ms(A.format(n=7), B.format(n=1))
    marks = sorted(known.get(k, "-") for k in cur)
    checks.append(("⑤ 분류 붙이기(머리줄·@@ 가 있는 diff 와 없는 씨앗이 같은 열쇠)", marks == ["-", "나"]))
    new, gone = compare(ms(A.format(n=3)), ms(A_IN_G.format(n=3)))
    checks.append(("⑥ 함수가 다르면 diff 가 같아도 다른 열쇠", sum(new.values()) == 1 and sum(gone.values()) == 1))
    prev_txt = "### esgapi.m.x_f\tesgapi.m.x_f__mutmut_3\tsurvived\t-\n-    x = 1\n+    x = 2\n"
    cur_txt = prev_txt + "### esgapi.m.x_h\tesgapi.m.x_h__mutmut_1\ttimeout\t나\n-    a and b\n+    a or b\n"
    new, gone = compare(parse_survivors(prev_txt), parse_survivors(cur_txt))
    checks.append(
        ("⑦ 시간초과는 견주기 밖(따로 셈)", sum(new.values()) == 0 and sum(gone.values()) == 0 and timeouts_in(cur_txt) == 1)
    )
    with tempfile.TemporaryDirectory() as tmp:
        res = Path(tmp) / "2026-01-01-000000"
        res.mkdir()
        line = "대상 수: 61 (지난 회 없음)"
        with contextlib.redirect_stdout(io.StringIO()):
            run({"--run": str(res), "--history": tmp, "--integration": "기본값 판 통합: 안 돌림", "--targets": line})
        second = (res / "summary.md").read_text(encoding="utf-8").splitlines()[1]
    checks.append(("⑧ --targets 줄이 summary.md 둘째 줄에 그대로", second == line))
    for name, ok in checks:
        print(f"  {'통과' if ok else '★ 실패'} {name}")
    passed = all(ok for _, ok in checks)
    print(f"SELF_TEST={'PASS' if passed else 'FAIL'} {sum(ok for _, ok in checks)}/{len(checks)}")
    return 0 if passed else 1


def main(argv: list[str]) -> int:
    if argv[1:] == ["--self-test"]:
        return self_test()
    rest = argv[1:]
    if len(rest) % 2 or not rest:
        print(__doc__, file=sys.stderr)
        return 2
    args = dict(zip(rest[::2], rest[1::2]))
    need = ["--run", "--history"]
    if "--results" in args:
        need += ["--diffs", "--known", "--targets-hash"]
    missing = [k for k in need if k not in args]
    if missing:
        print(f"빠진 인자: {' '.join(missing)}", file=sys.stderr)
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
