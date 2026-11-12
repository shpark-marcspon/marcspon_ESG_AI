// 원고작성 실어댑터 시험(밴드 RPW1 ① — 발주서 §2-1 S1): 진짜 createApi 에 가짜 서버(api/testing.ts)를 물려 경로마다 메서드·경로·쿼리·
//   본문·id 정수를 단언한다. 서명 PUT 은 sendUpload(틀이 준 것)로만 — 세션 Api 로 나가지 않는다. confirm 을 건너뛰지 않는다.
//   갈래: 읽기 ok·refused(회사 셋)·not_found·failed · 쓰기 rejected{code, fields}·refused·failed · 서버 message 0(결과 JSON 에 없음).
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { createDraftingStore } from './server.ts';
import {
  fakeDraftingServer,
  fakeOutline,
  fakeResult,
  json,
  refusal,
  storeOf,
  unreachable,
} from './testing.ts';
import type { ResultWire } from './testing.ts';

const SERVER_TEXT = '지어낸-서버글';
const pdf = (name = '지어낸 보고서.pdf') =>
  new File([new Uint8Array([37, 80, 68, 70])], name, {
    type: 'application/pdf',
  });

function seeded(options: Parameters<typeof fakeDraftingServer>[0] = {}) {
  const server = fakeDraftingServer({
    projects: [{ id: 7, name: '지어낸 프로젝트', year: 2026 }],
    ...options,
  });
  let n = 0;
  const store = storeOf(server, {
    newKey: () => `0000000${++n}-0000-4000-8000-000000000000`,
    newLaunchKey: () => `1111111${n}-0000-4000-8000-000000000000`,
  });
  return { server, store };
}

describe('① 목록·프로젝트·만들기', () => {
  it('listProjects: GET /drafting/projects?limit=100&offset=0 · companyId 0', async () => {
    const { server, store } = seeded();
    const out = await store.listProjects();
    expect(out.kind).toBe('ok');
    const call = server.calls.at(-1)!;
    expect([call.method, call.path]).toEqual(['GET', '/drafting/projects']);
    expect(Object.fromEntries(call.query)).toEqual({
      limit: '100',
      offset: '0',
    });
  });

  it('getProject: 경로 id 정수 · 404 → not_found', async () => {
    const { server, store } = seeded();
    expect((await store.getProject(7)).kind).toBe('ok');
    expect(server.calls.at(-1)!.path).toBe('/drafting/projects/7');
    expect(await store.getProject(99)).toEqual({ kind: 'not_found' });
  });

  it('createProject: 본문 {year, name}(앞뒤 공백 걷음) · 422 → rejected fields', async () => {
    const { server, store } = seeded();
    const ok = await store.createProject({
      year: 2026,
      name: '  지어낸 새 보고서 ',
    });
    expect(ok.kind).toBe('ok');
    expect(server.bodies('POST /drafting/projects')).toEqual([
      { year: 2026, name: '지어낸 새 보고서' },
    ]);
    const bad = await store.createProject({ year: 1999, name: '가' });
    expect(bad).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { year: ['지어낸 연도'] },
    });
  });

  it('회사 거절 셋 → refused(읽기·쓰기 다)', async () => {
    const { store } = seeded({ company: 'COMPANY_INACTIVE' });
    expect(await store.listProjects()).toEqual({
      kind: 'refused',
      company: 'inactive',
    });
    expect(await store.createProject({ year: 2026, name: '가' })).toEqual({
      kind: 'refused',
      company: 'inactive',
    });
  });

  it('끊김·꼴 틀림 → failed', async () => {
    const { server, store } = seeded();
    server.override['GET /drafting/projects'] = [
      unreachable,
      () => json(200, { count: 'x' }),
    ];
    expect(await store.listProjects()).toEqual({ kind: 'failed' });
    expect(await store.listProjects()).toEqual({ kind: 'failed' });
  });
});

