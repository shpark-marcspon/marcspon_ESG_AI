// @vitest-environment jsdom
// 같은 동작 테스트를 두 화면(본 화면, 둘째 화면)에 그대로 돌린다.
// 둘 다 통과하면: 동작은 헤드리스 층과 업무 로직에 있고, 화면은 바꿔 끼울 수 있다.
// 화면을 새로 만들 때 이 테스트가 요구하는 것은 이름표뿐이다(클래스 이름은 하나도 보지 않는다):
//   뿌리 = [data-layout] (키보드를 받는다), 문서 칸 = [data-document-id][data-current-page][data-scale],
//   항목 = [data-item-id][data-selected][data-kind-hidden] 과 그 안의 첫 단추, 그 안의 상태 = [data-status],
//   범례 = [data-kind][aria-pressed], 「고른 것만」 안내 = data-testid="dv-mode-note",
//   그리고 단추·입력의 이름(aria-label 또는 글자): 이전 쪽, 다음 쪽, 확대, 축소, 반려 사유, 확정, 반려, 검토대기로 되돌리기, 좁힌 자리로 보기.
// 쪽([data-page]), 강조의 판([data-mode]), 조각([data-highlight-ids][data-selected][data-pointed])은 헤드리스 컴포넌트가 붙인다.
import type { ComponentType } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import {
  DocumentViewer,
  PAGE_GAP,
  pageOffsets,
  parseViewerInput,
  useReviews,
} from '../../widgets/doc-viewer/index.ts';
import type {
  DocumentViewerProps,
  HighlightMode,
  OpenPdf,
  ViewerInput,
} from '../../widgets/doc-viewer/index.ts';
import { CompactViewer } from './CompactViewer.tsx';

afterEach(cleanup);

const SCREENS: [string, ComponentType<DocumentViewerProps>][] = [
  ['본 화면', DocumentViewer],
  ['둘째 화면', CompactViewer],
];

const fakeOpenPdf: OpenPdf = async () => ({
  renderPage: () => ({ done: Promise.resolve(), cancel: () => undefined }),
  close: () => undefined,
});

const pages = Array.from({ length: 5 }, () => ({ width: 600, height: 800 }));
function parsed(raw: unknown): ViewerInput {
  const result = parseViewerInput(raw);
  if (!result.ok) throw new Error(result.errors.join('\n'));
  return result.input;
}
/** 문서 둘. 항목 1 은 A 1쪽·B 4쪽, 항목 2 는 A 4쪽·B 1쪽, 항목 3 은 A 5쪽에만. */
const twoDocs = () =>
  parsed({
    version: 1,
    documents: [
      { id: 'a', url: 'a.pdf', pages },
      { id: 'b', url: 'b.pdf', pages },
    ],
    highlights: [
      {
        id: '1-a',
        documentId: 'a',
        page: 1,
        box: [50, 50, 150, 80],
        kind: 'match',
      },
      {
        id: '1-b',
        documentId: 'b',
        page: 4,
        box: [50, 50, 150, 80],
        kind: 'match',
      },
      {
        id: '2-a',
        documentId: 'a',
        page: 4,
        box: [50, 300, 150, 330],
        kind: 'mismatch',
      },
      {
        id: '2-b',
        documentId: 'b',
        page: 1,
        box: [50, 300, 150, 330],
        kind: 'mismatch',
      },
      {
        id: '3-a',
        documentId: 'a',
        page: 5,
        box: [50, 300, 150, 330],
        kind: 'unverified',
      },
    ],
    items: [
      {
        id: '1',
        title: '첫째',
        highlightIds: ['1-a', '1-b'],
        review: { status: 'pending' },
      },
      {
        id: '2',
        title: '둘째',
        highlightIds: ['2-a', '2-b'],
        review: { status: 'pending' },
      },
      {
        id: '3',
        title: '셋째',
        highlightIds: ['3-a'],
        review: { status: 'pending' },
      },
    ],
  });
