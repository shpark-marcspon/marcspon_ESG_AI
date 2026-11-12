"""흐름 greenwash.rewrite@R1 — 끝난 점검 실행의 결과(greenwash.result@1)를 받아 level High·Mid 문장마다
대체표현(exampleSentence)을 채운 사본과 그 사본으로 다시 지은 엑셀을 낸다(MARC-ENT-277 ①, 프롬프트 판 4 MARC-ENT-309,
모델 gpt-6-luna MARC-ENT-314).

    rewrite → report

E0(greenwash.colab@E0) 뒤에 따로 부르는 흐름이고 E0 를 고치지 않는다. 받는 것도 내는 것도 결과 꼴 greenwash.result@1
이다. 사본은 items 의 차례·개수와 exampleSentence 밖의 칸(키 차례 포함)이 입력과 같고, Low 는 null 그대로다.

- rewrite  대상(High·Mid)을 BATCH_SIZE 씩 묶어 묶음마다 한 번 부른다(RewriteBridge.ask). 묶음 안의 문장은 번호 i(묶음 안
           차례 0..k-1)로 보내고 답의 i 로 짝짓는다 — 답의 차례는 믿지 않는다. 끝난 묶음마다 체크포인트하고
           (ctx.checkpoint), resume 이 있으면 끝난 묶음을 건너뛴다. 망가진 답은 그 문장(또는 그 묶음)만 null 로 두고
           warnings 에 센다. 공급사 오류·시간 초과·예산 초과는 단계 실패다(이어 돌기는 체크포인트로).
           dry-run 이면 묶음마다 RewriteBridge.estimate 만 하고 공급사를 부르지 않는다
           (warnings·nulled 는 null — 안 쟀다)
- report   입력 결과의 깊은 사본에 examples 를 넣고 엑셀(greenwash-report.xlsx)을 다시 짓는다. dry-run 이어도 결과는
           exampleSentence 가 전부 null 인 사본과 엑셀이다(ScanResult 는 report 가 null 일 수 없다)

경고·사용량·dry-run 셈은 결과 꼴(@1, extra="forbid")에 칸이 없어 단계 rewrite 의 data(실행 기록)에 둔다. 결과만 보고는
dry-run 인지 모른다 — 단계 data 가 가른다. 토큰 사용량의 진실은 core.llm 의 호출 기록이다.

프롬프트 글은 템플릿 본문이다(prompts/rewrite/4.md, 초안 band-handoffs/rewrite-prompt-draft-4.md 그대로 — 판 3 에서 값은
원문 것까지 모두 빈칸(MARC-ENT-309), 없는 행위를 수식어로 끼워 넣는 꼴도 금지, 마지막 자기 점검 줄, 예시의 값을 빈칸으로
바꾼 것. 판 1·2·3 의 1.md·2.md·3.md 는 판 기록으로 남는다). 글에 `{{` 가 없어 E0 의 봉투가 필요 없고, 호출 기록의
promptId·템플릿 sha256 이 판을 가른다. 흐름이 CallRequest 를 직접 짓는다(inventory 선례).
답 꼴은 구조화 출력이 강제한다(schema RewriteAnswer, 이름 rewrite — items 배열, 항목마다 i·example_sentence). 꼴이
틀리면 호출 층이 한 번 더 부르고(MAX_SCHEMA_RETRIES) 그래도 틀리면 SchemaMismatch 다. 호출 층의 JSON 읽기는 되풀이된
키를 마지막 하나로 접으므로(실호출 RWL1 의 "items" 되풀이, MARC-ISSUE-164) 흐름이 답 글자에서 되풀이된 키를 다시 보고
그 묶음을 schema_mismatch 로 센다 — 조용히 마지막 하나만 남기지 않는다.
판 3 의 뒤 검사 둘(MARC-ENT-288): 원문에 없는 평가어(COMMENTARY_WORDS)가 든 답은 그 문장 null + commentary, 종결 어미가
원문과 다른 답은 그대로 쓰고 ending_mismatch 를 센다. 판 4 의 셋째(MARC-ENT-309): 빈칸 밖에 숫자가 남은 답은 그대로 쓰고
value_outside_blank 를 센다(이름 속 숫자 NAME_NUMBER_PATTERNS 는 뺀다). 없는 행위 단정은 코드로 검사하지 않는다(실호출
결과를 읽어 센다).
이 파일은 설정·환경 변수·키를 읽지 않고 SDK 클라이언트를 짓지 않는다(tests/flows/test_boundary.py). 클라이언트는 부르는
쪽이 지어 RewriteAdapters 로 넘긴다. 결과 꼴 모듈(contracts/shapes.py)을 들이지 않는다(등록 길, registration.py 머리).

무효 조건: 결과 꼴이 @2 가 되면 INPUT_SHAPE·RESULT_SHAPE 와 RewriteInputs 의 검사를 다시 본다.
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from pydantic import BaseModel, ConfigDict

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, FlowStep, OutputFile, StepContext, StepOutput
from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.types import (
    BudgetExceeded,
    CutOff,
    DryRunReport,
    LlmResult,
    ProviderFailed,
    Refused,
    SchemaMismatch,
    Tags,
    TimedOut,
)
from esgapi.greenwash.engines.e0.gw1 import frequency_extras
from esgapi.greenwash.outputs import xlsx

FLOW_ID: Final = "greenwash.rewrite@R1"
INPUT_SHAPE: Final = "greenwash.result@1"
"""받는 것이 결과 꼴 그대로라는 표지(core 는 비교하지 않는 이름표)."""
RESULT_SHAPE: Final = "greenwash.result@1"
REPORT_FILE: Final = "greenwash-report.xlsx"

PROMPT_ID: Final = "greenwash/rewrite@4"
"""core.llm 프롬프트 id(모듈/이름@판). 템플릿은 esgapi/greenwash/prompts/rewrite/4.md(MARC-ENT-309). 판 1(1.md,
MARC-ENT-278)·판 2(2.md, MARC-ENT-279)·판 3(3.md, MARC-ENT-288)은 지우지 않는다."""
CHAT_ROUTE: Final = "light-openai"
"""core/llm/data/models.json 의 경로 이름(gpt-6-luna 하나, MARC-ENT-314). E0 의 경로(light-openai-41, gpt-4.1-mini)와
다르다 — MARC-ENT-278 「gpt-4.1-mini」 를 이 흐름에서 갈음했다(E0 는 코랩 재현이라 그대로). colab_e0 의 이름을 들이지
않고 따로 적는다. luna 는 temperature 를 받지 않아(core.llm TEMPERATURE_UNSUPPORTED_MODELS) 요청에 싣지 않는다 —
MARC-ENT-278 「temperature 0」 도 MARC-ENT-314 로 갈음했다. 값을 주면 공급사를 부르기 전에 LlmConfigError 다."""
BATCH_SIZE: Final = 10
"""한 번 부를 때 문장 수의 상한(MARC-ENT-278 「10문장 묶음」)."""
TARGET_LEVELS: Final = ("High", "Mid")
"""채우는 level(MARC-ENT-278 4). Low 는 null 그대로."""
LEVELS: Final = ("High", "Mid", "Low")
MAX_CHARS: Final = 200
"""프롬프트의 「200자 이내」. 부드러운 상한이다 — 넘겨도 그대로 쓰고 over_length 만 센다(RW1 발주서 §2-0 ④)."""
MAX_SCHEMA_RETRIES: Final = 1
"""답 꼴이 schema 와 다를 때 호출 층이 같은 모델로 다시 부르는 횟수(RW2 발주서 §2-2). 묶음 하나가 많아야 두 번 부른다 —
dry-run 의 어림은 한 번 부른 값이다(LlmClient.dry_run 은 다시 부르기를 세지 않는다)."""
MAX_OUTPUT_TOKENS: Final = 3000
"""추정: 10문장 × 200자, 한글이 o200k 에서 글자당 1토큰 안팎이라 보고 JSON 틀을 더한 값에 여유를 둔 것(재지 않았다).
모의 모델 상한 4000(core/llm/data/models.synthetic.json) 안. 답 글의 상한이고, luna 는 추론 토큰이 출력 상한을 같이 써서
호출 층이 models.json 의 reasoningOutputReserveTokens(2000, 실측 전 값)를 더해 5000 을 보낸다 — 실호출에서 truncated 가
뜨면 다시 본다(MARC-ENT-314)."""

BLANK: Final = re.compile(r"\[____: [^\[\]\n]+\]")
"""빈칸 꼴 `[____: 항목명]`(밑줄 넷, 쌍점, 빈칸 하나, 대괄호·줄바꿈 없는 항목명. MARC-ENT-278 1). 화면이 빈칸을 강조할
때도 이 꼴이다. 글에서 맞은 곳을 다 지운 나머지에 `[_` 나 `__` 가 남으면 빈칸 규칙 어김이다(blank_malformed)."""

USER_BLOCK: Final = (
    "[문장 i={i}]\n"
    "원문: {sentence}\n"
    "리스크 등급: {level}\n"
    "위험 유형: {risk_tags}\n"
    "근거에서 확인된 사실:{confirmed}\n"
    "빠진 항목:{missing}\n"
    "수정 방향: {fix}"
)
"""문장 하나의 user 덩이(초안 「프롬프트 (user, 문장마다 반복)」의 꼴). 값은 format 의 값 자리로만 넣는다 — 문장 안의
`{`·`}` 가 틀을 깨지 않는다. 목록 칸(confirmed·missing)은 user_block 이 펴서 넣는다. 덩이끼리는 빈 줄 하나로 잇는다."""
NONE_LISTED: Final = "없음"

WARNINGS: Final = (
    "refused",
    "truncated",
    "schema_mismatch",
    "not_json",
    "missing_i",
    "duplicate_i",
    "unknown_i",
    "not_text",
    "blank_malformed",
    "over_length",
    "commentary",
    "ending_mismatch",
    "value_outside_blank",
)
"""단계 rewrite 의 data.warnings 의 키(실제 실행이면 다 있다. dry-run 이면 warnings 가 null). 판 2 부터 not_json 은 오지
않는다(키는 G1b 가 읽어 남긴다) — 꼴이 틀린 답은 구조화 출력 아래 SchemaMismatch(되풀이된 키 포함)라 schema_mismatch 로
센다. commentary·ending_mismatch 는 판 3 의 뒤 검사(MARC-ENT-288), value_outside_blank 는 판 4 의 것(MARC-ENT-309)이다 —
키는 끝에 더하기만 한다."""
COMMENTARY_WORDS: Final = ("필요", "추정", "확인할 수 있음", "제시함", "바람직")
"""판 3 이 금한 평가어(MARC-ENT-288). 답에 있고 원문에 없으면 그 문장은 고쳐 쓴 문장이 아니라 지적 글로 본다
(commentary)."""
HAPSYO: Final = "합쇼체"
HAERA: Final = "해라체"
ENDING_TRAILERS: Final = ". \t\n)）"
"""어미를 가르기 전에 글 끝에서 벗기는 글자(마침표·공백·닫는 괄호)."""
NAME_NUMBER_PATTERNS: Final = (
    re.compile(r"Scope ?[123](?:(?: ?[·,] ?| 및 )[123])*(?![0-9])"),
    re.compile(r"ISO ?[0-9]+(?:-[0-9]+)*"),
)
"""이름 속 숫자(값이 아님 — 판 4 「「Scope 1·2」「ISO 14001」처럼 이름에 든 숫자」): Scope 1·2·3(가운뎃점·쉼표·「및」
이음, 띄어쓰기 변형. 대문자 Scope 만)과 ISO 번호(ISO 14001, ISO 14064-1). 이 두 꼴만 뺀다."""
DIGIT: Final = re.compile(r"[0-9０-９]")
FAILED_BATCH: Final[Mapping[str, str]] = {
    "refusal": "refused",
    "truncated": "truncated",
    "schema_mismatch": "schema_mismatch",
}
"""그 묶음의 문장을 전부 null 로 두는 결과 갈래(LlmResult.kind) → 경고 이름."""


class RewriteAnswerItem(BaseModel):
    """답의 항목 하나: 보낸 번호 i 와 고쳐 쓴 예시 문장."""

    model_config = ConfigDict(extra="forbid")

    i: int
    example_sentence: str


class RewriteAnswer(BaseModel):
    """구조화 출력의 답 꼴(schema 이름 SCHEMA_NAME). i 의 범위·빠짐·겹침·빈 글·빈칸 꼴은 schema 가 막지 못해 pair 가
    본다."""

    model_config = ConfigDict(extra="forbid")

    items: list[RewriteAnswerItem]


SCHEMA_NAME: Final = "rewrite"


# ── 어댑터 ───────────────────────────────────────────────────────────────────


class RewriteBridge:
    """대체표현 묶음 하나 → core.llm. 부르기(ask)와 어림(estimate)이 같은 request() 를 쓴다 — dry-run 이 실제로 보낼
    것을 센다. 클라이언트는 부르는 쪽이 짓는다."""

    def __init__(self, client: LlmClient, *, route: str = CHAT_ROUTE, tags: Tags) -> None:
        self.client = client
        self.route = route
        self.tags = tags

    def request(self, sentences: str) -> CallRequest[RewriteAnswer]:
        return CallRequest(
            prompt=PROMPT_ID,
            route=self.route,
            tags=self.tags,
            vars={"sentences": sentences},
            schema=RewriteAnswer,
            schema_name=SCHEMA_NAME,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            max_schema_retries=MAX_SCHEMA_RETRIES,
        )

    def ask(self, sentences: str) -> LlmResult[RewriteAnswer]:
        return self.client.call(self.request(sentences))

    def estimate(self, sentences: str) -> DryRunReport:
        """공급사를 부르지 않는다(LlmClient.dry_run)."""
        return self.client.dry_run(self.request(sentences))


@dataclass(frozen=True, slots=True, kw_only=True)
class RewriteAdapters:
    llm: RewriteBridge


# ── 입력 ─────────────────────────────────────────────────────────────────────


def _is_texts(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in cast("list[object]", value))


@dataclass(frozen=True, slots=True, kw_only=True)
class RewriteInputs:
    """greenwash.result@1 의 점검한 실행(ScanResult) 하나. 이 흐름이 읽는 칸만 검사한다(어기면 ValueError) — 결과 꼴
    전체 검사(pydantic)는 등록 길에서 하지 않는다. 들어온 dict 는 고치지 않는다."""

    result: Mapping[str, object]
    dry_run: bool = False

    def __post_init__(self) -> None:
        result = self.result
        if result.get("schemaVersion") != RESULT_SHAPE:
            raise ValueError(f"결과 꼴이 {RESULT_SHAPE} 가 아니다: {result.get('schemaVersion')!r}")
        if result.get("dryRun") is not None:
            raise ValueError("dry-run 결과에는 고칠 문장이 없다")
        items = result.get("items")
        if not isinstance(items, list):
            raise ValueError("items 가 목록이 아니다")
        for n, given in enumerate(cast("list[object]", items)):
            if not isinstance(given, dict):
                raise ValueError(f"items[{n}] 가 객체가 아니다")
            item = cast("dict[str, object]", given)
            if item.get("level") not in LEVELS:
                raise ValueError(f"items[{n}].level 이 {LEVELS} 밖이다: {item.get('level')!r}")
            for key in ("sentence", "fixParagraph"):
                if not isinstance(item.get(key), str):
                    raise ValueError(f"items[{n}].{key} 가 글자가 아니다")
            for key in ("riskTags", "confirmedInEvidence", "missingFields"):
                if not _is_texts(item.get(key)):
                    raise ValueError(f"items[{n}].{key} 가 글자 목록이 아니다")


def _items(inputs: RewriteInputs) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", inputs.result["items"])


# ── 덩이와 답 ─────────────────────────────────────────────────────────────────


def _listed(values: Sequence[str]) -> str:
    """목록 칸: 머리 줄 다음 줄부터 한 줄에 하나 `- <값>`, 빈 목록이면 머리 줄에 `없음`."""
    if not values:
        return " " + NONE_LISTED
    return "".join("\n- " + value for value in values)


def user_block(i: int, item: Mapping[str, Any]) -> str:
    return USER_BLOCK.format(
        i=i,
        sentence=item["sentence"],
        level=item["level"],
        risk_tags=", ".join(item["riskTags"]),
        confirmed=_listed(item["confirmedInEvidence"]),
        missing=_listed(item["missingFields"]),
        fix=item["fixParagraph"],
    )


def user_text(items: Sequence[Mapping[str, Any]]) -> str:
    """묶음 하나의 user 글: 덩이(i = 묶음 안 차례)를 빈 줄 하나로 잇는다."""
    return "\n\n".join(user_block(i, item) for i, item in enumerate(items))


def answer_items(answer: RewriteAnswer) -> list[dict[str, object]]:
    """schema 를 지난 답 → pair 가 읽는 dict 목록(답의 차례 그대로)."""
    return [item.model_dump() for item in answer.items]


def repeated_keys(text: str) -> bool:
    """답 글자의 어느 객체에든 같은 키가 둘 이상 있으면 True. 호출 층의 JSON 읽기는 되풀이된 키를 마지막 하나로 접는다
    (MARC-ISSUE-164 의 `{"items": […], "items": […]}`). 글이 JSON 이 아니면 False — 그것은 호출 층이 이미 걸렀다."""
    found = False

    def pairs(given: list[tuple[str, object]]) -> dict[str, object]:
        nonlocal found
        keys = [key for key, _ in given]
        found = found or len(keys) != len(set(keys))
        return dict(given)

    try:
        json.loads(text, object_pairs_hook=pairs)
    except ValueError:
        return False
    return found


def blank_malformed(text: str) -> bool:
    rest = BLANK.sub("", text)
    return "[_" in rest or "__" in rest


def commentary(text: str, sentence: str) -> bool:
    """답에 원문에 없는 평가어(COMMENTARY_WORDS)가 있으면 True. 낱말 맞춤은 부분 글자 일치라 활용형(「필요한」
    「필요성」)도 들고, 한계로 「불필요」처럼 낱말 안에 든 것도 걸린다(오탐 — 그 문장이 null 이 될 뿐 실행은 간다).
    원문에 이미 있는 낱말은 걸지 않는다(원문 대조)."""
    return any(word in text and word not in sentence for word in COMMENTARY_WORDS)


def ending(text: str) -> str | None:
    """종결 어미의 갈래. 글 끝의 ENDING_TRAILERS 를 벗긴 뒤 「니다」로 끝나면 합쇼체, 「다」로 끝나면 해라체, 그 밖
    (「…등」, 벗긴 뒤 괄호 안 각주로 끝남 등)은 판정하지 않는다(None). 한계: 해라체 「아니다」「지니다」처럼 「니다」로
    끝나는 낱말도 합쇼체로 가른다(원문 「…아니다.」와 답 「…아닙니다.」의 다름을 못 센다 — 세지 않는 쪽이라 문장은
    그대로 쓴다)."""
    rest = text.rstrip(ENDING_TRAILERS)
    if rest.endswith("니다"):
        return HAPSYO
    if rest.endswith("다"):
        return HAERA
    return None


def ending_mismatch(text: str, sentence: str) -> bool:
    """답과 원문의 어미가 둘 다 판정됐는데 다르면 True. 판정 안 된 쪽이 있으면 세지 않는다."""
    got, was = ending(text), ending(sentence)
    return got is not None and was is not None and got != was


def value_outside_blank(text: str) -> bool:
    """빈칸(BLANK)과 이름 속 숫자(NAME_NUMBER_PATTERNS)를 다 지운 나머지에 아라비아 숫자가 있으면 True(판 4 「값은 모두
    빈칸」을 어긴 답 — 문장은 그대로 쓴다). 빈칸 안의 숫자(항목명 「감축률(%)」 「적용 범위(Scope 1·2 등)」)는 세지
    않는다. 한계: 두 꼴 밖의 이름 속 숫자(「ISO 14001:2015」의 판 연도, 「GRI 305」, 「RE100」, 「제3자」, 「1차」 등)도
    값으로 센다(오탐 — 경고만 늘고 문장은 그대로). 한자·한글로 쓴 수(「삼십 퍼센트」)는 세지 못한다."""
    rest = BLANK.sub("", text)
    for pattern in NAME_NUMBER_PATTERNS:
        rest = pattern.sub("", rest)
    return DIGIT.search(rest) is not None


def pair(
    answers: Sequence[Mapping[str, object]], sentences: Sequence[str], warnings: dict[str, int]
) -> list[str | None]:
    """답의 items 를 보낸 i(0..k-1, k = 원문 sentences 의 수)에 짝짓는다. 문장마다 글자나 null. warnings 를 늘린다.
    검사 차례(고정): 빈 글 → 빈칸 꼴 → 평가어(null) → 200자(남김) → 어미(남김) → 빈칸 밖 숫자(남김). null 이 된
    문장은 뒤의 것을 세지 않는다."""
    k = len(sentences)
    found: dict[int, list[Mapping[str, object]]] = {}
    for answer in answers:
        i = answer.get("i")
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < k:
            warnings["unknown_i"] += 1
            continue
        found.setdefault(i, []).append(answer)
    filled: list[str | None] = []
    for i in range(k):
        got = found.get(i, [])
        if not got:
            warnings["missing_i"] += 1
            filled.append(None)
            continue
        if len(got) > 1:
            warnings["duplicate_i"] += 1
            filled.append(None)
            continue
        value = got[0].get("example_sentence")
        if not isinstance(value, str) or not value.strip():
            warnings["not_text"] += 1
            filled.append(None)
            continue
        text = value.strip()
        if blank_malformed(text):
            warnings["blank_malformed"] += 1
            filled.append(None)
            continue
        if commentary(text, sentences[i]):
            warnings["commentary"] += 1
            filled.append(None)
            continue
        if len(text) > MAX_CHARS:
            warnings["over_length"] += 1
        if ending_mismatch(text, sentences[i]):
            warnings["ending_mismatch"] += 1
        if value_outside_blank(text):
            warnings["value_outside_blank"] += 1
        filled.append(text)
    return filled


# ── rewrite ──────────────────────────────────────────────────────────────────


def batches_of(items: Sequence[Mapping[str, Any]]) -> list[list[int]]:
    """대상(level ∈ TARGET_LEVELS)의 items 차례를 오름차순으로 BATCH_SIZE 씩 묶는다. 같은 입력이면 같은 나눔."""
    targets = [n for n, item in enumerate(items) if item["level"] in TARGET_LEVELS]
    return [targets[at : at + BATCH_SIZE] for at in range(0, len(targets), BATCH_SIZE)]


def _fresh(count: int, dry_run: bool) -> dict[str, Any]:
    return {
        "done": 0,
        "examples": [None] * count,
        "warnings": None if dry_run else dict.fromkeys(WARNINGS, 0),
        "calls": [],
        "dry_run": None
        if not dry_run
        else {"requests": 0, "model": None, "input_tokens": 0, "max_output_tokens": 0, "cost_upper_bound_usd": 0.0},
    }


def _resumed(resume: Mapping[str, object], count: int, dry_run: bool) -> dict[str, Any]:
    state = cast("dict[str, Any]", json.loads(json.dumps(resume)))
    if set(state) != set(_fresh(0, dry_run)) or len(state["examples"]) != count:
        raise ValueError("resume 이 이 흐름의 부분 산출물 꼴이 아니다")
    if (state["dry_run"] is None) == dry_run:
        raise ValueError("resume 과 이번 실행의 dry-run 이 다르다")
    return state


def rewrite(inputs: RewriteInputs, adapters: RewriteAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    items = _items(inputs)
    batches = batches_of(items)
    resume = ctx.resume
    state = _fresh(len(items), inputs.dry_run) if resume is None else _resumed(resume, len(items), inputs.dry_run)
    examples = cast("list[str | None]", state["examples"])
    for number in range(int(state["done"]), len(batches)):
        batch = batches[number]
        sentences = user_text([items[n] for n in batch])
        if inputs.dry_run:
            report = adapters.llm.estimate(sentences)
            dry = cast("dict[str, Any]", state["dry_run"])
            dry["requests"] += 1
            dry["model"] = report.model
            dry["input_tokens"] += report.estimate.input_tokens
            dry["max_output_tokens"] += report.estimate.max_output_tokens
            dry["cost_upper_bound_usd"] = round_usd(dry["cost_upper_bound_usd"] + report.estimate.cost_upper_bound_usd)
        else:
            _ask(adapters.llm, sentences, number, batch, [items[n]["sentence"] for n in batch], examples, state)
        state["done"] = number + 1
        ctx.checkpoint(state, done=number + 1, total=len(batches))
    targets = sum(len(batch) for batch in batches)
    nulled = None if inputs.dry_run else sum(1 for batch in batches for n in batch if examples[n] is None)
    return StepOutput(
        data={
            "targets": targets,
            "batches": len(batches),
            "examples": examples,
            "nulled": nulled,
            "warnings": state["warnings"],
            "calls": state["calls"],
            "dry_run": state["dry_run"],
        }
    )


def _ask(
    llm: RewriteBridge,
    sentences: str,
    number: int,
    batch: Sequence[int],
    originals: Sequence[str],
    examples: list[str | None],
    state: dict[str, Any],
) -> None:
    """묶음 하나를 부르고 examples·warnings·calls 를 채운다. originals 는 묶음 안 차례의 원문(뒤 검사의 대조).
    공급사 오류·시간 초과·예산 초과는 RuntimeError."""
    result = llm.ask(sentences)
    if isinstance(result, ProviderFailed | TimedOut | BudgetExceeded):
        raise RuntimeError(f"대체표현 부르기가 실패했다(묶음 {number}): {result.kind}")
    meta = result.meta
    state["calls"].append(
        {"batch": number, "callId": meta.call_id, "promptId": meta.prompt_id, "totalCostUsd": meta.total_cost_usd}
    )
    warnings = cast("dict[str, int]", state["warnings"])
    if isinstance(result, Refused | CutOff | SchemaMismatch):
        warnings[FAILED_BATCH[result.kind]] += len(batch)
        return
    if repeated_keys(result.text):
        warnings["schema_mismatch"] += len(batch)
        return
    for n, text in zip(batch, pair(answer_items(result.data), originals, warnings), strict=True):
        examples[n] = text


# ── report ───────────────────────────────────────────────────────────────────


def report(inputs: RewriteInputs, adapters: RewriteAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    examples = cast("list[str | None]", carried["rewrite"].data["examples"])
    result = cast("dict[str, Any]", json.loads(json.dumps(inputs.result, ensure_ascii=False)))
    for item, example in zip(cast("list[dict[str, Any]]", result["items"]), examples, strict=True):
        item["exampleSentence"] = example
    book = OutputFile(
        name=REPORT_FILE,
        media_type=xlsx.MEDIA_TYPE,
        content=xlsx.build(result, added_terms=frequency_extras(result["extraTerms"])),
    )
    return StepOutput(data={"results": [result]}, files=(book,))


STEPS: Final[tuple[FlowStep[RewriteInputs, RewriteAdapters], ...]] = (
    FlowStep(name="rewrite", run=rewrite),
    FlowStep(name="report", run=report),
)

FLOW: Final = make_flow(
    module="greenwash",
    id=FLOW_ID,
    input_shape=INPUT_SHAPE,
    inputs=RewriteInputs,
    adapters=RewriteAdapters,
    result_shapes=(RESULT_SHAPE,),
    output_files=(REPORT_FILE,),
    steps=STEPS,
)
