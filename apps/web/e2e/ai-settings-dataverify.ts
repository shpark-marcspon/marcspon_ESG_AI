// e2e 의 데이터 검증 AI 설정 흉내 서버(밴드 DVA2). /api/ai-settings/dataverify 경로 셋(목록 · POST · PUT /applied)과
// /api/ai-settings/dataverify/{id|default}/prompt-model 을 page.route 로 채운다. 글은 전부 지어낸 것이다(받은 노트북 글·서버 기본 글을 옮기지 않는다 —
// 자리 이름 `{기업명}` 등은 계약 글자라 쓴다). 이름(묶음·칸·고정 값 label)은 서버 label 꼴.
// 꼴은 서버 DVA1 을 따른다: dataverify.ai-settings@1 · ai-setting@1, prompt-model 은 ai.prompt-model@3 의 데이터 검증 꼴
//   (모델 칸 하나 shared · 묶음 셋 · 칸 여섯(지시 글·입력 글) · 출력절은 계산 계획·인사이트 지시 글 둘만 · 고정 묶음 둘 — 계산 도구 다섯·처리 값 넷).
//   경로 고름(routeChoices)은 acceptsTemperature true(서버 standard-openai-41 꼴 — 0~2, 기본 0.1) · webSearch true 고정.
//   - 서버 규칙대로 돈다: 목록은 새 것 먼저·limit·offset, 상태는 적용 여부에서 셈, POST 는 새 판(id·이름 v<n> 매김, 시험 중, 201), PUT /applied 는 적용 판 바꿈.
//   - POST 는 입력 글 칸에 그 칸 자리가 없으면 400 AI_PROMPT_PLACEHOLDER_MISSING(서버 accept_prompts 꼴 — 첫 빠진 칸 하나, 그 칸의 첫 빠진 자리).
//   - 받은 요청을 calls 에 적는다(메서드·URL·본문 — 판 목록·쓰기와 prompt-model 을 한 줄에, 차례 그대로).
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다.
import type { Page } from '@playwright/test';

const SHA = (n: number) => String(n).padStart(64, '0');
const ROUTE = [
  { key: 'fake-dv-1', label: '지어낸 검증 모델', provider: 'OpenAI' },
];

/** 입력 글 칸 → 지켜야 하는 자리(서버 REQUIRED 꼴). */
const COMPANY = ['{기업명}', '{SASB 산업분류}', '{중대토픽}', '{보고연도}'];
export const DV_REQUIRED: Readonly<Record<string, readonly string[]>> = {
  plan_user: [...COMPANY, '{입력 데이터 JSON}'],
  review_user: ['{계산 계획의 산식 목록}', '{입력 데이터 JSON}'],
  insight_user: [...COMPANY, '{입력 데이터 JSON}'],
};

/** 묶음 셋(key·서버 label). 칸은 <key>_system 「지시 글」 · <key>_user 「입력 글」. */
export const DV_GROUPS = [
  ['plan', '계산 계획'],
  ['review', '계산 검토'],
  ['insight', '리스크 진단'],
] as const;

/** 지어낸 출력절(계산 계획·인사이트 지시 글 끝에 둔다). */
const OUTPUT = '[지어낸 출력 형식]\n지어낸 열 하나 | 지어낸 열 둘';

/** 칸의 지어낸 기본 글(입력 글은 그 칸 자리를 품는다). */
export const dvText = (key: string) =>
  key.endsWith('_user') ?
    `지어낸 ${key} 기본 글\n${DV_REQUIRED[key]!.join('\n')}`
  : key === 'plan_system' || key === 'insight_system' ?
    `지어낸 ${key} 기본 글\n${OUTPUT}`
  : `지어낸 ${key} 기본 글`;

