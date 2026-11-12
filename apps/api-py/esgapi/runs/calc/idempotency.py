"""실행 만들기의 Idempotency-Key(밴드 IK1): 열쇠의 꼴과, 같은 열쇠로 다시 보낸 요청이 같은 요청인지 가를 본문 sha256.

    KEY_PATTERN                 열쇠의 꼴 — 소문자 UUID(36자). 경로의 머리 무늬(apis)가 쓴다. 틀리면 422
    body_sha256(...)            검증을 지난 본문 다섯 칸(launchKey·retrySegments 가 있으면 그만큼 더)을 정해진 차례의
                                JSON 바이트로 적은 sha256 hex

★ 바이트: {"module","flowId","documentId","options","resumeFromRunId"} 이 차례(기본값 채움 — flowId 생략 = null),
  launchKey(LK1)는 값이 있을 때만 여섯째로 덧붙인다(없으면 IK1 바이트 그대로 — 배포 전 열쇠의 다시 보냄이 같은 sha.
  같은 Idempotency-Key·다른 launchKey 는 다른 요청 → 409),
  retrySegments(RM1c)는 값이 있을 때만 그 다음에 {"fromRunId","step","keys"} 이 차례로 덧붙인다(keys 는 보낸 차례 —
  없으면 그 앞 바이트 그대로. 같은 Idempotency-Key·다른 retrySegments(keys 차례만 달라도) → 409),
  구분자 `,`·`:` 공백 없음, ensure_ascii=False(UTF-8), allow_nan=True(json 의 기본 — NaN 이 든 본문이 열쇠
  유무로 다른 갈래에 서지 않게: 열쇠가 있어도 BASE 와 같은 길로 간다. IK1 critic 처분 m3).
  **options 의 열쇠 차례는 그대로다**(sort_keys 가 아니다): 문서 없는 흐름은 옵션을 쓴 차례로 읽으므로
  (runs/models.py 의 OrderedJSONField) 차례가 다르면 다른 요청이다.
★ 무효 조건: 같은 웹이 같은 제출을 다시 보내면 바이트가 같으니 차례 규칙의 실무 차이는 0 이다. 손으로 옵션 차례를 바꿔
  다시 보내는 클라이언트는 409 를 받는다.
★ 저장된 칸(module·flow_id·options…)과 견주지 않는다: 흐름 생략은 기본 흐름으로 바뀌어 저장되고 이어 돌기는 옵션을 앞
  실행 것으로 갈아 끼운다 — 요청 그대로의 바이트만 같은 요청을 가른다.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Final

KEY_PATTERN: Final = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def body_sha256(
    *,
    module: str,
    flow_id: str | None,
    document_id: int | None,
    options: Mapping[str, object],
    resume_from: int | None,
    launch_key: str | None = None,
    retry: tuple[int, str, Sequence[str]] | None = None,
) -> str:
    """본문 다섯 칸(launch_key·retry 가 있으면 그만큼 더 — retry = (fromRunId, step, keys))의 정규화 sha256 hex
    (머리말의 바이트). 공백·최상위 열쇠 차례와 무관하고 options·keys 차례와는 유관하다."""
    canonical: dict[str, object] = {
        "module": module,
        "flowId": flow_id,
        "documentId": document_id,
        "options": dict(options),
        "resumeFromRunId": resume_from,
    }
    if launch_key is not None:
        canonical["launchKey"] = launch_key
    if retry is not None:
        from_run_id, step, keys = retry
        canonical["retrySegments"] = {"fromRunId": from_run_id, "step": step, "keys": list(keys)}
    text = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()  # 짝 없는 서로게이트는 뒤에서 400(LH1·340)
