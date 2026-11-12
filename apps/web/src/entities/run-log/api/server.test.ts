// 실행 기록 실어댑터(밴드 AD4R ①): 진짜 createApi 에 가짜 서버(모킹한 fetch)를 물려 부른 경로·쿼리를 단언한다.
//   list → GET /run-logs(쿼리 = 넣은 칸 + limit 50·offset, companyId 없음), metrics → GET /run-logs/metrics(쿼리 없음).
//   실패(400·403·404·422·5xx·던짐·꼴 틀림)는 모두 failed 하나.
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import type { Api } from '../../../shared/api/index.ts';
import {
  RUN_EXPORT_FALLBACK_NAME,
  RUN_NO_FILTER,
  runQuery,
} from '../model/index.ts';
import { RUN_PAGE_SIZE, createRunLogServerPort } from './index.ts';
import {
  FAKE_EXPORT_NAME,
  FAKE_EXPORT_TEXT,
  FAKE_FILE_TEXT,
  exportAnswer,
  fakeRunDetail,
  fakeRunLogServer,
  fakeRunMetrics,
  fakeRunRow,
  fakeServedName,
  fileAnswer,
  json,
  refusal,
  runFilePath,
} from './testing.ts';

const BASE = 'http://test.local/api';

function setup(
  rows = [fakeRunRow(2), fakeRunRow(1)],
  metrics = fakeRunMetrics(),
) {
  const server = fakeRunLogServer(rows, metrics, { baseUrl: BASE });
  const port = createRunLogServerPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  return { server, port };
}

const NOW = new Date('2026-10-15T03:00:00Z');
/** 처음 거르기(이번 달 — 2026-10-15 기준). */
const firstQuery = runQuery(RUN_NO_FILTER, NOW);

describe('list — GET /run-logs 한 쪽', () => {
  it('부른 경로가 정확히 /run-logs, 쿼리가 정확히 날짜 둘 + limit 50·offset 0, count 는 서버 값', async () => {
    const { server, port } = setup();
    const outcome = await port.list(firstQuery, 0);
    expect(outcome).toEqual({
      kind: 'ok',
      count: 2,
      isNext: false,
      rows: [fakeRunRow(2), fakeRunRow(1)],
    });
    expect(server.calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      'GET /run-logs',
    ]);
    expect(server.listQueries()).toEqual([
      {
        dateFrom: '2026-10-01',
        dateTo: '2026-10-15',
        limit: String(RUN_PAGE_SIZE),
        offset: '0',
      },
    ]);
    expect(RUN_PAGE_SIZE).toBe(50);
  });

  it('q·모듈·상태가 그 값으로 실리고, offset 50 이 실린다. companyId 는 없다', async () => {
    const { server, port } = setup();
    await port.list(
      runQuery(
        {
          query: ' 보고서 ',
          module: 'dataverify',
          period: 'all',
          status: 'queued',
          review: 'in_review',
        },
        NOW,
      ),
      50,
    );
    expect(server.listQueries()).toEqual([
      {
        q: '보고서',
        module: 'dataverify',
        status: 'queued',
        review: 'in_review',
        limit: '50',
        offset: '50',
      },
    ]);
    expect(server.calls[0]!.query.has('companyId')).toBe(false);
  });

  it('공백만·NUL 만 든 검색은 q 키째 나가지 않는다', async () => {
    const { server, port } = setup();
    await port.list(runQuery({ ...RUN_NO_FILTER, query: '   ' }, NOW), 0);
    await port.list(runQuery({ ...RUN_NO_FILTER, query: ' \u0000 ' }, NOW), 0);
    expect(server.calls.map((call) => call.query.has('q'))).toEqual([
      false,
      false,
    ]);
  });

  it('다음 쪽이 있으면 isNext 참, count 는 실린 수가 아니라 전부의 수', async () => {
    const many = Array.from({ length: 53 }, (_, i) => fakeRunRow(53 - i));
    const { port } = setup(many);
    const first = await port.list({}, 0);
    expect(
      first.kind === 'ok' && [first.count, first.isNext, first.rows.length],
    ).toEqual([53, true, 50]);
    const second = await port.list({}, 50);
    expect(second.kind === 'ok' && [second.isNext, second.rows.length]).toEqual(
      [false, 3],
    );
  });

  it('null 칸(이름·아이디·시작·끝·처리 시간)이 든 줄도 꼴 맞음', async () => {
    const row = fakeRunRow(7, {
      status: 'queued',
      createdByName: null,
      createdByUsername: null,
      startedAt: null,
      finishedAt: null,
      durationSec: null,
      tokens: 0,
      costUsd: 0,
      isTest: true,
    });
    const { port } = setup([row]);
    expect(await port.list({}, 0)).toEqual({
      kind: 'ok',
      count: 1,
      isNext: false,
      rows: [row],
    });
  });

  it('문서 두 칸 null 인 줄(문서 없는 실행 — ND1W)도 꼴 맞음', async () => {
    const row = fakeRunRow(8, { documentId: null, documentName: null });
    const { port } = setup([fakeRunRow(9), row]);
    expect(await port.list({}, 0)).toEqual({
      kind: 'ok',
      count: 2,
      isNext: false,
      rows: [fakeRunRow(9), row],
    });
  });

  it.each([
    ['검토·AI 설정 없음(null)', { review: null, aiSetting: null }],
    [
      '검토 중 · 판 v3',
      { review: 'in_review', aiSetting: { id: 3, name: 'v3' } },
    ],
    [
      '확정 · 기본 판(id null)',
      {
        review: 'confirmed',
        aiSetting: { id: null, name: 'colab-2026-01-15-v1' },
      },
    ],
  ] as const)('검토·AI 설정 꼴 맞음: %s', async (_, overrides) => {
    const row = fakeRunRow(7, overrides);
    const { port } = setup([row]);
    expect(await port.list({}, 0)).toEqual({
      kind: 'ok',
      count: 1,
      isNext: false,
      rows: [row],
    });
  });
});

