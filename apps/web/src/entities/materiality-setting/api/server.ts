// 중대성평가 IRO AI 설정 판의 실어댑터(밴드 IRA2 — 서버 IR4, sid:MARC-ENT-335 「/ai-settings/<모듈>」). 데이터 검증 실어댑터(entities/dataverify-setting/api/server.ts)와 같은 꼴, 경로 셋(운영 관리자만):
//   GET /ai-settings/materiality(목록 한 쪽 — limit 은 서버 최대 100) · POST /ai-settings/materiality(새 판 — 201, 고친 것은 늘 새 판)
//   · PUT /ai-settings/materiality/applied(적용 판 바꾸기). 판 하나·기본 판 GET 은 부르지 않는다 — 판 몫(그린워싱 기준표 같은 것)이 없어
//   바탕 판을 읽을 일이 없다. prompt-model 은 entities/ai-setting 의 공통 읽기(모듈 줄이 잇는다).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. companyId 는 어느 요청에도 싣지 않는다(sid:MARC-ENT-251).
// 갈래는 그린워싱 실어댑터(entities/greenwash-setting/api/server.ts)와 같다: 읽기는 꼴 틀림·4xx·5xx·끊김 모두 failed. 쓰기는 서버가 답한 거절 rejected
//   (새 판 저장은 model 의 CREATE_CODES(자리 지킴 AI_PROMPT_PLACEHOLDER_MISSING 포함)만 code·서버 message·fields 를 싣고 그 밖은 null), 끊김·꼴 틀린 답 failed. 적용 거절은 code null.
// 저장 본문은 이름으로 골라 담는다({title, memo, modelSettings, prompts} — 모르는 칸이 실리지 않는다).
import { asFailure } from '../../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  FailureFields,
} from '../../../shared/api/index.ts';
import { CREATE_CODES, SETTING_STATUSES, idOut } from '../model/index.ts';
import type {
  Setting,
  SettingCreate,
  SettingList,
  SettingSummary,
} from '../model/index.ts';

/** 한 쪽의 크기(서버 최대 — 1차는 판이 이보다 적다). */
export const MATERIALITY_SETTING_PAGE = 100;

export type SettingListOutcome =
  { kind: 'ok'; list: SettingList } | { kind: 'failed' };
/** 새 판 저장의 결과. rejected 의 code 는 알아본 거절(CREATE_CODES)만 — 그때만 서버 message·fields(아니면 null·빈 객체). */
export type SettingCreateOutcome =
  | { kind: 'ok'; setting: Setting }
  | {
      kind: 'rejected';
      code: string | null;
      message: string | null;
      fields: FailureFields;
    }
  | { kind: 'failed' };
export type SettingApplyOutcome =
  { kind: 'ok' } | { kind: 'rejected' } | { kind: 'failed' };

/** 새 판 저장 입력(껍데기의 공통 본문 — modelSettings·prompts 는 늘 싣는다). */
export type SettingCreateInput = Required<SettingCreate>;

export interface MaterialitySettingServerPort {
  /** 저장 판 목록의 한 쪽(offset 부터 MATERIALITY_SETTING_PAGE 개)과 지금 적용 판·기본 판. */
  list(offset: number): Promise<SettingListOutcome>;
  /** 새 판 저장: 본문 넷(판 이름·메모·모델 설정·프롬프트). */
  create(input: SettingCreateInput): Promise<SettingCreateOutcome>;
  /** 적용 판 바꾸기. null 은 기본 판. */
  apply(id: string | null): Promise<SettingApplyOutcome>;
}

export interface CreateMaterialitySettingServerPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
}

type Shape = Record<string, unknown>;
const isObject = (value: unknown): value is Shape =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const STATUSES: readonly unknown[] = SETTING_STATUSES;
const isString = (value: unknown): value is string => typeof value === 'string';
const isInt = (value: unknown): value is number => Number.isInteger(value);

function isAuthor(value: unknown) {
  return (
    isObject(value) &&
    isInt(value.id) &&
    (value.name === null || isString(value.name))
  );
}

function isSummary(value: unknown): value is SettingSummary {
  return (
    isObject(value) &&
    isInt(value.id) &&
    isString(value.name) &&
    isString(value.title) &&
    STATUSES.includes(value.status) &&
    isString(value.createdAt) &&
    isAuthor(value.createdBy) &&
    isString(value.memo)
  );
}

function isSetting(value: unknown): value is Setting {
  return (
    isObject(value) &&
    value.schemaVersion === 'materiality.ai-setting@1' &&
    isSummary(value)
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
    value.schemaVersion === 'materiality.ai-settings@1' &&
    isInt(value.companyId) &&
    isApplied(value.applied) &&
    isObject(value.default) &&
    isString(value.default.name) &&
    isString(value.default.title) &&
    Array.isArray(value.items) &&
    value.items.every(isSummary) &&
    isInt(value.total) &&
    value.total >= 0
  );
}

export function createMaterialitySettingServerPort({
  api,
}: CreateMaterialitySettingServerPortOptions): MaterialitySettingServerPort {
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

  /** 새 판 저장 실패의 갈래: 알아본 거절은 서버 message·fields 까지, 닿지 못함은 failed. */
  const createFailure = (failure: ApiFailure): SettingCreateOutcome => {
    if (failure.kind === 'network') return { kind: 'failed' };
    return failure.kind === 'api' && CREATE_CODES.includes(failure.code) ?
        {
          kind: 'rejected',
          code: failure.code,
          message: failure.message,
          fields: failure.fields,
        }
      : { kind: 'rejected', code: null, message: null, fields: {} };
  };

  return {
    async list(offset) {
      const result = await attempt(() =>
        client.GET('/ai-settings/materiality', {
          params: { query: { limit: MATERIALITY_SETTING_PAGE, offset } },
        }),
      );
      if ('failure' in result || !isList(result.data))
        return { kind: 'failed' };
      return { kind: 'ok', list: result.data };
    },

    async create({ title, memo, modelSettings, prompts }) {
      const result = await attempt(() =>
        client.POST('/ai-settings/materiality', {
          body: { title, memo, modelSettings, prompts },
        }),
      );
      if ('failure' in result) return createFailure(result.failure);
      if (!isSetting(result.data)) return { kind: 'failed' };
      return { kind: 'ok', setting: result.data };
    },

    async apply(id) {
      const settingId = id === null ? null : idOut(id);
      if (id !== null && settingId === null) return { kind: 'failed' };
      const result = await attempt(() =>
        client.PUT('/ai-settings/materiality/applied', {
          body: { id: settingId },
        }),
      );
      if ('failure' in result)
        return result.failure.kind === 'network' ?
            { kind: 'failed' }
          : { kind: 'rejected' };
      // 답은 바꾼 뒤 목록 첫 쪽이라 화면 값으로 쓰지 않는다 — 꼴만 본다.
      if (!isList(result.data)) return { kind: 'failed' };
      return { kind: 'ok' };
    },
  };
}
