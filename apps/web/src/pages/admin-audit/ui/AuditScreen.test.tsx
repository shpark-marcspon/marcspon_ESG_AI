// @vitest-environment jsdom
// AD-05 감사 기록 화면(밴드 AD2 ①, 실서버 AD5R ②). 진짜 어댑터(createAuditServerPort + createApi)에 가짜 감사 서버를 물리고 고정 시계로 본다.
//   ① 틀: 제목·설명·안내 띠, 예시 데이터 띠·바닥글 없음, 줄(시각·사람·행동 배지·대상·결과), 대체 사람 글은 회색, 건수 = 서버 count
//   ② 거르기 → 요청 URL: 처음(이번 주), 검색(멈춘 뒤 300ms·공백만은 요청 없음), 사람·행동·기간, 바꾸면 offset 0, 늦은 답은 버림
//   ③ 더 보기: offset 50, 이어 붙임, 다 받으면 단추 없음, 실패는 줄 유지·한 줄 글
//   ④ 링크: 「계정」 → onOpen, href 는 hrefOf
//   ⑤ 불러오기·실패: 300ms 뒤 스켈레톤, 실패 상자 [다시 시도] → 줄·행위자 둘 다 다시, 행위자만 실패해도 실패 상자
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { createAuditServerPort } from '../../../entities/audit-log/api/index.ts';
import {
  fakeActor,
  fakeAuditRow,
  fakeAuditServer,
  json,
  refusal,
} from '../../../entities/audit-log/api/testing.ts';
import { AUDIT_TEXT } from '../../../entities/audit-log/config/text.ts';
import type {
  AuditActorRow,
  AuditEventRow,
  AuditLink,
} from '../../../entities/audit-log/model/index.ts';
import { RUN_LOG_TEXT } from '../../../entities/run-log/config/text.ts';
import { createApi } from '../../../shared/api/index.ts';
import { AuditScreen } from './AuditScreen.tsx';

afterEach(cleanup);
vi.setConfig({ testTimeout: 15_000 });

beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

const words = AUDIT_TEXT;
const BASE = 'http://test.local/api';
/** 고정 시계: KST 2026-10-15(목) 12:00 — 이번 주 = 10-12 ~ 10-15. */
const NOW = new Date('2026-10-15T03:00:00Z');
const WEEK = { dateFrom: '2026-10-12', dateTo: '2026-10-15' };

/** 지어낸 줄 다섯(새 것 먼저 — 서버 차례). at 은 서버 꼴(+09:00). */
const ROWS: AuditEventRow[] = [
  fakeAuditRow(5, {
    at: '2026-10-15T16:02:00+09:00',
    actorKind: 'admin',
    actorUserId: 1,
    actorName: '운영 관리자 가',
    actorUsername: 'ops.ga',
    companyId: null,
    action: 'setting_change',
    event: 'user_created',
    targetKind: 'user',
    targetId: 12,
    targetLabel: 'user12',
  }),
  fakeAuditRow(4, {
    at: '2026-10-15T15:41:00+09:00',
    action: 'upload',
    event: 'document_uploaded',
    targetKind: 'document',
    targetId: 3,
    targetLabel: '보고서_예시.pdf',
  }),
  fakeAuditRow(3, {
    at: '2026-10-15T14:20:00+09:00',
    actorUserId: 13,
    actorName: '담당자 나',
    actorUsername: 'user13',
    event: 'login_failed',
    result: 'failure',
    reason: 'wrong_password',
  }),
  fakeAuditRow(2, {
    at: '2026-10-14T09:00:00+09:00',
    actorKind: 'anonymous',
    actorUserId: null,
    actorName: null,
    actorUsername: null,
    companyId: null,
    event: 'login_failed',
    result: 'failure',
    reason: 'unknown_user',
  }),
  fakeAuditRow(1, {
    at: '2026-10-13T09:00:00+09:00',
    actorKind: 'command',
    actorUserId: null,
    actorName: null,
    actorUsername: null,
    action: 'setting_change',
    event: 'password_reset',
    targetKind: 'user',
    targetId: 11,
    targetLabel: 'user11',
  }),
];
const ACTORS: AuditActorRow[] = [
  fakeActor(13, { actorName: '담당자 나', actorUsername: 'user13' }),
  fakeActor(1, {
    actorKind: 'admin',
    actorName: '운영 관리자 가',
    actorUsername: 'ops.ga',
  }),
  fakeActor(11, { actorName: '담당자 가', actorUsername: 'user11' }),
  fakeActor(20, { actorName: null, actorUsername: null }),
];

