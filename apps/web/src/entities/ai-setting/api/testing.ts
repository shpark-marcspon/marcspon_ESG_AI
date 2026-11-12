// 시험용 가짜 AI 설정(밴드 AD2W). 시험만 쓴다(공개 표면이 아니다). 값은 전부 지어낸 것이다(코랩 글·서버 기본 글을 옮기지 않는다).
//   - fakePromptModel: ai.prompt-model@3 한 벌 — 모델 칸 하나(judge)·묶음 하나(judge, 칸 넷)·경로 둘·고정 값 묶음 둘(값 없는 항목 셋 · 값 다섯).
//   - fakeWidePromptModel: 넓은 꼴 @3(AP1W) — 모델 칸 셋·묶음 다섯·칸 14(key 는 영문번역 꼴, label·글·경로는 지어낸 것).
//   - fakePromptModelServer: 통신 층 가짜(GET /ai-settings/<모듈>/{id|default}/prompt-model) — 어느 id 에나 답한다. 받은 요청을 calls 에 적는다.
//     override 에 「GET 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다).
//   - fakeAiSettingModule: 껍데기 시험용 모듈 한 줄(AiSettingModule — wide 면 넓은 꼴 prompt-model, modelNote 는 넘길 때만) — 판 목록·적용·prompt-model·새 판 저장을 메모리로 돈다.
//     저장(create)은 새 판 하나(열쇠 = 가장 큰 열쇠 + 1, 번호 v<가장 큰 n + 1>, 「초안」)를 더하고 부름 인자 {base, body, module} 를 적는다.
//     draft(모듈 초안 슬롯 — 시험이 지어 넘김)를 주면 모듈 줄에 싣고 구성 줄 끝에 그 초안 줄(body draft)을 더한다(AP1W ③).
//     판 셋(13 v3 초안 · 12 v2 적용 중 · 11 v1 지난 버전, 이름·만든 사람 없음)과 기본 판(이름 「기본 설정」). 부름을 calls 에 적고
//     override 에 부름 이름 → 함수(차례대로 쓰는 목록도 된다)를 주면 그 부름은 그 함수의 답을 낸다.
import type {
  AiSettingModule,
  AiSettingPort,
  ModelSlot,
  ModuleComponent,
  ModuleDraftSlot,
  PromptEntry,
  PromptModel,
  PromptModelOutcome,
  SaveOutcome,
  VersionPageOutcome,
  VersionRow,
} from '../model/index.ts';
import { DEFAULT_VERSION_KEY } from '../model/index.ts';

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (
  status: number,
  code: string,
  message = `지어낸-${code}`,
  fields: Record<string, string[]> | null = null,
) =>
  json(status, {
    error: { code, message, fields, legacyCode: code.toLowerCase() },
  });

const SHA = (n: number) => String(n).padStart(64, '0');

/** 지어낸 출력 형식 절(기본 글 끝에 둔다). */
const FAKE_OUTPUT = '[출력(JSON)]\n{"지어낸칸": "값"}';

/** 칸 넷(key 는 서버 명세의 차례를 흉내 — 글·label·메모는 지어낸 것). */
const FAKE_PROMPT_KEYS = ['detect', 'eval', 'repair', 'low_only'];
const LABELS: Record<string, string> = {
  detect: '지어낸 찾기',
  eval: '지어낸 판정',
  repair: '지어낸 고치기',
  low_only: '지어낸 낮음 전용',
};

/** 칸 하나: 기본 글 = 「지어낸 <key> 기본 글」 + 출력 절. text 를 주면 판의 글이 그것. */
function fakePromptEntry(
  key: string,
  { text, memo }: { text?: string; memo?: string } = {},
): PromptEntry {
  const defaultText = `지어낸 ${key} 기본 글\n${FAKE_OUTPUT}`;
  const body = text ?? defaultText;
  return {
    key,
    label: LABELS[key] ?? `지어낸 ${key}`,
    promptId: `greenwash.${key}`,
    promptVersion: '1',
    sha256: SHA(body.length),
    text: body,
    memo: memo ?? `지어낸 ${key} 메모`,
    defaultText,
    isDefault: body === defaultText,
    outputSection: FAKE_OUTPUT,
    outputKept: body.includes(FAKE_OUTPUT),
  };
}

