// AI 설정 prompt-model 읽기의 실어댑터(밴드 AD2W ② — 감독 처분 「대안」: 모듈 공통 꼴이라 플랫폼 땅에 둔다, app 층은 통신하지 않는다).
//   GET /ai-settings/<모듈>/{setting_id}/prompt-model · GET /ai-settings/<모듈>/default/prompt-model(ai.prompt-model@3 — 운영 관리자만).
//   답은 generated 의 AiPromptModel3 그대로(모델 칸 목록 + 프롬프트 묶음 목록, 둘 다 하나 이상). @2 답은 꼴 틀림 — failed.
//   계약에 경로가 있는 모듈은 PromptModelModule 의 낱말(경로 칸 <모듈> 과 같다 — 그린워싱·영문번역 TRA1). 경로는 그 낱말 한 꼴로 짓는다
//   (모듈마다 문자열 사본 0 — 다른 모듈은 서버 경로가 생길 때 낱말 하나를 더한다).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh)만 쓴다. companyId 는 싣지 않는다(sid:MARC-ENT-251).
// 갈래: 200 + 꼴 맞음 ok · 409 AI_SETTING_UNUSABLE unusable(서버 문장 — 화면에 그대로) · 404 missing · 그 밖(끊김·꼴 틀림·5xx·다른 4xx) failed.
// 나가는 id 는 `^[1-9][0-9]*$` 만 숫자로(아니면 요청 0 으로 failed — 서버는 숫자 아닌 id 에 422).
import { asFailure } from '../../../shared/api/index.ts';
import type { Api } from '../../../shared/api/index.ts';
import { DEFAULT_VERSION_KEY } from '../model/index.ts';
import type { PromptModel, PromptModelOutcome } from '../model/index.ts';

/** prompt-model 경로가 계약에 있는 모듈(경로 칸 낱말). */
type PromptModelModule =
  'greenwash' | 'translation' | 'dataverify' | 'materiality' | 'drafting';
const PROMPT_MODEL_MODULES: readonly string[] = [
  'greenwash',
  'translation',
  'dataverify',
  'materiality',
  'drafting',
] satisfies PromptModelModule[];

interface CreatePromptModelReaderOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
  module: PromptModelModule;
}

type Shape = Record<string, unknown>;
const isObject = (value: unknown): value is Shape =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isString = (value: unknown): value is string => typeof value === 'string';
const isInt = (value: unknown): value is number => Number.isInteger(value);
const isNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);
const isBoolean = (value: unknown): value is boolean =>
  typeof value === 'boolean';
const all = (value: unknown, check: (one: unknown) => boolean) =>
  Array.isArray(value) && value.every(check);
/** 하나 이상(all 은 빈 배열도 받는다). */
const some = (value: unknown, check: (one: unknown) => boolean) =>
  all(value, check) && (value as unknown[]).length > 0;

const isModelRef = (value: unknown) =>
  isObject(value) &&
  isString(value.key) &&
  isString(value.label) &&
  isString(value.provider);

const isModel = (value: unknown) =>
  isObject(value) &&
  isString(value.route) &&
  all(value.models, isModelRef) &&
  (value.temperature === null || isNumber(value.temperature)) &&
  isInt(value.maxOutputTokens) &&
  isBoolean(value.webSearch);

const isRouteChoice = (value: unknown) =>
  isObject(value) &&
  isString(value.route) &&
  all(value.models, isModelRef) &&
  isBoolean(value.acceptsTemperature) &&
  isInt(value.maxOutputTokensMax) &&
  isBoolean(value.webSearchAvailable);

const isEntry = (value: unknown) =>
  isObject(value) &&
  isString(value.key) &&
  isString(value.label) &&
  isString(value.promptId) &&
  isString(value.promptVersion) &&
  isString(value.sha256) &&
  isString(value.text) &&
  isString(value.memo) &&
  isString(value.defaultText) &&
  isBoolean(value.isDefault) &&
  (value.outputSection === null || isString(value.outputSection)) &&
  isBoolean(value.outputKept);

