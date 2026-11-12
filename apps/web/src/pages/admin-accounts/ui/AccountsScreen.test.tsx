// @vitest-environment jsdom
// AD-01 계정 관리 화면(밴드 AD1 ②). 가짜 계정 서버(entities/account/api/testing.ts) + 진짜 어댑터 + 고정 난수로 본다.
//   ① 목록: 줄·상태 배지(잠김 포함)·설명의 개수·「—」·불러오기(300ms 뒤 aria-busy)·실패 상자 [다시 시도]·빈 목록
//   ② AD-01a 만들기: 켜짐 조건·아이디 글자·409·422·쓰기 실패·두 번 보냄 막음 → AD-01b(값 = 요청 본문, 초점 [복사], Esc 로 안 닫힘, [확인] 뒤 DOM 에 없음)
//   ③ 초기화 확인 → AD-01b, 404 없는 계정
//   ④ 실서버 쓰기·거르기(UA1W ②): 진짜 어댑터 + 거르지 않는 가짜 서버 — 화면·훅이 어댑터·accountQuery 를 건너뛰면 빨갛다.
//      설명 = total(거른 count·줄 수가 아님), q·status 요청(빈 q·NUL 없음·디바운스), 웹 다시 거르기 없음, 늦은 답 버림,
//      PATCH 를 id 마다(일부 실패 → 실패한 것만 남김), 이름 고침 본문·같은 이름 0·404·422·500, 「준비 중」 없음.
// 시험 이름·단언 글에 임시 비밀번호 값을 싣지 않는다(요청 본문에서 꺼내 견준다).
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

import { createAccountsPort } from '../../../entities/account/api/index.ts';
import {
  fakeAccount,
  fakeAccountsServer,
  json,
  refusal,
} from '../../../entities/account/api/testing.ts';
import { ACCOUNT_TEXT } from '../../../entities/account/config/text.ts';
import { ACCESS_TTL_MINUTES } from '../../../entities/account/model/index.ts';
import type {
  Account,
  RandomFill,
} from '../../../entities/account/model/index.ts';
import { createApi } from '../../../shared/api/index.ts';
import { AccountsScreen, SEARCH_DELAY_MS } from './AccountsScreen.tsx';

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

const BASE = 'http://test.local/api';
const words = ACCOUNT_TEXT;

const seeded = (seed: number): RandomFill => {
  let state = seed >>> 0;
  return (array) => {
    for (let i = 0; i < array.length; i++) {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      array[i] = state;
    }
    return array;
  };
};

const ACCOUNTS = (): Account[] => [
  fakeAccount(1),
  fakeAccount(2, { isLocked: true }),
  fakeAccount(3, { isInitial: true, lastLoginAt: null }),
  fakeAccount(4, { isActive: false, isInitial: true }),
];

function setup(
  accounts = ACCOUNTS(),
  { copy = vi.fn(() => Promise.resolve()) } = {},
) {
  const server = fakeAccountsServer(accounts, { baseUrl: BASE });
  const port = createAccountsPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
    random: seeded(9),
  });
  render(<AccountsScreen port={port} copy={copy} />);
  return { server, copy };
}

const rowOf = (username: string) =>
  screen.getByText(username, { selector: 'td' }).closest('tr')!;
const listReady = () => screen.findByText('user01', { selector: 'td' });
const dialog = () => screen.getByRole('dialog');
const passwordField = () =>
  screen.queryByLabelText(words.password.label) as HTMLInputElement | null;

async function openCreate() {
  await listReady();
  fireEvent.click(screen.getByRole('button', { name: words.list.create }));
  return dialog();
}
function fill(username: string, name: string) {
  fireEvent.change(
    screen.getByRole('textbox', { name: words.create.username }),
    {
      target: { value: username },
    },
  );
  fireEvent.change(screen.getByRole('textbox', { name: words.create.name }), {
    target: { value: name },
  });
}
const submitButton = () =>
  within(dialog()).getByRole('button', { name: words.create.submit });

