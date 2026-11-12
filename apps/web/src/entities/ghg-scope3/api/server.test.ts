// 온실가스 Scope 3 실어댑터·가짜 서버 시험(밴드 S3W1 ① — 발주서 §3 의 1·3). 실어댑터는 진짜 createApi 로 가짜 서버에 잇는다.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import {
  ROW_KINDS,
  RUN_STEP_NAMES,
  RUN_STEP_STATUSES,
  SCOPE3_FLOW_ID,
  SCOPE3_MODULE,
} from '../model/index.ts';
import type { ResultRow, ResultSheet } from '../model/index.ts';
import type { RowFactorInput } from '../model/index.ts';
import {
  ORIGINAL_FILE_NAME,
  TEMPLATE_FILE_NAME,
  createScope3Port,
  fileNameFromDisposition,
  resultOf,
  runOf,
} from './server.ts';
import {
  FAKE_C3_NOTE,
  FAKE_C12_CODE,
  FAKE_C12_NAME,
  FAKE_EDITED_CO2E,
  FAKE_ERROR_CODES,
  FAKE_ERROR_MESSAGE,
  FAKE_FUEL,
  FAKE_GROUP_A,
  FAKE_MODE,
  FAKE_ORIGINAL_BYTES,
  FAKE_REJECT_DETAIL,
  FAKE_SHEET_ERROR,
  FAKE_SOURCE_TEXT,
  FAKE_TEMPLATE_BYTES,
  FAKE_TEMPLATE_NAME,
  FAKE_TREATMENT,
  XLSX_MEDIA_TYPE,
  activityRow,
  attachmentOf,
  c12Row,
  decimalSum,
  detailSheetName,
  energyRow,
  estimateGroupSteps,
  failedSheet,
  fakeAllShapesResult,
  fakeDetailResult,
  fakeDoneResult,
  fakeInput,
  fakeRejectedResult,
  fakeRowFactor,
  fakeS3Q1Result,
  fakeScope3Server,
  fakeTreatments,
  fifteenKeyInput,
  json,
  noBiogenicSplit,
  originalMediaType,
  portOf,
  processedSheet,
  purchaseRow,
  refusal,
  ruleGroupSteps,
  unreachable,
  withoutInput,
} from './testing.ts';
import type { FakeScope3Server, FakeScope3ServerOptions } from './testing.ts';

const fixedKeys = () => {
  let n = 0;
  return () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
};
const launchKeys = () => {
  let n = 0;
  return () => `11111111-0000-4000-8000-${String(++n).padStart(12, '0')}`;
};
const xlsx = (size = 3) =>
  new File([new Uint8Array(size).fill(7)], '지어낸 입력.xlsx');

function setup(options: FakeScope3ServerOptions = {}) {
  const server = fakeScope3Server(options);
  const port = portOf(server, {
    newKey: fixedKeys(),
    newLaunchKey: launchKeys(),
  });
  return { server, port };
}

describe('upload — POST /documents → PUT → confirm', () => {
  it('파일 이름·크기·보고연도를 싣고 바이트를 올리고 확인한다', async () => {
    const { server, port } = setup();
    const outcome = await port.upload(xlsx(5), 2025);
    expect(outcome).toEqual({ kind: 'ok', value: { documentId: '101' } });
    expect(server.bodies('POST /documents')).toEqual([
      { fileName: '지어낸 입력.xlsx', sizeBytes: 5, reportYear: 2025 },
    ]);
    expect(server.uploaded(101)).toEqual(new Uint8Array(5).fill(7));
    expect(server.count('POST /documents/101/confirm')).toBe(1);
  });

  it('413 upload_too_large(소문자) → rejected UPLOAD_TOO_LARGE, 올리지 않음', async () => {
    const { server, port } = setup({ uploadLimit: 4 });
    expect(await port.upload(xlsx(5), 2025)).toEqual({
      kind: 'rejected',
      code: 'UPLOAD_TOO_LARGE',
      fields: [],
    });
    expect(server.calls.map((c) => c.method)).toEqual(['POST']);
  });

  it('올리기(PUT) 실패 → failed, confirm 0', async () => {
    const { server } = setup();
    const api = createApi({
      baseUrl: 'http://test.local/api',
      fetch: server.send,
    });
    const port = createScope3Port({
      api,
      sendUpload: () => Promise.reject(new Error('upload failed 500')),
    });
    expect(await port.upload(xlsx(), 2025)).toEqual({ kind: 'failed' });
    expect(server.count('POST /documents/101/confirm')).toBe(0);
  });

  it('회사 거절 셋', async () => {
    for (const company of ['ambiguous', 'inactive', 'not_found'] as const) {
      const { port } = setup({ company });
      expect(await port.upload(xlsx(), 2025)).toEqual({
        kind: 'refused',
        company,
      });
    }
  });
});

describe('start — POST /runs', () => {
  it('module·flowId(늘)·documentId·launchKey·options{reportYear} 만 싣고 Idempotency-Key 머리', async () => {
    const { server, port } = setup();
    await port.upload(xlsx(), 2024);
    const outcome = await port.start('101', 2024);
    expect(outcome).toEqual({ kind: 'ok', value: { runId: '501' } });
    const [body] = server.bodies('POST /runs');
    expect(body).toEqual({
      module: SCOPE3_MODULE,
      flowId: SCOPE3_FLOW_ID,
      documentId: 101,
      launchKey: '11111111-0000-4000-8000-000000000001',
      options: { reportYear: 2024 },
    });
    expect(SCOPE3_FLOW_ID).toBe('scope3.colab@157');
    const call = server.calls.find((c) => c.path === '/runs')!;
    expect(call.headers.get('Idempotency-Key')).toBe(
      '00000000-0000-4000-8000-000000000001',
    );
  });

  it('고른 카테고리는 싣지 않는다 — 본문 열쇠 다섯, options 열쇠 하나', async () => {
    const { server, port } = setup();
    await port.upload(xlsx(), 2024);
    await port.start('101', 2024);
    const body = server.bodies('POST /runs')[0] as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(
      ['documentId', 'flowId', 'launchKey', 'module', 'options'].sort(),
    );
    expect(Object.keys(body.options as object)).toEqual(['reportYear']);
    expect(JSON.stringify(body)).not.toMatch(/C[0-9]+|categor/i);
  });

  it('답 없음이면 같은 열쇠·같은 본문으로 한 번 더', async () => {
    const { server, port } = setup();
    await port.upload(xlsx(), 2024);
    server.override['POST /runs'] = [unreachable];
    expect(await port.start('101', 2024)).toEqual({
      kind: 'ok',
      value: { runId: '501' },
    });
    const posts = server.calls.filter((c) => c.path === '/runs');
    expect(posts).toHaveLength(2);
    expect(posts[0]!.headers.get('Idempotency-Key')).toBe(
      posts[1]!.headers.get('Idempotency-Key'),
    );
    expect(posts[0]!.body).toEqual(posts[1]!.body);
  });

  it('글자 id 가 아니면 요청 없이 failed', async () => {
    const { server, port } = setup();
    expect(await port.start('x1', 2024)).toEqual({ kind: 'failed' });
    expect(server.calls).toHaveLength(0);
  });

  it.each([
    [refusal(422, 'FLOW_NOT_RUNNABLE'), 'FLOW_NOT_RUNNABLE'],
    [refusal(400, 'INVALID_OPTIONS'), 'INVALID_OPTIONS'],
    [refusal(409, 'DOCUMENT_NOT_UPLOADED'), 'DOCUMENT_NOT_UPLOADED'],
    [refusal(403, 'FORBIDDEN'), 'FORBIDDEN'],
    [refusal(413, 'upload_too_large'), 'UPLOAD_TOO_LARGE'],
    [refusal(422, 'UNKNOWN_FLOW'), null],
    [refusal(409, 'AI_SETTING_UNUSABLE'), null],
    [refusal(422, 'VALIDATION_ERROR'), 'VALIDATION_ERROR'],
  ] as const)('거절 %# → code %s', async (response, code) => {
    const { server, port } = setup();
    server.override['POST /runs'] = () => response.clone();
    expect(await port.start('101', 2024)).toEqual({
      kind: 'rejected',
      code,
      fields: [],
    });
  });

  it('회사 거절 셋 · 꼴 틀린 답 failed', async () => {
    for (const company of ['ambiguous', 'inactive', 'not_found'] as const) {
      const { port } = setup({ company });
      expect(await port.start('101', 2024)).toEqual({
        kind: 'refused',
        company,
      });
    }
    const { server, port } = setup();
    server.override['POST /runs'] = () => json(201, { id: 'x' });
    expect(await port.start('101', 2024)).toEqual({ kind: 'failed' });
  });
});

describe('template — 양식 내려받기(S3K1 경로)', () => {
  it('가짜 포트는 S3K1 계약대로 바이트와 filename* 이름', async () => {
    const { server, port } = setup();
    const outcome = await port.template();
    if (outcome.kind !== 'ok') throw new Error(outcome.kind);
    expect(new Uint8Array(await outcome.value.blob.arrayBuffer())).toEqual(
      FAKE_TEMPLATE_BYTES,
    );
    expect(outcome.value.fileName).toBe(FAKE_TEMPLATE_NAME);
    expect(server.count('GET /inventory/scope3/template')).toBe(1);
  });

  it('BASE 판은 404 → failed', async () => {
    const { port } = setup({ server: 'base' });
    expect(await port.template()).toEqual({ kind: 'failed' });
  });

  it('실어댑터가 GET /inventory/scope3/template 을 blob 으로 받는다(Q2 — 가짜의 덮어쓰기 없음)', async () => {
    const server = fakeScope3Server();
    const api = createApi({
      baseUrl: 'http://test.local/api',
      fetch: server.send,
    });
    const port = createScope3Port({ api, sendUpload: server.sendUpload });
    const outcome = await port.template();
    if (outcome.kind !== 'ok') throw new Error(outcome.kind);
    expect(outcome.value.fileName).toBe(FAKE_TEMPLATE_NAME);
    expect(server.calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      'GET /inventory/scope3/template',
    ]);
  });

  it('Content-Disposition 이 없으면 TEMPLATE_FILE_NAME · 끊김은 failed · 회사 거절은 refused', async () => {
    const { server, port } = setup();
    server.override['GET /inventory/scope3/template'] = [
      () => new Response(FAKE_TEMPLATE_BYTES, { status: 200 }),
      unreachable,
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
    ];
    const first = await port.template();
    expect(first.kind === 'ok' && first.value.fileName).toBe(
      TEMPLATE_FILE_NAME,
    );
    expect(await port.template()).toEqual({ kind: 'failed' });
    expect(await port.template()).toEqual({
      kind: 'refused',
      company: 'ambiguous',
    });
  });

  it('fileNameFromDisposition', () => {
    expect(fileNameFromDisposition(null)).toBeNull();
    expect(
      fileNameFromDisposition(`attachment; filename*=UTF-8''a%20b.xlsx`),
    ).toBe('a b.xlsx');
    expect(fileNameFromDisposition('attachment; filename="../x.xlsx"')).toBe(
      '..x.xlsx',
    );
  });
});

describe('run · latest — 그 해 마지막 실행', () => {
  it('run — GET /runs/{id} 의 칸', async () => {
    const { port } = setup({
      runs: [{ id: 7, status: 'processing', reportYear: 2025, documentId: 3 }],
    });
    expect(await port.run('7')).toEqual({
      kind: 'ok',
      value: expect.objectContaining({
        id: '7',
        status: 'processing',
        documentId: '3',
        flowId: SCOPE3_FLOW_ID,
        reportYear: 2025,
      }),
    });
  });

  it('run — 다른 모듈의 실행·꼴 틀림은 failed', async () => {
    const { port } = setup({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          module: 'inventory.scope12',
        },
      ],
    });
    expect(await port.run('7')).toEqual({ kind: 'failed' });
  });

  /** 실행 읽기 경로만(GET /runs 목록은 따로 센다). */
  const runReads = (server: FakeScope3Server) =>
    server.calls
      .filter((c) => c.method === 'GET' && /^\/runs\/\d+$/.test(c.path))
      .map((c) => c.path);
  const listReads = (server: FakeScope3Server) =>
    server.calls.filter((c) => c.method === 'GET' && c.path === '/runs').length;

  it('latest — 그 해 상태의 latest 하나를 읽는다(목록 0 · 실행 1 — GX5)', async () => {
    const { server, port } = setup({
      runs: [
        { id: 3, status: 'failed', reportYear: 2024, documentId: 1 },
        { id: 5, status: 'done', reportYear: 2025, documentId: 1 },
        { id: 9, status: 'processing', reportYear: 2023, documentId: 1 },
      ],
    });
    expect(await port.latest(2024)).toEqual({
      kind: 'ok',
      value: expect.objectContaining({ id: '3', status: 'failed' }),
    });
    expect(server.count('GET /inventory/scope3/years/2024')).toBe(1);
    expect(listReads(server)).toBe(0);
    expect(runReads(server)).toEqual(['/runs/3']);
  });

  it('latest — 다른 해 실행 25건 뒤로 밀린 그 해 실행도 찾는다(목록 20건 밖)', async () => {
    const { server, port } = setup({
      runs: [
        { id: 1, status: 'processing', reportYear: 2024, documentId: 1 },
        ...Array.from({ length: 25 }, (_, i) => ({
          id: i + 2,
          status: 'done' as const,
          reportYear: 2025,
          documentId: 1,
        })),
      ],
    });
    expect(await port.latest(2024)).toEqual({
      kind: 'ok',
      value: expect.objectContaining({ id: '1', status: 'processing' }),
    });
    expect(listReads(server)).toBe(0);
    expect(runReads(server)).toEqual(['/runs/1']);
  });

  it('latest — 다른 흐름(llm-first) 실행은 그 해 상태가 고르지 않는다 · 그것뿐이면 none(S3W2a ⑤)', async () => {
    const { port } = setup({
      runs: [
        { id: 5, status: 'failed', reportYear: 2025, documentId: 1 },
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          documentId: 1,
          flowId: 'scope3.llm-first@1',
          result: null,
        },
      ],
    });
    expect(await port.latest(2025)).toEqual({
      kind: 'ok',
      value: expect.objectContaining({ id: '5', flowId: SCOPE3_FLOW_ID }),
    });
    const only = setup({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          flowId: 'scope3.llm-first@1',
          result: null,
        },
      ],
    });
    expect(await only.port.latest(2025)).toEqual({ kind: 'none' });
  });

  it('latest — 그 해 latest 가 null 이면 none(실행 읽기 0 · 읽기 실패와 다르다)', async () => {
    const { server, port } = setup({
      runs: [{ id: 5, status: 'done', reportYear: 2025, documentId: 1 }],
    });
    expect(await port.latest(2024)).toEqual({ kind: 'none' });
    expect(runReads(server)).toEqual([]);
    expect(listReads(server)).toBe(0);
    const empty = setup();
    expect(await empty.port.latest(2024)).toEqual({ kind: 'none' });
  });

  it('latest — 그 해 상태 404·500·끊김·꼴 틀림, 실행 읽기 실패, 해·흐름 어긋남은 failed · 회사 거절은 refused', async () => {
    const year = 'GET /inventory/scope3/years/2024';
    const latestBody = (latest: unknown) =>
      json(200, {
        year: 2024,
        baseRunId: null,
        latest,
        categories: [],
        editedRowsUnlocked: 0,
      });
    for (const answer of [
      () => refusal(404, 'NOT_FOUND'),
      () => refusal(500, 'INTERNAL'),
      unreachable,
      () => json(200, { year: 2024 }),
      () => latestBody({ runId: 'x', status: 'done' }),
      () => latestBody({ runId: '5', status: 'done' }),
    ]) {
      const { server, port } = setup({
        runs: [{ id: 5, status: 'done', reportYear: 2025, documentId: 1 }],
      });
      server.override[year] = answer;
      expect(await port.latest(2024)).toEqual({ kind: 'failed' });
    }
    // 해는 같고 흐름이 다른 실행(llm-first — 결과 경로 404, S3W2a ⑤)을 그 해 상태가 가리키면 failed.
    const flow = setup({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2024,
          documentId: 1,
          flowId: 'scope3.llm-first@1',
          result: null,
        },
      ],
    });
    flow.server.override[year] = () =>
      latestBody({ runId: '9', status: 'done' });
    expect(await flow.port.latest(2024)).toEqual({ kind: 'failed' });
    const c = setup({
      runs: [{ id: 5, status: 'done', reportYear: 2024, documentId: 1 }],
    });
    c.server.override['GET /runs/5'] = () => refusal(500, 'INTERNAL');
    expect(await c.port.latest(2024)).toEqual({ kind: 'failed' });
    const d = setup({ company: 'inactive' });
    expect(await d.port.latest(2024)).toEqual({
      kind: 'refused',
      company: 'inactive',
    });
  });
});

