// @vitest-environment jsdom
// 배출량 글자는 세 자리(열 칸, 요약의 합계, 펼친 속)에서 같다 — 셋 다 model/format.ts 의 꼴 하나를 쓴다(sid:MARC-ENT-272).
// 열 칸은 이 화면(columns.tsx)이 그리므로 시험도 여기 둔다: 열이 자기 사본 꼴을 쓰면 여기서 빨강이다.
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

const inputOf = (emission: number) => {
  const parsed = parseTableInput({
    version: 2,
    unit: 'tCO2eq',
    categories: ['가'],
    rows: [
      {
        id: 'r1',
        raw: { itemName: '볼트', quantity: 1, unit: 'kg' },
        ai: {
          category: '가',
          candidates: [
            {
              id: 'a',
              factorName: '계수 가',
              factorValue: 1.5,
              factorUnit: 'kgCO2e/kg',
              emission,
            },
          ],
        },
        review: { status: 'finalized' },
      },
    ],
  });
  if (!parsed.ok) throw new Error(parsed.errors.join('\n'));
  return parsed.input;
};

let restoreLayout: () => void;
beforeEach(() => void (restoreLayout = fakeLayout()));
afterEach(() => {
  cleanup();
  restoreLayout();
});

describe('배출량 글자: 열 칸·합계·펼친 속', () => {
  it.each([
    [0.0004, '<0.001'],
    [0.0015, '0.002'],
    [0.28, '0.28'],
    [12345.6789, '12,345.679'],
  ])('%s 는 세 자리 모두 「%s」', (emission, text) => {
    const { rows, categories } = inputOf(emission);
    render(
      <ReviewTable
        rows={rows}
        categories={categories}
        columns={DEMO_COLUMNS}
        calculate={standInCalculate}
      />,
    );
    const row = document.querySelector<HTMLElement>('[data-row-id="r1"]')!;
    expect(row.querySelector('[data-column="emission"]')!.textContent).toBe(
      text,
    );
    expect(screen.getByTestId('rt-summary').textContent).toContain(
      `확정 합계 ${text} tCO2eq`,
    );
    fireEvent.click(within(row).getByLabelText('펼치기'));
    const opened = document.querySelector<HTMLElement>('[data-row-id="r1"]')!;
    expect(opened.textContent).toContain(`${text} tCO2eq`);
  });
});
