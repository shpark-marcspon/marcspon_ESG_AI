// 데이터 검증 실어댑터 + 가짜 서버(밴드 DV2a ① — 발주서 §3-1-1·4·5). readEdkXlsx·downloadEdkTemplate 는 밴드 DVX1 ②.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  OPTIONS_MAX_OCTETS,
  buildInput,
  pyJsonOctets,
} from '../model/index.ts';
import type {
  DataverifyInput,
  DataverifyRun,
  EdkData,
} from '../model/index.ts';
import { FAKE_COMPANY, edkData, edkItem } from '../model/testing.ts';
import { MIRRORED_EDK_READ } from './contract/edkRead.ts';
import { UUID_PATTERN } from './ids.ts';
import { EDK_TEMPLATE_FILE_NAME } from './server.ts';
import { DataverifyStoreError } from './store.ts';
import {
  FAKE_TEMPLATE_BYTES,
  FAKE_TEMPLATE_NAME,
  edkRejected,
  fakeDataverifyServer,
  fakeEdkReadOk,
  fakeRun,
  fakeSteps,
  json,
  refusal,
  serverStoreOf,
  unreachable,
} from './testing.ts';

const input = (data: unknown = edkData()): DataverifyInput =>
  buildInput(FAKE_COMPANY, data as EdkData);

/** 열쇠를 차례로 내는 함수(시험이 열쇠를 고정한다). */
function keys() {
  let n = 0;
  return () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
}

/** 옵션 셈이 정확히 n 바이트가 되는 입력(메모 칸을 늘린다). */
function inputOf(octets: number): DataverifyInput {
  const at = (memo: string) => input({ 환경: [edkItem({ 메모: memo })] });
  const base = pyJsonOctets({ input: at('') });
  return at('x'.repeat(octets - base));
}

