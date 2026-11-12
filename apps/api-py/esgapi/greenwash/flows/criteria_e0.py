"""E0 판의 판정(EVAL) 프롬프트 = 고정 틀 + 기준표(greenwash.criteria@1, 15줄). 틀·기본 판·조립·받기·판 묶음 값.

엔진의 글(engines/e0/prompts.py 의 EVAL)은 그대로 두고, 그 글을 「고칠 수 없는 틀」과 「고칠 수 있는 15줄」로
갈라 여기서 다시 잇는다. 틀과 줄 앞머리는 노트북 글의 것이라 E0 판에 묶인다(README 「다음 판 넣는 법」 — 판의
프롬프트를 아는 판단은 그 판의 흐름에 둔다).

- 기본 판(default_criteria)을 조립하면 엔진 글과 바이트가 같다(tests/flows/test_criteria_e0.py). 흠도 그대로다 — 예외
  조항 줄의 앞머리는 `-` 뒤에 띄어쓰기가 없다.
- 조립(build_eval_prompt)은 이어 붙이기로만 한다. 사용자가 쓴 글에 str.format·f-string·`%` 를 쓰지 않는다 — 기준 글의
  `{`·`}`·`{prompt_version}` 이 글자 그대로 남는다. 판 글자는 첫 줄 `[PromptVersion: …]` 에만 들어간다.
- 끈 줄은 줄째 빠진다. 한 구분을 모두 꺼도 같은 규칙 하나다(MARC-ENT-329): 틀의 글(절 머리·소개 줄·절 사이 빈 줄)은
  한 글자도 바뀌지 않고, 자리 표시 줄을 넣지 않는다. 그래서 빈 구분의 조립 글은 원본에서 그 구분의 줄들만 지운 글이다.
  무효 조건: 실호출에서 빈 절이 판정을 흔든다는 근거가 나오면 자리 표시 줄을 사용자에게 묻는다.
- 근거 가이드라인은 조립에 쓰지 않는다(MARC-ENT-329).
- 판 묶음 값(run_versions): 실행 행의 versions 에 실을 {"aiSetting", "evalPromptSha256"}. 부르는 자리는 그린워싱 끼움의
  `versions(options)`(밴드 G1b — core/flows/binding.py 의 RunBinding.versions)이고, 판 글자를 judge 와 같은 길로 넘기는
  flows/colab_e0.run_versions 를 부른다. 실행기가 `flow` 열쇠를 덧붙인다.
  `aiSetting` 은 AU1b·AD-04 도 읽는 열쇠, `evalPromptSha256` 은 그린워싱만 읽는 열쇠다.
- 받기(accept_criteria)의 거절은 CriteriaRejected(ValueError) 이고 문장은 화면에 그대로 보일 꼴이다. G1b 끼움이
  RunOptionsRejected 로, G2c-2 의 저장 경로가 E2 400 으로 옮긴다(code 는 E2 응답의 code 그대로).
"""

import hashlib
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import replace
from typing import Final, NoReturn, cast

from pydantic import ValidationError

from esgapi.greenwash.contracts.criteria_shapes import (
    CRITERIA_SHAPES,
    SHAPE,
    GreenwashCriteria,
    GreenwashCriterionCategory,
    GreenwashCriterionGuideline,
    GreenwashCriterionId,
    GreenwashCriterionRow,
    GreenwashCriterionVerdict,
)
from esgapi.greenwash.engines.e0.prompts import PromptPack, default_prompts

DEFAULT_VERSION: Final = "colab-2026-01-15-v1"
"""기본 판(코랩 노트북의 기준표)이 든 AI 설정 판의 이름."""

ROWS: Final[tuple[tuple[GreenwashCriterionId, GreenwashCriterionCategory], ...]] = (
    ("keyword-ghg", "targetKeyword"),
    ("keyword-exclusion", "targetKeyword"),
    ("evidence-quantity", "coreEvidence"),
    ("evidence-baseline", "coreEvidence"),
    ("evidence-boundary", "coreEvidence"),
    ("evidence-offset", "coreEvidence"),
    ("high-1", "high"),
    ("high-2", "high"),
    ("high-3", "high"),
    ("high-4", "high"),
    ("mid-1", "mid"),
    ("exception-1", "exception"),
    ("exception-2", "exception"),
    ("exception-3", "exception"),
    ("exception-4", "exception"),
)
"""줄 id 와 구분 — 차례가 곧 order(1..15)다."""

