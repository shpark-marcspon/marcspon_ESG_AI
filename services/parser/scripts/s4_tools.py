"""`scripts/section4-PD2.sh` 가 부르는 견주기 도구. 표준 라이브러리만 쓴다. 판정이 틀리면 종료 코드 1.

python s4_tools.py sha <골든 폴더>                 골든 여덟 파일의 sha256 == PD1 이 적어 둔 여덟
python s4_tools.py same <이쪽 폴더> <골든 폴더>    여덟 파일이 JSON 값으로 같은가, 수의 표, U+0007 0자
python s4_tools.py split <HTTP 답 폴더> <낼 폴더>  HTTP 답(<문서>.json)을 document.json·char-places.json 으로 가른다
python s4_tools.py score <앱 score.json> <골든 score.json>
python s4_tools.py facts <facts 폴더>              값 후보의 수 == 2,938 · 1,292 · 2,049 · 2,476
python s4_tools.py difflines <esg-lab> <커밋> <docparse 폴더>   파일마다 원본과의 diff 줄 수
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

DOCS = ["kb_2025_kor", "kb_2025_databook_kor", "samsung_2026_kor", "cosmax_2025_kor"]
FILES = ["document.json", "char-places.json"]

# esg-lab.worktrees/PD1/out/band-PD1/s4c/pdfium/sha256.txt (2026-10-07) 에서 발주서가 옮긴 값.
PD1_SHA256 = {
    "kb_2025_kor/document.json": "0ad1a66097f70d98b9a861571de8a4129051db84de358bfeca3771da7e5f82e2",
    "kb_2025_databook_kor/document.json": "c60c514dd92c5fec1ad0e82bee676fd59ea1256218b70f6c3839b190c22b6a96",
    "samsung_2026_kor/document.json": "3c00c599a78175fa9ba84cae8574333ee125191543fb69e89ff94c4fd9932bd5",
    "cosmax_2025_kor/document.json": "c11972565872e82faa43e366b3335254538423a05fcff525e9e0c68b6ce05736",
    "kb_2025_kor/char-places.json": "d3fd8f04652f1903483ceb4f32779717802a7b7849922cbcb7bff2696a05670a",
    "kb_2025_databook_kor/char-places.json": "d65d98e8dbed6eeca139930aaf78b3c930dfa7072b808cac5737bd92c9cd3b0f",
    "samsung_2026_kor/char-places.json": "d476df0e04caaa486478be3ffc498c7fa1567c14bd3768c03f5bc2ca80ae2562",
    "cosmax_2025_kor/char-places.json": "951562398717c34d0e56d6c33da665e7211e8b0d2c472720df908d690b9bf51c",
}
# PD1 이 잰 수 (발주서 「원본 요약」의 표): 쪽, 섹션, 블록, 표, 칸, 그릇, 못 이은 그릇, 글자 층 없는 쪽(쪽 번호들)
PD1_COUNTS = {
    "kb_2025_kor": (112, 17, 1572, 146, 9901, 7372, 0, [112]),
    "kb_2025_databook_kor": (79, 19, 1937, 203, 6665, 7153, 0, [79]),
    "samsung_2026_kor": (89, 56, 2339, 140, 5209, 6084, 0, [89]),
    "cosmax_2025_kor": (173, 60, 4905, 228, 8667, 10821, 0, [173]),
}
FACTS = {"kb_2025_kor": 2938, "kb_2025_databook_kor": 1292, "samsung_2026_kor": 2049, "cosmax_2025_kor": 2476}
# 분해 규칙과 엔진: 원본과 한 줄도 달라서는 안 되는 파일 열하나.
RULE_FILES = [
    "layout.py",
    "tables.py",
    "tables_lines.py",
    "tables_text.py",
    "table_model.py",
    "blocks.py",
    "sections.py",
    "reading_order.py",
    "charplaces.py",
    "engine/types.py",
    "engine/pdfium_engine.py",
]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_sha(gold):
    bad = 0
    for name, want in PD1_SHA256.items():
        got = hashlib.sha256((Path(gold) / name).read_bytes()).hexdigest()
        print(f"{'같음' if got == want else '다름'}  {got}  {name}")
        bad += got != want
    print(f"골든의 sha256 이 PD1 기록과 같은 것: {len(PD1_SHA256) - bad}/{len(PD1_SHA256)}")
    return bad


def counts(document, places):
    return (
        len(document["pages"]),
        len(document["sections"]),
        len(document["blocks"]),
        len(document["tables"]),
        sum(len(row) for t in document["tables"] for row in t["cells"]),
        len(places["containers"]),
        len(places["unlinked"]),
        [p["page"] for p in document["pages"] if p["text_layer"] == "none"],
    )


def cmd_same(mine, gold):
    bad, same = 0, 0
    print("| 문서 | 쪽 | 섹션 | 블록 | 표 | 칸 | 그릇 | 못 이은 그릇 | 글자 층 없는 쪽 | PD1 의 수와 | U+0007 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|")
    rows = []
    for doc in DOCS:
        loaded = {}
        for name in FILES:
            a_path, b_path = Path(mine) / doc / name, Path(gold) / doc / name
            a, b = load(a_path), load(b_path)
            loaded[name] = a
            equal = a == b
            same += equal
            bad += not equal
            rows.append(
                f"{'같음' if equal else '다름'}  {doc}/{name}  (바이트까지 {'같음' if a_path.read_bytes() == b_path.read_bytes() else '다름'})"
            )
        bell = sum(
            json.dumps(loaded[name], ensure_ascii=False).count("\\u0007")
            + json.dumps(loaded[name], ensure_ascii=False).count("\u0007")
            for name in FILES
        )
        got = counts(loaded["document.json"], loaded["char-places.json"])
        match = got == PD1_COUNTS[doc]
        bad += (not match) + (bell != 0)
        print(f"| {doc} | " + " | ".join(str(v) for v in got) + f" | {'같음' if match else '다름'} | {bell} |")
    print("\n".join(rows))
    print(f"JSON 값으로 같은 것: {same}/{len(DOCS) * len(FILES)}")
    return bad


def cmd_split(http, out):
    bad = 0
    for doc in DOCS:
        body = load(Path(http) / f"{doc}.json")
        keys = sorted(body)
        places = body.get("charPlaces")
        ok = keys == ["charPlaces", "document"] and places is not None
        print(
            f"{'있음' if ok else '없음'}  {doc}: 키 {keys}, charPlaces 의 그릇 {len(places['containers']) if places else '-'}"
        )
        bad += not ok
        if ok:
            target = Path(out) / doc
            target.mkdir(parents=True, exist_ok=True)
            (target / "document.json").write_text(json.dumps(body["document"], ensure_ascii=False), encoding="utf-8")
            (target / "char-places.json").write_text(json.dumps(places, ensure_ascii=False), encoding="utf-8")
    return bad


def cmd_score(mine, gold):
    a, b = load(mine), load(gold)
    equal = a == b
    print(f"score JSON: {'같음' if equal else '다름'} (전략 {sorted(a)})")
    auto = [a["auto"]["by_report"][r]["recall"] for r in sorted(a["auto"]["by_report"])]
    text = [a["text"]["all"][k] for k in ("recall", "recall_strict", "recall_position", "numeric_recall")]
    cells, tables = a["auto"]["all"]["gold_cells"], a["auto"]["all"]["tables"]
    print(f"정답 표 {tables}개 {cells}칸. auto 의 보고서별 일치율 {auto} (cosmax, kb, kb_databook, samsung)")
    print(f"text 의 전체 일치율(느슨·엄격·자리·숫자) {text}")
    want = auto == [1.0] * 4 and text == [0.8984, 0.7721, 0.74, 0.9358] and (tables, cells) == (15, 1496)
    print(f"PD1 이 잰 값(auto 1.0 ×4, text 0.8984·0.7721·0.74·0.9358, 15표 1,496칸)과 {'같음' if want else '다름'}")
    return (not equal) + (not want)


def cmd_facts(folder):
    bad = 0
    for doc, want in FACTS.items():
        got = len(load(Path(folder) / doc / "facts.json")["facts"])
        print(f"{'같음' if got == want else '다름'}  {doc}: 값 후보 {got} (PD1 {want})")
        bad += got != want
    return bad


def cmd_difflines(lab, commit, docparse):
    bad = 0
    print("| 파일 | 원본 줄 수 | 다른 줄 (−/+) | 갈래 |")
    print("|---|---:|---:|---|")
    for path in sorted(Path(docparse).rglob("*.py")):
        rel = path.relative_to(docparse).as_posix()
        shown = subprocess.run(["git", "-C", lab, "show", f"{commit}:py/docparse/{rel}"], capture_output=True)
        if shown.returncode != 0:
            print(f"| {rel} | - | - | 원본에 없음 |")
            bad += 1
            continue
        diff = subprocess.run(["diff", "-", str(path)], input=shown.stdout, capture_output=True).stdout.decode(
            "utf-8", "replace"
        )
        minus = sum(1 for line in diff.splitlines() if line.startswith("< "))
        plus = sum(1 for line in diff.splitlines() if line.startswith("> "))
        rule = rel in RULE_FILES
        bad += rule and (minus or plus)
        print(
            f"| {rel} | {len(shown.stdout.splitlines())} | {minus}/{plus} | {'규칙·엔진 (0 이어야 한다)' if rule else '이음매·껍데기'} |"
        )
    missing = [f for f in RULE_FILES if not (Path(docparse) / f).is_file()]
    print(f"규칙·엔진 파일 {len(RULE_FILES)}개 가운데 없는 것: {missing}")
    return bad + len(missing)


def main(argv):
    commands = {
        "sha": cmd_sha,
        "same": cmd_same,
        "split": cmd_split,
        "score": cmd_score,
        "facts": cmd_facts,
        "difflines": cmd_difflines,
    }
    if len(argv) < 2 or argv[1] not in commands:
        print(__doc__, file=sys.stderr)
        return 2
    return 1 if commands[argv[1]](*argv[2:]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
