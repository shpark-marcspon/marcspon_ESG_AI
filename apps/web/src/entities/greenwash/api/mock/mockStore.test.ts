// 목 저장소: 이름 표, 증가 id, 구독과 해제, 이어서 다시 실행, 데모 걸음(밴드 FW1b ①).
import { afterEach, describe, expect, it, vi } from 'vitest';

import { EMPTY_PARTS } from '../../model/index.ts';
import type { RunSnapshot } from '../store.ts';
import {
  MOCK_DOCUMENTS,
  MockUploadRejected,
  createMockStore,
  step,
} from './mockStore.ts';

const pdf = (name: string) =>
  new File([new Uint8Array([1])], name, { type: 'application/pdf' });
const request = (climate: number[]) => ({
  parts: { ...EMPTY_PARTS, climate },
  extraTerms: [],
  reportYear: 2026,
  previousDocumentId: null,
});

afterEach(() => {
  vi.useRealTimers();
});

describe('파일 이름 표', () => {
  it('표 안 이름은 쪽 수·글자 층을 돌려준다', async () => {
    const { store } = createMockStore();
    expect(await store.createDocument(pdf('목-보고서-60쪽.pdf'))).toEqual({
      documentId: 'doc-1',
      pageCount: 60,
      hasText: true,
    });
    expect(await store.createDocument(pdf('목-스캔-24쪽.pdf'))).toMatchObject({
      documentId: 'doc-2',
      pageCount: 24,
      hasText: false,
    });
    expect(
      (await store.createDocument(pdf('목-큰문서-320쪽.pdf'))).pageCount,
    ).toBe(320);
  });

  it('표 밖 이름은 거절한다', async () => {
    const { store } = createMockStore();
    await expect(
      store.createDocument(pdf('보고서.pdf')),
    ).rejects.toBeInstanceOf(MockUploadRejected);
  });

  it('맥 Finder 가 넘기는 NFD 이름도 표의 이름(NFC)과 같게 본다', async () => {
    const { store } = createMockStore();
    const name = '목-보고서-60쪽.pdf'.normalize('NFD');
    expect(name).not.toBe('목-보고서-60쪽.pdf');
    expect(await store.createDocument(pdf(name))).toMatchObject({
      pageCount: 60,
      hasText: true,
    });
  });

  it('기존 문서 목록은 지어낸 이름 다섯과 실호출 씨앗 하나(목록 씨앗의 판 사슬 마지막들)', async () => {
    const { store } = createMockStore();
    expect(await store.listDocuments()).toEqual(MOCK_DOCUMENTS);
    expect(MOCK_DOCUMENTS).toHaveLength(6);
    // 실호출 씨앗(doc-s6, 밴드 FX1)의 이름은 결과의 source 그대로(B.pdf)
    for (const doc of MOCK_DOCUMENTS)
      if (doc.documentId !== 'doc-s6') expect(doc.fileName).toMatch(/^목-/);
  });
});

