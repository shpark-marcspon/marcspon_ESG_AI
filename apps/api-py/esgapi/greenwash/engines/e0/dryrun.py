# pyright: basic
# ruff: noqa: E501, UP006, UP035, UP045
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   긴 줄(프롬프트·정규식 글자); typing.List 꼴; typing 의 옛 이름; Optional 꼴
"""dry-run: 호출을 조립하되 보내지 않고 요청 수·입력 글자·입력 토큰을 센다.

AI 의 답에 달린 것은 아래끝과 위끝으로 낸다.
- 아래끝: AI 가 후보를 하나도 돌려주지 않는다. 규칙 후보만 판정에 든다. 다시 묻기 0. 근거는 「[근거 없음]」.
  판정 코드(`checker.py`)를 기록만 하는 대화 포트와 빈 검색으로 실제로 돌려 센다.
- 위끝: 쪽마다 탐지 1 + 판정 4(평가 3 + Low 전용 1) + 다시 묻기 3 + 근거 물음 임베딩 4.
  문장 자리에 그 쪽의 가장 긴 문장, 근거 자리에 허용 쪽의 조각 가운데 근거 꼴로 다듬어 토큰이 가장 많은 것들을 넣어 센다.
토큰은 메시지의 글(시스템 + 사용자)만 센다. 대화 API 가 메시지마다 덧붙이는 틀 토큰은 세지 않는다.
"""

from typing import Any, Dict, List, Optional, Sequence

from esgapi.greenwash.engines.e0 import checker as checker_mod
from esgapi.greenwash.engines.e0.checker import GWConfig, sanitize_config_dict, scan_report_greenwashing_pages
from esgapi.greenwash.engines.e0.chunking import build_chunks_from_docs
from esgapi.greenwash.engines.e0.heuristics import (
    cap_evidence_context,
    collect_rule_based_declaratives,
    get_page_text,
    normalize_text_for_llm,
    split_sentences_kor,
)
from esgapi.greenwash.engines.e0.ports import (
    CHAT_ENCODING,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_ENCODING,
    ChatReply,
    Message,
    Tally,
    TokenCounter,
    prompt_kind,
)
from esgapi.greenwash.engines.e0.prompts import default_prompts
from esgapi.greenwash.engines.e0.retrieval import embedding_request_count

KINDS = ("detect", "eval", "low_only", "repair")

# 아래끝에서 기록용 대화가 돌려주는 답. 다시 묻기가 일어나지 않는 꼴(120자 이상, 구체 단서 있음)이다. 지은 글이다.
_DRY_EVAL = (
    '{"decision": "Mid", "risk_tags": [], "confirmed_in_evidence": [], "missing_fields": [], "reason_bullets": ["dry-run"], '
    '"fix_paragraph": "'
    + (
        "기준연도 2020년과 목표연도 2030년, Scope 1과 Scope 2의 범위, tCO2eq 단위의 수치를 함께 밝혀야 합니다. " * 3
    ).strip()
    + '", "evidence_internal": ""}'
)
_DRY_LOW = (
    '{"low_reason_bullets": ["dry-run"], "fix_paragraph": "'
    + ("선언적 표현을 줄이고 성과와 목표를 중심으로 공시해야 합니다. " * 2).strip()
    + '"}'
)


class _DryChat:
    """보내지 않는다. 받은 메시지를 적고 정해 둔 답을 돌려준다."""

    def __init__(self, pack):
        self.pack = pack
        self.sent: List[List[Message]] = []

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        self.sent.append(list(messages))
        kind = prompt_kind(messages[0].content, self.pack)
        if kind == "detect":
            return ChatReply(content="[]")
        if kind == "low_only":
            return ChatReply(content=_DRY_LOW)
        return ChatReply(content=_DRY_EVAL)


class _NoEvidenceIndex:
    """근거 물음을 적기만 하고 아무 조각도 돌려주지 않는다(「[근거 없음]」)."""

    def __init__(self):
        self.queries: List[str] = []

    def similarity_search(self, query: str, k: int = 4) -> List[Any]:
        self.queries.append(query)
        return []


def _cfg_from(config: Optional[Dict[str, Any]]) -> GWConfig:
    cfg = GWConfig()
    for k, v in sanitize_config_dict(config).items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def _evidence_part(chunk, cfg: GWConfig) -> str:
    """`build_evidence` 가 조각 하나를 근거로 다듬는 꼴."""
    p = int(chunk.metadata.get("page", 0)) + 1
    content = normalize_text_for_llm((chunk.page_content or "").strip())
    if len(content) > int(cfg.max_chars_per_chunk):
        content = content[: int(cfg.max_chars_per_chunk)] + " ..."
    return f"[p.{p}]\n{content}"


def max_evidence(
    chunks: Sequence[Any], allowed_pages: Sequence[int], cfg: GWConfig, counter: TokenCounter
) -> Dict[str, Any]:
    """허용 쪽의 조각으로 만들 수 있는 가장 큰 근거 글(토큰 기준. 토큰을 못 세면 글자 기준)."""
    allowed = set(int(p) for p in allowed_pages)
    parts = [_evidence_part(c, cfg) for c in chunks if int(c.metadata.get("page", 0)) + 1 in allowed]

    def weight(part: str):
        n = counter.count(CHAT_ENCODING, part)
        return (n if n is not None else len(part), len(part))

    top = sorted(parts, key=weight, reverse=True)[: int(cfg.evidence_k)]
    joined = "\n\n".join(top).strip()
    return {
        "text": cap_evidence_context(joined, max_total_chars=int(cfg.max_chars_evidence_total)),
        "cap_reached": len(joined) > int(cfg.max_chars_evidence_total),
    }


