// RP-04 결과 셈(밴드 RPW1 ③ 시험 S6 몫 — 발주서 §2-3): 상자 손셈(쪽 크기 0 → 그리지 않음 · y 는 위 원점) · 두 층 수 · sentence null ·
//   bullet·잎 갈래 · 점 다섯 · rejected 잎 전부 아직 · 띠 조건 둘(목차·문서)·표지·added · 다시 만들기 옵션 셋.
import { describe, expect, it } from 'vitest';

import type {
  Bullet,
  DraftingResult,
  Leaf,
  OutlineNode,
  Project,
  RunItem,
  Source,
} from '../../../entities/drafting/model/index.ts';
import {
  bandOf,
  bulletKindOf,
  chipPagesOf,
  dotOf,
  headCountsOf,
  leafCountOf,
  marksOf,
  needsChanges,
  pageSpanOf,
  rebuildOptionsOf,
  rebuildingKeysOf,
  runChoicesOf,
  screenRectOf,
  treeOf,
} from './evidence.ts';
import type { TreeRow } from './evidence.ts';

const source = (
  page: number,
  blockId: string,
  sentence: [number, number, number, number][] | null,
): Source => ({
  documentId: 101,
  blockId,
  page,
  blockBox: [10, 20, 300, 120],
  sentence: sentence && { index: 0, boxes: sentence },
});

const done = (key: string, bullets: Bullet[], pages = [2]): Leaf => ({
  key,
  titlePath: ['지어낸 가', `지어낸 ${key}`],
  pages,
  reusedFrom: null,
  outcome: { status: 'done', bullets },
});

const node = (
  key: string,
  parentKey: string | null,
  depth: number,
): OutlineNode => ({
  key,
  parentKey,
  depth,
  title: `지어낸 ${key}`,
  requirement: '',
});

const result = (leaves: Leaf[], patch: Partial<DraftingResult> = {}) =>
  ({
    schemaVersion: 'drafting.bullets@3',
    projectId: 1,
    outlineId: 201,
    outlineSha256: 'c',
    base: null,
    status: { status: 'done' },
    pdf: {
      documentId: 101,
      fileName: '지어낸.pdf',
      pageCount: 3,
      textPages: 3,
      pages: [],
    },
    leaves,
    warnings: [],
    ...patch,
  }) as DraftingResult;

describe('RP-04 셈 — 상자·두 층', () => {
  it('상자 손셈 — 위 원점 그대로 × 배율 · 쪽 크기 0 이면 null', () => {
    const page = { width: 595, height: 842 };
    expect(screenRectOf([72, 100, 300, 140], page, 1)).toEqual({
      left: 72,
      top: 100,
      width: 228,
      height: 40,
    });
    expect(screenRectOf([72, 100, 300, 140], page, 0.5)).toEqual({
      left: 36,
      top: 50,
      width: 114,
      height: 20,
    });
    expect(screenRectOf([1, 2, 3, 4], { width: 0, height: 842 }, 1)).toBe(null);
    expect(screenRectOf([1, 2, 3, 4], { width: 595, height: 0 }, 1)).toBe(null);
  });

  it('두 층 — 옅은 = 그 쪽 블록(블록 id 겹침 하나) · 진한 = 문장 상자 전부 · 다른 쪽 0', () => {
    const bullet: Bullet = {
      text: '지어낸 bullet',
      unsupported: false,
      sources: [
        source(2, 'b1', [
          [1, 1, 2, 2],
          [3, 3, 4, 4],
        ]),
        source(2, 'b1', [[5, 5, 6, 6]]),
        source(2, 'b2', [[7, 7, 8, 8]]),
        source(3, 'b3', null),
      ],
    };
    const two = marksOf(bullet, 2);
    expect(two.marks.filter((m) => m.layer === 'block')).toHaveLength(2);
    expect(two.marks.filter((m) => m.layer === 'sentence')).toHaveLength(4);
    expect(two.marks[0]!.box).toEqual([10, 20, 300, 120]);
    expect(two.paragraphOnly).toBe(false);
    const three = marksOf(bullet, 3);
    expect(three.marks.map((m) => m.layer)).toEqual(['block']);
    expect(three.paragraphOnly).toBe(true);
    expect(marksOf(bullet, 1)).toEqual({ marks: [], paragraphOnly: false });
    expect(marksOf(null, 2)).toEqual({ marks: [], paragraphOnly: false });
    // 한 쪽에 문장 있는 출처와 없는 출처가 섞이면 「문단까지만」이 아니다(검증 R5).
    const mixed: Bullet = {
      text: '지어낸 섞인 bullet',
      unsupported: false,
      sources: [source(4, 'b5', [[1, 1, 2, 2]]), source(4, 'b6', null)],
    };
    expect(marksOf(mixed, 4).paragraphOnly).toBe(false);
    expect(marksOf(mixed, 4).marks.map((m) => m.layer)).toEqual([
      'block',
      'block',
      'sentence',
    ]);
  });
});

