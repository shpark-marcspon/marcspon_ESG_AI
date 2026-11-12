// @vitest-environment jsdom
// 로그인 경로·가드 시험(밴드 LG1 ②). createAppRouter 에 메모리 기록과 가짜 로그인 서버(entities/session/api/testing.ts)를 넣어 본다.
//   ① 가드 표: 안 로그인·admin·service·isInitial 이 업무 주소·/login·/password·/ 를 열 때 ② 로그인(CM-01·01a·01b) → 역할별 첫 화면
//   ③ 세션이 바뀌면 가드가 다시 돈다(만료 → /login 에 안내) ④ StrictMode 로 그려도 부팅 복원의 refresh 는 한 번.
import { StrictMode } from 'react';

import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeAuthServer,
  memoryStorage,
} from '../../entities/session/api/testing.ts';
import type { FakeUser } from '../../entities/session/api/testing.ts';
import { SESSION_TEXT } from '../../entities/session/config/text.ts';
import { REFRESH_STORAGE_KEY } from '../../entities/session/model/index.ts';
import { createAppRouter } from '../router.tsx';

afterEach(cleanup);
vi.setConfig({ testTimeout: 20_000 });
const WAIT = { timeout: 8_000 };

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
const words = SESSION_TEXT.login;

const accounts = (): Record<string, FakeUser> => ({
  'ops.admin': { password: 'admin-pass-1', kind: 'admin' },
  user01: { password: 'service-pass-1', kind: 'service' },
  user03: { password: 'temp-pass-1', kind: 'service', isInitial: true },
});

// 지연 로드 화면(lazyRouteComponent)을 미리 불러 둔다 — 부하 아래 첫 waitFor 가 모듈 로드를 기다리지 않게(예열, sid:MARC-ISSUE-318).
// 경로 파일을 직접 가져오지 않고(칸 규칙) 버리는 라우터 하나의 경로 조각을 모두 싣는다. 모듈은 한 번 실리면 다음 라우터도 바로 쓴다.
beforeAll(async () => {
  const router = createAppRouter({
    history: createMemoryHistory(),
    openPdf: () => new Promise(() => {}),
    session: {
      send: fakeAuthServer(accounts(), { baseUrl: BASE }).send,
      storage: memoryStorage(),
      baseUrl: BASE,
    },
  });
  await Promise.all(
    Object.values(router.routesById).map((route) =>
      router.loadRouteChunk(route),
    ),
  );
}, 60_000);

/** 라우터 하나. signedIn 이면 그 계정의 refresh 를 보관소에 심는다(새로고침 뒤의 꼴). */
function setup(path: string, { signedIn }: { signedIn?: string } = {}) {
  const server = fakeAuthServer(accounts(), { baseUrl: BASE });
  const storage = memoryStorage();
  if (signedIn)
    storage.setItem(REFRESH_STORAGE_KEY, server.issue(signedIn).refresh);
  const history = createMemoryHistory({ initialEntries: [path] });
  const router = createAppRouter({
    history,
    openPdf: () => new Promise(() => {}),
    session: { send: server.send, storage, baseUrl: BASE },
  });
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  const session = router.options.context.session;
  return { server, storage, history, router, session };
}

const pathOf = (history: { location: { pathname: string } }) =>
  history.location.pathname;
const atPath = (history: { location: { pathname: string } }, path: string) =>
  waitFor(() => expect(pathOf(history)).toBe(path), WAIT);
const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );

async function typeLogin(username: string, password: string) {
  await screenShown('login');
  fireEvent.change(screen.getByLabelText(words.username), {
    target: { value: username },
  });
  fireEvent.change(screen.getByLabelText(words.password), {
    target: { value: password },
  });
}
/** [로그인] 단추. 제출 중에는 이름이 도는 표시의 이름(「로그인하는 중」)으로 바뀌어 type 으로 찾는다. */
const submitButton = () =>
  document.querySelector<HTMLButtonElement>('form button[type="submit"]')!;

describe('가드 ① 안 로그인', () => {
  it.each([
    '/greenwash',
    '/greenwash/runs/run-1',
    '/admin/accounts',
    '/password',
    '/',
    '/zzz',
  ])(
    '%s → /login(replace), 서버는 부르지 않는다(보관소에 refresh 없음)',
    async (path) => {
      const { history, server } = setup(path);
      await atPath(history, '/login');
      await screenShown('login');
      expect(history.length).toBe(1);
      expect(server.calls).toEqual([]);
    },
  );
});

