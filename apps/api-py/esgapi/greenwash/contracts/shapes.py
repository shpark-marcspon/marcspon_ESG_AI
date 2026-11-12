"""결과 꼴 greenwash.result@1 의 정의. TypedDict(모르는 키 금지) → JSON 스키마.

원천은 esg-lab GW1 의 결과(`schemas/greenwash-result.schema.json`, `py/greenwash/result.py`)다. 칸 이름은 GW1·노트북의
snake_case 를 camelCase 로 옮긴 것이다(GC3, pydantic `to_camel` 규칙). 값이 키인 자리(`LevelCounts` 의 High·Mid·Low,
`byPart` 의 파트 이름)는 그대로다. 엔진이 내는 snake 를 옮기는 경계는 contracts/wire.result_to_wire 하나다.
GW1 결과에서 뺀 것: `schema_version`(→ `schemaVersion`), `provider`·`calls`·`synthetic`(무엇이 실제로 불렸는지는
실행기의 사용량 기록이 진실이다). 더한 것: 항목의 `position`(GW1 `span` 의 자리)·`exampleSentence`, 결과의 `counts`·
`report`. GW1 은 dry-run 이면 칸을 뺐지만 여기서는 두 갈래(ScanResult·DryRunResult)가 같은 키를 다 갖고, 갈래는
`dryRun` 이 null 이냐로 가른다. 갈래마다 null·빈 목록이어야 하는 칸을 꼴이 강제한다.

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다(use_attribute_docstrings). 프론트는 고정 파일
tests/data/flow-shapes/greenwash.result@1.schema.json 을 읽고 zod 거울을 짓는다. 꼴을 바꾸면 새 판(@2)이다. 초안 판
시기의 @1 안 고침은 감독 승인으로만(G1c 의 extraTerms 가 그것이다).

이 파일은 등록 길(apps.py 의 ready → registration.py)에서 들이지 않는다(pydantic 의 꼴 짓기를 시작에 싣지 않는다).
"""

from collections.abc import Mapping
from typing import Annotated, Final, Literal, NotRequired, TypedDict

from pydantic import ConfigDict, Field, TypeAdapter, with_config

SHAPE: Final = "greenwash.result@1"
FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)

Page = Annotated[int, Field(ge=1)]
Count = Annotated[int, Field(ge=0)]

ExtraTerm = Annotated[str, Field(min_length=1, max_length=30)]
ExtraTerms = Annotated[list[ExtraTerm], Field(max_length=30)]
"""추가 단어: 한 단어 1~30자, 30개까지(흐름 입력의 검사 flows/colab.accept_extra_terms 와 같은 상한)."""
UsedTerms = Annotated[list[ExtraTerm], Field(max_length=1030)]
"""실행이 빈도에 센 낱말 전체(밴드 G2d): 판의 켠 대상 단어(받기 상한 100) + 추가 단어(30). 상한 1030 은 꼴의 느슨한
그물이다(판 저장 본문 꼴 1000 + 30)."""

Level = Literal["High", "Mid", "Low"]
"""판정 등급. High·Mid 는 위험 판정(근거와 견줘 근거가 모자라거나 과장된 주장 — High 가 더 무겁다), Low 는 「선언적
문장」(수치·검증 없이 다짐만 하는 문장 — 어미 규칙이 정한다. 쪽마다 많아야 하나). AI 가 위험이 없다고 본 문장
(NonRisk)은 items 에 없다."""

Box = Annotated[
    list[float],
    Field(
        min_length=4,
        max_length=4,
        description=(
            "[left, top, right, bottom]. 단위는 포인트(pt), 원점은 쪽의 왼쪽 위(문서 뷰어의 계약과 같다). "
            "left ≤ right, top ≤ bottom."
        ),
    ),
]


