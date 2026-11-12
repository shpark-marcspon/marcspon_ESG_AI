// 그린워싱 AI 설정 실어댑터(밴드 AD2R ① — 발주서 §3 B): 진짜 createApi 에 가짜 서버(모킹한 fetch)를 물려 부른 method·경로·쿼리·본문을 정확히 단언한다.
//   어느 요청에도 companyId 가 없다. 읽기 실패(꼴 틀림·4xx·5xx·던짐)는 failed, 쓰기의 서버 거절은 rejected(CRITERIA_*·NAME_CONFLICT 만 code), 끊김은 failed.
//   AD2W ③: 새 판 저장은 본문 다섯 칸, 거절 code 는 AI_MODEL_*·AI_PROMPT_*·VALIDATION_ERROR 까지(서버 message·fields 와 함께).
import { describe, expect, it } from 'vitest';

import { createApi } from '../../../shared/api/index.ts';
import { CRITERION_IDS } from '../model/index.ts';
import {
  GREENWASH_SETTING_PAGE,
  createGreenwashSettingServerPort,
} from './index.ts';
import {
  FAKE_DEFAULT_TERMS,
  fakeDefaultSetting,
  fakeGreenwashSettingServer,
  fakeSettingList,
  fakeSettings,
  json,
  refusal,
} from './testing.ts';

const BASE = 'http://test.local/api';

function setup() {
  const server = fakeGreenwashSettingServer({ baseUrl: BASE });
  const port = createGreenwashSettingServerPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  return { server, port };
}

const keys = (server: ReturnType<typeof setup>['server']) =>
  server.calls.map((call) => `${call.method} ${call.path}`);
const queries = (server: ReturnType<typeof setup>['server']) =>
  server.calls.map((call) => Object.fromEntries(call.query));

const v2 = () => fakeSettings()[1]!;

/** 새 판 저장 입력(AD2W ③ — 본문 다섯 칸, 모델 설정·프롬프트는 지어낸 것). */
const MODEL_SETTINGS = {
  steps: [
    {
      key: 'judge',
      route: 'fake-mini',
      temperature: 0.2,
      maxOutputTokens: 2000,
      webSearch: false,
    },
  ],
};
const PROMPTS = {
  steps: [
    {
      key: 'judge',
      prompts: [{ key: 'eval', text: '지어낸 판정 글', memo: '지어낸 메모' }],
    },
  ],
};
const input = (rows = v2().criteria.rows) => ({
  criteria: { ...v2().criteria, rows },
  title: '지어낸 판 이름',
  memo: '지어낸 판 메모',
  modelSettings: MODEL_SETTINGS,
  prompts: PROMPTS,
  terms: v2().terms,
});

/** 지어낸 대상 단어(G2d — 앞뒤 공백·끈 것 하나). */
const TERMS = [
  { text: ' 지어낸 초록낱말 ', enabled: true },
  { text: '친환경', enabled: false },
];

describe('list — GET /ai-settings/greenwash', () => {
  it('쿼리가 정확히 limit 100·offset, 답은 서버 목록 그대로', async () => {
    const { server, port } = setup();
    const outcome = await port.list(0);
    expect(outcome).toEqual({
      kind: 'ok',
      list: fakeSettingList(fakeSettings()),
    });
    await port.list(100);
    expect(keys(server)).toEqual([
      'GET /ai-settings/greenwash',
      'GET /ai-settings/greenwash',
    ]);
    expect(queries(server)).toEqual([
      { limit: '100', offset: '0' },
      { limit: '100', offset: '100' },
    ]);
    expect(GREENWASH_SETTING_PAGE).toBe(100);
  });

  it('꼴 틀림(status 모름·applied.kind 모름·schemaVersion)·400·500·던짐은 failed', async () => {
    const good = fakeSettingList(fakeSettings());
    const bad = [
      { ...good, items: [{ ...good.items[0]!, status: 'draft' }] },
      { ...good, applied: { kind: 'other' } },
      { ...good, applied: { kind: 'saved' } },
      { ...good, schemaVersion: 'greenwash.ai-settings@1' },
      { ...good, items: [{ ...good.items[0]!, createdBy: { id: 1 } }] },
      { ...good, items: [{ ...good.items[0]!, title: 3 }] },
      { ...good, default: { ...good.default, title: undefined } },
    ];
    for (const body of bad) {
      const { server, port } = setup();
      server.override['GET /ai-settings/greenwash'] = () => json(200, body);
      expect(await port.list(0), JSON.stringify(body)).toEqual({
        kind: 'failed',
      });
    }
    for (const answer of [
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
      () => refusal(500, 'SERVER_ERROR'),
      () => Promise.reject(new TypeError('끊김')),
    ]) {
      const { server, port } = setup();
      server.override['GET /ai-settings/greenwash'] = answer;
      expect(await port.list(0)).toEqual({ kind: 'failed' });
    }
  });

  it('만든 사람 이름 null 은 받는다', async () => {
    const { port } = setup();
    const outcome = await port.list(0);
    expect(
      outcome.kind === 'ok' && outcome.list.items[2]!.createdBy.name,
    ).toBeNull();
  });

  it('판 이름 title 은 글·null(옛 판) 둘 다 받고, 목록 default 는 기본 판 이름', async () => {
    const { port } = setup();
    const outcome = await port.list(0);
    expect(
      outcome.kind === 'ok' && outcome.list.items.map((item) => item.title),
    ).toEqual(['지어낸 판 셋', '지어낸 판 둘', null]);
    expect(outcome.kind === 'ok' && outcome.list.default.title).toBe(
      '기본 설정',
    );
    const fallback = await port.getDefault();
    expect(fallback.kind === 'ok' && fallback.setting.title).toBe('기본 설정');
  });
});

