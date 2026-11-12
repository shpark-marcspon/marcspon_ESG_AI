// 썸네일 칠하기(밴드 FW1b ①, 시안 GW-02_r1 「쪽을 누르면 칠하거나 지웁니다」).
// - 누르기: 고른 파트에 그 쪽을 넣거나 뺀다(토글).
// - 끌기: 시작 쪽의 토글 방향(없던 쪽이면 넣기, 있던 쪽이면 빼기)으로, 시작 쪽부터 지금 쪽까지를 칠한다.
//   끄는 동안의 기준은 끌기를 시작할 때의 집합이다(되돌아 끌면 지나갔던 쪽이 원래대로 돌아온다).
import { sortPages } from '../../../entities/greenwash/model/index.ts';

export type PaintMode = 'add' | 'remove';

/** 쪽 하나를 넣거나 뺀다. */
export function togglePage(pages: readonly number[], page: number): number[] {
  return pages.includes(page) ?
      pages.filter((p) => p !== page)
    : sortPages([...pages, page]);
}

/** 끌기를 시작한 쪽에서 방향을 정한다. */
export function paintModeAt(pages: readonly number[], page: number): PaintMode {
  return pages.includes(page) ? 'remove' : 'add';
}

/** 끌기 시작 때의 집합(base)에, from~to(어느 쪽이 크든) 구간을 mode 로 칠한 집합. */
export function paintRange(
  base: readonly number[],
  mode: PaintMode,
  from: number,
  to: number,
): number[] {
  const low = Math.min(from, to);
  const high = Math.max(from, to);
  const inRange = (page: number) => page >= low && page <= high;
  if (mode === 'remove') return base.filter((page) => !inRange(page));
  const added: number[] = [];
  for (let page = low; page <= high; page++) added.push(page);
  return sortPages([...base, ...added]);
}
