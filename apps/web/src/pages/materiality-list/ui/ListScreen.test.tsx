// @vitest-environment jsdom
// 평가 목록 화면(밴드 IRW1 ③ — 발주서 §3-③ 11, 판 IR-01·01a). 진짜 실어댑터 + 가짜 중대성평가 서버. 키트 Tabs(radix)는 mouseDown 으로 누른다.
//   머리 셈·안내 줄 0(고객사·운영 관리자 — sid:MARC-ENT-625) · 10열(기업·산업·토픽·기간·실행한 사람·평가 완료 일자·두 수·상태·다음 할 일, null 「–」) ·
//   상태 탭 → status 쿼리 · 「내가 돌린」 거르기·안내 띠·기업명 옆 최신 이슈 표시 0(IRW17, mine 쿼리 0) · 다음 할 일과 줄 누름(failed 줄 누름은 IR-03 — POST 0) ·
//   [다시 실행] → 새 실행(options 그대로)·거절 글 · 빈 목록(IR-01 빈 꼴 — 콜백 없으면 단추 0) · 거른 빔 → [거르기 풀기] · 실패 → [다시 시도] ·
//   [평가 안내]·[새 평가]는 콜백을 줄 때만. IRW2 ③: 빈 목록 intro(Q9) · 거르기 바꾸면 다시 실행 실패 글 지움(m4) · W8 · N2.
import type { ReactNode } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  FAKE_OTHER,
  FAKE_STARTED_AT,
  doneRun,
  fakeMaterialityServer,
  fakeRun,
  fakeSteps,
  json,
  refusal,
  serverStoreOf,
} from '../../../entities/materiality/api/testing.ts';
import type { FakeMaterialityServer } from '../../../entities/materiality/api/testing.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { fakeInput } from '../../../entities/materiality/model/testing.ts';
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

const words = IR_TEXT.list;
const LIST = 'GET /materiality/runs';
const flush = () => act(async () => {});

/** 실행 다섯: 21 done(나) · 22 processing(남 · 최신 이슈 반영) · 23 failed · 24 queued · 25 꼴 밖 입력의 done(요약 없음). */
function seeded() {
  return fakeMaterialityServer({
    runs: [
      doneRun(21, {
        createdAt: '2026-10-19T10:00:00+09:00',
        // 끝난 때 = 한국 시각 10-20 0시 10분(UTC 로는 10-19) — 칸이 시작·만든 때가 아니고 finishedAt 의 한국 날짜인지 가른다
        finishedAt: '2026-10-19T15:10:00Z',
      }),
      fakeRun(22, {
        status: 'processing',
        startedAt: FAKE_STARTED_AT,
        steps: fakeSteps(3, 'running'),
        createdAt: '2026-10-19T11:00:00+09:00',
        createdBy: FAKE_OTHER,
        options: {
          input: fakeInput({
            latestEventMode: true,
            dateRange: '2024-01-01~2024-12-31',
          }),
        },
      }),
      fakeRun(23, {
        status: 'failed',
        startedAt: FAKE_STARTED_AT,
        finishedAt: '2026-10-19T12:10:00+09:00',
        steps: fakeSteps(2, 'failed'),
        failedStep: 'keywords',
        createdAt: '2026-10-19T12:00:00+09:00',
      }),
      fakeRun(24, { createdAt: '2026-10-19T13:00:00+09:00' }),
      doneRun(25, {
        createdAt: '2026-10-19T09:00:00+09:00',
        options: { input: 'broken' },
        digest: 'none',
      }),
    ],
  });
}

function setup(
  server: FakeMaterialityServer = seeded(),
  operator = false,
  extra: { intro?: ReactNode; onIntro?: () => void; onNew?: () => void } = {},
) {
  const store = serverStoreOf(server, { pollMs: 5 });
  const props = { onViewResult: vi.fn(), onViewStatus: vi.fn() };
  render(
    <ListScreen store={store} operator={operator} {...props} {...extra} />,
  );
  return { server, ...props };
}

