// AD-02 구성 열 줄 짓기(밴드 AD2S ② — AiSettingsScreen 에서 옮김, 동작 0). 순수 함수 — 글은 인자로 받는다(어드민 pages model 은 문구 표를 가져오지 못한다).
//   차례(r3): 모델 설정 · 프롬프트 · 모듈 줄(lines 아님 — 준비 중) · 서버 고정 값 묶음(차례대로) · 모듈의 읽기 전용 줄(lines). 꼬리는 서버 값으로 셈.
//   AP1W ②: 모델 칸이 쓰이는 묶음(modelUses) · 저장 창 「고친 것」(changeList — 칸·묶음 하나면 글 한 줄, 여럿이면 항목 목록).
//   AP1W ③: 모듈 초안 줄(draft)의 꼬리는 moduleTail 로 — 읽는 중 「준비 중」 · 실패 「다시 시도」 · 고쳤으면 「고침 n」 · 아니면 모듈 sum.
//   LK2: 고정 값 묶음 줄·모듈의 읽기 전용 줄(lines)은 locked — 화면이 이름 앞 자물쇠를 그린다.
import type {
  Changes,
  ModuleComponent,
  PromptModel,
} from '../../../entities/ai-setting/model/index.ts';

/** 구성 열 줄 하나: 열쇠·이름·꼬리. */
export interface ComponentLine {
  key: string;
  label: string;
  sum?: string;
  /** 고정(읽기 전용) 줄 — 고정 값 묶음 · 모듈 읽기 전용 줄. */
  locked?: boolean;
}

/** 구성 열 글(AI_SETTING_TEXT.components 꼴). */
export interface LineWords {
  model: string;
  prompt: string;
  modelOne: string;
  modelSlots(n: number): string;
  modelMany(first: string): string;
  promptFixed(steps: number, prompts: number): string;
  fixedSum(n: number): string;
  edited(n: number): string;
  /** 모듈 초안 줄의 바탕 몫 읽는 중 꼬리(moduleTail 을 줄 때). */
  pending?: string;
  /** 모듈 초안 줄의 바탕 몫 읽기 실패 꼬리(moduleTail 을 줄 때). */
  retry?: string;
}

/** 모듈 초안 줄(draft)의 꼬리 재료: 바탕 몫 상태 · 모듈 셈 · 모듈 sum(안 고쳤을 때). */
export interface ModuleTail {
  state: 'loading' | 'failed' | 'ok';
  count: number;
  sum: string;
}

/** 모델 하나의 보이는 이름(「지어낸 미니」 — 회사 이름을 붙이지 않는다, 밴드 AD8). 이름이 비면 회사, 모델이 없으면 경로 이름. */
export const modelName = (
  models: readonly { provider: string; label: string }[],
  route: string,
) => models[0]?.label || models[0]?.provider || route;

/**
 * 모델 설정 꼬리: 모델 칸 하나 → 「모든 단계에 하나」, 칸 둘 이상 · 모두 같은 모델 → 「<n>칸」(AD6),
 * 다른 모델이 섞이면 「<첫 모델> · 단계마다 다름」.
 */
export function modelSum(model: PromptModel, words: LineWords) {
  const names = model.models.map((slot) =>
    modelName(slot.model.models, slot.model.route),
  );
  if (new Set(names).size > 1) return words.modelMany(names[0]!);
  return names.length <= 1 ? words.modelOne : words.modelSlots(names.length);
}

/** 프롬프트 칸 수(묶음마다 칸 수의 합). */
export const promptCount = (model: PromptModel) =>
  model.promptGroups.reduce((sum, group) => sum + group.prompts.length, 0);

