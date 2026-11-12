// 실행 기록의 실어댑터(밴드 AD4R ①). 서버 경로 둘 — 줄(GET /run-logs, 쪽)·이번 달 지표(GET /run-logs/metrics).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·창은 모른다(app/ 이 넣는다).
// 거르기는 서버가 한다: 화면이 만든 쿼리(model 의 runQuery — 값 있는 칸만)에 쪽(limit·offset)만 더해 보낸다.
// companyId 는 보내지 않는다(MARC-ENT-251 — 회사가 하나면 생략. 회사가 둘이면 400 COMPANY_AMBIGUOUS → failed).
// 한 번 보내고, 꼴 틀림·400·403·404·422·5xx·연결 끊김은 모두 failed 하나(MARC-ENT-260 3 「둘로만」). 서버 message 는 화면에 보이지 않는다.
// 엑셀(밴드 AD4X ②, GET /run-logs/export): 목록에 넘긴 그 쿼리를 쪽 없이 그대로 보내 Blob 과 서버가 정한 파일 이름을 돌려준다.
//   409 RUN_LOG_EXPORT_TOO_LARGE(서버 상한 — 웹은 숫자를 모른다)만 tooLarge, 그 밖 실패·Blob 아닌 답은 failed.
//   파일 이름은 Content-Disposition(filename* 해독), 없으면 model 의 대체 이름.
// 실행 상세(밴드 AD4W, GET /run-logs/{run_id}): 질의 없이 한 번. 404 RUN_NOT_FOUND 만 notFound, 그 밖 실패·꼴 틀림은 failed.
//   문서 두 칸은 null 도 받는다(model 의 RunLogDetail — ND1). 목록 가드(isRow)의 문서 두 칸은 그대로 non-null(ND1 따라잡기 몫).
// 결과 파일(밴드 RF1W, 서버 RF1 GET /run-logs/{run_id}/files/{name}): 질의 없이 한 번, Blob 과 Content-Disposition 이름(없으면 그 줄 이름)을 돌려준다.
//   이름은 경로 칸이라 openapi-fetch 가 encodeURIComponent 로 싣는다(여기서 또 하면 두 번 — 한글·공백·#·/ 는 시험이 본다).
//   404 RUN_NOT_FOUND·RUN_FILE_NOT_FOUND(이름으로만 가른다 — detail 과 같은 꼴, AD4P)만 notFound, 그 밖(503 저장소 셋·403·500·연결 끊김)·Blob 아닌 답은 failed.
// 같이 시작·이어서(LK1 다섯 칸 — launchKey·launchFirstRunId·launchIndex·launchSize·resumedFromRunId, 묶음 없으면 null): 줄·상세 가드가 같이 본다(AD4P).
import { asFailure } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import {
  RUN_EXPORT_FALLBACK_NAME,
  RUN_REVIEWS,
  RUN_STATUSES,
  RUN_STEP_STATUSES,
  fileNameFromDisposition,
} from '../model/index.ts';
import type {
  RunLogDetail,
  RunLogRow,
  RunMetricsRow,
  RunQuery,
} from '../model/index.ts';

/** 한 쪽의 크기(「더 보기」 한 번). */
export const RUN_PAGE_SIZE = 50;

export type RunPageOutcome =
  | { kind: 'ok'; count: number; isNext: boolean; rows: RunLogRow[] }
  | { kind: 'failed' };

export type RunMetricsOutcome =
  { kind: 'ok'; metrics: RunMetricsRow } | { kind: 'failed' };

export type RunExportOutcome =
  | { kind: 'ok'; blob: Blob; fileName: string }
  | { kind: 'tooLarge' }
  | { kind: 'failed' };

export type RunFileOutcome =
  | { kind: 'ok'; blob: Blob; fileName: string }
  | { kind: 'notFound' }
  | { kind: 'failed' };

export type RunDetailOutcome =
  | { kind: 'ok'; detail: RunLogDetail }
  | { kind: 'notFound' }
  | { kind: 'failed' };

export interface RunLogServerPort {
  /** 거른 줄의 한 쪽(offset 부터 RUN_PAGE_SIZE 줄). count 는 조건에 맞는 전부의 수. */
  list(query: RunQuery, offset: number): Promise<RunPageOutcome>;
  /** 이번 달 지표 다섯(서버 시계의 KST 그달 — 거르기와 따로). */
  metrics(): Promise<RunMetricsOutcome>;
  /** 거른 줄 전부의 엑셀(쪽 없음 — 쿼리는 list 에 넘긴 그대로). */
  exportFile(query: RunQuery): Promise<RunExportOutcome>;
  /** 실행 하나의 상세(단계·결과 파일). 질의 없음. */
  detail(runId: number): Promise<RunDetailOutcome>;
  /** 실행 하나의 결과 파일(상세 files[] 의 step 이 null 인 이름 — 흐름의 출력 파일). 질의 없음. 404 둘은 notFound. */
  file(runId: number, name: string): Promise<RunFileOutcome>;
}