describe('metrics — GET /run-logs/metrics', () => {
  it('경로 정확히, 쿼리 없음(companyId 도), 서버 값 그대로', async () => {
    const metrics = fakeRunMetrics();
    const { server, port } = setup([], metrics);
    expect(await port.metrics()).toEqual({ kind: 'ok', metrics });
    expect(server.calls).toHaveLength(1);
    expect(server.calls[0]!.path).toBe('/run-logs/metrics');
    expect([...server.calls[0]!.query.keys()]).toEqual([]);
  });

  it('null 둘(평균 처리 시간·실패율)도 꼴 맞음', async () => {
    const metrics = fakeRunMetrics({
      runs: 0,
      averageDurationSec: null,
      tokens: 0,
      costUsd: 0,
      failureRate: null,
    });
    const { port } = setup([], metrics);
    expect(await port.metrics()).toEqual({ kind: 'ok', metrics });
  });
  // MP1W: 모의 공급사 여부(AD-04 안내 띠의 근거)는 참·거짓 둘 다 꼴 맞음 — 값 그대로 싣는다.
  it.each([true, false])(
    'aiProviderMock %s 도 꼴 맞음(값 그대로)',
    async (mock) => {
      const metrics = fakeRunMetrics({ aiProviderMock: mock });
      const { port } = setup([], metrics);
      expect(await port.metrics()).toEqual({ kind: 'ok', metrics });
    },
  );
});

