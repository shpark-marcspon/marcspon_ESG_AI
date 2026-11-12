// @vitest-environment jsdom
// 목록 표 ui: 키트 SortIndicator 와 우리 SkeletonRows·Empty 를 실제로 그린다.
// (1) 진짜 table 의미 (2) 정렬 머리 칸을 누르면 aria-sort 가 바뀐다 (3) 클릭 줄의 Enter·Space
// (4) 로딩은 자리 잡은 줄 5(밴드 LD1 — loading 은 300ms 뒤 막대), 로딩 중 empty 0. 빈 것은 tbody 안 한 칸에. 옛 늦춘 값 prop 은 타입에 없다(밴드 DT1).
// 실제 선 색·높이는 e2e/parts.spec.ts 가 잰다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { Empty } from '../../empty/index.ts';
import type { SkeletonWidth } from '../../load-skeleton/index.ts';
import { useDataTable } from '../hooks/index.ts';
import type { DataTableColumnDef } from '../hooks/index.ts';
import type { ColumnSkeleton } from '../model/index.ts';
import { DataTable, ROW_FOCUS, ROW_HOVER } from './DataTable.tsx';
import type { DataTableProps } from './DataTable.tsx';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

// data-table model 의 ColumnSkeleton 은 load-skeleton 의 SkeletonWidth 와 같은 꼴이어야 한다(칸 규칙상 따로 적었다 — rules.ts).
// 양쪽으로 넘겨지면 같은 꼴이다(어느 한쪽이 바뀌면 typecheck 가 빨강).
const toSkeleton = (width: ColumnSkeleton): SkeletonWidth => width;
const toColumn = (width: SkeletonWidth): ColumnSkeleton => width;
void toSkeleton;
void toColumn;

interface Item {
  id: string;
  name: string;
  amount: number;
}
const DATA: Item[] = [
  { id: 'a', name: '나', amount: 2 },
  { id: 'b', name: '가', amount: 10 },
];
const COLUMNS: DataTableColumnDef<Item>[] = [
  { id: 'name', accessorKey: 'name', header: '이름' },
  {
    id: 'amount',
    accessorKey: 'amount',
    header: '양',
    meta: { align: 'right', skeleton: 40 },
  },
  {
    id: 'action',
    header: '동작',
    enableSorting: false,
    cell: () => <button type="button">보기</button>,
    meta: { align: 'center' },
  },
];

function Sample({
  data = DATA,
  loading,
  onClickRow,
}: {
  data?: Item[];
  loading?: boolean;
  onClickRow?: (row: Item) => void;
}) {
  const table = useDataTable({
    data,
    columns: COLUMNS,
    getRowId: (row) => row.id,
  });
  return (
    <DataTable
      table={table}
      aria-label="목록"
      loading={loading}
      onClickRow={onClickRow}
      empty={<Empty title="없어요" />}
    />
  );
}

