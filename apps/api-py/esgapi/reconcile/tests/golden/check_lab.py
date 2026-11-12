"""네 보고서 + 지은 문서에서 「같은 입력에서 TS = 파이썬」을 잰다. 컨테이너 없이 돈다.

    실행: (cd apps/api-py && uv run python -m esgapi.reconcile.tests.golden.check_lab [--input <폴더>] [--digest
    <파일>] [--ts <폴더>])
          앞서 make-golden.sh 가 TS 덤프를 .lab-golden/ts/ 에 만들어 두어야 한다.
    --input         문서마다 <문서>/document.json · char-places.json 이 든 폴더. 기본은 esg-lab 의 밴드 C1 산출
    (ESG_LAB 이 있을 때)
    --digest        건수와 해시를 적어 둔 파일. 기본은 이 폴더의 lab-digest.json. 상자 구획의 것은 그 곁의
    <이름>.places.json
    --ts            TS 덤프가 든 폴더. 기본은 apps/api-py/.lab-golden/ts
    --write-digest  견주지 않고 지금 값으로 digest 파일을 새로 쓴다(입력을 바꿨을 때. 예: PD2 병합 뒤 pdfium 산출)

재는 것, 문서마다:
  1. 입력 파일의 sha256 이 digest 와 같은가 (다르거나 없으면 건너뛰지 않고 **실패**한다)
  2. 구획 여덟이 TS 덤프와 **값 전체 일치**하는가 (건수가 아니라 값. 처음 갈리는 자리를 적는다)
  3. 구획의 건수와 해시가 digest 와 같은가
지은 문서는 거기에 구획 둘(dec·notation)을 더 보고, 방금 만든 TS 덤프가 저장소에 둔 것(synthetic/ts-dump.json)과
같은지도 본다.

구획은 두 묶음이다: 숫자 뽑기 일곱(`dump.py`, digest 는 lab-digest.json)과 상자 하나(`dump_places.py`,
lab-digest.places.json).
상자 묶음은 `calc/places.py` 가 있을 때만 잰다(커밋 경계 ① 에는 없다).

★ 무효 조건: 입력은 git 밖이다(기본은 esg-lab `out/band-C1/places`, 2026-10-05 밴드 C1 의 산출, pymupdf 엔진).
  esg-app 의 파서(pdfium)의 산출은 lab-digest.pdfium.json 과 쟀다(README.md). main 의 게이트(verify.sh)는 되재지 않는다.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from esgapi.reconcile.tests.golden import dump

HERE = Path(__file__).resolve().parent
API_PY = HERE.parents[3]
_LAB = os.environ.get("ESG_LAB")
DEFAULT_INPUT = Path(_LAB) / "out" / "band-C1" / "places" if _LAB else None
DOCS = ("kb_2025_kor", "kb_2025_databook_kor", "samsung_2026_kor", "cosmax_2025_kor")
Json = Any


@dataclass(frozen=True)
class Group:
    """구획의 묶음 하나: 무슨 입력을 읽어 무슨 구획을 내는가, digest 를 어느 파일에 두는가."""

    name: str
    sections: tuple[str, ...]
    case_sections: tuple[str, ...]  # 지은 문서에만 더 붙는 구획
    inputs: tuple[str, ...]
    digest_suffix: str
    run: Callable[[dict[str, Json], str], dict[str, Json]]
    run_cases: Callable[[Json], dict[str, Json]] | None


def groups() -> list[Group]:
    found = [
        Group(
            "numbers",
            dump.SECTIONS,
            dump.CASE_SECTIONS,
            ("document.json",),
            "",
            lambda files, doc: dump.dump_document(files["document.json"], doc),
            dump.dump_cases,
        )
    ]
    if importlib.util.find_spec("esgapi.reconcile.calc.places") is not None:
        places: Any = importlib.import_module("esgapi.reconcile.tests.golden.dump_places")
        found.append(
            Group(
                "places",
                places.SECTIONS,
                (),
                ("document.json", "char-places.json"),
                ".places",
                lambda files, doc: places.dump_places(files["document.json"], files["char-places.json"], doc),
                None,
            )
        )
    return found


def digest_path(base: Path, group: Group) -> Path:
    return base.with_name(f"{base.stem}{group.digest_suffix}{base.suffix}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


def sections_digest(sections: tuple[str, ...], value: dict[str, Json]) -> dict[str, Json]:
    return {name: {"count": dump.size(name, value[name]), "sha256": dump.digest(value[name])} for name in sections}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--digest", type=Path, default=HERE / "lab-digest.json")
    parser.add_argument("--ts", type=Path, default=API_PY / ".lab-golden" / "ts")
    parser.add_argument("--write-digest", action="store_true")
    args = parser.parse_args()
    if args.input is None:
        parser.error("--input 을 주거나 환경 변수 ESG_LAB(esg-lab 저장소의 경로)를 준다")

    all_groups = groups()
    section_total = sum(len(group.sections) for group in all_groups)
    problems: list[str] = []
    found: dict[str, dict[str, Json]] = {group.name: {"documents": {}, "synthetic": {}} for group in all_groups}
    expected: dict[str, Json] = {}
    if not args.write_digest:
        for group in all_groups:
            path = digest_path(args.digest, group)
            if path.is_file():
                expected[group.name] = read_json(path)
            else:
                problems.append(f"digest 파일이 없다: {path}")
    total_facts = 0
    total_boxes = 0
    documents_done = 0

    for doc in DOCS:
        ts_path = args.ts / f"{doc}.json"
        names = sorted({name for group in all_groups for name in group.inputs})
        missing = [str(args.input / doc / name) for name in names if not (args.input / doc / name).is_file()]
        if missing or not ts_path.is_file():
            problems.append(f"{doc}: 입력이 없다 — {', '.join(missing) or ts_path}")
            continue
        files = {name: read_json(args.input / doc / name) for name in names}
        hashes = {name: sha256_file(args.input / doc / name) for name in names}
        ts = read_json(ts_path)
        same = 0
        seconds = 0.0
        facts = 0
        boxes: int | None = None
        for group in all_groups:
            started = time.perf_counter()
            py = group.run(files, doc)
            seconds += time.perf_counter() - started
            entry = {
                "inputs": {name: hashes[name] for name in group.inputs},
                "sections": sections_digest(group.sections, py),
            }
            found[group.name]["documents"][doc] = entry
            for section in group.sections:
                difference = dump.first_difference(ts.get(section), py[section], section)
                if difference is None:
                    same += 1
                else:
                    problems.append(f"{doc}: TS 와 다르다 — {difference}")
            if "facts" in py:
                facts = len(py["facts"])
            if "places" in py:
                boxes = dump.size("places", py["places"])
            if not args.write_digest and group.name in expected:
                want = expected[group.name].get("documents", {}).get(doc)
                if want is None:
                    problems.append(f"{doc}: digest({group.name})에 없다")
                elif want["inputs"] != entry["inputs"]:
                    problems.append(
                        f"{doc}: 입력의 sha256 이 digest({group.name})와 다르다(다른 산출이다. 건너뛰지 않는다)"
                    )
                elif want["sections"] != entry["sections"]:
                    changed = [name for name in group.sections if want["sections"].get(name) != entry["sections"][name]]
                    problems.append(f"{doc}: 건수·해시가 digest 와 다르다 — {', '.join(changed)}")
        documents_done += 1
        total_facts += facts
        box_text = "(이 커밋에 없음)" if boxes is None else f"{boxes}/{facts}"
        total_boxes += boxes or 0
        print(
            f"{doc}: 값 후보 {facts} · 상자 {box_text} · TS 와 같은 구획 {same}/{section_total} · 파이썬 {seconds:.2f}s"
        )

    # 지은 문서: 입력이 저장소에 있다. 방금 만든 TS 덤프 = 저장소의 TS 덤프 = 파이썬.
    synthetic = HERE / "synthetic"
    committed = read_json(synthetic / "ts-dump.json")
    fresh_path = args.ts / "synthetic.json"
    if not fresh_path.is_file():
        problems.append(f"synthetic: TS 덤프가 없다 — {fresh_path}")
    else:
        difference = dump.first_difference(read_json(fresh_path), committed, "synthetic")
        if difference is not None:
            problems.append(f"synthetic: 방금 만든 TS 덤프가 저장소의 것과 다르다 — {difference}")
    files = {name: read_json(synthetic / name) for name in ("document.json", "char-places.json")}
    same = 0
    synthetic_total = 0
    for group in all_groups:
        py = group.run(files, "synthetic")
        if group.run_cases is not None:
            py = {**py, **group.run_cases(read_json(synthetic / "cases.json"))}
        sections = (*group.sections, *group.case_sections)
        synthetic_total += len(sections)
        for section in sections:
            difference = dump.first_difference(committed.get(section), py[section], section)
            if difference is None:
                same += 1
            else:
                problems.append(f"synthetic: TS 와 다르다 — {difference}")
        found[group.name]["synthetic"] = {"sections": sections_digest(sections, py)}
        if (
            not args.write_digest
            and group.name in expected
            and expected[group.name].get("synthetic") != found[group.name]["synthetic"]
        ):
            problems.append(f"synthetic: 건수·해시가 digest({group.name})와 다르다")
    print(f"synthetic: TS 와 같은 구획 {same}/{synthetic_total}")

    has_places = any("places" in group.sections for group in all_groups)
    box_total = f"{total_boxes}/{total_facts}" if has_places else "(이 커밋에 없음)"
    print(f"합: 값 후보 {total_facts} · 상자 {box_total} · 문서 {documents_done}/{len(DOCS)}")
    if args.write_digest:
        if problems:
            print("\n".join(f"★ {line}" for line in problems))
            print("TS 와 다른 채로는 digest 를 쓰지 않는다")
            return 1
        for group in all_groups:
            path = digest_path(args.digest, group)
            path.write_text(json.dumps(found[group.name], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"digest 를 썼다: {path}")
        return 0
    for line in problems:
        print(f"★ {line}")
    print("골든: 같다" if not problems else f"골든: 다르다 ({len(problems)}건)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
