// 그린워싱 AI 설정 판의 실어댑터(밴드 AD2R ①). 서버 경로 다섯(G2c2 — 운영 관리자만, sid:MARC-ENT-335 「/ai-settings/<모듈>」):
//   GET /ai-settings/greenwash(목록 한 쪽 — limit 은 서버 최대 100) · GET /ai-settings/greenwash/{id}(판 하나) · GET /ai-settings/greenwash/default(기본 판)
//   POST /ai-settings/greenwash(새 판 — 서버 판은 바뀌지 않는다, 고친 것은 늘 새 판) · PUT /ai-settings/greenwash/applied(적용 판 바꾸기 — PUT 은 이것 하나).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·창은 모른다(app/ 이 넣는다).
// companyId 는 어느 요청에도 싣지 않는다(sid:MARC-ENT-251 — 회사가 하나면 생략. 둘이면 400 COMPANY_AMBIGUOUS → 실패).
// 읽기: 꼴 틀림·4xx·5xx·연결 끊김은 모두 failed 하나(sid:MARC-ENT-260). 쓰기: 서버가 답한 거절은 rejected(code 는 CRITERIA_*·NAME_CONFLICT 만 싣고 그 밖은 null),
//   연결 끊김·꼴 틀린 답은 failed. 서버 message 는 싣지 않는다(화면 글은 웹 글 표 — config/text.ts).
//   AD2W ③(82 허락): 새 판 저장(create)은 본문 통째(model 의 saveBody 입력)를 받고, 거절 code 를 모델 설정(AI_MODEL_*)·프롬프트 글(AI_PROMPT_*)·
//   꼴 틀림(VALIDATION_ERROR)·대상 단어(TERMS_* — G2d)까지 넓힌다(CREATE_CODES)(서버 core/calc/ai_settings 의 code 이름 그대로 — 대문자). 알아본 code 의 거절에는 서버 message 와 fields(칸 경로 → 문장)를
//   싣는다(AD-02 가 「모델 설정 — 문장」·칸 아래 줄로 그린다). 적용(apply)의 거절은 그대로.
// 나가는 id 는 model 의 idOut 이 고른다 — 양의 정수 글자가 아니면 요청 0 으로 failed.
// AS3b ①: 기본 단어 목록 GET /greenwash/terms/default(defaultTerms — 기본 판·terms null 판의 대상 단어 바탕 몫). 꼴은 문자열 목록만 본다
//   (entities/greenwash 의 같은 부름을 가져오지 않는다 — 슬라이스 사이 import 0).
import { asFailure } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  FailureFields,
} from '../../../shared/api/index.ts';
import {
  CRITERION_IDS,
  SETTING_STATUSES,
  idOut,
  saveBody,
} from '../model/index.ts';
import type {
  Setting,
  SettingCriteria,
  SettingDefault,
  SettingList,
  SettingRow,
  SettingSummary,
} from '../model/index.ts';

/** 한 쪽의 크기(서버 최대 — 1차는 판이 이보다 적다). */
export const GREENWASH_SETTING_PAGE = 100;

export type SettingListOutcome =
  { kind: 'ok'; list: SettingList } | { kind: 'failed' };
export type SettingOutcome =
  { kind: 'ok'; setting: Setting } | { kind: 'failed' };
export type SettingDefaultOutcome =
  { kind: 'ok'; setting: SettingDefault } | { kind: 'failed' };
/**
 * 새 판 저장의 결과. rejected 의 code 는 알아본 거절(CRITERIA_*·NAME_CONFLICT·CREATE_CODES)만, 그 밖의 거절은 null.
 * message·fields 는 알아본 거절일 때만 서버 것 그대로(아니면 null·빈 객체).
 */
export type SettingCreateOutcome =
  | { kind: 'ok'; setting: Setting }
  | {
      kind: 'rejected';
      code: string | null;
      message: string | null;
      fields: FailureFields;
    }
  | { kind: 'failed' };
