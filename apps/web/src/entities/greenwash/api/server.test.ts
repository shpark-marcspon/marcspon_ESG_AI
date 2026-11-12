// 그린워싱 실어댑터(밴드 GW1R ① — 발주서 §3 A·B): 진짜 createApi 에 가짜 서버(모킹한 fetch)를 물려 부른 경로·본문·쿼리를 정확히 단언한다.
//   A 순수: 나가는 id, checks → 목록 원재료(자료 조건 ①~⑥), RunOut → 스냅샷.
//   B 어댑터: 올리기 셋째 걸음·실행 만들기·읽기·폴링(가짜 타이머)·다시 실행·409 갈래·검토 PUT 본문·checks 꼴 틀림.
import { afterEach, describe, expect, it, vi } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { buildCheckRows, overallPercent } from '../model/index.ts';
import { IDEMPOTENCY_KEY_PATTERN } from './idempotency.ts';
import { RUN_POLL_MS, createGreenwashServerStore } from './index.ts';
import type { GreenwashServerDeps, RunSnapshot } from './index.ts';
import { checkRowsOf, serverId, snapshotOf } from './server.ts';
import { StoreError, storeErrorKind } from './store.ts';
import {
  FAKE_CONFIRMER,
  FAKE_PDF_BYTES,
  fakeDocument,
  fakeGreenwashServer,
  fakeRun,
  fakeSteps,
  json,
  listedGreenwashServer,
  refusal,
} from './testing.ts';
import type { FakeGreenwashServer } from './testing.ts';

const BASE = 'http://test.local/api';

function setup(
  server: FakeGreenwashServer = fakeGreenwashServer(),
  deps: Partial<GreenwashServerDeps> = {},
) {
  const countPages = vi.fn(async () => 7);
  const sendUpload = vi.fn(server.sendUpload);
  const control = createGreenwashServerStore({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
    sendUpload,
    countPages,
    ...deps,
  });
  return { server, store: control.store, control, countPages, sendUpload };
}

const pdf = (size = 2048, name = '지어낸 보고서.pdf') =>
  new File([new Uint8Array(size)], name, { type: 'application/pdf' });

const keys = (server: FakeGreenwashServer) =>
  server.calls.map((call) => `${call.method} ${call.path}`);

const rejectionOf = async (promise: Promise<unknown>) => {
  try {
    await promise;
  } catch (error) {
    return storeErrorKind(error);
  }
  throw new Error('거절되지 않았다');
};

afterEach(() => {
  vi.useRealTimers();
});

describe('A — 나가는 id', () => {
  it("'12' → 12, 양의 정수 글자가 아니면 null", () => {
    expect(serverId('12')).toBe(12);
    for (const bad of ['run-1', '012', '1.5', '', '0', '-3', ' 12', '1e3'])
      expect(serverId(bad)).toBeNull();
  });

  it.each(['run-1', '012', '1.5', ''])(
    '%j 는 요청 없이 not_found(읽기·결과·검토·저장), 구독이면 onMissing',
    async (bad) => {
      const { server, store } = setup();
      expect(await rejectionOf(store.getRun(bad))).toBe('not_found');
      expect(await rejectionOf(store.getResult(bad))).toBe('not_found');
      expect(await rejectionOf(store.getReview(bad))).toBe('not_found');
      expect(await rejectionOf(store.putReview(bad, { marks: [] }))).toBe(
        'not_found',
      );
      expect(await rejectionOf(store.getDocument(bad))).toBe('not_found');
      const onMissing = vi.fn();
      const listener = vi.fn();
      store.subscribeRun(bad, listener, onMissing);
      await vi.waitFor(() => expect(onMissing).toHaveBeenCalledTimes(1));
      expect(listener).not.toHaveBeenCalled();
      expect(server.calls).toEqual([]);
    },
  );
});

