// e2e 의 그린워싱 AI 설정 흉내 서버(밴드 AD2R). /api/ai-settings/greenwash 다섯 경로를 page.route 로 채운다. 답의 값은 전부 지어낸 것이다
// (서버 criteria-default.json·코랩 원문을 옮기지 않는다). 서버 규칙대로 돈다: 목록은 새 것 먼저·limit·offset, 상태는 적용 여부에서 셈,
// POST 는 새 판(id·이름 v<n> 매김, criteria.version 을 그 이름으로 덮음, 상태 시험 중), PUT /applied 는 적용 판 바꿈(null = 기본 판).
//   - 받은 요청을 calls 에 적는다(메서드·URL·본문).
//   - gatePost(밴드 AD2S): POST 를 붙잡는다 — postArrived() 로 닿기를 기다리고 releasePost('ok' | 'fail') 로 푼다(fail = 500). 없으면 즉답.
//   - AS3b ①: 기본 단어 목록 GET /api/greenwash/terms/default(DEFAULT_TERMS — 지어낸 낱말)도 채운다. 그 요청은 calls 에 섞지 않고 termCalls 에 따로 센다.
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다.
import type { Page, Route } from '@playwright/test';

const IDS = [
  'keyword-ghg',
  'keyword-exclusion',
  'evidence-quantity',
  'evidence-baseline',
  'evidence-boundary',
  'evidence-offset',
  'high-1',
  'high-2',
  'high-3',
  'high-4',
  'mid-1',
  'exception-1',
  'exception-2',
  'exception-3',
  'exception-4',
] as const;
const CATEGORY = (id: string) =>
  id.startsWith('keyword') ? 'targetKeyword'
  : id.startsWith('evidence') ? 'coreEvidence'
  : id.startsWith('high') ? 'high'
  : id.startsWith('mid') ? 'mid'
  : 'exception';
const VERDICT = {
  targetKeyword: 'coreEvidenceApplies',
  coreEvidence: 'highIfMissing',
  high: 'High',
  mid: 'Mid',
  exception: 'NonRisk',
} as const;

export interface FakeRow {
  id: (typeof IDS)[number];
  category: string;
  order: number;
  enabled: boolean;
  text: string;
  terms: string[] | null;
  verdict: string;
  guideline: { text: string; status: 'draft' | 'confirmed' } | null;
}
export interface FakeCriteria {
  schemaVersion: 'greenwash.criteria@1';
  version: string;
  rows: FakeRow[];
}

/** 지어낸 기준표(15줄). high2 는 판마다 다른 High 2 글. */
export function criteria(version: string, high2: string): FakeCriteria {
  return {
    schemaVersion: 'greenwash.criteria@1',
    version,
    rows: IDS.map((id, index) => {
      const category = CATEGORY(id);
      const keyword = category === 'targetKeyword';
      return {
        id,
        category,
        order: index + 1,
        enabled: true,
        text:
          id === 'high-2' ? high2
          : keyword ? `지어낸 묶음 ${index + 1}`
          : `지어낸 ${id} 기준 글`,
        terms:
          id === 'keyword-ghg' ? ['지어낸말 하나', '지어낸말 둘', '지어낸말 셋']
          : id === 'keyword-exclusion' ? ['지어낸말 넷', '지어낸말 다섯']
          : null,
        verdict: VERDICT[category],
        guideline: keyword ? null : { text: '지어낸 기관', status: 'draft' },
      };
    }),
  };
}

interface Stored {
  id: number;
  name: string;
  title: string | null;
  createdAt: string;
  author: string | null;
  memo: string;
  criteria: FakeCriteria;
  /** 대상 단어(G2d — null = 코드 기본 목록). */
  terms: { text: string; enabled: boolean }[] | null;
  ever: boolean;
}

const DEFAULT_NAME = 'colab-2026-01-15-v1';
const DEFAULT_TITLE = '기본 설정';
const SHA = (n: number) => String(n).padStart(64, '0');

const answer = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

export interface FakeSettingCall {
  method: string;
  url: URL;
  body: unknown;
}

/** 기본 단어 목록(GET /api/greenwash/terms/default — 지어낸 낱말, 서버 GREEN_TERMS 를 옮기지 않는다). */
export const DEFAULT_TERMS = [
  '지어낸 기본 단어 하나',
  '지어낸 기본 단어 둘',
  '지어낸 기본 단어 셋',
];