describe('get — GET /ai-settings/greenwash/{id}', () => {
  it('경로에 숫자 id, 쿼리 없음, 판 하나', async () => {
    const { server, port } = setup();
    expect(await port.get('12')).toEqual({ kind: 'ok', setting: v2() });
    expect(keys(server)).toEqual(['GET /ai-settings/greenwash/12']);
    expect(queries(server)).toEqual([{}]);
  });

  it('양의 정수 글자가 아니면 요청 0 으로 failed', async () => {
    const { server, port } = setup();
    for (const id of ['012', '1.5', '', 'v3', 'default'])
      expect(await port.get(id), id).toEqual({ kind: 'failed' });
    expect(server.calls).toEqual([]);
  });

  it('꼴 틀림(rows 14줄·id 차례·status·계약 밖 category·verdict)·다른 id·404 는 failed', async () => {
    const good = v2();
    const bad = [
      {
        ...good,
        criteria: { ...good.criteria, rows: good.criteria.rows.slice(1) },
      },
      {
        ...good,
        criteria: {
          ...good.criteria,
          rows: [...good.criteria.rows].reverse(),
        },
      },
      {
        ...good,
        criteria: { ...good.criteria, schemaVersion: 'greenwash.criteria@2' },
      },
      { ...good, status: 'draft' },
      { ...good, id: 13 },
      {
        ...good,
        criteria: {
          ...good.criteria,
          rows: good.criteria.rows.map((row, index) =>
            index === 6 ? { ...row, category: 'weird' } : row,
          ),
        },
      },
      {
        ...good,
        criteria: {
          ...good.criteria,
          rows: good.criteria.rows.map((row, index) =>
            index === 6 ? { ...row, verdict: 'Low' } : row,
          ),
        },
      },
    ];
    for (const body of bad) {
      const { server, port } = setup();
      server.override['GET /ai-settings/greenwash/12'] = () => json(200, body);
      expect(await port.get('12')).toEqual({ kind: 'failed' });
    }
    const { port } = setup();
    expect(await port.get('99')).toEqual({ kind: 'failed' });
  });
});

describe('getDefault — GET /ai-settings/greenwash/default', () => {
  it('경로 정확히, 쿼리 없음, 기본 판', async () => {
    const { server, port } = setup();
    expect(await port.getDefault()).toEqual({
      kind: 'ok',
      setting: fakeDefaultSetting(),
    });
    expect(keys(server)).toEqual(['GET /ai-settings/greenwash/default']);
    expect(queries(server)).toEqual([{}]);
  });

  it('schemaVersion 이 다르면 failed', async () => {
    const { server, port } = setup();
    server.override['GET /ai-settings/greenwash/default'] = () =>
      json(200, { ...fakeDefaultSetting(), schemaVersion: 'x' });
    expect(await port.getDefault()).toEqual({ kind: 'failed' });
  });
});

