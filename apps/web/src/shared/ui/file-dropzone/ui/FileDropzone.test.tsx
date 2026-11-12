// @vitest-environment jsdom
// 파일 드롭존 ui + 훅: 키트 Spinner·아이콘과 우리 IconButton 을 실제로 그린다.
// (1) 칸은 button 역할이고 Enter·Space·클릭이 숨긴 입력을 누른다 (2) 고른 파일을 판정해 받은 것은 목록에, 거부된 것은 사유와 함께
// (3) 지우기 (4) 올리는 중에는 열리지 않고 도는 표시가 보인다 (5) readOnly·hideDrop (6) 줄 상태 글 (7) 끌어다 놓기.
// 실제 파일 창(filechooser)은 e2e/parts.spec.ts 가 연다.
import { useState } from 'react';

import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { PARTS_TEXT } from '../../text.ts';
import type { DraggableInputItem } from '../hooks/index.ts';
import { FileDropzone } from './FileDropzone.tsx';
import type { FileDropzoneProps } from './FileDropzone.tsx';

afterEach(cleanup);

const MB = 1024 * 1024;
function makeFile(name: string, type = '', size = 10) {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

function Harness({
  initial = [],
  ...props
}: Partial<FileDropzoneProps> & { initial?: DraggableInputItem[] }) {
  const [items, setItems] = useState<DraggableInputItem[]>(initial);
  return (
    <FileDropzone
      guide="끌어다 놓거나 눌러서 고르세요"
      formats="xlsx · 1MB 이하"
      itemList={items}
      onChangeItemList={setItems}
      accept={['.xlsx']}
      maxMb={1}
      maxCount={3}
      today={() => '2026-10-15'}
      {...props}
    />
  );
}

const zone = () =>
  screen.getByRole('button', { name: /끌어다 놓거나 눌러서 고르세요/ });
const input = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement;

describe('파일 드롭존', () => {
  it('칸은 Tab 으로 닿는 button 이고, Enter·Space·클릭이 숨긴 입력을 누른다. 입력은 accept 를 받는다', () => {
    const { container } = render(<Harness />);
    const field = input(container);
    const click = vi.spyOn(field, 'click');
    expect(zone().getAttribute('tabindex')).toBe('0');
    fireEvent.keyDown(zone(), { key: 'Enter' });
    fireEvent.keyDown(zone(), { key: ' ' });
    fireEvent.click(zone());
    fireEvent.keyDown(zone(), { key: 'a' });
    expect(click).toHaveBeenCalledTimes(3);
    expect(field.getAttribute('accept')).toBe('.xlsx');
    expect(field.hidden).toBe(true);
    expect(field.multiple).toBe(true);
    // 숨긴 입력은 칸 밖에 있다(안에 두면 input.click() 의 클릭이 칸으로 올라온다)
    expect(zone().contains(field)).toBe(false);
  });

  it('고른 파일을 걸러서 받는다: 받은 것은 목록(이름·날짜)에, 거부된 것은 사유와 함께 보인다. onError 는 거부 묶음으로 한 번', () => {
    const onError = vi.fn();
    const { container } = render(<Harness onError={onError} />);
    fireEvent.change(input(container), {
      target: {
        files: [
          makeFile('a.xlsx'),
          makeFile('b.xls'),
          makeFile('A.xlsx'),
          makeFile('큰.xlsx', '', 2 * MB),
        ],
      },
    });
    const items = screen.getAllByRole('listitem');
    const texts = items.map((item) => item.textContent);
    expect(texts).toContain('b.xls · XLSX 파일만 올려 주세요');
    expect(texts).toContain('A.xlsx · 같은 이름의 파일이 이미 있어요');
    expect(texts).toContain('큰.xlsx · 1MB 이하 파일을 올려 주세요');
    expect(screen.getByText('a.xlsx')).toBeTruthy();
    expect(screen.getByText('2026-10-15')).toBeTruthy();
    expect(onError).toHaveBeenCalledOnce();
    expect(
      onError.mock.calls[0]![0].map(
        (entry: { reason: string }) => entry.reason,
      ),
    ).toEqual(['type', 'duplicate', 'size']);
  });

  it('거부 사유를 알리는 자리(role=status)는 처음부터 비어 있는 채로 있고, 고른 뒤 그 안의 줄만 바뀐다', () => {
    const { container } = render(<Harness />);
    const region = container.querySelector(
      '[role="status"][aria-live="polite"]',
    )!;
    expect(region).not.toBeNull();
    expect(region.textContent).toBe('');
    expect(zone().contains(region)).toBe(false);
    fireEvent.change(input(container), {
      target: { files: [makeFile('b.xls')] },
    });
    expect(container.querySelector('[role="status"][aria-live="polite"]')).toBe(
      region,
    );
    expect(
      within(region as HTMLElement).getByRole('listitem').textContent,
    ).toBe('b.xls · XLSX 파일만 올려 주세요');
  });

  it('거부 사유 문구는 일부만 바꿀 수 있고, 빠진 것은 기본 문구다', () => {
    const { container } = render(
      <Harness text={{ rejectReason: { type: '형식이 달라요' } }} />,
    );
    fireEvent.change(input(container), {
      target: { files: [makeFile('b.xls'), makeFile('큰.xlsx', '', 2 * MB)] },
    });
    expect(screen.getByText('b.xls · 형식이 달라요')).toBeTruthy();
    expect(
      screen.getByText('큰.xlsx · 1MB 이하 파일을 올려 주세요'),
    ).toBeTruthy();
  });

  it('개수 상한: 남은 자리만큼 받고 나머지는 count 로 거부한다', () => {
    const { container } = render(
      <Harness
        initial={[{ id: 'x', name: '있는.xlsx', date: '2026-10-01' }]}
      />,
    );
    fireEvent.change(input(container), {
      target: {
        files: [makeFile('1.xlsx'), makeFile('2.xlsx'), makeFile('3.xlsx')],
      },
    });
    expect(screen.getByText('1.xlsx')).toBeTruthy();
    expect(screen.getByText('2.xlsx')).toBeTruthy();
    expect(screen.getByText('3.xlsx · 3개까지 올릴 수 있어요')).toBeTruthy();
  });

  it('✕ 로 지운다. 버튼 이름은 「<파일 이름> 지우기」', () => {
    render(
      <Harness
        initial={[
          { id: 'a', name: '가.xlsx', date: '2026-10-01' },
          { id: 'b', name: '나.xlsx', date: '2026-10-02' },
        ]}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '가.xlsx 지우기' }));
    expect(screen.queryByText('가.xlsx')).toBeNull();
    expect(screen.getByText('나.xlsx')).toBeTruthy();
  });

  it('올리는 중이면 칸이 열리지 않고 초점도 받지 않으며 도는 표시(업로드 중)가 보인다', () => {
    const { container } = render(<Harness isUploading />);
    const click = vi.spyOn(input(container), 'click');
    expect(zone().getAttribute('aria-disabled')).toBe('true');
    expect(zone().getAttribute('tabindex')).toBe('-1');
    fireEvent.keyDown(zone(), { key: 'Enter' });
    fireEvent.click(zone());
    expect(click).not.toHaveBeenCalled();
    expect(
      within(zone()).getByRole('status', { name: '업로드 중' }),
    ).toBeTruthy();
  });

  it('readOnly 면 칸과 ✕ 가 없고 목록만 보인다', () => {
    render(
      <Harness
        readOnly
        initial={[{ id: 'a', name: '가.xlsx', date: '2026-10-01' }]}
      />,
    );
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText('가.xlsx')).toBeTruthy();
  });

  it('hideDrop(sid:MARC-ISSUE-439): 칸과 숨긴 입력은 없고 파일 줄과 ✕ 는 남는다. ✕ 는 그 줄을 뺀 목록을 넘긴다', () => {
    const onChangeItemList = vi.fn();
    const items: DraggableInputItem[] = [
      { id: 'a', name: '가.xlsx', date: '2026-10-01' },
      { id: 'b', name: '나.xlsx', date: '2026-10-02' },
    ];
    const { container } = render(
      <FileDropzone
        guide="끌어다 놓거나 눌러서 고르세요"
        itemList={items}
        onChangeItemList={onChangeItemList}
        hideDrop
      />,
    );
    expect(screen.queryByRole('button', { name: /끌어다 놓거나/ })).toBeNull();
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(
      container.querySelector('[role="status"][aria-live="polite"]'),
    ).not.toBeNull();
    expect(screen.getByText('가.xlsx')).toBeTruthy();
    expect(screen.getByText('나.xlsx')).toBeTruthy();
    // 칸이 없으니 목록 위 간격도 없다(readOnly 와 같다)
    expect(container.querySelector('ul')!.getAttribute('class')).not.toMatch(
      /\bmt-3\b/,
    );
    fireEvent.click(screen.getByRole('button', { name: '가.xlsx 지우기' }));
    expect(onChangeItemList).toHaveBeenCalledOnce();
    expect(onChangeItemList).toHaveBeenCalledWith([items[1]]);
  });

  it('hideDrop 과 readOnly 가 같이 오면 readOnly 가 이긴다: ✕ 도 없다', () => {
    render(
      <Harness
        hideDrop
        readOnly
        initial={[{ id: 'a', name: '가.xlsx', date: '2026-10-01' }]}
      />,
    );
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText('가.xlsx')).toBeTruthy();
  });

  it('hideDrop 을 안 주면(또는 false) 그린 DOM 이 지금과 같다: 칸·입력이 있고 목록 위 간격 mt-3', () => {
    const initial = [{ id: 'a', name: '가.xlsx', date: '2026-10-01' }];
    const { container: plain } = render(<Harness initial={initial} />);
    const { container: off } = render(
      <Harness initial={initial} hideDrop={false} />,
    );
    expect(off.innerHTML).toBe(plain.innerHTML);
    expect(plain.querySelector('[role="button"]')).not.toBeNull();
    expect(plain.querySelector('input[type="file"]')).not.toBeNull();
    expect(plain.querySelectorAll('ul')[0]!.getAttribute('class')).toMatch(
      /\bmt-3\b/,
    );
  });

  it('줄의 상태 글: 업로드 중·업로드 실패. 문구는 text 로 바꿀 수 있다', () => {
    render(
      <Harness
        text={{ uploadFailed: '실패했어요' }}
        initial={[
          { id: 'a', name: '가.xlsx', date: '2026-10-01', status: 'uploading' },
          { id: 'b', name: '나.xlsx', date: '2026-10-02', status: 'failed' },
        ]}
      />,
    );
    const [first, second] = screen.getAllByRole('listitem');
    expect(within(first!).getByText('업로드 중')).toBeTruthy();
    expect(within(second!).getByText('실패했어요')).toBeTruthy();
  });

  it('끌어다 놓기: 놓은 파일도 같은 판정을 거친다', () => {
    render(<Harness />);
    fireEvent.dragEnter(zone());
    expect(zone().getAttribute('data-dragging')).toBe('true');
    fireEvent.drop(zone(), {
      dataTransfer: { files: [makeFile('놓은.xlsx'), makeFile('놓은.pdf')] },
    });
    expect(zone().hasAttribute('data-dragging')).toBe(false);
    expect(screen.getByText('놓은.xlsx')).toBeTruthy();
    expect(screen.getByText('놓은.pdf · XLSX 파일만 올려 주세요')).toBeTruthy();
  });

  it('꼴(344 SB6·SC8): 위 화살표 24 는 tertiary, 큰 글 secondary · 작은 글 tertiary, 지우기 단추는 28 상자에 × tertiary', () => {
    render(
      <Harness initial={[{ id: 'a', name: '가.xlsx', date: '2026-10-01' }]} />,
    );
    const classesOf = (element: Element) =>
      (element.getAttribute('class') ?? '').split(/\s+/);
    const icon = zone().querySelector('svg')!;
    expect(classesOf(icon)).toContain('text-text-tertiary');
    expect(classesOf(icon)).toContain('size-6');
    // AV2 디자인 대조 N2: 위 화살표–큰 글 사이 4(gap-1 — 시안)
    expect(classesOf(zone())).toContain('gap-1');
    expect(classesOf(zone())).not.toContain('gap-2');
    expect(
      classesOf(screen.getByText('끌어다 놓거나 눌러서 고르세요')),
    ).toContain('text-text-secondary');
    expect(classesOf(screen.getByText('xlsx · 1MB 이하'))).toContain(
      'text-text-tertiary',
    );
    const remove = screen.getByRole('button', {
      name: `가.xlsx ${PARTS_TEXT.removeFile}`,
    });
    expect(classesOf(remove)).toContain('size-7');
    expect(classesOf(remove)).toContain('text-text-tertiary');
    expect(classesOf(remove)).not.toContain('size-5');
  });

  it('올리는 중에는 위 화살표 자리에 도는 표시가 돈다', () => {
    render(<Harness isUploading />);
    const spinner = within(zone()).getByRole('status', { name: '업로드 중' });
    expect(spinner.getAttribute('class')).toContain('animate-spin');
    expect(zone().querySelectorAll('svg')).toHaveLength(1);
  });

  it('오류 aria(밴드 FZ1): invalid 면 칸에 aria-invalid="true", describedBy 는 aria-describedby 로. 안 주면 둘 다 속성이 없다', () => {
    const { unmount } = render(<Harness />);
    expect(zone().hasAttribute('aria-invalid')).toBe(false);
    expect(zone().hasAttribute('aria-describedby')).toBe(false);
    unmount();

    render(<Harness invalid={false} />);
    expect(zone().hasAttribute('aria-invalid')).toBe(false);
    cleanup();

    render(
      <>
        <Harness invalid describedBy="x" />
        <p id="x">파일을 하나 올려 주세요</p>
      </>,
    );
    expect(zone().getAttribute('aria-invalid')).toBe('true');
    expect(zone().getAttribute('aria-describedby')).toBe('x');
    expect(
      screen.getByRole('button', { description: '파일을 하나 올려 주세요' }),
    ).toBe(zone());
  });

  it('오류 aria(밴드 FZ1): readOnly 면 칸이 없어 aria-invalid 도 붙을 자리가 없다', () => {
    const { container } = render(<Harness readOnly invalid describedBy="x" />);
    expect(screen.queryByRole('button', { name: /끌어다 놓거나/ })).toBeNull();
    expect(container.querySelector('[aria-invalid]')).toBeNull();
    expect(container.querySelector('[aria-describedby]')).toBeNull();
  });
});
