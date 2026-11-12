// 시험용 가짜 그린워싱 AI 설정 서버(밴드 AD2R ①). 시험만 쓴다(공개 표면이 아니다).
// 답의 꼴은 api-py 의 /ai-settings/greenwash 다섯 경로(greenwash.ai-settings@2 · ai-setting@3 · ai-setting-default@3)를 따른다. 값은 전부 지어낸 것이다
//   (서버 criteria-default.json·코랩 원문을 옮기지 않는다 — 발주서 §1-8).
// 서버 규칙을 거르지 않고 따른다(화면 시험이 「진짜 어댑터 + 가짜」로 돈다 — 발주서 §3 ⓑ):
//   - 목록은 새 것 먼저(id 내림), limit(기본 20, 최대 100)·offset 으로 자른다. 상태는 적용 여부에서 센다(지금 적용 applied · 적용한 적 있음 past · 한 번도 testing).
//   - POST 는 새 판 하나: id = 가장 큰 id + 1, 이름 v<가장 큰 n + 1>, criteria.version 을 그 이름으로 덮는다. 받기 규칙 일부(15줄·id 차례·묶음 이름·글 1~300·한 줄)는 400 CRITERIA_*.
//   - PUT /applied: id null = 기본 판, 없는 id 404, 같은 판 다시 적용은 바뀜 0. 답은 바꾼 뒤 목록 첫 쪽(limit 20).
//   - 숫자 아닌 /{id} 는 422, 없는 id 는 404.
// Bearer 는 보지 않는다(세션 가짜 서버의 몫). 받은 요청을 calls 에 적는다(쿼리는 URLSearchParams, 본문은 JSON 그대로).
// GET /greenwash/terms/default(AS3b ① — 기본 단어 목록, 지어낸 낱말)도 answer 가 낸다. handles 는 넓히지 않는다(/ai-settings/greenwash 만 —
//   경로 시험은 그 경로를 그린워싱 가짜가 받는다). 모듈 줄 시험처럼 send 로 바로 넘기면 이 가짜가 답한다.
// override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다. 연결 끊김은 던지는 함수로).
import type {
  Setting,
  SettingCriteria,
  SettingDefault,
  SettingList,
  SettingRow,
  SettingSummary,
} from '../model/index.ts';
import { CRITERION_IDS, criterionTextProblem } from '../model/index.ts';