describe('create — POST /ai-settings/greenwash', () => {
  it('본문 정확히 {title, criteria:{schemaVersion, version:<바탕 판>, rows 15줄}, memo, modelSettings, prompts}, 쿼리 없음 → 새 판', async () => {
    const { server, port } = setup();
    const base = v2().criteria;
    const rows = base.rows.map((row) =>
      row.id === 'high-2' ? { ...row, enabled: false } : row,
    );
    const outcome = await port.create(input(rows));
    expect(keys(server)).toEqual(['POST /ai-settings/greenwash']);
    expect(queries(server)).toEqual([{}]);
    expect(server.bodies('POST /ai-settings/greenwash')).toEqual([
      {
        title: '지어낸 판 이름',
        criteria: {
          schemaVersion: 'greenwash.criteria@1',
          version: 'v2',
          rows,
        },
        memo: '지어낸 판 메모',
        modelSettings: MODEL_SETTINGS,
        prompts: PROMPTS,
        terms: null,
      },
    ]);
    const [body] = server.bodies('POST /ai-settings/greenwash') as [
      { criteria: { rows: { id: string; terms: unknown }[] } },
    ];
    expect(body.criteria.rows.map((row) => row.id)).toEqual([...CRITERION_IDS]);
    expect(body.criteria.rows[0]!.terms).toEqual(base.rows[0]!.terms);
    expect(outcome.kind === 'ok' && outcome.setting.name).toBe('v4');
    expect(outcome.kind === 'ok' && outcome.setting.status).toBe('testing');
  });

  it('400 CRITERIA_* 는 rejected{code}, 409 NAME_CONFLICT 는 rejected{code}, 그 밖의 거절은 code null, 던짐·꼴 틀린 답은 failed', async () => {
    const said = (code: string) => ({
      kind: 'rejected',
      code,
      message: `지어낸-${code}`,
      fields: {},
    });
    const unknown = { kind: 'rejected', code: null, message: null, fields: {} };
    const cases = [
      [
        () => refusal(400, 'CRITERIA_TEXT_LENGTH'),
        said('CRITERIA_TEXT_LENGTH'),
      ],
      [() => refusal(409, 'NAME_CONFLICT'), said('NAME_CONFLICT')],
      [() => refusal(422, 'VALIDATION_ERROR'), said('VALIDATION_ERROR')],
      [() => refusal(400, 'AI_MODEL_FAKE_UNKNOWN'), unknown],
      [() => refusal(500, 'SERVER_ERROR'), unknown],
      [() => json(500, undefined), unknown],
      [() => Promise.reject(new TypeError('끊김')), { kind: 'failed' }],
      [() => json(201, { schemaVersion: 'x' }), { kind: 'failed' }],
    ] as const;
    for (const [answer, expected] of cases) {
      const { server, port } = setup();
      server.override['POST /ai-settings/greenwash'] = answer;
      expect(await port.create(input())).toEqual(expected);
    }
  });

  it('AD2W ③: 모델 설정 거절 AI_MODEL_* 아홉·프롬프트 글 거절 AI_PROMPT_* 여덟은 code·서버 message·fields 그대로(서버 code 이름)', async () => {
    const codes = [
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
      'TERMS_TEXT',
      'TERMS_DUPLICATE',
      'TERMS_COUNT',
      'TERMS_NONE_ENABLED',
    ];
    for (const code of codes) {
      const { server, port } = setup();
      const fields =
        code.startsWith('AI_PROMPT_') ?
          { 'prompts.steps.0.prompts.1.text': ['지어낸 칸 문장'] }
        : code.startsWith('TERMS_') ? { 'terms.1.text': ['지어낸 단어 문장'] }
        : null;
      server.override['POST /ai-settings/greenwash'] = () =>
        json(400, {
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
  });

  it('G2d: 대상 단어 목록은 계약 칸만 본문에 싣고, 답의 terms(서버 정규형)를 그대로 돌려준다 — null 은 null', async () => {
    const { server, port } = setup();
    const extra = { extra: 'x' } as Record<string, unknown>;
    const outcome = await port.create({
      ...input(),
      terms: TERMS.map((term) => ({ ...term, ...extra })),
    });
    const [body] = server.bodies('POST /ai-settings/greenwash') as [
      { terms: unknown },
    ];
    expect(body.terms).toEqual(TERMS);
    expect(outcome.kind === 'ok' && outcome.setting.schemaVersion).toBe(
      'greenwash.ai-setting@3',
    );
    expect(outcome.kind === 'ok' && outcome.setting.terms).toEqual([
      { text: '지어낸 초록낱말', enabled: true },
      { text: '친환경', enabled: false },
    ]);
    const plain = await port.create(input());
    expect(plain.kind === 'ok' && plain.setting.terms).toBeNull();
  });

  it('G2d: 답의 terms 꼴이 틀리거나 판 꼴이 @2 면 failed — 기본 판은 terms null 만', async () => {
    const answers = [
      { ...fakeSettings()[0]!, terms: 'x' },
      { ...fakeSettings()[0]!, terms: [{ text: '친환경', enabled: 1 }] },
      { ...fakeSettings()[0]!, terms: [{ text: 3, enabled: true }] },
      { ...fakeSettings()[0]!, schemaVersion: 'greenwash.ai-setting@2' },
    ];
    for (const answer of answers) {
      const { server, port } = setup();
      server.override['POST /ai-settings/greenwash'] = () => json(201, answer);
      expect(await port.create(input())).toEqual({ kind: 'failed' });
    }
    const { server, port } = setup();
    server.override['GET /ai-settings/greenwash/default'] = () =>
      json(200, { ...fakeDefaultSetting(), terms: [] });
    expect(await port.getDefault()).toEqual({ kind: 'failed' });
  });

  it('AD2W ③: 422 VALIDATION_ERROR 의 fields.title·fields.memo 는 그대로 싣는다', async () => {
    const { server, port } = setup();
    server.override['POST /ai-settings/greenwash'] = () =>
      json(422, {
        error: {
          code: 'VALIDATION_ERROR',
          message: '지어낸 꼴 문장',
          fields: { title: ['지어낸 이름 문장'], memo: ['지어낸 메모 문장'] },
          legacyCode: 'invalid_input',
        },
      });
    expect(await port.create(input())).toEqual({
      kind: 'rejected',
      code: 'VALIDATION_ERROR',
      message: '지어낸 꼴 문장',
      fields: { title: ['지어낸 이름 문장'], memo: ['지어낸 메모 문장'] },
    });
  });
});

describe('apply — PUT /ai-settings/greenwash/applied', () => {
  it('본문 정확히 {id: 숫자}, 기본 판은 {id: null}, 쿼리 없음', async () => {
    const { server, port } = setup();
    expect(await port.apply('13')).toEqual({ kind: 'ok' });
    expect(await port.apply(null)).toEqual({ kind: 'ok' });
    expect(keys(server)).toEqual([
      'PUT /ai-settings/greenwash/applied',
      'PUT /ai-settings/greenwash/applied',
    ]);
    expect(queries(server)).toEqual([{}, {}]);
    expect(server.bodies('PUT /ai-settings/greenwash/applied')).toEqual([
      { id: 13 },
      { id: null },
    ]);
    expect(server.appliedId).toBeNull();
  });

  it('id 가 양의 정수 글자가 아니면 요청 0, 404 는 rejected, 끊김은 failed', async () => {
    const { server, port } = setup();
    expect(await port.apply('v3')).toEqual({ kind: 'failed' });
    expect(await port.apply('')).toEqual({ kind: 'failed' });
    expect(server.calls).toEqual([]);
    expect(await port.apply('99')).toEqual({ kind: 'rejected', code: null });
    server.override['PUT /ai-settings/greenwash/applied'] = () =>
      Promise.reject(new TypeError('끊김'));
    expect(await port.apply('13')).toEqual({ kind: 'failed' });
  });
});

describe('defaultTerms — GET /greenwash/terms/default(AS3b ①)', () => {
  it('경로 정확히, 쿼리 없음 → 낱말 목록(서버 차례 그대로)', async () => {
    const { server, port } = setup();
    expect(await port.defaultTerms()).toEqual({
      kind: 'ok',
      terms: [...FAKE_DEFAULT_TERMS],
    });
    expect(keys(server)).toEqual(['GET /greenwash/terms/default']);
    expect(queries(server)).toEqual([{}]);
  });

  it('꼴 틀림(목록 아님·글 아닌 낱말)·5xx·끊김은 failed — 빈 목록으로 두지 않는다', async () => {
    const { server, port } = setup();
    server.override['GET /greenwash/terms/default'] = [
      () => json(200, { terms: '지어낸 말' }),
      () => json(200, { terms: ['지어낸 말', 3] }),
      () => json(200, {}),
      () => json(500, undefined),
      () => Promise.reject(new TypeError('끊김')),
    ];
    for (let i = 0; i < 5; i += 1)
      expect(await port.defaultTerms()).toEqual({ kind: 'failed' });
  });
});

it('어느 요청에도 companyId 가 없다', async () => {
  const { server, port } = setup();
  await port.list(0);
  await port.get('12');
  await port.getDefault();
  await port.create(input());
  await port.apply('12');
  await port.apply(null);
  await port.defaultTerms();
  expect(server.calls).toHaveLength(7);
  for (const call of server.calls) {
    expect(call.query.has('companyId')).toBe(false);
    expect(JSON.stringify(call.body ?? {})).not.toContain('companyId');
  }
});
