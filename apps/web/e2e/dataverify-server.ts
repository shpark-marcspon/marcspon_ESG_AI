// e2e 의 데이터 검증 흉내 서버(밴드 DV2a ③ — e2e/translation-server.ts 꼴, 테스트 73 알림 H7). 빌드한 웹의 실어댑터가 부르는 경로를 page.route 로 채운다.
// 답의 값은 전부 지어낸 것이다(「가상건설」 꼴 — 실재 기업명 0). 포트는 쥐지 않는다 — playwright.config.ts 의 WEB_TEST_PORT 미리보기 서버에 붙는
//   page.route 뿐이다. e2e 는 웹 코드에서 문구 표(config/text.ts)만 들이므로(app/guards/layers.test.ts) 결과·실행의 꼴은 여기서 짓는다.
//   - 경로: POST /api/runs · GET /api/runs/{id} · GET /api/dataverify/runs(DV2b) · GET /api/dataverify/runs/{id}/result · GET /api/runs/{id}/files/{name}.
//   - POST /api/runs: 본문 열쇠가 launchKey·module·options 가 아니거나 options 열쇠가 input 이나 input·source 가 아니면 400 INVALID_OPTIONS. Idempotency-Key 를
//     calls 에 적고, 본 열쇠·같은 본문이면 앞 실행(서버 규칙), 본 열쇠·다른 본문이면 409. 새 실행은 queued 로 생긴다.
//   - 실행 읽기 한 번마다 한 걸음(queued → processing → done). 끝난 실행은 결과(dataverify.result@2)와 엑셀 하나를 단다.
//   - GET /api/dataverify/runs(DV2b): 새 것 먼저(id 내림), status 여러 번·mine 은 받기만(거르지 않음 — 단위 시험 몫), 줄은 DV1g 꼴
//     (source·기업명·보고연도·항목 수는 옵션에서, done 은 stages·checks). 목록 읽기는 걸음을 옮기지 않는다. seed(…) 로 실행을 미리 둔다.
//   - POST /api/dataverify/edk/read(DVX1 ②): 받은 바이트 수만 적고(내용은 보지 않는다) edk.answer 의 갈래를 낸다(기본 EDK_OK — 환경 둘).
//     GET /api/dataverify/edk/template: 지어낸 바이트 + 서버 머리 셋(Content-Type·Content-Disposition filename*=utf-8''…·nosniff).
// 로그인은 e2e/session.ts 의 signIn 을 뒤에 부른다(route 는 나중 것이 이긴다 — 이 흉내는 /api/** 를 받고 로그인 경로는 session 이 답한다).
import type { Page, Route } from '@playwright/test';

export interface DataverifyCall {
  method: string;
  path: string;
  body: unknown;
  idempotencyKey: string | null;
  /** 본문 바이트 수. */
  octets: number;
}

type Json = Record<string, unknown>;

const CREATED = '2026-10-19T10:40:00+09:00';
const FINISHED = '2026-10-19T10:58:00+09:00';
const REPORT = 'dataverify-report.xlsx';
/** 지어낸 파일 바이트(「PK」 머리만 — 실제 엑셀이 아니다). */
const BYTES = Buffer.from([80, 75, 3, 4, 9, 9]);
const STEPS = ['load', 'plan', 'review', 'insight', 'report'];

const answer = (route: Route, status: number, body?: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: body === undefined ? '' : JSON.stringify(body),
  });
