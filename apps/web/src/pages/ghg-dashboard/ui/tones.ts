// 대시보드 Scope 색(밴드 DB1 ② — e6 값 파일 0: Scope 1 보라 · Scope 2 청록 · Scope 3 초록). bg-current·stroke-current 와 함께 쓴다.
export const SCOPE_TONES = [
  'text-support-purple',
  'text-support-turquoise',
  'text-support-success',
] as const;

export const toneOf = (index: number): string =>
  SCOPE_TONES[index] ?? 'text-text-tertiary';

// 3개년 막대 칸 연한 바탕(밴드 DB2 — e6 「연한 바탕」: 막대 색 토큰에 투명도 3%, 새 토큰 없음).
export const SCOPE_WASHES = [
  'bg-support-purple/[0.03]',
  'bg-support-turquoise/[0.03]',
  'bg-support-success/[0.03]',
] as const;

export const washOf = (index: number): string => SCOPE_WASHES[index] ?? '';
