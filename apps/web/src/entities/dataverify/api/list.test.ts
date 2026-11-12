// 실행 목록 · 출처(밴드 DV2b — 발주서 §3): 실어댑터 + 가짜 서버. listRuns 쿼리·쪽 크기·거울 거절 · startRun 의 source 두 갈래 ·
//   getRun 의 source(옛 실행·꼴 밖 null) · rerun 이 source 를 그대로 싣는다 · 거울 칸 이름이 openapi.json 과 같다.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { PASTE_SOURCE, buildInput, fileSource } from '../model/index.ts';
import type { EdkData } from '../model/index.ts';
import { FAKE_COMPANY, edkData, fakeInput } from '../model/testing.ts';
import { MIRRORED_LIST } from './contract/runs.ts';
import { DataverifyStoreError, RUN_PAGE_LIMIT } from './store.ts';
import {
  FAKE_OTHER,
  fakeDataverifyServer,
  fakeRun,
  json,
  serverStoreOf,
  unreachable,
} from './testing.ts';

const LIST = 'GET /dataverify/runs';
const input = () => buildInput(FAKE_COMPANY, edkData() as unknown as EdkData);
/** 마지막으로 보낸 URL 의 쿼리(같은 이름 여럿은 배열). */
function lastQuery(sent: string[]) {
  const url = new URL(sent.at(-1)!);
  const out: Record<string, string[]> = {};
  for (const [key, value] of url.searchParams) (out[key] ??= []).push(value);
  return out;
}

/** 보낸 URL 을 적는 가짜 서버(가짜 서버 calls 는 path 만 적는다). */
function recorded(runs = [fakeRun(1)]) {
  const server = fakeDataverifyServer({ runs });
  const sent: string[] = [];
  const send = server.send;
  const wrapped = {
    ...server,
    send: (request: Request) => {
      sent.push(request.url);
      return send(request);
    },
  };
  return { server: wrapped, sent };
}

describe('listRuns', () => {
  it('쿼리: limit 20 · offset · status 여러 번(한 요청) · mine 은 참일 때만', async () => {
    const { server, sent } = recorded();
    const store = serverStoreOf(server);
    await store.listRuns({ offset: 0 });
    expect(lastQuery(sent)).toEqual({
      limit: [String(RUN_PAGE_LIMIT)],
      offset: ['0'],
    });
    await store.listRuns({ status: ['queued', 'processing'], offset: 0 });
    expect(lastQuery(sent).status).toEqual(['queued', 'processing']);
    expect(server.count(LIST)).toBe(2);
    await store.listRuns({ status: ['done'], mine: true, offset: 20 });
    expect(lastQuery(sent)).toEqual({
      status: ['done'],
      mine: ['true'],
      limit: ['20'],
      offset: ['20'],
    });
    await store.listRuns({ status: [], mine: false, offset: 0 });
    expect(lastQuery(sent).status).toBeUndefined();
    expect(lastQuery(sent).mine).toBeUndefined();
  });

  it('쪽을 거울에 대 돌려준다(새 것 먼저 · 거른 뒤 count · isNext)', async () => {
    const server = fakeDataverifyServer({
      runs: Array.from({ length: 22 }, (_, i) => fakeRun(i + 1)),
    });
    const page = await serverStoreOf(server).listRuns({ offset: 0 });
    expect(page.count).toBe(22);
    expect(page.isNext).toBe(true);
    expect(page.results).toHaveLength(20);
    expect(page.results[0]!.id).toBe(22);
    expect(page.results[0]!.source).toBeNull();
    expect(page.results[0]!.reportingYear).toBe(FAKE_COMPANY.reportingYear);
  });

  it('꼴 틀림 → rejected · 답 없음 → unreachable', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    server.override[LIST] = [
      () => json(200, { count: 1, isNext: false, results: [{ id: 1 }] }),
      () => json(200, { count: 0, isNext: false, results: [], extra: 1 }),
      unreachable,
    ];
    await expect(store.listRuns({ offset: 0 })).rejects.toMatchObject({
      kind: 'rejected',
    });
    // 맨 위 모르는 칸은 버리고 지난다(칸 더하기는 같은 판 안 — run_list_shapes.py 머리).
    await expect(store.listRuns({ offset: 0 })).resolves.toMatchObject({
      count: 0,
    });
    const lost = await store.listRuns({ offset: 0 }).catch((e: unknown) => e);
    expect(lost).toBeInstanceOf(DataverifyStoreError);
    expect((lost as DataverifyStoreError).kind).toBe('unreachable');
  });

  it('줄의 source 가 꼴 밖이면 쪽 전체를 거절한다(서버는 꼴 밖을 null 로 낸다 — 오면 계약 어긋남)', async () => {
    const server = fakeDataverifyServer({ runs: [fakeRun(1)] });
    const store = serverStoreOf(server);
    const page = await store.listRuns({ offset: 0 });
    server.override[LIST] = () =>
      json(200, {
        ...page,
        results: [
          { ...page.results[0], source: { kind: 'file', name: 'a/b' } },
        ],
      });
    await expect(store.listRuns({ offset: 0 })).rejects.toMatchObject({
      kind: 'rejected',
    });
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
    for (const [name, fields] of Object.entries(MIRRORED_LIST))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
  });
});

describe('startRun 의 source', () => {
  it('파일 → {kind:file, name} · 붙여 넣기 → {kind:paste}(이름 0) · 없으면 열쇠 0', async () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    await store.startRun(input(), fileSource('EDK_가상_2025.json'));
    await store.startRun(input(), PASTE_SOURCE);
    await store.startRun(input());
    const sources = server
      .posts()
      .map(
        (post) => (post.body as { options: Record<string, unknown> }).options,
      );
    expect(sources[0]!.source).toEqual({
      kind: 'file',
      name: 'EDK_가상_2025.json',
    });
    expect(sources[1]!.source).toEqual({ kind: 'paste' });
    expect(Object.keys(sources[1]!.source as object)).toEqual(['kind']);
    expect('source' in sources[2]!).toBe(false);
  });
});

describe('getRun 의 source · rerun', () => {
  it('준 그대로 · 옛 실행(키 없음)·꼴 밖은 null', async () => {
    const server = fakeDataverifyServer({
      runs: [
        fakeRun(1, {
          options: {
            input: fakeInput(),
            source: { kind: 'file', name: 'a.json' },
          },
        }),
        fakeRun(2),
        fakeRun(3, {
          options: { input: fakeInput(), source: { kind: 'paste', name: 'x' } },
        }),
      ],
    });
    const store = serverStoreOf(server);
    expect((await store.getRun('1')).source).toEqual({
      kind: 'file',
      name: 'a.json',
    });
    expect((await store.getRun('2')).source).toBeNull();
    expect((await store.getRun('3')).source).toBeNull();
  });

  it('rerun 은 GET /runs/{id} 의 options 를 source 까지 그대로 싣는다', async () => {
    const options = {
      input: fakeInput(),
      source: { kind: 'file', name: 'a.json' },
    };
    const server = fakeDataverifyServer({
      runs: [fakeRun(1, { options, status: 'failed', createdBy: FAKE_OTHER })],
    });
    const out = await serverStoreOf(server).rerun('1');
    expect(out).toEqual({ kind: 'started', runId: '30' });
    expect((server.posts()[0]!.body as { options: unknown }).options).toEqual(
      options,
    );
  });
});
