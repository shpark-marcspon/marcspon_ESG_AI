// 목 저장소의 결과·검토(밴드 FW2 ① §3): 목의 결과·검토 전부가 거울을 지나는가, 목록 씨앗 다섯, 끝내기와 지은 결과 [R7],
// 구독 즉시 현재값, PUT 갈아 끼우기 [B3]·확정 뒤 409, 문서 조회·PDF. 거울은 api/index.ts 로 가져온다 [R2].
import { afterEach, describe, expect, it, vi } from 'vitest';

import { EMPTY_PARTS, LEVELS, buildCheckRows } from '../../model/index.ts';
import type { GreenwashResult, GreenwashReview } from '../../model/index.ts';
import { parseResult, parseReview } from '../contract/index.ts';
import { StoreError } from '../store.ts';
import type { RunSnapshot } from '../store.ts';
import { createMockStore } from './mockStore.ts';

afterEach(() => {
  vi.useRealTimers();
});

const pdf = (name: string) =>
  new File([new Uint8Array([1])], name, { type: 'application/pdf' });

const SEED_RUNS = [
  'run-100',
  'run-101',
  'run-102',
  'run-103',
  'run-104',
  'run-105',
];

async function resultOf(
  control: ReturnType<typeof createMockStore>,
  runId: string,
): Promise<GreenwashResult> {
  const parsed = parseResult(await control.store.getResult(runId));
  if (!parsed.ok) throw new Error(parsed.issues);
  return parsed.value;
}

async function reviewOf(
  control: ReturnType<typeof createMockStore>,
  runId: string,
): Promise<GreenwashReview> {
  const parsed = parseReview(await control.store.getReview(runId));
  if (!parsed.ok) throw new Error(parsed.issues);
  return parsed.value;
}

describe('목 결과·검토 → 거울', () => {
  it('씨앗의 결과·검토 전부가 거울을 지난다(끝난 실행 셋)', async () => {
    const control = createMockStore();
    let passed = 0;
    for (const runId of SEED_RUNS) {
      const json = await control.store.getResult(runId).catch(() => null);
      if (json === null) continue;
      const result = parseResult(json);
      expect(result.ok ? 'ok' : result.issues, runId).toBe('ok');
      const review = parseReview(await control.store.getReview(runId));
      expect(review.ok ? 'ok' : review.issues, runId).toBe('ok');
      passed++;
    }
    expect(passed).toBe(3);
  });

  it('새로 만든 실행을 끝내면 지은 결과·검토도 거울을 지난다. 문장은 지정한 쪽 안, 등급 셋이 다 나온다 [R7]', async () => {
    const control = createMockStore();
    const { documentId } = await control.store.createDocument(
      pdf('목-보고서-60쪽.pdf'),
    );
    const { runId } = await control.store.createRun(documentId, {
      parts: { ceo: [3], company: [4, 5], climate: [5, 9] },
      extraTerms: ['초록 물결', '탄소 중립'],
      reportYear: 2026,
      previousDocumentId: null,
    });
    await expect(control.store.getResult(runId)).rejects.toMatchObject({
      kind: 'not_found',
    });
    control.finish(runId);
    const result = await resultOf(control, runId);
    expect(result.items.length).toBeGreaterThanOrEqual(3);
    expect(new Set(result.items.map((i) => i.level))).toEqual(new Set(LEVELS));
    for (const item of result.items) expect([3, 4, 5, 9]).toContain(item.page);
    // 상자 있음·없음이 섞인다(덧붙임 1), 상자의 쪽은 문장의 쪽
    expect(result.items.some((i) => i.position === null)).toBe(true);
    expect(result.items.some((i) => i.position !== null)).toBe(true);
    for (const i of result.items)
      if (i.position) expect(i.position.page).toBe(i.page);
    // 5쪽은 회사소개·기후/환경 토픽 두 파트
    expect(result.items.find((i) => i.page === 5)?.parts).toEqual([
      '회사소개',
      '기후/환경 토픽',
    ]);
    expect(result.extraTerms).toEqual(['초록 물결', '탄소 중립']);
    // 기본 목록과 겹친 추가 단어(탄소 중립)는 빈도에 줄이 없다
    const terms = result.wordCounts.total.map((row) => row.term);
    expect(terms).toContain('초록 물결');
    expect(terms).not.toContain('탄소 중립');
    expect(await reviewOf(control, runId)).toMatchObject({
      state: 'pending',
      marks: [],
      runId: 1,
    });
    // 같은 입력이면 같은 결과(결정적)
    const again = createMockStore();
    const doc2 = await again.store.createDocument(pdf('목-보고서-60쪽.pdf'));
    const run2 = await again.store.createRun(doc2.documentId, {
      parts: { ceo: [3], company: [4, 5], climate: [5, 9] },
      extraTerms: ['초록 물결', '탄소 중립'],
      reportYear: 2026,
      previousDocumentId: null,
    });
    again.finish(run2.runId);
    expect((await resultOf(again, run2.runId)).items).toEqual(result.items);
  });

  it('scenario done 은 결과가 있고, 데모 걸음으로 끝나도 결과가 생긴다', async () => {
    vi.useFakeTimers();
    const done = createMockStore({ scenario: 'done' });
    expect((await resultOf(done, 'run-1')).items.length).toBeGreaterThan(0);
    const demo = createMockStore({ demoIntervalMs: 10 });
    const { documentId } = await demo.store.createDocument(
      pdf('목-보고서-60쪽.pdf'),
    );
    const { runId } = await demo.store.createRun(documentId, {
      parts: { ...EMPTY_PARTS, climate: [2] },
      extraTerms: [],
      reportYear: 2026,
      previousDocumentId: null,
    });
    demo.start();
    vi.advanceTimersByTime(100);
    demo.stop();
    expect((await demo.store.getRun(runId)).progress.state).toBe('done');
    expect((await resultOf(demo, runId)).items.length).toBe(3);
  });
});

