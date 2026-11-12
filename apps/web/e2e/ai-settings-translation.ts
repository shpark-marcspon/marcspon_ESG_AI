// e2e 의 영문번역 AI 설정 흉내 서버(밴드 TRA1). /api/ai-settings/translation 경로 셋(목록 · POST · PUT /applied)과
// /api/ai-settings/translation/{id|default}/prompt-model 을 page.route 로 채운다. 답의 값은 전부 지어낸 것이다(코랩 글·서버 기본 글을 옮기지 않는다).
// 꼴은 서버 TR4 를 따른다: translation.ai-settings@1 · ai-setting@1, prompt-model 은 ai.prompt-model@3 의 영문번역 꼴
//   (모델 칸 셋 · 묶음 다섯 · 칸 열넷 · 고정 묶음 둘). 경로 고름(routeChoices)은 모두 acceptsTemperature false — main 서버 꼴(TRM1, temperature 는 늘 null).
//   - 서버 규칙대로 돈다: 목록은 새 것 먼저·limit·offset, 상태는 적용 여부에서 셈, POST 는 새 판(id·이름 v<n> 매김, 시험 중, 201), PUT /applied 는 적용 판 바꿈.
//   - 받은 요청을 calls 에 적는다(메서드·URL·본문 — 판 목록·쓰기와 prompt-model 을 한 줄에, 차례 그대로).
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다.
import type { Page } from '@playwright/test';

const SHA = (n: number) => String(n).padStart(64, '0');
const ROUTE_A = [
  { key: 'fake-tr-a-1', label: '지어낸 번역 모델 가', provider: 'Anthropic' },
];
const ROUTE_B = [
  { key: 'fake-tr-b-1', label: '지어낸 번역 모델 나', provider: 'OpenAI' },
];
const CHOICES = [
  {
    route: 'fake-tr-a',
    models: ROUTE_A,
    acceptsTemperature: false,
    maxOutputTokensMax: 16000,
    webSearchAvailable: false,
  },
  {
    route: 'fake-tr-b',
    models: ROUTE_B,
    acceptsTemperature: false,
    maxOutputTokensMax: 32000,
    webSearchAvailable: false,
  },
];

/** 모델 칸 셋(key·지어낸 label). */
export const TR_MODELS = [
  ['translate_ceo', '지어낸 번역 · 대표 글'],
  ['translate_other', '지어낸 번역 · 그 밖'],
  ['review', '지어낸 검수 모델'],
] as const;

/** 묶음 다섯(key·지어낸 label·칸 key·모델 칸) — 칸 차례는 서버 GROUPS 꼴. */
export const TR_GROUPS = [
  [
    'translate',
    '지어낸 번역',
    [
      'tone_ceo_message',
      'tone_story',
      'tone_general',
      'style_a',
      'style_b',
      'style_rules',
      'subject_fragment_rules',
      'terminology_note',
      'table_rules',
    ],
    ['translate_ceo', 'translate_other'],
  ],
  ['polish', '지어낸 윤문', ['polish'], ['translate_ceo', 'translate_other']],
  [
    'editorial_qa',
    '지어낸 범용 QA',
    ['editorial_qa'],
    ['translate_ceo', 'translate_other'],
  ],
  ['review', '지어낸 검수', ['review'], ['review']],
  [
    'autofix',
    '지어낸 자동 수정',
    ['autofix', 'autofix_korean'],
    ['translate_ceo', 'translate_other'],
  ],
] as const;

/** 칸 key 의 지어낸 label. */
export const trLabel = (key: string) => `지어낸 칸 ${key}`;

/** 지어낸 영문번역 ai.prompt-model@3 한 벌. */
export function translationPromptModel(settingName: string) {
  return {
    schemaVersion: 'ai.prompt-model@3',
    module: 'translation',
    settingName,
    editable: { model: true, prompts: true },
    limits: { textMax: 8000, memoMax: 500 },
    modelSettingsSha256: SHA(3),
    models: TR_MODELS.map(([key, label]) => ({
      key,
      label,
      model: {
        route: 'fake-tr-a',
        models: ROUTE_A,
        temperature: null,
        maxOutputTokens: 4000,
        webSearch: false,
      },
      routeChoices: CHOICES,
      unavailableRoutes: [],
    })),
    promptGroups: TR_GROUPS.map(([key, label, prompts, modelSlots]) => ({
      key,
      label,
      modelSlots: [...modelSlots],
      prompts: prompts.map((one) => {
        const text = `지어낸 ${one} 기본 글`;
        return {
          key: one,
          label: trLabel(one),
          promptId: `translation.${one}`,
          promptVersion: '1',
          sha256: SHA(text.length),
          text,
          memo: `지어낸 ${one} 메모`,
          defaultText: text,
          isDefault: true,
          outputSection: null,
          outputKept: true,
        };
      }),
    })),
    fixed: [
      {
        key: 'processing',
        label: '처리 값',
        items: [
          { key: 'gate', label: '지어낸 관문 점수', value: 90 },
          { key: 'batch', label: '지어낸 묶음 크기', value: 10 },
        ],
      },
      {
        key: 'readonly_prompts',
        label: '고정 글',
        items: [{ key: 'base', label: '지어낸 바탕 지시', value: '지어낸 글' }],
      },
    ],
  };
}

