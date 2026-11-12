// @vitest-environment jsdom
// useSession(밴드 LG1 ①). StrictMode 로 그려 effect 가 두 번 돌아도 부팅 복원의 refresh 는 한 번이다(critic 1 반영 N1·N2 — 심은 파손 ⓓ 가 문다).
import { StrictMode, useEffect } from 'react';

import { act, cleanup, render, screen, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { createSessionStore } from '../api/index.ts';
import type { SessionStore } from '../api/index.ts';
import { fakeAuthServer, memoryStorage } from '../api/testing.ts';
import { REFRESH_STORAGE_KEY } from '../model/index.ts';
import { useSession } from './useSession.ts';

afterEach(cleanup);

const BASE = 'http://test.local/api';

/** 상태를 글자로 그리고, 마운트 effect 에서 복원을 부른다(StrictMode 면 두 번). */
function Probe({ store }: { store: SessionStore }) {
  const state = useSession(store);
  useEffect(() => {
    void store.ready();
  }, [store]);
  return (
    <p data-testid="state">
      {state.status === 'signedIn' ?
        `${state.status}:${state.user.username}`
      : state.status}
    </p>
  );
}

describe('useSession', () => {
  it('StrictMode 이중 effect 에도 refresh 는 한 번, 상태는 restoring → signedIn', async () => {
    const server = fakeAuthServer(
      { user01: { password: 'service-pass-1', kind: 'service' } },
      { baseUrl: BASE },
    );
    const storage = memoryStorage({
      [REFRESH_STORAGE_KEY]: server.issue('user01').refresh,
    });
    const store = createSessionStore({
      send: server.send,
      storage,
      baseUrl: BASE,
    });
    render(
      <StrictMode>
        <Probe store={store} />
      </StrictMode>,
    );
    expect(screen.getByTestId('state').textContent).toBe('restoring');
    await waitFor(() =>
      expect(screen.getByTestId('state').textContent).toBe('signedIn:user01'),
    );
    expect(server.count('POST /auth/refresh')).toBe(1);
  });

  it('로그아웃하면 다시 그린다(signedOut)', async () => {
    const server = fakeAuthServer(
      { user01: { password: 'service-pass-1', kind: 'service' } },
      { baseUrl: BASE },
    );
    const store = createSessionStore({
      send: server.send,
      storage: memoryStorage(),
      baseUrl: BASE,
    });
    await store.ready();
    await store.login('user01', 'service-pass-1');
    render(<Probe store={store} />);
    expect(screen.getByTestId('state').textContent).toBe('signedIn:user01');
    await act(() => store.logout());
    expect(screen.getByTestId('state').textContent).toBe('signedOut');
  });
});