describe('목록 씨앗', () => {
  it('줄 다섯(검토 중 · 검토 대기 · AI 점검 중 · 멈춤 · 검토 완료), 이름은 지어낸 「목-」, 수정본은 마지막 판만', async () => {
    const source = await createMockStore().store.listCheckRows();
    const rows = buildCheckRows(source);
    // 다섯 + 실호출 씨앗 하나(run-106 「B.pdf」, 밴드 FX1. 이름은 결과의 source 그대로라 「목-」이 아니다)
    expect(rows).toHaveLength(6);
    expect(new Set(rows.map((row) => row.status))).toEqual(
      new Set(['in_review', 'pending', 'running', 'failed', 'confirmed']),
    );
    for (const row of rows)
      if (row.lastRun?.runId !== 'run-106')
        expect(row.doc.fileName).toMatch(/^목-/);
    const revision = rows.find((row) => row.previousVersionCount > 0)!;
    expect(revision.doc.fileName).toBe('목-환경경영보고서-2026.pdf');
    expect(revision.previousVersionCount).toBe(1);
    // 실행이 둘인 문서는 2회차
    expect(
      rows.find((row) => row.lastRun?.runId === 'run-101')?.runOrdinal,
    ).toBe(2);
    expect(source.companyName).toBe('고객사 A');
    // 확정 줄: 확정한 사람(검토의 confirmedBy 이름)과 확정 시각
    const confirmed = rows.find((row) => row.status === 'confirmed')!;
    expect(confirmed.lastRun?.review).toMatchObject({
      confirmedBy: '이두리',
      confirmedAt: '2026-10-03T15:30:00+09:00',
    });
  });
  it('세션에서 만든 실행도 목록에 든다(올린 사람 = 지금 사용자, 보고연도·수정본 대상은 실행 입력에서)', async () => {
    const control = createMockStore({
      now: () => new Date(Date.UTC(2026, 9, 20, 0, 0, 0)),
    });
    const { documentId } = await control.store.createDocument(
      pdf('목-보고서-60쪽.pdf'),
    );
    const before = buildCheckRows(await control.store.listCheckRows());
    expect(before).toHaveLength(6);
    await control.store.createRun(documentId, {
      parts: { ...EMPTY_PARTS, ceo: [1] },
      extraTerms: [],
      reportYear: 2025,
      previousDocumentId: 'doc-s5',
    });
    const source = await control.store.listCheckRows();
    const rows = buildCheckRows(source);
    // doc-s5 는 이제 앞 판이라 줄이 빠지고, 새 문서가 「이전 버전 1개」로 맨 위
    expect(rows).toHaveLength(6);
    expect(rows[0]).toMatchObject({
      status: 'running',
      previousVersionCount: 1,
    });
    expect(rows[0]!.doc).toMatchObject({
      documentId,
      reportYear: 2025,
      uploadedBy: { userId: source.currentUserId },
    });
  });
});