/** 지어낸 prompt-model 한 벌. change 로 칸·모델·편집 가능 여부를 바꾼다. */
export function fakePromptModel(
  settingName: string,
  change: {
    prompts?: Record<string, { text?: string; memo?: string }>;
    model?: Partial<ModelSlot['model']>;
    editable?: PromptModel['editable'];
  } = {},
): PromptModel {
  return {
    schemaVersion: 'ai.prompt-model@3',
    module: 'greenwash',
    settingName,
    editable: change.editable ?? { model: true, prompts: true },
    limits: { textMax: 8000, memoMax: 500 },
    modelSettingsSha256: SHA(1),
    models: [
      {
        key: 'judge',
        label: '지어낸 판정 단계',
        model: {
          route: 'fake-mini',
          models: [
            { key: 'fake-mini-1', label: '지어낸 미니', provider: 'OpenAI' },
          ],
          temperature: 0.2,
          maxOutputTokens: 2000,
          webSearch: false,
          ...change.model,
        },
        routeChoices: [
          {
            route: 'fake-mini',
            models: [
              { key: 'fake-mini-1', label: '지어낸 미니', provider: 'OpenAI' },
            ],
            acceptsTemperature: true,
            maxOutputTokensMax: 16000,
            webSearchAvailable: false,
          },
          {
            route: 'fake-think',
            models: [
              { key: 'fake-think-1', label: '지어낸 생각', provider: 'OpenAI' },
            ],
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
        prompts: FAKE_PROMPT_KEYS.map((key) =>
          fakePromptEntry(key, change.prompts?.[key]),
        ),
      },
    ],
    fixed: [
      {
        key: 'parts',
        label: '파트',
        items: [
          { key: 'part-a', label: '지어낸 파트 가', value: null },
          { key: 'part-b', label: '지어낸 파트 나', value: null },
          { key: 'part-c', label: '지어낸 파트 다', value: null },
        ],
      },
      {
        key: 'processing',
        label: '처리 값',
        items: [
          { key: 'p1', label: '지어낸 값 하나', value: 30 },
          { key: 'p2', label: '지어낸 값 둘', value: 1200 },
          { key: 'p3', label: '지어낸 값 셋', value: 'Mid' },
          { key: 'p4', label: '지어낸 값 넷', value: ['High', 'Mid'] },
          { key: 'p5', label: '지어낸 값 다섯', value: 5 },
        ],
      },
    ],
  };
}

/** 넓은 꼴의 묶음(key 는 영문번역 꼴 — 칸 9·1·1·1·2, 받는 모델 칸). label 은 지어낸 것. */
const WIDE_GROUPS = [
  {
    key: 'translate',
    label: '지어낸 옮김',
    modelSlots: ['translate_ceo', 'translate_other'],
    prompts: [
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
  },
  {
    key: 'polish',
    label: '지어낸 다듬기',
    modelSlots: ['translate_ceo', 'translate_other'],
    prompts: ['polish'],
  },
  {
    key: 'editorial_qa',
    label: '지어낸 살핌',
    modelSlots: ['translate_ceo', 'translate_other'],
    prompts: ['editorial_qa'],
  },
  {
    key: 'review',
    label: '지어낸 검토',
    modelSlots: ['review'],
    prompts: ['review'],
  },
  {
    key: 'autofix',
    label: '지어낸 고침',
    modelSlots: ['translate_ceo', 'translate_other'],
    prompts: ['autofix', 'autofix_korean'],
  },
] as const;

/** 넓은 꼴의 모델 칸 하나: 경로 둘(지어낸 이름) — 칸마다 다른 모델·출력 상한. temperature 는 warm 칸의 첫 경로만 받는다. */
function fakeWideSlot(
  key: string,
  label: string,
  n: string,
  { max, tokens, warm }: { max: number; tokens: number; warm: boolean },
): ModelSlot {
  const ref = (which: string) => ({
    key: `fake-${n}${which}-1`,
    label: `지어낸 ${n}${which}`,
    provider: 'OpenAI',
  });
  return {
    key,
    label,
    model: {
      route: `fake-${n}1`,
      models: [ref('1')],
      temperature: warm ? 0.3 : null,
      maxOutputTokens: tokens,
      webSearch: false,
    },
    routeChoices: ['1', '2'].map((which) => ({
      route: `fake-${n}${which}`,
      models: [ref(which)],
      acceptsTemperature: warm && which === '1',
      maxOutputTokensMax: which === '1' ? max : max * 2,
      webSearchAvailable: false,
    })),
    unavailableRoutes: [],
  };
}

/**
 * 넓은 꼴 prompt-model(@3): 모델 칸 셋(translate_ceo · translate_other · review — 칸 2 는 두 경로 다 temperature 를 받지 않음·null)
 * · 묶음 다섯(translate 9 · polish · editorial_qa · review · autofix 2 — 칸 14). 칸 label 은 「지어낸 글 n」(n = 칸 차례 1~14).
 */
export function fakeWidePromptModel(
  settingName: string,
  change: { editable?: PromptModel['editable'] } = {},
): PromptModel {
  const base = fakePromptModel(settingName, change);
  let n = 0;
  return {
    ...base,
    module: 'fake-wide',
    models: [
      fakeWideSlot('translate_ceo', '지어낸 칸 가', 'a', {
        max: 8000,
        tokens: 2000,
        warm: true,
      }),
      fakeWideSlot('translate_other', '지어낸 칸 나', 'b', {
        max: 12000,
        tokens: 3000,
        warm: true,
      }),
      fakeWideSlot('review', '지어낸 칸 다', 'c', {
        max: 4000,
        tokens: 1000,
        warm: false,
      }),
    ],
    promptGroups: WIDE_GROUPS.map((group) => ({
      key: group.key,
      label: group.label,
      modelSlots: [...group.modelSlots],
      prompts: group.prompts.map((key) => ({
        ...fakePromptEntry(key),
        label: `지어낸 글 ${(n += 1)}`,
      })),
    })),
  };
}

interface FakeCall {
  method: string;
  path: string;
  query: URLSearchParams;
}

type Answer = () => Response | Promise<Response>;

/** 통신 층 가짜 prompt-model 서버. 판 이름은 기본 판 「colab-2026-01-15-v1」, 저장 판 「setting-<id>」. */
export function fakePromptModelServer({
  baseUrl = 'http://test.local/api',
  module = 'greenwash',
}: { baseUrl?: string; module?: string } = {}) {
  const calls: FakeCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const pattern = new RegExp(
    `^/ai-settings/${module}/(\\d+|default)/prompt-model$`,
  );
  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) =>
    request.method === 'GET' && pattern.test(pathOf(request));

  const send = (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(request);
    calls.push({ method: request.method, path, query: url.searchParams });
    const key = `${request.method} ${path}`;
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return Promise.resolve(next());
    } else if (replaced) return Promise.resolve(replaced());
    const hit = pattern.exec(path);
    if (request.method !== 'GET' || !hit)
      throw new Error(`가짜에 없는 경로: ${key}`);
    const name =
      hit[1] === 'default' ? 'colab-2026-01-15-v1' : `setting-${hit[1]}`;
    return Promise.resolve(json(200, fakePromptModel(name)));
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  return { send, handles, calls, count, override };
}

/** 지어낸 저장 판 셋(새 것 먼저). */
export function fakeVersionRows(): VersionRow[] {
  return [
    {
      key: '13',
      kind: 'saved',
      number: 'v3',
      title: '지어낸 판 셋',
      status: 'testing',
      createdAt: '2026-10-19T11:40:00+09:00',
      author: '지어낸 관리자',
      memo: '지어낸 메모 셋',
    },
    {
      key: '12',
      kind: 'saved',
      number: 'v2',
      title: '지어낸 판 둘',
      status: 'applied',
      createdAt: '2026-10-18T10:20:00+09:00',
      author: '지어낸 관리자',
      memo: '지어낸 메모 둘',
    },
    {
      key: '11',
      kind: 'saved',
      number: 'v1',
      title: null,
      status: 'past',
      createdAt: '2026-10-17T09:00:00+09:00',
      author: null,
      memo: '',
    },
  ];
}

/** 지어낸 기본 판 줄(서버 default — 이름 「기본 설정」). */
function fakeBaseRow(applied = false): VersionRow {
  return {
    key: DEFAULT_VERSION_KEY,
    kind: 'default',
    number: 'colab-2026-01-15-v1',
    title: '기본 설정',
    status: applied ? 'applied' : 'default',
    createdAt: null,
    author: null,
    memo: '',
  };
}

/** 지어낸 구성 줄 둘(대상 단어 — 준비 중, 고정 규칙 — 읽기 전용 줄 글). */
const FAKE_COMPONENTS: readonly ModuleComponent[] = [
  {
    key: 'terms',
    label: '지어낸 대상 단어',
    sum: '준비 중',
    body: { kind: 'pending' },
  },
  {
    key: 'codeRules',
    label: '고정 규칙',
    sum: '읽기 전용',
    body: {
      kind: 'lines',
      title: '고정 규칙 · 읽기 전용',
      lines: ['지어낸 규칙 하나', '지어낸 규칙 둘'],
      foot: '지어낸 규칙 꼬리',
    },
  },
];

type Method = 'list' | 'apply' | 'promptModel' | 'create';
type Replace = (arg: unknown) => unknown;

interface FakeModuleCall {
  method: Method;
  arg: unknown;
}

interface Stored {
  row: VersionRow;
  ever: boolean;
}

/** 껍데기 시험용 모듈 한 줄. */
export function fakeAiSettingModule({
  rows = fakeVersionRows(),
  appliedDefault = false,
  pageSize = 100,
  name = '지어낸 모듈',
  components = FAKE_COMPONENTS,
  wide = false,
  modelNote,
  draft,
  promptModel = (key: string): PromptModelOutcome => ({
    kind: 'ok',
    model: wide ? fakeWidePromptModel(key) : fakePromptModel(key),
  }),
}: {
  rows?: readonly VersionRow[];
  appliedDefault?: boolean;
  pageSize?: number;
  name?: string;
  components?: readonly ModuleComponent[];
  /** 넓은 꼴 prompt-model(fakeWidePromptModel — 모델 칸 셋·묶음 다섯). */
  wide?: boolean;
  /** 모듈이 선언하는 모델 카드 곁 글(기본값 없음 — 넘기지 않으면 곁 글 없음). */
  modelNote?: string;
  /** 모듈 초안 슬롯(넘길 때만 — 구성 줄 끝에 「지어낸 초안 몫」 줄이 붙는다). */
  draft?: ModuleDraftSlot;
  promptModel?: (key: string) => PromptModelOutcome;
} = {}) {
  const calls: FakeModuleCall[] = [];
  const override: Partial<Record<Method, Replace | Replace[]>> = {};
  const stored: Stored[] = rows.map((row) => ({
    row: { ...row },
    ever: row.status !== 'testing',
  }));
  let applied: string | null =
    appliedDefault ? null : (
      (rows.find((row) => row.status === 'applied')?.key ?? null)
    );

  const statusOf = (one: Stored): VersionRow['status'] =>
    one.row.key === applied ? 'applied'
    : one.ever ? 'past'
    : 'testing';
  const current = () =>
    [...stored]
      .sort((a, b) => Number(b.row.key) - Number(a.row.key))
      .map((one) => ({ ...one.row, status: statusOf(one) }));

  /** 부름을 적고, override 가 있으면 그 답을, 없으면 own 의 답을 낸다. */
  async function call<T>(method: Method, arg: unknown, own: () => T) {
    calls.push({ method, arg });
    const replaced = override[method];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return (await next(arg)) as T;
    } else if (replaced) return (await replaced(arg)) as T;
    return own();
  }

  const module: AiSettingModule = {
    id: 'fake',
    name,
    components:
      draft === undefined ? components : (
        [
          ...components,
          {
            key: draft.key,
            label: '지어낸 초안 몫',
            sum: '',
            body: { kind: 'draft' },
          },
        ]
      ),
    ...(modelNote === undefined ? {} : { modelNote }),
    ...(draft === undefined ? {} : { draft }),
    port: {
      list: (offset) =>
        call<VersionPageOutcome>('list', offset, () => {
          const all = current();
          return {
            kind: 'ok',
            page: {
              rows: all.slice(offset, offset + pageSize),
              base: fakeBaseRow(applied === null),
              total: all.length,
            },
          };
        }),
      apply: (key) =>
        call('apply', key, () => {
          for (const one of stored) if (one.row.key === key) one.ever = true;
          applied = key;
          return { kind: 'ok' as const };
        }),
      promptModel: (key) => call('promptModel', key, () => promptModel(key)),
      create: (
        base: string,
        body: Parameters<AiSettingPort['create']>[1],
        module?: unknown,
      ) =>
        call<SaveOutcome>('create', { base, body, module }, () => {
          const key = String(
            Math.max(10, ...stored.map((one) => Number(one.row.key))) + 1,
          );
          const n =
            Math.max(
              0,
              ...stored.map((one) =>
                Number(/^v(\d+)$/.exec(one.row.number)?.[1] ?? 0),
              ),
            ) + 1;
          const row: VersionRow = {
            key,
            kind: 'saved',
            number: `v${n}`,
            title: body.title.trim(),
            status: 'testing',
            createdAt: '2026-10-20T09:30:00+09:00',
            author: '지어낸 관리자',
            memo: body.memo,
          };
          stored.push({ row, ever: false });
          return { kind: 'ok', key, number: row.number };
        }),
    },
  };

  const count = (method: Method) =>
    calls.filter((one) => one.method === method).length;
  /** 그 부름의 인자들(차례대로). */
  const args = (method: Method) =>
    calls.filter((one) => one.method === method).map((one) => one.arg);
  return { module, calls, count, args, override, rows: current };
}
