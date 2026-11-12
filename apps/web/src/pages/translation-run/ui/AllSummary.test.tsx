// @vitest-environment jsdom
// [전체] 탭(밴드 TRW0b, 발주서 §3-8 · 확정 판 v136): 파트별 줄 · 남은 파트 「–」 · [모두 받기] 끔(받을 파일 0) → 누름에 load 0·안내 글 ·
// 켜짐 → load 한 번 · 64MB 넘음 글 · 빠진 n 글 · loadWord 없는 줄은 Word 단추 0 · 줄 누름 → onOpenPart.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { AT_1155 } from '../../../entities/translation/model/testing.ts';
import { remainingLine } from '../../../entities/translation/ui/index.ts';
import { AllSummary } from './AllSummary.tsx';
import type { AllSummaryProps, AllSummaryRow } from './AllSummary.tsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const file = async () => ({ blob: new Blob(['x']), fileName: 'f.docx' });
const words = TR_TEXT.all;

const ROWS: AllSummaryRow[] = [
  {
    part: 'ceo',
    range: '1~3',
    round: 1,
    started: '11:48',
    finished: '11:53',
    state: 'done',
    issues: 3,
    misses: 0,
    fixed: 1,
    loadWord: file,
  },
  {
    part: 'story',
    range: '4~41',
    round: 2,
    started: '14:10',
    state: 'running',
    pages: { done: 20, total: 38 },
    issues: null,
    misses: null,
    fixed: null,
  },
  {
    part: 'general',
    range: '42~64',
    round: 1,
    started: '11:53',
    state: 'running',
    issues: null,
    misses: null,
    fixed: null,
  },
];
const STATS: AllSummaryProps['stats'] = [
  {
    key: 'translated',
    label: TR_TEXT.stats.labels.translated,
    value: 3,
    unit: 'page',
  },
  {
    key: 'untranslated',
    label: TR_TEXT.stats.labels.untranslated,
    value: 0,
    unit: 'page',
  },
];

function draw(props: Partial<AllSummaryProps> = {}) {
  const onOpenPart = vi.fn();
  render(
    <AllSummary stats={STATS} rows={ROWS} onOpenPart={onOpenPart} {...props} />,
  );
  return { onOpenPart };
}
// data-part 는 파트 칸 단추에 있다(DataTable 은 줄 data-* 를 받지 않는다 — 밴드 TRP2 TC3). 줄은 그 위 tr.
const row = (part: string) =>
  document.querySelector<HTMLElement>(`[data-part="${part}"]`)!.closest('tr')!;