describe('AD-01 ① 목록', () => {
  it('줄마다 아이디·이름·상태 배지(사용 중·잠김·초기화 대기·사용 중지)·마지막 로그인(없으면 —). 설명에 개수', async () => {
    setup();
    await listReady();
    const badge = (username: string) =>
      rowOf(username).querySelector('[data-status]')!;
    expect(badge('user01').textContent).toBe(words.status.active);
    expect(badge('user02').textContent).toBe(words.status.locked);
    expect(badge('user03').textContent).toBe(words.status.initial);
    expect(badge('user04').textContent).toBe(words.status.inactive);
    expect(rowOf('user01').textContent).toContain('2026-10-15 14:20');
    expect(rowOf('user03').textContent).toContain(words.list.never);
    expect(screen.getByText(words.list.description(4))).toBeTruthy();
    expect(screen.getByText(words.list.foot)).toBeTruthy();
    expect(screen.getByText(words.list.notice)).toBeTruthy();
    // 「만든 날」 열은 마지막 로그인과 비밀번호 사이(디자인 원문 UA1W Q9), 회사 이름 열은 없다
    expect(
      screen.getAllByRole('columnheader').map((cell) => cell.textContent),
    ).toEqual([
      '',
      words.list.columns.username,
      words.list.columns.name,
      words.list.columns.status,
      words.list.columns.lastLogin,
      words.list.columns.createdAt,
      words.list.columns.password,
    ]);
    expect(rowOf('user01').textContent).toContain('2026-10-01');
    expect(document.body.textContent).not.toContain('고객사 A');
    // 사용 중지 계정도 [초기화] 는 켜져 있다
    expect(
      within(rowOf('user04'))
        .getByRole('button', { name: words.list.resetLabel('user04') })
        .hasAttribute('disabled'),
    ).toBe(false);
  });

  it('불러오는 동안: 300ms 안에는 스켈레톤 없음, 그 뒤 표에 aria-busy', async () => {
    const { server } = setup();
    // 목록과 전체 수가 둘 다 GET /users 라 붙잡은 답을 모두 푼다(UA1W).
    const pending: (() => void)[] = [];
    const release = () => pending.splice(0).forEach((open) => open());
    server.override['GET /users'] = () =>
      new Promise((resolve) => {
        pending.push(() =>
          resolve(json(200, { count: 0, isNext: false, results: [] })),
        );
      });
    cleanup();
    const port = createAccountsPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
      random: seeded(1),
    });
    render(<AccountsScreen port={port} copy={() => Promise.resolve()} />);
    const table = screen.getByRole('table', { name: words.list.tableLabel });
    expect(table.getAttribute('aria-busy')).toBeNull();
    await waitFor(() => expect(table.getAttribute('aria-busy')).toBe('true'));
    await act(async () => release());
    await screen.findByText(words.list.empty);
    expect(table.getAttribute('aria-busy')).toBeNull();
  });

  it('받기 전(밴드 LD1): 첫 그림부터 몸 줄 5·설명 자리 막대, 빈 목록 글 0 — 받으면 설명 글과 빈 목록', async () => {
    const { server } = setup();
    const pending: (() => void)[] = [];
    server.override['GET /users'] = () =>
      new Promise((resolve) => {
        pending.push(() =>
          resolve(json(200, { count: 0, isNext: false, results: [] })),
        );
      });
    cleanup();
    const port = createAccountsPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
      random: seeded(1),
    });
    render(<AccountsScreen port={port} copy={() => Promise.resolve()} />);
    const skeletonRows = () =>
      document.querySelectorAll('tbody tr[data-skeleton-row]');
    expect(skeletonRows()).toHaveLength(5);
    expect(skeletonRows()[0]!.querySelectorAll('td')).toHaveLength(7);
    expect(screen.queryByText(words.list.empty)).toBeNull();
    expect(screen.getByTestId('description-pending')).toBeTruthy();
    await new Promise((done) => setTimeout(done, 400));
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByText(words.list.empty)).toBeNull();
    await act(async () => pending.splice(0).forEach((open) => open()));
    await screen.findByText(words.list.empty);
    expect(skeletonRows()).toHaveLength(0);
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.getByText(words.list.description(0))).toBeTruthy();
  });

  // 밴드 DT1 ②(J3, sid:MARC-ISSUE-374): table-fixed + colgroup — 로딩·받은 뒤 같은 col 폭(아이디 149 는 6c, 그 밖은 잰 값).
  it('열 폭: table-fixed · col 수 = 머리 칸 수 · 로딩과 받은 뒤 같은 col 폭', async () => {
    const { server } = setup();
    const pending: (() => void)[] = [];
    server.override['GET /users'] = () =>
      new Promise((resolve) => {
        pending.push(() =>
          resolve(json(200, { count: 0, isNext: false, results: [] })),
        );
      });
    cleanup();
    const port = createAccountsPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
      random: seeded(1),
    });
    render(<AccountsScreen port={port} copy={() => Promise.resolve()} />);
    const cols = () =>
      [...document.querySelectorAll('table colgroup > col')].map(
        (col) => (col as HTMLElement).style.width,
      );
    const table = screen.getByRole('table', { name: words.list.tableLabel });
    expect(table.className.split(/\s+/)).toContain('table-fixed');
    expect(cols()).toHaveLength(table.querySelectorAll('thead th').length);
    const loading = cols();
    expect(loading).toEqual([
      '48px',
      '149px',
      '',
      '84px',
      '153px',
      '112px',
      '88px',
    ]);
    await new Promise((done) => setTimeout(done, 400));
    expect(cols()).toEqual(loading);
    await act(async () => pending.splice(0).forEach((open) => open()));
    await screen.findByText(words.list.empty);
    expect(cols()).toEqual(loading);
  });

  it('실패(404 COMPANY_NOT_FOUND)는 실패 상자 + [다시 시도]. 받으면 제목으로 초점', async () => {
    const { server } = setup();
    server.override['GET /users'] = [() => refusal(404, 'COMPANY_NOT_FOUND')];
    const box = await screen.findByTestId('load-failure');
    expect(box.textContent).toContain(words.list.failed);
    expect(screen.queryByText(words.list.empty)).toBeNull();
    fireEvent.click(
      within(box).getByRole('button', { name: words.list.retry }),
    );
    await listReady();
    // 초점은 제목(h2) 하나 — 머리 묶음·body 가 아니다(sid:MARC-ISSUE-342). 부하 아래 늦을 수 있어 기다림만 늘린다.
    await waitFor(
      () =>
        expect(document.activeElement).toBe(
          screen.getByRole('heading', { name: words.list.title }),
        ),
      { timeout: 8_000 },
    );
  });

  it('빈 목록은 글 하나', async () => {
    setup([]);
    await screen.findByText(words.list.empty);
  });
});