export interface CreateRunLogServerPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
}

const STATUSES: readonly string[] = RUN_STATUSES;
const REVIEWS: readonly string[] = RUN_REVIEWS;
const STEP_STATUSES: readonly string[] = RUN_STEP_STATUSES;
const nullable = (value: unknown, type: 'string' | 'number') =>
  value === null || typeof value === type;

/** AI 설정 칸이 계약 꼴인가(null 또는 {id: 수|null, name: 글}). */
function isAiSetting(value: unknown): boolean {
  if (value === null) return true;
  if (typeof value !== 'object') return false;
  const setting = value as Record<string, unknown>;
  return nullable(setting.id, 'number') && typeof setting.name === 'string';
}

/** 결과 파일이 없다는 404 의 코드(실행 없음·그 이름 없음). */
const FILE_NOT_FOUND_CODES: readonly string[] = [
  'RUN_NOT_FOUND',
  'RUN_FILE_NOT_FOUND',
];

/** 같이 시작·이어서 다섯 칸(LK1)이 계약 꼴인가(모두 있어야 하고 값은 null 도). */
function hasLaunchFields(row: Record<string, unknown>): boolean {
  return (
    nullable(row.launchKey, 'string') &&
    nullable(row.launchFirstRunId, 'number') &&
    nullable(row.launchIndex, 'number') &&
    nullable(row.launchSize, 'number') &&
    nullable(row.resumedFromRunId, 'number')
  );
}

/** 줄과 상세가 같이 갖는 칸(문서 두 칸 빼고)이 계약 꼴인가. */
function hasRunFields(row: Record<string, unknown>): boolean {
  return (
    typeof row.id === 'number' &&
    typeof row.module === 'string' &&
    typeof row.flowId === 'string' &&
    typeof row.status === 'string' &&
    STATUSES.includes(row.status) &&
    typeof row.createdAt === 'string' &&
    nullable(row.startedAt, 'string') &&
    nullable(row.finishedAt, 'string') &&
    typeof row.createdByUserId === 'number' &&
    nullable(row.createdByName, 'string') &&
    nullable(row.createdByUsername, 'string') &&
    nullable(row.durationSec, 'number') &&
    typeof row.tokens === 'number' &&
    typeof row.costUsd === 'number' &&
    typeof row.isTest === 'boolean' &&
    (row.review === null ||
      (typeof row.review === 'string' && REVIEWS.includes(row.review))) &&
    isAiSetting(row.aiSetting) &&
    hasLaunchFields(row)
  );
}

/** 줄 하나가 계약 꼴인가(꼴 틀림은 실패로 — 틀린 정보를 그리지 않는다. 문서 두 칸은 null 도 — ND1·ND1W). */
function isRow(value: unknown): value is RunLogRow {
  if (typeof value !== 'object' || value === null) return false;
  const row = value as Record<string, unknown>;
  return (
    nullable(row.documentId, 'number') &&
    nullable(row.documentName, 'string') &&
    hasRunFields(row)
  );
}

/** 단계 하나가 계약 꼴인가. */
function isStep(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) return false;
  const step = value as Record<string, unknown>;
  return (
    typeof step.name === 'string' &&
    typeof step.position === 'number' &&
    typeof step.status === 'string' &&
    STEP_STATUSES.includes(step.status) &&
    nullable(step.startedAt, 'string') &&
    nullable(step.finishedAt, 'string') &&
    nullable(step.durationSec, 'number') &&
    nullable(step.tokens, 'number') &&
    nullable(step.costUsd, 'number')
  );
}

/** 결과 파일 하나가 계약 꼴인가. */
function isFile(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) return false;
  const file = value as Record<string, unknown>;
  return (
    typeof file.name === 'string' &&
    nullable(file.step, 'string') &&
    typeof file.mediaType === 'string' &&
    typeof file.sizeBytes === 'number'
  );
}

/** 상세가 계약 꼴인가(문서 두 칸은 null 도 — ND1). */
function isDetail(value: unknown): value is RunLogDetail {
  if (typeof value !== 'object' || value === null) return false;
  const detail = value as Record<string, unknown>;
  return (
    nullable(detail.documentId, 'number') &&
    nullable(detail.documentName, 'string') &&
    hasRunFields(detail) &&
    nullable(detail.failedStep, 'string') &&
    nullable(detail.errorCode, 'string') &&
    typeof detail.stepUsageRecorded === 'boolean' &&
    Array.isArray(detail.steps) &&
    detail.steps.every(isStep) &&
    Array.isArray(detail.files) &&
    detail.files.every(isFile)
  );
}

