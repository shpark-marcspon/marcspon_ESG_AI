// 변환 스크립트를 작은 가짜 입력으로 돌려 본다. 실제 자료는 쓰지 않는다.
import { describe, expect, it } from 'vitest';

import { parseViewerInput } from '../../src/widgets/doc-viewer/model/index.ts';
import { innerBoxesOf } from '../../src/widgets/doc-viewer/model/index.ts';
import type { LabDocument, LabOutcome } from './model.ts';
import { indexPlaces } from './places.ts';
import type { CharPlaces, PlaceContainer } from './places.ts';
import { buildReconcileInput, resolveTarget } from './reconcile.ts';
import type { Side } from './reconcile.ts';
import { buildSentenceInput, splitSentences } from './sentences.ts';

const source = { sha256: '0'.repeat(64) };

/**
 * 가짜 글자 자리의 그릇 하나. 글의 줄마다 토막 하나이고, 글자 하나의 폭은 10 이다(줄의 첫 글자가 x 에서 시작한다).
 * 줄과 줄 사이의 빈칸 하나에는 좌표가 없다(문서를 분해하는 쪽이 줄을 이을 때 끼우는 빈칸).
 */
function container(
  id: string,
  page: number,
  lines: { text: string; x: number; y: number }[],
): PlaceContainer {
  let start = 0;
  const runs = lines.map((line) => {
    const run = {
      start,
      y0: line.y,
      y1: line.y + 10,
      x0: [...line.text].map((_, k) => line.x + k * 10),
      x1: [...line.text].map((_, k) => line.x + k * 10 + 10),
    };
    start += line.text.length + 1;
    return run;
  });
  return {
    id,
    kind: id.includes(':') ? 'cell' : 'block',
    page,
    bbox: [0, 0, 1, 1],
    runs,
  };
}
const places = (...containers: PlaceContainer[]) =>
  indexPlaces({
    schema_version: '0.1',
    source,
    unit: 'utf16',
    containers,
    unlinked: [],
  } satisfies CharPlaces);

const docA: LabDocument = {
  source,
  pages: [
    { page: 1, width: 600, height: 800 },
    { page: 2, width: 600, height: 800 },
  ],
  blocks: [
    {
      id: 'p1-b1',
      page: 1,
      kind: 'paragraph',
      bbox: [50, 100, 550, 120],
      text: '2024년 배출량은 1,234톤이다.',
    },
    { id: 'p2-b1', page: 2, kind: 'table', bbox: [50, 200, 550, 260] },
  ],
  tables: [
    {
      id: 'p2-t1',
      page: 2,
      bbox: [50, 200, 550, 260],
      cells: [
        ['구분', '2023', '2024'],
        ['배출량', '1,300', '1,234'],
        ['비율', '40% / 60%', '55'],
      ],
    },
  ],
};
const docB: LabDocument = {
  source,
  pages: [{ page: 1, width: 800, height: 600 }],
  blocks: [],
  tables: [
    {
      id: 'p1-t1',
      page: 1,
      bbox: [100, 100, 700, 160],
      cells: [
        ['구분', '2024'],
        ['배출량', '1,234'],
        ['기타', '77'],
      ],
    },
  ],
};
const outcome: LabOutcome = {
  after: {
    verdicts: [
      { a: 'p1-b1#n2', b: 'p1-t1:r1c1', outcome: 'match', reason: 'exact' },
      {
        a: 'p2-t1:r1c2',
        b: 'p1-t1:r1c1',
        outcome: 'mismatch',
        reason: 'values_differ',
      },
    ],
  },
  states: {
    a: {
      'p1-b1#n2': 'compared:match',
      'p2-t1:r1c2': 'compared:mismatch',
      'p2-t1:r2c1#n2': 'asked:no_counterpart:different_item',
      'p2-t1:r1c1': 'unverified:table_not_paired',
    },
    b: { 'p1-t1:r1c1': 'compared:match', 'p1-t1:r2c1': 'left:in_paired_table' },
  },
};
const sideA: Side = { id: 'a', title: 'A', url: 'a.pdf', document: docA };
const sideB: Side = { id: 'b', title: 'B', url: 'b.pdf', document: docB };

