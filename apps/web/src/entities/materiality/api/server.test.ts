// 중대성평가 실어댑터 + 가짜 서버(밴드 IRW1 ① — 발주서 §3-1-1·2).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fakeInput, fakeResult } from '../model/testing.ts';
import { UUID_PATTERN } from './ids.ts';
import { MaterialityStoreError } from './store.ts';
import {
  REPORT,
  WEBSEARCH,
  doneRun,
  fakeMaterialityServer,
  fakeRun,
  json,
  refusal,
  serverStoreOf,
  unreachable,
} from './testing.ts';

/** 열쇠를 차례로 내는 함수(시험이 열쇠를 고정한다). */
function keys(head = '0') {
  let n = 0;
  return () =>
    `${head.repeat(8)}-0000-4000-8000-${String(++n).padStart(12, '0')}`;
}

const kindOf = async (promise: Promise<unknown>) => {
  try {
    await promise;
    return 'resolved';
  } catch (error) {
    return error instanceof MaterialityStoreError ? error.kind : 'other';
  }
};

describe('getRun', () => {
  it('실행 꼴: 상태·단계·파일·시각·input', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const run = await serverStoreOf(server).getRun('7');
    expect(run.runId).toBe('7');
    expect(run.status).toBe('done');
    expect(run.steps).toHaveLength(10);
    expect(run.files).toContain(REPORT);
    expect(run.startedAt).not.toBeNull();
    expect(run.input?.company.name).toBe(
      (fakeInput().company as { name: string }).name,
    );
  });

  it('module 이 다르면 not_found · input 꼴 밖이면 input null · id 꼴 밖은 요청 0', async () => {
    const server = fakeMaterialityServer({
      runs: [
        fakeRun(7, { module: 'dataverify' }),
        fakeRun(8, { options: { input: { schemaVersion: 'x' } } }),
      ],
    });
    const store = serverStoreOf(server);
    expect(await kindOf(store.getRun('7'))).toBe('not_found');
    expect((await store.getRun('8')).input).toBeNull();
    expect(await kindOf(store.getRun('07'))).toBe('not_found');
    expect(await kindOf(store.getRun('abc'))).toBe('not_found');
    expect(server.calls).toHaveLength(2);
  });

  it('단계 done·total(IRW6): 정수 → 값 · null → null · 음수·소수·글·done > total → 둘 다 null, 실행은 읽힘', async () => {
    const odd: [unknown, unknown][] = [
      [1, 2],
      [null, null],
      [-1, 2],
      [1.5, 2],
      ['1', 2],
      [3, 2],
      [2, 2],
    ];
    const run = fakeRun(7, { status: 'processing' });
    run.steps = run.steps.map((step, index) => ({
      ...step,
      ...(index < odd.length ?
        ({ done: odd[index]![0], total: odd[index]![1] } as {
          done: number | null;
          total: number | null;
        })
      : {}),
    }));
    const got = await serverStoreOf(
      fakeMaterialityServer({ runs: [run] }),
    ).getRun('7');
    expect(got.steps.map(({ done, total }) => [done, total])).toEqual([
      [1, 2],
      [null, null],
      [null, null],
      [null, null],
      [null, null],
      [null, null],
      [2, 2],
      [null, null],
      [null, null],
      [null, null],
    ]);
  });

  it('꼴 틀림 rejected · 끊김 unreachable', async () => {
    const server = fakeMaterialityServer();
    server.override['GET /runs/9'] = [() => json(200, { id: 9 }), unreachable];
    const store = serverStoreOf(server);
    expect(await kindOf(store.getRun('9'))).toBe('rejected');
    expect(await kindOf(store.getRun('9'))).toBe('unreachable');
  });
});

