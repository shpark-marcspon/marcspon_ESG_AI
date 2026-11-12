// e2e 의 중대성평가 흉내 서버(밴드 IRW1 ③ — e2e/dataverify-server.ts 꼴, 테스트 73 알림 H8). 빌드한 웹의 실어댑터가 부르는 경로를 page.route 로 채운다.
// 답의 값은 전부 지어낸 것이다(「가상건설」 꼴 — 실재 기업명 0). 포트는 쥐지 않는다 — playwright.config.ts 의 WEB_TEST_PORT 미리보기 서버에 붙는
//   page.route 뿐이다. e2e 는 웹 코드에서 문구 표(config/text.ts)만 들이므로(app/guards/layers.test.ts) 결과·실행의 꼴은 여기서 짓는다.
//   - 경로: GET /api/materiality/runs · POST /api/runs · GET /api/runs/{id} · GET /api/materiality/runs/{id}/result · GET /api/runs/{id}/files/{name}.
//   - GET /api/materiality/runs: 새 것 먼저(id 내림), status 여러 번은 거름, mine 은 받기만(거르지 않음 — 단위 시험 몫). 줄은 IR3c 꼴
//     (기업명·산업·토픽 수·기간·최신 이슈 반영은 옵션에서, done 은 두 수). 목록 읽기는 걸음을 옮기지 않는다. seed(…) 로 실행을 미리 둔다.
//   - POST /api/runs: 본문 열쇠가 launchKey·module·options 가 아니거나 module 이 materiality 가 아니거나 options 열쇠가 input 하나가 아니면 400.
//     Idempotency-Key 를 calls 에 적고, 본 열쇠·같은 본문이면 앞 실행, 본 열쇠·다른 본문이면 409. 새 실행은 queued 로 생긴다.
//   - 실행 읽기 한 번마다 한 걸음(queued → processing → done). 끝난 실행은 결과(materiality.result@2)와 엑셀 둘을 단다.
//   - 고침(밴드 IRW11): GET·POST /api/materiality/runs/{id}/result/edits — 실행마다 revision·고침(주소 → 값). baseRevision 이 다르면 409
//     EDIT_CONFLICT, 아니면 revision+1. GET result 는 받은 주소만 덮은 판(퍼짐은 흉내 내지 않음 — 웹 api/testing.ts 와 같은 규칙).
//     GET /api/materiality/runs/{id}/report 는 고친 판 최종 엑셀(지어낸 바이트) — calls 에 적힌다.
//   - POST /api/materiality/value-chain/read(밴드 IRW2 ③): 정해 둔 갈래 하나를 200 으로(기본 ok 세 행 — readAs 로 바꿈). 받은 바이트 수와
//     Content-Type 을 calls 에 적는다(맨 바이트 — 본문 JSON 0).
// 로그인은 e2e/session.ts 의 signIn 을 뒤에 부른다(route 는 나중 것이 이긴다 — 이 흉내는 /api/** 를 받고 로그인 경로는 session 이 답한다).
import type { Page, Route } from '@playwright/test';

export interface MaterialityCall {
  method: string;
  path: string;
  query: string;
  body: unknown;
  idempotencyKey: string | null;
  contentType: string | null;
  bytes: number;
}

type Json = Record<string, unknown>;
type Status = 'queued' | 'processing' | 'done' | 'failed';

const CREATED = '2026-10-19T14:00:00+09:00';
const STARTED = '2026-10-19T14:02:00+09:00';
const FINISHED = '2026-10-19T14:39:00+09:00';
export const REPORT = 'materiality-final-report.xlsx';
export const RESEARCH = 'materiality-websearch.xlsx';
/** 지어낸 파일 바이트(「PK」 머리만 — 실제 엑셀이 아니다). */
const BYTES = Buffer.from([80, 75, 3, 4, 9, 9]);
const STEPS = [
  'load',
  'regulation',
  'keywords',
  'controversy',
  'report',
  'part2_seed',
  'impact',
  'financial',
  'pathway',
  'report_iro',
];

/** 가치사슬 읽기 ok(지어낸 세 행 — 셋째 행 밸류체인은 서버가 글 그대로 준 「중류」라 화면이 비운다). */
export const VALUE_CHAIN_OK: Json = {
  ok: true,
  rows: [
    {
      business_unit: '가상 부문',
      business_unit_description: '가상 시공',
      value_chain_stage: '자체운영',
      stakeholder: '근로자',
      business_activity: '안전 관리',
    },
    {
      business_unit: '가상 부문',
      business_unit_description: '가상 시공',
      value_chain_stage: '업스트림',
      stakeholder: '협력회사',
      business_activity: '자재 구매',
    },
    {
      business_unit: '가상 부문 둘',
      business_unit_description: '',
      value_chain_stage: '중류',
      stakeholder: '고객',
      business_activity: '',
    },
  ],
  rowCount: 3,
};