describe('resolveTarget', () => {
  it('칸: 상자는 표 전체, 값은 그 칸', () => {
    const result = resolveTarget(sideA, 'p2-t1:r1c2');
    expect(result).toMatchObject({
      ok: true,
      target: {
        page: 2,
        box: [50, 200, 550, 260],
        form: 'cell',
        value: '1,234',
        containerId: 'p2-t1:r1c2',
        span: null,
      },
    });
  });
  it('칸 안의 n번째 숫자', () => {
    const result = resolveTarget(sideA, 'p2-t1:r2c1#n2');
    // "40% / 60%" 에서 60 은 여섯째 자리(0부터)에서 시작하고, 범위는 뒤의 % 까지다. 값(value)은 몸통만이다.
    expect(result).toMatchObject({
      ok: true,
      target: {
        form: 'cell#n',
        value: '60',
        containerId: 'p2-t1:r2c1',
        span: { start: 6, end: 9 },
      },
    });
  });
  it('문단의 n번째 숫자: 상자는 문단 전체', () => {
    const result = resolveTarget(sideA, 'p1-b1#n2');
    expect(result).toMatchObject({
      ok: true,
      target: {
        page: 1,
        box: [50, 100, 550, 120],
        form: 'block#n',
        value: '1,234',
      },
    });
  });
  it('없는 표·칸·숫자·문단은 오류', () => {
    for (const bad of [
      'p9-t9:r0c0',
      'p2-t1:r9c0',
      'p2-t1:r1c2#n2',
      'p1-b9#n1',
      'p1-b1#n9',
      'p2-b1#n1',
      '엉터리',
    ]) {
      expect(resolveTarget(sideA, bad).ok, bad).toBe(false);
    }
  });
  it('문단 안에서 값의 글자 범위는 글에서의 자리 그대로다(공백을 지우지 않는다. 글자 자리가 같은 자리를 쓴다)', () => {
    // "2024년 배출량은 1,234톤이다." 의 1,234 는 글의 11번째 자리(0부터)에서 시작해 16번째 자리 앞에서 끝난다.
    expect(resolveTarget(sideA, 'p1-b1#n2')).toMatchObject({
      ok: true,
      target: { containerId: 'p1-b1', span: { start: 11, end: 16 } },
    });
  });
  it('시험지가 값을 바꿨으면 판정이 본 값을 따로 든다', () => {
    const exam = {
      blocks: [],
      tables: [
        {
          id: 'p2-t1',
          cells: [
            ['구분', '2023', '2024'],
            ['배출량', '1,300', '9,999'],
            ['비율', '40% / 60%', '55'],
          ],
        },
      ],
    };
    const result = resolveTarget({ ...sideA, exam }, 'p2-t1:r1c2');
    expect(result).toMatchObject({
      ok: true,
      target: { value: '1,234', judgedValue: '9,999' },
    });
  });
});