describe('실패는 모두 failed 하나', () => {
  const answers = {
    '422': () => refusal(422, 'VALIDATION_ERROR'),
    '403 FORBIDDEN': () => refusal(403, 'FORBIDDEN'),
    '403 PASSWORD_CHANGE_REQUIRED': () =>
      refusal(403, 'PASSWORD_CHANGE_REQUIRED'),
    '404': () => refusal(404, 'COMPANY_NOT_FOUND'),
    '400': () => refusal(400, 'COMPANY_AMBIGUOUS'),
    '500': () => json(500, undefined),
    '502 빈 본문': () => new Response('', { status: 502 }),
    던짐: () => {
      throw new TypeError('연결 끊김');
    },
  };

  it.each(Object.entries(answers))('list: %s', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /run-logs'] = answer;
    expect(await port.list({}, 0)).toEqual({ kind: 'failed' });
  });

  it.each(Object.entries(answers))('metrics: %s', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /run-logs/metrics'] = answer;
    expect(await port.metrics()).toEqual({ kind: 'failed' });
  });

  it.each([
    ['results 가 배열이 아님', { count: 1, isNext: false, results: {} }],
    ['count 없음', { isNext: false, results: [] }],
    ['isNext 가 글자', { count: 0, isNext: 'no', results: [] }],
    [
      '줄의 칸 빠짐(documentName)',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), documentName: undefined }],
      },
    ],
    [
      '줄의 칸 빠짐(documentId)',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), documentId: undefined }],
      },
    ],
    [
      'status 모르는 값',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), status: 'cancelled' }],
      },
    ],
    [
      'costUsd 가 글자',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), costUsd: '0.58' }],
      },
    ],
    [
      'isTest 없음',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), isTest: undefined }],
      },
    ],
    [
      'id 가 글자',
      { count: 1, isNext: false, results: [{ ...fakeRunRow(1), id: '1' }] },
    ],
    [
      'review 모르는 값',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), review: 'done' }],
      },
    ],
    [
      'aiSetting.id 가 글자',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), aiSetting: { id: '1', name: 'v1' } }],
      },
    ],
    [
      'aiSetting.name 이 수',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), aiSetting: { id: 1, name: 3 } }],
      },
    ],
    [
      'review 키 없음',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), review: undefined }],
      },
    ],
    [
      'aiSetting 키 없음',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), aiSetting: undefined }],
      },
    ],
    [
      'documentId 가 글자(ND1W)',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), documentId: '101' }],
      },
    ],
    [
      'documentName 이 수(ND1W)',
      {
        count: 1,
        isNext: false,
        results: [{ ...fakeRunRow(1), documentName: 101 }],
      },
    ],
    ['null', null],
  ])('list 꼴 틀림: %s', async (_, body) => {
    const { server, port } = setup();
    server.override['GET /run-logs'] = () => json(200, body);
    expect(await port.list({}, 0)).toEqual({ kind: 'failed' });
  });

  it.each([
    ['빈 것', {}],
    ['runs 가 글자', { ...fakeRunMetrics(), runs: '42' }],
    ['failureRate 없음', { ...fakeRunMetrics(), failureRate: undefined }],
    ['costUsd null', { ...fakeRunMetrics(), costUsd: null }],
    [
      'aiProviderMock 없음(MP1W)',
      { ...fakeRunMetrics(), aiProviderMock: undefined },
    ],
    [
      'aiProviderMock 이 글자(MP1W)',
      { ...fakeRunMetrics(), aiProviderMock: 'true' },
    ],
    ['null', null],
  ])('metrics 꼴 틀림: %s', async (_, body) => {
    const { server, port } = setup();
    server.override['GET /run-logs/metrics'] = () => json(200, body);
    expect(await port.metrics()).toEqual({ kind: 'failed' });
  });
});

describe('exportFile — GET /run-logs/export(밴드 AD4X ②)', () => {
  const bytes = async (blob: Blob) =>
    new TextDecoder().decode(await blob.arrayBuffer());

  it('경로 정확히, 쿼리는 넘긴 그대로(쪽·회사 없음), Blob 바이트 = 흉내 몸, 이름은 filename* 해독', async () => {
    const { server, port } = setup();
    const query = runQuery(
      {
        query: ' 보고서 ',
        module: 'greenwash',
        period: 'month',
        status: 'done',
        review: 'confirmed',
      },
      NOW,
    );
    const outcome = await port.exportFile(query);
    expect(server.calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      'GET /run-logs/export',
    ]);
    expect(server.exportQueries()).toEqual([
      {
        dateFrom: '2026-10-01',
        dateTo: '2026-10-15',
        q: '보고서',
        module: 'greenwash',
        status: 'done',
        review: 'confirmed',
      },
    ]);
    for (const key of ['limit', 'offset', 'companyId'])
      expect(server.calls[0]!.query.has(key), key).toBe(false);
    expect(outcome.kind).toBe('ok');
    if (outcome.kind !== 'ok') return;
    expect(outcome.fileName).toBe(FAKE_EXPORT_NAME);
    expect(await bytes(outcome.blob)).toBe(FAKE_EXPORT_TEXT);
  });

  it('Content-Disposition 이 없으면 대체 이름', async () => {
    const { server, port } = setup();
    server.override['GET /run-logs/export'] = () => exportAnswer(null);
    const outcome = await port.exportFile({});
    expect(outcome.kind === 'ok' && outcome.fileName).toBe(
      RUN_EXPORT_FALLBACK_NAME,
    );
  });

  it('409 RUN_LOG_EXPORT_TOO_LARGE → tooLarge', async () => {
    const { server, port } = setup();
    server.override['GET /run-logs/export'] = () =>
      refusal(409, 'RUN_LOG_EXPORT_TOO_LARGE');
    expect(await port.exportFile({})).toEqual({ kind: 'tooLarge' });
  });

  it('Blob 꼴이 아닌 답 → failed(어댑터가 모양으로 본다)', async () => {
    const api = {
      client: {
        GET: async () => ({ data: '바이트 아님', response: new Response() }),
      },
    } as unknown as Api;
    const port = createRunLogServerPort({ api });
    expect(await port.exportFile({})).toEqual({ kind: 'failed' });
  });

  it.each([
    ['409 다른 code', () => refusal(409, 'CONFLICT')],
    ['500', () => json(500, undefined)],
    ['403', () => refusal(403, 'FORBIDDEN')],
    [
      '던짐',
      () => {
        throw new TypeError('연결 끊김');
      },
    ],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /run-logs/export'] = answer;
    expect(await port.exportFile({})).toEqual({ kind: 'failed' });
  });
});

