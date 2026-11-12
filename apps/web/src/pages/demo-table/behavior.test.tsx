// @vitest-environment jsdom
// 같은 동작 테스트를 두 화면(표, 카드)에 그대로 돌린다.
// 둘 다 통과하면: 동작은 헤드리스 층과 업무 로직에 있고, 화면은 바꿔 끼울 수 있다.
// 화면을 새로 만들 때 이 테스트가 요구하는 것은 이름표뿐이다:
//   행 = [data-row-id][data-status], 스크롤 상자 = data-testid="rt-scroll",
//   요약 = data-testid="rt-summary"(data-final-total, [data-status-count][data-count]), 일괄 결과 = data-testid="rt-bulk-result",
//   계산 실패 = 행의 data-calc-failed, 요약의 data-recalc-failed, 펼친 행 속의 data-testid="rt-calc-failed" 와 「다시 계산」 단추,
//   그리고 단추·입력의 이름(aria-label 또는 글자).
import type { ComponentType } from 'react';

import {
  act,
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
  currentEmission,
  parseTableInput,
  summarize,
} from '../../widgets/review-table/index.ts';
import type {
  ReviewRow,
  ReviewTableProps,
} from '../../widgets/review-table/index.ts';
import { ReviewCards } from './ReviewCards.tsx';
import { DEMO_COLUMNS } from './columns.tsx';
import { makeFakeInput } from './fakeRows.ts';
import { failingStandIn, standInCalculate } from './standInCalc.ts';

const parsed = parseTableInput(makeFakeInput(300, 7));
if (!parsed.ok) throw new Error(parsed.errors.join('\n'));
const { rows, categories } = parsed.input;
const before = summarize(rows);

const SCREENS: [string, ComponentType<ReviewTableProps>][] = [
  ['표', ReviewTable],
  ['카드(둘째 화면)', ReviewCards],
];

let restoreLayout: () => void;
beforeEach(() => void (restoreLayout = fakeLayout()));
afterEach(() => {
  cleanup();
  restoreLayout();
});

