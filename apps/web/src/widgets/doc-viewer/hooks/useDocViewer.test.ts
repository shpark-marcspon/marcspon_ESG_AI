// @vitest-environment jsdom
// 뷰어의 상태와 규칙을 화면 없이 본다. 마크업이 하나도 없다: 훅을 부르고, 돌려준 값만 읽는다.
// 여기 있는 규칙들은 전에 DocumentViewer.tsx 안에 있었고 화면을 그려야만 볼 수 있었다(ui/DocumentViewer.test.tsx 가 지금도 화면으로 본다).
import type { KeyboardEvent } from 'react';

import { act, renderHook } from '@testing-library/react';

import { describe, expect, it } from 'vitest';

import { isDrawn } from '../model/index.ts';
import type {
  HighlightMode,
  ReviewState,
  ViewerInput,
} from '../model/index.ts';
import {
  makeLinesInput,
  makeOverlapInput,
  makeTwoDocInput,
} from '../model/testing.ts';
import { useDocViewer } from './useDocViewer.ts';

const NO_REVIEWS: ReadonlyMap<string, ReviewState> = new Map();

function setup(
  input: ViewerInput,
  highlightMode?: HighlightMode,
  reviews = NO_REVIEWS,
) {
  const hook = renderHook(() =>
    useDocViewer({ input, reviews, highlightMode }),
  );
  const viewer = () => hook.result.current;
  /** 그 문서의 그 쪽에 지금 그려질 강조의 id. */
  const drawn = (documentId: string, page: number) =>
    viewer()
      .highlightsOn(documentId, page)
      .filter((h) => isDrawn(h, viewer().draw))
      .map((h) => h.id);
  const selected = () =>
    viewer()
      .rows.filter((row) => row.selected)
      .map((row) => row.item.id);
  return { viewer, drawn, selected };
}

/** 키 하나를 누른 것처럼 onKeyDown 을 부른다. preventDefault 를 불렀는지 돌려준다. */
function press(
  viewer: () => { onKeyDown(event: KeyboardEvent): void },
  key: string,
  init: {
    target?: EventTarget;
    ctrlKey?: boolean;
    metaKey?: boolean;
    altKey?: boolean;
  } = {},
): boolean {
  let prevented = false;
  const event = {
    key,
    target: document.body,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    ...init,
    preventDefault: () => void (prevented = true),
  };
  act(() => viewer().onKeyDown(event as unknown as KeyboardEvent));
  return prevented;
}

describe('고르기', () => {
  it('처음에는 아무것도 골라지지 않았고, 문서 칸이 갈 곳도 없다', () => {
    const { viewer, selected } = setup(makeTwoDocInput());
    expect(viewer().selectedItemId).toBeNull();
    expect(selected()).toEqual([]);
    expect(viewer().revealFor('a')).toBeNull();
    expect(viewer().draw.selectedIds.size).toBe(0);
  });

  it('항목을 고르면 그 강조들이 골라지고, 문서마다 그 문서에 있는 강조로 가라고 한다', () => {
    const { viewer, selected } = setup(makeTwoDocInput());
    act(() => viewer().select('2'));
    expect(selected()).toEqual(['2']);
    expect([...viewer().draw.selectedIds]).toEqual(['2-a', '2-b']);
    expect(viewer().revealFor('a')).toEqual({
      highlightId: '2-a',
      page: 4,
      box: [50, 300, 150, 330],
      seq: 1,
    });
    expect(viewer().revealFor('b')).toEqual({
      highlightId: '2-b',
      page: 1,
      box: [50, 300, 150, 330],
      seq: 1,
    });
  });

  it('그 문서에 강조가 없는 항목이면 그 문서 칸은 가만히 있는다', () => {
    const { viewer } = setup(makeTwoDocInput());
    act(() => viewer().select('3'));
    expect(viewer().revealFor('a')?.highlightId).toBe('3-a');
    expect(viewer().revealFor('b')).toBeNull();
  });

  it('같은 항목을 다시 고르면 seq 가 올라간다(그 자리로 다시 가라는 뜻)', () => {
    const { viewer } = setup(makeTwoDocInput());
    act(() => viewer().select('2'));
    act(() => viewer().select('2'));
    expect(viewer().revealFor('a')?.seq).toBe(2);
    expect(viewer().selectedItemId).toBe('2');
  });

  it('null 을 고르면 아무 일도 없다(가리키는 항목이 없는 상자를 눌렀을 때)', () => {
    const { viewer } = setup(makeTwoDocInput());
    act(() => viewer().select('2'));
    act(() => viewer().select(null));
    act(() => viewer().pick(['없는 강조']));
    expect(viewer().selectedItemId).toBe('2');
    expect(viewer().revealFor('a')?.seq).toBe(1);
  });
});

