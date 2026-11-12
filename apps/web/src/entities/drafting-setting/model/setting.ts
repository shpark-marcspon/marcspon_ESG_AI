// 원고작성 AI 설정 판의 꼴과 순수 함수(밴드 RPA3). 서버 /ai-settings/drafting(RPA1 — drafting.ai-settings@1)의 계약 꼴을 import type 으로만 받는다.
//   중대성평가 IRO(entities/materiality-setting/model/setting.ts)와 같은 꼴 — 판 몫(모듈 몫)이 없어 저장 본문은 공통 본문 그대로다
//   ({title, memo, modelSettings, prompts} — 서버 DraftingAiSettingCreate).
//   - 나가는 id(idOut): 웹 id 는 글자로 다루고, 경로·본문에 실을 때 안전한 정수만 숫자로(아니면 요청 0 — 서버는 숫자 아닌 id 에 422).
//   - 새 판 저장에서 알아보는 거절 code(CREATE_CODES): 중대성평가와 같은 스물(자리 지킴 AI_PROMPT_PLACEHOLDER_MISSING 포함 — RPA1 처분 ⑥,
//     fields prompts.steps.<i>.prompts.<j>.text). apps/api-py drafting/service/apis/ai_settings.py 머리 글 — code 이름 그대로, 대문자.
import type { Schemas } from '../../../shared/api/index.ts';

export type SettingList = Schemas['DraftingAiSettingList'];
export type SettingSummary = Schemas['DraftingAiSettingSummary'];
export type Setting = Schemas['DraftingAiSetting'];
export type SettingCreate = Schemas['DraftingAiSettingCreate'];
export type SettingStatus = SettingSummary['status'];

/** 저장 판의 상태 셋(계약 enum). */
export const SETTING_STATUSES = [
  'applied',
  'past',
  'testing',
] as const satisfies readonly SettingStatus[];

/** 새 판 저장에서 알아보는 거절 code(서버 이름 그대로). 알아본 거절에만 서버 message·fields 를 싣는다. */
export const CREATE_CODES: readonly string[] = [
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
  'AI_PROMPT_PLACEHOLDER_MISSING',
  'NAME_CONFLICT',
];

/** 웹 id(글자) → 경로·본문의 숫자. 안전한 정수 글자가 아니면 null(요청 0). */
export function idOut(id: string): number | null {
  const value = Number(id);
  return Number.isSafeInteger(value) ? value : null;
}
