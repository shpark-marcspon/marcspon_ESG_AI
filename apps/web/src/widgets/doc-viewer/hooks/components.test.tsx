// @vitest-environment jsdom
// 모양 없는 컴포넌트를 모양 없이 그려 본다. 클래스 이름도 CSS 도 주지 않는다.
// 그래도 (1) 쪽과 상자가 제자리에 놓이고(인라인 style) (2) 누르기가 훅에 닿고 (3) 상태 표시(data-*)가 맞아야 한다.
// 실제 브라우저에서 상자가 글자 위에 놓이는지는 e2e/ 가 본다.
import { act, cleanup, fireEvent, render } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { PAGE_GAP, pageOffsets } from '../model/index.ts';
import type {
  HighlightMode,
  ReviewState,
  ViewerInput,
} from '../model/index.ts';
import {
  makeLinesInput,
  makeOverlapInput,
  makeTwoDocInput,
  TEST_PAGES as pages,
} from '../model/testing.ts';
import { HighlightOverlay } from './HighlightOverlay.tsx';
import type { HighlightOverlayProps } from './HighlightOverlay.tsx';
import { PageCanvas } from './PageCanvas.tsx';
import { PageStack } from './PageStack.tsx';
import type { PdfHandle } from './pdfBackend.ts';
import { useDocViewer } from './useDocViewer.ts';
import type { DocViewer } from './useDocViewer.ts';
import { usePaneView } from './usePaneView.ts';
import type { PaneView } from './usePaneView.ts';

afterEach(cleanup);

const NO_REVIEWS: ReadonlyMap<string, ReviewState> = new Map();
type Look = Pick<
  HighlightOverlayProps,
  'classNames' | 'pieceProps' | 'renderCount'
>;

/** 훅 둘과 헤드리스 컴포넌트 둘만으로 만든 가장 작은 화면. 모양이 하나도 없다. 훅이 돌려준 것은 밖에서 읽을 수 있게 내놓는다. */
function setup(
  input: ViewerInput,
  options: {
    mode?: HighlightMode;
    look?: Look;
    stackClassNames?: { scroller?: string; stack?: string; page?: string };
  } = {},
) {
  const handles: { viewer?: DocViewer; panes: Map<string, PaneView> } = {
    panes: new Map(),
  };
  function Pane({
    documentId,
    viewer,
  }: {
    documentId: string;
    viewer: DocViewer;
  }) {
    const doc = input.documents.find((d) => d.id === documentId)!;
    const pane = usePaneView(doc.pages);
    handles.panes.set(documentId, pane);
    return (
      <section data-document-id={documentId}>
        <PageStack
          pane={pane}
          reveal={viewer.revealFor(documentId)}
          classNames={options.stackClassNames}
          notice={<p data-testid="notice">안내</p>}
          renderPage={(pageNumber, page) => (
            <HighlightOverlay
              highlights={viewer.highlightsOn(documentId, pageNumber)}
              page={page}
              scale={pane.scale}
              rotation={pane.rotation}
              draw={viewer.draw}
              onPick={viewer.pick}
              {...options.look}
            />
          )}
        />
      </section>
    );
  }
  function Bare() {
    const viewer = useDocViewer({
      input,
      reviews: NO_REVIEWS,
      highlightMode: options.mode,
    });
    handles.viewer = viewer;
    return (
      <div>
        {input.documents.map((doc) => (
          <Pane key={doc.id} documentId={doc.id} viewer={viewer} />
        ))}
      </div>
    );
  }
  const view = render(<Bare />);
  const section = (id: string) =>
    view.container.querySelector<HTMLElement>(`[data-document-id="${id}"]`)!;
  const scroller = (id: string) => section(id).firstElementChild as HTMLElement;
  const pageElements = (id: string) => [
    ...section(id).querySelectorAll<HTMLElement>('[data-page]'),
  ];
  const pieces = (id: string) => [
    ...section(id).querySelectorAll<HTMLElement>('[data-highlight-ids]'),
  ];
  const rect = (el: HTMLElement) =>
    [el.style.left, el.style.top, el.style.width, el.style.height].map(
      (value) => Number.parseFloat(value),
    );
  /** 조각들을 글로: 묶인 강조 id 와 표시. */
  const boxes = (id: string) =>
    pieces(id)
      .map(
        (el) =>
          `${el.dataset.highlightIds}${el.dataset.selected === 'true' ? ' [고름]' : ''}${el.dataset.pointed === 'true' ? ' [가리킴]' : ''}`,
      )
      .sort();
  return {
    view,
    viewer: () => handles.viewer!,
    pane: (id: string) => handles.panes.get(id)!,
    section,
    scroller,
    pageElements,
    pieces,
    rect,
    boxes,
  };
}

