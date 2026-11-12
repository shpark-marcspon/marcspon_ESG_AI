import { describe, expect, it } from 'vitest';

import { innerBoxesOf, parseViewerInput } from './contract.ts';

/** 맞는 자료 하나. 테스트마다 한 군데만 망가뜨려 본다. */
function valid() {
  return {
    version: 1,
    documents: [
      {
        id: 'a',
        url: 'a.pdf',
        pages: [
          { width: 600, height: 800 },
          { width: 600, height: 800 },
        ],
      },
    ],
    highlights: [
      {
        id: 'h1',
        documentId: 'a',
        page: 2,
        box: [10, 20, 110, 60],
        kind: 'match',
      },
    ],
    items: [
      {
        id: 'i1',
        title: '항목',
        highlightIds: ['h1'],
        review: { status: 'pending' },
      },
    ],
  };
}
const errorsOf = (raw: unknown) => {
  const result = parseViewerInput(raw);
  return result.ok ? [] : result.errors;
};

describe('parseViewerInput', () => {
  it('맞는 자료는 통과한다', () => {
    expect(parseViewerInput(valid()).ok).toBe(true);
  });

  it('없는 강조를 가리키는 항목', () => {
    const raw = valid();
    raw.items[0]!.highlightIds = ['h1', 'h9'];
    expect(errorsOf(raw)).toEqual(['items "i1": 없는 강조 "h9" 를 가리킨다']);
  });

  it('없는 쪽을 가리키는 강조', () => {
    const raw = valid();
    raw.highlights[0]!.page = 3;
    expect(errorsOf(raw)).toEqual([
      'highlights "h1": 없는 쪽 3 를 가리킨다(문서 "a" 는 2쪽)',
    ]);
  });

  it('없는 문서를 가리키는 강조', () => {
    const raw = valid();
    raw.highlights[0]!.documentId = 'z';
    expect(errorsOf(raw)).toEqual([
      'highlights "h1": 없는 문서 "z" 를 가리킨다',
    ]);
  });

  it('쪽 밖으로 나가는 상자, 뒤집힌 상자', () => {
    const outside = valid();
    outside.highlights[0]!.box = [10, 20, 700, 60];
    expect(errorsOf(outside)[0]).toContain('쪽(600×800) 밖으로 나간다');

    const flipped = valid();
    flipped.highlights[0]!.box = [10, 60, 110, 20];
    expect(errorsOf(flipped)[0]).toContain(
      '왼쪽·위가 오른쪽·아래보다 작아야 한다',
    );
  });

  it('좁힌 자리(innerBox)도 같은 검사를 받는다', () => {
    const raw = valid() as ReturnType<typeof valid> & {
      highlights: { innerBox?: number[] }[];
    };
    raw.highlights[0]!.innerBox = [10, 20, 110, 900];
    expect(errorsOf(raw)[0]).toContain('innerBox 가 쪽');
  });

  // ── 좁힌 자리의 두 꼴: 예전(innerBox 하나)과 지금(innerBoxes 여럿) ──
  type Loose = ReturnType<typeof valid> & {
    highlights: { innerBox?: number[]; innerBoxes?: number[][] }[];
  };

  it('좁힌 자리가 없는 강조, 예전 꼴(innerBox 하나), 새 꼴(innerBoxes 여럿)을 다 받고, innerBoxesOf 가 하나로 읽는다', () => {
    const none = parseViewerInput(valid());
    expect(none.ok && innerBoxesOf(none.input.highlights[0]!)).toEqual([]);

    const old = valid() as Loose;
    old.highlights[0]!.innerBox = [20, 30, 60, 40];
    const oldResult = parseViewerInput(old);
    expect(
      oldResult.ok && innerBoxesOf(oldResult.input.highlights[0]!),
    ).toEqual([[20, 30, 60, 40]]);

    const many = valid() as Loose;
    many.highlights[0]!.innerBoxes = [
      [60, 30, 100, 40],
      [20, 42, 50, 52],
    ];
    const manyResult = parseViewerInput(many);
    expect(
      manyResult.ok && innerBoxesOf(manyResult.input.highlights[0]!),
    ).toEqual([
      [60, 30, 100, 40],
      [20, 42, 50, 52],
    ]);
  });

  it('innerBoxes 의 상자마다 같은 검사를 받는다: 쪽 밖이면, 뒤집혔으면 거부하고 몇 번째인지 말한다', () => {
    const outside = valid() as Loose;
    outside.highlights[0]!.innerBoxes = [
      [20, 30, 60, 40],
      [20, 42, 650, 52],
    ];
    expect(errorsOf(outside)).toEqual([
      'highlights "h1": innerBoxes[1] 가 쪽(600×800) 밖으로 나간다',
    ]);

    const flipped = valid() as Loose;
    flipped.highlights[0]!.innerBoxes = [[60, 30, 20, 40]];
    expect(errorsOf(flipped)[0]).toContain(
      'innerBoxes[0] 의 왼쪽·위가 오른쪽·아래보다 작아야 한다',
    );
  });

  it('innerBoxes 는 비어 있으면 안 되고, innerBox 와 같이 줄 수 없다', () => {
    const empty = valid() as Loose;
    empty.highlights[0]!.innerBoxes = [];
    expect(errorsOf(empty)[0]).toContain('highlights.0.innerBoxes');

    const both = valid() as Loose;
    both.highlights[0]!.innerBox = [20, 30, 60, 40];
    both.highlights[0]!.innerBoxes = [[20, 30, 60, 40]];
    expect(errorsOf(both)[0]).toContain(
      'innerBox 와 innerBoxes 를 같이 줄 수 없다',
    );
  });

  it('id 가 겹치면 안 된다', () => {
    const raw = valid();
    raw.highlights.push({ ...raw.highlights[0]! });
    raw.items.push({ ...raw.items[0]! });
    expect(errorsOf(raw)).toEqual([
      'highlights: id "h1" 가 둘 이상이다',
      'items: id "i1" 가 둘 이상이다',
    ]);
  });

  it('꼴이 틀리면 어느 필드인지 말한다', () => {
    const raw = valid() as unknown as {
      items: { review: unknown }[];
      version: number;
    };
    raw.items[0]!.review = { status: 'rejected' }; // 반려인데 사유가 없다
    raw.version = 2;
    const errors = errorsOf(raw);
    expect(errors.some((error) => error.startsWith('version'))).toBe(true);
    expect(
      errors.some((error) => error.startsWith('items.0.review.reason')),
    ).toBe(true);
  });

  it('문서는 하나 또는 둘', () => {
    const raw = valid();
    raw.documents = [];
    expect(errorsOf(raw)[0]).toMatch(/^documents/);
    const three = valid();
    three.documents = [1, 2, 3].map((n) => ({
      ...three.documents[0]!,
      id: `d${n}`,
    }));
    expect(errorsOf(three)[0]).toMatch(/^documents/);
  });
});