describe('AD-01a 만들기 → AD-01b', () => {
  it('[만들기] 는 아이디 꼴이 맞고 다듬은 이름이 있어야 켜진다. 한글 아이디는 칸이 aria-invalid', async () => {
    setup();
    await openCreate();
    expect(submitButton().hasAttribute('disabled')).toBe(true);
    fill('담당자', '담당자 G');
    expect(submitButton().hasAttribute('disabled')).toBe(true);
    expect(
      screen
        .getByRole('textbox', { name: words.create.username })
        .getAttribute('aria-invalid'),
    ).toBe('true');
    fill('user07', '   ');
    expect(submitButton().hasAttribute('disabled')).toBe(true);
    fill('user07', '담당자 G');
    expect(submitButton().hasAttribute('disabled')).toBe(false);
    expect(screen.getByTestId('name-count').textContent).toBe('5 / 20');
  });

  it('409 → 아이디 칸 아래 오류 글 + 칸으로 초점, 다른 아이디로 만들면 AD-01b: 값 = 요청 본문, 초점 [복사], Esc 로 안 닫힘, [확인] 뒤 DOM 에 없음', async () => {
    const { server, copy } = setup();
    await openCreate();
    fill('user01', '  담당자 G  ');
    fireEvent.click(submitButton());
    await screen.findByText(words.create.taken);
    const usernameInput = screen.getByRole('textbox', {
      name: words.create.username,
    });
    expect(usernameInput.getAttribute('aria-invalid')).toBe('true');
    await waitFor(() => expect(document.activeElement).toBe(usernameInput));
    fill('user07', '  담당자 G  ');
    expect(screen.queryByText(words.create.taken)).toBeNull();
    fireEvent.click(submitButton());
    await screen.findByText(words.password.title);
    const sent = server.writes()[1]!;
    expect(sent.name).toBe('담당자 G');
    expect(passwordField()!.value).toBe(sent.password);
    expect(passwordField()!.readOnly).toBe(true);
    expect(
      screen.getByText(words.password.created('user07', '담당자 G')),
    ).toBeTruthy();
    await waitFor(() =>
      expect(document.activeElement?.textContent).toBe(words.password.copy),
    );
    fireEvent.click(screen.getByRole('button', { name: words.password.copy }));
    await screen.findByText(words.password.copied);
    expect(copy).toHaveBeenCalledWith(sent.password);
    // Esc 로 닫히지 않는다([확인]으로만)
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
    expect(passwordField()).not.toBeNull();
    // 목록은 다시 받았다(개수 5)
    await screen.findByText(words.list.description(5));
    fireEvent.click(
      screen.getByRole('button', { name: words.password.confirm }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.body.innerHTML).not.toContain(String(sent.password));
    await waitFor(() =>
      expect(document.activeElement?.textContent).toBe(words.list.create),
    );
    // 다시 열면 빈 입력 — 임시 비밀번호를 다시 볼 길이 없다
    fireEvent.click(screen.getByRole('button', { name: words.list.create }));
    expect(passwordField()).toBeNull();
    expect(
      (
        screen.getByRole('textbox', {
          name: words.create.username,
        }) as HTMLInputElement
      ).value,
    ).toBe('');
  });

  it('보내는 중에는 다시 보내지 않는다(같은 렌더 안의 두 번 제출 — POST /users 한 번)', async () => {
    const { server } = setup();
    await openCreate();
    fill('user07', '담당자 G');
    const form = submitButton().closest('form')!;
    fireEvent.submit(form);
    fireEvent.submit(form);
    await screen.findByText(words.password.title);
    expect(server.count('POST /users')).toBe(1);
  });

  it('422 VALIDATION_ERROR 는 그 칸 아래 「입력한 값을 확인해 주세요」(서버 message 는 안 보임)', async () => {
    const { server } = setup();
    server.override['POST /users'] = () =>
      refusal(422, 'VALIDATION_ERROR', { name: ['길이'] });
    await openCreate();
    fill('user07', '담당자 G');
    fireEvent.click(submitButton());
    await screen.findByText(words.create.invalid);
    expect(
      screen
        .getByRole('textbox', { name: words.create.name })
        .getAttribute('aria-invalid'),
    ).toBe('true');
    expect(document.body.textContent).not.toContain('지어낸-');
  });

  it('그 밖의 실패는 쓰기 실패 글, 모달은 그대로', async () => {
    const { server } = setup();
    server.override['POST /users'] = () => refusal(500, 'INTERNAL_ERROR');
    await openCreate();
    fill('user07', '담당자 G');
    fireEvent.click(submitButton());
    await screen.findByText(words.create.failed);
    expect(passwordField()).toBeNull();
  });

  it('복사가 실패하면 그 글', async () => {
    setup(ACCOUNTS(), { copy: vi.fn(() => Promise.reject(new Error('x'))) });
    await openCreate();
    fill('user07', '담당자 G');
    fireEvent.click(submitButton());
    await screen.findByText(words.password.title);
    fireEvent.click(screen.getByRole('button', { name: words.password.copy }));
    await screen.findByText(words.password.copyFailed);
  });
});

describe('초기화 확인 → AD-01b', () => {
  it('[초기화] → 확인 → POST /users/{id}/password-reset → AD-01b(초기화 누구 줄). [확인] 뒤 그 줄 [초기화] 로 초점', async () => {
    const { server } = setup();
    await listReady();
    const button = within(rowOf('user04')).getByRole('button', {
      name: words.list.resetLabel('user04'),
    });
    fireEvent.click(button);
    expect(screen.getByText(words.reset.title('user04'))).toBeTruthy();
    expect(screen.getByText(words.reset.body)).toBeTruthy();
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.reset.submit }),
    );
    await screen.findByText(words.password.title);
    expect(server.lastWrite()!.path).toBe('/users/4/password-reset');
    const sent = server.writes()[0]!;
    expect(passwordField()!.value).toBe(sent.password);
    expect(
      screen.getByText(words.password.reset('user04', '담당자 4')),
    ).toBeTruthy();
    fireEvent.click(
      screen.getByRole('button', { name: words.password.confirm }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(rowOf('user04')).getByRole('button', {
          name: words.list.resetLabel('user04'),
        }),
      ),
    );
  });

  it('404 USER_NOT_FOUND → 「이 계정을 찾을 수 없어요」, [초기화] 꺼짐, 목록 다시 받음', async () => {
    const { server } = setup();
    server.override['POST /users/1/password-reset'] = () =>
      refusal(404, 'USER_NOT_FOUND');
    await listReady();
    fireEvent.click(
      within(rowOf('user01')).getByRole('button', {
        name: words.list.resetLabel('user01'),
      }),
    );
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.reset.submit }),
    );
    await screen.findByText(words.reset.missing);
    expect(
      within(dialog())
        .getByRole('button', { name: words.reset.submit })
        .hasAttribute('disabled'),
    ).toBe(true);
    await waitFor(() => expect(server.listCount()).toBe(2));
    expect(passwordField()).toBeNull();
  });
});

