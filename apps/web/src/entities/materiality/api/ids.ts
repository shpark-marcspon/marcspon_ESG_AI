// 중대성평가 어댑터의 id·열쇠 꼴(밴드 IRW1 ①). 데이터 검증 api/ids.ts 와 같은 셈(가져오지 않고 옮겨 적음 — 공통화는 후속).
// - 나가는 id: `^[1-9][0-9]*$` 글자만 수로. 아니면 요청 없이 not_found.
// - Idempotency-Key: 소문자 UUID(서버 runs/calc/idempotency.py KEY_PATTERN).

/** 열쇠를 짓는 함수(시험이 열쇠를 고정한다). */
export type NewKey = () => string;

export const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export const newKey: NewKey = () => {
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

/** 나가는 id: 양의 정수 글자만 수로. 아니면 null(요청하지 않는다). */
export function serverId(id: string): number | null {
  if (!/^[1-9][0-9]*$/.test(id)) return null;
  const value = Number(id);
  return Number.isSafeInteger(value) ? value : null;
}
