// AD-02 모듈 줄(밴드 AD2W ①②, 새 판 저장 ③). 그린워싱 줄 = 그린워싱 실어댑터·공통 prompt-model 어댑터를 슬롯 꼴로 감싼 것 —
// 진짜 createApi + 통신 층 가짜 둘(그린워싱 AI 설정 서버 · prompt-model 서버)로 본다.
// AS3b ①: 대상 단어 모듈 초안 슬롯(바탕 몫 load · key 짝)·create 의 셋째 인자(고친 목록 / null·undefined 면 바탕 terms 그대로)·모듈 글 출처(K9).
import { describe, expect, it } from 'vitest';

import { ACCOUNT_TEXT } from '../../entities/account/config/text.ts';
import {
  fakePromptModel,
  fakePromptModelServer,
} from '../../entities/ai-setting/api/testing.ts';
import { AI_SETTING_TEXT } from '../../entities/ai-setting/config/text.ts';
import { AUDIT_TEXT } from '../../entities/audit-log/config/text.ts';
import {
  fakeSettingList as fakeDataverifySettingList,
  fakeDataverifySettingServer,
  fakeSettings as fakeDataverifySettings,
} from '../../entities/dataverify-setting/api/testing.ts';
import { DATAVERIFY_SETTING_TEXT } from '../../entities/dataverify-setting/config/text.ts';
import {
  fakeSettingList as fakeDraftingSettingList,
  fakeDraftingSettingServer,
  fakeSettings as fakeDraftingSettings,
} from '../../entities/drafting-setting/api/testing.ts';
import { DRAFTING_SETTING_TEXT } from '../../entities/drafting-setting/config/text.ts';
import {
  FAKE_DEFAULT_TERMS,
  fakeDefaultSetting,
  fakeGreenwashSettingServer,
  fakeSettingList,
  fakeSettings,
  json,
} from '../../entities/greenwash-setting/api/testing.ts';
import { GREENWASH_SETTING_TEXT } from '../../entities/greenwash-setting/config/text.ts';
import {
  fakeSettingList as fakeMaterialitySettingList,
  fakeMaterialitySettingServer,
  fakeSettings as fakeMaterialitySettings,
} from '../../entities/materiality-setting/api/testing.ts';
import { MATERIALITY_SETTING_TEXT } from '../../entities/materiality-setting/config/text.ts';
import { materialityPromptNote } from '../../entities/materiality-setting/ui/index.ts';
import {
  fakeSettingList as fakeTranslationSettingList,
  fakeTranslationSettingServer,
  fakeSettings as fakeTranslationSettings,
} from '../../entities/translation-setting/api/testing.ts';
import { TRANSLATION_SETTING_TEXT } from '../../entities/translation-setting/config/text.ts';
import { createApi } from '../../shared/api/index.ts';
import {
  aiSettingModules,
  dataverifyModule,
  dataverifyPage,
  draftingModule,
  draftingPage,
  draftingPromptModel,
  greenwashModule,
  materialityModule,
  materialityPage,
  materialityPromptModel,
  translationModule,
  translationPage,
  translationPromptModel,
} from './ai-setting-modules.ts';

const BASE = 'http://test.local/api';

function setup() {
  const settings = fakeGreenwashSettingServer({ baseUrl: BASE });
  const promptModels = fakePromptModelServer({ baseUrl: BASE });
  const api = createApi({
    baseUrl: BASE,
    fetch: (request: Request) =>
      promptModels.handles(request) ?
        promptModels.send(request)
      : settings.send(request),
  });
  return { settings, promptModels, module: greenwashModule(api) };
}