const badgeText = (username: string) =>
  rowOf(username).querySelector('[data-status]')!.textContent;
const check = (username: string) =>
  fireEvent.click(
    screen.getByRole('checkbox', { name: words.list.select(username) }),
  );
const toolbarButton = (name: string) => screen.getByRole('button', { name });
const search = (value: string) =>
  fireEvent.change(screen.getByLabelText(words.list.searchLabel), {
    target: { value },
  });
const pickStatus = (value: string) =>
  fireEvent.change(
    screen.getByRole('combobox', { name: words.list.statusLabel }),
    { target: { value } },
  );
/** 목록 요청(limit=100)의 쿼리들. */
const listQueries = (server: ReturnType<typeof setup>['server']) =>
  server.listQueries().filter((query) => query.get('limit') === '100');
/** 디바운스보다 조금 더 기다린다(그사이 요청이 생기지 않았음을 보려고). */
const pastDebounce = () =>
  act(
    () => new Promise((resolve) => setTimeout(resolve, SEARCH_DELAY_MS + 100)),
  );
/** 서버 거르기 흉내: q 가 든 요청에만 아이디가 그것을 품은 줄을 낸다(그 밖은 기본 답). */
const serverSearch =
  (server: ReturnType<typeof setup>['server']) => (url: URL) => {
    const q = url.searchParams.get('q');
    if (q === null || url.searchParams.get('limit') !== '100') return undefined;
    const results = server.accounts.filter((row) => row.username.includes(q));
    return json(200, { count: results.length, isNext: false, results });
  };

describe('④ 서버 거르기(UA1W ② — 가짜 서버는 거르지 않는다)', () => {
  it('상태 고르기는 공용 셀렉터 꼴(ENT-430 — 네이티브 select 그대로, OS 화살표 없음)', async () => {
    setup();
    await listReady();
    const select = screen.getByRole('combobox', {
      name: words.list.statusLabel,
    });
    expect(select.tagName).toBe('SELECT');
    const classes = select.className.split(/\s+/);
    expect(classes).toEqual(
      expect.arrayContaining(['appearance-none', 'rounded-component', 'px-4']),
    );
    expect(classes).not.toContain('rounded-control');
  });

  it('처음: 목록 한 번·전체 수 한 번, 설명의 개수는 전체 수(거른 count·줄 수가 아니다)', async () => {
    const { server } = setup();
    server.setCount({ total: 9, list: 3 });
    await listReady();
    await screen.findByText(words.list.description(9));
    expect(server.listCount()).toBe(1);
    expect(server.totalCount()).toBe(1);
    expect(screen.queryByText(words.list.description(3))).toBeNull();
    expect(screen.queryByText(words.list.description(4))).toBeNull();
  });

  it('검색 공백만 → 요청 없음, 「잠김」 → status=locked 이고 q 없음. 「 담당 」 → q=담당(다듬음)', async () => {
    const { server } = setup();
    await listReady();
    search('   ');
    await pastDebounce();
    expect(server.listCount()).toBe(1);
    pickStatus('locked');
    await waitFor(() => expect(server.listCount()).toBe(2));
    const locked = listQueries(server).at(-1)!;
    expect(locked.get('status')).toBe('locked');
    expect(locked.has('q')).toBe(false);
    expect(locked.has('companyId')).toBe(false);
    search(' 담당 ');
    await waitFor(() => expect(server.listCount()).toBe(3));
    expect(listQueries(server).at(-1)!.get('q')).toBe('담당');
    expect(listQueries(server).at(-1)!.get('status')).toBe('locked');
  });

  it('NUL 만 든 검색은 보내지 않는다, 150 코드 포인트에서 자른다, 칸의 maxLength 150', async () => {
    const { server } = setup();
    await listReady();
    expect(
      screen.getByLabelText(words.list.searchLabel).getAttribute('maxlength'),
    ).toBe('150');
    search('\u0000');
    await pastDebounce();
    expect(server.listCount()).toBe(1);
    search('😀'.repeat(151));
    await waitFor(() => expect(server.listCount()).toBe(2));
    expect(listQueries(server).at(-1)!.get('q')).toBe('😀'.repeat(150));
  });

  it('디바운스: 멈추기 전 두 글자는 요청 하나(마지막 글자)', async () => {
    const { server } = setup();
    await listReady();
    search('u');
    search('us');
    await waitFor(() => expect(server.listCount()).toBe(2));
    await pastDebounce();
    expect(server.listCount()).toBe(2);
    expect(listQueries(server).map((query) => query.get('q'))).toEqual([
      null,
      'us',
    ]);
  });

  it('「잠김」: 가짜가 돌려준 잠기지 않은 줄도 그대로 그린다(웹 다시 거르기 없음). 거르기를 바꿔도 전체 수는 다시 안 부르고 설명 그대로', async () => {
    const { server } = setup();
    server.setCount({ total: 9 });
    await listReady();
    pickStatus('locked');
    await waitFor(() => expect(server.listCount()).toBe(2));
    await waitFor(() =>
      expect(screen.getByText('user01', { selector: 'td' })).toBeTruthy(),
    );
    for (const username of ['user01', 'user02', 'user03', 'user04'])
      expect(screen.getByText(username, { selector: 'td' })).toBeTruthy();
    expect(server.totalCount()).toBe(1);
    expect(screen.getByText(words.list.description(9))).toBeTruthy();
  });

  it('늦은 답은 덮지 않는다: 「잠김」의 답이 「사용 중지」의 답보다 늦게 와도 「사용 중지」 줄', async () => {
    const { server } = setup();
    await listReady();
    let releaseLocked!: () => void;
    server.override['GET /users'] = (url) => {
      const status = url.searchParams.get('status');
      if (status === 'locked')
        return new Promise((resolve) => {
          releaseLocked = () =>
            resolve(
              json(200, {
                count: 1,
                isNext: false,
                results: [fakeAccount(21, { isLocked: true })],
              }),
            );
        });
      if (status === 'inactive')
        return json(200, {
          count: 1,
          isNext: false,
          results: [fakeAccount(22, { isActive: false })],
        });
      return undefined;
    };
    pickStatus('locked');
    await waitFor(() => expect(server.listCount()).toBe(2));
    pickStatus('inactive');
    await screen.findByText('user22', { selector: 'td' });
    await act(async () => releaseLocked());
    await act(() => new Promise((resolve) => setTimeout(resolve, 20)));
    expect(screen.queryByText('user21', { selector: 'td' })).toBeNull();
    expect(screen.getByText('user22', { selector: 'td' })).toBeTruthy();
  });

  it('거른 결과가 없으면 「조건에 맞는 계정이 없어요」, 거르지 않고 비면 「아직 만든 계정이 없어요」', async () => {
    const { server } = setup();
    server.override['GET /users'] = serverSearch(server);
    await listReady();
    search('user09');
    await screen.findByText(words.list.noMatch);
  });
});