export interface FakeGreenwashSettingCall {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (status: number, code: string) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

const CATEGORY: Record<SettingRow['id'], SettingRow['category']> = {
  'keyword-ghg': 'targetKeyword',
  'keyword-exclusion': 'targetKeyword',
  'evidence-quantity': 'coreEvidence',
  'evidence-baseline': 'coreEvidence',
  'evidence-boundary': 'coreEvidence',
  'evidence-offset': 'coreEvidence',
  'high-1': 'high',
  'high-2': 'high',
  'high-3': 'high',
  'high-4': 'high',
  'mid-1': 'mid',
  'exception-1': 'exception',
  'exception-2': 'exception',
  'exception-3': 'exception',
  'exception-4': 'exception',
};
const VERDICT: Record<SettingRow['category'], SettingRow['verdict']> = {
  targetKeyword: 'coreEvidenceApplies',
  coreEvidence: 'highIfMissing',
  high: 'High',
  mid: 'Mid',
  exception: 'NonRisk',
};
/** 지어낸 묶음 이름(고칠 수 없음 — 가짜 서버가 바꾼 이름을 400 으로 거절한다). */
export const FAKE_KEYWORD_NAMES = {
  'keyword-ghg': '지어낸 묶음 가',
  'keyword-exclusion': '지어낸 묶음 나',
} as const;

/** 지어낸 기준표 한 벌(15줄). textOf 로 줄 글을 바꾼다. 키워드 낱말은 3·2개. */
export function fakeCriteria(
  version: string,
  change: Partial<Record<SettingRow['id'], Partial<SettingRow>>> = {},
): SettingCriteria {
  return {
    schemaVersion: 'greenwash.criteria@1',
    version,
    rows: CRITERION_IDS.map((id, index): SettingRow => {
      const category = CATEGORY[id];
      const keyword = category === 'targetKeyword';
      return {
        id,
        category,
        order: index + 1,
        enabled: true,
        text:
          keyword ?
            FAKE_KEYWORD_NAMES[id as keyof typeof FAKE_KEYWORD_NAMES]
          : `지어낸 ${id} 기준 글`,
        terms:
          id === 'keyword-ghg' ? ['지어낸말 하나', '지어낸말 둘', '지어낸말 셋']
          : id === 'keyword-exclusion' ? ['지어낸말 넷', '지어낸말 다섯']
          : null,
        verdict: VERDICT[category],
        guideline:
          keyword ? null : (
            { text: '지어낸 기관 · 지어낸 조항', status: 'draft' }
          ),
        ...change[id],
      };
    }),
  };
}

const SHA = (n: number) => String(n).padStart(64, '0');

/** 지어낸 대상 단어(G2d — v3 판만 목록, 나머지는 null = 코드 기본 목록). */
const FAKE_TERMS: Setting['terms'] = [
  { text: '지어낸 초록낱말', enabled: true },
  { text: '친환경', enabled: false },
];

/** 지어낸 저장 판 셋(새 것 먼저): 13 v3 시험 중(대상 단어 목록) · 12 v2 적용 중 · 11 v1 지난 버전(만든 사람 이름 못 풂 · 판 이름 없는 옛 판). 판마다 기준표가 다르다. */
export function fakeSettings(): Setting[] {
  const one = (
    id: number,
    name: string,
    title: string | null,
    status: Setting['status'],
    createdAt: string,
    author: string | null,
    memo: string,
    criteria: SettingCriteria,
  ): Setting => ({
    schemaVersion: 'greenwash.ai-setting@3',
    id,
    name,
    title,
    status,
    createdAt,
    createdBy: { id: 7, name: author },
    memo,
    evalPromptSha256: SHA(id),
    criteria,
    terms: id === 13 ? FAKE_TERMS : null,
  });
  return [
    one(
      13,
      'v3',
      '지어낸 판 셋',
      'testing',
      '2026-10-19T11:40:00+09:00',
      '지어낸 관리자',
      '지어낸 메모 셋',
      fakeCriteria('v3', {
        'high-2': { text: '지어낸 v3 High 둘 글' },
        'exception-4': { enabled: false },
      }),
    ),
    one(
      12,
      'v2',
      '지어낸 판 둘',
      'applied',
      '2026-10-18T10:20:00+09:00',
      '지어낸 관리자',
      '지어낸 메모 둘',
      fakeCriteria('v2', { 'high-2': { text: '지어낸 v2 High 둘 글' } }),
    ),
    one(
      11,
      'v1',
      null,
      'past',
      '2026-10-17T09:00:00+09:00',
      null,
      '',
      fakeCriteria('v1', { 'high-2': { text: '지어낸 v1 High 둘 글' } }),
    ),
  ];
}

/** 지어낸 기본 판(이름은 계약 설명의 기본 판 이름). */
export function fakeDefaultSetting(): SettingDefault {
  return {
    schemaVersion: 'greenwash.ai-setting-default@3',
    name: 'colab-2026-01-15-v1',
    title: '기본 설정',
    criteria: fakeCriteria('colab-2026-01-15-v1', {
      'high-2': { text: '지어낸 기본 판 High 둘 글' },
    }),
    evalPromptSha256: SHA(0),
    terms: null,
  };
}

const summaryOf = (setting: Setting): SettingSummary => ({
  id: setting.id,
  name: setting.name,
  title: setting.title,
  status: setting.status,
  createdAt: setting.createdAt,
  createdBy: setting.createdBy,
  memo: setting.memo,
  evalPromptSha256: setting.evalPromptSha256,
});

/** 목록 한 쪽(판은 새 것 먼저로 넣어 준다). applied 를 안 주면 상태 applied 인 판에서 센다. */
export function fakeSettingList(
  settings: readonly Setting[],
  applied?: SettingList['applied'],
  { total = settings.length } = {},
): SettingList {
  const on = settings.find((one) => one.status === 'applied');
  const fallback = fakeDefaultSetting();
  return {
    schemaVersion: 'greenwash.ai-settings@2',
    companyId: 1,
    applied:
      applied ?? (on ? { kind: 'saved', id: on.id } : { kind: 'default' }),
    default: {
      name: fallback.name,
      title: fallback.title,
      evalPromptSha256: fallback.evalPromptSha256,
    },
    items: settings.map(summaryOf),
    total,
  };
}

/** 지어낸 기본 단어 목록(서버 GREEN_TERMS 를 옮기지 않는다). */
export const FAKE_DEFAULT_TERMS: readonly string[] = [
  '지어낸 기본말 하나',
  '지어낸 기본말 둘',
  '지어낸 기본말 셋',
];

interface Stored {
  setting: Setting;
  ever: boolean;
}

export interface FakeGreenwashSettingSeed {
  /** 저장 판(어느 차례든 — 가짜가 id 내림으로 낸다). 없으면 fakeSettings(). */
  settings?: readonly Setting[];
  defaultSetting?: SettingDefault;
  /** 기본 단어 목록(GET /greenwash/terms/default). 없으면 FAKE_DEFAULT_TERMS. */
  defaultTerms?: readonly string[];
  baseUrl?: string;
}

const LIST_PATH = '/ai-settings/greenwash';
const ONE = /^\/ai-settings\/greenwash\/([^/]+)$/;

export function fakeGreenwashSettingServer({
  settings = fakeSettings(),
  defaultSetting = fakeDefaultSetting(),
  defaultTerms = FAKE_DEFAULT_TERMS,
  baseUrl = 'http://test.local/api',
}: FakeGreenwashSettingSeed = {}) {
  const calls: FakeGreenwashSettingCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const stored: Stored[] = settings.map((setting) => ({
    setting: structuredClone(setting),
    ever: setting.status !== 'testing',
  }));
  let appliedId: number | null =
    settings.find((one) => one.status === 'applied')?.id ?? null;

  const statusOf = (one: Stored): Setting['status'] =>
    one.setting.id === appliedId ? 'applied'
    : one.ever ? 'past'
    : 'testing';
  const current = (): Setting[] =>
    [...stored]
      .sort((a, b) => b.setting.id - a.setting.id)
      .map((one) => ({ ...one.setting, status: statusOf(one) }));
  const listOf = (limit: number, offset: number): SettingList => {
    const all = current();
    return fakeSettingList(
      all.slice(offset, offset + limit),
      appliedId === null ?
        { kind: 'default' }
      : { kind: 'saved', id: appliedId },
      { total: all.length },
    );
  };

  /** 받기 규칙 일부(서버 criteria_e0 의 차례). 거절 code 또는 null. */
  const refused = (body: unknown): string | null => {
    if (typeof body !== 'object' || body === null) return 'CRITERIA_SHAPE';
    const { criteria } = body as { criteria?: SettingCriteria };
    if (!criteria || !Array.isArray(criteria.rows)) return 'CRITERIA_SHAPE';
    if (criteria.schemaVersion !== 'greenwash.criteria@1')
      return 'CRITERIA_SCHEMA_VERSION';
    if (
      typeof criteria.version !== 'string' ||
      !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(criteria.version)
    )
      return 'CRITERIA_VERSION';
    if (criteria.rows.length !== CRITERION_IDS.length)
      return 'CRITERIA_ROWS_FIXED';
    for (const [index, row] of criteria.rows.entries()) {
      if (row.id !== CRITERION_IDS[index] || row.order !== index + 1)
        return 'CRITERIA_ROW_ORDER';
      if (row.category === 'targetKeyword') {
        if (
          row.text.trim() !==
          FAKE_KEYWORD_NAMES[row.id as keyof typeof FAKE_KEYWORD_NAMES]
        )
          return 'CRITERIA_KEYWORD_NAME';
        if (!Array.isArray(row.terms) || row.terms.length < 1)
          return 'CRITERIA_TERMS_COUNT';
        continue;
      }
      const problem = criterionTextProblem(row.text);
      if (problem === 'length') return 'CRITERIA_TEXT_LENGTH';
      if (problem === 'multiline') return 'CRITERIA_TEXT_MULTILINE';
      if (row.terms !== null) return 'CRITERIA_TERMS_NOT_ALLOWED';
    }
    return null;
  };

  const answer = (key: string, url: URL, body: unknown): Response => {
    if (key === `GET ${LIST_PATH}`) {
      const limit = Number(url.searchParams.get('limit') ?? 20);
      const offset = Number(url.searchParams.get('offset') ?? 0);
      return json(200, listOf(limit, offset));
    }
    if (key === `GET ${LIST_PATH}/default`) return json(200, defaultSetting);
    if (key === 'GET /greenwash/terms/default')
      return json(200, { terms: [...defaultTerms] });
    if (key === `POST ${LIST_PATH}`) {
      const code = refused(body);
      if (code) return refusal(400, code);
      const {
        title,
        criteria,
        memo = '',
        terms = null,
      } = body as {
        title: string;
        criteria: SettingCriteria;
        memo?: string;
        terms?: Setting['terms'];
      };
      const id = Math.max(10, ...stored.map((one) => one.setting.id)) + 1;
      const n =
        Math.max(
          0,
          ...stored.map((one) =>
            Number(/^v(\d+)$/.exec(one.setting.name)?.[1] ?? 0),
          ),
        ) + 1;
      const name = `v${n}`;
      const setting: Setting = {
        schemaVersion: 'greenwash.ai-setting@3',
        id,
        name,
        title: title.trim(),
        status: 'testing',
        createdAt: '2026-10-20T09:30:00+09:00',
        createdBy: { id: 7, name: '지어낸 관리자' },
        memo,
        evalPromptSha256: SHA(id),
        criteria: {
          ...criteria,
          version: name,
          rows: criteria.rows.map((row) => ({ ...row, text: row.text.trim() })),
        },
        terms:
          terms === null ? null : (
            terms.map((term) => ({
              text: term.text.trim(),
              enabled: term.enabled,
            }))
          ),
      };
      stored.push({ setting, ever: false });
      return json(201, setting);
    }
    if (key === `PUT ${LIST_PATH}/applied`) {
      const { id } = body as { id: number | null };
      if (id !== null && !stored.some((one) => one.setting.id === id))
        return refusal(404, 'NOT_FOUND');
      if (id !== appliedId) {
        for (const one of stored) if (one.setting.id === id) one.ever = true;
        appliedId = id;
      }
      return json(200, listOf(20, 0));
    }
    const one = ONE.exec(url.pathname.slice(new URL(baseUrl).pathname.length));
    if (key.startsWith('GET ') && one) {
      if (!/^\d+$/.test(one[1]!)) return refusal(422, 'VALIDATION_ERROR');
      const found = current().find((setting) => setting.id === Number(one[1]));
      return found ? json(200, found) : refusal(404, 'NOT_FOUND');
    }
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) =>
    /^\/ai-settings\/greenwash(\/[^/]+)?$/.test(pathOf(request));

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(request);
    const key = `${request.method} ${path}`;
    const text = await request.clone().text();
    const body: unknown = text === '' ? undefined : JSON.parse(text);
    calls.push({ method: request.method, path, query: url.searchParams, body });
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(key, url, body);
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  /** 그 경로로 나간 본문들(차례대로). */
  const bodies = (key: string) =>
    calls
      .filter((call) => `${call.method} ${call.path}` === key)
      .map((call) => call.body);

  return {
    send,
    handles,
    calls,
    count,
    bodies,
    override,
    /** 지금 저장 판(새 것 먼저, 상태는 센 값). */
    settings: current,
    get appliedId() {
      return appliedId;
    },
  };
}
