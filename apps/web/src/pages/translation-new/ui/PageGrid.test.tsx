// @vitest-environment jsdom
// 쪽 칸 그리드(밴드 TRW0a ②, 발주서 §3-3-1): 칸 수·[더 보기]·끌기 한 번에 onPaint 한 번·떨어진 쪽 누름·Enter·Space·겹침 꼴·aria-pressed.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
// 썸네일 시험(밴드 TRW9) — 위 줄을 고치지 않는다, 더하기만.
import { act } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import type {
  PartKey,
  Range,
} from '../../../entities/translation/model/index.ts';
import type { LoadedPdf } from '../../../widgets/doc-viewer/index.ts';
import { PageGrid } from './PageGrid.tsx';
// 범례는 따로 가져온다(밴드 TRP3 ② — 위 줄을 고치면 기존 시험 줄이 바뀐다, 더하기만).
import { PageGridLegend } from './PageGrid.tsx';
import { PART_LOOK } from './partLook.ts';

afterEach(cleanup);

type Ranges = Record<PartKey, Range | null>;
const NONE: Ranges = { ceo: null, story: null, general: null };

const cell = (page: number) =>
  document.querySelector<HTMLButtonElement>(`[data-page="${page}"]`)!;
const cells = () => document.querySelectorAll('[data-page]');
const mouse = { pointerType: 'mouse', button: 0, buttons: 1 };

function draw(props: Partial<Parameters<typeof PageGrid>[0]> = {}) {
  const onPaint = vi.fn();
  const view = render(
    <PageGrid
      pageCount={64}
      ranges={NONE}
      active="story"
      onPaint={onPaint}
      {...props}
    />,
  );
  return { onPaint, ...view };
}

