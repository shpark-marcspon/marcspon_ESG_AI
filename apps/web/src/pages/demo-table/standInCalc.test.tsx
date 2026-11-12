// @vitest-environment jsdom
// 두 번 나누기 없음(sid:MARC-ENT-264 위험 ③). 후보의 배출량은 이미 tCO2eq 라, 계산 대역도 표도 다시 환산하지 않는다.
// 한 번 더 ÷1000 하면 1.8 이 0.0018 이 된다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { fakeLayout } from '../../shared/lib/testing/layout.ts';
import {
  ReviewTable,
  parseTableInput,
} from '../../widgets/review-table/index.ts';
import { DEMO_COLUMNS } from './columns.tsx';
import { standInCalculate } from './standInCalc.ts';

const parsed = parseTableInput({
  version: 2,
  unit: 'tCO2eq',
  categories: ['가'],
  rows: [
    {
      id: 'r1',
      raw: { itemName: '수지 원료', quantity: 1200, unit: 'kg' },
      ai: {
        category: '가',
        candidates: [
          {
            id: 'a',
            factorName: '계수 가',
            factorValue: 1,
            factorUnit: 'kgCO2e/kg',
            emission: 1.2,
          },
          {
            id: 'b',
            factorName: '계수 나',
            factorValue: 1.5,
            factorUnit: 'kgCO2e/kg',
            emission: 1.8,
          },
        ],
      },
      review: { status: 'pending' },
    },
  ],
});
if (!parsed.ok) throw new Error(parsed.errors.join('\n'));
const { rows, categories } = parsed.input;

let restoreLayout: () => void;
beforeEach(() => void (restoreLayout = fakeLayout()));
afterEach(() => {
  cleanup();
  restoreLayout();
});

describe('계산 대역은 받은 tCO2eq 를 그대로 돌려준다', () => {
  it('후보의 1.8 은 1.8 로 돌아온다', () => {
    expect(
      standInCalculate({
        row: rows[0]!,
        category: '가',
        candidate: rows[0]!.ai.candidates[1]!,
      }),
    ).toBe(1.8);
  });

  it('표에서 그 후보로 고쳐 최종 확정하면 확정 합계가 1.8 이다(0.0018 이 아니다)', () => {
    render(
      <ReviewTable
        rows={rows}
        categories={categories}
        columns={DEMO_COLUMNS}
        calculate={standInCalculate}
      />,
    );
    const row = () =>
      document.querySelector<HTMLElement>('[data-row-id="r1"]')!;
    fireEvent.click(within(row()).getByLabelText('펼치기'));
    fireEvent.click(within(row()).getByLabelText('후보 2 고르기'));
    expect(row().getAttribute('data-status')).toBe('edited');
    fireEvent.click(within(row()).getByRole('button', { name: '최종 확정' }));
    expect(row().getAttribute('data-status')).toBe('finalized');
    const summary = screen.getByTestId('rt-summary');
    expect(Number(summary.getAttribute('data-final-total'))).toBe(1.8);
    expect(summary.textContent).toContain('확정 합계 1.8 tCO2eq');
  });
});