describe('startRun', () => {
  it('본문 열쇠는 module·options, options 는 input 하나 · Idempotency-Key 소문자 UUID', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    const out = await store.startRun(input());
    expect(out).toEqual({ kind: 'started', runId: '30' });
    const [post] = server.posts();
    expect(Object.keys(post!.body as object)).toEqual([
      'module',
      'launchKey',
      'options',
    ]);
    expect((post!.body as { module: string }).module).toBe('dataverify');
    expect(Object.keys((post!.body as { options: object }).options)).toEqual([
      'input',
    ]);
    expect(post!.headers.get('Idempotency-Key')).toMatch(UUID_PATTERN);
    expect(
      (post!.body as { options: { input: DataverifyInput } }).options.input,
    ).toEqual(JSON.parse(JSON.stringify(input())));
  });

  it('열쇠: 실패 뒤 같은 본문은 같은 열쇠 · 본문이 바뀌면 새 열쇠 · 성공 뒤 새 열쇠', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server, { newKey: keys() });
    server.override['POST /runs'] = [
      () => refusal(500, 'INTERNAL'),
      unreachable,
    ];
    expect(await store.startRun(input())).toEqual({ kind: 'failed' });
    expect(await store.startRun(input())).toEqual({ kind: 'unreachable' });
    expect(await store.startRun(input())).toMatchObject({ kind: 'started' });
    const changed = input({ 환경: [edkItem({ 메모: '바뀜' })] });
    expect(await store.startRun(changed)).toMatchObject({ kind: 'started' });
    expect(await store.startRun(changed)).toMatchObject({ kind: 'started' });
    const used = server
      .posts()
      .map((call) => call.headers.get('Idempotency-Key'));
    expect(used).toEqual([
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000002',
      '00000000-0000-4000-8000-000000000003',
    ]);
    // 실패 뒤 다시 누름이 만든 실행은 하나(같은 열쇠의 앞 실행이 없었다).
    expect(server.runs.size).toBe(3);
  });

  it('forget: 실패 뒤 쥔 열쇠를 버린다 — 같은 본문의 다음 누름은 새 열쇠(요청 0)', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server, { newKey: keys() });
    server.override['POST /runs'] = [() => refusal(500, 'INTERNAL')];
    expect(await store.startRun(input())).toEqual({ kind: 'failed' });
    store.forget();
    expect(server.count('POST /runs')).toBe(1);
    expect(await store.startRun(input())).toMatchObject({ kind: 'started' });
    expect(
      server.posts().map((call) => call.headers.get('Idempotency-Key')),
    ).toEqual([
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000002',
    ]);
  });

  it('옵션 셈 = 상한이면 보내고, +1 이면 요청 0 으로 too_large', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    const atLimit = inputOf(OPTIONS_MAX_OCTETS);
    expect(pyJsonOctets({ input: atLimit })).toBe(OPTIONS_MAX_OCTETS);
    expect(await store.startRun(atLimit)).toMatchObject({ kind: 'started' });
    expect(await store.startRun(inputOf(OPTIONS_MAX_OCTETS + 1))).toEqual({
      kind: 'too_large',
    });
    expect(server.count('POST /runs')).toBe(1);
  });

  it('JSON.stringify 로는 상한 안이어도 서버 셈(구분자 공백)으로 넘으면 요청 0 으로 too_large', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    const at = (memo: string) => input({ 환경: [edkItem({ 메모: memo })] });
    const sent = (memo: string) =>
      new TextEncoder().encode(JSON.stringify({ input: at(memo) })).length;
    // stringify 셈 = 상한 − 5. 이 꼴의 구분자(", "·": ")는 다섯보다 많아 서버 셈은 상한을 넘는다.
    const memo = 'x'.repeat(OPTIONS_MAX_OCTETS - 5 - sent(''));
    expect(sent(memo)).toBe(OPTIONS_MAX_OCTETS - 5);
    expect(await store.startRun(at(memo))).toEqual({ kind: 'too_large' });
    expect(server.count('POST /runs')).toBe(0);
  });

  it('400 INVALID_OPTIONS: 다시 재서 넘으면 too_large, 아니면 unreadable(message 를 읽지 않는다)', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    server.override['POST /runs'] = () =>
      json(400, {
        error: {
          code: 'INVALID_OPTIONS',
          message: '실행 옵션이 너무 커요',
          fields: null,
          legacyCode: 'invalid_options',
        },
      });
    expect(await store.startRun(input())).toEqual({ kind: 'unreadable' });
    // 서버만 크다고 하는 갈래는 웹 셈을 믿는다 — 셈이 상한 안이면 unreadable.
    expect(await store.startRun(inputOf(OPTIONS_MAX_OCTETS))).toEqual({
      kind: 'unreadable',
    });
  });

  it('보내기 전 크기 검사(rerun): 셈이 상한을 넘는 받은 옵션은 요청 0 으로 too_large', async () => {
    const big = { input: inputOf(OPTIONS_MAX_OCTETS + 10) };
    const server = fakeDataverifyServer({
      runs: [fakeRun(5, { status: 'done', options: big })],
    });
    const store = serverStoreOf(server);
    expect(await store.rerun('5')).toEqual({ kind: 'too_large' });
    expect(server.count('POST /runs')).toBe(0);
  });

  it('그 밖 거절 failed · 끊김 unreachable · 답 꼴 틀림 failed', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    server.override['POST /runs'] = [
      () => refusal(409, 'IDEMPOTENCY_KEY_REUSED'),
      unreachable,
      () => json(201, { status: 'queued' }),
    ];
    expect(await store.startRun(input())).toEqual({ kind: 'failed' });
    expect(await store.startRun(input())).toEqual({ kind: 'unreachable' });
    expect(await store.startRun(input())).toEqual({ kind: 'failed' });
  });
});

