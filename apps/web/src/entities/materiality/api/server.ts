// 중대성평가 실어댑터(밴드 IRW1 ①). MaterialityStore 꼴을 서버 경로로 맞춘다 — 데이터 검증 api/server.ts(DV2a) 꼴을 따라 지음(가져오지 않는다).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·창·보관소는 모른다.
// 경로(발주서 §2-1):
//   listRuns     GET /materiality/runs?status=(여러 번)&mine=true(참일 때만)&limit=20&offset= → MaterialityRunPage(거울 — 꼴 틀림 rejected,
//                답 없음 unreachable). 검색·기간 거름은 없다(IR3c — 덧붙임 A).
//   getRun       GET /runs/{id} → MaterialityRun {status, steps{step, status, done, total}, failedStep, files, createdAt, startedAt, finishedAt,
//                input | null}. 단계의 done·total 은 둘 다 0 이상 정수이고 done ≤ total 일 때만 값, 아니면 둘 다 null(실행은 버리지 않음 — IRW6).
//                (module 이 materiality 가 아니면 not_found — apps/api-py/esgapi/runs/service/schemas/runs.py:79-96). options.input 은
//                input@1 거울(못 지나면 null).
//   subscribeRun 같은 경로의 폴링(그린워싱 subscribeRun 규칙 — store.ts). 멈춤은 done·failed.
//   getResult    GET /materiality/runs/{id}/result → materiality.result@2(거울). 404 not_found · 409 RUN_NOT_DONE not_done
//                (failed 실행도 409 — materiality/service/actions/result.py:34-43).
//   reportFile   GET /materiality/runs/{id}/report(blob — 고친 판 최종 엑셀, 밴드 IRW11 Q11) → 이름 REPORT_FILE_NAME.
//   getEdits     GET /materiality/runs/{id}/result/edits → materiality.result-edits@1(거울). 거절 갈래는 getResult 와 같다.
//   saveEdits    POST /materiality/runs/{id}/result/edits {baseRevision, changes:[{pointer, value}]} → 200 saved(거울) · 409 EDIT_CONFLICT
//                conflict · 400 INVALID_EDIT invalid · 그 밖 거절·꼴 틀림 failed · 답 없음 unreachable. 서버 message 0.
//   researchFile GET /runs/{id}/files/materiality-websearch.xlsx(blob — 1부 리서치 엑셀, sid:MARC-ENT-449) → 그 이름 그대로.
//   rerun        GET /runs/{id} 의 options 그대로 → POST /runs {module:'materiality', launchKey, options} + 머리 Idempotency-Key(소문자 UUID).
//                resumeFromRunId·flowId·documentId 0(처음부터 — 서버는 accept_options 로 다시 받고 「오늘까지」는 새 날짜, ★A).
//                열쇠·launchKey 는 첫 누름에 새로, 실패(거절·끊김) 뒤 같은 실행·같은 options 면 둘 다 같은 값, 만들어지면 버린다.
//                거절 failed, 답 없음 unreachable(만들었는지 모른다 — 같은 열쇠로 다시 보내면 서버가 앞 실행을 돌려준다).
//   createRun    (IRW2) POST /runs {module:'materiality', launchKey, options:{input}} + Idempotency-Key — 열쇠 규칙은 rerun 과 같다
//                (첫 누름·입력이 바뀌면 둘 다 새로, 실패 뒤 같은 입력이면 같은 값, 만들어지면 버림). 거절(422 포함) failed, 답 없음 unreachable.
//   readValueChain (IRW2) POST /materiality/value-chain/read — 본문은 파일의 맨 바이트(Content-Type xlsx), 답은 ok 두 갈래(거울).
//                거절·꼴 틀림 rejected, 답 없음 unreachable(던진다). 서버 message 는 거울만 지나고 화면에 0.
//   forget       쥔 열쇠를 버린다(요청 0 — 세션이 끝날 때 틀이 부른다).
// id 는 글자다: 나갈 때 `^[1-9][0-9]*$` 만 수로 — 아니면 요청 없이 not_found(구독이면 onMissing, rerun 이면 failed).
// 거절의 서버 message 는 화면에 보이지 않는다(이 파일의 거절 글은 개발자용 영문).
import { asFailure } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import { REPORT_FILE_NAME, RESEARCH_FILE_NAME } from '../model/index.ts';
import type {
  MaterialityRun,
  RunStatus,
  RunStep,
  StepStatus,
} from '../model/index.ts';
import {
  parseInput,
  parseResult,
  parseResultEdits,
  parseRunPage,
  parseValueChainRead,
} from './contract/index.ts';
import { newKey, serverId } from './ids.ts';
import type { NewKey } from './ids.ts';
import { MaterialityStoreError, RUN_PAGE_LIMIT } from './store.ts';
import type {
  MaterialityStore,
  RerunResult,
  SaveEditsResult,
  StoreErrorKind,
} from './store.ts';