describe('runOf — steps(밴드 S3W3d ③)', () => {
  const body = (steps: unknown) => ({
    id: 1,
    module: SCOPE3_MODULE,
    options: { reportYear: 2025 },
    status: 'processing',
    documentId: 1,
    flowId: SCOPE3_FLOW_ID,
    createdAt: '2026-01-01T00:00:00Z',
    finishedAt: null,
    errorCode: null,
    steps,
  });
  const step = (name: string, status = 'done') => ({
    step: name,
    status,
    done: null,
    total: null,
  });

  it('이름·상태만 싣는다(total·done 은 진행률이 아니다) · null 칸도 받는다', () => {
    expect(
      runOf(body([step('c1'), { ...step('c2', 'running'), done: 3, total: 3 }]))
        ?.steps,
    ).toEqual([
      { step: 'c1', status: 'done' },
      { step: 'c2', status: 'running' },
    ]);
  });

  it('꼴이 틀린 낱개·모르는 단계·모르는 상태만 버리고 실행은 산다', () => {
    const run = runOf(
      body([
        null,
        'c1',
        { step: 3, status: 'done' },
        step('c10'),
        step('지어낸 단계'),
        step('c3', '지어낸 상태'),
        step('assemble', 'pending'),
      ]),
    );
    expect(run?.status).toBe('processing');
    expect(run?.steps).toEqual([{ step: 'assemble', status: 'pending' }]);
  });

  it('빈 steps · 칸 없음 · 배열이 아님이면 빈 목록(실행은 산다)', () => {
    expect(runOf(body([]))?.steps).toEqual([]);
    expect(runOf(body(undefined))?.steps).toEqual([]);
    expect(runOf(body({ c1: 'done' }))?.steps).toEqual([]);
  });
});

describe('retry — 다시 계산 = 같은 문서·연도로 새 POST(resumeFromRunId 0)', () => {
  it('실패한 실행의 documentId·flowId·options 그대로, 새 열쇠·새 launchKey, 앞 실행은 그대로', async () => {
    const { server, port } = setup({
      runs: [{ id: 7, status: 'failed', reportYear: 2024, documentId: 1 }],
    });
    const outcome = await port.retry('7');
    expect(outcome).toEqual({ kind: 'ok', value: { runId: '501' } });
    const [body] = server.bodies('POST /runs') as Record<string, unknown>[];
    expect(body).toEqual({
      module: SCOPE3_MODULE,
      flowId: SCOPE3_FLOW_ID,
      documentId: 1,
      launchKey: '11111111-0000-4000-8000-000000000001',
      options: { reportYear: 2024 },
    });
    expect(body).not.toHaveProperty('resumeFromRunId');
    expect(server.runs().map((r) => [r.id, r.status])).toEqual([
      [7, 'failed'],
      [501, 'queued'],
    ]);
  });

  it('앞 실행이 다른 흐름이어도 flowId 는 늘 scope3.colab@157', async () => {
    const { server, port } = setup({
      runs: [
        {
          id: 7,
          status: 'failed',
          reportYear: 2024,
          documentId: 1,
          flowId: 'scope3.llm-first@1',
        },
      ],
    });
    await port.retry('7');
    expect(server.bodies('POST /runs')).toEqual([
      expect.objectContaining({ flowId: SCOPE3_FLOW_ID }),
    ]);
  });

  it('두 번 다시 계산하면 열쇠가 서로 다르다', async () => {
    const { server, port } = setup({
      runs: [{ id: 7, status: 'failed', reportYear: 2024, documentId: 1 }],
    });
    await port.retry('7');
    await port.retry('7');
    const keys = server.calls
      .filter((c) => c.path === '/runs' && c.method === 'POST')
      .map((c) => c.headers.get('Idempotency-Key'));
    expect(new Set(keys).size).toBe(2);
  });

  it('실패가 아닌 실행은 보내지 않고 rejected null · 읽기 실패 failed', async () => {
    const { server, port } = setup({
      runs: [{ id: 7, status: 'done', reportYear: 2024, documentId: 1 }],
    });
    expect(await port.retry('7')).toEqual({
      kind: 'rejected',
      code: null,
      fields: [],
    });
    expect(server.count('POST /runs')).toBe(0);
    expect(await port.retry('99')).toEqual({ kind: 'failed' });
  });
});

describe('가짜 서버 — S3K1 판·BASE 판', () => {
  it('S3K1 판: 진행 대본 queued → processing → done', async () => {
    const { port } = setup();
    await port.upload(xlsx(), 2024);
    await port.start('101', 2024);
    const seen: string[] = [];
    for (let i = 0; i < 4; i += 1) {
      const read = await port.run('501');
      if (read.kind === 'ok') seen.push(read.value.status);
    }
    expect(seen).toEqual(['queued', 'processing', 'done', 'done']);
  });

  it('S3K1 판: reportYear 빠짐·글자·1990 앞·올해 뒤 → 400 INVALID_OPTIONS', async () => {
    for (const options of [
      {},
      { reportYear: '2024' },
      { reportYear: 1989 },
      { reportYear: 2027 },
      { reportYear: true },
    ]) {
      const server = fakeScope3Server({ thisYear: 2026 });
      const port = portOf(server);
      await port.upload(xlsx(), 2024);
      const response = await server.send(
        new Request('http://test.local/api/runs', {
          method: 'POST',
          body: JSON.stringify({
            module: SCOPE3_MODULE,
            flowId: SCOPE3_FLOW_ID,
            documentId: 101,
            options,
          }),
        }),
      );
      expect(response.status).toBe(400);
    }
  });

  it('S3K1 판: resumeFromRunId 를 실으면 422(화면은 쓰지 않는다) · 올리지 않은 문서 409', async () => {
    const server = fakeScope3Server();
    const post = (body: unknown) =>
      server.send(
        new Request('http://test.local/api/runs', {
          method: 'POST',
          body: JSON.stringify(body),
        }),
      );
    const base = {
      module: SCOPE3_MODULE,
      flowId: SCOPE3_FLOW_ID,
      options: { reportYear: 2024 },
    };
    await server.send(
      new Request('http://test.local/api/documents', {
        method: 'POST',
        body: JSON.stringify({ fileName: 'a.xlsx', sizeBytes: 1 }),
      }),
    );
    expect((await post({ ...base, documentId: 101 })).status).toBe(409);
    expect(
      (await post({ ...base, documentId: 101, resumeFromRunId: 3 })).status,
    ).toBe(422);
  });

  it('S3K1 판: 운영 관리자 실행 열림', async () => {
    const { port } = setup({ operator: true });
    await port.upload(xlsx(), 2024);
    expect((await port.start('101', 2024)).kind).toBe('ok');
  });

  it('BASE 판: 422 FLOW_NOT_RUNNABLE(문서는 남음) · 운영 관리자 403 FORBIDDEN', async () => {
    const a = setup({ server: 'base' });
    expect(await a.port.upload(xlsx(), 2024)).toEqual({
      kind: 'ok',
      value: { documentId: '101' },
    });
    expect(await a.port.start('101', 2024)).toEqual({
      kind: 'rejected',
      code: 'FLOW_NOT_RUNNABLE',
      fields: [],
    });
    expect(a.server.uploaded(101)).not.toBeNull();
    const b = setup({ server: 'base', operator: true });
    await b.port.upload(xlsx(), 2024);
    expect(await b.port.start('101', 2024)).toEqual({
      kind: 'rejected',
      code: 'FORBIDDEN',
      fields: [],
    });
  });

  it('목록 요약에 연도·options 칸이 없다(서버 그대로)', async () => {
    const server = fakeScope3Server({
      runs: [{ id: 5, status: 'done', reportYear: 2025, documentId: 1 }],
    });
    const response = await server.send(
      new Request('http://test.local/api/runs?module=inventory.scope3'),
    );
    const page = (await response.json()) as { results: object[] };
    expect(Object.keys(page.results[0]!)).not.toContain('options');
    expect(JSON.stringify(page)).not.toContain('2025');
  });
});

describe('result — GET /inventory/scope3/runs/{id}/result', () => {
  const doneRun = { id: 7, status: 'done' as const, reportYear: 2025 };

  it('done → 시트·줄(co2e·생물기원 글자 그대로)·llmCalls · 시트 error 는 싣지 않음', async () => {
    const { server, port } = setup({
      runs: [{ ...doneRun, result: fakeAllShapesResult() }],
    });
    const outcome = await port.result('7');
    if (outcome.kind !== 'ok' || outcome.value.status !== 'done')
      throw new Error('done 아님');
    expect(server.count('GET /inventory/scope3/runs/7/result')).toBe(1);
    const sheets = outcome.value.sheets;
    expect(sheets.map((s) => s.status)).toEqual([
      'processed',
      'processed',
      'processed',
      'processed',
      'processed',
      'other',
      'other',
      'empty',
      'failed',
    ]);
    expect(sheets[0]).toEqual({
      status: 'processed',
      sheet: 's1',
      category: 'Category1',
      rows: [
        {
          rowId: 'p1',
          co2e: '1e-05',
          biogenic: null,
          origin: 'ai',
          formula: '지어낸 식',
          detail: {
            shape: 'purchase',
            kind: 'purchase',
            groupName: '지어낸 묶음',
            groupOrigin: 'ai',
            spendKrw: '100',
            factor: {
              title: '지어낸 항목',
              value: '0.1',
              unit: 'kgCO2e/KRW',
              source: 'db_keyword',
            },
            recommendations: [
              { title: '지어낸 추천', value: '0.2', expectedCo2e: '0.3' },
              { title: '지어낸 둘째 추천', value: '0.4', expectedCo2e: '0.6' },
            ],
          },
          // 입력 칸(S3W2c) — 서버 글자 그대로(수도 글자).
          input: {
            country: '지어낸 나라',
            site: '지어낸 사업장',
            name: '지어낸 품목',
            vehicle: '지어낸 수단',
            energy: '지어낸 에너지',
            people: '3.0',
            buildingArea: '100.0',
            usedArea: '25.0',
            buildingPeople: null,
            ownPeople: null,
            productCount: '7.0',
            sales: null,
            weight: '0.5',
            weightUnit: 'kg',
            stores: null,
            useMonths: '18.0',
          },
        },
      ],
    });
    expect(sheets[2]).toEqual({
      status: 'processed',
      sheet: 's5',
      category: 'Category5',
      rows: [
        {
          rowId: 'a1',
          co2e: '1',
          biogenic: '0.5',
          origin: 'rule',
          formula: '지어낸 식',
          detail: {
            shape: 'activity',
            kind: 'waste',
            activity: {
              value: '1.5',
              unit: 'kg',
              baseValue: '1.5',
              baseUnit: 'kg',
            },
            factor: {
              title: '지어낸 계수',
              value: '0.25',
              unit: 'kgCO2e/kg',
              source: '지어낸 시트',
            },
            treatment: '소각',
            mode: 'train',
            distance: {
              km: '12.5',
              roundTrip: '1',
              people: '3',
              trips: '2',
              workdays: '200',
            },
            fcf: '0.1',
            hasBiogenic: true,
            biogenicNote: '지어낸',
          },
          input: expect.objectContaining({ country: '지어낸 나라' }),
        },
      ],
    });
    // empty 는 이름을 갖고(상세에 나온다), not_target·not_yet_supported 는 other.
    expect(sheets[7]).toEqual({
      status: 'empty',
      sheet: 's-empty',
      category: 'Category14',
    });
    expect(sheets[8]).toEqual({
      status: 'failed',
      sheet: 's-bad',
      category: 'Category15',
    });
    expect(outcome.value.llmCalls).toEqual({
      classify: { success: 3, 'failed:refusal': 1 },
    });
    expect(JSON.stringify(outcome)).not.toContain(FAKE_SHEET_ERROR);
  });

  it('rejected → reason 만(detail 은 싣지 않음) · 셋 다', async () => {
    for (const reason of [
      'reader_problem',
      'factor_book',
      'legacy_template',
    ] as const) {
      const { port } = setup({
        runs: [{ ...doneRun, result: fakeRejectedResult(reason) }],
      });
      const outcome = await port.result('7');
      expect(outcome).toEqual({
        kind: 'ok',
        value: { status: 'rejected', reason },
      });
      expect(JSON.stringify(outcome)).not.toContain(FAKE_REJECT_DETAIL);
    }
  });

  it('404 not_found(없음·결과 없음) · 409 run_not_done · 끊김 → failed · 회사 거절 셋 → refused', async () => {
    const { port } = setup({
      runs: [
        { id: 7, status: 'processing', reportYear: 2025 },
        { id: 8, status: 'done', reportYear: 2025, result: null },
      ],
    });
    expect(await port.result('7')).toEqual({ kind: 'failed' });
    expect(await port.result('8')).toEqual({ kind: 'failed' });
    expect(await port.result('99')).toEqual({ kind: 'failed' });
    expect(await port.result('x')).toEqual({ kind: 'failed' });
    const cut = setup({ runs: [doneRun] });
    cut.server.override['GET /inventory/scope3/runs/7/result'] = unreachable;
    expect(await cut.port.result('7')).toEqual({ kind: 'failed' });
    for (const company of ['ambiguous', 'inactive', 'not_found'] as const) {
      const { port: refused } = setup({ company, runs: [doneRun] });
      expect(await refused.result('7')).toEqual({ kind: 'refused', company });
    }
  });

  it('꼴 틀림은 failed — ?? [] 로 메우지 않는다', async () => {
    const good = fakeDoneResult();
    const broken: [string, unknown][] = [
      ['sheets 없음', { ...good, sheets: undefined }],
      [
        'rows 가 배열 아님',
        {
          ...good,
          sheets: [
            {
              status: 'processed',
              sheet: 's',
              category: 'Category1',
              rows: null,
            },
          ],
        },
      ],
      [
        'co2e 가 수',
        {
          ...good,
          sheets: [
            processedSheet('s', 'Category1', [
              { ...purchaseRow('1'), co2e: 1 },
            ]),
          ],
        },
      ],
      [
        'biogenic 꼴 틀림',
        {
          ...good,
          sheets: [
            processedSheet('s', 'Category5', [
              { ...activityRow('waste', '1'), biogenic: 'x' },
            ]),
          ],
        },
      ],
      [
        'failed 의 category 없음',
        { ...good, sheets: [{ status: 'failed', sheet: 's' }] },
      ],
      [
        'failed 의 sheet 없음',
        { ...good, sheets: [{ status: 'failed', category: 'Category1' }] },
      ],
      [
        'empty 의 category 없음',
        { ...good, sheets: [{ status: 'empty', sheet: 's' }] },
      ],
      [
        'processed 의 sheet 가 수',
        {
          ...good,
          sheets: [
            { status: 'processed', sheet: 1, category: 'Category1', rows: [] },
          ],
        },
      ],
      ['llmCalls 의 수가 글자', { ...good, llmCalls: { a: { success: '1' } } }],
      ['모르는 판', { ...good, schemaVersion: 'scope3.colab.result@2' }],
      ['모르는 status', { ...good, status: 'partial' }],
      ['모르는 거절 까닭', fakeRejectedResult('other')],
    ];
    for (const [why, body] of broken) {
      expect(resultOf(body), why).toBeNull();
      const { port } = setup({ runs: [{ ...doneRun, result: body }] });
      expect(await port.result('7'), why).toEqual({ kind: 'failed' });
    }
  });

  it('모르는 시트 status 는 other(합에 넣지 않음 — 결과는 읽힘)', () => {
    const body = fakeDoneResult({
      sheets: [{ status: 'brand_new', sheet: 's', category: 'Category1' }],
    });
    expect(resultOf(body)).toEqual({
      status: 'done',
      sheets: [{ status: 'other' }],
      llmCalls: { classify: { success: 2 } },
    });
  });
});

