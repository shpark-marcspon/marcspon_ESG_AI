// @vitest-environment jsdom
// 검증 목록 화면(밴드 DV2b — 발주서 §3). 진짜 실어댑터 + 가짜 데이터 검증 서버. 키트 Tabs(radix)는 mouseDown 으로 누른다.
//   파일명(파일 이름 · 「붙여 넣은 데이터 · 시각」 · 옛 실행 「–」) · 요약 칸(null 「–」) · 상태별 배지·단추 · 탭 → status 쿼리 ·
//   「내가 올린 것만」 → mine(운영 관리자 0) · 화면 거르기(파일명·보고연도) · 빔 → intro · 거른 빔 → [거르기 풀기] · 실패 → [다시 시도] ·
//   [다시 실행] → 새 실행 · 판에 없는 「1회차」·「(핵심 n)」 0.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  FAKE_OTHER,
  fakeDataverifyServer,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/dataverify/api/testing.ts';
import type { FakeDataverifyServer } from '../../../entities/dataverify/api/testing.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import {
  fakeInput,
  fakeResult,
  planFailed,
} from '../../../entities/dataverify/model/testing.ts';
import { ListScreen } from './ListScreen.tsx';

afterEach(cleanup);
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

const words = DV_TEXT.list;
const LIST = 'GET /dataverify/runs';
const flush = () => act(async () => {});
const FILE = 'EDK_가상데이터_2025_환경_사업장통합_최종_v3.json';

const withSource = (source: unknown, year = '2025') => {
  const input = fakeInput();
  (input.company as Record<string, unknown>).reportingYear = year;
  return { input, source };
};

function seeded() {
  const server = fakeDataverifyServer({
    runs: [
      fakeRun(11, {
        options: withSource({ kind: 'file', name: FILE }),
        createdAt: '2026-10-19T10:31:00+09:00',
        // 끝난 때는 다음 날 한국 시각 0시 30분(UTC 로는 전날) — 칸이 createdAt 이 아니고 finishedAt 의 한국 날짜인지 가른다
        finishedAt: '2026-10-19T15:30:00Z',
      }),
      fakeRun(12, {
        options: withSource({ kind: 'paste' }),
        createdAt: '2026-10-19T10:42:00+09:00',
        createdBy: FAKE_OTHER,
      }),
      fakeRun(13, {
        options: withSource({ kind: 'file', name: 'b.json' }, '2024'),
        createdAt: '2026-10-19T10:44:00+09:00',
      }),
      fakeRun(14, { createdAt: '2026-10-19T10:46:00+09:00' }),
      fakeRun(15, {
        options: withSource({ kind: 'file', name: 'c.json' }),
        createdAt: '2026-10-19T10:48:00+09:00',
      }),
    ],
  });
  server.advance(11, { status: 'done' });
  server.advance(12, {
    status: 'done',
    result: fakeResult({ plan: planFailed() }),
  });
  server.advance(13, { status: 'processing', steps: fakeSteps(2, 'running') });
  server.advance(14, { status: 'failed' });
  return server;
}

async function draw(
  server: ReturnType<typeof fakeDataverifyServer>,
  { operator = false, intro }: { operator?: boolean; intro?: string } = {},
) {
  const calls = {
    onIntro: vi.fn(),
    onNewCheck: vi.fn(),
    onViewResult: vi.fn(),
    onViewStatus: vi.fn(),
  };
  render(
    <ListScreen
      store={serverStoreOf(server)}
      operator={operator}
      {...(intro === undefined ?
        {}
      : { intro: <p data-testid="intro">{intro}</p> })}
      {...calls}
    />,
  );
  await flush();
  return calls;
}

/** 응답을 붙잡아 두는 서버(첫 불러오기 시험 — 밴드 DV2e). release() 뒤에야 답한다. */
function held(server: FakeDataverifyServer) {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  return {
    server: {
      ...server,
      send: async (request: Request) => {
        await gate;
        return server.send(request);
      },
    },
    release: () => act(async () => release()),
  };
}