/** 폴링 간격 기본(ms). */
export const RUN_POLL_MS = 2000;
/** 값을 받은 뒤 이만큼 잇달아 실패하면 onFailed. */
export const RUN_POLL_FAILURES = 3;
/** 모듈 id. */
export const MODULE = 'materiality';
/** 가치사슬 엑셀 본문의 Content-Type. */
export const XLSX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export interface MaterialityServerDeps {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
  /** 폴링 간격(ms). 기본 RUN_POLL_MS. */
  pollMs?: number;
  /** 새 Idempotency-Key. 기본 newKey(시험이 고정한다). */
  newKey?: NewKey;
  /** 새 launchKey. 기본 newKey(같은 짓개 — 시험이 따로 고정한다). */
  newLaunchKey?: NewKey;
}

type Json = Record<string, unknown>;

const isObject = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value);
const isText = (value: unknown): value is string => typeof value === 'string';
const isTextOrNull = (value: unknown): value is string | null =>
  value === null || typeof value === 'string';
/** 단계 안 진행 수: 둘 다 0 이상 정수이고 done ≤ total 일 때만 값, 아니면 둘 다 null(IRW6). */
const countOf = (
  done: unknown,
  total: unknown,
): Pick<RunStep, 'done' | 'total'> =>
  isInt(done) && isInt(total) && done >= 0 && done <= total ?
    { done, total }
  : { done: null, total: null };
const RUN_STATUSES: readonly unknown[] = [
  'queued',
  'processing',
  'done',
  'failed',
];
const STEP_STATUSES: readonly unknown[] = [
  'pending',
  'running',
  'done',
  'failed',
];

/** Blob 꼴인가(전역 Blob 이 실행 환경마다 다를 수 있어 모양으로 본다). */
const isBlob = (value: unknown): value is Blob =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as Blob).size === 'number' &&
  typeof (value as Blob).type === 'string' &&
  typeof (value as Blob).arrayBuffer === 'function';

/** 실패 → 거절 갈래: 404 류·NOT_FOUND → not_found, RUN_NOT_DONE → not_done, 그 밖 서버 거절 → rejected, 답 없음 → lost. */
function kindOf(failure: ApiFailure, lost: StoreErrorKind): StoreErrorKind {
  if (failure.kind !== 'api') return lost;
  if (failure.code === 'RUN_NOT_DONE') return 'not_done';
  if (failure.code === 'NOT_FOUND' || failure.status === 404)
    return 'not_found';
  return 'rejected';
}

const refuse = (kind: StoreErrorKind, message: string) =>
  new MaterialityStoreError(kind, message);

/** RunOut → MaterialityRun(꼴이 틀리면 null). */
function runOf(
  body: unknown,
): { run: MaterialityRun; module: string; options: Json } | null {
  if (!isObject(body)) return null;
  const { id, module, options, status, steps, files } = body;
  if (
    !isInt(id) ||
    !isText(module) ||
    !isObject(options) ||
    !RUN_STATUSES.includes(status) ||
    !Array.isArray(steps) ||
    !Array.isArray(files) ||
    !files.every(isText) ||
    !isText(body.createdAt) ||
    !isTextOrNull(body.startedAt) ||
    !isTextOrNull(body.finishedAt) ||
    !isTextOrNull(body.failedStep)
  )
    return null;
  const stepList: RunStep[] = [];
  for (const step of steps) {
    if (
      !isObject(step) ||
      !isText(step.step) ||
      !STEP_STATUSES.includes(step.status)
    )
      return null;
    stepList.push({
      step: step.step,
      status: step.status as StepStatus,
      ...countOf(step.done, step.total),
    });
  }
  const input = parseInput(options.input);
  const run: MaterialityRun = {
    runId: String(id),
    status: status as RunStatus,
    steps: stepList,
    failedStep: body.failedStep,
    files: [...files],
    createdAt: body.createdAt,
    startedAt: body.startedAt,
    finishedAt: body.finishedAt,
    input: input.ok ? input.value : null,
  };
  return { run, module, options };
}