describe('PageStack: 쪽 쌓기와 보이는 쪽만 그리기', () => {
  it('클래스 이름을 주지 않으면 어느 요소에도 class 가 없다. 그래도 스크롤 상자·쌓는 판·쪽이 스스로 자리를 갖는다', () => {
    const { view, scroller, pageElements } = setup(makeTwoDocInput());
    expect(view.container.querySelectorAll('[class]')).toHaveLength(0);
    expect(scroller('a').style.overflow).toBe('auto');
    const stack = scroller('a').lastElementChild as HTMLElement;
    expect(stack.style.position).toBe('relative');
    expect(Number.parseFloat(stack.style.height)).toBe(5 * 800 + 6 * PAGE_GAP);
    expect(Number.parseFloat(stack.style.minWidth)).toBe(600 + 2 * PAGE_GAP);
    const first = pageElements('a')[0]!;
    expect([
      first.style.position,
      first.style.left,
      first.style.right,
      first.style.margin,
    ]).toEqual(['absolute', '0px', '0px', '0px auto']);
    expect([first.style.top, first.style.width, first.style.height]).toEqual([
      `${PAGE_GAP}px`,
      '600px',
      '800px',
    ]);
  });

  it('보이는 쪽과 그 앞뒤만 DOM 에 있고, 쪽마다 위에서부터의 거리가 셈한 값이다', () => {
    const { viewer, pageElements } = setup(makeTwoDocInput());
    expect(pageElements('a').map((el) => el.dataset.page)).toEqual(['1', '2']);
    act(() => viewer().select('2')); // A 의 4쪽으로
    expect(pageElements('a').map((el) => el.dataset.page)).toEqual([
      '3',
      '4',
      '5',
    ]);
    expect(
      pageElements('a').map((el) => Number.parseFloat(el.style.top)),
    ).toEqual(pageOffsets(pages, 1).slice(2, 5));
  });

  it('받은 클래스 이름과 안내를 제자리에 붙인다', () => {
    const { scroller, pageElements } = setup(makeTwoDocInput(), {
      stackClassNames: {
        scroller: 'x-scroller',
        stack: 'x-stack',
        page: 'x-page',
      },
    });
    expect(scroller('a').className).toBe('x-scroller');
    expect((scroller('a').lastElementChild as HTMLElement).className).toBe(
      'x-stack',
    );
    expect(pageElements('a')[0]!.className).toBe('x-page');
    // 안내는 스크롤 상자 안, 쌓는 판 앞에 온다.
    expect(scroller('a').firstElementChild!.getAttribute('data-testid')).toBe(
      'notice',
    );
  });
});