const rowOf = (id: number) =>
  document.querySelector(`[data-run-id="${id}"]`)?.closest('tr') ?? null;
const rows = () =>
  [...document.querySelectorAll('tbody [data-run-id]')].map(
    (node) => (node as HTMLElement).dataset.runId,
  );
const cells = (id: number) =>
  [...rowOf(id)!.querySelectorAll('td')].map((td) => td.textContent);
const tab = (name: string) =>
  fireEvent.mouseDown(screen.getByRole('tab', { name }));
const listQueries = (server: FakeMaterialityServer) =>
  server.calls.filter((c) => `${c.method} ${c.path}` === LIST);
/** 받은 줄 n 개가 다 그려질 때까지(머리 셈 줄을 지워 그 대신 — sid:MARC-ENT-625). 읽는 동안은 스켈레톤 줄이라 data-run-id 0. */
const shownRows = (n: number) =>
  vi.waitFor(() => expect(rows()).toHaveLength(n));
const ready = () => shownRows(5);
/** IRW4 목록 열 폭(회사·산업·토픽 수·리서치 기간·작성자·평가 완료 일자·영향·재무·상태·다음). */
const LIST_WIDTHS = [
  '136px',
  '168px',
  '56px',
  '124px',
  '96px',
  '153px',
  '111px',
  '111px',
  '136px',
  '98px',
];