/** 기본 단어 목록(코드 기본 목록 — 서버 차례 그대로). */
export type DefaultTermsOutcome =
  { kind: 'ok'; terms: string[] } | { kind: 'failed' };
export type SettingApplyOutcome =
  | { kind: 'ok' }
  | { kind: 'rejected'; code: string | null }
  | { kind: 'failed' };

export interface GreenwashSettingServerPort {
  /** 저장 판 목록의 한 쪽(offset 부터 GREENWASH_SETTING_PAGE 개)과 지금 적용 판·기본 판. */
  list(offset: number): Promise<SettingListOutcome>;
  /** 저장 판 하나(기준표째). id 는 웹 열쇠(String(id)). */
  get(id: string): Promise<SettingOutcome>;
  /** 기본 판(코랩 원본 기준표). */
  getDefault(): Promise<SettingDefaultOutcome>;
  /** 새 판 저장: 본문 여섯 칸 — 바탕 판 기준표·판 이름·메모·모델 설정·프롬프트·대상 단어(model 의 saveBody). */
  create(input: Parameters<typeof saveBody>[0]): Promise<SettingCreateOutcome>;
  /** 적용 판 바꾸기. null 은 기본 판. */
  apply(id: string | null): Promise<SettingApplyOutcome>;
  /** 기본 단어 목록(GET /greenwash/terms/default — 판 terms 가 null 일 때의 낱말). */
  defaultTerms(): Promise<DefaultTermsOutcome>;
}

export interface CreateGreenwashSettingServerPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
}

type Shape = Record<string, unknown>;
const isObject = (value: unknown): value is Shape =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const STATUSES: readonly unknown[] = SETTING_STATUSES;
const isString = (value: unknown): value is string => typeof value === 'string';
/** 줄의 구분·판정 결과(계약 enum — 모르는 값이 오면 꼴 틀림으로 그리지 않는다). */
const CATEGORIES: readonly unknown[] = [
  'targetKeyword',
  'coreEvidence',
  'high',
  'mid',
  'exception',
] satisfies SettingRow['category'][];
const VERDICTS: readonly unknown[] = [
  'coreEvidenceApplies',
  'highIfMissing',
  'High',
  'Mid',
  'NonRisk',
] satisfies SettingRow['verdict'][];
const isInt = (value: unknown): value is number => Number.isInteger(value);

function isAuthor(value: unknown) {
  return (
    isObject(value) &&
    isInt(value.id) &&
    (value.name === null || isString(value.name))
  );
}

function isGuideline(value: unknown) {
  return (
    value === null ||
    (isObject(value) &&
      isString(value.text) &&
      (value.status === 'draft' || value.status === 'confirmed'))
  );
}

/** 기준표가 계약 꼴인가: schemaVersion, 15줄이 id·order 차례 그대로, 칸 꼴. */
function isCriteria(value: unknown): value is SettingCriteria {
  if (!isObject(value)) return false;
  if (value.schemaVersion !== 'greenwash.criteria@1') return false;
  if (!isString(value.version) || !Array.isArray(value.rows)) return false;
  const rows: unknown[] = value.rows;
  return (
    rows.length === CRITERION_IDS.length &&
    rows.every(
      (row, index) =>
        isObject(row) &&
        row.id === CRITERION_IDS[index] &&
        row.order === index + 1 &&
        CATEGORIES.includes(row.category) &&
        typeof row.enabled === 'boolean' &&
        isString(row.text) &&
        (row.terms === null ||
          (Array.isArray(row.terms) && row.terms.every(isString))) &&
        VERDICTS.includes(row.verdict) &&
        isGuideline(row.guideline),
    )
  );
}

function isSummary(value: unknown): value is SettingSummary {
  return (
    isObject(value) &&
    isInt(value.id) &&
    isString(value.name) &&
    (value.title === null || isString(value.title)) &&
    STATUSES.includes(value.status) &&
    isString(value.createdAt) &&
    isAuthor(value.createdBy) &&
    isString(value.memo) &&
    isString(value.evalPromptSha256)
  );
}

