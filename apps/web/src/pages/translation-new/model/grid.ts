// 쪽 칸 그리드의 셈(밴드 TRW0a ②). 순수 함수만 — PageGrid 가 쓴다.
import { PART_KEYS } from '../../../entities/translation/model/index.ts';
import type {
  PartKey,
  Range,
} from '../../../entities/translation/model/index.ts';

/** 한 번에 더 보이는 칸 수(시안 TR-02 「1~40쪽을 보고 있어요」). */
export const GRID_STEP = 40;

/** 보이는 칸 수: 지금 shown 개에서 step 개 더(쪽 수를 넘지 않음). shown 0 은 처음 그리기. */
export function visibleCount(
  pageCount: number,
  shown: number,
  step: number,
): number {
  return Math.min(pageCount, shown + step);
}

/** 그 쪽을 가진 파트(PART_KEYS 차례)와 겹침(둘 이상) 여부. */
export function cellState(
  page: number,
  ranges: Readonly<Record<PartKey, Range | null>>,
): { parts: PartKey[]; overlap: boolean } {
  const parts = PART_KEYS.filter((part) => {
    const range = ranges[part];
    return range !== null && range.from <= page && page <= range.to;
  });
  return { parts, overlap: parts.length > 1 };
}

/** 보이는 칸(1~shown) 밖에 칠한 파트와 그 범위(보이지 않는 부분만). */
export function hiddenPainted(
  ranges: Readonly<Record<PartKey, Range | null>>,
  shown: number,
): { part: PartKey; range: Range }[] {
  return PART_KEYS.flatMap((part) => {
    const range = ranges[part];
    if (range === null || range.to <= shown) return [];
    return [
      { part, range: { from: Math.max(range.from, shown + 1), to: range.to } },
    ];
  });
}