describe('result — 상세 표 칸(S3W2b ① — kind 열넷의 판별 유니온)', () => {
  const done = (body: unknown) => {
    const result = resultOf(body);
    if (result === null || result.status !== 'done')
      throw new Error('done 아님');
    return result;
  };
  const processedRows = (sheets: ResultSheet[]) =>
    sheets.flatMap((sheet) => (sheet.status === 'processed' ? sheet.rows : []));

  it('fakeDetailResult: 줄마다 kind 그대로 · basic 0 · 시트 이름·empty·failed', () => {
    const result = done(fakeDetailResult());
    const rows = processedRows(result.sheets);
    expect(rows.every((row) => row.detail.shape !== 'basic')).toBe(true);
    const kinds = new Set(
      rows.map((row) => (row.detail.shape === 'basic' ? '' : row.detail.kind)),
    );
    expect([...kinds].sort()).toEqual([...ROW_KINDS].sort());
    expect(
      result.sheets.filter((sheet) => sheet.status !== 'processed'),
    ).toEqual([
      {
        status: 'failed',
        sheet: `${detailSheetName('c4-2')} 둘`,
        category: 'Category4',
      },
      {
        status: 'empty',
        sheet: `${detailSheetName('c6-2')} 둘`,
        category: 'Category6',
      },
      { status: 'other' },
    ]);
    expect(JSON.stringify(result)).not.toContain('ValueError');
  });

  it('구매 줄: 그룹명·지출·계수(값·단위·출처) · rowId·origin', () => {
    const row = processedRows(done(fakeDetailResult()).sheets)[0]!;
    expect(row).toMatchObject({
      rowId: `${detailSheetName('c1')}!5`,
      co2e: '3',
      origin: 'ai',
      detail: {
        shape: 'purchase',
        kind: 'purchase',
        groupName: FAKE_GROUP_A,
        spendKrw: '100',
        factor: { value: '0.1', unit: 'kgCO2e/KRW', source: 'db_keyword' },
      },
    });
  });

  it('활동 줄: 처리·수단·거리·FCF(글자 그대로) · 계수 source 는 factor.sheet 글자(S3W3c C5 ④)', () => {
    const rows = processedRows(done(fakeDetailResult()).sheets);
    const waste = rows.find((row) => row.rowId?.endsWith('!9'))!;
    expect(waste).toMatchObject({
      biogenic: '1.25',
      origin: 'estimate',
      detail: {
        shape: 'activity',
        kind: 'waste',
        treatment: FAKE_TREATMENT,
        fcf: '0.1',
        distance: null,
        mode: null,
        factor: { source: '지어낸 시트', unit: 'kgCO2e/kg' },
      },
    });
    const travel = rows.find(
      (row) =>
        row.detail.shape === 'activity' &&
        row.detail.kind === 'travel_distance',
    )!;
    expect(travel.detail).toMatchObject({
      mode: FAKE_MODE,
      distance: {
        km: '300',
        roundTrip: '2',
        people: '2',
        trips: '4',
        workdays: null,
      },
    });
  });

  it('에너지 줄: 계수 이름·배분·기간·투자 · 계수 null(C15)', () => {
    const rows = processedRows(done(fakeDetailResult()).sheets);
    const fuel = rows.find(
      (row) =>
        row.detail.shape === 'energy' && row.detail.kind === 'fuel_energy',
    )!;
    expect(fuel.detail).toMatchObject({
      factor: { title: FAKE_FUEL },
      buildingTotal: '10',
      years: '5',
      investment: { share: '0.1', scope1: '1', scope2: '2' },
      fcf: null,
    });
    const invest = rows.find(
      (row) =>
        row.detail.shape === 'energy' && row.detail.kind === 'investment',
    )!;
    expect(invest.detail).toMatchObject({ factor: null });
  });

  it('모르는 kind·꼴 틀린 칸은 그 줄만 basic(합 칸 co2e 는 그대로) — 결과는 읽힌다', () => {
    const cases: [string, Record<string, unknown>][] = [
      ['모르는 kind', { ...purchaseRow('2'), kind: 'brand_new' }],
      ['kind 없음', { ...activityRow('waste', '2'), kind: undefined }],
      ['그룹 없음', { ...purchaseRow('2'), group: null }],
      ['계수 값이 수', { ...purchaseRow('2'), factor: { value: 1 } }],
      ['활동량 꼴 틀림', { ...activityRow('waste', '2'), activity: 'x' }],
      [
        '거리 칸이 수',
        {
          ...activityRow('commute', '2'),
          distance: { km: 3 },
        },
      ],
      ['수단 꼴 틀림', { ...activityRow('commute', '2'), mode: 'x' }],
      ['투자 칸 꼴 틀림', { ...energyRow('investment', '2'), investment: 1 }],
      [
        'fcf 가 수',
        {
          ...activityRow('waste', '2', '0.5'),
          biogenic: { biogenicCo2e: '0.5', fcf: 0.3 },
        },
      ],
    ];
    for (const [why, row] of cases) {
      const result = done(
        fakeDoneResult({ sheets: [processedSheet('s', 'Category1', [row])] }),
      );
      const one = (result.sheets[0] as { rows: ResultRow[] }).rows[0]!;
      expect(one.detail, why).toEqual({ shape: 'basic' });
      expect(one.co2e, why).toBe('2');
    }
  });

  it('rowId·origin 꼴 틀림은 null(줄은 남음)', () => {
    const result = done(
      fakeDoneResult({
        sheets: [
          processedSheet('s', 'Category1', [
            { ...purchaseRow('2'), rowId: 7, origin: 'guess' },
          ]),
        ],
      }),
    );
    expect((result.sheets[0] as { rows: ResultRow[] }).rows[0]).toMatchObject({
      rowId: null,
      origin: null,
    });
  });
});

describe('result — 창 칸 originSteps·formula·biogenic.note(밴드 S3W4 ①)', () => {
  const rowFrom = (row: Record<string, unknown>) => {
    const result = resultOf(
      fakeDoneResult({ sheets: [processedSheet('s', 'Category1', [row])] }),
    );
    if (result === null || result.status !== 'done')
      throw new Error('done 아님');
    return (result.sheets[0] as { rows: ResultRow[] }).rows[0]!;
  };
  const groupOriginOf = (extra: Record<string, unknown>) => {
    const { detail } = rowFrom(purchaseRow('1', 'p', extra));
    if (detail.shape !== 'purchase') throw new Error('구매 줄 아님');
    return detail.groupOrigin;
  };
  const step = (name: unknown, origin: unknown) => ({
    step: name,
    origin,
    via: '지어낸',
  });

  it('group 단계 origin 셋 갈래 · 줄 origin 과 따로 읽는다', () => {
    expect(groupOriginOf({})).toBe('ai');
    expect(groupOriginOf({ ...ruleGroupSteps, origin: 'ai' })).toBe('rule');
    expect(groupOriginOf({ ...estimateGroupSteps, origin: 'ai' })).toBe(
      'estimate',
    );
  });

  it('group 단계가 없으면 null · factor 단계 ai 는 group 이 아니다', () => {
    expect(groupOriginOf({ originSteps: [] })).toBeNull();
    expect(groupOriginOf({ originSteps: [step('factor', 'ai')] })).toBeNull();
  });

  it('group 단계가 둘이면 ai 가 이긴다(차례 무관)', () => {
    const rule = step('group', 'rule');
    const ai = step('group', 'ai');
    expect(groupOriginOf({ originSteps: [rule, ai] })).toBe('ai');
    expect(groupOriginOf({ originSteps: [ai, rule] })).toBe('ai');
  });

  it('모르는 step·origin 낱개는 버린다(줄은 살고 별 없음)', () => {
    expect(
      groupOriginOf({
        originSteps: [
          step('brand_new', 'ai'),
          step('group', 'brand_new'),
          'x',
          null,
        ],
      }),
    ).toBeNull();
    expect(
      groupOriginOf({
        originSteps: [step('group', 'nope'), step('group', 'rule')],
      }),
    ).toBe('rule');
  });

  it('originSteps 가 배열이 아니면 그 줄만 basic(세 꼴 다 — [] 로 삼키지 않는다)', () => {
    const rows = [
      purchaseRow('2'),
      activityRow('waste', '2'),
      energyRow('product_eol', '2'),
    ];
    for (const row of rows)
      for (const originSteps of [null, undefined, {}, 'x']) {
        const one = rowFrom({ ...row, originSteps });
        expect(one.detail).toEqual({ shape: 'basic' });
        expect(one.co2e).toBe('2');
      }
  });

  it('formula: 글 그대로(빈 글도) · 글이 아니면 null(줄은 그대로)', () => {
    expect(rowFrom(purchaseRow('1')).formula).toBe('지어낸 식');
    expect(rowFrom(purchaseRow('1', 'p', { formula: '' })).formula).toBe('');
    const wrong = rowFrom(purchaseRow('1', 'p', { formula: 3 }));
    expect(wrong.formula).toBeNull();
    expect(wrong.detail.shape).toBe('purchase');
  });

  it('biogenic: 칸 있음·note 글자 그대로 · note null · 칸 없음 · note 가 수면 basic', () => {
    expect(rowFrom(activityRow('waste', '1', '0.5')).detail).toMatchObject({
      hasBiogenic: true,
      biogenicNote: '지어낸',
    });
    expect(
      rowFrom(activityRow('waste', '1', '0', 'a', noBiogenicSplit)).detail,
    ).toMatchObject({ hasBiogenic: true, biogenicNote: '해당없음', fcf: null });
    const nullNote = activityRow('waste', '1', '0.5');
    nullNote.biogenic = { ...(nullNote.biogenic as object), note: null };
    expect(rowFrom(nullNote).detail).toMatchObject({
      hasBiogenic: true,
      biogenicNote: null,
    });
    expect(rowFrom(energyRow('product_eol', '1')).detail).toMatchObject({
      hasBiogenic: false,
      biogenicNote: null,
    });
    const wrong = activityRow('waste', '1', '0.5');
    wrong.biogenic = { ...(wrong.biogenic as object), note: 3 };
    expect(rowFrom(wrong).detail).toEqual({ shape: 'basic' });
  });

  const recommendationsOf = (value: unknown) => {
    const { detail } = rowFrom(
      purchaseRow('1', 'p1', { recommendations: value }),
    );
    return detail.shape === 'purchase' ? detail.recommendations : 'basic';
  };

  it('추천은 구매 줄에 서버 차례·값 null 그대로 든다(rank 가 배열 자리 — 거르면 뒤 순위가 밀린다)', () => {
    const items = [
      { title: '지어낸 가', value: null, expectedCo2e: null },
      { title: '지어낸 나', value: '0.2', expectedCo2e: '0.3' },
    ];
    expect(recommendationsOf(items)).toEqual(items);
    expect(recommendationsOf([])).toEqual([]);
  });

  it.each([
    ['배열 아님', { title: '지어낸' }],
    ['없음', undefined],
    ['제목이 글자 아님', [{ title: 1, value: null, expectedCo2e: null }]],
    ['값이 수', [{ title: '지어낸', value: 1, expectedCo2e: null }]],
    ['칸 빠짐', [{ title: '지어낸', value: null }]],
    [
      '더한 칸(닫힌 꼴)',
      [{ title: '지어낸', value: null, expectedCo2e: null, 더한칸: 1 }],
    ],
    [
      '하나만 틀려도 통째로(일부만 남기면 자리가 밀린다)',
      [{ title: '지어낸', value: '1', expectedCo2e: null }, null],
    ],
  ])(
    '추천 꼴이 틀리면 추천만 빈 배열, 줄은 basic 이 아니다: %s',
    (_, value) => {
      expect(recommendationsOf(value)).toEqual([]);
    },
  );

  it('구매 밖 줄은 추천 칸이 없다 · factor.sheet 가 글자가 아니면 출처만 null(줄은 산다)', () => {
    const { detail } = rowFrom(activityRow('waste', '1'));
    expect(detail).not.toHaveProperty('recommendations');
    const lost = rowFrom(
      activityRow('waste', '1', undefined, 'a1', {
        factor: {
          title: null,
          value: '1',
          unit: 'kg',
          column: null,
          code: null,
        },
      }),
    ).detail;
    expect(lost.shape).toBe('activity');
    expect(lost.shape === 'activity' && lost.factor.source).toBeNull();
  });
});