VERDICT: Final[Mapping[GreenwashCriterionCategory, GreenwashCriterionVerdict]] = {
    "targetKeyword": "coreEvidenceApplies",
    "coreEvidence": "highIfMissing",
    "high": "High",
    "mid": "Mid",
    "exception": "NonRisk",
}
"""구분 → 판정 결과(고칠 수 없음)."""

PREFIX: Final[Mapping[GreenwashCriterionCategory, str]] = {
    "targetKeyword": "- ",
    "coreEvidence": "- ",
    "high": "- ",
    "mid": "- ",
    "exception": "-",  # 노트북의 흠 그대로(띄어쓰기 없음)
}
"""줄 앞머리. 줄 글 = 앞머리 + 본문, 키워드 줄의 본문은 `이름: 낱말, 낱말, …`."""

TERMS_SEPARATOR: Final = ", "
KEYWORD_SEPARATOR: Final = ": "

# ── 틀: 엔진 EVAL 에서 15줄을 뺀 나머지(줄 단위). 줄 사이는 "\n" 하나 ──────────────────────────────────

_VERSION_OPEN: Final = "[PromptVersion: "
_VERSION_CLOSE: Final = "]"
_INTRO: Final = (
    "당신은 ESG 보고서 문장의 그린워싱(표시·광고 오인) 가능성을 평가하는 전문가입니다.",
    "",
    "[입력]",
    "- 후보 문장 1개",
    "- 근거 컨텍스트(p.페이지): 제공된 컨텍스트 안에서만 판단합니다(추측 금지).",
    "",
    "[판정 규칙]",
    "- 이 프롬프트에서 'Low' 판정은 금지입니다. (Low는 시스템에서 이미 확정 처리합니다)",
    "- 근거 컨텍스트가 비어 있으면 NonRisk 판정 금지(최소 Mid).",
    "- 제공된 근거가 충분해 오해 소지가 해소되면 NonRisk로 판정하고, 결과 리포트에서 제외될 수 있도록 합니다.",
    "",
    "[온실가스/배제용어(강화 규칙)]",
    "다음 키워드가 문장에 포함되면 '온실가스/배제용어 Claim'으로 간주합니다:",
)
_EVIDENCE_HEAD: Final = (
    '▶ 온실가스/배제용어 Claim은 표현이 완곡하더라도, 근거 컨텍스트에서 아래의 핵심 근거가 "충분히" 확인되지 않으면'
    " High로 판정합니다.",
)
_HIGH_HEAD: Final = (
    "",
    "[등급]",
    "▶ High",
)
_MID_HEAD: Final = (
    "",
    "▶ Mid",
)
_EXCEPTION_HEAD: Final = (
    "",
    "[예외 조항 (Safe Harbor Rules)]",
    "다음과 같은 **'외부 객관적 근거'**가 포함된 정성적 주장은 정량 수치가 없어도 Non-Risk로 판정합니다.",
)
_OUTPUT: Final = (
    "",
    "[출력(JSON only)]",
    "{",
    '  "decision": "High|Mid|NonRisk",',
    '  "risk_tags": ["최대 3개"],',
    '  "confirmed_in_evidence": ["2~4개 (컨텍스트에서 직접 확인되는 사실만)"],',
    '  "missing_fields": ["필요시 2~6개 (정의/기준, 범위/경계, 산정/방법, 수치 등 구체적으로)"],',
    '  "reason_bullets": ["High/Mid인 경우에만 2~3개, 위험/모호성/부족만 개조식"],',
    '  "fix_paragraph": "High/Mid인 경우에만 4~6문장 줄글(마지막 문장 종결: 합니다/습니다/입니다.)",',
    '  "evidence_internal": "판단 근거 1~2문장(p.페이지 포함)"',
    "}",
)

# ── 기본 판: 엔진 EVAL 의 15줄에서 앞머리를 뗀 나머지(흠까지 그대로) ─────────────────────────────────

