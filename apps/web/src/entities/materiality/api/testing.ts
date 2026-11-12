// 시험용 가짜 중대성평가 서버(밴드 IRW1 ①). 어댑터·훅·화면·경로 시험이 같이 쓴다(공개 표면이 아니다 — 시험만 직접 가져온다).
// 답의 꼴은 api-py 의 경로(generated/api.d.ts)와 계약(RunOut·materiality.result@2)을 따른다. 값은 전부 지어낸 것이다(실재 기업명 0).
// 데이터 검증 api/testing.ts 꼴을 옮겨 적었다(가져오지 않는다).
//   - 거르지 않는다: 받은 요청을 calls 에 적고(method·path·body·headers), 서버 규칙대로 답한다.
//   - 경로: POST /runs · GET /runs/{id} · GET /materiality/runs(③) · GET /materiality/runs/{id}/result · GET /runs/{id}/files/{name}.
//   - GET /materiality/runs: 새 것 먼저(createdAt·id 내림), status 여러 번·mine=true(부른 사람 = createdBy.userId 가 FAKE_ME)·limit(1~20)·offset.
//     줄은 서버 짓기(materiality/service/actions/runs.py)를 흉내 낸다: 기업명·산업(기준·이름)·토픽 수·기간·최신 이슈 반영은 옵션에서
//     (꼴 밖이면 그 칸 null), failedStep 은 failed 만, currentStep 은 processing 의 running 단계, 두 수는 done 의 결과에서 셈
//     (digest@1 흉내 — part2 not_run 이면 null, FakeRun.digest 로 덮음·'none' 이면 옛 실행처럼 null).
//   - POST /runs: module materiality 아님·options 의 열쇠가 input 하나가 아님 → 400 INVALID_OPTIONS · documentId·resumeFromRunId·flowId 를
//     주면 422 VALIDATION_ERROR(이 화면은 싣지 않는다 — 흉내가 더 엄격하다) · Idempotency-Key 가 소문자 UUID 가 아니면 422, 본 열쇠·같은
//     본문이면 앞 실행 201, 본 열쇠·다른 본문 409 IDEMPOTENCY_KEY_REUSED · launchKey 가 소문자 UUID 가 아니면 422, 앞 실행과 같은 launchKey 면
//     409 LAUNCH_KEY_REUSED(실서버는 이어 돌기에서만 — 흉내가 더 엄격하다). 같은 options 의 두 번째 실행은 201(★A — actions/runs.py:273).
//   - POST /materiality/value-chain/read(밴드 IRW2): 맨 바이트를 받아 valueChain(정해 둔 답 — 기본 FAKE_VALUE_CHAIN_OK)을 200 으로. 빈 본문은
//     {ok:false, not_xlsx}(서버와 같다). 바이트는 calls 의 bytes 에.
//   - 결과: 끝나지 않음(queued·processing·failed) 409 RUN_NOT_DONE, 없는 실행·중대성평가 아님 404. 파일은 files 에 든 이름만.
//   - resultShapes 는 done 이면 둘(materiality.result@2 · materiality.digest@1 — IR3c 뒤 서버 꼴, 감독 5e 알림 10-26). 어댑터는 읽지 않는다.
//   - 고침(밴드 IRW11): GET·POST /materiality/runs/{id}/result/edits — 실행마다 revision·고침(바른 주소 → 지금 값)을 쥔다. POST 는
//     baseRevision 이 다르면 409 EDIT_CONFLICT, 주소가 POINTER_PATTERN 밖·본문 꼴 틀림이면 400 INVALID_EDIT, 아니면 revision+1 로 덮는다
//     (퍼짐·바른 주소 바꿈은 흉내 내지 않는다 — 받은 주소 그대로). GET result 는 **받은 주소만** 덮은 판을 낸다(퍼진 판이 필요한 시험은
//     고친 판 본문을 result 로). 고침 목록은 지금 값이 원문과 다른 칸만, 받은 차례. 시각은 editedAt(바꿀 수 있음), 사람은 FAKE_ME.
//   - GET /materiality/runs/{id}/report: 고친 판 최종 엑셀(blob) — 결과가 없으면 404·끝나지 않음 409(서버 actions/report.py 흉내).
// override 에 「메서드 경로」 → 답(차례 목록도 된다. 끊김은 던지는 함수로)을 주면 그 경로는 그 답을 낸다.
// advance(runId, {status, …}) 로 실행 상태를 바꾼다. done 이면 결과(기본 fakeResult)·파일(기본 최종 엑셀 하나)을 단다.
import { createApi } from '../../../shared/api/index.ts';
import { STEP_LINES } from '../model/index.ts';
import type { StepStatus } from '../model/index.ts';
import { POINTER_PATTERN } from '../model/index.ts';
import { fakeInput, fakeResult } from '../model/testing.ts';
import { UUID_PATTERN } from './ids.ts';
import { createMaterialityServerStore } from './server.ts';
import type { MaterialityServerDeps } from './server.ts';

