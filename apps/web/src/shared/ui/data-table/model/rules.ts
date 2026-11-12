// 목록 표의 규칙. 순수 TypeScript 다(React·TanStack·DOM 을 모른다).

/** 열의 정렬 상태. TanStack 의 getIsSorted() 와 같은 꼴이고, 키트 SortIndicator 의 direction 과도 같다. */
export type SortState = false | 'asc' | 'desc';
/** 머리 칸의 aria-sort 값. */
export type AriaSort = 'ascending' | 'descending' | 'none';
/** 칸 안의 글자 정렬. */
export type CellAlign = 'left' | 'center' | 'right';

/** 정렬 상태 → aria-sort. 정렬할 수 있는 열에만 단다(정렬할 수 없는 열에는 속성을 두지 않는다). */
export function ariaSortOf(sort: SortState): AriaSort {
  if (sort === 'asc') return 'ascending';
  if (sort === 'desc') return 'descending';
  return 'none';
}

/**
 * 열 정의의 meta.align → 칸 정렬. 기본은 왼쪽이다.
 * 숫자 열은 right, 체크·버튼 열은 center 를 준다. 모르는 값도 왼쪽이다.
 */
export function alignOf(meta: unknown): CellAlign {
  const align =
    meta && typeof meta === 'object' ?
      (meta as { align?: unknown }).align
    : undefined;
  return align === 'center' || align === 'right' ? align : 'left';
}

/**
 * 열의 스켈레톤 막대 폭(밴드 LD1 ②). load-skeleton 의 SkeletonWidth 와 같은 꼴이다 — 칸 규칙상 model·hooks 는 다른 부품을 못 가져와
 * 여기 다시 적는다(같은 꼴인지는 ui/DataTable.test.tsx 가 타입으로 본다). 'long' = 긴 글 칸, 수 = 고정 px, 짝 = 줄마다 그 사이.
 */
export type ColumnSkeleton =
  'long' | number | readonly [min: number, max: number];

/** 열 정의의 meta.skeleton → 막대 폭. 없거나 모르는 꼴이면 'long'. */
export function skeletonOf(meta: unknown): ColumnSkeleton {
  const width =
    meta && typeof meta === 'object' ?
      (meta as { skeleton?: unknown }).skeleton
    : undefined;
  if (typeof width === 'number' && Number.isFinite(width) && width > 0)
    return width;
  if (
    Array.isArray(width) &&
    width.length === 2 &&
    width.every((n) => typeof n === 'number' && Number.isFinite(n) && n > 0)
  )
    return [width[0] as number, width[1] as number];
  return 'long';
}

/** 누를 수 있는 줄에서 「누름」으로 치는 키: Enter 와 Space. */
export function isActivationKey(key: string): boolean {
  return key === 'Enter' || key === ' ';
}

/**
 * 칸 안의 컨트롤. 이것을 누르면 줄 클릭으로 번지지 않는다(키트 tanstack-table-renderer 의 목록
 * button·a·input·checkbox·switch + label·radio — sid:MARC-ENT-599 규칙 3, 밴드 TB1).
 */
export const CONTROL_SELECTOR =
  'button, a, input, label, [role="checkbox"], [role="switch"], [role="radio"]';
