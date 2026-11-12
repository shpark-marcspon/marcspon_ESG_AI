// 온실가스 Scope 3 실어댑터(밴드 S3W1 ①). 영문번역 api/server.ts(올리기 셋·POST /runs·GET /runs/{id})와 데이터 검증 api/server.ts
// (다시 실행·Content-Disposition 이름)의 꼴을 옮겨 적었다(가져오지 않는다 — 칸끼리, 공통화는 후속 sid:MARC-ISSUE-335).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)와 서명 주소 올리기(sendUpload — 경로 컴포넌트가 준다)만 쓴다.
// 경로:
//   upload(file, year)  POST /documents {fileName, sizeBytes, reportYear} → sendUpload(upload.url, upload.method, file)
//                       → POST /documents/{id}/confirm. 연도는 문서와 실행 options 둘 다에 싣는다(실행기가 끼움에 넘기는 문서에 연도 칸이 없다).
//   start(doc, year)    POST /runs {module:'inventory.scope3', flowId:'scope3.colab@157', documentId, launchKey, options:{reportYear}}
//                       + 머리 Idempotency-Key(소문자 UUID). flowId 는 늘 싣는다(서버 기본은 아직 llm-first — sid:MARC-ENT-442).
//                       답 없음(network)이면 같은 열쇠·같은 본문으로 한 번 더(서버가 만들었으면 앞 실행 201). 고른 카테고리는 싣지 않는다.
//   template()          GET /inventory/scope3/template(blob) — 이름은 Content-Disposition, 못 읽으면 TEMPLATE_FILE_NAME.
//   exportFile(year)    GET /inventory/scope3/years/{year}/export(blob — 밴드 S3D1, S3-15) — 이름은 Content-Disposition, 못 읽으면
//                       EXPORT_FILE_NAME(year). 404(그 해 결과 없음)는 notFound(데이터 다운로드 창이 따로 말한다).
//   original(runId)     GET /inventory/scope3/runs/{id}/original(blob — 밴드 S3Q1, S3-09 [원본 다운로드]) — 그 실행에 올린 엑셀 그대로.
//                       이름은 Content-Disposition(올린 이름), 못 읽으면 ORIGINAL_FILE_NAME. 404(원본 없음)는 notFound. 실행 상태는 보지 않는다.
//   result(id)          GET /inventory/scope3/runs/{id}/result → Scope3Result(손 거름 resultOf — 꼴이 틀리면 failed, 404·409 도 failed).
//                       시트의 error·거절의 detail 은 싣지 않는다(파일 내용이 섞일 수 있어 화면 0). 줄은 상세 표 칸까지(S3W2b ① — 모르는 kind 는 그 줄만 basic).
//                       줄의 input(S3W2c ① — 닫힌 키 열여섯, S3R3 useMonths 만 빠져도 됨)은 inputOf: 없음·null·꼴 틀림이면 그 줄의 input 만 null(줄 나머지는 그대로).
//   run(id)             GET /runs/{id} → Scope3Run(module 이 inventory.scope3 가 아니면 failed).
//   latest(year)        GET /inventory/scope3/years/{year} 의 latest({runId, status}) → 있으면 GET /runs/{runId} 하나(밴드 GX5 — 목록 20건
//                       밖으로 밀려도 찾는다). 서버가 흐름 scope3.colab@157 · purpose service · 그 해 실행만 고른다(utils/scope3_state.py
//                       counts_for_year — 옛 llm-first 는 안 섞인다, S3W2a ⑤). latest 가 null 이면 none. none 과 failed 는 다른 갈래다.
//                       읽은 실행의 해·흐름이 다르면 failed(계약 어김).
//   retry(id)           GET /runs/{id}(failed 가 아니면 보내지 않고 rejected) → start 와 같은 POST — 그 실행의 documentId·options 그대로, flowId 는 늘 상수,
//                       새 열쇠·새 launchKey(처음부터). resumeFromRunId 는 쓰지 않는다(시스템 복구 장치 — 감독 86 10-30, 그린워싱·번역·데이터 검증 꼴).
//   year(y)             GET /inventory/scope3/years/{y} → Scope3Year(밴드 S3W3a ① — 그 해의 지금 결과. 꼴이 틀리면 failed).
//   edits(id)           GET …/runs/{id}/edits → RunEdits(옛 실행도 읽는다).
//   history(id, 쪽)     GET …/runs/{id}/history?rowId=&page=&pageSize= → EditHistoryPage(준 칸만 싣는다).
//   lock(y, c, runId)   POST …/years/{y}/categories/{c}/lock?runId= → YearCategory. runId 는 사용자가 본 실행(stale_run 이 지키는 값).
//   unlock(y, c)        DELETE 같은 경로 → YearCategory(고객사 403 forbidden).
//   exclude·restore     POST …/runs/{id}/categories/{c}/exclusions·restorations {rowIds, reason} → RowEditResult.
//   factor(id, c, 입력) POST …/runs/{id}/categories/{c}/factors → RowEditResult. 몸은 다섯 키를 늘 싣는다(rank·custom 은 필수+nullable,
//                       키를 빼면 422 — S3K2b-2 리뷰 L3). 값·제목·출처·사유를 걷거나 고치지 않는다(서버가 검사한다).
//   ★ 이 경로들의 id 는 답에서 글자, 나갈 때 serverId 로 수(/runs 답의 id 는 수 — runOf 와 꼴이 다르다).
// 갈래: 읽기 ok | refused(회사 거절 셋) | failed. 쓰기 ok | rejected{code, fields} | refused | failed — code 는 SCOPE3_WRITE_CODES 만, 그 밖 거절은 null.
//   fields 는 422 의 칸 이름만이다(서버 문장은 버린다).
// 서버 code 는 대문자로 맞춰 본다(문서 413 은 소문자 upload_too_large 로 온다). 서버 message 는 싣지 않는다(화면 0). id 는 글자다.
import { asFailure, companyRefusalOf } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  CompanyRefusal,
} from '../../../shared/api/index.ts';
import {
  ACTIVITY_KINDS,
  C12_BRANCHES,
  C12_TREATMENTS,
  CATEGORIES,
  EDIT_KINDS,
  ENERGY_KINDS,
  FACTOR_CHOICES,
  INPUT_KEYS,
  OPTIONAL_INPUT_KEYS,
  REJECT_REASONS,
  RUN_STEP_NAMES,
  RUN_STEP_STATUSES,
  SCOPE3_FLOW_ID,
  SCOPE3_MODULE,
} from '../model/index.ts';
import type {
  ActivityKind,
  AmountCells,
  C12Branch,
  C12Treatment,
  C12TreatmentPart,
  C12Treatments,
  CategoryId,
  EditHistoryLine,
  EditHistoryPage,
  EditKind,
  EditPerson,
  EnergyKind,
  FactorCells,
  FactorChoice,
  RejectReason,
  ResultRow,
  ResultSheet,
  RowDetail,
  RowEdit,
  RowEditResult,
  RowFactor,
  RowFactorInput,
  RowInput,
  RowOrigin,
  RowRecommendation,
  RunEdits,
  RunStatus,
  RunStep,
  Scope3Result,
  Scope3Run,
  Scope3Year,
  YearCategory,
  YearCurrent,
} from '../model/index.ts';

