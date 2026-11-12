# pyright: basic
# ruff: noqa: E501, S112, UP006, UP035, UP045
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   긴 줄(프롬프트·정규식 글자); try-except-continue(노트북 동작); typing.List 꼴; typing 의 옛 이름; Optional 꼴
"""설정, 설정 다듬기, 후보 탐지·근거·판정·쪽 분석·스캔.

노트북(AI그린워싱 점검_E0의 사본.ipynb)의 셀 14(0·1·6·7절) 소스에서 기계로 뽑아 글자 그대로 옮겼다.
흠을 고치지 않는다(py/greenwash/README.md 의 「일부러 남긴 흠」). 원본 대조(tests/notebook_probe.py)가 같음을 잰다.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from esgapi.greenwash.engines.e0.heuristics import (
    _HIGH_RISK_KEYWORDS_RE,
    _as_str_list,
    _ensure_polite_ending,
    _fallback_fix_paragraph,
    _json_loads_safe,
    cap_evidence_context,
    collect_rule_based_declaratives,
    get_page_text,
    has_env_signal,
    is_hard_label,
    is_low_declarative,
    is_promo_like,
    is_table_like,
    normalize_text_for_llm,
    sentence_quality_score_kor,
    set_env_keywords,
)
from esgapi.greenwash.engines.e0.ports import ChatPort, HumanMessage, SystemMessage
from esgapi.greenwash.engines.e0.prompts import PromptPack, default_prompts

# 노트북의 `GreenwashingChecker.__init__` 기본값(ChatOpenAI 에 주던 것). 이 밴드는 실제 공급사를 부르지 않는다.
MODEL_NAME = "gpt-4.1-mini"
TEMPERATURE = 0.0
MAX_TOKENS = 1300

SAFE_LIMITS_INT = {
    "max_candidates_per_page": (0, 5),
    "evidence_k": (1, 5),
    "max_chars_page_text": (800, 5000),
    "max_chars_per_chunk": (200, 1200),
    "max_chars_evidence_total": (800, 4000),
    "debug_pages": (0, 10),
}


def sanitize_config_dict(cfg: Optional[Dict[str, Any]], verbose: bool = False) -> Dict[str, Any]:
    out = dict(cfg or {})

    # int 보정
    for k, (lo, hi) in SAFE_LIMITS_INT.items():
        if k in out:
            try:
                v = int(out[k])
                out[k] = max(lo, min(hi, v))
            except Exception:
                out[k] = lo

    # bool 보정
    for bk in ["use_evidence_failopen", "batch_eval", "debug"]:
        if bk in out:
            out[bk] = bool(out[bk])

    # report_levels 보정
    if "report_levels" in out:
        rl = out["report_levels"]
        if isinstance(rl, (list, tuple)):
            rl2 = [str(x).strip() for x in rl if str(x).strip()]
            out["report_levels"] = tuple(rl2) if rl2 else ("High", "Mid", "Low")
        elif isinstance(rl, str):
            parts = [p.strip() for p in rl.split(",") if p.strip()]
            out["report_levels"] = tuple(parts) if parts else ("High", "Mid", "Low")
        else:
            out["report_levels"] = ("High", "Mid", "Low")

    # prompt_version 보정
    if "prompt_version" in out:
        out["prompt_version"] = str(out["prompt_version"]).strip() or "2026-01-15-v1"

    # env 키워드 확장 옵션(선택)
    if "env_keywords_extra" in out:
        v = out["env_keywords_extra"]
        if isinstance(v, (list, tuple)):
            out["env_keywords_extra"] = [str(x).strip() for x in v if str(x).strip()]
        elif isinstance(v, str):
            out["env_keywords_extra"] = [p.strip() for p in v.split(",") if p.strip()]
        else:
            out["env_keywords_extra"] = []

    if "include_general_env" in out:
        out["include_general_env"] = bool(out["include_general_env"])

    return out


@dataclass
class GWConfig:
    # detect
    max_candidates_per_page: int = 3
    max_chars_page_text: int = 2500

    # evidence
    evidence_k: int = 2
    max_chars_per_chunk: int = 450
    use_evidence_failopen: bool = False
    max_chars_evidence_total: int = 1600

    # output
    report_levels: Tuple[str, ...] = ("High", "Mid", "Low")

    # debug
    debug: bool = False
    debug_pages: int = 2

    # batching (현재는 False 권장)
    batch_eval: bool = False

    # prompt version
    prompt_version: str = "2026-01-15-v1"


class GreenwashingChecker:
    def __init__(
        self,
        docs,
        vectorstore,
        llm: ChatPort,
        cfg: Optional[GWConfig] = None,
        prompts: Optional[PromptPack] = None,
    ):
        self.docs = docs
        self.vectorstore = vectorstore
        self.cfg = cfg or GWConfig()
        self.prompts = prompts or default_prompts(self.cfg.prompt_version)

        self.llm = llm

    # ---------- 후보 탐지 ----------
    def detect_candidates(self, page_text: str, page_number: int, debug: bool = False) -> List[Dict[str, Any]]:
        user_content = (
            f"아래 텍스트는 ESG 보고서의 {page_number}페이지 일부입니다.\n"
            f"이 텍스트 안에서 그린워싱 의심 후보 문장을 찾아주세요.\n\n"
            f"[텍스트]\n{page_text}"
        )
        resp = self.llm.invoke(
            [
                SystemMessage(content=self.prompts.detect_system_prompt),
                HumanMessage(content=user_content),
            ]
        )
        raw = (resp.content or "").strip()

        data = _json_loads_safe(raw)
        if not isinstance(data, list):
            return []

        out: List[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                sent = (item.get("sentence") or "").strip()
                if sent:
                    out.append({"sentence": sent})

        return out[: int(self.cfg.max_candidates_per_page)]

    # ---------- 후보 필터/정렬 ----------
    def filter_and_rank(self, candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        stats = {
            "raw": len(candidates),
            "hard_dropped": 0,
            "non_env_dropped": 0,
            "promo_dropped": 0,
            "table_dropped": 0,
            "kept": 0,
        }

        scored: List[Dict[str, Any]] = []
        for c in candidates:
            s = (c.get("sentence") or "").strip()

            if is_hard_label(s):
                stats["hard_dropped"] += 1
                continue
            if not has_env_signal(s):
                stats["non_env_dropped"] += 1
                continue
            if is_promo_like(s):
                stats["promo_dropped"] += 1
                continue
            if is_table_like(s) and (not _HIGH_RISK_KEYWORDS_RE.search(s)):
                stats["table_dropped"] += 1
                continue

            cc = dict(c)
            cc["_score"] = sentence_quality_score_kor(s)
            scored.append(cc)

        scored.sort(key=lambda x: x.get("_score", 0.0), reverse=True)
        kept = scored[: int(self.cfg.max_candidates_per_page)]
        for k in kept:
            k.pop("_score", None)

        stats["kept"] = len(kept)
        return kept, stats

    # ---------- 근거 검색 ----------
    def build_evidence(self, sentence: str, allowed_pages: Optional[List[int]]) -> Tuple[str, List[int]]:
        k = int(self.cfg.evidence_k)
        raw_docs = self.vectorstore.similarity_search(sentence, k=max(k * 5, 12))

        filtered = []
        if allowed_pages:
            allowed_set = set(int(p) for p in allowed_pages)
            for d in raw_docs:
                p = int(d.metadata.get("page", 0)) + 1
                if p in allowed_set:
                    filtered.append(d)
        else:
            filtered = raw_docs

        if self.cfg.use_evidence_failopen and (not filtered) and raw_docs:
            filtered = raw_docs[:k]

        sim_docs = filtered[:k]

        parts = []
        pages: List[int] = []
        for d in sim_docs:
            p = int(d.metadata.get("page", 0)) + 1
            pages.append(p)
            content = normalize_text_for_llm((d.page_content or "").strip())
            if len(content) > int(self.cfg.max_chars_per_chunk):
                content = content[: int(self.cfg.max_chars_per_chunk)] + " ..."
            parts.append(f"[p.{p}]\n{content}")

        evidence_text = "\n\n".join(parts).strip()
        evidence_text = cap_evidence_context(evidence_text, max_total_chars=int(self.cfg.max_chars_evidence_total))
        return evidence_text, sorted(set(pages))

    # ---------- 수정방향이 "일반론"인지 판정 ----------
    def _is_generic_fix(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        if len(t) < 120:
            return True

        generic_patterns = [
            r"정의/기준.*범위.*산정.*추가",
            r"정의/기준·범위·산정 방법",
            r"명확히\s*추가",
            r"명확히\s*제시",
            r"구체적(으로)?\s*(제시|설명)",
            r"추가\s*보완이\s*필요",
        ]
        hit = any(re.search(p, t) for p in generic_patterns)
        has_specific = bool(
            re.search(
                r"(\d+|%|톤|tCO2|tCO2eq|Scope\s*[123]|기준연도|목표연도|적용기간|제3자|책임부서|REC|크레딧|오프셋)",
                t,
                re.IGNORECASE,
            )
        )
        return hit and (not has_specific)

    # ---------- High/Mid/NonRisk 평가 ----------
    def eval_high_mid_or_nonrisk(self, sentence: str, evidence_context: str, debug: bool = False) -> Dict[str, Any]:
        user_content = f"[문장]\n{sentence}\n\n"
        user_content += f"[근거 컨텍스트]\n{evidence_context if evidence_context else '[근거 없음]'}\n"

        resp = self.llm.invoke(
            [
                SystemMessage(content=self.prompts.eval_system_prompt),
                HumanMessage(content=user_content),
            ]
        )
        raw = (resp.content or "").strip()

        data = _json_loads_safe(raw)
        if not isinstance(data, dict):
            data = {}

        decision = (data.get("decision") or "Mid").strip()
        if decision not in ("High", "Mid", "NonRisk"):
            decision = "Mid"

        # 근거 없으면 NonRisk 금지
        if (not evidence_context) and decision == "NonRisk":
            decision = "Mid"

        risk_tags = _as_str_list(data.get("risk_tags"), 3)
        confirmed = _as_str_list(data.get("confirmed_in_evidence"), 6)
        missing_fields = _as_str_list(data.get("missing_fields"), 12)
        reason_bullets = _as_str_list(data.get("reason_bullets"), 3)
        fix_paragraph = (data.get("fix_paragraph") or "").strip()

        # ============================================================
        # ✅ NonRisk 가드레일 (LLM 오판 방지)
        # - "수치만 있는 성과 주장"이 NonRisk로 빠지는 것을 막음
        # ============================================================

        if decision == "NonRisk":
            # (G1) 누락 필드가 하나라도 있으면 NonRisk 금지
            if missing_fields:
                decision = "Mid"

            # (G2) confirmed가 너무 빈약하면 NonRisk 금지 (안전장치)
            # - 최소 2개 이상 "직접 확인 사실"이 있어야 NonRisk 허용
            if decision == "NonRisk" and len(confirmed) < 2:
                decision = "Mid"

        # High/Mid인 경우: fix 일반론이면 1회 REPAIR
        if decision in ("High", "Mid"):
            if self._is_generic_fix(fix_paragraph):
                resp2 = self.llm.invoke(
                    [
                        SystemMessage(content=self.prompts.repair_fix_prompt),
                        HumanMessage(content=user_content + f"\n[리스크 등급]\n{decision}\n"),
                    ]
                )
                raw2 = (resp2.content or "").strip()
                d2 = _json_loads_safe(raw2)
                if isinstance(d2, dict):
                    fp2 = (d2.get("fix_paragraph") or "").strip()
                    if fp2:
                        fix_paragraph = fp2

            if len(fix_paragraph) < 60:
                fix_paragraph = _fallback_fix_paragraph(missing_fields)
            fix_paragraph = _ensure_polite_ending(fix_paragraph)

            if not reason_bullets:
                reason_bullets = ["근거 컨텍스트 대비 표현의 범위·기준·방법 또는 수치 정보가 충분히 확인되지 않음."]

        else:
            reason_bullets = []
            fix_paragraph = ""

        return {
            "decision": decision,
            "risk_tags": risk_tags,
            "confirmed_in_evidence": confirmed,
            "missing_fields": missing_fields,
            "reason_bullets": reason_bullets,
            "fix_paragraph": fix_paragraph,
            "evidence_internal": (data.get("evidence_internal") or "").strip(),
        }

    # ---------- Low 확정 문장: 사유/수정방향만 ----------
    def eval_low_only(self, sentence: str, evidence_context: str, debug: bool = False) -> Dict[str, Any]:
        user_content = f"[문장]\n{sentence}\n\n"
        user_content += f"[근거 컨텍스트]\n{evidence_context if evidence_context else '[근거 없음]'}\n"

        resp = self.llm.invoke(
            [
                SystemMessage(content=self.prompts.low_only_prompt),
                HumanMessage(content=user_content),
            ]
        )
        raw = (resp.content or "").strip()

        data = _json_loads_safe(raw)
        if not isinstance(data, dict):
            data = {}

        low_reason = _as_str_list(data.get("low_reason_bullets"), 2)
        fix_paragraph = (data.get("fix_paragraph") or "").strip()

        if len(fix_paragraph) < 40:
            fix_paragraph = _ensure_polite_ending(
                "선언적·리드성 문장은 최소화하고, 핵심 환경 성과·구체 목표·이행 현황 중심으로 공시의 중심을 재배치하는 것이 바람직합니다."
            )
        else:
            fix_paragraph = _ensure_polite_ending(fix_paragraph)

        if not low_reason:
            low_reason = ["선언적·포괄적 표현이 구체 성과/목표와 분리되어 공시 실질성을 약화시킬 수 있음."]

        return {"reason_bullets": low_reason, "fix_paragraph": fix_paragraph}

    # ---------- 페이지 분석 ----------
    def analyze_page(
        self, page_no: int, evidence_allowed_pages: Optional[List[int]], debug: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:

        doc = self.docs[page_no - 1]
        page_text = get_page_text(doc, max_chars=int(self.cfg.max_chars_page_text))
        if not page_text:
            return [], {
                "raw": 0,
                "hard_dropped": 0,
                "non_env_dropped": 0,
                "promo_dropped": 0,
                "table_dropped": 0,
                "kept": 0,
            }

        # (A) 규칙 기반 선언문 후보(LLM Detect 누락 방지)
        rule_cands = collect_rule_based_declaratives(
            page_text,
            max_n=max(3, int(self.cfg.max_candidates_per_page)),  # 페이지당 후보 상한과 비슷하게
        )

        # (B) LLM Detect 후보
        llm_cands = self.detect_candidates(page_text, page_no, debug=debug)

        # (C) merge + dedup (문장 중복 제거)
        seen = set()
        merged_raw = []
        for c in rule_cands + llm_cands:
            s = (c.get("sentence") or "").strip()
            if not s:
                continue
            key = re.sub(r"\s+", " ", s)
            if key in seen:
                continue
            seen.add(key)
            merged_raw.append({"sentence": s})

        # 기존 휴리스틱 필터/정렬 적용
        # ============================================================
        # ✅ 쿼터 방식: Low(선언문) 1개 + 비-Low(High/Mid/NonRisk 후보) N개
        # - Low가 kept 슬롯을 잠식하지 않도록 분리 선발
        # ============================================================

        # 1) merged_raw를 Low 후보 / 비-Low 후보로 분리
        low_raw = []
        nonlow_raw = []
        for c in merged_raw:
            s = (c.get("sentence") or "").strip()
            if not s:
                continue
            if is_low_declarative(s):
                low_raw.append({"sentence": s})
            else:
                nonlow_raw.append({"sentence": s})

        # 2) 비-Low 후보는 기존 방식대로 TopN 선발
        nonlow_kept, stats_nonlow = self.filter_and_rank(nonlow_raw)

        # 3) Low 후보는 별도 Top1 선발 (필터는 완화/동일 적용 중 택1)
        #    - 여기서는 동일한 filter_and_rank를 쓰되, 최대 1개만 남김
        #    - 임시로 cfg 값을 건드리지 않기 위해 슬라이스로 처리
        low_kept_all, stats_low = self.filter_and_rank(low_raw)
        low_kept = low_kept_all[:1]

        # 4) 최종 후보 결합: 비-Low N개 + Low 1개
        cands = nonlow_kept[: int(self.cfg.max_candidates_per_page)] + low_kept

        # 5) stats는 참고용으로 합산(kept는 실제 cands 길이)
        stats = {
            "raw": len(merged_raw),
            "hard_dropped": int(stats_nonlow.get("hard_dropped", 0)) + int(stats_low.get("hard_dropped", 0)),
            "non_env_dropped": int(stats_nonlow.get("non_env_dropped", 0)) + int(stats_low.get("non_env_dropped", 0)),
            "promo_dropped": int(stats_nonlow.get("promo_dropped", 0)) + int(stats_low.get("promo_dropped", 0)),
            "table_dropped": int(stats_nonlow.get("table_dropped", 0)) + int(stats_low.get("table_dropped", 0)),
            "kept": len(cands),
        }

        if not cands:
            return [], stats

        results: List[Dict[str, Any]] = []
        for cand in cands:
            sent = (cand.get("sentence") or "").strip()
            if not sent:
                continue

            ev_text, ev_pages = self.build_evidence(sent, allowed_pages=evidence_allowed_pages)

            # (1) Low 확정
            if is_low_declarative(sent):
                low_out = self.eval_low_only(sent, ev_text, debug=debug)
                results.append(
                    {
                        "page": page_no,
                        "sentence": sent,
                        "level": "Low",
                        "risk_tags": ["선언적 문장"],
                        "confirmed_in_evidence": [],
                        "missing_fields": [],
                        "reason_bullets": low_out.get("reason_bullets", []),
                        "fix_paragraph": low_out.get("fix_paragraph", ""),
                        "fix": low_out.get("fix_paragraph", ""),
                        "action": low_out.get("fix_paragraph", ""),
                        "evidence_internal": "",
                        "evidence_pages": ev_pages,
                    }
                )
                continue

            # (2) High/Mid/NonRisk
            out = self.eval_high_mid_or_nonrisk(sent, ev_text, debug=debug)
            if out.get("decision") == "NonRisk":
                continue

            results.append(
                {
                    "page": page_no,
                    "sentence": sent,
                    "level": out.get("decision", "Mid"),
                    "risk_tags": out.get("risk_tags", []),
                    "confirmed_in_evidence": out.get("confirmed_in_evidence", []),
                    "missing_fields": out.get("missing_fields", []),
                    "reason_bullets": out.get("reason_bullets", []),
                    "fix_paragraph": out.get("fix_paragraph", ""),
                    "fix": out.get("fix_paragraph", ""),
                    "action": out.get("fix_paragraph", ""),
                    "evidence_internal": out.get("evidence_internal", ""),
                    "evidence_pages": ev_pages,
                }
            )

        return results, stats


@dataclass
class ScanOutcome:
    """스캔이 돌려주는 것. 노트북은 결과 목록만 돌려주고 집계·실패 수는 print 했다."""

    results: List[Dict[str, Any]] = field(default_factory=list)
    agg: Dict[str, int] = field(
        default_factory=lambda: {
            "raw": 0,
            "hard_dropped": 0,
            "non_env_dropped": 0,
            "promo_dropped": 0,
            "table_dropped": 0,
            "kept": 0,
        }
    )
    failed: int = 0
    failed_pages: List[Dict[str, Any]] = field(default_factory=list)
    pages_norm: List[int] = field(default_factory=list)
    allowed_norm: List[int] = field(default_factory=list)
    cfg: Optional[GWConfig] = None
    total_pages: int = 0


def scan_report_greenwashing_pages(
    docs,
    pages: List[int],
    evidence_allowed_pages: Optional[List[int]] = None,
    config: Optional[Dict[str, Any]] = None,
    *,
    vectorstore=None,
    llm: Optional[ChatPort] = None,
    prompts: Optional[PromptPack] = None,
    resume: Optional[Dict[str, Any]] = None,
    checkpoint: Optional[Callable[[Dict[str, Any], int, int], None]] = None,
    reraise: Optional[Callable[[BaseException], bool]] = None,
) -> ScanOutcome:
    """GW1 의 스캔 루프(한 벌). 이어 돌기 꼭지는 GL1(MARC-TICK-112) 에서 더했고, 둘 다 None 이면 GW1 과 같다.

    resume      {"done_pages", "results", "agg", "failed", "failed_pages"} — 참이면 이 값에서 이어 돌고
                done_pages 의 쪽은 건너뛴다(대화 포트를 다시 부르지 않는다).
    checkpoint  쪽 하나가 끝날 때마다(성공·실패 모두) checkpoint(partial, done, total). 예외 처리 밖에서 부르므로
                받는 쪽의 예외는 쪽 실패로 삼켜지지 않고 그대로 올라간다.
    reraise     쪽 안의 예외를 다시 던질지의 판별(GSL1, MARC-ISSUE-414). 참이면 그 쪽을 failed_pages 에 적지 않고
                체크포인트 전에 다시 던진다(Celery soft limit — 흐름이 core 의 soft_deadline_in 으로 짓는다). None 이면 GW1 그대로.
    """

    if vectorstore is None:
        raise ValueError("vectorstore가 필요합니다. (scan_report_greenwashing_pages(..., vectorstore=vectorstore))")
    if llm is None:
        raise ValueError("llm(대화 포트)이 필요합니다.")

    safe_cfg_dict = sanitize_config_dict(config, verbose=False)

    # (선택) config로 env 키워드 확장
    if safe_cfg_dict.get("env_keywords_extra") or safe_cfg_dict.get("include_general_env"):
        set_env_keywords(
            extra_keywords=safe_cfg_dict.get("env_keywords_extra", []),
            include_general_env=bool(safe_cfg_dict.get("include_general_env", False)),
        )

    cfg = GWConfig()
    for k, v in safe_cfg_dict.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)

    checker = GreenwashingChecker(
        docs=docs,
        vectorstore=vectorstore,
        llm=llm,
        cfg=cfg,
        prompts=prompts,
    )

    total_pages = len(docs)
    if not pages:
        return ScanOutcome(cfg=cfg, total_pages=total_pages)

    # pages 정규화(1~total_pages)
    pages_norm = []
    for p in pages:
        try:
            pi = int(p)
            if 1 <= pi <= total_pages:
                pages_norm.append(pi)
        except Exception:
            continue
    pages_norm = sorted(set(pages_norm))

    if not pages_norm:
        return ScanOutcome(cfg=cfg, total_pages=total_pages)

    # evidence_allowed_pages 정규화
    if evidence_allowed_pages is None:
        allowed_norm = pages_norm[:]
    else:
        tmp = []
        for p in evidence_allowed_pages:
            try:
                pi = int(p)
                if 1 <= pi <= total_pages:
                    tmp.append(pi)
            except Exception:
                continue
        allowed_norm = sorted(set(tmp)) or pages_norm[:]

    report_levels = set(cfg.report_levels)

    if resume:
        done_pages: List[int] = list(resume["done_pages"])
        results: List[Dict[str, Any]] = list(resume["results"])
        agg: Dict[str, int] = dict(resume["agg"])
        failed: int = int(resume["failed"])
        failed_pages: List[Dict[str, Any]] = list(resume["failed_pages"])
    else:
        done_pages = []
        results = []
        agg = {"raw": 0, "hard_dropped": 0, "non_env_dropped": 0, "promo_dropped": 0, "table_dropped": 0, "kept": 0}
        failed = 0
        failed_pages = []

    for idx, page_no in enumerate(pages_norm, start=1):
        if page_no in done_pages:
            continue  # 앞 실행에서 끝난 쪽(대화 포트를 다시 부르지 않는다)
        debug_this = bool(cfg.debug and idx <= int(cfg.debug_pages))

        try:
            page_results, stats = checker.analyze_page(page_no, evidence_allowed_pages=allowed_norm, debug=debug_this)

            for k in agg:
                agg[k] += int(stats.get(k, 0))

            # report_levels에 포함된 level만 유지
            page_results = [r for r in page_results if (r.get("level") in report_levels)]

            if page_results:
                results.extend(page_results)

        except Exception as e:
            if reraise is not None and reraise(e):
                raise
            failed += 1
            failed_pages.append({"page": page_no, "error": f"{e}"})

        done_pages.append(page_no)
        if checkpoint is not None:
            partial = {
                "done_pages": done_pages,
                "results": results,
                "agg": agg,
                "failed": failed,
                "failed_pages": failed_pages,
            }
            checkpoint(partial, len(done_pages), len(pages_norm))

    return ScanOutcome(
        results=results,
        agg=agg,
        failed=failed,
        failed_pages=failed_pages,
        pages_norm=pages_norm,
        allowed_norm=allowed_norm,
        cfg=cfg,
        total_pages=total_pages,
    )