describe('result — 줄의 입력 칸 input(S3W2c ① — Q1·Q2)', () => {
  const one = (row: Record<string, unknown>): ResultRow => {
    const result = resultOf(
      fakeDoneResult({ sheets: [processedSheet('s', 'Category1', [row])] }),
    );
    if (result === null || result.status !== 'done')
      throw new Error('done 아님');
    return (result.sheets[0] as { rows: ResultRow[] }).rows[0]!;
  };

  it('있음: 키 열여섯 글자 그대로(수도 「3.0」 글자 — 셈은 model) · 처리기에 없는 키는 null', () => {
    const row = one(purchaseRow('2', 'p', { input: fakeInput('c12') }));
    expect(row.input).toEqual({
      country: '지어낸 나라 c12',
      site: null,
      name: '지어낸 이름 c12',
      vehicle: null,
      energy: null,
      people: null,
      buildingArea: null,
      usedArea: null,
      buildingPeople: null,
      ownPeople: null,
      productCount: null,
      sales: '1250.0',
      weight: '0.5',
      weightUnit: 'kg',
      stores: null,
      useMonths: null,
    });
  });

  it('S3R3: C11 useMonths 글자 그대로(「18.0」) · 키 열다섯(S3R3 앞 저장 — useMonths 없음)은 useMonths null, 나머지 그대로(감독 처분 Q3)', () => {
    const c11 = one(
      energyRow('product_use', '2', undefined, 'e', {
        input: fakeInput('c11'),
      }),
    );
    expect(c11.input).toMatchObject({
      productCount: '7.0',
      useMonths: '18.0',
    });
    const old = one(
      energyRow('product_use', '2', undefined, 'e', {
        input: fifteenKeyInput(fakeInput('c11')),
      }),
    );
    expect(old.input).toEqual({ ...c11.input, useMonths: null });
    expect(old.detail.shape).toBe('energy');
    const nulled = one(
      energyRow('product_use', '2', undefined, 'e', {
        input: fakeInput('c11', { useMonths: null }),
      }),
    );
    expect(nulled.input).toEqual(old.input);
  });

  it('없음(옛 결과)·null 은 input null — 줄 나머지 그대로', () => {
    for (const row of [
      withoutInput(purchaseRow('2')),
      purchaseRow('2', 'p', { input: null }),
    ]) {
      const read = one(row);
      expect(read.input).toBeNull();
      expect(read.detail.shape).toBe('purchase');
      expect(read.co2e).toBe('2');
    }
  });

  it('꼴 틀림(객체 아님·배열·모르는 키·키 빠짐·값이 수·값이 객체)은 그 줄의 input 만 null — detail·co2e 그대로', () => {
    const good = fakeInput('c3');
    const { stores: _stores, ...missing } = good;
    void _stores;
    // S3R3: useMonths 만 빠져도 되고(위 시험), 다른 키 하나가 빠지면(useMonths 가 있어도) 꼴 틀림.
    const { country: _country, ...missingCountry } = good;
    void _country;
    const cases: [string, unknown][] = [
      ['글자', '지어낸'],
      ['배열', []],
      ['수', 3],
      ['모르는 키', { ...good, extra: null }],
      ['키 빠짐', missing],
      ['키 빠짐(country)', missingCountry],
      ['값이 수', { ...good, people: 3 }],
      ['useMonths 값이 수', { ...good, useMonths: 18 }],
      ['useMonths 이름 틀림', { ...fifteenKeyInput(good), usemonths: null }],
      ['값이 객체', { ...good, country: { value: 'x' } }],
    ];
    for (const [why, input] of cases)
      for (const row of [
        purchaseRow('2', 'p', { input }),
        activityRow('waste', '2', '0.5', 'a', { input }),
        energyRow('fuel_energy', '2', undefined, 'e', { input }),
      ]) {
        const read = one(row);
        expect(read.input, why).toBeNull();
        expect(read.detail.shape, why).not.toBe('basic');
        expect(read.co2e, why).toBe('2');
      }
  });

  it('basic 줄(모르는 kind)도 input 을 싣는다', () => {
    const read = one({
      ...energyRow('fuel_energy', '2', undefined, 'e', {
        input: fakeInput('c3'),
      }),
      kind: 'brand_new',
    });
    expect(read.detail).toEqual({ shape: 'basic' });
    expect(read.input).toMatchObject({ energy: '지어낸 에너지 c3' });
  });

  it('fakeDetailResult: 입력 있는 줄·없는 줄(옛)·null 섞인 줄이 다 있다', () => {
    const result = resultOf(fakeDetailResult());
    if (result === null || result.status !== 'done') throw new Error('x');
    const rows = result.sheets.flatMap((sheet) =>
      sheet.status === 'processed' ? sheet.rows : [],
    );
    expect(rows.some((row) => row.input !== null)).toBe(true);
    expect(rows.filter((row) => row.input === null)).toHaveLength(2);
    // S3R3: C11 줄은 키 열다섯 옛 판 — input 은 읽히고 useMonths 만 null.
    const c11 = rows.filter((row) => row.rowId?.startsWith('c11_'));
    expect(c11).toHaveLength(1);
    expect(c11[0]!.input).toMatchObject({
      productCount: '7.0',
      useMonths: null,
    });
    expect(
      rows.some(
        (row) => row.input?.site === null && row.input.country !== null,
      ),
    ).toBe(true);
  });
});