@with_config(FORBID)
class Position(TypedDict):
    """문장이 쪽의 어디에 있는지. 문서 뷰어 계약(apps/web/src/doc-viewer/domain/contract.ts)의 강조에서 boxes 는
    innerBoxes 에 대응한다. 뷰어의 바깥 box 는 boxes 를 감싸는 상자로 지어 쓴다. 쪽 크기는 결과에 없다(PDF 에서 읽는다).
    """

    page: Page
    """쪽 번호. 1부터(항목의 page 와 같은 셈)."""
    boxes: Annotated[list[Box], Field(min_length=1)]
    """줄마다 상자 하나. 문장이 두 줄에 걸치면 상자 둘이다."""


@with_config(FORBID)
class Source(TypedDict):
    """점검한 파일."""

    fileName: str
    """올린 파일의 이름."""
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    """파일 바이트의 sha256(소문자 16진 64자)."""
    pageCount: Count
    """문서의 쪽 수."""


@with_config(FORBID)
class CheckerConfig(TypedDict):
    """노트북의 GWConfig 전부(값은 GW1 의 SCAN_CONFIG 를 채운 것). 화면에 보일 칸이 아니라 기록이다."""

    maxCandidatesPerPage: int
    """쪽마다 AI 에게서 받는 후보 문장의 상한."""
    maxCharsPageText: int
    """쪽 글을 이 글자 수까지만 본다(넘으면 잘린다)."""
    evidenceK: int
    """문장마다 보여 주는 근거 조각 수."""
    maxCharsPerChunk: int
    """근거 조각 하나의 글자 상한."""
    useEvidenceFailopen: bool
    """근거를 못 찾았을 때 점검 쪽 밖도 볼지(E0 는 false)."""
    maxCharsEvidenceTotal: int
    """근거 글의 합 상한."""
    reportLevels: list[str]
    """결과에 싣는 등급."""
    debug: bool
    debugPages: int
    batchEval: bool
    promptVersion: str
    """프롬프트의 판."""


@with_config(FORBID)
class ChunkingConfig(TypedDict):
    """근거 색인의 조각 설정(노트북 셀 11 의 값)."""

    chunkSize: int
    chunkOverlap: int
    separators: list[str]
    normalize: bool
    embeddingBatchSize: int


@with_config(FORBID)
class ChatParams(TypedDict):
    """노트북이 대화 모델에 주는 매개변수. 노트북 설정이며 실제로 넘겨졌는지는 실행기의 사용량 기록이 진실이다."""

    temperature: float
    maxTokens: int


@with_config(FORBID)
class Config(TypedDict):
    """점검 설정. GW1 의 config 그대로."""

    checker: CheckerConfig
    chunking: ChunkingConfig
    chat: ChatParams


@with_config(FORBID)
class Models(TypedDict):
    """노트북이 정한 모델 이름. 실제로 불린 공급사·모델이 아니다 — 그것은 실행기의 사용량 기록이 진실이다."""

    chat: str
    embedding: str


@with_config(FORBID)
class Part(TypedDict):
    """파트 하나와 그 쪽(사람이 준 쪽 입력을 문서 범위로 자른 것)."""

    name: str
    """파트 이름. E0 는 「CEO 메시지」·「회사소개」·「기후/환경 토픽」 셋이고 이 차례다."""
    pages: list[Page]
    """이 파트의 쪽(1부터, 오름차순). 빈 목록이면 그 파트는 점검하지 않았다. 한 쪽이 두 파트에 들 수 있다."""


