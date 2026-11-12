"""엑셀 greenwash-report.xlsx — 결과 greenwash.result@1 한 건에서만 칸을 채운다(새 셈 없음).

노트북에는 엑셀이 없다(셀 19 의 출력은 화면 print). 그래서 이 밴드가 정한 최소 구성이다(발주서 §2-8):
  요약       등급별 건수, 파트 × 등급 건수, 전체 문장 수, 점검 페이지 수, 인식 실패 페이지 수(ENT-603)
  문장       판정 문장 하나에 한 줄(items 차례)
  단어 빈도  낱말 하나에 한 줄(문서 전체 수의 내림차순 — 결과의 wordCounts.total 차례 그대로). 셋째 열 「추가」는
             추가 단어 가운데 빈도 목록에 더한 단어(added_terms — 흐름이 gw1.frequency_extras 로 지어 넘긴다)의
             줄에만 「추가」, 나머지는 빈 칸(G1c)
  설정       프롬프트 판, 모델(노트북 설정), 매개변수, 조각 설정, 추가 단어(줄바꿈으로 이음 — 단어에 쉼표가 들 수
             있다. 없으면 빈 칸 — G1c), 결과에 terms 가 있으면(판의 대상 단어로 센 실행 — G2d) 그 바로 뒤에 「대상
             단어」(빈도에 센 낱말 전체, 줄바꿈으로 이음). 「추가」 표시는 늘 기본 목록(GREEN_TERMS) 기준이다
확정본(adopted 가 값 — 보고서 GET 의 confirmed=true, 밴드 G1b-2a, MARC-ENT-356): 「문장」은 채택한 itemIndex 만(차례
그대로), 「요약」의 등급별·파트 × 등급·전체는 실린 문장으로 다시 센다(파트는 결과 parts 전부를 0 에서 — 빈 파트 포함).
점검 페이지·실패한 페이지·단어 빈도는 결과 그대로, 「설정」 끝에 판 줄 하나. adopted 가 None(기본값)이면 결과 그대로다
(흐름 report 단계의 엑셀).
검토 고침(edits 가 값 — 확정본만, 밴드 G1b-3, MARC-ENT-354 6): edits = itemIndex → (등급, 사유, 수정 방향), 칸마다
None = AI 그대로. 「문장」의 등급·사유·수정 방향은 고친 값(없으면 AI), 끝에 칸 넷 EDIT_HEADER — 「고침」(고친 칸 이름을
「·」로 이음)·AI 등급·AI 사유·AI 수정 방향(고친 칸만 AI 값, 나머지 빈 칸). 「요약」은 고친 등급으로 다시 센다(사본 items
를 덮은 뒤 adopted_only). 「설정」의 판 줄 앞에 「고친 문장」(실린 문장 중 고친 수) — 판 줄은 늘 끝. edits 가 None 이면
칸 넷도 「고친 문장」 줄도 없다(adopted 만 있으면 G1b-2a 확정본과 같은 칸 값). edits 만 있고 adopted 가 None 이면
ValueError(흐름 엑셀·미확정 보고서는 AI 값).
재판단(edits 길에만, 밴드 GRJ1 — MARC-ENT-617): bases 가 덮은 문장은 판정 칸이 기준 판단(마지막 done 재판단) 값이고,
「AI …」 칸도 그 값이다. 끝에 칸 둘 REJUDGE_HEADER(「근거 고침」 지움 n · 더함 n · 「재판단」 n회 · 때 · 이름 —
report.py 가 짓는다). 기준 판단이 리스크 아님이면 등급 칸 「리스크 아님」, 「요약」 등급 셋에서 빠지고 등급 셋 뒤
「리스크 아님(재판단)」 줄에 센다. 재판단 이력 시트는 없다(감독 Q5).
「단어 빈도」의 차례는 결과의 wordCounts.total 그대로다(GW1 counts_json = Counter.most_common — 수가 같으면 문서에서
처음 나온 낱말이 앞. 발주서 §2-8 의 「같으면 낱말 차례」와 다르다 — 결과와 같은 차례가 낫다고 보아 결과를 따랐다).
글자 칸(AI 가 돌려준 글이 든다)은 두 가지만 다듬는다: xlsx 가 담지 못하는 제어 문자(openpyxl ILLEGAL_CHARACTERS_RE)를
지우고, `=` 로 시작해도 수식이 아니라 글자 칸으로 둔다. 그 밖의 값은 결과 그대로다.
openpyxl 의 xlsx 는 만든 시각이 들어가 바이트가 실행마다 다르다 — 테스트는 읽어 들인 칸 값을 결과와 견준다.
"""