describe('S3W3a 지금 결과 경로', () => {
  const body = (rows: unknown[]) =>
    fakeDoneResult({
      sheets: [processedSheet('C1_지어낸', 'Category1', rows as never)],
    });
  const twoRuns = (extra: FakeScope3ServerOptions = {}) =>
    setup({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: body([purchaseRow('0.1', 'A!2'), purchaseRow('0.2', 'A!3')]),
        },
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: body([purchaseRow('5', 'A!2')]),
        },
      ],
      ...extra,
    });
  const R9 = '/inventory/scope3/runs/9';

  it('year: 글자 id · 카테고리 열넷 · 합은 정확합 글자 · 기준은 새 것', async () => {
    const { port, server } = twoRuns({
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    const outcome = await port.year(2025);
    expect(outcome.kind).toBe('ok');
    if (outcome.kind !== 'ok') return;
    expect(outcome.value.baseRunId).toBe('9');
    expect(outcome.value.latest).toEqual({ runId: '9', status: 'done' });
    expect(outcome.value.categories).toHaveLength(14);
    const c1 = outcome.value.categories[0]!;
    expect(c1.current).toEqual({
      runId: '7',
      total: '0.3',
      sheets: 1,
      failedSheets: 0,
    });
    expect(c1.locked).toBe(true);
    expect(server.count('GET /inventory/scope3/years/2025')).toBe(1);
  });

  it('decimalSum: 서버 decimal_text 꼴(지수 0 · 끝 0 걷음 · 음수 · 수 없음 null)', () => {
    expect(decimalSum(['0.1', '0.2'])).toBe('0.3');
    expect(decimalSum(['1e-07'])).toBe('0.0000001');
    expect(decimalSum(['1.50', '2.50'])).toBe('4');
    expect(decimalSum(['-1.5', '1'])).toBe('-0.5');
    expect(decimalSum(['1e3'])).toBe('1000');
    expect(decimalSum([null, 'nan'])).toBeNull();
  });

  it('year: 실행 없음·base 판에서도 답한다(첫 화면 [다음]이 지난다)', async () => {
    const { port } = setup({ server: 'base' });
    const outcome = await port.year(2025);
    expect(outcome.kind === 'ok' && outcome.value.baseRunId).toBeNull();
  });

  it('읽기 셋: 꼴 틀림·404·회사 셋', async () => {
    const { port, server } = twoRuns();
    server.override['GET /inventory/scope3/years/2025'] = () =>
      json(200, { year: '2025' });
    expect(await port.year(2025)).toEqual({ kind: 'failed' });
    expect(await port.edits('404')).toEqual({ kind: 'failed' });
    expect(await port.history('404')).toEqual({ kind: 'failed' });
    expect(await port.edits('x')).toEqual({ kind: 'failed' });
    expect(await port.history('x')).toEqual({ kind: 'failed' });
    server.override[`GET ${R9}/edits`] = () =>
      json(200, { runId: 9, rows: [] });
    expect(await port.edits('9')).toEqual({ kind: 'failed' });
    server.override[`GET ${R9}/history`] = () => json(200, { results: [] });
    expect(await port.history('9')).toEqual({ kind: 'failed' });
    for (const company of ['ambiguous', 'inactive', 'not_found'] as const) {
      const made = setup({ company });
      expect(await made.port.year(2025)).toEqual({ kind: 'refused', company });
      expect(await made.port.edits('9')).toEqual({ kind: 'refused', company });
      expect(await made.port.history('9')).toEqual({
        kind: 'refused',
        company,
      });
      expect(await made.port.lock(2025, 'C1', '9')).toEqual({
        kind: 'refused',
        company,
      });
      expect(await made.port.unlock(2025, 'C1')).toEqual({
        kind: 'refused',
        company,
      });
      expect(await made.port.exclude('9', 'C1', ['A!2'], '지어낸')).toEqual({
        kind: 'refused',
        company,
      });
      expect(await made.port.restore('9', 'C1', ['A!2'], '지어낸')).toEqual({
        kind: 'refused',
        company,
      });
      expect(
        await made.port.factor('9', 'C1', {
          rowId: 'A!2',
          reason: '지어낸',
          choice: 'applied',
        }),
      ).toEqual({ kind: 'refused', company });
    }
  });

  it('edits: factor 칸이 없는 줄은 꼴 틀림(null 은 값, 없음은 failed)', async () => {
    const { port, server } = twoRuns();
    const row = {
      rowId: 'A!2',
      category: 'C1',
      excluded: true,
      editedAt: '2026-03-01T00:00:01Z',
      editedBy: null,
    };
    server.override[`GET ${R9}/edits`] = [
      () => json(200, { runId: '9', rows: [{ ...row, factor: null }] }),
      () => json(200, { runId: '9', rows: [row] }),
    ];
    expect((await port.edits('9')).kind).toBe('ok');
    expect(await port.edits('9')).toEqual({ kind: 'failed' });
  });

  it('history: 준 칸만 쿼리에 · 새 것 먼저 · rowId 거름', async () => {
    const { port, server } = twoRuns();
    await port.exclude('9', 'C1', ['A!2'], '지어낸 하나');
    await port.restore('9', 'C1', ['A!2'], '지어낸 둘');
    const outcome = await port.history('9', {
      rowId: 'A!2',
      page: 1,
      pageSize: 1,
    });
    expect(
      outcome.kind === 'ok' && outcome.value.lines.map((one) => one.kind),
    ).toEqual(['restore']);
    expect(outcome.kind === 'ok' && outcome.value.hasNext).toBe(true);
    const last = server.calls.at(-1)!;
    expect(Object.fromEntries(last.query)).toEqual({
      rowId: 'A!2',
      page: '1',
      pageSize: '1',
    });
    await port.history('9');
    expect([...server.calls.at(-1)!.query.keys()]).toEqual([]);
  });

  it('lock: 쿼리 runId 는 수 · 답은 그 카테고리 · 안 나간 id 는 failed', async () => {
    const { port, server } = twoRuns();
    const outcome = await port.lock(2025, 'C1', '9');
    expect(outcome.kind === 'ok' && outcome.value.locked).toBe(true);
    const sent = server.calls.at(-1)!;
    expect(sent.method).toBe('POST');
    expect(sent.path).toBe('/inventory/scope3/years/2025/categories/C1/lock');
    expect(sent.query.get('runId')).toBe('9');
    const before = server.calls.length;
    expect(await port.lock(2025, 'C1', 'x')).toEqual({ kind: 'failed' });
    expect(server.calls).toHaveLength(before);
  });

  it('lock 거절: 409 stale_run · not_computed · 404 는 code 없음', async () => {
    const { port } = twoRuns();
    expect(await port.lock(2025, 'C1', '7')).toEqual({
      kind: 'rejected',
      code: 'STALE_RUN',
      fields: [],
    });
    expect(await port.lock(2025, 'C2', '9')).toEqual({
      kind: 'rejected',
      code: 'NOT_COMPUTED',
      fields: [],
    });
    const none = setup();
    expect(await none.port.lock(2025, 'C1', '9')).toEqual({
      kind: 'rejected',
      code: 'NOT_COMPUTED',
      fields: [],
    });
    const server404 = twoRuns();
    server404.server.override[
      'POST /inventory/scope3/years/2025/categories/C1/lock'
    ] = () => refusal(404, 'NOT_FOUND');
    expect(await server404.port.lock(2025, 'C1', '9')).toEqual({
      kind: 'rejected',
      code: null,
      fields: [],
    });
  });

  it('unlock: 고객사 403 forbidden · 운영 관리자 풀림 · 핀이 풀리면 기준으로', async () => {
    const customer = twoRuns({
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    expect(await customer.port.unlock(2025, 'C1')).toEqual({
      kind: 'rejected',
      code: 'FORBIDDEN',
      fields: [],
    });
    const admin = twoRuns({
      operator: true,
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    const outcome = await admin.port.unlock(2025, 'C1');
    expect(outcome.kind === 'ok' && outcome.value.current?.runId).toBe('9');
    expect(admin.server.calls.at(-1)!.method).toBe('DELETE');
  });

  it('exclude·restore: 몸 그대로 · 합에서 빠지고 돌아옴 · 서버 판정 차례(locked 먼저)', async () => {
    const { port, server } = twoRuns();
    const out = await port.exclude('9', 'C1', ['A!2'], ' 지어낸 ');
    expect(out.kind === 'ok' && out.value.category.current?.total).toBeNull();
    expect(server.bodies(`POST ${R9}/categories/C1/exclusions`)).toEqual([
      { rowIds: ['A!2'], reason: ' 지어낸 ' },
    ]);
    const back = await port.restore('9', 'C1', ['A!2'], '지어낸');
    expect(back.kind === 'ok' && back.value.category.current?.total).toBe('5');
    expect(await port.exclude('7', 'C1', ['A!2'], '지어낸')).toEqual({
      kind: 'rejected',
      code: 'STALE_RUN',
      fields: [],
    });
    const locked = twoRuns({
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    expect(await locked.port.exclude('7', 'C1', ['A!2'], '지어낸')).toEqual({
      kind: 'rejected',
      code: 'LOCKED',
      fields: [],
    });
    expect(await port.exclude('404', 'C1', ['A!2'], '지어낸')).toEqual({
      kind: 'rejected',
      code: null,
      fields: [],
    });
    expect(await port.exclude('x', 'C1', ['A!2'], '지어낸')).toEqual({
      kind: 'failed',
    });
  });

  it('422: fields 는 칸 이름만(서버 문장 버림) · 모르는 줄', async () => {
    const { port } = twoRuns();
    expect(await port.exclude('9', 'C1', [], '   ')).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: ['rowIds', 'reason'],
    });
    expect(await port.restore('9', 'C1', ['없는 줄'], '지어낸')).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: ['rowIds'],
    });
  });

  it('모르는 code 면 fields 도 비운다', async () => {
    const { port, server } = twoRuns();
    server.override[`POST ${R9}/categories/C1/exclusions`] = () =>
      refusal(409, 'SOMETHING_ELSE', { rowIds: ['지어낸'] });
    expect(await port.exclude('9', 'C1', ['A!2'], '지어낸')).toEqual({
      kind: 'rejected',
      code: null,
      fields: [],
    });
  });

  it.each([
    [{ choice: 'applied' }, { rank: null, custom: null, choice: 'applied' }],
    [
      { choice: 'recommended', rank: 2 },
      { rank: 2, custom: null, choice: 'recommended' },
    ],
    [
      {
        choice: 'custom',
        custom: { title: ' 가 ', value: '1.50', source: '나' },
      },
      {
        rank: null,
        custom: { title: ' 가 ', value: '1.50', source: '나' },
        choice: 'custom',
      },
    ],
  ] as const)('factor 몸 전체: %j', async (pick, want) => {
    const { port, server } = twoRuns();
    const outcome = await port.factor('9', 'C1', {
      rowId: 'A!2',
      reason: ' 지어낸 ',
      ...pick,
    } as RowFactorInput);
    expect(outcome.kind).toBe('ok');
    expect(server.bodies(`POST ${R9}/categories/C1/factors`)).toEqual([
      { rowId: 'A!2', reason: ' 지어낸 ', ...want },
    ]);
  });

  it('factor: applied 는 합을 안 바꾸고 고친 줄에 안 든다 · 추천은 고친 값으로', async () => {
    const { port } = twoRuns();
    const applied = await port.factor('9', 'C1', {
      rowId: 'A!2',
      reason: '지어낸',
      choice: 'applied',
    });
    expect(applied.kind === 'ok' && applied.value.category.current?.total).toBe(
      '5',
    );
    expect(applied.kind === 'ok' && applied.value.category.editedRows).toBe(0);
    const picked = await port.factor('9', 'C1', {
      rowId: 'A!2',
      reason: '지어낸',
      choice: 'recommended',
      rank: 1,
    });
    expect(picked.kind === 'ok' && picked.value.category.current?.total).toBe(
      FAKE_EDITED_CO2E,
    );
    expect(picked.kind === 'ok' && picked.value.category.editedRows).toBe(1);
  });

  it('factor 거절: C12·C15 409 · 키가 빠지면 422 · 안 나간 id', async () => {
    const result = fakeDoneResult({
      sheets: [
        processedSheet('C12_지어낸', 'Category12', [
          energyRow('product_eol', '1', null, 'B!2'),
        ]),
      ],
    });
    const { port } = setup({
      runs: [{ id: 9, status: 'done', reportYear: 2025, result }],
    });
    expect(
      await port.factor('9', 'C12', {
        rowId: 'B!2',
        reason: '지어낸',
        choice: 'applied',
      }),
    ).toEqual({ kind: 'rejected', code: 'FACTOR_NOT_EDITABLE', fields: [] });
    expect(
      await port.factor('x', 'C12', {
        rowId: 'B!2',
        reason: '지어낸',
        choice: 'applied',
      }),
    ).toEqual({ kind: 'failed' });
    const server = fakeScope3Server();
    const answer = await server.send(
      new Request(`http://test.local/api${R9}/categories/C1/factors`, {
        method: 'POST',
        body: JSON.stringify({
          rowId: 'A!2',
          choice: 'applied',
          reason: '지어낸',
        }),
      }),
    );
    expect(answer.status).toBe(422);
  });

  it('쓰기 답 꼴이 틀리면 failed · 답 없음이면 failed', async () => {
    const { port, server } = twoRuns();
    const key = 'POST /inventory/scope3/years/2025/categories/C1/lock';
    server.override[key] = [() => json(200, { category: 'C1' }), unreachable];
    expect(await port.lock(2025, 'C1', '9')).toEqual({ kind: 'failed' });
    expect(await port.lock(2025, 'C1', '9')).toEqual({ kind: 'failed' });
  });

  it('다른 실행의 사건은 그 실행 덧판에만 · 새 실행 합에 안 붙는다(570)', async () => {
    const { port } = setup({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: body([purchaseRow('1', 'A!2')]),
          edits: [{ rowId: 'A!2', category: 'C1', excluded: true }],
        },
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: body([purchaseRow('1', 'A!2')]),
        },
      ],
    });
    const seven = await port.edits('7');
    const nine = await port.edits('9');
    expect(seven.kind === 'ok' && seven.value.rows).toHaveLength(1);
    expect(nine.kind === 'ok' && nine.value.rows).toEqual([]);
    const year = await port.year(2025);
    expect(year.kind === 'ok' && year.value.editedRowsUnlocked).toBe(0);
    expect(year.kind === 'ok' && year.value.categories[0]!.current?.total).toBe(
      '1',
    );
  });

  it('⑩ 사건 없는 줄 applied 는 사건 0(rows·edits·history 빔) · 같은 고름 두 번은 사건 하나', async () => {
    const { port } = twoRuns();
    const pick = { rowId: 'A!2', reason: '지어낸' };
    const applied = await port.factor('9', 'C1', {
      ...pick,
      choice: 'applied',
    });
    expect(applied.kind === 'ok' && applied.value.rows).toEqual([]);
    const edits = await port.edits('9');
    expect(edits.kind === 'ok' && edits.value.rows).toEqual([]);
    const empty = await port.history('9');
    expect(empty.kind === 'ok' && empty.value.count).toBe(0);
    await port.factor('9', 'C1', { ...pick, choice: 'recommended', rank: 1 });
    await port.factor('9', 'C1', { ...pick, choice: 'recommended', rank: 1 });
    const one = await port.history('9');
    expect(one.kind === 'ok' && one.value.count).toBe(1);
    await port.factor('9', 'C1', { ...pick, choice: 'recommended', rank: 2 });
    await port.factor('9', 'C1', { ...pick, choice: 'applied' });
    const three = await port.history('9');
    expect(three.kind === 'ok' && three.value.count).toBe(3);
  });

  it('가짜 몸 검사: 순위 1~4 · 직접 입력 칸(서버 check_factor_body)', async () => {
    const { port } = twoRuns();
    const pick = { rowId: 'A!2', reason: '지어낸' };
    expect(
      await port.factor('9', 'C1', { ...pick, choice: 'recommended', rank: 9 }),
    ).toEqual({ kind: 'rejected', code: 'VALIDATION_ERROR', fields: ['rank'] });
    expect(
      await port.factor('9', 'C1', {
        ...pick,
        choice: 'custom',
        custom: { title: ' ', value: 'abc', source: ' ' },
      }),
    ).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      fields: ['custom.title', 'custom.source', 'custom.value'],
    });
  });

  it('editedRowsUnlocked: 잠근 카테고리는 빠지고 그 카테고리 editedRows 는 센다 · 한 줄이 둘 다여도 1', async () => {
    const { port } = setup({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet('C1_지어낸', 'Category1', [
                purchaseRow('1', 'A!2'),
              ]),
              processedSheet('C2_지어낸', 'Category2', [
                purchaseRow('1', 'B!2'),
              ]),
            ],
          }),
          edits: [
            { rowId: 'A!2', category: 'C1', excluded: true },
            {
              rowId: 'B!2',
              category: 'C2',
              excluded: true,
              factor: fakeRowFactor(),
            },
          ],
        },
      ],
      locks: [{ year: 2025, category: 'C1', runId: 9 }],
    });
    const year = await port.year(2025);
    if (year.kind !== 'ok') throw new Error('읽기 실패');
    expect(year.value.editedRowsUnlocked).toBe(1);
    expect(year.value.categories[0]!.editedRows).toBe(1);
    expect(year.value.categories[1]!.editedRows).toBe(1);
  });

  it('시트 수: failed 가 섞인 카테고리의 sheets·failedSheets', async () => {
    const { port } = setup({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet('C1_가', 'Category1', [purchaseRow('1', 'A!2')]),
              failedSheet('C1_나', 'Category1'),
              failedSheet('C1_다', 'Category1'),
            ],
          }),
        },
      ],
    });
    const year = await port.year(2025);
    if (year.kind !== 'ok') throw new Error('읽기 실패');
    expect(year.value.categories[0]!.current).toEqual({
      runId: '9',
      total: '1',
      sheets: 1,
      failedSheets: 2,
    });
  });

  it('사건은 rowId + 카테고리로 짝짓는다 — 다른 카테고리의 같은 rowId 는 합·editedRows 를 안 바꾼다', async () => {
    const { port } = setup({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet('C1_지어낸', 'Category1', [
                purchaseRow('1', 'A!2'),
              ]),
              processedSheet('C2_지어낸', 'Category2', [
                purchaseRow('2', 'A!2'),
              ]),
            ],
          }),
          edits: [{ rowId: 'A!2', category: 'C2', excluded: true }],
        },
      ],
    });
    const year = await port.year(2025);
    if (year.kind !== 'ok') throw new Error('읽기 실패');
    const [c1, c2] = year.value.categories;
    expect(c1!.current?.total).toBe('1');
    expect(c1!.editedRows).toBe(0);
    expect(c2!.current?.total).toBeNull();
    expect(c2!.editedRows).toBe(1);
  });

  describe('파서: 칸 하나가 틀리면 failed', () => {
    type Cell = Record<string, unknown>;
    const rawOf = async (server: FakeScope3Server, path: string) =>
      (await (
        await server.send(new Request(`http://test.local/api${path}`))
      ).json()) as Cell;
    const seededRuns = () =>
      twoRuns({ locks: [{ year: 2025, category: 'C1', runId: 7 }] });
    const firstCategory = (body: Cell) => (body.categories as Cell[])[0]!;
    const currentOfBody = (body: Cell) => firstCategory(body).current as Cell;

    it.each<[string, (body: Cell) => void]>([
      ['year', (b) => (b.year = '2025')],
      ['baseRunId', (b) => (b.baseRunId = 9)],
      ['editedRowsUnlocked', (b) => (b.editedRowsUnlocked = '0')],
      ['latest.runId 수', (b) => ((b.latest as Cell).runId = 9)],
      ['latest.status', (b) => ((b.latest as Cell).status = 'lost')],
      ['categories', (b) => (b.categories = {})],
      ['category C10', (b) => (firstCategory(b).category = 'C10')],
      ['category 모름', (b) => (firstCategory(b).category = 'Category1')],
      ['locked', (b) => (firstCategory(b).locked = 'true')],
      ['lockedAt', (b) => (firstCategory(b).lockedAt = 1)],
      ['lockedBy.id', (b) => (firstCategory(b).lockedBy = { id: 7, name: '' })],
      ['editedRows', (b) => (firstCategory(b).editedRows = '0')],
      ['current 칸 없음', (b) => delete firstCategory(b).current],
      ['current.runId', (b) => (currentOfBody(b).runId = 7)],
      ['current.total', (b) => (currentOfBody(b).total = 1)],
      ['current.sheets', (b) => (currentOfBody(b).sheets = '1')],
      ['current.failedSheets', (b) => (currentOfBody(b).failedSheets = '0')],
    ])('연도 %s', async (_, plant) => {
      const { server, port } = seededRuns();
      const body = await rawOf(server, '/inventory/scope3/years/2025');
      plant(body);
      server.override['GET /inventory/scope3/years/2025'] = () =>
        json(200, body);
      expect(await port.year(2025)).toEqual({ kind: 'failed' });
    });

    const editRow: Cell = {
      rowId: 'A!2',
      category: 'C1',
      excluded: false,
      factor: fakeRowFactor(),
      editedAt: '2026-03-01T00:00:01Z',
      editedBy: { id: '7', name: '지어낸' },
    };
    it.each<[string, Cell]>([
      ['rowId', { rowId: 2 }],
      ['category', { category: 'C10' }],
      ['excluded', { excluded: 'no' }],
      ['editedAt', { editedAt: 1 }],
      ['editedBy', { editedBy: { id: 7, name: '지어낸' } }],
      ['factor.choice', { factor: fakeRowFactor({ choice: 'ai' }) }],
      ['factor.rank', { factor: fakeRowFactor({ rank: '1' }) }],
      ['factor.co2e', { factor: fakeRowFactor({ co2e: 1 }) }],
      ['factor.ai', { factor: fakeRowFactor({ ai: null }) }],
    ])('덧판 %s', async (_, wrong) => {
      const { server, port } = seededRuns();
      server.override[`GET ${R9}/edits`] = [
        () => json(200, { runId: '9', rows: [editRow] }),
        () => json(200, { runId: '9', rows: [{ ...editRow, ...wrong }] }),
      ];
      expect((await port.edits('9')).kind).toBe('ok');
      expect(await port.edits('9')).toEqual({ kind: 'failed' });
    });

    const line: Cell = {
      id: '1',
      rowId: 'A!2',
      category: 'C1',
      kind: 'exclude',
      reason: '지어낸',
      at: '2026-03-01T00:00:01Z',
      by: null,
      batchId: null,
      factor: null,
    };
    const pageOf = (results: Cell[], extra: Cell = {}) => ({
      count: 1,
      totalPages: 1,
      page: 1,
      pageSize: 20,
      hasNext: false,
      hasPrevious: false,
      results,
      ...extra,
    });
    it.each<[string, Cell, Cell]>([
      ['id', { id: 1 }, {}],
      ['kind', { kind: 'edit' }, {}],
      ['reason', { reason: 1 }, {}],
      ['at', { at: 1 }, {}],
      ['batchId', { batchId: 1 }, {}],
      ['by', { by: { id: 1, name: '' } }, {}],
      ['factor', { factor: {} }, {}],
      ['count', {}, { count: '1' }],
      ['totalPages', {}, { totalPages: '1' }],
      ['hasNext', {}, { hasNext: 'no' }],
      ['hasPrevious', {}, { hasPrevious: 'no' }],
    ])('히스토리 %s', async (_, wrongLine, wrongPage) => {
      const { server, port } = seededRuns();
      server.override[`GET ${R9}/history`] = [
        () => json(200, pageOf([line])),
        () => json(200, pageOf([{ ...line, ...wrongLine }], wrongPage)),
      ];
      expect((await port.history('9')).kind).toBe('ok');
      expect(await port.history('9')).toEqual({ kind: 'failed' });
    });
  });

  it('진행·실패·거절 실행은 기준이 아니다 · latest 는 어느 상태든', async () => {
    const { port } = setup({
      runs: [
        { id: 7, status: 'done', reportYear: 2025 },
        {
          id: 8,
          status: 'done',
          reportYear: 2025,
          result: fakeRejectedResult(),
        },
        { id: 9, status: 'failed', reportYear: 2025 },
        { id: 10, status: 'processing', reportYear: 2025 },
      ],
    });
    const year = await port.year(2025);
    expect(year.kind === 'ok' && year.value.baseRunId).toBe('7');
    expect(year.kind === 'ok' && year.value.latest).toEqual({
      runId: '10',
      status: 'processing',
    });
  });
});