/** 대상 단어 칸(G2d): null(코드 기본 목록) 또는 {text: 글, enabled: 참거짓} 목록. */
function isTerms(value: unknown) {
  return (
    value === null ||
    (Array.isArray(value) &&
      value.every(
        (term) =>
          isObject(term) &&
          isString(term.text) &&
          typeof term.enabled === 'boolean',
      ))
  );
}

function isSetting(value: unknown): value is Setting {
  return (
    isObject(value) &&
    value.schemaVersion === 'greenwash.ai-setting@3' &&
    isCriteria(value.criteria) &&
    isTerms(value.terms) &&
    isSummary(value)
  );
}

function isDefault(value: unknown): value is SettingDefault {
  return (
    isObject(value) &&
    value.schemaVersion === 'greenwash.ai-setting-default@3' &&
    value.terms === null &&
    isString(value.name) &&
    isString(value.title) &&
    isString(value.evalPromptSha256) &&
    isCriteria(value.criteria)
  );
}

function isApplied(value: unknown) {
  if (!isObject(value)) return false;
  if (value.kind === 'default') return true;
  return value.kind === 'saved' && isInt(value.id);
}

function isList(value: unknown): value is SettingList {
  return (
    isObject(value) &&
    value.schemaVersion === 'greenwash.ai-settings@2' &&
    isInt(value.companyId) &&
    isApplied(value.applied) &&
    isObject(value.default) &&
    isString(value.default.name) &&
    isString(value.default.title) &&
    isString(value.default.evalPromptSha256) &&
    Array.isArray(value.items) &&
    value.items.every(isSummary) &&
    isInt(value.total) &&
    value.total >= 0
  );
}

/** 쓰기 거절의 code: 받기 거절(CRITERIA_*)과 이름 겹침(NAME_CONFLICT — 화면은 일반 글)만 싣는다. */
const refusedCode = (failure: ApiFailure) =>
  (
    failure.kind === 'api' &&
    /^(CRITERIA_[A-Z_]+|NAME_CONFLICT)$/.test(failure.code)
  ) ?
    failure.code
  : null;

/**
 * 새 판 저장에서 더 알아보는 code(AD2W ③ — 서버 이름 그대로, 나갈 때 대문자): 꼴 틀림, 모델 설정 받기 거절 아홉·프롬프트 글 받기 거절 여덟
 * (apps/api-py core/calc/ai_settings 의 ai_model_*·ai_prompt_*), 대상 단어 받기 거절 넷(G2d — greenwash/flows/terms_e0 의 TERMS_*).
 */
const CREATE_CODES: readonly string[] = [
  'VALIDATION_ERROR',
  'AI_MODEL_STEPS_FIXED',
  'AI_MODEL_ROUTE_UNKNOWN',
  'AI_MODEL_ROUTE_UNAVAILABLE',
  'AI_MODEL_TOOL_LOOP_UNSUPPORTED',
  'AI_MODEL_TEMPERATURE_RANGE',
  'AI_MODEL_TEMPERATURE_UNSUPPORTED',
  'AI_MODEL_WEB_SEARCH_UNSUPPORTED',
  'AI_MODEL_WEB_SEARCH_FIXED',
  'AI_MODEL_MAX_OUTPUT_RANGE',
  'AI_PROMPT_STEPS_FIXED',
  'AI_PROMPT_KEYS_FIXED',
  'AI_PROMPT_TEXT_EMPTY',
  'AI_PROMPT_TEXT_DUPLICATE',
  'AI_PROMPT_TEXT_LENGTH',
  'AI_PROMPT_CHARS',
  'AI_PROMPT_MEMO_LENGTH',
  'AI_PROMPT_TOTAL_SIZE',
  'TERMS_TEXT',
  'TERMS_DUPLICATE',
  'TERMS_COUNT',
  'TERMS_NONE_ENABLED',
];