describe('A — checks → 목록 원재료(자료 조건 ①~⑥)', () => {
  it('id 는 글자, confirmedBy 는 이름만, progress 는 단계로, errorCode 는 그대로, uploadedAt null 은 이른 실행 때', async () => {
    const { store } = setup(listedGreenwashServer());
    const source = await store.listCheckRows();
    expect(source.currentUserId).toBe('7');
    expect(source.companyName).toBe('지어낸 회사');
    expect(source.documents.map((doc) => doc.uploadedBy)).toEqual([
      { userId: '7', name: '담당자 가' },
      { userId: '8', name: '담당자 나' },
      { userId: '8', name: '담당자 나' },
      { userId: '7', name: '담당자 가' },
    ]);
    expect(source.documents.map((doc) => doc.documentId)).toEqual([
      '1',
      '2',
      '3',
      '4',
    ]);
    expect(source.documents.map((doc) => doc.pageCount)).toEqual([
      40,
      null,
      10,
      10,
    ]);
    // ⑥ 올림 확인 전(null)이면 그 문서 실행 가운데 이른 만든 때.
    expect(source.documents[2]!.uploadedAt).toBe('2026-10-18T09:07:00+09:00');
    const runs = Object.fromEntries(source.runs.map((run) => [run.runId, run]));
    expect(Object.keys(runs)).toEqual(['5', '6', '7', '8']);
    expect(runs['5']!.documentId).toBe('1');
    // ② 확정자는 이름만(id 9 는 싣지 않는다).
    expect(runs['5']!.review).toEqual({
      state: 'confirmed',
      reviewed: 3,
      total: 3,
      confirmedAt: '2026-10-18T10:00:00+09:00',
      confirmedBy: FAKE_CONFIRMER.name,
    });
    // ③ extract done · index done · judge running 3/10 → 판정 3/10, 34%.
    expect(runs['6']!.progress).toEqual({
      state: 'running',
      stage: 'judge',
      judge: { done: 3, total: 10 },
    });
    expect(overallPercent(runs['6']!.progress)).toBe(34);
    // ④ 실패 둘 다 extract 에서 멈춤, code 는 그대로.
    expect(runs['7']!.progress.state).toBe('failed');
    expect(runs['7']!.progress.stage).toBe('extract');
    expect(runs['8']!.progress.stage).toBe('extract');
    expect(runs['7']!.errorCode).toBe('no_text_layer');
    expect(runs['8']!.errorCode).toBe('step_error');
    expect(runs['5']!.errorCode).toBeNull();
    // 줄 짓기(모델)가 그대로 받는다.
    expect(buildCheckRows(source).map((row) => row.status)).toEqual([
      'failed',
      'failed',
      'running',
      'confirmed',
    ]);
  });

  it('[R3] uploadedAt null 은 그 문서 실행 가운데 가장 이른 만든 때(줄 차례와 무관)', async () => {
    const server = fakeGreenwashServer({
      documents: [fakeDocument(3, { uploadedAt: null })],
      runs: [
        fakeRun(9, 3, { createdAt: '2026-10-18T11:00:00+09:00' }),
        fakeRun(5, 3, { createdAt: '2026-10-18T10:00:00+09:00' }),
        fakeRun(7, 3, { createdAt: '2026-10-18T10:30:00+09:00' }),
      ],
    });
    const { store } = setup(server);
    const source = await store.listCheckRows();
    expect(source.documents[0]!.uploadedAt).toBe('2026-10-18T10:00:00+09:00');
  });

  it('G1e 전 꼴(runs[].errorCode 없음)도 받는다 — null 로', () => {
    const source = checkRowsOf({
      schemaVersion: 'greenwash.checks@1',
      currentUserId: 7,
      companyName: '지어낸 회사',
      documents: [],
      runs: [
        {
          runId: 5,
          documentId: 1,
          createdAt: '2026-10-18T09:05:00+09:00',
          createdByUserId: 7,
          status: 'failed',
          steps: fakeSteps(0, { status: 'failed' }),
          checkedPages: 3,
          levelCounts: null,
          review: null,
        },
      ],
    });
    expect(source?.runs[0]!.errorCode).toBeNull();
  });

  it('runs[].finishedAt(GCB1): 글자는 그대로, null 은 null, 없음(옛 서버)은 null, 수면 꼴 틀림(응답 null — 다른 칸과 같은 규칙)', () => {
    const run = (id: number, patch: Record<string, unknown>) => ({
      runId: id,
      documentId: 1,
      createdAt: '2026-10-18T09:05:00+09:00',
      createdByUserId: 7,
      status: 'done',
      steps: fakeSteps(10),
      checkedPages: 3,
      levelCounts: null,
      review: null,
      errorCode: null,
      ...patch,
    });
    const body = (runs: unknown[]) => ({
      schemaVersion: 'greenwash.checks@1',
      currentUserId: 7,
      companyName: '지어낸 회사',
      documents: [],
      runs,
    });
    const source = checkRowsOf(
      body([
        run(5, { finishedAt: '2026-10-19T00:10:00+09:00' }),
        run(6, { finishedAt: null }),
        run(7, {}),
      ]),
    );
    expect(source?.runs.map((r) => [r.runId, r.finishedAt])).toEqual([
      ['5', '2026-10-19T00:10:00+09:00'],
      ['6', null],
      ['7', null],
    ]);
    expect(checkRowsOf(body([run(8, { finishedAt: 1760000000 })]))).toBeNull();
    expect(checkRowsOf(body([run(9, { finishedAt: true })]))).toBeNull();
  });

  it.each([
    ['schemaVersion 이 다름', { schemaVersion: 'greenwash.checks@2' }],
    ['currentUserId 가 글자', { currentUserId: '7' }],
    ['runs 가 없음', { runs: undefined }],
  ])('꼴 틀림(%s) → null', (_name, patch) => {
    expect(
      checkRowsOf({
        schemaVersion: 'greenwash.checks@1',
        currentUserId: 7,
        companyName: '회사',
        documents: [],
        runs: [],
        ...patch,
      }),
    ).toBeNull();
  });
});

describe('A — RunOut → 스냅샷', () => {
  it('checkedPages 는 겹친 쪽을 한 번만 센 합집합, errorCode·startedAt·finishedAt 그대로, pageCount·rerunOf null', () => {
    const snapshot = snapshotOf({
      id: 12,
      documentId: 3,
      module: 'greenwash',
      status: 'failed',
      steps: fakeSteps(0, { status: 'failed' }),
      options: { parts: { ceo: [1, 2], company: [2, 3], climate: [3, 4] } },
      parts: { ceo: [1, 2], company: [2, 3], climate: [3, 4] },
      startedAt: '2026-10-18T09:00:00+09:00',
      finishedAt: '2026-10-18T09:03:00+09:00',
      errorCode: 'no_text_layer',
    });
    expect(snapshot).toEqual({
      runId: '12',
      documentId: '3',
      startedAt: '2026-10-18T09:00:00+09:00',
      finishedAt: '2026-10-18T09:03:00+09:00',
      pageCount: null,
      checkedPages: 4,
      progress: {
        state: 'failed',
        stage: 'extract',
        judge: { done: 0, total: 4 },
      },
      rerunOf: null,
      errorCode: 'no_text_layer',
    });
  });

  it('options 꼴이 틀리면(parts 없음·쪽이 글자) 거절, 그린워싱이 아닌 실행은 not_found', async () => {
    const server = fakeGreenwashServer({
      documents: [fakeDocument(1)],
      runs: [
        fakeRun(5, 1, { options: { extraTerms: [] } }),
        fakeRun(6, 1, {
          options: { parts: { ceo: ['1'], company: [], climate: [] } },
        }),
        fakeRun(7, 1, { module: 'inventory' }),
      ],
    });
    const { store } = setup(server);
    expect(await rejectionOf(store.getRun('5'))).toBe('rejected');
    expect(await rejectionOf(store.getRun('6'))).toBe('rejected');
    expect(await rejectionOf(store.getRun('7'))).toBe('not_found');
  });
});