describe('buildReconcileInput', () => {
  it('판정마다 항목 하나와 강조 둘, 짝 없는 자리마다 항목 하나와 강조 하나. 불일치가 먼저 온다', () => {
    const { input, problems, records } = buildReconcileInput(
      sideA,
      sideB,
      outcome,
    );
    expect(problems).toEqual([]);
    expect(parseViewerInput(input)).toMatchObject({ ok: true });

    expect(
      input.items.map((item) => [item.id, item.title, item.highlightIds]),
    ).toEqual([
      ['v2', '1,234 ≠ 1,234', ['v2-a', 'v2-b']],
      ['v1', '1,234 = 1,234', ['v1-a', 'v1-b']],
      ['u-a1', '60 · 짝 없음', ['u-a1']],
      ['u-b1', '77 · 짝 없음', ['u-b1']],
    ]);
    expect(
      input.highlights.map((h) => [h.id, h.documentId, h.page, h.kind]),
    ).toEqual([
      ['v2-a', 'a', 2, 'mismatch'],
      ['v2-b', 'b', 1, 'mismatch'],
      ['v1-a', 'a', 1, 'match'],
      ['v1-b', 'b', 1, 'match'],
      ['u-a1', 'a', 2, 'unverified'],
      ['u-b1', 'b', 1, 'unverified'],
    ]);
    // 글자 자리를 주지 않았으니 좁힌 자리는 없다. 짐작해서 넣지도 않는다. 그 사실을 알림에 적는다.
    expect(input.highlights.every((h) => innerBoxesOf(h).length === 0)).toBe(
      true,
    );
    expect(records.map((record) => record.result)).toEqual(
      Array.from({ length: 6 }, () => ({ found: false, reason: 'no_places' })),
    );
    expect(input.notice).toContain('글자 자리(char-places.json) 없이 변환했다');
    // 목록에 넣지 않은 것은 개수로 알린다.
    expect(input.notice).toContain('A 1자리, B 0자리');
    expect(input.documents.map((doc) => doc.pages.length)).toEqual([2, 1]);
  });

  // ── 글자 자리에서 좁은 상자를 얻는다. 자리 표기 세 꼴 ──
  // A: 1쪽 문단 「2024년 배출량은 1,234톤이다.」(x 50 에서 시작, 글자 폭 10), 2쪽 표의 칸 둘.  B: 1쪽 표의 칸 둘.
  const placesA = places(
    container('p1-b1', 1, [
      { text: '2024년 배출량은 1,234톤이다.', x: 50, y: 105 },
    ]),
    container('p2-t1:r1c2', 2, [{ text: '1,234', x: 400, y: 225 }]),
    container('p2-t1:r2c1', 2, [{ text: '40% / 60%', x: 200, y: 245 }]),
  );
  const placesB = places(
    container('p1-t1:r1c1', 1, [{ text: '1,234', x: 410, y: 125 }]),
  );

  it('표의 칸: 칸의 글 전체의 상자. box 는 표 전체 그대로다', () => {
    const { input, records } = buildReconcileInput(
      { ...sideA, places: placesA },
      { ...sideB, places: placesB },
      outcome,
    );
    const byId = new Map(input.highlights.map((h) => [h.id, h]));
    expect(byId.get('v1-b')!.innerBoxes).toEqual([[410, 125, 460, 135]]);
    expect(byId.get('v1-b')!.box).toEqual([100, 100, 700, 160]);
    expect(byId.get('v2-a')!.innerBoxes).toEqual([[400, 225, 450, 235]]);
    // 「77」의 칸(r2c1)은 글자 자리에 없다. 좁히지 않고 표 상자만 두고, 까닭을 기록에 남긴다.
    expect(innerBoxesOf(byId.get('u-b1')!)).toEqual([]);
    expect(
      records.find((record) => record.highlightId === 'u-b1')!.result,
    ).toEqual({ found: false, reason: 'container_missing' });
    expect(parseViewerInput(input)).toMatchObject({ ok: true });
    expect(input.notice).toContain('강조 6개 중 5개가 상자를 얻었다');
  });

  it('칸 안의 n번째 숫자: 그 숫자의 글자만(뒤의 % 까지) 덮는다', () => {
    // 「40% / 60%」 칸의 둘째 숫자(60). 60% 는 글의 6~9번째 자리 = x 260~290.
    const { input, records } = buildReconcileInput(
      { ...sideA, places: placesA },
      sideB,
      outcome,
    );
    const highlight = input.highlights.find((h) => h.id === 'u-a1')!;
    expect(highlight.text).toBe('60');
    expect(highlight.box).toEqual([50, 200, 550, 260]);
    expect(highlight.innerBoxes).toEqual([[260, 245, 290, 255]]);
    expect(
      records.find((record) => record.highlightId === 'u-a1'),
    ).toMatchObject({
      form: 'cell#n',
      result: { found: true, covered: 3, length: 3 },
    });
  });

  it('문단 속 n번째 숫자: 그 숫자의 글자만 덮는다. 같은 값이 두 번 나와도 가리킨 쪽이다', () => {
    // 「2024년 배출량은 1,234톤이다.」 의 둘째 숫자 1,234 는 11~16번째 자리 = x 160~210. 뒤의 「톤」은 덮지 않는다.
    const first = buildReconcileInput(
      { ...sideA, places: placesA },
      sideB,
      outcome,
    );
    expect(
      first.input.highlights.find((h) => h.id === 'v1-a')!.innerBoxes,
    ).toEqual([[160, 105, 210, 115]]);

    const text = '가 나 다 5건, 라 마 5건';
    const doc: LabDocument = {
      source,
      pages: [{ page: 1, width: 600, height: 800 }],
      blocks: [
        {
          id: 'p1-b1',
          page: 1,
          kind: 'paragraph',
          bbox: [0, 0, 300, 20],
          text,
        },
      ],
      tables: [],
    };
    const one: LabOutcome = {
      after: {
        verdicts: [
          { a: 'p1-b1#n2', b: 'p1-b1#n1', outcome: 'match', reason: 'exact' },
        ],
      },
      states: { a: {}, b: {} },
    };
    const side: Side = {
      id: 'a',
      title: 'A',
      url: 'a.pdf',
      document: doc,
      places: places(container('p1-b1', 1, [{ text, x: 0, y: 5 }])),
    };
    const { input } = buildReconcileInput(side, { ...side, id: 'b' }, one);
    // a 는 둘째 5(글의 14번째 자리), b 는 첫째 5(6번째 자리)를 가리킨다.
    expect(input.highlights.map((h) => h.innerBoxes)).toEqual([
      [[140, 5, 150, 15]],
      [[60, 5, 70, 15]],
    ]);
  });

  it('글자 범위가 두 줄에 걸치면 상자가 둘이다(줄마다 하나). 하나로 뭉치지 않는다', () => {
    // 한 숫자가 줄 끝에서 끊기는 일은 실제 자료에서 못 봤지만, 칸의 글이 두 줄인 칸은 있다: 칸 전체의 상자가 줄마다 하나다.
    const doc: LabDocument = {
      source,
      pages: [{ page: 1, width: 600, height: 800 }],
      blocks: [],
      tables: [
        { id: 'p1-t1', page: 1, bbox: [0, 0, 500, 100], cells: [['12 345']] },
      ],
    };
    const one: LabOutcome = {
      after: { verdicts: [] },
      states: { a: { 'p1-t1:r0c0': 'left:in_paired_table' }, b: {} },
    };
    const side: Side = {
      id: 'a',
      title: 'A',
      url: 'a.pdf',
      document: doc,
      places: places(
        container('p1-t1:r0c0', 1, [
          { text: '12', x: 300, y: 10 },
          { text: '345', x: 100, y: 30 },
        ]),
      ),
    };
    const { input, records } = buildReconcileInput(
      side,
      { ...side, id: 'b', places: undefined },
      one,
    );
    expect(input.highlights[0]!.innerBoxes).toEqual([
      [300, 10, 320, 20],
      [100, 30, 130, 40],
    ]);
    expect(records[0]!.result).toMatchObject({ found: true, length: null });
    expect(parseViewerInput(input)).toMatchObject({ ok: true });
  });

  it('글자 자리의 그릇이 다른 쪽에 있으면 넣지 않는다(자료가 서로 어긋난 것이다)', () => {
    const wrongPage = places(
      container('p1-t1:r1c1', 2, [{ text: '1,234', x: 410, y: 125 }]),
    );
    const { input, records } = buildReconcileInput(
      sideA,
      { ...sideB, places: wrongPage },
      outcome,
    );
    expect(
      innerBoxesOf(input.highlights.find((h) => h.id === 'v1-b')!),
    ).toEqual([]);
    expect(
      records.find((record) => record.highlightId === 'v1-b')!.result,
    ).toEqual({ found: false, reason: 'page_differs' });
  });

  it('글자 자리에 그 숫자의 글자가 없으면 넣지 않는다(그릇은 있는데 그 범위에 좌표 있는 글자가 없다). 상자를 얻은 것으로 세지도 않는다', () => {
    // 문단 「2024년 배출량은 1,234톤이다.」 의 글자 자리가 앞의 「2024년」 까지만 있다. 가리킨 숫자 「1,234」(11~16번째 자리)에는 좌표가 없다.
    const partial = places(
      container('p1-b1', 1, [{ text: '2024년', x: 50, y: 100 }]),
    );
    const { input, records } = buildReconcileInput(
      { ...sideA, places: partial },
      sideB,
      outcome,
    );
    const highlight = input.highlights.find((h) => h.id === 'v1-a')!;
    expect(innerBoxesOf(highlight)).toEqual([]);
    expect(highlight.box).toEqual([50, 100, 550, 120]);
    expect(
      records.find((record) => record.highlightId === 'v1-a')!.result,
    ).toEqual({ found: false, reason: 'no_glyphs_in_span' });
    // 화면의 알림이 말하는 「상자를 얻은 강조」의 수에도 들지 않는다.
    expect(records.filter((record) => record.result.found)).toEqual([]);
    expect(input.notice).toContain(
      `강조 ${input.highlights.length}개 중 0개가 상자를 얻었다`,
    );
    expect(parseViewerInput(input)).toMatchObject({ ok: true });
  });

  it('항목의 제목은 판정이 본 값(시험지의 값)으로 적고, PDF 원문의 값은 덧붙는 글에 적는다', () => {
    const exam = {
      blocks: [],
      tables: [
        {
          id: 'p2-t1',
          cells: [
            ['구분', '2023', '2024'],
            ['배출량', '1,300', '9,999'],
            ['비율', '40% / 60%', '55'],
          ],
        },
      ],
    };
    const { input } = buildReconcileInput({ ...sideA, exam }, sideB, outcome);
    const mismatch = input.items.find((item) => item.id === 'v2')!;
    expect(mismatch.title).toBe('9,999 ≠ 1,234');
    expect(mismatch.detail).toContain('PDF 원문은 「1,234」');
    // 강조의 글자는 PDF 에 실제로 있는 값이다.
    expect(input.highlights.find((h) => h.id === 'v2-a')!.text).toBe('1,234');
  });

  it('n번째 숫자의 자리는 PDF 원문의 글에서 센다. 시험지가 글자 수를 바꿔도 상자는 원문의 자리다', () => {
    // 시험지는 「40% / 60%」 를 「4,000% / 61%」 로 바꿨다. 판정이 본 값은 61, 원문의 값은 60, 글자 범위는 원문의 6~9 다.
    const exam = {
      blocks: [],
      tables: [
        {
          id: 'p2-t1',
          cells: [
            ['구분', '2023', '2024'],
            ['배출량', '1,300', '1,234'],
            ['비율', '4,000% / 61%', '55'],
          ],
        },
      ],
    };
    expect(resolveTarget({ ...sideA, exam }, 'p2-t1:r2c1#n2')).toMatchObject({
      ok: true,
      target: { value: '60', judgedValue: '61', span: { start: 6, end: 9 } },
    });
    const block = {
      blocks: [{ id: 'p1-b1', text: '2024년도의 배출량은 9,999톤이다.' }],
      tables: [],
    };
    expect(resolveTarget({ ...sideA, exam: block }, 'p1-b1#n2')).toMatchObject({
      ok: true,
      target: {
        value: '1,234',
        judgedValue: '9,999',
        span: { start: 11, end: 16 },
      },
    });
  });

  it('풀지 못한 자리 표기는 problems 에 모으고 항목을 만들지 않는다', () => {
    const broken: LabOutcome = {
      after: {
        verdicts: [
          {
            a: 'p9-t9:r0c0',
            b: 'p1-t1:r1c1',
            outcome: 'match',
            reason: 'exact',
          },
        ],
      },
      states: { a: {}, b: {} },
    };
    const { input, problems } = buildReconcileInput(sideA, sideB, broken);
    expect(problems).toHaveLength(1);
    expect(input.items).toEqual([]);
  });
});

