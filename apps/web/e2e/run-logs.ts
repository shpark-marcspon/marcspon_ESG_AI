// e2e 의 실행 기록 흉내 서버(밴드 AD4R). /api/run-logs·/api/run-logs/metrics 를 page.route 로 채운다. 답의 값은 전부 지어낸 것이다.
//   - GET /run-logs → RunLogPageOut. 받은 쿼리의 status·review 가 있으면 그 값의 줄만(서버 거르기 흉내 — 화면이 쿼리를 보냈는지 줄 수로도 보인다),
//     limit·offset 으로 자른다. 그 밖의 거르기(q·날짜·모듈)는 하지 않는다 — 시험은 요청 URL 로 단언한다.
//   - GET /run-logs/metrics → RunMetricsOut.
//   - GET /run-logs/export → 지어낸 바이트(진짜 xlsx 아님)와 서버 꼴 Content-Disposition(filename*=utf-8''…). setExport('tooLarge') 면 409(밴드 AD4X ②).
//   - GET /run-logs/<id> → 넷째 인자 details 에 그 id 가 있으면 RunLogDetailOut, 없으면 404 RUN_NOT_FOUND(밴드 AD4W).
//   - GET /run-logs/<id>/files/<이름> → 다섯째 인자 files 에 「<id>/<이름>」(이름은 풀어 쓴 글)이 있으면 지어낸 바이트 + Content-Disposition(그 값이 서버 이름),
//     없으면 404 RUN_FILE_NOT_FOUND(밴드 RF1W).
//   - 받은 요청의 URL 을 모은다(urls).
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다.
import type { Page, Route } from '@playwright/test';

export interface FakeRunRow {
  id: number;
  module: string;
  flowId: string;
  documentId: number;
  documentName: string;
  status: 'queued' | 'processing' | 'done' | 'failed';
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  createdByUserId: number;
  createdByName: string | null;
  createdByUsername: string | null;
  durationSec: number | null;
  tokens: number;
  costUsd: number;
  isTest: boolean;
  review: 'pending' | 'in_review' | 'confirmed' | null;
  aiSetting: { id: number | null; name: string } | null;
  /** 같이 시작·이어서(서버 LK1 — 밴드 AD4P). 넘기지 않으면 runRow 가 null 로 채운다. */
  launchKey?: string | null;
  launchFirstRunId?: number | null;
  launchIndex?: number | null;
  launchSize?: number | null;
  resumedFromRunId?: number | null;
}

/** 실행 상세(RunLogDetailOut — 문서 두 칸은 null 도, ND1). */
export interface FakeRunDetail extends Omit<
  FakeRunRow,
  'documentId' | 'documentName'
> {
  documentId: number | null;
  documentName: string | null;
  failedStep: string | null;
  errorCode: string | null;
  stepUsageRecorded: boolean;
  steps: {
    name: string;
    position: number;
    status: 'pending' | 'running' | 'done' | 'failed';
    startedAt: string | null;
    finishedAt: string | null;
    durationSec: number | null;
    tokens: number | null;
    costUsd: number | null;
  }[];
  files: {
    name: string;
    step: string | null;
    mediaType: string;
    sizeBytes: number;
  }[];
}

export interface FakeRunMetrics {
  month: string;
  runs: number;
  averageDurationSec: number | null;
  tokens: number;
  costUsd: number;
  failureRate: number | null;
  aiProviderMock: boolean;
}

const answer = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

export const runRow = (
  id: number,
  overrides: Partial<FakeRunRow> = {},
): FakeRunRow => ({
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
  createdByName: '지어낸 담당자',
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
});

/** 줄 하나의 상세(기본: 단계 기록 있음·그린워싱 E0 단계 여섯·결과 파일 하나 — 값은 지어냄). */
export const runDetail = (
  row: FakeRunRow,
  overrides: Partial<FakeRunDetail> = {},
): FakeRunDetail => ({
  ...row,
  failedStep: null,
  errorCode: null,
  stepUsageRecorded: true,
  steps: (
    [
      ['extract', 42, 0, 0],
      ['index', 58, 21_300, 0.01],
      ['judge', 331, 86_800, 0.57],
      ['wordcount', 4, 0, 0],
      ['locate', 36, 0, 0],
      ['report', 14, 0, 0],
    ] as const
  ).map(([name, durationSec, tokens, costUsd], position) => ({
    name,
    position,
    status: 'done' as const,
    startedAt: row.startedAt,
    finishedAt: row.finishedAt,
    durationSec,
    tokens,
    costUsd,
  })),
  files: [
    {
      name: `지어낸 결과 ${row.id}.xlsx`,
      step: 'report',
      mediaType:
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      sizeBytes: 20_480,
    },
  ],
  ...overrides,
});

/**
 * 문서 없는 줄(밴드 ND1W — 목록의 문서 두 칸 null, 흉내 서버에 그대로 실린다).
 * FakeRunRow 는 문서 두 칸을 글자로 둔다(기존 시험이 이름을 글자로 넘긴다) — 그래서 이 줄만 꼴을 넓혀 넘긴다.
 */
