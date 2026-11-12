import { describe, expect, it } from 'vitest';

import type { Highlight, Item } from './contract.ts';
import {
  contextBoxes,
  groupHighlights,
  shapeOf,
  unionBox,
} from './highlightGroups.ts';
import { neighborItem, pickFromHighlights } from './selection.ts';

const item = (id: string, highlightIds: string[]): Item => ({
  id,
  title: id,
  highlightIds,
  review: { status: 'pending' },
});
const items = [
  item('1', ['1-a', '1-b']),
  item('2', ['2-a']),
  item('3', ['3-a', '3-b']),
];

describe('pickFromHighlights', () => {
  it('그 강조를 가리키는 항목을 고른다', () => {
    expect(pickFromHighlights(items, ['2-a'], null)).toBe('2');
  });
  it('겹친 강조: 누를 때마다 다음 항목으로 돈다', () => {
    expect(pickFromHighlights(items, ['1-b', '3-b'], null)).toBe('1');
    expect(pickFromHighlights(items, ['1-b', '3-b'], '1')).toBe('3');
    expect(pickFromHighlights(items, ['1-b', '3-b'], '3')).toBe('1');
  });
  it('가리키는 항목이 없으면 null', () => {
    expect(pickFromHighlights(items, ['zzz'], '1')).toBeNull();
  });
});

describe('neighborItem', () => {
  it('다음·이전. 끝에서 멈춘다', () => {
    expect(neighborItem(items, null, 1)).toBe('1');
    expect(neighborItem(items, '1', 1)).toBe('2');
    expect(neighborItem(items, '3', 1)).toBe('3');
    expect(neighborItem(items, '2', -1)).toBe('1');
    expect(neighborItem(items, '1', -1)).toBe('1');
    expect(neighborItem([], null, 1)).toBeNull();
  });
});

describe('groupHighlights', () => {
  const h = (
    id: string,
    kind: string,
    innerBox?: Highlight['innerBox'],
  ): Highlight => ({
    id,
    documentId: 'a',
    page: 1,
    box: [0, 0, 100, 100],
    innerBox,
    kind,
  });
  const highlights = [
    h('x', 'match', [10, 10, 20, 20]),
    h('y', 'mismatch', [30, 10, 40, 20]),
    h('z', 'match'),
  ];

  it('좁힌 자리로 그릴 때: 좁힌 자리마다 하나, 없는 것은 큰 상자. 큰 상자가 먼저(아래에) 온다', () => {
    const groups = groupHighlights(highlights, new Set(['y']), true);
    expect(groups.map((g) => [g.highlightIds, g.narrowed, g.selected])).toEqual(
      [
        [['z'], false, false],
        [['x'], true, false],
        [['y'], true, true],
      ],
    );
  });
  it('큰 상자로 그릴 때: 같은 자리는 하나로 묶인다. 종류가 섞이면 kind 는 null', () => {
    const groups = groupHighlights(highlights, new Set(['y']), false);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({
      highlightIds: ['x', 'y', 'z'],
      kind: null,
      selected: true,
      narrowed: false,
    });
  });
  it('contextBoxes: 좁힌 자리로 그린 강조가 골라졌을 때만 바깥 상자를 준다', () => {
    expect(contextBoxes(highlights, new Set(['y']), true)).toEqual([
      [0, 0, 100, 100],
    ]);
    expect(contextBoxes(highlights, new Set(['z']), true)).toEqual([]);
    expect(contextBoxes(highlights, new Set(['y']), false)).toEqual([]);
  });

  // ── 강조 하나에 상자 여럿 ──
  const lines: Highlight = {
    id: 's',
    documentId: 'a',
    page: 1,
    box: [0, 0, 100, 100],
    innerBoxes: [
      [60, 10, 100, 20],
      [0, 22, 30, 32],
    ],
    kind: 'sentence',
  };

  it('상자가 여럿인 강조는 묶음 하나다. 묶음이 그 상자들을 전부 가진다(첫 것만도, 감싼 큰 상자 하나도 아니다)', () => {
    const groups = groupHighlights([lines], new Set(), true);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({
      highlightIds: ['s'],
      boxes: [
        [60, 10, 100, 20],
        [0, 22, 30, 32],
      ],
      narrowed: true,
    });
    expect(shapeOf(lines, true).boxes).toEqual([
      [60, 10, 100, 20],
      [0, 22, 30, 32],
    ]);
    // 좁힌 자리를 끄면 문단 전체 상자 하나다.
    expect(shapeOf(lines, false)).toEqual({
      boxes: [[0, 0, 100, 100]],
      narrowed: false,
    });
  });
  it('상자들이 전부 같은 강조끼리만 묶인다. 한 줄만 같은 강조는 따로다', () => {
    const same: Highlight = { ...lines, id: 't', kind: 'other' };
    const firstLineOnly: Highlight = {
      ...lines,
      id: 'u',
      innerBoxes: [[60, 10, 100, 20]],
    };
    const groups = groupHighlights(
      [lines, same, firstLineOnly],
      new Set(['t']),
      true,
    );
    expect(
      groups.map((g) => [g.highlightIds, g.boxes.length, g.selected, g.kind]),
    ).toEqual([
      [['s', 't'], 2, true, null],
      [['u'], 1, false, 'sentence'],
    ]);
  });
  it('여러 줄 강조의 크기는 줄 조각을 다 합친 것이다: 첫 줄 조각이 작아도, 둘째 줄 안에 놓인 작은 강조가 그 위에(나중에) 온다', () => {
    // 문장이 줄 끝에서 시작한다: 첫 줄 조각은 10×10, 둘째 줄 조각은 300×10. 숫자 하나(20×10)가 그 둘째 줄 안에 있다.
    // 숫자가 나중에 그려져야 문장의 조각에 덮이지 않고 눌린다. 입력의 차례와는 상관없다.
    const sentence: Highlight = {
      id: 's',
      documentId: 'a',
      page: 1,
      box: [0, 0, 400, 100],
      innerBoxes: [
        [390, 10, 400, 20],
        [0, 22, 300, 32],
      ],
      kind: 'sentence',
    };
    const number: Highlight = {
      id: 'n',
      documentId: 'a',
      page: 1,
      box: [0, 0, 400, 100],
      innerBox: [100, 22, 120, 32],
      kind: 'match',
    };
    for (const input of [
      [sentence, number],
      [number, sentence],
    ]) {
      expect(
        groupHighlights(input, new Set(), true).map((g) => g.highlightIds),
      ).toEqual([['s'], ['n']]);
    }
  });
  it('예전 꼴(innerBox 하나)은 상자 하나짜리 묶음이다', () => {
    expect(
      groupHighlights([h('x', 'match', [10, 10, 20, 20])], new Set(), true)[0]!
        .boxes,
    ).toEqual([[10, 10, 20, 20]]);
  });
  it('unionBox: 상자들을 전부 감싼 상자(강조로 갈 때의 스크롤 자리를 여기서 잰다)', () => {
    expect(
      unionBox([
        [60, 10, 100, 20],
        [0, 22, 30, 32],
      ]),
    ).toEqual([0, 10, 100, 32]);
    expect(unionBox([[5, 6, 7, 8]])).toEqual([5, 6, 7, 8]);
    // 둘째 줄이 첫 줄보다 오른쪽까지 가는 경우(첫 상자의 변만 봐서는 안 된다).
    expect(
      unionBox([
        [60, 10, 100, 20],
        [0, 22, 130, 32],
      ]),
    ).toEqual([0, 10, 130, 32]);
  });
});