describe('getResult', () => {
  it('200 은 거울을 지난 화면 꼴 · 404 not_found · 409(진행·실패) not_done · 꼴 틀림 rejected', async () => {
    const server = fakeMaterialityServer({
      runs: [
        doneRun(7),
        fakeRun(8, { status: 'processing' }),
        fakeRun(9, { status: 'failed' }),
        doneRun(10, { result: { ...fakeResult(), part2: { status: 'x' } } }),
      ],
    });
    const store = serverStoreOf(server);
    const result = await store.getResult('7');
    expect(result.part2.status).toBe('done');
    expect(await kindOf(store.getResult('99'))).toBe('not_found');
    expect(await kindOf(store.getResult('8'))).toBe('not_done');
    expect(await kindOf(store.getResult('9'))).toBe('not_done');
    expect(await kindOf(store.getResult('10'))).toBe('rejected');
    expect(server.count('GET /materiality/runs/7/result')).toBe(1);
  });
});

describe('reportFile', () => {
  it('최종 엑셀 이름으로 받고, 없으면 not_found', async () => {
    const server = fakeMaterialityServer({
      runs: [doneRun(7), doneRun(8, { files: [], result: null })],
    });
    const store = serverStoreOf(server);
    const file = await store.reportFile('7');
    expect(file.fileName).toBe(REPORT);
    expect(file.blob.size).toBeGreaterThan(0);
    expect(server.calls.at(-1)!.path).toBe('/materiality/runs/7/report');
    expect(await kindOf(store.reportFile('8'))).toBe('not_found');
  });

  it('researchFile: 1부 리서치 엑셀 이름으로 받고(sid:MARC-ENT-449), 없으면 not_found', async () => {
    const server = fakeMaterialityServer({
      runs: [doneRun(7), doneRun(8, { files: [REPORT] })],
    });
    const store = serverStoreOf(server);
    const file = await store.researchFile('7');
    expect(file.fileName).toBe(WEBSEARCH);
    expect(server.calls.at(-1)!.path).toBe(`/runs/7/files/${WEBSEARCH}`);
    expect(await kindOf(store.researchFile('8'))).toBe('not_found');
    expect(await kindOf(store.researchFile('x'))).toBe('not_found');
  });
});

describe('rerun', () => {
  it('GET /runs/{id} 의 options 그대로(깊은 같음) · 본문 열쇠는 module·launchKey·options 셋뿐 · IK 소문자 UUID', async () => {
    const options = {
      input: fakeInput({ dateRange: '2024-01-01~2024-12-31' }),
    };
    const server = fakeMaterialityServer({ runs: [doneRun(7, { options })] });
    const store = serverStoreOf(server);
    expect(await store.rerun('7')).toEqual({ kind: 'started', runId: '30' });
    const [post] = server.posts();
    const body = post!.body as Record<string, unknown>;
    expect(Object.keys(body)).toEqual(['module', 'launchKey', 'options']);
    expect(body.module).toBe('materiality');
    expect(body.options).toEqual(options);
    expect(body.launchKey).toMatch(UUID_PATTERN);
    expect(post!.headers.get('Idempotency-Key')).toMatch(UUID_PATTERN);
    expect(body.launchKey).not.toBe(post!.headers.get('Idempotency-Key'));
    expect(server.runs.get(30)!.options).toEqual(options);
  });

  it('열쇠: 실패(거절·끊김) 뒤 같은 실행은 같은 열쇠·launchKey · 성공 뒤 새 열쇠 · 다른 실행은 새 열쇠', async () => {
    const server = fakeMaterialityServer({
      runs: [doneRun(7), fakeRun(8, { status: 'failed' })],
    });
    const store = serverStoreOf(server, {
      newKey: keys('a'),
      newLaunchKey: keys('b'),
    });
    server.override['POST /runs'] = [
      () => refusal(500, 'INTERNAL'),
      unreachable,
    ];
    expect(await store.rerun('7')).toEqual({ kind: 'failed' });
    expect(await store.rerun('7')).toEqual({ kind: 'unreachable' });
    expect(await store.rerun('7')).toMatchObject({ kind: 'started' });
    expect(await store.rerun('7')).toMatchObject({ kind: 'started' });
    expect(await store.rerun('8')).toMatchObject({ kind: 'started' });
    const posts = server.posts();
    const ik = posts.map((call) => call.headers.get('Idempotency-Key'));
    const lk = posts.map(
      (call) => (call.body as { launchKey: string }).launchKey,
    );
    expect(ik[0]).toBe(ik[1]);
    expect(ik[1]).toBe(ik[2]);
    expect(lk[0]).toBe(lk[2]);
    expect(new Set([ik[2], ik[3], ik[4]]).size).toBe(3);
    expect(new Set([lk[2], lk[3], lk[4]]).size).toBe(3);
  });

  it('같은 options 의 두 번째 실행도 만들어진다(★A) · forget 뒤는 새 열쇠', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const store = serverStoreOf(server, { newKey: keys('c') });
    server.override['POST /runs'] = [unreachable];
    expect(await store.rerun('7')).toEqual({ kind: 'unreachable' });
    store.forget();
    expect(await store.rerun('7')).toEqual({ kind: 'started', runId: '30' });
    expect(await store.rerun('7')).toEqual({ kind: 'started', runId: '31' });
    const ik = server.posts().map((c) => c.headers.get('Idempotency-Key'));
    expect(ik[0]).not.toBe(ik[1]);
  });

  it('읽기 실패·꼴 밖 id·남의 모듈 → failed(보내지 않음) · 거절 → failed', async () => {
    const server = fakeMaterialityServer({
      runs: [fakeRun(7, { module: 'greenwash' }), doneRun(8)],
    });
    const store = serverStoreOf(server);
    expect(await store.rerun('99')).toEqual({ kind: 'failed' });
    expect(await store.rerun('x')).toEqual({ kind: 'failed' });
    expect(await store.rerun('7')).toEqual({ kind: 'failed' });
    expect(server.posts()).toHaveLength(0);
    server.override['POST /runs'] = () => refusal(400, 'INVALID_OPTIONS');
    expect(await store.rerun('8')).toEqual({ kind: 'failed' });
  });
});