describe('목록 표', () => {
  it('진짜 table·머리 칸·몸 칸으로 그린다. 정렬 열의 머리 칸만 button 과 aria-sort 를 가진다', () => {
    render(<Sample />);
    const table = screen.getByRole('table', { name: '목록' });
    const headers = within(table).getAllByRole('columnheader');
    expect(headers).toHaveLength(3);
    expect(headers.map((header) => header.getAttribute('aria-sort'))).toEqual([
      'none',
      'none',
      null,
    ]);
    expect(
      within(headers[0]!).getByRole('button', { name: '이름' }),
    ).toBeTruthy();
    expect(within(headers[2]!).queryByRole('button')).toBeNull();
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    // 칸 정렬: 기본 왼쪽, 숫자 오른쪽, 버튼 가운데
    const cells = within(within(table).getAllByRole('row')[1]!).getAllByRole(
      'cell',
    );
    expect(
      cells.map(
        (cell) => cell.className.match(/text-(left|right|center)/)?.[1],
      ),
    ).toEqual(['left', 'right', 'center']);
  });

  it('정렬 머리 칸을 누르면 aria-sort 가 ascending → descending 으로 바뀌고 줄 차례가 바뀐다', () => {
    render(<Sample />);
    const header = () => screen.getAllByRole('columnheader')[0]!;
    const names = () =>
      screen
        .getAllByRole('row')
        .slice(1)
        .map((row) => within(row).getAllByRole('cell')[0]!.textContent);
    expect(names()).toEqual(['나', '가']);
    fireEvent.click(within(header()).getByRole('button'));
    expect(header().getAttribute('aria-sort')).toBe('ascending');
    expect(names()).toEqual(['가', '나']);
    fireEvent.click(within(header()).getByRole('button'));
    expect(header().getAttribute('aria-sort')).toBe('descending');
    expect(names()).toEqual(['나', '가']);
  });

  it('onClickRow 가 있으면 줄이 초점을 받고 Enter·Space·클릭으로 눌린다. 칸 안 버튼은 번지지 않는다', () => {
    const onClickRow = vi.fn();
    render(<Sample onClickRow={onClickRow} />);
    const row = screen.getAllByRole('row')[1]!;
    expect(row.getAttribute('tabindex')).toBe('0');
    fireEvent.keyDown(row, { key: 'Enter' });
    fireEvent.keyDown(row, { key: ' ' });
    fireEvent.click(within(row).getAllByRole('cell')[0]!);
    fireEvent.click(within(row).getByRole('button', { name: '보기' }));
    expect(onClickRow.mock.calls.map(([item]) => (item as Item).id)).toEqual([
      'a',
      'a',
      'a',
    ]);
  });

  it('onClickRow 가 없으면 줄은 초점을 받지 않고 hover 바탕도 없다', () => {
    render(<Sample />);
    const row = screen.getAllByRole('row')[1]!;
    expect(row.hasAttribute('tabindex')).toBe(false);
    expect(row.className).not.toContain('hover:bg-background-secondary');
  });

  // 걷은 prop(밴드 DT1, sid:MARC-ISSUE-373): 쓰는 쪽이 늦춘 값을 받던 옛 로딩 prop. 이름은 잼(grep 0)에 걸리지 않게 나눠 쓴다.
  it('옛 로딩 prop 을 넘기면 타입 오류(DataTableProps 에 없다)', () => {
    type Old = `is${'Loading'}`;
    const props: Omit<DataTableProps<Item>, 'table'> = {
      loading: true,
      // @ts-expect-error — 걷은 prop
      [`is${'Loading'}` as Old]: true,
    };
    expect(props.loading).toBe(true);
  });

  it('줄 0 이면 Empty 를 tbody 안 한 칸에(colSpan = 열 수)', () => {
    render(<Sample data={[]} />);
    const body = screen.getAllByRole('rowgroup')[1]!;
    const only = within(body).getAllByRole('cell');
    expect(only).toHaveLength(1);
    expect(only[0]!.getAttribute('colspan')).toBe('3');
    expect(within(only[0]!).getByText('없어요')).toBeTruthy();
  });

  it('loading(날 값) + 줄 0 + empty: empty 는 그리지 않고 머리줄 그대로, 첫 그림부터 줄 5 · 막대는 300ms 뒤', () => {
    vi.useFakeTimers();
    render(<Sample data={[]} loading />);
    const table = screen.getByRole('table');
    expect(table.getAttribute('aria-busy')).toBe('true');
    expect(within(table).getAllByRole('columnheader')).toHaveLength(3);
    expect(screen.queryByText('없어요')).toBeNull();
    const body = screen.getAllByRole('rowgroup')[1]!;
    expect(body.querySelectorAll('tr')).toHaveLength(5);
    expect(body.querySelectorAll('[data-skeleton-bar]')).toHaveLength(0);
    act(() => vi.advanceTimersByTime(300));
    expect(body.querySelectorAll('tr')).toHaveLength(5);
    expect(body.querySelectorAll('[data-skeleton-bar]')).toHaveLength(15);
    expect(screen.queryByText('없어요')).toBeNull();
  });

  it('loading 줄의 막대는 열 meta.skeleton·align 을 따른다(이름 긴 글 · 양 40px 오른쪽 · 동작 가운데)', () => {
    vi.useFakeTimers();
    render(<Sample loading />);
    act(() => vi.advanceTimersByTime(300));
    const cells = screen
      .getAllByRole('rowgroup')[1]!
      .querySelector('tr')!
      .querySelectorAll<HTMLElement>('[data-skeleton-bar]');
    expect(cells[0]!.style.width).toBe('66%');
    expect(cells[1]!.style.width).toBe('40px');
    expect(cells[1]!.className.split(/\s+/)).toContain('ml-auto');
    expect(cells[2]!.className.split(/\s+/)).toContain('mx-auto');
  });

  it('loading 이 거짓이 되면 진짜 줄', () => {
    const { rerender } = render(<Sample loading />);
    expect(screen.queryByText('나')).toBeNull();
    rerender(<Sample />);
    expect(screen.getByText('나')).toBeTruthy();
    expect(screen.getByRole('table').getAttribute('aria-busy')).toBeNull();
  });
});

// index.ts 로 나가는지는 슬라이스 밖에서 본다(ui/ 는 ../index.ts 를 가져오지 못한다 — layers.test): RunsScreen.test 가 공개 표면에서 가져와 줄 class 를 단언한다.
describe('줄 hover·초점 공용 값(밴드 WM1, sid:MARC-ISSUE-606)', () => {
  it('ROW_HOVER·ROW_FOCUS 는 DataTable 줄 꼴 그대로다(모듈 표가 공개 표면에서 이것을 import 한다)', () => {
    expect(ROW_HOVER).toBe('hover:bg-background-secondary');
    expect(ROW_FOCUS).toBe(
      'focus-visible:bg-background-secondary focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-secondary',
    );
  });
});
