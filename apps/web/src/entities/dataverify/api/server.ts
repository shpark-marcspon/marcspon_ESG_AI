// 데이터 검증 실어댑터(밴드 DV2a ①). DataverifyStore 꼴을 서버 경로로 맞춘다 — 영문번역 api/server.ts(TRW1a) 꼴을 따라 지음(가져오지 않는다).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·창·보관소는 모른다. 파일을 올리지 않는다
//   (문서 없는 흐름 — 입력은 options 에 실린다, sid:MARC-ENT-420).
// 경로:
//   startRun     POST /runs {module:'dataverify', launchKey, options:{input, source?}} + 머리 Idempotency-Key(소문자 UUID). documentId·flowId·
//                resumeFromRunId·companyId 0. source 는 준 때만(DV2b — 파일 {kind:'file', name} · 붙여 넣기 {kind:'paste'}). 열쇠는 첫 누름·본문이 바뀔 때만 새로, 실패 뒤 같은 본문이면 같은 열쇠,
//                만들어지면 버린다. launchKey(소문자 UUID, 사람 동작마다 하나 — DV2d)는 Idempotency-Key 와 같은 삶이고 서로 다른 값이다:
//                서버는 IK 본문 sha 에 launchKey 를 넣고(같은 IK·다른 launchKey 는 409 IDEMPOTENCY_KEY_REUSED) 이어 돌기에서 앞 실행과 같은
//                launchKey 는 409 LAUNCH_KEY_REUSED 라(runs.py:20-27, actions/runs.py:346) 다시 보냄은 둘 다 같은 값·새 동작은 둘 다 새로.
//                256KiB 셈은 options 만(launchKey 밖).
//                options 를 파이썬 셈(model/options.ts pyJsonOctets — 서버 runs.py:253-256)으로 재서 256KiB 를 넘으면 보내지 않고 too_large.
//                400 INVALID_OPTIONS 는 message 를 읽지 않고 다시 재서 넘으면 too_large, 아니면 unreadable.
//                그 밖 거절 failed, 답 없음 unreachable(만들었는지 모른다 — 같은 열쇠로 다시 보내면 서버가 앞 실행을 돌려준다).
//   listRuns     GET /dataverify/runs?status=(여러 번)&mine=true(참일 때만)&limit=20&offset= → DataverifyRunPage(거울 — 꼴 틀림 rejected,
//                답 없음 unreachable). 서버 검색·연도 인자는 없다(화면이 받은 20건 안에서 거른다 — sid:MARC-ENT-432).
//   getRun       GET /runs/{id} → DataverifyRun(module 이 dataverify 가 아니면 not_found). options.input·source 는 거울(못 지나면 null).
//   subscribeRun 같은 경로의 폴링(그린워싱 subscribeRun 규칙 — store.ts). 멈춤은 done·failed.
//   getResult    GET /dataverify/runs/{id}/result → dataverify.result@2(거울). 404 not_found · 409 RUN_NOT_DONE not_done
//                (failed 실행도 409 — dataverify/service/apis/dataverify.py:35-41).
//   reportFile   GET /runs/{id}/files/dataverify-report.xlsx(blob) → 그 이름 그대로.
//   rerun        GET /runs/{id} 의 options 그대로 → startRun 과 같은 POST(새 열쇠·새 launchKey — 처음부터, resumeFromRunId 0).
//   readEdkXlsx  POST /dataverify/edk/read — 본문은 올린 파일의 맨 바이트(Content-Type xlsx, multipart 아님 — 중대성평가 readValueChain 꼴,
//                밴드 DVX1 ②). 답은 거울(ok 두 갈래 — 서버 거절은 값, 꼴 틀림 rejected, 답 없음 unreachable). 파일은 저장되지 않는다.
//   downloadEdkTemplate GET /dataverify/edk/template[?year=](blob) — 이름은 Content-Disposition(없으면 EDK_TEMPLATE_FILE_NAME).
//                year 는 네 자리 글자일 때만 싣는다(아니면 빼고 서버가 해−1).
//   forget       쥔 열쇠를 버린다(요청 0 — 세션이 끝날 때 틀이 부른다).
// id 는 글자다: 나갈 때 `^[1-9][0-9]*$` 만 수로 — 아니면 요청 없이 not_found(구독이면 onMissing).
// 거절의 서버 message 는 화면에 보이지 않는다(이 파일의 거절 글은 개발자용 영문).
import { asFailure } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import { REPORT_FILE_NAME, buildOptions, isTooLarge } from '../model/index.ts';
import type { DataverifyRun, RunStatus, StepStatus } from '../model/index.ts';
import {
  parseEdkRead,
  parseInput,
  parseResult,
  parseRunPage,
  parseSource,
} from './contract/index.ts';
import { newKey, serverId } from './ids.ts';
import type { NewKey } from './ids.ts';
import { DataverifyStoreError, RUN_PAGE_LIMIT } from './store.ts';
import type { DataverifyStore, StartResult, StoreErrorKind } from './store.ts';

