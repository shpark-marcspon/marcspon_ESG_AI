// @vitest-environment jsdom
// 묶음 표(밴드 TRW0b, 발주서 §3-7, 결정 sid:MARC-ENT-404·393): 묶음 줄 = rows 수(같은 파일 두 묶음 = 줄 둘) · 펼치면 파트 줄 = 파트 수 ·
// 회차 n 글 · 앞 회차 있으면 펼침 단추(aria-expanded·앞 회차 줄 = 상태·시각), 없으면 0 · [결과 보기]/[진행 보기] 갈림 ·
// 다시 단추(서버 오류·일부 쪽만, 파트 하나면 [다시 실행], 막은 파트 0) · 콜백 인자 · 운영 관리자 머리 줄(v136 — 숨김 없음).
import type { ReactElement } from 'react';

import {
  ChevronDownIcon,
  ChevronRightIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../config/text.ts';
import { SAMPLE_FILE } from '../model/testing.ts';
import { BatchTable } from './BatchTable.tsx';
import type { BatchRow, BatchTableProps } from './BatchTable.tsx';

afterEach(cleanup);

const words = TR_TEXT.list;

const ROWS: BatchRow[] = [
  {
    batchId: 'b1',
    fileName: SAMPLE_FILE,
    uploaded: '2026-10-19 11:40',
    style: 'B',
    uploader: '담당자 A',
    lastStarted: '2026-10-19 14:10',
    parts: [
      {
        part: 'ceo',
        range: '1~3',
        round: 1,
        started: '11:48',
        state: 'done',
        earlier: [],
      },
      {
        part: 'story',
        range: '4~41',
        round: 2,
        started: '14:10',
        state: 'running',
        pages: { done: 20, total: 38 },
        earlier: [{ round: 1, state: 'failed_partial', at: '11:48' }],
      },
      {
        part: 'general',
        range: '42~64',
        round: 1,
        started: '11:53',
        state: 'done',
        earlier: [],
      },
    ],
  },
  {
    // 같은 파일을 다시 번역 = 새 줄(404)
    batchId: 'b2',
    fileName: SAMPLE_FILE,
    uploaded: '2026-10-19 11:40',
    style: 'A',
    uploader: '담당자 A',
    lastStarted: '2026-10-20 09:30',
    parts: [
      {
        part: 'general',
        range: '42~64',
        round: 1,
        started: '09:30',
        state: 'done',
        earlier: [],
      },
    ],
  },
  {
    batchId: 'b3',
    fileName: 'annual_ko_extract.docx',
    uploaded: '2026-10-19 12:00',
    style: 'A',
    uploader: '담당자 B',
    lastStarted: '2026-10-19 12:05',
    parts: [
      {
        part: 'story',
        range: '4~41',
        round: 1,
        started: '12:05',
        state: 'done',
        earlier: [],
      },
      {
        part: 'general',
        range: '42~140',
        round: 1,
        started: '12:05',
        state: 'failed',
        reason: 'too_large',
        earlier: [],
      },
    ],
  },
  {
    batchId: 'b4',
    fileName: 'appendix_ko_extract.docx',
    uploaded: '2026-10-18 09:55',
    style: 'A',
    uploader: '담당자 C',
    lastStarted: '2026-10-18 10:02',
    parts: [
      {
        part: 'general',
        range: '1~18',
        round: 1,
        started: '10:02',
        state: 'failed',
        earlier: [],
      },
    ],
  },
];

function draw(props: Partial<BatchTableProps> = {}) {
  const calls = {
    onOpenBatch: vi.fn(),
    onOpenPart: vi.fn(),
    onRetryPart: vi.fn(),
  };
  render(<BatchTable rows={ROWS} {...calls} {...props} />);
  return calls;
}
const batch = (id: string) =>
  within(document.querySelector<HTMLElement>(`[data-batch="${id}"]`)!);
const batchRows = () => document.querySelectorAll('[data-row="batch"]');
const partRows = (id: string) =>
  document.querySelectorAll(`[data-batch="${id}"] [data-row="part"]`);
const batchRow = (id: string) =>
  document.querySelector<HTMLElement>(
    `[data-batch="${id}"] [data-row="batch"]`,
  )!;
const partRow = (id: string, part: string) =>
  document.querySelector<HTMLElement>(
    `[data-batch="${id}"] [data-row="part"][data-part="${part}"]`,
  )!;

describe('BatchTable', () => {
  it('묶음 줄 = rows 수 — 같은 파일 두 묶음은 줄 둘', () => {
    draw();
    expect(batchRows()).toHaveLength(4);
    expect(screen.getAllByText(SAMPLE_FILE)).toHaveLength(2);
  });

  it('파트 여럿: 「파트 3」·묶음 셈, 파일 이름 단추로 펼치면 파트 줄 = 파트 수', () => {
    draw();
    const row = batch('b1');
    expect(row.getByText(words.partCount(3))).toBeTruthy();
    expect(row.getByTestId('batch-summary').textContent).toBe(
      '완료 2진행 중 1',
    );
    expect(partRows('b1')).toHaveLength(0);
    // [TRP2 TE3] 펼침은 파일명 앞 꺾쇠 단추(파일명은 맨 글) — 「파트 펼치기」 → 누르면 「파트 접기」.
    expect(row.queryByRole('button', { name: SAMPLE_FILE })).toBeNull();
    const toggle = row.getByRole('button', { name: words.expandParts });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(toggle.getAttribute('aria-label')).toBe(words.collapseParts);
    expect(partRows('b1')).toHaveLength(3);
    expect(
      document.getElementById(toggle.getAttribute('aria-controls')!),
    ).not.toBeNull();
  });

  // 밴드 TRW7 ③a sid:MARC-ISSUE-451 → 밴드 TRW12(sid:MARC-ENT-599 규칙 2, 감독 허락 11-08): hover 바탕·커서는 누를 수 있는 줄에만.
  // 누를 수 있는 줄 = 묶음 줄 b1(여럿)·b2(하나, 결과 보기) · 파트 줄 ceo, 누를 수 없는 줄 = 묶음 줄 b4(막힌 하나) · 파트 줄 b3 general(막음) · 앞 회차 줄.
  it('줄 hover: 누를 수 있는 줄만 hover·cursor(파트 줄은 칸 tertiary), 누를 수 없는 줄은 둘 다 없음', () => {
    draw({ initialOpen: ['b1', 'b3'] });
    fireEvent.click(
      batch('b1').getByRole('button', { name: TR_TEXT.cells.round(2) }),
    );
    const classesOf = (row: Element) => row.className.split(/\s+/);
    for (const id of ['b1', 'b2']) {
      const row = batchRow(id);
      expect(classesOf(row), id).toContain('hover:bg-background-secondary');
      expect(classesOf(row), id).toContain('cursor-pointer');
    }
    const blocked = batchRow('b4');
    expect(classesOf(blocked)).not.toContain('hover:bg-background-secondary');
    expect(classesOf(blocked)).not.toContain('cursor-pointer');
    const earlier = document.querySelectorAll('[data-earlier]');
    expect(earlier).toHaveLength(1);
    expect(classesOf(earlier[0]!)).not.toContain(
      'hover:bg-background-secondary',
    );
    expect(classesOf(earlier[0]!)).not.toContain('cursor-pointer');
    // 파트 줄은 칸 바탕이 secondary 라 칸이 tertiary 로(밴드 TRW7 ③b — 디자인 74 답). 줄 하나에 칸 전부.
    const open = partRow('b1', 'ceo');
    expect(classesOf(open)).toContain('group/part');
    expect(classesOf(open)).toContain('cursor-pointer');
    const cells = open.querySelectorAll('td');
    expect(cells.length).toBeGreaterThan(0);
    for (const cell of cells)
      expect(cell.className).toContain(
        'group-hover/part:bg-background-tertiary',
      );
    const shut = partRow('b3', 'general');
    expect(classesOf(shut)).not.toContain('cursor-pointer');
    for (const cell of shut.querySelectorAll('td'))
      expect(cell.className).not.toContain(
        'group-hover/part:bg-background-tertiary',
      );
  });

  it('회차: 앞 회차가 있으면 「회차 2」 펼침 단추 → 앞 회차 줄(상태·시각만), 없으면 펼침 단추 0', () => {
    draw({ initialOpen: ['b1'] });
    const row = batch('b1');
    const rounds = row.getByRole('button', { name: TR_TEXT.cells.round(2) });
    expect(rounds.getAttribute('aria-expanded')).toBe('false');
    expect(document.querySelectorAll('[data-earlier]')).toHaveLength(0);
    fireEvent.click(rounds);
    expect(rounds.getAttribute('aria-expanded')).toBe('true');
    const earlier = document.querySelectorAll('[data-earlier]');
    expect(earlier).toHaveLength(1);
    expect(earlier[0]!.textContent).toBe('회차 111:48실패 · 일부 페이지');
    expect(earlier[0]!.querySelectorAll('button')).toHaveLength(0);
    expect(document.getElementById(rounds.getAttribute('aria-controls')!)).toBe(
      earlier[0],
    );
    // CEO·일반은 회차 1 뿐 — 펼침 단추 0
    expect(row.queryAllByRole('button', { name: /^회차/ })).toHaveLength(1);
    fireEvent.click(rounds);
    expect(document.querySelectorAll('[data-earlier]')).toHaveLength(0);
  });

  it('다음 할 일: 진행 중 → [진행 보기], 완료 → [결과 보기], 콜백 인자(묶음 id·파트)', () => {
    const { onOpenBatch, onOpenPart } = draw({ initialOpen: ['b1'] });
    const row = batch('b1');
    const parts = partRows('b1');
    expect(
      within(parts[0] as HTMLElement).getByRole('button').textContent,
    ).toBe(words.viewResult);
    fireEvent.click(
      within(parts[1] as HTMLElement).getByRole('button', {
        name: words.viewProgress,
      }),
    );
    expect(onOpenPart).toHaveBeenCalledWith('b1', 'story');
    // 묶음 줄: 진행 중이 있으면 [진행 보기]
    const batchCell = document.querySelector(
      '[data-batch="b1"] [data-row="batch"]',
    ) as HTMLElement;
    fireEvent.click(
      within(batchCell).getByRole('button', { name: words.viewProgress }),
    );
    expect(onOpenBatch).toHaveBeenCalledWith('b1');
    expect(row.getAllByText('진행 중 · 번역 20/38페이지')).toHaveLength(1);
    // 끝난 묶음은 [결과 보기]
    fireEvent.click(
      batch('b3').getByRole('button', { name: words.viewResult }),
    );
    expect(onOpenBatch).toHaveBeenLastCalledWith('b3');
  });

  it('파트 하나: 펼치지 않고 그 파트를 묶음 줄에 바로, 실패면 [다시 실행] → onRetryPart(묶음 id, 파트)', () => {
    const { onRetryPart } = draw();
    const row = batch('b4');
    expect(
      row.queryByRole('button', { name: 'appendix_ko_extract.docx' }),
    ).toBeNull();
    expect(row.getByText(TR_TEXT.cells.partRange('일반', '1~18'))).toBeTruthy();
    expect(row.getAllByRole('button').map((b) => b.textContent)).toEqual([
      TR_TEXT.failure.retrySingle,
    ]);
    fireEvent.click(row.getByRole('button'));
    expect(onRetryPart).toHaveBeenCalledWith('b4', 'general');
  });

  // [밴드 TRW1b] retryable false 줄(batchId 없는 옛 묶음)은 다시 단추 0 — 같은 실패 파트라도.
  it('retryable false 줄 → 다시 단추 0, 다른 줄은 그대로', () => {
    draw({
      rows: ROWS.map((row) =>
        row.batchId === 'b4' ? { ...row, retryable: false } : row,
      ),
    });
    expect(
      batch('b4').queryByRole('button', { name: TR_TEXT.failure.retrySingle }),
    ).toBeNull();
  });

  it('파트 여럿의 일부 쪽 실패 → [결과 보기] + [이 파트만 다시], 막은 파트(분량 많음)는 다시 단추 0', () => {
    const rows: BatchRow[] = [
      {
        ...ROWS[2]!,
        parts: [
          { ...ROWS[2]!.parts[0]!, state: 'failed_partial' },
          ROWS[2]!.parts[1]!,
        ],
      },
    ];
    draw({ rows, initialOpen: ['b3'] });
    const parts = partRows('b3');
    expect(
      within(parts[0] as HTMLElement)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual([words.viewResult, TR_TEXT.failure.retryPart]);
    expect(
      within(parts[1] as HTMLElement).queryAllByRole('button'),
    ).toHaveLength(0);
    // 밴드 TRW15: 막은 파트도 목록 꼬리는 「실패」 하나(까닭은 결과 화면 카드).
    expect(parts[1]!.textContent).toContain('실패');
    expect(parts[1]!.textContent).not.toContain('분량 많음');
  });

  it('콜백이 없으면 단추를 그리지 않는다(펼침 단추 밖)', () => {
    render(<BatchTable rows={ROWS} initialOpen={['b1', 'b3']} />);
    const names = screen.getAllByRole('button').map((b) => b.textContent);
    expect(names).not.toContain(words.viewResult);
    expect(names).not.toContain(words.viewProgress);
    expect(names).not.toContain(TR_TEXT.failure.retrySingle);
  });

  it('운영 관리자도 같은 단추 — 표는 사용자 종류를 받지 않는다(v136, 작업 회사는 화면 meta — TRC1)', () => {
    const { onRetryPart } = draw();
    fireEvent.click(
      batch('b4').getByRole('button', { name: TR_TEXT.failure.retrySingle }),
    );
    expect(onRetryPart).toHaveBeenCalledWith('b4', 'general');
  });
});

// 밴드 TRP3 ② TE3(디자인 6c 재대조): 꺾쇠는 접힘 › · 펼침 ∨, 색 #6F7781(text-tertiary). 아이콘은 같은 아이콘을 따로 그려 svg 꼴로 견준다.
describe('BatchTable 꺾쇠 · TRP3 ②', () => {
  const svgOf = (icon: ReactElement) => {
    const { container, unmount } = render(icon);
    const markup = container.querySelector('svg')!.innerHTML;
    unmount();
    return markup;
  };

  it('접힘 = ChevronRight · 펼침 = ChevronDown · 단추 글 색 text-text-tertiary', () => {
    const right = svgOf(<ChevronRightIcon />);
    const down = svgOf(<ChevronDownIcon />);
    expect(right).not.toBe(down);
    draw();
    const toggle = batch('b1').getByRole('button', {
      name: words.expandParts,
    });
    expect(toggle.className.split(/\s+/)).toContain('text-text-tertiary');
    expect(toggle.querySelector('svg')!.innerHTML).toBe(right);
    fireEvent.click(toggle);
    expect(toggle.querySelector('svg')!.innerHTML).toBe(down);
  });
});

describe('BatchTable loading · TRP5', () => {
  it('loading: 머리줄 일곱 그대로 · 몸은 스켈레톤 줄 5(칸 일곱) · 묶음 줄 0(rows 를 줘도) · 표 aria-busy', () => {
    draw({ loading: true });
    const table = screen.getByRole('table');
    expect(table.getAttribute('aria-busy')).toBe('true');
    expect(table.querySelectorAll('thead th')).toHaveLength(7);
    const skeleton = screen.getByTestId('batch-skeleton');
    const lines = skeleton.querySelectorAll('[data-skeleton-row]');
    expect(lines).toHaveLength(5);
    for (const line of lines)
      expect(line.querySelectorAll('td')).toHaveLength(7);
    expect(batchRows()).toHaveLength(0);
  });

  it('loading 이 아니면 스켈레톤 0 · aria-busy 없음 · 묶음 줄 = rows', () => {
    draw();
    expect(screen.queryByTestId('batch-skeleton')).toBeNull();
    expect(screen.getByRole('table').hasAttribute('aria-busy')).toBe(false);
    expect(batchRows()).toHaveLength(ROWS.length);
  });
});

// 밴드 TRW6 ④: 원본 PDF 로 시작한 줄(pdf) → 파일명 앞 회색 「PDF」 배지, 워드 줄은 0.
describe('BatchTable PDF 줄 (TRW6 ④)', () => {
  it('pdf 줄만 파일명 앞 「PDF」 배지 하나 · 파일명 글 그대로', () => {
    draw({
      rows: [
        { ...ROWS[0]!, batchId: 'p1', fileName: 'made_up.pdf', pdf: true },
        ROWS[1]!,
      ],
    });
    const marks = screen.getAllByTestId('batch-pdf-mark');
    expect(marks).toHaveLength(1);
    expect(marks[0]!.textContent).toBe(words.pdfMark);
    expect(batch('p1').getByText('made_up.pdf')).toBeTruthy();
    expect(
      document.querySelector('[data-batch="p1"]')!.contains(marks[0]!),
    ).toBe(true);
  });

  it('pdf 칸이 없는 줄(워드)은 배지 0', () => {
    draw();
    expect(screen.queryByTestId('batch-pdf-mark')).toBeNull();
  });
});

// 밴드 TRW12(sid:MARC-ENT-599 규칙 1~4, sid:MARC-ISSUE-603): 줄 클릭 = 그 줄의 보기 단추와 같은 곳 · Enter 로도 · 줄 안 단추는 줄 클릭 0.
describe('BatchTable 줄 클릭 · TRW12', () => {
  const enter = (row: HTMLElement) => fireEvent.keyDown(row, { key: 'Enter' });
  const notClickable = (row: HTMLElement) => {
    expect(row.hasAttribute('tabindex')).toBe(false);
    expect(row.className.split(/\s+/)).not.toContain('cursor-pointer');
    expect(row.hasAttribute('aria-label')).toBe(false);
  };

  it('묶음 줄 · 파트 여럿 → onOpenBatch(묶음 id) 클릭 한 번·Enter 한 번, 펼침 0, 줄 이름 「파일명 · 진행 보기」', () => {
    const { onOpenBatch, onOpenPart } = draw();
    const row = batchRow('b1');
    expect(row.getAttribute('tabindex')).toBe('0');
    expect(row.getAttribute('aria-label')).toBe(
      words.rowLabel(SAMPLE_FILE, words.viewProgress),
    );
    fireEvent.click(row);
    expect(onOpenBatch).toHaveBeenCalledTimes(1);
    expect(onOpenBatch).toHaveBeenLastCalledWith('b1');
    expect(partRows('b1')).toHaveLength(0); // 감독 판단 a — 펼침은 꺾쇠로만
    enter(row);
    expect(onOpenBatch).toHaveBeenCalledTimes(2);
    expect(onOpenPart).not.toHaveBeenCalled();
    // 끝난 묶음 줄 이름은 [결과 보기]
    expect(batchRow('b3').getAttribute('aria-label')).toBe(
      words.rowLabel('annual_ko_extract.docx', words.viewResult),
    );
  });

  it('묶음 줄 · 파트 하나(보기 단추 있음) → onOpenPart(묶음 id, 파트) 클릭·Enter 각 한 번', () => {
    const { onOpenBatch, onOpenPart } = draw();
    const row = batchRow('b2');
    expect(row.getAttribute('aria-label')).toBe(
      words.rowLabel(SAMPLE_FILE, words.viewResult),
    );
    fireEvent.click(row);
    expect(onOpenPart).toHaveBeenCalledTimes(1);
    expect(onOpenPart).toHaveBeenLastCalledWith('b2', 'general');
    enter(row);
    expect(onOpenPart).toHaveBeenCalledTimes(2);
    expect(onOpenBatch).not.toHaveBeenCalled();
  });

  it('펼친 파트 줄(보기 단추 있음) → onOpenPart(묶음 id, 파트) 클릭·Enter 각 한 번, 줄 이름에 파트 이름', () => {
    const { onOpenBatch, onOpenPart } = draw({ initialOpen: ['b1'] });
    const row = partRow('b1', 'story');
    expect(row.getAttribute('tabindex')).toBe('0');
    expect(row.getAttribute('aria-label')).toBe(
      words.rowLabel(
        SAMPLE_FILE,
        words.viewProgress,
        TR_TEXT.parts.names.story,
      ),
    );
    fireEvent.click(row);
    expect(onOpenPart).toHaveBeenCalledTimes(1);
    expect(onOpenPart).toHaveBeenLastCalledWith('b1', 'story');
    enter(row);
    expect(onOpenPart).toHaveBeenCalledTimes(2);
    expect(onOpenBatch).not.toHaveBeenCalled();
  });

  it('누를 수 없는 줄 — 막힌 파트 하나 묶음 줄 · 막은 파트 줄 · 앞 회차 줄: 클릭·Enter 콜백 0, tabindex·cursor·줄 이름 없음', () => {
    const calls = draw({ initialOpen: ['b1', 'b3'] });
    fireEvent.click(
      batch('b1').getByRole('button', { name: TR_TEXT.cells.round(2) }),
    );
    const earlier = document.querySelector<HTMLElement>('[data-earlier]')!;
    for (const row of [batchRow('b4'), partRow('b3', 'general'), earlier]) {
      notClickable(row);
      fireEvent.click(row);
      enter(row);
    }
    expect(calls.onOpenBatch).not.toHaveBeenCalled();
    expect(calls.onOpenPart).not.toHaveBeenCalled();
    expect(calls.onRetryPart).not.toHaveBeenCalled();
  });

  it('스켈레톤 줄은 누를 수 없다', () => {
    draw({ loading: true });
    for (const row of screen
      .getByTestId('batch-skeleton')
      .querySelectorAll<HTMLElement>('tr'))
      notClickable(row);
  });

  it('콜백이 없으면 줄도 누를 수 없다(단추를 안 그리는 규칙과 같음)', () => {
    render(<BatchTable rows={ROWS} initialOpen={['b1']} />);
    for (const row of [batchRow('b1'), batchRow('b2'), partRow('b1', 'ceo')])
      notClickable(row);
  });

  it('줄 안 단추(꺾쇠·회차·[이 파트만 다시]·[결과 보기]) 누름 → 줄 콜백 0, 단추 자기 콜백만', () => {
    const rows: BatchRow[] = [
      ROWS[0]!,
      {
        ...ROWS[2]!,
        parts: [
          { ...ROWS[2]!.parts[0]!, state: 'failed_partial' },
          ROWS[2]!.parts[1]!,
        ],
      },
    ];
    const { onOpenBatch, onOpenPart, onRetryPart } = draw({
      rows,
      initialOpen: ['b3'],
    });
    // 꺾쇠 → 펼침만
    fireEvent.click(
      batch('b1').getByRole('button', { name: words.expandParts }),
    );
    expect(partRows('b1')).toHaveLength(3);
    // 회차 → 앞 회차 펼침만
    fireEvent.click(
      batch('b1').getByRole('button', { name: TR_TEXT.cells.round(2) }),
    );
    expect(document.querySelectorAll('[data-earlier]')).toHaveLength(1);
    expect(onOpenBatch).not.toHaveBeenCalled();
    expect(onOpenPart).not.toHaveBeenCalled();
    // [이 파트만 다시] → onRetryPart 만
    const part = within(partRow('b3', 'story'));
    fireEvent.click(
      part.getByRole('button', { name: TR_TEXT.failure.retryPart }),
    );
    expect(onRetryPart).toHaveBeenCalledTimes(1);
    expect(onOpenPart).not.toHaveBeenCalled();
    // [결과 보기] → 단추의 onOpenPart 한 번(줄 클릭이 겹쳐 두 번이 되지 않음)
    fireEvent.click(part.getByRole('button', { name: words.viewResult }));
    expect(onOpenPart).toHaveBeenCalledTimes(1);
    expect(onOpenPart).toHaveBeenLastCalledWith('b3', 'story');
    // 묶음 줄 [진행 보기] → onOpenBatch 한 번
    fireEvent.click(
      within(batchRow('b1')).getByRole('button', { name: words.viewProgress }),
    );
    expect(onOpenBatch).toHaveBeenCalledTimes(1);
    // 단추에서 Enter 는 단추 몫 — 줄 콜백 0
    fireEvent.keyDown(
      batch('b1').getByRole('button', { name: words.collapseParts }),
      { key: 'Enter' },
    );
    expect(onOpenBatch).toHaveBeenCalledTimes(1);
  });
});