type FakeServer = ReturnType<typeof fakeAuditServer>;

/** prepare 는 그리기 전에 가짜 서버를 손본다(첫 요청의 답을 바꿀 때). */
function setup(
  rows = ROWS,
  actors = ACTORS,
  prepare: (server: FakeServer) => void = () => {},
) {
  const server = fakeAuditServer(rows, actors, { baseUrl: BASE });
  prepare(server);
  const port = createAuditServerPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  const onOpen = vi.fn<(link: AuditLink) => void>();
  render(
    <AuditScreen
      port={port}
      now={() => NOW}
      hrefOf={() => '/admin/accounts'}
      onOpen={onOpen}
    />,
  );
  return { server, onOpen };
}

const rowIds = () =>
  [...document.querySelectorAll('tbody tr[data-audit-id]')].map((row) =>
    row.getAttribute('data-audit-id'),
  );
const cellsOf = (id: string) =>
  [
    ...document.querySelectorAll(`tr[data-audit-id="${id}"] td`),
  ] as HTMLElement[];
const count = () => screen.getByTestId('count').textContent;
const loaded = () => waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

/** 고르기 칸(키트 dropdown-menu)을 열고 값 하나를 고른다. */
function choose(name: string, option: string) {
  fireEvent.keyDown(screen.getByRole('button', { name }), { key: 'Enter' });
  fireEvent.click(screen.getByRole('menuitemradio', { name: option }));
}
const type = (value: string) =>
  fireEvent.change(screen.getByLabelText(words.searchLabel), {
    target: { value },
  });

/** 답을 붙잡아 두는 override(풀면 그때 가짜 서버의 답). */
function hold(server: FakeServer, key: string) {
  let release!: (response: Response) => void;
  const held = new Promise<Response>((done) => (release = done));
  const answers = server.override[key];
  server.override[key] = [
    () => held,
    ...(Array.isArray(answers) ? answers : []),
  ];
  return release;
}

