// AI 설정 판 초안(밴드 AD2W ③). 셈은 바탕 값과 견주고(되돌리면 0), 본문은 안 고친 칸까지 늘 넷 다(발주서 Q1), webSearch 는 읽은 값 그대로.
import { describe, expect, it } from 'vitest';

import { fakePromptModel } from '../api/testing.ts';
import { fakeWidePromptModel } from '../api/testing.ts';
import {
  bodyOf,
  changedModels,
  changes,
  draftOf,
  modelErrors,
  nextNumber,
  promptErrors,
  saveFormProblems,
  withRoute,
} from './draft.ts';
import type { Draft } from './draft.ts';
import type { VersionRow } from './slot.ts';

/** U+3000(전각 공백 — Python·JS 둘 다 공백). 글로 두면 보이지 않아 코드포인트로. */
const IDEOGRAPHIC = String.fromCodePoint(0x3000);
const pm = fakePromptModel('setting-13');
const setModel = (
  draft: Draft,
  change: Partial<Draft['models'][number]>,
): Draft => ({
  ...draft,
  models: [{ ...draft.models[0]!, ...change }],
});
const setPrompt = (
  draft: Draft,
  index: number,
  change: Partial<Draft['prompts'][number][number]>,
): Draft => ({
  ...draft,
  prompts: [
    draft.prompts[0]!.map((one, at) =>
      at === index ? { ...one, ...change } : one,
    ),
  ],
});

describe('draftOf · changes — 바탕 값과 견줌', () => {
  it('바탕 그대로면 0, 수 칸은 글(temperature 0.2 → 「0.2」)', () => {
    const draft = draftOf(pm);
    expect(draft.models).toEqual([
      {
        key: 'judge',
        route: 'fake-mini',
        temperature: '0.2',
        maxOutputTokens: '2000',
      },
    ]);
    expect(changes(pm, draft)).toEqual({ model: 0, prompts: [], total: 0 });
  });

  it('고쳤다 되돌리면 0(손댄 적이 아니라 값으로 센다)', () => {
    const edited = setModel(draftOf(pm), { maxOutputTokens: '3000' });
    expect(changes(pm, edited).total).toBe(1);
    expect(changes(pm, setModel(edited, { maxOutputTokens: '2000' }))).toEqual({
      model: 0,
      prompts: [],
      total: 0,
    });
    expect(
      changes(pm, setModel(edited, { maxOutputTokens: '02000' })).total,
    ).toBe(0);
  });

  it('모델 칸 둘을 고쳐도 1, 프롬프트는 고친 칸마다 1', () => {
    let draft = setModel(draftOf(pm), {
      temperature: '0.5',
      maxOutputTokens: '3000',
    });
    draft = setPrompt(draft, 1, { text: '지어낸 고친 글' });
    draft = setPrompt(draft, 3, { memo: '지어낸 고친 메모' });
    expect(changes(pm, draft)).toEqual({
      model: 1,
      prompts: [
        { group: 0, prompt: 1 },
        { group: 0, prompt: 3 },
      ],
      total: 3,
    });
  });

  it('메모 뒤 공백만(Python strip 뒤 같음) = 0, 글은 바이트로(뒤 공백 하나도 1)', () => {
    const base = pm.promptGroups[0]!.prompts[0]!;
    expect(
      changes(
        pm,
        setPrompt(draftOf(pm), 0, {
          memo: `${base.memo} ${IDEOGRAPHIC}\u001c`,
        }),
      ).total,
    ).toBe(0);
    expect(
      changes(pm, setPrompt(draftOf(pm), 0, { text: `${base.text} ` })).total,
    ).toBe(1);
  });

  it('temperature 를 받지 않는 판(null)은 null 초안, 같으면 0', () => {
    const think = fakePromptModel('setting-13', {
      model: { route: 'fake-think', temperature: null },
    });
    expect(draftOf(think).models[0]!.temperature).toBeNull();
    expect(changes(think, draftOf(think)).total).toBe(0);
  });
});