const refusal = (route: Route, status: number, code: string) =>
  answer(route, status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

interface Run {
  id: number;
  options: Json;
  status: 'queued' | 'processing' | 'done';
}

/** 목록 줄(DV1g DataverifyRunRow 꼴 — 지어낸 값). */
function rowOf(run: Run): Json {
  const input = (run.options.input ?? {}) as {
    company?: Json;
    data?: Json;
  };
  const env = input.data?.['환경'];
  const done = run.status === 'done';
  const head = { status: 'done', partial: false };
  return {
    id: run.id,
    status: run.status,
    createdAt: CREATED,
    finishedAt: done ? FINISHED : null,
    createdBy: { userId: 1, name: '담당자 A' },
    source: run.options.source ?? null,
    companyName: input.company?.name ?? null,
    reportingYear: input.company?.reportingYear ?? null,
    itemCount: Array.isArray(env) ? env.length : null,
    failedStep: null,
    currentStep: run.status === 'processing' ? 'review' : null,
    stages: done ? { plan: head, review: head, insight: head } : null,
    checks:
      done ?
        { ok: 1, fail: 1, notComputed: 0, naValues: 0, toolErrors: 1 }
      : null,
  };
}

const stepsOf = (status: Run['status']) =>
  STEPS.map((step, index) => ({
    step,
    status:
      status === 'done' ? 'done'
      : status === 'queued' ? 'pending'
      : index < 2 ? 'done'
      : index === 2 ? 'running'
      : 'pending',
    done: null,
    total: null,
  }));

const S1 = ['온실가스 배출량', '직접 배출량', 'Scope 1', 'tCO2eq'];
const S2 = ['온실가스 배출량', '간접 배출량', 'Scope 2', 'tCO2eq'];
const S12 = ['온실가스 배출량', '총 배출량', 'Scope 1+2', 'tCO2eq'];

/** 결과(dataverify.result@2). 회사는 실행의 입력에서 — 그 밖은 지어낸 값. */
function resultOf(run: Run): Json {
  const input = run.options.input as { company: Json };
  return {
    schemaVersion: 'dataverify.result@2',
    company: input.company,
    scope: {
      themes: ['환경'],
      itemCount: 2,
      keyItemCount: 1,
      years: ['2023', '2024'],
    },
    settings: {
      model: 'made-up-model',
      tolerance: '0.0',
      temperature: '0.1',
      maxSteps: { plan: 12, review: 6, insight: 12 },
      promptIds: {
        plan: 'dataverify/plan@1',
        review: 'dataverify/review@1',
        insight: 'dataverify/insight@1',
      },
    },
    plan: {
      status: 'done',
      partial: false,
      formulas: ['총 배출량 = 직접 배출량 + 간접 배출량'],
      raw: '지어낸 원문',
      failure: null,
    },
    review: {
      status: 'done',
      partial: false,
      report: '## 1. 합계 검증\n2024 | 1605.0 | 1610.0 | 5.0',
      checks: [
        {
          seq: 1,
          tool: 'sum_check_by_name',
          kind: 'check',
          rule: 'sum',
          items: { byName: { total: S12, a: S1, b: S2 }, raw: null },
          tolerance: '0.0',
          years: [
            {
              year: '2023',
              ok: true,
              status: 'OK',
              diff: '0.0',
              note: null,
              explanation:
                'Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0).',
            },
            {
              year: '2024',
              ok: false,
              status: 'FAIL',
              diff: '5.0',
              note: null,
              explanation:
                'Sum(1300.0 + 310.0) - Target(1605.0) = 5.000000 → exceeds tolerance (0.0).',
            },
          ],
        },
        {
          seq: 2,
          tool: 'ratio_check_by_name',
          kind: 'error',
          message: '지어낸 도구 오류',
          args: {},
        },
      ],
      failure: null,
    },
    insight: {
      status: 'done',
      partial: false,
      report: '지어낸 인사이트 원문',
      rows: [
        {
          area: '환경',
          indicator: 'Scope 2',
          observation: '지어낸 관찰',
          risk: '지어낸 리스크',
          interpretation: '지어낸 해석',
        },
      ],
      rowsParsed: 'parsed',
      sources: [],
      failure: null,
    },
    warnings: [],
  };
}

/** 엑셀 읽기 ok 답(서버 꼴 — data 는 「환경」만, 지어낸 값). */
export const EDK_OK: Json = {
  ok: true,
  data: {
    환경: [
      {
        ID: 90001,
        테마: '환경',
        항목: '가상 직접 배출량',
        대분류: '온실가스 배출량',
        중분류: '직접 배출량',
        소분류: 'Scope 1',
        '입력 방식': '숫자',
        단위: 'tCO2eq',
        values: { '2022': 1200, '2023': 1300, '2024': null },
        핵심데이터: 'Y',
        메모: null,
      },
      {
        ID: 90002,
        테마: '환경',
        항목: '가상 간접 배출량',
        대분류: '온실가스 배출량',
        중분류: '간접 배출량',
        소분류: 'Scope 2',
        '입력 방식': '숫자',
        단위: 'tCO2eq',
        values: { '2022': 300, '2023': 310.5, '2024': 320 },
        핵심데이터: 'N',
        메모: '가상 메모',
      },
    ],
  },
  itemCount: 2,
  skipped: { themes: 2, items: 5 },
  years: ['2022', '2023', '2024'],
  skippedEmptyRows: 40,
  ignoredColumns: 1,
};
/** 엑셀 읽기 거절 답(message 는 지어낸 글 — 화면에 나오면 안 된다). */
export const edkRejected = (kind: string, row: number | null = null): Json => ({
  ok: false,
  kind,
  row,
  column: row === null ? null : 1,
  message: `지어낸-${kind}-글`,
});

export async function fakeDataverifyApi(page: Page) {
  const calls: DataverifyCall[] = [];
  const runs = new Map<number, Run>();
  const keys = new Map<string, { id: number; body: string }>();
  let runSeq = 30;
  /** 엑셀 읽기가 낼 갈래(시험이 바꾼다). */
  const edk: { answer: Json } = { answer: EDK_OK };

  const runOut = (run: Run) => ({
    id: run.id,
    module: 'dataverify',
    flowId: 'dataverify.colab@156',
    documentId: null,
    options: run.options,
    status: run.status,
    steps: stepsOf(run.status),
    createdAt: CREATED,
    startedAt: run.status === 'queued' ? null : CREATED,
    finishedAt: run.status === 'done' ? FINISHED : null,
    failedStep: null,
    errorCode: null,
    errorMessage: null,
    resumedFromRunId: null,
    resultShapes: run.status === 'done' ? ['dataverify.result@2'] : [],
    files: run.status === 'done' ? [REPORT] : [],
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
    const method = request.method();
    let body: unknown;
    try {
      body = request.postData() ? request.postDataJSON() : undefined;
    } catch {
      body = undefined;
    }
    const idempotencyKey = request.headers()['idempotency-key'] ?? null;
    const octets = request.postDataBuffer()?.length ?? 0;
    calls.push({ method, path, body, idempotencyKey, octets });

    if (method === 'POST' && path === '/dataverify/edk/read')
      return answer(route, 200, edk.answer);
    if (method === 'GET' && path === '/dataverify/edk/template')
      return route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: {
          'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent('EDK-인벤토리-양식.xlsx')}`,
          'X-Content-Type-Options': 'nosniff',
        },
        body: BYTES,
      });

    if (method === 'POST' && path === '/runs') {
      const b = (body ?? {}) as Json;
      const options = b.options as Json | undefined;
      if (
        Object.keys(b).sort().join() !== 'launchKey,module,options' ||
        b.module !== 'dataverify' ||
        typeof options !== 'object' ||
        options === null ||
        !['input', 'input,source'].includes(Object.keys(options).join())
      )
        return refusal(route, 400, 'INVALID_OPTIONS');
      const text = JSON.stringify(body);
      if (idempotencyKey !== null) {
        const seen = keys.get(idempotencyKey);
        if (seen && seen.body === text)
          return answer(route, 201, { id: seen.id, status: 'queued' });
        if (seen) return refusal(route, 409, 'IDEMPOTENCY_KEY_REUSED');
      }
      const run: Run = { id: runSeq++, options, status: 'queued' };
      runs.set(run.id, run);
      if (idempotencyKey !== null)
        keys.set(idempotencyKey, { id: run.id, body: text });
      return answer(route, 201, { id: run.id, status: 'queued' });
    }
    if (method === 'GET' && path === '/dataverify/runs') {
      const results = [...runs.values()]
        .sort((a, b) => b.id - a.id)
        .slice(0, 20)
        .map(rowOf);
      return answer(route, 200, {
        count: runs.size,
        isNext: runs.size > 20,
        results,
      });
    }
    let match = /^\/runs\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      const out = runOut(run);
      // 읽기 한 번마다 한 걸음(답은 걸음 앞의 꼴).
      if (run.status === 'queued') run.status = 'processing';
      else if (run.status === 'processing') run.status = 'done';
      return answer(route, 200, out);
    }
    match = /^\/dataverify\/runs\/(\d+)\/result$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(route, 409, 'RUN_NOT_DONE');
      return answer(route, 200, resultOf(run));
    }
    match = /^\/runs\/(\d+)\/files\/([^/]+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      const name = decodeURIComponent(match[2]!);
      if (!run || run.status !== 'done' || name !== REPORT)
        return refusal(route, 404, 'NOT_FOUND');
      return route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: { 'Content-Disposition': `attachment; filename="${name}"` },
        body: BYTES,
      });
    }
    return refusal(route, 404, 'NOT_FOUND');
  });

  const posts = () =>
    calls.filter((call) => call.method === 'POST' && call.path === '/runs');
  /** 실행을 미리 둔다(목록 시험 — id 는 30 아래부터 오르게 준다). */
  const seed = (id: number, options: Json, status: Run['status'] = 'done') =>
    runs.set(id, { id, options, status });
  return { calls, posts, runs, seed, edk };
}
