// AD-02 저장 거절·실패 풀이(밴드 AD2S ②): code 로 가른다. 글은 시험이 지은 것(문구 표를 가져오지 않는다).
import { describe, expect, it } from 'vitest';
import { vi } from 'vitest';

import { fakeWidePromptModel } from '../../../entities/ai-setting/api/testing.ts';
import { promptLabel } from '../../../entities/ai-setting/model/index.ts';
import { refusalOf, slotKey } from './refusal.ts';
import type { RefusalWords } from './refusal.ts';

const words: RefusalWords = {
  modelRefused: (message) => `모델: ${message}`,
  fieldRefused: (name, message) => `${name}: ${message}`,
  failed: '일반 실패',
};
const labels: Record<string, string> = {
  '0/1': '지어낸 판정',
  '0/3': '지어낸 찾기',
};
const label = (step: number, prompt: number) =>
  labels[slotKey(step, prompt)] ?? null;
const rejected = (
  code: string | null,
  message: string | null,
  fields: Record<string, string[]> = {},
) => ({ kind: 'rejected' as const, code, message, fields });

describe('refusalOf', () => {
  it('AI_MODEL_* → 창 줄 「모델: 서버 문장」 · 칸 오류 0', () => {
    expect(
      refusalOf(
        rejected('AI_MODEL_NOT_ALLOWED', '지어낸 모델 문장'),
        label,
        words,
      ),
    ).toEqual({
      failure: '모델: 지어낸 모델 문장',
      titleError: null,
      memoError: null,
      slots: {},
    });
  });

  it('AI_PROMPT_* 아는 경로 둘 → 그 칸 오류 + 창 줄 「 · 」 이음 (fields 문장이 없으면 서버 문장)', () => {
    const got = refusalOf(
      rejected('AI_PROMPT_TOO_LONG', '지어낸 전체 문장', {
        'prompts.steps.0.prompts.1.text': ['지어낸 글 문장'],
        'prompts.steps.0.prompts.3.memo': [],
      }),
      label,
      words,
    );
    expect(got.slots).toEqual({
      '0/1': { text: '지어낸 글 문장' },
      '0/3': { memo: '지어낸 전체 문장' },
    });
    expect(got.failure).toBe(
      '지어낸 판정: 지어낸 글 문장 · 지어낸 찾기: 지어낸 전체 문장',
    );
  });

  it('AI_PROMPT_* 모르는 경로뿐 → 칸 오류 0 · 창 줄은 서버 문장', () => {
    const got = refusalOf(
      rejected('AI_PROMPT_TOO_LONG', '지어낸 전체 문장', {
        'prompts.steps.0.prompts.2.text': ['지어낸 글 문장'],
        'somewhere.else': ['지어낸'],
      }),
      label,
      words,
    );
    expect(got).toEqual({
      failure: '지어낸 전체 문장',
      titleError: null,
      memoError: null,
      slots: {},
    });
  });

  it('VALIDATION_ERROR fields.title·memo → 그 칸 오류(창 줄 0)', () => {
    expect(
      refusalOf(
        rejected('VALIDATION_ERROR', '지어낸', {
          title: ['지어낸 이름 문장'],
          memo: ['지어낸 메모 문장'],
        }),
        label,
        words,
      ),
    ).toEqual({
      failure: null,
      titleError: '지어낸 이름 문장',
      memoError: '지어낸 메모 문장',
      slots: {},
    });
  });

  it.each([
    ['message null', rejected('AI_MODEL_NOT_ALLOWED', null)],
    ['VALIDATION_ERROR 칸 0', rejected('VALIDATION_ERROR', '지어낸')],
    ['모르는 code', rejected('SOMETHING', '지어낸')],
    ['failed', { kind: 'failed' as const }],
  ])('%s → 일반 실패', (_, outcome) => {
    expect(refusalOf(outcome, label, words)).toEqual({
      failure: '일반 실패',
      titleError: null,
      memoError: null,
      slots: {},
    });
  });
});

describe('promptLabel(AP1W — 묶음 i, 칸 j)', () => {
  it('prompts.steps.4.prompts.1.text → 묶음 4(autofix) 칸 1(autofix_korean)의 label · 모르는 자리는 null', () => {
    const wide = fakeWidePromptModel('v3');
    const got = refusalOf(
      rejected('AI_PROMPT_TOO_LONG', '지어낸 전체 문장', {
        'prompts.steps.4.prompts.1.text': ['지어낸 글 문장'],
      }),
      promptLabel(wide),
      words,
    );
    const entry = wide.promptGroups[4]!.prompts[1]!;
    expect(entry.key).toBe('autofix_korean');
    expect(got.failure).toBe(`${entry.label}: 지어낸 글 문장`);
    expect(got.slots).toEqual({ '4/1': { text: '지어낸 글 문장' } });
    expect(promptLabel(wide)(5, 0)).toBeNull();
    expect(promptLabel(wide)(0, 9)).toBeNull();
  });
});

describe('refusalOf 모듈 물음(AP1W ③)', () => {
  const fields = { words: ['지어낸 낱말 문장'] };
  const ask = vi.fn((code: string | null) =>
    code?.startsWith('FAKE_DRAFT_') ?
      { line: '지어낸 모듈 줄', refused: fields }
    : null,
  );

  it('공통 code 밖이면 모듈에 먼저 묻는다 — 답이 있으면 창 줄 = line · module = 짚은 자리', () => {
    expect(
      refusalOf(rejected('FAKE_DRAFT_X', null, fields), label, words, ask),
    ).toEqual({
      failure: '지어낸 모듈 줄',
      titleError: null,
      memoError: null,
      slots: {},
      module: fields,
    });
    expect(ask).toHaveBeenLastCalledWith('FAKE_DRAFT_X', fields);
  });

  it('모듈이 null 이면 지금 갈래(일반 실패) · AI_MODEL_·AI_PROMPT_·VALIDATION_ERROR 는 묻지 않는다', () => {
    ask.mockClear();
    expect(
      refusalOf(rejected('SOMETHING', '지어낸', fields), label, words, ask),
    ).toEqual({
      failure: '일반 실패',
      titleError: null,
      memoError: null,
      slots: {},
    });
    expect(ask).toHaveBeenCalledTimes(1);
    ask.mockClear();
    for (const code of ['AI_MODEL_X', 'AI_PROMPT_X', 'VALIDATION_ERROR'])
      refusalOf(rejected(code, '지어낸', fields), label, words, ask);
    expect(ask).not.toHaveBeenCalled();
  });
});