/** 모델 칸 하나: 고를 경로 하나 이상, 쓸 수 없는 경로 이름(글 목록 — 화면 0, Q5). */
const isSlot = (value: unknown) =>
  isObject(value) &&
  isString(value.key) &&
  isString(value.label) &&
  isModel(value.model) &&
  some(value.routeChoices, isRouteChoice) &&
  all(value.unavailableRoutes, isString);

/** 프롬프트 묶음 하나: 칸 하나 이상, 받는 모델 칸 key(글 목록). */
const isGroup = (value: unknown) =>
  isObject(value) &&
  isString(value.key) &&
  isString(value.label) &&
  all(value.modelSlots, isString) &&
  some(value.prompts, isEntry);

const isFixedValue = (value: unknown) =>
  value === null ||
  isString(value) ||
  isNumber(value) ||
  (Array.isArray(value) && value.every(isString));

const isFixedGroup = (value: unknown) =>
  isObject(value) &&
  isString(value.key) &&
  isString(value.label) &&
  all(
    value.items,
    (item) =>
      isObject(item) &&
      isString(item.key) &&
      isString(item.label) &&
      isFixedValue(item.value),
  );

/** key 가 서로 겹치지 않는가(모델 칸끼리, 묶음끼리 — 화면이 key 로 칸을 찾는다). */
const distinctKeys = (value: unknown) => {
  const keys = (value as { key: string }[]).map((one) => one.key);
  return new Set(keys).size === keys.length;
};

/** 답이 ai.prompt-model@3 꼴인가(칸 전부 — 모델 칸·묶음은 하나 이상, key 겹침 없음). */
export function isPromptModel(value: unknown): value is PromptModel {
  return (
    isObject(value) &&
    value.schemaVersion === 'ai.prompt-model@3' &&
    isString(value.module) &&
    isString(value.settingName) &&
    isString(value.modelSettingsSha256) &&
    isObject(value.editable) &&
    isBoolean(value.editable.model) &&
    isBoolean(value.editable.prompts) &&
    isObject(value.limits) &&
    isInt(value.limits.textMax) &&
    isInt(value.limits.memoMax) &&
    some(value.models, isSlot) &&
    distinctKeys(value.models) &&
    some(value.promptGroups, isGroup) &&
    distinctKeys(value.promptGroups) &&
    all(value.fixed, isFixedGroup)
  );
}

/** 판 열쇠 하나의 prompt-model 을 읽는 함수. 캐시하지 않는다(판마다 한 번은 화면 훅이 정한다). */
export function createPromptModelReader({
  api,
  module,
}: CreatePromptModelReaderOptions) {
  const { client } = api;
  const send = (key: string) => {
    if (!PROMPT_MODEL_MODULES.includes(module)) return null;
    if (key === DEFAULT_VERSION_KEY)
      return () => client.GET(`/ai-settings/${module}/default/prompt-model`);
    if (!/^[1-9][0-9]*$/.test(key)) return null;
    const settingId = Number(key);
    if (!Number.isSafeInteger(settingId)) return null;
    return () =>
      client.GET(`/ai-settings/${module}/{setting_id}/prompt-model`, {
        params: { path: { setting_id: settingId } },
      });
  };

  return async (key: string): Promise<PromptModelOutcome> => {
    const request = send(key);
    if (request === null) return { kind: 'failed' };
    try {
      const { data } = await request();
      if (!isPromptModel(data)) return { kind: 'failed' };
      return { kind: 'ok', model: data };
    } catch (error) {
      const failure = asFailure(error);
      if (failure.kind !== 'api') return { kind: 'failed' };
      if (failure.status === 409 && failure.code === 'AI_SETTING_UNUSABLE')
        return { kind: 'unusable', message: failure.message };
      if (failure.status === 404) return { kind: 'missing' };
      return { kind: 'failed' };
    }
  };
}