describe('IR-01 평가 목록', () => {
  it('머리 · 새 것 먼저 · 10열 글(판 차례) · null 「–」 · 안내 띠 0', async () => {
    setup();
    await ready();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      words.title,
    );
    expect(
      [...document.querySelectorAll('thead th')].map((th) => th.textContent),
    ).toEqual(Object.values(words.columns));
    expect(Object.values(words.columns)).toContain('평가 완료 일자');
    expect(Object.values(words.columns)).not.toContain('마지막 실행');
    expect(document.body.textContent).not.toContain('실행 5회');
    expect(document.body.textContent).not.toContain('계정이 돌린 평가');
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(rows()).toEqual(['24', '23', '22', '21', '25']);
    expect(cells(21)).toEqual([
      '가상물산',
      '가상 산업',
      '2',
      '2025-01-01 ~ 2026-10-19',
      '담당자 A',
      '2026-10-20',
      '3',
      '3',
      IR_TEXT.badge.done,
      words.next.result,
    ]);
    expect(cells(22)).toEqual([
      // 0207ff2a — latestEventMode 참이어도 기업명 옆 표시 0(열은 10 그대로)
      '가상물산',
      '가상 산업',
      '2',
      '2024-01-01 ~ 2024-12-31',
      '담당자 B',
      // 처리 중 줄은 시작 때가 있어도 「–」(완료 줄만 날짜)
      '–',
      '–',
      '–',
      words.processing(IR_TEXT.status.lines.controversy.name),
      words.next.progress,
    ]);
    expect(cells(24)[3]).toBe('2025-01-01 ~ 오늘까지');
    expect(cells(24)[8]).toBe(IR_TEXT.badge.queued);
    expect(cells(23)[8]).toBe(IR_TEXT.badge.failed);
    expect(cells(23)[9]).toBe(words.next.rerun);
    // 실패 줄은 끝난 때가 있어도 · 대기 줄은 「–」, 끝난 때만 있는 done(25)은 그 날짜
    expect(cells(23)[5]).toBe('–');
    expect(cells(24)[5]).toBe('–');
    expect(cells(25)[5]).toBe('2026-10-19');
    expect(cells(25).slice(0, 4)).toEqual(['–', '–', '–', '–']);
    expect(cells(25).slice(6, 8)).toEqual(['–', '–']);
    // 68f3d0fb — 아래 안내 띠 0
    expect(screen.queryByTestId('list-notice')).toBeNull();
    expect(document.body.textContent).not.toContain(
      '중대성 점수는 매기지 않아요',
    );
    expect(screen.queryByTestId('latest-event')).toBeNull();
    expect(document.body.textContent).not.toContain('최신 이슈');
    expect(document.body.textContent).not.toContain('1회차');
  });

  it('산업은 산업 이름(입력 차례, 「, 」) · 모르는 단계는 「처리 중」만', async () => {
    const server = fakeMaterialityServer({
      runs: [
        fakeRun(31, {
          status: 'processing',
          steps: [
            { step: 'later_step', status: 'running', done: null, total: null },
          ],
          options: {
            input: fakeInput({
              industries: [
                {
                  standard: 'SASB',
                  industryName: '가상 산업 하나',
                  description: 'x',
                },
                {
                  standard: 'GICS',
                  industryName: '가상 산업 둘',
                  description: 'x',
                },
              ],
            }),
          },
        }),
      ],
    });
    setup(server);
    await shownRows(1);
    expect(cells(31)[1]).toBe('가상 산업 하나, 가상 산업 둘');
    expect(cells(31)[8]).toBe(words.processing(null));
  });

  it('다음 할 일: [결과 보기] · [진행 보기] · 줄 누름(done → 결과, failed → 그 실행의 IR-03 — POST 0)', async () => {
    const { server, onViewResult, onViewStatus } = setup();
    await ready();
    fireEvent.click(within(rowOf(21)!).getByRole('button'));
    expect(onViewResult).toHaveBeenCalledWith('21');
    fireEvent.click(within(rowOf(22)!).getByRole('button'));
    expect(onViewStatus).toHaveBeenCalledWith('22');
    fireEvent.click(rowOf(23)!.querySelector('td')!);
    expect(onViewStatus).toHaveBeenCalledWith('23');
    fireEvent.click(rowOf(25)!.querySelector('td')!);
    expect(onViewResult).toHaveBeenCalledWith('25');
    await flush();
    expect(server.posts()).toHaveLength(0);
  });

  it('[다시 실행]: 그 실행의 options 그대로 새 실행 → onViewStatus · 거절이면 다시 실행 실패 글', async () => {
    const { server, onViewStatus } = setup();
    await ready();
    fireEvent.click(within(rowOf(23)!).getByRole('button'));
    await vi.waitFor(() => expect(onViewStatus).toHaveBeenCalledWith('30'));
    expect(server.runs.get(30)!.options).toEqual(server.runs.get(23)!.options);
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    fireEvent.click(within(rowOf(23)!).getByRole('button'));
    expect((await screen.findByTestId('list-rerun-error')).textContent).toBe(
      IR_TEXT.common.rerunFailed,
    );
    expect(document.body.textContent).not.toContain('지어낸');
  });

  it('상태 탭 → status 쿼리(「대기·처리 중」은 둘 한 요청) · 「내가 돌린」 거르기 0 · mine 쿼리 0', async () => {
    const { server } = setup();
    await ready();
    tab(words.tabs.active);
    await vi.waitFor(() => expect(rows()).toEqual(['24', '22']));
    expect(listQueries(server).at(-1)!.query.getAll('status')).toEqual([
      'queued',
      'processing',
    ]);
    tab(words.tabs.failed);
    await vi.waitFor(() => expect(rows()).toEqual(['23']));
    tab(words.tabs.all);
    await ready();
    // 2f094f75 — 고객사에게도 거르기 칸 0, 요청에 mine 0
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(document.body.textContent).not.toContain('내가 돌린');
    expect(listQueries(server).length).toBeGreaterThan(0);
    expect(listQueries(server).every((c) => !c.query.has('mine'))).toBe(true);
  });

  it('거른 빔 → 「조건에 맞는 평가가 없어요」+[거르기 풀기] · 빈 목록 → IR-01 빈 꼴(단추 0)', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(21)] });
    setup(server);
    await shownRows(1);
    tab(words.tabs.failed);
    expect(
      (await screen.findByTestId('list-empty-filtered')).textContent,
    ).toContain(words.emptyFiltered);
    fireEvent.click(screen.getByRole('button', { name: words.clearFilter }));
    await shownRows(1);
    cleanup();
    setup(fakeMaterialityServer());
    const empty = await screen.findByTestId('list-empty');
    expect(empty.textContent).toBe(words.empty);
    expect(within(empty).queryAllByRole('button')).toEqual([]);
    expect(screen.queryByRole('button', { name: words.newRun })).toBeNull();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      words.title,
    );
  });

  it('불러오기 실패 → 「평가 목록을 불러오지 못했어요」+[다시 시도]', async () => {
    const server = seeded();
    server.override[LIST] = [() => refusal(500, 'INTERNAL')];
    setup(server);
    await screen.findByText(words.loadFailed);
    fireEvent.click(screen.getByRole('button', { name: IR_TEXT.common.retry }));
    await ready();
  });

  it('운영 관리자: 셈·안내 줄 0 · 「내가 돌린」 거르기 0(mine 0) · 안내 띠 0', async () => {
    const { server } = setup(seeded(), true);
    await ready();
    expect(document.body.textContent).not.toContain('운영 관리자 · 실행');
    expect(document.body.textContent).not.toContain('계정이 돌린 평가');
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(document.body.textContent).not.toContain('내가 돌린');
    expect(screen.queryByTestId('list-notice')).toBeNull();
    expect(listQueries(server).every((c) => !c.query.has('mine'))).toBe(true);
  });

  it('[평가 안내]·[새 평가]는 콜백을 줄 때만(IRW2 가 넘긴다)', async () => {
    setup();
    await ready();
    expect(screen.queryByText(words.introLink)).toBeNull();
    expect(screen.queryByRole('button', { name: words.newRun })).toBeNull();
    cleanup();
    const onIntro = vi.fn();
    const onNew = vi.fn();
    setup(seeded(), false, { onIntro, onNew });
    await ready();
    fireEvent.click(screen.getByText(words.introLink));
    fireEvent.click(screen.getByRole('button', { name: words.newRun }));
    expect(onIntro).toHaveBeenCalledTimes(1);
    expect(onNew).toHaveBeenCalledTimes(1);
  });

  it('done 이라도 2부 not_run 이면 두 수 「–」(요약이 null)', async () => {
    const server = fakeMaterialityServer({
      runs: [doneRun(41, { digest: { impactRows: null, pathwayRows: null } })],
    });
    setup(server);
    await shownRows(1);
    expect(cells(41).slice(6, 8)).toEqual(['–', '–']);
  });
});

