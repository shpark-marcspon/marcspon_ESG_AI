// AD-02 구성 열 줄 짓기(밴드 AD2S ②): 차례(r3) · 꼬리 셈 · 모델 이름. 글은 시험이 지은 것(문구 표를 가져오지 않는다).
import { describe, expect, it } from 'vitest';

import { fakePromptModel } from '../../../entities/ai-setting/api/testing.ts';
import { fakeWidePromptModel } from '../../../entities/ai-setting/api/testing.ts';
import type {
  Changes,
  ModuleComponent,
} from '../../../entities/ai-setting/model/index.ts';
import { componentLines, modelName, modelSum, promptCount } from './lines.ts';
import { modelUses } from './lines.ts';
import type { LineWords } from './lines.ts';

const words: LineWords = {
  model: '모델',
  prompt: '글',
  modelOne: '하나',
  modelSlots: (n) => `칸${n}개`,
  modelMany: (first) => `${first} 외`,
  promptFixed: (steps, n) => `단계${steps}칸${n}`,
  fixedSum: (n) => `묶음${n}`,
  edited: (n) => `고침${n}`,
};
const NONE: Changes = { model: 0, prompts: [], total: 0 };
const components: readonly ModuleComponent[] = [
  {
    key: 'rules',
    label: '지어낸 규칙 줄',
    sum: '읽기',
    body: { kind: 'lines', title: '지어낸', lines: ['하나'], foot: '꼬리' },
  },
  {
    key: 'terms',
    label: '지어낸 단어',
    sum: '준비',
    body: { kind: 'pending' },
  },
];
const keys = (lines: { key: string }[]) => lines.map((line) => line.key);

describe('componentLines', () => {
  it('차례: 모델 · 프롬프트 · 모듈 줄(lines 아님) · 고정 묶음 · 모듈 줄(lines) — 모듈 차례와 무관', () => {
    const lines = componentLines({
      model: fakePromptModel('v3'),
      changes: NONE,
      components,
      words,
    });
    expect(keys(lines)).toEqual([
      'model',
      'prompt',
      'module:terms',
      'fixed:parts',
      'fixed:processing',
      'module:rules',
    ]);
    expect(lines.map((line) => line.sum)).toEqual([
      '하나',
      '단계1칸4',
      '준비',
      '묶음3',
      '묶음5',
      '읽기',
    ]);
    expect(lines.map((line) => line.label)).toEqual([
      '모델',
      '글',
      '지어낸 단어',
      '파트',
      '처리 값',
      '지어낸 규칙 줄',
    ]);
  });

  it('model null(판 읽기 전) → 모델·프롬프트 꼬리 없음 · 고정 묶음 없음', () => {
    const lines = componentLines({
      model: null,
      changes: NONE,
      components,
      words,
    });
    expect(keys(lines)).toEqual([
      'model',
      'prompt',
      'module:terms',
      'module:rules',
    ]);
    expect(lines[0]!.sum).toBeUndefined();
    expect(lines[1]!.sum).toBeUndefined();
  });

  it('고침: changes.model → 모델 「고침1」, 칸 셋 → 프롬프트 「고침3」(model 이 없어도)', () => {
    const changes: Changes = {
      model: 1,
      prompts: [
        { group: 0, prompt: 0 },
        { group: 0, prompt: 1 },
        { group: 0, prompt: 3 },
      ],
      total: 4,
    };
    for (const model of [fakePromptModel('v3'), null]) {
      const lines = componentLines({ model, changes, components, words });
      expect(lines[0]!.sum).toBe('고침1');
      expect(lines[1]!.sum).toBe('고침3');
    }
  });
});

describe('componentLines locked (LK2)', () => {
  it('고정 값 묶음 줄 · 모듈 읽기 전용 줄(lines)만 locked, 모델·프롬프트·모듈 준비 줄은 아님', () => {
    const lines = componentLines({
      model: fakePromptModel('v3'),
      changes: NONE,
      components,
      words,
    });
    expect(
      lines.filter((line) => line.locked === true).map((line) => line.key),
    ).toEqual(['fixed:parts', 'fixed:processing', 'module:rules']);
    for (const key of ['model', 'prompt', 'module:terms'])
      expect(lines.find((line) => line.key === key)!.locked).toBeUndefined();
  });
});