describe('AD-05 ① 틀과 줄', () => {
  it('제목·설명·새 안내 띠·표 머리, 예시 데이터 띠와 바닥글은 없다', async () => {
    setup();
    await loaded();
    expect(
      document.querySelector('[data-screen="admin-audit"]'),
    ).not.toBeNull();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      words.title,
    );
    expect(screen.getByText(words.description)).toBeTruthy();
    expect(screen.getByText(words.notice)).toBeTruthy();
    expect(screen.queryByTestId('mock-band')).toBeNull();
    expect(screen.queryByText('이름과 숫자는 모두 지어낸 예시예요')).toBeNull();
    expect(screen.queryByText(/예시 데이터예요/)).toBeNull();
    expect(
      screen.getAllByRole('columnheader').map((cell) => cell.textContent),
    ).toEqual(Object.values(words.columns));
  });

  it('줄은 서버 값 그대로(차례·시각·사람·행동·대상·결과), 건수는 서버 count', async () => {
    setup();
    await loaded();
    expect(rowIds()).toEqual(['5', '4', '3', '2', '1']);
    expect(count()).toBe('5건');
    const text = (id: string) => cellsOf(id).map((cell) => cell.textContent);
    expect(text('5')).toEqual([
      '2026-10-15 16:02',
      '운영 관리자 가',
      '설정 변경',
      '계정 · user12 만듦',
      '성공',
    ]);
    expect(text('4')).toEqual([
      '2026-10-15 15:41',
      '담당자 가',
      '업로드',
      '보고서_예시.pdf',
      '성공',
    ]);
    expect(text('3')).toEqual([
      '2026-10-15 14:20',
      '담당자 나',
      '로그인',
      words.noTarget,
      '실패 · 비밀번호 틀림',
    ]);
    expect(text('2')).toEqual([
      '2026-10-14 09:00',
      '없는 아이디',
      '로그인',
      words.noTarget,
      '실패 · 없는 아이디',
    ]);
    expect(text('1')[1]).toBe('관리 명령');
    expect(text('1')[3]).toBe('계정 · user11 비밀번호 초기화');
    const badge = (id: string) =>
      document.querySelector(`tr[data-audit-id="${id}"] [data-action]`)!;
    expect(badge('5').className).toContain('support-orange');
    expect(badge('4').className).toContain('bg-background-tertiary');
    expect(
      document.querySelector('tr[data-audit-id="3"] [data-failure]')!.className,
    ).toContain('text-support-error-accent');
  });

  it('사람을 찾지 못한 줄의 대체 글은 회색, 이름은 회색이 아니다', async () => {
    setup();
    await loaded();
    for (const id of ['1', '2']) {
      expect(cellsOf(id)[1]!.className, id).toContain('text-text-tertiary');
      expect(cellsOf(id)[1]!.hasAttribute('data-actor-missing')).toBe(true);
    }
    expect(cellsOf('3')[1]!.className).not.toContain('text-text-tertiary');
  });

  it('건수 「{n}건」 은 실린 줄 수가 아니라 서버 count', async () => {
    const { server } = setup();
    server.override['GET /audit-logs'] = () =>
      json(200, { count: 37, isNext: false, results: ROWS.slice(0, 2) });
    type('x');
    await waitFor(() => expect(count()).toBe('37건'));
    expect(rowIds()).toHaveLength(2);
  });
});

