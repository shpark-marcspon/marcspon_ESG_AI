// 시험용 가짜 실행 기록 서버(밴드 AD4R ①). 시험만 쓴다(공개 표면이 아니다).
// 답의 꼴은 api-py 의 GET /run-logs(RunLogPageOut)·GET /run-logs/metrics(RunMetricsOut)를 따른다. 값은 전부 지어낸 것이다.
// Bearer 는 보지 않는다(세션 가짜 서버의 몫).
//   - GET /run-logs 는 받은 limit·offset 으로 줄을 잘라 낼 뿐 거르지 않는다 — 시험은 거르기를 요청 URL 로 단언한다.
//   - GET /run-logs/export 는 지어낸 바이트(진짜 xlsx 아님)를 서버 머리 꼴(Content-Disposition: attachment; filename*=utf-8''…)로 낸다(밴드 AD4X ②).
//   - GET /run-logs/<id> 는 셋째 인자 details 에 그 id 가 있으면 200, 없으면 404 RUN_NOT_FOUND(밴드 AD4W).
//   - GET /run-logs/<id>/files/<이름> 은 그 상세의 step 이 null 인 파일이면 지어낸 바이트 + Content-Disposition(서버 이름 = fakeServedName — 줄 이름과 일부러 다르다),
//     상세는 있고 그 파일이 없으면(또는 단계 중간 파일이면) 404 RUN_FILE_NOT_FOUND, 상세가 없으면 404 RUN_NOT_FOUND(밴드 RF1W). 경로의 이름은 퍼센트 꼴 그대로 적힌다.
//   - 받은 요청을 calls 에 적는다(쿼리는 URLSearchParams 로).
// override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다. 연결 끊김은 던지는 함수로).
import type { RunLogDetail, RunLogRow, RunMetricsRow } from '../model/index.ts';

export interface FakeRunLogCall {
  method: string;
  path: string;
  query: URLSearchParams;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (status: number, code: string) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

/** 엑셀 흉내의 파일 이름(서버 꼴 「실행기록_YYYY-MM-DD_HHMM.xlsx」). */
export const FAKE_EXPORT_NAME = '실행기록_2026-10-22_1430.xlsx';
/** 엑셀 흉내의 몸(지어낸 글자 바이트 — 진짜 xlsx 아님). */
export const FAKE_EXPORT_TEXT = '지어낸 엑셀 바이트';
const XLSX =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

/** 엑셀 답(머리를 바꿔 끼울 수 있다 — null 이면 Content-Disposition 없음). */
export const exportAnswer = (
  disposition:
    | string
    | null = `attachment; filename*=utf-8''${encodeURIComponent(FAKE_EXPORT_NAME)}`,
) =>
  new Response(new TextEncoder().encode(FAKE_EXPORT_TEXT), {
    status: 200,
    headers: {
      'Content-Type': XLSX,
      ...(disposition === null ? {} : { 'Content-Disposition': disposition }),
    },
  });

/** 결과 파일 흉내의 몸(지어낸 글자 바이트). */
export const FAKE_FILE_TEXT = '지어낸 결과 파일 바이트';
/** 결과 파일 흉내에서 서버가 Content-Disposition 에 싣는 이름(줄 이름과 달라야 어댑터가 머리를 읽는지 보인다). */
export const fakeServedName = (name: string) => `받은_${name}`;
/** 결과 파일 경로(가짜 서버가 적는 꼴 — 이름은 퍼센트 꼴). */
export const runFilePath = (runId: number, name: string) =>
  `/run-logs/${runId}/files/${encodeURIComponent(name)}`;

/** 결과 파일 답(null 이면 Content-Disposition 없음). */
export const fileAnswer = (disposition: string | null) =>
  new Response(new TextEncoder().encode(FAKE_FILE_TEXT), {
    status: 200,
    headers: {
      'Content-Type': 'application/octet-stream',
      ...(disposition === null ? {} : { 'Content-Disposition': disposition }),
    },
  });

/** 지어낸 실행 줄 하나(기본: 그린워싱 완료). */
export function fakeRunRow(
  id: number,
  overrides: Partial<RunLogRow> = {},
): RunLogRow {
  return {
    id,
    module: 'greenwash',
    flowId: 'greenwash.colab@E0',
    documentId: id + 100,
    documentName: `지어낸 문서 ${id}.pdf`,
    status: 'done',
    createdAt: '2026-10-15T14:20:00+09:00',
    startedAt: '2026-10-15T14:20:05+09:00',
    finishedAt: '2026-10-15T14:28:05+09:00',
    createdByUserId: 11,
    createdByName: '담당자 가',
    createdByUsername: 'user11',
    durationSec: 485,
    tokens: 108_100,
    costUsd: 0.58,
    isTest: false,
    review: null,
    aiSetting: null,
    launchKey: null,
    launchFirstRunId: null,
    launchIndex: null,
    launchSize: null,
    resumedFromRunId: null,
    ...overrides,
  };
}

/** 지어낸 지표(이번 달). */
export function fakeRunMetrics(
  overrides: Partial<RunMetricsRow> = {},
): RunMetricsRow {
  return {
    month: '2026-10',
    runs: 42,
    averageDurationSec: 400,
    tokens: 3_150_000,
    costUsd: 18.4,
    failureRate: 0.048,
    aiProviderMock: true,
    ...overrides,
  };
}

/** 그린워싱 E0 의 단계 여섯(서버 선언 차례 — 이름만 서버 것, 값은 지어냄). */
const FAKE_STEPS: RunLogDetail['steps'] = [
  ['extract', 42, 0, 0],
  ['index', 58, 21_300, 0.01],
  ['judge', 331, 86_800, 0.57],
  ['wordcount', 4, 0, 0],
  ['locate', 36, 0, 0],
  ['report', 14, 0, 0],
].map(([name, durationSec, tokens, costUsd], position) => ({
  name: name as string,
  position,
  status: 'done' as const,
  startedAt: '2026-10-15T14:20:05+09:00',
  finishedAt: '2026-10-15T14:28:05+09:00',
  durationSec: durationSec as number,
  tokens: tokens as number,
  costUsd: costUsd as number,
}));

/** 지어낸 실행 상세 하나(기본: 그린워싱 완료·단계 기록 있음·단계 여섯·결과 파일 둘). 만든 때는 잡힌 때와 분이 다르다(시각 칸은 startedAt). */
export function fakeRunDetail(
  id: number,
  overrides: Partial<RunLogDetail> = {},
): RunLogDetail {
  return {
    ...fakeRunRow(id, { createdAt: '2026-10-15T14:18:00+09:00' }),
    failedStep: null,
    errorCode: null,
    stepUsageRecorded: true,
    steps: FAKE_STEPS,
    files: [
      {
        name: `지어낸 결과 ${id}.xlsx`,
        step: 'report',
        mediaType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        sizeBytes: 20_480,
      },
      {
        name: `지어낸 표시 ${id}.pdf`,
        step: 'report',
        mediaType: 'application/pdf',
        sizeBytes: 409_600,
      },
    ],
    ...overrides,
  };
}

export function fakeRunLogServer(
  rows: RunLogRow[] = [],
  metrics: RunMetricsRow = fakeRunMetrics(),
  {
    baseUrl = 'http://test.local/api',
    details = {},
  }: { baseUrl?: string; details?: Record<number, RunLogDetail> } = {},
) {
  const calls: FakeRunLogCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};