interface Stored {
  id: number;
  name: string;
  title: string;
  memo: string;
  createdAt: string;
  ever: boolean;
}

export interface FakeTranslationCall {
  method: string;
  url: URL;
  body: unknown;
}

/** 영문번역 흉내를 건다. 저장 판 둘(지어낸 v2 시험 중 · v1 적용 중). */
export async function fakeTranslationSettingApi(page: Page) {
  const calls: FakeTranslationCall[] = [];
  const stored: Stored[] = [
    {
      id: 12,
      name: 'v2',
      title: '지어낸 문체 다듬기',
      memo: '지어낸 메모',
      createdAt: '2026-10-24T10:00:00+09:00',
      ever: false,
    },
    {
      id: 11,
      name: 'v1',
      title: '지어낸 첫 판',
      memo: '',
      createdAt: '2026-10-22T09:00:00+09:00',
      ever: true,
    },
  ];
  let appliedId: number | null = 11;
  const summary = (one: Stored) => ({
    id: one.id,
    name: one.name,
    title: one.title,
    status:
      one.id === appliedId ? 'applied'
      : one.ever ? 'past'
      : 'testing',
    createdAt: one.createdAt,
    createdBy: { id: 7, name: '지어낸 관리자' },
    memo: one.memo,
  });
  const list = (limit: number, offset: number) => {
    const all = [...stored].sort((a, b) => b.id - a.id);
    return {
      schemaVersion: 'translation.ai-settings@1',
      companyId: 1,
      applied:
        appliedId === null ?
          { kind: 'default' }
        : { kind: 'saved', id: appliedId },
      default: { name: 'colab-tr-v1', title: '지어낸 기본 설정' },
      items: all.slice(offset, offset + limit).map(summary),
      total: all.length,
    };
  };
  const reply = (status: number, body: unknown) => ({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

  await page.route(
    /\/api\/ai-settings\/translation(\/applied)?(\?.*)?$/,
    (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const body: unknown = request.postDataJSON?.() ?? null;
      calls.push({ method: request.method(), url, body });
      if (request.method() === 'GET')
        return route.fulfill(
          reply(
            200,
            list(
              Number(url.searchParams.get('limit') ?? 20),
              Number(url.searchParams.get('offset') ?? 0),
            ),
          ),
        );
      if (request.method() === 'POST') {
        const { title, memo = '' } = body as { title: string; memo?: string };
        const id = Math.max(...stored.map((one) => one.id)) + 1;
        const one: Stored = {
          id,
          name: `v${stored.length + 1}`,
          title: title.trim(),
          memo,
          createdAt: '2026-10-26T09:30:00+09:00',
          ever: false,
        };
        stored.push(one);
        return route.fulfill(
          reply(201, {
            schemaVersion: 'translation.ai-setting@1',
            ...summary(one),
          }),
        );
      }
      if (request.method() === 'PUT') {
        appliedId = (body as { id: number | null }).id;
        const one = stored.find((entry) => entry.id === appliedId);
        if (one) one.ever = true;
        return route.fulfill(reply(200, list(20, 0)));
      }
      return route.fulfill(reply(405, {}));
    },
  );
  await page.route(
    /\/api\/ai-settings\/translation\/(\d+|default)\/prompt-model(\?.*)?$/,
    (route) => {
      const request = route.request();
      const url = new URL(request.url());
      calls.push({ method: request.method(), url, body: null });
      const hit = /\/(\d+|default)\/prompt-model$/.exec(url.pathname)!;
      const name = hit[1] === 'default' ? 'colab-tr-v1' : `setting-${hit[1]}`;
      return route.fulfill(reply(200, translationPromptModel(name)));
    },
  );

  /** 나간 요청 「메서드 /api 뒤 경로」(차례 그대로). */
  const keys = () =>
    calls.map((call) => `${call.method} ${call.url.pathname.slice(4)}`);
  /** POST 본문들. */
  const posted = () =>
    calls.filter((call) => call.method === 'POST').map((call) => call.body);
  return { calls, keys, posted };
}