describe('IR-01 시안 대조 손질(밴드 IRW1b)', () => {
  it('W8 리서치 기간 「~」 앞뒤 띄움 — 안 돈 실행(원문)·끝 날 있는 실행 둘 다', async () => {
    setup();
    await ready();
    expect(cells(24)[3]).toBe('2025-01-01 ~ 오늘까지');
    expect(cells(22)[3]).toBe('2024-01-01 ~ 2024-12-31');
  });

  it('W2 머리·짧은 칸은 한 줄, 산업 열만 줄바꿈 — 넘치면 카드 안 표 감싸개가 가로 스크롤', async () => {
    setup();
    await ready();
    const wrap = document.querySelector('table')!.parentElement!;
    expect(wrap.className).toContain('overflow-x-auto');
    expect(wrap.className).toContain('[&_th]:whitespace-nowrap');
    expect(wrap.className).toContain('[&_td:not([colspan])]:whitespace-nowrap');
    expect(wrap.closest('[data-screen="materiality-list"]')).not.toBeNull();
    const industry = rowOf(21)!.querySelector('[data-testid="industry"]')!;
    expect(industry.className).toContain('whitespace-normal');
    expect(industry.textContent).toBe('가상 산업');
    // 줄을 바꾸는 칸은 산업 · 리서치 기간 · 상태(감싸개와 배지) · 회사·작성자 — 셋째·넷째는 IRW2 N2, 끝 둘은 IRW4 Q3.
    expect(
      rowOf(21)!.querySelectorAll('[class~="whitespace-normal"]'),
    ).toHaveLength(6);
  });
});