describe('구독·문서·PDF', () => {
  it('구독 즉시 현재값을 한 번 보낸다. 없는 실행은 onMissing', () => {
    const control = createMockStore();
    const seen: RunSnapshot[] = [];
    const missing = vi.fn();
    const off = control.store.subscribeRun('run-103', (run) => seen.push(run));
    expect(seen.map((run) => run.progress.judge.done)).toEqual([6]);
    off();
    control.store.subscribeRun('run-999', () => seen.push(seen[0]!), missing);
    expect(missing).toHaveBeenCalledTimes(1);
    expect(seen).toHaveLength(1);
  });

  it('시각은 +09:00 ISO, 문서 조회는 쪽 수, 없는 것은 not_found', async () => {
    const control = createMockStore({
      now: () => new Date(Date.UTC(2026, 9, 16, 0, 5, 0)),
    });
    const { documentId } = await control.store.createDocument(
      pdf('목-보고서-139쪽.pdf'),
    );
    const { runId } = await control.store.createRun(documentId, {
      parts: { ...EMPTY_PARTS, ceo: [1] },
      extraTerms: [],
      reportYear: null,
      previousDocumentId: null,
    });
    expect((await control.store.getRun(runId)).startedAt).toBe(
      '2026-10-16T09:05:00+09:00',
    );
    expect(await control.store.getDocument(documentId)).toEqual({
      documentId,
      fileName: '목-보고서-139쪽.pdf',
      pageCount: 139,
    });
    await expect(control.store.getDocument('doc-x')).rejects.toBeInstanceOf(
      StoreError,
    );
    await expect(control.store.getRun('run-x')).rejects.toMatchObject({
      kind: 'not_found',
    });
  });

  it('openDocumentPdf: 이 세션에서 올린 파일은 그 File, 씨앗 문서는 null', async () => {
    const control = createMockStore();
    const file = pdf('목-보고서-60쪽.pdf');
    const { documentId } = await control.store.createDocument(file);
    expect(await control.store.openDocumentPdf(documentId)).toBe(file);
    expect(await control.store.openDocumentPdf('doc-s1')).toBeNull();
  });

  it('autoFinishMs: 이 세션에서 만든 실행을 그 뒤에 끝낸다(씨앗은 그대로)', async () => {
    vi.useFakeTimers();
    const control = createMockStore({ autoFinishMs: 50 });
    const { documentId } = await control.store.createDocument(
      pdf('목-보고서-60쪽.pdf'),
    );
    const { runId } = await control.store.createRun(documentId, {
      parts: { ...EMPTY_PARTS, ceo: [1, 2] },
      extraTerms: [],
      reportYear: null,
      previousDocumentId: null,
    });
    expect((await control.store.getRun(runId)).progress.state).toBe('running');
    vi.advanceTimersByTime(50);
    expect((await control.store.getRun(runId)).progress.state).toBe('done');
    expect((await control.store.getRun('run-103')).progress.state).toBe(
      'running',
    );
  });
});