/** 보낸 URL(가짜 서버 calls 는 path 만 적는다). lastQuery = 마지막 쿼리(같은 이름 여럿은 배열). */
const sent: string[] = [];
function tracked(server: ReturnType<typeof fakeDataverifyServer>) {
  const send = server.send;
  sent.length = 0;
  return {
    ...server,
    send: (request: Request) => {
      sent.push(request.url);
      return send(request);
    },
  };
}
const lastQuery = () => {
  const out: Record<string, string[]> = {};
  for (const [k, v] of new URL(sent.at(-1)!).searchParams)
    (out[k] ??= []).push(v);
  return out;
};
/** 옛 실행(14 — source 없음) 줄: 파일명 칸이 「–」인 줄(시각 칸이 날짜만이라 시각으로 찾지 않는다 — sid:MARC-ENT-625). */
const OLD = '옛 실행';
const rowWith = (text: string) =>
  text === OLD ?
    screen
      .getAllByRole('row')
      .find((row) => row.querySelector('td')?.textContent === DV_TEXT.dash)!
  : screen.getAllByRole('row').find((row) => row.textContent?.includes(text))!;

describe('ListScreen (DV2b §3)', () => {
  it('머리(셈·안내 줄 없음 — sid:MARC-ENT-625)·검증 안내·판 열 차례·안내 띠', async () => {
    const calls = await draw(seeded());
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    expect(screen.getByText(FILE)).toBeTruthy();
    expect(document.body.textContent).not.toContain('파일 5건');
    expect(document.body.textContent).not.toContain('계정이 올린 파일');
    expect(screen.queryByTestId('description-pending')).toBeNull();
    const heads = screen
      .getAllByRole('columnheader')
      .map((th) => th.textContent);
    expect(heads).toEqual(Object.values(words.columns));
    expect(heads).toContain('담당자');
    expect(heads).toContain('검증 완료 일자');
    expect(heads).not.toContain('올린 사람');
    expect(heads).not.toContain('마지막 실행');
    expect(screen.getByTestId('list-notice').textContent).toContain(
      words.notice,
    );
    fireEvent.click(screen.getByText(words.introLink));
    expect(calls.onIntro).toHaveBeenCalled();
  });

  it('파일명 칸: 파일 이름(넘치면 「…」·올리면 전체) · 「붙여 넣은 데이터 · 시각」 · 옛 실행 「–」', async () => {
    await draw(seeded());
    const names = screen.getAllByTestId('file-name');
    const file = names.find((n) => n.textContent === FILE)!;
    expect(file.getAttribute('title')).toBe(FILE);
    expect(file.className).toContain('truncate');
    expect(
      screen.getByText(DV_TEXT.source.pastedAt('2026-10-19 10:42')),
    ).toBeTruthy();
    // 옛 실행(14 — source 없음)의 파일명 칸은 「–」, 실행은 그대로 보인다.
    const old = rowWith(OLD);
    expect(within(old).getAllByRole('cell')[0]!.textContent).toBe(DV_TEXT.dash);
  });

  it('요약 칸: 보고연도·담당자·환경 항목·검증 완료 일자·어긋남·계산 못 함 — done 만 수, 그 밖 「–」 · 「1회차」·「핵심」 0', async () => {
    await draw(seeded());
    const done = within(rowWith(FILE))
      .getAllByRole('cell')
      .map((c) => c.textContent);
    // 파일명 · 2025 · 담당자 A · 항목 수 · 검증 완료 일자(finishedAt 의 한국 날짜만) · 어긋남(fail) · 계산 못 함(notComputed)
    expect(done.slice(1, 5)).toEqual(['2025', '담당자 A', '2', '2026-10-20']);
    expect(Number(done[5])).toBeGreaterThan(0);
    expect(done[6]).toMatch(/^\d+$/);
    const running = within(rowWith('b.json'))
      .getAllByRole('cell')
      .map((c) => c.textContent);
    // 아직 안 끝난 줄(finishedAt null)의 검증 완료 일자는 「–」
    expect(running[4]).toBe(DV_TEXT.dash);
    expect(running[5]).toBe(DV_TEXT.dash);
    expect(running[6]).toBe(DV_TEXT.dash);
    const body = document.body.textContent!;
    expect(body).not.toContain('1회차');
    expect(body).not.toContain('핵심');
  });

  it('상태 배지·다음 할 일: 완료 → 결과 보기 · 일부 단계 못 함 · 검증 중 · <단계> → 진행 보기 · 대기 · 실패 → 다시 실행', async () => {
    const calls = await draw(seeded());
    const status = (text: string) =>
      within(rowWith(text)).getByTestId('row-status').textContent;
    expect(status(FILE)).toBe(words.badge.done);
    expect(status('붙여 넣은')).toBe(words.badge.done + words.badge.someFailed);
    expect(status('b.json')).toBe(
      words.badge.processing(DV_TEXT.status.stepNames.review),
    );
    expect(status('c.json')).toBe(words.badge.queued);
    expect(status(OLD)).toBe(words.badge.failed);
    const next = (text: string) =>
      within(rowWith(text)).getAllByRole('button').at(-1)!;
    expect(next(FILE).textContent).toBe(words.next.result);
    expect(next('b.json').textContent).toBe(words.next.progress);
    expect(next('c.json').textContent).toBe(words.next.progress);
    expect(next(OLD).textContent).toBe(words.next.rerun);
    fireEvent.click(next(FILE));
    expect(calls.onViewResult).toHaveBeenCalledWith('11');
    fireEvent.click(next('c.json'));
    expect(calls.onViewStatus).toHaveBeenCalledWith('15');
  });

  it('줄 누름: done → DV-04 · 그 밖 → 그 실행의 DV-03(실패 줄도 — 새 실행 0)', async () => {
    const server = seeded();
    const calls = await draw(server);
    fireEvent.click(within(rowWith(FILE)).getAllByRole('cell')[1]!);
    expect(calls.onViewResult).toHaveBeenLastCalledWith('11');
    fireEvent.click(within(rowWith(OLD)).getAllByRole('cell')[1]!);
    expect(calls.onViewStatus).toHaveBeenLastCalledWith('14');
    expect(server.posts()).toHaveLength(0);
  });

  it('[다시 실행] → rerun(옵션 그대로) 뒤 새 실행의 DV-03 · 거절이면 시작 실패 글', async () => {
    const server = seeded();
    const calls = await draw(server);
    const rerun = () => within(rowWith(OLD)).getByText(words.next.rerun);
    fireEvent.click(rerun());
    await flush();
    expect(calls.onViewStatus).toHaveBeenCalledWith('30');
    expect(server.posts()).toHaveLength(1);
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    fireEvent.click(rerun());
    await flush();
    expect(screen.getByTestId('list-rerun-error').textContent).toBe(
      DV_TEXT.newCheck.errors.startFailed,
    );
  });

  it('탭 → status 쿼리(「대기·처리 중」은 둘을 한 요청) · 「내가 올린 것만」 → mine=true', async () => {
    const server = tracked(seeded());
    await draw(server);
    expect(lastQuery()).toEqual({ limit: ['20'], offset: ['0'] });
    for (const [tab, statuses] of [
      ['active', ['queued', 'processing']],
      ['done', ['done']],
      ['failed', ['failed']],
    ] as const) {
      fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs[tab] }));
      await flush();
      expect(lastQuery().status).toEqual(statuses);
    }
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs.all }));
    await flush();
    expect(lastQuery().status).toBeUndefined();
    fireEvent.click(screen.getByRole('checkbox', { name: words.mineOnly }));
    await flush();
    expect(lastQuery().mine).toEqual(['true']);
    // 담당자 B 가 올린 붙여 넣은 줄이 빠진다(서버 거름).
    expect(
      screen.queryByText(DV_TEXT.source.pastedAt('2026-10-19 10:42')),
    ).toBeNull();
  });

  it('운영 관리자: 「내가 올린 것만」 0 · 운영 관리자 셈·안내 줄 0 · mine 0', async () => {
    const server = tracked(seeded());
    await draw(server, { operator: true });
    expect(screen.queryByRole('checkbox', { name: words.mineOnly })).toBeNull();
    expect(screen.queryByText(words.mineOnly)).toBeNull();
    expect(screen.getByText(FILE)).toBeTruthy();
    expect(document.body.textContent).not.toContain('운영 관리자 · 파일');
    expect(document.body.textContent).not.toContain('계정이 올린 파일');
    expect(lastQuery().mine).toBeUndefined();
  });

  it('화면 거르기: 파일명 검색(대소문자 무시)·보고연도(받은 줄의 해만) · 거른 빔 → [거르기 풀기]', async () => {
    const server = tracked(seeded());
    await draw(server);
    const asked = sent.length;
    fireEvent.change(screen.getByRole('textbox', { name: words.search }), {
      target: { value: 'B.JSON' },
    });
    expect(
      screen.getAllByTestId('file-name').map((n) => n.textContent),
    ).toEqual(['b.json']);
    fireEvent.change(screen.getByRole('textbox', { name: words.search }), {
      target: { value: '' },
    });
    const year = screen.getByRole('combobox', { name: words.yearLabel });
    expect(
      [...year.querySelectorAll('option')].map((o) => o.textContent),
    ).toEqual([words.yearAll, '2025', '2024']);
    fireEvent.change(year, { target: { value: '2024' } });
    expect(
      screen.getAllByTestId('file-name').map((n) => n.textContent),
    ).toEqual(['b.json']);
    // 화면 거르기는 요청을 내지 않는다(서버 검색 0 — sid:MARC-ENT-432).
    expect(sent.length).toBe(asked);
    fireEvent.change(screen.getByRole('textbox', { name: words.search }), {
      target: { value: '없는 이름' },
    });
    expect(screen.getByTestId('list-empty-filtered').textContent).toContain(
      words.emptyFiltered,
    );
    fireEvent.click(screen.getByRole('button', { name: words.clearFilter }));
    expect(screen.getAllByTestId('file-name')).toHaveLength(4);
  });

  it('빔: 거름 없는 첫 쪽 0건 → intro(표·머리 0) · intro 없으면 판 빈 글 + [새 검증] · 서버 거름의 빔은 거른 빔', async () => {
    await draw(fakeDataverifyServer(), { intro: 'DV-00' });
    expect(screen.getByTestId('intro')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('heading', { name: words.title })).toBeNull();
    cleanup();
    const calls = await draw(fakeDataverifyServer());
    expect(screen.getByTestId('list-empty').textContent).toContain(words.empty);
    // 빈 글은 엑셀로 말한다 — 화면 전체 글에 「JSON」 0(밴드 DV13 — 컨설턴트 댓글 11-10, sid:MARC-ISSUE-646)
    expect(document.body.textContent).not.toMatch(/json/i);
    fireEvent.click(
      within(screen.getByTestId('list-empty')).getByRole('button', {
        name: words.newCheck,
      }),
    );
    expect(calls.onNewCheck).toHaveBeenCalled();
    cleanup();
    const only = fakeDataverifyServer({ runs: [fakeRun(1)] });
    await draw(only, { intro: 'DV-00' });
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs.done }));
    await flush();
    expect(screen.queryByTestId('intro')).toBeNull();
    expect(screen.getByTestId('list-empty-filtered')).toBeTruthy();
  });

  it('다시 읽기(DV2e): 탭을 바꾼 응답 전에는 표 머리 + 스켈레톤 줄 · 빈 글 0 · 설명 자리 막대', async () => {
    const base = fakeDataverifyServer({ runs: [fakeRun(1)] });
    let hold = false;
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const server = {
      ...base,
      send: async (request: Request) => {
        if (hold) await gate;
        return base.send(request);
      },
    };
    await draw(server, { intro: 'DV-00' });
    hold = true;
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs.done }));
    await flush();
    const table = screen.getByRole('table');
    expect(table.getAttribute('aria-busy')).toBe('true');
    expect(screen.getAllByRole('columnheader')).toHaveLength(
      Object.keys(words.columns).length,
    );
    expect(screen.queryByTestId('list-empty-filtered')).toBeNull();
    expect(screen.queryByTestId('intro')).toBeNull();
    // 설명 줄이 없어 읽는 동안에도 설명 막대 자리가 없다(sid:MARC-ENT-625)
    expect(screen.queryByTestId('description-pending')).toBeNull();
    await act(async () => release());
    expect(screen.getByTestId('list-empty-filtered')).toBeTruthy();
    expect(screen.queryByTestId('description-pending')).toBeNull();
  });

  it('불러오기 실패 → 「검증 목록을 불러오지 못했어요」 + [다시 시도] 가 다시 부른다', async () => {
    const server = seeded();
    server.override[LIST] = [() => refusal(500, 'INTERNAL')];
    await draw(server);
    expect(screen.getByText(words.loadFailed)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: words.retry }));
    await flush();
    expect(server.count(LIST)).toBe(2);
    expect(screen.getByText(FILE)).toBeTruthy();
  });
});