@with_config(FORBID)
class Item(TypedDict):
    """판정 문장 하나. items 의 차례는 한 번 쓰면 바뀌지 않는다 — (실행 id, items 차례 0부터)가 문장의 열쇠다.

    Low 이면 늘: riskTags = ["선언적 문장"], confirmedInEvidence = [], missingFields = [], evidenceInternal = "".
    fixParagraph 는 등급과 상관없이 늘 비지 않는다(High·Mid 는 60자, Low 는 40자보다 짧으면 노트북이 대신 쓰는 글이
    들어간다). Low 는 쪽마다 많아야 하나다.
    """

    page: Page
    """문장이 나온 쪽. 1부터."""
    parts: list[str]
    """이 쪽이 든 파트의 이름 목록(Part.name). 한 쪽이 두 파트에 들면 둘이다."""
    sentence: str
    """AI 가 돌려준 문장. 쪽 글에 그대로 있는지는 확인하지 않는다(노트북 동작)."""
    level: Level
    """판정 등급."""
    riskTags: list[str]
    """위험 유형(AI 가 붙인 꼬리표, 셋까지). Low 는 ["선언적 문장"]."""
    confirmedInEvidence: list[str]
    """근거에서 확인된 사실. Low 는 빈 목록."""
    missingFields: list[str]
    """근거에서 빠진 항목. Low 는 빈 목록."""
    reasonBullets: list[str]
    """판정 사유(줄마다 하나)."""
    fixParagraph: str
    """수정 방향(늘 비지 않음). 노트북의 세 벌 칸(fix, action, fix_paragraph)을 한 칸으로 싣는다."""
    evidencePages: list[Page]
    """AI 에게 보여 준 근거 조각의 쪽(1부터). 빈 목록이면 「근거 없음」으로 판정한 것이다. Low 도 근거를 찾는다."""
    evidenceInternal: str
    """판단 근거 한 줄(내부용). Low 는 빈 글이다."""
    position: Position | None
    """문장의 쪽 위 자리. 찾지 못했거나 좌표 엔진이 없으면 null. E0 흐름은 좌표 엔진이 없어 늘 null 이다(예시
    result-normal.json 의 상자는 좌표 엔진이 생긴 뒤의 꼴을 보이려고 지은 값이다)."""
    exampleSentence: str | None
    """고쳐 쓴 예시 문장. E0 는 늘 null(채우는 것은 다음 흐름 판)."""


@with_config(FORBID)
class FailedPage(TypedDict):
    """판정 중 예외가 나 건너뛴 쪽. 그 쪽의 후보는 집계에 들지 않고, 그 쪽에서 판정이 끝난 문장도 items 에 없다."""

    page: Page
    """쪽 번호. 1부터."""
    error: str
    """예외의 글."""


@with_config(FORBID)
class CandidateStats(TypedDict):
    """후보 문장의 집계(점검 쪽마다 더한 것). 쪽마다 후보를 Low 꼴(선언적 문장)과 나머지로 나눠 각각 거른 뒤, 나머지는
    점수 높은 차례로 상한(maxCandidatesPerPage)까지, Low 꼴은 하나까지 남긴 것이 kept 다(쪽당 상한 + 1 까지. 그래서
    raw - 넷 ≥ kept). kept 가운데 AI 가 위험 없음으로 본 문장은 items 에 없다. 실패한 쪽의 후보는 들지 않는다."""

    raw: Count
    """규칙과 AI 가 찾은 후보 문장 전부."""
    hardDropped: Count
    """문장이 아니어서 버린 것(15자 미만, 제목·라벨 꼴, 끝맺음 없는 짧은 글)."""
    nonEnvDropped: Count
    """환경 낱말이 없어 버린 것."""
    promoDropped: Count
    """환경 낱말 없이 홍보 문구로 보여 버린 것. 노트북은 환경 낱말이 없는 문장을 앞에서 이미 버리므로
    실제로는 늘 0 이다."""
    tableDropped: Count
    """표의 줄처럼 보이고 고위험 낱말이 없어 버린 것."""
    kept: Count
    """판정에 넘긴 후보(쪽당 상한 + Low 꼴 하나까지)."""
    failedPages: list[FailedPage]
    """실패한 쪽. 빈 목록이면 실패 없음."""


@with_config(FORBID)
class LevelCounts(TypedDict):
    """등급별 문장 수."""

    High: Count
    Mid: Count
    Low: Count


@with_config(FORBID)
class Counts(TypedDict):
    """items 에서 센 건수(새 셈이 아니라 items 를 다시 센 것)."""

    total: Count
    """전체 문장 수(= items 의 길이)."""
    byLevel: LevelCounts
    """등급별 문장 수. 합이 total 이다."""
    byPart: dict[str, LevelCounts]
    """파트 이름(parts 의 name 전부, 빈 파트 포함) → 등급별 수. 두 파트에 든 쪽의 문장은 두 파트에서 다 센다(노트북
    동작). 그래서 byPart 의 합이 total 보다 클 수 있다."""