/** 문서 하나. B 의 1쪽 한 칸을 항목 1(일치)과 항목 4(불일치)가 같이 가리킨다. 항목 5 는 따로. */
const overlap = () =>
  parsed({
    version: 1,
    documents: [{ id: 'b', url: 'b.pdf', pages }],
    highlights: [
      {
        id: '1-b',
        documentId: 'b',
        page: 1,
        box: [50, 50, 150, 80],
        kind: 'match',
      },
      {
        id: '4-b',
        documentId: 'b',
        page: 1,
        box: [50, 50, 150, 80],
        kind: 'mismatch',
      },
      {
        id: '5-b',
        documentId: 'b',
        page: 1,
        box: [50, 300, 150, 330],
        kind: 'match',
      },
    ],
    items: [
      {
        id: '1',
        title: '첫째',
        highlightIds: ['1-b'],
        review: { status: 'pending' },
      },
      {
        id: '4',
        title: '넷째',
        highlightIds: ['4-b'],
        review: { status: 'pending' },
      },
      {
        id: '5',
        title: '다섯째',
        highlightIds: ['5-b'],
        review: { status: 'pending' },
      },
    ],
  });
/** A 의 1쪽에 두 줄짜리 문장 강조 s(조각 둘), 조각이 전부 같은 강조 t(다른 종류, 다른 항목), 한 줄짜리 u. */
const lines = () => {
  const twoLines = [
    [300, 400, 500, 412],
    [50, 416, 220, 428],
  ];
  return parsed({
    version: 1,
    documents: [{ id: 'a', url: 'a.pdf', pages }],
    highlights: [
      {
        id: 's-a',
        documentId: 'a',
        page: 1,
        box: [50, 380, 550, 450],
        innerBoxes: twoLines,
        kind: 'sentence',
      },
      {
        id: 't-a',
        documentId: 'a',
        page: 1,
        box: [50, 380, 550, 450],
        innerBoxes: twoLines,
        kind: 'note',
      },
      {
        id: 'u-a',
        documentId: 'a',
        page: 1,
        box: [50, 500, 550, 520],
        innerBox: [60, 500, 90, 512],
        kind: 'note',
      },
    ],
    items: [
      {
        id: 's',
        title: '두 줄 문장',
        highlightIds: ['s-a'],
        review: { status: 'pending' },
      },
      {
        id: 't',
        title: '같은 자리의 다른 항목',
        highlightIds: ['t-a'],
        review: { status: 'pending' },
      },
      {
        id: 'u',
        title: '한 줄',
        highlightIds: ['u-a'],
        review: { status: 'pending' },
      },
    ],
  });
};