import io
import json
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Final

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.worksheet.worksheet import Worksheet

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEETS: Final = ("요약", "문장", "단어 빈도", "설정")
SENTENCE_HEADER: Final = (
    "파트",
    "페이지",
    "등급",
    "문장",
    "위험 유형",
    "확인된 근거",
    "빠진 항목",
    "사유",
    "수정 방향",
    "참고한 근거 페이지",
    "예시 문장",
)
EDIT_HEADER: Final = ("고침", "AI 등급", "AI 사유", "AI 수정 방향")
REJUDGE_HEADER: Final = ("근거 고침", "재판단")
NONRISK: Final = "리스크 아님"
"""재판단 결과가 리스크 아님(기준 판단의 level 이 null)인 문장의 등급 칸 글(감독 Q3)."""
NONRISK_SUMMARY: Final = "리스크 아님(재판단)"
BASIS_KEYS: Final = (
    "level",
    "riskTags",
    "confirmedInEvidence",
    "missingFields",
    "reasonBullets",
    "fixParagraph",
    "evidencePages",
)
"""기준 판단(재판단)이 덮는 칸 — actions/review.JUDGED_KEYS 와 같다(시험이 견준다)."""
EDIT_NAMES: Final = ("등급", "사유", "수정 방향")
WORD_HEADER: Final = ("낱말", "수", "추가")
ADDED: Final = "추가"
LEVELS: Final = ("High", "Mid", "Low")

type Edit = tuple[str | None, Sequence[str] | None, str | None]
"""한 문장의 고침 — (등급, 사유 줄, 수정 방향). 칸 None = AI 그대로."""
type Note = tuple[str, str]
"""한 문장의 「근거 고침」·「재판단」 칸 글(부르는 쪽 report.py 가 짓는다 — 없으면 빈 칸)."""


def _join(values: Sequence[object], sep: str = ", ") -> str:
    return sep.join(str(v) for v in values)


def summary_rows(result: Mapping[str, Any], *, nonrisk: int | None = None) -> list[tuple[str, int]]:
    """nonrisk 가 값이면(검토 반영 엑셀 — 기준 판단이 있는 길) 등급 셋 뒤에 「리스크 아님(재판단)」 줄."""
    counts = result["counts"]
    rows: list[tuple[str, int]] = [(f"등급 {level}", int(counts["byLevel"][level])) for level in LEVELS]
    if nonrisk is not None:
        rows.append((NONRISK_SUMMARY, nonrisk))
    for part, levels in counts["byPart"].items():
        rows.extend((f"{part} · {level}", int(levels[level])) for level in LEVELS)
    rows.append(("전체 문장 수", int(counts["total"])))
    rows.append(("점검 페이지 수", len(result["pages"])))
    rows.append(("인식 실패 페이지 수", len(result["candidateStats"]["failedPages"])))
    return rows


def sentence_rows(result: Mapping[str, Any]) -> list[tuple[str | int, ...]]:
    return [
        (
            _join(item["parts"]),
            int(item["page"]),
            NONRISK if item["level"] is None else item["level"],
            item["sentence"],
            _join(item["riskTags"]),
            _join(item["confirmedInEvidence"], "\n"),
            _join(item["missingFields"], "\n"),
            _join(item["reasonBullets"], "\n"),
            item["fixParagraph"],
            _join(item["evidencePages"]),
            item["exampleSentence"] or "",
        )
        for item in result["items"]
    ]