describe('B — createDocument(올리기 셋째 걸음)', () => {
  it('쪽 세기 → POST /documents {fileName, sizeBytes} → sendUpload(url, PUT, file) → POST /documents/12/confirm, 답 {12, 7쪽, 글자 있음}', async () => {
    const { server, store, countPages, sendUpload } = setup();
    const file = pdf(2048);
    const created = await store.createDocument(file);
    expect(created).toEqual({ documentId: '12', pageCount: 7, hasText: true });
    expect(countPages).toHaveBeenCalledWith(file);
    expect(keys(server)).toEqual([
      'POST /documents',
      'POST /documents/12/confirm',
    ]);
    expect(server.calls[0]!.body).toEqual({
      fileName: '지어낸 보고서.pdf',
      sizeBytes: 2048,
    });
    expect(server.calls[1]!.body).toBeUndefined();
    expect(sendUpload).toHaveBeenCalledTimes(1);
    expect(sendUpload).toHaveBeenCalledWith(
      'http://test.local/fake-upload/12',
      'PUT',
      file,
    );
    expect(server.uploads).toEqual([
      { url: 'http://test.local/fake-upload/12', method: 'PUT', size: 2048 },
    ]);
    // 어느 요청에도 companyId 가 없다.
    for (const call of server.calls) {
      expect(call.query.has('companyId')).toBe(false);
      expect(JSON.stringify(call.body ?? {})).not.toContain('companyId');
    }
    // 이 탭에서 올린 File 은 원본 PDF 로 남는다(Q11), forget 하면 비운다.
    expect(await store.openDocumentPdf('12')).toBe(file);
    expect((await store.getDocument('12')).pageCount).toBe(7);
  });

  it('서버가 쪽 수·글자 층을 알면(X1b-2a) 그 값이 이긴다', async () => {
    const { store } = setup(
      fakeGreenwashServer({ serverPageCount: 9, serverHasText: false }),
    );
    expect(await store.createDocument(pdf())).toEqual({
      documentId: '12',
      pageCount: 9,
      hasText: false,
    });
  });

  it('쪽을 못 세면(던짐·0) POST 0 으로 거절', async () => {
    for (const countPages of [
      vi.fn(async () => {
        throw new Error('PDF 아님');
      }),
      vi.fn(async () => 0),
    ]) {
      const { server, store } = setup(fakeGreenwashServer(), { countPages });
      expect(await rejectionOf(store.createDocument(pdf()))).toBe('rejected');
      expect(server.calls).toEqual([]);
    }
  });

  it('413 은 크기 갈래(too_large — GP1 §1-8)·confirm 409·올리기 실패는 거절(올리기 실패면 confirm 0)', async () => {
    const big = setup();
    big.server.override['POST /documents'] = () =>
      refusal(413, 'UPLOAD_TOO_LARGE');
    expect(await rejectionOf(big.store.createDocument(pdf()))).toBe(
      'too_large',
    );
    expect(big.sendUpload).not.toHaveBeenCalled();

    const mismatch = setup();
    mismatch.server.override['POST /documents/12/confirm'] = () =>
      refusal(409, 'UPLOAD_SIZE_MISMATCH');
    expect(await rejectionOf(mismatch.store.createDocument(pdf()))).toBe(
      'rejected',
    );

    const putFails = setup(fakeGreenwashServer(), {
      sendUpload: vi.fn(async () => {
        throw new Error('403');
      }),
    });
    expect(await rejectionOf(putFails.store.createDocument(pdf()))).toBe(
      'rejected',
    );
    expect(keys(putFails.server)).toEqual(['POST /documents']);
    expect(await putFails.store.openDocumentPdf('12')).toBeNull();

    // 서명 PUT 이 앞단 413 으로 막히면(app 의 sendUpload 가 too_large 로 던짐) 그 갈래 그대로(밴드 GP1)
    const proxyTooLarge = setup(fakeGreenwashServer(), {
      sendUpload: vi.fn(async () => {
        throw new StoreError('too_large', '올리기 실패 413');
      }),
    });
    expect(await rejectionOf(proxyTooLarge.store.createDocument(pdf()))).toBe(
      'too_large',
    );
    expect(keys(proxyTooLarge.server)).toEqual(['POST /documents']);
  });

  it('[R2] getDocument 는 서버 쪽 수가 생기면 이 탭의 셈보다 서버 값', async () => {
    const { server, store } = setup();
    await store.createDocument(pdf());
    expect((await store.getDocument('12')).pageCount).toBe(7);
    server.docs.get(12)!.pageCount = 30;
    expect((await store.getDocument('12')).pageCount).toBe(30);
  });

  it('forget 하면 올린 File·센 쪽 수를 잊는다 — 다음 미리보기는 서버 원본(GET /documents/12/file, 밴드 GR3)', async () => {
    const { server, store, control } = setup();
    const file = pdf();
    await store.createDocument(file);
    control.forget();
    const opened = await store.openDocumentPdf('12');
    expect(opened).not.toBeNull();
    expect(opened).not.toBe(file);
    expect(keys(server).at(-1)).toBe('GET /documents/12/file');
    expect((await store.getDocument('12')).pageCount).toBeNull();
  });
});

describe('B — 문서 원본 미리보기(밴드 GR3 — 운영 관리자·다른 사용자·새로 고침, 리허설 sid:MARC-TICK-257)', () => {
  const served = () =>
    setup(fakeGreenwashServer({ documents: [fakeDocument(3)] }));
  const fileGets = (server: FakeGreenwashServer) =>
    keys(server).filter((key) => key === 'GET /documents/3/file').length;

  it('이 탭에서 올리지 않은 문서 → GET /documents/3/file(companyId 없음) → File(바이트·이름·application/pdf). 다시 열면 요청 없이 같은 File', async () => {
    const { server, store } = served();
    const file = await store.openDocumentPdf('3');
    expect(keys(server)).toEqual(['GET /documents/3/file']);
    expect(file).toBeInstanceOf(File);
    expect(file!.name).toBe('지어낸 보고서 3.pdf');
    expect(file!.type).toBe('application/pdf');
    expect(new Uint8Array(await file!.arrayBuffer())).toEqual(FAKE_PDF_BYTES);
    expect(server.calls[0]!.query.has('companyId')).toBe(false);
    expect(await store.openDocumentPdf('3')).toBe(file);
    expect(fileGets(server)).toBe(1);
  });

  it('이 탭에서 올린 문서는 서버에 묻지 않는다(올린 File 그대로)', async () => {
    const { server, store } = setup();
    const file = pdf();
    await store.createDocument(file);
    expect(await store.openDocumentPdf('12')).toBe(file);
    expect(keys(server)).not.toContain('GET /documents/12/file');
  });

  it('Content-Disposition 이 없으면 이름은 document-<id>.pdf', async () => {
    const { server, store } = served();
    server.override['GET /documents/3/file'] = () =>
      new Response(FAKE_PDF_BYTES.slice(), {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      });
    expect((await store.openDocumentPdf('3'))!.name).toBe('document-3.pdf');
  });

  it.each([
    ['없음 404', () => refusal(404, 'NOT_FOUND')],
    ['권한 403', () => refusal(403, 'FORBIDDEN')],
    ['올림 확인 전 409', () => refusal(409, 'NOT_UPLOADED')],
    ['서버 500', () => refusal(500, 'INTERNAL_SERVER_ERROR')],
    ['빈 본문 204', () => new Response(null, { status: 204 })],
    [
      '끊김',
      () => {
        throw new TypeError('지어낸 끊김');
      },
    ],
  ] as const)(
    '%s → null(화면의 「미리보기를 열 수 없어요」 갈래), 받지 못한 것은 두지 않는다(다음 열기에 다시 묻는다)',
    async (_name, answer) => {
      const { server, store } = served();
      server.override['GET /documents/3/file'] = answer;
      expect(await store.openDocumentPdf('3')).toBeNull();
      expect(await store.openDocumentPdf('3')).toBeNull();
      expect(fileGets(server)).toBe(2);
    },
  );

  it('서버 id 가 아니면 요청 없이 null', async () => {
    const { server, store } = served();
    expect(await store.openDocumentPdf('seed-1')).toBeNull();
    expect(server.calls).toEqual([]);
  });

  it('forget 하면 받은 원본도 잊는다(다음 열기에 다시 받는다)', async () => {
    const { server, store, control } = served();
    const first = await store.openDocumentPdf('3');
    control.forget();
    const second = await store.openDocumentPdf('3');
    expect(second).not.toBe(first);
    expect(fileGets(server)).toBe(2);
  });
});