export const runRowNoDocument = (
  id: number,
  overrides: Partial<FakeRunRow> = {},
): FakeRunRow =>
  ({
    ...runRow(id, overrides),
    documentId: null,
    documentName: null,
  }) as unknown as FakeRunRow;

/** 엑셀 흉내의 파일 이름·몸(서버 꼴 「실행기록_YYYY-MM-DD_HHMM.xlsx」, 지어낸 바이트). */
export const EXPORT_NAME = '실행기록_2026-10-22_1430.xlsx';
export const EXPORT_TEXT = '지어낸 엑셀 바이트';

/** 결과 파일 흉내의 몸(지어낸 바이트). */
export const FILE_TEXT = '지어낸 결과 파일 바이트';
/** 모은 URL 가운데 GET /run-logs/<id>/files/<이름> 요청들(fakeRunLogApi 의 urls 를 넘긴다). */
export const fileUrlsOf = (urls: URL[]) =>
  urls.filter((url) => /^\/api\/run-logs\/\d+\/files\//.test(url.pathname));

export const RUN_METRICS: FakeRunMetrics = {
  month: '2026-10',
  runs: 42,
  averageDurationSec: 400,
  tokens: 3_150_000,
  costUsd: 18.4,
  failureRate: 0.048,
  aiProviderMock: true,
};

export async function fakeRunLogApi(
  page: Page,
  rows: FakeRunRow[],
  metrics: FakeRunMetrics = RUN_METRICS,
  details: Record<number, FakeRunDetail> = {},
  files: Record<string, string> = {},
) {
  const urls: URL[] = [];
  await page.route(
    /\/api\/run-logs\/\d+\/files\/[^/?]+(\?.*)?$/,
    async (route) => {
      const url = new URL(route.request().url());
      urls.push(url);
      const [, , , id, , name] = url.pathname.split('/');
      const key = `${id}/${decodeURIComponent(name!)}`;
      if (!Object.hasOwn(files, key))
        return answer(route, 404, {
          error: {
            code: 'RUN_FILE_NOT_FOUND',
            message: '지어낸-RUN_FILE_NOT_FOUND',
            fields: null,
            legacyCode: 'run_file_not_found',
          },
        });
      return route.fulfill({
        status: 200,
        contentType: 'application/octet-stream',
        headers: {
          'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(files[key]!)}`,
        },
        body: Buffer.from(FILE_TEXT, 'utf8'),
      });
    },
  );
  await page.route(/\/api\/run-logs\/\d+(\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    urls.push(url);
    const id = Number(url.pathname.split('/').at(-1));
    if (Object.hasOwn(details, id)) return answer(route, 200, details[id]);
    return answer(route, 404, {
      error: {
        code: 'RUN_NOT_FOUND',
        message: '지어낸-RUN_NOT_FOUND',
        fields: null,
        legacyCode: 'run_not_found',
      },
    });
  });
  let exportKind: 'ok' | 'tooLarge' = 'ok';
  await page.route(/\/api\/run-logs\/export(\?.*)?$/, async (route) => {
    urls.push(new URL(route.request().url()));
    if (exportKind === 'tooLarge')
      return answer(route, 409, {
        error: {
          code: 'RUN_LOG_EXPORT_TOO_LARGE',
          message: '지어낸-RUN_LOG_EXPORT_TOO_LARGE',
          fields: null,
          legacyCode: 'run_log_export_too_large',
        },
      });
    return route.fulfill({
      status: 200,
      contentType:
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      headers: {
        'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(EXPORT_NAME)}`,
      },
      body: Buffer.from(EXPORT_TEXT, 'utf8'),
    });
  });
  await page.route(/\/api\/run-logs\/metrics(\?.*)?$/, async (route) => {
    urls.push(new URL(route.request().url()));
    return answer(route, 200, metrics);
  });
  await page.route(/\/api\/run-logs(\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    urls.push(url);
    const status = url.searchParams.get('status');
    const review = url.searchParams.get('review');
    const matched = rows.filter(
      (row) =>
        (!status || row.status === status) &&
        (!review || row.review === review),
    );
    const limit = Number(url.searchParams.get('limit') ?? 20);
    const offset = Number(url.searchParams.get('offset') ?? 0);
    const results = matched.slice(offset, offset + limit);
    return answer(route, 200, {
      count: matched.length,
      isNext: offset + results.length < matched.length,
      results,
    });
  });
  /** GET /run-logs 요청들(줄 경로만). */
  const listUrls = () => urls.filter((url) => url.pathname === '/api/run-logs');
  /** GET /run-logs/export 요청들. */
  const exportUrls = () =>
    urls.filter((url) => url.pathname === '/api/run-logs/export');
  /** 다음 엑셀 답을 바꾼다. */
  const setExport = (kind: 'ok' | 'tooLarge') => {
    exportKind = kind;
  };
  /** GET /run-logs/<id> 요청들. */
  const detailUrls = () =>
    urls.filter((url) => /^\/api\/run-logs\/\d+$/.test(url.pathname));
  return { urls, listUrls, exportUrls, detailUrls, setExport };
}
