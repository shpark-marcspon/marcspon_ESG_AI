// e2e 의 중대성평가 IRO AI 설정 흉내 서버(밴드 IRA2). /api/ai-settings/materiality 경로 셋(목록 · POST · PUT /applied)과
// /api/ai-settings/materiality/{id|default}/prompt-model 을 page.route 로 채운다. 글은 전부 지어낸 것이다(받은 노트북 글·서버 기본 글을 옮기지 않는다 —
// 자리 이름 `{토픽}` 등은 계약 글자라 쓴다). 이름(묶음·칸·고정 값 label)은 서버 label 꼴.
// 꼴은 서버 IR4 를 따른다: materiality.ai-settings@1 · ai-setting@1, prompt-model 은 ai.prompt-model@3 의 중대성평가 꼴
//   (모델 칸 둘 research·analysis · 묶음 여섯 · 칸 열넷(IRA3) · 출력절은 여섯 칸 · 고정 묶음 둘 — 웹 검색 둘·실행 규칙 여섯).
//   경로 고름(routeChoices)은 둘 다 acceptsTemperature true(서버 gpt-4o·gpt-4.1 꼴) — analysis 의 temperature 기본은 null, webSearch 는 research true·analysis false 고정.
//   - 서버 규칙대로 돈다: 목록은 새 것 먼저·limit·offset, 상태는 적용 여부에서 셈, POST 는 새 판(id·이름 v<n> 매김, 시험 중, 201), PUT /applied 는 적용 판 바꿈.
//   - POST 는 analysis temperature 가 값이면 400 AI_MODEL_TEMPERATURE_UNSUPPORTED, 자리 지킴 칸에 그 칸 자리가 없으면 400 AI_PROMPT_PLACEHOLDER_MISSING
//     (서버 accept_model → accept_prompts 차례 — 첫 빠진 칸 하나, 그 칸의 첫 빠진 자리).
//   - 받은 요청을 calls 에 적는다(메서드·URL·본문 — 판 목록·쓰기와 prompt-model 을 한 줄에, 차례 그대로).
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다.
import type { Page } from '@playwright/test';

const SHA = (n: number) => String(n).padStart(64, '0');
const RESEARCH_ROUTE = [
  { key: 'fake-ir-r1', label: '지어낸 리서치 모델', provider: 'OpenAI' },
];
const ANALYSIS_ROUTE = [
  { key: 'fake-ir-a1', label: '지어낸 분석 모델', provider: 'OpenAI' },
];

const PART2 = [
  '{기업명}',
  '{산업 정의}',
  '{가치사슬 활동}',
  '{토픽}',
  '{서브토픽}',
  '{서브토픽 설명}',
  '{컨트로버시 리서치의 답}',
  '{규제·정책 리서치의 답}',
];
/** 자리 지킴 칸 → 지켜야 하는 자리(서버 REQUIRED 꼴). */
export const IR_REQUIRED: Readonly<Record<string, readonly string[]>> = {
  regulation_system: ['{신뢰 출처 목록}'],
  impact_input: PART2,
  financial_input: PART2,
  pathway_input: ['{재무 영향 정의의 답}'],
};

/** 칸 key → 서버 칸 이름(LABELS 꼴). */
export const IR_LABELS: Readonly<Record<string, string>> = {
  regulation_system: '지시 글',
  regulation_prefix: '입력 글',
  keywords_system: '키워드 지시',
  keywords_prefix: '키워드 입력',
  controversy_system: '이슈 지시',
  controversy_prefix: '이슈 입력',
  impact_system: '지시 글',
  impact_input: '입력 글',
  financial_system: '지시 글',
  financial_input: '입력 글',
  pathway_system: '지시 글',
  pathway_input: '입력 글',
  whitelist_non_financial: '비금융',
  whitelist_financial: '금융',
};

/** 묶음 여섯(key·서버 label·칸·모델 칸). */
export const IR_GROUPS = [
  [
    'regulation',
    '규제·정책 리서치',
    ['regulation_system', 'regulation_prefix'],
    'research',
  ],
  [
    'controversy',
    '컨트로버시 리서치',
    [
      'keywords_system',
      'keywords_prefix',
      'controversy_system',
      'controversy_prefix',
    ],
    'research',
  ],
  [
    'impact',
    '환경·사회 영향 정의',
    ['impact_system', 'impact_input'],
    'analysis',
  ],
  [
    'financial',
    '재무 영향 정의',
    ['financial_system', 'financial_input'],
    'analysis',
  ],
  [
    'pathway',
    '재무 영향 경로',
    ['pathway_system', 'pathway_input'],
    'analysis',
  ],
  [
    'whitelist',
    '신뢰 출처 목록',
    ['whitelist_non_financial', 'whitelist_financial'],
    'research',
  ],
] as const;

/** 출력절이 있는 칸(서버 OUTPUT_MARKS 꼴). */
const OUTPUT_KEYS = [
  'regulation_system',
  'keywords_prefix',
  'controversy_system',
  'impact_system',
  'financial_system',
  'pathway_system',
];
/** 지어낸 출력절(그 칸 글 끝에 둔다). */
const outputOf = (key: string) =>
  OUTPUT_KEYS.includes(key) ?
    `[지어낸 출력 형식 ${key}]\n지어낸 열 하나`
  : null;

/** 칸의 지어낸 기본 글(자리 지킴 칸은 그 칸 자리를 품는다, 출력절 칸은 끝에 절). */
export const irText = (key: string) =>
  [`지어낸 ${key} 기본 글`, ...(IR_REQUIRED[key] ?? []), outputOf(key)]
    .filter((line) => line !== null)
    .join('\n');

