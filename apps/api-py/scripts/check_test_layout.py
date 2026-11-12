"""테스트 자리 규칙의 검사(밴드 T1a). 테스트는 `esgapi/<모듈>/tests/` 안에서 소스의 폴더 구조를 비춘다.

    사용(apps/api-py 에서): uv run --frozen python scripts/check_test_layout.py [--list]

대상은 `esgapi/*/tests/**` 아래 `.py` — git 이 추적하는 것과 새 파일(무시 목록 밖)에서, 작업 트리에 있는 것만.
소스도 같은 목록에서 본다(`tests`·`migrations`·`__pycache__` 아래는 소스가 아니다). git 은 저장소 뿌리에 못 박아
부른다(`git -C <뿌리>`): 워크트리의 커밋 훅에는 GIT_DIR 이 와 있어, 하위 폴더에서 부른 git 은 그 폴더를 뿌리로 본다.

`T = esgapi/<모듈>/tests/<D>/test_<stem>.py`(`<D>` 는 비어도 된다), 그 소스 자리 `S = esgapi/<모듈>/<D>`:
  R1  `<D>` 가 비어 있지 않으면 `S` 가 `.py` 를 품은 소스 폴더여야 한다.
  R2  `stem` 을 `_` 로 나눈 앞마디 `p`(한 마디, 두 마디, … 차례로)마다: `S/p.py` 가 있으면 비춘 것(끝).
      `S/p/` 가 소스 꾸러미면 어김(`tests/<D>/<p>/` 로). `S` 아래 더 깊은 자리에 `p` 꾸러미나 `p.py` 가 있으면 어김.
      아무것에도 안 걸리면 자유(소스 하나를 비추지 않는 검사 파일).
  R3  `tests/` 와 파일 사이의 모든 하위 폴더에 `__init__.py`(중간 폴더 포함).
  `test_` 로 시작하지 않는 `.py`(conftest·도우미)는 R3 만 본다.
  `tests/` 아래 `data` 폴더와 그 아래 전부는 셋 다 안 본다(자료 자리).

허용 목록 `scripts/test-layout-allow.txt`(한 줄에 `esgapi/…` 하나, `#` 주석): 옛 평평한 파일. 목록의 파일은 R1·R2 를
안 본다. 규칙에 맞는데 목록에 있으면 어김(「필요 없는 허용」 — 옮겼으면 그 줄을 지운다. 목록은 줄어들기만 한다).
목록에 있는데 없는 파일은 어김이 아니고 「허용인데 없음」으로 센다.

출력: 셈 한 줄 + 어김마다 `경로 ← 까닭`. 어김이 있으면 종료 1, 대상을 못 읽으면(git 실패·대상 0) 종료 2.
`--list` 는 테스트 파일마다 판정(비춤·자유·허용·어김)을 더 찍는다. 표준 라이브러리만 쓴다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # 저장소 뿌리(scripts → api-py → apps → 뿌리)
PREFIX = "apps/api-py/"  # 뿌리에서 본 이 꾸러미의 자리
PKG = ROOT / PREFIX
ALLOW = Path(__file__).with_name("test-layout-allow.txt")
NOT_SOURCE = frozenset({"tests", "migrations", "__pycache__"})
PATHSPEC = f":(glob){PREFIX}esgapi/**"


def listed() -> set[str]:
    """`esgapi/**` 아래 파일(apps/api-py 기준 경로). 추적 + 새 파일, 작업 트리에 있는 것만."""
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", PATHSPEC],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        print(f"git ls-files 가 실패했다({out.returncode}): {out.stderr.strip()}")
        sys.exit(2)
    paths = {p.removeprefix(PREFIX) for p in out.stdout.split("\0") if p.startswith(PREFIX)}
    return {p for p in paths if (PKG / p).is_file()}


def read_allow() -> list[str]:
    if not ALLOW.is_file():
        return []
    rows = (line.split("#", 1)[0].strip() for line in ALLOW.read_text(encoding="utf-8").splitlines())
    return [r for r in rows if r]


class Tree:
    """소스 쪽의 모양: `.py` 파일들과 그것을 바로 품은 폴더들."""

    def __init__(self, files: set[str]) -> None:
        self.files = {f for f in files if f.endswith(".py") and not NOT_SOURCE.intersection(f.split("/")[:-1])}
        self.pkgs = {f.rsplit("/", 1)[0] for f in self.files}

    def deeper(self, base: str, name: str) -> list[str]:
        """`base` 아래 두 단 이상 깊은 자리의 `name` 꾸러미나 `name.py`."""
        hits: list[str] = []
        for f in self.files:
            if f.startswith(base + "/") and f.count("/") - base.count("/") >= 2 and f.endswith("/" + name + ".py"):
                hits.append(f)
        for d in self.pkgs:
            if d.startswith(base + "/") and d.count("/") - base.count("/") >= 2 and d.endswith("/" + name):
                hits.append(d + "/")
        return sorted(hits)


def judge(path: str, tree: Tree) -> tuple[str, str]:
    """R1·R2 의 판정: ("mirror"|"free"|"bad", 까닭)."""
    parts = path.split("/")  # esgapi, 모듈, tests, *D, 파일
    d = parts[3:-1]
    src = "/".join(["esgapi", parts[1], *d])
    if d and src not in tree.pkgs:
        return "bad", f"R1 소스 폴더 {src}/ 가 없다"
    toks = parts[-1].removesuffix(".py").removeprefix("test_").split("_")
    for k in range(1, len(toks) + 1):
        p = "_".join(toks[:k])
        if f"{src}/{p}.py" in tree.files:
            return "mirror", f"{src}/{p}.py"
        if f"{src}/{p}" in tree.pkgs:
            return "bad", f"R2 소스 꾸러미 {src}/{p}/ 가 있다 → {'/'.join(parts[:-1])}/{p}/ 로"
        hits = tree.deeper(src, p)
        if hits:
            return "bad", f"R2 소스가 {', '.join(hits[:2])} 에 있다"
    return "free", ""


def main() -> int:
    show = "--list" in sys.argv[1:]
    unknown = [a for a in sys.argv[1:] if a != "--list"]
    if unknown:
        print(f"모르는 인자: {' '.join(unknown)}  (사용: check_test_layout.py [--list])")
        return 2
    files = listed()
    tree = Tree(files)
    allow = read_allow()
    allowed = set(allow)
    tests = sorted(f for f in files if f.endswith(".py") and len(f.split("/")) >= 4 and f.split("/")[2] == "tests")
    if not tests:
        print(f"대상이 0 이다: {PREFIX}esgapi/*/tests/ 아래 .py 를 못 읽었다(뿌리 {ROOT})")
        return 2

    n = mirrored = free = held = 0
    bad: list[tuple[str, str]] = []
    rows: list[str] = []
    for path in tests:
        parts = path.split("/")
        d = parts[3:-1]
        if "data" in d:
            continue
        for i in range(1, len(d) + 1):
            init = "/".join([*parts[:3], *d[:i], "__init__.py"])
            if init not in files:
                bad.append((path, f"R3 {init} 가 없다"))
                break
        if not parts[-1].startswith("test_"):
            continue
        n += 1
        kind, why = judge(path, tree)
        if path in allowed:
            if kind == "bad":
                held += 1
                rows.append(f"  허용  {path}")
            else:
                bad.append((path, "필요 없는 허용 — 규칙에 맞는다. test-layout-allow.txt 에서 이 줄을 지운다"))
                rows.append(f"  어김  {path}")
        elif kind == "bad":
            bad.append((path, why))
            rows.append(f"  어김  {path}")
        elif kind == "mirror":
            mirrored += 1
            rows.append(f"  비춤  {path} ↔ {why}")
        else:
            free += 1
            rows.append(f"  자유  {path}")
    present = set(tests)
    missing = sorted(a for a in allowed if a not in present)

    counts = f"비춘 것 {mirrored} · 자유 {free} · 허용 {held} · 허용인데 없음 {len(missing)} · 어김 {len(bad)}"
    print(f"테스트 파일 {n} · {counts}")
    for path, why in bad:
        print(f"{path} ← {why}")
    for path in missing:
        print(f"(허용인데 없음) {path}")
    if show:
        print("\n".join(rows))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