describe('PageStack: 스크롤(훅이 말하고 컴포넌트가 간다)', () => {
  it('훅이 쪽 이동을 말하면 스크롤 상자를 그 높이로 옮긴다', () => {
    const { pane, scroller } = setup(makeTwoDocInput());
    act(() => pane('a').goToPage(3));
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[2]! - PAGE_GAP);
    // 다른 문서 칸은 그대로다.
    expect(scroller('b').scrollTop).toBe(0);
  });

  it('사람이 다른 데로 스크롤한 뒤 같은 쪽으로 다시 가라고 하면 다시 간다(높이가 같아도 요청은 새것이다)', () => {
    const { pane, scroller } = setup(makeTwoDocInput());
    act(() => pane('a').goToPage(3));
    const there = scroller('a').scrollTop;
    scroller('a').scrollTop = 40;
    fireEvent.scroll(scroller('a'));
    act(() => pane('a').goToPage(3));
    expect(scroller('a').scrollTop).toBe(there);
  });

  it('배율을 바꾸면 보던 자리를 지키는 높이로 옮기고, 쪽의 크기가 새 배율이다', () => {
    const { pane, scroller, pageElements } = setup(makeTwoDocInput());
    act(() => pane('a').goToPage(2));
    act(() => pane('a').zoomIn());
    expect(scroller('a').scrollTop).toBe(
      pageOffsets(pages, 1.25)[1]! - PAGE_GAP,
    );
    expect([
      pageElements('a')[0]!.style.width,
      pageElements('a')[0]!.style.height,
    ]).toEqual(['750px', '1000px']);
  });

  it('사람이 스크롤하면 훅에 알린다(지금 쪽과 그릴 쪽이 따라간다)', () => {
    const { pane, scroller, pageElements } = setup(makeTwoDocInput());
    scroller('a').scrollTop = pageOffsets(pages, 1)[4]!;
    fireEvent.scroll(scroller('a'));
    expect(pane('a').currentPage).toBe(5);
    expect(pageElements('a').map((el) => el.dataset.page)).toEqual(['4', '5']);
  });

  it('항목을 고르면 문서 칸마다 그 강조의 자리로 간다(세로와 가로). 같은 항목을 다시 고르면 다시 간다', () => {
    const { viewer, scroller, pane } = setup(makeTwoDocInput());
    act(() => viewer().select('2'));
    // jsdom 은 화면 크기가 0 이라: 세로는 상자의 윗변이 화면 맨 위, 가로는 쪽의 왼쪽 틈 + 상자의 가운데.
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[3]! + 300);
    expect(scroller('a').scrollLeft).toBe(PAGE_GAP + 100);
    expect(scroller('b').scrollTop).toBe(pageOffsets(pages, 1)[0]! + 300);
    expect(pane('a').currentPage).toBe(4);

    scroller('a').scrollTop = 0;
    fireEvent.scroll(scroller('a'));
    act(() => viewer().select('2'));
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[3]! + 300);
  });

  it('가리키기만 하거나 배율을 바꾸는 것으로는 강조로 끌려가지 않는다', () => {
    const { viewer, scroller, pane } = setup(makeTwoDocInput());
    act(() => viewer().point('hover', '2'));
    expect(scroller('a').scrollTop).toBe(0);
    act(() => viewer().select('2'));
    act(() => pane('a').goToPage(1));
    act(() => pane('a').zoomIn());
    // 1쪽의 맨 위에 그대로다(골라 둔 강조가 있는 4쪽으로 돌아가지 않는다).
    expect(scroller('a').scrollTop).toBe(0);
  });

  it('폭 맞춤은 스크롤 상자의 지금 폭을 읽어 쓴다', () => {
    const { pane, scroller } = setup(makeTwoDocInput());
    Object.defineProperty(scroller('a'), 'clientWidth', {
      configurable: true,
      value: 1000,
    });
    act(() => pane('a').fitWidth());
    expect(pane('a').scale).toBe(1.6);
  });
});