describe('AD-01c 사용 중지·다시 사용(실서버 PATCH — id 마다 차례로)', () => {
  it('둘 고르고 [사용 중지] → 「계정 2개를 사용 중지할까요?」·고른 줄 목록 → 확인 → PATCH 둘(본문 {isActive:false})·모달 닫힘·고름 비움·목록 다시 받음·배지는 서버 값', async () => {
    const { server } = setup();
    await listReady();
    check('user01');
    check('user03');
    fireEvent.click(toolbarButton(words.list.deactivate));
    const modal = dialog();
    expect(
      within(modal).getByText(words.active.deactivateTitle(2)),
    ).toBeTruthy();
    expect(
      within(modal).getByText(words.active.who('user01', '담당자 1')),
    ).toBeTruthy();
    expect(
      within(modal).getByText(words.active.deactivateBody(ACCESS_TTL_MINUTES)),
    ).toBeTruthy();
    fireEvent.click(
      within(modal).getByRole('button', { name: words.active.deactivate }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(server.patches()).toEqual([
      { id: 1, body: '{"isActive":false}' },
      { id: 3, body: '{"isActive":false}' },
    ]);
    await waitFor(() =>
      expect(badgeText('user01')).toBe(words.status.inactive),
    );
    expect(badgeText('user03')).toBe(words.status.inactive);
    expect(badgeText('user02')).toBe(words.status.locked);
    expect(server.listCount()).toBe(2);
    expect(
      (
        screen.getByRole('checkbox', {
          name: words.list.select('user01'),
        }) as HTMLButtonElement
      ).getAttribute('data-state'),
    ).toBe('unchecked');
  });

  it('셋 중 하나가 500 → 모달 유지·계정 목록이 그 하나만·빨강 한 줄(버튼 줄 위)·고름도 그 하나. 성공분은 배지에. 다시 확인하면 닫힘', async () => {
    const { server } = setup();
    server.override['PATCH /users/3'] = [() => refusal(500, 'INTERNAL_ERROR')];
    await listReady();
    check('user01');
    check('user02');
    check('user03');
    fireEvent.click(toolbarButton(words.list.deactivate));
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.active.deactivate }),
    );
    const failure = await within(dialog()).findByTestId('active-failure');
    expect(failure.getAttribute('role')).toBe('alert');
    // 성공 둘을 앞에 말한다(디자인 대조 C1)
    expect(failure.textContent).toBe(words.active.deactivatePartly(2, 1));
    // 버튼 줄 바로 위(디자인 원문 Q4)
    expect(failure.nextElementSibling?.querySelector('button')).not.toBeNull();
    const modal = dialog();
    expect(
      within(modal).getByText(words.active.deactivateTitle(1)),
    ).toBeTruthy();
    expect(
      within(modal).getByText(words.active.who('user03', '담당자 3')),
    ).toBeTruthy();
    expect(
      within(modal).queryByText(words.active.who('user01', '담당자 1')),
    ).toBeNull();
    expect(server.patches().map((call) => call.id)).toEqual([1, 2, 3]);
    await waitFor(() =>
      expect(badgeText('user01')).toBe(words.status.inactive),
    );
    expect(badgeText('user02')).toBe(words.status.inactive);
    const checked = (username: string) =>
      screen
        .getByRole('checkbox', {
          name: words.list.select(username),
          hidden: true,
        })
        .getAttribute('data-state');
    expect(checked('user01')).toBe('unchecked');
    expect(checked('user03')).toBe('checked');
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.active.deactivate }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(server.patches().map((call) => call.id)).toEqual([1, 2, 3, 3]);
    await waitFor(() =>
      expect(badgeText('user03')).toBe(words.status.inactive),
    );
  });

  it.each([
    [
      '사용 중지',
      [fakeAccount(1), fakeAccount(2)],
      words.list.deactivate,
      words.active.deactivate,
      words.active.deactivatePartly(1, 1),
    ],
    [
      '다시 사용',
      [
        fakeAccount(1, { isActive: false }),
        fakeAccount(2, { isActive: false }),
      ],
      words.list.reactivate,
      words.active.reactivate,
      words.active.reactivatePartly(1, 1),
    ],
  ])(
    '%s 성공 1·실패 1 → 「계정 1개는 …했어요. 1개는 …하지 못했어요」(성공 수는 어댑터의 done)',
    async (_, rows, open, confirm, text) => {
      const { server } = setup(rows);
      server.override['PATCH /users/2'] = () => refusal(500, 'INTERNAL_ERROR');
      await listReady();
      check('user01');
      check('user02');
      fireEvent.click(toolbarButton(open));
      fireEvent.click(within(dialog()).getByRole('button', { name: confirm }));
      expect(
        (await within(dialog()).findByTestId('active-failure')).textContent,
      ).toBe(text);
    },
  );

  it('사용 중지 둘 다 실패(성공 0) → 실패 글 그대로', async () => {
    const { server } = setup();
    server.override['PATCH /users/1'] = () => refusal(500, 'INTERNAL_ERROR');
    server.override['PATCH /users/3'] = () => refusal(500, 'INTERNAL_ERROR');
    await listReady();
    check('user01');
    check('user03');
    fireEvent.click(toolbarButton(words.list.deactivate));
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.active.deactivate }),
    );
    expect(
      (await within(dialog()).findByTestId('active-failure')).textContent,
    ).toBe(words.active.deactivateFailed(2));
  });

  it('모두 실패해도 같은 꼴(다시 사용 — 「다시 사용하지 못했어요」)', async () => {
    const { server } = setup();
    server.override['PATCH /users/4'] = () => refusal(500, 'INTERNAL_ERROR');
    await listReady();
    check('user04');
    fireEvent.click(toolbarButton(words.list.reactivate));
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.active.reactivate }),
    );
    expect(
      (await within(dialog()).findByTestId('active-failure')).textContent,
    ).toBe(words.active.reactivateFailed(1));
    expect(
      within(dialog()).getByText(words.active.who('user04', '담당자 4')),
    ).toBeTruthy();
  });

  it('고른 계정이 모두 사용 중지면 같은 자리가 [다시 사용] → 확인 → PATCH {isActive:true} → 배지가 서버 값(초기화 대기)', async () => {
    const { server } = setup();
    await listReady();
    check('user04');
    fireEvent.click(toolbarButton(words.list.reactivate));
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.active.reactivate }),
    );
    await waitFor(() => expect(badgeText('user04')).toBe(words.status.initial));
    expect(server.patches()).toEqual([{ id: 4, body: '{"isActive":true}' }]);
  });

  it('[전체 고르기] 는 보이는 줄(서버가 거른 줄)만 고른다', async () => {
    const { server } = setup();
    server.override['GET /users'] = serverSearch(server);
    await listReady();
    search('user02');
    await waitFor(() =>
      expect(screen.queryByText('user01', { selector: 'td' })).toBeNull(),
    );
    fireEvent.click(
      screen.getByRole('checkbox', { name: words.list.selectAll }),
    );
    fireEvent.click(toolbarButton(words.list.deactivate));
    expect(
      within(dialog()).getByText(words.active.deactivateTitle(1)),
    ).toBeTruthy();
  });
});