describe('launchKey(DV2d — Idempotency-Key 와 같은 삶)', () => {
  /** 다른 꼴의 열쇠를 차례로 내는 함수(launchKey 를 IK 와 가려 고정한다). */
  function launchKeys() {
    let n = 0;
    return () => `11111111-1111-4111-8111-${String(++n).padStart(12, '0')}`;
  }
  const sent = (server: ReturnType<typeof fakeDataverifyServer>) =>
    server.posts().map((call) => ({
      key: call.headers.get('Idempotency-Key'),
      launchKey: (call.body as { launchKey?: unknown }).launchKey,
    }));

  it('첫 [검증 시작] 본문에 소문자 UUID launchKey · IK 와 다른 값(기본 짓개)', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    expect(await store.startRun(input())).toMatchObject({ kind: 'started' });
    const [one] = sent(server);
    expect(one!.launchKey).toMatch(UUID_PATTERN);
    expect(one!.launchKey).not.toBe(one!.key);
  });

  it('실패 뒤 같은 본문 = 둘 다 같음 · 본문 바뀜 = 둘 다 새로 · 성공 뒤 새 누름 = 둘 다 새로', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server, {
      newKey: keys(),
      newLaunchKey: launchKeys(),
    });
    server.override['POST /runs'] = [
      () => refusal(500, 'INTERNAL'),
      unreachable,
    ];
    expect(await store.startRun(input())).toEqual({ kind: 'failed' });
    expect(await store.startRun(input())).toEqual({ kind: 'unreachable' });
    expect(await store.startRun(input())).toMatchObject({ kind: 'started' });
    const changed = input({ 환경: [edkItem({ 메모: '바뀜' })] });
    expect(await store.startRun(changed)).toMatchObject({ kind: 'started' });
    expect(await store.startRun(changed)).toMatchObject({ kind: 'started' });
    const k = (n: number) =>
      `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
    const l = (n: number) =>
      `11111111-1111-4111-8111-${String(n).padStart(12, '0')}`;
    expect(sent(server)).toEqual([
      { key: k(1), launchKey: l(1) },
      { key: k(1), launchKey: l(1) },
      { key: k(1), launchKey: l(1) },
      { key: k(2), launchKey: l(2) },
      { key: k(3), launchKey: l(3) },
    ]);
    expect(server.runs.size).toBe(3);
  });

  it('실패 뒤 본문을 고쳐 다시 누름 = 둘 다 새로(쥔 열쇠를 잇지 않는다)', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server, {
      newKey: keys(),
      newLaunchKey: launchKeys(),
    });
    server.override['POST /runs'] = [
      () => refusal(500, 'INTERNAL'),
      () => refusal(500, 'INTERNAL'),
    ];
    expect(await store.startRun(input())).toEqual({ kind: 'failed' });
    const changed = input({ 환경: [edkItem({ 메모: '고침' })] });
    expect(await store.startRun(changed)).toEqual({ kind: 'failed' });
    const k = (n: number) =>
      `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
    const l = (n: number) =>
      `11111111-1111-4111-8111-${String(n).padStart(12, '0')}`;
    expect(sent(server)).toEqual([
      { key: k(1), launchKey: l(1) },
      { key: k(2), launchKey: l(2) },
    ]);
  });

  it('답 없음 뒤 같은 IK·같은 launchKey 다시 보냄 → 서버가 앞 실행을 돌려준다(409 0)', async () => {
    const server = fakeDataverifyServer();
    // 서버는 만들었지만 답이 끊긴 갈래: 첫 POST 는 통과시키고 답만 던진다.
    let first = true;
    const pass = server.send;
    const store = serverStoreOf({
      ...server,
      send: async (request: Request) => {
        const answer = await pass(request);
        if (first && request.method === 'POST') {
          first = false;
          throw new TypeError('끊김');
        }
        return answer;
      },
    });
    expect(await store.startRun(input())).toEqual({ kind: 'unreachable' });
    expect(await store.startRun(input())).toEqual({
      kind: 'started',
      runId: '30',
    });
    expect(server.runs.size).toBe(1);
    const [a, b] = sent(server);
    expect(b).toEqual(a);
  });

  it('rerun = 둘 다 새로(앞 누름이 쥔 열쇠도 잇지 않는다) · 서버 LAUNCH_KEY_REUSED 0', async () => {
    const options = { input: input() };
    const server = fakeDataverifyServer({
      runs: [
        fakeRun(5, {
          status: 'failed',
          options: JSON.parse(JSON.stringify(options)) as Record<
            string,
            unknown
          >,
        }),
      ],
    });
    const store = serverStoreOf(server, {
      newKey: keys(),
      newLaunchKey: launchKeys(),
    });
    server.override['POST /runs'] = [() => refusal(500, 'INTERNAL')];
    // 같은 본문의 [검증 시작]이 실패해 열쇠를 쥔 채로 [다시 실행].
    expect(await store.startRun(input())).toEqual({ kind: 'failed' });
    expect(await store.rerun('5')).toMatchObject({ kind: 'started' });
    expect(await store.rerun('5')).toMatchObject({ kind: 'started' });
    const used = sent(server);
    expect(new Set(used.map((u) => u.key)).size).toBe(3);
    expect(new Set(used.map((u) => u.launchKey)).size).toBe(3);
    for (const u of used) expect(u.launchKey).not.toBe(u.key);
  });

  it('흉내 서버: 같은 IK·다른 launchKey 409 IDEMPOTENCY_KEY_REUSED · 같은 launchKey 새 IK 409 LAUNCH_KEY_REUSED · 꼴 밖 422', async () => {
    const server = fakeDataverifyServer();
    const body = (launchKey: unknown) =>
      JSON.stringify({
        module: 'dataverify',
        launchKey,
        options: { input: input() },
      });
    const post = (key: string, launchKey: unknown) =>
      server.send(
        new Request('http://test.local/api/runs', {
          method: 'POST',
          headers: {
            'Idempotency-Key': key,
            'Content-Type': 'application/json',
          },
          body: body(launchKey),
        }),
      );
    const k = keys();
    const ik = k();
    const lk = k();
    expect((await post(ik, lk)).status).toBe(201);
    expect((await post(ik, lk)).status).toBe(201);
    const reused = await post(ik, k());
    expect(reused.status).toBe(409);
    expect(await reused.text()).toContain('IDEMPOTENCY_KEY_REUSED');
    const again = await post(k(), lk);
    expect(again.status).toBe(409);
    expect(await again.text()).toContain('LAUNCH_KEY_REUSED');
    expect((await post(k(), 'NOT-A-UUID')).status).toBe(422);
    expect(server.runs.size).toBe(1);
  });
});