describe('PageGrid', () => {
  it('칸 수 = min(쪽 수, 40), [더 보기] 한 번 → 쪽 수까지(또는 80)', () => {
    draw();
    expect(cells()).toHaveLength(40);
    fireEvent.click(
      screen.getByRole('button', { name: TR_TEXT.grid.more(41, 64) }),
    );
    expect(cells()).toHaveLength(64);
    expect(screen.queryByRole('button', { name: /^더 보기/ })).toBeNull();
    cleanup();
    draw({ pageCount: 120 });
    fireEvent.click(screen.getByRole('button', { name: /^더 보기/ }));
    expect(cells()).toHaveLength(80);
  });

  it('쪽 수 ≤ 40 이면 [더 보기] 없음', () => {
    draw({ pageCount: 12 });
    expect(cells()).toHaveLength(12);
    expect(screen.queryByRole('button', { name: /^더 보기/ })).toBeNull();
  });

  it('끌기: pointerdown(3) → pointermove(7) → pointerup 이면 onPaint(고른 파트, 3~7) 한 번', () => {
    const { onPaint } = draw();
    fireEvent.pointerDown(cell(3), mouse);
    fireEvent.pointerMove(cell(5), mouse);
    fireEvent.pointerMove(cell(7), mouse);
    expect(onPaint).not.toHaveBeenCalled();
    // 끄는 동안 미리 칠한다
    expect(cell(5).getAttribute('data-parts')).toBe('story');
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledTimes(1);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 3, to: 7 });
  });

  it('거꾸로 끌어도 from ≤ to', () => {
    const { onPaint } = draw({ active: 'ceo' });
    fireEvent.pointerDown(cell(9), mouse);
    fireEvent.pointerMove(cell(2), mouse);
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledWith('ceo', { from: 2, to: 9 });
  });

  it('움직이지 않고 뗀 마우스 누름 = 누름(떨어진 쪽이면 늘린 범위). 뒤따르는 click 은 무시', () => {
    const { onPaint } = draw({
      ranges: { ...NONE, story: { from: 4, to: 6 } },
    });
    fireEvent.pointerDown(cell(10), mouse);
    fireEvent.pointerUp(window, mouse);
    fireEvent.click(cell(10), { detail: 1 });
    expect(onPaint).toHaveBeenCalledTimes(1);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 4, to: 10 });
  });

  // 밴드 TRW3: 옛 「끝이 그 쪽으로 준다」 → 그 쪽을 뺀다(가운데면 가까운 끝까지 같이).
  it('구간 안의 쪽 누름(Enter) = 그 쪽을 뺀다 — 가운데면 가까운 끝까지', () => {
    const { onPaint } = draw({
      ranges: { ...NONE, story: { from: 4, to: 41 } },
    });
    fireEvent.keyDown(cell(30), { key: 'Enter' });
    expect(onPaint).toHaveBeenCalledWith('story', { from: 4, to: 29 });
    fireEvent.keyDown(cell(4), { key: 'Enter' });
    expect(onPaint).toHaveBeenLastCalledWith('story', { from: 5, to: 41 });
  });

  it('Enter·Space = 누름(빈 파트면 그 한 쪽)', () => {
    const { onPaint } = draw({ active: 'general' });
    fireEvent.keyDown(cell(5), { key: 'Enter' });
    expect(onPaint).toHaveBeenLastCalledWith('general', { from: 5, to: 5 });
    fireEvent.keyDown(cell(8), { key: ' ' });
    expect(onPaint).toHaveBeenCalledTimes(2);
    fireEvent.keyDown(cell(8), { key: 'a' });
    expect(onPaint).toHaveBeenCalledTimes(2);
  });

  it('터치 톡 누름 = 누름', () => {
    const { onPaint } = draw();
    fireEvent.pointerDown(cell(6), { pointerType: 'touch', button: 0 });
    fireEvent.click(cell(6), { detail: 1 });
    expect(onPaint).toHaveBeenCalledWith('story', { from: 6, to: 6 });
  });

  it('겹친 쪽은 겹침 꼴(data-overlap)과 파트 점(겹친 수만큼), aria-pressed 는 고른 파트의 쪽, 이름은 「n쪽, 파트」', () => {
    draw({
      ranges: {
        ceo: { from: 1, to: 8 },
        story: { from: 7, to: 41 },
        general: { from: 8, to: 9 },
      },
      active: 'story',
    });
    expect(cell(3).hasAttribute('data-overlap')).toBe(false);
    expect(cell(3).querySelectorAll('[data-part-dot]')).toHaveLength(0);
    expect(cell(7).getAttribute('data-overlap')).toBe('true');
    expect(cell(7).querySelectorAll('[data-part-dot]')).toHaveLength(2);
    expect(cell(8).querySelectorAll('[data-part-dot]')).toHaveLength(3);
    expect(cell(3).getAttribute('aria-pressed')).toBe('false');
    expect(cell(20).getAttribute('aria-pressed')).toBe('true');
    expect(cell(30).getAttribute('aria-label')).toBe('30페이지, 스토리');
    expect(cell(3).getAttribute('aria-label')).toBe('3페이지, CEO 메시지');
    expect(cell(7).getAttribute('aria-label')).toBe(
      '7페이지, CEO 메시지, 스토리',
    );
  });

  it('보이지 않는 칸에 칠한 쪽을 알린다', () => {
    draw({ ranges: { ...NONE, story: { from: 4, to: 41 } } });
    expect(screen.getByTestId('page-grid').textContent).toContain(
      '1~40페이지를 보고 있어요 · 41~64페이지에 스토리 41페이지가 칠해져 있어요',
    );
  });

  // sid:MARC-ISSUE-307 1(TRW0b): 보이는 칸이 쪽 수를 따른다.
  it('0쪽으로 뜬 뒤 쪽 수가 오면 첫 칸들이 나온다', () => {
    const { onPaint, rerender } = draw({ pageCount: 0 });
    expect(cells()).toHaveLength(0);
    rerender(
      <PageGrid
        pageCount={64}
        ranges={NONE}
        active="story"
        onPaint={onPaint}
      />,
    );
    expect(cells()).toHaveLength(40);
  });

  it('쪽 수가 줄면 마지막 쪽 너머 칸이 없다(더 보기로 늘린 뒤에도)', () => {
    const { onPaint, rerender } = draw({ pageCount: 120 });
    fireEvent.click(screen.getByRole('button', { name: /^더 보기/ }));
    expect(cells()).toHaveLength(80);
    rerender(
      <PageGrid
        pageCount={50}
        ranges={NONE}
        active="story"
        onPaint={onPaint}
      />,
    );
    expect(cells()).toHaveLength(50);
    expect(cell(51)).toBeNull();
    expect(screen.queryByRole('button', { name: /^더 보기/ })).toBeNull();
    rerender(
      <PageGrid
        pageCount={12}
        ranges={NONE}
        active="story"
        onPaint={onPaint}
      />,
    );
    expect(cells()).toHaveLength(12);
  });
});