describe.each(SCREENS)('문서 뷰어의 동작: %s', (_name, Screen) => {
  function Harness({
    input,
    mode,
  }: {
    input: ViewerInput;
    mode?: HighlightMode;
  }) {
    const reviews = useReviews(input.items);
    return (
      <Screen
        input={input}
        openPdf={fakeOpenPdf}
        reviews={reviews.states}
        onReview={reviews.apply}
        highlightMode={mode}
      />
    );
  }
  async function show(input: ViewerInput, mode?: HighlightMode) {
    const view = render(<Harness input={input} mode={mode} />);
    // 가짜 PDF 가 「열릴」 때까지 한 번 기다린다.
    await act(async () => undefined);
    const root = view.container.querySelector<HTMLElement>('[data-layout]')!;
    const pane = (id: string) =>
      view.container.querySelector<HTMLElement>(`[data-document-id="${id}"]`)!;
    // 스크롤 상자: 쪽을 담은 판의 부모(PageStack 의 구조).
    const scroller = (id: string) =>
      pane(id).querySelector<HTMLElement>('[data-page]')!.parentElement!
        .parentElement!;
    const item = (id: string) =>
      view.container.querySelector<HTMLElement>(`[data-item-id="${id}"]`)!;
    const head = (id: string) => item(id).querySelector<HTMLElement>('button')!;
    const clickItem = (id: string) => fireEvent.click(head(id));
    const selected = () =>
      [
        ...view.container.querySelectorAll<HTMLElement>(
          '[data-item-id][data-selected="true"]',
        ),
      ].map((el) => el.dataset.itemId);
    const pieces = (id: string, ids?: string) => [
      ...pane(id).querySelectorAll<HTMLElement>(
        ids ? `[data-highlight-ids="${ids}"]` : '[data-highlight-ids]',
      ),
    ];
    /** 그 문서 칸에 지금 그려진 조각들: 묶인 강조 id 와 표시 둘. */
    const boxes = (id: string) =>
      pieces(id)
        .map(
          (el) =>
            `${el.dataset.highlightIds}${el.dataset.selected === 'true' ? ' [고름]' : ''}${el.dataset.pointed === 'true' ? ' [가리킴]' : ''}`,
        )
        .sort();
    const rect = (el: HTMLElement) =>
      [el.style.left, el.style.top, el.style.width, el.style.height].map(
        (value) => Number.parseFloat(value),
      );
    const legend = (kind: string) =>
      view.container.querySelector<HTMLElement>(
        `[data-kind="${kind}"][aria-pressed]`,
      )!;
    const status = (id: string) =>
      item(id).querySelector<HTMLElement>('[data-status]')!.dataset.status;
    return {
      view,
      root,
      pane,
      scroller,
      item,
      head,
      clickItem,
      selected,
      pieces,
      boxes,
      rect,
      legend,
      status,
    };
  }

  it('문서가 둘이면 칸이 둘, 하나면 하나다', async () => {
    const two = await show(twoDocs());
    expect(two.root.dataset.layout).toBe('side-by-side');
    expect(
      two.view.container.querySelectorAll('[data-document-id]'),
    ).toHaveLength(2);
    cleanup();
    const one = await show(overlap());
    expect(one.root.dataset.layout).toBe('single');
    expect(
      one.view.container.querySelectorAll('[data-document-id]'),
    ).toHaveLength(1);
  });

  it('항목 → 강조: 항목을 누르면 그 강조가 골라지고, 문서마다 그 쪽으로 간다', async () => {
    const { pane, scroller, clickItem, selected, boxes } =
      await show(twoDocs());
    clickItem('2');
    expect(selected()).toEqual(['2']);
    expect(pane('a').dataset.currentPage).toBe('4');
    expect(pane('b').dataset.currentPage).toBe('1');
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[3]! + 300);
    expect(boxes('a')).toContain('2-a [고름]');
    expect(boxes('b')).toEqual(['2-b [고름]']);
  });

  it('강조 → 항목: 문서의 조각을 누르면 그 항목이 골라지고, 다른 문서도 따라간다', async () => {
    const { pane, pieces, selected, boxes } = await show(twoDocs());
    fireEvent.click(pieces('b', '2-b')[0]!);
    expect(selected()).toEqual(['2']);
    expect(pane('a').dataset.currentPage).toBe('4');
    expect(boxes('a')).toContain('2-a [고름]');
  });

  it('같은 항목을 다시 누르면 그 자리로 다시 간다', async () => {
    const { scroller, clickItem } = await show(twoDocs());
    clickItem('2');
    const there = scroller('a').scrollTop;
    scroller('a').scrollTop = 0;
    fireEvent.scroll(scroller('a'));
    clickItem('2');
    expect(scroller('a').scrollTop).toBe(there);
  });

  it('보이는 쪽과 그 앞뒤만 그린다', async () => {
    const { pane, clickItem } = await show(twoDocs());
    const drawn = () =>
      [...pane('a').querySelectorAll<HTMLElement>('[data-page]')].map(
        (el) => el.dataset.page,
      );
    expect(drawn()).toEqual(['1', '2']);
    clickItem('2');
    expect(drawn()).toEqual(['3', '4', '5']);
  });

  it('키보드: j 는 다음 항목, k 는 이전 항목. 끝에서 멈춘다. 사유를 적는 중에는 글자다', async () => {
    const { root, pane, selected } = await show(twoDocs());
    fireEvent.keyDown(root, { key: 'j' });
    expect(selected()).toEqual(['1']);
    fireEvent.keyDown(root, { key: 'j' });
    expect(selected()).toEqual(['2']);
    expect(pane('a').dataset.currentPage).toBe('4');
    fireEvent.keyDown(root, { key: 'j' });
    fireEvent.keyDown(root, { key: 'j' });
    expect(selected()).toEqual(['3']);
    fireEvent.keyDown(root, { key: 'k' });
    expect(selected()).toEqual(['2']);
    fireEvent.keyDown(screen.getByLabelText('반려 사유'), { key: 'j' });
    expect(selected()).toEqual(['2']);
  });

  it('가리키기: 항목에 마우스를 올리거나 초점이 가면 그 조각에 표시가 붙고, 떼면 돌아온다. 고르지도 스크롤하지도 않는다', async () => {
    const { item, head, boxes, selected, scroller } = await show(twoDocs());
    fireEvent.mouseEnter(item('2'));
    expect(boxes('b')).toEqual(['2-b [가리킴]']);
    expect(selected()).toEqual([]);
    expect(scroller('a').scrollTop).toBe(0);
    fireEvent.mouseLeave(item('2'));
    expect(boxes('b')).toEqual(['2-b']);
    fireEvent.focus(head('2'));
    expect(boxes('b')).toEqual(['2-b [가리킴]']);
    fireEvent.blur(head('2'));
    expect(boxes('b')).toEqual(['2-b']);
  });

  it('가리키기: 마우스가 초점보다 먼저다. 다른 항목을 고르면 초점으로 가리킨 것은 지워지고 마우스로 가리킨 것은 남는다', async () => {
    const { item, head, boxes, root } = await show(overlap());
    fireEvent.focus(head('5'));
    fireEvent.mouseEnter(item('1'));
    expect(boxes('b')).toEqual(['1-b 4-b [가리킴]', '5-b']);
    fireEvent.mouseLeave(item('1'));
    expect(boxes('b')).toEqual(['1-b 4-b', '5-b [가리킴]']);
    // 5 를 눌러 고른 뒤(초점이 남는다) j·k 로 다른 항목에 가면 5 는 가리킨 것으로 남지 않는다.
    fireEvent.click(head('5'));
    expect(boxes('b')).toEqual(['1-b 4-b', '5-b [고름] [가리킴]']);
    // 마우스는 어디에도 올라가 있지 않다. 초점만 5 의 단추에 남아 있다.
    fireEvent.keyDown(root, { key: 'k' });
    expect(boxes('b')).toEqual(['1-b 4-b [고름]', '5-b']);
    // 마우스를 5 에 올려 둔 채 다른 항목으로 가면, 마우스로 가리킨 것은 남는다.
    fireEvent.mouseEnter(item('5'));
    fireEvent.keyDown(root, { key: 'k' });
    expect(boxes('b')).toEqual(['1-b 4-b [고름]', '5-b [가리킴]']);
  });

  it('범례: 종류를 끄면 그 종류의 조각이 사라지고 항목은 남아 흐려진다. 고르면 꺼진 종류여도 보인다', async () => {
    const { legend, boxes, item, clickItem, view } = await show(twoDocs());
    expect(
      [
        ...view.container.querySelectorAll<HTMLElement>(
          '[data-kind][aria-pressed]',
        ),
      ].map((el) => el.dataset.kind),
    ).toEqual(['match', 'mismatch', 'unverified']);
    fireEvent.click(legend('mismatch'));
    expect(legend('mismatch').getAttribute('aria-pressed')).toBe('false');
    expect(boxes('b')).toEqual([]);
    expect(boxes('a')).toEqual(['1-a']);
    expect(['1', '2', '3'].map((id) => item(id).dataset.kindHidden)).toEqual([
      'false',
      'true',
      'false',
    ]);
    clickItem('2');
    expect(boxes('b')).toEqual(['2-b [고름]']);
    clickItem('3');
    expect(boxes('b')).toEqual([]);
    fireEvent.click(legend('mismatch'));
    expect(boxes('b')).toEqual(['2-b']);
  });

  it('겹친 조각은 누를 때마다 다음 항목으로 돈다. 한 종류를 끄면 남은 항목만 돈다', async () => {
    const { pieces, selected, legend, boxes } = await show(overlap());
    fireEvent.click(pieces('b', '1-b 4-b')[0]!);
    expect(selected()).toEqual(['1']);
    fireEvent.click(pieces('b', '1-b 4-b')[0]!);
    expect(selected()).toEqual(['4']);
    fireEvent.click(pieces('b', '1-b 4-b')[0]!);
    expect(selected()).toEqual(['1']);
    fireEvent.click(legend('mismatch'));
    // 4 는 꺼졌고 골라져 있지도 않다. 묶음에는 1 만 남는다.
    expect(boxes('b')).toEqual(['1-b [고름]', '5-b']);
    fireEvent.click(pieces('b', '1-b')[0]!);
    expect(selected()).toEqual(['1']);
  });

  for (const mode of ['outline', 'fill'] as const) {
    it(`보기 방식 ${mode}: 조각을 전부 그리고, 판의 data-mode 가 그 방식이다. 안내 글은 없다`, async () => {
      const { view, boxes, clickItem } = await show(overlap(), mode);
      expect(
        [...view.container.querySelectorAll<HTMLElement>('[data-mode]')].map(
          (el) => el.dataset.mode,
        ),
      ).toEqual([mode, mode]);
      expect(boxes('b')).toEqual(['1-b 4-b', '5-b']);
      clickItem('5');
      expect(boxes('b')).toEqual(['1-b 4-b', '5-b [고름]']);
      expect(view.queryByTestId('dv-mode-note')).toBeNull();
    });
  }

  it('보기 방식 selected(고른 것만): 고르기 전에는 조각이 없고, 고른 것과 가리킨 것만 그린다. 안내 글이 보인다', async () => {
    const { view, boxes, clickItem, item } = await show(overlap(), 'selected');
    expect(boxes('b')).toEqual([]);
    expect(view.getByTestId('dv-mode-note').textContent).toContain(
      '눌러 고를 수 없',
    );
    clickItem('5');
    expect(boxes('b')).toEqual(['5-b [고름]']);
    fireEvent.mouseEnter(item('4'));
    expect(boxes('b')).toEqual(['4-b [가리킴]', '5-b [고름]']);
  });

  it('보기 방식을 주지 않으면 옅게(outline)다', async () => {
    const { view } = await show(overlap());
    expect(
      view.container.querySelector<HTMLElement>('[data-mode]')!.dataset.mode,
    ).toBe('outline');
  });

  it('여러 조각 강조: 줄마다 조각 하나가 입력의 자리에 놓이고, 어느 조각을 눌러도 그 항목이 골라지며 조각이 전부 표시를 갖는다', async () => {
    const { pieces, rect, selected, item, scroller, view } =
      await show(lines());
    expect(pieces('a', 's-a t-a').map(rect)).toEqual([
      [300, 400, 200, 12],
      [50, 416, 170, 12],
    ]);
    expect(pieces('a', 'u-a').map(rect)).toEqual([[60, 500, 30, 12]]);
    fireEvent.click(pieces('a', 's-a t-a')[1]!);
    expect(selected()).toEqual(['s']);
    expect(pieces('a', 's-a t-a').map((el) => el.dataset.selected)).toEqual([
      'true',
      'true',
    ]);
    // 조각들을 감싼 상자의 윗변(첫 줄)으로 스크롤하고, 가로는 감싼 상자의 가운데로 잰다.
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[0]! + 400);
    expect(scroller('a').scrollLeft).toBe(PAGE_GAP + 275);
    // 같은 자리의 다른 항목으로 돈다(첫 줄 조각으로도).
    fireEvent.click(pieces('a', 's-a t-a')[0]!);
    expect(selected()).toEqual(['t']);
    fireEvent.mouseEnter(item('s'));
    expect(pieces('a', 's-a t-a').map((el) => el.dataset.pointed)).toEqual([
      'true',
      'true',
    ]);
    // 좁힌 자리를 끄면 문단 전체 상자 하나로 돌아간다.
    fireEvent.click(within(view.container).getByLabelText(/좁힌 자리로 보기/));
    expect(pieces('a', 's-a t-a').map(rect)).toEqual([[50, 380, 500, 70]]);
  });

  it('쪽 이동과 확대: 쪽 이동은 그 쪽의 맨 위로 가고, 확대해도 보던 자리에 머문다', async () => {
    const { pane, scroller } = await show(twoDocs());
    const a = within(pane('a'));
    fireEvent.click(a.getByRole('button', { name: '다음 페이지' }));
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[1]! - PAGE_GAP);
    fireEvent.click(a.getByRole('button', { name: '확대' }));
    expect(pane('a').dataset.scale).toBe('1.25');
    expect(scroller('a').scrollTop).toBe(
      pageOffsets(pages, 1.25)[1]! - PAGE_GAP,
    );
    fireEvent.click(a.getByRole('button', { name: '축소' }));
    expect(pane('a').dataset.scale).toBe('1');
    // 다른 문서 칸은 그대로다.
    expect(pane('b').dataset.scale).toBe('1');
  });

  it('검토: 사유 없이는 반려되지 않고, 사유를 적으면 반려되고, 되돌려 확정할 수 있다. 항목마다 따로다', async () => {
    const { clickItem, status, view } = await show(twoDocs());
    const all = within(view.container);
    clickItem('1');
    fireEvent.click(all.getByRole('button', { name: '반려' }));
    expect(status('1')).toBe('pending');
    expect(all.getByRole('alert').textContent).toContain('사유');
    fireEvent.change(all.getByLabelText('반려 사유'), {
      target: { value: '단위가 다르다' },
    });
    fireEvent.click(all.getByRole('button', { name: '반려' }));
    expect(status('1')).toBe('rejected');
    expect(view.container.textContent).toContain('반려 사유: 단위가 다르다');
    fireEvent.click(all.getByRole('button', { name: '검토대기로 되돌리기' }));
    expect(status('1')).toBe('pending');
    fireEvent.click(all.getByRole('button', { name: '확정' }));
    clickItem('2');
    expect(['1', '2', '3'].map(status)).toEqual([
      'confirmed',
      'pending',
      'pending',
    ]);
  });

  it('적다 만 사유는 다른 항목으로 가면 버려진다', async () => {
    const { clickItem, view } = await show(twoDocs());
    const all = within(view.container);
    clickItem('1');
    fireEvent.change(all.getByLabelText('반려 사유'), {
      target: { value: '적다 만 것' },
    });
    clickItem('2');
    expect((all.getByLabelText('반려 사유') as HTMLTextAreaElement).value).toBe(
      '',
    );
  });
});

describe('둘째 화면은 본 화면의 것을 쓰지 않는다', () => {
  it('본 화면의 클래스 이름(dv-)이 DOM 에 하나도 없다', async () => {
    function Harness() {
      const input = lines();
      const reviews = useReviews(input.items);
      return (
        <CompactViewer
          input={input}
          openPdf={fakeOpenPdf}
          reviews={reviews.states}
          onReview={reviews.apply}
        />
      );
    }
    const view = render(<Harness />);
    await act(async () => undefined);
    expect(
      view.container.querySelectorAll('[data-highlight-ids]').length,
    ).toBeGreaterThan(0);
    expect(
      [...view.container.querySelectorAll('[class]')].filter((el) =>
        /(^|\s)dv-/.test(el.getAttribute('class')!),
      ),
    ).toHaveLength(0);
  });
});