describe('그린워싱 모듈 줄', () => {
  it('목록은 다섯 — 그린워싱(이름·id)이 먼저(영문번역은 밴드 TRA1, 데이터 검증은 밴드 DVA2, 중대성평가 IRO 는 밴드 IRA2, 보고서 작성은 밴드 RPA3 — 끝), 구성 줄은 대상 단어(모듈 초안 — 꼬리는 슬롯) · 고정 규칙(GREENWASH_SETTING_TEXT.fixedRules 줄 글)', () => {
    const modules = aiSettingModules(createApi({ baseUrl: BASE }));
    expect(modules.map((one) => [one.id, one.name])).toEqual([
      ['greenwash', '그린워싱'],
      ['translation', '영문번역'],
      ['dataverify', '데이터 검증'],
      ['materiality', '중대성평가 IRO'],
      ['drafting', '보고서 작성'],
    ]);
    expect(modules[0]!.components).toEqual([
      {
        key: 'terms',
        label: '대상 단어',
        sum: '',
        body: { kind: 'draft' },
      },
      {
        key: 'codeRules',
        label: AI_SETTING_TEXT.codeRules.label,
        sum: AI_SETTING_TEXT.codeRules.sum,
        body: {
          kind: 'lines',
          title: GREENWASH_SETTING_TEXT.module.codeRules.title,
          lines: GREENWASH_SETTING_TEXT.fixedRules,
          foot: GREENWASH_SETTING_TEXT.module.codeRules.foot,
        },
      },
    ]);
  });

  it('list: 저장 판 줄(번호·이름 null·상태·만든 때·만든 사람·메모)과 기본 판 줄(서버 default.title), 적용 판은 상태로 접힘', async () => {
    const { module, settings } = setup();
    const outcome = await module.port.list(0);
    expect(outcome.kind).toBe('ok');
    if (outcome.kind !== 'ok') return;
    expect(outcome.page.total).toBe(3);
    expect(
      outcome.page.rows.map((row) => [
        row.key,
        row.number,
        row.title,
        row.status,
        row.author,
      ]),
    ).toEqual([
      ['13', 'v3', '지어낸 판 셋', 'testing', '지어낸 관리자'],
      ['12', 'v2', '지어낸 판 둘', 'applied', '지어낸 관리자'],
      ['11', 'v1', null, 'past', null],
    ]);
    expect(outcome.page.rows[0]).toMatchObject({
      kind: 'saved',
      createdAt: '2026-10-19T11:40:00+09:00',
      memo: '지어낸 메모 셋',
    });
    expect(outcome.page.base).toEqual({
      key: 'default',
      kind: 'default',
      number: 'colab-2026-01-15-v1',
      title: '기본 설정',
      status: 'default',
      createdAt: null,
      author: null,
      memo: '',
    });
    expect(
      settings.calls.map((call) => Object.fromEntries(call.query)),
    ).toEqual([{ limit: '100', offset: '0' }]);
  });

  it('list: 기본 판이 적용 중이면 기본 판 줄 상태 applied · 실패는 failed', async () => {
    const { module, settings } = setup();
    settings.override['GET /ai-settings/greenwash'] = [
      () => json(200, fakeSettingList([], { kind: 'default' })),
      () => json(500, { error: { code: 'X', message: 'x', fields: null } }),
    ];
    const first = await module.port.list(0);
    expect(first.kind === 'ok' && first.page.base.status).toBe('applied');
    expect(await module.port.list(0)).toEqual({ kind: 'failed' });
  });

  it('apply: 저장 판 열쇠 → PUT {id:13}, null → {id:null}, 거절 → failed', async () => {
    const { module, settings } = setup();
    expect(await module.port.apply('13')).toEqual({ kind: 'ok' });
    expect(await module.port.apply(null)).toEqual({ kind: 'ok' });
    expect(await module.port.apply('99')).toEqual({ kind: 'failed' });
    expect(settings.bodies('PUT /ai-settings/greenwash/applied')).toEqual([
      { id: 13 },
      { id: null },
      { id: 99 },
    ]);
  });

  it('promptModel: 공통 읽기 어댑터 — 저장 판 /13/prompt-model · 기본 판 /default/prompt-model, 그린워싱 서버는 부르지 않는다', async () => {
    const { module, settings, promptModels } = setup();
    expect((await module.port.promptModel('13')).kind).toBe('ok');
    expect((await module.port.promptModel('default')).kind).toBe('ok');
    expect(promptModels.calls.map((call) => call.path)).toEqual([
      '/ai-settings/greenwash/13/prompt-model',
      '/ai-settings/greenwash/default/prompt-model',
    ]);
    expect(settings.calls).toEqual([]);
  });

  describe('create: 바탕 판 기준표 한 번 읽고(Q4) POST 한 번 — 본문 다섯 칸', () => {
    const body = {
      title: '지어낸 새 판',
      memo: '지어낸 판 메모',
      modelSettings: {
        steps: [
          {
            key: 'judge',
            route: 'fake-mini',
            temperature: 0.2,
            maxOutputTokens: 3000,
            webSearch: false,
          },
        ],
      },
      prompts: {
        steps: [
          {
            key: 'judge',
            prompts: [{ key: 'eval', text: '지어낸 판정 글', memo: '' }],
          },
        ],
      },
    };
    const keys = (settings: ReturnType<typeof setup>['settings']) =>
      settings.calls.map((call) => `${call.method} ${call.path}`);

    it('저장 판 바탕: GET /13 → POST 한 번(criteria·terms = 13 의 기준표·대상 단어 그대로 · title·memo·modelSettings·prompts) → 새 판 열쇠·번호', async () => {
      const { module, settings, promptModels } = setup();
      const outcome = await module.port.create('13', body);
      expect(keys(settings)).toEqual([
        'GET /ai-settings/greenwash/13',
        'POST /ai-settings/greenwash',
      ]);
      const v3 = fakeSettings().find((one) => one.id === 13)!;
      expect(v3.terms).not.toBeNull(); // 분모: 바탕 판에 단어 목록이 있다
      expect(settings.bodies('POST /ai-settings/greenwash')).toEqual([
        {
          title: body.title,
          criteria: v3.criteria,
          memo: body.memo,
          modelSettings: body.modelSettings,
          prompts: body.prompts,
          terms: v3.terms,
        },
      ]);
      expect(outcome).toEqual({ kind: 'ok', key: '14', number: 'v4' });
      expect(promptModels.calls).toEqual([]);
    });

    it('기본 판 바탕: GET /default 의 기준표', async () => {
      const { module, settings } = setup();
      await module.port.create('default', body);
      expect(keys(settings)).toEqual([
        'GET /ai-settings/greenwash/default',
        'POST /ai-settings/greenwash',
      ]);
      const [sent] = settings.bodies('POST /ai-settings/greenwash') as [
        { criteria: unknown; terms: unknown },
      ];
      expect(sent.criteria).toEqual(fakeDefaultSetting().criteria);
      expect(sent.terms).toBeNull();
    });

    it('G2d: 단어 칸 없는 저장 판(12) 바탕이면 terms null 그대로 — 복제가 단어를 잃거나 지어내지 않는다', async () => {
      const { module, settings } = setup();
      await module.port.create('12', body);
      const [sent] = settings.bodies('POST /ai-settings/greenwash') as [
        { terms: unknown },
      ];
      expect(fakeSettings().find((one) => one.id === 12)!.terms).toBeNull();
      expect(sent.terms).toBeNull();
    });

    it('바탕 판 읽기 실패 → failed, POST 0', async () => {
      const { module, settings } = setup();
      settings.override['GET /ai-settings/greenwash/13'] = () =>
        json(500, undefined);
      expect(await module.port.create('13', body)).toEqual({
        kind: 'failed',
      });
      expect(keys(settings)).toEqual(['GET /ai-settings/greenwash/13']);
    });

    it('거절은 code·서버 문장·fields 그대로, 끊김은 failed', async () => {
      const { module, settings } = setup();
      settings.override['POST /ai-settings/greenwash'] = [
        () =>
          json(400, {
            error: {
              code: 'AI_PROMPT_TEXT_EMPTY',
              message: '지어낸 빈 글 문장',
              fields: {
                'prompts.steps.0.prompts.0.text': ['지어낸 빈 글 문장'],
              },
              legacyCode: 'ai_prompt_text_empty',
            },
          }),
        () => Promise.reject(new TypeError('끊김')),
      ];
      expect(await module.port.create('13', body)).toEqual({
        kind: 'rejected',
        code: 'AI_PROMPT_TEXT_EMPTY',
        message: '지어낸 빈 글 문장',
        fields: { 'prompts.steps.0.prompts.0.text': ['지어낸 빈 글 문장'] },
      });
      expect(await module.port.create('13', body)).toEqual({
        kind: 'failed',
      });
    });
  });

  it('모델 카드 곁 글은 모듈 선언 — 그린워싱 글 표(AS3b K9, AP1W Q1 (가)). 셈 줄 이음은 없다(338 A10)', () => {
    expect(setup().module.modelNote).toBe(
      GREENWASH_SETTING_TEXT.module.modelNote,
    );
    expect('saveRule' in setup().module).toBe(false);
  });

  it('AS3b ② 처리 흐름 띠는 모듈 선언(flowSlot) — 셋째 열 대신', () => {
    expect(typeof setup().module.flow).toBe('function');
  });

  describe('AS3b ① create 셋째 인자(모듈 초안 — K4)', () => {
    const body = {
      title: '지어낸 새 판',
      memo: '',
      modelSettings: { steps: [] },
      prompts: { steps: [] },
    };
    const sentTerms = (settings: ReturnType<typeof setup>['settings']) =>
      (
        settings.bodies('POST /ai-settings/greenwash') as { terms: unknown }[]
      ).map((one) => one.terms);

    it('null·undefined(안 고침·복제) → 바탕 판 terms 그대로 — 목록은 목록, null 은 null', async () => {
      const { module, settings } = setup();
      await module.port.create('13', body, null);
      await module.port.create('13', body, undefined);
      await module.port.create('12', body, null);
      await module.port.create('default', body, undefined);
      const v3 = fakeSettings().find((one) => one.id === 13)!.terms;
      expect(sentTerms(settings)).toEqual([v3, v3, null, null]);
    });

    it('고친 목록 → 그 목록 전체(차례 그대로·trim 한 글), 바탕 null 에서 고쳤으면 null 로 되돌리지 않는다', async () => {
      const { module, settings } = setup();
      const draft = [
        { text: ' 지어낸 기본말 하나 ', enabled: false },
        { text: '지어낸 새말', enabled: true },
      ];
      await module.port.create('12', body, draft);
      expect(sentTerms(settings)).toEqual([
        [
          { text: '지어낸 기본말 하나', enabled: false },
          { text: '지어낸 새말', enabled: true },
        ],
      ]);
    });

    it('바탕 판 읽기 실패면 모듈 초안이 있어도 POST 0', async () => {
      const { module, settings } = setup();
      settings.override['GET /ai-settings/greenwash/12'] = () =>
        json(500, undefined);
      expect(
        await module.port.create('12', body, [
          { text: '지어낸 새말', enabled: true },
        ]),
      ).toEqual({ kind: 'failed' });
      expect(settings.count('POST /ai-settings/greenwash')).toBe(0);
    });
  });

  describe('AS3b ① 대상 단어 슬롯 — 바탕 몫 load·key 짝', () => {
    it('슬롯 key 는 구성 줄 terms(body draft)와 짝 — 늘 같은 key', () => {
      const { module } = setup();
      const line = module.components.find((one) => one.body.kind === 'draft');
      expect(module.draft?.key).toBe('terms');
      expect(line?.key).toBe(module.draft?.key);
      expect(setup().module.draft?.key).toBe(module.draft?.key);
    });

    it('기본 판 → GET /default 뒤 /greenwash/terms/default 낱말을 다 켬', async () => {
      const { module, settings } = setup();
      expect(await module.draft!.load('default')).toEqual({
        kind: 'ok',
        base: FAKE_DEFAULT_TERMS.map((text) => ({ text, enabled: true })),
      });
      expect(settings.calls.map((call) => call.path)).toEqual([
        '/ai-settings/greenwash/default',
        '/greenwash/terms/default',
      ]);
    });

    it('저장 판 terms null → 기본 단어 목록, 목록 → 그대로(기본 단어 읽기 0)', async () => {
      const { module, settings } = setup();
      const v2 = await module.draft!.load('12');
      expect(v2).toEqual({
        kind: 'ok',
        base: FAKE_DEFAULT_TERMS.map((text) => ({ text, enabled: true })),
      });
      const v3 = await module.draft!.load('13');
      expect(v3).toEqual({
        kind: 'ok',
        base: fakeSettings().find((one) => one.id === 13)!.terms,
      });
      expect(settings.calls.map((call) => call.path)).toEqual([
        '/ai-settings/greenwash/12',
        '/greenwash/terms/default',
        '/ai-settings/greenwash/13',
      ]);
    });

    it('슬롯 배선: count·changed·sum(전체 수)·blocked·refusal 이 대상 단어 함수와 글 표로 이어진다', () => {
      const slot = setup().module.draft!;
      const base = [
        { text: '지어낸 하나', enabled: true },
        { text: '지어낸 둘', enabled: true },
        { text: '지어낸 셋', enabled: false },
      ];
      const draft = [
        { text: '지어낸 둘', enabled: false },
        { text: '지어낸 셋', enabled: false },
        { text: '지어낸 넷', enabled: true },
      ];
      expect(slot.count(base, base)).toBe(0);
      expect(slot.count(base, draft)).toBe(3);
      expect(slot.changed(base, draft)).toEqual([
        '대상 단어 1개 추가 · 1개 삭제 · 1개 사용 바꿈',
      ]);
      expect(slot.changed(base, base)).toEqual([]);
      expect(slot.sum(base, base)).toBe('3개'); // 켠 수(2)가 아니라 전체 수
      expect(slot.blocked(draft)).toBe(false);
      expect(
        slot.blocked(draft.map((one) => ({ ...one, enabled: false }))),
      ).toBe(true);
      expect(
        slot.refusal('TERMS_DUPLICATE', { 'terms.1.text': ['서버 문장'] }),
      ).toEqual({
        line: `대상 단어 — ${GREENWASH_SETTING_TEXT.terms.refused.TERMS_DUPLICATE}`,
        refused: {
          'terms.1.text': [
            GREENWASH_SETTING_TEXT.terms.refused.TERMS_DUPLICATE,
          ],
        },
      });
      expect(slot.refusal('AI_PROMPT_TEXT_EMPTY', {})).toBeNull();
    });

    it('판 읽기 실패·기본 단어 읽기 실패 → failed(빈 목록으로 두지 않는다)', async () => {
      const { module, settings } = setup();
      settings.override['GET /ai-settings/greenwash/13'] = () =>
        json(500, undefined);
      settings.override['GET /greenwash/terms/default'] = () =>
        json(500, undefined);
      expect(await module.draft!.load('13')).toEqual({ kind: 'failed' });
      expect(await module.draft!.load('12')).toEqual({ kind: 'failed' });
      expect(await module.draft!.load('default')).toEqual({ kind: 'failed' });
    });
  });
});

