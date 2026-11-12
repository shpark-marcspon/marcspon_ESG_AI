"""core 문서 산출물의 계약 `core.doc-artifact@1`(밴드 RP2a ①, 결정 MARC-ENT-514 — 설계 band-handoffs/RP2-design.md §1).
표준 라이브러리만 쓴다(django 0 — core/tests/documents/test_structure.py 의 import 검사가 지킨다).

산출물 = 파서(services/parser)가 PDF 하나를 분해한 출력 **그대로**(문서 모델 + 글자 자리 두 JSON, layout 2 는 도표 라벨
까지 세 JSON — CHL1). core 가 회사마다
한 번 저장하고(core/models.py 의 DocumentArtifactRow — 불변 행), 모듈은 core 의 읽기 포트(selectors.py 의
find_artifact·artifact_view → view.py 의 DocArtifactView)로만 읽는다. 이 파일이 박는 것: 이름·판, 열쇠의 판 칸
`EPOCH`, 본문 크기 상한, 상태 두 값, 구조 관계 이름 목록(structure.py), 파서 출력의 꼴 검사·NUL 정리·이름 칸
자르기, 짓는 길의 결과 꼴.

열쇠 = (회사, CONTRACT, 원본 PDF 의 sha256, 분해 판 layout, EPOCH). 다르면 새 행이고 옛 행은 그대로다.

★ EPOCH 규칙 — 파서(services/parser 의 소스·스키마)를 고치는 밴드는 **같은 커밋에서** `EPOCH_PARSER_SHA` 에 새 값을
  더하고 `EPOCH` 를 +1 한다(주석만 바꿔도 기계적으로). 이 파일의 두 줄이 그 밴드의 알림 줄이다(플랫폼-서버 e7).
  까닭: 파서의 `__version__` 은 출력이 바뀌어도 오르지 않는다 — 열쇠로 못 쓴다(설계 B2). 그래서 앱 쪽 판 상수를 두고,
  파서 코드·스키마의 지문(`EPOCH_PARSER_SHA[EPOCH]`)을 시험(test_contract.py C1)이 지금 services/parser 와 견준다 —
  파서가 바뀌면 빨개져 EPOCH 올림을 코드 리뷰로 강제한다.
  지문의 셈: services/parser 아래 `docparse/**/*.py`·`schemas/*.json` 과 `app.py`·`pyproject.toml`·`uv.lock`(QC3 —
  응답을 싸는 자리와 의존 판)을 상대 경로(posix) 차례로, 파일마다 `상대 경로 + NUL + 바이트 수 + NUL + 바이트` 를
  이어 sha256(16진).
  무효 조건: 출력을 바꾸는 것이 그 밖(파서 이미지의 라이브러리 판 — pypdfium2 등)에 있으면 지문이 못 본다. 그때도 EPOCH
  를 손으로 올린다.
도표 라벨 칸(chart_labels, CHL1)의 NULL 은 둘이다: EPOCH 1 행·판 1 = 칸 없음(뷰 None) · EPOCH 2 이상 판 2 = 라벨 못 지음
  (파서가 라벨 요청을 거절해 라벨 없이 지은 행 — 뷰 ChartLabelsUnavailable). 둘을 접지 않는다.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal, cast

CONTRACT: Final = "core.doc-artifact@1"
EPOCH: Final = 2
# EPOCH → 그 판을 지을 때의 services/parser 지문(위 머리말의 셈). 옛 판의 줄은 지우지 않는다.
EPOCH_PARSER_SHA: Final[Mapping[int, str]] = {
    # QC3: 지문 범위 넓힘(app.py·pyproject·uv.lock) — 출력 0 바뀜, 행 그대로
    1: "60f829dd4697012cb665201065636ca9cffd5d7fc3d834354937f12e9f18d437",
    # CHL1: layout 2 chartLabels(쿼리 charts=1 일 때만) — layout 1·요청 없는 layout 2 출력 0 바뀜
    2: "dafd93ce1aa4ff3da5cecb1a5e730ea2782219d67d548d528806ef3e3145b46b",
}
# 본문(문서 모델 + 글자 자리를 compact JSON 으로 적은 UTF-8 바이트의 합) 상한. 넘으면 `too_large` 행(본문 NULL)이다.
# 근거(어림 — 잰 상한 아님): 공개 보고서 173쪽이 7,924,381 B(약 7.9 MB, core/resources/parser.py 머리말)의 네 배,
# 파서 응답 상한(64 MiB)의 절반. 실측 표는 band-reports/RP2a.md ⑪.
ARTIFACT_MAX_BYTES: Final = 32 * 1024 * 1024
LAYOUTS: Final[tuple[int, ...]] = (1, 2)
STATUSES: Final = ("ready", "too_large")
# 구조 관계 이름(읽을 때 structure.py 가 코드로 짓는다 — 저장 0). 늘리면 structure.py·시험과 함께.
RELATIONS: Final[tuple[str, ...]] = (
    "section_contains",
    "table_contains",
    "cell_row_header",
    "cell_col_header",
    "next_block",
    "title_path",
    "on_page",
)
# 파서에 넘기는 파일 이름. 문서마다 같은 값이라야 출력의 source.file_name 이 문서 이름으로 갈리지 않는다(514 ⑭).
PARSE_FILE_NAME: Final = "document.pdf"
UNIT: Final = "utf16"
# 파서 이름·판 칸의 길이(core/models.py 의 DocumentArtifactRow.parser_name·parser_version — 시험이 견준다). 넘으면 잘라
# 끝에 `…` 를 이 길이 안에 넣는다(보이기용 — 열쇠 아님, QC3).
PARSER_TEXT_MAX: Final = 40
# 파서 출력 글자의 NUL(`\x00`)을 바꾸는 글자. PostgreSQL jsonb 는 `\u0000` 을 받지 않는다(DataError). U+FFFD 는
# UTF-16 한 단위라 글자 자리(unit utf16)의 offset 이 밀리지 않는다(QC3).
NUL_REPLACEMENT: Final = "\ufffd"

ArtifactStatus = Literal["ready", "too_large"]


@dataclass(frozen=True, slots=True)
class ParserInfo:
    name: str
    version: str  # 보이기용(열쇠 아님 — 위 EPOCH 규칙)
    layout: int


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """산출물 한 행의 머리(본문 없음 — 목록·찾기는 jsonb 를 싣지 않는다, e7 ⑬)."""

    id: int
    source_sha256: str
    parser: ParserInfo
    epoch: int
    page_count: int
    body_bytes: int
    status: ArtifactStatus


@dataclass(frozen=True, slots=True)
class ArtifactRefused:
    """이 문서로는 산출물을 짓지 않는다(다시 해도 같다). code: `too_many_pages` 또는 파서의 거절 code
    (`parse_timeout`·`password_protected`·`not_a_pdf` … — 없으면 `rejected`). 행 0."""

    code: str


@dataclass(frozen=True, slots=True)
class ArtifactUnreadable:
    """원본을 읽지 못했다. code: `document_missing`·`storage_unconfigured`·`object_changed`·저장소 결과의 타입 이름
    (drafting 의 service/actions/run_sources.py 의 옛 갈래와 같은 이름). 행 0."""

    code: str


class ArtifactInvalid(Exception):
    """파서가 약속한 꼴이 아닌 것을 냈다(invalid_response·꼴 어김). 행 0 — 부르는 쪽의 단계 실패."""


class ArtifactNotFound(LookupError):
    """그 회사의 그 문서에 이어진 그 산출물이 없다(남의 것이어도), 또는 본문이 없다(`too_large`)."""


def body_bytes(
    document: Mapping[str, Any], char_places: Mapping[str, Any], chart_labels: Mapping[str, Any] | None = None
) -> int:
    """본문 크기 — 두 JSON(도표 라벨이 있으면 셋, CHL1)을 compact(`separators=(",", ":")`, `ensure_ascii=False`)로
    적은 UTF-8 바이트의 합."""
    parts = (document, char_places) if chart_labels is None else (document, char_places, chart_labels)
    return sum(len(json.dumps(part, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) for part in parts)


def _mapping(value: object) -> Mapping[str, Any] | None:
    return cast("Mapping[str, Any]", value) if isinstance(value, Mapping) else None


def _layout_of(part: Mapping[str, Any]) -> object:
    parser = _mapping(part.get("parser")) or {}
    return parser.get("layout", 1)  # 칸이 없으면 기본 판(1) — 파서 스키마의 약속


def shape_problem(
    document: object, char_places: object, *, layout: int, sha256: str, chart_labels: object = None
) -> str | None:
    """파서 출력이 이 계약이 받는 꼴인가. 어긴 것 한 줄(없으면 None).

    보는 것: 두 JSON 이 객체 · 판(`parser.layout`, 없으면 1)이 둘 다 `layout` · 두 `source.sha256` 이 원본의 sha256 ·
    `source.page_count` 가 1 이상 정수 · 글자 자리의 `unit` 이 `utf16` · 문서 모델의 pages·sections·blocks·tables 와
    글자 자리의 containers·unlinked 가 배열. 스키마 전부를 다시 재지 않는다(파서가 내기 전에 스스로 잰다 — 파서의
    output_schema_invalid).
    도표 라벨(CHL1)은 있을 때만 본다: 객체 · `source.sha256` 이 원본의 sha256 · charts·words·unlinked 가 배열.
    """
    doc, places = _mapping(document), _mapping(char_places)
    if doc is None or places is None:
        return "문서 모델과 글자 자리가 둘 다 객체가 아니다"
    for name, part in (("document", doc), ("charPlaces", places)):
        if _layout_of(part) != layout:
            return f"{name} 의 분해 판이 {layout} 이 아니다"
        source = _mapping(part.get("source")) or {}
        if source.get("sha256") != sha256:
            return f"{name} 의 source.sha256 이 원본과 다르다"
    pages = (_mapping(doc.get("source")) or {}).get("page_count")
    if not isinstance(pages, int) or isinstance(pages, bool) or pages < 1:
        return "document 의 source.page_count 가 1 이상 정수가 아니다"
    if places.get("unit") != UNIT:
        return f"charPlaces 의 unit 이 {UNIT} 이 아니다"
    for name, part, keys in (
        ("document", doc, ("pages", "sections", "blocks", "tables")),
        ("charPlaces", places, ("containers", "unlinked")),
    ):
        for key in keys:
            if not isinstance(part.get(key), list):
                return f"{name} 의 {key} 가 배열이 아니다"
    if chart_labels is None:
        return None
    labels = _mapping(chart_labels)
    if labels is None:
        return "chartLabels 가 객체가 아니다"
    if (_mapping(labels.get("source")) or {}).get("sha256") != sha256:
        return "chartLabels 의 source.sha256 이 원본과 다르다"
    for key in ("charts", "words", "unlinked"):
        if not isinstance(labels.get(key), list):
            return f"chartLabels 의 {key} 가 배열이 아니다"
    return None


def page_count_of(document: Mapping[str, Any]) -> int:
    """꼴 검사를 지난 문서 모델의 PDF 전체 쪽 수."""
    return int(document["source"]["page_count"])


def _fit(text: str) -> str:
    return text if len(text) <= PARSER_TEXT_MAX else text[: PARSER_TEXT_MAX - 1] + "…"


def parser_info_of(document: Mapping[str, Any], *, layout: int) -> ParserInfo:
    """이름·판은 PARSER_TEXT_MAX 안으로 자른다(칸 길이)."""
    parser = _mapping(document.get("parser")) or {}
    return ParserInfo(
        name=_fit(str(parser.get("name", ""))), version=_fit(str(parser.get("version", ""))), layout=layout
    )


def scrub_nul(value: Any) -> tuple[Any, int]:
    """JSON 값 안의 글자(키 포함)마다 NUL 을 NUL_REPLACEMENT 로 바꾼 사본과 바꾼 수. 꼴 검사 뒤·INSERT 전에 부른다."""
    if isinstance(value, str):
        count = value.count("\x00")
        return (value.replace("\x00", NUL_REPLACEMENT) if count else value), count
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        total = 0
        for key, item in cast("Mapping[Any, Any]", value).items():
            new_key, key_count = scrub_nul(key)
            out[new_key], item_count = scrub_nul(item)
            total += key_count + item_count
        return out, total
    if isinstance(value, list):
        items = [scrub_nul(item) for item in cast("list[Any]", value)]
        return [item for item, _ in items], sum(count for _, count in items)
    return value, 0