describe('AD-05 ② 거르기 → 요청 URL', () => {
  it('처음: 줄 한 번(이번 주, 쿼리는 날짜 둘·limit 50·offset 0)과 행위자 한 번', async () => {
    const { server } = setup();
    await loaded();
    expect(server.count('GET /audit-logs')).toBe(1);
    expect(server.count('GET /audit-logs/actors')).toBe(1);
    expect(server.listQueries()).toEqual([
      { ...WEEK, limit: '50', offset: '0' },
    ]);
  });

  it('검색: 멈춘 뒤 300ms 에 한 번(그 안의 두 글자는 요청 하나), 앞뒤 빈칸은 걷고, 입력은 150자', async () => {
    const { server } = setup();
    await loaded();
    expect(
      screen.getByLabelText(words.searchLabel).getAttribute('maxLength'),
    ).toBe('150');
    vi.useFakeTimers();
    try {
      type('k');
      type(' ki ');
      await act(() => vi.advanceTimersByTimeAsync(299));
      expect(server.count('GET /audit-logs')).toBe(1);
      await act(() => vi.advanceTimersByTimeAsync(1));
      expect(server.count('GET /audit-logs')).toBe(2);
      expect(server.listQueries()[1]).toEqual({
        ...WEEK,
        q: 'ki',
        limit: '50',
        offset: '0',
      });
      await act(() => vi.advanceTimersByTimeAsync(1_000));
      expect(server.count('GET /audit-logs')).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('공백만 든 검색은 요청을 내지 않고(쿼리가 같다), 그 뒤 거르기를 바꾼 요청에도 q 가 없다', async () => {
    const { server } = setup();
    await loaded();
    vi.useFakeTimers();
    try {
      type('   ');
      await act(() => vi.advanceTimersByTimeAsync(1_000));
      expect(server.count('GET /audit-logs')).toBe(1);
    } finally {
      vi.useRealTimers();
    }
    choose(words.action.name, words.actions.login);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(2));
    expect(server.calls.at(-1)!.query.has('q')).toBe(false);
    expect(server.calls.at(-1)!.query.get('action')).toBe('login');
  });

  it('사람 → actorUserId, 행동 「설정 변경」 → action=setting_change, 기간 「전체」 → 날짜 키 없음. 거르기를 바꿔도 행위자는 다시 부르지 않는다', async () => {
    const { server } = setup();
    await loaded();
    choose(words.actor.name, '담당자 나');
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(2));
    expect(server.listQueries()[1]).toEqual({
      ...WEEK,
      actorUserId: '13',
      limit: '50',
      offset: '0',
    });
    expect(
      screen.getByRole('button', { name: words.actor.name }).textContent,
    ).toBe('사람: 담당자 나');
    choose(words.action.name, words.actions.setting_change);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(3));
    expect(server.listQueries()[2]!.action).toBe('setting_change');
    choose(words.period.name, words.period.options.all);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(4));
    expect(server.listQueries()[3]).toEqual({
      actorUserId: '13',
      action: 'setting_change',
      limit: '50',
      offset: '0',
    });
    choose(words.period.name, words.period.options.month);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(5));
    expect(server.listQueries()[4]!.dateFrom).toBe('2026-10-01');
    expect(server.count('GET /audit-logs/actors')).toBe(1);
  });

  it('사람 고르기: 「전체」 + 행위자 목록(이름 차례, 운영 관리자 꼬리, 못 찾은 사람 맨 뒤). 행동: 「전체」 + 아홉', async () => {
    setup();
    await loaded();
    fireEvent.keyDown(screen.getByRole('button', { name: words.actor.name }), {
      key: 'Enter',
    });
    expect(
      screen.getAllByRole('menuitemradio').map((item) => item.textContent),
    ).toEqual([
      '전체',
      '담당자 가',
      '담당자 나',
      '운영 관리자 가 · 운영 관리자',
      '알 수 없는 사람',
    ]);
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
    fireEvent.keyDown(screen.getByRole('button', { name: words.action.name }), {
      key: 'Enter',
    });
    expect(
      screen.getAllByRole('menuitemradio').map((item) => item.textContent),
    ).toEqual(['전체', ...Object.values(words.actions)]);
  });

  it('늦은 답은 버린다: 첫 거르기의 답을 붙잡고 다시 바꾸면, 둘째 답 뒤에 첫 답이 와도 화면은 둘째 값', async () => {
    const { server } = setup();
    await loaded();
    const releaseFirst = hold(server, 'GET /audit-logs');
    choose(words.action.name, words.actions.upload);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(2));
    server.override['GET /audit-logs'] = () =>
      json(200, { count: 1, isNext: false, results: [ROWS[1]] });
    choose(words.action.name, words.actions.login);
    await waitFor(() => expect(rowIds()).toEqual(['4']));
    releaseFirst(
      json(200, { count: 2, isNext: false, results: [ROWS[0], ROWS[2]] }),
    );
    await new Promise((done) => setTimeout(done, 50));
    expect(rowIds()).toEqual(['4']);
    expect(count()).toBe('1건');
  });

  // 0건 꼴(디자인 원문 2): 기간만 걸렸으면 빈 상태, 검색·사람·행동이 걸렸으면 「조건에 맞는 기록이 없어요」 + [거르기 풀기].
  const empty = () => screen.queryByTestId('empty');
  const clearButton = () =>
    screen.queryByRole('button', { name: words.clearFilter });

  it('0건 · 기간만(이번 주): 「이번 주 기록이 없어요」·「기간을 넓혀 보세요.」, [거르기 풀기]·「조건에 맞는…」 없음', async () => {
    setup([], ACTORS);
    await waitFor(() => expect(empty()).not.toBeNull());
    expect(count()).toBe('0건');
    expect(
      [...empty()!.querySelectorAll('p')].map((line) => line.textContent),
    ).toEqual([
      words.emptyPeriod(words.period.options.week),
      words.widenPeriod,
    ]);
    expect(empty()!.textContent).toBe(
      '이번 주 기록이 없어요기간을 넓혀 보세요.',
    );
    expect(clearButton()).toBeNull();
    expect(screen.queryByText(words.noMatch)).toBeNull();
  });

  it('0건 · 기간 「전체」: 「아직 기록이 없어요」 한 줄, 보조 줄·[거르기 풀기] 없음', async () => {
    const { server } = setup([], ACTORS);
    await waitFor(() => expect(empty()).not.toBeNull());
    choose(words.period.name, words.period.options.all);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(2));
    await waitFor(() => expect(empty()!.textContent).toBe(words.emptyAll));
    expect(empty()!.querySelectorAll('p')).toHaveLength(1);
    expect(clearButton()).toBeNull();
  });

  it('0건 · 사람을 고른 뒤: 「조건에 맞는 기록이 없어요」·[거르기 풀기] → 검색·사람·행동을 비우고 기간 전체로(그 뒤는 「아직 기록이 없어요」)', async () => {
    const { server } = setup([], ACTORS);
    await waitFor(() => expect(empty()).not.toBeNull());
    choose(words.actor.name, '담당자 나');
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(2));
    await waitFor(() => expect(screen.getByText(words.noMatch)).toBeTruthy());
    expect(empty()).toBeNull();
    fireEvent.click(clearButton()!);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(3));
    expect(server.listQueries()[2]).toEqual({ limit: '50', offset: '0' });
    await waitFor(() => expect(empty()?.textContent).toBe(words.emptyAll));
    expect(clearButton()).toBeNull();
  });
});

