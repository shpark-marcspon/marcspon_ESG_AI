// 실행 만들기(POST /runs)의 Idempotency-Key 열쇠(밴드 GR2, sid:MARC-ISSUE-225 웹 몫 — 서버 IK1 병합 71bfce3).
// 꼴은 서버 KEY_PATTERN(apps/api-py/esgapi/runs/calc/idempotency.py) 그대로 소문자 UUID(36자). 틀리면 서버가 422.
// 쓰는 법(훅이 쥔다 — useNewCheckForm·useRerunAction): 사용자가 단추를 새로 누른 한 번 = 열쇠 하나.
//   답이 끊기면(unreachable) 열쇠를 쥔 채 다음 누름에 같은 열쇠로 다시 보낸다 — 서버가 앞 실행을 201 로 돌려줘 실행은 하나다.
//   성공·서버 거절(api)이면 버린다(다음 누름은 새 열쇠). 화면을 떠나면(훅이 내려가면) 같이 버려진다.
// crypto.randomUUID 는 보안 출처(https·localhost)에만 있다: 없으면 getRandomValues 로 같은 꼴(v4)을 짓는다.

/** 열쇠를 짓는 함수. 훅은 이것을 받아 쓴다(시험이 열쇠를 고정한다). */
export type NewIdempotencyKey = () => string;

export const IDEMPOTENCY_KEY_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export const newIdempotencyKey: NewIdempotencyKey = () => {
  if (typeof crypto.randomUUID === 'function')
    return crypto.randomUUID().toLowerCase();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'));
  return [
    hex.slice(0, 4),
    hex.slice(4, 6),
    hex.slice(6, 8),
    hex.slice(8, 10),
    hex.slice(10, 16),
  ]
    .map((part) => part.join(''))
    .join('-');
};
