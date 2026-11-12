// 실호출 씨앗(밴드 FX1, sid:MARC-ISSUE-129): 공개 보고서 B 를 실제로 1회 돌린 결과를 가린 판(fixtures/report-b.result.json, 가림 sid:MARC-ENT-190)이
// 거울을 지나는가, counts 가 items 를 다시 센 것과 같은가, 목 저장소의 run-106 이 그 결과를 그대로 내는가, High 0 인 결과에서 모델 함수가 깨지지 않는가.
import { describe, expect, it } from 'vitest';

import {
  LEVELS,
  buildCheckRows,
  filterReviewRows,
  joinReview,
  reviewTally,
} from '../../model/index.ts';
import type { GreenwashResult, LevelCounts } from '../../model/index.ts';
import { parseResult, parseReview } from '../contract/index.ts';
import raw from './fixtures/report-b.result.json?raw';
import { createMockStore } from './mockStore.ts';

const RUN_ID = 'run-106';

function fixture(): GreenwashResult {
  const parsed = parseResult(JSON.parse(raw));
  if (!parsed.ok) throw new Error(parsed.issues);
  return parsed.value;
}

describe('실호출 fixture(공개 보고서 B, 가림판)', () => {
  it('거울(parseResult)을 지난다', () => {
    const parsed = parseResult(JSON.parse(raw));
    expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
  });

  it('counts 는 items 의 level 을 다시 센 것과 같다(High 0 · Mid 11 · Low 11), 위치 없는 문장 둘', () => {
    const result = fixture();
    const recount: LevelCounts = { High: 0, Mid: 0, Low: 0 };
    for (const item of result.items) recount[item.level] += 1;
    expect(recount).toEqual({ High: 0, Mid: 11, Low: 11 });
    expect(result.counts?.byLevel).toEqual(recount);
    expect(result.counts?.total).toBe(result.items.length);
    expect(result.items.filter((item) => item.position === null)).toHaveLength(
      2,
    );
    expect(result.source).toMatchObject({
      fileName: 'B.pdf',
      pageCount: 89,
      sha256: '0'.repeat(64),
    });
  });

  it('목 저장소의 run-106 은 fixture 와 같은 문장 22 개를 내고, 목록 줄·검토 잇기를 지나도 22', async () => {
    const control = createMockStore();
    const parsed = parseResult(await control.store.getResult(RUN_ID));
    if (!parsed.ok) throw new Error(parsed.issues);
    expect(parsed.value.items).toHaveLength(22);
    expect(parsed.value).toEqual(fixture());

    const review = parseReview(await control.store.getReview(RUN_ID));
    if (!review.ok) throw new Error(review.issues);
    expect(review.value).toMatchObject({ state: 'pending', marks: [] });
    expect(joinReview(parsed.value.items, review.value.marks)).toHaveLength(22);

    const snapshot = await control.store.getRun(RUN_ID);
    expect(snapshot).toMatchObject({
      pageCount: 89,
      progress: { state: 'done' },
    });
    expect(await control.store.getDocument(snapshot.documentId)).toEqual({
      documentId: snapshot.documentId,
      fileName: 'B.pdf',
      pageCount: 89,
    });

    const rows = buildCheckRows(await control.store.listCheckRows());
    const row = rows.find((r) => r.lastRun?.runId === RUN_ID);
    expect(row).toMatchObject({ status: 'pending', next: 'review' });
    expect(row?.lastRun?.levelCounts).toEqual({ High: 0, Mid: 11, Low: 11 });
    expect(row?.lastRun?.review).toMatchObject({ reviewed: 0, total: 22 });
  });

  it('High 0 인 결과: High 묶음은 비고, 다른 묶음·셈은 그대로다', () => {
    const result = fixture();
    const rows = joinReview(result.items, []);
    expect(filterReviewRows(rows, { part: null, tab: 'High' })).toEqual([]);
    expect(filterReviewRows(rows, { part: null, tab: 'Mid' })).toHaveLength(11);
    expect(filterReviewRows(rows, { part: null, tab: 'Low' })).toHaveLength(11);
    // 문장이 없는 파트(CEO 메시지·회사소개)를 고르면 빈 목록
    for (const part of ['CEO 메시지', '회사소개'])
      expect(filterReviewRows(rows, { part, tab: 'all' })).toEqual([]);
    expect(reviewTally(rows)).toEqual({
      total: 22,
      reviewed: 0,
      adopted: 0,
      excluded: 0,
      pending: 22,
      edited: 0,
    });
    // 파트별 셈에도 High 칸이 0 으로 있다(배지가 빈 값이 아니라 0 을 받는다)
    for (const counts of Object.values(result.counts?.byPart ?? {}))
      expect(Object.keys(counts).sort()).toEqual([...LEVELS].sort());
  });
});