export interface FakeMaterialityCall {
  method: string;
  path: string;
  /** 쿼리(목록의 status·mine·limit·offset). */
  query: URLSearchParams;
  /** JSON 본문(JSON 이 아니면 undefined). */
  body: unknown;
  /** 받은 본문 바이트 그대로. */
  bytes: Uint8Array;
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

/** 서버 단계 열(★B — iro_155.py:163-170 차례). */
export const STEP_NAMES: readonly string[] = STEP_LINES.flatMap(
  ({ steps }) => steps,
);

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
  /** done 의 요약(materiality.digest@1 의 두 수). null 이면 결과에서 셈, 'none' 이면 요약 없는 옛 실행. */
  digest:
    { impactRows: number | null; pathwayRows: number | null } | 'none' | null;
}

/** 시험의 「나」(mine=true 가 고르는 사람). */
export const FAKE_ME = { userId: 7, name: '담당자 A' };
export const FAKE_OTHER = { userId: 8, name: '담당자 B' };

/** 단계 열: 앞의 doneUntil 개는 done, 그다음 하나는 at, 나머지 pending. done·total 은 counts 에 있는 단계만 그 값,
 *  없으면 null(IRW6 — 기존 부름은 그대로 null). */
export function fakeSteps(
  doneUntil: number,
  at?: StepStatus,
  counts: Record<string, [number, number]> = {},
): FakeStep[] {
  return STEP_NAMES.map((step, index) => ({
    step,
    status:
      index < doneUntil ? 'done'
      : index === doneUntil && at !== undefined ? at
      : 'pending',
    done: counts[step]?.[0] ?? null,
    total: counts[step]?.[1] ?? null,
  }));
}

export const FAKE_CREATED_AT = '2026-10-19T14:00:00+09:00';
export const FAKE_STARTED_AT = '2026-10-19T14:02:00+09:00';
export const FAKE_FINISHED_AT = '2026-10-19T14:39:00+09:00';
/** 지어낸 엑셀 바이트(실제 파일이 아니다 — 「PK」 머리만). */
export const FAKE_FILE_BYTES = new Uint8Array([80, 75, 3, 4, 9, 9]);
export const REPORT = 'materiality-final-report.xlsx';
export const WEBSEARCH = 'materiality-websearch.xlsx';

