// @vitest-environment jsdom
//
// 부품 테스트. 브라우저가 아니라 jsdom 이라 PDF 를 그리지 못한다. 그래서 가짜 PdfHandle 을 넣고,
// 「무엇이 골라지고 어느 쪽으로 가는가」만 본다. 상자가 글자 위에 놓이는지는 e2e/ 가 본다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { useReviews } from '../hooks/index.ts';
import type { OpenPdf } from '../hooks/index.ts';
import {
  MIXED_COLOR,
  PAGE_GAP,
  pageOffsets,
  parseViewerInput,
} from '../model/index.ts';
import type { HighlightMode, ViewerInput } from '../model/index.ts';
import { DocumentViewer } from './DocumentViewer.tsx';

afterEach(cleanup);

const fakeOpenPdf: OpenPdf = async () => ({
  renderPage: () => ({ done: Promise.resolve(), cancel: () => undefined }),
  close: () => undefined,
});

const pages = Array.from({ length: 5 }, () => ({ width: 600, height: 800 }));
function makeInput(): ViewerInput {
  const parsed = parseViewerInput({
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
  if (!parsed.ok) throw new Error(parsed.errors.join('\n'));
  return parsed.input;
}

function Harness({
  input,
  mode,
}: {
  input: ViewerInput;
  mode?: HighlightMode;
}) {
  const reviews = useReviews(input.items);
  // mode 를 안 주면 highlightMode 를 아예 넘기지 않는다(앞서 있던 쓰임 그대로).
  return (
    <DocumentViewer
      input={input}
      openPdf={fakeOpenPdf}
      reviews={reviews.states}
      onReview={reviews.apply}
      {...(mode ? { highlightMode: mode } : {})}
    />
  );
}

async function setup(mode?: HighlightMode, input: ViewerInput = makeInput()) {
  const view = render(<Harness input={input} mode={mode} />);
  // 가짜 PDF 가 「열릴」 때까지 한 번 기다린다.
  await act(async () => undefined);
  const root = view.container.querySelector<HTMLElement>('.dv-root')!;
  const pane = (id: string) =>
    view.container.querySelector<HTMLElement>(
      `.dv-pane[data-document-id="${id}"]`,
    )!;
  const scroller = (id: string) =>
    pane(id).querySelector<HTMLElement>('.dv-scroller')!;
  const item = (id: string) =>
    view.container.querySelector<HTMLElement>(
      `.dv-item[data-item-id="${id}"]`,
    )!;
  const clickItem = (id: string) =>
    fireEvent.click(item(id).querySelector('button')!);
  const selectedHighlights = (id: string) =>
    [
      ...pane(id).querySelectorAll<HTMLElement>(
        '.dv-highlight[data-selected="true"]',
      ),
    ].map((el) => el.dataset.highlightIds);
  /** 그 문서 칸에 지금 그려진 상자들: 묶인 강조 id 와 모양을 정하는 표시 둘. */
  const boxes = (id: string) =>
    [...pane(id).querySelectorAll<HTMLElement>('.dv-highlight')]
      .map(
        (el) =>
          `${el.dataset.highlightIds}${el.dataset.selected === 'true' ? ' [고름]' : ''}${el.dataset.pointed === 'true' ? ' [가리킴]' : ''}`,
      )
      .sort();
  const layerModes = () => [
    ...new Set(
      [...view.container.querySelectorAll<HTMLElement>('.dv-highlights')].map(
        (el) => el.dataset.mode,
      ),
    ),
  ];
  const legend = (kind: string) =>
    view.container.querySelector<HTMLElement>(`.dv-kind[data-kind="${kind}"]`)!;
  return {
    view,
    root,
    pane,
    scroller,
    item,
    clickItem,
    selectedHighlights,
    boxes,
    layerModes,
    legend,
  };
}

/** 같은 자리에 겹친 상자가 있는 자료: B 의 1쪽 한 칸을 항목 1(일치)과 항목 4(불일치)가 같이 가리킨다. */
function makeOverlapInput(): ViewerInput {
  const parsed = parseViewerInput({
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
  if (!parsed.ok) throw new Error(parsed.errors.join('\n'));
  return parsed.input;
}

describe('DocumentViewer', () => {
  it('쪽의 캔버스에는 클래스를 붙이지 않는다(받는 CSS 규칙이 없는 이름을 달지 않는다. 자리 잡기는 헤드리스의 PageCanvas 가 한다)', async () => {
    const { view } = await setup();
    const canvases = [...view.container.querySelectorAll('canvas')];
    expect(canvases.length).toBeGreaterThan(0);
    expect(canvases.map((canvas) => canvas.getAttribute('class'))).toEqual(
      canvases.map(() => null),
    );
  });

  it('문서가 둘이면 나란히 놓는다', async () => {
    const { root, pane } = await setup();
    expect(root.dataset.layout).toBe('side-by-side');
    expect(pane('a')).toBeTruthy();
    expect(pane('b')).toBeTruthy();
  });

  it('항목을 누르면 그 강조가 골라지고, 문서마다 그 쪽으로 간다', async () => {
    const { pane, scroller, item, clickItem, selectedHighlights } =
      await setup();
    clickItem('2');

    expect(item('2').dataset.selected).toBe('true');
    // A 는 4쪽, B 는 1쪽으로.
    expect(pane('a').dataset.currentPage).toBe('4');
    expect(pane('b').dataset.currentPage).toBe('1');
    // jsdom 은 화면 높이가 0 이라, 상자의 윗변이 화면 맨 위에 오는 자리로 간다.
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[3]! + 300);
    expect(selectedHighlights('a')).toEqual(['2-a']);
    expect(selectedHighlights('b')).toEqual(['2-b']);
  });

  it('상자를 누르면 그 항목이 골라지고, 다른 문서도 따라간다', async () => {
    const { pane, item, selectedHighlights } = await setup();
    // B 의 1쪽에 보이는 상자는 2-b 다.
    fireEvent.click(
      pane('b').querySelector('.dv-highlight[data-highlight-ids="2-b"]')!,
    );

    expect(item('2').dataset.selected).toBe('true');
    expect(item('1').dataset.selected).toBe('false');
    expect(pane('a').dataset.currentPage).toBe('4');
    expect(selectedHighlights('a')).toEqual(['2-a']);
  });

  it('키보드: j 는 다음 항목, k 는 이전 항목. 끝에서 멈춘다', async () => {
    const { root, pane, item } = await setup();
    const selected = () =>
      ['1', '2', '3'].filter((id) => item(id).dataset.selected === 'true');

    fireEvent.keyDown(root, { key: 'j' });
    expect(selected()).toEqual(['1']);
    fireEvent.keyDown(root, { key: 'j' });
    expect(selected()).toEqual(['2']);
    expect(pane('a').dataset.currentPage).toBe('4');
    fireEvent.keyDown(root, { key: 'j' });
    fireEvent.keyDown(root, { key: 'j' });
    expect(selected()).toEqual(['3']);
    expect(pane('a').dataset.currentPage).toBe('5');
    fireEvent.keyDown(root, { key: 'k' });
    expect(selected()).toEqual(['2']);
  });

  it('사유를 적는 중에는 j·k 가 글자다', async () => {
    const { item, clickItem } = await setup();
    clickItem('1');
    fireEvent.keyDown(within(item('1')).getByLabelText('반려 사유'), {
      key: 'j',
    });
    expect(item('1').dataset.selected).toBe('true');
    expect(item('2').dataset.selected).toBe('false');
  });

  it('보이는 쪽과 그 앞뒤만 그린다', async () => {
    const { pane, clickItem } = await setup();
    const drawn = () =>
      [...pane('a').querySelectorAll<HTMLElement>('.dv-page')].map(
        (el) => el.dataset.page,
      );
    expect(drawn()).toEqual(['1', '2']);
    clickItem('2'); // A 의 4쪽으로
    expect(drawn()).toEqual(['3', '4', '5']);
  });

  it('검토 상태: 사유 없이는 반려되지 않는다. 사유를 적으면 반려되고, 되돌릴 수 있다', async () => {
    const { item, clickItem } = await setup();
    clickItem('1');
    const scope = within(item('1'));
    const status = () => item('1').querySelector('.dv-status')!.textContent;

    fireEvent.click(scope.getByRole('button', { name: '반려' }));
    expect(status()).toBe('검토대기');
    expect(scope.getByRole('alert').textContent).toContain('사유');

    fireEvent.change(scope.getByLabelText('반려 사유'), {
      target: { value: '단위가 다르다' },
    });
    fireEvent.click(scope.getByRole('button', { name: '반려' }));
    expect(status()).toBe('반려');
    expect(item('1').textContent).toContain('반려 사유: 단위가 다르다');

    fireEvent.click(scope.getByRole('button', { name: '검토대기로 되돌리기' }));
    expect(status()).toBe('검토대기');
    fireEvent.click(scope.getByRole('button', { name: '확정' }));
    expect(status()).toBe('확정');
  });

  it('검토 상태는 항목마다 따로다', async () => {
    const { item, clickItem } = await setup();
    const status = (id: string) =>
      item(id).querySelector('.dv-status')!.textContent;
    clickItem('1');
    fireEvent.click(within(item('1')).getByRole('button', { name: '확정' }));
    clickItem('2');
    fireEvent.change(within(item('2')).getByLabelText('반려 사유'), {
      target: { value: '사유' },
    });
    fireEvent.click(within(item('2')).getByRole('button', { name: '반려' }));
    expect([status('1'), status('2'), status('3')]).toEqual([
      '확정',
      '반려',
      '검토대기',
    ]);
  });

  it('같은 항목을 다시 누르면 그 자리로 다시 간다', async () => {
    const { scroller, clickItem } = await setup();
    clickItem('2');
    const there = scroller('a').scrollTop;
    // 사람이 다른 데로 스크롤했다.
    scroller('a').scrollTop = 0;
    fireEvent.scroll(scroller('a'));
    clickItem('2');
    expect(scroller('a').scrollTop).toBe(there);
  });

  it('쪽 이동 단추는 그 쪽의 맨 위로 가고, 확대해도 보던 자리에 머문다', async () => {
    const { pane, scroller } = await setup();
    const a = within(pane('a'));
    fireEvent.click(a.getByRole('button', { name: '다음 페이지' }));
    // 2쪽의 맨 위(쪽 사이 틈이 보이는 자리).
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[1]! - PAGE_GAP);

    fireEvent.click(a.getByRole('button', { name: '확대' }));
    expect(pane('a').dataset.scale).toBe('1.25');
    // 확대한 뒤에도 2쪽의 맨 위다.
    expect(scroller('a').scrollTop).toBe(
      pageOffsets(pages, 1.25)[1]! - PAGE_GAP,
    );
  });

  it('문서가 하나면 한 칸만 놓는다', async () => {
    const input = makeInput();
    const single: ViewerInput = {
      ...input,
      documents: [input.documents[0]!],
      highlights: input.highlights.filter((h) => h.documentId === 'a'),
      items: input.items.map((it) => ({
        ...it,
        highlightIds: it.highlightIds.filter((id) => id.endsWith('-a')),
      })),
    };
    const view = render(<Harness input={single} />);
    await act(async () => undefined);
    expect(
      view.container.querySelector<HTMLElement>('.dv-root')!.dataset.layout,
    ).toBe('single');
    expect(view.container.querySelectorAll('.dv-pane')).toHaveLength(1);
    expect(screen.getAllByText(/항목 3개/)).toHaveLength(1);
  });
});

// B 의 1쪽에는 2-b(불일치)가, 보이는 앞뒤 쪽까지 치면 그것 하나만 그려진다(1-b 는 4쪽). A 의 1쪽에는 1-a(일치).
describe('강조의 보기 방식', () => {
  it('보기 방식을 주지 않으면 옅게다', async () => {
    const { layerModes, boxes } = await setup();
    expect(layerModes()).toEqual(['outline']);
    expect(boxes('a')).toEqual(['1-a']);
    expect(boxes('b')).toEqual(['2-b']);
  });

  for (const mode of ['outline', 'fill'] as const) {
    it(`${mode}: 상자를 전부 그리고, 고른 것과 가리킨 것에만 표시가 붙는다`, async () => {
      const { layerModes, boxes, clickItem, item, view } = await setup(
        mode,
        makeOverlapInput(),
      );
      expect(layerModes()).toEqual([mode]);
      // 아무것도 고르지 않았을 때: 표시 없는 상자 둘(겹친 것 하나, 따로 하나).
      expect(boxes('b')).toEqual(['1-b 4-b', '5-b']);
      clickItem('5');
      expect(boxes('b')).toEqual(['1-b 4-b', '5-b [고름]']);
      fireEvent.mouseEnter(item('1'));
      expect(boxes('b')).toEqual(['1-b 4-b [가리킴]', '5-b [고름]']);
      // 「고른 것만」의 안내 글은 이 방식에 없다.
      expect(view.queryByTestId('dv-mode-note')).toBeNull();
    });
  }

  it('selected(고른 것만): 고르기 전에는 상자가 없고, 고른 항목의 상자만 그린다. 나머지는 DOM 에 없어 누를 수 없다', async () => {
    const { layerModes, boxes, clickItem, pane, item, view } = await setup(
      'selected',
      makeOverlapInput(),
    );
    expect(layerModes()).toEqual(['selected']);
    expect(boxes('b')).toEqual([]);
    expect(view.getByTestId('dv-mode-note').textContent).toContain(
      '눌러 고를 수 없',
    );

    clickItem('5');
    expect(boxes('b')).toEqual(['5-b [고름]']);
    // 나머지 상자(1-b, 4-b)는 그려지지 않았다. 누를 단추가 없다.
    expect(pane('b').querySelectorAll('button.dv-highlight')).toHaveLength(1);
    expect(
      pane('b').querySelector('.dv-highlight[data-highlight-ids*="1-b"]'),
    ).toBeNull();
    // 고른 상자를 눌러도 다른 항목으로 넘어가지 않는다(같은 자리에 겹친 것이 그려져 있지 않다).
    clickItem('1');
    expect(boxes('b')).toEqual(['1-b [고름]']);
    fireEvent.click(pane('b').querySelector('.dv-highlight')!);
    expect(item('1').dataset.selected).toBe('true');
    expect(item('4').dataset.selected).toBe('false');
  });

  it('selected: 목록에서 가리킨 항목의 상자는 잠깐 그려진다', async () => {
    const { boxes, clickItem, item } = await setup(
      'selected',
      makeOverlapInput(),
    );
    clickItem('5');
    fireEvent.mouseEnter(item('4'));
    expect(boxes('b')).toEqual(['4-b [가리킴]', '5-b [고름]']);
    fireEvent.mouseLeave(item('4'));
    expect(boxes('b')).toEqual(['5-b [고름]']);
  });

  for (const mode of ['outline', 'fill'] as const) {
    it(`${mode}: 같은 자리에 겹친 상자는 누를 때마다 다음 항목으로 돈다`, async () => {
      const { pane, item } = await setup(mode, makeOverlapInput());
      const selected = () =>
        ['1', '4', '5'].filter((id) => item(id).dataset.selected === 'true');
      const shared = () =>
        pane('b').querySelector<HTMLElement>(
          '.dv-highlight[data-highlight-ids="1-b 4-b"]',
        )!;
      expect(shared().textContent).toBe('2'); // 겹친 개수
      fireEvent.click(shared());
      expect(selected()).toEqual(['1']);
      fireEvent.click(shared());
      expect(selected()).toEqual(['4']);
      fireEvent.click(shared());
      expect(selected()).toEqual(['1']);
    });
  }
});

describe('같은 자리에 겹친 상자의 생김', () => {
  const piece = (pane: HTMLElement, ids: string) =>
    pane.querySelector<HTMLElement>(
      `.dv-highlight[data-highlight-ids="${ids}"]`,
    )!;

  it('마우스를 올리면 뜨는 글(title)에 겹친 개수와 누르는 법이 있다. 겹치지 않은 상자의 글에는 없다', async () => {
    const { pane } = await setup(undefined, makeOverlapInput());
    expect(piece(pane('b'), '1-b 4-b').title).toContain('겹친 강조 2개');
    expect(piece(pane('b'), '1-b 4-b').title).toContain(
      '누를 때마다 다음 항목',
    );
    expect(piece(pane('b'), '5-b').title).not.toContain('겹친');
  });

  it('종류가 섞인 묶음은 어느 한 종류의 색이 아니라 따로 정한 섞임 색이다. 한 종류뿐인 상자는 범례에 나온 그 종류의 색이다', async () => {
    const { pane, legend } = await setup(undefined, makeOverlapInput());
    /** 색 글자를 브라우저(jsdom)가 적는 꼴로 바꾼다. 요소의 style 에서 읽은 값과 견주려고. */
    const asStyle = (color: string) =>
      Object.assign(document.createElement('i').style, { color }).color;
    const legendColor = (kind: string) =>
      asStyle(
        legend(kind).querySelector<HTMLElement>('.dv-dot')!.style.background,
      );
    const mixed = piece(pane('b'), '1-b 4-b').style.color;
    expect(piece(pane('b'), '5-b').style.color).toBe(legendColor('match'));
    expect(mixed).toBe(asStyle(MIXED_COLOR));
    expect([legendColor('match'), legendColor('mismatch')]).not.toContain(
      mixed,
    );
  });
});

describe('범례로 종류 켜고 끄기', () => {
  it('종류를 끄면 그 종류의 상자가 사라지고, 다시 켜면 나온다. 다른 종류는 그대로다', async () => {
    const { boxes, legend } = await setup();
    expect(legend('mismatch').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(legend('mismatch'));
    expect(legend('mismatch').getAttribute('aria-pressed')).toBe('false');
    expect(boxes('b')).toEqual([]); // 2-b(불일치)가 사라졌다
    expect(boxes('a')).toEqual(['1-a']); // 일치는 그대로
    fireEvent.click(legend('mismatch'));
    expect(boxes('b')).toEqual(['2-b']);
  });

  it('꺼진 종류라도 고른 항목의 상자는 보인다. 다른 항목을 고르면 다시 사라진다', async () => {
    const { boxes, legend, clickItem } = await setup();
    fireEvent.click(legend('mismatch'));
    clickItem('2');
    expect(boxes('b')).toEqual(['2-b [고름]']);
    // A 는 4쪽으로 갔다. 앞뒤 쪽까지 그리므로 5쪽의 3-a(확인 못 함, 켜져 있다)도 같이 있다.
    expect(boxes('a')).toEqual(['2-a [고름]', '3-a']);
    clickItem('3'); // A 의 5쪽으로 간다. B 는 그대로 1쪽이다
    expect(boxes('b')).toEqual([]);
  });

  it('종류가 섞인 항목은 그 종류가 전부 꺼졌을 때만 흐려진다', async () => {
    const input = makeInput();
    // 항목 1 의 강조 둘을 서로 다른 종류로 만든다(1-a 일치, 1-b 불일치).
    const mixed: ViewerInput = {
      ...input,
      highlights: input.highlights.map((h) =>
        h.id === '1-b' ? { ...h, kind: 'mismatch' } : h,
      ),
    };
    const { legend, item } = await setup('outline', mixed);
    fireEvent.click(legend('mismatch'));
    expect(item('1').dataset.kindHidden).toBe('false');
    fireEvent.click(legend('match'));
    expect(item('1').dataset.kindHidden).toBe('true');
  });

  it('꺼진 종류의 항목은 목록에 남고 흐리게 표시된다(숨기지 않는다). j·k 도 그대로 밟는다', async () => {
    const { legend, item, root } = await setup();
    fireEvent.click(legend('mismatch'));
    expect(['1', '2', '3'].map((id) => item(id).dataset.kindHidden)).toEqual([
      'false',
      'true',
      'false',
    ]);
    fireEvent.keyDown(root, { key: 'j' });
    fireEvent.keyDown(root, { key: 'j' });
    expect(item('2').dataset.selected).toBe('true');
  });

  it('겹친 상자에서 한 종류를 끄면 남은 것만 묶이고, 누르면 남은 항목만 돈다', async () => {
    const { boxes, legend, pane, item } = await setup(
      'outline',
      makeOverlapInput(),
    );
    fireEvent.click(legend('mismatch'));
    expect(boxes('b')).toEqual(['1-b', '5-b']);
    const shared = () =>
      pane('b').querySelector<HTMLElement>(
        '.dv-highlight[data-highlight-ids="1-b"]',
      )!;
    fireEvent.click(shared());
    fireEvent.click(shared());
    expect(item('1').dataset.selected).toBe('true');
    expect(item('4').dataset.selected).toBe('false');
  });

  it('뷰어는 종류의 뜻을 모른다: 입력이 준 종류마다 단추가 하나씩 있고 어느 것이든 꺼진다', async () => {
    const { view, legend, boxes } = await setup();
    expect(
      [...view.container.querySelectorAll<HTMLElement>('.dv-kind')].map(
        (el) => el.dataset.kind,
      ),
    ).toEqual(['match', 'mismatch', 'unverified']);
    fireEvent.click(legend('match'));
    expect(boxes('a')).toEqual([]);
    expect(boxes('b')).toEqual(['2-b']);
  });
});

describe('목록의 항목을 가리키면(마우스를 올리거나 초점이 가면)', () => {
  it('그 항목의 상자가 진해지고, 떼면 돌아온다. 고르지도 스크롤하지도 않는다', async () => {
    const { boxes, item, scroller, pane } = await setup();
    fireEvent.mouseEnter(item('2'));
    expect(boxes('b')).toEqual(['2-b [가리킴]']);
    // 고른 것이 아니다. 2-a 가 있는 A 의 4쪽으로 가지도 않는다.
    expect(item('2').dataset.selected).toBe('false');
    expect(scroller('a').scrollTop).toBe(0);
    expect(pane('a').dataset.currentPage).toBe('1');
    fireEvent.mouseLeave(item('2'));
    expect(boxes('b')).toEqual(['2-b']);
  });

  it('키보드 초점이 간 항목도 같다', async () => {
    const { boxes, item, scroller } = await setup();
    const head = item('2').querySelector<HTMLElement>('.dv-item-head')!;
    fireEvent.focus(head);
    expect(boxes('b')).toEqual(['2-b [가리킴]']);
    expect(scroller('a').scrollTop).toBe(0);
    fireEvent.blur(head);
    expect(boxes('b')).toEqual(['2-b']);
  });

  it('마우스를 올린 항목이 초점이 간 항목보다 먼저다. 마우스를 떼면 초점이 간 항목으로 돌아간다', async () => {
    const { boxes, item } = await setup('outline', makeOverlapInput());
    fireEvent.focus(item('5').querySelector<HTMLElement>('.dv-item-head')!);
    expect(boxes('b')).toEqual(['1-b 4-b', '5-b [가리킴]']);
    fireEvent.mouseEnter(item('1'));
    expect(boxes('b')).toEqual(['1-b 4-b [가리킴]', '5-b']);
    fireEvent.mouseLeave(item('1'));
    expect(boxes('b')).toEqual(['1-b 4-b', '5-b [가리킴]']);
  });

  it('고른 항목을 가리키면 두 표시가 같이 붙는다', async () => {
    const { boxes, item, clickItem } = await setup();
    clickItem('2');
    fireEvent.mouseEnter(item('2'));
    expect(boxes('b')).toEqual(['2-b [고름] [가리킴]']);
  });

  it('항목을 눌러 고른 뒤(초점이 그 단추에 남는다) j 로 옮기면, 앞 항목의 상자는 가리킨 것으로 남지 않는다', async () => {
    const { boxes, item, root } = await setup('selected', makeOverlapInput());
    const head = item('1').querySelector<HTMLElement>('.dv-item-head')!;
    // 사람이 누르면 초점이 먼저 가고 눌린다.
    fireEvent.focus(head);
    fireEvent.click(head);
    expect(boxes('b')).toEqual(['1-b [고름] [가리킴]']);
    fireEvent.keyDown(root, { key: 'j' });
    // 「고른 것만」인데 앞 항목(1-b)이 계속 그려지면 안 된다.
    expect(boxes('b')).toEqual(['4-b [고름]']);
  });

  it('마우스를 올려 둔 채 j 로 옮기면, 마우스로 가리킨 것은 남는다(마우스가 실제로 그 위에 있다)', async () => {
    const { boxes, item, root } = await setup('selected', makeOverlapInput());
    fireEvent.mouseEnter(item('5'));
    fireEvent.keyDown(root, { key: 'j' }); // 첫 항목(1)이 골라진다
    expect(boxes('b')).toEqual(['1-b [고름]', '5-b [가리킴]']);
    fireEvent.mouseLeave(item('5'));
    expect(boxes('b')).toEqual(['1-b [고름]']);
  });

  it('겹친 묶음에서는 둘째 항목을 가리켜도 그 묶음이 진해진다', async () => {
    const { boxes, item } = await setup('outline', makeOverlapInput());
    fireEvent.mouseEnter(item('4'));
    expect(boxes('b')).toEqual(['1-b 4-b [가리킴]', '5-b']);
  });
});

// ── 강조 하나에 상자 여럿(여러 줄에 걸친 문장) ──
// A 의 2쪽에 두 줄짜리 문장 강조 s(상자 둘), 그것과 상자가 전부 같은 강조 t(다른 종류, 다른 항목), 한 줄짜리 u.
function makeLinesInput(): ViewerInput {
  const twoLines = [
    [300, 400, 500, 412],
    [50, 416, 220, 428],
  ];
  const parsed = parseViewerInput({
    version: 1,
    documents: [{ id: 'a', url: 'a.pdf', pages }],
    highlights: [
      {
        id: 's-a',
        documentId: 'a',
        page: 2,
        box: [50, 380, 550, 450],
        innerBoxes: twoLines,
        kind: 'sentence',
      },
      {
        id: 't-a',
        documentId: 'a',
        page: 2,
        box: [50, 380, 550, 450],
        innerBoxes: twoLines,
        kind: 'note',
      },
      {
        id: 'u-a',
        documentId: 'a',
        page: 2,
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
    kinds: [
      { kind: 'sentence', label: '문장', color: '#d97706' },
      { kind: 'note', label: '메모', color: '#2563eb' },
    ],
  });
  if (!parsed.ok) throw new Error(parsed.errors.join('\n'));
  return parsed.input;
}

describe('상자가 여럿인 강조', () => {
  /** 그 강조(들)의 조각들. 화면 자리(left, top, width, height)와 표시를 같이 본다. */
  const pieces = (pane: HTMLElement, ids: string) =>
    [
      ...pane.querySelectorAll<HTMLElement>(
        `.dv-highlight[data-highlight-ids="${ids}"]`,
      ),
    ].map((el) => ({
      rect: [el.style.left, el.style.top, el.style.width, el.style.height].map(
        (value) => Number.parseFloat(value),
      ),
      selected: el.dataset.selected === 'true',
      pointed: el.dataset.pointed === 'true',
      el,
    }));
  /** 2쪽으로 가서(항목 u 를 눌러) 그 쪽의 상자가 그려지게 한다. */
  async function setupLines(mode?: HighlightMode) {
    const ui = await setup(mode, makeLinesInput());
    ui.clickItem('u');
    return ui;
  }

  it('줄마다 조각 하나로 그린다: 조각의 자리가 입력의 상자 그대로이고(첫 것만도, 감싼 큰 상자 하나도 아니다), 한 틀 안에 든다', async () => {
    const { pane } = await setupLines();
    const drawn = pieces(pane('a'), 's-a t-a');
    expect(drawn.map((piece) => piece.rect)).toEqual([
      [300, 400, 200, 12],
      [50, 416, 170, 12],
    ]);
    expect(new Set(drawn.map((piece) => piece.el.parentElement)).size).toBe(1);
    expect(drawn[0]!.el.parentElement!.className).toBe('dv-group');
    // 상자가 하나뿐인 강조(예전 꼴 innerBox)는 조각 하나다.
    expect(pieces(pane('a'), 'u-a').map((piece) => piece.rect)).toEqual([
      [60, 500, 30, 12],
    ]);
  });

  it('항목을 고르면 조각이 전부 골라지고, 조각들을 감싼 상자의 윗변으로 스크롤한다', async () => {
    const { pane, scroller, clickItem } = await setupLines();
    clickItem('s');
    expect(pieces(pane('a'), 's-a t-a').map((piece) => piece.selected)).toEqual(
      [true, true],
    );
    // jsdom 은 화면 높이가 0 이라 상자의 윗변이 화면 맨 위에 온다. 두 줄 가운데 위쪽 줄(y 400)이다.
    expect(scroller('a').scrollTop).toBe(pageOffsets(pages, 1)[1]! + 400);
    // 가로도 감싼 상자(x 50~500)의 가운데로 잰다. 첫 조각(x 300~500)만으로 재면 다른 값이 나온다.
    // jsdom 은 화면 폭이 0 이라: 쌓는 폭 = 쪽 폭 + 양옆 틈, 쪽의 왼쪽 = 틈, 가려는 자리 = 틈 + 가운데(275).
    expect(scroller('a').scrollLeft).toBe(PAGE_GAP + 275);
    // 고른 강조가 든 문단 전체는 점선으로 한 번만 그린다.
    expect(pane('a').querySelectorAll('.dv-context')).toHaveLength(1);
  });

  it('어느 조각을 눌러도 그 항목이 골라진다. 같은 자리의 항목이 둘이면 누를 때마다 돈다(둘째 줄 조각으로도)', async () => {
    const { pane, item } = await setupLines();
    const selected = () =>
      ['s', 't', 'u'].filter((id) => item(id).dataset.selected === 'true');
    fireEvent.click(pieces(pane('a'), 's-a t-a')[1]!.el);
    expect(selected()).toEqual(['s']);
    fireEvent.click(pieces(pane('a'), 's-a t-a')[0]!.el);
    expect(selected()).toEqual(['t']);
    fireEvent.click(pieces(pane('a'), 's-a t-a')[1]!.el);
    expect(selected()).toEqual(['s']);
  });

  it('목록에서 가리키면 조각이 전부 진해지고, 떼면 전부 돌아온다', async () => {
    const { pane, item } = await setupLines();
    fireEvent.mouseEnter(item('s'));
    expect(pieces(pane('a'), 's-a t-a').map((piece) => piece.pointed)).toEqual([
      true,
      true,
    ]);
    fireEvent.mouseLeave(item('s'));
    expect(pieces(pane('a'), 's-a t-a').map((piece) => piece.pointed)).toEqual([
      false,
      false,
    ]);
  });

  it('겹친 개수는 한 번만 적는다(마지막 조각에). Tab 은 첫 조각에만 선다', async () => {
    const { pane } = await setupLines();
    const drawn = pieces(pane('a'), 's-a t-a');
    expect(drawn.map((piece) => piece.el.textContent)).toEqual(['', '2']);
    expect(drawn.map((piece) => piece.el.getAttribute('tabindex'))).toEqual([
      null,
      '-1',
    ]);
    expect(drawn.map((piece) => piece.el.getAttribute('aria-hidden'))).toEqual([
      null,
      'true',
    ]);
  });

  it('고른 것만: 고르기 전에는 조각이 없고, 고르면 그 강조의 조각이 전부 그려진다', async () => {
    const { pane, clickItem, boxes } = await setupLines('selected');
    // 지금 고른 것은 u 다(2쪽으로 가려고 눌렀다).
    expect(boxes('a')).toEqual(['u-a [고름]']);
    clickItem('s');
    expect(boxes('a')).toEqual(['s-a [고름]', 's-a [고름]']);
    expect(pieces(pane('a'), 's-a').map((piece) => piece.rect)).toEqual([
      [300, 400, 200, 12],
      [50, 416, 170, 12],
    ]);
  });

  for (const mode of ['outline', 'fill'] as const) {
    it(`${mode}: 조각을 전부 그리고, 고른 강조의 조각에만 표시가 붙는다`, async () => {
      const { clickItem, boxes } = await setupLines(mode);
      expect(boxes('a')).toEqual(['s-a t-a', 's-a t-a', 'u-a [고름]']);
      clickItem('s');
      expect(boxes('a')).toEqual(['s-a t-a [고름]', 's-a t-a [고름]', 'u-a']);
    });
  }

  it('범례에서 종류를 끄면 그 종류의 조각이 전부 사라진다. 남은 강조의 조각은 그대로 둘이다', async () => {
    const { pane, legend, clickItem, boxes } = await setupLines();
    fireEvent.click(legend('note'));
    // t(메모)가 빠져 s 만 남는다. 조각은 여전히 둘이고 겹친 개수는 없다. u(메모)는 골라져 있어 남는다.
    expect(boxes('a')).toEqual(['s-a', 's-a', 'u-a [고름]']);
    expect(
      pieces(pane('a'), 's-a').map((piece) => piece.el.textContent),
    ).toEqual(['', '']);
    fireEvent.click(legend('sentence'));
    expect(boxes('a')).toEqual(['u-a [고름]']);
    // 꺼진 종류라도 고르면 조각이 전부 보인다.
    clickItem('s');
    expect(boxes('a')).toEqual(['s-a [고름]', 's-a [고름]']);
  });

  it('새 꼴(innerBoxes)만 든 자료에서도 「좁힌 자리로 보기」가 뜬다', async () => {
    const input = makeLinesInput();
    const onlyNew: ViewerInput = {
      ...input,
      highlights: input.highlights.filter((h) => h.innerBox === undefined),
      items: input.items.filter((entry) => entry.id !== 'u'),
    };
    const { view } = await setup(undefined, onlyNew);
    expect(
      within(view.container).getByLabelText(/좁힌 자리로 보기/),
    ).toBeTruthy();
  });

  it('좁힌 자리를 끄면 문단 전체 상자 하나로 돌아간다', async () => {
    const { pane, view } = await setupLines();
    fireEvent.click(within(view.container).getByLabelText(/좁힌 자리로 보기/));
    expect(pieces(pane('a'), 's-a t-a').map((piece) => piece.rect)).toEqual([
      [50, 380, 500, 70],
    ]);
  });
});
