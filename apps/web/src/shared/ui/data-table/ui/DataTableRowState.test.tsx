// @vitest-environment jsdom
// 줄 열림 · 펼침 줄 data-* · 누름 줄 hover(밴드 DT3, sid:MARC-ISSUE-402): rowExpanded · expandedRowAttrs · rowHover.
// ① 셋 다 없으면 BASE(aff154be) 와 바이트까지 같은 DOM — 아래 BASE_DOM 은 편집 전 BASE 코드로 같은 자료를 그려 뽑은 innerHTML(두 번 뽑아 같음).
// ② 칸마다 단위 ③ 「2-2 꼴」(지어낸 자료 — 중대성평가 결과 2-2 손 표가 그리는 짜임을 이 셋으로 낼 수 있는가).
import * as React from 'react';

import { cleanup, fireEvent, render } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { useDataTable } from '../hooks/index.ts';
import type { DataTableColumnDef } from '../hooks/index.ts';
import { DataTable } from './DataTable.tsx';
import type { DataTableProps } from './DataTable.tsx';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** 지어낸 줄: 묶음(group) 안의 항목. */
interface Item {
  id: string;
  group: string;
  name: string;
  size: number;
}
const ITEMS: Item[] = [
  { id: 'i1', group: 'P', name: '가', size: 3 },
  { id: 'i2', group: 'P', name: '나', size: 1 },
  { id: 'i3', group: 'Q', name: '다', size: 2 },
];
const COLUMNS: DataTableColumnDef<Item>[] = [
  { id: 'name', accessorKey: 'name', header: '이름', enableSorting: false },
  { id: 'size', accessorKey: 'size', header: '크기', meta: { align: 'right' } },
  { id: 'note', header: '비고', enableSorting: false, cell: () => '-' },
];
function Sample({
  data = ITEMS,
  ...props
}: Omit<DataTableProps<Item>, 'table'> & { data?: Item[] }) {
  const table = useDataTable({
    data,
    columns: COLUMNS,
    getRowId: (row) => row.id,
  });
  return <DataTable table={table} aria-label="표" {...props} />;
}
/** ⓠ 펼침 줄 둘 + 데이터 줄 data-*. */
const EXPAND = {
  renderExpanded: (item: Item) => (item.id === 'i2' ? null : `펼침 ${item.id}`),
  rowAttrs: (item: Item) => ({
    'data-item': item.id,
    'data-big': item.size > 1 ? '' : undefined,
  }),
};
/** ⓡ 누름 줄(i2 는 누를 수 없음). */
const CLICK = {
  onClickRow: () => {},
  isRowClickable: (item: Item) => item.id !== 'i2',
  rowLabel: (item: Item) => `${item.name} 열기`,
};
/** ⓢ 묶음 + 줄 id + 줄 바탕 + 펼침. */
const GROUP = {
  groupOf: (item: Item) => item.group,
  rowId: (item: Item) => `r-${item.id}`,
  rowTone: (item: Item) => (item.id === 'i1' ? ('subtle' as const) : undefined),
  renderExpanded: (item: Item) => (item.id === 'i1' ? `펼침 ${item.id}` : null),
};