describe('문서의 상자를 눌러 고르기', () => {
  it('상자를 누르면 그것을 가리키는 항목이 골라진다', () => {
    const { viewer, selected } = setup(makeTwoDocInput());
    act(() => viewer().pick(['2-b']));
    expect(selected()).toEqual(['2']);
    // 다른 문서 칸도 따라간다.
    expect(viewer().revealFor('a')?.highlightId).toBe('2-a');
  });

  it('같은 자리에 겹친 상자는 누를 때마다 다음 항목으로 돈다', () => {
    const { viewer, selected } = setup(makeOverlapInput());
    act(() => viewer().pick(['1-b', '4-b']));
    expect(selected()).toEqual(['1']);
    act(() => viewer().pick(['1-b', '4-b']));
    expect(selected()).toEqual(['4']);
    act(() => viewer().pick(['1-b', '4-b']));
    expect(selected()).toEqual(['1']);
  });
});

describe('키보드', () => {
  it('j 는 다음 항목, k 는 이전 항목. 아무것도 안 골랐으면 첫 항목, 끝에서 멈춘다', () => {
    const { viewer, selected } = setup(makeTwoDocInput());
    expect(press(viewer, 'j')).toBe(true);
    expect(selected()).toEqual(['1']);
    press(viewer, 'j');
    press(viewer, 'j');
    press(viewer, 'j');
    expect(selected()).toEqual(['3']);
    press(viewer, 'k');
    expect(selected()).toEqual(['2']);
  });

  it('글자를 적는 중이거나 Ctrl·Meta·Alt 와 같이 누르면 흘려보낸다. 다른 키도 그렇다', () => {
    const { viewer, selected } = setup(makeTwoDocInput());
    expect(
      press(viewer, 'j', { target: document.createElement('textarea') }),
    ).toBe(false);
    expect(
      press(viewer, 'j', { target: document.createElement('input') }),
    ).toBe(false);
    expect(press(viewer, 'j', { ctrlKey: true })).toBe(false);
    expect(press(viewer, 'j', { metaKey: true })).toBe(false);
    expect(press(viewer, 'k', { altKey: true })).toBe(false);
    expect(press(viewer, 'x')).toBe(false);
    expect(selected()).toEqual([]);
  });
});