// 밴드 TRA1: 영문번역 줄 = 영문번역 실어댑터·공통 prompt-model 어댑터(module 'translation')를 슬롯 꼴로 감싼 것. 모듈 몫이 없어 저장은 바탕 판을 읽지 않는다.
describe('영문번역 모듈 줄(밴드 TRA1)', () => {
  function translation() {
    const settings = fakeTranslationSettingServer({ baseUrl: BASE });
    const promptModels = fakePromptModelServer({
      baseUrl: BASE,
      module: 'translation',
    });
    const api = createApi({
      baseUrl: BASE,
      fetch: (request: Request) =>
        promptModels.handles(request) ?
          promptModels.send(request)
        : settings.send(request),
    });
    return { settings, promptModels, module: translationModule(api) };
  }
  const body = {
    title: '지어낸 새 판',
    memo: '지어낸 메모',
    modelSettings: {
      steps: [
        {
          key: 'translate_ceo',
          route: 'fake-route-b',
          temperature: null,
          maxOutputTokens: 3000,
          webSearch: false,
        },
      ],
    },
    prompts: {
      steps: [
        {
          key: 'review',
          prompts: [{ key: 'review', text: '지어낸 검수 글', memo: '' }],
        },
      ],
    },
  };

  it('id 는 경로 칸 낱말 translation · 이름은 메뉴·감사 낱말과 같음 · 구성 줄은 고정 규칙 하나 · 모델 곁 글 0 · 모듈 초안 0 · 흐름 띠 있음', () => {
    const { module } = translation();
    expect(module.id).toBe('translation');
    expect(module.name).toBe(TRANSLATION_SETTING_TEXT.module.name);
    expect(module.name).toBe(ACCOUNT_TEXT.shell.menu.aiSettingsTranslation);
    expect(module.name).toBe(AUDIT_TEXT.entry.modules.translation);
    expect(module.components).toEqual([
      {
        key: 'codeRules',
        label: AI_SETTING_TEXT.codeRules.label,
        sum: AI_SETTING_TEXT.codeRules.sum,
        body: {
          kind: 'lines',
          title: TRANSLATION_SETTING_TEXT.module.codeRules.title,
          lines: TRANSLATION_SETTING_TEXT.fixedRules,
          foot: TRANSLATION_SETTING_TEXT.module.codeRules.foot,
        },
      },
    ]);
    expect(module.modelNote).toBeUndefined();
    expect(module.draft).toBeUndefined();
    expect(typeof module.flow).toBe('function');
    // 밴드 DVA2(K1·K2): 영문번역 줄은 칸 안내·출력 안내 모듈 글이 없다(껍데기 공통 글 그대로).
    expect(module.promptNote).toBeUndefined();
    expect(module.outputNote).toBeUndefined();
  });

  it('translationPage: 저장 판 줄(번호·이름·상태·만든 때·만든 사람·메모)과 기본 판 줄 — 적용 default/saved 두 갈래', () => {
    const items = fakeTranslationSettings();
    const saved = translationPage(
      fakeTranslationSettingList(items, { kind: 'saved', id: 11 }),
    );
    expect(saved).toEqual({
      kind: 'ok',
      page: {
        rows: [
          {
            key: '12',
            kind: 'saved',
            number: 'v2',
            title: '지어낸 문체 다듬기',
            status: 'testing',
            createdAt: '2026-10-24T10:00:00+09:00',
            author: '지어낸 관리자',
            memo: '지어낸 메모 둘',
          },
          {
            key: '11',
            kind: 'saved',
            number: 'v1',
            title: '지어낸 첫 판',
            status: 'applied',
            createdAt: '2026-10-22T09:00:00+09:00',
            author: null,
            memo: '',
          },
        ],
        base: {
          key: 'default',
          kind: 'default',
          number: 'colab-tr-v1',
          title: '지어낸 기본 설정',
          status: 'default',
          createdAt: null,
          author: null,
          memo: '',
        },
        total: 2,
      },
    });
    const base = translationPage(
      fakeTranslationSettingList([], { kind: 'default' }),
    );
    expect(base.kind === 'ok' && base.page.base.status).toBe('applied');
    expect(base.kind === 'ok' && base.page.rows).toEqual([]);
  });

  it('list·apply: 영문번역 서버 — 실패는 failed', async () => {
    const { module, settings } = translation();
    const page = await module.port.list(0);
    expect(page.kind === 'ok' && page.page.rows.map((row) => row.key)).toEqual([
      '12',
      '11',
    ]);
    expect(await module.port.apply('12')).toEqual({ kind: 'ok' });
    expect(await module.port.apply(null)).toEqual({ kind: 'ok' });
    settings.override['GET /ai-settings/translation'] = () =>
      json(500, { error: { code: 'X', message: 'x', fields: null } });
    expect(await module.port.list(0)).toEqual({ kind: 'failed' });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      [
        'GET /ai-settings/translation',
        'PUT /ai-settings/translation/applied',
        'PUT /ai-settings/translation/applied',
        'GET /ai-settings/translation',
      ],
    );
  });

  it('promptModel: 공통 읽기 — /ai-settings/translation/{id|default}/prompt-model, 영문번역 서버는 부르지 않는다', async () => {
    const { module, settings, promptModels } = translation();
    expect((await module.port.promptModel('12')).kind).toBe('ok');
    expect((await module.port.promptModel('default')).kind).toBe('ok');
    expect(promptModels.calls.map((call) => call.path)).toEqual([
      '/ai-settings/translation/12/prompt-model',
      '/ai-settings/translation/default/prompt-model',
    ]);
    expect(settings.calls).toEqual([]);
  });

  it('create: 바탕 판 GET 0 · POST 한 번(본문 = 공통 본문 그대로) → 새 판 열쇠·번호, 거절은 code·서버 문장 그대로', async () => {
    const { module, settings, promptModels } = translation();
    for (const base of ['12', 'default'])
      expect(await module.port.create(base, body)).toMatchObject({
        kind: 'ok',
      });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      ['POST /ai-settings/translation', 'POST /ai-settings/translation'],
    );
    expect(settings.bodies('POST /ai-settings/translation')).toEqual([
      body,
      body,
    ]);
    expect(promptModels.calls).toEqual([]);
    expect(settings.settings()[0]).toMatchObject({ id: 14, name: 'v4' });
    settings.override['POST /ai-settings/translation'] = () =>
      json(400, {
        error: {
          code: 'AI_MODEL_TEMPERATURE_UNSUPPORTED',
          message: '지어낸 서버 문장',
          fields: null,
        },
      });
    expect(await module.port.create('12', body)).toEqual({
      kind: 'rejected',
      code: 'AI_MODEL_TEMPERATURE_UNSUPPORTED',
      message: '지어낸 서버 문장',
      fields: {},
    });
  });

  it('TRA2 D1·D9·D10: 처음 칸 = 번역 묶음의 보이는 차례 첫 칸(style_rules) · 상세 라벨 「칸」 · KEY 소문자 — 그린워싱 줄은 셋 다 없음', () => {
    const { module } = translation();
    const groups = [
      {
        key: 'translate',
        label: '지어낸 번역',
        prompts: ['tone_ceo_message', 'style_a', 'style_rules'].map((key) => ({
          key,
          label: `지어낸 ${key}`,
        })),
      },
      { key: 'polish', label: '지어낸 윤문', prompts: [] },
    ];
    expect(module.firstSlot?.(groups)).toEqual({ group: 0, prompt: 2 });
    expect(module.firstSlot?.([...groups].reverse())).toEqual({
      group: 1,
      prompt: 2,
    });
    expect(module.slotLabel).toBe('칸');
    expect(module.lowerKey).toBe(true);
    const greenwash = setup().module;
    expect(greenwash.firstSlot).toBeUndefined();
    expect(greenwash.slotLabel).toBeUndefined();
    expect(greenwash.lowerKey).toBeUndefined();
    // 밴드 DVA2(K1·K2): 그린워싱 줄은 칸 안내·출력 안내 모듈 글이 없다(껍데기 공통 글 그대로).
    expect(greenwash.promptNote).toBeUndefined();
    expect(greenwash.outputNote).toBeUndefined();
  });

  it('TRA2 D2: 「고정 글」(readonly_prompts) 값은 비움(카드는 이름만) · 처리 값 묶음은 그대로 · ok 아닌 갈래는 그대로', () => {
    const base = fakePromptModel('v1', {});
    const model = {
      ...base,
      fixed: [
        ...base.fixed,
        {
          key: 'readonly_prompts',
          label: '고정 글',
          items: [
            {
              key: 'base',
              label: '지어낸 바탕 지시',
              value: '지어낸 긴 글\n'.repeat(45),
            },
          ],
        },
      ],
    };
    const out = translationPromptModel({ kind: 'ok', model });
    if (out.kind !== 'ok') throw new Error('ok 여야 한다');
    expect(
      out.model.fixed.find((one) => one.key === 'readonly_prompts')!.items,
    ).toEqual([{ key: 'base', label: '지어낸 바탕 지시', value: null }]);
    expect(
      out.model.fixed.filter((one) => one.key !== 'readonly_prompts'),
    ).toEqual(base.fixed);
    expect(out.model.promptGroups).toBe(model.promptGroups);
    expect(translationPromptModel({ kind: 'failed' })).toEqual({
      kind: 'failed',
    });
  });
});