describe('DV-01 시안 대조 손질(밴드 DV3 ①)', () => {
  it('W5 검색 칸 폭 300(w-[300px]) · w-64 0', async () => {
    await draw(seeded());
    const search = screen.getByRole('textbox', { name: words.search });
    const box = search.closest('.w-\\[300px\\]');
    expect(box).not.toBeNull();
    expect(box!.className).not.toContain('w-64');
  });
});

describe('DV-01 열 폭 고정(밴드 DVW1 ②-3)', () => {
  /** 고정 짜임 표의 colgroup 폭(px 글, 폭 없으면 ''). */
  const colWidths = (table: Element) => {
    expect(table.className).toContain('table-fixed');
    const cols = [...table.querySelectorAll(':scope > colgroup > col')];
    expect(cols).toHaveLength(table.querySelectorAll('thead th').length);
    return cols.map((col) => (col as HTMLElement).style.width);
  };

  /** 1280 max-content + 32 잰 폭 — 파일명만 폭 없음(남은 폭). */
  const WIDTHS = [
    '',
    '80px',
    '120px',
    '84px',
    '153px',
    '68px',
    '87px',
    '160px',
    '98px',
  ];

  it('table-fixed · col 수 = 머리 수 · 짧은 칸 잰 폭 · 다시 읽는 동안(스켈레톤)도 같은 colgroup', async () => {
    const base = seeded();
    let hold = false;
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const server = {
      ...base,
      send: async (request: Request) => {
        if (hold) await gate;
        return base.send(request);
      },
    };
    await draw(server);
    expect(colWidths(screen.getByRole('table'))).toEqual(WIDTHS);
    hold = true;
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs.done }));
    await flush();
    expect(screen.getByRole('table').getAttribute('aria-busy')).toBe('true');
    expect(colWidths(screen.getByRole('table'))).toEqual(WIDTHS);
    await act(async () => release());
    expect(colWidths(screen.getByRole('table'))).toEqual(WIDTHS);
  });

  it('skeletonRows: 다시 읽는 동안 스켈레톤 줄 수 = 직전에 그린 줄 수(기본 5 아님)', async () => {
    const base = fakeDataverifyServer({ runs: [fakeRun(1), fakeRun(2)] });
    let hold = false;
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const server = {
      ...base,
      send: async (request: Request) => {
        if (hold) await gate;
        return base.send(request);
      },
    };
    await draw(server);
    expect(document.querySelectorAll('tbody tr')).toHaveLength(2);
    hold = true;
    fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabs.active }));
    await flush();
    expect(
      document.querySelectorAll('tbody tr[data-skeleton-row]'),
    ).toHaveLength(2);
    await act(async () => release());
  });
});