// ★ 거울(K2): 같은 표를 e2e spec 「S3W3c1 거울」 에 글자로 한 벌 더 둔다 — 한쪽을 고치면 다른 쪽도 고친다. 기대 값은 서버 scope3_factors.py·scope3_edits.py 에서 옮긴 리터럴이다.
describe('가짜 계수 규칙 — 서버 판정 차례(거울 표)', () => {
  const KINDS = [
    'transport_spend',
    'travel_spend',
    'transport_distance',
    'travel_distance',
    'commute',
    'fuel_energy',
    'leased_asset',
    'leased_out_asset',
    'product_use',
    'franchise',
  ];
  const RECS = [
    { title: '지어낸 가', value: '0.2', expectedCo2e: '0.3' },
    { title: '지어낸 나', value: null, expectedCo2e: null },
    { title: '지어낸 다', value: '1e-05', expectedCo2e: '0.6' },
  ];
  const SHEETS = [
    {
      status: 'processed',
      sheet: 'c1',
      category: 'Category1',
      rows: [
        {
          rowId: 'P!2',
          kind: 'purchase',
          co2e: '5',
          factor: {
            title: '지어낸 원안',
            value: '0.1',
            unit: 'kgCO2e/KRW',
            column: '2024\n판',
            source: 'db_keyword',
          },
          recommendations: RECS,
        },
        {
          rowId: 'P!3',
          kind: 'purchase',
          co2e: null,
          factor: {
            title: null,
            value: null,
            unit: 'kgCO2e/KRW',
            column: null,
            source: 'none',
          },
          recommendations: [],
        },
        ...KINDS.map((kind) => ({
          rowId: `K!${kind}`,
          kind,
          co2e: '1',
          factor: { title: 't', value: '1', unit: 'kg', sheet: '지어낸 시트' },
        })),
      ],
    },
    {
      status: 'processed',
      sheet: 'c3',
      category: 'Category3',
      rows: [
        { rowId: 'E!2', kind: 'fuel_energy', co2e: null, factor: null },
        {
          rowId: 'E!3',
          kind: 'fuel_energy',
          co2e: '1',
          factor: { title: 't', value: '1', sheet: '지어낸 시트' },
        },
      ],
    },
    {
      status: 'processed',
      sheet: 'c5',
      category: 'Category5',
      rows: [
        {
          rowId: 'W!2',
          kind: 'waste',
          co2e: '1',
          biogenic: { biogenicCo2e: '0.25', fcf: '0.5' },
          factor: { title: 't', value: '1', unit: 'kg', sheet: '지어낸 시트' },
        },
        {
          rowId: 'W!3',
          kind: 'waste',
          co2e: '1',
          biogenic: { biogenicCo2e: null, fcf: null },
          factor: { title: 't', value: '1', unit: 'kg', sheet: '지어낸 시트' },
        },
      ],
    },
    {
      status: 'processed',
      sheet: 'c12',
      category: 'Category12',
      rows: [
        {
          rowId: 'L!2',
          kind: 'product_eol',
          co2e: '1',
          factor: { title: 't', value: '1', unit: 'kg', sheet: '지어낸 시트' },
        },
      ],
    },
    {
      status: 'processed',
      sheet: 'c15',
      category: 'Category15',
      rows: [{ rowId: 'I!2', kind: 'investment', co2e: '1', factor: null }],
    },
  ];
  const base = { rowId: 'P!2', rank: null, custom: null, reason: '지어낸' };
  const custom = (over: Record<string, unknown>) => ({
    ...base,
    choice: 'custom',
    custom: { title: '지어낸', value: '0.5', source: '지어낸', ...over },
  });
  const pick = (rank: number, rowId = 'P!2') => ({
    ...base,
    rowId,
    choice: 'recommended',
    rank,
  });
  const LONG = '가'.repeat(201);
  const LONGEST = '😀'.repeat(200);
  const { rank: _rank, ...noRank } = base;
  const TABLE: [
    string,
    number,
    string,
    unknown,
    number,
    string | null,
    string[],
  ][] = [
    [
      'rank 키 없음',
      51,
      'C1',
      { ...noRank, choice: 'applied' },
      422,
      'VALIDATION_ERROR',
      ['rank'],
    ],
    [
      '더한 키',
      51,
      'C1',
      { ...base, choice: 'applied', 더한칸: 1 },
      422,
      'VALIDATION_ERROR',
      ['더한칸'],
    ],
    [
      '모르는 고름',
      51,
      'C1',
      { ...base, choice: 'other' },
      422,
      'VALIDATION_ERROR',
      ['choice'],
    ],
    [
      '추천인데 순위 없음',
      51,
      'C1',
      { ...base, choice: 'recommended' },
      422,
      'VALIDATION_ERROR',
      ['rank'],
    ],
    [
      '적용인데 순위',
      51,
      'C1',
      { ...base, choice: 'applied', rank: 1 },
      422,
      'VALIDATION_ERROR',
      ['rank'],
    ],
    ['순위 범위 밖', 51, 'C1', pick(5), 422, 'VALIDATION_ERROR', ['rank']],
    [
      '직접인데 입력 없음',
      51,
      'C1',
      { ...base, choice: 'custom' },
      422,
      'VALIDATION_ERROR',
      ['custom'],
    ],
    [
      '적용인데 입력',
      51,
      'C1',
      { ...custom({}), choice: 'applied' },
      422,
      'VALIDATION_ERROR',
      ['custom'],
    ],
    [
      '값 지수',
      51,
      'C1',
      custom({ value: '1e-3' }),
      422,
      'VALIDATION_ERROR',
      ['custom.value'],
    ],
    [
      '값 음수',
      51,
      'C1',
      custom({ value: '-1' }),
      422,
      'VALIDATION_ERROR',
      ['custom.value'],
    ],
    [
      '값 0',
      51,
      'C1',
      custom({ value: '0.0' }),
      422,
      'VALIDATION_ERROR',
      ['custom.value'],
    ],
    [
      '값 소수 11자리',
      51,
      'C1',
      custom({ value: '0.12345678901' }),
      422,
      'VALIDATION_ERROR',
      ['custom.value'],
    ],
    [
      '값 소수 10자리',
      51,
      'C1',
      custom({ value: '0.1234567890' }),
      200,
      null,
      [],
    ],
    [
      '제목 빈 글',
      51,
      'C1',
      custom({ title: '  ' }),
      422,
      'VALIDATION_ERROR',
      ['custom.title'],
    ],
    [
      '제목 201자',
      51,
      'C1',
      custom({ title: LONG }),
      422,
      'VALIDATION_ERROR',
      ['custom.title'],
    ],
    [
      '제목 200 코드 포인트',
      51,
      'C1',
      custom({ title: LONGEST }),
      200,
      null,
      [],
    ],
    [
      '출처 201자',
      51,
      'C1',
      custom({ source: LONG }),
      422,
      'VALIDATION_ERROR',
      ['custom.source'],
    ],
    [
      '사유 빈 글',
      51,
      'C1',
      { ...base, choice: 'applied', reason: ' ' },
      422,
      'VALIDATION_ERROR',
      ['reason'],
    ],
    [
      '사유 301자',
      51,
      'C1',
      { ...base, choice: 'applied', reason: '가'.repeat(301) },
      422,
      'VALIDATION_ERROR',
      ['reason'],
    ],
    [
      '사유 300 코드 포인트',
      51,
      'C1',
      { ...base, choice: 'applied', reason: '😀'.repeat(300) },
      200,
      null,
      [],
    ],
    ...KINDS.map((kind): (typeof TABLE)[number] => [
      `식 있는 kind ${kind}`,
      51,
      'C1',
      { ...custom({}), rowId: `K!${kind}` },
      200,
      null,
      [],
    ]),
    [
      '없는 실행',
      99,
      'C1',
      { ...base, choice: 'applied' },
      404,
      'NOT_FOUND',
      [],
    ],
    [
      '없는 카테고리',
      51,
      'C10',
      { ...base, choice: 'applied' },
      404,
      'NOT_FOUND',
      [],
    ],
    [
      '옛 실행은 줄을 보기 전에 stale',
      50,
      'C1',
      { ...base, rowId: '없음', choice: 'applied' },
      409,
      'STALE_RUN',
      [],
    ],
    [
      '없는 줄(단수 rowId)',
      51,
      'C1',
      { ...base, rowId: '없음', choice: 'applied' },
      422,
      'VALIDATION_ERROR',
      ['rowId'],
    ],
    [
      '계수 객체 없음',
      51,
      'C3',
      { ...base, rowId: 'E!2', choice: 'applied' },
      409,
      'FACTOR_NOT_EDITABLE',
      [],
    ],
    [
      '단위 없음',
      51,
      'C3',
      { ...base, rowId: 'E!3', choice: 'applied' },
      409,
      'FACTOR_NOT_EDITABLE',
      [],
    ],
    [
      '식 없는 C12',
      51,
      'C12',
      { ...base, rowId: 'L!2', choice: 'applied' },
      409,
      'FACTOR_NOT_EDITABLE',
      [],
    ],
    [
      '식 없는 C15',
      51,
      'C15',
      { ...base, rowId: 'I!2', choice: 'applied' },
      409,
      'FACTOR_NOT_EDITABLE',
      [],
    ],
    [
      '409 가 없는 순위보다 앞',
      51,
      'C12',
      pick(1, 'L!2'),
      409,
      'FACTOR_NOT_EDITABLE',
      [],
    ],
    ['없는 순위', 51, 'C1', pick(4), 422, 'VALIDATION_ERROR', ['rank']],
    ['값 null 순위', 51, 'C1', pick(2), 422, 'VALIDATION_ERROR', ['rank']],
    [
      '추천 없는 줄',
      51,
      'C1',
      pick(1, 'P!3'),
      422,
      'VALIDATION_ERROR',
      ['rank'],
    ],
    [
      '값 null 줄은 받는다',
      51,
      'C1',
      { ...custom({}), rowId: 'P!3' },
      200,
      null,
      [],
    ],
    ['셋째 자리 추천', 51, 'C1', pick(3), 200, null, []],
  ];
  const fresh = () => {
    const result = fakeDoneResult({ sheets: SHEETS });
    return fakeScope3Server({
      runs: [
        { id: 50, status: 'done', reportYear: 2025, result },
        { id: 51, status: 'done', reportYear: 2025, result },
      ],
    });
  };
  const post = async (
    server: ReturnType<typeof fakeScope3Server>,
    run: number,
    category: string,
    body: unknown,
  ) => {
    const answer = await server.send(
      new Request(
        `http://test.local/api/inventory/scope3/runs/${run}/categories/${category}/factors`,
        { method: 'POST', body: JSON.stringify(body) },
      ),
    );
    return {
      status: answer.status,
      body: (await answer.json()) as Record<string, any>,
    };
  };
  const factorOf = (reply: { body: Record<string, any> }) =>
    reply.body.rows[0].factor as Record<string, unknown>;

  it.each(TABLE)('%s', async (_, run, category, body, status, code, fields) => {
    const reply = await post(fresh(), run, category, body);
    expect(reply.status).toBe(status);
    expect(reply.body.error?.code ?? null).toBe(code);
    expect(Object.keys(reply.body.error?.fields ?? {}).sort()).toEqual(fields);
  });

  it('잠김은 줄을 보기 전이고 몸 422 뒤다', async () => {
    const result = fakeDoneResult({ sheets: SHEETS });
    const server = fakeScope3Server({
      runs: [{ id: 51, status: 'done', reportYear: 2025, result }],
      locks: [{ year: 2025, category: 'C1', runId: 51 }],
    });
    const missing = { ...base, rowId: '없음', choice: 'applied' };
    expect((await post(server, 51, 'C1', missing)).body.error.code).toBe(
      'LOCKED',
    );
    expect(
      (await post(server, 51, 'C1', { ...missing, reason: ' ' })).status,
    ).toBe(422);
  });

  it('직접 입력: 값은 repr 꼴 · 글은 걷음 · 단위·AI 원안은 그 줄에서', async () => {
    for (const [sent, kept] of [
      ['0.50', '0.5'],
      ['2', '2.0'],
      ['0.00001', '1e-05'],
    ] as const) {
      const reply = await post(
        fresh(),
        51,
        'C1',
        custom({ value: sent, title: ' 가 ', source: ' 나 ' }),
      );
      expect(factorOf(reply)).toEqual({
        choice: 'custom',
        rank: null,
        title: '가',
        value: kept,
        source: '나',
        unit: 'kgCO2e/KRW',
        co2e: '7.25',
        biogenicCo2e: null,
        ai: {
          title: '지어낸 원안',
          value: '0.1',
          source: '지어낸 계수표 2024 판',
          co2e: '5',
        },
      });
    }
  });

  it('추천: 그 순위의 제목·값 글자 그대로 · 출처는 AI 원안 출처', async () => {
    expect(factorOf(await post(fresh(), 51, 'C1', pick(3)))).toMatchObject({
      choice: 'recommended',
      rank: 3,
      title: '지어낸 다',
      value: '1e-05',
      source: '지어낸 계수표 2024 판',
    });
  });

  it('적용: 고친 뒤 되돌리면 AI 원안 값 · 생물기원은 줄의 값', async () => {
    const server = fresh();
    const rowId = 'W!2';
    await post(server, 51, 'C5', { ...custom({}), rowId });
    const back = await post(server, 51, 'C5', {
      ...base,
      rowId,
      choice: 'applied',
    });
    expect(factorOf(back)).toEqual({
      choice: 'applied',
      rank: null,
      title: 't',
      value: '1',
      source: '지어낸 시트',
      unit: 'kg',
      co2e: '1',
      biogenicCo2e: '0.25',
      ai: { title: 't', value: '1', source: '지어낸 시트', co2e: '1' },
    });
  });

  it('생물기원: 폐기물 줄만 새로 오고 FCF 가 없으면 「0.0」 · 구매 줄은 null', async () => {
    const of = async (rowId: string, category: string) =>
      factorOf(await post(fresh(), 51, category, { ...custom({}), rowId }))
        .biogenicCo2e;
    expect(await of('W!2', 'C5')).toBe('0.75');
    expect(await of('W!3', 'C5')).toBe('0.0');
    expect(await of('P!2', 'C1')).toBeNull();
  });
});

