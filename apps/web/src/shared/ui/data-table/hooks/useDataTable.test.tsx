// @vitest-environment jsdom
// 목록 표 headless: (1) 칸 안 컨트롤 판정 (2) 누를 수 있는 줄의 클릭·Enter·Space (3) describeTable 이 머리·몸·정렬 상태를 낸다.
// 모양 없이 그린다(클래스를 주지 않는다).
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  clickableRowProps,
  describeTable,
  isFromControl,
  useDataTable,
} from './useDataTable.ts';
import type { DataTableColumnDef } from './useDataTable.ts';

afterEach(cleanup);

describe('칸 안 컨트롤 판정', () => {
  function rowWith(inner: string) {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${inner}</td>`;
    document.body.append(row);
    return row;
  }

  it('button·a·input·[role=checkbox]·[role=switch]·label·[role=radio] 와 그 안에서 온 것은 컨트롤이다', () => {
    for (const inner of [
      '<button><span id="t">x</span></button>',
      '<a href="#"><span id="t">x</span></a>',
      '<input id="t" />',
      '<div role="checkbox"><span id="t"></span></div>',
      '<div role="switch" id="t"></div>',
      // label·radio: 밴드 TB1(sid:MARC-ENT-599 규칙 3) — label 의 글을 누르면 묶인 컨트롤이 바뀐다, 줄을 열지 않는다
      '<label><input type="checkbox" /><span id="t">고르기</span></label>',
      '<label id="t" for="far">고르기</label>',
      '<div role="radio" aria-checked="false"><span id="t">x</span></div>',
      '<div role="radiogroup"><span role="radio" id="t"></span></div>',
    ]) {
      const row = rowWith(inner);
      expect(isFromControl(row.querySelector('#t'), row), inner).toBe(true);
      row.remove();
    }
  });

  it('보통 글자, 줄 자신, 줄 밖의 컨트롤은 컨트롤이 아니다', () => {
    const row = rowWith('<span id="t">글자</span>');
    expect(isFromControl(row.querySelector('#t'), row)).toBe(false);
    expect(isFromControl(row, row)).toBe(false);
    expect(isFromControl(null, row)).toBe(false);
    // 줄이 버튼 안에 있을 때(바깥 컨트롤)는 줄 안의 것이 아니다
    const outer = document.createElement('button');
    const inner = rowWith('<span id="u">x</span>');
    outer.append(inner);
    expect(isFromControl(inner.querySelector('#u'), inner)).toBe(false);
  });
});

describe('누를 수 있는 줄', () => {
  function Row({ onClickRow }: { onClickRow?: (row: string) => void }) {
    return (
      <table>
        <tbody>
          <tr data-testid="row" {...clickableRowProps('행1', onClickRow)}>
            <td>
              글자 <button type="button">칸 안 버튼</button>
            </td>
          </tr>
        </tbody>
      </table>
    );
  }

  it('onClickRow 가 없으면 줄은 초점을 받지 않는다', () => {
    expect(clickableRowProps('x', undefined)).toBeUndefined();
    render(<Row />);
    expect(screen.getByTestId('row').hasAttribute('tabindex')).toBe(false);
  });

  it('클릭·Enter·Space 는 onClickRow 를 부르고, 다른 키는 부르지 않는다', () => {
    const onClickRow = vi.fn();
    render(<Row onClickRow={onClickRow} />);
    const row = screen.getByTestId('row');
    expect(row.getAttribute('tabindex')).toBe('0');
    fireEvent.click(row);
    fireEvent.keyDown(row, { key: 'Enter' });
    const space = fireEvent.keyDown(row, { key: ' ' });
    expect(space).toBe(false); // preventDefault: Space 가 쪽을 내리지 않는다
    fireEvent.keyDown(row, { key: 'a' });
    expect(onClickRow.mock.calls).toEqual([['행1'], ['행1'], ['행1']]);
  });

  it('칸 안 버튼의 클릭과 Enter 는 줄 클릭으로 번지지 않는다', () => {
    const onClickRow = vi.fn();
    render(<Row onClickRow={onClickRow} />);
    const button = screen.getByRole('button', { name: '칸 안 버튼' });
    fireEvent.click(button);
    fireEvent.keyDown(button, { key: 'Enter' });
    expect(onClickRow).not.toHaveBeenCalled();
  });
});

describe('describeTable', () => {
  interface Item {
    id: string;
    name: string;
    amount: number;
  }
  const data: Item[] = [
    { id: 'a', name: '나', amount: 2 },
    { id: 'b', name: '가', amount: 10 },
  ];
  const columns: DataTableColumnDef<Item>[] = [
    { id: 'name', accessorKey: 'name', header: '이름' },
    {
      id: 'amount',
      accessorKey: 'amount',
      header: '양',
      meta: { align: 'right' },
    },
    {
      id: 'action',
      header: '동작',
      enableSorting: false,
      cell: () => '버튼',
      meta: { align: 'center' },
    },
  ];

  it('머리·몸·칸 정렬·정렬 상태를 낸다. 정렬할 수 없는 열에는 aria-sort 가 없다', () => {
    const { result } = renderHook(() =>
      useDataTable({ data, columns, getRowId: (row) => row.id }),
    );
    let view = describeTable(result.current);
    expect(view.columnCount).toBe(3);
    expect(view.headers.map((header) => header.content)).toEqual([
      '이름',
      '양',
      '동작',
    ]);
    expect(view.headers.map((header) => header.align)).toEqual([
      'left',
      'right',
      'center',
    ]);
    expect(view.headers.map((header) => header.ariaSort)).toEqual([
      'none',
      'none',
      undefined,
    ]);
    expect(view.rows.map((row) => row.id)).toEqual(['a', 'b']);
    expect(view.rows[0]!.cells.map((cell) => cell.align)).toEqual([
      'left',
      'right',
      'center',
    ]);

    act(() => view.headers[0]!.toggleSort());
    view = describeTable(result.current);
    expect(view.headers[0]!.sort).toBe('asc');
    expect(view.headers[0]!.ariaSort).toBe('ascending');
    expect(view.rows.map((row) => row.original.name)).toEqual(['가', '나']);

    // 숫자 열도 오름차순부터 돈다(TanStack 기본은 숫자 열만 내림차순부터)
    act(() => view.headers[1]!.toggleSort());
    view = describeTable(result.current);
    expect(view.headers[1]!.sort).toBe('asc');
    expect(view.rows.map((row) => row.original.amount)).toEqual([2, 10]);
  });
});