/** 폴링 간격 기본(ms) — 데이터 검증 RUN_POLL_MS 와 같다. */
export const RUN_POLL_MS = 2000;
/** 양식 이름을 모를 때(Content-Disposition 이 없거나 못 읽음). */
export const TEMPLATE_FILE_NAME = 'scope3-template.xlsx';
/** 데이터 엑셀 이름을 모를 때(서버 export_file_name 의 회사 토막 없는 꼴). */
export const EXPORT_FILE_NAME = (year: number) => `${year}_Scope3_데이터.xlsx`;
/** 원본 이름을 모를 때(Content-Disposition 이 없거나 못 읽음 — 서버는 올린 이름을 준다). */
export const ORIGINAL_FILE_NAME = 'Scope3_원본.xlsx';

/** 쓰기 거절 중 화면이 가르는 code. */
export const SCOPE3_WRITE_CODES = [
  'FLOW_NOT_RUNNABLE',
  'INVALID_OPTIONS',
  'DOCUMENT_NOT_UPLOADED',
  'FORBIDDEN',
  'UPLOAD_TOO_LARGE',
  'LOCKED',
  'STALE_RUN',
  'NOT_COMPUTED',
  'FACTOR_NOT_EDITABLE',
  'VALIDATION_ERROR',
] as const;
export type Scope3WriteCode = (typeof SCOPE3_WRITE_CODES)[number];

export type { CompanyRefusal };

export type ReadOutcome<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

/** 그 해 마지막 실행 — 없음(none)과 읽기 실패(failed)를 한 값으로 접지 않는다. */
export type LatestOutcome =
  | { kind: 'ok'; value: Scope3Run }
  | { kind: 'none' }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export type WriteOutcome<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'rejected'; code: Scope3WriteCode | null; fields: string[] }
  | { kind: 'refused'; company: CompanyRefusal }
  | { kind: 'failed' };

export interface Scope3Template {
  blob: Blob;
  fileName: string;
}

/** 내려받은 데이터 엑셀(S3-15). */
export type Scope3File = Scope3Template;

/** 데이터 엑셀 읽기 — 그 해 결과 없음(404)은 notFound. */
export type ExportOutcome = ReadOutcome<Scope3File> | { kind: 'notFound' };

export interface Scope3Port {
  upload(
    file: File,
    year: number,
  ): Promise<WriteOutcome<{ documentId: string }>>;
  start(
    documentId: string,
    year: number,
  ): Promise<WriteOutcome<{ runId: string }>>;
  template(): Promise<ReadOutcome<Scope3Template>>;
  /** 그 해의 Scope 3 데이터 엑셀(지금 결과 — 서버가 짓는다). */
  exportFile(year: number): Promise<ExportOutcome>;
  /** 그 실행에 올린 엑셀 원본(S3Q1 — 바이트 그대로, 404 는 notFound). */
  original(runId: string): Promise<ExportOutcome>;
  result(id: string): Promise<ReadOutcome<Scope3Result>>;
  run(id: string): Promise<ReadOutcome<Scope3Run>>;
  latest(year: number): Promise<LatestOutcome>;
  retry(id: string): Promise<WriteOutcome<{ runId: string }>>;
  year(year: number): Promise<ReadOutcome<Scope3Year>>;
  edits(id: string): Promise<ReadOutcome<RunEdits>>;
  history(
    id: string,
    page?: EditHistoryQuery,
  ): Promise<ReadOutcome<EditHistoryPage>>;
  lock(
    year: number,
    category: CategoryId,
    runId: string,
  ): Promise<WriteOutcome<YearCategory>>;
  unlock(
    year: number,
    category: CategoryId,
  ): Promise<WriteOutcome<YearCategory>>;
  exclude(
    id: string,
    category: CategoryId,
    rowIds: readonly string[],
    reason: string,
  ): Promise<WriteOutcome<RowEditResult>>;
  restore(
    id: string,
    category: CategoryId,
    rowIds: readonly string[],
    reason: string,
  ): Promise<WriteOutcome<RowEditResult>>;
  factor(
    id: string,
    category: CategoryId,
    input: RowFactorInput,
  ): Promise<WriteOutcome<RowEditResult>>;
}

/** 히스토리 쪽 고르기(준 칸만 쿼리에 싣는다). */
export interface EditHistoryQuery {
  rowId?: string;
  page?: number;
  pageSize?: number;
}