describe('withRoute · modelErrors', () => {
  it('받지 않는 경로 → temperature null, 다시 받는 경로 → 바탕 값', () => {
    const think = withRoute(pm, draftOf(pm), 0, 'fake-think');
    expect(think.models[0]).toMatchObject({
      route: 'fake-think',
      temperature: null,
    });
    expect(withRoute(pm, think, 0, 'fake-mini').models[0]!.temperature).toBe(
      '0.2',
    );
  });

  it('바탕이 null 인데 받는 경로로 오면 빈칸 → 범위 오류(저장 끔)', () => {
    const think = fakePromptModel('setting-13', {
      model: { route: 'fake-think', temperature: null },
    });
    const mini = withRoute(think, draftOf(think), 0, 'fake-mini');
    expect(mini.models[0]!.temperature).toBe('');
    expect(modelErrors(think, mini)[0]!.temperature).toBe('range');
  });

  it('temperature 0~2, 출력 상한 1~경로의 maxOutputTokensMax 정수', () => {
    const at = (change: Partial<Draft['models'][number]>) =>
      modelErrors(pm, setModel(draftOf(pm), change))[0];
    expect(at({ temperature: '0' })!.temperature).toBeNull();
    expect(at({ temperature: '2' })!.temperature).toBeNull();
    expect(at({ temperature: '2.01' })!.temperature).toBe('range');
    expect(at({ temperature: '-0.1' })!.temperature).toBe('range');
    expect(at({ temperature: '가' })!.temperature).toBe('range');
    expect(at({ maxOutputTokens: '16000' })!.maxOutputTokens).toBeNull();
    expect(at({ maxOutputTokens: '16001' })!.maxOutputTokens).toBe('range');
    expect(at({ maxOutputTokens: '0' })!.maxOutputTokens).toBe('range');
    expect(at({ maxOutputTokens: '1.5' })!.maxOutputTokens).toBe('range');
    expect(
      modelErrors(
        pm,
        setModel(withRoute(pm, draftOf(pm), 0, 'fake-think'), {
          maxOutputTokens: '32000',
        }),
      )[0]!.maxOutputTokens,
    ).toBeNull();
  });
});

describe('bodyOf — 늘 넷, webSearch 읽은 값', () => {
  it('안 고친 칸도 넷 다(바탕 바이트), 고친 칸만 고친 값, 모델 다섯 칸', () => {
    const draft = setPrompt(
      setModel(draftOf(pm), { maxOutputTokens: '3000' }),
      1,
      { text: '지어낸 고친 글' },
    );
    const body = bodyOf(pm, draft, { title: '지어낸 판', memo: '' });
    expect(Object.keys(body)).toEqual([
      'title',
      'memo',
      'modelSettings',
      'prompts',
    ]);
    expect(body.modelSettings).toEqual({
      steps: [
        {
          key: 'judge',
          route: 'fake-mini',
          temperature: 0.2,
          maxOutputTokens: 3000,
          webSearch: false,
        },
      ],
    });
    expect(body.prompts.steps[0]!.prompts).toEqual(
      pm.promptGroups[0]!.prompts.map((one, index) => ({
        key: one.key,
        text: index === 1 ? '지어낸 고친 글' : one.text,
        memo: one.memo,
      })),
    );
  });

  it('webSearch 는 읽은 값 그대로(true 판이면 true), temperature null 경로는 null', () => {
    const searching = fakePromptModel('setting-13', {
      model: { webSearch: true },
    });
    const think = withRoute(searching, draftOf(searching), 0, 'fake-think');
    const step = bodyOf(searching, think, { title: '가', memo: '' })
      .modelSettings.steps[0]!;
    expect(step.webSearch).toBe(true);
    expect(step.temperature).toBeNull();
  });
});

describe('saveFormProblems · nextNumber', () => {
  it('이름: 서버 strip 뒤 1~40 코드포인트, 메모: 생 코드포인트 0~200', () => {
    expect(saveFormProblems('', '').title).toBe('empty');
    expect(saveFormProblems(` ${IDEOGRAPHIC}`, '').title).toBe('empty');
    expect(saveFormProblems('\u001c', '').title).toBeNull();
    expect(saveFormProblems('😀'.repeat(40), '').title).toBeNull();
    expect(saveFormProblems('😀'.repeat(41), '').title).toBe('over');
    expect(saveFormProblems('가', '😀'.repeat(200)).memo).toBeNull();
    expect(saveFormProblems('가', `${'나'.repeat(200)} `).memo).toBe('over');
  });

  it('번호 추정 = 실린 저장 판 번호의 최댓값 + 1(기본 판 빼고, 없으면 v1)', () => {
    const row = (number: string, kind: VersionRow['kind'] = 'saved') =>
      ({ number, kind }) as VersionRow;
    expect(nextNumber([row('v3'), row('v12'), row('v2')])).toBe('v13');
    expect(nextNumber([row('colab-2026-01-15-v1', 'default')])).toBe('v1');
    expect(nextNumber([])).toBe('v1');
  });
});

describe('promptErrors — 서버 셈(글 = 생 코드포인트, 메모 = Python strip 뒤)', () => {
  const at = (change: Partial<Draft['prompts'][number][number]>) =>
    promptErrors(pm, setPrompt(draftOf(pm), 1, change))[0]![1]!;

  it('바탕 그대로면 오류 0', () => {
    expect(promptErrors(pm, draftOf(pm)).flat()).toEqual(
      pm.promptGroups[0]!.prompts.map(() => ({ text: null, memo: null })),
    );
  });

  it('글: 4바이트 글자 8000 = 됨, 8001 = 넘침, \\x1c·공백만 = 빈 글', () => {
    expect(at({ text: '😀'.repeat(8000) }).text).toBeNull();
    expect(at({ text: '😀'.repeat(8001) }).text).toBe('over');
    expect(at({ text: '\u001c \n' }).text).toBe('empty');
    expect(at({ text: '\ufeff' }).text).toBeNull();
  });

  it('메모: strip 뒤 500 = 됨(뒤 공백은 안 셈), 501 = 넘침, 빈 메모는 됨', () => {
    expect(at({ memo: `${'가'.repeat(500)}   ` }).memo).toBeNull();
    expect(at({ memo: '가'.repeat(501) }).memo).toBe('over');
    expect(at({ memo: '' }).memo).toBeNull();
  });
});