describe('AD-05 ③ 더 보기', () => {
  const many = Array.from({ length: 53 }, (_, i) =>
    fakeAuditRow(53 - i, { at: '2026-10-15T09:00:00+09:00' }),
  );

  it('「53건 중 50건」 → [더 보기] → offset 50, 줄이 이어 붙고, 다 받으면 단추 없이 「53건」', async () => {
    const { server } = setup(many);
    await loaded();
    expect(rowIds()).toHaveLength(50);
    expect(count()).toBe('53건 중 50건');
    fireEvent.click(screen.getByRole('button', { name: words.more }));
    await waitFor(() => expect(rowIds()).toHaveLength(53));
    expect(server.listQueries()[1]).toEqual({
      ...WEEK,
      limit: '50',
      offset: '50',
    });
    expect(rowIds().slice(48)).toEqual(['5', '4', '3', '2', '1']);
    expect(count()).toBe('53건');
    expect(screen.queryByRole('button', { name: words.more })).toBeNull();
  });

  it('더 보기 실패: 줄은 그대로, 「기록을 더 불러오지 못했어요」 + [다시 시도] → 이어 붙음', async () => {
    const { server } = setup(many);
    await loaded();
    server.override['GET /audit-logs'] = [() => refusal(500, 'INTERNAL')];
    fireEvent.click(screen.getByRole('button', { name: words.more }));
    const more = await screen.findByTestId('more');
    await waitFor(() =>
      expect(within(more).getByText(words.moreFailed)).toBeTruthy(),
    );
    expect(rowIds()).toHaveLength(50);
    expect(screen.queryByTestId('load-failure')).toBeNull();
    fireEvent.click(within(more).getByRole('button', { name: words.retry }));
    await waitFor(() => expect(rowIds()).toHaveLength(53));
    expect(server.listQueries().map((query) => query.offset)).toEqual([
      '0',
      '50',
      '50',
    ]);
  });

  it('더 보기 뒤 거르기를 바꾸면 offset 0 부터 다시', async () => {
    const { server } = setup(many);
    await loaded();
    fireEvent.click(screen.getByRole('button', { name: words.more }));
    await waitFor(() => expect(rowIds()).toHaveLength(53));
    choose(words.action.name, words.actions.run);
    await waitFor(() => expect(server.count('GET /audit-logs')).toBe(3));
    expect(server.listQueries()[2]!.offset).toBe('0');
    await waitFor(() => expect(rowIds()).toHaveLength(50));
  });

  it('불러오는 동안 두 번 눌러도 요청은 하나', async () => {
    const { server } = setup(many);
    await loaded();
    const release = hold(server, 'GET /audit-logs');
    const button = screen.getByRole('button', { name: words.more });
    fireEvent.click(button);
    fireEvent.click(button);
    await new Promise((done) => setTimeout(done, 20));
    expect(server.count('GET /audit-logs')).toBe(2);
    release(json(200, { count: 53, isNext: false, results: many.slice(50) }));
    await waitFor(() => expect(rowIds()).toHaveLength(53));
  });
});