describe('RP-04 셈 — 갈래·점', () => {
  it('bullet 갈래 셋(checks.py) · 칩 = 출처 쪽마다 하나 · 찾은 페이지', () => {
    const cited: Bullet = {
      text: 'a',
      unsupported: false,
      sources: [
        source(3, 'x', null),
        source(2, 'y', null),
        source(3, 'z', null),
      ],
    };
    expect(bulletKindOf(cited)).toBe('chips');
    expect(chipPagesOf(cited)).toEqual([2, 3]);
    expect(bulletKindOf({ text: 'b', unsupported: true, sources: [] })).toBe(
      'no_source',
    );
    expect(
      bulletKindOf({
        text: 'c',
        unsupported: true,
        sources: [source(2, 'y', null)],
      }),
    ).toBe('not_in_source');
    expect(pageSpanOf([27, 23, 25])).toEqual([23, 27]);
    expect(pageSpanOf([4])).toEqual([4, 4]);
    expect(pageSpanOf([])).toBe(null);
  });

  it('점 다섯 · 트리 = 지금 목차(결과에 없는 잎은 아직 · 부모 점 없음) · 머리 셈은 잎만', () => {
    const ok: Bullet = { text: 'a', unsupported: false, sources: [] };
    const odd: Bullet = { text: 'b', unsupported: true, sources: [] };
    const leaves: Leaf[] = [
      done('a1', [ok]),
      done('a2', [ok, odd]),
      { ...done('a3', []), outcome: { status: 'no_material' } },
      {
        ...done('a4', []),
        outcome: { status: 'failed', failure: { kind: 'k', message: 'm' } },
      },
      { ...done('a5', []), outcome: { status: 'not_run', reason: 'r' } },
    ];
    expect(leaves.map(dotOf)).toEqual([
      'done',
      'unsupported',
      'no_material',
      'failed',
      'not_run',
    ]);
    expect(dotOf(undefined)).toBe('not_run');
    const nodes = [
      node('a', null, 1),
      ...['a1', 'a2', 'a3', 'a4', 'a5', 'a6'].map((key) => node(key, 'a', 2)),
    ];
    const rows = treeOf(nodes, result(leaves));
    expect(rows.map((row) => `${row.number}:${row.dot ?? '-'}`)).toEqual([
      '1:-',
      '1.1:done',
      '1.2:unsupported',
      '1.3:no_material',
      '1.4:failed',
      '1.5:not_run',
      '1.6:not_run',
    ]);
    expect(headCountsOf(rows)).toEqual({
      total: 6,
      drafted: 2,
      noMaterial: 1,
      failed: 1,
      notRun: 2,
    });
    expect(leafCountOf(nodes)).toBe(6);
  });

  it('rejected — 결과 잎을 붙이지 않음(잎 전부 아직)', () => {
    const rows = treeOf(
      [node('a1', null, 1)],
      result([done('a1', [])], {
        status: {
          status: 'rejected',
          code: 'over_budget',
          stage: 'before_map',
          message: '지어낸 서버 글',
        },
      }),
    );
    expect(rows.map((row) => row.dot)).toEqual(['not_run']);
    expect(rows[0]!.leaf).toBe(null);
  });
});

