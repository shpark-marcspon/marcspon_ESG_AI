// @vitest-environment jsdom
// 시안 값 꼴(밴드 TRP2 경계 ①, 발주서 §3): TC18 수 칸 · TC2 상태 배지 짝 · TC3 묶음 표 머리·몸 · TC14 진행 머리 · TE10 진행 막대.
// jsdom 은 tailwind 를 계산하지 못해 클래스·role·aria 로 단언한다(폭에 기대는 TC18 한 줄은 e2e 계산 값).
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { TAB_STATES } from '../model/index.ts';
import type { TabState } from '../model/index.ts';
import { AT_1205 } from '../model/testing.ts';
import { BatchTable } from './BatchTable.tsx';
import type { BatchRow } from './BatchTable.tsx';
import { PartFailureCard } from './PartFailureCard.tsx';
import { PART_STATUS_LOOK, PartStatusText } from './PartStatusText.tsx';
import { StageCard } from './StageCard.tsx';
import { StatTiles } from './StatTiles.tsx';

afterEach(cleanup);

/** 클래스를 모두 가졌는가(jest-dom 없이). */
function hasClasses(element: Element, ...names: string[]) {
  const own = element.className.split(/\s+/);
  for (const name of names) expect(own).toContain(name);
}

/** 키트 Badge 변형 → 바탕 클래스(packages/ui badge.tsx). */
const BG: Record<string, string> = {
  success: 'bg-support-success-subtle',
  orange: 'bg-support-orange-subtle',
  error: 'bg-support-error-subtle',
  grey: 'bg-background-tertiary',
};

describe('TC2 상태 배지', () => {
  it.each([
    ['done', 'success'],
    ['running', 'orange'],
    ['queued', 'grey'],
    ['failed', 'error'],
    ['failed_partial', 'error'],
  ] as const)('%s → %s 배지(sm)', (state, look) => {
    expect(PART_STATUS_LOOK[state]).toBe(look);
    render(<PartStatusText state={state} />);
    const badge = document.querySelector(`[data-state="${state}"]`)!;
    hasClasses(badge, BG[look]!);
    hasClasses(badge, 'h-5', 'px-1', 'text-style-pre-caption-02');
  });

  it('표는 상태 다섯을 모두 덮는다', () => {
    expect(Object.keys(PART_STATUS_LOOK).sort()).toEqual(
      [...TAB_STATES].sort(),
    );
  });

  it('묶음 셈은 상태마다 배지(완료 success · 실패 error)', () => {
    const row: BatchRow = {
      batchId: 'b1',
      fileName: 'sample.txt',
      uploaded: '10-19 11:40',
      style: 'B',
      uploader: '담당자 A',
      lastStarted: '10-19 12:05',
      parts: AT_1205.map((part) => ({
        part: part.part,
        range: '1~3',
        round: 1,
        started: '12:05',
        state: part.state as TabState,
        earlier: [],
      })),
    };
    render(<BatchTable rows={[row]} />);
    const items = [...screen.getByTestId('batch-summary').children];
    expect(items.map((item) => item.textContent)).toEqual(['완료 2', '실패 1']);
    hasClasses(items[0]!, BG.success!);
    hasClasses(items[1]!, BG.error!);
  });
});

describe('TC3 묶음 표 머리·몸(DataTable 과 같은 꼴)', () => {
  it('머리 칸 #FAFBFB·위아래 선·높이 40·왼쪽, 몸 칸 높이 56·아래 선', () => {
    render(
      <BatchTable
        rows={[
          {
            batchId: 'b1',
            fileName: 'sample.txt',
            uploaded: '10-19 11:40',
            style: 'B',
            uploader: '담당자 A',
            lastStarted: '10-19 12:05',
            parts: [
              {
                part: 'story',
                range: '4~41',
                round: 1,
                started: '12:05',
                state: 'done',
                earlier: [],
              },
            ],
          },
        ]}
      />,
    );
    const heads = screen.getAllByRole('columnheader');
    expect(heads).toHaveLength(7);
    for (const head of heads)
      hasClasses(
        head,
        'h-10',
        'border-y',
        'border-border-tertiary',
        'bg-support-grey-subtle',
        'text-left',
      );
    for (const cell of screen.getAllByRole('cell'))
      hasClasses(cell, 'h-14', 'border-b', 'px-4', 'text-left');
  });
});

describe('TC18 수 칸', () => {
  it('2열 → lg 4열(md 없음), 사이 16 · 안쪽 24 · 숫자 display-03 · 꼬리 caption-03 tertiary', () => {
    render(
      <StatTiles
        items={[{ key: 'a', label: 'a', value: 1, unit: 'page', note: '꼬리' }]}
      />,
    );
    const list = document.querySelector('ul')!;
    hasClasses(list, 'grid-cols-2', 'gap-4', 'lg:grid-cols-4');
    expect(list.className).not.toMatch(/\bmd:/);
    const card = document.querySelector('[data-stat="a"] section')!;
    hasClasses(card, 'p-6');
    hasClasses(
      screen.getByTestId('stat-value').parentElement!,
      'text-style-pre-display-03',
    );
    hasClasses(
      screen.getByText('꼬리'),
      'text-style-pre-caption-03',
      'text-text-tertiary',
    );
  });
});