describe('B — createRun·읽기 경로', () => {
  const uploadedServer = () =>
    fakeGreenwashServer({ documents: [fakeDocument(12)] });

  it('POST /runs 본문은 정확히 {module, documentId, options:{parts, extraTerms}} — 추가 단어가 없으면 키 없음', async () => {
    const { server, store } = setup(uploadedServer());
    const parts = { ceo: [1], company: [2, 3], climate: [3, 4, 5] };
    expect(
      await store.createRun('12', {
        parts,
        extraTerms: ['지어낸말'],
        reportYear: null,
        previousDocumentId: null,
      }),
    ).toEqual({ runId: '13' });
    await store.createRun('12', {
      parts,
      extraTerms: [],
      reportYear: null,
      previousDocumentId: null,
    });
    expect(keys(server)).toEqual(['POST /runs', 'POST /runs']);
    expect(server.calls[0]!.body).toEqual({
      module: 'greenwash',
      documentId: 12,
      launchKey: expect.stringMatching(IDEMPOTENCY_KEY_PATTERN),
      options: { parts, extraTerms: ['지어낸말'] },
    });
    expect(server.calls[1]!.body).toEqual({
      module: 'greenwash',
      documentId: 12,
      launchKey: expect.stringMatching(IDEMPOTENCY_KEY_PATTERN),
      options: { parts },
    });
  });

  it('수정본 대상이 있으면 요청 없이 거절(조용히 버리지 않는다). 보고연도는 거절하지 않고 PATCH 로 옮긴다(밴드 GW2R ③ — 아래 B 보고연도 시험)', async () => {
    const { server, store } = setup(uploadedServer());
    const parts = { ceo: [1], company: [], climate: [] };
    expect(
      await rejectionOf(
        store.createRun('12', {
          parts,
          extraTerms: [],
          reportYear: null,
          previousDocumentId: '3',
        }),
      ),
    ).toBe('rejected');
    expect(server.calls).toEqual([]);
  });

  it('올림 확인 전 문서 409 DOCUMENT_NOT_UPLOADED·옵션 400 INVALID_OPTIONS 는 rejected', async () => {
    const server = fakeGreenwashServer({
      documents: [fakeDocument(12, { status: 'awaiting_upload' })],
    });
    const { store } = setup(server);
    const request = {
      parts: { ceo: [1], company: [], climate: [] },
      extraTerms: [],
      reportYear: null,
      previousDocumentId: null,
    };
    expect(await rejectionOf(store.createRun('12', request))).toBe('rejected');
    server.override['POST /runs'] = () => refusal(400, 'INVALID_OPTIONS');
    expect(await rejectionOf(store.createRun('12', request))).toBe('rejected');
  });

  it('GET /documents/12 · GET /greenwash/terms/default 경로, 서버 쪽 수 → 이 탭의 셈 → null', async () => {
    const server = fakeGreenwashServer({
      documents: [
        fakeDocument(12, { pageCount: 30 }),
        fakeDocument(14, { pageCount: null }),
      ],
      defaultTerms: ['친환경', '녹색'],
    });
    const { store } = setup(server);
    expect(await store.getDocument('12')).toEqual({
      documentId: '12',
      fileName: '지어낸 보고서 12.pdf',
      pageCount: 30,
    });
    expect((await store.getDocument('14')).pageCount).toBeNull();
    expect(await store.listDefaultTerms()).toEqual(['친환경', '녹색']);
    expect(await rejectionOf(store.getDocument('99'))).toBe('not_found');
    expect(keys(server)).toEqual([
      'GET /documents/12',
      'GET /documents/14',
      'GET /greenwash/terms/default',
      'GET /documents/99',
    ]);
  });

  it('listDocuments 는 checks 의 문서(늦게 올린 것 먼저)', async () => {
    const { server, store } = setup(listedGreenwashServer());
    const documents = await store.listDocuments();
    expect(documents.map((doc) => doc.documentId)).toEqual([
      '3',
      '1',
      '2',
      '4',
    ]);
    expect(keys(server)).toEqual(['GET /greenwash/checks']);
  });

  it('checks 꼴 틀림·500·끊김 → 거절(목으로 메우지 않는다)', async () => {
    const { server, store } = setup(listedGreenwashServer());
    server.override['GET /greenwash/checks'] = [
      () => json(200, { schemaVersion: 'greenwash.checks@1', runs: [] }),
      () => refusal(500, 'INTERNAL_SERVER_ERROR'),
      () => {
        throw new TypeError('fetch failed');
      },
    ];
    for (let i = 0; i < 3; i++)
      expect(await rejectionOf(store.listCheckRows())).toBe('rejected');
  });
});

