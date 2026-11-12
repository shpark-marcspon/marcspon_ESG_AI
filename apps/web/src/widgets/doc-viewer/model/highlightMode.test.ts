import { describe, expect, it } from 'vitest';

import type { Highlight } from './contract.ts';
import {
  DEFAULT_HIGHLIGHT_MODE,
  HIGHLIGHT_MODES,
  isDrawn,
  isHighlightMode,
} from './highlightMode.ts';
import type { HighlightMode } from './highlightMode.ts';

const h = (id: string, kind: string): Highlight => ({
  id,
  documentId: 'a',
  page: 1,
  box: [0, 0, 10, 10],
  kind,
});
const set = (...ids: string[]): ReadonlySet<string> => new Set(ids);

describe('isDrawn: 이 강조의 상자를 그리는가', () => {
  // 강조 넷: 고른 것, 가리킨 것, 켜진 종류의 나머지, 꺼진 종류의 나머지. 그리고 꺼진 종류인데 고른 것·가리킨 것.
  const all = [
    h('picked', 'x'),
    h('pointed', 'x'),
    h('rest-on', 'x'),
    h('rest-off', 'off'),
    h('picked-off', 'off'),
    h('pointed-off', 'off'),
  ];
  const drawn = (mode: HighlightMode) =>
    all
      .filter((highlight) =>
        isDrawn(highlight, {
          mode,
          hiddenKinds: set('off'),
          selectedIds: set('picked', 'picked-off'),
          pointedIds: set('pointed', 'pointed-off'),
        }),
      )
      .map((highlight) => highlight.id);

  it('옅게·전체 채움: 꺼진 종류의 나머지만 빠진다. 고른 것과 가리킨 것은 종류가 꺼져 있어도 남는다', () => {
    expect(drawn('outline')).toEqual([
      'picked',
      'pointed',
      'rest-on',
      'picked-off',
      'pointed-off',
    ]);
    expect(drawn('fill')).toEqual([
      'picked',
      'pointed',
      'rest-on',
      'picked-off',
      'pointed-off',
    ]);
  });

  it('고른 것만: 고른 것과 가리킨 것만 남는다', () => {
    expect(drawn('selected')).toEqual([
      'picked',
      'pointed',
      'picked-off',
      'pointed-off',
    ]);
  });

  it('아무것도 고르지 않았고 끈 종류도 없으면: 고른 것만에서는 0개, 나머지 두 방식에서는 전부', () => {
    const none = { hiddenKinds: set(), selectedIds: set(), pointedIds: set() };
    expect(
      all.filter((highlight) =>
        isDrawn(highlight, { mode: 'selected', ...none }),
      ),
    ).toHaveLength(0);
    expect(
      all.filter((highlight) =>
        isDrawn(highlight, { mode: 'outline', ...none }),
      ),
    ).toHaveLength(all.length);
    expect(
      all.filter((highlight) => isDrawn(highlight, { mode: 'fill', ...none })),
    ).toHaveLength(all.length);
  });
});

describe('보기 방식의 목록', () => {
  it('기본값은 옅게이고, 방식은 셋이다', () => {
    expect(DEFAULT_HIGHLIGHT_MODE).toBe('outline');
    expect(HIGHLIGHT_MODES.map((entry) => entry.mode)).toEqual([
      'outline',
      'selected',
      'fill',
    ]);
  });

  it('주소로 받은 값은 아는 방식일 때만 받는다', () => {
    expect(isHighlightMode('fill')).toBe(true);
    expect(isHighlightMode('Fill')).toBe(false);
    expect(isHighlightMode(null)).toBe(false);
    expect(isHighlightMode('')).toBe(false);
  });
});
