import { describe, expect, it } from 'vitest';

import { parseTableInput } from '../../src/widgets/review-table/model/index.ts';
import { buildTableInput, labRowSchema, standInEmission } from './scope3.ts';
import type { LabCall, LabFactor } from './scope3.ts';

const factor = (
  id: string,
  value: number | null,
  per: string | null,
): LabFactor => ({
  id,
  name: { original: `factor ${id}`, ko: id === 'f1' ? '수지' : null },
  value,
  unit: `kg CO2e/${per}`,
  unit_denominator: per,
  source: { name: '계수표' },
});
const factors = new Map(
  [
    factor('f1', 1.5, 'kg'),
    factor('f2', 2500, 'tonnes'),
    factor('f3', 0.3, 'USD'),
  ].map((f) => [f.id, f]),
);

// 실행 결과의 행에는 정답(gold)이 붙어 온다.
const rawRows = [
  {
    rowId: 'r1',
    itemName: '수지 원료',
    unit: 'kg',
    status: 'recommended',
    predictedCategory: 1,
    picks: ['f1', 'f2', 'f3'],
    basis: { used: 'activity' },
    calcStatus: 'computed',
    gold: { category: 1, factorIds: ['f2'], note: '정답 메모' },
  },
  {
    rowId: 'r2',
    itemName: '기타 용역',
    unit: null,
    status: 'no_candidates',
    predictedCategory: 'other',
    picks: [],
    basis: null,
    calcStatus: 'not_calculated',
    gold: { category: 2, factorIds: [], note: '정답 메모' },
  },
];
const call = (promptId: string, item: object, response: object): LabCall => ({
  promptId,
  body: {
    request: { user: [{ text: `ITEM_JSON: ${JSON.stringify(item)}` }] },
    responseText: JSON.stringify(response),
  },
});
const calls = [
  call(
    'scope3/classify@1',
    { item_name: '수지원료', unit: 'kg' },
    { category: 1, reason: '원료다.' },
  ),
  call(
    'scope3/recommend@1',
    { item_name: '수지원료', unit: 'kg' },
    {
      picks: [{ factor_id: 'f1', reason: '재질이 같다.', confidence: 'high' }],
    },
  ),
];

describe('분류·추천 실측 산출물 → 검토 표 입력', () => {
  const rows = rawRows.map((row) => labRowSchema.parse(row));
  const { input, counts } = buildTableInput(rows, factors, calls, [
    { row_id: 'r1', quantity: '1200', amount: '5000', currency: 'KRW' },
  ]);

  it('표의 입력 계약을 통과한다', () => {
    expect(parseTableInput(input).ok).toBe(true);
    expect(input.rows.map((row) => row.review.status)).toEqual([
      'pending',
      'pending',
    ]);
  });

  it('정답(gold)은 싣지 않는다', () => {
    expect(JSON.stringify(input)).not.toMatch(/gold|정답 메모|factorIds/);
  });

  it('후보의 순서는 추천 순서이고, 이유·신뢰도는 호출 기록에 있던 것만 붙는다(품목명의 빈칸이 달라도 잇는다)', () => {
    const [first, second] = input.rows[0]!.ai.candidates;
    expect(first).toMatchObject({
      id: 'f1',
      factorName: '수지',
      factorValue: 1.5,
      reason: '재질이 같다.',
      confidence: 'high',
    });
    expect(second).toMatchObject({ id: 'f2', factorName: 'factor f2' });
    expect(second).not.toHaveProperty('reason');
    expect(input.rows[0]!.ai.categoryNote).toBe('원료다.');
    expect(counts).toMatchObject({
      rows: 2,
      candidates: 3,
      withReason: 1,
      unknownFactors: 0,
    });
  });

  it('배출량(대역)은 단위가 같을 때만 계산하고, tCO2eq 로 낸다(kgCO2e ÷ 1000 한 번)', () => {
    expect(input.rows[0]!.ai.candidates.map((c) => c.emission)).toEqual([
      1.8,
      3,
      null,
    ]); // kg×kg, kg→t, kg 과 USD
    expect(standInEmission(2, 't', factors.get('f1')!)).toBe(3);
    // 작은 값이 톤에서 0.1 로 잘려 0 이 되지 않는다(1 kg × 1.5 = 1.5 kgCO2e = 0.0015 t).
    expect(standInEmission(1, 'kg', factors.get('f1')!)).toBe(0.0015);
    expect(standInEmission(null, 'kg', factors.get('f1')!)).toBeNull();
    expect(standInEmission(5, 'kg', factor('x', null, 'kg'))).toBeNull();
    expect(counts.withEmission).toBe(2);
  });

  it('이름이 같아도 단위가 다르면 다른 품목이다: 이유를 잇지 않는다. 수량이 비어 있으면 0 이 아니라 없음이다', () => {
    const other = labRowSchema.parse({ ...rawRows[0], rowId: 'r9', unit: 't' });
    const result = buildTableInput([other], factors, calls, [
      { row_id: 'r9', quantity: '', amount: null },
    ]);
    expect(result.input.rows[0]!.ai.candidates[0]).not.toHaveProperty('reason');
    expect(result.input.rows[0]!.raw.quantity).toBeNull();
    expect(result.input.rows[0]!.ai.candidates.map((c) => c.emission)).toEqual([
      null,
      null,
      null,
    ]);
  });

  it('카테고리 번호는 이름표로 바뀐다', () => {
    expect(input.rows[0]!.ai.category).toBe('1 구매한 제품과 서비스');
    expect(input.categories).toEqual([
      '1 구매한 제품과 서비스',
      '2 자본재',
      '4 업스트림 운송',
      '6 출장',
      '7 통근',
      '9 다운스트림 운송',
      '기타',
    ]);
    const labelOf = (predictedCategory: number | string) =>
      buildTableInput(
        [labRowSchema.parse({ ...rawRows[1], predictedCategory })],
        factors,
      ).input.rows[0]!.ai.category;
    expect([1, 2, 4, 6, 7, 9, 'other'].map(labelOf)).toEqual(input.categories);
  });

  it('후보가 없는 행, 카테고리가 other 인 행', () => {
    expect(input.rows[1]).toMatchObject({
      processing: '후보 없음',
      ai: { category: '기타', candidates: [] },
      raw: { quantity: null, unit: null },
    });
  });
});