describe('RP-04 셈 — 띠·다시 만들기', () => {
  const project = (outlineId: number, documentId: number) =>
    ({
      outline: { outlineId },
      pdf: { documentId },
    }) as unknown as Project;

  it('띠 조건 — 목차 판이 다르거나 문서가 다를 때만', () => {
    const now = result([]);
    expect(needsChanges(project(201, 101), now)).toBe(false);
    expect(needsChanges(project(202, 101), now)).toBe(true);
    expect(needsChanges(project(201, 102), now)).toBe(true);
  });

  it('띠 셈 — changed·added 만 셈 · 표지 · 문서 changed · 바뀐 것 없으면 null', () => {
    const band = bandOf({
      baseRunId: 301,
      baseOutlineId: 201,
      outlineId: 202,
      pdf: 'same',
      leaves: [
        { key: 'a1', change: 'same' },
        { key: 'a2', change: 'changed' },
        { key: 'a7', change: 'added' },
      ],
      removed: ['a6'],
    });
    expect(band?.count).toBe(2);
    expect([...band!.marks]).toEqual([
      ['a2', 'changed'],
      ['a7', 'added'],
    ]);
    expect(band?.reuploaded).toBe(false);
    const same = {
      baseRunId: 301,
      baseOutlineId: 201,
      outlineId: 201,
      pdf: 'same' as const,
      leaves: [{ key: 'a1', change: 'same' as const }],
      removed: [],
    };
    expect(bandOf(same)).toBe(null);
    expect(bandOf({ ...same, pdf: 'changed' })).toEqual({
      count: 0,
      marks: new Map(),
      reuploaded: true,
    });
  });

  it('다시 만들기 옵션 셋 — 전체 base 0 · 바뀐 목차 rebuild [] · 이 목차 rebuild [key]', () => {
    expect(rebuildOptionsOf({ kind: 'all' }, 1, 301)).toEqual({ projectId: 1 });
    expect(rebuildOptionsOf({ kind: 'changed' }, 1, 301)).toEqual({
      projectId: 1,
      base: { runId: 301, rebuild: [] },
    });
    expect(rebuildOptionsOf({ kind: 'one', key: 'a2' }, 1, 301)).toEqual({
      projectId: 1,
      base: { runId: 301, rebuild: ['a2'] },
    });
  });
});

describe('실행 고르기', () => {
  const item = (id: number, createdAt: string): RunItem => ({
    id,
    status: 'done',
    createdAt,
    finishedAt: createdAt,
    outlineId: 201,
    baseRunId: null,
    rebuild: [],
    progress: null,
    rejected: false,
    leaves: null,
  });
  const page = {
    count: 3,
    isNext: false,
    results: [
      item(9, '2026-03-04T05:06:07+09:00'),
      item(7, '2026-03-03T23:30:00+00:00'),
      item(2, '2026-03-02T01:00:00+09:00'),
    ],
  };

  it('새 것 먼저 — 번호는 만든 차례(전체 수에서) · 맨 위만 「지금」 · 시각은 한국 시각', () => {
    expect(runChoicesOf(page, 7)).toEqual([
      { runId: 9, n: 3, at: '2026-03-04 05:06', latest: true },
      { runId: 7, n: 2, at: '2026-03-04 08:30', latest: false },
      { runId: 2, n: 1, at: '2026-03-02 01:00', latest: false },
    ]);
  });

  it('쪽 밖 실행이 더 있어도 번호는 전체 수에서', () => {
    expect(runChoicesOf({ ...page, count: 60, isNext: true }, 9)![0]!.n).toBe(
      60,
    );
  });

  it('지금 실행이 그 쪽에 없으면 null(고르기 숨김)', () => {
    expect(runChoicesOf(page, 8)).toBeNull();
  });
});

describe('rebuildingKeysOf — 서버 reuse 규칙', () => {
  const rowOf = (key: string, status: 'done' | 'failed' | null) =>
    ({
      key,
      isLeaf: true,
      leaf: status === null ? null : { outcome: { status } },
    }) as unknown as TreeRow;
  const rows = [
    rowOf('k', 'done'),
    rowOf('c', 'done'),
    rowOf('s', 'done'),
    rowOf('f', 'failed'),
    rowOf('n', null),
  ];
  const clean = { mapping: { failedBatches: [] } };
  const changed = {
    count: 1,
    reuploaded: false,
    marks: new Map([['c', 'changed' as const]]),
  };

  it('rebuild [k] ∪ 띠 marks ∪ done 아닌 잎 — 나머지는 그대로', () => {
    expect([...rebuildingKeysOf(['k'], changed, rows, clean)].sort()).toEqual([
      'c',
      'f',
      'k',
      'n',
    ]);
  });
  it('문서 어긋남 · 앞 지도 깨짐 → 잎 전부', () => {
    expect(
      rebuildingKeysOf([], { ...changed, reuploaded: true }, rows, clean).size,
    ).toBe(5);
    expect(
      rebuildingKeysOf([], null, rows, { mapping: { failedBatches: [{}] } })
        .size,
    ).toBe(5);
  });
});
