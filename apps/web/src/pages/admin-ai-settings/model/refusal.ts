// AD-02 저장 거절·실패 → 창 안 줄·칸 오류(밴드 AD2S ② — AiSettingsScreen 에서 옮김, 동작 0). 순수 함수 — 글은 인자로 받는다.
//   code 로 가른다(상태 코드가 아니다): AI_MODEL_* 「모델 설정 — 서버 문장」, AI_PROMPT_* 의 fields 경로는 (묶음, 칸)으로 풀어 칸 오류 + 창 줄,
//   VALIDATION_ERROR 의 fields.title·memo 는 그 칸 아래, 그 밖은 일반 글.
//   AP1W ③: 그 셋 밖의 거절은 모듈(초안 슬롯의 refusal)에 먼저 묻는다 — 답이 있으면 창 줄과 모듈이 짚은 자리(module), null 이면 지금 갈래.
import { promptFieldOf } from '../../../entities/ai-setting/model/index.ts';
import type {
  ModuleRefused,
  SaveOutcome,
} from '../../../entities/ai-setting/model/index.ts';

/** 서버가 짚은 프롬프트 칸 오류(「묶음/칸」 → 칸 종류 → 문장). */
export type SlotRefusals = Readonly<
  Record<string, { text?: string; memo?: string }>
>;
export const slotKey = (group: number, prompt: number) => `${group}/${prompt}`;

/** 저장 창에 보이는 거절(창 안 줄 · 이름 칸 · 메모 칸). */
export interface RefusalShown {
  failure: string | null;
  titleError: string | null;
  memoError: string | null;
}

/** 거절 글(AI_SETTING_TEXT.save 꼴). */
export interface RefusalWords {
  modelRefused(message: string): string;
  fieldRefused(name: string, message: string): string;
  failed: string;
}

/** 모듈 거절 풀이(초안 슬롯의 refusal — 모르는 거절은 null). */
export type ModuleRefusal = (
  code: string | null,
  fields: Readonly<Record<string, readonly string[]>>,
) => { line: string; refused: ModuleRefused } | null;

/** 모듈에 묻지 않는 code(공통 갈래가 푼다). */
const COMMON_CODE = /^(AI_MODEL_|AI_PROMPT_|VALIDATION_ERROR$)/;

/** 저장 거절·실패 → 창 안 줄·칸 오류. label 은 칸 자리의 서버 label(모르는 자리는 null). module 은 모듈이 아는 거절이면 답한다. */
export function refusalOf(
  outcome: Exclude<SaveOutcome, { kind: 'ok' }>,
  label: (group: number, prompt: number) => string | null,
  words: RefusalWords,
  module?: ModuleRefusal,
): RefusalShown & { slots: SlotRefusals; module?: ModuleRefused } {
  const none = { failure: null, titleError: null, memoError: null, slots: {} };
  if (
    module &&
    outcome.kind === 'rejected' &&
    !COMMON_CODE.test(outcome.code ?? '')
  ) {
    const answer = module(outcome.code, outcome.fields);
    if (answer)
      return { ...none, failure: answer.line, module: answer.refused };
  }
  if (outcome.kind === 'rejected' && outcome.message !== null) {
    if (outcome.code?.startsWith('AI_MODEL_'))
      return { ...none, failure: words.modelRefused(outcome.message) };
    if (outcome.code?.startsWith('AI_PROMPT_')) {
      const slots: Record<string, { text?: string; memo?: string }> = {};
      const lines: string[] = [];
      for (const [path, messages] of Object.entries(outcome.fields)) {
        const at = promptFieldOf(path);
        const name = at && label(at.group, at.prompt);
        if (!at || name === null) continue;
        const key = slotKey(at.group, at.prompt);
        const said = messages[0] ?? outcome.message;
        slots[key] = { ...slots[key], [at.field]: said };
        lines.push(words.fieldRefused(name, said));
      }
      return {
        ...none,
        slots,
        failure: lines.length > 0 ? lines.join(' · ') : outcome.message,
      };
    }
    const title = outcome.fields.title?.[0] ?? null;
    const memo = outcome.fields.memo?.[0] ?? null;
    if (outcome.code === 'VALIDATION_ERROR' && (title ?? memo) !== null)
      return { ...none, titleError: title, memoError: memo };
  }
  return { ...none, failure: words.failed };
}
