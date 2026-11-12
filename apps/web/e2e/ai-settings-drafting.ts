// e2e 의 원고작성(보고서 작성) AI 설정 흉내 서버(밴드 RPA3). /api/ai-settings/drafting 경로 셋(목록 · POST · PUT /applied)과
// /api/ai-settings/drafting/{id|default}/prompt-model 을 page.route 로 채운다. 글은 전부 지어낸 것이다(서버 기본 글·시안 글을 옮기지 않는다 —
// 자리 이름 `{목차}`·`{페이지 글}`·`{제목 경로}`·`{요구 내용}` 은 계약 글자라 쓴다). 이름(묶음·칸·모델 칸·고정 값 label)은 서버 label 꼴.
// 꼴은 서버 RPA1 을 따른다: drafting.ai-settings@1 · ai-setting@1, prompt-model 은 ai.prompt-model@3 의 원고작성 꼴
//   (prompt_model_v2.py — 모델 칸 둘 map·draft · 묶음 둘 · 칸 넷(지시 글·입력 글) · 출력절 0 · 고정 묶음 둘 — 근거 표지·글 규칙 둘(RPQ1 e63908e8 꼴 markers·writing)·실행 규칙 넷).
//   경로 고름(routeChoices)은 둘 다 acceptsTemperature true · webSearchAvailable false(webSearch false 고정) · maxOutputTokensMax 는 지어낸 값.
//   - 서버 규칙대로 돈다: 목록은 새 것 먼저·limit·offset, 상태는 적용 여부에서 셈, POST 는 새 판(id·이름 v<n> 매김, 시험 중, 201), PUT /applied 는 적용 판 바꿈.
//   - POST 는 temperature 가 null 이면 400 AI_MODEL_TEMPERATURE_RANGE, 입력 글에 그 칸 자리가 없으면 400 AI_PROMPT_PLACEHOLDER_MISSING
//     (서버 accept_model → accept_prompts 차례 — 첫 빠진 칸 하나, 그 칸의 첫 빠진 자리. 문장은 지어낸 것).
//   - 받은 요청을 calls 에 적는다(메서드·URL·본문 — 판 목록·쓰기와 prompt-model 을 한 줄에, 차례 그대로).
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다.
import type { Page } from '@playwright/test';

const SHA = (n: number) => String(n).padStart(64, '0');
const LIGHT_ROUTE = [
  { key: 'fake-rp-l1', label: '지어낸 가벼운 모델', provider: 'OpenAI' },
];
const STANDARD_ROUTE = [
  { key: 'fake-rp-s1', label: '지어낸 보통 모델', provider: 'OpenAI' },
];
/** 경로의 출력 상한 위끝(지어낸 값 — 실경로 값 꼴). */
export const RP_MAX_OUTPUT_MAX = 16000;
/** 모델 칸의 출력 상한 기본(지어낸 값). */
export const RP_MAX_OUTPUT = 4000;

/** 입력 글 → 지켜야 하는 자리(서버 REQUIRED 꼴). */
export const RP_REQUIRED: Readonly<Record<string, readonly string[]>> = {
  map_user: ['{목차}', '{페이지 글}'],
  draft_user: ['{제목 경로}', '{요구 내용}', '{페이지 글}'],
};

/** 칸 key → 서버 칸 이름(LABELS 꼴). */
export const RP_LABELS: Readonly<Record<string, string>> = {
  map_system: '지시 글',
  map_user: '입력 글',
  draft_system: '지시 글',
  draft_user: '입력 글',
};

/** 모델 칸 둘(key·서버 label 꼴). */
export const RP_MODELS = [
  ['map', '목차 달기'],
  ['draft', '초안 짓기'],
] as const;

/** 묶음 둘(key·서버 label·칸·모델 칸). */
export const RP_GROUPS = [
  ['map', '목차 달기', ['map_system', 'map_user'], 'map'],
  ['draft', '초안 짓기', ['draft_system', 'draft_user'], 'draft'],
] as const;

/** 고정 묶음 둘(서버 fixed_groups 꼴 — label 은 서버 꼴, 값은 지어낸 것). */
export const RP_FIXED = [
  {
    key: 'rules',
    label: '근거 표지·글 규칙',
    items: [
      { key: 'markers', label: '자료 표지', value: '지어낸 표지 규칙 글' },
      { key: 'writing', label: '글 규칙', value: '지어낸 글 규칙 글' },
    ],
  },
  {
    key: 'processing',
    label: '실행 규칙',
    items: [
      { key: 'page_max_chars', label: '페이지 글 상한(자)', value: 1111 },
      { key: 'batch_max_chars', label: '페이지 묶음 상한(자)', value: 2222 },
      {
        key: 'material_max_chars',
        label: '초안 재료 전체 상한(자)',
        value: 3333,
      },
      { key: 'timeout_ms', label: '호출 시간 상한(밀리초)', value: 4444 },
    ],
  },
];

/** 칸의 지어낸 기본 글(입력 글은 그 칸 자리를 한 줄씩 품는다). */
export const rpText = (key: string) =>
  [`지어낸 ${key} 기본 글`, ...(RP_REQUIRED[key] ?? [])].join('\n');