describe('① PDF 올림(POST → 서명 PUT → confirm) · 붙임', () => {
  it('셋을 차례로 · 서명 PUT 은 sendUpload 로만(세션 Api 0) · confirm 답의 쪽 수·hasText', async () => {
    const { server, store } = seeded({ pageCount: 3 });
    const out = await store.uploadPdf(pdf());
    expect(out).toEqual({
      kind: 'ok',
      value: { documentId: 101, pageCount: 3, hasText: true },
    });
    expect(server.calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      'POST /documents',
      'POST /documents/101/confirm',
    ]);
    expect(server.bodies('POST /documents')).toEqual([
      { fileName: '지어낸 보고서.pdf', sizeBytes: 4 },
    ]);
    expect(
      server.uploads.map((u) => [
        u.method,
        u.url.startsWith('http://storage.test/upload/101?'),
      ]),
    ).toEqual([['PUT', true]]);
  });

  it('올림 실패 → failed(confirm 없음) · confirm 거절 → rejected', async () => {
    const { server, store } = seeded();
    server.override['POST /documents'] = () =>
      json(201, {
        document: { id: 555 },
        upload: { url: 'http://storage.test/upload/555?x', method: 'PUT' },
      });
    expect(await store.uploadPdf(pdf())).toEqual({ kind: 'failed' });
    expect(server.count('POST /documents/555/confirm')).toBe(0);
  });

  it('hasText 거짓·null 을 그대로 낸다', async () => {
    expect((await seeded({ noText: true }).store.uploadPdf(pdf())).kind).toBe(
      'ok',
    );
    const none = await seeded({ noText: true }).store.uploadPdf(pdf());
    expect(none.kind === 'ok' && none.value.hasText).toBe(false);
    const unknown = await seeded({ textUnknown: true }).store.uploadPdf(pdf());
    expect(unknown.kind === 'ok' && unknown.value.hasText).toBeNull();
  });

  it('attachDocument: PUT …/document {documentId} · 글자 없는 문서 422 DOCUMENT_NO_TEXT_LAYER', async () => {
    const { server, store } = seeded();
    const up = await store.uploadPdf(pdf());
    const id = up.kind === 'ok' ? up.value.documentId : 0;
    const out = await store.attachDocument(7, id);
    expect(out.kind === 'ok' && out.value.pdf?.documentId).toBe(id);
    expect(server.bodies('PUT /drafting/projects/7/document')).toEqual([
      { documentId: id },
    ]);

    const bare = seeded({ noText: true });
    const up2 = await bare.store.uploadPdf(pdf());
    const id2 = up2.kind === 'ok' ? up2.value.documentId : 0;
    expect(await bare.store.attachDocument(7, id2)).toEqual({
      kind: 'rejected',
      code: 'DOCUMENT_NO_TEXT_LAYER',
      fields: {},
    });
  });
});