/** 지어낸 데이터 검증 ai.prompt-model@3 한 벌. */
export function dataverifyPromptModel(settingName: string) {
  return {
    schemaVersion: 'ai.prompt-model@3',
    module: 'dataverify',
    settingName,
    editable: { model: true, prompts: true },
    limits: { textMax: 8000, memoMax: 500 },
    modelSettingsSha256: SHA(5),
    models: [
      {
        key: 'shared',
        label: '세 단계 공통',
        model: {
          route: 'fake-dv',
          models: ROUTE,
          temperature: 0.1,
          maxOutputTokens: 4000,
          webSearch: true,
        },
        routeChoices: [
          {
            route: 'fake-dv',
            models: ROUTE,
            acceptsTemperature: true,
            maxOutputTokensMax: 32768,
            webSearchAvailable: true,
          },
        ],
        unavailableRoutes: [],
      },
    ],
    promptGroups: DV_GROUPS.map(([key, label]) => ({
      key,
      label,
      modelSlots: ['shared'],
      prompts: (['system', 'user'] as const).map((part) => {
        const one = `${key}_${part}`;
        const text = dvText(one);
        const output = part === 'system' && key !== 'review' ? OUTPUT : null;
        return {
          key: one,
          label: part === 'system' ? '지시 글' : '입력 글',
          promptId: `dataverify.${key}`,
          promptVersion: 'fake',
          sha256: SHA(text.length),
          text,
          memo: part === 'system' ? `지어낸 ${one} 메모` : '',
          defaultText: text,
          isDefault: true,
          outputSection: output,
          outputKept: true,
        };
      }),
    })),
    fixed: [
      {
        key: 'tools',
        label: '계산 도구',
        items: ['sum', 'sum_n', 'ratio', 'value_of', 'search'].map((key) => ({
          key,
          label: `지어낸 도구 ${key}`,
          value: `지어낸 ${key} 하는 일`,
        })),
      },
      {
        key: 'processing',
        label: '처리 값',
        items: [
          { key: 'tolerance', label: '판정 허용 오차', value: '0.0' },
          { key: 'plan_steps', label: '계산 계획 걸음', value: 9 },
          { key: 'review_steps', label: '계산 검토 걸음', value: '지어낸 셈' },
          { key: 'insight_steps', label: '리스크 진단 걸음', value: 9 },
        ],
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

export interface FakeDataverifyCall {
  method: string;
  url: URL;
  body: unknown;
}

type PromptsIn = {
  steps: { key: string; prompts: { key: string; text: string }[] }[];
};

/** 입력 글 자리 지킴(서버 accept_prompts 꼴) — 첫 빠진 칸의 거절 본문, 없으면 null. */
function placeholderMissing(prompts: PromptsIn | null | undefined) {
  for (const [i, step] of (prompts?.steps ?? []).entries())
    for (const [j, prompt] of step.prompts.entries()) {
      const missing = (DV_REQUIRED[prompt.key] ?? []).find(
        (slot) => !prompt.text.includes(slot),
      );
      if (missing !== undefined) {
        const message = `입력 글에서 ${missing} 자리를 지우면 안 돼요`;
        return {
          error: {
            code: 'AI_PROMPT_PLACEHOLDER_MISSING',
            message,
            fields: { [`prompts.steps.${i}.prompts.${j}.text`]: [message] },
            legacyCode: 'ai_prompt_placeholder_missing',
          },
        };
      }
    }
  return null;
}

/** 데이터 검증 흉내를 건다. 저장 판 둘(지어낸 v2 시험 중 · v1 적용 중). */
export async function fakeDataverifySettingApi(page: Page) {
  const calls: FakeDataverifyCall[] = [];
  const stored: Stored[] = [
    {
      id: 12,
      name: 'v2',
      title: '지어낸 검토 손질',
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
      schemaVersion: 'dataverify.ai-settings@1',
      companyId: 1,
      applied:
        appliedId === null ?
          { kind: 'default' }
        : { kind: 'saved', id: appliedId },
      default: { name: 'colab-dv-v1', title: '지어낸 기본 설정' },
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
    /\/api\/ai-settings\/dataverify(\/applied)?(\?.*)?$/,
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
          prompts,
        } = body as {
          title: string;
          memo?: string;
          prompts?: PromptsIn | null;
        };
        const refused = placeholderMissing(prompts);
        if (refused) return route.fulfill(reply(400, refused));
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
            schemaVersion: 'dataverify.ai-setting@1',
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
    /\/api\/ai-settings\/dataverify\/(\d+|default)\/prompt-model(\?.*)?$/,
    (route) => {
      const request = route.request();
      const url = new URL(request.url());
      calls.push({ method: request.method(), url, body: null });
      const hit = /\/(\d+|default)\/prompt-model$/.exec(url.pathname)!;
      const name = hit[1] === 'default' ? 'colab-dv-v1' : `setting-${hit[1]}`;
      return route.fulfill(reply(200, dataverifyPromptModel(name)));
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