/** BASE(aff154be) 의 innerHTML — ⓟ 그냥 · ⓠ renderExpanded+rowAttrs · ⓡ 누름 줄 · ⓢ groupOf+rowId+rowTone+renderExpanded · ⓣ loading 첫 그림. */
const BASE_DOM = {
  plain:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">이름</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">크기<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">가</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">3</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">나</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">1</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">다</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr></tbody></table></div>',
  expand:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">이름</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">크기<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr data-item="i1" data-big="" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">가</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">3</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr data-expanded-row=""><td colspan="3" class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary py-3">펼침 i1</td></tr><tr data-item="i2" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">나</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">1</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr data-item="i3" data-big="" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">다</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr data-expanded-row=""><td colspan="3" class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary py-3">펼침 i3</td></tr></tbody></table></div>',
  click:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">이름</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">크기<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr tabindex="0" aria-label="가 열기" class="cursor-pointer hover:bg-background-secondary focus-visible:bg-background-secondary focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-secondary"><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">가</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">3</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">나</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">1</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr><tr tabindex="0" aria-label="다 열기" class="cursor-pointer hover:bg-background-secondary focus-visible:bg-background-secondary focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-secondary"><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">다</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr></tbody></table></div>',
  group:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">이름</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">크기<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody data-group="P"><tr id="r-i1" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left bg-background-secondary">가</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right bg-background-secondary">3</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left bg-background-secondary">-</td></tr><tr data-expanded-row=""><td colspan="3" class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary py-3">펼침 i1</td></tr><tr id="r-i2" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">나</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">1</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr></tbody><tbody data-group="Q"><tr id="r-i3" class=""><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">다</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-right">2</td><td class="h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary text-left">-</td></tr></tbody></table></div>',
  loading:
    '<div class="w-full overflow-x-auto"><table aria-label="표" class="w-full border-collapse" aria-busy="true"><thead><tr><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">이름</th><th scope="col" aria-sort="none" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-right"><button type="button" class="inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary justify-end">크기<svg aria-hidden="true" viewBox="0 0 16 16" fill="none" class="h-4 w-4 shrink-0"><path d="M7.99992 13.3334L10.6666 9.33337H5.33325L7.99992 13.3334Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M7.99992 2.66663L10.6666 6.66663H5.33325L7.99992 2.66663Z" fill="var(--marcspon-token-grey-400, #b0b7bf)" stroke="var(--marcspon-token-grey-400, #b0b7bf)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg></button></th><th scope="col" class="h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary text-left">비고</th></tr></thead><tbody><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr><tr aria-hidden="true" data-skeleton-row=""><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td><td class="h-14 border-0 border-b border-solid border-border-tertiary px-4"></td></tr></tbody></table></div>',
};

const bodyRows = () => [...document.querySelectorAll('tbody tr')];
const dataRows = () =>
  bodyRows().filter((row) => !row.hasAttribute('data-expanded-row'));
const expandedRows = () => [
  ...document.querySelectorAll('tr[data-expanded-row]'),
];
const words = (element: Element) =>
  element.className.split(/\s+/).filter(Boolean);
const attrNames = (element: Element) =>
  [...element.attributes].map((attribute) => attribute.name);
const FOCUS = [
  'cursor-pointer',
  'focus-visible:bg-background-secondary',
  'focus-visible:outline',
  'focus-visible:outline-2',
  'focus-visible:-outline-offset-2',
  'focus-visible:outline-border-secondary',
];
const HOVER = 'hover:bg-background-secondary';
const OPEN_I1 = (item: Item) =>
  item.id === 'i1' ? true
  : item.id === 'i2' ? false
  : undefined;

describe('① 셋 다 없으면 BASE 와 바이트까지 같은 DOM', () => {
  it('ⓟ 그냥 표', () => {
    expect(render(<Sample />).container.innerHTML).toBe(BASE_DOM.plain);
  });

  it('ⓠ renderExpanded + rowAttrs(펼침 줄 둘)', () => {
    expect(render(<Sample {...EXPAND} />).container.innerHTML).toBe(
      BASE_DOM.expand,
    );
  });

  it('ⓡ 누름 줄(onClickRow + isRowClickable 하나 거짓 + rowLabel)', () => {
    expect(render(<Sample {...CLICK} />).container.innerHTML).toBe(
      BASE_DOM.click,
    );
  });

  it('ⓢ groupOf + rowId + rowTone + renderExpanded', () => {
    expect(render(<Sample {...GROUP} />).container.innerHTML).toBe(
      BASE_DOM.group,
    );
  });

  it('ⓣ loading 첫 그림(막대 300ms 전)', () => {
    vi.useFakeTimers();
    expect(render(<Sample loading />).container.innerHTML).toBe(
      BASE_DOM.loading,
    );
  });

  it('rowExpanded 늘 undefined · expandedRowAttrs 빈 것 · rowHover="background" 여도 같다(ⓠ·ⓡ·ⓢ)', () => {
    const none = {
      rowExpanded: () => undefined,
      expandedRowAttrs: () => ({}),
      rowHover: 'background' as const,
    };
    expect(render(<Sample {...EXPAND} {...none} />).container.innerHTML).toBe(
      BASE_DOM.expand,
    );
    cleanup();
    expect(render(<Sample {...CLICK} {...none} />).container.innerHTML).toBe(
      BASE_DOM.click,
    );
    cleanup();
    expect(render(<Sample {...GROUP} {...none} />).container.innerHTML).toBe(
      BASE_DOM.group,
    );
  });
});