describe.each(SCREENS)('검토 표의 동작: %s', (_name, Screen) => {
  const show = () =>
    render(
      <Screen
        rows={rows}
        categories={categories}
        columns={DEMO_COLUMNS}
        calculate={standInCalculate}
      />,
    );
  const domRows = () => [
    ...document.querySelectorAll<HTMLElement>('[data-row-id]'),
  ];
  const rowElement = (id: string) =>
    document.querySelector<HTMLElement>(`[data-row-id="${id}"]`)!;
  const summary = () => screen.getByTestId('rt-summary');
  const count = (status: string) =>
    Number(
      summary()
        .querySelector(`[data-status-count="${status}"]`)!
        .getAttribute('data-count'),
    );
  const finalTotal = () => Number(summary().getAttribute('data-final-total'));
  /** 그 행만 남게 걸러서 화면에 올리고 펼친다. */
  function open(row: ReviewRow): HTMLElement {
    fireEvent.change(screen.getByLabelText('글자로 걸러 보기'), {
      target: { value: String(row.raw.itemName) },
    });
    fireEvent.click(within(rowElement(row.id)).getByLabelText('펼치기'));
    return rowElement(row.id);
  }

  it('300행 가운데 보이는 만큼만 DOM 에 있다', () => {
    show();
    expect(domRows().length).toBeGreaterThan(5);
    expect(domRows().length).toBeLessThan(30);
    expect(Number(summary().getAttribute('data-total'))).toBe(300);
    expect(count('pending')).toBe(before.byStatus.pending);
    expect(finalTotal()).toBeCloseTo(before.finalTotal, 6);
  });

  it('다른 후보를 골라 수정하고 최종 확정하면 요약이 바뀐다', () => {
    show();
    const target = rows.find(
      (row) =>
        row.status === 'pending' &&
        row.ai.candidates.length >= 2 &&
        row.ai.candidates[1]!.emission !== null,
    )!;
    const element = open(target);
    fireEvent.click(within(element).getByLabelText('후보 2 고르기'));
    expect(rowElement(target.id).dataset.status).toBe('edited');
    expect(count('edited')).toBe(before.byStatus.edited + 1);
    // 아직 확정 전이라 결과 합계는 그대로다.
    expect(finalTotal()).toBeCloseTo(before.finalTotal, 6);

    fireEvent.click(
      within(rowElement(target.id)).getByRole('button', { name: '최종 확정' }),
    );
    expect(rowElement(target.id).dataset.status).toBe('finalized');
    expect(count('finalized')).toBe(before.byStatus.finalized + 1);
    // 합계에는 원본(대표 후보)이 아니라 고른 후보의 값이 든다.
    expect(finalTotal()).toBeCloseTo(
      before.finalTotal + target.ai.candidates[1]!.emission!,
      6,
    );
  });

  it('사유 없이 반려하면 거부되고, 사유를 적으면 반려된다', () => {
    show();
    const target = rows.find((row) => row.status === 'pending')!;
    const element = open(target);
    fireEvent.click(within(element).getByRole('button', { name: '반려' }));
    expect(
      within(rowElement(target.id)).getByRole('alert').textContent,
    ).toContain('사유');
    expect(rowElement(target.id).dataset.status).toBe('pending');

    fireEvent.change(
      within(rowElement(target.id)).getByLabelText('반려 사유'),
      { target: { value: '계수가 맞지 않는다' } },
    );
    fireEvent.click(
      within(rowElement(target.id)).getByRole('button', { name: '반려' }),
    );
    expect(rowElement(target.id).dataset.status).toBe('rejected');
    expect(count('rejected')).toBe(before.byStatus.rejected + 1);
  });

  it('상태로 걸러 본 뒤 일괄 최종 확정: 화면에 없는 행까지, 걸러 본 그 행들만 바뀐다', () => {
    show();
    fireEvent.change(screen.getByLabelText('상태로 걸러 보기'), {
      target: { value: 'accepted' },
    });
    expect(
      Number(screen.getByTestId('rt-shown').getAttribute('data-shown')),
    ).toBe(before.byStatus.accepted);
    // 반영 행이 화면에 다 들어오지 않는다.
    expect(domRows().length).toBeLessThan(before.byStatus.accepted);

    fireEvent.click(screen.getByRole('button', { name: '일괄 최종 확정' }));
    const accepted = rows.filter((row) => row.status === 'accepted');
    const able = accepted.filter((row) => currentEmission(row) !== null);
    const result = screen.getByTestId('rt-bulk-result');
    expect(Number(result.getAttribute('data-applied'))).toBe(able.length);
    expect(Number(result.getAttribute('data-skipped'))).toBe(
      accepted.length - able.length,
    );

    fireEvent.change(screen.getByLabelText('상태로 걸러 보기'), {
      target: { value: '' },
    });
    expect(count('finalized')).toBe(before.byStatus.finalized + able.length);
    expect(count('accepted')).toBe(accepted.length - able.length);
    expect(count('pending')).toBe(before.byStatus.pending);
    expect(count('edited')).toBe(before.byStatus.edited);
    expect(finalTotal()).toBeCloseTo(
      before.finalTotal +
        able.reduce((sum, row) => sum + currentEmission(row)!, 0),
      6,
    );
  });

  it('행 둘을 골라 일괄 반영하면 그 둘만 바뀐다', () => {
    show();
    const targets = domRows()
      .filter((element) => element.dataset.status === 'pending')
      .slice(0, 2);
    expect(targets).toHaveLength(2);
    const ids = targets.map((element) => element.dataset.rowId!);
    const able = ids.filter(
      (id) => rows.find((row) => row.id === id)!.ai.candidates.length > 0,
    ).length;
    for (const id of ids)
      fireEvent.click(within(rowElement(id)).getByLabelText('행 고르기'));
    expect(rowElement(ids[0]!).getAttribute('aria-selected')).toBe('true');

    fireEvent.change(screen.getByLabelText('일괄 대상'), {
      target: { value: 'selected' },
    });
    fireEvent.click(screen.getByRole('button', { name: '일괄 반영' }));
    const result = screen.getByTestId('rt-bulk-result');
    expect(Number(result.getAttribute('data-targeted'))).toBe(2);
    expect(Number(result.getAttribute('data-applied'))).toBe(able);
    expect(count('accepted')).toBe(before.byStatus.accepted + able);
    expect(count('pending')).toBe(before.byStatus.pending - able);
  });

  it('키보드로 지금 행을 옮긴다', () => {
    show();
    const box = screen.getByTestId('rt-scroll');
    fireEvent.keyDown(box, { key: 'ArrowDown' });
    fireEvent.keyDown(box, { key: 'ArrowDown' });
    expect(
      document.querySelector('[data-active]')!.getAttribute('data-row-id'),
    ).toBe(rows[1]!.id);
    fireEvent.keyDown(box, { key: ' ' });
    expect(rowElement(rows[1]!.id).getAttribute('aria-selected')).toBe('true');
  });

  it('계산이 실패하면 그 행에 표시가 남고 확정이 거부된다. 일괄의 건너뛴 까닭에 나온다. 다시 계산하면 풀려 확정된다', async () => {
    // 행마다 첫 계산만 실패하는 대역.
    render(
      <Screen
        rows={rows}
        categories={categories}
        columns={DEMO_COLUMNS}
        calculate={failingStandIn(1)}
      />,
    );
    const failedCount = () =>
      Number(summary().getAttribute('data-recalc-failed'));
    const target = rows.find(
      (row) =>
        row.status === 'pending' &&
        row.ai.candidates.length >= 2 &&
        row.ai.candidates[1]!.emission !== null,
    )!;
    const element = open(target);
    expect(failedCount()).toBe(0);

    await act(
      async () =>
        void fireEvent.click(within(element).getByLabelText('후보 2 고르기')),
    );
    expect(rowElement(target.id).dataset.status).toBe('edited');
    expect(rowElement(target.id).dataset.calcFailed).toBe('true');
    expect(
      within(rowElement(target.id)).getByTestId('rt-calc-failed').textContent,
    ).toContain('계산하지 못했다');
    expect(failedCount()).toBe(1);
    expect(summary().textContent).toContain('계산 실패 1');
    // 배출량 열은 「없음」(—)이 아니라 실패라고 적는다.
    expect(
      rowElement(target.id).querySelector('[data-column="emission"]')!
        .textContent,
    ).toContain('계산 실패');

    // 최종 확정 단추는 잠겨 있고, 일괄로 해도 건너뛴다. 까닭이 글자로 나온다.
    expect(
      within(rowElement(target.id)).getByRole<HTMLButtonElement>('button', {
        name: '최종 확정',
      }).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '일괄 최종 확정' }));
    const result = screen.getByTestId('rt-bulk-result');
    expect([
      result.getAttribute('data-targeted'),
      result.getAttribute('data-applied'),
      result.getAttribute('data-skipped'),
    ]).toEqual(['1', '0', '1']);
    expect(result.textContent).toContain('수정 1개: 계산하지 못했다');
    expect(rowElement(target.id).dataset.status).toBe('edited');

    // 다시 계산: 이번에는 대역이 답한다.
    await act(
      async () =>
        void fireEvent.click(
          within(rowElement(target.id)).getByRole('button', {
            name: '다시 계산',
          }),
        ),
    );
    expect(rowElement(target.id).dataset.calcFailed).toBeUndefined();
    expect(
      within(rowElement(target.id)).queryByTestId('rt-calc-failed'),
    ).toBeNull();
    expect(failedCount()).toBe(0);
    fireEvent.click(
      within(rowElement(target.id)).getByRole('button', { name: '최종 확정' }),
    );
    expect(rowElement(target.id).dataset.status).toBe('finalized');
    expect(finalTotal()).toBeCloseTo(
      before.finalTotal + target.ai.candidates[1]!.emission!,
      6,
    );
  });
});
