// 테스트가 쓰는 행 만들기. 제품 코드는 이 파일을 쓰지 않는다.
import type { Candidate, ReviewRow } from './row.ts';

export function candidate(
  id: string,
  emission: number | null = 100,
): Candidate {
  return {
    id,
    factorName: `계수 ${id}`,
    factorValue: emission === null ? null : 1,
    factorUnit: 'kgCO2e/kg',
    emission,
  };
}

/** 기본은 후보 둘(배출량 100, 250)인 검토대기 행. */
export function makeRow(
  patch: Partial<ReviewRow> & { candidates?: Candidate[] } = {},
): ReviewRow {
  const { candidates, ...rest } = patch;
  return {
    id: 'r1',
    raw: { itemName: '품목' },
    ai: {
      category: '가',
      candidates: candidates ?? [candidate('a', 100), candidate('b', 250)],
    },
    edit: null,
    status: 'pending',
    ...rest,
  };
}

// 시험 파일 셋이 쓰던 행 묶음(밴드 CW1 ②, sid:MARC-ISSUE-114 (1)). 꼴이 저마다 달라 이름을 갈랐다.

/** 100행. 짝수째는 검토대기, 홀수째는 반영. */
export function alternatingRows(count = 100): ReviewRow[] {
  return Array.from({ length: count }, (_, i) =>
    makeRow({
      id: `r${i}`,
      raw: { itemName: `품목 ${i}` },
      status: i % 2 === 0 ? 'pending' : 'accepted',
      candidates: [candidate('a', 100), candidate('b', 250)],
    }),
  );
}

/** 200행. 짝수째는 반영, 홀수째는 검토대기. 열째마다 후보가 없다. 수량은 섞여 있고 몇 개는 비어 있다. */
export function boardRows(count = 200): ReviewRow[] {
  return Array.from({ length: count }, (_, i) =>
    makeRow({
      id: `r${i}`,
      raw: {
        itemName: i % 4 === 0 ? `강판 ${i}` : `수지 ${i}`,
        amount: i % 7 === 0 ? null : (i * 37) % 101,
      },
      status: i % 2 === 0 && i % 10 !== 0 ? 'accepted' : 'pending',
      candidates: i % 10 === 0 ? [] : [candidate(`c${i}`, 10)],
    }),
  );
}

/** 여섯 행: 검토대기 셋(r0~r2), 반영(r3), 최종확정(r4), 후보의 배출량이 없는 반영(r5). */
export function sixRows(): ReviewRow[] {
  return [
    makeRow({ id: 'r0', raw: { itemName: '품목 0' } }),
    makeRow({ id: 'r1', raw: { itemName: '품목 1' } }),
    makeRow({ id: 'r2', raw: { itemName: '품목 2' } }),
    makeRow({ id: 'r3', raw: { itemName: '품목 3' }, status: 'accepted' }),
    makeRow({ id: 'r4', raw: { itemName: '품목 4' }, status: 'finalized' }),
    makeRow({
      id: 'r5',
      raw: { itemName: '품목 5' },
      status: 'accepted',
      candidates: [candidate('a', null)],
    }),
  ];
}
