// 원고작성 목록 상태 셈(밴드 RPW1 ① — 발주서 §2-0 ③). rowViewOf 상태 여덟·진행·잎 셈·다음 할 일 · 거르기 탭 · 보고연도 · 검색 · 한국 날짜 · id·글자 수.
import { describe, expect, it } from 'vitest';

import { idOf, lengthOf } from './ids.ts';
import {
  dayOf,
  inFilter,
  matchesQuery,
  rowViewOf,
  yearsOfRows,
} from './project.ts';
import type { ProjectRow, RunItem } from './project.ts';

const run = (patch: Partial<RunItem> = {}): RunItem => ({
  id: 301,
  status: 'done',
  createdAt: '2026-10-20T01:00:00Z',
  finishedAt: '2026-10-20T01:05:00Z',
  outlineId: 201,
  baseRunId: null,
  rebuild: [],
  progress: null,
  rejected: false,
  leaves: { total: 3, drafted: 3, noMaterial: 0, failed: 0, notRun: 0 },
  ...patch,
});
const row = (patch: Partial<ProjectRow> = {}): ProjectRow => ({
  id: 7,
  name: '지어낸 보고서',
  year: 2026,
  createdAt: '2026-10-19T00:00:00Z',
  hasDocument: true,
  documentName: '지어낸-전년도.pdf',
  outlineId: 201,
  outlineRevision: 1,
  latestRun: run(),
  ...patch,
});

describe('rowViewOf — 상태 여덟', () => {
  it('문서 없음 → no_document · 다시 올리기', () => {
    expect(rowViewOf(row({ hasDocument: false, latestRun: null }))).toEqual({
      state: 'no_document',
      progress: null,
      leaves: null,
      next: { to: 'upload' },
    });
  });
  it('목차 없음 → no_outline · RP-03', () => {
    const view = rowViewOf(row({ outlineId: null, latestRun: null }));
    expect([view.state, view.next]).toEqual(['no_outline', { to: 'outline' }]);
  });
  it('실행 없음 → no_draft · RP-03', () => {
    const view = rowViewOf(row({ latestRun: null }));
    expect([view.state, view.next]).toEqual(['no_draft', { to: 'outline' }]);
  });
  it('queued·processing → drafting, 진행 n/m 은 둘 다 값일 때만', () => {
    const p = rowViewOf(
      row({
        latestRun: run({
          status: 'processing',
          progress: { step: 'draft', done: 2, total: 5 },
          leaves: null,
        }),
      }),
    );
    expect([p.state, p.progress, p.next]).toEqual([
      'drafting',
      { done: 2, total: 5 },
      { to: 'run', runId: 301 },
    ]);
    const q = rowViewOf(
      row({ latestRun: run({ status: 'queued', leaves: null }) }),
    );
    expect([q.state, q.progress]).toEqual(['drafting', null]);
    const e = rowViewOf(
      row({
        latestRun: run({
          status: 'processing',
          progress: { step: 'extract', done: null, total: null },
        }),
      }),
    );
    expect(e.progress).toBeNull();
    expect(
      rowViewOf(
        row({
          latestRun: run({
            status: 'processing',
            progress: { step: 'extract', done: null, total: null },
            leaves: null,
          }),
        }),
      ).leaves,
    ).toBeNull();
    expect(p.leaves).toEqual({ drafted: 2, total: 5 });
  });
  it('failed·rejected → failed', () => {
    expect(rowViewOf(row({ latestRun: run({ status: 'failed' }) })).state).toBe(
      'failed',
    );
    expect(rowViewOf(row({ latestRun: run({ rejected: true }) })).state).toBe(
      'failed',
    );
  });
  it('실행 목차 ≠ 지금 목차 → outline_changed', () => {
    expect(rowViewOf(row({ outlineId: 202 })).state).toBe('outline_changed');
  });
  it('실행의 판을 모르면(outlineId null) 목차 바뀜이라 말하지 않는다(검증 R2)', () => {
    expect(rowViewOf(row({ latestRun: run({ outlineId: null }) })).state).toBe(
      'done',
    );
  });
  it('잎 failed + notRun > 0 → partial(맞는 자료 없음만은 done)', () => {
    const leaves = (failed: number, notRun: number, noMaterial = 0) =>
      rowViewOf(
        row({
          latestRun: run({
            leaves: {
              total: 4,
              drafted: 4 - failed - notRun - noMaterial,
              noMaterial,
              failed,
              notRun,
            },
          }),
        }),
      );
    expect(leaves(1, 0).state).toBe('partial');
    expect(leaves(0, 1).state).toBe('partial');
    expect(leaves(0, 0, 1).state).toBe('done');
    expect(leaves(1, 0).leaves).toEqual({ drafted: 3, total: 4 });
  });
});

describe('거르기 · 연도 · 검색 · 날짜', () => {
  it('inFilter — 탭 넷의 상태 묶음', () => {
    expect(inFilter('all', 'failed')).toBe(true);
    expect(inFilter('preparing', 'no_draft')).toBe(true);
    expect(inFilter('preparing', 'drafting')).toBe(false);
    expect(inFilter('done', 'outline_changed')).toBe(true);
    expect(inFilter('done', 'partial')).toBe(true);
    expect(inFilter('failed', 'done')).toBe(false);
  });
  it('yearsOfRows — 겹침 없이 큰 해 먼저', () => {
    expect(
      yearsOfRows([
        row({ year: 2025 }),
        row({ year: 2026 }),
        row({ year: 2025 }),
      ]),
    ).toEqual([2026, 2025]);
  });
  it('matchesQuery — 이름·파일 이름, 대소문자·앞뒤 공백 무시', () => {
    expect(matchesQuery(row(), '  ')).toBe(true);
    expect(matchesQuery(row(), '보고서')).toBe(true);
    expect(matchesQuery(row({ documentName: 'ABC.pdf' }), 'abc')).toBe(true);
    expect(matchesQuery(row({ documentName: null }), '전년도')).toBe(false);
  });
  it('dayOf — 한국 날짜, 못 읽으면 글자 그대로', () => {
    expect(dayOf('2026-10-19T15:00:00Z')).toBe('2026-10-20');
    expect(dayOf('2026-10-19T14:59:59Z')).toBe('2026-10-19');
    expect(dayOf('지어낸')).toBe('지어낸');
  });
});

describe('ids', () => {
  it('idOf — 양의 정수 글자만', () => {
    expect(idOf('7')).toBe(7);
    for (const text of ['0', '07', '-1', '1.5', 'x7', '', '99999999999999999'])
      expect(idOf(text), text).toBeNull();
  });
  it('lengthOf — 코드 포인트', () => {
    expect(lengthOf('😀가')).toBe(2);
  });
});
