# pyright: basic
# ruff: noqa: E501, RUF100, UP006, UP017, UP035, UP045
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   긴 줄(프롬프트·정규식 글자); GW1 의 줄 noqa; typing.List 꼴; timezone.utc; typing 의 옛 이름; Optional 꼴
"""대화·임베딩 포트, 대본대로 답하는 모의 대화, 결정적 모의 임베딩, 토큰 세기, 호출 기록.

노트북은 `ChatOpenAI`·`OpenAIEmbeddings` 를 바로 불렀다. 여기서는 얇은 포트로 가른다.
이 밴드에는 실제 공급사 어댑터가 없다(모의와 dry-run 뿐이다).
호출 기록의 칸 이름은 `ts/llm/src/log.ts` 의 `CallRecord` 를 따른다.
"""

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

from esgapi.greenwash.engines.e0.heuristics import build_env_keywords_re, is_hard_label, split_sentences_kor
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, PromptPack, default_prompts

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 50
# tiktoken 의 model.py 가 두 모델에 주는 부호화 이름(README 의 ★4).
CHAT_ENCODING = "o200k_base"
EMBEDDING_ENCODING = "cl100k_base"


# ----------------------------------------------------------------------------
# 메시지와 포트
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Message:
    role: str
    content: str


def SystemMessage(content: str) -> Message:  # noqa: N802 — 노트북의 이름(langchain_core.messages)을 그대로 둔다
    return Message(role="system", content=content)


def HumanMessage(content: str) -> Message:  # noqa: N802
    return Message(role="user", content=content)


@dataclass(frozen=True)
class ChatReply:
    content: Any


class ChatPort(Protocol):
    def invoke(self, messages: Sequence[Message]) -> ChatReply: ...


class EmbeddingPort(Protocol):
    def embed_documents(self, texts: List[str]) -> List[List[float]]: ...

    def embed_query(self, text: str) -> List[float]: ...


def prompt_kind(system: str, pack: PromptPack) -> str:
    """시스템 프롬프트가 넷 가운데 어느 것인지. 넷이 아니면 `unknown`."""
    if system == pack.detect_system_prompt:
        return "detect"
    if system == pack.eval_system_prompt:
        return "eval"
    if system == pack.repair_fix_prompt:
        return "repair"
    if system == pack.low_only_prompt:
        return "low_only"
    return "unknown"


# ----------------------------------------------------------------------------
# 대본대로 답하는 모의 대화
# ----------------------------------------------------------------------------
# 지은 글이다(synthetic). 실제 모델의 답이 아니다.
_LONG_FIX = (
    "이 문장은 감축 목표의 기준연도와 목표연도를 2020년과 2030년처럼 연도로 밝혀야 합니다. "
    "적용 범위를 Scope 1과 Scope 2로 나누어 적고 포함하지 않는 사업장을 함께 적어야 합니다. "
    "감축량은 tCO2eq 단위의 수치와 산정 방법을 같이 제시해야 합니다. "
    "제3자 검증을 받았는지와 검증 기관을 밝히는 것이 바람직합니다."
)

