// @vitest-environment jsdom
// 온실가스 읽기 훅 넷(밴드 W12-0a ② — ① 검증 권고): 실어댑터 결과 → 상태 갈래 매핑.
//   ok → ready(값) · refused → refused(회사) · failed → failed · 상세 404 → missing · 상세 id null → 읽지 않음(loading) ·
//   q·page 가 바뀌면 다시 읽음 · retry 는 loading 부터.
import { act, renderHook, waitFor } from '@testing-library/react';

import { describe, expect, it } from 'vitest';

import {
  codesByName,
  fakeCodes,
  fakeGhgServer,
  fakeHeadquarters,
  portsOf,
  unreachable,
} from '../api/testing.ts';
import type { FakeGhgServerOptions } from '../api/testing.ts';
import {
  useAdminFacilityCodes,
  useBranch,
  useBranches,
  useFacilityCodes,
} from './index.ts';

const BASE = 'http://test.local/api';

function ports(options: FakeGhgServerOptions = {}) {
  const server = fakeGhgServer({ baseUrl: BASE, ...options });
  return { server, ...portsOf(server, BASE) };
}

describe('useBranches', () => {
  it('ok → ready · q·page 바뀌면 다시 읽음', async () => {
    const { server, port } = ports();
    const { result, rerender } = renderHook(
      ({ q, page }) => useBranches(port, q, page),
      { initialProps: { q: '', page: 1 } },
    );
    expect(result.current.status).toEqual({ state: 'loading' });
    await waitFor(() => expect(result.current.status.state).toBe('ready'));
    if (result.current.status.state === 'ready')
      expect(result.current.status.value.results.map((b) => b.id)).toEqual([
        '1',
      ]);
    rerender({ q: '본', page: 1 });
    await waitFor(() => expect(server.count('GET /branches')).toBe(2));
  });

  it('회사 거절 → refused · 끊김 → failed · retry 는 loading 부터', async () => {
    const refused = ports({ company: 'COMPANY_NOT_FOUND' });
    const a = renderHook(() => useBranches(refused.port, '', 1));
    await waitFor(() =>
      expect(a.result.current.status).toEqual({
        state: 'refused',
        company: 'not_found',
      }),
    );
    const broken = ports();
    broken.server.override['GET /branches'] = [unreachable];
    const b = renderHook(() => useBranches(broken.port, '', 1));
    await waitFor(() =>
      expect(b.result.current.status).toEqual({ state: 'failed' }),
    );
    act(() => b.result.current.retry());
    expect(b.result.current.status).toEqual({ state: 'loading' });
    await waitFor(() => expect(b.result.current.status.state).toBe('ready'));
  });
});

describe('useBranch', () => {
  it('ok → ready(상세) · 404 → missing · id null → 읽지 않음', async () => {
    const { server, port } = ports();
    const one = renderHook(() => useBranch(port, '1'));
    await waitFor(() =>
      expect(one.result.current.status).toEqual({
        state: 'ready',
        value: fakeHeadquarters(),
      }),
    );
    const gone = renderHook(() => useBranch(port, '99'));
    await waitFor(() =>
      expect(gone.result.current.status).toEqual({ state: 'missing' }),
    );
    const before = server.calls.length;
    const none = renderHook(() => useBranch(port, null));
    expect(none.result.current.status).toEqual({ state: 'loading' });
    expect(server.calls.length).toBe(before);
  });
});

describe('useFacilityCodes · useAdminFacilityCodes', () => {
  it('코드 목록 ready · 어드민 쪽 ready · 고객사 어드민 403 → failed', async () => {
    const { port, admin } = ports();
    const codes = renderHook(() => useFacilityCodes(port));
    await waitFor(() =>
      expect(codes.result.current.status).toEqual({
        state: 'ready',
        // 고객사 목록은 이름 가나다 → id(W12-0b1 ① L3).
        value: codesByName(fakeCodes()),
      }),
    );
    const page = renderHook(() => useAdminFacilityCodes(admin, 1));
    await waitFor(() => expect(page.result.current.status.state).toBe('ready'));
    const customer = ports({ admin: false });
    const refused = renderHook(() => useAdminFacilityCodes(customer.admin, 1));
    await waitFor(() =>
      expect(refused.result.current.status).toEqual({ state: 'failed' }),
    );
  });
});