describe('HighlightOverlay: 강조를 제자리에 얹기', () => {
  it('모양을 하나도 주지 않아도 조각이 입력의 상자 자리에 놓인다(판은 쪽을 꽉 채운다)', () => {
    const { section, pieces, rect } = setup(makeOverlapInput());
    const layer = section('b').querySelector<HTMLElement>('[data-mode]')!;
    expect([layer.style.position, layer.style.inset]).toEqual([
      'absolute',
      '0px',
    ]);
    expect(layer.dataset.mode).toBe('outline');
    // 큰 상자가 먼저 오는 차례는 넓이가 같으면 입력의 차례다.
    expect(
      pieces('b').map((el) => [el.dataset.highlightIds, rect(el)]),
    ).toEqual([
      ['1-b 4-b', [50, 50, 100, 30]],
      ['5-b', [50, 300, 100, 30]],
    ]);
    for (const el of pieces('b'))
      expect([el.tagName, el.style.position, el.style.boxSizing]).toEqual([
        'BUTTON',
        'absolute',
        'border-box',
      ]);
  });

  it('배율과 회전이 바뀌면 조각의 자리가 따라간다', () => {
    const { pane, pieces, rect } = setup(makeOverlapInput());
    act(() => pane('b').zoomIn());
    expect(rect(pieces('b')[1]!)).toEqual([62.5, 375, 125, 37.5]);
  });

  it('고른 강조가 든 문단 전체의 상자(context)도 입력의 자리에 놓이고, 배율이 바뀌면 따라간다. 누르기를 받지 않는다', () => {
    const { viewer, pane, section, rect } = setup(makeLinesInput(), {
      look: { classNames: { context: 'x-context' } },
    });
    const contexts = () => [
      ...section('a').querySelectorAll<HTMLElement>('.x-context'),
    ];
    expect(contexts()).toEqual([]);
    // 항목 u: 2쪽의 문단 [50, 500, 550, 520] 안의 좁힌 자리 하나.
    act(() => viewer().select('u'));
    expect(contexts().map(rect)).toEqual([[50, 500, 500, 20]]);
    expect(contexts()[0]!.style.pointerEvents).toBe('none');
    act(() => pane('a').zoomIn());
    expect(contexts().map(rect)).toEqual([[62.5, 625, 625, 25]]);
  });

  it('상태 표시: 고른 것은 data-selected, 가리킨 것은 data-pointed. 좁힌 자리로 그린 것은 data-narrowed', () => {
    const { viewer, boxes, pieces } = setup(makeOverlapInput());
    expect(boxes('b')).toEqual(['1-b 4-b', '5-b']);
    act(() => viewer().select('5'));
    act(() => viewer().point('hover', '4'));
    expect(boxes('b')).toEqual(['1-b 4-b [가리킴]', '5-b [고름]']);
    expect(pieces('b').map((el) => el.dataset.narrowed)).toEqual([
      'false',
      'false',
    ]);
  });

  it('조각을 누르면 훅의 pick 에 닿는다: 겹친 묶음은 누를 때마다 다음 항목으로 돈다', () => {
    const { viewer, pieces } = setup(makeOverlapInput());
    fireEvent.click(pieces('b')[0]!);
    expect(viewer().selectedItemId).toBe('1');
    fireEvent.click(pieces('b')[0]!);
    expect(viewer().selectedItemId).toBe('4');
    fireEvent.click(pieces('b')[1]!);
    expect(viewer().selectedItemId).toBe('5');
  });

  it('보기 방식은 판의 data-mode 로만 알린다. 「고른 것만」은 고른 것과 가리킨 것만 DOM 에 둔다', () => {
    const { viewer, section, boxes } = setup(makeOverlapInput(), {
      mode: 'selected',
    });
    expect(
      section('b').querySelector<HTMLElement>('[data-mode]')!.dataset.mode,
    ).toBe('selected');
    expect(boxes('b')).toEqual([]);
    act(() => viewer().select('5'));
    expect(boxes('b')).toEqual(['5-b [고름]']);
  });

  it('범례에서 끈 종류는 그리지 않고, 묶음과 겹친 개수는 남은 것만 센다', () => {
    const renderCount = vi.fn((count: number) => <b>{count}</b>);
    const { viewer, boxes } = setup(makeOverlapInput(), {
      look: { renderCount },
    });
    expect(renderCount).toHaveBeenLastCalledWith(
      2,
      expect.objectContaining({ highlightIds: ['1-b', '4-b'] }),
    );
    renderCount.mockClear();
    act(() => viewer().toggleKind('mismatch'));
    expect(boxes('b')).toEqual(['1-b', '5-b']);
    expect(renderCount).not.toHaveBeenCalled();
  });

  it('여러 줄 강조: 줄마다 조각 하나가 한 틀 안에 들고, 표시는 조각마다 같다. Tab 은 첫 조각에만 선다', () => {
    const { viewer, pieces, rect, section } = setup(makeLinesInput());
    act(() => viewer().select('u')); // 2쪽으로
    const drawn = pieces('a').filter(
      (el) => el.dataset.highlightIds === 's-a t-a',
    );
    expect(drawn.map(rect)).toEqual([
      [300, 400, 200, 12],
      [50, 416, 170, 12],
    ]);
    expect(new Set(drawn.map((el) => el.parentElement)).size).toBe(1);
    expect(drawn.map((el) => el.getAttribute('tabindex'))).toEqual([
      null,
      '-1',
    ]);
    expect(drawn.map((el) => el.getAttribute('aria-hidden'))).toEqual([
      null,
      'true',
    ]);
    expect(drawn.map((el) => el.dataset.narrowed)).toEqual(['true', 'true']);
    // 둘째 줄 조각을 눌러도 그 항목이 골라지고, 두 조각이 다 골라진 표시를 갖는다.
    fireEvent.click(drawn[1]!);
    expect(viewer().selectedItemId).toBe('s');
    expect(
      pieces('a')
        .filter((el) => el.dataset.highlightIds === 's-a t-a')
        .map((el) => el.dataset.selected),
    ).toEqual(['true', 'true']);
    // 고른 강조가 든 문단 전체(context)는 누를 수 없는 상자 하나다.
    const context = [
      ...section('a').querySelectorAll<HTMLElement>('[data-mode] > div'),
    ].filter((el) => el.style.pointerEvents === 'none');
    expect(context.map(rect)).toEqual([[50, 380, 500, 70]]);
  });

  it('좁힌 자리를 끄면 문단 전체 상자 하나로 그린다', () => {
    const { viewer, pieces, rect } = setup(makeLinesInput());
    act(() => viewer().select('u'));
    act(() => viewer().setUseInnerBox(false));
    expect(
      pieces('a')
        .filter((el) => el.dataset.highlightIds === 's-a t-a')
        .map(rect),
    ).toEqual([[50, 380, 500, 70]]);
  });
});