describe('modelSum · modelName · promptCount', () => {
  it('칸 하나 → 하나 · 같은 모델 둘 → 「칸2개」(AD6) · 다른 모델 → 「<첫 이름> 외」', () => {
    const one = fakePromptModel('v3');
    expect(modelSum(one, words)).toBe('하나');
    const step = one.models[0]!;
    const same = { ...one, models: [step, { ...step, key: 'second' }] };
    expect(modelSum(same, words)).toBe('칸2개');
    const other = {
      ...one,
      models: [
        step,
        {
          ...step,
          key: 'second',
          model: {
            ...step.model,
            route: 'fake-think',
            models: [
              { key: 'fake-think-1', label: '지어낸 생각', provider: 'OpenAI' },
            ],
          },
        },
      ],
    };
    expect(modelSum(other, words)).toBe('지어낸 미니 외');
  });

  it('modelName: 모델 이름만(회사 이름 0), 이름이 비면 회사, 모델이 없으면 경로 이름', () => {
    expect(
      modelName([{ provider: 'OpenAI', label: '지어낸 미니' }], 'fake-mini'),
    ).toBe('지어낸 미니');
    expect(modelName([{ provider: 'OpenAI', label: '' }], 'fake-mini')).toBe(
      'OpenAI',
    );
    expect(modelName([{ provider: '', label: '' }], 'fake-mini')).toBe(
      'fake-mini',
    );
    expect(modelName([], 'fake-route')).toBe('fake-route');
  });

  it('promptCount: 단계마다 칸 수를 더한다', () => {
    const one = fakePromptModel('v3');
    expect(promptCount(one)).toBe(4);
    expect(
      promptCount({
        ...one,
        promptGroups: [one.promptGroups[0]!, one.promptGroups[0]!],
      }),
    ).toBe(8);
  });
});

describe('넓은 꼴 @3(AP1W)', () => {
  it('promptCount = 묶음 칸 합 14 · 모델 칸 셋 다른 모델 → 「<첫 이름> 외」', () => {
    const wide = fakeWidePromptModel('v3');
    expect(promptCount(wide)).toBe(14);
    expect(modelSum(wide, words)).toBe('지어낸 a1 외');
  });
});

describe('modelUses · 모델 몫 셈(AP1W ②)', () => {
  it('modelUses: 칸 key → 그 칸을 쓰는 묶음 label(묶음 차례), 쓰는 곳 0 인 칸은 빈 목록', () => {
    const wide = fakeWidePromptModel('v3');
    const used = ['지어낸 옮김', '지어낸 다듬기', '지어낸 살핌', '지어낸 고침'];
    expect(modelUses(wide)).toEqual({
      translate_ceo: used,
      translate_other: used,
      review: ['지어낸 검토'],
    });
    const idle = {
      ...wide,
      promptGroups: wide.promptGroups.map((group) => ({
        ...group,
        modelSlots: group.modelSlots.filter((key) => key !== 'review'),
      })),
    };
    expect(modelUses(idle).review).toEqual([]);
  });

  it('모델 칸 둘을 고치면 모델 줄 「고침2」', () => {
    const lines = componentLines({
      model: fakeWidePromptModel('v3'),
      changes: { model: 2, prompts: [], total: 2 },
      components,
      words,
    });
    expect(lines[0]!.sum).toBe('고침2');
  });
});

describe('모듈 초안 줄 꼬리(AP1W ③ — moduleTail)', () => {
  const withDraft: readonly ModuleComponent[] = [
    ...components,
    {
      key: 'draft',
      label: '지어낸 초안 몫',
      sum: '모듈 sum',
      body: { kind: 'draft' },
    },
  ];
  const tailOf = (
    moduleTail?: Parameters<typeof componentLines>[0]['moduleTail'],
  ) =>
    componentLines({
      model: fakePromptModel('v3'),
      changes: NONE,
      components: withDraft,
      words: { ...words, pending: '읽는 중', retry: '다시' },
      moduleTail,
    }).find((line) => line.key === 'module:draft')!.sum;

  it('읽는 중 「pending」 · 실패 「retry」 · 고쳤으면 「고침 n」 · 아니면 모듈 sum — 차례는 고정 묶음 앞', () => {
    expect(tailOf({ state: 'loading', count: 0, sum: '' })).toBe('읽는 중');
    expect(tailOf({ state: 'failed', count: 0, sum: '' })).toBe('다시');
    expect(tailOf({ state: 'ok', count: 3, sum: '낱말 둘' })).toBe('고침3');
    expect(tailOf({ state: 'ok', count: 0, sum: '낱말 둘' })).toBe('낱말 둘');
    expect(tailOf()).toBe('모듈 sum');
    const lines = componentLines({
      model: fakePromptModel('v3'),
      changes: NONE,
      components: withDraft,
      words,
    });
    expect(keys(lines).indexOf('module:draft')).toBeLessThan(
      keys(lines).findIndex((key) => key.startsWith('fixed:')),
    );
  });
});