// 밴드 TRW3(그린워싱처럼): 칠한 쪽 누름 = 해제, 끌기는 시작 쪽이 칠하기·지우개를 정함, 칸 밖으로 끌어도 이어짐.
describe('PageGrid 누름·끌기 · TRW3', () => {
  const story = (from: number, to: number) => ({
    ranges: { ...NONE, story: { from, to } },
  });

  it('칠한 쪽 마우스 누름 → onPaint(파트, 줄어든 범위)', () => {
    const { onPaint } = draw(story(4, 10));
    fireEvent.pointerDown(cell(10), mouse);
    fireEvent.pointerUp(window, mouse);
    fireEvent.click(cell(10), { detail: 1 });
    expect(onPaint).toHaveBeenCalledTimes(1);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 4, to: 9 });
  });

  it('한 쪽만 칠한 쪽 마우스 누름 → onPaint(파트, null)', () => {
    const { onPaint } = draw(story(6, 6));
    fireEvent.pointerDown(cell(6), mouse);
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledWith('story', null);
  });

  it('Enter 로도 해제(한 쪽뿐 → null)', () => {
    const { onPaint } = draw(story(6, 6));
    fireEvent.keyDown(cell(6), { key: 'Enter' });
    expect(onPaint).toHaveBeenCalledWith('story', null);
  });

  it('칠한 쪽에서 끌기 = 지우개: 끄는 중 미리 지우고, 떼면 지운 범위', () => {
    const { onPaint } = draw(story(4, 20));
    fireEvent.pointerDown(cell(15), mouse);
    fireEvent.pointerMove(cell(25), mouse);
    // 미리 보기: 15~20 이 빠지고 4~14 는 남는다
    expect(cell(16).getAttribute('data-parts')).toBeNull();
    expect(cell(14).getAttribute('data-parts')).toBe('story');
    expect(onPaint).not.toHaveBeenCalled();
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledTimes(1);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 4, to: 14 });
  });

  it('지우개 가운데: 작은 쪽이 같이 빠짐', () => {
    const { onPaint } = draw(story(4, 20));
    fireEvent.pointerDown(cell(7), mouse);
    fireEvent.pointerMove(cell(9), mouse);
    // 미리 보기: 남는 앞 4~6 이 작아 같이 빠진다
    expect(cell(5).getAttribute('data-parts')).toBeNull();
    expect(cell(10).getAttribute('data-parts')).toBe('story');
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 10, to: 20 });
  });

  it('빈 쪽에서 끌기 = 칠하기: 기존 구간과 이은 범위(사이도 채움), 미리 보기도', () => {
    const { onPaint } = draw(story(4, 6));
    fireEvent.pointerDown(cell(12), mouse);
    fireEvent.pointerMove(cell(14), mouse);
    expect(cell(9).getAttribute('data-parts')).toBe('story');
    expect(cell(15).getAttribute('data-parts')).toBeNull();
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 4, to: 14 });
  });

  it('칸 밖(아래)으로 끌어도 칸 상자 안으로 당긴 자리의 쪽(마지막 보이는 쪽)까지', () => {
    const rect = (top: number, bottom: number) =>
      ({
        top,
        bottom,
        left: 0,
        right: 500,
        width: 500,
        height: bottom - top,
        x: 0,
        y: top,
        toJSON: () => ({}),
      }) as DOMRect;
    const spy = vi
      .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockImplementation(() => rect(100, 600));
    const points: [number, number][] = [];
    const original = document.elementFromPoint;
    document.elementFromPoint = (x: number, y: number) => {
      points.push([x, y]);
      return cell(40);
    };
    try {
      const { onPaint } = draw();
      fireEvent.pointerDown(cell(35), mouse);
      fireEvent.pointerMove(document.body, {
        ...mouse,
        clientX: 900,
        clientY: 750,
      });
      // 칸 상자 안으로 당긴 자리(오른쪽 499, 아래 599)에서 찾는다
      expect(points.at(-1)).toEqual([499, 599]);
      expect(cell(40).getAttribute('data-parts')).toBe('story');
      fireEvent.pointerUp(window, mouse);
      expect(onPaint).toHaveBeenCalledWith('story', { from: 35, to: 40 });
    } finally {
      document.elementFromPoint = original;
      spy.mockRestore();
    }
  });

  it('왼쪽 단추가 떨어진(buttons 0) pointermove 는 끌기 끝 — 그때까지의 범위로 한 번', () => {
    const { onPaint } = draw();
    fireEvent.pointerDown(cell(3), mouse);
    fireEvent.pointerMove(cell(5), mouse);
    fireEvent.pointerMove(cell(8), { pointerType: 'mouse', buttons: 0 });
    expect(onPaint).toHaveBeenCalledTimes(1);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 3, to: 5 });
    fireEvent.pointerMove(cell(9), mouse);
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledTimes(1);
  });
});