export function createMaterialityServerStore({
  api,
  pollMs = RUN_POLL_MS,
  newKey: makeKey = newKey,
  newLaunchKey: makeLaunchKey = newKey,
}: MaterialityServerDeps): MaterialityStore {
  const { client } = api;
  /** 아직 만들어지지 않은 [다시 실행] 하나: 그 실행·본문과 열쇠·launchKey(실패 뒤 다시 누름에 둘 다 같은 값). */
  let pending: {
    source: number;
    body: string;
    key: string;
    launchKey: string;
  } | null = null;
  /** 아직 만들어지지 않은 [평가 시작] 하나: 본문과 열쇠·launchKey(실패 뒤 같은 입력이면 둘 다 같은 값). */
  let pendingNew: { body: string; key: string; launchKey: string } | null =
    null;

  /** 보낸다. 실패는 MaterialityStoreError 로 던진다. lost 는 답을 받지 못했을 때의 갈래(기본 rejected). */
  async function send<T>(
    what: string,
    request: () => Promise<{ data?: T }>,
    lost: StoreErrorKind = 'rejected',
  ): Promise<unknown> {
    let data: T | undefined;
    try {
      ({ data } = await request());
    } catch (error) {
      throw refuse(kindOf(asFailure(error), lost), `${what} failed`);
    }
    if (data === undefined) throw refuse('rejected', `${what}: empty answer`);
    return data;
  }

  const idOrMissing = (id: string, what: string) => {
    const value = serverId(id);
    if (value === null) throw refuse('not_found', `${what}: not a server id`);
    return value;
  };

  async function readRun(id: number) {
    const body = await send(
      'run',
      () => client.GET('/runs/{run_id}', { params: { path: { run_id: id } } }),
      'unreachable',
    );
    const read = runOf(body);
    if (read === null) throw refuse('rejected', 'run: bad shape');
    // 중대성평가가 아닌 실행은 이 화면에 없는 것이다.
    if (read.module !== MODULE)
      throw refuse('not_found', 'run: not materiality');
    return read;
  }

  /** 출력 파일 하나(blob) → 그 이름 그대로. */
  async function readFile(runId: string, name: string) {
    const id = idOrMissing(runId, 'file');
    let answer: { data?: unknown };
    try {
      answer = await client.GET('/runs/{run_id}/files/{name}', {
        params: { path: { run_id: id, name } },
        parseAs: 'blob',
      });
    } catch (error) {
      throw refuse(kindOf(asFailure(error), 'rejected'), 'file failed');
    }
    if (!isBlob(answer.data)) throw refuse('rejected', 'file: not a file');
    return { blob: answer.data, fileName: name };
  }

  const store: MaterialityStore = {
    async listRuns({ status, mine, offset }) {
      const body = await send(
        'run list',
        () =>
          client.GET('/materiality/runs', {
            params: {
              query: {
                ...(status === undefined || status.length === 0 ?
                  {}
                : { status: [...status] }),
                ...(mine ? { mine: true } : {}),
                limit: RUN_PAGE_LIMIT,
                offset,
              },
            },
          }),
        'unreachable',
      );
      const parsed = parseRunPage(body);
      if (!parsed.ok)
        throw refuse('rejected', `run list shape: ${parsed.issues}`);
      return parsed.value;
    },

    forget() {
      pending = null;
      pendingNew = null;
    },

    async createRun(input): Promise<RerunResult> {
      const options = { input };
      const body = JSON.stringify(options);
      if (pendingNew === null || pendingNew.body !== body)
        pendingNew = { body, key: makeKey(), launchKey: makeLaunchKey() };
      const { key, launchKey } = pendingNew;
      let answer: unknown;
      try {
        ({ data: answer } = await client.POST('/runs', {
          params: { header: { 'Idempotency-Key': key } },
          body: { module: MODULE, launchKey, options },
        }));
      } catch (error) {
        return asFailure(error).kind === 'api' ?
            { kind: 'failed' }
          : { kind: 'unreachable' };
      }
      if (!isObject(answer) || !isInt(answer.id)) return { kind: 'failed' };
      if (pendingNew?.key === key) pendingNew = null;
      return { kind: 'started', runId: String(answer.id) };
    },

    async readValueChain(file) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const body = await send(
        'value chain read',
        () =>
          client.POST('/materiality/value-chain/read', {
            // 본문은 맨 바이트(multipart 아님 — 서버 경로의 선언). openapi 의 본문 타입은 글자라 바꿔 싣는다(영문번역 readGlossary 꼴).
            body: bytes as unknown as string,
            bodySerializer: (value: unknown) => value as BodyInit,
            headers: { 'Content-Type': XLSX_MEDIA_TYPE },
          }),
        'unreachable',
      );
      const parsed = parseValueChainRead(body);
      if (!parsed.ok)
        throw refuse('rejected', `value chain read shape: ${parsed.issues}`);
      return parsed.value;
    },

    async getRun(runId) {
      return (await readRun(idOrMissing(runId, 'run'))).run;
    },

    subscribeRun(runId, listener, onMissing, onFailed) {
      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const id = serverId(runId);
      if (id === null) {
        // 요청 없이 없는 실행(해제했으면 부르지 않는다).
        void Promise.resolve().then(() => {
          if (!stopped) onMissing?.();
        });
        return () => {
          stopped = true;
        };
      }
      let received = false;
      let failures = 0;
      const tick = async () => {
        let run: MaterialityRun;
        try {
          run = (await readRun(id)).run;
        } catch (error) {
          if (stopped) return;
          if (
            error instanceof MaterialityStoreError &&
            error.kind === 'not_found'
          ) {
            stopped = true;
            onMissing?.();
            return;
          }
          failures += 1;
          if (!received || failures >= RUN_POLL_FAILURES) {
            stopped = true;
            onFailed?.();
            return;
          }
          timer = setTimeout(() => void tick(), pollMs);
          return;
        }
        if (stopped) return;
        received = true;
        failures = 0;
        listener(run);
        if (run.status === 'queued' || run.status === 'processing')
          timer = setTimeout(() => void tick(), pollMs);
      };
      void tick();
      return () => {
        stopped = true;
        if (timer !== undefined) clearTimeout(timer);
      };
    },

    async getResult(runId) {
      const id = idOrMissing(runId, 'run');
      const body = await send('result', () =>
        client.GET('/materiality/runs/{run_id}/result', {
          params: { path: { run_id: id } },
        }),
      );
      const parsed = parseResult(body);
      if (!parsed.ok)
        throw refuse('rejected', `result shape: ${parsed.issues}`);
      return parsed.value;
    },

    async reportFile(runId) {
      const id = idOrMissing(runId, 'report');
      let answer: { data?: unknown };
      try {
        answer = await client.GET('/materiality/runs/{run_id}/report', {
          params: { path: { run_id: id } },
          parseAs: 'blob',
        });
      } catch (error) {
        throw refuse(kindOf(asFailure(error), 'rejected'), 'report failed');
      }
      if (!isBlob(answer.data)) throw refuse('rejected', 'report: not a file');
      return { blob: answer.data, fileName: REPORT_FILE_NAME };
    },

    async getEdits(runId) {
      const id = idOrMissing(runId, 'run');
      const body = await send('edits', () =>
        client.GET('/materiality/runs/{run_id}/result/edits', {
          params: { path: { run_id: id } },
        }),
      );
      const parsed = parseResultEdits(body);
      if (!parsed.ok) throw refuse('rejected', `edits shape: ${parsed.issues}`);
      return parsed.value;
    },

    async saveEdits(runId, baseRevision, changes): Promise<SaveEditsResult> {
      const id = serverId(runId);
      if (id === null) return { kind: 'failed' };
      let answer: unknown;
      try {
        ({ data: answer } = await client.POST(
          '/materiality/runs/{run_id}/result/edits',
          {
            params: { path: { run_id: id } },
            body: {
              baseRevision,
              changes: changes.map(({ pointer, value }) => ({
                pointer,
                value,
              })),
            },
          },
        ));
      } catch (error) {
        const failure = asFailure(error);
        if (failure.kind !== 'api') return { kind: 'unreachable' };
        if (failure.code === 'EDIT_CONFLICT') return { kind: 'conflict' };
        if (failure.code === 'INVALID_EDIT') return { kind: 'invalid' };
        return { kind: 'failed' };
      }
      const parsed = parseResultEdits(answer);
      return parsed.ok ?
          { kind: 'saved', edits: parsed.value }
        : { kind: 'failed' };
    },

    researchFile: (runId) => readFile(runId, RESEARCH_FILE_NAME),

    async rerun(runId): Promise<RerunResult> {
      const id = serverId(runId);
      if (id === null) return { kind: 'failed' };
      let options: Json;
      try {
        ({ options } = await readRun(id));
      } catch {
        // 읽지 못했으면 보내지 않았다 — 만들어지지 않은 것이 확실하다.
        return { kind: 'failed' };
      }
      const body = JSON.stringify(options);
      if (pending === null || pending.source !== id || pending.body !== body)
        pending = {
          source: id,
          body,
          key: makeKey(),
          launchKey: makeLaunchKey(),
        };
      const { key, launchKey } = pending;
      let answer: unknown;
      try {
        ({ data: answer } = await client.POST('/runs', {
          params: { header: { 'Idempotency-Key': key } },
          body: { module: MODULE, launchKey, options },
        }));
      } catch (error) {
        return asFailure(error).kind === 'api' ?
            { kind: 'failed' }
          : { kind: 'unreachable' };
      }
      if (!isObject(answer) || !isInt(answer.id)) return { kind: 'failed' };
      if (pending?.key === key) pending = null;
      return { kind: 'started', runId: String(answer.id) };
    },
  };

  return store;
}