/** 서명 주소로 파일 본문을 올린다(실패는 던진다). */
export type SendUpload = (
  url: string,
  method: string,
  file: File,
) => Promise<void>;
/** 열쇠를 짓는 함수(시험이 고정한다). */
export type NewKey = () => string;

export interface CreateScope3PortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
  sendUpload: SendUpload;
  /** 새 Idempotency-Key. 기본 newKey. */
  newKey?: NewKey;
  /** 새 launchKey. 기본 newKey. */
  newLaunchKey?: NewKey;
}

/** 소문자 UUID(서버 runs/calc/idempotency.py KEY_PATTERN — 데이터 검증 api/ids.ts 를 옮겨 적음). */
export const newKey: NewKey = () => {
  if (typeof crypto.randomUUID === 'function')
    return crypto.randomUUID().toLowerCase();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'));
  return [
    hex.slice(0, 4),
    hex.slice(4, 6),
    hex.slice(6, 8),
    hex.slice(8, 10),
    hex.slice(10, 16),
  ]
    .map((part) => part.join(''))
    .join('-');
};

/** 나가는 id: 양의 정수 글자만 수로. 아니면 null(요청하지 않는다). */
function serverId(id: string): number | null {
  if (!/^[1-9][0-9]*$/.test(id)) return null;
  const value = +id;
  return Number.isSafeInteger(value) ? value : null;
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

/**
 * Content-Disposition → 파일 이름(데이터 검증 api/server.ts fileNameFromDisposition 과 같은 셈 — 옮겨 적음):
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

/** steps 칸 → 아는 단계만. 꼴이 틀린 낱개·모르는 단계는 버린다(진행 표시가 없어도 폴링은 산다). done·total 은 진행률이 아니라 싣지 않는다. */
function stepsOf(value: unknown): RunStep[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((one: unknown) => {
    if (!isObject(one)) return [];
    const step = RUN_STEP_NAMES.find((name) => name === one.step);
    const status = RUN_STEP_STATUSES.find((name) => name === one.status);
    return step && status ? [{ step, status }] : [];
  });
}

/** RunOut → Scope3Run(꼴이 틀리거나 다른 모듈이면 null). */
export function runOf(body: unknown): Scope3Run | null {
  if (!isObject(body)) return null;
  const { id, module, options, status, documentId, flowId } = body;
  if (
    !isInt(id) ||
    module !== SCOPE3_MODULE ||
    !isObject(options) ||
    !RUN_STATUSES.includes(status) ||
    !(documentId === null || isInt(documentId)) ||
    !isText(flowId) ||
    !isText(body.createdAt) ||
    !isTextOrNull(body.finishedAt) ||
    !isTextOrNull(body.errorCode)
  )
    return null;
  return {
    id: String(id),
    status: status as RunStatus,
    documentId: documentId === null ? null : String(documentId),
    flowId,
    reportYear: isInt(options.reportYear) ? options.reportYear : null,
    options: { ...options },
    createdAt: body.createdAt,
    finishedAt: body.finishedAt,
    errorCode: body.errorCode,
    steps: stepsOf(body.steps),
  };
}

const RESULT_SCHEMA = 'scope3.colab.result@1';

const ORIGINS: readonly unknown[] = ['rule', 'ai', 'estimate'];

/** 글자거나 null 이면 그 값, 아니면 undefined(꼴 틀림). */
const textOrNull = (value: unknown): string | null | undefined =>
  isTextOrNull(value) ? value : undefined;

/** 상세 칸들(모두 글자·null)을 한 번에 — 하나라도 꼴이 틀리면 null. */
function cellsOf<K extends string>(
  body: unknown,
  keys: readonly K[],
): Record<K, string | null> | null {
  if (!isObject(body)) return null;
  const out = {} as Record<K, string | null>;
  for (const key of keys) {
    const value = textOrNull(body[key]);
    if (value === undefined) return null;
    out[key] = value;
  }
  return out;
}

/**
 * 계수 칸(구매는 source 코드가 있고 unit 이 늘 글자, 활동·에너지는 서버 출처 글 sourceText(S3Q1 — 없거나 글이 아니면 sheet 글자)를 source 칸에 —
 * 출처 글만이라 꼴이 틀려도 줄을 떨구지 않고 그 칸만 물러선다).
 */
function factorOf(body: unknown, withSource: boolean): FactorCells | null {
  const cells = cellsOf(body, ['title', 'value', 'unit'] as const);
  if (cells === null || !isObject(body)) return null;
  if (!withSource)
    return {
      ...cells,
      source:
        isText(body.sourceText) && body.sourceText.trim() !== '' ?
          body.sourceText
        : isText(body.sheet) ? body.sheet
        : null,
    };
  return isText(body.source) ? { ...cells, source: body.source } : null;
}

const RECOMMENDATION_KEYS: readonly string[] = [
  'title',
  'value',
  'expectedCo2e',
];

/**
 * 구매 줄의 추천(openapi ColabRecommendationJson — 닫힘). 서버가 items[rank-1] 로 고르니 차례·값 null 을 그대로 둔다(거르면 뒤 순위가 밀린다).
 * 하나라도 꼴이 틀리면 추천만 빈 배열 — 줄은 그대로 둔다(inputOf 결).
 */
function recommendationsOf(body: unknown): RowRecommendation[] {
  if (!Array.isArray(body)) return [];
  const out: RowRecommendation[] = [];
  for (const one of body) {
    if (
      !isObject(one) ||
      !isText(one.title) ||
      !Object.keys(one).every((key) => RECOMMENDATION_KEYS.includes(key))
    )
      return [];
    const cells = cellsOf(one, ['value', 'expectedCo2e'] as const);
    if (cells === null) return [];
    out.push({ title: one.title, ...cells });
  }
  return out;
}

const amountOf = (body: unknown): AmountCells | null =>
  cellsOf(body, ['value', 'unit', 'baseValue', 'baseUnit'] as const);

/** null 이면 null, 꼴이 맞으면 그 값, 틀리면 undefined. */
function nullable<T>(
  body: unknown,
  read: (body: unknown) => T | null,
): T | null | undefined {
  if (body === null) return null;
  const value = read(body);
  return value === null ? undefined : value;
}

/** group 단계의 origin(밴드 S3W4 Q3). 모르는 step·origin 낱개는 버린다. 단계가 둘이면 ai 가 이긴다(별은 ai 단계가 있을 때 선다). */
function groupOriginOf(steps: readonly unknown[]): RowOrigin | null {
  const origins = steps.flatMap((one) =>
    isObject(one) && one.step === 'group' && ORIGINS.includes(one.origin) ?
      [one.origin as RowOrigin]
    : [],
  );
  return origins.includes('ai') ? 'ai' : (origins[0] ?? null);
}

/** 줄의 상세 칸(kind 별). 모르는 kind·꼴 틀린 칸이면 null — 그 줄은 basic(행·배출량)으로 남는다(발주서 §1-5). */
function detailOf(body: Json): RowDetail | null {
  const { kind, originSteps } = body;
  if (!Array.isArray(originSteps)) return null;
  const hasBiogenic = isObject(body.biogenic);
  const fcf =
    isObject(body.biogenic) ? textOrNull(body.biogenic.fcf)
    : body.biogenic === null || body.biogenic === undefined ? null
    : undefined;
  const biogenicNote =
    isObject(body.biogenic) ? textOrNull(body.biogenic.note) : null;
  if (kind === 'purchase') {
    const group = body.group;
    const factor = factorOf(body.factor, true);
    const spendKrw = textOrNull(body.spendKrw);
    if (!isObject(group) || !isText(group.name) || factor === null) return null;
    if (spendKrw === undefined) return null;
    return {
      shape: 'purchase',
      kind,
      groupName: group.name,
      groupOrigin: groupOriginOf(originSteps),
      spendKrw,
      factor,
      recommendations: recommendationsOf(body.recommendations),
    };
  }
  const activity = amountOf(body.activity);
  if (activity === null || fcf === undefined || biogenicNote === undefined)
    return null;
  if ((ACTIVITY_KINDS as readonly unknown[]).includes(kind)) {
    const factor = factorOf(body.factor, false);
    const treatment = textOrNull(body.treatment);
    const mode = nullable(body.mode, (one) =>
      isObject(one) && isText(one.value) ? one.value : null,
    );
    const distance = nullable(body.distance, (one) =>
      cellsOf(one, ['km', 'roundTrip', 'people', 'trips', 'workdays'] as const),
    );
    if (
      factor === null ||
      treatment === undefined ||
      mode === undefined ||
      distance === undefined
    )
      return null;
    return {
      shape: 'activity',
      kind: kind as ActivityKind,
      activity,
      factor,
      treatment,
      mode,
      distance,
      fcf,
      hasBiogenic,
      biogenicNote,
    };
  }
  if ((ENERGY_KINDS as readonly unknown[]).includes(kind)) {
    const factor = nullable(body.factor, (one) => factorOf(one, false));
    const treatments =
      kind === 'product_eol' ?
        treatmentsOf(body.treatments, body.factor)
      : null;
    const allocation = nullable(body.allocation, (one) =>
      cellsOf(one, ['buildingTotal'] as const),
    );
    const product = nullable(body.product, (one) =>
      cellsOf(one, ['years'] as const),
    );
    const investment = nullable(body.investment, (one) =>
      cellsOf(one, ['share', 'scope1', 'scope2'] as const),
    );
    if (
      factor === undefined ||
      allocation === undefined ||
      product === undefined ||
      investment === undefined
    )
      return null;
    return {
      shape: 'energy',
      kind: kind as EnergyKind,
      activity,
      factor,
      buildingTotal: allocation?.buildingTotal ?? null,
      years: product?.years ?? null,
      investment,
      fcf,
      hasBiogenic,
      biogenicNote,
      ...(treatments === null ? {} : { treatments }),
    };
  }
  return null;
}

/**
 * C12 처리방법별 값(S3Q1 — openapi ColabC12TreatmentsJson). 칸이 없거나(옛 결과) 꼴이 하나라도 틀리면 null — 그 칸만 없음(줄은 그대로, 창은 지금 표).
 * 처리방법은 셋(enum)·겹침 없음. code 는 줄 factor.code(글자가 아니면 null).
 */
function treatmentsOf(body: unknown, factor: unknown): C12Treatments | null {
  if (!isObject(body) || !Array.isArray(body.parts)) return null;
  const branch = body.branch;
  const shareTotal = textOrNull(body.shareTotal);
  if (
    !(C12_BRANCHES as readonly unknown[]).includes(branch) ||
    shareTotal === undefined
  )
    return null;
  const parts: C12TreatmentPart[] = [];
  for (const one of body.parts as unknown[]) {
    if (!isObject(one) || typeof one.used !== 'boolean') return null;
    const share = textOrNull(one.share);
    const value = textOrNull(one.factor);
    if (
      !(C12_TREATMENTS as readonly unknown[]).includes(one.treatment) ||
      share === undefined ||
      value === undefined ||
      parts.some((part) => part.treatment === one.treatment)
    )
      return null;
    parts.push({
      treatment: one.treatment as C12Treatment,
      share,
      factor: value,
      used: one.used,
    });
  }
  const code = isObject(factor) && isText(factor.code) ? factor.code : null;
  return { branch: branch as C12Branch, shareTotal, parts, code };
}

/**
 * 줄의 입력 칸(openapi ColabRowInputJson — required 열다섯이 다 있고 그 밖 키 0, 값은 글이거나 null). useMonths(S3R3)는 없어도 되고 없으면
 * null(S3R3 앞 키 열다섯 저장 결과 — 감독 처분 Q3, 화면 「-」). 칸이 없거나(옛 결과 — 다시 셈하지 않는다,
 * sid:MARC-ENT-539) null 이거나 꼴이 틀리면 null — 그 줄의 다른 칸·detail 은 그대로 둔다(줄을 basic 으로 떨구지 않는다, 발주서 S3W2c Q2).
 * C5 의 name 은 엔진이 회사별 매핑으로 채운 뒤의 값일 수 있다 — 입력 글자 그대로라고 단언하지 않는다(Q6).
 */
function inputOf(body: unknown): RowInput | null {
  if (!isObject(body)) return null;
  if (
    !Object.keys(body).every((key) =>
      (INPUT_KEYS as readonly string[]).includes(key),
    )
  )
    return null;
  const filled: Record<string, unknown> = { ...body };
  for (const key of OPTIONAL_INPUT_KEYS)
    if (!Object.hasOwn(filled, key)) filled[key] = null;
  return cellsOf(filled, INPUT_KEYS);
}

/**
 * 줄 하나(꼴이 틀리면 null — 결과 전체가 failed). 카드가 쓰는 co2e·생물기원은 S3W2a 그대로 엄격하다.
 * 상세 칸은 detailOf — 모르는 kind·꼴 틀린 칸은 그 줄만 basic(화면 전체를 죽이지 않는다). purchase 줄에는 biogenic 칸이 없다.
 */
function rowOf(body: unknown): ResultRow | null {
  if (!isObject(body) || !isTextOrNull(body.co2e)) return null;
  const biogenic = body.biogenic;
  let biogenicCo2e: string | null = null;
  if (biogenic !== undefined && biogenic !== null) {
    if (!isObject(biogenic) || !isTextOrNull(biogenic.biogenicCo2e))
      return null;
    biogenicCo2e = biogenic.biogenicCo2e;
  }
  return {
    rowId: isText(body.rowId) ? body.rowId : null,
    co2e: body.co2e,
    biogenic: biogenicCo2e,
    origin: ORIGINS.includes(body.origin) ? (body.origin as RowOrigin) : null,
    formula: isText(body.formula) ? body.formula : null,
    detail: detailOf(body) ?? { shape: 'basic' },
    input: inputOf(body.input),
  };
}

/** 시트 하나(꼴이 틀리면 null). not_target·not_yet_supported·모르는 status 는 other — 합·상세에 넣지 않는다. */
function sheetOf(body: unknown): ResultSheet | null {
  if (!isObject(body) || !isText(body.status)) return null;
  const { category, rows, sheet, status } = body;
  if (status === 'failed' || status === 'empty')
    return isText(category) && isText(sheet) ?
        { status, sheet, category }
      : null;
  if (status !== 'processed') return { status: 'other' };
  if (!isText(category) || !isText(sheet) || !Array.isArray(rows)) return null;
  const parsed: ResultRow[] = [];
  for (const row of rows) {
    const one = rowOf(row);
    if (one === null) return null;
    parsed.push(one);
  }
  return { status: 'processed', sheet, category, rows: parsed };
}

/** llmCalls(프롬프트 → 갈래 → 수). 꼴이 틀리면 null. */
function llmCallsOf(
  body: unknown,
): Record<string, Record<string, number>> | null {
  if (!isObject(body)) return null;
  const out: Record<string, Record<string, number>> = {};
  for (const [prompt, counts] of Object.entries(body)) {
    if (!isObject(counts)) return null;
    const line: Record<string, number> = {};
    for (const [via, count] of Object.entries(counts)) {
      if (!isInt(count)) return null;
      line[via] = count;
    }
    out[prompt] = line;
  }
  return out;
}

/** 결과 본문 → Scope3Result(꼴이 틀리거나 모르는 판이면 null). */
export function resultOf(body: unknown): Scope3Result | null {
  if (!isObject(body) || body.schemaVersion !== RESULT_SCHEMA) return null;
  if (body.status === 'rejected') {
    const rejected = body.rejected;
    if (!isObject(rejected)) return null;
    const reason = rejected.reason;
    return (REJECT_REASONS as readonly unknown[]).includes(reason) ?
        { status: 'rejected', reason: reason as RejectReason }
      : null;
  }
  if (body.status !== 'done' || !Array.isArray(body.sheets)) return null;
  const sheets: ResultSheet[] = [];
  for (const sheet of body.sheets) {
    const one = sheetOf(sheet);
    if (one === null) return null;
    sheets.push(one);
  }
  const llmCalls = llmCallsOf(body.llmCalls);
  return llmCalls === null ? null : { status: 'done', sheets, llmCalls };
}

/** 서버 열넷(C10 뺌 — 1차 계산 0). */
const isCategory = (value: unknown): value is CategoryId =>
  CATEGORIES.some((one) => one.id === value && !one.disabled);

/** {id, name} 글자 둘(꼴이 틀리면 null). */
function personOf(body: unknown): EditPerson | null {
  if (!isObject(body) || !isText(body.id) || !isText(body.name)) return null;
  return { id: body.id, name: body.name };
}

/** 지금 계수 상태(Scope3RowEditFactorOut). 꼴이 틀리면 null. */
function rowFactorOf(body: unknown): RowFactor | null {
  if (!isObject(body)) return null;
  const cells = cellsOf(body, [
    'title',
    'value',
    'source',
    'unit',
    'co2e',
    'biogenicCo2e',
  ] as const);
  const ai = cellsOf(body.ai, ['title', 'value', 'source', 'co2e'] as const);
  const { choice, rank } = body;
  if (
    cells === null ||
    ai === null ||
    !(FACTOR_CHOICES as readonly unknown[]).includes(choice) ||
    !(rank === null || isInt(rank))
  )
    return null;
  return { ...cells, choice: choice as FactorChoice, rank, ai };
}

/** 줄의 지금 상태(Scope3RowEditOut). factor·editedBy 는 칸이 있어야 한다(없으면 꼴 틀림 — null 은 값이다). */
function rowEditOf(body: unknown): RowEdit | null {
  if (!isObject(body)) return null;
  const { rowId, category, excluded, editedAt } = body;
  const factor = nullable(body.factor, rowFactorOf);
  const editedBy = nullable(body.editedBy, personOf);
  if (
    !isText(rowId) ||
    !isCategory(category) ||
    typeof excluded !== 'boolean' ||
    !isText(editedAt) ||
    factor === undefined ||
    editedBy === undefined
  )
    return null;
  return { rowId, category, excluded, factor, editedAt, editedBy };
}

/** 목록의 값을 다 읽는다 — 하나라도 꼴이 틀리면 null. */
function listOf<T>(
  body: unknown,
  read: (one: unknown) => T | null,
): T[] | null {
  if (!Array.isArray(body)) return null;
  const out: T[] = [];
  for (const item of body) {
    const one = read(item);
    if (one === null) return null;
    out.push(one);
  }
  return out;
}

/** Scope3RowEditsOut → RunEdits(꼴이 틀리면 null). */
export function runEditsOf(body: unknown): RunEdits | null {
  if (!isObject(body) || !isText(body.runId)) return null;
  const rows = listOf(body.rows, rowEditOf);
  return rows === null ? null : { runId: body.runId, rows };
}

function historyLineOf(body: unknown): EditHistoryLine | null {
  if (!isObject(body)) return null;
  const { id, rowId, category, kind, reason, at, batchId } = body;
  const by = nullable(body.by, personOf);
  const factor = nullable(body.factor, rowFactorOf);
  if (
    !isText(id) ||
    !isText(rowId) ||
    !isCategory(category) ||
    !(EDIT_KINDS as readonly unknown[]).includes(kind) ||
    !isText(reason) ||
    !isText(at) ||
    !isTextOrNull(batchId) ||
    by === undefined ||
    factor === undefined
  )
    return null;
  return {
    id,
    rowId,
    category,
    kind: kind as EditKind,
    reason,
    at,
    by,
    batchId,
    factor,
  };
}

/** Scope3RowEditHistoryPageOut → EditHistoryPage(꼴이 틀리면 null). */
export function historyPageOf(body: unknown): EditHistoryPage | null {
  if (!isObject(body)) return null;
  const { count, totalPages, page, pageSize, hasNext, hasPrevious } = body;
  const lines = listOf(body.results, historyLineOf);
  if (
    !isInt(count) ||
    !isInt(totalPages) ||
    !isInt(page) ||
    !isInt(pageSize) ||
    typeof hasNext !== 'boolean' ||
    typeof hasPrevious !== 'boolean' ||
    lines === null
  )
    return null;
  return { count, totalPages, page, pageSize, hasNext, hasPrevious, lines };
}

function yearCurrentOf(body: unknown): YearCurrent | null {
  if (!isObject(body)) return null;
  const { runId, total, sheets, failedSheets } = body;
  if (
    !isText(runId) ||
    !isTextOrNull(total) ||
    !isInt(sheets) ||
    !isInt(failedSheets)
  )
    return null;
  return { runId, total, sheets, failedSheets };
}

/** Scope3YearCategoryOut → YearCategory(꼴이 틀리면 null). 쓰기 답의 category 도 이것이다. */
function yearCategoryOf(body: unknown): YearCategory | null {
  if (!isObject(body)) return null;
  const { category, locked, lockedAt, editedRows } = body;
  const current = nullable(body.current, yearCurrentOf);
  const lockedBy = nullable(body.lockedBy, personOf);
  if (
    !isCategory(category) ||
    typeof locked !== 'boolean' ||
    !isTextOrNull(lockedAt) ||
    !isInt(editedRows) ||
    current === undefined ||
    lockedBy === undefined
  )
    return null;
  return { category, current, locked, lockedAt, lockedBy, editedRows };
}

/** Scope3YearLatestOut(id 는 글자 — /runs 와 다르다). */
function yearLatestOf(body: unknown): Scope3Year['latest'] {
  if (
    !isObject(body) ||
    !isText(body.runId) ||
    !RUN_STATUSES.includes(body.status)
  )
    return null;
  return { runId: body.runId, status: body.status as RunStatus };
}

/** Scope3YearOut → Scope3Year(꼴이 틀리면 null). */
export function yearOf(body: unknown): Scope3Year | null {
  if (!isObject(body)) return null;
  const { year, baseRunId, editedRowsUnlocked } = body;
  const latest = nullable(body.latest, yearLatestOf);
  const categories = listOf(body.categories, yearCategoryOf);
  if (
    !isInt(year) ||
    !isTextOrNull(baseRunId) ||
    !isInt(editedRowsUnlocked) ||
    latest === undefined ||
    categories === null
  )
    return null;
  return { year, baseRunId, latest, categories, editedRowsUnlocked };
}

/** Scope3RowEditResultOut → RowEditResult(꼴이 틀리면 null). */
export function rowEditResultOf(body: unknown): RowEditResult | null {
  if (!isObject(body)) return null;
  const category = yearCategoryOf(body.category);
  const rows = listOf(body.rows, rowEditOf);
  return category === null || rows === null ? null : { category, rows };
}

const isBlob = (value: unknown): value is Blob =>
  typeof value === 'object' &&
  value !== null &&
  typeof (value as Blob).arrayBuffer === 'function';

type Sent = { data: unknown } | { failure: ApiFailure };

/** 한 번 보낸다. 실패는 갈래로(던지지 않는다). */
async function attempt<T>(send: () => Promise<{ data?: T }>): Promise<Sent> {
  try {
    const { data } = await send();
    if (data === undefined) return { failure: { kind: 'network' } };
    return { data };
  } catch (error) {
    return { failure: asFailure(error) };
  }
}

function readFailure(failure: ApiFailure): ReadOutcome<never> {
  const company = companyRefusalOf(failure);
  return company ? { kind: 'refused', company } : { kind: 'failed' };
}

function writeFailure(failure: ApiFailure): WriteOutcome<never> {
  if (failure.kind !== 'api') return { kind: 'failed' };
  const company = companyRefusalOf(failure);
  if (company) return { kind: 'refused', company };
  const code = failure.code.toUpperCase();
  const known = (SCOPE3_WRITE_CODES as readonly string[]).includes(code);
  return {
    kind: 'rejected',
    code: known ? (code as Scope3WriteCode) : null,
    fields: known ? Object.keys(failure.fields ?? {}) : [],
  };
}

export function createScope3Port({
  api,
  sendUpload,
  newKey: makeKey = newKey,
  newLaunchKey: makeLaunchKey = newKey,
}: CreateScope3PortOptions): Scope3Port {
  const { client } = api;

  async function readRun(id: number): Promise<ReadOutcome<Scope3Run>> {
    const sent = await attempt(() =>
      client.GET('/runs/{run_id}', { params: { path: { run_id: id } } }),
    );
    if ('failure' in sent) return readFailure(sent.failure);
    const run = runOf(sent.data);
    return run ? { kind: 'ok', value: run } : { kind: 'failed' };
  }

  /** GET /inventory/scope3/years/{year} → Scope3Year(latest 와 year 가 같이 쓴다). */
  function readYear(year: number): Promise<ReadOutcome<Scope3Year>> {
    return read(
      () =>
        client.GET('/inventory/scope3/years/{year}', {
          params: { path: { year } },
        }),
      yearOf,
    );
  }

  /** POST /runs 하나(열쇠는 한 번 짓고, 답 없음이면 같은 열쇠·같은 본문으로 한 번 더). */
  async function postRun(
    documentId: number,
    flowId: string,
    options: Json,
  ): Promise<WriteOutcome<{ runId: string }>> {
    const key = makeKey();
    const launchKey = makeLaunchKey();
    const send = () =>
      attempt(() =>
        client.POST('/runs', {
          params: { header: { 'Idempotency-Key': key } },
          body: {
            module: SCOPE3_MODULE,
            flowId,
            documentId,
            launchKey,
            options,
          },
        }),
      );
    let sent = await send();
    if ('failure' in sent && sent.failure.kind === 'network')
      sent = await send();
    if ('failure' in sent) return writeFailure(sent.failure);
    const answer = sent.data;
    if (!isObject(answer) || !isInt(answer.id)) return { kind: 'failed' };
    return { kind: 'ok', value: { runId: String(answer.id) } };
  }

  /** 읽기 하나: 보내고 파서에 태운다(꼴이 틀리면 failed). */
  async function read<T>(
    send: () => Promise<{ data?: unknown }>,
    parse: (body: unknown) => T | null,
  ): Promise<ReadOutcome<T>> {
    const sent = await attempt(send);
    if ('failure' in sent) return readFailure(sent.failure);
    const value = parse(sent.data);
    return value === null ? { kind: 'failed' } : { kind: 'ok', value };
  }

  /** 쓰기 하나: 보내고 파서에 태운다(꼴이 틀리면 failed). */
  async function write<T>(
    send: () => Promise<{ data?: unknown }>,
    parse: (body: unknown) => T | null,
  ): Promise<WriteOutcome<T>> {
    const sent = await attempt(send);
    if ('failure' in sent) return writeFailure(sent.failure);
    const value = parse(sent.data);
    return value === null ? { kind: 'failed' } : { kind: 'ok', value };
  }

  /** 제외·복구(같은 몸, 경로만 다르다). */
  function rowsEdit(
    path:
      | '/inventory/scope3/runs/{run_id}/categories/{category}/exclusions'
      | '/inventory/scope3/runs/{run_id}/categories/{category}/restorations',
    id: string,
    category: CategoryId,
    rowIds: readonly string[],
    reason: string,
  ): Promise<WriteOutcome<RowEditResult>> {
    const value = serverId(id);
    if (value === null) return Promise.resolve({ kind: 'failed' });
    return write(
      () =>
        client.POST(path, {
          params: { path: { run_id: value, category } },
          body: { rowIds: [...rowIds], reason },
        }),
      rowEditResultOf,
    );
  }

  return {
    async upload(file, year) {
      const created = await attempt(() =>
        client.POST('/documents', {
          body: { fileName: file.name, sizeBytes: file.size, reportYear: year },
        }),
      );
      if ('failure' in created) return writeFailure(created.failure);
      const made = isObject(created.data) ? created.data.document : null;
      const upload = isObject(created.data) ? created.data.upload : null;
      if (
        !isObject(made) ||
        !isInt(made.id) ||
        !isObject(upload) ||
        !isText(upload.url) ||
        !isText(upload.method)
      )
        return { kind: 'failed' };
      try {
        await sendUpload(upload.url, upload.method, file);
      } catch {
        return { kind: 'failed' };
      }
      const id = made.id;
      const confirmed = await attempt(() =>
        client.POST('/documents/{document_id}/confirm', {
          params: { path: { document_id: id } },
        }),
      );
      if ('failure' in confirmed) return writeFailure(confirmed.failure);
      return { kind: 'ok', value: { documentId: String(id) } };
    },

    async start(documentId, year) {
      const id = serverId(documentId);
      if (id === null) return { kind: 'failed' };
      return postRun(id, SCOPE3_FLOW_ID, { reportYear: year });
    },

    async template() {
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/inventory/scope3/template', {
          parseAs: 'blob',
        });
      } catch (error) {
        return readFailure(asFailure(error));
      }
      if (!isBlob(answer.data)) return { kind: 'failed' };
      return {
        kind: 'ok',
        value: {
          blob: answer.data,
          fileName:
            fileNameFromDisposition(
              answer.response.headers.get('Content-Disposition'),
            ) ?? TEMPLATE_FILE_NAME,
        },
      };
    },

    async exportFile(year) {
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/inventory/scope3/years/{year}/export', {
          params: { path: { year } },
          parseAs: 'blob',
        });
      } catch (error) {
        const failure = asFailure(error);
        if (failure.kind === 'api' && failure.code === 'NOT_FOUND')
          return { kind: 'notFound' };
        return readFailure(failure);
      }
      if (!isBlob(answer.data)) return { kind: 'failed' };
      return {
        kind: 'ok',
        value: {
          blob: answer.data,
          fileName:
            fileNameFromDisposition(
              answer.response.headers.get('Content-Disposition'),
            ) ?? EXPORT_FILE_NAME(year),
        },
      };
    },

    async original(runId) {
      const value = serverId(runId);
      if (value === null) return { kind: 'failed' };
      let answer: { data?: unknown; response: Response };
      try {
        answer = await client.GET('/inventory/scope3/runs/{run_id}/original', {
          params: { path: { run_id: value } },
          parseAs: 'blob',
        });
      } catch (error) {
        const failure = asFailure(error);
        if (failure.kind === 'api' && failure.code === 'NOT_FOUND')
          return { kind: 'notFound' };
        return readFailure(failure);
      }
      if (!isBlob(answer.data)) return { kind: 'failed' };
      return {
        kind: 'ok',
        value: {
          blob: answer.data,
          fileName:
            fileNameFromDisposition(
              answer.response.headers.get('Content-Disposition'),
            ) ?? ORIGINAL_FILE_NAME,
        },
      };
    },

    async result(id) {
      const value = serverId(id);
      if (value === null) return { kind: 'failed' };
      const sent = await attempt(() =>
        client.GET('/inventory/scope3/runs/{run_id}/result', {
          params: { path: { run_id: value } },
        }),
      );
      if ('failure' in sent) return readFailure(sent.failure);
      const result = resultOf(sent.data);
      return result ? { kind: 'ok', value: result } : { kind: 'failed' };
    },

    async run(id) {
      const value = serverId(id);
      if (value === null) return { kind: 'failed' };
      return readRun(value);
    },

    async latest(year) {
      const state = await readYear(year);
      if (state.kind !== 'ok') return state;
      const last = state.value.latest;
      if (last === null) return { kind: 'none' };
      const id = serverId(last.runId);
      if (id === null) return { kind: 'failed' };
      const read = await readRun(id);
      if (read.kind !== 'ok') return read;
      return (
          read.value.reportYear === year && read.value.flowId === SCOPE3_FLOW_ID
        ) ?
          read
        : { kind: 'failed' };
    },

    async retry(id) {
      const value = serverId(id);
      if (value === null) return { kind: 'failed' };
      const read = await readRun(value);
      if (read.kind === 'refused') return read;
      if (read.kind !== 'ok') return { kind: 'failed' };
      const run = read.value;
      const documentId =
        run.documentId === null ? null : serverId(run.documentId);
      // 실패한 실행만 다시 계산한다(그 밖은 보내지 않는다).
      if (run.status !== 'failed' || documentId === null)
        return { kind: 'rejected', code: null, fields: [] };
      // 흐름은 늘 1차 흐름(앞 실행이 다른 흐름이었어도 — sid:MARC-ENT-442).
      return postRun(documentId, SCOPE3_FLOW_ID, run.options);
    },

    year(year) {
      return readYear(year);
    },

    async edits(id) {
      const value = serverId(id);
      if (value === null) return { kind: 'failed' };
      return read(
        () =>
          client.GET('/inventory/scope3/runs/{run_id}/edits', {
            params: { path: { run_id: value } },
          }),
        runEditsOf,
      );
    },

    async history(id, page = {}) {
      const value = serverId(id);
      if (value === null) return { kind: 'failed' };
      return read(
        () =>
          client.GET('/inventory/scope3/runs/{run_id}/history', {
            params: { path: { run_id: value }, query: { ...page } },
          }),
        historyPageOf,
      );
    },

    async lock(year, category, runId) {
      const value = serverId(runId);
      if (value === null) return { kind: 'failed' };
      return write(
        () =>
          client.POST(
            '/inventory/scope3/years/{year}/categories/{category}/lock',
            {
              params: { path: { year, category }, query: { runId: value } },
            },
          ),
        yearCategoryOf,
      );
    },

    unlock(year, category) {
      return write(
        () =>
          client.DELETE(
            '/inventory/scope3/years/{year}/categories/{category}/lock',
            { params: { path: { year, category } } },
          ),
        yearCategoryOf,
      );
    },

    exclude(id, category, rowIds, reason) {
      return rowsEdit(
        '/inventory/scope3/runs/{run_id}/categories/{category}/exclusions',
        id,
        category,
        rowIds,
        reason,
      );
    },

    restore(id, category, rowIds, reason) {
      return rowsEdit(
        '/inventory/scope3/runs/{run_id}/categories/{category}/restorations',
        id,
        category,
        rowIds,
        reason,
      );
    },

    async factor(id, category, input) {
      const value = serverId(id);
      if (value === null) return { kind: 'failed' };
      return write(
        () =>
          client.POST(
            '/inventory/scope3/runs/{run_id}/categories/{category}/factors',
            {
              params: { path: { run_id: value, category } },
              // 다섯 키를 늘 싣는다 — rank·custom 은 필수+nullable(키를 빼면 422).
              body: {
                rowId: input.rowId,
                choice: input.choice,
                rank: input.choice === 'recommended' ? input.rank : null,
                custom: input.choice === 'custom' ? input.custom : null,
                reason: input.reason,
              },
            },
          ),
        rowEditResultOf,
      );
    },
  };
}