/** 판 셋(13 v3 시험 중 · 12 v2 적용 중 · 11 v1 지난 버전)과 기본 판으로 시작한다. */
export async function fakeAiSettingApi(page: Page, { gatePost = false } = {}) {
  const calls: FakeSettingCall[] = [];
  const termCalls: URL[] = [];
  const heldPosts: ((how: 'ok' | 'fail') => void)[] = [];
  const arrivals: (() => void)[] = [];
  const stored: Stored[] = [
    {
      id: 11,
      name: 'v1',
      title: null,
      createdAt: '2026-10-17T09:00:00+09:00',
      author: null,
      memo: '',
      criteria: criteria('v1', '지어낸 v1 High 둘 글'),
      terms: null,
      ever: true,
    },
    {
      id: 12,
      name: 'v2',
      title: '지어낸 판 둘',
      createdAt: '2026-10-18T10:20:00+09:00',
      author: '지어낸 관리자',
      memo: '지어낸 메모 둘',
      criteria: criteria('v2', '지어낸 v2 High 둘 글'),
      terms: null,
      ever: true,
    },
    {
      id: 13,
      name: 'v3',
      title: '지어낸 판 셋',
      createdAt: '2026-10-19T11:40:00+09:00',
      author: '지어낸 관리자',
      memo: '지어낸 메모 셋',
      criteria: criteria('v3', '지어낸 v3 High 둘 글'),
      terms: [
        { text: '지어낸 초록낱말', enabled: true },
        { text: '친환경', enabled: false },
      ],
      ever: false,
    },
  ];
  let applied: number | null = 12;

  const status = (one: Stored) =>
    one.id === applied ? 'applied'
    : one.ever ? 'past'
    : 'testing';
  const summary = (one: Stored) => ({
    id: one.id,
    name: one.name,
    title: one.title,
    status: status(one),
    createdAt: one.createdAt,
    createdBy: { id: 7, name: one.author },
    memo: one.memo,
    evalPromptSha256: SHA(one.id),
  });
  const full = (one: Stored) => ({
    schemaVersion: 'greenwash.ai-setting@3',
    ...summary(one),
    criteria: one.criteria,
    terms: one.terms,
  });
  const list = (limit: number, offset: number) => {
    const all = [...stored].sort((a, b) => b.id - a.id);
    return {
      schemaVersion: 'greenwash.ai-settings@2',
      companyId: 1,
      applied:
        applied === null ? { kind: 'default' } : { kind: 'saved', id: applied },
      default: {
        name: DEFAULT_NAME,
        title: DEFAULT_TITLE,
        evalPromptSha256: SHA(0),
      },
      items: all.slice(offset, offset + limit).map(summary),
      total: all.length,
    };
  };

  await page.route(
    /\/api\/ai-settings\/greenwash(\/[^/?]+)?(\?.*)?$/,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const raw = request.postData();
      const body: unknown = raw ? JSON.parse(raw) : undefined;
      calls.push({ method: request.method(), url, body });
      const tail = url.pathname.replace(/^\/api\/ai-settings\/greenwash/, '');
      if (request.method() === 'GET' && tail === '') {
        const limit = Number(url.searchParams.get('limit') ?? 20);
        const offset = Number(url.searchParams.get('offset') ?? 0);
        return answer(route, 200, list(limit, offset));
      }
      if (request.method() === 'GET' && tail === '/default')
        return answer(route, 200, {
          schemaVersion: 'greenwash.ai-setting-default@3',
          name: DEFAULT_NAME,
          title: DEFAULT_TITLE,
          criteria: criteria(DEFAULT_NAME, '지어낸 기본 판 High 둘 글'),
          evalPromptSha256: SHA(0),
          terms: null,
        });
      if (request.method() === 'POST' && tail === '') {
        if (gatePost) {
          const how = await new Promise<'ok' | 'fail'>((done) => {
            heldPosts.push(done);
            for (const arrived of arrivals.splice(0)) arrived();
          });
          if (how === 'fail')
            return answer(route, 500, {
              error: {
                code: 'INTERNAL_ERROR',
                message: '지어낸-500',
                fields: null,
              },
            });
        }
        const given = body as {
          title: string;
          criteria: FakeCriteria;
          memo?: string;
          terms?: Stored['terms'];
        };
        const id = Math.max(...stored.map((one) => one.id)) + 1;
        const name = `v${stored.length + 1}`;
        const one: Stored = {
          id,
          name,
          title: given.title.trim(),
          createdAt: '2026-10-20T09:30:00+09:00',
          author: '지어낸 관리자',
          memo: given.memo ?? '',
          criteria: { ...given.criteria, version: name },
          terms: given.terms ?? null,
          ever: false,
        };
        stored.push(one);
        return answer(route, 201, full(one));
      }
      if (request.method() === 'PUT' && tail === '/applied') {
        const { id } = body as { id: number | null };
        if (id !== null && !stored.some((one) => one.id === id))
          return answer(route, 404, {
            error: {
              code: 'NOT_FOUND',
              message: '지어낸-NOT_FOUND',
              fields: null,
              legacyCode: 'not_found',
            },
          });
        for (const one of stored) if (one.id === id) one.ever = true;
        applied = id;
        return answer(route, 200, list(20, 0));
      }
      const found = stored.find((one) => `/${one.id}` === tail);
      if (request.method() === 'GET' && found)
        return answer(route, 200, full(found));
      return answer(route, 404, {
        error: {
          code: 'NOT_FOUND',
          message: '지어낸-NOT_FOUND',
          fields: null,
          legacyCode: 'not_found',
        },
      });
    },
  );

  await page.route(/\/api\/greenwash\/terms\/default(\?.*)?$/, (route) => {
    termCalls.push(new URL(route.request().url()));
    return answer(route, 200, { terms: DEFAULT_TERMS });
  });

  /** 그 메서드·경로(/api 뒤)로 나간 요청들. */
  const sent = (method: string, path: string) =>
    calls.filter(
      (call) =>
        call.method === method &&
        call.url.pathname === `/api/ai-settings/greenwash${path}`,
    );
  /** 붙잡힌 POST 가 닿을 때까지(이미 있으면 바로). */
  const postArrived = () =>
    heldPosts.length > 0 ?
      Promise.resolve()
    : new Promise<void>((done) => arrivals.push(done));
  /** 가장 먼저 붙잡힌 POST 를 푼다. */
  const releasePost = (how: 'ok' | 'fail') => heldPosts.shift()?.(how);
  return { calls, termCalls, sent, postArrived, releasePost };
}