describe('데이터 검증 모듈 줄(밴드 DVA2)', () => {
  function dataverify() {
    const settings = fakeDataverifySettingServer({ baseUrl: BASE });
    const promptModels = fakePromptModelServer({
      baseUrl: BASE,
      module: 'dataverify',
    });
    const api = createApi({
      baseUrl: BASE,
      fetch: (request: Request) =>
        promptModels.handles(request) ?
          promptModels.send(request)
        : settings.send(request),
    });
    return { settings, promptModels, module: dataverifyModule(api) };
  }
  const own = DATAVERIFY_SETTING_TEXT;
  const body = {
    title: '지어낸 새 판',
    memo: '지어낸 메모',
    modelSettings: {
      steps: [
        {
          key: 'shared',
          route: 'fake-route-b',
          temperature: 0.3,
          maxOutputTokens: 3000,
          webSearch: true,
        },
      ],
    },
    prompts: {
      steps: [
        {
          key: 'review',
          prompts: [
            { key: 'review_system', text: '지어낸 검토 지시', memo: '' },
            {
              key: 'review_user',
              text: '지어낸 {계산 계획의 산식 목록} {입력 데이터 JSON}',
              memo: '',
            },
          ],
        },
      ],
    },
  };

  it('id 는 경로 칸 낱말 dataverify · 이름은 메뉴·감사 낱말과 같음 · 구성 줄은 고정 규칙 하나(DATAVERIFY_SETTING_TEXT.fixedRules) · 모델 곁 글 = 시안 글 · 모듈 초안 0 · 흐름 띠 있음', () => {
    const { module } = dataverify();
    expect(module.id).toBe('dataverify');
    expect(module.name).toBe(own.module.name);
    expect(module.name).toBe(ACCOUNT_TEXT.shell.menu.aiSettingsDataverify);
    expect(module.name).toBe(AUDIT_TEXT.entry.modules.dataverify);
    expect(module.components).toEqual([
      {
        key: 'codeRules',
        label: AI_SETTING_TEXT.codeRules.label,
        sum: AI_SETTING_TEXT.codeRules.sum,
        body: {
          kind: 'lines',
          title: own.module.codeRules.title,
          lines: own.fixedRules,
          foot: own.module.codeRules.foot,
        },
      },
    ]);
    expect(module.modelNote).toBe(
      '세 단계에 같이 쓰여요 · 모델 하나로 세 프롬프트를 불러요',
    );
    expect(module.draft).toBeUndefined();
    expect(typeof module.flow).toBe('function');
  });

  it('TRA2 D1·D9·D10: firstSlot 없음(띠 차례 = 서버 차례 — {0,0}) · 상세 라벨 「칸」 · KEY 소문자', () => {
    const { module } = dataverify();
    expect(module.firstSlot).toBeUndefined();
    expect(module.slotLabel).toBe('칸');
    expect(module.lowerKey).toBe(true);
  });

  it('promptNote: 입력 글 셋만 자리 안내(그 칸 자리를 늘어놓음) · 계산 검토는 기업 낱말 0 · 지시 글·모르는 칸 null', () => {
    const { module } = dataverify();
    const note = module.promptNote!;
    const plan = note('plan', 'plan_user')!;
    expect(plan).toBe(
      `${own.placeholders.lead(['{기업명}', '{SASB 산업분류}', '{중대토픽}', '{보고연도}', '{입력 데이터 JSON}'])} — ${own.placeholders.company} · ${own.placeholders.tail}`,
    );
    expect(note('insight', 'insight_user')).toBe(plan);
    const review = note('review', 'review_user')!;
    expect(review).toBe(
      `${own.placeholders.lead(['{계산 계획의 산식 목록}', '{입력 데이터 JSON}'])} — ${own.placeholders.review} · ${own.placeholders.tail}`,
    );
    for (const word of ['기업명', 'SASB', '중대토픽', '보고연도'])
      expect(review).not.toContain(word);
    for (const key of ['plan_system', 'review_system', 'insight_system', 'x'])
      expect(note('plan', key)).toBeNull();
  });

  it('outputNote: 계산 계획·인사이트 지시 글만 모듈 글 · 그 밖 칸 넷 null(껍데기가 outputSection 규칙으로 고름)', () => {
    const { module } = dataverify();
    const note = module.outputNote!;
    expect(note('plan', 'plan_system')).toBe(own.outputNotes.plan_system);
    expect(note('insight', 'insight_system')).toBe(
      own.outputNotes.insight_system,
    );
    for (const [group, key] of [
      ['plan', 'plan_user'],
      ['review', 'review_system'],
      ['review', 'review_user'],
      ['insight', 'insight_user'],
    ])
      expect(note(group!, key!)).toBeNull();
  });

  it('dataverifyPage: 저장 판 줄(번호·이름·상태·만든 때·만든 사람·메모)과 기본 판 줄 — 적용 default/saved 두 갈래', () => {
    const items = fakeDataverifySettings();
    const saved = dataverifyPage(
      fakeDataverifySettingList(items, { kind: 'saved', id: 11 }),
    );
    expect(saved).toEqual({
      kind: 'ok',
      page: {
        rows: [
          {
            key: '12',
            kind: 'saved',
            number: 'v2',
            title: '지어낸 검토 손질',
            status: 'testing',
            createdAt: '2026-10-24T10:00:00+09:00',
            author: '지어낸 관리자',
            memo: '지어낸 메모 둘',
          },
          {
            key: '11',
            kind: 'saved',
            number: 'v1',
            title: '지어낸 첫 판',
            status: 'applied',
            createdAt: '2026-10-22T09:00:00+09:00',
            author: null,
            memo: '',
          },
        ],
        base: {
          key: 'default',
          kind: 'default',
          number: 'colab-dv-v1',
          title: '지어낸 기본 설정',
          status: 'default',
          createdAt: null,
          author: null,
          memo: '',
        },
        total: 2,
      },
    });
    const base = dataverifyPage(
      fakeDataverifySettingList([], { kind: 'default' }),
    );
    expect(base.kind === 'ok' && base.page.base.status).toBe('applied');
    expect(base.kind === 'ok' && base.page.rows).toEqual([]);
  });

  it('list·apply: 데이터 검증 서버 — 실패는 failed', async () => {
    const { module, settings } = dataverify();
    const page = await module.port.list(0);
    expect(page.kind === 'ok' && page.page.rows.map((row) => row.key)).toEqual([
      '12',
      '11',
    ]);
    expect(await module.port.apply('12')).toEqual({ kind: 'ok' });
    expect(await module.port.apply(null)).toEqual({ kind: 'ok' });
    settings.override['GET /ai-settings/dataverify'] = () =>
      json(500, { error: { code: 'X', message: 'x', fields: null } });
    expect(await module.port.list(0)).toEqual({ kind: 'failed' });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      [
        'GET /ai-settings/dataverify',
        'PUT /ai-settings/dataverify/applied',
        'PUT /ai-settings/dataverify/applied',
        'GET /ai-settings/dataverify',
      ],
    );
  });

  it('promptModel: 공통 읽기 — /ai-settings/dataverify/{id|default}/prompt-model, 받은 그대로(고정 값 덮기 0), 데이터 검증 서버는 부르지 않는다', async () => {
    const { module, settings, promptModels } = dataverify();
    const read = await module.port.promptModel('12');
    expect(read.kind).toBe('ok');
    expect(read.kind === 'ok' && read.model).toEqual(
      fakePromptModel('setting-12'),
    );
    expect((await module.port.promptModel('default')).kind).toBe('ok');
    expect(promptModels.calls.map((call) => call.path)).toEqual([
      '/ai-settings/dataverify/12/prompt-model',
      '/ai-settings/dataverify/default/prompt-model',
    ]);
    expect(settings.calls).toEqual([]);
  });

  it('create: 바탕 판 GET 0 · POST 한 번(본문 = 공통 본문 그대로) → 새 판 열쇠·번호, 자리 지움 거절은 code·서버 문장·fields 그대로', async () => {
    const { module, settings, promptModels } = dataverify();
    for (const base of ['12', 'default'])
      expect(await module.port.create(base, body)).toMatchObject({
        kind: 'ok',
      });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      ['POST /ai-settings/dataverify', 'POST /ai-settings/dataverify'],
    );
    expect(settings.bodies('POST /ai-settings/dataverify')).toEqual([
      body,
      body,
    ]);
    expect(promptModels.calls).toEqual([]);
    expect(settings.settings()[0]).toMatchObject({ id: 14, name: 'v4' });
    const fields = {
      'prompts.steps.1.prompts.1.text': [
        '입력 글에서 {계산 계획의 산식 목록} 자리를 지우면 안 돼요',
      ],
    };
    settings.override['POST /ai-settings/dataverify'] = () =>
      json(400, {
        error: {
          code: 'AI_PROMPT_PLACEHOLDER_MISSING',
          message: '입력 글에서 {계산 계획의 산식 목록} 자리를 지우면 안 돼요',
          fields,
        },
      });
    expect(await module.port.create('12', body)).toEqual({
      kind: 'rejected',
      code: 'AI_PROMPT_PLACEHOLDER_MISSING',
      message: '입력 글에서 {계산 계획의 산식 목록} 자리를 지우면 안 돼요',
      fields,
    });
  });
});