describe('B — subscribeRun 폴링(가짜 타이머)', () => {
  const pollServer = (status: 'queued' | 'processing' = 'processing') =>
    fakeGreenwashServer({
      documents: [fakeDocument(3)],
      runs: [
        fakeRun(12, 3, {
          status,
          steps: fakeSteps(2, { status: 'running', done: 1, total: 3 }),
        }),
      ],
    });
  const runCalls = (server: FakeGreenwashServer) =>
    server.count('GET /runs/12');
  /** 마이크로태스크를 비운다(응답이 돌아올 때까지). */
  const settle = () => vi.advanceTimersByTimeAsync(0);

  it('곧바로 한 번 → 응답 뒤 2초마다 → done 에서 멈춤', async () => {
    vi.useFakeTimers();
    const server = pollServer();
    const { store } = setup(server);
    const seen: RunSnapshot[] = [];
    store.subscribeRun('12', (run) => seen.push(run));
    await settle();
    expect(runCalls(server)).toBe(1);
    expect(seen.map((run) => run.progress.state)).toEqual(['running']);
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS - 1);
    expect(runCalls(server)).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(runCalls(server)).toBe(2);
    server.advance(12, { status: 'done' });
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS);
    expect(runCalls(server)).toBe(3);
    expect(seen.map((run) => run.progress.state)).toEqual([
      'running',
      'running',
      'done',
    ]);
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 5);
    expect(runCalls(server)).toBe(3);
    expect(RUN_POLL_MS).toBe(2000);
  });

  it('failed 에서도 멈춘다, errorCode 가 실린다', async () => {
    vi.useFakeTimers();
    const server = pollServer('queued');
    server.advance(12, {
      status: 'failed',
      steps: fakeSteps(0, { status: 'failed' }),
      errorCode: 'no_text_layer',
    });
    const { store } = setup(server);
    const seen: RunSnapshot[] = [];
    store.subscribeRun('12', (run) => seen.push(run));
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 3);
    expect(runCalls(server)).toBe(1);
    expect(seen.map((run) => run.errorCode)).toEqual(['no_text_layer']);
  });

  it('응답이 오기 전에는 다음 요청을 보내지 않는다(겹침 0)', async () => {
    vi.useFakeTimers();
    const server = pollServer();
    let release: (() => void) | null = null;
    server.override['GET /runs/12'] = [
      () =>
        new Promise<Response>((resolve) => {
          release = () => resolve(json(200, fakeRunOut()));
        }),
    ];
    const { store } = setup(server);
    const listener = vi.fn();
    store.subscribeRun('12', listener);
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 5);
    expect(runCalls(server)).toBe(1);
    expect(listener).not.toHaveBeenCalled();
    release!();
    await settle();
    expect(listener).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS);
    expect(runCalls(server)).toBe(2);
  });

  it('404 → onMissing 한 번, 그 뒤 요청 0', async () => {
    vi.useFakeTimers();
    const { server, store } = setup(fakeGreenwashServer());
    const onMissing = vi.fn();
    const listener = vi.fn();
    store.subscribeRun('12', listener, onMissing);
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 3);
    expect(onMissing).toHaveBeenCalledTimes(1);
    expect(listener).not.toHaveBeenCalled();
    expect(runCalls(server)).toBe(1);
  });

  it('처음 읽기 500 → onFailed 곧바로 한 번, 멈춤', async () => {
    vi.useFakeTimers();
    const server = pollServer();
    server.override['GET /runs/12'] = () =>
      refusal(500, 'INTERNAL_SERVER_ERROR');
    const { store } = setup(server);
    const onFailed = vi.fn();
    const onMissing = vi.fn();
    store.subscribeRun('12', vi.fn(), onMissing, onFailed);
    await settle();
    expect(onFailed).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 5);
    expect(onFailed).toHaveBeenCalledTimes(1);
    expect(onMissing).not.toHaveBeenCalled();
    expect(runCalls(server)).toBe(1);
  });

  it('받은 뒤 500,500,200,500 → onFailed 0(성공하면 셈 0), 받은 뒤 500 셋 → onFailed 한 번·멈춤', async () => {
    vi.useFakeTimers();
    const server = pollServer();
    const ok = () => json(200, fakeRunOut());
    const fail = () => refusal(500, 'INTERNAL_SERVER_ERROR');
    server.override['GET /runs/12'] = [
      ok,
      fail,
      fail,
      ok,
      fail,
      fail,
      fail,
      ok,
    ];
    const { store } = setup(server);
    const onFailed = vi.fn();
    const listener = vi.fn();
    store.subscribeRun('12', listener, undefined, onFailed);
    await settle();
    // ok, (500, 500, 200, 500) — 셈이 되돌아가 아직 실패 아님
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 4);
    expect(runCalls(server)).toBe(5);
    expect(listener).toHaveBeenCalledTimes(2);
    expect(onFailed).not.toHaveBeenCalled();
    // 500, 500 → 셋째 연속 실패에서 onFailed 한 번
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 2);
    expect(runCalls(server)).toBe(7);
    expect(onFailed).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 5);
    expect(runCalls(server)).toBe(7);
    expect(onFailed).toHaveBeenCalledTimes(1);
  });

  it('[R1] 해제 뒤에 온 실패 응답은 onFailed·onMissing 을 부르지 않는다', async () => {
    vi.useFakeTimers();
    const server = pollServer();
    const pending: (() => void)[] = [];
    server.override['GET /runs/12'] = [
      () =>
        new Promise<Response>((resolve) => {
          pending.push(() => resolve(refusal(500, 'INTERNAL_SERVER_ERROR')));
        }),
      () =>
        new Promise<Response>((resolve) => {
          pending.push(() => resolve(refusal(404, 'NOT_FOUND')));
        }),
    ];
    const { store } = setup(server);
    const onFailed = vi.fn();
    const onMissing = vi.fn();
    const first = store.subscribeRun('12', vi.fn(), onMissing, onFailed);
    const second = store.subscribeRun('12', vi.fn(), onMissing, onFailed);
    await settle();
    first();
    second();
    pending.forEach((release) => release());
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 3);
    expect(onFailed).not.toHaveBeenCalled();
    expect(onMissing).not.toHaveBeenCalled();
  });

  it('해제 뒤에 온 응답은 버리고, 다음 요청도 없다', async () => {
    vi.useFakeTimers();
    const server = pollServer();
    let release: (() => void) | null = null;
    server.override['GET /runs/12'] = [
      () =>
        new Promise<Response>((resolve) => {
          release = () => resolve(json(200, fakeRunOut()));
        }),
    ];
    const { store } = setup(server);
    const listener = vi.fn();
    const unsubscribe = store.subscribeRun('12', listener);
    await settle();
    unsubscribe();
    release!();
    await vi.advanceTimersByTimeAsync(RUN_POLL_MS * 3);
    expect(listener).not.toHaveBeenCalled();
    expect(runCalls(server)).toBe(1);
  });
});

/** 가짜 서버 밖에서 쓰는 RunOut 하나(processing, 실행 12). */
function fakeRunOut() {
  return {
    id: 12,
    documentId: 3,
    module: 'greenwash',
    flowId: 'greenwash.colab@E0',
    status: 'processing',
    steps: fakeSteps(2, { status: 'running', done: 1, total: 3 }),
    options: { parts: { ceo: [], company: [], climate: [1, 2, 3] } },
    errorCode: null,
    errorMessage: null,
    failedStep: null,
    files: [],
    resultShapes: ['greenwash.result@1'],
    resumedFromRunId: null,
    createdAt: '2026-10-18T09:00:00+09:00',
    startedAt: '2026-10-18T09:00:01+09:00',
    finishedAt: null,
  };
}

describe('B — rerun', () => {
  it('GET /runs/12 → 같은 documentId·options 로 POST /runs(resumeFromRunId 없음)', async () => {
    const options = {
      parts: { ceo: [1], company: [2], climate: [3] },
      extraTerms: ['지어낸말'],
    };
    const server = fakeGreenwashServer({
      documents: [fakeDocument(3)],
      runs: [
        fakeRun(12, 3, {
          status: 'failed',
          steps: fakeSteps(1, { status: 'failed' }),
          errorCode: 'step_error',
          options,
        }),
      ],
    });
    const { store } = setup(server);
    expect(await store.rerun('12')).toEqual({ runId: '13' });
    expect(keys(server)).toEqual(['GET /runs/12', 'POST /runs']);
    expect(server.calls[1]!.body).toEqual({
      module: 'greenwash',
      documentId: 3,
      launchKey: expect.stringMatching(IDEMPOTENCY_KEY_PATTERN),
      options,
    });
  });

  it('failed 가 아니면 POST 0 으로 거절', async () => {
    const server = fakeGreenwashServer({
      documents: [fakeDocument(3)],
      runs: [fakeRun(12, 3, { status: 'done', steps: fakeSteps(6) })],
    });
    const { store } = setup(server);
    expect(await rejectionOf(store.rerun('12'))).toBe('rejected');
    expect(keys(server)).toEqual(['GET /runs/12']);
  });
});