// 밴드 TRP3 ② N2(디자인 6c 재대조): 범례·「n~m쪽을 보고 있어요」는 400 12(caption-03, 500 의 caption-02 아님).
describe('PageGrid 글 꼴 · TRP3 ②', () => {
  it('「1~40쪽을 보고 있어요」 줄과 범례는 caption-03', () => {
    draw();
    render(<PageGridLegend />);
    for (const id of ['grid-viewing', 'grid-legend']) {
      const classes = screen.getByTestId(id).className.split(/\s+/);
      expect(classes, id).toContain('text-style-pre-caption-03');
      expect(classes, id).not.toContain('text-style-pre-caption-02');
    }
    expect(screen.getByTestId('grid-viewing').textContent).toContain(
      TR_TEXT.grid.viewing(1, 40),
    );
  });
});

// 밴드 TRP4 ②-12 N2(디자인 6c TRP3 재대조): 「쪽을 누르면…」 줄은 400 12(caption-03), 500 의 caption-02 아님.
describe('PageGrid 누름 안내 줄 · TRP4', () => {
  it('grid-note 는 caption-03', () => {
    render(<PageGridLegend />);
    const classes = screen.getByTestId('grid-note').className.split(/\s+/);
    expect(classes).toContain('text-style-pre-caption-03');
    expect(classes).not.toContain('text-style-pre-caption-02');
  });
});

