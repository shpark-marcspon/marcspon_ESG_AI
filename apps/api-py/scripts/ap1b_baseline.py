"""밴드 AP1b ①-0 바닥 기준물을 쓰거나 대조한다(도우미 esgapi/greenwash/tests/flows/ap1b_baseline.py 의 갈래 아홉).

    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python scripts/ap1b_baseline.py [--out <폴더>] [--check]

--out 이 없으면 esgapi/greenwash/tests/data/ap1b-baseline/ 에 쓴다(BASE 코드로 한 번 — 커밋된 파일은 고치지 않는다).
--check 는 쓰지 않고 versions 갈래 여섯(v1~v6)은 지금 코드로 다시 지은 바이트가, @2 몸 셋(p1~p3)은 파일 sha256 이
README 표와 같은지 본다(p1~p3 는 다시 짓지 않는다 — 발주서 M2). 다르면 종료 코드 1. 공급사·키·네트워크 0.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

from esgapi.greenwash.tests.flows import ap1b_baseline as baseline

ROW = re.compile(r"^\| `(?P<file>[^`]+\.json)` \| `(?P<sha>[0-9a-f]{64})` \|", re.MULTILINE)


def readme_shas(folder: Path) -> dict[str, str]:
    return {m["file"]: m["sha"] for m in ROW.finditer((folder / "README.md").read_text(encoding="utf-8"))}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=baseline.DATA)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    out: Path = args.out
    differ: list[str] = []
    if args.check:
        shas = readme_shas(baseline.DATA)
        for branch in baseline.VERSIONS:
            name = baseline.versions_file(branch)
            if baseline.dump(baseline.versions_of(branch)) != (baseline.DATA / name).read_bytes():
                differ.append(name)
        for branch in baseline.PROMPT_MODELS:
            name = baseline.prompt_file(branch)
            found = hashlib.sha256((baseline.DATA / name).read_bytes()).hexdigest()
            if shas.get(name) != found:
                differ.append(name)
    else:
        out.mkdir(parents=True, exist_ok=True)
        for branch in baseline.VERSIONS:
            (out / baseline.versions_file(branch)).write_bytes(baseline.dump(baseline.versions_of(branch)))
        for branch in baseline.PROMPT_MODELS:
            (out / baseline.prompt_file(branch)).write_bytes(baseline.dump(baseline.prompt_v2(branch)))
        for path in sorted(out.glob("*.json")):
            sys.stdout.write(f"| `{path.name}` | `{hashlib.sha256(path.read_bytes()).hexdigest()}` |\n")
    for name in differ:
        sys.stderr.write(f"기준물과 다름: {name}\n")
    total = len(baseline.VERSIONS) + len(baseline.PROMPT_MODELS)
    sys.stdout.write(f"AP1B_BASELINE {'check' if args.check else 'write'} files={total} differ={len(differ)}\n")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
