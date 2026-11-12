"""파서 기준선 대조(밴드 PB1, MARC-TICK-122)의 명령줄: 합성 PDF 짓기·분해 산출 해시·고정값과 견주기.

── 뜻 ──
기준선은 esg-lab 커밋 2e2c2c4 의 `py/docparse` 를 pdfium 엔진으로 돌린 산출이다(MARC-RPT-4·PD1 MARC-TICK-46 의 측정이
그 판으로 잰 것이다). PB1 은 그 산출과 esg-app `docparse/` 의 산출이 같음을 보이고, 합성 PDF 의 산출을 해시로 얼렸다
(`tests/baseline/synthetic.sha256.json`). `tests/test_baseline.py` 가 그 고정값과 견주며, `scripts/verify.sh` 의
`lane_parser`(pytest)에 저절로 든다. 공개 보고서 A·B 의 대조는 저장소 밖(검증 감독이 가진 스크립트와 고정값)이다.

── 쓰는 법(백엔드 PX 와 그 뒤) ──
- 커밋마다 `scripts/verify.sh --fast`(또는 `uv run --project services/parser --frozen pytest -q services/parser`)를 돌린다.
- 병합 전에 검증 감독에게 공개 보고서 A·B 대조(b)를 다시 돌려 달라고 요청한다.
- 빨개지면 실패 글이 다른 부분의 이름을 찍는다: document.pages·sections·blocks·tables·rest(나열한 칸 밖 전부),
  char-places.containers·unlinked·rest. `pdf` 가 다르면 짓개(`tests/baseline_doc.py`)나 `tests/pdfbuild.py` 가 바뀐
  것이고 분해기 탓이 아니다.

── 고정값을 바꾸는 규칙 ──
- 분해기의 산출을 **일부러** 바꾸는 커밋만 고정값을 바꾼다. 같은 커밋에서 고친다.
- 커밋 메시지에 다른 부분의 이름과 까닭을 적는다. 고정값의 `_comment` 에 적힌 기준 커밋도 같이 고친다.
- 공개 보고서 고정값(저장소 밖)은 검증 감독에게 다시 돌려 달라고 요청한다.
- D4 의 쪽 수·시간 상한에 걸리게 일부러 지은 큰 문서는 대조 밖이다.

── 정규화 ──
`source.file_name` 하나만 상수 "<pdf>" 로 바꾼다(document 와 char-places 둘 다). 파일 이름은 짓는 자리에 따라 달라지고
쪽 내용과 무관하다. 그 밖의 칸은 전부 해시에 든다. 직렬화는
`json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))` 의 UTF-8 바이트이고 sha256 이다.

── 명령 ──
  python scripts/parser_baseline.py build <out.pdf> [--toc]        합성 PDF 를 짓는다(--toc: 목차 단 판)
  python scripts/parser_baseline.py build <out.pdf> --doc layout2 [--extra]
                                                                  번역 판(밴드 TRD1)의 합성 PDF(--extra: 앞에 문단 하나 더)
  python scripts/parser_baseline.py hash <parse 산출 폴더>          해시 JSON 을 stdout 에
  python scripts/parser_baseline.py check <parse 산출 폴더> <고정 JSON> <판 이름>
                                                                  같으면 0, 다르면 1 과 다른 부분 이름
산출 폴더는 `python -m docparse parse <pdf> --out <폴더> --places` 의 것(document.json·char-places.json)이다.
`hash`·`check` 는 표준 라이브러리만 쓰고 docparse 를 들이지 않는다: 어느 분해기의 산출이든 같은 코드로 잰다.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

FILE_NAME_PLACEHOLDER = "<pdf>"
DOCUMENT_PARTS = ("pages", "sections", "blocks", "tables")
PLACES_PARTS = ("containers", "unlinked")
PART_NAMES = (
    *(f"document.{k}" for k in DOCUMENT_PARTS),
    "document.rest",
    *(f"char-places.{k}" for k in PLACES_PARTS),
    "char-places.rest",
)


def normalize(obj: dict) -> dict:
    """`source.file_name` 을 상수로 바꾼 얕은 사본. 다른 칸은 그대로다."""
    out = dict(obj)
    if isinstance(out.get("source"), dict):
        out["source"] = {**out["source"], "file_name": FILE_NAME_PLACEHOLDER}
    return out


def digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _split(obj: dict, named: tuple[str, ...], prefix: str) -> dict[str, str]:
    parts = {f"{prefix}.{k}": digest(obj.get(k)) for k in named}
    parts[f"{prefix}.rest"] = digest({k: v for k, v in obj.items() if k not in named})
    return parts


def hashes(document: dict, places: dict) -> dict:
    """{"all", "document", "char-places", "parts": {부분 이름: 해시}}. 입력은 분해 산출(dict) 그대로."""
    doc, pl = normalize(document), normalize(places)
    return {
        "all": digest({"document": doc, "char-places": pl}),
        "document": digest(doc),
        "char-places": digest(pl),
        "parts": {**_split(doc, DOCUMENT_PARTS, "document"), **_split(pl, PLACES_PARTS, "char-places")},
    }


def hash_dir(out_dir: Path) -> dict:
    document = json.loads((out_dir / "document.json").read_text(encoding="utf-8"))
    places = json.loads((out_dir / "char-places.json").read_text(encoding="utf-8"))
    return hashes(document, places)


def differing(got: dict, want: dict) -> list[str]:
    """다른 부분의 이름(부분 해시 → 전체 해시 차례). 같으면 빈 목록."""
    names = [n for n in PART_NAMES if got["parts"].get(n) != want["parts"].get(n)]
    names += [k for k in ("document", "char-places", "all") if got.get(k) != want.get(k)]
    return names


def _build(out: Path, toc: bool, doc: str = "baseline", extra: bool = False) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tests import baseline_doc, layout2_doc  # 짓개는 tests/ 에 있다(pdfbuild 와 나란히)

    out.write_bytes(layout2_doc.build(extra_block=extra) if doc == "layout2" else baseline_doc.build(toc=toc))
    print(hashlib.sha256(out.read_bytes()).hexdigest())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="parser_baseline", description="파서 기준선 대조(PB1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="합성 PDF 를 짓고 그 sha256 을 찍는다")
    b.add_argument("out")
    b.add_argument("--toc", action="store_true", help="목차 단 판")
    b.add_argument(
        "--doc", choices=("baseline", "layout2"), default="baseline", help="짓개 (layout2: tests/layout2_doc.py)"
    )
    b.add_argument("--extra", action="store_true", help="layout2 짓개의 앞에 문단 하나 더한 판")
    h = sub.add_parser("hash", help="분해 산출 폴더의 해시 JSON")
    h.add_argument("dir")
    c = sub.add_parser("check", help="분해 산출 폴더를 고정 JSON 의 한 판과 견준다")
    c.add_argument("dir")
    c.add_argument("fixed")
    c.add_argument("variant")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        _build(Path(a.out), a.toc, a.doc, a.extra)
        return 0
    if a.cmd == "hash":
        print(json.dumps(hash_dir(Path(a.dir)), ensure_ascii=False, indent=1, sort_keys=True))
        return 0
    want = json.loads(Path(a.fixed).read_text(encoding="utf-8"))["variants"][a.variant]
    diff = differing(hash_dir(Path(a.dir)), want)
    if diff:
        print(f"DIFF {a.variant}: {', '.join(diff)}")
        return 1
    print(f"SAME {a.variant}: {len(PART_NAMES)}/{len(PART_NAMES)} 부분")
    return 0


if __name__ == "__main__":
    sys.exit(main())