describe('getRun · subscribeRun', () => {
  it('실행 꼴 · input 거울(못 지나면 null) · 데이터 검증 아님은 not_found', async () => {
    const server = fakeDataverifyServer({
      runs: [
        fakeRun(7),
        fakeRun(8, { options: { input: { schemaVersion: 'x' } } }),
        fakeRun(9, { module: 'greenwash' }),
      ],
    });
    const store = serverStoreOf(server);
    const run = await store.getRun('7');
    expect(run).toMatchObject({
      runId: '7',
      status: 'queued',
      failedStep: null,
      errorCode: null,
      files: [],
      finishedAt: null,
    });
    expect(run.steps.map((s) => s.step)).toEqual([
      'load',
      'plan',
      'review',
      'insight',
      'report',
    ]);
    expect(run.input?.company.name).toBe('가상건설');
    expect(JSON.stringify(run)).not.toContain('지어낸 오류 글');
    expect((await store.getRun('8')).input).toBeNull();
    await expect(store.getRun('9')).rejects.toMatchObject({
      kind: 'not_found',
    });
    await expect(store.getRun('99')).rejects.toMatchObject({
      kind: 'not_found',
    });
    await expect(store.getRun('0')).rejects.toMatchObject({
      kind: 'not_found',
    });
    expect(server.count('GET /runs/0')).toBe(0);
  });

  describe('폴링(가짜 시계)', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    const settle = () => vi.advanceTimersByTimeAsync(0);

    it('계속 → done 에서 멈춤', async () => {
      const server = fakeDataverifyServer({ runs: [fakeRun(7)] });
      const store = serverStoreOf(server, { pollMs: 100 });
      const seen: DataverifyRun[] = [];
      const stop = store.subscribeRun('7', (run) => seen.push(run));
      await settle();
      expect(seen.map((r) => r.status)).toEqual(['queued']);
      server.advance(7, { status: 'processing' });
      await vi.advanceTimersByTimeAsync(100);
      server.advance(7, { status: 'done' });
      await vi.advanceTimersByTimeAsync(100);
      await vi.advanceTimersByTimeAsync(1000);
      expect(seen.map((r) => r.status)).toEqual([
        'queued',
        'processing',
        'done',
      ]);
      expect(server.count('GET /runs/7')).toBe(3);
      stop();
    });

    it('failed 에서 멈춤', async () => {
      const server = fakeDataverifyServer({ runs: [fakeRun(7)] });
      server.advance(7, { status: 'failed', errorCode: 'STEP_FAILED' });
      const store = serverStoreOf(server, { pollMs: 100 });
      const seen: DataverifyRun[] = [];
      store.subscribeRun('7', (run) => seen.push(run));
      await vi.advanceTimersByTimeAsync(1000);
      expect(seen).toHaveLength(1);
      expect(seen[0]).toMatchObject({
        status: 'failed',
        errorCode: 'STEP_FAILED',
        failedStep: 'plan',
      });
    });

    it('값을 받은 뒤 연속 3번 실패 → onFailed 한 번(성공하면 셈 0), 처음 실패는 곧바로', async () => {
      const server = fakeDataverifyServer({ runs: [fakeRun(7)] });
      const store = serverStoreOf(server, { pollMs: 100 });
      const failed = vi.fn();
      server.override['GET /runs/7'] = [() => json(200, null)];
      store.subscribeRun('7', () => undefined, undefined, failed);
      await settle();
      expect(failed).toHaveBeenCalledTimes(1);

      const later = vi.fn();
      const seen: string[] = [];
      server.override['GET /runs/7'] = [];
      const stop = store.subscribeRun(
        '7',
        (run) => seen.push(run.status),
        undefined,
        later,
      );
      await settle();
      server.override['GET /runs/7'] = [
        unreachable,
        unreachable,
        () => refusal(500, 'INTERNAL'),
      ];
      await vi.advanceTimersByTimeAsync(100);
      await vi.advanceTimersByTimeAsync(100);
      expect(later).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(100);
      expect(later).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1000);
      expect(later).toHaveBeenCalledTimes(1);
      expect(seen).toEqual(['queued']);
      stop();
    });

    it('404 → onMissing 한 번 · 꼴 밖 id 는 요청 0', async () => {
      const server = fakeDataverifyServer();
      const store = serverStoreOf(server, { pollMs: 100 });
      const missing = vi.fn();
      store.subscribeRun('12', () => undefined, missing);
      store.subscribeRun('abc', () => undefined, missing);
      await vi.advanceTimersByTimeAsync(1000);
      expect(missing).toHaveBeenCalledTimes(2);
      expect(server.calls).toHaveLength(1);
    });

    it('해제 뒤 온 답은 버리고 다음 폴링 0', async () => {
      const server = fakeDataverifyServer({ runs: [fakeRun(7)] });
      const store = serverStoreOf(server, { pollMs: 100 });
      const listener = vi.fn();
      const stop = store.subscribeRun('7', listener);
      stop();
      await vi.advanceTimersByTimeAsync(1000);
      expect(listener).not.toHaveBeenCalled();
      expect(server.count('GET /runs/7')).toBe(1);
    });
  });
});