describe('넓은 꼴 @3 — 모델 칸 key ≠ 묶음 key(AP1W)', () => {
  const wide = fakeWidePromptModel('setting-13');
  const setSlot = (
    draft: Draft,
    slot: number,
    change: Partial<Draft['models'][number]>,
  ): Draft => ({
    ...draft,
    models: draft.models.map((one, index) =>
      index === slot ? { ...one, ...change } : one,
    ),
  });

  it('bodyOf: modelSettings.steps = 모델 칸 차례(칸 key), prompts.steps = 묶음 차례(묶음 key, 칸 9·1·1·1·2)', () => {
    const body = bodyOf(wide, draftOf(wide), { title: '가', memo: '' });
    expect(body.modelSettings.steps.map((one) => one.key)).toEqual([
      'translate_ceo',
      'translate_other',
      'review',
    ]);
    expect(body.modelSettings.steps.map((one) => one.maxOutputTokens)).toEqual([
      2000, 3000, 1000,
    ]);
    expect(body.prompts.steps.map((one) => one.key)).toEqual([
      'translate',
      'polish',
      'editorial_qa',
      'review',
      'autofix',
    ]);
    expect(body.prompts.steps.map((one) => one.prompts.length)).toEqual([
      9, 1, 1, 1, 2,
    ]);
    expect(body.prompts.steps[4]!.prompts.map((one) => one.key)).toEqual([
      'autofix',
      'autofix_korean',
    ]);
  });

  it('withRoute: 그 칸 경로의 temperature 규칙 — 칸 1 받지 않는 경로 → null, 다시 받는 경로 → 그 칸 바탕 0.3 · 다른 칸 그대로', () => {
    const away = withRoute(wide, draftOf(wide), 1, 'fake-b2');
    expect(away.models[1]).toMatchObject({
      route: 'fake-b2',
      temperature: null,
    });
    const back = withRoute(wide, away, 1, 'fake-b1');
    expect(back.models[1]).toMatchObject({
      route: 'fake-b1',
      temperature: '0.3',
    });
    expect(back.models[0]).toEqual(draftOf(wide).models[0]);
    const review = withRoute(wide, draftOf(wide), 2, 'fake-c2');
    expect(review.models[2]).toMatchObject({
      route: 'fake-c2',
      temperature: null,
    });
  });

  it('modelErrors: 칸마다 그 칸 경로의 상한(8000 · 12000 · 4000)', () => {
    const over = (slot: number, tokens: string) =>
      modelErrors(
        wide,
        setSlot(draftOf(wide), slot, { maxOutputTokens: tokens }),
      )[slot]!.maxOutputTokens;
    expect(over(0, '8000')).toBeNull();
    expect(over(0, '8001')).toBe('range');
    expect(over(1, '12000')).toBeNull();
    expect(over(1, '12001')).toBe('range');
    expect(over(2, '4000')).toBeNull();
    expect(over(2, '4001')).toBe('range');
  });

  it('changes 모델 몫 = 고친 모델 칸 수(Q4 (나)): 칸 0·칸 1 → 2 · 칸 0 의 temperature·출력 상한 둘 → 1 · 되돌리면 0', () => {
    const two = setSlot(
      setSlot(draftOf(wide), 0, { maxOutputTokens: '2500' }),
      1,
      { temperature: '0.9' },
    );
    expect(changes(wide, two)).toMatchObject({ model: 2, total: 2 });
    expect(changedModels(wide, two)).toEqual([0, 1]);
    const one = setSlot(draftOf(wide), 0, {
      temperature: '0.9',
      maxOutputTokens: '2500',
    });
    expect(changes(wide, one)).toMatchObject({ model: 1, total: 1 });
    expect(
      changes(
        wide,
        setSlot(one, 0, { temperature: '0.3', maxOutputTokens: '2000' }),
      ),
    ).toMatchObject({ model: 0, total: 0 });
  });

  it('changes: 칸 1 출력 상한만 → 모델 고침 · total 1 / 묶음 4 칸 1 글 → prompts [{group 4, prompt 1}]', () => {
    const slot1 = changes(
      wide,
      setSlot(draftOf(wide), 1, { maxOutputTokens: '3500' }),
    );
    expect(slot1.model).toBeTruthy();
    expect(slot1.total).toBe(1);
    const base = draftOf(wide);
    const text = changes(wide, {
      ...base,
      prompts: base.prompts.map((group, g) =>
        group.map((one, p) =>
          g === 4 && p === 1 ? { ...one, text: '지어낸 고친 글' } : one,
        ),
      ),
    });
    expect(text.prompts).toEqual([{ group: 4, prompt: 1 }]);
    expect(text.total).toBe(1);
  });
});