  const answer = (key: string, url: URL): Response => {
    if (key === 'GET /run-logs') {
      const limit = Number(url.searchParams.get('limit') ?? 20);
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const page = rows.slice(offset, offset + limit);
      return json(200, {
        count: rows.length,
        isNext: offset + page.length < rows.length,
        results: page,
      });
    }
    if (key === 'GET /run-logs/metrics') return json(200, metrics);
    if (key === 'GET /run-logs/export') return exportAnswer();
    const file = /^GET \/run-logs\/(\d+)\/files\/([^/]+)$/.exec(key);
    if (file) {
      const id = Number(file[1]);
      const name = decodeURIComponent(file[2]!);
      if (!Object.hasOwn(details, id)) return refusal(404, 'RUN_NOT_FOUND');
      const served = details[id]!.files.some(
        (each) => each.name === name && each.step === null,
      );
      return served ?
          fileAnswer(
            `attachment; filename*=utf-8''${encodeURIComponent(fakeServedName(name))}`,
          )
        : refusal(404, 'RUN_FILE_NOT_FOUND');
    }
    const detail = /^GET \/run-logs\/(\d+)$/.exec(key);
    if (detail) {
      const id = Number(detail[1]);
      return Object.hasOwn(details, id) ?
          json(200, details[id])
        : refusal(404, 'RUN_NOT_FOUND');
    }
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) =>
    /^\/run-logs(\/metrics|\/export|\/\d+(\/files\/[^/]+)?)?$/.test(
      pathOf(request),
    );

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(request);
    const key = `${request.method} ${path}`;
    calls.push({ method: request.method, path, query: url.searchParams });
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(key, url);
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  /** GET /run-logs 요청들의 쿼리(글자 — 키 차례 그대로). */
  const listQueries = () =>
    calls
      .filter((call) => call.path === '/run-logs')
      .map((call) => Object.fromEntries(call.query));

  /** GET /run-logs/export 요청들의 쿼리(글자 — 키 차례 그대로). */
  const exportQueries = () =>
    calls
      .filter((call) => call.path === '/run-logs/export')
      .map((call) => Object.fromEntries(call.query));

  /** GET /run-logs/<id> 요청들(경로와 쿼리 — 키 차례 그대로). */
  const detailCalls = () =>
    calls
      .filter((call) => /^\/run-logs\/\d+$/.test(call.path))
      .map((call) => ({
        path: call.path,
        query: Object.fromEntries(call.query),
      }));

  /** GET /run-logs/<id>/files/<이름> 요청들(경로와 쿼리 — 이름은 퍼센트 꼴 그대로). */
  const fileCalls = () =>
    calls
      .filter((call) => /^\/run-logs\/\d+\/files\//.test(call.path))
      .map((call) => ({
        path: call.path,
        query: Object.fromEntries(call.query),
      }));

  return {
    send,
    handles,
    calls,
    count,
    listQueries,
    exportQueries,
    detailCalls,
    fileCalls,
    override,
    rows,
  };
}