def word_rows(result: Mapping[str, Any], added_terms: Collection[str]) -> list[tuple[str, int, str | None]]:
    added = set(added_terms)
    return [
        (row["term"], int(row["count"]), ADDED if row["term"] in added else None)
        for row in result["wordCounts"]["total"]
    ]


def adopted_only(result: Mapping[str, Any], adopted: Collection[int]) -> dict[str, Any]:
    """확정본의 결과 사본: items 는 채택한 itemIndex 만(차례 그대로), counts 는 그것으로 다시 셈(머리말)."""
    wanted = set(adopted)
    items = [item for index, item in enumerate(result["items"]) if index in wanted]
    by_level = dict.fromkeys(LEVELS, 0)
    by_part: dict[str, dict[str, int]] = {part["name"]: dict.fromkeys(LEVELS, 0) for part in result["parts"]}
    for item in items:
        part_counts = [by_part.setdefault(part, dict.fromkeys(LEVELS, 0)) for part in item["parts"]]
        if item["level"] is None:
            continue  # 리스크 아님(재판단) — 세 등급 어디에도 세지 않는다(감독 R5). 파트는 빈 칸으로도 남긴다
        by_level[item["level"]] += 1
        for levels in part_counts:
            levels[item["level"]] += 1
    counts = {**result["counts"], "total": len(items), "byLevel": by_level, "byPart": by_part}
    return {**result, "items": items, "counts": counts}