describe('가리키기(마우스를 올리거나 초점이 가면)', () => {
  it('가리킨 항목의 강조가 pointedIds 에 든다. 고르지도 않고 갈 곳도 생기지 않는다', () => {
    const { viewer } = setup(makeTwoDocInput());
    act(() => viewer().point('hover', '2'));
    expect([...viewer().draw.pointedIds]).toEqual(['2-a', '2-b']);
    expect(viewer().selectedItemId).toBeNull();
    expect(viewer().revealFor('a')).toBeNull();
    act(() => viewer().point('hover', null));
    expect(viewer().draw.pointedIds.size).toBe(0);
  });

  it('마우스를 올린 것이 초점이 간 것보다 먼저다. 마우스를 떼면 초점이 간 것으로 돌아간다', () => {
    const { viewer } = setup(makeOverlapInput());
    act(() => viewer().point('focus', '5'));
    expect([...viewer().draw.pointedIds]).toEqual(['5-b']);
    act(() => viewer().point('hover', '1'));
    expect([...viewer().draw.pointedIds]).toEqual(['1-b']);
    act(() => viewer().point('hover', null));
    expect([...viewer().draw.pointedIds]).toEqual(['5-b']);
  });

  it('다른 항목을 고르면 초점으로 가리킨 것을 지운다(초점은 옛 항목의 단추에 남아 있다)', () => {
    const { viewer } = setup(makeOverlapInput());
    act(() => viewer().point('focus', '1'));
    act(() => viewer().select('1'));
    // 같은 항목을 고른 것이면 그대로 둔다.
    expect([...viewer().draw.pointedIds]).toEqual(['1-b']);
    act(() => viewer().select('4'));
    expect(viewer().draw.pointedIds.size).toBe(0);
  });

  it('다른 항목을 골라도 마우스로 가리킨 것은 남는다(마우스가 실제로 그 위에 있다)', () => {
    const { viewer } = setup(makeOverlapInput());
    act(() => viewer().point('hover', '5'));
    act(() => viewer().select('1'));
    expect([...viewer().draw.pointedIds]).toEqual(['5-b']);
  });

  it('같은 것을 다시 가리키면 상태가 바뀌지 않는다(다시 그리지 않는다)', () => {
    const { viewer } = setup(makeTwoDocInput());
    act(() => viewer().point('hover', '2'));
    const before = viewer().draw.pointedIds;
    act(() => viewer().point('hover', '2'));
    expect(viewer().draw.pointedIds).toBe(before);
  });
});

describe('범례로 종류 켜고 끄기', () => {
  it('입력이 준 종류마다 칸이 하나씩 있고, 누를 때마다 켜짐이 뒤집힌다', () => {
    const { viewer } = setup(makeTwoDocInput());
    expect(
      viewer().legend.map((entry) => `${entry.kind}:${entry.shown}`),
    ).toEqual(['match:true', 'mismatch:true', 'unverified:true']);
    act(() => viewer().toggleKind('mismatch'));
    expect(
      viewer().legend.map((entry) => `${entry.kind}:${entry.shown}`),
    ).toEqual(['match:true', 'mismatch:false', 'unverified:true']);
    act(() => viewer().toggleKind('mismatch'));
    expect(viewer().legend.every((entry) => entry.shown)).toBe(true);
  });

  it('끈 종류의 강조는 그리지 않는다. 다른 종류는 그대로다', () => {
    const { viewer, drawn } = setup(makeTwoDocInput());
    act(() => viewer().toggleKind('mismatch'));
    expect(drawn('b', 1)).toEqual([]);
    expect(drawn('a', 1)).toEqual(['1-a']);
  });

  it('꺼진 종류여도 고른 것과 가리킨 것은 그린다', () => {
    const { viewer, drawn } = setup(makeTwoDocInput());
    act(() => viewer().toggleKind('mismatch'));
    act(() => viewer().select('2'));
    expect(drawn('b', 1)).toEqual(['2-b']);
    act(() => viewer().select('3'));
    expect(drawn('b', 1)).toEqual([]);
    act(() => viewer().point('hover', '2'));
    expect(drawn('b', 1)).toEqual(['2-b']);
  });

  it('목록의 줄: 강조가 전부 꺼진 종류일 때만 kindHidden 이다(종류가 섞인 항목은 하나라도 켜져 있으면 아니다)', () => {
    const input = makeTwoDocInput();
    // 항목 1 의 강조 둘을 서로 다른 종류로 만든다(1-a 일치, 1-b 불일치).
    const mixed: ViewerInput = {
      ...input,
      highlights: input.highlights.map((h) =>
        h.id === '1-b' ? { ...h, kind: 'mismatch' } : h,
      ),
    };
    const { viewer } = setup(mixed);
    const hidden = () => viewer().rows.map((row) => row.kindHidden);
    expect(viewer().rows[0]!.kinds).toEqual(['match', 'mismatch']);
    act(() => viewer().toggleKind('mismatch'));
    expect(hidden()).toEqual([false, true, false]);
    act(() => viewer().toggleKind('match'));
    expect(hidden()).toEqual([true, true, false]);
  });

  it('꺼진 종류의 항목도 j·k 가 그대로 밟는다', () => {
    const { viewer, selected } = setup(makeTwoDocInput());
    act(() => viewer().toggleKind('mismatch'));
    press(viewer, 'j');
    press(viewer, 'j');
    expect(selected()).toEqual(['2']);
  });
});

