// @vitest-environment jsdom
// 로그인 화면 단독(밴드 DT1 C1, critic 반영 3): 세션 끝남 띠는 카드 위에 따로 그려 카드 안 실패 글과 같이 보일 수 있다.
// 경로에서는 제출이 onDismissNotice 로 안내를 내리므로(useLoginForm), 둘이 같이 있는 꼴은 화면 단독으로만 만든다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { SESSION_TEXT } from '../../../entities/session/config/text.ts';
import { LoginScreen } from './LoginScreen.tsx';

afterEach(cleanup);

const words = SESSION_TEXT.login;

describe('CM-01 세션 끝남 띠(카드 위)', () => {
  it('로그인이 틀려도 카드 위 주황 띠(정보 아이콘)는 남고, 카드 안에 틀림 글이 같이 보인다', async () => {
    render(
      <LoginScreen
        notice="expired"
        onLogin={() => Promise.resolve({ ok: false, reason: 'invalid' })}
        onDismissNotice={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(words.username), {
      target: { value: 'user01' },
    });
    fireEvent.change(screen.getByLabelText(words.password), {
      target: { value: 'wrong-pass' },
    });
    await act(async () => {
      fireEvent.submit(document.querySelector('form')!);
    });
    const failure = await screen.findByRole('alert');
    expect(failure.textContent).toBe(words.invalid);
    const notice = screen.getByRole('status');
    expect(notice.textContent).toBe(SESSION_TEXT.notice.expired);
    expect(notice.getAttribute('data-tone')).toBe('important');
    expect(notice.querySelector('svg')).not.toBeNull();
    const card = document.querySelector('main > section')!;
    expect(card.contains(failure)).toBe(true);
    expect(card.contains(notice)).toBe(false);
  });

  it('잠김 안내는 카드 안 빨간 띠 그대로, 카드 위 자리는 없다', () => {
    render(
      <LoginScreen
        notice="locked"
        onLogin={() => Promise.resolve({ ok: true })}
        onDismissNotice={vi.fn()}
      />,
    );
    const notice = screen.getByRole('status');
    expect(notice.getAttribute('data-tone')).toBe('error');
    expect(document.querySelector('main > section')!.contains(notice)).toBe(
      true,
    );
    expect(document.querySelector('main')!.children).toHaveLength(1);
  });
});

describe('부팅 복원이 서버에 닿지 못함 띠(카드 위, 밴드 SN1)', () => {
  const retryButton = () => screen.getByRole('button', { name: words.retry });

  it('[T6] unreachable 은 카드 위 오류 띠(role=status) + [다시 시도]', () => {
    render(
      <LoginScreen
        notice="unreachable"
        onLogin={() => Promise.resolve({ ok: true })}
        onDismissNotice={vi.fn()}
        onRetry={() => Promise.resolve()}
      />,
    );
    const notice = screen.getByRole('status');
    expect(notice.getAttribute('data-tone')).toBe('error');
    expect(notice.getAttribute('data-reason')).toBe('unreachable');
    expect(notice.textContent).toContain(SESSION_TEXT.notice.unreachable);
    expect(notice.contains(retryButton())).toBe(true);
    expect(document.querySelector('main > section')!.contains(notice)).toBe(
      false,
    );
    expect(retryButton().getAttribute('aria-disabled')).toBeNull();
  });

  it('[T6] 누르는 동안 aria-disabled, 두 번 눌러도 onRetry 는 한 번, 풀리면 다시 켜진다', async () => {
    let finish!: () => void;
    const onRetry = vi.fn(
      () => new Promise<void>((resolve) => (finish = resolve)),
    );
    render(
      <LoginScreen
        notice="unreachable"
        onLogin={() => Promise.resolve({ ok: true })}
        onDismissNotice={vi.fn()}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(retryButton());
    fireEvent.click(retryButton());
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(retryButton().getAttribute('aria-disabled')).toBe('true');
    await act(async () => finish());
    expect(retryButton().getAttribute('aria-disabled')).toBeNull();
    fireEvent.click(retryButton());
    expect(onRetry).toHaveBeenCalledTimes(2);
  });

  it('[T6] 다른 안내(expired·locked·relogin)에는 [다시 시도] 가 없다', () => {
    for (const notice of ['expired', 'locked', 'relogin'] as const) {
      render(
        <LoginScreen
          notice={notice}
          onLogin={() => Promise.resolve({ ok: true })}
          onDismissNotice={vi.fn()}
          onRetry={() => Promise.resolve()}
        />,
      );
      expect(screen.queryByRole('button', { name: words.retry })).toBeNull();
      cleanup();
    }
  });
});