describe('가드 ① 복원된 세션(새로고침 뒤)', () => {
  it.each([
    ['user01', '/', '/greenwash'],
    ['user01', '/login', '/greenwash'],
    ['user01', '/password', '/greenwash'],
    ['user01', '/admin/accounts', '/greenwash'],
    ['user01', '/greenwash/xyz', '/greenwash'],
    ['ops.admin', '/', '/admin/accounts'],
    // 밴드 SV1(sid:MARC-ENT-286): 운영 관리자도 /greenwash/** 를 연다(발주서 §2 바뀌는 단언 2).
    ['ops.admin', '/greenwash', '/greenwash'],
    [
      'ops.admin',
      '/greenwash/runs/run-1/review',
      '/greenwash/runs/run-1/review',
    ],
    ['ops.admin', '/login', '/admin/accounts'],
    ['ops.admin', '/zzz', '/admin/accounts'],
  ])('%s 가 %s 를 열면 %s', async (who, path, landing) => {
    const { history } = setup(path, { signedIn: who });
    await atPath(history, landing);
    expect(history.length).toBe(1);
  });

  it('고객사 사용자는 /greenwash/** 그대로(목록이 뜬다)', async () => {
    const { history } = setup('/greenwash/new', { signedIn: 'user01' });
    await screenShown('new');
    expect(pathOf(history)).toBe('/greenwash/new');
  });

  it('운영 관리자는 /admin/accounts 그대로(빈 자리표)', async () => {
    const { history } = setup('/admin/accounts', { signedIn: 'ops.admin' });
    await screenShown('admin-accounts');
    expect(pathOf(history)).toBe('/admin/accounts');
  });

  it('[B2] isInitial 인데 임시 비밀번호가 메모리에 없음(새로고침) → revoke → 세션 비움 → /login 에 「임시 비밀번호로 다시 로그인」(회색 안내 띠)', async () => {
    const { history, server, storage } = setup('/password', {
      signedIn: 'user03',
    });
    await atPath(history, '/login');
    const notice = await screen.findByRole('status', {}, WAIT);
    expect(notice.textContent).toBe('임시 비밀번호로 다시 로그인해 주세요');
    // 오류 띠가 아니라 회색 안내 띠(디자인 감독 ④)
    expect(notice.getAttribute('data-tone')).toBe('default');
    // 카드 안 그대로(밴드 DT1 C1 은 세션 끝남만 카드 위로)
    expect(
      document
        .querySelector('main[data-screen="login"] > section')!
        .contains(notice),
    ).toBe(true);
    expect(server.count('POST /auth/revoke')).toBe(1);
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('[ⓓ] StrictMode 로 그려도 부팅 복원의 refresh 는 한 번', async () => {
    const { history, server } = setup('/greenwash', { signedIn: 'user01' });
    await screenShown('list');
    expect(pathOf(history)).toBe('/greenwash');
    expect(server.count('POST /auth/refresh')).toBe(1);
    expect(server.count('GET /users/me')).toBe(1);
  });
});

describe('로그인 ② CM-01·01a·01b', () => {
  it('두 칸 다 차야 [로그인] 이 켜진다. 아이디 저장·회원가입은 없다', async () => {
    setup('/login');
    await screenShown('login');
    expect(submitButton()).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByLabelText(words.username), {
      target: { value: 'user01' },
    });
    expect(submitButton()).toHaveProperty('disabled', true);
    fireEvent.change(screen.getByLabelText(words.password), {
      target: { value: 'x' },
    });
    expect(submitButton()).toHaveProperty('disabled', false);
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(
      screen.getByLabelText(words.username).getAttribute('autocomplete'),
    ).toBe('username');
    expect(
      screen.getByLabelText(words.password).getAttribute('autocomplete'),
    ).toBe('current-password');
  });

  it('고객사 사용자 로그인(Enter 로 제출) → /greenwash, companySubdomain 은 보내지 않는다', async () => {
    const { history, server } = setup('/login');
    await typeLogin('user01', 'service-pass-1');
    fireEvent.submit(submitButton().closest('form')!);
    await atPath(history, '/greenwash');
    await screenShown('list');
    expect(JSON.parse(server.calls[0]!.body)).toEqual({
      username: 'user01',
      password: 'service-pass-1',
    });
  });

  it('운영 관리자 로그인 → /admin/accounts', async () => {
    const { history } = setup('/login');
    await typeLogin('ops.admin', 'admin-pass-1');
    fireEvent.click(submitButton());
    await atPath(history, '/admin/accounts');
    await screenShown('admin-accounts');
  });

  it('isInitial 로그인 → /password(임시 비밀번호는 메모리에)', async () => {
    const { history, session } = setup('/login');
    await typeLogin('user03', 'temp-pass-1');
    fireEvent.click(submitButton());
    await atPath(history, '/password');
    expect(session.hasTemporaryPassword()).toBe(true);
  });

  it('[ⓒ] 틀린 비밀번호(01a): 한 글(role=alert), 비밀번호 칸을 비우고 그리로 초점, 주소 그대로', async () => {
    const { history } = setup('/login');
    await typeLogin('user01', 'nope');
    fireEvent.click(submitButton());
    const alert = await screen.findByRole('alert', {}, WAIT);
    expect(alert.textContent).toBe(words.invalid);
    expect(alert.textContent).toBe(
      '아이디 또는 비밀번호가 맞지 않아요. 다시 확인해 주세요.',
    );
    const password = screen.getByLabelText(words.password) as HTMLInputElement;
    expect(password.value).toBe('');
    expect(document.activeElement).toBe(password);
    expect(pathOf(history)).toBe('/login');
  });

  it('없는 아이디·꼴 틀린 아이디(422)도 같은 글', async () => {
    setup('/login');
    await typeLogin('no such!', 'x');
    fireEvent.click(submitButton());
    expect((await screen.findByRole('alert', {}, WAIT)).textContent).toBe(
      words.invalid,
    );
  });

  it('[잠금] 401 ACCOUNT_LOCKED 는 틀림 글과 따로 잠김 글', async () => {
    const { server } = setup('/login');
    server.users.user01!.locked = true;
    await typeLogin('user01', 'service-pass-1');
    fireEvent.click(submitButton());
    const alert = await screen.findByRole('alert', {}, WAIT);
    expect(alert.textContent).toBe(words.locked);
    expect(alert.textContent).not.toBe(words.invalid);
    expect(alert.getAttribute('data-reason')).toBe('locked');
  });

  it('5xx·연결 끊김 → 「로그인하지 못했어요」, 칸은 그대로', async () => {
    const { server } = setup('/login');
    server.override['POST /auth/login'] = () => {
      throw new TypeError('fetch failed');
    };
    await typeLogin('user01', 'service-pass-1');
    fireEvent.click(submitButton());
    expect((await screen.findByRole('alert', {}, WAIT)).textContent).toBe(
      words.failed,
    );
    expect(
      (screen.getByLabelText(words.password) as HTMLInputElement).value,
    ).toBe('service-pass-1');
  });

  it('제출 중에는 두 번 보내지 않는다(단추 안 도는 표시)', async () => {
    const { server, history } = setup('/login');
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.override['POST /auth/login'] = async () => {
      await gate;
      return new Response(JSON.stringify(server.issue('user01')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };
    await typeLogin('user01', 'service-pass-1');
    fireEvent.click(submitButton());
    fireEvent.click(submitButton());
    fireEvent.submit(submitButton().closest('form')!);
    expect(submitButton().getAttribute('aria-busy')).toBe('true');
    expect(screen.getByLabelText(words.submitting)).toBeTruthy();
    release();
    await atPath(history, '/greenwash');
    expect(
      server.calls.filter((call) => call.path === '/auth/login'),
    ).toHaveLength(1);
  });

  it('비밀번호 보기 단추는 aria-pressed 로 켜짐을 알리고 칸을 글자로 보인다', async () => {
    setup('/login');
    await screenShown('login');
    const toggle = screen.getByRole('button', { name: words.showPassword });
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByLabelText(words.password).getAttribute('type')).toBe(
      'text',
    );
  });

  it('[DT1 C2] 아이디·비밀번호 칸과 [로그인]은 40(h-10 · 버튼 lg) — 48(h-12) 아님', async () => {
    setup('/login');
    await screenShown('login');
    const username = screen.getByLabelText(words.username);
    const password = screen.getByLabelText(words.password);
    for (const field of [username, password]) {
      expect(field.className).toContain('h-10');
      expect(field.className).not.toMatch(/\bh-12\b/);
    }
    expect(submitButton().className).toContain('h-10');
    expect(submitButton().className).not.toMatch(/\bh-12\b/);
  });

  it('CM-01b: 「비밀번호를 잊으셨나요?」 → 모달 → [확인] 으로 닫으면 글 단추로 초점', async () => {
    setup('/login');
    await screenShown('login');
    const forgot = screen.getByRole('button', { name: words.forgot });
    act(() => forgot.focus());
    fireEvent.click(forgot);
    const dialog = await screen.findByRole(
      'dialog',
      { name: SESSION_TEXT.forgot.title },
      WAIT,
    );
    expect(dialog.textContent).toContain(SESSION_TEXT.forgot.body);
    // 밴드 DT1 C8: [확인] 최소 폭 96(시안 .c-modal .foot .e-btn)
    expect(
      screen.getByRole('button', { name: SESSION_TEXT.forgot.confirm })
        .className,
    ).toContain('min-w-24');
    fireEvent.click(
      screen.getByRole('button', { name: SESSION_TEXT.forgot.confirm }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull(), WAIT);
    await waitFor(() => expect(document.activeElement).toBe(forgot), WAIT);
  });
});

describe('세션 바뀜 ③ — 가드가 다시 돈다', () => {
  it('refresh 실패(만료) → /login 에 「로그인이 끝났어요. 다시 로그인해 주세요」', async () => {
    const { history, server, session } = setup('/greenwash', {
      signedIn: 'user01',
    });
    await screenShown('list');
    server.expireAccess();
    server.override['POST /auth/refresh'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'TOKEN_NOT_VALID',
            message: 'x',
            fields: null,
            legacyCode: 'token_not_valid',
          },
        }),
        { status: 444, headers: { 'Content-Type': 'application/json' } },
      );
    await act(async () => {
      await session.api.client.GET('/users/me').catch(() => undefined);
    });
    await atPath(history, '/login');
    const notice = await screen.findByRole('status', {}, WAIT);
    expect(notice.textContent).toBe(SESSION_TEXT.notice.expired);
    expect(notice.textContent).toBe('로그인이 끝났어요. 다시 로그인해 주세요');
    // 밴드 DT1 C1(시안 CM-03 상태 예시 7): 카드 **위** 주황 띠(important) + 정보 아이콘, 카드와 같은 440 폭. 카드 안에는 없다.
    expect(notice.getAttribute('data-tone')).toBe('important');
    const card = document.querySelector('main[data-screen="login"] > section')!;
    expect(card.contains(notice)).toBe(false);
    expect(
      notice.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(notice.parentElement!.className).toContain('w-[440px]');
    expect(notice.querySelector('svg')).not.toBeNull();
    expect(document.querySelectorAll('[data-reason="expired"]')).toHaveLength(
      1,
    );
  });

  it('로그아웃(세션 층) → /login, 안내 없음', async () => {
    const { history, session } = setup('/admin/accounts', {
      signedIn: 'ops.admin',
    });
    await screenShown('admin-accounts');
    await act(() => session.logout());
    await atPath(history, '/login');
    await screenShown('login');
    expect(screen.queryByRole('status')).toBeNull();
  });
});

const pw = SESSION_TEXT.password;

/** user03(isInitial)으로 로그인해 CM-02 에 선다. */
async function atPasswordChange() {
  const context = setup('/login');
  await typeLogin('user03', 'temp-pass-1');
  fireEvent.click(submitButton());
  await atPath(context.history, '/password');
  await screenShown('password');
  return context;
}
/** CM-02 의 두 칸(새 비밀번호·확인). 라벨 글이 서로를 품어(「새 비밀번호」⊂「새 비밀번호 확인」) 차례로 찾는다. */
const newInput = () =>
  document.querySelectorAll<HTMLInputElement>('form input')[0]!;
const confirmInput = () =>
  document.querySelectorAll<HTMLInputElement>('form input')[1]!;
const changeButton = () =>
  document.querySelector<HTMLButtonElement>('form button[type="submit"]')!;
function typeNew(next: string, again: string) {
  fireEvent.change(newInput(), { target: { value: next } });
  fireEvent.change(confirmInput(), { target: { value: again } });
}

describe('비밀번호 바꾸기 ③ CM-02', () => {
  it('제목·안내·「{아이디} · 임시 비밀번호로 로그인함」, 지금 비밀번호 칸은 없다', async () => {
    await atPasswordChange();
    expect(screen.getByRole('heading', { name: pw.title })).toBeTruthy();
    expect(screen.getByText(pw.lead)).toBeTruthy();
    expect(screen.getByTestId('who').textContent).toBe(
      'user03 · 임시 비밀번호로 로그인함',
    );
    expect(document.querySelectorAll('input')).toHaveLength(2);
  });

  it('[DT1 C2·C3·C4] 칸·[바꾸기] 40, 누구 줄 12/500, 규칙 줄·상태 글 12/400, 필수는 점, 칸 아래 오류 글 12/400 에 색 #A72027 그대로(ENT-306)', async () => {
    const { server } = await atPasswordChange();
    for (const field of [newInput(), confirmInput()]) {
      expect(field.className).toContain('h-10');
      expect(field.className).not.toMatch(/\bh-12\b/);
    }
    expect(changeButton().className).not.toMatch(/\bh-12\b/);
    expect(changeButton().className).toContain('h-10');
    expect(screen.getByTestId('who').className).toContain(
      'text-style-pre-caption-02',
    );
    const rule = screen.getByRole('list', { name: pw.rulesLabel });
    expect(rule.className).toContain('text-style-pre-caption-03');
    expect(rule.querySelector('span')!.className).toContain(
      'text-style-pre-caption-03',
    );
    const labels = [...document.querySelectorAll('form label')];
    expect(labels.map((label) => label.textContent)).toEqual([
      pw.newPassword,
      pw.confirm,
    ]);
    for (const label of labels)
      expect(label.querySelectorAll('[data-required-mark]')).toHaveLength(1);
    typeNew('greenpaper', 'greenpape');
    const mismatch = screen.getByText(pw.mismatch);
    expect(mismatch.className).toContain('text-style-pre-caption-03');
    expect(mismatch.className).not.toContain('text-style-pre-caption-01');
    expect(mismatch.className).toContain('text-support-error-accent');
    expect(mismatch.className).not.toMatch(/\btext-support-error\b(?!-)/);
    server.override['POST /users/me/password'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'PASSWORD_REJECTED',
            message: 'x',
            fields: null,
            legacyCode: 'password_rejected',
          },
        }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    typeNew('green-paper-1', 'green-paper-1');
    fireEvent.click(changeButton());
    const rejected = await screen.findByRole('alert', {}, WAIT);
    expect(rejected.textContent).toBe(pw.rejected);
    expect(rejected.className).toContain('text-style-pre-caption-03');
    expect(rejected.className).toContain('text-support-error-accent');
    expect(rejected.className).not.toMatch(/\btext-support-error\b(?!-)/);
  });

  it('[ⓔ] 7자는 꺼짐·「아직」, 8자는 켜짐·충족(두 칸 같을 때), 다르면 꺼짐 + aria-invalid + 오류 글', async () => {
    await atPasswordChange();
    typeNew('1234567', '1234567');
    expect(changeButton().disabled).toBe(true);
    const rule = screen.getByRole('list', { name: pw.rulesLabel });
    expect(rule.textContent).toContain('아직');
    expect(rule.querySelector('li')!.className).toContain('text-text-tertiary');
    expect(newInput().getAttribute('aria-describedby')).toBe(rule.id);
    typeNew('12345678', '12345678');
    expect(changeButton().disabled).toBe(false);
    expect(rule.textContent).toContain(pw.ruleMet);
    typeNew('greenpaper', 'greenpape');
    expect(changeButton().disabled).toBe(true);
    expect(confirmInput().getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText(pw.mismatch)).toBeTruthy();
  });

  it('바꾸기 성공 → 임시 비밀번호를 currentPassword 로 보내고 → 역할별 첫 화면(/greenwash), 임시 비밀번호는 지운다', async () => {
    const { history, server, session } = await atPasswordChange();
    typeNew('green-paper-1', 'green-paper-1');
    fireEvent.click(changeButton());
    await atPath(history, '/greenwash');
    const call = server.calls.find((row) => row.path === '/users/me/password')!;
    expect(JSON.parse(call.body)).toEqual({
      currentPassword: 'temp-pass-1',
      newPassword: 'green-paper-1',
    });
    expect(session.hasTemporaryPassword()).toBe(false);
  });

  it('400 PASSWORD_REJECTED → 해요체 글(서버 message 는 보이지 않는다), 주소 그대로', async () => {
    const { history, server } = await atPasswordChange();
    server.override['POST /users/me/password'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'PASSWORD_REJECTED',
            message: '새 비밀번호를 쓸 수 없다',
            fields: null,
            legacyCode: 'password_rejected',
          },
        }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    typeNew('green-paper-1', 'green-paper-1');
    fireEvent.click(changeButton());
    const alert = await screen.findByRole('alert', {}, WAIT);
    expect(alert.textContent).toBe(pw.rejected);
    expect(alert.textContent).toBe(
      '이 비밀번호는 쓸 수 없어요. 다른 비밀번호를 입력해 주세요.',
    );
    // 새 비밀번호 칸 아래 오류 글: 칸이 aria-invalid, 그 글을 aria-describedby 로 잇는다
    expect(newInput().getAttribute('aria-invalid')).toBe('true');
    expect(newInput().getAttribute('aria-describedby')).toContain(alert.id);
    expect(alert.tagName).toBe('P');
    expect(document.body.textContent).not.toContain('새 비밀번호를 쓸 수 없다');
    expect(pathOf(history)).toBe('/password');
  });

  it('400 CURRENT_PASSWORD_MISMATCH → 세션 비움 → /login 에 「임시 비밀번호로 다시 로그인」(회색 안내 띠)', async () => {
    const { history, server, storage } = await atPasswordChange();
    server.users.user03!.password = 'reset-again';
    typeNew('green-paper-1', 'green-paper-1');
    fireEvent.click(changeButton());
    await atPath(history, '/login');
    expect((await screen.findByRole('status', {}, WAIT)).textContent).toBe(
      SESSION_TEXT.notice.relogin,
    );
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
  });

  it('401 ACCOUNT_LOCKED → 세션 비움 → /login 에 잠김 글', async () => {
    const { history, server } = await atPasswordChange();
    server.users.user03!.locked = true;
    typeNew('green-paper-1', 'green-paper-1');
    fireEvent.click(changeButton());
    await atPath(history, '/login');
    expect((await screen.findByRole('status', {}, WAIT)).textContent).toBe(
      SESSION_TEXT.notice.locked,
    );
  });

  it('CM-02 에서 /greenwash·/admin/accounts·/login 으로 가려 해도 /password', async () => {
    const { history, router } = await atPasswordChange();
    for (const to of ['/greenwash', '/admin/accounts', '/login'] as const) {
      // router.navigate 의 약속은 act 안에서 기다리지 않는다(app/greenwash/router.test.tsx 와 같다).
      act(() => void router.navigate({ to }));
      await waitFor(() => expect(router.state.status).toBe('idle'), WAIT);
      await atPath(history, '/password');
    }
    await screenShown('password');
  });

  it('[로그아웃] → revoke(보관소의 refresh) → 세션 비움 → /login, 임시 비밀번호도 지운다', async () => {
    const { history, server, storage, session } = await atPasswordChange();
    const refresh = storage.getItem(REFRESH_STORAGE_KEY);
    fireEvent.click(screen.getByRole('button', { name: pw.logout }));
    await atPath(history, '/login');
    const revoke = server.calls.find((row) => row.path === '/auth/revoke')!;
    expect(JSON.parse(revoke.body)).toEqual({ refresh });
    expect(storage.getItem(REFRESH_STORAGE_KEY)).toBeNull();
    expect(session.hasTemporaryPassword()).toBe(false);
    expect(screen.queryByRole('status')).toBeNull();
  });
});