describe('★ 가짜 ↔ openapi(generated/openapi.json)', () => {
  type Schema = Record<string, unknown>;
  const here = dirname(fileURLToPath(import.meta.url));
  const openapi = JSON.parse(
    readFileSync(
      resolve(here, '../../../../../api-py/generated/openapi.json'),
      'utf8',
    ),
  ) as {
    paths: Record<string, Record<string, Schema>>;
    components: { schemas: Record<string, Schema> };
  };
  const schemas = openapi.components.schemas;
  const deref = (schema: Schema): Schema => {
    const ref = schema.$ref;
    return typeof ref === 'string' ?
        deref(schemas[ref.replace('#/components/schemas/', '')]!)
      : schema;
  };
  const kindOf = (value: unknown) =>
    value === null ? 'null'
    : Array.isArray(value) ? 'array'
    : Number.isInteger(value) ? 'integer'
    : typeof value;

  /** 값을 스키마 따라 걸어 내려가며 어긋난 곳(경로)을 모은다. 객체는 칸 집합이 같아야 한다(⊆ 아님). */
  function gaps(
    value: unknown,
    raw: Schema,
    at: string,
    kinds: Set<string>,
  ): string[] {
    const schema = deref(raw);
    const union = (schema.oneOf ?? schema.anyOf) as Schema[] | undefined;
    if (union) {
      const disc = schema.discriminator as
        { propertyName: string; mapping: Record<string, string> } | undefined;
      if (disc) {
        const tag = (value as Schema | null)?.[disc.propertyName];
        const target = disc.mapping[String(tag)];
        if (!target) return [`${at}: 판별 ${String(tag)} 없음`];
        return gaps(value, { $ref: target }, at, kinds);
      }
      for (const one of union) {
        const tried = gaps(value, one, at, new Set());
        if (tried.length === 0) return gaps(value, one, at, kinds);
      }
      return [`${at}: 어느 갈래에도 안 맞음`];
    }
    if ('const' in schema && value !== schema.const)
      return [`${at}: const ${String(schema.const)} ≠ ${String(value)}`];
    if (Array.isArray(schema.enum) && !schema.enum.includes(value))
      return [`${at}: enum 밖 ${String(value)}`];
    const type = schema.type;
    const kind = kindOf(value);
    if (
      type === 'number' ?
        kind !== 'integer' && kind !== 'number'
      : type !== kind
    )
      return [`${at}: ${String(type)} ≠ ${kind}`];
    if (type === 'array')
      return (value as unknown[]).flatMap((item, i) =>
        gaps(item, schema.items as Schema, `${at}[${i}]`, kinds),
      );
    if (
      schema.format === 'date-time' &&
      Number.isNaN(Date.parse(value as string))
    )
      return [`${at}: date-time 아님 ${String(value)}`];
    if (type !== 'object') return [];
    const object = value as Schema;
    const properties = schema.properties as Record<string, Schema> | undefined;
    if (!properties)
      return Object.entries(object).flatMap(([key, one]) =>
        gaps(one, schema.additionalProperties as Schema, `${at}.${key}`, kinds),
      );
    if (typeof object.kind === 'string') kinds.add(object.kind);
    // S3W2c: 칸 = required 는 다 있음 + properties 밖 칸 0(줄의 NotRequired input 하나 — 옛 결과 줄). 다른 객체는 required 가
    //   properties 전부라 그대로 같음이다(input 은 S3R3 부터 required 열다섯 + 선택 useMonths — 닫힘). 줄 쪽은 아래 시험이 넓어지지 않았음을 본다.
    const required = ((schema.required as string[] | undefined) ?? []).sort();
    const want = Object.keys(properties).sort();
    const have = Object.keys(object).sort();
    const missing = required.filter((key) => !have.includes(key));
    const unknown = have.filter((key) => !want.includes(key));
    if (missing.length > 0 || unknown.length > 0)
      return [`${at}: 칸 ${have.join(',')} ≠ ${want.join(',')}`];
    return have.flatMap((key) =>
      gaps(object[key], properties[key]!, `${at}.${key}`, kinds),
    );
  }
  const resultSchema = (
    openapi.paths['/inventory/scope3/runs/{run_id}/result']!.get!
      .responses as Record<string, { content: Record<string, Schema> }>
  )['200']!.content['application/json']!.schema as Schema;
  /** S3Q1 가짜의 첫 C12 줄 treatments. */
  const firstTreatments = (body: Schema) =>
    (body.sheets as { rows: Schema[] }[])[0]!.rows[0]!.treatments as Schema;
  const ROW_KINDS = [
    'purchase',
    'transport_spend',
    'travel_spend',
    'waste',
    'transport_distance',
    'travel_distance',
    'commute',
    'fuel_energy',
    'leased_asset',
    'leased_out_asset',
    'product_use',
    'product_eol',
    'franchise',
    'investment',
  ];

  it('걸음 자체: 칸 하나 더함·뺌·이름 틀림·const·enum 밖은 빨강', () => {
    expect(gaps(fakeDoneResult(), resultSchema, '$', new Set())).toEqual([]);
    const plants: ((row: Schema) => void)[] = [
      (row) => (row.extra = 1),
      (row) => delete row.spendNote,
      (row) => {
        row.spend_note = row.spendNote;
        delete row.spendNote;
      },
      (row) => (row.unit = 'kgCO2eq'),
      (row) =>
        ((row.group as Schema).llm = {
          outcome: 'maybe',
          answer: '',
          reason: null,
        }),
    ];
    for (const plant of plants) {
      const body = fakeDoneResult();
      plant((body.sheets as { rows: Schema[] }[])[0]!.rows[0]!);
      expect(gaps(body, resultSchema, '$', new Set())).not.toEqual([]);
    }
  });

  it('S3W2c·S3R3·S3Q1 걸음: 줄에서 빠져도 되는 칸은 NotRequired 인 input(에너지 줄은 S3Q1 treatments 더) · input 안은 required 열다섯 + 선택 useMonths 하나 · 밖 키 0', () => {
    const row = (name: string) =>
      deref({ $ref: `#/components/schemas/${name}` });
    const expected: Record<string, string[]> = {
      ColabRowJson: ['input'],
      ColabActivityRowJson: ['input'],
      ColabEnergyRowJson: ['input', 'treatments'], // S3Q1: C12 처리방법별 칸(product_eol 만)
    };
    for (const [name, want] of Object.entries(expected)) {
      const schema = row(name);
      const optional = Object.keys(schema.properties as Schema)
        .filter((key) => !(schema.required as string[]).includes(key))
        .sort();
      expect(optional, name).toEqual(want);
    }
    const input = row('ColabRowInputJson');
    expect(input.additionalProperties).toBe(false);
    const inputOptional = Object.keys(input.properties as Schema).filter(
      (key) => !(input.required as string[]).includes(key),
    );
    expect(inputOptional).toEqual(['useMonths']);
    expect([...(input.required as string[])].sort()).toEqual(
      Object.keys(input.properties as Schema)
        .filter((key) => key !== 'useMonths')
        .sort(),
    );
    expect(Object.keys(input.properties as Schema)).toHaveLength(16);
    expect(input.required as string[]).toHaveLength(15);
    const plants: ((input: Schema) => void)[] = [
      (input) => delete input.stores,
      (input) => (input.extra = null),
      (input) => (input.people = 3),
      (input) => (input.useMonths = 18),
      (input) => {
        input.usemonths = input.useMonths;
        delete input.useMonths;
      },
    ];
    for (const plant of plants) {
      const body = fakeDoneResult();
      const first = (body.sheets as { rows: Schema[] }[])[0]!.rows[0]!;
      first.input = { ...(first.input as Schema) };
      plant(first.input as Schema);
      expect(gaps(body, resultSchema, '$', new Set())).not.toEqual([]);
    }
    // 키 열다섯 줄(S3R3 앞 저장 — useMonths 없음)은 맞다.
    const fifteen = fakeDoneResult();
    const firstRow = (fifteen.sheets as { rows: Schema[] }[])[0]!.rows[0]!;
    firstRow.input = fifteenKeyInput(firstRow.input as Schema);
    expect(gaps(fifteen, resultSchema, '$', new Set())).toEqual([]);
    // 옛 줄(input 없음)은 맞다 — 그 밖 칸 하나를 빼면 빨강.
    const old = fakeDoneResult();
    const rows = (old.sheets as { rows: Schema[] }[])[0]!.rows;
    rows[0] = withoutInput(rows[0]!);
    expect(gaps(old, resultSchema, '$', new Set())).toEqual([]);
    delete rows[0]!.missing;
    expect(gaps(old, resultSchema, '$', new Set())).not.toEqual([]);
  });

  it('S3R3 ★ 가짜 input 은 일부러 둔 키 열다섯 옛 줄(상세 C11) 하나 빼고 전부 키 열여섯(useMonths 를 통째 빠뜨리면 빨강)', () => {
    const inputs = [
      fakeDoneResult(),
      fakeAllShapesResult(),
      fakeDetailResult(),
    ].flatMap((body) =>
      (body.sheets as { rows?: Schema[] }[]).flatMap((sheet) =>
        (sheet.rows ?? []).flatMap((one) =>
          one.input ? [one.input as Schema] : [],
        ),
      ),
    );
    const sizes = inputs.map((one) => Object.keys(one).length);
    expect(sizes.filter((size) => size === 15)).toHaveLength(1);
    expect(sizes.filter((size) => size !== 15 && size !== 16)).toEqual([]);
    expect(sizes.filter((size) => size === 16).length).toBeGreaterThan(20);
  });

  it('S3W2c: 상세 가짜에 input 있는 줄과 없는 줄(옛)이 둘 다 있다', () => {
    const rows = (fakeDetailResult().sheets as { rows?: Schema[] }[]).flatMap(
      (sheet) => sheet.rows ?? [],
    );
    expect(rows.some((one) => 'input' in one)).toBe(true);
    expect(rows.some((one) => !('input' in one))).toBe(true);
  });

  it('S3W4: 가짜 그룹 단계는 셋 갈래를 다 갖고 · 남의 줄 enum 은 빨강(구매 줄 mapping · 활동 줄 group)', () => {
    for (const body of [fakeAllShapesResult(), fakeDetailResult()]) {
      const rows = (body.sheets as { rows?: Schema[] }[]).flatMap(
        (sheet) => sheet.rows ?? [],
      );
      const origins = rows.flatMap((one) =>
        (one.originSteps as Schema[])
          .filter((step) => step.step === 'group')
          .map((step) => step.origin),
      );
      expect([...new Set(origins)].sort()).toEqual(['ai', 'estimate', 'rule']);
      for (const one of rows) {
        const steps = (one.originSteps as Schema[]).map((step) => step.step);
        if (one.kind === 'purchase') expect(steps).toContain('group');
        else expect(steps).not.toContain('group');
      }
      expect(
        rows.some(
          (one) => (one.biogenic as Schema | null)?.note === '해당없음',
        ),
      ).toBe(true);
      expect(rows.some((one) => one.formula === '')).toBe(true);
    }
    const swapped: [Schema, string][] = [
      [purchaseRow('1'), 'mapping'],
      [activityRow('waste', '1'), 'group'],
      [energyRow('product_eol', '1'), 'group'],
    ];
    for (const [row, step] of swapped) {
      const wrong = {
        ...row,
        originSteps: [{ step, origin: 'ai', via: '지어낸' }],
      };
      const body = fakeDoneResult({
        sheets: [processedSheet('s', 'Category1', [wrong])],
      });
      expect(gaps(body, resultSchema, '$', new Set())).not.toEqual([]);
    }
  });

  it('결과 본문 넷(기본·모든 꼴·거절)의 칸 = openapi · 시트 다섯 갈래 · 줄 kind 열넷', () => {
    const kinds = new Set<string>();
    for (const body of [
      fakeDoneResult(),
      fakeAllShapesResult(),
      fakeDetailResult(),
      fakeRejectedResult(),
      fakeRejectedResult('legacy_template'),
    ])
      expect(gaps(body, resultSchema, '$', kinds)).toEqual([]);
    expect([...kinds].sort()).toEqual([...ROW_KINDS].sort());
    const statuses = new Set(
      (fakeAllShapesResult().sheets as Schema[]).map((s) => s.status),
    );
    expect([...statuses].sort()).toEqual([
      'empty',
      'failed',
      'not_target',
      'not_yet_supported',
      'processed',
    ]);
  });

  it('S3Q1 ★ 새 칸 가짜(treatments 갈래 넷·옛 줄 · sourceText 있음/없음)의 칸 = openapi · 「기타」·칸 더함·sourceText 수는 빨강(openapi 는 treatments 를 에너지 줄 꼴 전부에 열어 둔다 — product_eol 만 읽는 것은 파서 몫)', () => {
    const body = fakeS3Q1Result();
    expect(gaps(body, resultSchema, '$', new Set())).toEqual([]);
    const rows = (body.sheets as { rows: Schema[] }[]).flatMap(
      (sheet) => sheet.rows,
    );
    const branches = rows
      .map((row) => (row.treatments as Schema | undefined)?.branch)
      .filter((one) => one !== undefined);
    expect(new Set(branches)).toEqual(new Set(['code', 'name', 'average']));
    expect(
      rows.some((row) => row.kind === 'product_eol' && !('treatments' in row)),
    ).toBe(true);
    const sources = rows.map((row) => 'sourceText' in (row.factor as Schema));
    expect(sources).toContain(true);
    expect(sources).toContain(false);
    const plants: ((body: Schema) => void)[] = [
      (one) =>
        ((firstTreatments(one).parts as Schema[])[0]!.treatment = '기타'),
      (one) => ((firstTreatments(one).parts as Schema[])[0]!.used = 'true'),
      (one) => (firstTreatments(one).extra = 1),
      (one) => (firstTreatments(one).branch = 'other'),
      (one) =>
        ((
          (one.sheets as { rows: Schema[] }[])[1]!.rows[0]!.factor as Schema
        ).sourceText = 3),
    ];
    for (const plant of plants) {
      const one = fakeS3Q1Result();
      plant(one);
      expect(gaps(one, resultSchema, '$', new Set())).not.toEqual([]);
    }
  });

  it('S3Q1 ★ 원본 경로가 openapi 에 있고 가짜의 Content-Type 은 그 경로의 200 content 안 · 이름 머리는 실어댑터가 읽는 꼴', async () => {
    const op = openapi.paths['/inventory/scope3/runs/{run_id}/original']!.get!;
    expect(op.operationId).toBe('inventory_scope3_original_get');
    const content = Object.keys(
      (op.responses as Record<string, { content: Schema }>)['200']!.content,
    ).sort();
    expect(content).toEqual(
      [
        XLSX_MEDIA_TYPE,
        'application/vnd.ms-excel',
        'application/octet-stream',
      ].sort(),
    );
    for (const name of ['가짜 원본.xlsx', 'plain.XLS', 'noext', 'a"b.csv']) {
      expect(content).toContain(originalMediaType(name));
      expect(fileNameFromDisposition(attachmentOf(name))).toBe(name);
    }
    const server = fakeScope3Server({
      runs: [{ id: 9, status: 'done', reportYear: 2025, documentId: 77 }],
    });
    const answer = await server.send(
      new Request('http://test.local/api/inventory/scope3/runs/9/original'),
    );
    expect(content).toContain(answer.headers.get('Content-Type'));
    expect(answer.headers.get('Content-Disposition')).toBe(
      "attachment; filename*=utf-8''%EC%A7%80%EC%96%B4%EB%82%B8.xlsx",
    );
  });

  it('가짜 서버가 내는 결과 본문도 그대로(200 의 json)', async () => {
    const server = fakeScope3Server({
      runs: [{ id: 7, status: 'done', reportYear: 2025 }],
    });
    const response = await server.send(
      new Request('http://test.local/api/inventory/scope3/runs/7/result'),
    );
    expect(gaps(await response.json(), resultSchema, '$', new Set())).toEqual(
      [],
    );
  });

  it('RunOut 칸 집합 = openapi RunOut.properties · errorCode ∈ 표 · failedStep ∈ c1…·assemble', () => {
    const runOut = schemas.RunOut!;
    const want = Object.keys(runOut.properties as object).sort();
    const steps = /^(c([1-9]|1[0-5])|assemble)$/;
    for (const errorCode of FAKE_ERROR_CODES) {
      const server = fakeScope3Server({
        runs: [
          { id: 1, status: 'failed', reportYear: 2025, errorCode },
          { id: 2, status: 'done', reportYear: 2025 },
        ],
      });
      for (const run of server.runs()) {
        expect(Object.keys(run).sort()).toEqual(want);
        // RunOut.steps: 선언 차례 열다섯 · RunStepOut 칸 다섯.
        const stepOut = schemas.RunStepOut!;
        const stepKeys = Object.keys(stepOut.properties as object).sort();
        const list = run.steps as Record<string, unknown>[];
        expect(list.map((one) => one.step)).toEqual([...RUN_STEP_NAMES]);
        for (const one of list) {
          expect(Object.keys(one).sort()).toEqual(stepKeys);
          expect(RUN_STEP_STATUSES).toContain(one.status);
        }
        if (run.status === 'failed') {
          expect(run.errorCode).toBe(errorCode);
          expect(run.errorMessage).toBe(FAKE_ERROR_MESSAGE);
          if (run.failedStep !== null) expect(run.failedStep).toMatch(steps);
        }
      }
    }
    expect(() =>
      fakeScope3Server({
        runs: [
          {
            id: 1,
            status: 'failed',
            reportYear: 2025,
            errorCode: 'step_failed',
          },
        ],
      }),
    ).toThrow();
  });

  // ★ S3W3a: 새 경로 여덟의 성공 답을 openapi 와 걷는다(상태 번호 포함). factor 값·null 둘 다.
  const SCHEMA_OF = (path: string, method: string) =>
    (
      openapi.paths[path]![method]!.responses as Record<
        string,
        { content: Record<string, Schema> }
      >
    )['200']!.content['application/json']!.schema as Schema;
  const Y = '/inventory/scope3/years/{year}';
  const LOCK = `${Y}/categories/{category}/lock`;
  const R = '/inventory/scope3/runs/{run_id}';
  const seeded = (operator = false) =>
    fakeScope3Server({
      operator,
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet('C1_지어낸', 'Category1', [
                purchaseRow('1.5', 'C1!2'),
                purchaseRow('2.5', 'C1!3'),
                purchaseRow('3.5', 'C1!4'),
              ]),
              failedSheet('C2_지어낸', 'Category2'),
            ],
          }),
          edits: [
            { rowId: 'C1!2', category: 'C1', excluded: true },
            { rowId: 'C1!3', category: 'C1', factor: fakeRowFactor() },
            { rowId: 'C1!4', category: 'C1', excluded: true, by: null },
          ],
        },
      ],
    });
  const call = async (
    server: ReturnType<typeof fakeScope3Server>,
    method: string,
    path: string,
    body?: unknown,
  ) => {
    const response = await server.send(
      new Request(`http://test.local/api${path}`, {
        method,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      }),
    );
    return { status: response.status, body: (await response.json()) as Schema };
  };
  const ROWS = '/inventory/scope3/runs/7/categories/C1';
  const walks: [string, string, string, unknown, string, string][] = [
    ['연도', 'GET', '/inventory/scope3/years/2025', undefined, Y, 'get'],
    [
      '사건 없는 해',
      'GET',
      '/inventory/scope3/years/2024',
      undefined,
      Y,
      'get',
    ],
    [
      '덧판',
      'GET',
      '/inventory/scope3/runs/7/edits',
      undefined,
      `${R}/edits`,
      'get',
    ],
    [
      '히스토리',
      'GET',
      '/inventory/scope3/runs/7/history',
      undefined,
      `${R}/history`,
      'get',
    ],
    [
      '제외',
      'POST',
      `${ROWS}/exclusions`,
      { rowIds: ['C1!3'], reason: '지어낸' },
      `${R}/categories/{category}/exclusions`,
      'post',
    ],
    [
      '복구',
      'POST',
      `${ROWS}/restorations`,
      { rowIds: ['C1!2'], reason: '지어낸' },
      `${R}/categories/{category}/restorations`,
      'post',
    ],
    [
      '계수',
      'POST',
      `${ROWS}/factors`,
      {
        rowId: 'C1!4',
        choice: 'recommended',
        rank: 2,
        custom: null,
        reason: '지어낸',
      },
      `${R}/categories/{category}/factors`,
      'post',
    ],
    [
      '잠그기',
      'POST',
      '/inventory/scope3/years/2025/categories/C1/lock?runId=7',
      undefined,
      LOCK,
      'post',
    ],
    [
      '풀기',
      'DELETE',
      '/inventory/scope3/years/2025/categories/C1/lock',
      undefined,
      LOCK,
      'delete',
    ],
  ];
  it.each(walks)(
    'S3W3a 가짜 답 = openapi 200: %s',
    async (_, method, url, body, path, verb) => {
      const server = seeded(true);
      const answer = await call(server, method, url, body);
      expect(answer.status).toBe(200);
      expect(gaps(answer.body, SCHEMA_OF(path, verb), '$', new Set())).toEqual(
        [],
      );
    },
  );

  it('S3W3a 걸음이 factor 값·null 둘 다 지나고, 칸을 빼면 빨강(factor·batchId·by required · kind·choice enum)', async () => {
    const server = seeded();
    const { body: edits } = await call(
      server,
      'GET',
      '/inventory/scope3/runs/7/edits',
    );
    const rows = edits.rows as Schema[];
    expect(rows.some((row) => row.factor === null)).toBe(true);
    expect(rows.some((row) => row.factor !== null)).toBe(true);
    const editsSchema = SCHEMA_OF(`${R}/edits`, 'get');
    const noFactor = structuredClone(edits);
    delete (noFactor.rows as Schema[])[0]!.factor;
    expect(gaps(noFactor, editsSchema, '$', new Set())).not.toEqual([]);
    const badChoice = structuredClone(edits);
    (
      (badChoice.rows as Schema[]).find((row) => row.factor)!.factor as Schema
    ).choice = 'ai';
    expect(gaps(badChoice, editsSchema, '$', new Set())).not.toEqual([]);

    const { body: page } = await call(
      server,
      'GET',
      '/inventory/scope3/runs/7/history',
    );
    const lines = page.results as Schema[];
    expect(lines.some((line) => line.factor === null)).toBe(true);
    expect(lines.some((line) => line.factor !== null)).toBe(true);
    const historySchema = SCHEMA_OF(`${R}/history`, 'get');
    for (const key of ['factor', 'batchId', 'by']) {
      const bad = structuredClone(page);
      delete (bad.results as Schema[])[0]![key];
      expect(gaps(bad, historySchema, '$', new Set())).not.toEqual([]);
    }
    const badKind = structuredClone(page);
    (badKind.results as Schema[])[0]!.kind = 'edit';
    expect(gaps(badKind, historySchema, '$', new Set())).not.toEqual([]);
  });

  it('S3W3a 쓰기로 생긴 사건도 히스토리 걸음을 지난다 — 세 갈래가 다 나온다', async () => {
    const server = seeded();
    await call(server, 'POST', `${ROWS}/exclusions`, {
      rowIds: ['C1!3'],
      reason: '지어낸',
    });
    await call(server, 'POST', `${ROWS}/restorations`, {
      rowIds: ['C1!2'],
      reason: '지어낸',
    });
    await call(server, 'POST', `${ROWS}/factors`, {
      rowId: 'C1!4',
      choice: 'custom',
      rank: null,
      custom: { title: '지어낸', value: '0.5', source: '지어낸' },
      reason: '지어낸',
    });
    const { body: page } = await call(
      server,
      'GET',
      '/inventory/scope3/runs/7/history',
    );
    expect(
      gaps(page, SCHEMA_OF(`${R}/history`, 'get'), '$', new Set()),
    ).toEqual([]);
    expect(
      [...new Set((page.results as Schema[]).map((one) => one.kind))].sort(),
    ).toEqual(['exclude', 'factor', 'restore']);
  });

  it.each([
    ['403', 'DELETE', '/inventory/scope3/years/2025/categories/C1/lock', 403],
    ['404', 'GET', '/inventory/scope3/runs/404/edits', 404],
    [
      '409',
      'POST',
      '/inventory/scope3/years/2025/categories/C2/lock?runId=7',
      409,
    ],
  ] as const)(
    'S3W3a 가짜 거절 몸 %s = openapi ErrorBody',
    async (_, method, url, status) => {
      const answer = await call(seeded(), method, url);
      expect(answer.status).toBe(status);
      expect(gaps(answer.body, schemas.ErrorBody!, '$', new Set())).toEqual([]);
    },
  );

  it('S3W3a 파서가 가짜 답을 다 읽는다 — 꼴이 어긋나면 파서가 먼저 빨강', async () => {
    const server = seeded();
    const port = portOf(server);
    expect((await port.year(2025)).kind).toBe('ok');
    expect((await port.edits('7')).kind).toBe('ok');
    expect((await port.history('7')).kind).toBe('ok');
  });

  it('S3W3a 요청 몸: factor 세 갈래가 Scope3RowEditFactorIn required 다섯을 싣고 칸이 맞다', async () => {
    const server = seeded();
    const port = portOf(server);
    const inputs: RowFactorInput[] = [
      { rowId: 'C1!4', reason: '지어낸', choice: 'applied' },
      { rowId: 'C1!4', reason: '지어낸', choice: 'recommended', rank: 1 },
      {
        rowId: 'C1!4',
        reason: '지어낸',
        choice: 'custom',
        custom: { title: '지어낸', value: '0.5', source: '지어낸' },
      },
    ];
    for (const input of inputs) await port.factor('7', 'C1', input);
    const schema = { $ref: '#/components/schemas/Scope3RowEditFactorIn' };
    const sent = server.bodies(`POST ${ROWS}/factors`) as Schema[];
    expect(sent).toHaveLength(3);
    const required = (deref(schema).required as string[]).sort();
    expect(required).toEqual(['choice', 'custom', 'rank', 'reason', 'rowId']);
    for (const body of sent) {
      expect(Object.keys(body).sort()).toEqual(required);
      expect(gaps(body, schema, '$', new Set())).toEqual([]);
    }
  });

  it('가짜 errorCode 표 = api-py errors.py RUN_ERROR_MESSAGES 의 열쇠(서버가 code 를 더하면 빨강)', () => {
    const source = readFileSync(
      resolve(here, '../../../../../api-py/esgapi/runs/calc/errors.py'),
      'utf8',
    );
    const block = /RUN_ERROR_MESSAGES[^{]*\{([\s\S]*?)\n\}/.exec(source)![1]!;
    const keys = [...block.matchAll(/^\s*"([a-z_]+)":/gm)].map((m) => m[1]);
    expect([...FAKE_ERROR_CODES].sort()).toEqual(keys.sort());
  });
});

