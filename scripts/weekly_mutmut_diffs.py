"""mutmut 3.8.0 의 변이 diff 를 이름 목록으로 한 프로세스에서 뽑는다(scripts/weekly.sh 가 부른다).

    사용(사본의 apps/api-py 에서 — mutants/ 와 setup.cfg 가 있는 곳):
        uv run --frozen --with mutmut==3.8.0 python -I <저장소>/scripts/weekly_mutmut_diffs.py <이름 목록 파일>

이름마다 `mutmut show` 를 따로 부르면 매번 uv 와 mutmut 을 띄우는 값이 붙는다. 여기서는 mutmut 3.8.0 의
`mutmut.mutation.diff_apply.get_diff_for_mutant(이름, path=…)` 를 한 번 띄운 프로세스에서 부른다(`mutmut show` 가
부르는 것과 같은 함수). 이름 → 원본 파일은 `walk_mutatable_files()` 와 `SourceFileMutationData.load()` 로 한 번만
훑는다(`find_mutant` 는 이름마다 전부를 다시 훑는다). 판은 핀(mutmut==3.8.0)으로 고정 — 판이 바뀌면 이 자리를 다시 본다.

출력(표준 출력): 이름마다 `### <이름>` 한 줄 뒤에 그 diff(머리줄 `---`/`+++`·`@@` 포함 그대로). 못 뽑은 이름은
`### <이름>` 뒤에 `!! <까닭>` 한 줄. 끝 줄(표준 오류) `DIFFS=<뽑음>/<전체>`. 하나라도 못 뽑으면 1.
표준 라이브러리와 mutmut 만 쓴다.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("사용: python -I scripts/weekly_mutmut_diffs.py <이름 목록 파일>", file=sys.stderr)
        return 2
    names = [line.strip() for line in Path(argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]

    from mutmut.mutation.data import SourceFileMutationData
    from mutmut.mutation.diff_apply import get_diff_for_mutant
    from mutmut.utils.file_utils import walk_mutatable_files

    path_of: dict[str, Path] = {}
    for path in walk_mutatable_files():
        data = SourceFileMutationData(path=path)
        data.load()
        for key in data.exit_code_by_key:
            path_of[key] = path

    done = 0
    for name in names:
        print(f"### {name}")
        path = path_of.get(name)
        if path is None:
            print("!! mutmut 의 결과에 없는 이름")
            continue
        try:
            print(get_diff_for_mutant(name, path=path))
        except Exception as err:  # noqa: BLE001 — 하나가 깨져도 나머지는 뽑는다(까닭을 남긴다)
            print(f"!! {type(err).__name__}: {err}")
            continue
        done += 1
    print(f"DIFFS={done}/{len(names)}", file=sys.stderr)
    return 0 if done == len(names) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