// 밴드 TRW9: PDF 입력의 칸 썸네일. 칸 안의 그림만 바뀌고 칸 수·이름·끌기·누름은 그대로다. 안 주면 워드 칸 DOM 그대로.
describe('PageGrid 썸네일 · TRW9', () => {
  const flush = () => act(async () => {});
  const canvases = () => document.querySelectorAll('canvas');
  const frames = () => document.querySelectorAll('[data-thumb-frame]');
  const canvasOf = (page: number) => cell(page).querySelector('canvas')!;
  const labels = () =>
    [...cells()].map((one) => one.getAttribute('aria-label'));

  /** 가짜 연 PDF(그리기는 곧 끝남, fail 쪽은 거절). 그린 쪽 번호를 남긴다. */
  function ready(fail: readonly number[] = []) {
    const drawn: number[] = [];
    const thumbs: LoadedPdf = {
      state: 'ready',
      pdf: {
        renderPage: (page) => {
          drawn.push(page);
          return {
            done:
              fail.includes(page) ?
                Promise.reject(new Error('지어낸 그리기 실패'))
              : Promise.resolve(),
            cancel() {},
          };
        },
        close() {},
      },
    };
    return { thumbs, drawn };
  }

  it('thumbs 없음: 캔버스·틀·data-pdf-state 0, 칸은 빈 쪽 모양 그대로', () => {
    draw({ pageCount: 3 });
    expect(canvases()).toHaveLength(0);
    expect(frames()).toHaveLength(0);
    expect(screen.getByTestId('page-grid').hasAttribute('data-pdf-state')).toBe(
      false,
    );
    expect(cell(1).querySelector('span')!.className).toContain('aspect-[3/4]');
  });

  it('ready · 45쪽: 보이는 칸만 그린다(1~40) · [더 보기] → 45', async () => {
    const { thumbs, drawn } = ready();
    draw({ pageCount: 45, thumbs });
    await flush();
    expect(canvases()).toHaveLength(40);
    expect(drawn).toEqual(Array.from({ length: 40 }, (_, i) => i + 1));
    expect(screen.getByTestId('page-grid').getAttribute('data-pdf-state')).toBe(
      'ready',
    );
    fireEvent.click(screen.getByRole('button', { name: /^더 보기/ }));
    await flush();
    expect(canvases()).toHaveLength(45);
    expect(drawn).toHaveLength(45);
  });

  it('ready: 그림 위 끌기 3→7 → onPaint(고른 파트, 3~7) 한 번, 끄는 동안 칠함', async () => {
    const { thumbs } = ready();
    const { onPaint } = draw({ thumbs });
    await flush();
    fireEvent.pointerDown(canvasOf(3), mouse);
    fireEvent.pointerMove(canvasOf(7), mouse);
    expect(cell(5).getAttribute('data-parts')).toBe('story');
    fireEvent.pointerUp(window, mouse);
    expect(onPaint).toHaveBeenCalledTimes(1);
    expect(onPaint).toHaveBeenCalledWith('story', { from: 3, to: 7 });
  });

  it('ready: Enter·터치 톡 = 누름', async () => {
    const { thumbs } = ready();
    const { onPaint } = draw({ thumbs });
    await flush();
    fireEvent.keyDown(cell(5), { key: 'Enter' });
    expect(onPaint).toHaveBeenLastCalledWith('story', { from: 5, to: 5 });
    fireEvent.pointerDown(canvasOf(6), { pointerType: 'touch', button: 0 });
    fireEvent.click(canvasOf(6), { detail: 1 });
    expect(onPaint).toHaveBeenCalledTimes(2);
    expect(onPaint).toHaveBeenLastCalledWith('story', { from: 6, to: 6 });
  });

  it('ready: 겹친 쪽 data-overlap·파트 점 · 칠한 칸의 틀에 그 파트 색', async () => {
    const { thumbs } = ready();
    draw({
      thumbs,
      ranges: {
        ceo: { from: 1, to: 2 },
        story: { from: 2, to: 3 },
        general: null,
      },
    });
    await flush();
    expect(cell(2).getAttribute('data-overlap')).toBe('true');
    expect(cell(2).querySelectorAll('[data-part-dot]')).toHaveLength(2);
    const frame = cell(1).querySelector('[data-thumb-frame]')!.className;
    for (const name of PART_LOOK.ceo.frame.split(' '))
      expect(frame).toContain(name);
  });

  it.each<[string, LoadedPdf]>([
    ['loading', { state: 'loading' }],
    ['error', { state: 'error', message: '지어낸 열기 실패' }],
  ])('%s: 칸 수·이름 그대로, 캔버스 0, 누름 그대로', (state, thumbs) => {
    draw({ pageCount: 3 });
    const before = labels();
    cleanup();
    const { onPaint } = draw({ pageCount: 3, thumbs });
    expect(screen.getByTestId('page-grid').getAttribute('data-pdf-state')).toBe(
      state,
    );
    expect(cells()).toHaveLength(3);
    expect(labels()).toEqual(before);
    expect(canvases()).toHaveLength(0);
    expect(cell(1).querySelector('span')!.className).toContain(
      'aspect-[1/1.414]',
    );
    fireEvent.keyDown(cell(2), { key: 'Enter' });
    expect(onPaint).toHaveBeenCalledWith('story', { from: 2, to: 2 });
  });

  it('한 쪽 그리기 실패: 그 칸은 남고 글 0', async () => {
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { thumbs } = ready([2]);
    draw({ pageCount: 3, thumbs });
    await flush();
    expect(canvasOf(2).getAttribute('data-render-state')).toBe('error');
    expect(cell(2).getAttribute('data-page')).toBe('2');
    expect(cell(2).textContent).toBe('2');
    quiet.mockRestore();
  });
});

