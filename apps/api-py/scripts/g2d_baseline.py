"""밴드 G2d ②-0 바닥 기준물을 쓰거나 대조한다(도우미 esgapi/greenwash/tests/flows/g2d_baseline.py 의 갈래 다섯).

    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python scripts/g2d_baseline.py [--out <폴더>] [--check]

--out 이 없으면 esgapi/greenwash/tests/data/g2d-baseline/<갈래>.json 에 쓴다(바닥 코드로 한 번 — 커밋된 파일은 고치지
않는다, 발주서 §1-5). --check 는 쓰지 않고 지금 코드로 지은 바이트가 커밋된 파일과 같은지 보고, 다르면 종료 코드 1.
공급사는 모의뿐이라 네트워크·키 0 이다.
"""

import argparse
import sys
from pathlib import Path

from esgapi.greenwash.tests.flows import g2d_baseline as baseline


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, default=baseline.DATA)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    out: Path = args.out
    differ: list[str] = []
    for branch in baseline.BRANCHES:
        built = baseline.dump(baseline.build(branch))
        if args.check:
            if built != baseline.stored(branch):
                differ.append(branch)
            continue
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{branch}.json").write_bytes(built)
    for branch in differ:
        sys.stderr.write(f"기준물과 다름: {branch}\n")
    sys.stdout.write(
        f"G2D_BASELINE {'check' if args.check else 'write'} branches={len(baseline.BRANCHES)} differ={len(differ)}\n"
    )
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