describe('buildSentenceInput (가짜 자료)', () => {
  it('숫자가 든 긴 문단만 고르고, 가짜라고 적는다', () => {
    const long = (n: number) =>
      `이 문단은 ${n}번째이며 충분히 길어서 고를 수 있는 문단이다. 뒤에 한 문장이 더 있다.`;
    const document: LabDocument = {
      source,
      pages: [{ page: 1, width: 600, height: 800 }],
      blocks: [
        ...Array.from({ length: 15 }, (_, i) => ({
          id: `p1-b${i + 1}`,
          page: 1,
          kind: 'paragraph',
          bbox: [50, 20 + i * 30, 550, 40 + i * 30] as [
            number,
            number,
            number,
            number,
          ],
          text: long(i + 1),
        })),
        {
          id: 'p1-b90',
          page: 1,
          kind: 'heading',
          bbox: [50, 700, 550, 720],
          text: '제목 2024 는 문단이 아니라서 고르지 않는다. 충분히 길어도 마찬가지다.',
        },
        {
          id: 'p1-b91',
          page: 1,
          kind: 'paragraph',
          bbox: [50, 730, 550, 750],
          text: '짧다 1',
        },
      ],
      tables: [],
    };
    const input = buildSentenceInput(document, 'A', 'a.pdf');
    expect(parseViewerInput(input)).toMatchObject({ ok: true });
    expect(input.notice).toContain('가짜 자료');
    expect(input.items.map((item) => item.id)).toEqual([
      'p1-b1',
      'p1-b8',
      'p1-b15',
    ]);
    expect(input.items[0]!.title).toBe(
      '1쪽 · 이 문단은 1번째이며 충분히 길어서 고를 수 있는 문단이다.',
    );
    expect(input.documents).toHaveLength(1);
  });

  it('글자 자리가 없으면 상자는 문단 전체뿐이다', () => {
    const text =
      '앞 문장이다. 둘째 문장에는 숫자 12 가 있고 충분히 길어서 고를 수 있다. 끝 문장이다.';
    const document: LabDocument = {
      source,
      pages: [{ page: 1, width: 600, height: 800 }],
      blocks: [
        {
          id: 'p1-b1',
          page: 1,
          kind: 'paragraph',
          bbox: [50, 20, 550, 60],
          text,
        },
      ],
      tables: [],
    };
    const input = buildSentenceInput(document, 'A', 'a.pdf');
    expect(innerBoxesOf(input.highlights[0]!)).toEqual([]);
    expect(input.highlights[0]!.box).toEqual([50, 20, 550, 60]);
    expect(input.notice).toContain('상자가 문단 전체다');
  });

  it('글자 자리가 있으면 숫자가 든 첫 문장 하나를 줄마다 상자 하나로 강조한다', () => {
    // 문단이 두 줄로 놓였다. 첫 줄 「앞 문장이다. 둘째 문장에는 숫자 12 가」, 둘째 줄 「있고 충분히 길어서 고를 수 있다. 끝 문장이다.」
    const lines = [
      '앞 문장이다. 둘째 문장에는 숫자 12 가',
      '있고 충분히 길어서 고를 수 있다. 끝 문장이다.',
    ];
    const text = lines.join(' ');
    const document: LabDocument = {
      source,
      pages: [{ page: 1, width: 600, height: 800 }],
      blocks: [
        {
          id: 'p1-b1',
          page: 1,
          kind: 'paragraph',
          bbox: [50, 20, 550, 60],
          text,
        },
      ],
      tables: [],
    };
    const input = buildSentenceInput(
      document,
      'A',
      'a.pdf',
      places(
        container('p1-b1', 1, [
          { text: lines[0]!, x: 50, y: 20 },
          { text: lines[1]!, x: 50, y: 40 },
        ]),
      ),
    );
    expect(parseViewerInput(input)).toMatchObject({ ok: true });
    const highlight = input.highlights[0]!;
    expect(highlight.text).toBe(
      '둘째 문장에는 숫자 12 가 있고 충분히 길어서 고를 수 있다.',
    );
    // 첫 줄: 「둘째」(8번째 글자, x 130)부터 줄 끝(23글자, x 280)까지.  둘째 줄: 줄 처음(x 50)부터 「있다.」의 점(19글자, x 240)까지.
    expect(highlight.innerBoxes).toEqual([
      [130, 20, 280, 30],
      [50, 40, 240, 50],
    ]);
    expect(highlight.box).toEqual([50, 20, 550, 60]);
    expect(input.items[0]!.title).toBe(
      '1쪽 · 둘째 문장에는 숫자 12 가 있고 충분히 길어서 고를 수 있다.',
    );
    expect(input.notice).toContain('1문장 중 1문장이 상자를 얻었다');
  });
});

