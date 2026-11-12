// e2e 의 AI 설정 prompt-model 흉내 서버(밴드 AD2W ② — 껍데기 공통 도우미, sid:MARC-ENT-386-4). GET /api/ai-settings/<모듈>/{id|default}/prompt-model 을
// page.route 로 채운다(ai-settings.ts 의 정규식은 마디 하나만 받아 두 마디 경로가 새지 않게 따로 건다). 어느 id 에나 답한다.
// 답의 값은 전부 지어낸 것이다(코랩 글·서버 기본 글을 옮기지 않는다): ai.prompt-model@3 — 모델 칸 하나(judge) · 묶음 하나(judge, 칸 넷) · 경로 둘 · 고정 값 묶음 둘.
//   - 받은 요청을 calls 에 적는다(메서드·URL).
import type { Page } from '@playwright/test';

const OUTPUT = '[출력(JSON)]\n{"지어낸칸": "값"}';
const SHA = (n: number) => String(n).padStart(64, '0');
const MINI = [{ key: 'fake-mini-1', label: '지어낸 미니', provider: 'OpenAI' }];
const THINK = [
  { key: 'fake-think-1', label: '지어낸 생각', provider: 'OpenAI' },
];

/** 칸 넷의 key 와 지어낸 label. */
export const PROMPT_SLOTS = [
  ['detect', '지어낸 찾기'],
  ['eval', '지어낸 판정'],
  ['repair', '지어낸 고치기'],
  ['low_only', '지어낸 낮음 전용'],
] as const;

/** 지어낸 ai.prompt-model@3 한 벌. */
export function promptModel(settingName: string, module = 'greenwash') {
  return {
    schemaVersion: 'ai.prompt-model@3',
    module,
    settingName,
    editable: { model: true, prompts: true },
    limits: { textMax: 8000, memoMax: 500 },
    modelSettingsSha256: SHA(1),
    models: [
      {
        key: 'judge',
        label: '지어낸 판정 단계',
        model: {
          route: 'fake-mini',
          models: MINI,
          temperature: 0.2,
          maxOutputTokens: 2000,
          webSearch: false,
        },
        routeChoices: [
          {
            route: 'fake-mini',
            models: MINI,
            acceptsTemperature: true,
            maxOutputTokensMax: 16000,
            webSearchAvailable: false,
          },
          {
            route: 'fake-think',
            models: THINK,
            acceptsTemperature: false,
            maxOutputTokensMax: 32000,
            webSearchAvailable: false,
          },
        ],
        unavailableRoutes: [],
      },
    ],
    promptGroups: [
      {
        key: 'judge',
        label: '지어낸 판정 단계',
        modelSlots: ['judge'],
        prompts: PROMPT_SLOTS.map(([key, label]) => {
          const text = `지어낸 ${key} 기본 글\n${OUTPUT}`;
          return {
            key,
            label,
            promptId: `${module}.${key}`,
            promptVersion: '1',
            sha256: SHA(text.length),
            text,
            memo: `지어낸 ${key} 메모`,
            defaultText: text,
            isDefault: true,
            outputSection: OUTPUT,
            outputKept: true,
          };
        }),
      },
    ],
    fixed: [
      {
        key: 'parts',
        label: '파트',
        items: [
          { key: 'part-a', label: '지어낸 파트 가', value: null },
          { key: 'part-b', label: '지어낸 파트 나', value: null },
        ],
      },
      {
        key: 'processing',
        label: '처리 값',
        items: [
          { key: 'p1', label: '지어낸 값 하나', value: 30 },
          { key: 'p2', label: '지어낸 값 둘', value: ['High', 'Mid'] },
        ],
      },
    ],
  };
}

export interface PromptModelCall {
  method: string;
  url: URL;
}

/** prompt-model 흉내를 건다. 판 이름은 기본 판 「colab-2026-01-15-v1」, 저장 판 「setting-<id>」. */
export async function fakePromptModelApi(page: Page, module = 'greenwash') {
  const calls: PromptModelCall[] = [];
  const pattern = new RegExp(
    `/api/ai-settings/${module}/(\\d+|default)/prompt-model(\\?.*)?$`,
  );
  await page.route(pattern, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({ method: request.method(), url });
    const hit = pattern.exec(url.pathname)!;
    const name =
      hit[1] === 'default' ? 'colab-2026-01-15-v1' : `setting-${hit[1]}`;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(promptModel(name, module)),
    });
  });
  /** 나간 판 경로(/api 뒤 — 「/13/prompt-model」 꼴). */
  const paths = () =>
    calls.map((call) =>
      call.url.pathname.replace(`/api/ai-settings/${module}`, ''),
    );
  return { calls, paths };
}
