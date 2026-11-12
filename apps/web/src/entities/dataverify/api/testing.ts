// 시험용 가짜 데이터 검증 서버(밴드 DV2a ①). 어댑터·훅·화면·경로 시험이 같이 쓴다(공개 표면이 아니다 — 시험만 직접 가져온다).
// 답의 꼴은 api-py 의 경로(generated/api.d.ts)와 계약(RunOut·dataverify.result@2)을 따른다. 값은 전부 지어낸 것이다(실재 기업명 0).
//   - 거르지 않는다: 받은 요청을 calls 에 적고(method·path·body·headers·바이트 수), 서버 규칙대로 답한다.
//   - 경로: POST /runs · GET /runs/{id} · GET /dataverify/runs(DV2b) · GET /dataverify/runs/{id}/result · GET /runs/{id}/files/{name}.
//   - GET /dataverify/runs: 새 것 먼저(createdAt·id 내림), status 여러 번·mine=true(부른 사람 = createdBy.userId 가 FAKE_ME)·limit(≤20)·
//     offset. 줄은 서버 짓기(dataverify/service/actions/runs.py)를 흉내 낸다: source·기업명·보고연도·항목 수는 옵션에서(꼴 밖이면 null),
//     failedStep 은 failed 만, currentStep 은 processing 의 running 단계, stages·checks 는 done 의 digest(기본 결과에서 셈 — FakeRun.digest 로 덮음).
//   - POST /runs: module dataverify 아님·options 의 열쇠가 input 이나 input·source 가 아님 → 400 INVALID_OPTIONS · documentId 를 주면 422
//     DOCUMENT_NOT_ACCEPTED · Idempotency-Key 가 소문자 UUID 가 아니면 422, 본 열쇠·같은 본문이면 앞 실행 201, 본 열쇠·다른 본문 409
//     IDEMPOTENCY_KEY_REUSED(본문에 launchKey 가 들어 있다 — 같은 열쇠·다른 launchKey 도 409) · launchKey(DV2d)가 소문자 UUID 가 아니면 422
//     VALIDATION_ERROR, 앞 실행과 같은 launchKey 면 409 LAUNCH_KEY_REUSED(runs.py:20-27 —
//     실서버는 이어 돌기에서만 거절하나 흉내는 모든 새 POST 에서 거절해 더 엄격하다). 크기 상한은 재지 않는다(그 갈래는 override 로 — 서버 셈은 웹 model 이 흉내 낸다).
//   - 결과: 끝나지 않음(queued·processing·failed) 409 RUN_NOT_DONE, 없는 실행 404. 파일은 files 에 든 이름만.
//   - POST /dataverify/edk/read(DVX1 ②): 받은 바이트 수만 적고(내용은 보지 않는다) 정해 둔 갈래를 낸다 — 기본 fakeEdkReadOk(), 갈래를
//     바꾸려면 override(edkRejected(kind)). GET /dataverify/edk/template: 지어낸 바이트 + 서버 머리 셋(Content-Type·Content-Disposition
//     filename*=utf-8''…·nosniff). year 는 calls 의 search 로 본다.
// override 에 「메서드 경로」 → 답(차례 목록도 된다. 끊김은 던지는 함수로)을 주면 그 경로는 그 답을 낸다.
// advance(runId, {status, …}) 로 실행 상태를 바꾼다. done 이면 결과(기본 fakeResult)·파일(기본 엑셀 하나)을 단다.
import { createApi } from '../../../shared/api/index.ts';
import { STEP_NAMES } from '../model/index.ts';
import type { StepStatus } from '../model/index.ts';
import { edkData, fakeInput, fakeResult } from '../model/testing.ts';
import { UUID_PATTERN } from './ids.ts';
import { createDataverifyServerStore } from './server.ts';
import type { DataverifyServerDeps } from './server.ts';

export interface FakeDataverifyCall {
  method: string;
  path: string;
  /** JSON 본문(JSON 이 아니면 undefined). */
  body: unknown;
  /** 본문 바이트 수. */
  octets: number;
  /** 물음 글(?year=… — 없으면 빈 글). */
  search: string;
  headers: Headers;
}

type Answer = () => Response | Promise<Response>;
type Json = Record<string, unknown>;

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
/** 답을 받지 못함(끊김). */
export const unreachable = (): Response => {
  throw new TypeError('network down');
};

export interface FakeStep {
  step: string;
  status: StepStatus;
  done: number | null;
  total: number | null;
}
export interface FakeRun {
  id: number;
  module: string;
  options: Json;
  status: 'queued' | 'processing' | 'done' | 'failed';
  steps: FakeStep[];
  failedStep: string | null;
  errorCode: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  files: string[];
  result: Json | null;
  /** 만든 사람(목록 줄 createdBy). 기본 FAKE_ME. */
  createdBy: { userId: number; name: string };
  /** done 의 요약(dataverify.digest@1 의 stages·checks). null 이면 결과에서 셈(옛 실행처럼 비우려면 'none'). */
  digest: { stages: Json; checks: Json } | 'none' | null;
}