def dry_run(
    docs, pages: List[int], allowed_pages: List[int], config: Optional[Dict[str, Any]], counter: TokenCounter
) -> Dict[str, Any]:
    cfg = _cfg_from(config)
    pack = default_prompts(cfg.prompt_version)
    chunks = build_chunks_from_docs(docs)["chunks"] if docs else []

    index_tally = Tally(EMBEDDING_ENCODING)
    index_tally.add(
        counter, [c.page_content for c in chunks], requests=embedding_request_count(len(chunks), EMBEDDING_BATCH_SIZE)
    )

    # ---- 아래끝: 판정 코드를 기록만 하는 포트로 돌린다 ----
    chat = _DryChat(pack)
    index = _NoEvidenceIndex()
    outcome = scan_report_greenwashing_pages(
        docs, pages, evidence_allowed_pages=allowed_pages, config=config, vectorstore=index, llm=chat
    )
    if outcome.failed:
        raise RuntimeError(f"dry-run 의 아래끝 실행에서 쪽이 실패했다: {outcome.failed_pages}")

    lower = {k: Tally(CHAT_ENCODING) for k in KINDS}
    for msgs in chat.sent:
        lower[prompt_kind(msgs[0].content, pack)].add(counter, [m.content for m in msgs])
    lower_queries = Tally(EMBEDDING_ENCODING)
    for q in index.queries:
        lower_queries.add(counter, [q])

    # ---- 위끝 ----
    ev = max_evidence(chunks, outcome.allowed_norm, cfg, counter)
    upper = {k: Tally(CHAT_ENCODING) for k in KINDS}
    upper_queries = Tally(EMBEDDING_ENCODING)
    per_page: List[Dict[str, Any]] = []
    rule_total = 0
    sent_by_page = _group_by_detect(chat.sent, pack)
    for page_no in outcome.pages_norm:
        raw_len = len(normalize_text_for_llm((docs[page_no - 1].page_content or "").strip()))
        page_text = get_page_text(docs[page_no - 1], max_chars=int(cfg.max_chars_page_text))
        row: Dict[str, Any] = {
            "page": page_no,
            "text_chars": raw_len,
            "truncated": raw_len > int(cfg.max_chars_page_text),
            "rule_candidates": 0,
            "lower_judged": 0,
        }
        if page_text:
            rule = collect_rule_based_declaratives(page_text, max_n=max(3, int(cfg.max_candidates_per_page)))
            row["rule_candidates"] = len(rule)
            rule_total += len(rule)
            row["lower_judged"] = len(sent_by_page.pop(0)) - 1
            longest = max(split_sentences_kor(page_text), key=len)
            user = f"[문장]\n{longest}\n\n" + f"[근거 컨텍스트]\n{ev['text'] if ev['text'] else '[근거 없음]'}\n"
            detect_user = (
                f"아래 텍스트는 ESG 보고서의 {page_no}페이지 일부입니다.\n"
                f"이 텍스트 안에서 그린워싱 의심 후보 문장을 찾아주세요.\n\n"
                f"[텍스트]\n{page_text}"
            )
            upper["detect"].add(counter, [pack.detect_system_prompt, detect_user])
            for _ in range(int(cfg.max_candidates_per_page)):
                upper["eval"].add(counter, [pack.eval_system_prompt, user])
                upper["repair"].add(counter, [pack.repair_fix_prompt, user + "\n[리스크 등급]\nHigh\n"])
            upper["low_only"].add(counter, [pack.low_only_prompt, user])
            for _ in range(int(cfg.max_candidates_per_page) + 1):
                upper_queries.add(counter, [longest])
        per_page.append(row)

    def total(by_kind: Dict[str, Tally]) -> Tally:
        t = Tally(CHAT_ENCODING)
        for k in KINDS:
            t.merge(by_kind[k])
        return t

    upper_total = total(upper)
    return {
        "pages_checked": len(outcome.pages_norm),
        "pages_with_text": sum(1 for r in per_page if r["text_chars"] > 0),
        "pages_truncated": sum(1 for r in per_page if r["truncated"]),
        "chunks": len(chunks),
        "embedding_index": index_tally.to_json(),
        "rule_candidates": rule_total,
        "lower": {
            "chat": total(lower).to_json(),
            "chat_by_kind": {k: lower[k].to_json() for k in KINDS},
            "embedding_queries": lower_queries.to_json(),
            "judged": lower["eval"].requests + lower["low_only"].requests,
        },
        "upper": {
            "chat": upper_total.to_json(),
            "chat_by_kind": {k: upper[k].to_json() for k in KINDS},
            "embedding_queries": upper_queries.to_json(),
            "output_tokens_max": upper_total.requests * checker_mod.MAX_TOKENS,
            "evidence_chars": len(ev["text"]),
            "evidence_cap_reached": ev["cap_reached"],
        },
        "per_page": per_page,
    }


def _group_by_detect(sent: List[List[Message]], pack) -> List[List[List[Message]]]:
    """보낸 메시지를 탐지 요청에서 끊어 쪽별로 묶는다(글이 있는 쪽마다 탐지가 정확히 한 번 나간다)."""
    groups: List[List[List[Message]]] = []
    for msgs in sent:
        if prompt_kind(msgs[0].content, pack) == "detect":
            groups.append([])
        groups[-1].append(msgs)
    return groups
