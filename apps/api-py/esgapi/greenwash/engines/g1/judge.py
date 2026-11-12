"""판정(luna, 프롬프트 greenwash/ge-judge@1): 기준 줄마다 걸림 · 등급 H/M/L/None · 카테고리 · 이유 · 확인된 것·빠진 것 ·
근거 단락 인용. 답 꼴은 구조화 출력(JudgeAnswer)이고 어긋나면 판정 실패다 — Mid 로 구제하지 않는다(E0 흠 8 반대).

기준 줄은 엔진이 박지 않는다: 흐름이 기준 판(flows/criteria_e0 기본 판 15줄 등)을 읽어 CriterionLine 으로 넘긴다(B1).
카테고리 목록도 인자다(MARC-ENT-612 전에는 빈 목록 → 카테고리는 null 만).
공급사는 포트(JudgePort) 하나로만 닿는다: (프롬프트 변수) → 답 | 실패 갈래. 그 다리(LlmClient)는 흐름의 몫이다.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

PROMPT_ID: Final = "greenwash/ge-judge@1"
ANSWER_MAX_TOKENS: Final = 2000
"""답의 출력 상한(R8). 호출 층이 luna 추론 여유 2000 을 더해 보낸다(보낸 상한 4000)."""

Level = Literal["High", "Mid", "Low", "None"]
JudgeFailure = Literal["judge_failed", "judge_unparsed", "judge_cut_off", "budget_exceeded"]
"""budget_exceeded = 실행 비용 상한(core 상한 — 부르기 전에 걸림, 642-2). 이름을 judge_failed 로 접지 않는다."""


class CriterionHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lineId: str
    hit: bool


class JudgeAnswer(BaseModel):
    """greenwash/ge-judge@1 의 답 꼴(구조화 출력)."""

    model_config = ConfigDict(extra="forbid")

    criteria: list[CriterionHit]
    level: Level
    category: str | None
    reason: str
    confirmed: list[str]
    missing: list[str]
    evidence: list[str]


@dataclass(frozen=True, slots=True)
class CriterionLine:
    """기준 줄 하나: id · 무리(대상 키워드·핵심 근거·High·Mid·예외) · 글. 걸리면 무엇이 되는지(E0 verdict)는 싣지
    않는다 — 등급은 프롬프트의 [등급] 정의로 정하고 기준 줄은 점검표다(검증 3 R2)."""

    id: str
    group: str
    text: str


@dataclass(frozen=True, slots=True)
class Judged:
    level: Level
    category: str | None
    reason: str
    confirmed: tuple[str, ...]
    missing: tuple[str, ...]
    criteria_hit: tuple[str, ...]
    cited: tuple[str, ...]
    kind: Literal["judged"] = "judged"


@dataclass(frozen=True, slots=True)
class NotJudged:
    code: JudgeFailure
    kind: Literal["not_judged"] = "not_judged"


type JudgeOutcome = Judged | NotJudged


@dataclass(frozen=True, slots=True)
class JudgeReply:
    """포트의 답: 성공이면 answer, 아니면 failure(공급사·시간 = judge_failed, 꼴 어긋남 = judge_unparsed, 출력 상한에서
    잘림 = judge_cut_off, 실행 비용 상한 = budget_exceeded)."""

    answer: JudgeAnswer | None
    failure: JudgeFailure | None = None


JudgePort = Callable[[Mapping[str, str]], JudgeReply]

GROUP_NAME: Final[Mapping[str, str]] = {
    "targetKeyword": "대상 키워드",
    "coreEvidence": "핵심 근거",
    "high": "High 조건",
    "mid": "Mid 조건",
    "exception": "예외(위험 아님)",
}


def criteria_text(lines: Sequence[CriterionLine]) -> str:
    return "\n".join(f"[{c.id}] ({GROUP_NAME.get(c.group, c.group)}) {c.text}" for c in lines)


def categories_text(categories: Sequence[str]) -> str:
    return " · ".join(categories) if categories else "(목록 없음 — category 는 반드시 null)"


def judge_vars(
    *, claim: str, page: int, evidence: str, lines: Sequence[CriterionLine], categories: Sequence[str]
) -> dict[str, str]:
    """프롬프트 변수. 근거가 비면(찾았는데 없음) 그렇다고 적는다."""
    return {
        "criteria": criteria_text(lines),
        "categories": categories_text(categories),
        "claim": claim,
        "page": str(page),
        "evidence": evidence or "(이 문서에서 근거로 쓸 단락을 찾지 못했다)",
    }


def judge(port: JudgePort, variables: Mapping[str, str], lines: Sequence[CriterionLine]) -> JudgeOutcome:
    reply = port(variables)
    if reply.answer is None:
        return NotJudged(code=reply.failure or "judge_failed")
    a = reply.answer
    known = {c.id for c in lines}
    return Judged(
        level=a.level,
        category=a.category,
        reason=a.reason.strip(),
        confirmed=tuple(x.strip() for x in a.confirmed if x.strip()),
        missing=tuple(x.strip() for x in a.missing if x.strip()),
        criteria_hit=tuple(dict.fromkeys(c.lineId for c in a.criteria if c.hit and c.lineId in known)),
        cited=tuple(dict.fromkeys(x.strip() for x in a.evidence if x.strip())),
    )