/** 시험의 「나」(mine=true 가 고르는 사람). */
export const FAKE_ME = { userId: 7, name: '담당자 A' };
export const FAKE_OTHER = { userId: 8, name: '담당자 B' };

/** 단계 다섯: 앞의 doneUntil 개는 done, 그다음 하나는 at, 나머지 pending. */
export function fakeSteps(doneUntil: number, at?: StepStatus): FakeStep[] {
  return STEP_NAMES.map((step, index) => ({
    step,
    status:
      index < doneUntil ? 'done'
      : index === doneUntil && at !== undefined ? at
      : 'pending',
    done: null,
    total: null,
  }));
}

export const FAKE_CREATED_AT = '2026-10-19T10:40:00+09:00';
export const FAKE_FINISHED_AT = '2026-10-19T10:58:00+09:00';
/** 지어낸 엑셀 바이트(실제 파일이 아니다 — 「PK」 머리만). */
export const FAKE_FILE_BYTES = new Uint8Array([80, 75, 3, 4, 9, 9]);
export const REPORT = 'dataverify-report.xlsx';

/** 지어낸 양식 바이트(실제 엑셀이 아니다 — 「PK」 머리만)와 서버가 다는 이름(EDK-인벤토리-양식.xlsx). */
export const FAKE_TEMPLATE_BYTES = new Uint8Array([80, 75, 3, 4, 7, 7, 7]);
export const FAKE_TEMPLATE_NAME = 'EDK-인벤토리-양식.xlsx';

/** 엑셀 읽기 ok 답(서버 꼴 — data 는 「환경」만, 나머지 테마는 수로). 기본은 edkData() 의 환경 둘 · 뺀 테마 둘(항목 둘). */
export function fakeEdkReadOk(extra: Json = {}): Json {
  const env = (edkData() as { 환경: Json[] }).환경;
  return {
    ok: true,
    data: { 환경: env },
    itemCount: env.length,
    skipped: { themes: 2, items: 2 },
    years: ['2022', '2023', '2024'],
    skippedEmptyRows: 3,
    ignoredColumns: 1,
    ...extra,
  };
}

/** 엑셀 읽기 거절 답(message 는 지어낸 글 — 화면에 나오면 안 된다). */
export function edkRejected(
  kind: string,
  row: number | null = null,
  column: number | null = null,
): Json {
  return { ok: false, kind, row, column, message: `지어낸-${kind}-글` };
}

export function fakeRun(id: number, extra: Partial<FakeRun> = {}): FakeRun {
  return {
    id,
    module: 'dataverify',
    options: { input: fakeInput() },
    status: 'queued',
    steps: fakeSteps(0),
    failedStep: null,
    errorCode: null,
    createdAt: FAKE_CREATED_AT,
    startedAt: null,
    finishedAt: null,
    files: [],
    result: null,
    createdBy: FAKE_ME,
    digest: null,
    ...extra,
  };
}

export interface AdvanceInput {
  status: FakeRun['status'];
  steps?: FakeStep[];
  errorCode?: string | null;
  /** done 의 결과(기본 fakeResult()). */
  result?: Json;
  /** 지은 파일(기본 done 이면 엑셀 하나). */
  files?: string[];
}

/** 결과에서 digest 셈(서버 outputs/digest.py 흉내 — 시험 값만 맞으면 된다: OK·FAIL·note 있는 해). */
export function digestOf(
  result: Json | null,
): { stages: Json; checks: Json } | null {
  if (result === null) return null;
  const head = (stage: unknown) => {
    const s = (stage ?? {}) as Json;
    return {
      status: s.status,
      partial: s.status === 'done' ? s.partial : null,
    };
  };
  const checks = { ok: 0, fail: 0, notComputed: 0, naValues: 0, toolErrors: 0 };
  const review = (result.review ?? {}) as Json;
  for (const check of (review.checks ?? []) as Json[]) {
    if (check.kind === 'error') checks.toolErrors += 1;
    for (const year of (check.years ?? []) as Json[]) {
      if (year.note !== null && year.note !== undefined)
        checks.notComputed += 1;
      else if (year.status === 'OK') checks.ok += 1;
      else if (year.status === 'FAIL') checks.fail += 1;
    }
  }
  return {
    stages: {
      plan: head(result.plan),
      review: head(result.review),
      insight: head(result.insight),
    },
    checks,
  };
}

export interface FakeDataverifyServerOptions {
  baseUrl?: string;
  runs?: FakeRun[];
  nextRunId?: number;
}

