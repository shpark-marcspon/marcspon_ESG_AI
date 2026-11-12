// @vitest-environment jsdom
// useObjectUrl(밴드 WC1 ③): 쪽 썸네일과 검토 쪽 칸이 같이 쓰는 File → object URL. 열고, 파일이 바뀌거나 내려가면 revoke 한다.
// 심은 파손: useObjectUrl 에서 revokeObjectURL 을 빼면 아래 시험이 빨강이다.
import { StrictMode } from 'react';

import { cleanup, renderHook } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useObjectUrl } from './useObjectUrl.ts';

let seq = 0;
const created: string[] = [];
const revoked: string[] = [];

beforeEach(() => {
  seq = 0;
  created.length = 0;
  revoked.length = 0;
  URL.createObjectURL = vi.fn(() => {
    const url = `blob:목/${++seq}`;
    created.push(url);
    return url;
  });
  URL.revokeObjectURL = vi.fn((url: string) => {
    revoked.push(url);
  });
});
afterEach(cleanup);

describe('useObjectUrl', () => {
  it('파일을 열어 URL 을 주고, 파일이 바뀌면 앞 URL 을, 내려가면 지금 URL 을 revoke 한다', () => {
    const first = new File(['%PDF'], '목-하나.pdf', {
      type: 'application/pdf',
    });
    const second = new File(['%PDF'], '목-둘.pdf', { type: 'application/pdf' });
    const hook = renderHook(({ file }) => useObjectUrl(file), {
      initialProps: { file: first },
    });
    expect(hook.result.current).toBe('blob:목/1');
    expect(revoked).toEqual([]);

    hook.rerender({ file: second });
    expect(hook.result.current).toBe('blob:목/2');
    expect(revoked).toEqual(['blob:목/1']);

    // 같은 파일로 다시 그리면 새로 열지 않는다
    hook.rerender({ file: second });
    expect(created).toEqual(['blob:목/1', 'blob:목/2']);

    hook.unmount();
    expect(revoked).toEqual(['blob:목/1', 'blob:목/2']);
  });

  it('StrictMode(effect 를 한 번 더 돌림)에서도 새지 않는다: 만든 수 = revoke 수 + 1, 내려가면 같다', () => {
    const file = new File(['%PDF'], '목-하나.pdf', { type: 'application/pdf' });
    const hook = renderHook(() => useObjectUrl(file), { wrapper: StrictMode });
    expect(created.length).toBe(revoked.length + 1);
    expect(hook.result.current).toBe(created.at(-1));
    hook.unmount();
    expect(revoked.length).toBe(created.length);
  });
});
