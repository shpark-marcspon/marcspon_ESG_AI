// AI 설정 판 초안(밴드 AD2W ③ — sid:MARC-ENT-387 「한 번 저장 = 새 판 하나」, 386 노트 「판 초안 하나 + [저장] 하나」). 순수 함수만 있다.
//   - 초안 = 바탕 판 prompt-model(@3)의 고칠 수 있는 칸: 모델 칸마다 모델(경로·temperature·출력 상한 — 칸 글 그대로) · 프롬프트 묶음마다 칸(글·메모).
//     수 칸은 글로 둔다(고치는 동안 틀린 글도 담는다). temperature 를 받지 않는 경로면 null.
//   - 셈(changes)은 바탕 값과 견준다(되돌려 같아지면 0): 모델 = 고친 모델 칸 수(칸 안 여러 값 = 1 — AP1W Q4 (나)), 프롬프트 = 글 바이트가 다르거나 메모가 Python strip 뒤
//     다른 칸마다 1(서버가 칸 메모를 strip 뒤에 잰다).
//   - 본문(bodyOf)은 안 고친 칸까지 늘 다(발주서 Q1), webSearch 는 읽은 값 그대로(sid:MARC-ENT-372 — 웹검색 칸 0).
//     modelSettings.steps[i] = 모델 칸 i(key = 칸 key), prompts.steps[i] = 묶음 i(key = 묶음 key) — 입력 꼴 그대로(AP1W).
//   - 저장 창 칸(saveFormProblems): 판 이름 = 서버 strip(pydantic) 뒤 코드포인트 1~40, 판 메모 = 생 코드포인트 0~200(서버는 메모를 떼지 않는다).
//   - 번호 추정(nextNumber): 서버는 v<실린 저장 판 번호의 최댓값 + 1>(services/ai_settings.py) — 저장 창의 「v4」는 추정이고 알림은 응답 번호.
import { codepoints, isBlank, pyStrip, titleStrip } from './chars.ts';
import type { PromptModel, RouteChoice, SaveBody, VersionRow } from './slot.ts';

export interface ModelDraft {
  key: string;
  route: string;
  /** temperature 칸 글. 경로가 받지 않으면 null. */
  temperature: string | null;
  maxOutputTokens: string;
}

export interface Draft {
  models: readonly ModelDraft[];
  /** 프롬프트 묶음마다 칸들(prompt-model promptGroups 차례 그대로). */
  prompts: readonly { key: string; text: string; memo: string }[][];
}

export interface Changes {
  /** 고친 모델 칸 수(칸 안 여러 값을 고쳐도 그 칸은 1). */
  model: number;
  /** 고친 칸의 자리(묶음·칸 번호). */
  prompts: readonly { group: number; prompt: number }[];
  /** 저장 막대의 「고친 것 n개」(모듈 몫은 AS3b 가 더한다). */
  total: number;
}

/** 프롬프트 칸 하나의 오류(없으면 null): 글 = 생 코드포인트가 textMax 넘음·Python strip 뒤 빈 글, 메모 = strip 뒤 코드포인트가 memoMax 넘음(서버 셈). */
export interface PromptErrors {
  text: 'over' | 'empty' | null;
  memo: 'over' | null;
}

/** 모델 칸 하나의 오류(없으면 null). */
export interface ModelErrors {
  temperature: 'range' | null;
  maxOutputTokens: 'range' | null;
}

const choiceOf = (pm: PromptModel, slot: number, route: string) =>
  pm.models[slot]?.routeChoices.find((choice) => choice.route === route);

/** 바탕 판 그대로의 초안. */
export function draftOf(pm: PromptModel): Draft {
  return {
    models: pm.models.map((slot) => ({
      key: slot.key,
      route: slot.model.route,
      temperature:
        slot.model.temperature === null ? null : String(slot.model.temperature),
      maxOutputTokens: String(slot.model.maxOutputTokens),
    })),
    prompts: pm.promptGroups.map((group) =>
      group.prompts.map((one) => ({
        key: one.key,
        text: one.text,
        memo: one.memo,
      })),
    ),
  };
}

/** 소수 글 → 수(빈 글·꼴 틀림은 NaN). */
const decimal = (text: string) =>
  /^\s*-?(\d+(\.\d*)?|\.\d+)\s*$/.test(text) ? Number(text) : Number.NaN;
/** 정수 글 → 수(꼴 틀림은 NaN). */
const integer = (text: string) =>
  /^\s*\d+\s*$/.test(text) ? Number(text) : Number.NaN;

/** 모델 칸 하나의 경로를 바꾼 초안: temperature 를 받지 않는 경로면 null, 받는 경로로 오면 바탕 값(바탕이 null 이면 빈칸 — 저장 끔). */
export function withRoute(
  pm: PromptModel,
  draft: Draft,
  slot: number,
  route: string,
): Draft {
  const accepts = choiceOf(pm, slot, route)?.acceptsTemperature ?? false;
  const base = pm.models[slot]?.model.temperature ?? null;
  return {
    ...draft,
    models: draft.models.map((one, index) =>
      index !== slot ? one : (
        {
          ...one,
          route,
          temperature:
            !accepts ? null
            : one.temperature !== null ? one.temperature
            : base === null ? ''
            : String(base),
        }
      ),
    ),
  };
}

