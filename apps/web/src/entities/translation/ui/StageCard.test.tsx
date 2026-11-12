// @vitest-environment jsdom
// 진행 카드(밴드 TRW0b, 발주서 §3-3): 단계 셋 줄 꼴(data-state) · 「번역 20 / 38쪽」 · 줄인 꼴 대기 글 · 주의 줄 있음/없음 · 「비용」 말 없음.
import { cleanup, render, screen } from '@testing-library/react';
import { waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';
import { vi } from 'vitest';

import { TR_TEXT } from '../config/text.ts';
import { stageProgress } from '../model/index.ts';
import { StageCard } from './StageCard.tsx';

afterEach(cleanup);

/** 주의 줄 prop 시험용 지어낸 글(번역 진행 화면의 안심 줄은 지웠다 — 밴드 WT1, sid:MARC-ENT-625. 부품 prop 은 남는다). */
const CAUTION = '지어낸 주의 한 줄';
const META = '스토리 4~41페이지(총 38페이지) · 스타일 B · 11:48 시작';

describe('StageCard', () => {
  it('큰 꼴: 「2 / 3단계」·「번역 20 / 38쪽」, 단계 셋 줄의 data-state, 지금 단계는 aria-current', () => {
    render(
      <StageCard
        stageIndex={2}
        stages={['done', 'now', 'todo']}
        pages={{ done: 20, total: 38 }}
        meta={META}
      />,
    );
    expect(screen.getByTestId('stage-step').textContent).toBe('2 / 3단계');
    expect(screen.getByTestId('stage-pages').textContent).toBe(
      '번역 20 / 38페이지',
    );
    const rows = document.querySelectorAll('[data-stage]');
    expect([...rows].map((row) => row.getAttribute('data-state'))).toEqual([
      'done',
      'now',
      'todo',
    ]);
    expect(rows[1]!.getAttribute('aria-current')).toBe('step');
    expect(rows[1]!.textContent).toContain(
      '번역 20 / 38페이지 · 검수·자동 수정은',
    );
    expect(screen.getByTestId('stage-card').textContent).not.toMatch(/비용/);
  });

  it('주의 줄은 caution 이 있을 때만', () => {
    const { rerender } = render(
      <StageCard stageIndex={1} stages={['now', 'todo', 'todo']} meta={META} />,
    );
    expect(screen.queryByTestId('stage-caution')).toBeNull();
    expect(screen.queryByTestId('stage-pages')).toBeNull();
    rerender(
      <StageCard
        stageIndex={1}
        stages={['now', 'todo', 'todo']}
        meta={META}
        caution={CAUTION}
      />,
    );
    expect(screen.getByTestId('stage-caution').textContent).toBe(CAUTION);
  });

  it('줄인 꼴 · 대기: 「대기」 + 차례를 기다리는 글, 「서버가 둘까지…」 설명 없음', () => {
    const queued = TR_TEXT.stage.queued('일반', '42~64');
    render(
      <StageCard
        compact
        stageIndex={1}
        stages={['todo', 'todo', 'todo']}
        meta="일반 42~64페이지(총 23페이지)"
        queuedText={queued}
      />,
    );
    const card = screen.getByTestId('stage-card');
    expect(card.hasAttribute('data-compact')).toBe(true);
    expect(card.textContent).toContain(`대기${queued}`);
    expect(card.textContent).not.toMatch(/서버가/);
    expect(
      [...document.querySelectorAll('[data-stage]')].every(
        (row) => row.getAttribute('data-state') === 'todo',
      ),
    ).toBe(true);
  });

  it('줄인 꼴 · 준비 중: 머리 줄에 단계 글, 「준비 중 · …」 줄', () => {
    render(
      <StageCard
        compact
        stageIndex={1}
        stages={['now', 'todo', 'todo']}
        meta="일반 42~64페이지(총 23페이지) · 11:53 시작"
      />,
    );
    const card = screen.getByTestId('stage-card');
    expect(card.textContent).toContain(
      '일반 42~64페이지(총 23페이지) · 11:53 시작 · 1 / 3단계',
    );
    expect(card.textContent).toContain(TR_TEXT.stage.prepareNow);
  });

  // 밴드 TRP3 TB1(디자인 6c 답): 주의 상자는 PageInfo caution 톤(시안 TR-03 g-info--caution).
  it('주의 상자는 caution 톤(data-tone)', () => {
    render(
      <StageCard
        stageIndex={1}
        stages={['now', 'todo', 'todo']}
        meta={META}
        caution={CAUTION}
      />,
    );
    expect(screen.getByTestId('stage-caution').getAttribute('data-tone')).toBe(
      'caution',
    );
  });
});

// 밴드 TRP3 ② TC16(디자인 6c 재대조): 대기 줄인 꼴은 배지 + 한 줄만 — 머리 줄·단계 이름 셋 없음.
describe('StageCard 대기 · TRP3 ②', () => {
  it('줄인 꼴 · 대기: 카드 글 = 「대기」 + 대기 글뿐, [data-stage] 0, meta 글 없음', () => {
    const queued = TR_TEXT.stage.queued('일반', '42~64');
    render(
      <StageCard
        compact
        stageIndex={1}
        stages={['todo', 'todo', 'todo']}
        meta="일반 42~64페이지(총 23페이지)"
        queuedText={queued}
      />,
    );
    const card = screen.getByTestId('stage-card');
    expect(card.textContent).toBe(`대기${queued}`);
    expect(card.querySelectorAll('[data-stage]')).toHaveLength(0);
    expect(card.textContent).not.toContain('23페이지)');
  });
});

// 밴드 TRP4 ②-1~3: 진행 막대 gw-m-flow·gw-m-width · 지금 단계 점 gw-m-ring · 끝남 체크 gw-m-pop · 머리 글자만 CountUp(aria 는 끝 값).
describe('StageCard 움직임(TRP4)', () => {
  /** prefers-reduced-motion: reduce 의 답을 정해 둔 matchMedia(r3-flow GP4 R2 꼴). */
  function stubMotion(reduce: boolean) {
    vi.stubGlobal(
      'matchMedia',
      (query: string) =>
        ({
          matches: query.includes('reduce') ? reduce : !reduce,
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
        }) as unknown as MediaQueryList,
    );
  }
  afterEach(() => vi.unstubAllGlobals());
  const card = () => (
    <StageCard
      stageIndex={2}
      stages={['done', 'now', 'todo']}
      pages={{ done: 20, total: 38 }}
      meta={META}
    />
  );

  it('ⓐ 채움 막대에 gw-m-flow·gw-m-width, 폭은 그대로 stageProgress 값 %', () => {
    render(card());
    const fill = screen.getByTestId('stage-progress-fill');
    expect(fill.classList.contains('gw-m-flow')).toBe(true);
    expect(fill.classList.contains('gw-m-width')).toBe(true);
    expect(fill.style.width).toBe(
      `${stageProgress(2, { done: 20, total: 38 })}%`,
    );
  });

  it('ⓑ 지금 단계 줄의 점에만 gw-m-ring, 끝남 줄의 체크 svg 에 gw-m-pop', () => {
    render(card());
    const dot = (stage: string) =>
      document.querySelector(`[data-stage="${stage}"] > span[aria-hidden]`)!;
    expect(
      document
        .querySelector('[aria-current="step"] > span[aria-hidden]')!
        .classList.contains('gw-m-ring'),
    ).toBe(true);
    expect(dot('prepare').classList.contains('gw-m-ring')).toBe(false);
    expect(dot('word').classList.contains('gw-m-ring')).toBe(false);
    expect(
      dot('prepare').querySelector('svg')!.classList.contains('gw-m-pop'),
    ).toBe(true);
  });

  it('ⓒ 움직임 켬: 처음 「2 / 3단계」(단계 글은 굴리지 않음 — TRP5)·「번역 0 / 38쪽」, 그동안 aria-valuenow 는 끝 값 → 끝 글로 굴러감', async () => {
    stubMotion(false);
    render(card());
    const end = String(stageProgress(2, { done: 20, total: 38 }));
    expect(screen.getByTestId('stage-step').textContent).toBe('2 / 3단계');
    expect(screen.getByTestId('stage-pages').textContent).toBe(
      '번역 0 / 38페이지',
    );
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe(
      end,
    );
    await waitFor(() =>
      expect(screen.getByTestId('stage-step').textContent).toBe('2 / 3단계'),
    );
    await waitFor(() =>
      expect(screen.getByTestId('stage-pages').textContent).toBe(
        '번역 20 / 38페이지',
      ),
    );
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe(
      end,
    );
  });

  it('ⓓ 움직임 줄임: 처음부터 끝 글', () => {
    stubMotion(true);
    render(card());
    expect(screen.getByTestId('stage-step').textContent).toBe('2 / 3단계');
    expect(screen.getByTestId('stage-pages').textContent).toBe(
      '번역 20 / 38페이지',
    );
  });
});

describe('StageCard 굴림 손질(TRP5)', () => {
  function stubMotion(reduce: boolean) {
    vi.stubGlobal(
      'matchMedia',
      (query: string) =>
        ({
          matches: query.includes('reduce') ? reduce : !reduce,
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
        }) as unknown as MediaQueryList,
    );
  }
  afterEach(() => vi.unstubAllGlobals());
  const card = (props: {
    stageIndex?: 1 | 2 | 3;
    done?: number;
    seenKey?: string;
  }) => (
    <StageCard
      stageIndex={props.stageIndex ?? 2}
      stages={['done', 'now', 'todo']}
      pages={{ done: props.done ?? 20, total: 38 }}
      meta={META}
      {...(props.seenKey === undefined ? {} : { seenKey: props.seenKey })}
    />
  );
  const stepText = () => screen.getByTestId('stage-step').textContent;
  const pagesText = () => screen.getByTestId('stage-pages').textContent;

  it('B-1 움직임 켬: 단계 글은 첫 그림부터 끝 값(「0 / 3단계」 없음), 바뀌면 바로 새 값', () => {
    stubMotion(false);
    const { rerender } = render(card({ seenKey: 'b-1/story' }));
    expect(stepText()).toBe('2 / 3단계');
    rerender(card({ stageIndex: 3, seenKey: 'b-1/story' }));
    expect(stepText()).toBe('3 / 3단계');
  });

  it('B-2 움직임 켬: 처음 붙음은 0 에서 굴림 → 떼고 다시 붙으면 첫 그림부터 끝 값 → 그 뒤 바뀜은 앞 값에서 굴림', async () => {
    stubMotion(false);
    const first = render(card({ seenKey: 'b-2/story' }));
    expect(pagesText()).toBe('번역 0 / 38페이지');
    await waitFor(() => expect(pagesText()).toBe('번역 20 / 38페이지'));
    first.unmount();
    const again = render(card({ seenKey: 'b-2/story' }));
    expect(pagesText()).toBe('번역 20 / 38페이지');
    again.rerender(card({ done: 25, seenKey: 'b-2/story' }));
    // 바뀐 직후는 앞 값(0 으로 돌아가지 않음) → 굴러서 끝 값
    expect(pagesText()).toBe('번역 20 / 38페이지');
    await waitFor(() => expect(pagesText()).toBe('번역 25 / 38페이지'));
  });

  it('B-2 다른 열쇠(다른 파트)는 따로 — 처음 붙으면 0 에서', () => {
    stubMotion(false);
    const first = render(card({ seenKey: 'b-2b/ceo' }));
    first.unmount();
    render(card({ seenKey: 'b-2b/story' }));
    expect(pagesText()).toBe('번역 0 / 38페이지');
  });

  it('B-2 움직임 줄임: 처음 붙음부터 늘 끝 값', () => {
    stubMotion(true);
    render(card({ seenKey: 'b-2c/story' }));
    expect(pagesText()).toBe('번역 20 / 38페이지');
    expect(stepText()).toBe('2 / 3단계');
  });
});

// 밴드 TRW6 ④: PDF 흐름 파트의 준비 진행 중 글 「PDF 읽는 중 · …」(큰 꼴·줄인 꼴), 단계 수 그대로.
describe('StageCard pdf (TRW6 ④)', () => {
  it.each([false, true])(
    '준비 진행 중 · pdf · compact=%s → PDF 읽는 중 글, 워드 글 0 · 단계 셋',
    (compact) => {
      render(
        <StageCard
          compact={compact}
          pdf
          stageIndex={1}
          stages={['now', 'todo', 'todo']}
          meta="일반 1~3페이지(총 3페이지) · 10:05 시작"
        />,
      );
      const card = screen.getByTestId('stage-card');
      expect(card.textContent).toContain(TR_TEXT.stage.prepareNowPdf);
      expect(card.textContent).not.toContain(TR_TEXT.stage.prepareNow);
      expect(card.textContent).toContain('1 / 3단계');
    },
  );

  it('pdf 여도 준비가 끝났으면 「PDF 읽는 중」 0', () => {
    render(
      <StageCard
        pdf
        stageIndex={2}
        stages={['done', 'now', 'todo']}
        meta="일반 1~3페이지(총 3페이지) · 10:05 시작"
      />,
    );
    expect(screen.getByTestId('stage-card').textContent).not.toContain(
      TR_TEXT.stage.prepareNowPdf,
    );
  });
});