describe('실행', () => {
  it('실행 id 는 증가 카운터이고, 점검할 쪽은 파트 합집합', async () => {
    const { store } = createMockStore();
    const { documentId } = await store.createDocument(
      pdf('목-보고서-60쪽.pdf'),
    );
    const a = await store.createRun(documentId, request([3, 4]));
    const b = await store.createRun(documentId, request([5]));
    expect([a.runId, b.runId]).toEqual(['run-1', 'run-2']);
    const run = await store.getRun(a.runId);
    expect(run.checkedPages).toBe(2);
    expect(run.pageCount).toBe(60);
    expect(run.progress).toEqual({
      state: 'running',
      stage: 'extract',
      judge: { done: 0, total: 2 },
    });
  });

  it('없는 문서·없는 실행은 거절한다', async () => {
    const { store } = createMockStore();
    await expect(store.createRun('doc-9', request([1]))).rejects.toThrow();
    await expect(store.getRun('run-9')).rejects.toThrow();
  });

  it('구독자는 바뀔 때마다 받고, 해제하면 더 받지 않는다', async () => {
    const control = createMockStore({ scenario: 'running' });
    const runId = control.seededRunId!;
    const seen: RunSnapshot[] = [];
    const unsubscribe = control.store.subscribeRun(runId, (run) =>
      seen.push(run),
    );
    control.setProgress(runId, {
      state: 'running',
      stage: 'judge',
      judge: { done: 30, total: 44 },
    });
    // 구독 즉시 현재값(28)을 먼저 받는다(저장소 계약, 밴드 FW2 ① sid:MARC-ISSUE-99 2)
    expect(seen.map((run) => run.progress.judge.done)).toEqual([28, 30]);
    unsubscribe();
    control.setProgress(runId, {
      state: 'done',
      stage: 'summarize',
      judge: { done: 44, total: 44 },
    });
    expect(seen).toHaveLength(2);
    expect((await control.store.getRun(runId)).progress.state).toBe('done');
  });

  it('목록 줄 runs[].finishedAt(GCB1) = 그 실행의 끝난 때 — 씨앗의 끝난 실행은 값, 도는 실행은 null, 끝나면 값', async () => {
    const control = createMockStore({ scenario: 'running' });
    const runId = control.seededRunId!;
    const finishedOf = async () =>
      Object.fromEntries(
        (await control.store.listCheckRows()).runs.map((run) => [
          run.runId,
          run.finishedAt,
        ]),
      );
    const before = await finishedOf();
    expect(before[runId]).toBeNull();
    const seeded = Object.entries(before).filter(([id]) => id !== runId);
    expect(seeded.length).toBeGreaterThan(0); // 분모: 씨앗 실행이 있다
    for (const [id, finished] of seeded)
      expect(finished).toBe((await control.store.getRun(id)).finishedAt);
    expect(seeded.some(([, finished]) => typeof finished === 'string')).toBe(
      true,
    );
    control.setProgress(runId, {
      state: 'done',
      stage: 'summarize',
      judge: { done: 44, total: 44 },
    });
    const after = (await finishedOf())[runId];
    expect(typeof after).toBe('string');
    expect(after).toBe((await control.store.getRun(runId)).finishedAt);
  });

  it('scenario failed: 28/44 쪽에서 실행 전체가 멈춘 실행 하나. 다시 실행은 새 id 로 같은 입력을 처음부터', async () => {
    const control = createMockStore({ scenario: 'failed' });
    expect(control.seededRunId).toBe('run-1');
    const failed = await control.store.getRun('run-1');
    expect(failed.progress).toEqual({
      state: 'failed',
      stage: 'judge',
      judge: { done: 28, total: 44 },
    });
    const { runId } = await control.store.rerun('run-1');
    expect(runId).toBe('run-2');
    const rerun = await control.store.getRun(runId);
    expect(rerun.rerunOf).toBe('run-1');
    expect(rerun.documentId).toBe(failed.documentId);
    expect(rerun.checkedPages).toBe(failed.checkedPages);
    expect(rerun.progress).toEqual({
      state: 'running',
      stage: 'extract',
      judge: { done: 0, total: 44 },
    });
    // 실패가 아닌 실행은 다시 실행할 수 없다
    await expect(control.store.rerun(runId)).rejects.toThrow();
  });

  it('열쇠(밴드 GR2): 같은 열쇠면 앞에 만든 실행 id 를 그대로(새 실행 0), 다른 열쇠·열쇠 없음은 새 실행 — createRun·rerun 둘 다', async () => {
    const control = createMockStore({ scenario: 'failed' });
    const { store } = control;
    const { documentId } = await store.createDocument(
      pdf('목-보고서-60쪽.pdf'),
    );
    const a = await store.createRun(documentId, request([3]), 'key-a');
    expect(await store.createRun(documentId, request([3]), 'key-a')).toEqual(a);
    const b = await store.createRun(documentId, request([3]), 'key-b');
    const c = await store.createRun(documentId, request([3]));
    expect(new Set([a.runId, b.runId, c.runId]).size).toBe(3);
    // rerun: 같은 열쇠의 두 번째는 「이미 다시 실행한 실행」 거절이 아니라 앞 실행
    const r = await store.rerun('run-1', 'key-r');
    expect(await store.rerun('run-1', 'key-r')).toEqual(r);
    await expect(store.rerun('run-1', 'key-s')).rejects.toThrow();
  });

  it('scenario 가 없으면 미리 만든 실행이 없다', () => {
    expect(createMockStore().seededRunId).toBeNull();
  });
});