export function fakeRun(id: number, extra: Partial<FakeRun> = {}): FakeRun {
  return {
    id,
    module: 'materiality',
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

/** 결과에서 digest@1 의 두 수(서버 outputs 흉내 — 2-1 = impact done rows, 2-2 = pathway done rows, part2 not_run 이면 null). */
export function digestOf(result: Json | null) {
  const part2 = (result?.part2 ?? null) as Json | null;
  if (part2 === null || part2.status !== 'done')
    return { impactRows: null, pathwayRows: null };
  let impactRows = 0;
  let pathwayRows = 0;
  for (const topic of (part2.topics ?? []) as Json[])
    for (const sub of (topic.subtopics ?? []) as Json[]) {
      const impact = sub.impact as Json;
      const pathway = sub.pathway as Json;
      if (impact.status === 'done')
        impactRows += (impact.rows as unknown[]).length;
      if (pathway.status === 'done')
        pathwayRows += (pathway.rows as unknown[]).length;
    }
  return { impactRows, pathwayRows };
}

/** 끝난 실행(결과·두 엑셀 — 화면은 최종 엑셀 단추만). */
export const doneRun = (id: number, extra: Partial<FakeRun> = {}) =>
  fakeRun(id, {
    status: 'done',
    steps: fakeSteps(STEP_NAMES.length),
    startedAt: FAKE_STARTED_AT,
    finishedAt: FAKE_FINISHED_AT,
    files: [WEBSEARCH, REPORT],
    result: fakeResult(),
    ...extra,
  });

export interface AdvanceInput {
  status: FakeRun['status'];
  steps?: FakeStep[];
  errorCode?: string | null;
  /** done 의 결과(기본 fakeResult()). */
  result?: Json;
  /** 지은 파일(기본 done 이면 두 엑셀). */
  files?: string[];
}

/** 가치사슬 읽기의 지어낸 행(실재 기업 0 — 판 예시 꼴). */
export const FAKE_VALUE_CHAIN_ROWS = [
  {
    business_unit: '가상 부문 A',
    business_unit_description: '가상 시설 시공',
    value_chain_stage: '자체운영',
    stakeholder: '현장 근로자',
    business_activity: '현장 안전 관리',
  },
  {
    business_unit: '가상 부문 A',
    business_unit_description: '가상 자재 조달',
    value_chain_stage: '업스트림',
    stakeholder: '협력회사',
    business_activity: '자재 구매',
  },
  {
    business_unit: '가상 부문 B',
    business_unit_description: '가상 시설 유지 보수',
    value_chain_stage: '가상 단계',
    stakeholder: '발주처',
    business_activity: '하자 보수 운영',
  },
];
export const FAKE_VALUE_CHAIN_OK = {
  ok: true,
  rows: FAKE_VALUE_CHAIN_ROWS,
  rowCount: FAKE_VALUE_CHAIN_ROWS.length,
};
/** 읽지 못함 답 하나(서버 꼴 — message 는 지어낸 글). */
export const valueChainRejected = (
  kind: string,
  row: number | null = null,
  column: number | null = null,
) => ({ ok: false, kind, row, column, message: `지어낸-${kind}` });

export interface FakeMaterialityServerOptions {
  baseUrl?: string;
  runs?: FakeRun[];
  nextRunId?: number;
  /** POST /materiality/value-chain/read 의 답(200 본문). 기본 FAKE_VALUE_CHAIN_OK. */
  valueChain?: unknown;
  /** 고침 저장 시각(+09:00 ISO). 기본 FAKE_EDITED_AT. */
  editedAt?: string;
}

/** 지어낸 고침 시각. */
export const FAKE_EDITED_AT = '2026-11-03T14:28:05+09:00';

type Body = Record<string, unknown>;
/** JSON Pointer 자리의 값을 읽는다(없으면 undefined). */
export function pointerGet(body: unknown, pointer: string): unknown {
  let at: unknown = body;
  for (const part of pointer.split('/').slice(1)) {
    if (typeof at !== 'object' || at === null) return undefined;
    at = (at as Body)[part];
  }
  return at;
}
/** JSON Pointer 자리에 값을 쓴다(그 자리의 부모가 있을 때만). */
export function pointerSet(body: unknown, pointer: string, value: unknown) {
  const parts = pointer.split('/').slice(1);
  const last = parts.pop()!;
  const parent = pointerGet(body, `/${parts.join('/')}`);
  if (typeof parent === 'object' && parent !== null)
    (parent as Body)[last] = value;
}

export function fakeMaterialityServer({
  baseUrl = 'http://test.local/api',
  runs = [],
  nextRunId = 30,
  valueChain = FAKE_VALUE_CHAIN_OK,
  editedAt = FAKE_EDITED_AT,
}: FakeMaterialityServerOptions = {}) {
  /** 실행마다의 고침(바른 주소 → 지금 값·시각). */
  const editMap = new Map<
    number,
    {
      revision: number;
      current: Map<string, { value: string | null; editedAt: string }>;
    }
  >();
  const clock = { editedAt };
  const editsOf = (id: number) => {
    let found = editMap.get(id);
    if (!found) {
      found = { revision: 0, current: new Map() };
      editMap.set(id, found);
    }
    return found;
  };
  /** 받은 주소만 덮은 결과. */
  const editedResult = (run: FakeRun) => {
    const found = editMap.get(run.id);
    if (!found || found.current.size === 0) return run.result;
    const out = structuredClone(run.result);
    for (const [pointer, { value }] of found.current)
      pointerSet(out, pointer, value);
    return out;
  };
  const editsOut = (run: FakeRun) => {
    const found = editsOf(run.id);
    return {
      schemaVersion: 'materiality.result-edits@1',
      revision: found.revision,
      edits: [...found.current.entries()]
        .filter(
          ([pointer, { value }]) => pointerGet(run.result, pointer) !== value,
        )
        .map(([pointer, { value, editedAt: at }]) => ({
          pointer,
          value,
          original: (pointerGet(run.result, pointer) ?? null) as string | null,
          editedAt: at,
          editedBy: { name: FAKE_ME.name },
        })),
    };
  };
  const calls: FakeMaterialityCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const runMap = new Map(runs.map((run) => [run.id, { ...run }]));
  let runSeq = nextRunId;
  const runKeys = new Map<string, { id: number; body: string }>();
  const launchKeys = new Set<string>();

  const basePath = new URL(baseUrl).pathname;
  const pathOf = (url: URL) => url.pathname.slice(basePath.length);

  const runOut = (run: FakeRun) => ({
    id: run.id,
    module: run.module,
    flowId: `${run.module}.iro@155`,
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
    resultShapes:
      run.result === null ?
        []
      : ['materiality.result@2', 'materiality.digest@1'],
    files: [...run.files],
  });

  /** 서버 짓기(actions/runs.py) 흉내 — 옵션 꼴 밖이면 그 칸만 null. */
  const rowOut = (run: FakeRun) => {
    const given = run.options.input;
    const input = (
      typeof given === 'object' && given !== null && !Array.isArray(given) ?
        given
      : {}) as Json;
    const company = input.company as Json | undefined;
    const industries = input.industries;
    const industriesOk =
      Array.isArray(industries) &&
      industries.every(
        (item: Json) =>
          typeof item === 'object' &&
          item !== null &&
          typeof item.standard === 'string' &&
          typeof item.industryName === 'string',
      );
    const digest =
      run.status !== 'done' || run.digest === 'none' ?
        { impactRows: null, pathwayRows: null }
      : (run.digest ?? digestOf(run.result));
    return {
      id: run.id,
      status: run.status,
      createdAt: run.createdAt,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
      createdBy: { ...run.createdBy },
      companyName: typeof company?.name === 'string' ? company.name : null,
      industries:
        industriesOk ?
          (industries as Json[]).map((item) => ({
            standard: item.standard,
            industryName: item.industryName,
          }))
        : null,
      topicCount: Array.isArray(input.topics) ? input.topics.length : null,
      dateRange: typeof input.dateRange === 'string' ? input.dateRange : null,
      latestEventMode:
        typeof input.latestEventMode === 'boolean' ?
          input.latestEventMode
        : null,
      failedStep: run.status === 'failed' ? run.failedStep : null,
      currentStep:
        run.status === 'processing' ?
          (run.steps.find((s) => s.status === 'running')?.step ?? null)
        : null,
      impactRows: digest.impactRows,
      pathwayRows: digest.pathwayRows,
    };
  };

  function listOut(query: URLSearchParams): Response {
    const statuses = query.getAll('status');
    const limit = Number(query.get('limit') ?? '20');
    const offset = Number(query.get('offset') ?? '0');
    if (!(limit >= 1 && limit <= 20) || !(offset >= 0))
      return refusal(422, 'VALIDATION_ERROR');
    const mine = query.get('mine') === 'true';
    const all = [...runMap.values()]
      .filter((run) => run.module === 'materiality')
      .filter((run) => statuses.length === 0 || statuses.includes(run.status))
      .filter((run) => !mine || run.createdBy.userId === FAKE_ME.userId)
      .sort((a, b) =>
        a.createdAt === b.createdAt ?
          b.id - a.id
        : b.createdAt.localeCompare(a.createdAt),
      );
    return json(200, {
      count: all.length,
      isNext: offset + limit < all.length,
      results: all.slice(offset, offset + limit).map(rowOut),
    });
  }

  function answer(
    method: string,
    path: string,
    body: unknown,
    headers: Headers,
    query: URLSearchParams = new URLSearchParams(),
    bytes: Uint8Array = new Uint8Array(),
  ): Response {
    if (method === 'GET' && path === '/materiality/runs') return listOut(query);
    if (method === 'POST' && path === '/materiality/value-chain/read')
      return json(
        200,
        bytes.length === 0 ? valueChainRejected('not_xlsx') : valueChain,
      );
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
      if ('documentId' in b || 'resumeFromRunId' in b || 'flowId' in b)
        return refusal(422, 'VALIDATION_ERROR');
      const options = b.options as Json | undefined;
      if (
        b.module !== 'materiality' ||
        typeof options !== 'object' ||
        options === null ||
        Object.keys(options).join() !== 'input'
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
    let match = /^\/runs\/(\d+)$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run) return refusal(404, 'NOT_FOUND');
      return json(200, runOut(run));
    }
    match = /^\/materiality\/runs\/(\d+)\/result$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run || run.module !== 'materiality')
        return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
      if (run.result === null) return refusal(404, 'NOT_FOUND');
      return json(200, editedResult(run));
    }
    match = /^\/materiality\/runs\/(\d+)\/result\/edits$/.exec(path);
    if (match) {
      const run = runMap.get(Number(match[1]));
      if (!run || run.module !== 'materiality')
        return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
      if (run.result === null) return refusal(404, 'NOT_FOUND');
      if (method === 'GET') return json(200, editsOut(run));
      if (method === 'POST') {
        const b = (body ?? {}) as Json;
        const changes = b.changes;
        if (
          typeof b.baseRevision !== 'number' ||
          !Array.isArray(changes) ||
          changes.length === 0
        )
          return refusal(422, 'VALIDATION_ERROR');
        const found = editsOf(run.id);
        if (b.baseRevision !== found.revision)
          return refusal(409, 'EDIT_CONFLICT');
        const seen = new Set<string>();
        for (const change of changes as Json[]) {
          const pointer = change.pointer;
          if (
            typeof pointer !== 'string' ||
            !POINTER_PATTERN.test(pointer) ||
            seen.has(pointer) ||
            pointerGet(run.result, pointer) === undefined ||
            !(change.value === null || typeof change.value === 'string')
          )
            return refusal(400, 'INVALID_EDIT');
          seen.add(pointer);
        }
        found.revision += 1;
        for (const change of changes as Json[]) {
          const value = change.value as string | null;
          found.current.set(change.pointer as string, {
            value: value === null || value.trim() === '' ? null : value,
            editedAt: clock.editedAt,
          });
        }
        return json(200, editsOut(run));
      }
    }
    match = /^\/materiality\/runs\/(\d+)\/report$/.exec(path);
    if (method === 'GET' && match) {
      const run = runMap.get(Number(match[1]));
      if (!run || run.module !== 'materiality')
        return refusal(404, 'NOT_FOUND');
      if (run.status !== 'done') return refusal(409, 'RUN_NOT_DONE');
      if (run.result === null) return refusal(404, 'NOT_FOUND');
      return new Response(FAKE_FILE_BYTES, {
        status: 200,
        headers: {
          'Content-Type':
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename="${REPORT}"`,
        },
      });
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
    throw new Error(`fake materiality server: no route ${method} ${path}`);
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
      query: new URLSearchParams(url.searchParams),
      body,
      bytes,
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
      bytes,
    );
  };

  const advance = (runId: number, input: AdvanceInput) => {
    const run = runMap.get(runId);
    if (!run) throw new Error(`no run ${runId}`);
    run.status = input.status;
    if (input.errorCode !== undefined) run.errorCode = input.errorCode;
    if (input.status !== 'queued' && run.startedAt === null)
      run.startedAt = FAKE_STARTED_AT;
    if (input.steps) run.steps = input.steps;
    else if (input.status === 'done') run.steps = fakeSteps(STEP_NAMES.length);
    else if (input.status === 'processing') run.steps = fakeSteps(3, 'running');
    else if (input.status === 'failed') run.steps = fakeSteps(1, 'failed');
    run.failedStep =
      input.status === 'failed' ?
        (run.steps.find((s) => s.status === 'failed')?.step ?? null)
      : null;
    if (input.status === 'done' || input.status === 'failed')
      run.finishedAt ??= FAKE_FINISHED_AT;
    if (input.status === 'done') {
      run.result = input.result ?? fakeResult();
      run.files = input.files ?? [WEBSEARCH, REPORT];
    } else if (input.files) run.files = input.files;
  };

  return {
    calls,
    override,
    runs: runMap,
    send,
    advance,
    /** 고침 시각(다음 저장부터). */
    clock,
    /** 다른 사람이 먼저 고친 것처럼 revision 을 올리고 값을 쓴다(409 흉내). */
    editElsewhere: (runId: number, pointer: string, value: string | null) => {
      const found = editsOf(runId);
      found.revision += 1;
      found.current.set(pointer, { value, editedAt: clock.editedAt });
    },
    /** 그 경로의 부른 수. */
    count: (key: string) =>
      calls.filter((call) => `${call.method} ${call.path}` === key).length,
    /** POST /runs 의 부름들. */
    posts: () =>
      calls.filter((call) => call.method === 'POST' && call.path === '/runs'),
  };
}

export type FakeMaterialityServer = ReturnType<typeof fakeMaterialityServer>;

/** 진짜 실어댑터 + 이 가짜 서버. */
export function serverStoreOf(
  server: FakeMaterialityServer,
  deps: Partial<Omit<MaterialityServerDeps, 'api'>> = {},
  baseUrl = 'http://test.local/api',
) {
  return createMaterialityServerStore({
    api: createApi({ baseUrl, fetch: server.send }),
    ...deps,
  });
}