const routeChoice = (route: string, models: typeof LIGHT_ROUTE) => ({
  route,
  models,
  acceptsTemperature: true,
  maxOutputTokensMax: RP_MAX_OUTPUT_MAX,
  webSearchAvailable: false,
});

/** 지어낸 원고작성 ai.prompt-model@3 한 벌. */
export function draftingPromptModel(settingName: string) {
  return {
    schemaVersion: 'ai.prompt-model@3',
    module: 'drafting',
    settingName,
    editable: { model: true, prompts: true },
    limits: { textMax: 8000, memoMax: 500 },
    modelSettingsSha256: SHA(5),
    models: RP_MODELS.map(([key, label]) => ({
      key,
      label,
      model: {
        route: 'fake-rp-light',
        models: LIGHT_ROUTE,
        temperature: 0,
        maxOutputTokens: RP_MAX_OUTPUT,
        webSearch: false,
      },
      routeChoices: [
        routeChoice('fake-rp-light', LIGHT_ROUTE),
        routeChoice('fake-rp-standard', STANDARD_ROUTE),
      ],
      unavailableRoutes: [],
    })),
    promptGroups: RP_GROUPS.map(([key, label, prompts, slot]) => ({
      key,
      label,
      modelSlots: [slot],
      prompts: prompts.map((one, index) => {
        const text = rpText(one);
        return {
          key: one,
          label: RP_LABELS[one]!,
          promptId: `drafting/${key}@fake`,
          promptVersion: 'fake',
          sha256: SHA(text.length),
          text,
          memo: index === 0 ? `지어낸 ${one} 메모` : '',
          defaultText: text,
          isDefault: true,
          outputSection: null,
          outputKept: true,
        };
      }),
    })),
    fixed: RP_FIXED,
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

export interface FakeDraftingCall {
  method: string;
  url: URL;
  body: unknown;
}

type PromptsIn = {
  steps: { key: string; prompts: { key: string; text: string }[] }[];
};
type ModelsIn = { steps: { key: string; temperature: number | null }[] };

const refusalOf = (
  code: string,
  message: string,
  fields: Record<string, string[]> | null,
) => ({ error: { code, message, fields, legacyCode: code.toLowerCase() } });

/** 모델 받기(서버 accept_model 꼴 — temperature null 거절). */
function temperatureRefused(models: ModelsIn | null | undefined) {
  const empty = models?.steps.find((step) => step.temperature === null);
  return empty ?
      refusalOf('AI_MODEL_TEMPERATURE_RANGE', '지어낸 temperature 거절', null)
    : null;
}

/** 자리 지킴(서버 accept_prompts 꼴) — 첫 빠진 칸의 거절 본문, 없으면 null. */
function placeholderMissing(prompts: PromptsIn | null | undefined) {
  for (const [i, step] of (prompts?.steps ?? []).entries())
    for (const [j, prompt] of step.prompts.entries()) {
      const missing = (RP_REQUIRED[prompt.key] ?? []).find(
        (slot) => !prompt.text.includes(slot),
      );
      if (missing !== undefined) {
        const message = `지어낸 자리 거절 ${missing}`;
        return refusalOf('AI_PROMPT_PLACEHOLDER_MISSING', message, {
          [`prompts.steps.${i}.prompts.${j}.text`]: [message],
        });
      }
    }
  return null;
}

/** 원고작성 흉내를 건다. 저장 판 둘(지어낸 v2 시험 중 · v1 적용 중). */
export async function fakeDraftingSettingApi(page: Page) {
  const calls: FakeDraftingCall[] = [];
  const stored: Stored[] = [
    {
      id: 12,
      name: 'v2',
      title: '지어낸 초안 손질',
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
      schemaVersion: 'drafting.ai-settings@1',
      companyId: 1,
      applied:
        appliedId === null ?
          { kind: 'default' }
        : { kind: 'saved', id: appliedId },
      default: { name: 'v2-code', title: '지어낸 기본 설정' },
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
    /\/api\/ai-settings\/drafting(\/applied)?(\?.*)?$/,
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
        const {
          title,
          memo = '',
          modelSettings,
          prompts,
        } = body as {
          title: string;
          memo?: string;
          modelSettings?: ModelsIn | null;
          prompts?: PromptsIn | null;
        };
        const refused =
          temperatureRefused(modelSettings) ?? placeholderMissing(prompts);
        if (refused) return route.fulfill(reply(400, refused));
        const id = Math.max(...stored.map((one) => one.id)) + 1;
        const one: Stored = {
          id,
          name: `v${stored.length + 1}`,
          title: title.trim(),
          memo,
          createdAt: '2026-11-01T09:30:00+09:00',
          ever: false,
        };
        stored.push(one);
        return route.fulfill(
          reply(201, {
            schemaVersion: 'drafting.ai-setting@1',
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
    /\/api\/ai-settings\/drafting\/(\d+|default)\/prompt-model(\?.*)?$/,
    (route) => {
      const request = route.request();
      const url = new URL(request.url());
      calls.push({ method: request.method(), url, body: null });
      const hit = /\/(\d+|default)\/prompt-model$/.exec(url.pathname)!;
      const name = hit[1] === 'default' ? 'v2-code' : `setting-${hit[1]}`;
      return route.fulfill(reply(200, draftingPromptModel(name)));
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