// detail → GET /run-logs/{id}(질의 없음, 밴드 AD4W): 404 RUN_NOT_FOUND 만 notFound, 문서 두 칸 null 은 ok.
describe('detail — GET /run-logs/{run_id}(밴드 AD4W)', () => {
  function setupDetail(details = { 31: fakeRunDetail(31) }) {
    const server = fakeRunLogServer([], fakeRunMetrics(), {
      baseUrl: BASE,
      details,
    });
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    return { server, port };
  }

  it('경로 정확히 /run-logs/31, 질의 없음(companyId 없음), 답 그대로 ok', async () => {
    const { server, port } = setupDetail();
    expect(await port.detail(31)).toEqual({
      kind: 'ok',
      detail: fakeRunDetail(31),
    });
    expect(server.calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      'GET /run-logs/31',
    ]);
    expect(server.detailCalls()).toEqual([{ path: '/run-logs/31', query: {} }]);
  });

  it('문서 두 칸 null(문서를 지운 실행 — ND1) → ok', async () => {
    const detail = fakeRunDetail(31, { documentId: null, documentName: null });
    const { port } = setupDetail({ 31: detail });
    expect(await port.detail(31)).toEqual({ kind: 'ok', detail });
  });

  it.each([
    ['steps 가 배열 아님', { steps: {} }],
    [
      '단계 status 모르는 값',
      { steps: [{ ...fakeRunDetail(31).steps[0]!, status: 'skipped' }] },
    ],
    [
      '단계 tokens 가 글자',
      { steps: [{ ...fakeRunDetail(31).steps[0]!, tokens: '1' }] },
    ],
    ['stepUsageRecorded 없음', { stepUsageRecorded: undefined }],
    [
      '파일 sizeBytes 가 글자',
      { files: [{ ...fakeRunDetail(31).files[0]!, sizeBytes: '20480' }] },
    ],
    ['failedStep 이 수', { failedStep: 3 }],
  ])('꼴 틀림: %s → failed', async (_, broken) => {
    const { server, port } = setupDetail();
    server.override['GET /run-logs/31'] = () =>
      json(200, { ...fakeRunDetail(31), ...broken });
    expect(await port.detail(31)).toEqual({ kind: 'failed' });
  });

  it('404 RUN_NOT_FOUND → notFound(가짜에 없는 id)', async () => {
    const { server, port } = setupDetail();
    expect(await port.detail(32)).toEqual({ kind: 'notFound' });
    expect(server.calls.map((call) => call.path)).toEqual(['/run-logs/32']);
  });

  it.each([
    ['404 COMPANY_NOT_FOUND', () => refusal(404, 'COMPANY_NOT_FOUND')],
    ['403', () => refusal(403, 'FORBIDDEN')],
    ['500', () => json(500, undefined)],
    [
      '던짐',
      () => {
        throw new TypeError('연결 끊김');
      },
    ],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setupDetail();
    server.override['GET /run-logs/31'] = answer;
    expect(await port.detail(31)).toEqual({ kind: 'failed' });
  });
});