export function fakeDataverifyServer({
  baseUrl = 'http://test.local/api',
  runs = [],
  nextRunId = 30,
}: FakeDataverifyServerOptions = {}) {
  const calls: FakeDataverifyCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const runMap = new Map(runs.map((run) => [run.id, { ...run }]));
  let runSeq = nextRunId;
  const runKeys = new Map<string, { id: number; body: string }>();
  /** 실행을 만든 launchKey(서버 LK1 — 앞 실행과 같으면 409). */
  const launchKeys = new Set<string>();

  const basePath = new URL(baseUrl).pathname;
  const pathOf = (url: URL) => url.pathname.slice(basePath.length);

  /** 서버 짓기(actions/runs.py) 흉내 — 옵션 꼴 밖이면 그 칸만 null. */
  const rowOut = (run: FakeRun) => {
    const input = (run.options.input ?? null) as Json | null;
    const company = (input?.company ?? null) as Json | null;
    const env = ((input?.data ?? null) as Json | null)?.['환경'];
    const source = run.options.source as Json | undefined;
    const sourceOk =
      source !== undefined &&
      ((source.kind === 'paste' && Object.keys(source).length === 1) ||
        (source.kind === 'file' &&
          typeof source.name === 'string' &&
          Object.keys(source).length === 2));
    const digest =
      run.status !== 'done' || run.digest === 'none' ?
        null
      : (run.digest ?? digestOf(run.result));
    return {
      id: run.id,
      status: run.status,
      createdAt: run.createdAt,
      finishedAt: run.finishedAt,
      createdBy: { ...run.createdBy },
      source: sourceOk ? structuredClone(source) : null,
      companyName: typeof company?.name === 'string' ? company.name : null,
      reportingYear:
        typeof company?.reportingYear === 'string' ?
          company.reportingYear
        : null,
      itemCount: Array.isArray(env) ? env.length : null,
      failedStep: run.status === 'failed' ? run.failedStep : null,
      currentStep:
        run.status === 'processing' ?
          (run.steps.find((s) => s.status === 'running')?.step ?? null)
        : null,
      stages: digest === null ? null : structuredClone(digest.stages),
      checks: digest === null ? null : structuredClone(digest.checks),
    };
  };

  const runOut = (run: FakeRun) => ({
    id: run.id,
    module: run.module,
    flowId: `${run.module}.colab@156`,
    documentId: null,
    options: structuredClone(run.options),
    status: run.status,
    steps: run.steps.map((s) => ({ ...s })),
    createdAt: run.createdAt,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
    failedStep: run.failedStep,
    errorCode: run.errorCode,
    errorMessage: run.errorCode === null ? null : '지어낸 오류 글',
    resumedFromRunId: null,
    resultShapes: run.result === null ? [] : ['dataverify.result@2'],
    files: [...run.files],
  });

  function listOut(query: URLSearchParams): Response {
    const statuses = query.getAll('status');
    const limit = Number(query.get('limit') ?? '20');
    const offset = Number(query.get('offset') ?? '0');
    if (!(limit >= 1 && limit <= 20) || !(offset >= 0))
      return refusal(422, 'VALIDATION_ERROR');
    const mine = query.get('mine') === 'true';
    const all = [...runMap.values()]
      .filter((run) => run.module === 'dataverify')
      .filter((run) => statuses.length === 0 || statuses.includes(run.status))
      .filter((run) => !mine || run.createdBy.userId === FAKE_ME.userId)
      .sort((a, b) =>
        a.createdAt === b.createdAt ?
          b.id - a.id
        : b.createdAt.localeCompare(a.createdAt),
      );
    const results = all.slice(offset, offset + limit).map(rowOut);
    return json(200, {
      count: all.length,
      isNext: offset + limit < all.length,
      results,
    });
  }

  function answer(
    method: string,
    path: string,
    body: unknown,
    headers: Headers,
    query: URLSearchParams = new URLSearchParams(),
  ): Response {
    if (method === 'POST' && path === '/runs') {
      const b = (body ?? {}) as Json;
      const key = headers.get('Idempotency-Key');
      if (key !== null && !UUID_PATTERN.test(key))
        return refusal(422, 'VALIDATION_ERROR');
      const text = JSON.stringify(body);
      if (key !== null) {
        const seen = runKeys.get(key);
        if (seen && seen.body === text)
          return json(201, { id: seen.id, status: 'queued' });
        if (seen) return refusal(409, 'IDEMPOTENCY_KEY_REUSED');
      }
      const launchKey = b.launchKey;
      if (
        launchKey !== undefined &&
        launchKey !== null &&
        (typeof launchKey !== 'string' || !UUID_PATTERN.test(launchKey))
      )
        return refusal(422, 'VALIDATION_ERROR');
      if ('documentId' in b) return refusal(422, 'DOCUMENT_NOT_ACCEPTED');
      const options = b.options as Json | undefined;
      if (
        b.module !== 'dataverify' ||
        typeof options !== 'object' ||
        options === null ||
        !['input', 'input,source'].includes(Object.keys(options).join())
      )
        return refusal(400, 'INVALID_OPTIONS');
      if (typeof launchKey === 'string') {
        if (launchKeys.has(launchKey)) return refusal(409, 'LAUNCH_KEY_REUSED');
        launchKeys.add(launchKey);
      }
      const id = runSeq++;
      runMap.set(id, fakeRun(id, { options: structuredClone(options) }));
      if (key !== null) runKeys.set(key, { id, body: text });
      return json(201, { id, status: 'queued' });
    }
    if (method === 'GET' && path === '/dataverify/runs') return listOut(query);
    if (method === 'POST' && path === '/dataverify/edk/read')
      return json(200, fakeEdkReadOk());
    if (method === 'GET' && path === '/dataverify/edk/template') {
      const year = query.get('year');
      if (year !== null && !/^[0-9]{4}$/.test(year))
        return refusal(422, 'VALIDATION_ERROR');
      return new Response(FAKE_TEMPLATE_BYTES, {
        status: 200,
        headers: {
          'Content-Type':
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(FAKE_TEMPLATE_NAME)}`,
          'X-Content-Type-Options': 'nosniff',
        },
      });
    }
    let match = /^\/runs\/(\d+)$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(404, 'NOT_FOUND');
      return json(200, runOut(run));
    }
    match = /^\/dataverify\/runs\/(\d+)\/result$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run || run.module !== 'dataverify') return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
      if (run.result === null) return refusal(404, 'NOT_FOUND');
      return json(200, run.result);
    }
    match = /^\/runs\/(\d+)\/files\/([^/]+)$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      const name = decodeURIComponent(match[2]!);
      if (!run || !run.files.includes(name)) return refusal(404, 'NOT_FOUND');
      return new Response(FAKE_FILE_BYTES, {
        status: 200,
        headers: {
          'Content-Type':
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename="${name}"`,
        },
      });
    }
    throw new Error(`fake dataverify server: no route ${method} ${path}`);
  }

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(url);
    const bytes = new Uint8Array(await request.clone().arrayBuffer());
    let body: unknown;
    try {
      body =
        bytes.length === 0 ?
          undefined
        : JSON.parse(new TextDecoder().decode(bytes));
    } catch {
      body = undefined;
    }
    calls.push({
      method: request.method,
      path,
      body,
      octets: bytes.length,
      search: url.search,
      headers: new Headers(request.headers),
    });
    const key = `${request.method} ${path}`;
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(
      request.method,
      path,
      body,
      new Headers(request.headers),
      url.searchParams,
    );
  };

  const advance = (runId: number, input: AdvanceInput) => {
    const run = runMap.get(runId);
    if (!run) throw new Error(`no run ${runId}`);
    run.status = input.status;
    if (input.errorCode !== undefined) run.errorCode = input.errorCode;
    if (input.status !== 'queued' && run.startedAt === null)
      run.startedAt = FAKE_CREATED_AT;
    if (input.steps) run.steps = input.steps;
    else if (input.status === 'done') run.steps = fakeSteps(5);
    else if (input.status === 'processing') run.steps = fakeSteps(2, 'running');
    else if (input.status === 'failed') run.steps = fakeSteps(1, 'failed');
    run.failedStep =
      input.status === 'failed' ?
        (run.steps.find((s) => s.status === 'failed')?.step ?? null)
      : null;
    if (input.status === 'done' || input.status === 'failed')
      run.finishedAt ??= FAKE_FINISHED_AT;
    if (input.status === 'done') {
      run.result = input.result ?? fakeResult();
      run.files = input.files ?? [REPORT];
    } else if (input.files) run.files = input.files;
  };

  return {
    calls,
    override,
    runs: runMap,
    send,
    advance,
    /** 그 경로의 부른 수. */
    count: (key: string) =>
      calls.filter((call) => `${call.method} ${call.path}` === key).length,
    /** POST /runs 의 부름들. */
    posts: () =>
      calls.filter((call) => call.method === 'POST' && call.path === '/runs'),
  };
}

export type FakeDataverifyServer = ReturnType<typeof fakeDataverifyServer>;

/** 진짜 실어댑터 + 이 가짜 서버. */
export function serverStoreOf(
  server: FakeDataverifyServer,
  deps: Partial<Omit<DataverifyServerDeps, 'api'>> = {},
  baseUrl = 'http://test.local/api',
) {
  return createDataverifyServerStore({
    api: createApi({ baseUrl, fetch: server.send }),
    ...deps,
  });
}
