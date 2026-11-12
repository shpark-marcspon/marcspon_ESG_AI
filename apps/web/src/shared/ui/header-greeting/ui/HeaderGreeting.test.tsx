// @vitest-environment jsdom
// 머리 인사말 + [로그아웃]: 인사말과 단추 글, 누르면 onLogout 한 번(끝나기 전 두 번 눌러도), 끝나면 다시 누를 수 있다.
// 밴드 SV1: [로그아웃]은 md(디자인 리뷰 C6), action 자리는 인사말과 [로그아웃] 사이(없으면 둘뿐).
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { HeaderGreeting } from './HeaderGreeting.tsx';

afterEach(cleanup);

describe('머리 인사말 + [로그아웃]', () => {
  it('인사말 옆 글 단추. 끝나기 전에는 두 번 눌러도 onLogout 은 한 번, 끝나면 다시 부를 수 있다', async () => {
    let finish!: () => void;
    const onLogout = vi.fn(
      () => new Promise<void>((resolve) => (finish = resolve)),
    );
    render(<HeaderGreeting greeting="인사" onLogout={onLogout} />);
    expect(screen.getByText('인사')).toBeTruthy();
    const button = screen.getByRole('button', { name: '로그아웃' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(onLogout).toHaveBeenCalledTimes(1);
    await act(async () => finish());
    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    expect(onLogout).toHaveBeenCalledTimes(2);
  });

  it('onLogout 이 거절해도 단추가 다시 살아난다(처리 안 된 거절 없음)', async () => {
    const onLogout = vi.fn(() => Promise.reject(new Error('끊김')));
    render(<HeaderGreeting greeting="인사" onLogout={onLogout} />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    });
    expect(
      screen.getByRole('button', { name: '로그아웃' }).hasAttribute('disabled'),
    ).toBe(false);
  });

  it('단추 글을 바꿀 수 있다', () => {
    render(
      <HeaderGreeting
        greeting="인사"
        logoutLabel="나가기"
        onLogout={() => Promise.resolve()}
      />,
    );
    expect(screen.getByRole('button', { name: '나가기' })).toBeTruthy();
  });

  it('[로그아웃]은 md(높이 36 — h-9, 글 14 pre-body-05). sm 꼴이 아니다(디자인 리뷰 C6)', () => {
    render(
      <HeaderGreeting greeting="인사" onLogout={() => Promise.resolve()} />,
    );
    const button = screen.getByRole('button', { name: '로그아웃' });
    expect(button.className.split(/\s+/)).toContain('h-9');
    expect(button.className.split(/\s+/)).toContain('text-style-pre-body-05');
    expect(button.className.split(/\s+/)).not.toContain('h-7');
  });

  it('action 은 인사말과 [로그아웃] 사이에 그린다(DOM 차례)', () => {
    render(
      <HeaderGreeting
        greeting="인사"
        action={<button type="button">가운데</button>}
        onLogout={() => Promise.resolve()}
      />,
    );
    const greeting = screen.getByText('인사');
    const row = greeting.parentElement!;
    expect([...row.children].map((node) => node.textContent)).toEqual([
      '인사',
      '가운데',
      '로그아웃',
    ]);
  });

  it('action 이 없으면 인사말과 [로그아웃] 둘뿐이다(지금 DOM 그대로)', () => {
    render(
      <HeaderGreeting greeting="인사" onLogout={() => Promise.resolve()} />,
    );
    const row = screen.getByText('인사').parentElement!;
    expect([...row.children].map((node) => node.tagName)).toEqual([
      'SPAN',
      'BUTTON',
    ]);
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });
});
