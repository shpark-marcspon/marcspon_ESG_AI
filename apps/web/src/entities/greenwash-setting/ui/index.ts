// 그린워싱 AI 설정 판 ui 칸의 공개 표면(밴드 AS3b ①). app/admin/ai-setting-modules.ts 만 가져온다.
//   termsDraftSlot: AD-02 모듈 초안 슬롯(대상 단어) 한 벌 — 꼴은 entities/ai-setting 의 ModuleDraftSlot 과 구조로 맞춘다(그 슬라이스도 api 칸도 가져오지 않는다,
//   읽기 함수는 모듈 줄이 넘긴다 — 발주서 K1). key 는 늘 'terms'(구성 줄 terms 와 짝 — 바탕 몫 캐시가 key 에 묶인다).
//   flowSlot(AS3b ②): 처리 흐름 띠 그리기 — 껍데기의 FlowProps 와 구조로 맞춘다(FlowBand 에 글 표를 붙여 넘김).
//   바탕 몫(load): 기본 판 = getDefault(terms 늘 null) → 기본 단어 목록, 저장 판 = get(id) 의 terms(null 이면 기본 단어 목록). 하나라도 실패 = failed(빈 목록으로 두지 않는다).
import { createElement } from 'react';
import type { ReactNode } from 'react';

import type { GREENWASH_SETTING_TEXT } from '../config/text.ts';
import {
  DEFAULT_KEY,
  termsBase,
  termsBlocked,
  termsChanged,
  termsCount,
  termsRefusal,
} from '../model/index.ts';
import type { Term, TermsDraft } from '../model/index.ts';
import { FlowBand } from './FlowBand.tsx';
import type { FlowBandProps } from './FlowBand.tsx';
import { TermsCard } from './TermsCard.tsx';

export { FlowBand } from './FlowBand.tsx';
export type { FlowBandProps } from './FlowBand.tsx';
export { TermsCard } from './TermsCard.tsx';
export type { TermsCardProps } from './TermsCard.tsx';

type Read<T> = Promise<{ kind: 'ok'; setting: T } | { kind: 'failed' }>;

/** 바탕 몫 읽기(모듈 줄이 그린워싱 실어댑터에서 넘긴다). */
export interface TermsReader {
  get(id: string): Read<{ terms: readonly Term[] | null }>;
  getDefault(): Read<{ terms: null }>;
  defaultTerms(): Promise<
    { kind: 'ok'; terms: readonly string[] } | { kind: 'failed' }
  >;
}

/** 구성 줄 열쇠(대상 단어). */
export const TERMS_SLOT_KEY = 'terms';

const list = (value: unknown) => value as TermsDraft;

/** 대상 단어 모듈 초안 슬롯(AD-02 ModuleDraftSlot 꼴). */
export function termsDraftSlot(
  reader: TermsReader,
  words: typeof GREENWASH_SETTING_TEXT,
) {
  const t = words.terms;
  const withDefaults = async (terms: readonly Term[] | null) => {
    if (terms !== null)
      return { kind: 'ok' as const, base: termsBase(terms, []) };
    const defaults = await reader.defaultTerms();
    return defaults.kind === 'ok' ?
        { kind: 'ok' as const, base: termsBase(null, defaults.terms) }
      : { kind: 'failed' as const };
  };
  return {
    key: TERMS_SLOT_KEY,
    async load(
      version: string,
    ): Promise<{ kind: 'ok'; base: unknown } | { kind: 'failed' }> {
      const loaded =
        version === DEFAULT_KEY ?
          await reader.getDefault()
        : await reader.get(version);
      if (loaded.kind !== 'ok') return { kind: 'failed' };
      return withDefaults(loaded.setting.terms);
    },
    count: (base: unknown, draft: unknown) =>
      termsCount(list(base), list(draft)),
    changed: (base: unknown, draft: unknown) =>
      termsChanged(list(base), list(draft), t.changed),
    blocked: (draft: unknown) => termsBlocked(list(draft)),
    sum: (_base: unknown, draft: unknown) => t.sum(list(draft).length),
    refusal: (
      code: string | null,
      fields: Readonly<Record<string, readonly string[]>>,
    ) => termsRefusal(code, fields, { label: t.title, refused: t.refused }),
    render: (p: {
      base: unknown;
      draft: unknown;
      readOnly: boolean;
      onChange(next: unknown): void;
      refused: Readonly<Record<string, readonly string[]>>;
    }): ReactNode =>
      createElement(TermsCard, {
        base: list(p.base),
        draft: list(p.draft),
        readOnly: p.readOnly,
        refused: p.refused,
        onChange: p.onChange,
        words: t,
      }),
  };
}

/** 처리 흐름 띠(AD-02 AiSettingModule.flow 꼴). */
export function flowSlot(words: typeof GREENWASH_SETTING_TEXT) {
  return function flow(p: Omit<FlowBandProps, 'words'>): ReactNode {
    return createElement(FlowBand, { ...p, words: words.flow });
  };
}