describe('B — 실행 만들기 끊김(밴드 GR1, sid:MARC-ISSUE-225)', () => {
  const request = {
    parts: { ceo: [1], company: [], climate: [] },
    extraTerms: [] as string[],
    reportYear: null,
    previousDocumentId: null,
  };
  const failedRun = () =>
    fakeGreenwashServer({
      documents: [fakeDocument(3), fakeDocument(12)],
      runs: [
        fakeRun(12, 3, {
          status: 'failed',
          steps: fakeSteps(1, { status: 'failed' }),
          errorCode: 'step_error',
        }),
      ],
    });

  it.each([
    [
      '끊김(network)',
      () => {
        throw new TypeError('지어낸 끊김');
      },
    ],
    [
      '꼴 밖 502(unexpected)',
      () => new Response('지어낸 게이트웨이', { status: 502 }),
    ],
  ] as const)(
    'POST /runs %s → unreachable(만들어졌는지 모른다). createRun·rerun 둘 다(POST 는 부름마다 한 번)',
    async (_name, answer) => {
      const server = failedRun();
      server.override['POST /runs'] = answer;
      const { store } = setup(server);
      expect(await rejectionOf(store.createRun('12', request))).toBe(
        'unreachable',
      );
      expect(await rejectionOf(store.rerun('12'))).toBe('unreachable');
      expect(server.count('POST /runs')).toBe(2);
    },
  );

  it('서버가 code 로 거절한 POST /runs(500 INTERNAL_SERVER_ERROR)는 rejected 그대로, 실행 읽기의 끊김도 rejected 그대로', async () => {
    const server = failedRun();
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL_SERVER_ERROR');
    const { store } = setup(server);
    expect(await rejectionOf(store.createRun('12', request))).toBe('rejected');
    server.override['GET /runs/12'] = () => {
      throw new TypeError('지어낸 끊김');
    };
    expect(await rejectionOf(store.rerun('12'))).toBe('rejected');
    expect(server.count('POST /runs')).toBe(1);
  });
});

describe('B — Idempotency-Key(밴드 GR2, sid:MARC-ISSUE-225 · 서버 IK1)', () => {
  const KEY_A = '0f8a3c2e-5b1d-4e7a-9c6f-2d4b8e1a7c3f';
  const KEY_B = '7c1e9a4b-2f6d-4a8c-b3e5-9d0f1a2b3c4d';
  const request = {
    parts: { ceo: [1], company: [], climate: [] },
    extraTerms: [] as string[],
    reportYear: null,
    previousDocumentId: null,
  };
  const failedRun = () =>
    fakeGreenwashServer({
      documents: [fakeDocument(3), fakeDocument(12)],
      runs: [
        fakeRun(12, 3, {
          status: 'failed',
          steps: fakeSteps(1, { status: 'failed' }),
          errorCode: 'step_error',
        }),
      ],
    });
  const keyOf = (server: FakeGreenwashServer, index: number) => {
    const posts = server.calls.filter((call) => call.path === '/runs');
    return posts[index]!.headers.get('Idempotency-Key');
  };

  it('createRun·rerun 의 POST /runs 에 받은 열쇠를 머리 그대로 싣는다(소문자 UUID), 다른 요청에는 싣지 않는다', async () => {
    const server = failedRun();
    const { store } = setup(server);
    await store.createRun('12', { ...request, reportYear: 2026 }, KEY_A);
    await store.rerun('12', KEY_B);
    expect(keys(server)).toEqual([
      'PATCH /documents/12',
      'POST /runs',
      'GET /runs/12',
      'POST /runs',
    ]);
    expect(keyOf(server, 0)).toBe(KEY_A);
    expect(keyOf(server, 1)).toBe(KEY_B);
    for (const call of server.calls.filter((c) => c.method !== 'POST'))
      expect(call.headers.has('Idempotency-Key')).toBe(false);
  });

  it('열쇠를 주지 않으면 머리가 없다(서버 머리도 선택)', async () => {
    const server = failedRun();
    const { store } = setup(server);
    await store.createRun('12', request);
    expect(server.calls[0]!.headers.has('Idempotency-Key')).toBe(false);
  });

  it('끊김 뒤 같은 열쇠로 다시 부르면 서버가 끊긴 요청으로 만든 실행을 돌려준다(실행 하나), 새 열쇠면 새 실행', async () => {
    const server = failedRun();
    // 첫 POST /runs 는 서버에 닿아 실행이 만들어진 뒤 답만 끊긴다
    let drop = true;
    const fetch = async (request: Request) => {
      const answer = await server.send(request);
      if (drop && request.method === 'POST' && request.url.endsWith('/runs')) {
        drop = false;
        throw new TypeError('지어낸 끊김');
      }
      return answer;
    };
    const { store } = setup(server, {
      api: createApi({ baseUrl: BASE, fetch }),
    });
    expect(await rejectionOf(store.createRun('12', request, KEY_A))).toBe(
      'unreachable',
    );
    expect(await store.createRun('12', request, KEY_A)).toEqual({
      runId: '13',
    });
    expect(await store.createRun('12', request, KEY_B)).toEqual({
      runId: '14',
    });
    expect([0, 1, 2].map((i) => keyOf(server, i))).toEqual([
      KEY_A,
      KEY_A,
      KEY_B,
    ]);
  });

  it('409 IDEMPOTENCY_KEY_REUSED(같은 열쇠·다른 본문)는 createRun 에서 key_reused(sid:MARC-ISSUE-312), rerun 은 rejected 그대로', async () => {
    const server = failedRun();
    const { store } = setup(server);
    await store.createRun('12', request, KEY_A);
    expect(
      await rejectionOf(
        store.createRun(
          '12',
          { ...request, parts: { ceo: [2], company: [], climate: [] } },
          KEY_A,
        ),
      ),
    ).toBe('key_reused');
    server.override['POST /runs'] = () =>
      refusal(409, 'IDEMPOTENCY_KEY_REUSED');
    expect(await rejectionOf(store.rerun('12', KEY_B))).toBe('rejected');
  });
});