describe('보기 방식', () => {
  it('안 주면 옅게(outline)다', () => {
    expect(setup(makeTwoDocInput()).viewer().mode).toBe('outline');
    expect(setup(makeTwoDocInput()).viewer().draw.mode).toBe('outline');
  });

  it('고른 것만(selected): 고르기 전에는 그릴 것이 없고, 고른 것과 가리킨 것만 그린다', () => {
    const { viewer, drawn } = setup(makeOverlapInput(), 'selected');
    expect(drawn('b', 1)).toEqual([]);
    act(() => viewer().select('5'));
    expect(drawn('b', 1)).toEqual(['5-b']);
    act(() => viewer().point('hover', '4'));
    expect(drawn('b', 1)).toEqual(['4-b', '5-b']);
  });

  it('고른 것만: 항목을 눌러 고른 뒤(초점이 남는다) j 로 옮기면 앞 항목은 그려지지 않는다', () => {
    const { viewer, drawn } = setup(makeOverlapInput(), 'selected');
    act(() => viewer().point('focus', '1'));
    act(() => viewer().select('1'));
    press(viewer, 'j');
    expect(drawn('b', 1)).toEqual(['4-b']);
  });
});

describe('좁힌 자리와 여러 줄 강조', () => {
  it('좁힌 자리를 가진 강조가 있을 때만 hasInnerBoxes 다', () => {
    expect(setup(makeTwoDocInput()).viewer().hasInnerBoxes).toBe(false);
    expect(setup(makeLinesInput()).viewer().hasInnerBoxes).toBe(true);
  });

  it('갈 곳의 상자는 조각들을 전부 감싼 상자다. 좁힌 자리를 끄면 문단 전체 상자다', () => {
    const { viewer } = setup(makeLinesInput());
    act(() => viewer().select('s'));
    expect(viewer().revealFor('a')).toEqual({
      highlightId: 's-a',
      page: 2,
      box: [50, 400, 500, 428],
      seq: 1,
    });
    act(() => viewer().setUseInnerBox(false));
    expect(viewer().draw.useInnerBox).toBe(false);
    // seq 는 그대로다: 좁힌 자리를 껐다고 다시 가지는 않는다.
    expect(viewer().revealFor('a')).toEqual({
      highlightId: 's-a',
      page: 2,
      box: [50, 380, 550, 450],
      seq: 1,
    });
  });
});

describe('목록의 줄', () => {
  it('검토 상태는 밖에서 받은 것이 먼저고, 없으면 입력의 것이다', () => {
    const reviews = new Map<string, ReviewState>([
      ['2', { status: 'rejected', reason: '단위가 다르다' }],
    ]);
    const { viewer } = setup(makeTwoDocInput(), undefined, reviews);
    expect(viewer().rows.map((row) => row.review.status)).toEqual([
      'pending',
      'rejected',
      'pending',
    ]);
  });

  it('쪽마다의 강조는 입력의 차례대로다. 강조가 없는 쪽은 빈 목록이다', () => {
    const { viewer } = setup(makeOverlapInput());
    expect(
      viewer()
        .highlightsOn('b', 1)
        .map((h) => h.id),
    ).toEqual(['1-b', '4-b', '5-b']);
    expect(viewer().highlightsOn('b', 2)).toEqual([]);
    expect(viewer().highlightsOn('없는 문서', 1)).toEqual([]);
  });
});