describe('② 목차 저장·실행 시작·실행 읽기', () => {
  it('saveOutline: PUT …/outline {nodes}(마디 다섯 칸만) · 422 nodes.<i>.title', async () => {
    const { server, store } = seeded();
    const out = await store.saveOutline(7, fakeOutline());
    expect(out.kind).toBe('ok');
    expect(server.bodies('PUT /drafting/projects/7/outline')).toEqual([
      { nodes: fakeOutline() },
    ]);
    const bad = await store.saveOutline(7, [
      { ...fakeOutline()[0]!, title: ' ' },
    ]);
    expect(bad).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: { 'nodes.0.title': ['지어낸 제목'] },
    });
  });

  it('startRun: POST /runs {module, launchKey, options} + Idempotency-Key · 끊김 뒤 같은 옵션은 같은 열쇠', async () => {
    const { server, store } = seeded();
    server.seedProject(7, {
      documentId: server.seedDocument(),
      nodes: fakeOutline(),
    });
    server.override['POST /runs'] = [unreachable];
    expect(await store.startRun({ projectId: 7 }, null)).toEqual({
      kind: 'failed',
    });
    const out = await store.startRun({ projectId: 7 }, null);
    expect(out).toEqual({ kind: 'ok', value: { runId: 301 } });
    const posts = server.calls.filter((c) => c.path === '/runs');
    expect(posts.map((c) => c.headers.get('Idempotency-Key'))).toEqual([
      '00000001-0000-4000-8000-000000000000',
      '00000001-0000-4000-8000-000000000000',
    ]);
    expect(posts[1]!.body).toEqual({
      module: 'drafting',
      launchKey: '11111111-0000-4000-8000-000000000000',
      options: { projectId: 7 },
    });
  });

  it('startRun: 서버 답은 RunCreatedOut{id, status} 뿐 — 새 실행도 같은 열쇠 다시 보냄도 201 로 실행 id', async () => {
    const { server, store } = seeded();
    server.override['POST /runs'] = [
      () => json(201, { id: 41, status: 'queued' }),
      () => json(201, { id: 41, status: 'processing' }),
    ];
    expect(await store.startRun({ projectId: 7 }, null)).toEqual({
      kind: 'ok',
      value: { runId: 41 },
    });
    expect(await store.startRun({ projectId: 7 }, null)).toEqual({
      kind: 'ok',
      value: { runId: 41 },
    });
  });

  it('startRun 거절 셋 → rejected code(서버 글 0)', async () => {
    const ai = seeded({ aiUnusable: true });
    ai.server.seedProject(7, {
      documentId: ai.server.seedDocument(),
      nodes: fakeOutline(),
    });
    const refused = await ai.store.startRun({ projectId: 7 }, null);
    expect(refused).toEqual({
      kind: 'rejected',
      code: 'AI_SETTING_UNUSABLE',
      fields: {},
    });
    expect(JSON.stringify(refused)).not.toContain(SERVER_TEXT);
    const bad = seeded();
    expect(await bad.store.startRun({ projectId: 7 }, null)).toEqual({
      kind: 'rejected',
      code: 'INVALID_OPTIONS',
      fields: {},
    });
  });

  it('startRun: 옵션 거울 밖(모르는 키)은 요청 없이 failed', async () => {
    const { server, store } = seeded();
    const odd = { projectId: 7, extra: 1 } as unknown as { projectId: number };
    expect(await store.startRun(odd, null)).toEqual({ kind: 'failed' });
    expect(server.count('POST /runs')).toBe(0);
  });

  it('getRun: GET /runs/{id} → 단계·옵션(errorCode·message 0) · 다른 모듈 → not_found', async () => {
    const { server, store } = seeded();
    server.seedProject(7, {
      documentId: server.seedDocument(),
      nodes: fakeOutline(),
    });
    await store.startRun({ projectId: 7 }, null);
    const out = await store.getRun(301);
    expect(out.kind === 'ok' && out.value).toEqual({
      id: 301,
      status: 'queued',
      steps: ['extract', 'map', 'draft', 'report'].map((step) => ({
        step,
        status: 'pending',
        done: null,
        total: null,
      })),
      projectId: 7,
      base: null,
    });
    server.override['GET /runs/302'] = () =>
      json(200, {
        id: 302,
        module: 'translation',
        status: 'done',
        options: {},
        steps: [],
        errorCode: null,
        createdAt: 'x',
        finishedAt: null,
      });
    expect(await store.getRun(302)).toEqual({ kind: 'not_found' });
  });

  it('openPdf: 문서마다 한 벌(같은 문서는 GET …/file 하나) · missing 은 쥐지 않음(다시 부르면 다시 읽음)', async () => {
    const { server, store } = seeded({
      pdfs: { 101: new Uint8Array([37, 80, 68, 70]) },
    });
    server.seedDocument();
    server.seedDocument();
    const [first, second] = await Promise.all([
      store.openPdf(101),
      store.openPdf(101),
    ]);
    expect(first.kind).toBe('ready');
    expect(await store.openPdf(101)).toBe(first);
    expect(second).toBe(first);
    expect(server.count('GET /documents/101/file')).toBe(1);
    expect(await store.openPdf(102)).toEqual({ kind: 'missing' });
    expect(await store.openPdf(102)).toEqual({ kind: 'missing' });
    expect(server.count('GET /documents/102/file')).toBe(2);
  });
});

/** 저장소를 새로 짓는다(기본 모듈 표) — 경로 컴포넌트가 다시 마운트된 꼴. 프로젝트 id 는 시험마다 겹치지 않게. */
function remounted(projectId: number) {
  const server = fakeDraftingServer({
    projects: [{ id: projectId, name: '지어낸 프로젝트', year: 2026 }],
  });
  server.seedProject(projectId, {
    documentId: server.seedDocument(),
    nodes: fakeOutline(),
  });
  return {
    server,
    fresh: () =>
      createDraftingStore({
        api: createApi({
          baseUrl: 'http://test.local/api',
          fetch: server.send,
        }),
        sendUpload: server.sendUpload,
      }),
    sent: () =>
      server.calls
        .filter((call) => call.path === '/runs')
        .map((call) => [
          call.headers.get('Idempotency-Key'),
          (call.body as { launchKey: string }).launchKey,
        ]),
  };
}