_DEFAULT_TEXT: Final[Mapping[GreenwashCriterionId, str]] = {
    "keyword-ghg": "온실가스",
    "keyword-exclusion": "배제용어",
    "evidence-quantity": "정량 수치(절감량/비율 등) 또는 정량 산출 결과",
    "evidence-baseline": "기준연도/비교 기준(예: 2019 대비, 기준기간)",
    "evidence-boundary": "범위/경계(조직/사업/제품/지역, Scope 1/2/3, 포함·제외 조건)",
    "evidence-offset": "온실가스 용어만 해당: 감축과 상쇄(크레딧/REC 등) 구분(혼용 또는 불명확하면 High)",
    "high-1": (
        "절대적·단언적 표현(100%, 완전, 제로, 무공해, 기후중립, 탄소배출 제로 등), 사업영역 배제용어(친환경 신기술/신사"
        "업, 청정 기술, 그린 투자, 그린 포트폴리오),관용적 오사용 표현(청정수소, 청정 LNG, 그린 디젤) + 근거 불충분"
    ),
    "high-2": "탄소중립/넷제로 등 온실가스 목표·성과를 기준연도/범위/이행/검증 없이 사용",
    "high-3": (
        "온실가스/배제용어 Claim인데, 위 [온실가스/배제용어 강화 규칙]의 핵심 근거가 컨텍스트에서 충분히 확인되지 않음"
    ),
    "high-4": "환경주장 목표 및 성과가 있으나 정량 수치가 없는 경우",
    "mid-1": (
        "환경 주장·성과·목표는 있으나 기준연도/목표연도/비교 기준, 범위(Scope/사업/제품), 실행계획 중 일부가 불충분하여"
        " 오해 소지가 남는 경우"
    ),
    "exception-1": "국제 기구/이니셔티브 승인: SBTi 목표 승인, RE100 가입 승인 등 외부 공인 기관의 검토를 통과한 사실.",
    "exception-2": (
        "공인 인증 획득: ISO 14001(환경경영), 환경표지 인증, 저탄소 제품 인증 등 국가/국제 표준 인증 취득 사실."
    ),
    "exception-3": "제3자 검증 완료: 공인 인증기관으로부터 제3자 검증(Assurance)을 완료했다는 명시적 언급.",
    "exception-4": (
        "법적/거버넌스 체계: IFRS S2에서 요구하는 이사회 보고 체계, 기후 리스크 관리 프로세스 구축 등 제도적 장치 기술."
    ),
}
_DEFAULT_TERMS: Final[Mapping[GreenwashCriterionId, tuple[str, ...]]] = {
    "keyword-ghg": ("탄소", "온실가스", "CO2", "CO₂", "탄소중립", "넷제로", "Net Zero", "기후중립"),
    "keyword-exclusion": (
        "친환경",
        "환경친화",
        "자연적",
        "생분해 가능",
        "기후중립",
        "에코",
        "지속가능성",
        "동물친화적",
        "플라스틱중립",
        "탈플라스틱",
        "산림벌채 중단",
    ),
}


def default_criteria() -> GreenwashCriteria:
    """기본 판 15줄(전부 켬, 가이드라인 없음). 부를 때마다 새로 짓는다 — 부른 쪽이 고쳐도 다음 기본 판은 그대로다."""
    rows: list[GreenwashCriterionRow] = []
    for order, (row_id, category) in enumerate(ROWS, start=1):
        terms = _DEFAULT_TERMS.get(row_id)
        rows.append(
            {
                "id": row_id,
                "category": category,
                "order": order,
                "enabled": True,
                "text": _DEFAULT_TEXT[row_id],
                "terms": None if terms is None else list(terms),
                "verdict": VERDICT[category],
                "guideline": None,
            }
        )
    return {"schemaVersion": SHAPE, "version": DEFAULT_VERSION, "rows": rows}


# ── 조립 ─────────────────────────────────────────────────────────────────────────────────────────


def row_line(row: GreenwashCriterionRow) -> str:
    """줄 하나의 글 = 앞머리 + 본문. 키워드 줄의 본문은 이름 + ": " + 낱말을 ", " 로 이은 것."""
    terms = row["terms"]
    body = row["text"] if terms is None else row["text"] + KEYWORD_SEPARATOR + TERMS_SEPARATOR.join(terms)
    return PREFIX[row["category"]] + body


def build_eval_prompt(criteria: GreenwashCriteria, prompt_version: str) -> str:
    """판정 프롬프트(system 글). 켠 줄만 차례대로 틀의 절 자리에 이어 붙인다. 받은(accept_criteria) 기준표를 넣는다."""
    lines: dict[GreenwashCriterionCategory, list[str]] = {category: [] for category in VERDICT}
    for row in criteria["rows"]:
        if row["enabled"]:
            lines[row["category"]].append(row_line(row))
    return "\n".join(
        [
            _VERSION_OPEN + prompt_version + _VERSION_CLOSE,
            *_INTRO,
            *lines["targetKeyword"],
            *_EVIDENCE_HEAD,
            *lines["coreEvidence"],
            *_HIGH_HEAD,
            *lines["high"],
            *_MID_HEAD,
            *lines["mid"],
            *_EXCEPTION_HEAD,
            *lines["exception"],
            *_OUTPUT,
        ]
    )