describe('AD-05 ④ 링크', () => {
  it('「계정」 → onOpen(accounts), href 는 hrefOf. 새 탭 누름은 가로채지 않는다. 그 밖 토막은 링크가 아니다', async () => {
    const { onOpen } = setup();
    await loaded();
    const links = screen.getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(['계정', '계정']);
    expect(links[0]!.getAttribute('href')).toBe('/admin/accounts');
    fireEvent.click(links[0]!);
    expect(onOpen).toHaveBeenLastCalledWith({ kind: 'accounts' });
    fireEvent.click(links[0]!, { ctrlKey: true });
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});

describe('AD-05 ⑤ 불러오기·실패', () => {
  it('300ms 안에는 아무것도, 뒤에는 aria-busy 스켈레톤', async () => {
    vi.useFakeTimers();
    try {
      let release!: (response: Response) => void;
      setup(ROWS, ACTORS, (server) => {
        release = hold(server, 'GET /audit-logs');
      });
      const table = screen.getByRole('table', { name: words.tableLabel });
      expect(table.getAttribute('aria-busy')).toBeNull();
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(table.getAttribute('aria-busy')).toBe('true');
      expect(screen.getByRole('status').textContent).toBe(words.loading);
      await act(async () => {
        release(json(200, { count: 5, isNext: false, results: ROWS }));
        await vi.advanceTimersByTimeAsync(10);
      });
      expect(table.getAttribute('aria-busy')).toBeNull();
      expect(rowIds()).toHaveLength(5);
    } finally {
      vi.useRealTimers();
    }
  });

  it('줄 실패 → 「감사 기록을 불러오지 못했어요」 + [다시 시도] → 줄·행위자 둘 다 다시. 실패 동안 건수 글 없음', async () => {
    const { server } = setup(ROWS, ACTORS, (fake) => {
      fake.override['GET /audit-logs'] = [
        () => refusal(422, 'VALIDATION_ERROR'),
      ];
    });
    const failure = await screen.findByTestId('load-failure');
    expect(within(failure).getByText(words.failed)).toBeTruthy();
    expect(screen.queryByTestId('count')).toBeNull();
    fireEvent.click(within(failure).getByRole('button', { name: words.retry }));
    await loaded();
    expect(server.count('GET /audit-logs')).toBe(2);
    expect(server.count('GET /audit-logs/actors')).toBe(2);
  });

  it('행위자만 실패해도 실패 상자 하나(「둘로만」)', async () => {
    setup(ROWS, ACTORS, (server) => {
      server.override['GET /audit-logs/actors'] = [
        () => refusal(403, 'FORBIDDEN'),
      ];
    });
    expect(await screen.findByTestId('load-failure')).toBeTruthy();
    expect(rowIds()).toEqual([]);
  });

  it('연결 끊김(던짐)도 실패 상자', async () => {
    setup(ROWS, ACTORS, (server) => {
      server.override['GET /audit-logs'] = () => {
        throw new TypeError('끊김');
      };
    });
    expect(await screen.findByTestId('load-failure')).toBeTruthy();
  });
});

describe('AD-05 ⑥ 표 줄 꼴(밴드 DT1 C15)', () => {
  it('표 칸은 줄 56(h-14) — 48 아님', async () => {
    setup();
    await loaded();
    const cells = cellsOf(rowIds()[0]!);
    expect(cells.length).toBeGreaterThan(0);
    for (const cell of cells) {
      expect(cell.className).toContain('h-14');
      expect(cell.className).not.toMatch(/\bh-12\b/);
    }
  });
});

describe('AD-05 ⑦ AI 설정 줄(밴드 AD4X ③)', () => {
  it('「AI 설정」 → onOpen(ai-settings, v3), href 는 hrefOf(link). 대상 글 「AI 설정 · 그린워싱 · v3 만듦」·기본 판 적용은 판 없이', async () => {
    const server = fakeAuditServer(
      [
        fakeAuditRow(2, {
          action: 'setting_change',
          event: 'ai_setting_created',
          targetKind: 'ai_setting',
          targetId: 3,
          targetLabel: 'v3',
          module: 'greenwash',
        }),
        fakeAuditRow(1, {
          action: 'setting_change',
          event: 'ai_setting_applied',
          targetKind: 'ai_setting',
          targetId: null,
          targetLabel: 'colab-2026-01-15-v1',
          module: 'greenwash',
        }),
      ],
      ACTORS,
      { baseUrl: BASE },
    );
    const port = createAuditServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    const onOpen = vi.fn<(link: AuditLink) => void>();
    const hrefOf = (link: AuditLink) =>
      link.kind === 'ai-settings' ?
        `/ai?version=${link.version ?? ''}`
      : '/accounts';
    render(
      <AuditScreen
        port={port}
        now={() => NOW}
        hrefOf={hrefOf}
        onOpen={onOpen}
      />,
    );
    await loaded();
    expect(cellsOf('2')[3]!.textContent).toBe('AI 설정 · 그린워싱 · v3 만듦');
    expect(cellsOf('1')[3]!.textContent).toBe(
      'AI 설정 · 그린워싱 · 기본 설정 적용',
    );
    const links = screen.getAllByRole('link', { name: 'AI 설정' });
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/ai?version=v3',
      '/ai?version=',
    ]);
    fireEvent.click(links[0]!);
    expect(onOpen).toHaveBeenLastCalledWith({
      kind: 'ai-settings',
      module: 'greenwash',
      version: 'v3',
    });
    fireEvent.click(links[1]!);
    expect(onOpen).toHaveBeenLastCalledWith({
      kind: 'ai-settings',
      module: 'greenwash',
      version: null,
    });
  });

  it('모듈 이름 표는 실행 기록 문구 표와 같다(entities 끼리 가져오지 않는 사본)', () => {
    expect(AUDIT_TEXT.entry.modules).toEqual(RUN_LOG_TEXT.modules);
  });
});