describe('getResult · reportFile · rerun', () => {
  it('done → 결과 · queued·failed → not_done(409) · 없음 → not_found', async () => {
    const server = fakeDataverifyServer({
      runs: [fakeRun(1), fakeRun(2), fakeRun(3)],
    });
    server.advance(1, { status: 'done' });
    server.advance(3, { status: 'failed' });
    const store = serverStoreOf(server);
    expect((await store.getResult('1')).company.name).toBe('가상건설');
    await expect(store.getResult('2')).rejects.toMatchObject({
      kind: 'not_done',
    });
    await expect(store.getResult('3')).rejects.toMatchObject({
      kind: 'not_done',
    });
    await expect(store.getResult('4')).rejects.toMatchObject({
      kind: 'not_found',
    });
    server.override['GET /dataverify/runs/1/result'] = () =>
      json(200, { schemaVersion: 'dataverify.result@2' });
    await expect(store.getResult('1')).rejects.toBeInstanceOf(
      DataverifyStoreError,
    );
  });

  it('엑셀: 이름 그대로 받기 · 없으면 거절', async () => {
    const server = fakeDataverifyServer({ runs: [fakeRun(1), fakeRun(2)] });
    server.advance(1, { status: 'done' });
    server.advance(2, { status: 'done', files: [] });
    const store = serverStoreOf(server);
    const file = await store.reportFile('1');
    expect(file.fileName).toBe('dataverify-report.xlsx');
    expect(file.blob.size).toBe(6);
    expect(server.calls.at(-1)!.path).toBe(
      '/runs/1/files/dataverify-report.xlsx',
    );
    await expect(store.reportFile('2')).rejects.toMatchObject({
      kind: 'not_found',
    });
  });

  it('rerun: 받은 options 그대로 새 POST(resumeFromRunId 0) · 새 열쇠', async () => {
    const options = { input: input({ 환경: [edkItem({ 메모: '앞 실행' })] }) };
    const server = fakeDataverifyServer({
      runs: [
        fakeRun(5, {
          status: 'failed',
          options: JSON.parse(JSON.stringify(options)) as Record<
            string,
            unknown
          >,
        }),
      ],
    });
    const store = serverStoreOf(server, { newKey: keys() });
    expect(await store.rerun('5')).toEqual({ kind: 'started', runId: '30' });
    expect(await store.rerun('5')).toEqual({ kind: 'started', runId: '31' });
    const [first, second] = server.posts();
    expect(first!.body).toEqual({
      module: 'dataverify',
      launchKey: expect.stringMatching(UUID_PATTERN),
      options: JSON.parse(JSON.stringify(options)),
    });
    expect(first!.headers.get('Idempotency-Key')).not.toBe(
      second!.headers.get('Idempotency-Key'),
    );
    expect(await store.rerun('77')).toEqual({ kind: 'failed' });
    expect(await store.rerun('x')).toEqual({ kind: 'failed' });
  });
});

