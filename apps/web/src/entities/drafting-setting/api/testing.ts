// 시험용 가짜 원고작성 AI 설정 서버(밴드 RPA3). 시험만 쓴다(공개 표면이 아니다).
// 답의 꼴은 api-py 의 /ai-settings/drafting 경로 셋(drafting.ai-settings@1 · ai-setting@1 — RPA1)을 따른다. 값은 전부 지어낸 것이다.
// 서버 규칙을 거르지 않고 따른다(그린워싱 가짜 entities/greenwash-setting/api/testing.ts 꼴):
//   - 목록은 새 것 먼저(id 내림), limit(기본 20, 최대 100)·offset 으로 자른다. 상태는 적용 여부에서 센다(지금 적용 applied · 적용한 적 있음 past · 한 번도 testing).
//   - POST 는 새 판 하나(201): id = 가장 큰 id + 1, 이름 v<가장 큰 n + 1>. title 이 빈 글이면 422 VALIDATION_ERROR.
//   - PUT /applied: id null = 기본 판, 없는 id 404. 답은 바꾼 뒤 목록 첫 쪽(limit 20).
// Bearer 는 보지 않는다(세션 가짜 서버의 몫). prompt-model 은 받지 않는다(entities/ai-setting 의 가짜 — module 'drafting').
// override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다. 연결 끊김은 던지는 함수로).
import type { Setting, SettingList, SettingSummary } from '../model/index.ts';

export interface FakeDraftingSettingCall {
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
export const refusal = (
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  });

/** 지어낸 저장 판 둘(새 것 먼저 — v2 시험 중, v1 적용 중). */
export function fakeSettings(): Setting[] {
  return [
    {
      schemaVersion: 'drafting.ai-setting@1',
      id: 12,
      name: 'v2',
      title: '지어낸 초안 손질',
      status: 'testing',
      createdAt: '2026-10-24T10:00:00+09:00',
      createdBy: { id: 7, name: '지어낸 관리자' },
      memo: '지어낸 메모 둘',
    },
    {
      schemaVersion: 'drafting.ai-setting@1',
      id: 11,
      name: 'v1',
      title: '지어낸 첫 판',
      status: 'applied',
      createdAt: '2026-10-22T09:00:00+09:00',
      createdBy: { id: 7, name: null },
      memo: '',
    },
  ];
}

const summaryOf = (setting: Setting): SettingSummary => ({
  id: setting.id,
  name: setting.name,
  title: setting.title,
  status: setting.status,
  createdAt: setting.createdAt,
  createdBy: setting.createdBy,
  memo: setting.memo,
});

export function fakeSettingList(
  items: readonly Setting[],
  applied: SettingList['applied'],
  { total = items.length }: { total?: number } = {},
): SettingList {
  return {
    schemaVersion: 'drafting.ai-settings@1',
    companyId: 1,
    applied,
    default: { name: 'v2-code', title: '지어낸 기본 설정' },
    items: items.map(summaryOf),
    total,
  };
}

const LIST_PATH = '/ai-settings/drafting';

export function fakeDraftingSettingServer({
  settings = fakeSettings(),
  baseUrl = 'http://test.local/api',
}: { settings?: Setting[]; baseUrl?: string } = {}) {
  const calls: FakeDraftingSettingCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const stored = settings.map((setting) => ({
    setting: structuredClone(setting),
    ever: setting.status !== 'testing',
  }));
  let appliedId: number | null =
    settings.find((one) => one.status === 'applied')?.id ?? null;

  const statusOf = (one: (typeof stored)[number]): Setting['status'] =>
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

  const answer = (key: string, url: URL, body: unknown): Response => {
    if (key === `GET ${LIST_PATH}`) {
      const limit = Number(url.searchParams.get('limit') ?? 20);
      const offset = Number(url.searchParams.get('offset') ?? 0);
      return json(200, listOf(limit, offset));
    }
    if (key === `POST ${LIST_PATH}`) {
      const { title, memo = '' } = body as { title?: string; memo?: string };
      if (typeof title !== 'string' || title.trim() === '')
        return refusal(422, 'VALIDATION_ERROR');
      const id = Math.max(10, ...stored.map((one) => one.setting.id)) + 1;
      const n =
        Math.max(
          0,
          ...stored.map((one) =>
            Number(/^v(\d+)$/.exec(one.setting.name)?.[1] ?? 0),
          ),
        ) + 1;
      const setting: Setting = {
        schemaVersion: 'drafting.ai-setting@1',
        id,
        name: `v${n}`,
        title: title.trim(),
        status: 'testing',
        createdAt: '2026-10-26T09:30:00+09:00',
        createdBy: { id: 7, name: '지어낸 관리자' },
        memo,
      };
      stored.push({ setting, ever: false });
      return json(201, setting);
    }
    if (key === `PUT ${LIST_PATH}/applied`) {
      const { id } = body as { id: number | null };
      if (id !== null) {
        const one = stored.find((entry) => entry.setting.id === id);
        if (!one) return refusal(404, 'NOT_FOUND');
        one.ever = true;
      }
      appliedId = id;
      return json(200, listOf(20, 0));
    }
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때 — prompt-model 은 받지 않는다). */
  const handles = (request: Request) =>
    /^\/ai-settings\/drafting(\/applied)?$/.test(pathOf(request));

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
