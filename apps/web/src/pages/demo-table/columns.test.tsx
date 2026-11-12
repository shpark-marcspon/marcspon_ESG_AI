// 띄워 보는 화면의 열 구성. 열은 「지금 값」(수정했으면 수정값)을 보여야 한다. 원본값을 보이면 사람이 고친 것이 표에 안 나온다.
import { describe, expect, it } from 'vitest';

import type { ReviewRow } from '../../widgets/review-table/index.ts';
import { DEMO_COLUMNS } from './columns.tsx';

const candidates = [
  {
    id: 'a',
    factorName: '계수 가',
    factorValue: 1,
    factorUnit: 'kgCO2e/kg',
    emission: 100,
  },
  {
    id: 'b',
    factorName: '계수 나',
    factorValue: 2,
    factorUnit: 'kgCO2e/kg',
    emission: 1234.56,
  },
];
const base: ReviewRow = {
  id: 'r',
  raw: { itemName: '품목', quantity: 1200, unit: 'kg' },
  ai: { category: '가', candidates },
  edit: null,
  status: 'pending',
};
const column = (id: string) => DEMO_COLUMNS.find((entry) => entry.id === id)!;
const shown = (id: string, row: ReviewRow) => {
  const entry = column(id);
  return entry.render ? entry.render(row) : entry.value(row);
};

describe('띄워 보는 화면의 열', () => {
  it('고치지 않은 행: 배출량·계수·카테고리는 AI 원본(대표 후보)의 값이다', () => {
    expect(column('emission').value(base)).toBe(100);
    expect(shown('emission', base)).toBe('100');
    expect(shown('factor', base)).toBe('계수 가');
    expect(shown('category', base)).toBe('가');
  });

  it('다른 후보를 골라 고친 행: 배출량 열은 원본값(100)이 아니라 다시 계산한 값을 보이고, 정렬도 그 값으로 한다', () => {
    const edited: ReviewRow = {
      ...base,
      status: 'edited',
      edit: { candidateId: 'b', emission: 1234.56, recalcPending: false },
    };
    expect(column('emission').value(edited)).toBe(1234.56);
    expect(shown('emission', edited)).toBe('1,234.56');
    expect(shown('factor', edited)).toBe('계수 나');
  });

  it('카테고리를 고친 행은 원본과 고친 값을 같이 보인다', () => {
    const edited: ReviewRow = {
      ...base,
      status: 'edited',
      edit: { category: '나', emission: 100, recalcPending: false },
    };
    expect(shown('category', edited)).toBe('가 → 나');
    expect(column('category').value(edited)).toBe('나');
  });

  it('배출량 열의 네 가지 글자: 값, 재계산 대기, 계산 실패, 없음(—)', () => {
    const pending: ReviewRow = {
      ...base,
      status: 'edited',
      edit: { candidateId: 'b', emission: null, recalcPending: true },
    };
    const failed: ReviewRow = {
      ...base,
      status: 'edited',
      edit: {
        candidateId: 'b',
        emission: null,
        recalcPending: false,
        recalcFailed: true,
      },
    };
    const none: ReviewRow = {
      ...base,
      status: 'edited',
      edit: { candidateId: 'b', emission: null, recalcPending: false },
    };
    expect([
      shown('emission', base),
      shown('emission', pending),
      shown('emission', failed),
      shown('emission', none),
    ]).toEqual(['100', '재계산 대기', '계산 실패', '—']);
    // 정렬에 쓰는 값은 셋 다 비어 있다(맨 뒤로 간다).
    expect(
      [pending, failed, none].map((row) => column('emission').value(row)),
    ).toEqual([null, null, null]);
  });

  it('배출량 열은 소수 셋째까지, 0 이 아닌 작은 값은 「<0.001」(수량 열의 꼴과 따로다 — sid:MARC-ENT-272)', () => {
    const withEmission = (emission: number): ReviewRow => ({
      ...base,
      ai: { ...base.ai, candidates: [{ ...candidates[0]!, emission }] },
    });
    expect(shown('emission', withEmission(0.0015))).toBe('0.002');
    expect(shown('emission', withEmission(0.0004))).toBe('<0.001');
    expect(shown('emission', withEmission(12345.6789))).toBe('12,345.679');
    // 수량 열은 「<0.001」 규칙을 타지 않는다.
    expect(shown('quantity', { ...base, raw: { quantity: 0.0004 } })).toBe('0');
  });
});