def eval_pack(criteria: GreenwashCriteria, prompt_version: str) -> PromptPack:
    """엔진의 프롬프트 넷에서 판정 글만 기준표로 지은 것으로 바꾼 묶음. 나머지 셋(탐지·다시 묻기·Low 전용)은 그대로."""
    return replace(default_prompts(prompt_version), eval_system_prompt=build_eval_prompt(criteria, prompt_version))


def run_versions(criteria: object, prompt_version: str) -> dict[str, object]:
    """실행 판 묶음에 실을 값(끼움 versions() 의 반환 꼴). criteria 가 None 이면 기본 판, 그 밖은
    받기(accept_criteria)를 거친 값으로 짓는다 — 받기 전 원본(앞뒤 공백 등)으로 불러도 실행이 보낼 글의 해시와 같다.
    어기면 CriteriaRejected.

    prompt_version 은 실행의 judge 가 쓰는 판 글자다. 끼움은 flows/colab_e0.run_versions 를 부른다(judge 와 같은 길
    judged_prompt_version(SCAN_CONFIG) 로 판 글자를 넘긴다 — 이 파일은 흐름 설정을 모른다)."""
    used = default_criteria() if criteria is None else accept_criteria(criteria)
    text = build_eval_prompt(used, prompt_version)
    return {"aiSetting": used["version"], "evalPromptSha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


# ── 받기 ─────────────────────────────────────────────────────────────────────────────────────────

ROW_COUNT: Final = len(ROWS)
TEXT_CHARS: Final = 300
TERMS_MAX: Final = 30
TERM_CHARS: Final = 30
GUIDELINE_CHARS: Final = 200
VERSION_CHARS: Final = 64
VERSION_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
INVISIBLE: Final = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
"""한 줄 검사에서 막는 글자 범주: 제어(탭 등)·서식(U+200B 등)·짝 없는 서로게이트(UTF-8 로 못 씀)·사용자 정의·
배정 안 됨·줄 나눔(U+2028)·문단 나눔(U+2029)."""

MESSAGES: Final[Mapping[str, str]] = {
    "CRITERIA_SHAPE": "기준표의 꼴이 맞지 않아요",
    "CRITERIA_SCHEMA_VERSION": "기준표의 schemaVersion 은 greenwash.criteria@1 이어야 해요",
    "CRITERIA_VERSION": "판 이름은 영문이나 숫자로 시작하는 1~64자(영문·숫자·.·_·-)로 써 주세요",
    "CRITERIA_ROWS_FIXED": "기준표의 줄은 15줄 그대로여야 해요",
    "CRITERIA_ROW_ORDER": "기준표의 줄 차례(id·order)는 바꿀 수 없어요",
    "CRITERIA_ROW_KIND": "줄의 구분과 판정 결과는 바꿀 수 없어요",
    "CRITERIA_KEYWORD_NAME": "대상 키워드 묶음의 이름은 바꿀 수 없어요",
    "CRITERIA_TERMS_COUNT": "대상 키워드의 낱말은 1~30개로 넣어 주세요",
    "CRITERIA_TERM_LENGTH": "대상 키워드의 낱말은 1~30자로 써 주세요",
    "CRITERIA_TERM_COMMA": "대상 키워드의 낱말에는 쉼표를 쓸 수 없어요",
    "CRITERIA_TERM_DUPLICATE": "같은 묶음에 같은 낱말을 두 번 넣을 수 없어요",
    "CRITERIA_TERMS_NOT_ALLOWED": "낱말 목록은 대상 키워드 줄에만 넣을 수 있어요",
    "CRITERIA_TEXT_LENGTH": "기준 글은 1~300자로 써 주세요",
    "CRITERIA_TEXT_MULTILINE": "기준 글은 줄바꿈이나 보이지 않는 글자 없이 한 줄로 써 주세요",
    "CRITERIA_GUIDELINE_LENGTH": "근거 가이드라인은 1~200자로 써 주세요",
}
"""거절 code → 문장(해요체 한 문장). code 는 G2c-2 의 E2 응답이 그대로 쓴다. 한 줄 검사는 기준 글·낱말·가이드라인이
같은 code(CRITERIA_TEXT_MULTILINE)다. 한 구분을 모두 끈 기준표는 거절하지 않는다(MARC-ENT-329)."""


class CriteriaRejected(ValueError):
    """받기의 거절. str(e) 는 문장(MESSAGES), code 는 그 열쇠."""

    def __init__(self, code: str) -> None:
        super().__init__(MESSAGES[code])
        self.code = code


def _reject(code: str) -> NoReturn:
    raise CriteriaRejected(code)


def _one_line(text: str) -> bool:
    """줄 하나가 틀의 절 머리를 흉내 내지 못하게: 줄바꿈 없이 한 줄이고 보이지 않는 글자가 없다."""
    return len(text.splitlines()) == 1 and not any(unicodedata.category(c) in INVISIBLE for c in text)


def _accept_terms(row: GreenwashCriterionRow) -> list[str]:
    if row["text"].strip() != _DEFAULT_TEXT[row["id"]]:
        _reject("CRITERIA_KEYWORD_NAME")
    terms = [term.strip() for term in row["terms"] or []]
    if not 1 <= len(terms) <= TERMS_MAX:
        _reject("CRITERIA_TERMS_COUNT")
    for term in terms:
        if not 1 <= len(term) <= TERM_CHARS:
            _reject("CRITERIA_TERM_LENGTH")
        if "," in term:
            _reject("CRITERIA_TERM_COMMA")
        if not _one_line(term):
            _reject("CRITERIA_TEXT_MULTILINE")
    if len(set(terms)) != len(terms):
        _reject("CRITERIA_TERM_DUPLICATE")
    return terms


def _accept_text(row: GreenwashCriterionRow) -> str:
    text = row["text"].strip()
    if not 1 <= len(text) <= TEXT_CHARS:
        _reject("CRITERIA_TEXT_LENGTH")
    if not _one_line(text):
        _reject("CRITERIA_TEXT_MULTILINE")
    if row["terms"] is not None:
        _reject("CRITERIA_TERMS_NOT_ALLOWED")
    return text


def _accept_guideline(given: GreenwashCriterionGuideline | None) -> GreenwashCriterionGuideline | None:
    if given is None:
        return None
    text = given["text"].strip()
    if not 1 <= len(text) <= GUIDELINE_CHARS:
        _reject("CRITERIA_GUIDELINE_LENGTH")
    if not _one_line(text):
        _reject("CRITERIA_TEXT_MULTILINE")
    return {"text": text, "status": given["status"]}


def accept_criteria(given: object) -> GreenwashCriteria:
    """기준표 받기(발주서 G2c §2-3). 어기면 CriteriaRejected. 받은 꼴은 글·낱말·가이드라인의 앞뒤 공백을 지운 새 값이다.

    차례: schemaVersion → 꼴(strict, 모르는 키·타입·id 거절) → 판 이름 → 15줄 → 줄 차례(id·order) → 구분·판정 결과의
    짝 → 줄마다 글(키워드 줄은 이름 고정과 낱말 목록, 그 밖은 1~300자와 terms null) → 가이드라인.

    거절 code 와 문장은 MESSAGES 를 본다.

    판 이름 규칙은 추정이다 — G2c-2 가 판 이름 규칙을 정하면 따른다.
    """
    if not isinstance(given, dict) or cast("dict[str, object]", given).get("schemaVersion") != SHAPE:
        _reject("CRITERIA_SHAPE" if not isinstance(given, dict) else "CRITERIA_SCHEMA_VERSION")
    try:
        checked = CRITERIA_SHAPES[SHAPE].validate_python(given, strict=True)
    except ValidationError:
        _reject("CRITERIA_SHAPE")
    version = checked["version"]
    if not (len(version) <= VERSION_CHARS and VERSION_NAME.fullmatch(version)):
        _reject("CRITERIA_VERSION")
    if len(checked["rows"]) != ROW_COUNT:
        _reject("CRITERIA_ROWS_FIXED")
    rows: list[GreenwashCriterionRow] = []
    for order, ((row_id, category), row) in enumerate(zip(ROWS, checked["rows"], strict=True), start=1):
        if row["id"] != row_id or row["order"] != order:
            _reject("CRITERIA_ROW_ORDER")
        if row["category"] != category:
            _reject("CRITERIA_ROW_KIND")
        if row["verdict"] != VERDICT[category]:
            _reject("CRITERIA_ROW_KIND")
        keyword = category == "targetKeyword"
        rows.append(
            {
                "id": row_id,
                "category": category,
                "order": order,
                "enabled": row["enabled"],
                "text": row["text"].strip() if keyword else _accept_text(row),
                "terms": _accept_terms(row) if keyword else None,
                "verdict": VERDICT[category],
                "guideline": _accept_guideline(row["guideline"]),
            }
        )
    return {"schemaVersion": SHAPE, "version": version, "rows": rows}