// file → GET /run-logs/{run_id}/files/{name}(질의 없음, 밴드 RF1W): 이름은 경로 칸(퍼센트 꼴), 받은 Blob 과 Content-Disposition 이름(없으면 줄 이름).
describe('file — GET /run-logs/{run_id}/files/{name}(밴드 RF1W)', () => {
  const bytes = async (blob: Blob) =>
    new TextDecoder().decode(await blob.arrayBuffer());
  /** 한글·공백·#·/ 가 든 이름(경로 칸에서 퍼센트 꼴이어야 한 칸으로 간다). */
  const NAME = '지어낸 결과 #1/요약.xlsx';

  function setupFile(name = NAME) {
    const detail = fakeRunDetail(7, {
      files: [
        { name, step: null, mediaType: 'application/pdf', sizeBytes: 10 },
        {
          name: '지어낸 중간.json',
          step: 'judge',
          mediaType: 'application/json',
          sizeBytes: 10,
        },
      ],
    });
    const server = fakeRunLogServer([], fakeRunMetrics(), {
      baseUrl: BASE,
      details: { 7: detail },
    });
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    return { server, port };
  }

  it('URL = /run-logs/7/files/<encode 된 이름>(질의 0, companyId 없음), 200 Blob + filename* → 그 이름', async () => {
    const { server, port } = setupFile();
    const outcome = await port.file(7, NAME);
    expect(server.fileCalls()).toEqual([
      {
        path: '/run-logs/7/files/%EC%A7%80%EC%96%B4%EB%82%B8%20%EA%B2%B0%EA%B3%BC%20%231%2F%EC%9A%94%EC%95%BD.xlsx',
        query: {},
      },
    ]);
    expect(server.fileCalls()[0]!.path).toBe(runFilePath(7, NAME));
    expect(outcome.kind).toBe('ok');
    if (outcome.kind !== 'ok') return;
    expect(outcome.fileName).toBe(fakeServedName(NAME).replace('/', ''));
    expect(await bytes(outcome.blob)).toBe(FAKE_FILE_TEXT);
  });

  it('Content-Disposition 이 없으면 그 줄 이름', async () => {
    const { server, port } = setupFile('지어낸 결과.pdf');
    server.override[`GET ${runFilePath(7, '지어낸 결과.pdf')}`] = () =>
      fileAnswer(null);
    const outcome = await port.file(7, '지어낸 결과.pdf');
    expect(outcome.kind === 'ok' && outcome.fileName).toBe('지어낸 결과.pdf');
  });

  it('filename="…"(따옴표 꼴)도 서버 이름', async () => {
    const { server, port } = setupFile('지어낸 결과.pdf');
    server.override[`GET ${runFilePath(7, '지어낸 결과.pdf')}`] = () =>
      fileAnswer('attachment; filename="served.pdf"');
    const outcome = await port.file(7, '지어낸 결과.pdf');
    expect(outcome.kind === 'ok' && outcome.fileName).toBe('served.pdf');
  });

  it('404 RUN_FILE_NOT_FOUND(단계 중간 파일·없는 이름)·404 RUN_NOT_FOUND(없는 실행) → notFound(AD4P)', async () => {
    const { server, port } = setupFile();
    expect(await port.file(7, '지어낸 중간.json')).toEqual({
      kind: 'notFound',
    });
    expect(await port.file(7, '없는.pdf')).toEqual({ kind: 'notFound' });
    expect(await port.file(8, NAME)).toEqual({ kind: 'notFound' });
    expect(server.fileCalls()).toHaveLength(3);
  });

  it('Blob 꼴이 아닌 답 → failed(어댑터가 모양으로 본다)', async () => {
    const api = {
      client: {
        GET: async () => ({ data: '바이트 아님', response: new Response() }),
      },
    } as unknown as Api;
    const port = createRunLogServerPort({ api });
    expect(await port.file(7, NAME)).toEqual({ kind: 'failed' });
  });

  it.each([
    ['503 storage_unavailable', () => refusal(503, 'storage_unavailable')],
    ['500', () => json(500, undefined)],
    ['403', () => refusal(403, 'FORBIDDEN')],
    [
      '던짐(연결 끊김)',
      () => {
        throw new TypeError('연결 끊김');
      },
    ],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setupFile();
    server.override[`GET ${runFilePath(7, NAME)}`] = answer;
    expect(await port.file(7, NAME)).toEqual({ kind: 'failed' });
  });
});