describe('② rowExpanded', () => {
  it('true 줄 "true" · false 줄 "false" · undefined 줄 속성 없음', () => {
    render(<Sample rowExpanded={OPEN_I1} />);
    expect(dataRows().map((row) => row.getAttribute('aria-expanded'))).toEqual([
      'true',
      'false',
      null,
    ]);
  });

  it('펼침 줄 tr 에는 0', () => {
    render(<Sample {...EXPAND} rowExpanded={() => true} />);
    expect(expandedRows()).toHaveLength(2);
    for (const row of expandedRows())
      expect(row.hasAttribute('aria-expanded')).toBe(false);
    expect(document.querySelectorAll('[aria-expanded]')).toHaveLength(3);
  });

  it('스켈레톤 줄·빈 줄 tr 에는 0', () => {
    vi.useFakeTimers();
    render(<Sample loading rowExpanded={() => true} />);
    expect(bodyRows()).toHaveLength(5);
    expect(document.querySelectorAll('[aria-expanded]')).toHaveLength(0);
    cleanup();
    render(<Sample data={[]} empty={<p>없음</p>} rowExpanded={() => true} />);
    expect(bodyRows()).toHaveLength(1);
    expect(document.querySelectorAll('[aria-expanded]')).toHaveLength(0);
  });

  it('누를 수 없는 줄에 true 를 주면 그대로 단다(Q2)', () => {
    render(<Sample {...CLICK} rowExpanded={() => true} />);
    const i2 = dataRows()[1]!;
    expect(i2.hasAttribute('tabindex')).toBe(false);
    expect(i2.getAttribute('aria-expanded')).toBe('true');
  });

  it('onClickRow·rowLabel 과 같이: tabIndex 0·aria-label 그대로', () => {
    render(<Sample {...CLICK} rowExpanded={OPEN_I1} />);
    const i1 = dataRows()[0]!;
    expect(i1.getAttribute('aria-expanded')).toBe('true');
    expect(i1.getAttribute('tabindex')).toBe('0');
    expect(i1.getAttribute('aria-label')).toBe('가 열기');
  });

  it('groupOf 묶음 안에서도', () => {
    render(<Sample {...GROUP} rowExpanded={OPEN_I1} />);
    const groups = [...document.querySelectorAll('tbody')];
    expect(groups.map((group) => group.dataset.group)).toEqual(['P', 'Q']);
    expect(
      [...groups[0]!.querySelectorAll('tr')].map((row) =>
        row.getAttribute('aria-expanded'),
      ),
    ).toEqual(['true', null, 'false']);
    expect(groups[1]!.querySelector('tr')!.hasAttribute('aria-expanded')).toBe(
      false,
    );
  });
});