describe('B — 본문 launchKey(밴드 GP6 · 서버 LK1 · AD4P H1)', () => {
  const KEY_A = '3d5f7a9c-1b2e-4c6d-8e0f-a1b2c3d4e5f6';
  const KEY_B = '9e8d7c6b-5a4f-4e3d-a2c1-b0f9e8d7c6b5';
  const request = {
    parts: { ceo: [1], company: [], climate: [] },
    extraTerms: [] as string[],
    reportYear: null,
    previousDocumentId: null,
  };
  const failedRun = () =>
    fakeGreenwashServer({
      documents: [fakeDocument(3), fakeDocument(12)],
      runs: [
        fakeRun(12, 3, {
          status: 'failed',
          steps: fakeSteps(1, { status: 'failed' }),
          errorCode: 'step_error',
        }),
      ],
    });
  const launchKeyOf = (server: FakeGreenwashServer, index: number) => {
    const posts = server.calls.filter((call) => call.path === '/runs');
    return (posts[index]!.body as { launchKey?: unknown }).launchKey;
  };

  it('ⓐ 점검 시작의 본문 launchKey 는 그 누름의 열쇠(Idempotency-Key) 그대로 — 소문자 UUID', async () => {
    const server = failedRun();
    const { store } = setup(server);
    await store.createRun('12', request, KEY_A);
    expect(launchKeyOf(server, 0)).toBe(KEY_A);
    expect(launchKeyOf(server, 0)).toMatch(IDEMPOTENCY_KEY_PATTERN);
  });

  it('ⓑ 끊김 뒤 같은 열쇠로 다시 보내면 launchKey 도 같다 — 본문이 같아 서버가 앞 실행을 돌려준다(409 아님)', async () => {
    const server = failedRun();
    let drop = true;
    const fetch = async (request: Request) => {
      const answer = await server.send(request);
      if (drop && request.method === 'POST' && request.url.endsWith('/runs')) {
        drop = false;
        throw new TypeError('지어낸 끊김');
      }
      return answer;
    };
    const { store } = setup(server, {
      api: createApi({ baseUrl: BASE, fetch }),
    });
    expect(await rejectionOf(store.createRun('12', request, KEY_A))).toBe(
      'unreachable',
    );
    expect(await store.createRun('12', request, KEY_A)).toEqual({
      runId: '13',
    });
    expect([launchKeyOf(server, 0), launchKeyOf(server, 1)]).toEqual([
      KEY_A,
      KEY_A,
    ]);
  });

  it('ⓒ 다시 하기는 그 누름의 새 열쇠 = 앞과 다른 launchKey', async () => {
    const server = failedRun();
    const { store } = setup(server);
    await store.createRun('12', request, KEY_A);
    await store.rerun('12', KEY_B);
    expect(launchKeyOf(server, 1)).toBe(KEY_B);
    expect(launchKeyOf(server, 1)).not.toBe(launchKeyOf(server, 0));
  });

  it('ⓓ 열쇠 없이 부르면 머리는 없고 launchKey 는 새로 지은 소문자 UUID(부를 때마다 다름)', async () => {
    const server = failedRun();
    const { store } = setup(server);
    await store.createRun('12', request);
    await store.rerun('12');
    const posts = server.calls.filter((call) => call.path === '/runs');
    for (const call of posts) {
      expect(call.headers.has('Idempotency-Key')).toBe(false);
      expect((call.body as { launchKey?: unknown }).launchKey).toMatch(
        IDEMPOTENCY_KEY_PATTERN,
      );
    }
    expect(launchKeyOf(server, 1)).not.toBe(launchKeyOf(server, 0));
  });

  it('흉내 서버도 꼴 틀린 launchKey 는 422 VALIDATION_ERROR(서버 LK1 무늬)', async () => {
    const server = failedRun();
    const answer = await server.send(
      new Request(`${BASE}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          module: 'greenwash',
          documentId: 12,
          launchKey: 'NOT-A-UUID',
          options: { parts: request.parts },
        }),
      }),
    );
    expect(answer.status).toBe(422);
  });
});

describe('B — 결과·검토와 409 갈래(Q12)', () => {
  const doneServer = () => {
    const server = fakeGreenwashServer({
      documents: [fakeDocument(3)],
      runs: [
        fakeRun(12, 3, { status: 'processing', steps: fakeSteps(2) }),
        fakeRun(14, 3, { dryRun: true }),
      ],
    });
    return server;
  };

  it('끝나지 않은 실행: getResult·getReview 의 409 RUN_NOT_DONE → not_found, putReview → run_not_done', async () => {
    const { server, store } = setup(doneServer());
    expect(await rejectionOf(store.getResult('12'))).toBe('not_found');
    expect(await rejectionOf(store.getReview('12'))).toBe('not_found');
    expect(await rejectionOf(store.putReview('12', { marks: [] }))).toBe(
      'run_not_done',
    );
    expect(keys(server)).toEqual([
      'GET /greenwash/runs/12/result',
      'GET /greenwash/runs/12/review',
      'PUT /greenwash/runs/12/review',
    ]);
  });

  it('dry-run 실행의 검토: 409 NO_REVIEW → no_review(읽기·저장)', async () => {
    const server = doneServer();
    server.advance(14, { status: 'done' });
    const { store } = setup(server);
    expect(await rejectionOf(store.getReview('14'))).toBe('no_review');
    expect(await rejectionOf(store.putReview('14', { marks: [] }))).toBe(
      'no_review',
    );
  });

  it('결과·검토 JSON 은 그대로, PUT 본문은 받은 그대로, 확정 뒤 PUT 409 REVIEW_LOCKED → review_locked, 400 INVALID_REVIEW → rejected', async () => {
    const server = doneServer();
    server.advance(12, { status: 'done' });
    const { store } = setup(server);
    expect(await store.getResult('12')).toEqual(server.runs.get(12)!.result);
    expect(await store.getReview('12')).toEqual({
      schemaVersion: 'greenwash.review@3',
      evidence: [],
      rejudges: [],
      runId: 12,
      state: 'pending',
      confirmedAt: null,
      confirmedBy: null,
      marks: [],
      edits: [],
    });
    const update = {
      marks: [
        { itemIndex: 0, decision: 'adopted' as const, excludeReason: null },
        {
          itemIndex: 2,
          decision: 'excluded' as const,
          excludeReason: 'not_environmental' as const,
        },
      ],
    };
    const saved = await store.putReview('12', update);
    expect(server.calls.at(-1)!.body).toEqual(update);
    expect(saved).toMatchObject({ state: 'in_review' });
    await store.putReview('12', { ...update, state: 'confirmed' });
    expect(server.calls.at(-1)!.body).toEqual({
      ...update,
      state: 'confirmed',
    });
    expect(await rejectionOf(store.putReview('12', { marks: [] }))).toBe(
      'review_locked',
    );
    server.override['PUT /greenwash/runs/12/review'] = () =>
      refusal(400, 'INVALID_REVIEW');
    expect(await rejectionOf(store.putReview('12', { marks: [] }))).toBe(
      'rejected',
    );
  });
});

describe('B — 보고연도 PATCH(밴드 GW2R ③ Q8)', () => {
  const parts = { ceo: [1], company: [], climate: [2] };
  const request = (reportYear: number | null) => ({
    parts,
    extraTerms: [] as string[],
    reportYear,
    previousDocumentId: null,
  });
  const uploaded = () => fakeGreenwashServer({ documents: [fakeDocument(12)] });

  it('연도 있음 → PATCH /documents/12 본문 정확히 {reportYear:2026} → 그 뒤 POST /runs(옵션에 연도 없음, companyId 없음)', async () => {
    const { server, store } = setup(uploaded());
    expect(await store.createRun('12', request(2026))).toEqual({
      runId: '13',
    });
    expect(keys(server)).toEqual(['PATCH /documents/12', 'POST /runs']);
    expect(server.calls[0]!.body).toEqual({ reportYear: 2026 });
    expect(server.calls[1]!.body).toEqual({
      module: 'greenwash',
      documentId: 12,
      launchKey: expect.stringMatching(IDEMPOTENCY_KEY_PATTERN),
      options: { parts },
    });
    expect(JSON.stringify(server.calls.map((call) => call.body))).not.toContain(
      'companyId',
    );
    expect(server.docs.get(12)!.reportYear).toBe(2026);
  });

  it('연도 null → PATCH 0, POST /runs 하나', async () => {
    const { server, store } = setup(uploaded());
    await store.createRun('12', request(null));
    expect(keys(server)).toEqual(['POST /runs']);
  });

  it.each([
    ['422', () => refusal(422, 'VALIDATION_ERROR')],
    ['409 NOT_UPLOADED', () => refusal(409, 'NOT_UPLOADED')],
    ['500', () => refusal(500, 'INTERNAL_SERVER_ERROR')],
    [
      '끊김',
      () => {
        throw new TypeError('지어낸 끊김');
      },
    ],
    [
      '답의 연도가 다름',
      () => json(200, { ...fakeDocOut(12), reportYear: 2025 }),
    ],
    [
      '답의 id 가 다름',
      () => json(200, { ...fakeDocOut(13), reportYear: 2026 }),
    ],
  ] as const)('PATCH %s → 거절, POST /runs 0', async (_name, answer) => {
    const server = uploaded();
    server.override['PATCH /documents/12'] = answer;
    const { store } = setup(server);
    expect(await rejectionOf(store.createRun('12', request(2026)))).toBe(
      'rejected',
    );
    expect(server.count('POST /runs')).toBe(0);
  });

  it('가짜 서버 규칙: 1900~2100 밖이면 422(거절, POST 0)', async () => {
    const { server, store } = setup(uploaded());
    expect(await rejectionOf(store.createRun('12', request(2101)))).toBe(
      'rejected',
    );
    expect(keys(server)).toEqual(['PATCH /documents/12']);
  });
});

/** DocumentOut 꼴(지어낸) — PATCH 답 갈음에 쓴다. */
function fakeDocOut(id: number) {
  return {
    id,
    fileName: '지어낸.pdf',
    sizeBytes: 1,
    status: 'uploaded',
    pageCount: 10,
    hasText: true,
    reportYear: null,
    previousDocumentId: null,
    etag: '"x"',
    createdAt: '2026-10-18T09:00:00+09:00',
    uploadedAt: '2026-10-18T09:00:05+09:00',
  };
}

describe('B — 엑셀 report GET(밴드 GW2R ③ Q9)', () => {
  const doneServer = (options = {}) => {
    const server = fakeGreenwashServer({
      documents: [fakeDocument(3)],
      runs: [
        fakeRun(12, 3, { status: 'processing', steps: fakeSteps(2) }),
        fakeRun(14, 3, {
          status: 'processing',
          steps: fakeSteps(2),
          dryRun: true,
        }),
        fakeRun(15, 3, { status: 'processing', steps: fakeSteps(2) }),
      ],
      ...options,
    });
    server.advance(12, { status: 'done' });
    server.advance(14, { status: 'done' });
    return server;
  };

  it('확정 전 결과 → GET /greenwash/runs/12/report 쿼리 없음, Blob(바이트 그대로)·이름은 Content-Disposition 의 filename*', async () => {
    const { server, store } = setup(doneServer());
    const report = await store.getReport('12', false);
    expect(keys(server)).toEqual(['GET /greenwash/runs/12/report']);
    expect(server.calls[0]!.query.toString()).toBe('');
    expect(new Uint8Array(await report.blob.arrayBuffer())).toEqual(
      new Uint8Array([80, 75, 3, 4, 1, 2, 3]),
    );
    expect(report.fileName).toBe('지어낸 보고서 12.xlsx');
  });

  it('확정본 → ?confirmed=true(쿼리 그것 하나), 확정 전 실행이면 409 NOT_CONFIRMED → 거절', async () => {
    const server = doneServer();
    const { store } = setup(server);
    expect(await rejectionOf(store.getReport('12', true))).toBe('rejected');
    expect(server.calls[0]!.query.toString()).toBe('confirmed=true');
    server.runs.get(12)!.review = {
      state: 'confirmed',
      marks: [],
      confirmedAt: '2026-10-19T10:00:00+09:00',
      confirmedBy: FAKE_CONFIRMER,
    };
    const report = await store.getReport('12', true);
    expect(report.fileName).toBe('지어낸 보고서 12 확정본.xlsx');
    expect(server.calls.at(-1)!.query.toString()).toBe('confirmed=true');
  });

  it('Content-Disposition 이 없으면 greenwash-<runId>.xlsx', async () => {
    const { store } = setup(doneServer({ reportDisposition: null }));
    expect((await store.getReport('12', false)).fileName).toBe(
      'greenwash-12.xlsx',
    );
  });

  it('끝나지 않음 409 RUN_NOT_DONE · dry-run 409 NO_REPORT · 500 · 없음 404 → 거절(Blob 없음)', async () => {
    const server = doneServer();
    const { store } = setup(server);
    expect(await rejectionOf(store.getReport('15', false))).toBe(
      'run_not_done',
    );
    expect(await rejectionOf(store.getReport('14', false))).toBe('rejected');
    expect(await rejectionOf(store.getReport('99', false))).toBe('not_found');
    server.override['GET /greenwash/runs/12/report'] = () =>
      refusal(500, 'INTERNAL_SERVER_ERROR');
    expect(await rejectionOf(store.getReport('12', false))).toBe('rejected');
    expect(server.calls.every((call) => !call.query.has('companyId'))).toBe(
      true,
    );
  });

  it('답이 파일이 아니면(빈 본문 204) 거절', async () => {
    const server = doneServer();
    server.override['GET /greenwash/runs/12/report'] = () =>
      new Response(null, { status: 204 });
    const { store } = setup(server);
    expect(await rejectionOf(store.getReport('12', false))).toBe('rejected');
  });
});