@with_config(FORBID)
class TermCount(TypedDict):
    """의심 낱말 하나와 그 수."""

    term: str
    """의심 낱말(노트북의 낱말 목록 그대로)."""
    count: Annotated[int, Field(ge=1)]
    """나온 수(1 이상 — 안 나온 낱말은 싣지 않는다)."""


@with_config(FORBID)
class PageTermCounts(TypedDict):
    """한 쪽의 낱말 수."""

    page: Page
    """쪽 번호. 1부터."""
    counts: list[TermCount]
    """그 쪽의 낱말 수. 많은 차례(같으면 노트북 낱말 목록의 차례)."""


@with_config(FORBID)
class WordCounts(TypedDict):
    """의심 낱말의 빈도. 문서 전체를 센다(점검 쪽만이 아니다). AI 를 쓰지 않으므로 dry-run 에서도 채운다."""

    total: list[TermCount]
    """문서 전체의 낱말 수. 많은 차례(같으면 처음 나온 쪽의 차례, 같은 쪽 안에서는 노트북 낱말 목록의 차례)."""
    pages: list[PageTermCounts]
    """쪽마다의 낱말 수(쪽 차례). 낱말이 하나도 없는 쪽은 싣지 않는다."""


@with_config(FORBID)
class MeasuredTokens(TypedDict):
    """잰 토큰 수."""

    status: Literal["measured"]
    encoding: str
    """토큰 부호화의 이름(대화 o200k_base, 임베딩 cl100k_base)."""
    value: Count


@with_config(FORBID)
class UnmeasuredTokens(TypedDict):
    """못 잰 토큰 수. 못 쟀으면 0 이 아니라 이 갈래다."""

    status: Literal["unmeasured"]
    encoding: str
    reason: str
    """못 잰 까닭."""


Tokens = Annotated[MeasuredTokens | UnmeasuredTokens, Field(discriminator="status")]


@with_config(FORBID)
class Tally(TypedDict):
    """요청 수와 보낼 글의 양."""

    requests: Count
    """요청 수."""
    inputChars: Count
    """보낼 글의 글자 수."""
    inputTokens: Tokens
    """보낼 글의 토큰 수."""


@with_config(FORBID)
class ByKind(TypedDict):
    """대화 요청의 종류별 셈(노트북 프롬프트 넷: 탐지, 판정, Low 판정, 수정 방향 다시 묻기)."""

    detect: Tally
    eval: Tally
    lowOnly: Tally
    repair: Tally


@with_config(FORBID)
class DryRunLower(TypedDict):
    """아래끝: AI 후보 0, 다시 묻기 0, 근거 없음."""

    chat: Tally
    chatByKind: ByKind
    embeddingQueries: Tally
    judged: Count
    """판정한 문장 수(규칙 후보만)."""


@with_config(FORBID)
class DryRunUpper(TypedDict):
    """위끝: 쪽마다 탐지 1 + 판정 3 + Low 판정 1 + 다시 묻기 3 + 근거 물음 4(후보 상한 3 일 때)."""

    chat: Tally
    chatByKind: ByKind
    embeddingQueries: Tally
    outputTokensMax: Count
    """대화 요청 수 × 출력 상한."""
    evidenceChars: Count
    """근거 글이 가장 길 때의 글자 수."""
    evidenceCapReached: bool
    """근거 글이 합 상한에 닿았는지."""


@with_config(FORBID)
class DryRunPage(TypedDict):
    """점검 쪽 하나의 셈."""

    page: Page
    """쪽 번호. 1부터."""
    textChars: Count
    """쪽 글의 글자 수(자르기 전)."""
    truncated: bool
    """글이 상한을 넘어 잘렸는지."""
    ruleCandidates: Count
    """규칙이 뽑은 선언문 후보 수."""
    lowerJudged: Count
    """아래끝에서 판정한 문장 수."""