describe('DV-01 첫 읽기 꼴(밴드 DV4, sid:MARC-ISSUE-404 · sid:MARC-ENT-443 ②③ — 그린워싱 GL1 꼴)', () => {
  // 가짜 시계는 setTimeout·clearTimeout 만(약속·effect 는 진짜로 돈다 — 응답은 act 안에서 끝낸다).
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const skeletonRows = () => document.querySelectorAll('[data-skeleton-row]');
  const bars = () =>
    document.querySelectorAll('[data-skeleton-row] [data-skeleton-bar]');
  const outer = () => document.querySelector('[data-screen="dataverify-list"]');

  it('첫 그림부터 제목(설명 막대 0 — ENT-625)·표 머리 + 스켈레톤 줄 5 · DV-00·빈 글 0 · 299ms 막대 0 / 300ms 막대 → 받으면 진짜 줄', async () => {
    const { server, release } = held(seeded());
    await draw(server, { intro: 'DV-00' });
    expect(outer()?.getAttribute('aria-busy')).toBe('true');
    expect(outer()?.getAttribute('data-list-state')).toBe('loading');
    expect(screen.getByRole('heading', { name: words.title })).toBeTruthy();
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.getByRole('table').getAttribute('aria-busy')).toBe('true');
    expect(screen.getAllByRole('columnheader')).toHaveLength(
      Object.keys(words.columns).length,
    );
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    expect(screen.queryByTestId('intro')).toBeNull();
    expect(screen.queryByTestId('list-empty')).toBeNull();
    // 라이브 영역은 처음부터 있고(빈 글) 같은 마디에 글만 들어간다(밴드 LA1 ①)
    const live = screen.getByRole('status');
    expect(live.textContent).toBe('');
    expect(bars()).toHaveLength(0);
    act(() => vi.advanceTimersByTime(299));
    expect(bars()).toHaveLength(0);
    expect(live.textContent).toBe('');
    act(() => vi.advanceTimersByTime(1));
    expect(bars().length).toBeGreaterThan(0);
    expect(live.textContent).toBe(words.loading);
    expect(screen.getByRole('status')).toBe(live);
    await release();
    expect(live.isConnected).toBe(true);
    expect(live.textContent).toBe('');
    expect(skeletonRows()).toHaveLength(0);
    expect(screen.getByText(FILE)).toBeTruthy();
    expect(document.querySelectorAll('tbody tr')).toHaveLength(5);
    expect(outer()?.hasAttribute('aria-busy')).toBe(false);
    expect(outer()?.hasAttribute('data-list-state')).toBe(false);
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.queryByTestId('intro')).toBeNull();
  });

  it('300ms 안에 받으면 막대를 그린 적이 없다', async () => {
    const { server, release } = held(seeded());
    await draw(server);
    act(() => vi.advanceTimersByTime(200));
    await release();
    act(() => vi.advanceTimersByTime(500));
    expect(bars()).toHaveLength(0);
    expect(skeletonRows()).toHaveLength(0);
    expect(screen.getByText(FILE)).toBeTruthy();
  });

  it('0건이면 받은 뒤에야 DV-00 · 그 전에는 목록 틀', async () => {
    const { server, release } = held(fakeDataverifyServer());
    await draw(server, { intro: 'DV-00' });
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByTestId('intro')).toBeNull();
    expect(skeletonRows()).toHaveLength(5);
    await release();
    expect(screen.getByTestId('intro')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('heading', { name: words.title })).toBeNull();
  });

  it('첫 읽기 실패 → 표 안 「검증 목록을 불러오지 못했어요」 + [다시 시도] · DV-00 0', async () => {
    const server = seeded();
    server.override[LIST] = [() => refusal(500, 'INTERNAL')];
    const { server: slow, release } = held(server);
    await draw(slow, { intro: 'DV-00' });
    expect(skeletonRows()).toHaveLength(5);
    await release();
    expect(skeletonRows()).toHaveLength(0);
    expect(screen.getByText(words.loadFailed)).toBeTruthy();
    expect(screen.getByRole('button', { name: words.retry })).toBeTruthy();
    expect(screen.queryByTestId('intro')).toBeNull();
    expect(outer()?.hasAttribute('aria-busy')).toBe(false);
  });
});
