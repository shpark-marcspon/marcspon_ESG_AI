// 원고작성 AI 설정 실어댑터(밴드 RPA3 — 발주서 §3-1-1): 진짜 createApi 에 가짜 서버(모킹한 fetch)를 물려 부른 method·경로·쿼리·본문을 정확히 단언한다.
//   어느 요청에도 companyId 가 없다. 읽기 실패(꼴 틀림·5xx·던짐)는 failed, 새 판 저장의 서버 거절은 rejected(CREATE_CODES 만 code·서버 message·fields), 끊김은 failed.
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { CREATE_CODES } from '../model/index.ts';
import {
  DRAFTING_SETTING_PAGE,
  createDraftingSettingServerPort,
} from './index.ts';
import {
  fakeDraftingSettingServer,
  fakeSettingList,
  fakeSettings,
  json,
  refusal,
} from './testing.ts';

const BASE = 'http://test.local/api';

function setup() {
  const server = fakeDraftingSettingServer({ baseUrl: BASE });
  const port = createDraftingSettingServerPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  return { server, port };
}

const keys = (server: ReturnType<typeof setup>['server']) =>
  server.calls.map((call) => `${call.method} ${call.path}`);

/** 새 판 저장 입력(본문 넷 — 모델 설정·프롬프트는 지어낸 것). */
const input = () => ({
  title: '지어낸 판 이름',
  memo: '지어낸 판 메모',
  modelSettings: {
    steps: [
      {
        key: 'map',
        route: 'fake-route-a',
        temperature: 0,
        maxOutputTokens: 4000,
        webSearch: false,
      },
      {
        key: 'draft',
        route: 'fake-route-b',
        temperature: 0.3,
        maxOutputTokens: 3000,
        webSearch: false,
      },
    ],
  },
  prompts: {
    steps: [
      {
        key: 'draft',
        prompts: [
          {
            key: 'draft_system',
            text: '지어낸 지시 글',
            memo: '지어낸 메모',
          },
          {
            key: 'draft_user',
            text: '지어낸 입력 글 {제목 경로} {요구 내용} {페이지 글}',
            memo: '',
          },
        ],
      },
    ],
  },
});

describe('list — GET /ai-settings/drafting', () => {
  it('쿼리가 정확히 limit 100·offset, companyId 없음, 답은 서버 목록 그대로', async () => {
    const { server, port } = setup();
    const outcome = await port.list(0);
    expect(DRAFTING_SETTING_PAGE).toBe(100);
    expect(keys(server)).toEqual(['GET /ai-settings/drafting']);
    expect(Object.fromEntries(server.calls[0]!.query)).toEqual({
      limit: '100',
      offset: '0',
    });
    expect(outcome).toEqual({
      kind: 'ok',
      list: fakeSettingList(fakeSettings(), { kind: 'saved', id: 11 }),
    });
    await port.list(100);
    expect(server.calls[1]!.query.get('offset')).toBe('100');
  });

  it.each([
    ['다른 schemaVersion', { schemaVersion: 'greenwash.ai-settings@2' }],
    ['title null 인 줄', { items: [{ ...fakeSettings()[0], title: null }] }],
    ['applied 꼴 틀림', { applied: { kind: 'saved' } }],
    ['total 음수', { total: -1 }],
  ])('꼴 틀림(%s) → failed', async (_, change) => {
    const { server, port } = setup();
    server.override['GET /ai-settings/drafting'] = () =>
      json(200, {
        ...fakeSettingList(fakeSettings(), { kind: 'default' }),
        ...change,
      });
    expect(await port.list(0)).toEqual({ kind: 'failed' });
  });

  it.each([
    ['500', () => refusal(500, 'SERVER_ERROR')],
    ['403', () => refusal(403, 'FORBIDDEN')],
    [
      '끊김',
      () => {
        throw new TypeError('끊김');
      },
    ],
  ])('%s → failed', async (_, answer) => {
    const { server, port } = setup();
    server.override['GET /ai-settings/drafting'] = answer;
    expect(await port.list(0)).toEqual({ kind: 'failed' });
  });
});

describe('apply — PUT /ai-settings/drafting/applied', () => {
  it('저장 판 열쇠 → 본문 {id:12}, null → {id:null}, companyId 없음', async () => {
    const { server, port } = setup();
    expect(await port.apply('12')).toEqual({ kind: 'ok' });
    expect(await port.apply(null)).toEqual({ kind: 'ok' });
    expect(keys(server)).toEqual([
      'PUT /ai-settings/drafting/applied',
      'PUT /ai-settings/drafting/applied',
    ]);
    expect(server.bodies('PUT /ai-settings/drafting/applied')).toEqual([
      { id: 12 },
      { id: null },
    ]);
    for (const call of server.calls)
      expect(call.query.has('companyId')).toBe(false);
  });

  it('숫자 아닌 열쇠 → 요청 0 으로 failed · 서버 거절(409·404) → rejected · 끊김 → failed', async () => {
    const { server, port } = setup();
    expect(await port.apply('abc')).toEqual({ kind: 'failed' });
    expect(server.calls).toHaveLength(0);
    server.override['PUT /ai-settings/drafting/applied'] = [
      () => refusal(409, 'AI_SETTING_APPLY_CONFLICT'),
      () => refusal(404, 'NOT_FOUND'),
      () => {
        throw new TypeError('끊김');
      },
    ];
    expect(await port.apply('12')).toEqual({ kind: 'rejected' });
    expect(await port.apply('99')).toEqual({ kind: 'rejected' });
    expect(await port.apply('12')).toEqual({ kind: 'failed' });
  });
});