describe('이름 고침(실서버 PATCH {name})', () => {
  const startEditing = (username: string) =>
    fireEvent.click(
      screen.getByRole('button', { name: words.list.editName(username) }),
    );
  const nameInput = () =>
    screen.getByRole('textbox', {
      name: words.list.nameLabel,
    }) as HTMLInputElement;

  it('이름 칸 단추 → 편집 중(입력 칸·「편집 중」·[저장] 켜짐) → 「  재무팀  」 [저장] → PATCH /users/1 본문 {"name":"재무팀"}(다듬음) → 편집 끝·서버 이름', async () => {
    const { server } = setup();
    await listReady();
    expect(toolbarButton(words.list.save).hasAttribute('disabled')).toBe(true);
    startEditing('user01');
    const row = rowOf('user01');
    expect(row.getAttribute('data-editing')).toBe('true');
    expect(within(row).getByText(words.list.editing)).toBeTruthy();
    const input = within(row).getByRole('textbox', {
      name: words.list.nameLabel,
    });
    expect(document.activeElement).toBe(input);
    fireEvent.change(input, { target: { value: '  재무팀  ' } });
    fireEvent.click(toolbarButton(words.list.save));
    await screen.findByText('재무팀', { selector: 'button' });
    expect(server.patches()).toEqual([{ id: 1, body: '{"name":"재무팀"}' }]);
    expect(rowOf('user01').getAttribute('data-editing')).toBeNull();
    expect(server.accounts[0]!.name).toBe('재무팀');
  });

  it('같은 이름(앞뒤 공백만 다름)이면 PATCH 0, 편집만 끝난다', async () => {
    const { server } = setup();
    await listReady();
    startEditing('user02');
    fireEvent.change(nameInput(), { target: { value: ' 담당자 2 ' } });
    fireEvent.keyDown(nameInput(), { key: 'Enter' });
    await waitFor(() =>
      expect(rowOf('user02').getAttribute('data-editing')).toBeNull(),
    );
    expect(server.patches()).toEqual([]);
  });

  it.each([
    [
      '422',
      () => refusal(422, 'VALIDATION_ERROR', { name: ['길이'] }),
      words.list.rename.invalid,
    ],
    ['500', () => refusal(500, 'INTERNAL_ERROR'), words.list.rename.failed],
    [
      '연결 끊김',
      () => Promise.reject(new TypeError('끊김')),
      words.list.rename.failed,
    ],
  ])(
    '%s → 단추 무리 옆 한 줄(role=alert)·편집 유지(입력 그대로)',
    async (_, answer, text) => {
      const { server } = setup();
      server.override['PATCH /users/2'] = answer;
      await listReady();
      startEditing('user02');
      fireEvent.change(nameInput(), { target: { value: '법무팀' } });
      fireEvent.click(toolbarButton(words.list.save));
      const error = await screen.findByTestId('rename-error');
      await waitFor(() => expect(error.textContent).toBe(text));
      expect(error.getAttribute('role')).toBe('alert');
      expect(rowOf('user02').getAttribute('data-editing')).toBe('true');
      expect(nameInput().value).toBe('법무팀');
      expect(document.body.textContent).not.toContain('지어낸-');
      expect(server.patches()).toHaveLength(1);
    },
  );

  it('404 → 「이 계정을 찾을 수 없어요」, 편집 끝, 목록 다시 받음', async () => {
    const { server } = setup();
    server.override['PATCH /users/2'] = () => refusal(404, 'USER_NOT_FOUND');
    await listReady();
    startEditing('user02');
    fireEvent.change(nameInput(), { target: { value: '법무팀' } });
    fireEvent.click(toolbarButton(words.list.save));
    await waitFor(() =>
      expect(screen.getByTestId('rename-error').textContent).toBe(
        words.list.rename.missing,
      ),
    );
    expect(rowOf('user02').getAttribute('data-editing')).toBeNull();
    await waitFor(() => expect(server.listCount()).toBe(2));
  });

  it('편집 중 Esc = [취소](이름 그대로·PATCH 0), Enter = [저장]. 다듬어 빈 이름은 [저장] 꺼짐', async () => {
    const { server } = setup();
    await listReady();
    startEditing('user02');
    fireEvent.change(nameInput(), { target: { value: '바꾸다 만 이름' } });
    fireEvent.keyDown(nameInput(), { key: 'Escape' });
    expect(
      screen.queryByRole('textbox', { name: words.list.nameLabel }),
    ).toBeNull();
    expect(rowOf('user02').textContent).toContain('담당자 2');
    expect(server.patches()).toEqual([]);
    startEditing('user02');
    fireEvent.change(nameInput(), { target: { value: '   ' } });
    expect(toolbarButton(words.list.save).hasAttribute('disabled')).toBe(true);
    fireEvent.change(nameInput(), { target: { value: '법무팀' } });
    fireEvent.keyDown(nameInput(), { key: 'Enter' });
    await screen.findByText('법무팀', { selector: 'button' });
    expect(server.patches()).toEqual([{ id: 2, body: '{"name":"법무팀"}' }]);
  });
});