describe('HighlightOverlay: 모양을 입히는 길', () => {
  it('classNames 는 판·틀·context 에, pieceProps 는 조각마다 붙는다. 겹친 개수는 renderCount 가 마지막 조각에 한 번 그린다', () => {
    const look: Look = {
      classNames: { layer: 'x-layer', group: 'x-group', context: 'x-context' },
      pieceProps: (group) => ({
        className: `x-piece x-${group.kind ?? 'mixed'}`,
        style: { color: 'red' },
        title: `강조 ${group.highlightIds.length}개`,
      }),
      renderCount: (count) => <b>{count}</b>,
    };
    const { viewer, section, pieces } = setup(makeLinesInput(), { look });
    act(() => viewer().select('u'));
    expect(section('a').querySelector('[data-mode]')!.className).toBe(
      'x-layer',
    );
    const drawn = pieces('a').filter(
      (el) => el.dataset.highlightIds === 's-a t-a',
    );
    expect(drawn.map((el) => el.className)).toEqual([
      'x-piece x-mixed',
      'x-piece x-mixed',
    ]);
    expect(drawn[0]!.parentElement!.className).toBe('x-group');
    expect(drawn.map((el) => [el.style.color, el.title])).toEqual([
      ['red', '강조 2개'],
      ['red', '강조 2개'],
    ]);
    expect(drawn.map((el) => el.innerHTML)).toEqual(['', '<b>2</b>']);
    expect(
      pieces('a').find((el) => el.dataset.highlightIds === 'u-a')!.className,
    ).toBe('x-piece x-note');
    expect(section('a').querySelector('.x-context')).not.toBeNull();
  });

  it('pieceProps 의 style 이 자리와 크기를 덮어쓰지 못한다', () => {
    const look: Look = {
      pieceProps: () => ({
        style: { position: 'static', left: 1, top: 2, width: 3, height: 4 },
      }),
    };
    const { pieces, rect } = setup(makeOverlapInput(), { look });
    expect(pieces('b')[1]!.style.position).toBe('absolute');
    expect(rect(pieces('b')[1]!)).toEqual([50, 300, 100, 30]);
  });
});