describe('steps 꼴', () => {
  it('fakeSteps 는 단계 다섯', () => {
    expect(fakeSteps(2, 'running').map((s) => s.status)).toEqual([
      'done',
      'done',
      'running',
      'pending',
      'pending',
    ]);
  });
});

describe('readEdkXlsx(DVX1 ②)', () => {
  const READ = 'POST /dataverify/edk/read';
  const XLSX =
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  const BYTES = new Uint8Array([80, 75, 3, 4, 1, 2, 3, 4, 5]);
  const file = () => new Blob([BYTES], { type: XLSX });

  it('맨 바이트를 Content-Type xlsx 로 보내고(multipart 0) ok 갈래를 그대로', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    expect(await store.readEdkXlsx(file())).toEqual(fakeEdkReadOk());
    const [call] = server.calls.filter(
      (each) => `${each.method} ${each.path}` === READ,
    );
    expect(call!.octets).toBe(BYTES.length);
    expect(call!.headers.get('Content-Type')).toBe(XLSX);
    expect(call!.search).toBe('');
  });

  it('거절 갈래는 값(kind·row·column·message 꼴 그대로)', async () => {
    const server = fakeDataverifyServer();
    server.override[READ] = () => json(200, edkRejected('bad_cell', 7, 11));
    const store = serverStoreOf(server);
    expect(await store.readEdkXlsx(file())).toEqual(
      edkRejected('bad_cell', 7, 11),
    );
  });

  it('strict 거울: 모르는 칸·모르는 kind·여섯째 칸 → rejected · 끊김 unreachable · 413·5xx rejected', async () => {
    const server = fakeDataverifyServer();
    server.override[READ] = [
      () => json(200, fakeEdkReadOk({ extra: 1 })),
      () => json(200, { ...edkRejected('not_xlsx'), sheet: 'x' }),
      () => json(200, edkRejected('not_a_kind')),
      () => json(200, fakeEdkReadOk({ skipped: { themes: 1 } })),
      () => json(200, { ...fakeEdkReadOk(), data: [] }),
      unreachable,
      () => refusal(413, 'BODY_TOO_LARGE'),
      () => refusal(500, 'INTERNAL'),
    ];
    const store = serverStoreOf(server);
    const kinds: string[] = [];
    for (let n = 0; n < 8; n += 1)
      kinds.push(
        await store.readEdkXlsx(file()).then(
          () => 'ok',
          (error: unknown) => (error as DataverifyStoreError).kind,
        ),
      );
    expect(kinds).toEqual([
      'rejected',
      'rejected',
      'rejected',
      'rejected',
      'rejected',
      'unreachable',
      'rejected',
      'rejected',
    ]);
  });

  it('거울 칸 이름이 openapi.json 의 스키마 칸과 같다', () => {
    const openapi = JSON.parse(
      readFileSync(
        resolve(
          dirname(fileURLToPath(import.meta.url)),
          '../../../../../api-py/generated/openapi.json',
        ),
        'utf8',
      ),
    ) as {
      components: {
        schemas: Record<string, { properties: Record<string, unknown> }>;
      };
    };
    for (const [name, fields] of Object.entries(MIRRORED_EDK_READ))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
  });
});