/** Blob 꼴인가(전역 Blob 이 실행 환경마다 다를 수 있어 모양으로 본다 — 크기·종류·바이트 읽기). */
const isBlob = (value: unknown): value is Blob =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as Blob).size === 'number' &&
  typeof (value as Blob).type === 'string' &&
  typeof (value as Blob).arrayBuffer === 'function';

/** 지표가 계약 꼴인가. */
function isMetrics(value: unknown): value is RunMetricsRow {
  if (typeof value !== 'object' || value === null) return false;
  const metrics = value as Record<string, unknown>;
  return (
    typeof metrics.month === 'string' &&
    typeof metrics.runs === 'number' &&
    nullable(metrics.averageDurationSec, 'number') &&
    typeof metrics.tokens === 'number' &&
    typeof metrics.costUsd === 'number' &&
    nullable(metrics.failureRate, 'number') &&
    typeof metrics.aiProviderMock === 'boolean'
  );
}

export function createRunLogServerPort({
  api,
}: CreateRunLogServerPortOptions): RunLogServerPort {
  const { client } = api;

  /** 한 번 보낸다. 실패는 갈래로(던지지 않는다). */
  async function attempt<T>(
    send: () => Promise<{ data?: T }>,
  ): Promise<{ data: T } | { failure: ApiFailure }> {
    try {
      const { data } = await send();
      if (data === undefined) return { failure: { kind: 'network' } };
      return { data };
    } catch (error) {
      return { failure: asFailure(error) };
    }
  }

  return {
    async list(query, offset) {
      const result = await attempt(() =>
        client.GET('/run-logs', {
          params: { query: { ...query, limit: RUN_PAGE_SIZE, offset } },
        }),
      );
      if ('failure' in result) return { kind: 'failed' };
      const body: unknown = result.data;
      if (typeof body !== 'object' || body === null) return { kind: 'failed' };
      const { count, isNext, results } = body as Record<string, unknown>;
      if (
        typeof count !== 'number' ||
        typeof isNext !== 'boolean' ||
        !Array.isArray(results) ||
        !results.every(isRow)
      )
        return { kind: 'failed' };
      return { kind: 'ok', count, isNext, rows: results };
    },

    async metrics() {
      const result = await attempt(() => client.GET('/run-logs/metrics'));
      if ('failure' in result) return { kind: 'failed' };
      const body: unknown = result.data;
      if (!isMetrics(body)) return { kind: 'failed' };
      return { kind: 'ok', metrics: body };
    },

    async exportFile(query) {
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/run-logs/export', {
          params: { query },
          parseAs: 'blob',
        });
      } catch (error) {
        const failure = asFailure(error);
        return (
            failure.kind === 'api' &&
              failure.code === 'RUN_LOG_EXPORT_TOO_LARGE'
          ) ?
            { kind: 'tooLarge' }
          : { kind: 'failed' };
      }
      const blob = answer.data;
      if (!isBlob(blob)) return { kind: 'failed' };
      return {
        kind: 'ok',
        blob,
        fileName:
          fileNameFromDisposition(
            answer.response.headers.get('Content-Disposition'),
          ) ?? RUN_EXPORT_FALLBACK_NAME,
      };
    },

    async detail(runId) {
      let answer: { data?: unknown };
      try {
        answer = await client.GET('/run-logs/{run_id}', {
          params: { path: { run_id: runId } },
        });
      } catch (error) {
        const failure = asFailure(error);
        return failure.kind === 'api' && failure.code === 'RUN_NOT_FOUND' ?
            { kind: 'notFound' }
          : { kind: 'failed' };
      }
      const body = answer.data;
      if (!isDetail(body)) return { kind: 'failed' };
      return { kind: 'ok', detail: body };
    },

    async file(runId, name) {
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/run-logs/{run_id}/files/{name}', {
          params: { path: { run_id: runId, name } },
          parseAs: 'blob',
        });
      } catch (error) {
        const failure = asFailure(error);
        return (
            failure.kind === 'api' &&
              FILE_NOT_FOUND_CODES.includes(failure.code)
          ) ?
            { kind: 'notFound' }
          : { kind: 'failed' };
      }
      const blob = answer.data;
      if (!isBlob(blob)) return { kind: 'failed' };
      return {
        kind: 'ok',
        blob,
        fileName:
          fileNameFromDisposition(
            answer.response.headers.get('Content-Disposition'),
          ) ?? name,
      };
    },
  };
}