const routeChoice = (route: string, models: typeof RESEARCH_ROUTE) => ({
  route,
  models,
  acceptsTemperature: true,
  maxOutputTokensMax: 32768,
  webSearchAvailable: true,
});

/** 지어낸 중대성평가 ai.prompt-model@3 한 벌. */
export function materialityPromptModel(settingName: string) {
  return {
    schemaVersion: 'ai.prompt-model@3',
    module: 'materiality',
    settingName,
    editable: { model: true, prompts: true },
    limits: { textMax: 8000, memoMax: 500 },
    modelSettingsSha256: SHA(5),
    models: [
      {
        key: 'research',
        label: '리서치 모델',
        model: {
          route: 'fake-ir-r',
          models: RESEARCH_ROUTE,
          temperature: 0.1,
          maxOutputTokens: 16384,
          webSearch: true,
        },
        routeChoices: [routeChoice('fake-ir-r', RESEARCH_ROUTE)],
        unavailableRoutes: [],
      },
      {
        key: 'analysis',
        label: '분석 모델',
        model: {
          route: 'fake-ir-a',
          models: ANALYSIS_ROUTE,
          temperature: null,
          maxOutputTokens: 32768,
          webSearch: false,
        },
        routeChoices: [routeChoice('fake-ir-a', ANALYSIS_ROUTE)],
        unavailableRoutes: [],
      },
    ],
    promptGroups: IR_GROUPS.map(([key, label, prompts, slot]) => ({
      key,
      label,
      modelSlots: [slot],
      prompts: prompts.map((one, index) => {
        const text = irText(one);
        return {
          key: one,
          label: IR_LABELS[one]!,
          promptId: `materiality.${key}`,
          promptVersion: 'fake',
          sha256: SHA(text.length),
          text,
          memo: index === 0 && key !== 'whitelist' ? `지어낸 ${one} 메모` : '',
          defaultText: text,
          isDefault: true,
          outputSection: outputOf(one),
          outputKept: true,
        };
      }),
    })),
    fixed: [
      {
        key: 'tools',
        label: '웹 검색',
        items: [
          { key: 'research', label: '리서치 모델', value: '지어낸 늘 검색' },
          { key: 'analysis', label: '분석 모델', value: '지어낸 켰을 때만' },
        ],
      },
      {
        key: 'processing',
        label: '실행 규칙',
        items: [
          { key: 'calls', label: '호출 단위', value: '지어낸 호출 단위' },
          { key: 'max_steps', label: '호출마다 걸음', value: 1 },
          { key: 'retry', label: '잘림 다시 시도', value: 1 },
          { key: 'max_cost_usd', label: '실행 비용 상한(USD)', value: '9.5' },
          {
            key: 'whitelist',
            label: '신뢰 출처 판 고름',
            value: '지어낸 고름',
          },
          {
            key: 'analysis_temperature',
            label: '분석 모델 temperature',
            value: '지어낸 싣지 않음',
          },
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

export interface FakeMaterialityCall {
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

/** 모델 받기(서버 accept_model 꼴 — analysis 는 temperature null 만). */
function temperatureRefused(models: ModelsIn | null | undefined) {
  const analysis = models?.steps.find((step) => step.key === 'analysis');
  return analysis && analysis.temperature !== null ?
      refusalOf(
        'AI_MODEL_TEMPERATURE_UNSUPPORTED',
        '지어낸 분석 temperature 거절',
        null,
      )
    : null;
}

/** 자리 지킴(서버 accept_prompts 꼴) — 첫 빠진 칸의 거절 본문, 없으면 null. */
function placeholderMissing(prompts: PromptsIn | null | undefined) {
  for (const [i, step] of (prompts?.steps ?? []).entries())
    for (const [j, prompt] of step.prompts.entries()) {
      const missing = (IR_REQUIRED[prompt.key] ?? []).find(
        (slot) => !prompt.text.includes(slot),
      );
      if (missing !== undefined) {
        const message = `${IR_LABELS[prompt.key]}에서 ${missing} 자리를 지우면 안 돼요`;
        return refusalOf('AI_PROMPT_PLACEHOLDER_MISSING', message, {
          [`prompts.steps.${i}.prompts.${j}.text`]: [message],
        });
      }
    }
  return null;
}

/** 중대성평가 흉내를 건다. 저장 판 둘(지어낸 v2 시험 중 · v1 적용 중). */
export async function fakeMaterialitySettingApi(page: Page) {
  const calls: FakeMaterialityCall[] = [];
  const stored: Stored[] = [
    {
      id: 12,
      name: 'v2',
      title: '지어낸 리서치 손질',
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
      schemaVersion: 'materiality.ai-settings@1',
      companyId: 1,
      applied:
        appliedId === null ?
          { kind: 'default' }
        : { kind: 'saved', id: appliedId },
      default: { name: 'colab-155', title: '지어낸 기본 설정' },
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
    /\/api\/ai-settings\/materiality(\/applied)?(\?.*)?$/,
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
          createdAt: '2026-10-28T09:30:00+09:00',
          ever: false,
        };
        stored.push(one);
        return route.fulfill(
          reply(201, {
            schemaVersion: 'materiality.ai-setting@1',
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
    /\/api\/ai-settings\/materiality\/(\d+|default)\/prompt-model(\?.*)?$/,
    (route) => {
      const request = route.request();
      const url = new URL(request.url());
      calls.push({ method: request.method(), url, body: null });
      const hit = /\/(\d+|default)\/prompt-model$/.exec(url.pathname)!;
      const name = hit[1] === 'default' ? 'colab-155' : `setting-${hit[1]}`;
      return route.fulfill(reply(200, materialityPromptModel(name)));
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