describe('downloadEdkTemplate(DVX1 ②)', () => {
  const TEMPLATE = 'GET /dataverify/edk/template';

  it('year 를 싣고 blob 과 Content-Disposition 이름(퍼센트 풂)', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    const got = await store.downloadEdkTemplate('2024');
    expect(got.fileName).toBe(FAKE_TEMPLATE_NAME);
    expect(new Uint8Array(await got.blob.arrayBuffer())).toEqual(
      FAKE_TEMPLATE_BYTES,
    );
    const [call] = server.calls.filter(
      (each) => `${each.method} ${each.path}` === TEMPLATE,
    );
    expect(call!.search).toBe('?year=2024');
  });

  it('year 가 없거나 네 자리 꼴 밖이면 빼고 보낸다', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    await store.downloadEdkTemplate();
    await store.downloadEdkTemplate('24');
    await store.downloadEdkTemplate('2024 ');
    expect(
      server.calls
        .filter((each) => `${each.method} ${each.path}` === TEMPLATE)
        .map((each) => each.search),
    ).toEqual(['', '', '']);
  });

  it('이름 머리가 없으면 기본 이름 · 끊김 unreachable · 거절 rejected', async () => {
    const server = fakeDataverifyServer();
    server.override[TEMPLATE] = [
      () => new Response(FAKE_TEMPLATE_BYTES, { status: 200 }),
      unreachable,
      () => refusal(401, 'NOT_AUTHENTICATED'),
    ];
    const store = serverStoreOf(server);
    expect((await store.downloadEdkTemplate('2024')).fileName).toBe(
      EDK_TEMPLATE_FILE_NAME,
    );
    await expect(store.downloadEdkTemplate('2024')).rejects.toMatchObject({
      kind: 'unreachable',
    });
    await expect(store.downloadEdkTemplate('2024')).rejects.toMatchObject({
      kind: 'rejected',
    });
  });
});