describe('「준비 중」 글 없음 — 쓰기 단추는 늘 켬(MARC-ENT-285)', () => {
  it('준비 중 글 0, 이름 칸은 단추, [사용 중지] 는 고른 것이 있을 때만 켬(aria-disabled 없음)', async () => {
    setup();
    await listReady();
    expect(document.body.textContent).not.toContain('준비 중');
    expect(
      screen.getByRole('button', { name: words.list.editName('user01') }),
    ).toBeTruthy();
    expect(
      toolbarButton(words.list.deactivate).getAttribute('aria-disabled'),
    ).toBe('true');
    check('user01');
    expect(
      toolbarButton(words.list.deactivate).hasAttribute('aria-disabled'),
    ).toBe(false);
    fireEvent.click(toolbarButton(words.list.deactivate));
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});

/** AD-01b 가 떠 있을 때 Esc·바깥 누름(덮개 pointerdown)으로 닫히지 않고 값이 그대로인가. */
async function staysOpen(secret: unknown) {
  fireEvent.keyDown(document.activeElement ?? document.body, {
    key: 'Escape',
  });
  // Radix 는 바깥 누름 듣기를 한 틱 늦게 단다.
  await act(() => new Promise((resolve) => setTimeout(resolve, 0)));
  fireEvent.pointerDown(document.body);
  fireEvent.pointerUp(document.body);
  fireEvent.click(document.body);
  await act(() => new Promise((resolve) => setTimeout(resolve, 0)));
  expect(screen.queryByRole('dialog')).not.toBeNull();
  expect(passwordField()?.value).toBe(secret);
}

describe('AD-01b 는 [확인]으로만 닫힌다(감독 판단 15)', () => {
  it('만들기 흐름: Esc·바깥 누름에 안 닫히고 값이 그대로', async () => {
    const { server } = setup();
    await openCreate();
    fill('user07', '담당자 G');
    fireEvent.click(submitButton());
    await screen.findByText(words.password.title);
    await staysOpen(server.writes()[0]!.password);
  });

  it('초기화 흐름: Esc·바깥 누름에 안 닫히고 값이 그대로', async () => {
    const { server } = setup();
    await listReady();
    fireEvent.click(
      within(rowOf('user01')).getByRole('button', {
        name: words.list.resetLabel('user01'),
      }),
    );
    fireEvent.click(
      within(dialog()).getByRole('button', { name: words.reset.submit }),
    );
    await screen.findByText(words.password.title);
    await staysOpen(server.writes()[0]!.password);
  });

  it('(대조) 만들기 입력 단계에서는 Esc 로 닫힌다 — 위 두 시험이 빈 검사가 아니다', async () => {
    setup();
    await openCreate();
    fireEvent.keyDown(document.activeElement ?? document.body, {
      key: 'Escape',
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });
});

describe('가지 리뷰 지적(④)', () => {
  it('(1) 거르기에 숨은 고름은 [사용 중지] 에 끼지 않는다(보이는 줄만)', async () => {
    const { server } = setup();
    server.override['GET /users'] = serverSearch(server);
    await listReady();
    check('user01');
    search('user02');
    await waitFor(() =>
      expect(screen.queryByText('user01', { selector: 'td' })).toBeNull(),
    );
    check('user02');
    fireEvent.click(toolbarButton(words.list.deactivate));
    const modal = dialog();
    expect(
      within(modal).getByText(words.active.deactivateTitle(1)),
    ).toBeTruthy();
    expect(
      within(modal).queryByText(words.active.who('user01', '담당자 1')),
    ).toBeNull();
  });

  it('(2) 이름 칸에서 한글 조합 중의 Enter·Esc 는 저장·취소하지 않는다', async () => {
    setup();
    await listReady();
    fireEvent.click(
      screen.getByRole('button', { name: words.list.editName('user01') }),
    );
    const input = screen.getByRole('textbox', { name: words.list.nameLabel });
    fireEvent.change(input, { target: { value: '재무' } });
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    fireEvent.keyDown(input, { key: 'Escape', isComposing: true });
    expect(
      screen.getByRole('textbox', { name: words.list.nameLabel }),
    ).toBeTruthy();
    fireEvent.keyDown(input, { key: 'Enter' });
    await screen.findByText('재무', { selector: 'button' });
  });

  it.each([
    ['쓰기 실패(500)', () => refusal(500, 'INTERNAL_ERROR')],
    ['409', () => refusal(409, 'USERNAME_TAKEN')],
  ])(
    '(3) 만들기 %s 뒤 목록을 다시 받는다(행이 생겼을 수 있다)',
    async (_, answer) => {
      const { server } = setup();
      server.override['POST /users'] = answer;
      await openCreate();
      fill('user07', '담당자 G');
      fireEvent.click(submitButton());
      await waitFor(() => expect(server.listCount()).toBe(2));
    },
  );

  it('(3) 422 칸 오류 뒤에는 다시 받지 않는다(행이 생기지 않았다)', async () => {
    const { server } = setup();
    server.override['POST /users'] = () =>
      refusal(422, 'VALIDATION_ERROR', { name: ['길이'] });
    await openCreate();
    fill('user07', '담당자 G');
    fireEvent.click(submitButton());
    await screen.findByText(words.create.invalid);
    expect(server.listCount()).toBe(1);
  });
});

describe('이름 편집이 끝나면 초점은 그 줄의 이름 칸 단추로', () => {
  it.each([
    [
      'Esc',
      (input: HTMLElement) => fireEvent.keyDown(input, { key: 'Escape' }),
    ],
    [
      'Enter',
      (input: HTMLElement) => fireEvent.keyDown(input, { key: 'Enter' }),
    ],
    ['[저장]', () => fireEvent.click(toolbarButton(words.list.save))],
    ['[취소]', () => fireEvent.click(toolbarButton(words.list.cancel))],
  ])('%s 뒤', async (_, finish) => {
    setup();
    await listReady();
    fireEvent.click(
      screen.getByRole('button', { name: words.list.editName('user02') }),
    );
    const input = screen.getByRole('textbox', { name: words.list.nameLabel });
    fireEvent.change(input, { target: { value: '법무팀' } });
    finish(input);
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: words.list.editName('user02') }),
      ),
    );
  });
});