@with_config(FORBID)
class DryRun(TypedDict):
    """보내지 않고 센 것(GW1 의 dry_run 칸 그대로). 입력 글자·토큰은 메시지의 글이고 메시지 틀 토큰은 들지 않는다."""

    pagesChecked: Count
    """점검 쪽 수."""
    pagesWithText: Count
    """글이 있는 점검 쪽 수."""
    pagesTruncated: Count
    """글이 상한(기본 2,500자)을 넘어 잘린 쪽."""
    chunks: Count
    """문서 전체의 조각 수."""
    embeddingIndex: Tally
    """조각 전체를 임베딩하는 요청(묶음 50)."""
    ruleCandidates: Count
    """규칙이 뽑은 선언문 후보의 합(쪽당 끊은 뒤)."""
    lower: DryRunLower
    upper: DryRunUpper
    perPage: list[DryRunPage]
    """점검 쪽마다(쪽 차례)."""


@with_config(FORBID)
class Report(TypedDict):
    """흐름이 낸 파일."""

    file: Literal["greenwash-report.xlsx"]
    """엑셀 보고서의 파일 이름(흐름의 출력 파일)."""


@with_config(FORBID)
class ScanResult(TypedDict):
    """greenwash.result@1 — 점검한 실행(dry-run 아님). dryRun 이 null 이고 candidateStats·counts·report 가 채워진다.
    점검 쪽이 없으면 items 가 빈 목록이다. 키 차례는 아래와 같고 schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.result@1"]
    source: Source
    config: Config
    models: Models
    """노트북 설정의 모델 이름(실제로 불린 모델이 아니다)."""
    promptVersion: str
    """노트북 프롬프트의 판. E0 는 2026-01-15-v1."""
    parts: list[Part]
    """파트 셋과 그 쪽."""
    pages: list[Page]
    """점검한 쪽(파트의 합집합, 1부터, 오름차순). 근거를 찾아도 되는 쪽과 같다."""
    extraTerms: ExtraTerms
    """사용자가 이 점검에 더한 단어(받은 꼴 그대로, 받은 차례). 판정 대상 키워드(환경 낱말)에 모두 썼고, 단어 빈도에는
    기본 목록과 겹치지 않는 것만 더했다. 한 번도 안 나온 단어는 빈도 표에 줄이 없다. 빈도 표의 『추가』 표시는 화면
    몫이다. 기본 목록 단어는 화면이 입력 때 막는다. 중복 제거와 기본 목록 비교는 대소문자·하이픈·띄어쓰기를 무시한
    글자 그대로라(「탄소 중립」 = 「탄소중립」), 노트북 목록에서 붙어 버린 낱말의 조각(예: eco)은 따로 세어진다."""
    terms: NotRequired[UsedTerms]
    """이 실행이 의심 낱말 빈도에 센 낱말 전체(차례 그대로 — 밴드 G2d): AI 설정 판의 켠 대상 단어(판 차례) 뒤에 추가
    단어 가운데 비교 키가 판 단어와 같지 않은 것. 판의 대상 단어로 센 실행에만 있다 — 칸이 없으면 코드 기본 목록
    (GET /greenwash/terms/default) + 추가 단어로 셌다. 판 단어는 판정할 문장을 고르는 환경 낱말에는 쓰지 않았다(코드
    고정). 빈도 표의 『추가』 표시는 이 칸과 무관하게 기본 목록 기준이다."""
    items: list[Item]
    """판정 문장. 쪽 차례, 쪽 안에서는 노트북이 낸 차례. 실행마다 한 번 쓰면 바뀌지 않고 items 의 차례가 고정이다 —
    (runId, itemIndex) 가 문장의 고정 열쇠다(검토 표시·비교·엑셀이 이것으로 잇는다)."""
    candidateStats: CandidateStats
    """후보 집계."""
    counts: Counts
    """items 의 건수."""
    wordCounts: WordCounts
    """의심 낱말 빈도."""
    dryRun: None
    """dry-run 이 아니므로 null."""
    report: Report
    """엑셀 보고서."""


@with_config(FORBID)
class DryRunResult(TypedDict):
    """greenwash.result@1 — dry-run(AI 를 부르지 않고 요청 수·글자·토큰만 센 실행). dryRun 이 채워지고 items 는 빈
    목록, candidateStats·counts·report 는 null 이다. wordCounts 는 AI 가 필요 없어 채운다. 키는 ScanResult 와 같다."""

    schemaVersion: Literal["greenwash.result@1"]
    source: Source
    config: Config
    models: Models
    """노트북 설정의 모델 이름(실제로 불린 모델이 아니다)."""
    promptVersion: str
    """노트북 프롬프트의 판. E0 는 2026-01-15-v1."""
    parts: list[Part]
    """파트 셋과 그 쪽."""
    pages: list[Page]
    """점검할 쪽(파트의 합집합, 1부터, 오름차순)."""
    extraTerms: ExtraTerms
    """사용자가 이 점검에 더한 단어(받은 꼴 그대로, 받은 차례). 판정 대상 키워드(환경 낱말)에 모두 썼고, 단어 빈도에는
    기본 목록과 겹치지 않는 것만 더했다. 한 번도 안 나온 단어는 빈도 표에 줄이 없다. 빈도 표의 『추가』 표시는 화면
    몫이다. 기본 목록 단어는 화면이 입력 때 막는다. 중복 제거와 기본 목록 비교는 대소문자·하이픈·띄어쓰기를 무시한
    글자 그대로라(「탄소 중립」 = 「탄소중립」), 노트북 목록에서 붙어 버린 낱말의 조각(예: eco)은 따로 세어진다."""
    terms: NotRequired[UsedTerms]
    """이 실행이 의심 낱말 빈도에 센 낱말 전체(차례 그대로 — 밴드 G2d): AI 설정 판의 켠 대상 단어(판 차례) 뒤에 추가
    단어 가운데 비교 키가 판 단어와 같지 않은 것. 판의 대상 단어로 센 실행에만 있다 — 칸이 없으면 코드 기본 목록
    (GET /greenwash/terms/default) + 추가 단어로 셌다. 판 단어는 판정할 문장을 고르는 환경 낱말에는 쓰지 않았다(코드
    고정). 빈도 표의 『추가』 표시는 이 칸과 무관하게 기본 목록 기준이다."""
    items: Annotated[list[Item], Field(max_length=0)]
    """dry-run 은 판정하지 않으므로 빈 목록."""
    candidateStats: None
    counts: None
    wordCounts: WordCounts
    """의심 낱말 빈도."""
    dryRun: DryRun
    """dry-run 의 셈."""
    report: None


GreenwashResult = Annotated[
    ScanResult | DryRunResult,
    Field(
        title="greenwash.result@1",
        description=(
            "흐름 greenwash.colab@E0 의 결과. 두 갈래(ScanResult·DryRunResult)의 키는 같고 dryRun 이 null 이면 "
            "ScanResult(점검한 실행), 아니면 DryRunResult(dry-run)다. "
            "갈래마다의 규칙은 $defs 의 두 갈래 description 에. "
            "결과는 실행마다 한 번 쓰면 바뀌지 않고 items 의 차례가 고정이다 — (runId, itemIndex) 가 문장의 "
            "고정 열쇠다(검토 표시·비교·엑셀이 이것으로 잇는다)."
        ),
    ),
]
"""greenwash.result@1. 두 갈래의 키는 같고 dryRun 이 null 이면 ScanResult, 아니면 DryRunResult 다.
결과는 실행마다 한 번 쓰면 바뀌지 않고 items 의 차례가 고정이다 — (runId, itemIndex) 가 문장의 고정 열쇠다(검토 표시·
비교·엑셀이 이것으로 잇는다)."""

RESULT_SHAPES: Final[Mapping[str, TypeAdapter[ScanResult | DryRunResult]]] = {
    SHAPE: TypeAdapter[ScanResult | DryRunResult](GreenwashResult)
}
"""결과 꼴 id → 검사기. validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