describe('PageCanvas', () => {
  const handle = (done: Promise<void>, log: string[] = []): PdfHandle => ({
    renderPage: (pageNumber, _canvas, scale, rotation) => {
      log.push(`render ${pageNumber} ${scale} ${rotation}`);
      return {
        done,
        cancel: () => void log.push(`cancel ${pageNumber} ${scale}`),
      };
    },
    close: () => undefined,
  });

  it('다 그려지면 data-render-state 가 done 이다. 캔버스는 스스로 display: block 만 갖고, 받은 클래스 이름을 붙인다', async () => {
    const view = render(
      <PageCanvas
        pdf={handle(Promise.resolve())}
        pageNumber={1}
        scale={1}
        rotation={0}
        className="x-canvas"
      />,
    );
    const canvas = () => view.container.querySelector('canvas')!;
    expect(canvas().dataset.renderState).toBe('rendering');
    await act(async () => undefined);
    expect(canvas().dataset.renderState).toBe('done');
    expect([canvas().style.display, canvas().className]).toEqual([
      'block',
      'x-canvas',
    ]);
  });

  it('배율이 바뀌면 그리던 것을 취소하고 캔버스를 새로 만들어 다시 그린다', async () => {
    const log: string[] = [];
    const pdf = handle(Promise.resolve(), log);
    const view = render(
      <PageCanvas pdf={pdf} pageNumber={2} scale={1} rotation={0} />,
    );
    const before = view.container.querySelector('canvas');
    view.rerender(
      <PageCanvas pdf={pdf} pageNumber={2} scale={1.5} rotation={0} />,
    );
    await act(async () => undefined);
    expect(view.container.querySelector('canvas')).not.toBe(before);
    expect(log).toEqual(['render 2 1 0', 'cancel 2 1', 'render 2 1.5 0']);
  });

  it('그리지 못하면 data-render-state 가 error 이고, 받은 errorFallback 을 보인다', async () => {
    const quiet = vi
      .spyOn(console, 'error')
      .mockImplementation(() => undefined);
    const failed = Promise.reject(new Error('깨진 쪽'));
    const view = render(
      <PageCanvas
        pdf={handle(failed)}
        pageNumber={1}
        scale={1}
        rotation={0}
        errorFallback={<p>못 그렸다</p>}
      />,
    );
    await act(async () => undefined);
    expect(view.container.querySelector('canvas')!.dataset.renderState).toBe(
      'error',
    );
    expect(view.container.textContent).toBe('못 그렸다');
    quiet.mockRestore();
  });

  it('문서(pdf)를 갈아 끼우면 앞의 그리기를 취소하고 새 문서로 그린다. 뒤늦게 끝나거나 실패한 앞의 그리기는 상태를 바꾸지 않는다', async () => {
    const quiet = vi
      .spyOn(console, 'error')
      .mockImplementation(() => undefined);
    const log: string[] = [];
    /** 그리기가 끝나는 때를 밖에서 정하는 가짜 문서. */
    function pending(name: string) {
      let settle!: { resolve(): void; reject(error: Error): void };
      const done = new Promise<void>(
        (resolve, reject) => (settle = { resolve, reject }),
      );
      const pdf: PdfHandle = {
        renderPage: () => (
          log.push(`render ${name}`),
          { done, cancel: () => void log.push(`cancel ${name}`) }
        ),
        close: () => undefined,
      };
      return { pdf, settle };
    }
    const [first, second, third] = [
      pending('첫째'),
      pending('둘째'),
      pending('셋째'),
    ];
    const view = render(
      <PageCanvas
        pdf={first.pdf}
        pageNumber={1}
        scale={1}
        rotation={0}
        errorFallback={<p>못 그렸다</p>}
      />,
    );
    const state = () =>
      view.container.querySelector('canvas')!.dataset.renderState;

    view.rerender(
      <PageCanvas
        pdf={second.pdf}
        pageNumber={1}
        scale={1}
        rotation={0}
        errorFallback={<p>못 그렸다</p>}
      />,
    );
    expect(log).toEqual(['render 첫째', 'cancel 첫째', 'render 둘째']);
    // 취소된 첫째의 그리기가 (오류 없이) 풀린다. 둘째는 아직 그리는 중이다.
    await act(async () => first.settle.resolve());
    expect(state()).toBe('rendering');
    await act(async () => second.settle.resolve());
    expect(state()).toBe('done');

    // 문서를 두 번 더 갈았다. 가운데 것은 다 그리기 전에 밀려났고, 마지막 것이 다 그려진 뒤에야 실패를 알린다.
    const late = pending('늦은 것');
    view.rerender(
      <PageCanvas
        pdf={late.pdf}
        pageNumber={1}
        scale={1}
        rotation={0}
        errorFallback={<p>못 그렸다</p>}
      />,
    );
    view.rerender(
      <PageCanvas
        pdf={third.pdf}
        pageNumber={1}
        scale={1}
        rotation={0}
        errorFallback={<p>못 그렸다</p>}
      />,
    );
    await act(async () => third.settle.resolve());
    await act(async () =>
      late.settle.reject(new Error('이미 떠난 문서의 오류')),
    );
    expect(state()).toBe('done');
    expect(view.container.textContent).toBe('');
    quiet.mockRestore();
  });

  // 떠난 뒤의 거절(취소·문서 닫힘 탓)은 찍지 않는다 — sid:MARC-ISSUE-419
  /** 그릴 때마다 끝을 밖에서 정하는 일을 하나씩 만드는 가짜 문서. jobs[n] 이 n 번째 그리기다. */
  function deferredHandle() {
    const jobs: { reject(error: Error): void }[] = [];
    const pdf: PdfHandle = {
      renderPage: () => {
        let reject!: (error: Error) => void;
        const done = new Promise<void>((_, no) => (reject = no));
        jobs.push({ reject });
        return { done, cancel: () => undefined };
      },
      close: () => undefined,
    };
    return { pdf, jobs };
  }

  it('화면을 떠난 뒤 그리기가 거절되면(Transport destroyed) 아무것도 찍지 않는다', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { pdf, jobs } = deferredHandle();
    const view = render(
      <PageCanvas pdf={pdf} pageNumber={1} scale={1} rotation={0} />,
    );
    view.unmount();
    await act(async () => jobs[0]!.reject(new Error('Transport destroyed')));
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it('배율이 바뀐 뒤 앞 그리기가 거절되어도 찍지 않고, 새 그리기는 그리는 중 그대로다', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { pdf, jobs } = deferredHandle();
    const view = render(
      <PageCanvas pdf={pdf} pageNumber={1} scale={1} rotation={0} />,
    );
    view.rerender(
      <PageCanvas pdf={pdf} pageNumber={1} scale={2} rotation={0} />,
    );
    await act(async () => jobs[0]!.reject(new Error('Transport destroyed')));
    expect(spy).not.toHaveBeenCalled();
    expect(view.container.querySelector('canvas')!.dataset.renderState).toBe(
      'rendering',
    );
    spy.mockRestore();
  });

  it('살아 있는 그리기가 실패하면 그대로 찍고 data-render-state 가 error 다', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { pdf, jobs } = deferredHandle();
    const view = render(
      <PageCanvas pdf={pdf} pageNumber={3} scale={1} rotation={0} />,
    );
    await act(async () => jobs[0]!.reject(new Error('깨진 쪽')));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0]![0]).toContain('페이지를 그리지 못했다');
    expect(view.container.querySelector('canvas')!.dataset.renderState).toBe(
      'error',
    );
    spy.mockRestore();
  });
});