// 밴드 DT1(이슈 189 의 C3·C4·C10b·C11): jsdom 은 크기를 못 재므로 클래스(토큰 이름)로 본다.
describe('DT1 생김새 — 필수 점·확인 모달 가운데·AD-01b 누구 줄·[복사]', () => {
  const labelOf = (name: string) =>
    [...dialog().querySelectorAll('label')].find((node) =>
      node.textContent?.startsWith(name),
    )!;

  it('C4 AD-01a 아이디·이름 라벨: 빨간 「*」 글자 없이 필수 점(RequiredMark) 하나', async () => {
    setup();
    await openCreate();
    for (const name of [words.create.username, words.create.name]) {
      const label = labelOf(name);
      expect(label.textContent).toBe(name);
      expect(label.querySelectorAll('[data-required-mark]')).toHaveLength(1);
      expect(label.querySelector('.text-support-error-accent')).toBeNull();
    }
  });

  it('C3·C11 AD-01b: 누구 줄 pre-caption-02 tertiary, [복사]는 md 꼴에 h-10(lg 아님)', async () => {
    setup();
    await openCreate();
    fill('user07', '담당자 G');
    fireEvent.click(submitButton());
    await screen.findByText(words.password.title);
    const who = within(dialog()).getByTestId('who');
    expect(who.className).toContain('text-style-pre-caption-02');
    expect(who.className).toContain('text-text-tertiary');
    expect(who.className).not.toContain('text-style-pre-body-04');
    const copyButton = screen.getByRole('button', {
      name: words.password.copy,
    });
    expect(copyButton.className).toContain('h-10');
    expect(copyButton.className).toContain('text-style-pre-body-05');
    expect(copyButton.className).not.toContain('text-style-pre-body-01');
    // 제목은 왼쪽 그대로(판정 2 — 폼·결과 모달)
    expect(screen.getByText(words.password.title).className).not.toContain(
      'text-center',
    );
  });

  it('C10b 초기화 확인: 제목·본문 가운데', async () => {
    setup();
    await listReady();
    fireEvent.click(
      within(rowOf('user04')).getByRole('button', {
        name: words.list.resetLabel('user04'),
      }),
    );
    expect(screen.getByText(words.reset.title('user04')).className).toContain(
      'text-center',
    );
    expect(screen.getByText(words.reset.body).className).toContain(
      'text-center',
    );
  });

  it('C10b AD-01c 사용 중지 확인: 제목·본문 가운데, 계정 목록 14/500 primary(왼쪽 — Q10)', async () => {
    setup();
    await listReady();
    check('user01');
    fireEvent.click(toolbarButton(words.list.deactivate));
    const modal = dialog();
    expect(
      within(modal).getByText(words.active.deactivateTitle(1)).className,
    ).toContain('text-center');
    expect(
      within(modal).getByText(words.active.deactivateBody(ACCESS_TTL_MINUTES))
        .className,
    ).toContain('text-center');
    const list = within(modal)
      .getByText(words.active.who('user01', '담당자 1'))
      .closest('ul')!;
    expect(list.className).toContain('text-style-pre-body-05');
    expect(list.className).toContain('text-text-primary');
    expect(list.className).not.toContain('text-center');
  });
});