describe('M5 실행 시작 열쇠의 수명', () => {
  it('failed 뒤 다시 마운트 → 같은 Idempotency-Key·launchKey · 실행 하나', async () => {
    const { server, fresh, sent } = remounted(7101);
    server.override['POST /runs'] = [unreachable];
    expect(await fresh().startRun({ projectId: 7101 }, 201)).toEqual({
      kind: 'failed',
    });
    expect((await fresh().startRun({ projectId: 7101 }, 201)).kind).toBe('ok');
    const [first, second] = sent();
    expect(second).toEqual(first);
    expect(server.runs()).toHaveLength(1);
  });

  it('refused 뒤에도 같은 열쇠 · ok 로 끝나면 표에서 지움', async () => {
    const { server, fresh, sent } = remounted(7102);
    server.override['POST /runs'] = [() => refusal(400, 'COMPANY_INACTIVE')];
    expect((await fresh().startRun({ projectId: 7102 }, 201)).kind).toBe(
      'refused',
    );
    expect((await fresh().startRun({ projectId: 7102 }, 201)).kind).toBe('ok');
    expect(sent()[1]).toEqual(sent()[0]);
  });

  it('ok 뒤 같은 본문 → 새 열쇠 · 실행 둘', async () => {
    const { server, fresh, sent } = remounted(7103);
    await fresh().startRun({ projectId: 7103 }, 201);
    await fresh().startRun({ projectId: 7103 }, 201);
    const [first, second] = sent();
    expect(second![0]).not.toBe(first![0]);
    expect(second![1]).not.toBe(first![1]);
    expect(server.runs()).toHaveLength(2);
  });

  it('rejected 뒤 같은 본문 → 새 열쇠', async () => {
    const { server, fresh, sent } = remounted(7104);
    server.override['POST /runs'] = [() => refusal(409, 'AI_SETTING_UNUSABLE')];
    expect((await fresh().startRun({ projectId: 7104 }, 201)).kind).toBe(
      'rejected',
    );
    await fresh().startRun({ projectId: 7104 }, 201);
    expect(sent()[1]![0]).not.toBe(sent()[0]![0]);
  });

  it('목차 판이 다르면 새 열쇠 · outlineRef 는 본문에 싣지 않음', async () => {
    const { server, fresh, sent } = remounted(7105);
    server.override['POST /runs'] = [unreachable];
    await fresh().startRun({ projectId: 7105 }, 201);
    await fresh().startRun({ projectId: 7105 }, 202);
    expect(sent()[1]![0]).not.toBe(sent()[0]![0]);
    expect(
      (server.bodies('POST /runs')[1] as { options: unknown }).options,
    ).toEqual({ projectId: 7105 });
  });
});

describe('⑨ 올림 끊기', () => {
  const pdfFile = () =>
    new File([new Uint8Array([37, 80, 68, 70])], '지어낸.pdf', {
      type: 'application/pdf',
    });

  it('signal 을 서명 PUT 에 넘긴다 · 끊겨 던지면 failed · confirm 0', async () => {
    const server = fakeDraftingServer();
    const control = new AbortController();
    const got: (AbortSignal | undefined)[] = [];
    const store = createDraftingStore({
      api: createApi({ baseUrl: 'http://test.local/api', fetch: server.send }),
      pendingRuns: new Map(),
      sendUpload: async (_url, _method, _file, signal) => {
        got.push(signal);
        control.abort();
        throw new Error('지어낸 끊김');
      },
    });
    expect(await store.uploadPdf(pdfFile(), control.signal)).toEqual({
      kind: 'failed',
    });
    expect(got).toEqual([control.signal]);
    expect(server.count('POST /documents/101/confirm')).toBe(0);
  });

  it('PUT 이 끝난 뒤 끊겨도 confirm 을 보내지 않는다', async () => {
    const server = fakeDraftingServer();
    const control = new AbortController();
    const store = createDraftingStore({
      api: createApi({ baseUrl: 'http://test.local/api', fetch: server.send }),
      pendingRuns: new Map(),
      sendUpload: async (url, method, file) => {
        await server.sendUpload(url, method, file);
        control.abort();
      },
    });
    expect(await store.uploadPdf(pdfFile(), control.signal)).toEqual({
      kind: 'failed',
    });
    expect(server.count('POST /documents/101/confirm')).toBe(0);
  });
});