export function createGreenwashSettingServerPort({
  api,
}: CreateGreenwashSettingServerPortOptions): GreenwashSettingServerPort {
  const { client } = api;

  /** 한 번 보낸다. 실패는 갈래로(던지지 않는다). */
  async function attempt<T>(
    send: () => Promise<{ data?: T }>,
  ): Promise<{ data: unknown } | { failure: ApiFailure }> {
    try {
      const { data } = await send();
      if (data === undefined) return { failure: { kind: 'network' } };
      return { data };
    } catch (error) {
      return { failure: asFailure(error) };
    }
  }

  /** 쓰기 실패의 갈래: 서버가 답한 거절은 rejected, 닿지 못함은 failed. */
  const writeFailure = (failure: ApiFailure) =>
    failure.kind === 'network' ?
      ({ kind: 'failed' } as const)
    : ({ kind: 'rejected', code: refusedCode(failure) } as const);

  /** 새 판 저장 실패의 갈래: 알아본 거절은 서버 message·fields 까지, 닿지 못함은 failed. */
  const createFailure = (failure: ApiFailure): SettingCreateOutcome => {
    if (failure.kind === 'network') return { kind: 'failed' };
    const code =
      failure.kind === 'api' && CREATE_CODES.includes(failure.code) ?
        failure.code
      : refusedCode(failure);
    return code !== null && failure.kind === 'api' ?
        {
          kind: 'rejected',
          code,
          message: failure.message,
          fields: failure.fields,
        }
      : { kind: 'rejected', code: null, message: null, fields: {} };
  };

  return {
    async list(offset) {
      const result = await attempt(() =>
        client.GET('/ai-settings/greenwash', {
          params: { query: { limit: GREENWASH_SETTING_PAGE, offset } },
        }),
      );
      if ('failure' in result || !isList(result.data))
        return { kind: 'failed' };
      return { kind: 'ok', list: result.data };
    },

    async get(id) {
      const settingId = idOut(id);
      if (settingId === null) return { kind: 'failed' };
      const result = await attempt(() =>
        client.GET('/ai-settings/greenwash/{setting_id}', {
          params: { path: { setting_id: settingId } },
        }),
      );
      if (
        'failure' in result ||
        !isSetting(result.data) ||
        result.data.id !== settingId
      )
        return { kind: 'failed' };
      return { kind: 'ok', setting: result.data };
    },

    async getDefault() {
      const result = await attempt(() =>
        client.GET('/ai-settings/greenwash/default'),
      );
      if ('failure' in result || !isDefault(result.data))
        return { kind: 'failed' };
      return { kind: 'ok', setting: result.data };
    },

    async create(input) {
      const result = await attempt(() =>
        client.POST('/ai-settings/greenwash', { body: saveBody(input) }),
      );
      if ('failure' in result) return createFailure(result.failure);
      if (!isSetting(result.data)) return { kind: 'failed' };
      return { kind: 'ok', setting: result.data };
    },

    async apply(id) {
      const settingId = id === null ? null : idOut(id);
      if (id !== null && settingId === null) return { kind: 'failed' };
      const result = await attempt(() =>
        client.PUT('/ai-settings/greenwash/applied', {
          body: { id: settingId },
        }),
      );
      if ('failure' in result) return writeFailure(result.failure);
      // 답은 바꾼 뒤 목록 첫 쪽(limit 20 고정)이라 화면 값으로 쓰지 않는다 — 꼴만 본다.
      if (!isList(result.data)) return { kind: 'failed' };
      return { kind: 'ok' };
    },

    async defaultTerms() {
      const result = await attempt(() =>
        client.GET('/greenwash/terms/default'),
      );
      if (
        'failure' in result ||
        !isObject(result.data) ||
        !Array.isArray(result.data.terms) ||
        !result.data.terms.every(isString)
      )
        return { kind: 'failed' };
      return { kind: 'ok', terms: [...result.data.terms] };
    },
  };
}