// 밴드 AD4P: 결과 파일 404 갈래(이름으로만 — detail 과 같은 꼴)와 LK1 다섯 칸 가드.
describe('file 404 갈래(밴드 AD4P)', () => {
  const NAME = '지어낸 결과.pdf';
  function setupOne() {
    const server = fakeRunLogServer([], fakeRunMetrics(), {
      baseUrl: BASE,
      details: {
        7: fakeRunDetail(7, {
          files: [
            {
              name: NAME,
              step: null,
              mediaType: 'application/pdf',
              sizeBytes: 1,
            },
          ],
        }),
      },
    });
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    return { server, port };
  }

  it.each([
    ['404 RUN_NOT_FOUND', 'RUN_NOT_FOUND'],
    ['404 RUN_FILE_NOT_FOUND', 'RUN_FILE_NOT_FOUND'],
  ])('%s → notFound', async (_, code) => {
    const { server, port } = setupOne();
    server.override[`GET ${runFilePath(7, NAME)}`] = () => refusal(404, code);
    expect(await port.file(7, NAME)).toEqual({ kind: 'notFound' });
    expect(server.fileCalls()).toHaveLength(1);
  });

  it.each([
    ['503 STORAGE_UNAVAILABLE', () => refusal(503, 'STORAGE_UNAVAILABLE')],
    ['503 STORAGE_DENIED', () => refusal(503, 'STORAGE_DENIED')],
    ['503 STORAGE_UNCONFIGURED', () => refusal(503, 'STORAGE_UNCONFIGURED')],
    ['404 인데 code 가 둘 밖(NOT_FOUND)', () => refusal(404, 'NOT_FOUND')],
    ['404 빈 본문(프록시)', () => new Response('', { status: 404 })],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setupOne();
    server.override[`GET ${runFilePath(7, NAME)}`] = answer;
    expect(await port.file(7, NAME)).toEqual({ kind: 'failed' });
  });
});

describe('가드 — 같이 시작·이어서 다섯 칸(LK1, 밴드 AD4P)', () => {
  const LAUNCHED = {
    launchKey: '지어낸-묶음-열쇠',
    launchFirstRunId: 101,
    launchIndex: 2,
    launchSize: 3,
    resumedFromRunId: 88,
  };
  const BROKEN: [string, Record<string, unknown>][] = [
    ['launchKey 빠짐', { launchKey: undefined }],
    ['launchFirstRunId 빠짐', { launchFirstRunId: undefined }],
    ['launchIndex 빠짐', { launchIndex: undefined }],
    ['launchSize 빠짐', { launchSize: undefined }],
    ['resumedFromRunId 빠짐', { resumedFromRunId: undefined }],
    ['launchKey 가 수', { launchKey: 1 }],
    ['launchSize 가 글자', { launchSize: '3' }],
    ['launchFirstRunId 가 글자', { launchFirstRunId: '101' }],
    ['resumedFromRunId 가 글자', { resumedFromRunId: '88' }],
  ];
  const page = (row: unknown) => ({ count: 1, isNext: false, results: [row] });
  function setupDetail() {
    const server = fakeRunLogServer([], fakeRunMetrics(), {
      baseUrl: BASE,
      details: { 31: fakeRunDetail(31) },
    });
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    return { server, port };
  }

  it('줄: 다섯 칸 null·수(글) → ok', async () => {
    for (const row of [fakeRunRow(1), fakeRunRow(1, LAUNCHED)]) {
      const { server, port } = setup();
      server.override['GET /run-logs'] = () => json(200, page(row));
      expect(await port.list({}, 0)).toEqual({
        kind: 'ok',
        count: 1,
        isNext: false,
        rows: [row],
      });
    }
  });

  it.each(BROKEN)('줄: %s → failed', async (_, broken) => {
    const { server, port } = setup();
    server.override['GET /run-logs'] = () =>
      json(200, page({ ...fakeRunRow(1, LAUNCHED), ...broken }));
    expect(await port.list({}, 0)).toEqual({ kind: 'failed' });
  });

  it('상세: 다섯 칸 null·수(글) → ok', async () => {
    for (const detail of [fakeRunDetail(31), fakeRunDetail(31, LAUNCHED)]) {
      const { server, port } = setupDetail();
      server.override['GET /run-logs/31'] = () => json(200, detail);
      expect(await port.detail(31)).toEqual({ kind: 'ok', detail });
    }
  });

  it.each(BROKEN)('상세: %s → failed', async (_, broken) => {
    const { server, port } = setupDetail();
    server.override['GET /run-logs/31'] = () =>
      json(200, { ...fakeRunDetail(31, LAUNCHED), ...broken });
    expect(await port.detail(31)).toEqual({ kind: 'failed' });
  });
});