describe('buildSentenceInput: 글자 자리가 어긋났을 때', () => {
  it('글자 자리의 그릇이 문단과 다른 쪽에 있으면 그 상자를 쓰지 않는다. 문단 전체 상자로 남는다', () => {
    const lines = [
      '앞 문장이다. 둘째 문장에는 숫자 12 가',
      '있고 충분히 길어서 고를 수 있다. 끝 문장이다.',
    ];
    const document: LabDocument = {
      source,
      pages: [
        { page: 1, width: 600, height: 800 },
        { page: 2, width: 600, height: 800 },
      ],
      blocks: [
        {
          id: 'p1-b1',
          page: 1,
          kind: 'paragraph',
          bbox: [50, 20, 550, 60],
          text: lines.join(' '),
        },
      ],
      tables: [],
    };
    // 그릇의 id 는 같은데 2쪽의 것이다(문서 모델과 글자 자리가 서로 어긋난 자료).
    const input = buildSentenceInput(
      document,
      'A',
      'a.pdf',
      places(
        container('p1-b1', 2, [
          { text: lines[0]!, x: 50, y: 20 },
          { text: lines[1]!, x: 50, y: 40 },
        ]),
      ),
    );
    expect(innerBoxesOf(input.highlights[0]!)).toEqual([]);
    expect(input.highlights[0]).toMatchObject({
      page: 1,
      box: [50, 20, 550, 60],
    });
    expect(input.notice).toContain('1문장 중 0문장이 상자를 얻었다');
  });
});

describe('splitSentences', () => {
  const cut = (text: string) =>
    splitSentences(text).map((sentence) =>
      text.slice(sentence.start, sentence.end),
    );
  it('마침표·물음표·느낌표 뒤에 공백이 오거나 글이 끝나는 자리에서 가른다. 소수점에서는 가르지 않는다', () => {
    expect(cut('비율은 3.5% 다. 정말인가? 그렇다!  끝')).toEqual([
      '비율은 3.5% 다.',
      '정말인가?',
      '그렇다!',
      '끝',
    ]);
  });
  it('닫는 따옴표·괄호는 앞 문장에 붙인다. 마침표가 없으면 글 전체가 한 문장이다', () => {
    expect(cut('그는 “한다.” 라고 했다 (2024.) 끝')).toEqual([
      '그는 “한다.”',
      '라고 했다 (2024.)',
      '끝',
    ]);
    expect(cut('마침표 없는 글 12')).toEqual(['마침표 없는 글 12']);
    expect(cut('')).toEqual([]);
  });
});