describe('중대성평가 IRO 모듈 줄(밴드 IRA2)', () => {
  function materiality() {
    const settings = fakeMaterialitySettingServer({ baseUrl: BASE });
    const promptModels = fakePromptModelServer({
      baseUrl: BASE,
      module: 'materiality',
    });
    const api = createApi({
      baseUrl: BASE,
      fetch: (request: Request) =>
        promptModels.handles(request) ?
          promptModels.send(request)
        : settings.send(request),
    });
    return { settings, promptModels, module: materialityModule(api) };
  }
  const own = MATERIALITY_SETTING_TEXT;
  const body = {
    title: '지어낸 새 판',
    memo: '지어낸 메모',
    modelSettings: {
      steps: [
        {
          key: 'research',
          route: 'fake-route-a',
          temperature: 0.3,
          maxOutputTokens: 3000,
          webSearch: true,
        },
        {
          key: 'analysis',
          route: 'fake-route-b',
          temperature: null,
          maxOutputTokens: 6000,
          webSearch: false,
        },
      ],
    },
    prompts: {
      steps: [
        {
          key: 'pathway',
          prompts: [
            { key: 'pathway_system', text: '지어낸 경로 지시', memo: '' },
            {
              key: 'pathway_input',
              text: '지어낸 {재무 영향 정의의 답}',
              memo: '',
            },
          ],
        },
      ],
    },
  };
  /** 서버 fixed 둘(prompt_model_155.fixed_groups 꼴 — 값은 지어낸 것) + 앞뒤 다른 묶음. */
  const fixed = () => [
    { key: 'other', label: '지어낸 다른 묶음', items: [] },
    {
      key: 'tools',
      label: '웹 검색',
      items: [
        { key: 'research', label: '리서치 모델', value: '지어낸 검색 하나' },
        { key: 'analysis', label: '분석 모델', value: '지어낸 검색 둘' },
      ],
    },
    {
      key: 'processing',
      label: '실행 규칙',
      items: [
        { key: 'calls', label: '호출 단위', value: '지어낸 호출' },
        { key: 'max_steps', label: '호출마다 걸음', value: 1 },
        { key: 'retry', label: '잘림 다시 시도', value: 1 },
        { key: 'max_cost_usd', label: '실행 비용 상한(USD)', value: '5.0' },
        { key: 'whitelist', label: '신뢰 출처 판 고름', value: '지어낸 고름' },
        {
          key: 'analysis_temperature',
          label: '분석 모델 temperature',
          value: '지어낸 싣지 않음',
        },
      ],
    },
  ];
  const withFixed = () => ({
    kind: 'ok' as const,
    model: { ...fakePromptModel('setting-12'), fixed: fixed() },
  });

  it('id 는 경로 칸 낱말 materiality · 이름은 감사 낱말·시안 제목과 같음(메뉴 줄은 짧은 「중대성평가」 — Q4) · 구성 줄은 고정 규칙 하나 · 모델 곁 글 = 시안 글 · 모듈 초안 0 · 흐름 띠 있음', () => {
    const { module } = materiality();
    expect(module.id).toBe('materiality');
    expect(module.name).toBe(own.module.name);
    expect(module.name).toBe(AUDIT_TEXT.entry.modules.materiality);
    expect(module.name).toBe('중대성평가 IRO');
    expect(ACCOUNT_TEXT.shell.menu.aiSettingsMateriality).toBe('중대성평가');
    expect(module.components).toEqual([
      {
        key: 'codeRules',
        label: AI_SETTING_TEXT.codeRules.label,
        sum: AI_SETTING_TEXT.codeRules.sum,
        body: {
          kind: 'lines',
          title: own.module.codeRules.title,
          lines: own.fixedRules,
          foot: own.module.codeRules.foot,
        },
      },
    ]);
    expect(module.modelNote).toBe(
      '모델 칸 둘 · 리서치 두 단계는 리서치 모델, 영향 · 재무 세 단계는 분석 모델을 불러요',
    );
    expect(module.draft).toBeUndefined();
    expect(typeof module.flow).toBe('function');
  });

  it('TRA2 D1·D9·D10: firstSlot 없음(띠 차례 = 서버 차례 — {0,0} = regulation_system) · 상세 라벨 「칸」 · KEY 소문자', () => {
    const { module } = materiality();
    expect(module.firstSlot).toBeUndefined();
    expect(module.slotLabel).toBe('칸');
    expect(module.lowerKey).toBe(true);
  });

  it('K3 hideTemperature: 분석 모델 칸만 참 · 리서치·모르는 칸 거짓 — 다른 모듈 줄 셋은 없음(★T B1), 중대성평가 줄은 promptNote·outputNote 있음', () => {
    const { module } = materiality();
    expect(module.hideTemperature!('analysis')).toBe(true);
    expect(module.hideTemperature!('research')).toBe(false);
    expect(module.hideTemperature!('x')).toBe(false);
    const modules = aiSettingModules(createApi({ baseUrl: BASE }));
    expect(modules.map((one) => one.hideTemperature)).toEqual([
      undefined,
      undefined,
      undefined,
      expect.any(Function),
      undefined,
    ]);
    expect(typeof module.promptNote).toBe('function');
    expect(typeof module.outputNote).toBe('function');
  });

  it('promptNote: 몸은 entity 의 materialityPromptNote — 칸 열넷·옛 가변 입력 셋·모르는 칸 모두 같은 값(IRA3)', () => {
    const { module } = materiality();
    const note = module.promptNote!;
    const groups: [string, string[]][] = [
      [
        'regulation',
        ['regulation_system', 'regulation_prefix', 'regulation_input'],
      ],
      [
        'controversy',
        [
          'keywords_system',
          'keywords_prefix',
          'keywords_input',
          'controversy_system',
          'controversy_prefix',
          'controversy_input',
        ],
      ],
      ['impact', ['impact_system', 'impact_input']],
      ['financial', ['financial_system', 'financial_input']],
      ['pathway', ['pathway_system', 'pathway_input', 'x']],
      ['whitelist', ['whitelist_non_financial', 'whitelist_financial']],
    ];
    for (const [group, keys] of groups)
      for (const key of keys)
        expect(note(group, key), key).toBe(materialityPromptNote(key));
    expect(note('regulation', 'regulation_prefix')).toBe(own.inputNote);
    expect(note('whitelist', 'whitelist_financial')).toBeNull();
  });

  it('outputNote: 출력절 칸 여섯만 모듈 글 · 그 밖 칸 여덟 null(껍데기가 outputSection 규칙으로 고름)', () => {
    const { module } = materiality();
    const note = module.outputNote!;
    for (const [group, key] of [
      ['regulation', 'regulation_system'],
      ['controversy', 'keywords_prefix'],
      ['controversy', 'controversy_system'],
      ['impact', 'impact_system'],
      ['financial', 'financial_system'],
      ['pathway', 'pathway_system'],
    ])
      expect(note(group!, key!), key).toBe(own.outputNotes[key!]);
    for (const [group, key] of [
      ['regulation', 'regulation_prefix'],
      ['controversy', 'keywords_system'],
      ['controversy', 'controversy_prefix'],
      ['impact', 'impact_input'],
      ['financial', 'financial_input'],
      ['pathway', 'pathway_input'],
      ['whitelist', 'whitelist_non_financial'],
      ['whitelist', 'whitelist_financial'],
    ])
      expect(note(group!, key!), key).toBeNull();
  });

  it('materialityPage: 저장 판 줄(번호·이름·상태·만든 때·만든 사람·메모)과 기본 판 줄 — 적용 default/saved 두 갈래', () => {
    const items = fakeMaterialitySettings();
    const saved = materialityPage(
      fakeMaterialitySettingList(items, { kind: 'saved', id: 11 }),
    );
    expect(saved).toEqual({
      kind: 'ok',
      page: {
        rows: [
          {
            key: '12',
            kind: 'saved',
            number: 'v2',
            title: '지어낸 리서치 손질',
            status: 'testing',
            createdAt: '2026-10-24T10:00:00+09:00',
            author: '지어낸 관리자',
            memo: '지어낸 메모 둘',
          },
          {
            key: '11',
            kind: 'saved',
            number: 'v1',
            title: '지어낸 첫 판',
            status: 'applied',
            createdAt: '2026-10-22T09:00:00+09:00',
            author: null,
            memo: '',
          },
        ],
        base: {
          key: 'default',
          kind: 'default',
          number: 'colab-155',
          title: '지어낸 기본 설정',
          status: 'default',
          createdAt: null,
          author: null,
          memo: '',
        },
        total: 2,
      },
    });
    const base = materialityPage(
      fakeMaterialitySettingList([], { kind: 'default' }),
    );
    expect(base.kind === 'ok' && base.page.base.status).toBe('applied');
    expect(base.kind === 'ok' && base.page.rows).toEqual([]);
  });

  it('list·apply: 중대성평가 서버 — 실패는 failed', async () => {
    const { module, settings } = materiality();
    const page = await module.port.list(0);
    expect(page.kind === 'ok' && page.page.rows.map((row) => row.key)).toEqual([
      '12',
      '11',
    ]);
    expect(await module.port.apply('12')).toEqual({ kind: 'ok' });
    expect(await module.port.apply(null)).toEqual({ kind: 'ok' });
    settings.override['GET /ai-settings/materiality'] = () =>
      json(500, { error: { code: 'X', message: 'x', fields: null } });
    expect(await module.port.list(0)).toEqual({ kind: 'failed' });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      [
        'GET /ai-settings/materiality',
        'PUT /ai-settings/materiality/applied',
        'PUT /ai-settings/materiality/applied',
        'GET /ai-settings/materiality',
      ],
    );
  });

  it('promptModel: 공통 읽기 — /ai-settings/materiality/{id|default}/prompt-model, 중대성평가 서버는 부르지 않는다', async () => {
    const { module, settings, promptModels } = materiality();
    const read = await module.port.promptModel('12');
    expect(read.kind).toBe('ok');
    expect((await module.port.promptModel('default')).kind).toBe('ok');
    expect(promptModels.calls.map((call) => call.path)).toEqual([
      '/ai-settings/materiality/12/prompt-model',
      '/ai-settings/materiality/default/prompt-model',
    ]);
    expect(settings.calls).toEqual([]);
  });

  it('materialityPromptModel(Q1 가): 웹 검색·실행 규칙 둘 → 「실행 규칙」 카드 하나(항목 여덟 — 웹 검색 둘이 먼저, label 이음 · 값 그대로) · 다른 묶음 자리 그대로 · 둘 중 하나 없음·ok 아닌 갈래는 받은 그대로', () => {
    const folded = materialityPromptModel(withFixed());
    expect(folded.kind === 'ok' && folded.model.fixed).toEqual([
      { key: 'other', label: '지어낸 다른 묶음', items: [] },
      {
        key: 'processing',
        label: '실행 규칙',
        items: [
          {
            key: 'tools.research',
            label: '웹 검색 · 리서치 모델',
            value: '지어낸 검색 하나',
          },
          {
            key: 'tools.analysis',
            label: '웹 검색 · 분석 모델',
            value: '지어낸 검색 둘',
          },
          ...fixed()[2]!.items,
        ],
      },
    ]);
    const only = {
      kind: 'ok' as const,
      model: { ...fakePromptModel('setting-12'), fixed: fixed().slice(2) },
    };
    expect(materialityPromptModel(only)).toEqual(only);
    for (const outcome of [
      { kind: 'failed' as const },
      { kind: 'missing' as const },
      { kind: 'unusable' as const, message: '지어낸 문장' },
    ])
      expect(materialityPromptModel(outcome)).toEqual(outcome);
  });

  it('create: 바탕 판 GET 0 · POST 한 번(본문 = 공통 본문 그대로 — 분석 temperature null) → 새 판 열쇠·번호, 자리 지움 거절은 code·서버 문장·fields 그대로', async () => {
    const { module, settings, promptModels } = materiality();
    for (const base of ['12', 'default'])
      expect(await module.port.create(base, body)).toMatchObject({
        kind: 'ok',
      });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      ['POST /ai-settings/materiality', 'POST /ai-settings/materiality'],
    );
    expect(settings.bodies('POST /ai-settings/materiality')).toEqual([
      body,
      body,
    ]);
    expect(promptModels.calls).toEqual([]);
    expect(settings.settings()[0]).toMatchObject({ id: 14, name: 'v4' });
    const fields = {
      'prompts.steps.0.prompts.2.text': [
        '가변 입력에서 {토픽} 자리를 지우면 안 돼요',
      ],
    };
    settings.override['POST /ai-settings/materiality'] = () =>
      json(400, {
        error: {
          code: 'AI_PROMPT_PLACEHOLDER_MISSING',
          message: '가변 입력에서 {토픽} 자리를 지우면 안 돼요',
          fields,
        },
      });
    expect(await module.port.create('12', body)).toEqual({
      kind: 'rejected',
      code: 'AI_PROMPT_PLACEHOLDER_MISSING',
      message: '가변 입력에서 {토픽} 자리를 지우면 안 돼요',
      fields,
    });
  });
});

