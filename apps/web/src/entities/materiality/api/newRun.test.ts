// 새 평가 어댑터(밴드 IRW2 ② — 발주서 §3 시험 4). 진짜 실어댑터 + 가짜 서버.
//   readValueChain: 맨 바이트(Content-Type xlsx, multipart 아님) · ok 두 갈래 거울(strict — 모르는 칸 rejected) · 끊김 unreachable · 5xx rejected ·
//     거울 칸 이름이 openapi.json 의 스키마 칸과 같다.
//   createRun: 본문 열쇠 셋(module·launchKey·options{input}) · Idempotency-Key · 실패 뒤 같은 입력이면 같은 두 열쇠, 입력이 바뀌면 새로,
//     만들어지면 버린다 · 422 failed · 끊김 unreachable.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { buildInput } from '../model/index.ts';
import { fakeDraft } from '../model/testing.ts';
import { MIRRORED_VALUE_CHAIN } from './contract/valueChain.ts';
import { MaterialityStoreError } from './store.ts';
import {
  FAKE_VALUE_CHAIN_OK,
  fakeMaterialityServer,
  json,
  refusal,
  serverStoreOf,
  unreachable,
  valueChainRejected,
} from './testing.ts';

const READ = 'POST /materiality/value-chain/read';
const XLSX =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const BYTES = new Uint8Array([80, 75, 3, 4, 1, 2, 3]);
const file = () => new Blob([BYTES], { type: XLSX });

/** 열쇠를 차례로 내는 짓개. */
const keys = (prefix: string) => {
  let n = 0;
  return () =>
    `${prefix}${String((n += 1)).padStart(7, '0')}-0000-4000-8000-000000000000`;
};

describe('readValueChain', () => {
  it('맨 바이트를 Content-Type xlsx 로 보내고 ok 갈래를 그대로', async () => {
    const server = fakeMaterialityServer();
    const read = await serverStoreOf(server).readValueChain(file());
    expect(read).toEqual(FAKE_VALUE_CHAIN_OK);
    const [call] = server.calls;
    expect(`${call!.method} ${call!.path}`).toBe(READ);
    expect([...call!.bytes]).toEqual([...BYTES]);
    expect(call!.headers.get('Content-Type')).toBe(XLSX);
  });

  it('ok:false 갈래도 200 그대로(kind·row·column)', async () => {
    const server = fakeMaterialityServer({
      valueChain: valueChainRejected('too_long', 3, 1),
    });
    const read = await serverStoreOf(server).readValueChain(file());
    expect(read).toMatchObject({
      ok: false,
      kind: 'too_long',
      row: 3,
      column: 1,
    });
  });

  it('꼴 밖(모르는 칸·모르는 kind·column 5·행 0개)은 rejected', async () => {
    for (const body of [
      { ...FAKE_VALUE_CHAIN_OK, extra: 1 },
      valueChainRejected('later_kind'),
      valueChainRejected('too_long', 1, 5),
      { ok: true, rows: [], rowCount: 0 },
      {
        ...FAKE_VALUE_CHAIN_OK,
        rows: [{ ...FAKE_VALUE_CHAIN_OK.rows[0], sixth: '' }],
      },
    ]) {
      const server = fakeMaterialityServer({ valueChain: body });
      const error = await serverStoreOf(server)
        .readValueChain(file())
        .catch((caught: unknown) => caught);
      expect(error, JSON.stringify(body)).toBeInstanceOf(MaterialityStoreError);
      expect((error as MaterialityStoreError).kind).toBe('rejected');
    }
  });

  it('끊김 unreachable · 5xx·413 rejected', async () => {
    const server = fakeMaterialityServer();
    server.override[READ] = [
      unreachable,
      () => refusal(503, 'SERVICE_UNAVAILABLE'),
      () => refusal(413, 'PAYLOAD_TOO_LARGE'),
    ];
    const store = serverStoreOf(server);
    const kinds: string[] = [];
    for (let i = 0; i < 3; i += 1)
      kinds.push(
        await store.readValueChain(file()).then(
          () => 'ok',
          (error: unknown) => (error as MaterialityStoreError).kind,
        ),
      );
    expect(kinds).toEqual(['unreachable', 'rejected', 'rejected']);
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
    for (const [name, fields] of Object.entries(MIRRORED_VALUE_CHAIN))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
  });
});

describe('createRun', () => {
  const input = buildInput(fakeDraft());

  it('POST /runs {module, launchKey, options:{input}} + Idempotency-Key → started', async () => {
    const server = fakeMaterialityServer({ nextRunId: 41 });
    const store = serverStoreOf(server, {
      newKey: keys('a'),
      newLaunchKey: keys('b'),
    });
    expect(await store.createRun(input)).toEqual({
      kind: 'started',
      runId: '41',
    });
    const [post] = server.posts();
    expect(Object.keys(post!.body as object)).toEqual([
      'module',
      'launchKey',
      'options',
    ]);
    expect(post!.body).toEqual({
      module: 'materiality',
      launchKey: 'b0000001-0000-4000-8000-000000000000',
      options: { input },
    });
    expect(post!.headers.get('Idempotency-Key')).toBe(
      'a0000001-0000-4000-8000-000000000000',
    );
  });

  it('실패 뒤 같은 입력이면 같은 두 열쇠, 입력이 바뀌면 새로, 만들어지면 버린다', async () => {
    const server = fakeMaterialityServer();
    server.override['POST /runs'] = [
      unreachable,
      () => refusal(422, 'VALIDATION_ERROR'),
    ];
    const store = serverStoreOf(server, {
      newKey: keys('a'),
      newLaunchKey: keys('b'),
    });
    expect(await store.createRun(input)).toEqual({ kind: 'unreachable' });
    expect(await store.createRun(input)).toEqual({ kind: 'failed' });
    expect((await store.createRun(input)).kind).toBe('started');
    const changed = buildInput(fakeDraft({ company: '가상물산 둘' }));
    expect((await store.createRun(changed)).kind).toBe('started');
    expect((await store.createRun(changed)).kind).toBe('started');
    const ik = server
      .posts()
      .map((post) => post.headers.get('Idempotency-Key')!.slice(0, 8));
    const lk = server
      .posts()
      .map((post) =>
        (post.body as { launchKey: string }).launchKey.slice(0, 8),
      );
    expect(ik).toEqual([
      'a0000001',
      'a0000001',
      'a0000001',
      'a0000002',
      'a0000003',
    ]);
    expect(lk).toEqual([
      'b0000001',
      'b0000001',
      'b0000001',
      'b0000002',
      'b0000003',
    ]);
  });

  it('답 꼴 틀림 failed · forget 뒤 다음 누름은 새 열쇠', async () => {
    const server = fakeMaterialityServer();
    server.override['POST /runs'] = [() => json(201, { status: 'queued' })];
    const store = serverStoreOf(server, {
      newKey: keys('a'),
      newLaunchKey: keys('b'),
    });
    expect(await store.createRun(input)).toEqual({ kind: 'failed' });
    store.forget();
    await store.createRun(input);
    expect(
      server
        .posts()
        .map((post) => post.headers.get('Idempotency-Key')!.slice(0, 8)),
    ).toEqual(['a0000001', 'a0000002']);
  });
});