/** 구성 열 줄들(r3 차례). model 이 없으면(판 읽기 전) 모델·프롬프트 꼬리 없음. */
export function componentLines({
  model,
  changes,
  components,
  words,
  moduleTail,
}: {
  model: PromptModel | null;
  changes: Changes;
  components: readonly ModuleComponent[];
  words: LineWords;
  /** 모듈 초안 줄의 꼬리(없으면 모듈 줄의 sum 그대로). */
  moduleTail?: ModuleTail;
}): ComponentLine[] {
  const tail = (one: ModuleComponent) =>
    one.body.kind !== 'draft' || !moduleTail ? one.sum
    : moduleTail.state === 'loading' ? words.pending
    : moduleTail.state === 'failed' ? words.retry
    : moduleTail.count > 0 ? words.edited(moduleTail.count)
    : moduleTail.sum;
  return [
    {
      key: 'model',
      label: words.model,
      sum:
        changes.model > 0 ? words.edited(changes.model)
        : model ? modelSum(model, words)
        : undefined,
    },
    {
      key: 'prompt',
      label: words.prompt,
      sum:
        changes.prompts.length > 0 ? words.edited(changes.prompts.length)
        : model ?
          words.promptFixed(model.promptGroups.length, promptCount(model))
        : undefined,
    },
    ...components
      .filter((one) => one.body.kind !== 'lines')
      .map((one) => ({
        key: `module:${one.key}`,
        label: one.label,
        sum: tail(one),
      })),
    ...(model?.fixed ?? []).map((group) => ({
      key: `fixed:${group.key}`,
      label: group.label,
      sum: words.fixedSum(group.items.length),
      locked: true,
    })),
    ...components
      .filter((one) => one.body.kind === 'lines')
      .map((one) => ({
        key: `module:${one.key}`,
        label: one.label,
        sum: one.sum,
        locked: true,
      })),
  ];
}

/** 모델 칸 key → 그 칸의 글을 받는 묶음 label(묶음 차례 — 서버 modelSlots 를 거꾸로). 쓰는 곳이 없는 칸은 빈 목록. */
export function modelUses(model: {
  models: readonly PromptModel['models'][number][];
  promptGroups: readonly PromptModel['promptGroups'][number][];
}): Record<string, string[]> {
  const uses: Record<string, string[]> = Object.fromEntries(
    model.models.map((slot) => [slot.key, []]),
  );
  for (const group of model.promptGroups)
    for (const key of group.modelSlots) uses[key]?.push(group.label);
  return uses;
}

/** 저장 창 「고친 것」 글(AI_SETTING_TEXT.changed + prompt.slot 꼴). */
export interface ChangeWords {
  model: string;
  join: string;
  slot(index: number, label: string): string;
  slotModel(slot: string): string;
  slotPrompt(n: number, group: string, slot: string): string;
}

/**
 * 저장 창 「고친 것」: 모델 칸·묶음이 하나씩이면 지금 글 한 줄(「모델 설정 · 2. 칸」), 어느 하나라도 둘 이상이면 항목 목록
 * (모델 칸 차례 → 묶음·칸 차례 — 모델 칸 둘 이상이면 고친 칸마다 「모델 설정 · <칸>」, 하나면 「모델 설정」, 프롬프트 「<묶음 순번>. <묶음> · <칸>」).
 */
export function changeList({
  model,
  changedSlots,
  changes,
  words,
}: {
  model: PromptModel;
  /** 고친 모델 칸의 자리(칸 차례). */
  changedSlots: readonly number[];
  changes: Changes;
  words: ChangeWords;
}): string | string[] {
  const { models, promptGroups } = model;
  const label = (group: number, prompt: number) =>
    promptGroups[group]?.prompts[prompt]?.label ?? '';
  if (models.length < 2 && promptGroups.length < 2) {
    const before = (group: number) =>
      promptGroups
        .slice(0, group)
        .reduce((sum, one) => sum + one.prompts.length, 0);
    return [
      ...(changes.model > 0 ? [words.model] : []),
      ...changes.prompts.map(({ group, prompt }) =>
        words.slot(before(group) + prompt + 1, label(group, prompt)),
      ),
    ].join(words.join);
  }
  return [
    ...(models.length < 2 ?
      changes.model > 0 ?
        [words.model]
      : []
    : changedSlots.map((index) => words.slotModel(models[index]?.label ?? ''))),
    ...changes.prompts.map(({ group, prompt }) =>
      words.slotPrompt(
        group + 1,
        promptGroups[group]?.label ?? '',
        label(group, prompt),
      ),
    ),
  ];
}