DEFAULT_SCRIPT: Dict[str, List[Any]] = {
    "detect": [{"pick_env": 2}, {"pick_env": 3}, {"json": []}, {"pick_env": 1}],
    "eval": [
        {
            "json": {
                "decision": "High",
                "risk_tags": ["절대적 표현", "근거 부족"],
                "confirmed_in_evidence": ["목표 연도가 적혀 있음(p.1)"],
                "missing_fields": ["범위/경계", "산정/방법"],
                "reason_bullets": ["기준연도와 범위가 확인되지 않음", "정량 수치가 없음"],
                "fix_paragraph": _LONG_FIX,
                "evidence_internal": "컨텍스트에 수치가 없습니다(p.1).",
            }
        },
        {
            "json": {
                "decision": "Mid",
                "risk_tags": ["범위 불명확"],
                "confirmed_in_evidence": [],
                "missing_fields": ["정의/기준"],
                "reason_bullets": [],
                "fix_paragraph": "범위를 명확히 제시해야 합니다.",
                "evidence_internal": "",
            }
        },
        {
            "json": {
                "decision": "NonRisk",
                "risk_tags": [],
                "confirmed_in_evidence": ["기준연도 2020년이 적혀 있음", "제3자 검증을 받았다고 적혀 있음"],
                "missing_fields": [],
                "reason_bullets": [],
                "fix_paragraph": "",
                "evidence_internal": "근거가 충분합니다.",
            }
        },
    ],
    "repair": [{"json": {"fix_paragraph": _LONG_FIX}}],
    "low_only": [
        {
            "json": {
                "low_reason_bullets": ["선언적 표현이 성과와 떨어져 있음"],
                "fix_paragraph": "의지를 밝힌 글만으로는 읽는 사람이 실제 성과를 가늠하기 어렵습니다. 수치와 기한이 있는 목표를 글의 앞에 두는 편이 좋겠습니다.",
            }
        },
    ],
}


# 대본의 「환경 낱말이 있는 문장」은 늘 기본 낱말 목록으로 고른다(스캔 설정이 넓힌 전역 정규식을 따라가지 않는다).
_PICK_ENV_RE = build_env_keywords_re(extra_keywords=None, include_general_env=False)


def _pick_env_sentences(user: str, n: int) -> str:
    """탐지 물음의 「[텍스트]」 뒤에서 환경 낱말이 있고 제목 꼴이 아닌 문장을 앞에서 n 개 골라 JSON 배열로."""
    marker = "[텍스트]\n"
    text = user[user.index(marker) + len(marker) :] if marker in user else user
    picked = [s for s in split_sentences_kor(text) if _PICK_ENV_RE.search(s.strip()) and not is_hard_label(s)][:n]
    return json.dumps([{"sentence": s} for s in picked], ensure_ascii=False)