/** 지어낸 입력(materiality.input@1). */
export function inputOf(company = '가상건설'): Json {
  return {
    schemaVersion: 'materiality.input@1',
    company: { name: company },
    industries: [
      {
        standard: 'SASB',
        industryName: 'Engineering & Construction Services',
        description: '가상 설명',
      },
    ],
    topics: [
      { topic: '기후변화 대응', description: '가상 설명' },
      { topic: '안전보건', description: '가상 설명' },
    ],
    geoScope: '가상 범위',
    userLocation: 'KR',
    mainLanguage: '한국어',
    dateRange: '2025-01-01~오늘까지',
    sector: 'non_financial',
    latestEventMode: false,
    subtopicsByTopic: null,
    valueChain: null,
  };
}

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
  status: Status;
  createdBy: { userId: number; name: string };
}

const stepsOf = (status: Status) =>
  STEPS.map((step, index) => ({
    step,
    status:
      status === 'done' ? 'done'
      : status === 'queued' ? 'pending'
      : status === 'failed' ?
        index < 2 ? 'done'
        : index === 2 ? 'failed'
        : 'pending'
      : index < 3 ? 'done'
      : index === 3 ? 'running'
      : 'pending',
    done: null,
    total: null,
  }));

const context = (title: string) => ({
  regulations: [
    {
      title: `${title} 규제`,
      summary: `${title} 규제 요약`,
      url: `https://example.com/reg/${encodeURIComponent(title)}`,
    },
  ],
  controversies: [],
});

/** 결과(materiality.result@2 — 거울 strict 를 지나는 꼴). 회사는 실행의 입력에서 — 그 밖은 지어낸 값. */
function resultOf(run: Run): Json {
  const input = run.options.input as Json;
  const subtopic = (name: string) => ({
    name,
    description: `${name} 설명`,
    autofilled: false,
    impact: {
      status: 'done',
      parsed: {},
      rows: [
        {
          impactDefinition: `${name} 영향`,
          impactType: '부정',
          // IRW10: 가치사슬 활동 열(IR-04 r2)이 빈 「–」만 찍히지 않게 — 짧은 것 하나·두 줄을 넘는 긴 것 하나(지어낸 글).
          valueChainActivities: [
            `${name} 활동 · 자재 조달`,
            `${name} 활동 · 여러 공정이 겹치는 자리의 관리와 작업 절차 운영을 길게 적은 지어낸 글`,
          ],
          context: context(name),
        },
      ],
    },
    financial: {
      status: 'done',
      parsed: {},
      rows: [
        {
          impactDefinition: `${name} 재무`,
          impactType: '리스크',
          riskType: '리스크-규제 및 법률',
          valueChainActivities: [`${name} 활동 · 현장 운영`],
          context: context(name),
        },
      ],
    },
    pathway: {
      status: 'done',
      parsed: {},
      rows: [
        {
          i: 1,
          impactDefinition: `${name} 경로`,
          impactDriver: `${name} 요인`,
          businessImpact: `${name} 비즈니스`,
          financialImpact: `${name} 재무 영향`,
          impactType: '리스크',
          riskType: '리스크-규제 및 법률',
          context: context(name),
        },
      ],
    },
  });
  const outcome = {
    status: 'done',
    parsed: {},
    items: [],
    selfCheck: null,
    topicNameMismatch: false,
  };
  const topics = ['기후변화 대응', '안전보건'];
  return {
    schemaVersion: 'materiality.result@2',
    company: input.company,
    scope: {
      topicCount: 2,
      sector: 'non_financial',
      whitelist: 'cell73',
      dateRange: input.dateRange,
      geoScope: '가상 범위',
      userLocation: 'KR',
      mainLanguage: '한국어',
      latestEventMode: false,
    },
    settings: {
      model: 'made-up-model',
      temperature: '0.1',
      searchContextSize: 'low',
      promptIds: { regulation: null, keywords: null, controversy: null },
      part2: {
        model: 'made-up-model',
        maxOutputTokens: 100,
        latestEventMode: false,
        promptIds: { impact: null, financial: null, pathway: null },
      },
    },
    part1: {
      keywords: { status: 'not_run', message: '지어낸 서버 글' },
      topics: topics.map((topic) => ({
        topic,
        description: '가상 설명',
        keywordStr: null,
        regulation: outcome,
        controversy: outcome,
      })),
    },
    part2: {
      status: 'done',
      input: { source: 'result' },
      topics: topics.map((topic, index) => ({
        topic,
        description: '가상 설명',
        subtopics: [subtopic(`가상 서브토픽 ${index + 1}`)],
      })),
    },
    warnings: [],
  };
}

