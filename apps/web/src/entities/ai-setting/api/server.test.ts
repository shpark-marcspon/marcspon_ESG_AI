// prompt-model 읽기 실어댑터(밴드 AD2W ②). 진짜 createApi + 통신 층 가짜(fakePromptModelServer)로 본다.
//   갈래: 200 꼴 맞음 ok · 409 AI_SETTING_UNUSABLE unusable(서버 문장) · 404 missing · 꼴 틀림(@1)·500·끊김 failed. 경로의 id·default, 숫자 아닌 열쇠는 요청 0.
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { createPromptModelReader, isPromptModel } from './server.ts';
import {
  fakePromptModel,
  fakePromptModelServer,
  fakeWidePromptModel,
  json,
  refusal,
} from './testing.ts';

const BASE = 'http://test.local/api';

function reader() {
  const server = fakePromptModelServer({ baseUrl: BASE });
  const read = createPromptModelReader({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
    module: 'greenwash',
  });
  return { server, read };
}

describe('createPromptModelReader', () => {
  it('저장 판은 GET /{id}/prompt-model, 기본 판은 /default/prompt-model — companyId 없음, 답은 꼴 그대로', async () => {
    const { server, read } = reader();
    const saved = await read('13');
    expect(saved).toEqual({ kind: 'ok', model: fakePromptModel('setting-13') });
    const base = await read('default');
    expect(base.kind === 'ok' && base.model.settingName).toBe(
      'colab-2026-01-15-v1',
    );
    expect(server.calls.map((call) => call.path)).toEqual([
      '/ai-settings/greenwash/13/prompt-model',
      '/ai-settings/greenwash/default/prompt-model',
    ]);
    for (const call of server.calls)
      expect(call.query.has('companyId')).toBe(false);
  });

  it('영문번역(밴드 TRA1): 같은 꼴로 /ai-settings/translation/{id}/prompt-model · /default/prompt-model — 그린워싱 경로 0', async () => {
    const server = fakePromptModelServer({
      baseUrl: BASE,
      module: 'translation',
    });
    const read = createPromptModelReader({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
      module: 'translation',
    });
    expect(await read('7')).toEqual({
      kind: 'ok',
      model: fakePromptModel('setting-7'),
    });
    expect((await read('default')).kind).toBe('ok');
    expect(await read('abc')).toEqual({ kind: 'failed' });
    expect(server.calls.map((call) => call.path)).toEqual([
      '/ai-settings/translation/7/prompt-model',
      '/ai-settings/translation/default/prompt-model',
    ]);
  });

  it('데이터 검증(밴드 DVA2): 같은 꼴로 /ai-settings/dataverify/{id}/prompt-model · /default/prompt-model — 그린워싱·영문번역 경로 0', async () => {
    const server = fakePromptModelServer({
      baseUrl: BASE,
      module: 'dataverify',
    });
    const read = createPromptModelReader({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
      module: 'dataverify',
    });
    expect(await read('13')).toEqual({
      kind: 'ok',
      model: fakePromptModel('setting-13'),
    });
    expect((await read('default')).kind).toBe('ok');
    expect(await read('abc')).toEqual({ kind: 'failed' });
    expect(server.calls.map((call) => call.path)).toEqual([
      '/ai-settings/dataverify/13/prompt-model',
      '/ai-settings/dataverify/default/prompt-model',
    ]);
    for (const call of server.calls)
      expect(call.query.has('companyId')).toBe(false);
  });

  it('중대성평가 IRO(밴드 IRA2): 같은 꼴로 /ai-settings/materiality/{id}/prompt-model · /default/prompt-model — 다른 모듈 경로 0', async () => {
    const server = fakePromptModelServer({
      baseUrl: BASE,
      module: 'materiality',
    });
    const read = createPromptModelReader({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
      module: 'materiality',
    });
    expect(await read('13')).toEqual({
      kind: 'ok',
      model: fakePromptModel('setting-13'),
    });
    expect((await read('default')).kind).toBe('ok');
    expect(await read('abc')).toEqual({ kind: 'failed' });
    expect(server.calls.map((call) => call.path)).toEqual([
      '/ai-settings/materiality/13/prompt-model',
      '/ai-settings/materiality/default/prompt-model',
    ]);
    for (const call of server.calls)
      expect(call.query.has('companyId')).toBe(false);
  });

  it('보고서 작성(밴드 RPA3): 같은 꼴로 /ai-settings/drafting/{id}/prompt-model · /default/prompt-model — 다른 모듈 경로 0', async () => {
    const server = fakePromptModelServer({
      baseUrl: BASE,
      module: 'drafting',
    });
    const read = createPromptModelReader({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
      module: 'drafting',
    });
    expect(await read('13')).toEqual({
      kind: 'ok',
      model: fakePromptModel('setting-13'),
    });
    expect((await read('default')).kind).toBe('ok');
    expect(await read('abc')).toEqual({ kind: 'failed' });
    expect(server.calls.map((call) => call.path)).toEqual([
      '/ai-settings/drafting/13/prompt-model',
      '/ai-settings/drafting/default/prompt-model',
    ]);
    for (const call of server.calls)
      expect(call.query.has('companyId')).toBe(false);
  });

  it('409 AI_SETTING_UNUSABLE → unusable(서버 문장 그대로) · 404 → missing', async () => {
    const { server, read } = reader();
    server.override['GET /ai-settings/greenwash/13/prompt-model'] = () =>
      refusal(409, 'AI_SETTING_UNUSABLE', '지어낸 쓸 수 없는 판 문장');
    server.override['GET /ai-settings/greenwash/12/prompt-model'] = () =>
      refusal(404, 'NOT_FOUND');
    expect(await read('13')).toEqual({
      kind: 'unusable',
      message: '지어낸 쓸 수 없는 판 문장',
    });
    expect(await read('12')).toEqual({ kind: 'missing' });
  });

  it.each([
    [
      '꼴 틀림(@1)',
      () =>
        json(200, {
          ...fakePromptModel('v1'),
          schemaVersion: 'ai.prompt-model@1',
        }),
    ],
    [
      '칸 빠짐(limits)',
      () => json(200, { ...fakePromptModel('v1'), limits: undefined }),
    ],
    ['다른 409', () => refusal(409, 'NAME_CONFLICT')],
    ['500', () => refusal(500, 'SERVER_ERROR')],
    ['끊김', () => Promise.reject(new TypeError('끊김'))],
  ])('%s → failed', async (_, answer) => {
    const { server, read } = reader();
    server.override['GET /ai-settings/greenwash/13/prompt-model'] = answer;
    expect(await read('13')).toEqual({ kind: 'failed' });
  });

  it.each(['0', '013', 'abc', '', '9007199254740993'])(
    '숫자 아닌 열쇠 %j → 요청 0 으로 failed',
    async (key) => {
      const { server, read } = reader();
      expect(await read(key)).toEqual({ kind: 'failed' });
      expect(server.calls).toEqual([]);
    },
  );

  it('isPromptModel: 칸 하나라도 꼴이 틀리면 거짓(값 배열의 글 아님·경로 능력 빠짐·칸 outputKept 빠짐)', () => {
    const good = fakePromptModel('v1');
    expect(isPromptModel(good)).toBe(true);
    const slot = good.models[0]!;
    const group = good.promptGroups[0]!;
    for (const bad of [
      {
        ...good,
        fixed: [
          { ...good.fixed[0]!, items: [{ key: 'a', label: 'b', value: [1] }] },
        ],
      },
      {
        ...good,
        models: [
          {
            ...slot,
            routeChoices: [
              { ...slot.routeChoices[0]!, acceptsTemperature: undefined },
            ],
          },
        ],
      },
      {
        ...good,
        promptGroups: [
          {
            ...group,
            prompts: [{ ...group.prompts[0]!, outputKept: undefined }],
          },
        ],
      },
      { ...good, editable: { model: true } },
    ])
      expect(isPromptModel(bad)).toBe(false);
  });

  it('isPromptModel @3: @2 머리·빈 모델 칸·빈 묶음·빈 경로·빈 칸·unavailableRoutes/modelSlots 빠짐이나 글 아님 → 거짓, 넓은 꼴은 참', () => {
    const good = fakePromptModel('v1');
    const slot = good.models[0]!;
    const group = good.promptGroups[0]!;
    expect(isPromptModel(fakeWidePromptModel('v1'))).toBe(true);
    const head = { ...good, models: undefined, promptGroups: undefined };
    for (const [name, bad] of [
      [
        '@2 꼴(단계 목록)',
        {
          ...head,
          schemaVersion: 'ai.prompt-model@2',
          steps: [{ ...slot, prompts: group.prompts }],
        },
      ],
      ['@2 머리', { ...good, schemaVersion: 'ai.prompt-model@2' }],
      ['모델 칸 0', { ...good, models: [] }],
      ['묶음 0', { ...good, promptGroups: [] }],
      ['경로 0', { ...good, models: [{ ...slot, routeChoices: [] }] }],
      ['칸 0', { ...good, promptGroups: [{ ...group, prompts: [] }] }],
      [
        'unavailableRoutes 빠짐',
        { ...good, models: [{ ...slot, unavailableRoutes: undefined }] },
      ],
      [
        'unavailableRoutes 글 아님',
        { ...good, models: [{ ...slot, unavailableRoutes: [1] }] },
      ],
      [
        'modelSlots 빠짐',
        { ...good, promptGroups: [{ ...group, modelSlots: undefined }] },
      ],
      [
        'modelSlots 글 아님',
        { ...good, promptGroups: [{ ...group, modelSlots: [null] }] },
      ],
    ] as const)
      expect(isPromptModel(bad), name).toBe(false);
  });

  it('isPromptModel: 모델 칸 key 겹침·묶음 key 겹침 → 거짓, 지금 가짜(judge 하나·넓은 꼴)는 참 (MS1W ④)', () => {
    const good = fakePromptModel('v1');
    const wide = fakeWidePromptModel('v1');
    expect(isPromptModel(good)).toBe(true);
    expect(isPromptModel(wide)).toBe(true);
    const slot = good.models[0]!;
    const group = good.promptGroups[0]!;
    expect(
      isPromptModel({ ...good, models: [slot, { ...slot, label: '둘째' }] }),
      '모델 칸 key 겹침',
    ).toBe(false);
    expect(
      isPromptModel({
        ...good,
        promptGroups: [group, { ...group, label: '둘째' }],
      }),
      '묶음 key 겹침',
    ).toBe(false);
    expect(
      isPromptModel({
        ...wide,
        models: [...wide.models, { ...wide.models[0]!, label: '끝' }],
      }),
      '넓은 꼴에 모델 칸 key 겹침',
    ).toBe(false);
  });

  it('@2 답(단계 목록) → failed', async () => {
    const { server, read } = reader();
    const { models, promptGroups, ...head } = fakePromptModel('setting-13');
    server.override['GET /ai-settings/greenwash/13/prompt-model'] = () =>
      json(200, {
        ...head,
        schemaVersion: 'ai.prompt-model@2',
        steps: [{ ...models[0]!, prompts: promptGroups[0]!.prompts }],
      });
    expect(await read('13')).toEqual({ kind: 'failed' });
  });
});