def render_script_entry(entry: Any, user: str) -> str:
    """대본의 한 칸을 응답 글로. 글자열은 그대로, `{"json": …}` 은 JSON 으로, `{"fenced": …}` 는 코드 울타리에 싸서."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict) and "json" in entry:
        return json.dumps(entry["json"], ensure_ascii=False)
    if isinstance(entry, dict) and "fenced" in entry:
        return "```json\n" + json.dumps(entry["fenced"], ensure_ascii=False, indent=2) + "\n```"
    if isinstance(entry, dict) and "pick_env" in entry:
        return _pick_env_sentences(user, int(entry["pick_env"]))
    raise ValueError(f"대본의 칸을 읽을 수 없다: {entry!r}")


class ScriptedChat:
    """프롬프트 갈래(탐지·평가·다시 묻기·Low 전용)마다 대본을 차례로 돌려 가며 답한다. 보낸 메시지를 전부 적어 둔다."""

    def __init__(self, script: Optional[Dict[str, List[Any]]] = None, pack: Optional[PromptPack] = None):
        self.script = script if script is not None else DEFAULT_SCRIPT
        self.pack = pack or default_prompts(PROMPT_VERSION)
        self.cursor: Dict[str, int] = {}
        self.sent: List[List[Message]] = []

    def respond(self, system: str, user: str) -> str:
        kind = prompt_kind(system, self.pack)
        entries = self.script.get(kind)
        if not entries:
            raise ValueError(f"대본에 `{kind}` 갈래의 답이 없다")
        i = self.cursor.get(kind, 0)
        self.cursor[kind] = i + 1
        return render_script_entry(entries[i % len(entries)], user)

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        msgs = [Message(role=m.role, content=m.content) for m in messages]
        self.sent.append(msgs)
        return ChatReply(content=self.respond(msgs[0].content, msgs[1].content))


# ----------------------------------------------------------------------------
# 결정적 모의 임베딩
# ----------------------------------------------------------------------------
class MockEmbedding:
    """글자 두 개씩의 해시를 칸에 더해 길이 1 로 맞춘 벡터. 같은 글이면 늘 같은 벡터다. 뜻을 담지 않는다(synthetic)."""

    def __init__(self, dim: int = 256, batch_size: int = EMBEDDING_BATCH_SIZE):
        self.dim = dim
        self.batch_size = batch_size
        self.document_requests: List[int] = []
        self.query_requests = 0

    def _vector(self, text: str) -> List[float]:
        v = [0.0] * self.dim
        t = text or ""
        grams = [t[i : i + 2] for i in range(max(1, len(t) - 1))] or [""]
        for g in grams:
            h = hashlib.sha256(g.encode("utf-8")).digest()
            v[int.from_bytes(h[:4], "big") % self.dim] += 1.0 if h[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0.0:
            v[0] = 1.0
            norm = 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            self.document_requests.append(len(batch))
            out.extend(self._vector(t) for t in batch)
        return out

    def embed_query(self, text: str) -> List[float]:
        self.query_requests += 1
        return self._vector(text)


# ----------------------------------------------------------------------------
# 토큰 세기 — 「못 쟀다」를 0 으로 접지 않는다
# ----------------------------------------------------------------------------
Encoder = Callable[[str], int]


class TokenCounter:
    """부호화 이름 → 세는 함수. 세는 함수를 얻지 못한 부호화는 「못 쟀다」(None)로 남긴다."""

    def __init__(self, encoders: Optional[Dict[str, Encoder]] = None, reasons: Optional[Dict[str, str]] = None):
        self.encoders = dict(encoders or {})
        self.reasons = dict(reasons or {})

    def count(self, encoding: str, text: str) -> Optional[int]:
        enc = self.encoders.get(encoding)
        if enc is None:
            return None
        return enc(text)

    def reason(self, encoding: str) -> str:
        return self.reasons.get(encoding, "토큰 세는 것이 주어지지 않았다")


def tiktoken_counter(encodings: Sequence[str] = (CHAT_ENCODING, EMBEDDING_ENCODING)) -> TokenCounter:
    """`tiktoken` 으로 센다. 부호화 파일을 얻지 못하면(네트워크 없음 등) 그 부호화는 「못 쟀다」로 남는다."""
    encoders: Dict[str, Encoder] = {}
    reasons: Dict[str, str] = {}
    for name in encodings:
        try:
            import tiktoken

            enc = tiktoken.get_encoding(name)
            encoders[name] = (lambda e: lambda text: len(e.encode(text, disallowed_special=())))(enc)
        except Exception as e:  # 부호화 파일을 못 받음
            reasons[name] = f"{type(e).__name__}: {e}"[:300]
    return TokenCounter(encoders, reasons)


@dataclass
class Tally:
    """요청 수, 입력 글자 수, 입력 토큰 수. 토큰을 한 번이라도 못 셌으면 합계는 「못 쟀다」다."""

    encoding: str
    requests: int = 0
    chars: int = 0
    tokens: int = 0
    unmeasured: bool = False
    reason: str = ""

    def add(self, counter: TokenCounter, texts: Sequence[str], requests: int = 1) -> None:
        self.requests += requests
        for t in texts:
            self.chars += len(t)
            n = counter.count(self.encoding, t)
            if n is None:
                self.unmeasured = True
                self.reason = counter.reason(self.encoding)
            else:
                self.tokens += n

    def merge(self, other: "Tally") -> None:
        self.requests += other.requests
        self.chars += other.chars
        self.tokens += other.tokens
        if other.unmeasured:
            self.unmeasured = True
            self.reason = other.reason

    def to_json(self) -> Dict[str, Any]:
        if self.unmeasured:
            tokens: Dict[str, Any] = {"status": "unmeasured", "encoding": self.encoding, "reason": self.reason}
        else:
            tokens = {"status": "measured", "encoding": self.encoding, "value": self.tokens}
        return {"requests": self.requests, "input_chars": self.chars, "input_tokens": tokens}


# ----------------------------------------------------------------------------
# 호출 기록 (ts/llm/src/log.ts 의 CallRecord 와 같은 칸 이름)
# ----------------------------------------------------------------------------
def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class CallLog:
    records: List[Dict[str, Any]] = field(default_factory=list)

    def write(self, record: Dict[str, Any]) -> None:
        self.records.append(record)

    def dump_jsonl(self, path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for r in self.records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _record(
    *,
    provider: str,
    model: str,
    prompt_id: str,
    template_hash: str,
    request: Any,
    started: float,
    call_id: int,
    embedding_inputs: Optional[int] = None,
) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "callId": f"gw-{call_id:05d}",
        "attempt": 1,
        "provider": provider,
        "model": model,
        "apiModelId": None,
        "responseModelId": None,
        "promptId": prompt_id,
        # ts/llm 은 숫자 판을 쓴다. 노트북의 판은 글자열(`2026-01-15-v1`)이라 글자열로 싣는다.
        "promptVersion": PROMPT_VERSION,
        "templateHash": template_hash,
        "requestHash": sha256_json(request),
        # 모의 공급사는 토큰을 세지 않는다. 0 이 아니라 null(못 쟀다)이다.
        "inputTokens": None,
        "outputTokens": None,
        "cacheReadTokens": None,
        "cacheWriteTokens": None,
        "costUsd": None,
        "durationMs": int((time.monotonic() - started) * 1000),
        "resultKind": "ok",
        "tenant": "lab",
        "module": "greenwash",
        "warnings": [],
    }
    if embedding_inputs is not None:
        rec["embeddingInputs"] = embedding_inputs
    return rec


class RecordingChat:
    """대화 포트를 감싸 부를 때마다 호출 기록 한 줄을 남긴다. 본문은 싣지 않는다."""

    def __init__(
        self,
        inner: ChatPort,
        log: CallLog,
        *,
        provider: str,
        model: str,
        pack: Optional[PromptPack] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.inner = inner
        self.log = log
        self.provider = provider
        self.model = model
        self.pack = pack or default_prompts(PROMPT_VERSION)
        self.params = dict(params or {})

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        started = time.monotonic()
        try:
            return self.inner.invoke(messages)
        finally:
            system = messages[0].content if messages else ""
            self.log.write(
                _record(
                    provider=self.provider,
                    model=self.model,
                    prompt_id=f"greenwash/{prompt_kind(system, self.pack)}",
                    template_hash=hashlib.sha256(system.encode("utf-8")).hexdigest(),
                    request={"model": self.model, **self.params, "messages": [[m.role, m.content] for m in messages]},
                    started=started,
                    call_id=len(self.log.records) + 1,
                )
            )


class RecordingEmbedding:
    """임베딩 포트를 감싸 요청(묶음)마다 호출 기록 한 줄을 남긴다."""

    def __init__(
        self,
        inner: EmbeddingPort,
        log: CallLog,
        *,
        provider: str,
        model: str = EMBEDDING_MODEL,
        batch_size: int = EMBEDDING_BATCH_SIZE,
    ):
        self.inner = inner
        self.log = log
        self.provider = provider
        self.model = model
        self.batch_size = batch_size

    def _write(self, texts: List[str], started: float) -> None:
        self.log.write(
            _record(
                provider=self.provider,
                model=self.model,
                prompt_id="embedding",
                template_hash="",
                request={"model": self.model, "input": texts},
                started=started,
                call_id=len(self.log.records) + 1,
                embedding_inputs=len(texts),
            )
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            started = time.monotonic()
            out.extend(self.inner.embed_documents(batch))
            self._write(batch, started)
        return out

    def embed_query(self, text: str) -> List[float]:
        started = time.monotonic()
        v = self.inner.embed_query(text)
        self._write([text], started)
        return v