describe('데모 모드', () => {
  it('걸음: 추출 → 판정(쪽 하나씩) → 정리 → 끝', () => {
    let progress = {
      state: 'running' as const,
      stage: 'extract' as const,
      judge: { done: 0, total: 2 },
    } as Parameters<typeof step>[0];
    const trail: string[] = [];
    for (let i = 0; i < 6; i++) {
      progress = step(progress);
      trail.push(`${progress.state}/${progress.stage}/${progress.judge.done}`);
    }
    expect(trail).toEqual([
      'running/judge/0',
      'running/judge/1',
      'running/judge/2',
      'running/summarize/2',
      'done/summarize/2',
      'done/summarize/2',
    ]);
  });

  it('demoIntervalMs 를 주고 start 할 때만 시간으로 흐르고, stop 으로 멈추고 start 로 다시 켠다', async () => {
    vi.useFakeTimers();
    const still = createMockStore({ scenario: 'running' });
    still.start();
    const moving = createMockStore({
      scenario: 'running',
      demoIntervalMs: 100,
    });
    vi.advanceTimersByTime(300);
    expect((await moving.store.getRun('run-1')).progress.judge.done).toBe(28);
    moving.start();
    moving.start();
    vi.advanceTimersByTime(300);
    expect((await still.store.getRun('run-1')).progress.judge.done).toBe(28);
    expect((await moving.store.getRun('run-1')).progress.judge.done).toBe(31);
    moving.stop();
    vi.advanceTimersByTime(300);
    expect((await moving.store.getRun('run-1')).progress.judge.done).toBe(31);
    moving.start();
    vi.advanceTimersByTime(100);
    expect((await moving.store.getRun('run-1')).progress.judge.done).toBe(32);
    moving.stop();
  });
});

describe('씨앗 문서의 PDF(밴드 GVS1)', () => {
  it('실호출 씨앗(run-106) 문서는 처음 열 때 지은 PDF(89쪽, 이름 그대로)를 짓고 다시 열면 같은 File, 다른 씨앗은 null', async () => {
    const { store } = createMockStore();
    const run = await store.getRun('run-106');
    const file = await store.openDocumentPdf(run.documentId);
    expect(file).not.toBeNull();
    expect(file!.name).toBe('B.pdf');
    expect(file!.type).toBe('application/pdf');
    const text = new TextDecoder().decode(await file!.arrayBuffer());
    expect(text.startsWith('%PDF-1.4\n')).toBe(true);
    expect(text).toContain('/Count 89 >>');
    expect(text.match(/\/Type \/Page /g)).toHaveLength(89);
    // 11쪽 상자 [70.09, 431.92, 281.63, 440.43] 자리의 지어낸 글
    expect(text).toMatch(/BT \/F1 8\.51 Tf 70\.09 \d+(\.\d+)? Td \(M+\) Tj ET/);
    expect(await store.openDocumentPdf(run.documentId)).toBe(file);
    for (const other of ['run-100', 'run-101', 'run-105']) {
      const seed = await store.getRun(other);
      expect(await store.openDocumentPdf(seed.documentId)).toBeNull();
    }
  });
});