describe('create — POST /ai-settings/drafting', () => {
  it('본문은 정확히 {title, memo, modelSettings, prompts} — 다른 칸·companyId 0, 201 → 새 판', async () => {
    const { server, port } = setup();
    const extra = { ...input(), companyId: 1, criteria: null } as ReturnType<
      typeof input
    >;
    const outcome = await port.create(extra);
    expect(keys(server)).toEqual(['POST /ai-settings/drafting']);
    expect(server.bodies('POST /ai-settings/drafting')).toEqual([input()]);
    expect(server.calls[0]!.query.has('companyId')).toBe(false);
    expect(outcome.kind === 'ok' && outcome.setting).toMatchObject({
      id: 13,
      name: 'v3',
      title: '지어낸 판 이름',
      status: 'testing',
    });
  });

  it('알아본 거절은 code·서버 message·fields 그대로(CREATE_CODES 각 하나), 그 밖 거절은 code·message null', async () => {
    expect(CREATE_CODES).toHaveLength(20);
    for (const code of CREATE_CODES) {
      const { server, port } = setup();
      const fields =
        code.startsWith('AI_PROMPT_') ?
          { 'prompts.steps.0.prompts.0.text': ['지어낸 칸 문장'] }
        : null;
      server.override['POST /ai-settings/drafting'] = () =>
        json(code === 'VALIDATION_ERROR' ? 422 : 400, {
          error: {
            code,
            message: '지어낸 서버 문장',
            fields,
            legacyCode: code.toLowerCase(),
          },
        });
      expect(await port.create(input()), code).toEqual({
        kind: 'rejected',
        code,
        message: '지어낸 서버 문장',
        fields: fields ?? {},
      });
    }
    for (const code of [
      'CRITERIA_SHAPE',
      'TERMS_COUNT',
      'FORBIDDEN',
      'AI_SETTING_UNUSABLE',
    ]) {
      const { server, port } = setup();
      server.override['POST /ai-settings/drafting'] = () => refusal(400, code);
      expect(await port.create(input()), code).toEqual({
        kind: 'rejected',
        code: null,
        message: null,
        fields: {},
      });
    }
  });

  it('자리 지움 400 AI_PROMPT_PLACEHOLDER_MISSING → code·서버 문장·fields 경로 그대로(칸 오류로 풀리게)', async () => {
    const { server, port } = setup();
    const fields = {
      'prompts.steps.1.prompts.1.text': ['지어낸 자리 문장 {페이지 글}'],
    };
    server.override['POST /ai-settings/drafting'] = () =>
      json(400, {
        error: {
          code: 'AI_PROMPT_PLACEHOLDER_MISSING',
          message: '지어낸 자리 문장 {페이지 글}',
          fields,
          legacyCode: 'ai_prompt_placeholder_missing',
        },
      });
    expect(await port.create(input())).toEqual({
      kind: 'rejected',
      code: 'AI_PROMPT_PLACEHOLDER_MISSING',
      message: '지어낸 자리 문장 {페이지 글}',
      fields,
    });
  });

  it.each([['AI_MODEL_TEMPERATURE_RANGE', null]])(
    '%s(temperature null — 서버 accept_model) → code·서버 문장·fields 그대로',
    async (code, fields) => {
      const { server, port } = setup();
      server.override['POST /ai-settings/drafting'] = () =>
        json(400, {
          error: {
            code,
            message: '지어낸 서버 문장',
            fields,
            legacyCode: code.toLowerCase(),
          },
        });
      expect(await port.create(input())).toEqual({
        kind: 'rejected',
        code,
        message: '지어낸 서버 문장',
        fields: fields ?? {},
      });
    },
  );

  it('끊김·꼴 틀린 답 → failed', async () => {
    const { server, port } = setup();
    server.override['POST /ai-settings/drafting'] = [
      () => {
        throw new TypeError('끊김');
      },
      () => json(201, { ...fakeSettings()[0], schemaVersion: 'x' }),
    ];
    expect(await port.create(input())).toEqual({ kind: 'failed' });
    expect(await port.create(input())).toEqual({ kind: 'failed' });
  });
});