describe('502 시험 빈 곳', () => {
  it('ⓐ listRuns: GET …/runs?limit=50&offset=0', async () => {
    const { server, store } = seeded();
    expect((await store.listRuns(7)).kind).toBe('ok');
    const call = server.calls.at(-1)!;
    expect([call.method, call.path]).toEqual([
      'GET',
      '/drafting/projects/7/runs',
    ]);
    expect(Object.fromEntries(call.query)).toEqual({
      limit: '50',
      offset: '0',
    });
  });

  const LEAVES = ['done', 'no_material', 'failed', 'not_run', 'done'].map(
    (status, at) => ({
      key: `k${at}`,
      titlePath: ['지어낸'],
      pages: [],
      reusedFrom: null,
      outcome: { status },
    }),
  ) as unknown as ResultWire['leaves'];

  /** 실행 하나를 그 꼴로 옮긴 뒤 목록 줄의 latestRun. */
  function latest(
    status: 'queued' | 'processing' | 'done' | 'failed',
    patch?: Parameters<typeof fakeResult>[2],
  ) {
    const { server, store } = seeded();
    server.seedProject(7, {
      documentId: server.seedDocument(),
      nodes: fakeOutline(),
    });
    return store.startRun({ projectId: 7 }, null).then(() => {
      server.runPatch(301, { status });
      if (patch) server.results.set(301, fakeResult(server, 301, patch));
      return server.project(7)!.latestRun!;
    });
  }

  it('ⓑ 가짜 잎 셈 == RPS1 runs.py _leaves — done·@3 만 값, rejected 도 잎을 센다, 그 밖 null', async () => {
    const counts = {
      total: 5,
      drafted: 2,
      noMaterial: 1,
      failed: 1,
      notRun: 1,
    };
    const done = await latest('done', { leaves: LEAVES });
    expect([done.rejected, done.leaves]).toEqual([false, counts]);
    const rejected = await latest('done', {
      leaves: LEAVES,
      status: {
        status: 'rejected',
        code: 'over_budget',
        stage: 'before_draft',
      } as ResultWire['status'],
    });
    expect([rejected.rejected, rejected.leaves]).toEqual([true, counts]);
    const noResult = await latest('done');
    expect([noResult.rejected, noResult.leaves]).toEqual([null, null]);
    for (const status of ['queued', 'processing', 'failed'] as const) {
      const run = await latest(status);
      expect([status, run.rejected, run.leaves]).toEqual([status, null, null]);
    }
  });
});

describe('RPW3 D6 쓰기 갈래 — 5xx 는 failed', () => {
  it.each([
    ['봉투 있는 500', () => refusal(500, 'INTERNAL_ERROR')],
    ['봉투 없는 503', () => new Response('', { status: 503 })],
  ])(
    '시작 %s → failed · 다시 누르면 같은 Idempotency-Key·launchKey · 실행 하나',
    async (_name, answer) => {
      const id = _name === '봉투 있는 500' ? 7201 : 7202;
      const { server, fresh, sent } = remounted(id);
      server.override['POST /runs'] = [answer];
      expect(await fresh().startRun({ projectId: id }, 201)).toEqual({
        kind: 'failed',
      });
      expect((await fresh().startRun({ projectId: id }, 201)).kind).toBe('ok');
      expect(sent()[1]).toEqual(sent()[0]);
      expect(server.runs()).toHaveLength(1);
    },
  );

  it('시작 4xx 거절 → rejected · 다시 누르면 새 열쇠 둘 다', async () => {
    const { server, fresh, sent } = remounted(7203);
    server.override['POST /runs'] = [() => refusal(422, 'VALIDATION_ERROR')];
    expect((await fresh().startRun({ projectId: 7203 }, 201)).kind).toBe(
      'rejected',
    );
    await fresh().startRun({ projectId: 7203 }, 201);
    expect(sent()[1]![0]).not.toBe(sent()[0]![0]);
    expect(sent()[1]![1]).not.toBe(sent()[0]![1]);
  });

  it('getDocument — 파일 이름·쪽 수 · 없으면 not_found', async () => {
    const { server, fresh } = remounted(7204);
    const documentId = server.seedDocument('지어낸 원본.pdf');
    expect(await fresh().getDocument(documentId)).toEqual({
      kind: 'ok',
      value: { fileName: '지어낸 원본.pdf', pageCount: expect.any(Number) },
    });
    expect((await fresh().getDocument(99_999)).kind).toBe('not_found');
  });
});