describe('PageGrid 썸네일 상자 비율 · TRW10', () => {
  const flush = () => act(async () => {});
  const frameOf = (page: number) =>
    cell(page).querySelector('[data-thumb-frame]')!;

  function ready(fail: readonly number[] = []): LoadedPdf {
    return {
      state: 'ready',
      pdf: {
        renderPage: (page) => ({
          done:
            fail.includes(page) ?
              Promise.reject(new Error('지어낸 그리기 실패'))
            : Promise.resolve(),
          cancel() {},
        }),
        close() {},
      },
    };
  }

  it('ready: 모든 틀이 비율 고정 상자 · 캔버스는 상자를 채움', async () => {
    draw({ pageCount: 3, thumbs: ready() });
    await flush();
    const frames = document.querySelectorAll('[data-thumb-frame]');
    expect(frames).toHaveLength(3);
    for (const frame of frames) {
      expect(frame.className).toContain('aspect-[1/1.414]');
      expect(frame.className).toContain('w-full');
      const canvas = frame.querySelector('canvas')!;
      for (const name of [
        '!h-full',
        '!w-full',
        'object-contain',
        'mix-blend-multiply',
      ])
        expect(canvas.className).toContain(name);
    }
  });

  it('한 쪽 그리기 실패: 그 칸만 회색 상자 · 틀 글 0 · 칸 수·data-page 그대로', async () => {
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => {});
    draw({ pageCount: 3, thumbs: ready([2]) });
    await flush();
    expect(document.querySelectorAll('[data-thumb-failed]')).toHaveLength(1);
    expect(frameOf(2).querySelector('[data-thumb-failed]')).not.toBeNull();
    expect(frameOf(2).textContent).toBe('');
    expect(frameOf(2).className).toContain('aspect-[1/1.414]');
    expect(cells()).toHaveLength(3);
    expect(cell(2).getAttribute('data-page')).toBe('2');
    quiet.mockRestore();
  });

  it.each<[string, LoadedPdf]>([
    ['loading', { state: 'loading' }],
    ['error', { state: 'error', message: '지어낸 열기 실패' }],
  ])('%s(thumbs 있음): 빈 종이도 같은 비율 · 캔버스 0', (_state, thumbs) => {
    draw({ pageCount: 3, thumbs });
    expect(cell(1).querySelector('span')!.className).toContain(
      'aspect-[1/1.414]',
    );
    expect(document.querySelectorAll('canvas')).toHaveLength(0);
  });

  it('thumbs 없음(워드): 빈 종이는 3/4 그대로', () => {
    draw({ pageCount: 3 });
    const paper = cell(1).querySelector('span')!.className;
    expect(paper).toContain('aspect-[3/4]');
    expect(paper).not.toContain('aspect-[1/1.414]');
  });

  it('칠한 칸(CEO 3~7): 틀에 비율과 파트 색 둘 다', async () => {
    draw({
      thumbs: ready(),
      ranges: { ceo: { from: 3, to: 7 }, story: null, general: null },
    });
    await flush();
    const frame = frameOf(5).className;
    expect(frame).toContain('aspect-[1/1.414]');
    for (const name of PART_LOOK.ceo.frame.split(' '))
      expect(frame).toContain(name);
  });
});