describe('subscribeRun', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('곧바로 한 번 · 응답 뒤 2초 · done 에서 멈춤', async () => {
    const server = fakeMaterialityServer({
      runs: [fakeRun(7, { status: 'processing' })],
    });
    const store = serverStoreOf(server);
    const seen: string[] = [];
    const stop = store.subscribeRun('7', (run) => seen.push(run.status));
    await vi.advanceTimersByTimeAsync(0);
    expect(seen).toEqual(['processing']);
    await vi.advanceTimersByTimeAsync(1999);
    expect(seen).toHaveLength(1);
    server.advance(7, { status: 'done' });
    await vi.advanceTimersByTimeAsync(1);
    expect(seen).toEqual(['processing', 'done']);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(server.count('GET /runs/7')).toBe(2);
    stop();
  });

  it('404 → onMissing · 처음 읽기 실패 → 곧바로 onFailed · 값 뒤 연속 3번 실패 → onFailed', async () => {
    const server = fakeMaterialityServer({
      runs: [fakeRun(8, { status: 'queued' })],
    });
    const store = serverStoreOf(server);
    const missing = vi.fn();
    store.subscribeRun('99', () => {}, missing);
    await vi.advanceTimersByTimeAsync(0);
    expect(missing).toHaveBeenCalledTimes(1);

    server.override['GET /runs/9'] = unreachable;
    const failedFirst = vi.fn();
    store.subscribeRun('9', () => {}, undefined, failedFirst);
    await vi.advanceTimersByTimeAsync(0);
    expect(failedFirst).toHaveBeenCalledTimes(1);

    const failed = vi.fn();
    const seen = vi.fn();
    store.subscribeRun('8', seen, undefined, failed);
    await vi.advanceTimersByTimeAsync(0);
    server.override['GET /runs/8'] = unreachable;
    await vi.advanceTimersByTimeAsync(4000);
    expect(failed).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2000);
    expect(failed).toHaveBeenCalledTimes(1);
    expect(seen).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(server.count('GET /runs/8')).toBe(4);
  });

  it('해제 뒤 온 답은 버린다', async () => {
    const server = fakeMaterialityServer({ runs: [fakeRun(7)] });
    const store = serverStoreOf(server);
    const seen = vi.fn();
    const stop = store.subscribeRun('7', seen);
    stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(seen).not.toHaveBeenCalled();
  });
});