describe('② expandedRowAttrs', () => {
  const attrs = (item: Item) => ({
    'data-row': 'summary',
    'data-no': item.id,
    'data-none': undefined,
  });

  it('펼침 줄 tr 에 준 data-* · data-expanded-row 는 "" 그대로 · undefined 값 키는 없음', () => {
    render(<Sample {...EXPAND} expandedRowAttrs={attrs} />);
    const [first, second] = expandedRows();
    expect(attrNames(first!)).toEqual([
      'data-row',
      'data-no',
      'data-expanded-row',
    ]);
    expect(first!.getAttribute('data-no')).toBe('i1');
    expect(second!.getAttribute('data-no')).toBe('i3');
    expect(first!.getAttribute('data-expanded-row')).toBe('');
    expect(first!.hasAttribute('data-none')).toBe(false);
  });

  it('쓰는 쪽이 data-expanded-row 를 줘도 "" 를 덮지 못한다', () => {
    render(
      <Sample
        {...EXPAND}
        expandedRowAttrs={() => ({ 'data-expanded-row': 'x' })}
      />,
    );
    for (const row of expandedRows())
      expect(row.getAttribute('data-expanded-row')).toBe('');
  });

  it('데이터 줄 tr 에는 안 붙는다', () => {
    render(<Sample {...EXPAND} expandedRowAttrs={attrs} />);
    for (const row of dataRows()) {
      expect(row.hasAttribute('data-row')).toBe(false);
      expect(row.hasAttribute('data-no')).toBe(false);
    }
    expect(dataRows().map((row) => row.getAttribute('data-item'))).toEqual([
      'i1',
      'i2',
      'i3',
    ]);
  });

  it('rowAttrs 만 주면 펼침 줄 속성은 data-expanded-row 하나', () => {
    render(<Sample {...EXPAND} />);
    for (const row of expandedRows())
      expect(attrNames(row)).toEqual(['data-expanded-row']);
  });

  it('renderExpanded 가 null 인 줄은 펼침 줄 0 이고 expandedRowAttrs 를 부르지 않는다', () => {
    const spy = vi.fn(attrs);
    render(<Sample {...EXPAND} expandedRowAttrs={spy} />);
    expect(expandedRows()).toHaveLength(2);
    expect(spy.mock.calls.map(([item]) => item.id).sort()).toEqual([
      'i1',
      'i3',
    ]);
  });

  it('groupOf: 펼침 줄이 attrs 와 함께 그 줄의 tbody 안', () => {
    render(<Sample {...GROUP} expandedRowAttrs={attrs} />);
    const groups = [...document.querySelectorAll('tbody')];
    const opened = groups[0]!.querySelector('tr[data-expanded-row]')!;
    expect(opened.getAttribute('data-no')).toBe('i1');
    expect(opened.previousElementSibling!.id).toBe('r-i1');
    expect(groups[1]!.querySelector('tr[data-expanded-row]')).toBeNull();
  });

  it('rowSpanOf 로 덮인 열이 있을 때 펼침 칸 colSpan 그대로', () => {
    render(
      <Sample
        {...EXPAND}
        expandedRowAttrs={attrs}
        rowSpanOf={(item, columnId) =>
          columnId !== 'name' ? undefined
          : item.id === 'i1' ? 2
          : item.id === 'i2' ? 0
          : undefined
        }
      />,
    );
    const [first, second] = expandedRows();
    expect((first!.firstElementChild as HTMLTableCellElement).colSpan).toBe(2);
    expect((second!.firstElementChild as HTMLTableCellElement).colSpan).toBe(3);
    expect(first!.getAttribute('data-no')).toBe('i1');
  });
});

describe('② rowHover', () => {
  it('"none" + 누름 줄: hover 바탕 없음, cursor·초점 다섯 그대로', () => {
    render(<Sample {...CLICK} rowHover="none" />);
    const i1 = words(dataRows()[0]!);
    expect(i1).not.toContain(HOVER);
    for (const word of FOCUS) expect(i1).toContain(word);
    expect(i1).toHaveLength(FOCUS.length);
  });

  it('기본·"background": hover 있음', () => {
    render(<Sample {...CLICK} />);
    expect(words(dataRows()[0]!)).toContain(HOVER);
    cleanup();
    render(<Sample {...CLICK} rowHover="background" />);
    expect(words(dataRows()[0]!)).toContain(HOVER);
  });

  it('"none" 이어도 누를 수 없는 줄 class ""', () => {
    render(<Sample {...CLICK} rowHover="none" />);
    expect(dataRows()[1]!.getAttribute('class')).toBe('');
  });

  it('"none" + rowTone subtle: td 바탕 그대로', () => {
    render(<Sample {...CLICK} {...GROUP} rowHover="none" />);
    const cells = [...dataRows()[0]!.querySelectorAll('td')];
    for (const cell of cells)
      expect(words(cell)).toContain('bg-background-secondary');
  });
});

describe('② 타입', () => {
  it('rowHover 는 닫힌 값 · expandedRowAttrs 는 data-* 만', () => {
    const props: Omit<DataTableProps<Item>, 'table'> = {
      // @ts-expect-error — 'background' | 'none' 만
      rowHover: 'flat',
    };
    type Attrs = ReturnType<
      NonNullable<DataTableProps<Item>['expandedRowAttrs']>
    >;
    const bad = (): Attrs => ({
      // @ts-expect-error — data-* 만
      'aria-expanded': 'true',
    });
    expect(props.rowHover).toBe('flat');
    expect(bad()).toEqual({ 'aria-expanded': 'true' });
  });
});

/** 「2-2 꼴」 지어낸 자료: 영향 경로 줄 넷 + 정하지 못함 하나. */
type Line =
  | { kind: 'line'; no: number; text: string; summary: string }
  | { kind: 'undecided'; no: number };