/** 목록 줄(IR3c MaterialityRunRow 꼴 — 지어낸 값). */
function rowOf(run: Run): Json {
  const input = (run.options.input ?? {}) as Json;
  const done = run.status === 'done';
  return {
    id: run.id,
    status: run.status,
    createdAt: CREATED,
    startedAt: run.status === 'queued' ? null : STARTED,
    finishedAt: done || run.status === 'failed' ? FINISHED : null,
    createdBy: run.createdBy,
    companyName: (input.company as Json | undefined)?.name ?? null,
    industries:
      Array.isArray(input.industries) ?
        (input.industries as Json[]).map((item) => ({
          standard: item.standard,
          industryName: item.industryName,
        }))
      : null,
    topicCount: Array.isArray(input.topics) ? input.topics.length : null,
    dateRange: input.dateRange ?? null,
    latestEventMode: input.latestEventMode ?? null,
    failedStep: run.status === 'failed' ? 'keywords' : null,
    currentStep: run.status === 'processing' ? 'controversy' : null,
    impactRows: done ? 2 : null,
    pathwayRows: done ? 2 : null,
  };
}

export async function fakeMaterialityApi(page: Page) {
  const calls: MaterialityCall[] = [];
  const runs = new Map<number, Run>();
  const keys = new Map<string, { id: number; body: string }>();
  let runSeq = 30;
  let valueChainRead: Json = VALUE_CHAIN_OK;
  const ME = { userId: 1, name: '담당자 A' };
  /** 실행마다 고침(밴드 IRW11). */
  const edits = new Map<
    number,
    { revision: number; current: Map<string, string | null> }
  >();
  const editsOf = (id: number) => {
    let found = edits.get(id);
    if (!found) {
      found = { revision: 0, current: new Map() };
      edits.set(id, found);
    }
    return found;
  };
  const walk = (body: unknown, pointer: string) => {
    const parts = pointer.split('/').slice(1);
    const last = parts.pop()!;
    let at: unknown = body;
    for (const part of parts)
      at =
        at === null || typeof at !== 'object' ? undefined : (at as Json)[part];
    return { parent: at as Json | undefined, last };
  };
  const editedOf = (run: Run) => {
    const out = resultOf(run);
    for (const [pointer, value] of editsOf(run.id).current) {
      const { parent, last } = walk(out, pointer);
      if (parent && typeof parent === 'object') parent[last] = value;
    }
    return out;
  };
  const editsOut = (run: Run) => {
    const original = resultOf(run);
    const found = editsOf(run.id);
    return {
      schemaVersion: 'materiality.result-edits@1',
      revision: found.revision,
      edits: [...found.current.entries()]
        .map(([pointer, value]) => {
          const { parent, last } = walk(original, pointer);
          return {
            pointer,
            value,
            original: (parent?.[last] ?? null) as string | null,
          };
        })
        .filter((entry) => entry.value !== entry.original)
        .map((entry) => ({
          ...entry,
          editedAt: '2026-11-03T14:28:05+09:00',
          editedBy: { name: ME.name },
        })),
    };
  };

  const runOut = (run: Run) => ({
    id: run.id,
    module: 'materiality',
    flowId: 'materiality.iro@155',
    documentId: null,
    options: run.options,
    status: run.status,
    steps: stepsOf(run.status),
    createdAt: CREATED,
    startedAt: run.status === 'queued' ? null : STARTED,
    finishedAt:
      run.status === 'done' || run.status === 'failed' ? FINISHED : null,
    failedStep: run.status === 'failed' ? 'keywords' : null,
    errorCode: run.status === 'failed' ? 'flow_failed' : null,
    errorMessage: run.status === 'failed' ? '지어낸 오류 글' : null,
    resumedFromRunId: null,
    resultShapes:
      run.status === 'done' ?
        ['materiality.result@2', 'materiality.digest@1']
      : [],
    files: run.status === 'done' ? [RESEARCH, REPORT] : [],
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
    calls.push({
      method,
      path,
      query: url.search,
      body,
      idempotencyKey,
      contentType: request.headers()['content-type'] ?? null,
      bytes: request.postDataBuffer()?.length ?? 0,
    });

    if (method === 'POST' && path === '/materiality/value-chain/read')
      return answer(route, 200, valueChainRead);

    if (method === 'GET' && path === '/materiality/runs') {
      const statuses = url.searchParams.getAll('status');
      const all = [...runs.values()]
        .filter((run) => statuses.length === 0 || statuses.includes(run.status))
        .sort((a, b) => b.id - a.id);
      return answer(route, 200, {
        count: all.length,
        isNext: all.length > 20,
        results: all.slice(0, 20).map(rowOf),
      });
    }
    if (method === 'POST' && path === '/runs') {
      const b = (body ?? {}) as Json;
      const options = b.options as Json | undefined;
      if (
        Object.keys(b).sort().join() !== 'launchKey,module,options' ||
        b.module !== 'materiality' ||
        typeof options !== 'object' ||
        options === null ||
        Object.keys(options).join() !== 'input'
      )
        return refusal(route, 400, 'INVALID_OPTIONS');
      const text = JSON.stringify(body);
      if (idempotencyKey !== null) {
        const seen = keys.get(idempotencyKey);
        if (seen && seen.body === text)
          return answer(route, 201, { id: seen.id, status: 'queued' });
        if (seen) return refusal(route, 409, 'IDEMPOTENCY_KEY_REUSED');
      }
      const run: Run = {
        id: runSeq++,
        options,
        status: 'queued',
        createdBy: ME,
      };
      runs.set(run.id, run);
      if (idempotencyKey !== null)
        keys.set(idempotencyKey, { id: run.id, body: text });
      return answer(route, 201, { id: run.id, status: 'queued' });
    }
    let match = /^\/runs\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      const out = runOut(run);
      // 읽기 한 번마다 한 걸음(답은 걸음 앞의 꼴). 실패한 실행은 그대로.
      if (run.status === 'queued') run.status = 'processing';
      else if (run.status === 'processing') run.status = 'done';
      return answer(route, 200, out);
    }
    match = /^\/materiality\/runs\/(\d+)\/result$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(route, 409, 'RUN_NOT_DONE');
      return answer(route, 200, editedOf(run));
    }
    match = /^\/materiality\/runs\/(\d+)\/result\/edits$/.exec(path);
    if (match) {
      const run = runs.get(Number(match[1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(route, 409, 'RUN_NOT_DONE');
      if (method === 'GET') return answer(route, 200, editsOut(run));
      const b = (body ?? {}) as Json;
      const found = editsOf(run.id);
      if (b.baseRevision !== found.revision)
        return refusal(route, 409, 'EDIT_CONFLICT');
      if (!Array.isArray(b.changes) || b.changes.length === 0)
        return refusal(route, 400, 'INVALID_EDIT');
      found.revision += 1;
      for (const change of b.changes as Json[]) {
        const value = change.value as string | null;
        found.current.set(
          change.pointer as string,
          value === null || value.trim() === '' ? null : value,
        );
      }
      return answer(route, 200, editsOut(run));
    }
    match = /^\/materiality\/runs\/(\d+)\/report$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      if (!run || run.status !== 'done')
        return refusal(route, 404, 'NOT_FOUND');
      return route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: { 'Content-Disposition': `attachment; filename="${REPORT}"` },
        body: BYTES,
      });
    }
    match = /^\/runs\/(\d+)\/files\/([^/]+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.get(Number(match[1]));
      const name = decodeURIComponent(match[2]!);
      if (
        !run ||
        run.status !== 'done' ||
        (name !== REPORT && name !== RESEARCH)
      )
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
  /** 실행을 미리 둔다(id 는 30 아래부터 오르게 준다). */
  const seed = (
    id: number,
    status: Status,
    options: Json = { input: inputOf() },
    createdBy = ME,
  ) => runs.set(id, { id, options, status, createdBy });
  /** 가치사슬 읽기가 낼 갈래(ok 나 {ok: false, kind, row, column, message}). */
  const readAs = (body: Json) => {
    valueChainRead = body;
  };
  const reads = () =>
    calls.filter(
      (call) =>
        call.method === 'POST' && call.path === '/materiality/value-chain/read',
    );
  return { calls, posts, reads, runs, seed, readAs };
}