/** 모델 칸마다 오류: temperature 0~2, 출력 상한 1~경로의 maxOutputTokensMax 정수. */
export function modelErrors(pm: PromptModel, draft: Draft): ModelErrors[] {
  return draft.models.map((one, slot) => {
    const choice: RouteChoice | undefined = choiceOf(pm, slot, one.route);
    const temperature =
      one.temperature === null ? null : decimal(one.temperature);
    const tokens = integer(one.maxOutputTokens);
    return {
      temperature:
        temperature === null || (temperature >= 0 && temperature <= 2) ?
          null
        : 'range',
      maxOutputTokens:
        tokens >= 1 && tokens <= (choice?.maxOutputTokensMax ?? 0) ?
          null
        : 'range',
    };
  });
}

/** 묶음마다 칸마다 프롬프트 칸 오류(AD2W ④ — 서버 _check_prompt_step 과 같은 셈, 서버가 마지막 그물). */
export function promptErrors(pm: PromptModel, draft: Draft): PromptErrors[][] {
  const { textMax, memoMax } = pm.limits;
  return draft.prompts.map((group) =>
    group.map((one) => ({
      text:
        codepoints(one.text) > textMax ? 'over'
        : isBlank(one.text) ? 'empty'
        : null,
      memo: codepoints(pyStrip(one.memo)) > memoMax ? 'over' : null,
    })),
  );
}

/** 바탕 판과 값이 다른 모델 칸의 자리(칸 차례). */
export function changedModels(pm: PromptModel, draft: Draft): number[] {
  return pm.models.flatMap((slot, index) => {
    const one = draft.models[index];
    if (!one) return [];
    const temperature =
      one.temperature === null ? null : decimal(one.temperature);
    return (
        one.route !== slot.model.route ||
          temperature !== slot.model.temperature ||
          integer(one.maxOutputTokens) !== slot.model.maxOutputTokens
      ) ?
        [index]
      : [];
  });
}

/** 바탕 판과 견준 고침. */
export function changes(pm: PromptModel, draft: Draft): Changes {
  const model = changedModels(pm, draft).length;
  const prompts = pm.promptGroups.flatMap((group, groupIndex) =>
    group.prompts.flatMap((base, promptIndex) => {
      const one = draft.prompts[groupIndex]?.[promptIndex];
      const changed =
        one !== undefined &&
        (one.text !== base.text || pyStrip(one.memo) !== pyStrip(base.memo));
      return changed ? [{ group: groupIndex, prompt: promptIndex }] : [];
    }),
  );
  return { model, prompts, total: model + prompts.length };
}

/** 저장 본문의 공통 몫: 판 이름·메모 + 모델 칸마다 다섯 칸(webSearch 는 읽은 값) + 묶음마다 칸 다. */
export function bodyOf(
  pm: PromptModel,
  draft: Draft,
  { title, memo }: { title: string; memo: string },
): SaveBody {
  return {
    title,
    memo,
    modelSettings: {
      steps: pm.models.map((slot, index) => {
        const one = draft.models[index]!;
        return {
          key: slot.key,
          route: one.route,
          temperature:
            one.temperature === null ? null : decimal(one.temperature),
          maxOutputTokens: integer(one.maxOutputTokens),
          webSearch: slot.model.webSearch,
        };
      }),
    },
    prompts: {
      steps: pm.promptGroups.map((group, index) => ({
        key: group.key,
        prompts: (draft.prompts[index] ?? []).map((one) => ({
          key: one.key,
          text: one.text,
          memo: one.memo,
        })),
      })),
    },
  };
}

/** 저장 창의 번호 추정: 실린 저장 판 번호(v<n>)의 최댓값 + 1(없으면 v1). */
export function nextNumber(rows: readonly VersionRow[]): string {
  const numbers = rows
    .filter((row) => row.kind === 'saved')
    .map((row) => Number(/^v(\d+)$/.exec(row.number)?.[1] ?? 0));
  return `v${Math.max(0, ...numbers) + 1}`;
}

/** 판 이름·메모의 상한(서버 apis/ai_settings.py — 이름 1~40, 메모 0~200 코드포인트). */
const TITLE_MAX = 40;
const MEMO_MAX = 200;

/** 저장 창 칸의 걸림(없으면 null). */
export function saveFormProblems(title: string, memo: string) {
  const length = codepoints(titleStrip(title));
  return {
    title:
      length === 0 ? ('empty' as const)
      : length > TITLE_MAX ? ('over' as const)
      : null,
    memo: codepoints(memo) > MEMO_MAX ? ('over' as const) : null,
  };
}
