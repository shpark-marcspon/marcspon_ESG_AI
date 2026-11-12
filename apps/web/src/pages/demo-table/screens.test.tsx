// @vitest-environment jsdom
// 두 화면이 모양 없는 컴포넌트(RowStack)에 넘기는 것을 본다. 화면이 지켜야 하는 약속이 여기서 깨지면 빨개진다:
//   - renderRow 를 useCallback 으로 감쌌는가(한 행만 다시 그린다)      - onRenderRow 를 넘기는가
//   - rowCount 에 걸러 본 결과의 행 수를 넘기는가                       - 칸에 role="gridcell" 을 붙였는가
// 표 화면의 「한 행만 다시 그리기」는 review-table/ui/ReviewTable.test.tsx 에도 있다. 여기서는 같은 것을 카드 화면까지 돌린다.
import type { ComponentType } from 'react';

import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fakeLayout } from '../../shared/lib/testing/layout.ts';
import {
  ReviewTable,
  parseTableInput,
} from '../../widgets/review-table/index.ts';
import type { ReviewTableProps } from '../../widgets/review-table/index.ts';
import { ReviewCards } from './ReviewCards.tsx';
import { DEMO_COLUMNS } from './columns.tsx';
import { makeFakeInput } from './fakeRows.ts';
import { standInCalculate } from './standInCalc.ts';

const parsed = parseTableInput(makeFakeInput(300, 7));
if (!parsed.ok) throw new Error(parsed.errors.join('\n'));
const { rows, categories } = parsed.input;

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

describe.each(SCREENS)('화면이 행 창에 넘기는 것: %s', (_name, Screen) => {
  function show() {
    const onRenderRow = vi.fn<(rowId: string) => void>();
    render(
      <Screen
        rows={rows}
        categories={categories}
        columns={DEMO_COLUMNS}
        calculate={standInCalculate}
        onRenderRow={onRenderRow}
      />,
    );
    const domRows = () => [
      ...document.querySelectorAll<HTMLElement>('[data-row-id]'),
    ];
    const rendered = () => onRenderRow.mock.calls.map(([id]) => id);
    return { onRenderRow, domRows, rendered };
  }

  it('그린 행을 세어 알리고, 한 행을 펼치거나 바꾸면 그 행만 다시 그린다', () => {
    const { onRenderRow, domRows, rendered } = show();
    // 처음에는 크기를 재기 전에 몇 행을 더 그렸다가 걷어 낼 수 있다. 그래서 「DOM 의 행은 다 세어졌다」까지만 본다.
    expect(rendered().length).toBeGreaterThan(0);
    for (const element of domRows())
      expect(rendered()).toContain(element.dataset.rowId);
    const target = domRows().find(
      (element) => element.dataset.status === 'pending',
    )!;
    const id = target.dataset.rowId!;
    const element = () =>
      document.querySelector<HTMLElement>(`[data-row-id="${id}"]`)!;

    onRenderRow.mockClear();
    fireEvent.click(within(element()).getByLabelText('펼치기'));
    expect(rendered()).toEqual([id]);

    onRenderRow.mockClear();
    fireEvent.change(within(element()).getByLabelText('반려 사유'), {
      target: { value: '단위가 다르다' },
    });
    fireEvent.click(within(element()).getByRole('button', { name: '반려' }));
    expect(element().dataset.status).toBe('rejected');
    expect(rendered()).toEqual([id]);
  });

  it('행 창의 행 수 표시는 걸러 본 결과의 수다(전체 행 수가 아니다)', () => {
    show();
    // 행 수는 grid 가 말한다. 표는 머리글 줄까지 세고(+1), 머리글이 없는 카드는 자료 행만 센다.
    const grid = screen.getByRole('grid');
    const headerRows = Screen === ReviewTable ? 1 : 0;
    expect(grid.getAttribute('aria-rowcount')).toBe(String(300 + headerRows));
    fireEvent.change(screen.getByLabelText('상태로 걸러 보기'), {
      target: { value: 'accepted' },
    });
    const shown = Number(
      screen.getByTestId('rt-shown').getAttribute('data-shown'),
    );
    expect(shown).toBeLessThan(300);
    expect(grid.getAttribute('aria-rowcount')).toBe(String(shown + headerRows));
  });

  it('행(role=row)의 바로 아래에는 칸(role=gridcell)이 있다', () => {
    const { domRows } = show();
    for (const element of domRows()) {
      expect(element.getAttribute('role')).toBe('row');
      expect(
        element.querySelectorAll('[role="gridcell"]').length,
      ).toBeGreaterThan(0);
    }
  });
});

/** 공용 NativeSelect 꼴인가: 감싼 span 안에 appearance-none select 와 꺾쇠 svg(aria-hidden) 형제(sid:MARC-ENT-430). */
function isNativeSelect(select: HTMLElement) {
  const wrap = select.parentElement!;
  return (
    select.tagName === 'SELECT' &&
    select.className.split(/\s+/).includes('appearance-none') &&
    wrap.tagName === 'SPAN' &&
    wrap.querySelector(':scope > svg[aria-hidden="true"]') !== null
  );
}

describe.each(SCREENS)(
  '고르기 칸은 공용 NativeSelect(202): %s',
  (_name, Screen) => {
    it('도구 줄 셋(상태·카테고리·일괄 대상)과 펼친 행의 카테고리 수정', () => {
      render(
        <Screen
          rows={rows}
          categories={categories}
          columns={DEMO_COLUMNS}
          calculate={standInCalculate}
        />,
      );
      for (const name of [
        '상태로 걸러 보기',
        '카테고리로 걸러 보기',
        '일괄 대상',
      ])
        expect(isNativeSelect(screen.getByRole('combobox', { name }))).toBe(
          true,
        );
      fireEvent.click(screen.getAllByRole('button', { name: '펼치기' })[0]!);
      expect(
        isNativeSelect(screen.getByRole('combobox', { name: '카테고리 수정' })),
      ).toBe(true);
    });
  },
);
