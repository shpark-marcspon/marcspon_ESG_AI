# pyright: basic
# ruff: noqa: SIM102, SIM103, UP006, UP034, UP035, UP045
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   겹친 if; bool 되돌리기; typing.List 꼴; 군더더기 괄호; typing 의 옛 이름; Optional 꼴
"""쪽 글 다듬기, 정규식·환경 낱말, 문장 가르기, 후보 거르기, Low 판정, JSON 구제, 폴백 문구.

노트북(AI그린워싱 점검_E0의 사본.ipynb)의 셀 14(0~4절) 소스에서 기계로 뽑아 글자 그대로 옮겼다.
흠을 고치지 않는다(py/greenwash/README.md 의 「일부러 남긴 흠」). 원본 대조(tests/notebook_probe.py)가 같음을 잰다.
"""

import json
import re
from typing import Any, Dict, List, Optional


def cap_text(s: str, max_chars: int) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "\n...(truncated)"


def cap_evidence_context(evidence: str, max_total_chars: int = 1600) -> str:
    return cap_text(evidence, max_total_chars)


def normalize_text_for_llm(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"(?<!\n)\n(?!\n)", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def get_page_text(doc, max_chars: int) -> str:
    raw = normalize_text_for_llm((getattr(doc, "page_content", "") or "").strip())
    if len(raw) > max_chars:
        raw = raw[:max_chars] + "\n...\n(이 페이지 텍스트는 일부만 잘라서 제공되었습니다.)"
    return raw


_FACT_TENSE_RE = re.compile(
    r"(수립|검증|승인|확인|인정|채택|공시|제출|분석|평가|적용|이행)"
    r"(하였|했|한|되었|되었습니다|됩니다|받았|받았습니다|"
    r"완료되었|완료되었습니다|확정되었|확정되었습니다|됨|중입니다|하고\s*있습니다)",
    re.IGNORECASE,
)


_LABEL_PATTERNS = [
    r"^\s*목차\b",
    r"^\s*Contents\b",
    r"^\s*Table of Contents\b",
    r"^\s*표\s*\d+",
    r"^\s*Figure\s*\d+",
    r"^\s*그림\s*\d+",
    r"^\s*페이지\s*\d+",
    r"^\s*p\.\s*\d+",
]


_PROMO_PHRASES_RE = re.compile(
    r"(지속가능한\s*성장|성장\s*기반|가치\s*창출|혁신|도전|리더십|앞장|추구|기여|"
    r"강화해\s*나가|기반을\s*마련|패러다임|비즈니스\s*기회|솔루션|미래\s*가치)",
    re.IGNORECASE,
)


_HIGH_RISK_KEYWORDS_RE = re.compile(
    r"(친환경\s*신기술|친환경\s*매출|그린\s*매출|지속가능\s*플라스틱|무공해|완전|100%|제로|"
    r"환경오염\s*방지|환경\s*가치\s*창출|탄소\s*중립|net\s*zero|탄소\s*배출\s*제로|기후\s*중립|"
    r"플라스틱\s*중립)",
    re.IGNORECASE,
)


DEFAULT_ENV_KEYWORDS = [
    # 기후/탄소
    r"탄소",
    r"온실가스",
    r"배출",
    r"넷제로",
    r"net\s*zero",
    r"탄소중립",
    r"기후대응",
    r"re100",
    r"scope\s*[123]",
    r"기후변화",
    r"기후\s*리스크",
    # 상쇄/크레딧/전력조달
    r"상쇄",
    r"offset",
    r"오프셋",
    r"크레딧",
    r"rec",
    r"i-?rec",
    r"k-?rec",
    r"배출권",
    r"ets",
    r"배출권거래",
    # 에너지
    r"에너지",
    r"재생에너지",
    r"전력",
    r"에너지\s*효율",
    r"mwh",
    r"kwh",
    r"gwh",
    r"ppa",
    r"rps",
    # 자원/순환/플라스틱
    r"자원순환",
    r"순환경제",
    r"재활용",
    r"재사용",
    r"플라스틱",
    r"pcr",
    r"rpet",
    r"폐기물",
    r"매립",
    r"소각",
    # 수자원/오염
    r"수자원",
    r"용수",
    r"취수",
    r"폐수",
    r"방류",
    r"수질",
    r"대기오염",
    r"미세먼지",
    r"nox",
    r"sox",
    r"voc",
    # 생물다양성/자연
    r"생물다양성",
    r"tnfd",
    r"sbtn",
    r"sbti",
    # 표준/평가/인증 (보고서에 자주 등장)
    r"탄소발자국",
    r"carbon\s*footprint",
    r"lca",
    r"전과정",
    r"epd",
    r"환경성적",
    r"환경표지",
    r"녹색제품",
    # 일반 키워드(보고서에서 흔함)
    r"친환경",
]


def build_env_keywords_re(extra_keywords=None, include_general_env: bool = False) -> re.Pattern:
    pats = list(DEFAULT_ENV_KEYWORDS)
    if include_general_env:
        pats.append(r"환경")  # 너무 넓어서 기본 False 권장
    if extra_keywords:
        for kw in extra_keywords:
            kw = str(kw).strip()
            if kw and len(kw) <= 80:
                pats.append(kw)
    return re.compile(r"(" + r"|".join(pats) + r")", re.IGNORECASE)


_ENV_KEYWORDS_RE = build_env_keywords_re(extra_keywords=None, include_general_env=False)


def set_env_keywords(extra_keywords=None, include_general_env: bool = False):
    """Step6 실행 전에 1회 호출해서 환경 키워드 확장 가능."""
    global _ENV_KEYWORDS_RE
    _ENV_KEYWORDS_RE = build_env_keywords_re(extra_keywords=extra_keywords, include_general_env=include_general_env)


def has_env_signal(s: str) -> bool:
    return bool(_ENV_KEYWORDS_RE.search((s or "").strip()))


def is_hard_label(sentence: str) -> bool:
    if not sentence:
        return True
    s = sentence.strip().strip('"').strip("'").strip()
    if not s:
        return True
    if len(s) < 15:
        return True
    for pat in _LABEL_PATTERNS:
        if re.search(pat, s, re.IGNORECASE):
            return True
    has_end = bool(re.search(r"(다|니다|습니다|입니다|요)([.!?]?)$", s)) or s.endswith((".", "!", "?"))
    if not has_end and len(s) < 40:
        if s.endswith(("수립", "구축", "확대", "전환", "강화", "개선", "추진", "도입", "검토", "제고", "달성")):
            return True
    return False


def is_promo_like(sentence: str) -> bool:
    s = (sentence or "").strip()
    if not s:
        return True
    if has_env_signal(s):
        return False
    return bool(_PROMO_PHRASES_RE.search(s))


def is_table_like(sentence: str) -> bool:
    s = (sentence or "").strip()
    if not s:
        return True
    if "|" in s or "\t" in s:
        return True
    digits = sum(ch.isdigit() for ch in s)
    if len(s) >= 30 and digits / max(1, len(s)) >= 0.25:
        return True
    if re.search(r"(억원|백만원|톤|tCO2|tCO₂|tCO2eq|MWh|kWh|GWh|MW|%){2,}", s, re.IGNORECASE):
        return True
    return False


def sentence_quality_score_kor(sentence: str) -> float:
    s = " ".join((sentence or "").strip().split())
    if not s:
        return 0.0
    score = 0.0
    if re.search(r"[가-힣]", s):
        score += 0.2
    if re.search(r"(다|니다|습니다|입니다|요)([.!?]?)$", s) or s.endswith((".", "!", "?")):
        score += 0.3
    if re.search(r"(하다|되다|있다|없다|추진|운영|강화|확대|감축|대체|도입|수립|공개|검증|목표|계획)", s):
        score += 0.2
    digits = sum(ch.isdigit() for ch in s)
    if digits >= 18:
        score -= 0.2
    if len(s) < 25:
        score -= 0.2
    if len(s) > 250:
        score -= 0.1
    return max(0.0, min(1.0, score))


def is_low_declarative(sentence: str) -> bool:
    s = (sentence or "").strip()
    if not s:
        return False

    # Fact는 Low 확정 대상 아님
    if _FACT_TENSE_RE.search(s):
        return False

    # 환경 신호가 있어야 "환경 선언문"으로 취급
    if not has_env_signal(s):
        return False

    # 정량/근거 단서가 있으면 선언으로 확정하지 않음 (High/Mid/NonRisk 평가로 넘김)
    if re.search(
        r"(\d+|%|톤|tCO2|tCO₂|tCO2eq|기준연도|목표연도|Scope\s*[123]|원단위|검증|제3자|인증)", s, re.IGNORECASE
    ):
        return False

    # 의지/방향/계획 패턴
    if re.search(
        r"(하고자\s*합니다|추구합니다|노력하고\s*있습니다|기여하고자\s*합니다|확산하고자\s*합니다|"
        r"추진할\s*예정|계획입니다|목표로\s*합니다|지향합니다|강화해\s*나가겠습니다|"
        r"확대해\s*나가겠습니다|지속적으로\s*추진하겠습니다|추진해\s*나가겠습니다)",
        s,
    ):
        return True

    return False


def split_sentences_kor(text: str) -> List[str]:
    """
    look-behind 없이 안전하게 문장 분리.
    - 마침표/물음표/느낌표 뒤
    - 또는 '다/니다/습니다/입니다' 같은 종결어미 뒤에서 문장 경계를 만들고 분리
    """
    t = (text or "").strip()
    if not t:
        return []

    # 공백 정리
    t = re.sub(r"\s+", " ", t)

    # 1) 기호 종결(.?! ) 뒤에 구분자 삽입
    t = re.sub(r"([\.!?])\s+", r"\1<SPLIT>", t)

    # 2) 한글 종결어미 뒤에 구분자 삽입
    #    - lookbehind 대신 "캡처 + 치환" 사용
    t = re.sub(r"(다|니다|습니다|입니다)\s+", r"\1<SPLIT>", t)

    parts = [p.strip() for p in t.split("<SPLIT>") if p.strip()]
    return parts


def collect_rule_based_declaratives(page_text: str, max_n: int = 5) -> List[Dict[str, Any]]:
    """
    페이지 텍스트에서 규칙 기반으로 '환경 선언문 후보'를 뽑아 반환.
    - 실제 Low 확정은 analyze_page에서 is_low_declarative로 수행
    - 여기서는 후보 풀에 올리는 역할만 함
    """
    sents = split_sentences_kor(page_text)
    out: List[Dict[str, Any]] = []

    for s in sents:
        ss = s.strip()
        if not ss:
            continue

        # 환경 신호 + 선언/의지 패턴(=Low 후보일 가능성)
        if has_env_signal(ss):
            if re.search(
                r"(하고자\s*합니다|추구합니다|노력하고\s*있습니다|기여하고자\s*합니다|확산하고자\s*합니다|"
                r"추진할\s*예정|계획입니다|목표로\s*합니다|지향합니다|강화해\s*나가겠습니다|"
                r"확대해\s*나가겠습니다|지속적으로\s*추진하겠습니다|추진해\s*나가겠습니다)",
                ss,
            ):
                out.append({"sentence": ss})

        if len(out) >= max_n:
            break

    return out


def _extract_json_substring(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip()
    i = t.find("[")
    j = t.rfind("]")
    if 0 <= i < j:
        return t[i : j + 1]
    i = t.find("{")
    j = t.rfind("}")
    if 0 <= i < j:
        return t[i : j + 1]
    return None


def _json_loads_safe(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        sub = _extract_json_substring(text)
        if not sub:
            return None
        try:
            return json.loads(sub)
        except Exception:
            return None


def _as_str_list(x: Any, max_n: int) -> List[str]:
    if not isinstance(x, list):
        return []
    out = []
    for v in x:
        s = str(v).strip()
        if s:
            out.append(s)
    return out[:max_n]


def _ensure_polite_ending(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if t.endswith(("입니다.", "합니다.", "습니다.")):
        return t
    if not t.endswith("."):
        t += "."
    if not t.endswith(("입니다.", "합니다.", "습니다.")):
        t += " 추가 보완이 필요합니다."
    return t


def _fallback_fix_paragraph(missing_fields: List[str]) -> str:
    mf = set((missing_fields or []))
    bullets = []
    if any("정의" in x or "기준" in x for x in mf):
        bullets.append("용어의 정의와 판단 기준(내부 기준 또는 공인 기준)을 명확히 제시해야 합니다.")
    if any("범위" in x or "경계" in x or "Scope" in x for x in mf):
        bullets.append(
            "적용 범위(조직·사업·제품·지역·Scope, 포함·제외 조건)와 적용 기간(기준연도·목표연도)을 구체화해야 합니다."
        )
    if any("산정" in x or "방법" in x or "방법론" in x for x in mf):
        bullets.append("정량 지표(단위 포함)와 산정 방식(데이터 출처, 계산 로직, 비교 기준, 가정)을 설명해야 합니다.")

    if not bullets:
        bullets = [
            "해당 주장(성과/목표/효과)의 대상 범위와 기간을 먼저 명확히 해야 합니다.",
            "정량 지표(단위 포함)와 산정 방법, 확인 절차를 함께 제시해야 합니다.",
        ]

    bullets = bullets[:4]
    paragraph = " ".join(bullets)
    paragraph += " 또한 상쇄(REC/크레딧)와 실제 감축을 혼용하지 않도록 구분 표기하는 것이 필요합니다."
    return _ensure_polite_ending(paragraph)
