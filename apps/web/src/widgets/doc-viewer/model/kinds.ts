// 종류 → 색과 이름. 뷰어는 종류의 뜻을 모른다. 입력이 준 색을 쓰고, 안 준 종류에는 차례대로 기본 색을 준다.
import type { ViewerInput } from './contract.ts';

export interface KindLook {
  label: string;
  color: string;
}

const FALLBACK_COLORS = [
  '#2563eb',
  '#d97706',
  '#7c3aed',
  '#059669',
  '#db2777',
  '#475569',
];
export const MIXED_COLOR = '#475569';

export function kindLooks(input: ViewerInput): Map<string, KindLook> {
  const looks = new Map<string, KindLook>();
  for (const style of input.kinds ?? [])
    looks.set(style.kind, { label: style.label, color: style.color });
  for (const h of input.highlights) {
    if (!looks.has(h.kind)) {
      looks.set(h.kind, {
        label: h.kind,
        color: FALLBACK_COLORS[looks.size % FALLBACK_COLORS.length]!,
      });
    }
  }
  return looks;
}