describe('AllSummary', () => {
  it('파트별 줄 = rows, 남은 파트의 수치는 「–」, 0 은 「0건」', () => {
    draw({ remainingLine: remainingLine(AT_1155) });
    expect(document.querySelectorAll('[data-part]')).toHaveLength(3);
    expect(screen.getByTestId('remaining-line').textContent).toBe(
      '3파트 중 1파트 완료 · 2파트 진행 중',
    );
    expect(row('ceo').querySelector('[data-cell="issues"]')!.textContent).toBe(
      '3건',
    );
    expect(row('ceo').querySelector('[data-cell="misses"]')!.textContent).toBe(
      '0건',
    );
    expect(row('ceo').querySelector('[data-cell="fixed"]')!.textContent).toBe(
      '1개',
    );
    for (const cell of ['issues', 'misses', 'fixed'])
      expect(
        row('story').querySelector(`[data-cell="${cell}"]`)!.textContent,
      ).toBe('–');
    expect(row('story').textContent).toContain('진행 중 · 번역 20/38페이지');
    expect(row('general').textContent).toContain('진행 중 · 준비');
    expect(row('story').textContent).toContain('회차 2');
    expect(row('ceo').textContent).toContain('11:48 · 11:53');
  });

  it('loadWord 없는 줄은 Word 단추 0, 있는 줄만', () => {
    draw();
    expect(screen.getAllByRole('button', { name: words.word })).toHaveLength(1);
    expect(screen.getByTestId('word-ceo')).toBeTruthy();
    expect(screen.queryByTestId('word-story')).toBeNull();
  });

  // [TRP2 TC22] 파트 칸은 글자뿐, 줄을 누르면(마우스·Enter) 그 파트 탭. [Word] 누름은 줄 누름이 아니다.
  it('줄 누름 → onOpenPart(파트), 파트 칸에 단추 없음, [Word] 누름은 줄 누름 아님', () => {
    const { onOpenPart } = draw();
    const story = row('story');
    expect(story.getAttribute('aria-label')).toBe(
      words.rowLabel(TR_TEXT.cells.partRange('스토리', '4~41')),
    );
    expect(
      screen.queryByRole('button', {
        name: TR_TEXT.cells.partRange('스토리', '4~41'),
      }),
    ).toBeNull();
    fireEvent.click(story);
    expect(onOpenPart).toHaveBeenCalledWith('story');
    fireEvent.keyDown(row('general'), { key: 'Enter' });
    expect(onOpenPart).toHaveBeenLastCalledWith('general');
    onOpenPart.mockClear();
    fireEvent.click(screen.getByTestId('word-ceo'));
    expect(onOpenPart).not.toHaveBeenCalled();
  });

  it('[모두 받기] 끔(받을 자동 수정 병기본 0) → 누름에 load 0, 안내 「받을 … 없어요」', async () => {
    const load = vi.fn(file);
    draw({ downloadAll: { load, disabled: true } });
    const button = screen.getByTestId('download-all');
    expect(button.getAttribute('aria-disabled')).toBe('true');
    await act(async () => fireEvent.click(button));
    expect(load).not.toHaveBeenCalled();
    expect(screen.getByTestId('all-summary').textContent).toContain(
      words.noFiles,
    );
  });

  it('[모두 받기] 켜짐 → load 한 번, 안내 「자동 수정 병기본이 있는 끝난 파트만 받아요」', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:fake');
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const load = vi.fn(file);
    draw({ downloadAll: { load, disabled: false } });
    expect(screen.getByTestId('all-summary').textContent).toContain(
      words.downloadLead,
    );
    await act(async () => fireEvent.click(screen.getByTestId('download-all')));
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('64MB 넘음 글(archiveError) · 빠진 n 글(missingCount > 0 만)', () => {
    draw({
      downloadAll: {
        load: file,
        disabled: false,
        archiveError: 'too_large',
        missingCount: 1,
      },
    });
    expect(screen.getByTestId('archive-error').textContent).toBe(
      words.archiveTooLarge,
    );
    expect(screen.getByTestId('archive-missing').textContent).toBe(
      '1개 파일을 넣지 못했어요. 받은 zip 에 없는 파트는 아래 표의 [Word]로 받아 주세요',
    );
    cleanup();
    // 받을 것 없음(409 NO_FINISHED_PARTS — TRP1 W4)은 끈 단추와 같은 글.
    draw({
      downloadAll: { load: file, disabled: false, archiveError: 'nothing' },
    });
    expect(screen.getByTestId('archive-error').textContent).toBe(words.noFiles);
    cleanup();
    draw({ downloadAll: { load: file, disabled: false, missingCount: 0 } });
    expect(screen.queryByTestId('archive-error')).toBeNull();
    expect(screen.queryByTestId('archive-missing')).toBeNull();
  });

  // [밴드 TRW1b D2] 409 NO_FINISHED_PARTS 뒤 단추가 꺼지면 noFiles 글은 단추 옆 한 자리만. too_large 는 꺼져도 그대로.
  it('archiveError nothing + 꺼진 단추 → noFiles 글 한 자리(archive-error 0) · too_large 는 그대로', () => {
    draw({
      downloadAll: { load: file, disabled: true, archiveError: 'nothing' },
    });
    expect(screen.queryByTestId('archive-error')).toBeNull();
    expect(screen.getAllByText(words.noFiles)).toHaveLength(1);
    cleanup();
    draw({
      downloadAll: { load: file, disabled: true, archiveError: 'too_large' },
    });
    expect(screen.getByTestId('archive-error').textContent).toBe(
      words.archiveTooLarge,
    );
  });

  it('downloadAll 이 없으면 [모두 받기] 없음(파트 하나)', () => {
    draw();
    expect(screen.queryByTestId('download-all')).toBeNull();
  });

  // 밴드 TRP3 TB2(시안 TR-04): [모두 받기] solid-black round md · 파트 표 [Word] outline-grey round sm.
  it('[모두 받기]는 켜짐·꺼짐 모두 bg-button-black, 파트 표 [Word]는 h-7·rounded-full(h-9 아님)', () => {
    draw({ downloadAll: { load: vi.fn(file), disabled: false } });
    expect(
      screen.getByTestId('download-all').classList.contains('bg-button-black'),
    ).toBe(true);
    const word = screen.getByTestId('word-ceo').classList;
    expect(word.contains('h-7')).toBe(true);
    expect(word.contains('rounded-full')).toBe(true);
    expect(word.contains('h-9')).toBe(false);
    cleanup();
    draw({ downloadAll: { load: vi.fn(file), disabled: true } });
    const off = screen.getByTestId('download-all');
    expect(off.getAttribute('aria-disabled')).toBe('true');
    expect(off.classList.contains('bg-button-black')).toBe(true);
  });
});

// 밴드 TRW2(6c 10-26): A·B 견주기 줄 — 수치 「A / B」, 표 머리 아랫줄 「A / B」(TRW5 — 옛 끝 「(A / B)」), [Word A]·[Word B](있는 스타일만, 단추 사이 gap-2).
describe('AllSummary A·B 견주기(TRW2)', () => {
  const sep = TR_TEXT.stats.pairSeparator;
  const loadA = vi.fn(file);
  const loadB = vi.fn(file);
  const COMPARE_ROWS: AllSummaryRow[] = [
    {
      ...ROWS[0]!,
      issues: { A: 12, B: 9 },
      misses: { A: 0, B: null },
      fixed: { A: 1, B: 2 },
      loadWord: undefined,
      loadWords: { A: loadA, B: loadB },
    },
    {
      ...ROWS[1]!,
      part: 'story',
      state: 'done',
      issues: { A: 1, B: 1 },
      misses: { A: 1, B: 1 },
      fixed: { A: 0, B: 0 },
      loadWords: { A: file },
    },
  ];

  it('수치 칸은 「12건 / 9건」(없음은 그 쪽만 「–」), 표 머리 아랫줄 A / B', () => {
    draw({ rows: COMPARE_ROWS, compare: true });
    const cell = (id: string) =>
      row('ceo').querySelector(`[data-cell="${id}"]`)!.textContent;
    expect(cell('issues')).toBe(`12건${sep}9건`);
    expect(cell('misses')).toBe(`0건${sep}–`);
    expect(cell('fixed')).toBe(`1개${sep}2개`);
    expect(
      screen.getByRole('columnheader', {
        name: `${words.columns.glossaryMiss} ${words.pairSub}`,
      }),
    ).toBeTruthy();
  });

  // 밴드 TRW5(디자인 N2): 머리는 두 줄 — 윗줄 이름, 아랫줄 작은 회색 「A / B」(괄호 0). 수 칸 셋 모두.
  it('견주기 수 칸 머리 두 줄: 「검수 이슈」 + 아랫줄 「A / B」, 괄호 없음', () => {
    draw({ rows: COMPARE_ROWS, compare: true });
    expect(words.pairSub).toBe('A / B');
    for (const name of [
      words.columns.issues,
      words.columns.glossaryMiss,
      words.columns.fixed,
    ]) {
      const head = screen.getByRole('columnheader', {
        name: `${name} A / B`,
      });
      expect(head.textContent).not.toMatch(/[()]/);
      const sub = head.querySelector('[data-header-sub]')!;
      expect(sub.textContent).toBe('A / B');
      expect(sub.className.split(/\s+/)).toEqual(
        expect.arrayContaining(['block', 'text-text-tertiary']),
      );
    }
    expect(document.querySelectorAll('[data-header-sub]')).toHaveLength(3);
  });

  it('견주기 1280 꺾임 막음: [Word A]·[Word B] 한 줄(flex-nowrap), 회차·시각 nowrap', () => {
    draw({ rows: COMPARE_ROWS, compare: true });
    const pair = screen.getByTestId('words-ceo');
    expect(pair.classList.contains('flex-nowrap')).toBe(true);
    expect(pair.classList.contains('flex-wrap')).toBe(false);
    const cells = row('ceo').querySelectorAll('td');
    for (const td of [cells[1]!, cells[2]!])
      expect(td.querySelector('.whitespace-nowrap')).not.toBeNull();
    // 열 폭 고정(DT1 꼴): table-fixed + colgroup, 내려받기 열은 견주기 198(최소 166 이상).
    expect(
      document.querySelector('table')!.classList.contains('table-fixed'),
    ).toBe(true);
    const cols = [...document.querySelectorAll('colgroup col')];
    expect((cols.at(-1) as HTMLElement).style.width).toBe('198px');
  });

  it('[Word A]·[Word B] 는 각자 그 load, 한 스타일만 있으면 그 단추만', async () => {
    draw({ rows: COMPARE_ROWS, compare: true });
    expect(screen.getByTestId('word-ceo-A').textContent).toContain(
      words.wordOf('A'),
    );
    expect(screen.queryByTestId('word-ceo')).toBeNull();
    expect(screen.getByTestId('word-story-A')).toBeTruthy();
    expect(screen.queryByTestId('word-story-B')).toBeNull();
    await act(async () => {
      fireEvent.click(screen.getByTestId('word-ceo-B'));
    });
    expect(loadB).toHaveBeenCalledTimes(1);
    expect(loadA).not.toHaveBeenCalled();
    // 두 단추는 한 줄 묶음 안, 사이 8(gap-2)
    const pair = screen.getByTestId('words-ceo');
    expect(pair.classList.contains('gap-2')).toBe(true);
    expect(pair.contains(screen.getByTestId('word-ceo-A'))).toBe(true);
    expect(pair.contains(screen.getByTestId('word-ceo-B'))).toBe(true);
  });

  it('한 스타일 줄(숫자)은 그대로 — 표 머리에 A / B 줄 없음', () => {
    draw();
    expect(
      screen.getByRole('columnheader', { name: words.columns.issues }),
    ).toBeTruthy();
    expect(document.querySelector('[data-header-sub]')).toBeNull();
    expect(row('ceo').querySelector('[data-cell="issues"]')!.textContent).toBe(
      '3건',
    );
  });
});