describe('PUT', () => {
  it('받은 marks 로 갈아 끼운다(합치지 않는다 [B3]). state 를 주지 않으면 그대로', async () => {
    const control = createMockStore();
    await control.store.putReview('run-102', {
      marks: [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
        { itemIndex: 1, decision: 'adopted', excludeReason: null },
      ],
    });
    await control.store.putReview('run-102', {
      marks: [{ itemIndex: 2, decision: 'excluded', excludeReason: '기타: x' }],
    });
    expect(await reviewOf(control, 'run-102')).toMatchObject({
      state: 'in_review',
      marks: [{ itemIndex: 2, decision: 'excluded', excludeReason: '기타: x' }],
    });
  });

  it('서버 규칙 (a): 표시가 있는 첫 PUT 이면 pending → in_review, 표시 0 이면 그대로. state 는 confirmed·생략 밖이면 rejected(결함 D1)', async () => {
    const control = createMockStore();
    expect((await reviewOf(control, 'run-102')).state).toBe('pending');
    await control.store.putReview('run-102', { marks: [] });
    expect((await reviewOf(control, 'run-102')).state).toBe('pending');
    await control.store.putReview('run-102', {
      state: null,
      marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
    });
    expect((await reviewOf(control, 'run-102')).state).toBe('in_review');
    await control.store.putReview('run-102', { marks: [] });
    expect(await reviewOf(control, 'run-102')).toMatchObject({
      state: 'in_review',
      marks: [],
    });
    await expect(
      control.store.putReview('run-102', {
        state: 'in_review' as unknown as 'confirmed',
        marks: [],
      }),
    ).rejects.toMatchObject({ kind: 'rejected' });
  });

  it('서버 규칙 (b): 확정이면 표시 없는 문장을 adopted 로 채운 결과 items 전부', async () => {
    const control = createMockStore();
    await control.store.putReview('run-102', {
      state: 'confirmed',
      marks: [{ itemIndex: 1, decision: 'excluded', excludeReason: '기타: x' }],
    });
    expect(await reviewOf(control, 'run-102')).toMatchObject({
      state: 'confirmed',
      marks: [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
        { itemIndex: 1, decision: 'excluded', excludeReason: '기타: x' },
        { itemIndex: 2, decision: 'adopted', excludeReason: null },
      ],
    });
  });

  it('[GW1R ③] 409 차례는 서버(actions/review.py)와 같은 부분: done 이 아님(RUN_NOT_DONE)을 잠김(REVIEW_LOCKED)보다 먼저 본다(옛 111 (2))', async () => {
    const control = createMockStore();
    await control.store.putReview('run-102', {
      state: 'confirmed',
      marks: [0, 1, 2].map((i) => ({
        itemIndex: i,
        decision: 'adopted' as const,
        excludeReason: null,
      })),
    });
    // 확정된 실행을 다시 돌고 있는 꼴로 둔다(둘 다 해당) — 서버 차례면 run_not_done
    control.setProgress('run-102', {
      state: 'running',
      stage: 'judge',
      judge: { done: 1, total: 3 },
    });
    await expect(
      control.store.putReview('run-102', { marks: [] }),
    ).rejects.toMatchObject({ kind: 'run_not_done' });
  });

  it('확정하면 confirmedAt(+09:00) 과 confirmedBy(지금 사용자) 가 서고, 그 뒤 PUT 은 review_locked(409). 확정 전 검토의 confirmedBy 는 null', async () => {
    const control = createMockStore({
      now: () => new Date(Date.UTC(2026, 9, 16, 1, 0, 0)),
    });
    expect(await reviewOf(control, 'run-102')).toMatchObject({
      state: 'pending',
      confirmedBy: null,
    });
    await control.store.putReview('run-102', {
      state: 'confirmed',
      marks: [0, 1, 2].map((i) => ({
        itemIndex: i,
        decision: 'adopted' as const,
        excludeReason: null,
      })),
    });
    expect(await reviewOf(control, 'run-102')).toMatchObject({
      state: 'confirmed',
      confirmedAt: '2026-10-16T10:00:00+09:00',
      confirmedBy: { id: 1, name: '김하나' },
    });
    await expect(
      control.store.putReview('run-102', { marks: [] }),
    ).rejects.toMatchObject({ kind: 'review_locked' });
    await expect(
      control.store.putReview('run-105', { marks: [] }),
    ).rejects.toMatchObject({ kind: 'review_locked' });
    expect(await reviewOf(control, 'run-105')).toMatchObject({
      confirmedBy: { id: 2, name: '이두리' },
    });
    const rows = buildCheckRows(await control.store.listCheckRows());
    expect(
      rows.find((row) => row.lastRun?.runId === 'run-102')?.lastRun?.review,
    ).toMatchObject({ state: 'confirmed', confirmedBy: '김하나' });
  });

  it('문장 차례 밖·차례가 어긋난 marks 는 rejected, 끝나지 않은 실행(AI 점검 중·실패)은 run_not_done(409), 없는 실행은 not_found', async () => {
    const control = createMockStore();
    await expect(
      control.store.putReview('run-102', {
        marks: [{ itemIndex: 9, decision: 'adopted', excludeReason: null }],
      }),
    ).rejects.toMatchObject({ kind: 'rejected' });
    await expect(
      control.store.putReview('run-102', {
        marks: [
          { itemIndex: 1, decision: 'adopted', excludeReason: null },
          { itemIndex: 0, decision: 'adopted', excludeReason: null },
        ],
      }),
    ).rejects.toMatchObject({ kind: 'rejected' });
    await expect(
      control.store.putReview('run-103', { marks: [] }),
    ).rejects.toMatchObject({ kind: 'run_not_done' });
    await expect(
      control.store.putReview('run-104', { marks: [] }),
    ).rejects.toMatchObject({ kind: 'run_not_done' });
    await expect(
      control.store.putReview('run-999', { marks: [] }),
    ).rejects.toMatchObject({ kind: 'not_found' });
  });
});