/** 폴링 간격 기본(ms). */
export const RUN_POLL_MS = 2000;
/** 값을 받은 뒤 이만큼 잇달아 실패하면 onFailed. */
export const RUN_POLL_FAILURES = 3;
/** 모듈 id. */
export const MODULE = 'dataverify';
/** 엑셀 본문의 꼴(서버 edk 경로의 선언). */
export const XLSX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
/** 양식 이름을 모를 때(Content-Disposition 이 없거나 못 읽음). */
export const EDK_TEMPLATE_FILE_NAME = 'EDK-inventory-template.xlsx';
const YEAR = /^[0-9]{4}$/;

/**
 * Content-Disposition → 파일 이름(영문번역 api/server.ts fileNameFromDisposition 과 같은 셈 — 옮겨 적음, 칸끼리 가져오지 않는다):
 * filename*=UTF-8''… 가 있으면 그것, 없으면 filename="…"·filename=…. 경로 글자는 지운다. 못 읽으면 null.
 */
export function fileNameFromDisposition(header: string | null): string | null {
  if (header === null) return null;
  const clean = (name: string) => {
    const trimmed = name.replace(/[/\\]/g, '').trim();
    return trimmed === '' ? null : trimmed;
  };
  const star = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (star) {
    try {
      return clean(decodeURIComponent(star[1]!.trim()));
    } catch {
      // 퍼센트 꼴이 깨졌으면 아래 filename= 으로
    }
  }
  const quoted = /filename\s*=\s*"((?:[^"\\]|\\.)*)"/.exec(header);
  if (quoted) return clean(quoted[1]!.replace(/\\(.)/g, '$1'));
  const bare = /filename\s*=\s*([^;\s]+)/.exec(header);
  if (bare) return clean(bare[1]!);
  return null;
}

export interface DataverifyServerDeps {
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
  new DataverifyStoreError(kind, message);

/** RunOut → DataverifyRun(꼴이 틀리면 null). */
function runOf(
  body: unknown,
): { run: DataverifyRun; module: string; options: Json } | null {
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
    !isTextOrNull(body.finishedAt) ||
    !isTextOrNull(body.failedStep) ||
    !isTextOrNull(body.errorCode)
  )
    return null;
  const stepList: { step: string; status: StepStatus }[] = [];
  for (const step of steps) {
    if (
      !isObject(step) ||
      !isText(step.step) ||
      !STEP_STATUSES.includes(step.status)
    )
      return null;
    stepList.push({ step: step.step, status: step.status as StepStatus });
  }
  const input = parseInput(options.input);
  const source = parseSource(options.source);
  const run: DataverifyRun = {
    runId: String(id),
    status: status as RunStatus,
    steps: stepList,
    failedStep: body.failedStep,
    errorCode: body.errorCode,
    files: [...files],
    createdAt: body.createdAt,
    finishedAt: body.finishedAt,
    input: input.ok ? input.value : null,
    source: source.ok ? source.value : null,
  };
  return { run, module, options };
}