describe('AD-05 ⑧ 첫 불러오기 자리(밴드 LD1, sid:MARC-ENT-443)', () => {
  it('받기 전: 첫 그림부터 몸 줄 5, 빈 상태 0 — 받으면 빈 상태', async () => {
    let release!: (response: Response) => void;
    setup([], ACTORS, (server) => {
      release = hold(server, 'GET /audit-logs');
    });
    const skeletonRows = () =>
      document.querySelectorAll('tbody tr[data-skeleton-row]');
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByTestId('empty')).toBeNull();
    await new Promise((done) => setTimeout(done, 400));
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByTestId('empty')).toBeNull();
    await act(async () => {
      release(json(200, { count: 0, isNext: false, results: [] }));
    });
    expect(await screen.findByTestId('empty')).toBeTruthy();
    expect(skeletonRows()).toHaveLength(0);
  });

  // 밴드 DT1 ②(J3, sid:MARC-ISSUE-374): 옛 머리 칸 w-40·w-28 을 colgroup 으로(값 그대로).
  it('열 폭: table-fixed · col 수 = 머리 칸 수 · 로딩과 받은 뒤 같은 col 폭', async () => {
    let release!: (response: Response) => void;
    setup([], ACTORS, (server) => {
      release = hold(server, 'GET /audit-logs');
    });
    const cols = () =>
      [...document.querySelectorAll('table colgroup > col')].map(
        (col) => (col as HTMLElement).style.width,
      );
    const table = screen.getByRole('table');
    expect(table.className.split(/\s+/)).toContain('table-fixed');
    expect(cols()).toHaveLength(table.querySelectorAll('thead th').length);
    const loading = cols();
    expect(loading).toEqual(['160px', '112px', '112px', '', '160px']);
    await act(async () => {
      release(json(200, { count: 0, isNext: false, results: [] }));
    });
    expect(await screen.findByTestId('empty')).toBeTruthy();
    expect(cols()).toEqual(loading);
  });
});