describe('결과 고침(밴드 IRW11)', () => {
  const DEF = '/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition';

  it('getEdits: GET …/result/edits → 거울(revision 0 · 고침 0) · 꼴 틀림 rejected · 404 not_found · 끊김 rejected', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const store = serverStoreOf(server);
    expect(await store.getEdits('7')).toEqual({ revision: 0, edits: [] });
    expect(server.calls.at(-1)!.path).toBe('/materiality/runs/7/result/edits');
    server.override['GET /materiality/runs/7/result/edits'] = [
      () =>
        json(200, { schemaVersion: 'materiality.result-edits@1', revision: 0 }),
      () => refusal(404, 'NOT_FOUND'),
      unreachable,
    ];
    expect(await kindOf(store.getEdits('7'))).toBe('rejected');
    expect(await kindOf(store.getEdits('7'))).toBe('not_found');
    // 답 없음도 거절(getResult 와 같은 갈래 — 화면은 둘 다 읽기 전용)
    expect(await kindOf(store.getEdits('7'))).toBe('rejected');
  });

  it('saveEdits: 본문 {baseRevision, changes:[{pointer, value}]} 그대로 · saved(새 revision·고침) · 갈래 다섯 · 서버 message 0', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const store = serverStoreOf(server);
    const saved = await store.saveEdits('7', 0, [
      { pointer: DEF, value: '가상 정의 고침' },
    ]);
    expect(server.calls.at(-1)!.body).toEqual({
      baseRevision: 0,
      changes: [{ pointer: DEF, value: '가상 정의 고침' }],
    });
    expect(saved.kind).toBe('saved');
    if (saved.kind !== 'saved') return;
    expect(saved.edits.revision).toBe(1);
    expect(saved.edits.edits).toEqual([
      {
        pointer: DEF,
        value: '가상 정의 고침',
        original: '서브 가 영향',
        editedAt: '2026-11-03T14:28:05+09:00',
        editedBy: { name: '담당자 A' },
      },
    ]);
    expect(
      (await store.saveEdits('7', 0, [{ pointer: DEF, value: 'x' }])).kind,
    ).toBe('conflict');
    server.override['POST /materiality/runs/7/result/edits'] = [
      () => refusal(400, 'INVALID_EDIT'),
      () => refusal(500, 'INTERNAL'),
      () => json(200, { revision: 2 }),
      unreachable,
    ];
    const kinds = [];
    for (let n = 0; n < 4; n += 1)
      kinds.push(
        (await store.saveEdits('7', 1, [{ pointer: DEF, value: 'y' }])).kind,
      );
    expect(kinds).toEqual(['invalid', 'failed', 'failed', 'unreachable']);
    expect(JSON.stringify(kinds)).not.toContain('지어낸');
    expect((await store.saveEdits('x', 0, [])).kind).toBe('failed');
  });

  it('가짜 서버: GET result 는 받은 주소만 덮은 판 · 원문과 같아지면 목록에서 빠짐', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const store = serverStoreOf(server);
    await store.saveEdits('7', 0, [{ pointer: DEF, value: '가상 정의 고침' }]);
    const result = await store.getResult('7');
    expect(
      result.part2.status === 'done' &&
        result.part2.topics[0]!.subtopics[0]!.impact.status === 'done' &&
        result.part2.topics[0]!.subtopics[0]!.impact.rows[0]!.impactDefinition,
    ).toBe('가상 정의 고침');
    const back = await store.saveEdits('7', 1, [
      { pointer: DEF, value: '서브 가 영향' },
    ]);
    expect(back.kind === 'saved' && back.edits).toEqual({
      revision: 2,
      edits: [],
    });
  });
});