const LINES: Line[] = [
  { kind: 'line', no: 1, text: '줄 하나', summary: '요약 하나' },
  { kind: 'line', no: 2, text: '줄 둘', summary: '요약 둘' },
  { kind: 'line', no: 3, text: '줄 셋', summary: '요약 셋' },
  { kind: 'line', no: 4, text: '줄 넷', summary: '요약 넷' },
  { kind: 'undecided', no: 5 },
];
const HEADS = [
  '번호',
  '주제',
  '세부',
  '정의',
  '종류',
  '갈래',
  '동인',
  '사업',
  '재무',
];
const LINE_COLUMNS: DataTableColumnDef<Line>[] = HEADS.map((header, index) => ({
  id: `c${index}`,
  header,
  enableSorting: false,
  cell: ({ row }) =>
    index === 0 ? row.original.no
    : row.original.kind === 'line' ? row.original.text
    : '-',
}));
function PathwaySample() {
  const [open, setOpen] = React.useState<number | null>(null);
  const table = useDataTable({
    data: LINES,
    columns: LINE_COLUMNS,
    getRowId: (row) => String(row.no),
  });
  return (
    <DataTable
      table={table}
      aria-label="경로"
      onClickRow={(row) => setOpen(open === row.no ? null : row.no)}
      isRowClickable={(row) => row.kind === 'line'}
      rowExpanded={(row) => (row.kind === 'line' ? open === row.no : undefined)}
      renderExpanded={(row) =>
        row.kind === 'line' && open === row.no ? row.summary : null
      }
      rowAttrs={(row) => ({
        'data-row': row.kind === 'line' ? 'pathway' : 'undecided',
        'data-no': String(row.no),
      })}
      expandedRowAttrs={(row) => ({
        'data-row': 'pathway-summary',
        'data-no': String(row.no),
      })}
      rowHover="none"
    />
  );
}
/** 줄마다 [data-row, data-no, aria-expanded, tabindex] — 진짜 2-2 에 같은 요약을 돌려 대 봤다(보고 DT3 ③). */
const shape = () =>
  bodyRows().map((row) => [
    row.getAttribute('data-row'),
    row.getAttribute('data-no'),
    row.getAttribute('aria-expanded') ?? '-',
    row.getAttribute('tabindex') ?? '-',
  ]);
const CLOSED = [
  ['pathway', '1', 'false', '0'],
  ['pathway', '2', 'false', '0'],
  ['pathway', '3', 'false', '0'],
  ['pathway', '4', 'false', '0'],
  ['undecided', '5', '-', '-'],
];
const line = (no: number) =>
  document.querySelector(`tr[data-row="pathway"][data-no="${no}"]`)!;

describe('③ 「2-2 꼴」', () => {
  it('처음 · 누름 · Enter · Space 의 짜임', () => {
    render(<PathwaySample />);
    expect(shape()).toEqual(CLOSED);
    fireEvent.click(line(1));
    expect(shape()).toEqual([
      ['pathway', '1', 'true', '0'],
      ['pathway-summary', '1', '-', '-'],
      ...CLOSED.slice(1),
    ]);
    fireEvent.keyDown(line(1), { key: 'Enter' });
    expect(shape()).toEqual(CLOSED);
    fireEvent.keyDown(line(2), { key: ' ' });
    expect(shape()).toEqual([
      CLOSED[0],
      ['pathway', '2', 'true', '0'],
      ['pathway-summary', '2', '-', '-'],
      ...CLOSED.slice(2),
    ]);
  });

  it('요약 칸 하나 colSpan 9 · pathway 줄 hover 0·초점 여섯 · undecided 줄 class ""', () => {
    render(<PathwaySample />);
    fireEvent.click(line(1));
    const summary = document.querySelector('tr[data-row="pathway-summary"]')!;
    expect(summary.querySelectorAll('td')).toHaveLength(1);
    expect(summary.querySelector('td')!.colSpan).toBe(9);
    expect(summary.textContent).toBe('요약 하나');
    for (const no of [1, 2, 3, 4]) {
      const classes = words(line(no));
      expect(classes).not.toContain(HOVER);
      for (const word of FOCUS) expect(classes).toContain(word);
    }
    expect(
      document.querySelector('tr[data-row="undecided"]')!.getAttribute('class'),
    ).toBe('');
  });
});