describe('S3Q1 original — GET /inventory/scope3/runs/{id}/original(올린 엑셀 그대로)', () => {
  it('올린 바이트·올린 이름 그대로 · 실행 상태는 보지 않는다(queued 도)', async () => {
    const { server, port } = setup();
    const up = await port.upload(xlsx(4), 2025);
    if (up.kind !== 'ok') throw new Error(up.kind);
    const made = await port.start(up.value.documentId, 2025);
    if (made.kind !== 'ok') throw new Error(made.kind);
    const outcome = await port.original(made.value.runId);
    if (outcome.kind !== 'ok') throw new Error(outcome.kind);
    expect(new Uint8Array(await outcome.value.blob.arrayBuffer())).toEqual(
      new Uint8Array(4).fill(7),
    );
    expect(outcome.value.fileName).toBe('지어낸 입력.xlsx');
    expect(
      server.count(`GET /inventory/scope3/runs/${made.value.runId}/original`),
    ).toBe(1);
  });

  it('시드 문서는 지어낸 바이트 · 문서 없는 실행·없는 실행·다른 모듈은 notFound · 끊김 failed · 회사 거절 refused · 이름 머리 없으면 ORIGINAL_FILE_NAME', async () => {
    const { server, port } = setup({
      runs: [
        { id: 9, status: 'done', reportYear: 2025, documentId: 77 },
        { id: 10, status: 'done', reportYear: 2025 },
        {
          id: 11,
          status: 'done',
          reportYear: 2025,
          documentId: 78,
          module: 'dataverify',
        },
      ],
    });
    const seeded = await port.original('9');
    if (seeded.kind !== 'ok') throw new Error(seeded.kind);
    expect(new Uint8Array(await seeded.value.blob.arrayBuffer())).toEqual(
      FAKE_ORIGINAL_BYTES,
    );
    expect(seeded.value.fileName).toBe('지어낸.xlsx');
    expect(await port.original('10')).toEqual({ kind: 'notFound' });
    expect(await port.original('11')).toEqual({ kind: 'notFound' });
    expect(await port.original('999')).toEqual({ kind: 'notFound' });
    expect(await port.original('x')).toEqual({ kind: 'failed' });
    server.override['GET /inventory/scope3/runs/9/original'] = [
      () => new Response(FAKE_ORIGINAL_BYTES, { status: 200 }),
      unreachable,
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
    ];
    const bare = await port.original('9');
    expect(bare.kind === 'ok' && bare.value.fileName).toBe(ORIGINAL_FILE_NAME);
    expect(await port.original('9')).toEqual({ kind: 'failed' });
    expect(await port.original('9')).toEqual({
      kind: 'refused',
      company: 'ambiguous',
    });
  });
});

describe('S3Q1 result — 출처 글 sourceText · C12 처리방법별 칸 treatments(손 거름)', () => {
  const rowsOf = (body: unknown) => {
    const result = resultOf(body);
    if (result?.status !== 'done') throw new Error('done 아님');
    return result.sheets.flatMap((sheet) =>
      sheet.status === 'processed' ? sheet.rows : [],
    );
  };
  const factorSource = (row: ResultRow) =>
    row.detail.shape === 'basic' ? undefined : row.detail.factor?.source;
  const treatmentsOf = (row: ResultRow) =>
    row.detail.shape === 'energy' ? row.detail.treatments : undefined;

  it('활동·에너지 줄 출처 = sourceText(있으면) · 없거나 글이 아니거나 빈 글이면 sheet 글자 · 줄은 떨구지 않는다', () => {
    const rows = rowsOf(fakeS3Q1Result());
    expect(rows.map(factorSource).slice(5)).toEqual([
      FAKE_C3_NOTE,
      '에너지_C3',
      FAKE_SOURCE_TEXT,
    ]);
    for (const odd of [3, '', '  ', null]) {
      const body = fakeDoneResult({
        sheets: [
          processedSheet('c5_지어낸', 'Category5', [
            activityRow('waste', '5', '0.25', 'c5_지어낸!3', {
              factor: {
                title: 't',
                value: '1',
                unit: 'kg',
                column: null,
                sheet: '지어낸 시트',
                code: null,
                sourceText: odd,
              },
            }),
          ]),
        ],
      });
      const [row] = rowsOf(body);
      expect(row!.detail.shape, String(odd)).toBe('activity');
      expect(factorSource(row!)).toBe('지어낸 시트');
    }
  });

  it('treatments: 갈래·서버 글자 그대로 · code 는 줄 factor.code · 옛 줄은 칸 없음', () => {
    const rows = rowsOf(fakeS3Q1Result());
    expect(treatmentsOf(rows[0]!)).toEqual({
      branch: 'code',
      shareTotal: '1.0',
      code: FAKE_C12_CODE,
      parts: [
        { treatment: '매립', share: '0.1', factor: '0.013', used: true },
        { treatment: '소각', share: '0.125', factor: '3.4', used: true },
        { treatment: '재활용', share: '0.775', factor: '0.0186', used: true },
      ],
    });
    expect(treatmentsOf(rows[1]!)?.code).toBeNull();
    expect(treatmentsOf(rows[2]!)).toMatchObject({
      branch: 'average',
      shareTotal: null,
    });
    expect(treatmentsOf(rows[3]!)?.parts[0]).toEqual({
      treatment: '매립',
      share: null,
      factor: '0.013',
      used: true,
    });
    expect(treatmentsOf(rows[4]!)).toBeUndefined();
    expect(rows[4]!.detail.shape).toBe('energy');
  });

  it('treatments 꼴이 틀리면 그 칸만 없음(줄은 그대로) — 「기타」·겹침·used 글자·branch 밖·share 수·parts 아님', () => {
    const breaks: ((t: Record<string, unknown>) => void)[] = [
      (t) => ((t.parts as Record<string, unknown>[])[0]!.treatment = '기타'),
      (t) => ((t.parts as Record<string, unknown>[])[1]!.treatment = '매립'),
      (t) => ((t.parts as Record<string, unknown>[])[0]!.used = 'true'),
      (t) => (t.branch = 'other'),
      (t) => ((t.parts as Record<string, unknown>[])[0]!.share = 0.1),
      (t) => (t.shareTotal = 1),
      (t) => (t.parts = null),
    ];
    for (const broken of breaks) {
      const treatments = fakeTreatments('code');
      broken(treatments);
      const [row] = rowsOf(
        fakeDoneResult({
          sheets: [
            processedSheet('c12_지어낸', 'Category12', [
              c12Row('c12_지어낸!3', treatments),
            ]),
          ],
        }),
      );
      expect(row!.detail.shape).toBe('energy');
      expect(treatmentsOf(row!)).toBeUndefined();
    }
    const [other] = rowsOf(
      fakeDoneResult({
        sheets: [
          processedSheet('c3_지어낸', 'Category3', [
            energyRow('fuel_energy', '3', undefined, 'c3_지어낸!3', {
              treatments: fakeTreatments('code'),
            }),
          ]),
        ],
      }),
    );
    expect(treatmentsOf(other!)).toBeUndefined(); // product_eol 만 읽는다
    expect(FAKE_C12_NAME).toBeTruthy();
  });
});