describe('목 [다시 실행]·끝내기 타이머', () => {
  it('같은 실패 실행을 두 번 다시 실행하면 두 번째는 거절(이미 다시 돈 실행) — 새 실행은 하나', async () => {
    const control = createMockStore({ scenario: 'failed' });
    const failed = control.seededRunId!;
    const { runId } = await control.store.rerun(failed);
    await expect(control.store.rerun(failed)).rejects.toBeInstanceOf(
      StoreError,
    );
    const source = await control.store.listCheckRows();
    expect(
      source.runs.filter((run) => run.runId !== failed && run.runId !== runId)
        .length,
    ).toBe(source.runs.length - 2);
    const reruns = (
      await Promise.all(
        source.runs.map((run) => control.store.getRun(run.runId)),
      )
    ).filter((run) => run.rerunOf === failed);
    expect(reruns.map((run) => run.runId)).toEqual([runId]);
  });

  it('stop() 은 &autofinish 끝내기 타이머도 지운다(내려간 뒤 실행이 끝나지 않는다)', async () => {
    vi.useFakeTimers();
    try {
      const control = createMockStore({ autoFinishMs: 300 });
      const { documentId } = await control.store.createDocument(
        new File(['%PDF'], '목-보고서-60쪽.pdf', {
          type: 'application/pdf',
        }),
      );
      const { runId } = await control.store.createRun(documentId, {
        parts: { ceo: [1], company: [], climate: [] },
        extraTerms: [],
        reportYear: null,
        previousDocumentId: null,
      });
      control.stop();
      await vi.advanceTimersByTimeAsync(1000);
      expect((await control.store.getRun(runId)).progress.state).toBe(
        'running',
      );
    } finally {
      vi.useRealTimers();
    }
  });
});