export function createDataverifyServerStore({
  api,
  pollMs = RUN_POLL_MS,
  newKey: makeKey = newKey,
  newLaunchKey: makeLaunchKey = newKey,
}: DataverifyServerDeps): DataverifyStore {
  const { client } = api;
  /** 아직 만들어지지 않은 본문과 그 열쇠·launchKey(실패 뒤 다시 누름에 둘 다 같은 값). */
  let pending: { body: string; key: string; launchKey: string } | null = null;

  /** 보낸다. 실패는 DataverifyStoreError 로 던진다. lost 는 답을 받지 못했을 때의 갈래(기본 rejected). */
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
    // 데이터 검증이 아닌 실행은 이 화면에 없는 것이다.
    if (read.module !== MODULE)
      throw refuse('not_found', 'run: not dataverify');
    return read;
  }

  /** POST /runs. options 는 그대로 싣는다(재는 것은 model 의 파이썬 셈). */
  async function postRun(options: Json, fresh = false): Promise<StartResult> {
    if (isTooLarge(options)) return { kind: 'too_large' };
    const body = JSON.stringify(options);
    if (fresh || pending === null || pending.body !== body)
      pending = { body, key: makeKey(), launchKey: makeLaunchKey() };
    const { key, launchKey } = pending;
    let answer: unknown;
    try {
      ({ data: answer } = await client.POST('/runs', {
        params: { header: { 'Idempotency-Key': key } },
        body: { module: MODULE, launchKey, options },
      }));
    } catch (error) {
      const failure = asFailure(error);
      if (failure.kind !== 'api') return { kind: 'unreachable' };
      if (failure.code === 'INVALID_OPTIONS')
        return isTooLarge(options) ?
            { kind: 'too_large' }
          : { kind: 'unreadable' };
      return { kind: 'failed' };
    }
    if (!isObject(answer) || !isInt(answer.id)) return { kind: 'failed' };
    if (pending?.key === key) pending = null;
    return { kind: 'started', runId: String(answer.id) };
  }

  const store: DataverifyStore = {
    startRun: (input, source) => postRun(buildOptions(input, source)),

    async listRuns({ status, mine, offset }) {
      const body = await send(
        'run list',
        () =>
          client.GET('/dataverify/runs', {
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
        let run: DataverifyRun;
        try {
          run = (await readRun(id)).run;
        } catch (error) {
          if (stopped) return;
          if (
            error instanceof DataverifyStoreError &&
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
        client.GET('/dataverify/runs/{run_id}/result', {
          params: { path: { run_id: id } },
        }),
      );
      const parsed = parseResult(body);
      if (!parsed.ok)
        throw refuse('rejected', `result shape: ${parsed.issues}`);
      return parsed.value;
    },

    async reportFile(runId) {
      const id = idOrMissing(runId, 'run');
      let answer: { data?: unknown };
      try {
        answer = await client.GET('/runs/{run_id}/files/{name}', {
          params: { path: { run_id: id, name: REPORT_FILE_NAME } },
          parseAs: 'blob',
        });
      } catch (error) {
        throw refuse(kindOf(asFailure(error), 'rejected'), 'report failed');
      }
      if (!isBlob(answer.data)) throw refuse('rejected', 'report: not a file');
      return { blob: answer.data, fileName: REPORT_FILE_NAME };
    },

    async readEdkXlsx(file) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const body = await send(
        'edk read',
        () =>
          client.POST('/dataverify/edk/read', {
            // 본문은 맨 바이트(multipart 아님 — 서버 경로의 선언). openapi 의 본문 타입은 글자라 바꿔 싣는다(중대성평가 readValueChain 꼴).
            body: bytes as unknown as string,
            bodySerializer: (value: unknown) => value as BodyInit,
            headers: { 'Content-Type': XLSX_MEDIA_TYPE },
          }),
        'unreachable',
      );
      const parsed = parseEdkRead(body);
      if (!parsed.ok)
        throw refuse('rejected', `edk read shape: ${parsed.issues}`);
      return parsed.value;
    },

    async downloadEdkTemplate(year) {
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/dataverify/edk/template', {
          params: {
            query:
              year !== undefined && YEAR.test(year) ?
                { year: Number(year) }
              : {},
          },
          parseAs: 'blob',
        });
      } catch (error) {
        throw refuse(
          kindOf(asFailure(error), 'unreachable'),
          'template failed',
        );
      }
      if (!isBlob(answer.data))
        throw refuse('rejected', 'template: not a file');
      return {
        blob: answer.data,
        fileName:
          fileNameFromDisposition(
            answer.response.headers.get('Content-Disposition'),
          ) ?? EDK_TEMPLATE_FILE_NAME,
      };
    },

    async rerun(runId) {
      const id = serverId(runId);
      if (id === null) return { kind: 'failed' };
      let options: Json;
      try {
        ({ options } = await readRun(id));
      } catch {
        // 읽지 못했으면 보내지 않았다 — 만들어지지 않은 것이 확실하다.
        return { kind: 'failed' };
      }
      // 새 동작 — 앞 누름이 쥔 열쇠를 잇지 않는다(둘 다 새로).
      return postRun(options, true);
    },
  };

  return store;
}
