import { describe, expect, it } from 'vitest';

import { parseTableInput } from '../../widgets/review-table/index.ts';
import { makeFakeInput } from './fakeRows.ts';

describe('가짜 행', () => {
  const input = makeFakeInput(5000);

  it('씨앗이 같으면 같은 행이 나오고, 다르면 다르다', () => {
    expect(makeFakeInput(200)).toEqual(makeFakeInput(200));
    expect(makeFakeInput(200, 1)).not.toEqual(makeFakeInput(200, 2));
  });

  it('입력 계약을 통과한다', () => {
    expect(parseTableInput(input).ok).toBe(true);
  });

  it('일곱 상태와 후보 0~3개가 다 섞여 있다', () => {
    const statuses = new Set(input.rows.map((row) => row.review.status));
    expect([...statuses].sort()).toEqual([
      'accepted',
      'declined',
      'edited',
      'finalized',
      'pending',
      'rejected',
      'rerequested',
    ]);
    expect(new Set(input.rows.map((row) => row.ai.candidates.length))).toEqual(
      new Set([0, 1, 2, 3]),
    );
    // 배출량을 계산하지 못한 후보도 있다.
    expect(
      input.rows.some((row) =>
        row.ai.candidates.some((candidate) => candidate.emission === null),
      ),
    ).toBe(true);
  });

  it('최종확정 행은 전부 배출량이 있다', () => {
    const finalized = input.rows.filter(
      (row) => row.review.status === 'finalized',
    );
    expect(finalized.length).toBeGreaterThan(100);
    expect(
      finalized.every((row) => row.ai.candidates[0]!.emission !== null),
    ).toBe(true);
  });

  it('배출량은 tCO2eq 다: 입력의 단위가 tCO2eq 이고, 값은 수량 × 계수(kgCO2e) ÷ 1000 한 번', () => {
    expect(input).toMatchObject({ version: 2, unit: 'tCO2eq' });
    const emissions = input.rows.flatMap((row) =>
      row.ai.candidates.flatMap((candidate) =>
        candidate.emission === null ? [] : [candidate.emission],
      ),
    );
    // 수량은 5000 이하, 가짜 계수는 9.1 이하라 kg 로는 45500, 톤으로는 45.5 를 넘지 못한다.
    expect(Math.max(...emissions)).toBeLessThanOrEqual(45.5);
    const row = input.rows.find(
      (entry) => entry.ai.candidates[0]?.factorValue,
    )!;
    const quantity = row.raw.quantity as number;
    const factorValue = row.ai.candidates[0]!.factorValue!;
    expect(row.ai.candidates[0]!.emission).toBeCloseTo(
      (quantity * factorValue) / 1000,
      4,
    );
  });
});