describe('IR-01 손질(밴드 IRW2 ③ — Q9 · 381 m4·W8 · N2)', () => {
  const intro = <div data-screen="materiality-intro">평가 안내 몸</div>;

  it('Q9 거름 없는 첫 쪽 0건 → intro(목록 틀 0) · 첫 응답 전에는 intro 0', async () => {
    const server = fakeMaterialityServer();
    server.override[LIST] = [
      async () => {
        await new Promise((done) => setTimeout(done, 30));
        return json(200, { count: 0, isNext: false, results: [] });
      },
    ];
    setup(server, false, { intro, onIntro: vi.fn(), onNew: vi.fn() });
    expect(document.querySelector('[data-screen="materiality-intro"]')).toBe(
      null,
    );
    expect(
      document.querySelector('[data-list-state="loading"]'),
    ).not.toBeNull();
    await vi.waitFor(() =>
      expect(
        document.querySelector('[data-screen="materiality-intro"]'),
      ).not.toBeNull(),
    );
    expect(document.querySelector('[data-screen="materiality-list"]')).toBe(
      null,
    );
    expect(screen.queryByRole('heading', { name: words.title })).toBeNull();
  });

  it('Q9 거른 빔은 intro 가 아니라 「조건에 맞는 평가가 없어요」 · 운영 관리자도 빈 목록 → intro', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(21)] });
    setup(server, false, { intro });
    await shownRows(1);
    tab(words.tabs.failed);
    await screen.findByTestId('list-empty-filtered');
    expect(document.querySelector('[data-screen="materiality-intro"]')).toBe(
      null,
    );
    cleanup();
    setup(fakeMaterialityServer(), true, { intro });
    await vi.waitFor(() =>
      expect(
        document.querySelector('[data-screen="materiality-intro"]'),
      ).not.toBeNull(),
    );
  });

  it('Q9 intro 가 없으면 IR-01 빈 꼴 — [새 평가]는 빈 글 아래 하나(판, onNew 를 줄 때만)', async () => {
    const onNew = vi.fn();
    setup(fakeMaterialityServer(), false, { onNew });
    const empty = await screen.findByTestId('list-empty');
    expect(empty.textContent).toBe(words.empty + words.newRun);
    expect(screen.getAllByRole('button', { name: words.newRun })).toEqual([
      within(empty).getByRole('button', { name: words.newRun }),
    ]);
    fireEvent.click(within(empty).getByRole('button', { name: words.newRun }));
    expect(onNew).toHaveBeenCalledTimes(1);
  });

  it('m4 다시 실행 실패 글은 상태 탭을 바꾸면 사라진다', async () => {
    const server = seeded();
    setup(server);
    await ready();
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    fireEvent.click(within(rowOf(23)!).getByRole('button'));
    await screen.findByTestId('list-rerun-error');
    tab(words.tabs.failed);
    expect(screen.queryByTestId('list-rerun-error')).toBeNull();
  });

  it('m4 [거르기 풀기]도 다시 실행 실패 글을 지운다', async () => {
    const server = seeded();
    setup(server);
    await ready();
    tab(words.tabs.failed);
    await vi.waitFor(() => expect(rows()).toEqual(['23']));
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    server.override[LIST] = [
      () => json(200, { count: 0, isNext: false, results: [] }),
    ];
    fireEvent.click(within(rowOf(23)!).getByRole('button'));
    await screen.findByTestId('list-rerun-error');
    tab(words.tabs.done);
    await screen.findByTestId('list-empty-filtered');
    fireEvent.click(screen.getByRole('button', { name: words.clearFilter }));
    expect(screen.queryByTestId('list-rerun-error')).toBeNull();
  });

  it('W8 원문이 「~끝」 꼴이면 앞 빈칸 0(「~ 끝」) · 「시작~」 은 「시작 ~」 · 「~」 없으면 원문', async () => {
    const run = (id: number, dateRange: string) =>
      fakeRun(id, {
        createdAt: `2026-10-19T1${id - 50}:00:00+09:00`,
        options: { input: fakeInput({ dateRange }) },
      });
    setup(
      fakeMaterialityServer({
        runs: [run(51, '~2024-12-31'), run(52, '2024-01-01~'), run(53, '가상')],
      }),
    );
    await shownRows(3);
    expect(cells(51)[3]).toBe('~ 2024-12-31');
    expect(cells(52)[3]).toBe('2024-01-01 ~');
    expect(cells(53)[3]).toBe('가상');
  });

  it('N2(Q10) 산업 머리 168 · 상태 머리 136 · 상태 칸·배지 줄바꿈 · 리서치 기간 두 nowrap 덩이 — 셋 같이', async () => {
    setup();
    await ready();
    const wrap = document.querySelector('table')!.parentElement!;
    const heads = [...document.querySelectorAll('thead th')].map(
      (th) => th.textContent,
    );
    expect(heads[1]).toBe(words.columns.industry);
    expect(heads[8]).toBe(words.columns.status);
    const table = wrap.querySelector('table')!;
    expect(table.className).toContain('table-fixed');
    const cols = [...table.querySelectorAll<HTMLElement>('col')];
    expect([cols[1]!.style.width, cols[8]!.style.width]).toEqual([
      '168px',
      '136px',
    ]);
    const status = rowOf(22)!.querySelector('[data-testid="row-status"]')!;
    expect(status.className).toContain('whitespace-normal');
    const badge = status.firstElementChild!;
    expect(badge.className).toContain('h-auto');
    expect(badge.className).toContain('whitespace-normal');
    const period = rowOf(22)!.querySelector('[data-testid="period"]')!;
    expect(period.className).toContain('whitespace-normal');
    expect(
      [...period.children].map((part) => [part.className, part.textContent]),
    ).toEqual([
      ['whitespace-nowrap', '2024-01-01 ~'],
      ['whitespace-nowrap', '2024-12-31'],
    ]);
    // 빈칸은 두 덩이 사이(부모 글) — 줄을 바꿀 자리(검증 3 B1).
    expect(period.textContent).toBe('2024-01-01 ~ 2024-12-31');
    expect(badge.className).toContain('w-auto');
  });

  it('IRW4 N4 열 폭 고정: table-fixed · col 열 폭(짧은 칸 잰 max-content, 산업·상태 판 N2) · 회사·작성자 글 칸 안 줄바꿈', async () => {
    setup();
    await ready();
    const table = document.querySelector('table')!;
    expect(table.className).toContain('table-fixed');
    expect(
      [...table.querySelectorAll<HTMLElement>('colgroup > col')].map(
        (col) => col.style.width,
      ),
    ).toEqual(LIST_WIDTHS);
    const company =
      rowOf(21)!.querySelector('[data-run-id]')!.firstElementChild!;
    expect(company.className).toContain('whitespace-normal');
    const createdBy = rowOf(21)!.querySelectorAll('td')[4]!.firstElementChild!;
    expect(createdBy.tagName).toBe('SPAN');
    expect(createdBy.className).toContain('whitespace-normal');
  });
});

describe('IR-01 한국어 칸 keep-all(밴드 IRW5 — sid:MARC-ISSUE-433)', () => {
  it('N2 회사·산업·작성자 글 span ⊃ break-keep(낱말 중간 줄바꿈 0)', async () => {
    setup();
    await ready();
    const row = rowOf(21)!;
    const company = row.querySelector('[data-run-id]')!.firstElementChild!;
    const industry = row.querySelector('[data-testid="industry"]')!;
    const createdBy = row.querySelectorAll('td')[4]!.firstElementChild!;
    for (const span of [company, industry, createdBy]) {
      expect(span.tagName).toBe('SPAN');
      expect(span.className).toContain('whitespace-normal');
      expect(span.className).toContain('break-keep');
    }
  });
});