describe('TC14·TE10 진행 머리와 막대', () => {
  const draw = (bare?: boolean) =>
    render(
      <StageCard
        stageIndex={2}
        stages={['done', 'now', 'todo']}
        pages={{ done: 20, total: 38 }}
        meta="스토리 4~41쪽(38쪽) · 스타일 B · 11:48 시작"
        {...(bare === undefined ? {} : { bare })}
      />,
    );

  it('「진행」 h3 heading-02 · 「2 / 3단계」 display-04 줄 높이 1.3 · 쪽 caption-03 · meta caption-03', () => {
    draw();
    hasClasses(
      screen.getByRole('heading', { level: 3, name: '진행' }),
      'text-style-pre-heading-02',
    );
    hasClasses(
      screen.getByTestId('stage-step'),
      'text-style-pre-display-04',
      'leading-[1.3]',
    );
    hasClasses(
      screen.getByTestId('stage-pages'),
      'text-style-pre-caption-03',
      'text-text-tertiary',
    );
    hasClasses(
      screen.getByTestId('stage-step').parentElement!,
      'flex-col',
      'items-end',
    );
    hasClasses(screen.getByText(/^스토리 4~41쪽/), 'text-style-pre-caption-03');
  });

  it('progressbar: 0~100 · 이름 「전체 단계 진행」 · aria-valuenow = 채움 폭 = 51', () => {
    draw();
    const bar = screen.getByRole('progressbar', { name: '전체 단계 진행' });
    expect(bar.getAttribute('aria-valuemin')).toBe('0');
    expect(bar.getAttribute('aria-valuemax')).toBe('100');
    expect(bar.getAttribute('aria-valuenow')).toBe('51');
    hasClasses(bar, 'h-2', 'rounded-full', 'bg-background-tertiary');
    const fill = screen.getByTestId('stage-progress-fill');
    expect(fill.style.width).toBe('51%');
    hasClasses(fill, 'bg-support-orange');
  });

  it('bare 면 Card(section) 없이 div', () => {
    draw(true);
    expect(screen.getByTestId('stage-card').tagName).toBe('DIV');
    cleanup();
    draw();
    expect(screen.getByTestId('stage-card').tagName).toBe('SECTION');
  });
});

// [TRP2 ②] 목록 표 TC4·TC5 · 대기 줄 TC16 · 실패 카드 TC17.
describe('TRP2 ② 목록 표·대기·실패 꼴', () => {
  const PARTS = (['ceo', 'story'] as const).map((part, index) => ({
    part,
    range: index === 0 ? '1~3' : '4~41',
    round: index === 0 ? 1 : 2,
    started: '12:05',
    state: 'done' as const,
    earlier:
      index === 0 ? [] : [{ round: 1, state: 'failed' as const, at: '11:48' }],
  }));
  const ROW: BatchRow = {
    batchId: 'b1',
    fileName: 'sample.txt',
    uploaded: '10-19 11:40',
    style: 'B',
    uploader: '담당자 A',
    lastStarted: '10-19 12:05',
    parts: PARTS,
  };

  it('TC4 파일명 400 14 #383C40 · 올림 caption-03 tertiary · TC5 펼친 파트 줄 바탕 secondary · 「회차 n」 회색 배지 꼴', () => {
    render(<BatchTable rows={[ROW]} initialOpen={['b1']} />);
    hasClasses(
      screen.getByText('sample.txt'),
      'text-style-pre-body-06',
      'text-text-secondary',
    );
    hasClasses(
      screen.getByText('10-19 11:40 올림'),
      'text-style-pre-caption-03',
      'text-text-tertiary',
    );
    for (const cell of document.querySelectorAll('[data-row="part"] td'))
      hasClasses(cell, 'bg-background-secondary');
    const rounds = screen.getByRole('button', { name: '회차 2' });
    hasClasses(
      rounds,
      'h-5',
      'px-1',
      'bg-background-tertiary',
      'text-text-tertiary',
      'text-style-pre-caption-02',
    );
    expect(rounds.getAttribute('aria-expanded')).toBe('false');
  });

  it('TC16 대기 = 회색 배지 「대기」 + 400 16 #383C40 한 줄', () => {
    render(
      <StageCard
        stageIndex={1}
        stages={['todo', 'todo', 'todo']}
        meta="일반"
        compact
        queuedText="일반 42~64쪽은 차례를 기다리고 있어요"
      />,
    );
    const line = screen.getByTestId('stage-queued');
    hasClasses(line, 'text-style-pre-body-03', 'text-text-secondary');
    hasClasses(line.firstElementChild!, BG.grey!);
    expect(line.firstElementChild!.textContent).toBe('대기');
  });

  it('TC17 파일 줄 = 아이콘 + 500 16 #383C40 · 까닭 = PageInfo error', () => {
    render(
      <PartFailureCard
        kind="rejected"
        reason="no_pages"
        fileLine="sample.txt · 스토리"
      />,
    );
    const file = screen.getByText('sample.txt · 스토리');
    hasClasses(file, 'text-style-pre-body-02', 'text-text-secondary');
    expect(file.querySelector('svg')).not.toBeNull();
    expect(
      screen
        .getByTestId('part-failure')
        .querySelector('[data-tone]')!
        .getAttribute('data-tone'),
    ).toBe('error');
  });
});