describe('보고서 작성 모듈 줄(밴드 RPA3)', () => {
  function drafting() {
    const settings = fakeDraftingSettingServer({ baseUrl: BASE });
    const promptModels = fakePromptModelServer({
      baseUrl: BASE,
      module: 'drafting',
    });
    const api = createApi({
      baseUrl: BASE,
      fetch: (request: Request) =>
        promptModels.handles(request) ?
          promptModels.send(request)
        : settings.send(request),
    });
    return { settings, promptModels, module: draftingModule(api) };
  }
  const own = DRAFTING_SETTING_TEXT;
  const body = {
    title: '지어낸 새 판',
    memo: '지어낸 메모',
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
            { key: 'draft_system', text: '지어낸 초안 지시', memo: '' },
            {
              key: 'draft_user',
              text: '지어낸 {제목 경로} {요구 내용} {페이지 글}',
              memo: '',
            },
          ],
        },
      ],
    },
  };
  /** 서버 fixed 둘(prompt_model_v2.fixed_groups 꼴 — 값·label 은 지어낸 것, 근거 표지 묶음은 항목 둘로 늘려 봄) + 앞 다른 묶음. */
  const fixed = () => [
    {
      key: 'other',
      label: '지어낸 다른 묶음',
      items: [{ key: 'x', label: '지어낸 항목', value: '지어낸 값' }],
    },
    {
      key: 'rules',
      label: '지어낸 표지 규칙',
      items: [
        { key: 'markers', label: '지어낸 표지', value: '지어낸 규칙 글' },
        { key: 'writing', label: '지어낸 쓰기', value: '지어낸 쓰기 글' },
      ],
    },
    {
      key: 'processing',
      label: '지어낸 실행 규칙',
      items: [
        { key: 'page_max_chars', label: '지어낸 쪽 상한', value: 1234 },
        { key: 'timeout_ms', label: '지어낸 시간 상한', value: 5678 },
      ],
    },
  ];
  const withFixed = () => ({
    kind: 'ok' as const,
    model: { ...fakePromptModel('setting-12'), fixed: fixed() },
  });

  it('id 는 경로 칸 낱말 drafting · 이름 「보고서 작성」은 메뉴 낱말과 같음(sid:MARC-ENT-525) · 감사 낱말 = 메뉴 낱말(AD6 — 감사·실행 기록 표에 drafting 「보고서 작성」) · 구성 줄 0(Q5) · 모듈 초안 0 · 흐름 띠 있음', () => {
    const { module } = drafting();
    expect(module.id).toBe('drafting');
    expect(module.name).toBe(own.module.name);
    expect(module.name).toBe('보고서 작성');
    expect(module.name).toBe(ACCOUNT_TEXT.shell.menu.aiSettingsDrafting);
    expect(AUDIT_TEXT.entry.modules.drafting).toBe(module.name);
    expect(module.components).toEqual([]);
    expect(module.draft).toBeUndefined();
    expect(typeof module.flow).toBe('function');
  });

  it('적용 안내 = 문구 표의 글(RPW12 · 디자인 c3 확정) · 그린워싱은 없음', () => {
    const { module } = drafting();
    expect(module.applyNote).toBe(own.applyNote);
    expect(module.applyNote).toBe(
      '적용한 설정은 다음 실행부터 써요 · 도는 중인 실행은 그대로예요 · 다음 실행은 앞 초안을 이어 받지 않고 전부 새로 지어요',
    );
    expect(setup().module.applyNote).toBeUndefined();
  });

  it('모델 카드 곁 글 없음(RPA4 — 이슈 490 Q1 (가) 뒤집음, 모의 위끝은 서버가 깎음)', () => {
    const { module } = drafting();
    expect(module.name).toBe(own.module.name);
    expect(module.modelNote).toBeUndefined();
  });

  it('TRA2 D1·D4·D9·D10: firstSlot 없음({0,0} = map_system) · 출력 안내 모듈 글 없음 · hideTemperature 없음 · 상세 라벨 「칸」 · KEY 소문자', () => {
    const { module } = drafting();
    expect(module.firstSlot).toBeUndefined();
    expect(module.outputNote).toBeUndefined();
    expect(module.hideTemperature).toBeUndefined();
    expect(module.slotLabel).toBe('칸');
    expect(module.lowerKey).toBe(true);
  });

  it('promptNote: 입력 글 둘만 자리 안내(그 칸 자리를 늘어놓음) · 지시 글 둘·모르는 칸 null', () => {
    const { module } = drafting();
    const note = module.promptNote!;
    const p = own.placeholders;
    expect(note('map', 'map_user')).toBe(
      `${p.lead(['{목차}', '{페이지 글}'])} · ${p.tail}`,
    );
    expect(note('draft', 'draft_user')).toBe(
      `${p.lead(['{제목 경로}', '{요구 내용}', '{페이지 글}'])} · ${p.tail}`,
    );
    for (const [group, prompt] of [
      ['map', 'map_system'],
      ['draft', 'draft_system'],
      ['draft', 'x'],
    ] as const)
      expect(note(group, prompt), prompt).toBeNull();
  });

  it('draftingPage: 저장 판 줄(번호·이름·상태·만든 때·만든 사람·메모)과 기본 판 줄 — 적용 default/saved 두 갈래', () => {
    const items = fakeDraftingSettings();
    const saved = draftingPage(
      fakeDraftingSettingList(items, { kind: 'saved', id: 11 }),
    );
    expect(saved).toEqual({
      kind: 'ok',
      page: {
        rows: [
          {
            key: '12',
            kind: 'saved',
            number: 'v2',
            title: '지어낸 초안 손질',
            status: 'testing',
            createdAt: '2026-10-24T10:00:00+09:00',
            author: '지어낸 관리자',
            memo: '지어낸 메모 둘',
          },
          {
            key: '11',
            kind: 'saved',
            number: 'v1',
            title: '지어낸 첫 판',
            status: 'applied',
            createdAt: '2026-10-22T09:00:00+09:00',
            author: null,
            memo: '',
          },
        ],
        base: {
          key: 'default',
          kind: 'default',
          number: 'v2-code',
          title: '지어낸 기본 설정',
          status: 'default',
          createdAt: null,
          author: null,
          memo: '',
        },
        total: 2,
      },
    });
    const base = draftingPage(fakeDraftingSettingList([], { kind: 'default' }));
    expect(base.kind === 'ok' && base.page.base.status).toBe('applied');
    expect(base.kind === 'ok' && base.page.rows).toEqual([]);
  });

  it('list·apply: 보고서 작성 서버 — 실패는 failed', async () => {
    const { module, settings } = drafting();
    const page = await module.port.list(0);
    expect(page.kind === 'ok' && page.page.rows.map((row) => row.key)).toEqual([
      '12',
      '11',
    ]);
    expect(await module.port.apply('12')).toEqual({ kind: 'ok' });
    expect(await module.port.apply(null)).toEqual({ kind: 'ok' });
    settings.override['GET /ai-settings/drafting'] = () =>
      json(500, { error: { code: 'X', message: 'x', fields: null } });
    expect(await module.port.list(0)).toEqual({ kind: 'failed' });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      [
        'GET /ai-settings/drafting',
        'PUT /ai-settings/drafting/applied',
        'PUT /ai-settings/drafting/applied',
        'GET /ai-settings/drafting',
      ],
    );
  });

  it('promptModel: 공통 읽기 — /ai-settings/drafting/{id|default}/prompt-model, 보고서 작성 서버는 부르지 않는다', async () => {
    const { module, settings, promptModels } = drafting();
    const read = await module.port.promptModel('12');
    expect(read.kind).toBe('ok');
    expect((await module.port.promptModel('default')).kind).toBe('ok');
    expect(promptModels.calls.map((call) => call.path)).toEqual([
      '/ai-settings/drafting/12/prompt-model',
      '/ai-settings/drafting/default/prompt-model',
    ]);
    expect(settings.calls).toEqual([]);
  });

  it('draftingPromptModel(Q2 가): 「rules」 묶음의 모든 항목 값 null(label·key·차례·수 그대로) · 실행 규칙·다른 묶음 그대로 · ok 아닌 갈래는 받은 그대로', () => {
    const emptied = draftingPromptModel(withFixed());
    expect(emptied.kind === 'ok' && emptied.model.fixed).toEqual([
      fixed()[0],
      {
        key: 'rules',
        label: '지어낸 표지 규칙',
        items: [
          { key: 'markers', label: '지어낸 표지', value: null },
          { key: 'writing', label: '지어낸 쓰기', value: null },
        ],
      },
      fixed()[2],
    ]);
    expect(emptied.kind === 'ok' && emptied.model.models).toEqual(
      withFixed().model.models,
    );
    for (const outcome of [
      { kind: 'failed' as const },
      { kind: 'missing' as const },
      { kind: 'unusable' as const, message: '지어낸 문장' },
    ])
      expect(draftingPromptModel(outcome)).toEqual(outcome);
  });

  it('promptModel 은 draftingPromptModel 을 거친다 — 가짜 fixed 의 rules 값이 비어 나온다', async () => {
    const { module, promptModels } = drafting();
    promptModels.override['GET /ai-settings/drafting/12/prompt-model'] = () =>
      json(200, withFixed().model);
    const read = await module.port.promptModel('12');
    expect(read.kind === 'ok' && read.model.fixed[1]!.items).toEqual([
      { key: 'markers', label: '지어낸 표지', value: null },
      { key: 'writing', label: '지어낸 쓰기', value: null },
    ]);
    expect(read.kind === 'ok' && read.model.fixed[2]).toEqual(fixed()[2]);
  });

  it('create: 바탕 판 GET 0 · POST 한 번(본문 = 공통 본문 그대로) → 새 판 열쇠·번호, 자리 지움 거절은 code·서버 문장·fields 그대로', async () => {
    const { module, settings, promptModels } = drafting();
    for (const base of ['12', 'default'])
      expect(await module.port.create(base, body)).toMatchObject({
        kind: 'ok',
      });
    expect(settings.calls.map((call) => `${call.method} ${call.path}`)).toEqual(
      ['POST /ai-settings/drafting', 'POST /ai-settings/drafting'],
    );
    expect(settings.bodies('POST /ai-settings/drafting')).toEqual([body, body]);
    expect(promptModels.calls).toEqual([]);
    expect(settings.settings()[0]).toMatchObject({ id: 14, name: 'v4' });
    const fields = {
      'prompts.steps.1.prompts.1.text': ['지어낸 자리 문장 {페이지 글}'],
    };
    settings.override['POST /ai-settings/drafting'] = () =>
      json(400, {
        error: {
          code: 'AI_PROMPT_PLACEHOLDER_MISSING',
          message: '지어낸 자리 문장 {페이지 글}',
          fields,
        },
      });
    expect(await module.port.create('12', body)).toEqual({
      kind: 'rejected',
      code: 'AI_PROMPT_PLACEHOLDER_MISSING',
      message: '지어낸 자리 문장 {페이지 글}',
      fields,
    });
  });
});