def with_bases(result: Mapping[str, Any], bases: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    """결과 사본: 재판단이 기준이 된 문장의 판정 칸(BASIS_KEYS)을 기준 판단 값으로 덮는다(level None = 리스크 아님).
    첫 AI 판단(원 결과)은 그대로 — 이 사본만 바뀐다."""
    items = [
        {**item, **{key: bases[index][key] for key in BASIS_KEYS}} if index in bases else item
        for index, item in enumerate(result["items"])
    ]
    return {**result, "items": items}


def with_edits(result: Mapping[str, Any], edits: Mapping[int, Edit]) -> dict[str, Any]:
    """결과 사본: items 의 등급·사유·수정 방향을 고친 값으로 덮는다(counts 는 그대로 — adopted_only 가 다시 센다)."""
    items: list[Any] = []
    for index, item in enumerate(result["items"]):
        level, bullets, fix = edits.get(index, (None, None, None))
        items.append(
            {
                **item,
                "level": item["level"] if level is None else level,
                "reasonBullets": item["reasonBullets"] if bullets is None else list(bullets),
                "fixParagraph": item["fixParagraph"] if fix is None else fix,
            }
        )
    return {**result, "items": items}


def edit_columns(item: Mapping[str, Any], edit: Edit | None) -> tuple[str, str, str, str]:
    """「문장」 끝 칸 넷(EDIT_HEADER). item = AI 항목(기준 판단 — 재판단이 있으면 그 값). 고친 칸만 AI 값을 싣는다."""
    level, bullets, fix = edit if edit is not None else (None, None, None)
    edited = (level is not None, bullets is not None, fix is not None)
    return (
        "·".join(name for name, on in zip(EDIT_NAMES, edited, strict=True) if on),
        (NONRISK if item["level"] is None else item["level"]) if edited[0] else "",
        _join(item["reasonBullets"], "\n") if edited[1] else "",
        item["fixParagraph"] if edited[2] else "",
    )


def config_rows(result: Mapping[str, Any]) -> list[tuple[str, str]]:
    config = result["config"]
    return [
        ("프롬프트 판", str(result["promptVersion"])),
        ("대화 모델(노트북 설정)", str(result["models"]["chat"])),
        ("임베딩 모델(노트북 설정)", str(result["models"]["embedding"])),
        ("매개변수", json.dumps(config["chat"], ensure_ascii=False)),
        ("조각 설정", json.dumps(config["chunking"], ensure_ascii=False)),
        ("추가 단어", _join(result["extraTerms"], "\n")),  # 단어에 쉼표가 들 수 있어 줄바꿈으로 잇는다
        *([("대상 단어", _join(result["terms"], "\n"))] if "terms" in result else []),  # 판 단어로 센 실행만(G2d)
    ]


def cell_text(value: str) -> str:
    """xlsx 가 담지 못하는 제어 문자를 지운다(그대로 두면 openpyxl 이 IllegalCharacterError — 판정을 다 마친 뒤
    report 단계가 실패한다)."""
    return ILLEGAL_CHARACTERS_RE.sub("", value)


def _put(sheet: Worksheet, row: Sequence[object]) -> None:
    sheet.append([cell_text(v) if isinstance(v, str) else v for v in row])
    for cell in sheet[sheet.max_row]:
        if cell.data_type == "f":  # `=` 로 시작하는 글 — 수식이 아니라 글자로
            cell.data_type = "s"


def build(
    result: Mapping[str, Any],
    *,
    added_terms: Collection[str],
    adopted: Collection[int] | None = None,
    edits: Mapping[int, Edit] | None = None,
    bases: Mapping[int, Mapping[str, Any]] | None = None,
    notes: Mapping[int, Note] | None = None,
) -> bytes:
    """결과 한 건 → xlsx 바이트. dry-run 결과는 받지 않는다(엑셀이 없다). adopted 가 값이면 확정본, edits 가 값이면
    고친 값과 AI 원래 판단(머리말). bases·notes(GRJ1)는 edits 길에만: bases = 재판단이 기준이 된 itemIndex → 기준 판단
    칸(BASIS_KEYS — 등급·사유·수정 방향은 「사용자 고침 > 기준 판단 > 첫 판단」, 「AI …」 칸도 기준 판단), notes =
    itemIndex → 「근거 고침」·「재판단」 칸 글. edits 가 값이면 칸 둘 REJUDGE_HEADER 와 요약 「리스크 아님(재판단)」
    줄이 늘 있다(값이 없으면 빈 칸·0). edits 가 None 이면 셋 다 없다(흐름 엑셀·g2d-baseline 바이트 그대로)."""
    if result["dryRun"] is not None:
        raise ValueError("dry-run 결과에는 엑셀이 없다")
    if edits is not None and adopted is None:
        raise ValueError("고침은 확정본에만 싣는다")
    if (bases is not None or notes is not None) and edits is None:
        raise ValueError("기준 판단·근거 고침 칸은 검토 반영(edits) 엑셀에만 싣는다")
    total = len(result["items"])
    kept = list(range(total)) if adopted is None else sorted(set(adopted) & set(range(total)))
    if bases:
        result = with_bases(result, bases)
    originals = result["items"]  # 「AI …」 칸 = 기준 판단(재판단이 없으면 첫 판단)
    if edits is not None:
        result = with_edits(result, edits)
    if adopted is not None:
        result = adopted_only(result, adopted)
    book = Workbook()
    summary = book.active
    assert summary is not None  # noqa: S101 — 새 Workbook 은 시트 하나를 갖고 시작한다
    summary.title = SHEETS[0]
    _put(summary, ("이름", "수"))
    nonrisk = None if edits is None else sum(1 for item in result["items"] if item["level"] is None)
    for row in summary_rows(result, nonrisk=nonrisk):
        _put(summary, row)
    sentences = book.create_sheet(SHEETS[1])
    _put(sentences, SENTENCE_HEADER if edits is None else SENTENCE_HEADER + EDIT_HEADER + REJUDGE_HEADER)
    shown = notes or {}
    for index, row in zip(kept, sentence_rows(result), strict=True):
        if edits is None:
            _put(sentences, row)
        else:
            _put(sentences, row + edit_columns(originals[index], edits.get(index)) + shown.get(index, ("", "")))
    words = book.create_sheet(SHEETS[2])
    _put(words, WORD_HEADER)
    for row in word_rows(result, added_terms):
        _put(words, row)
    settings = book.create_sheet(SHEETS[3])
    _put(settings, ("이름", "값"))
    for row in config_rows(result):
        _put(settings, row)
    if edits is not None:
        edited = sum(1 for index in kept if any(v is not None for v in edits.get(index, (None, None, None))))
        _put(settings, ("고친 문장", str(edited)))
    if adopted is not None:
        _put(settings, ("판", f"확정본 — 채택 {len(result['items'])} / 전체 {total}"))
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
