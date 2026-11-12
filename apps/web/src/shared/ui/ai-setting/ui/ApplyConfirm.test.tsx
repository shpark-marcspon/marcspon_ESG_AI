// @vitest-environment jsdom
// AI 설정 적용 확인 창(밴드 AD2R ④ — 캔버스 v110 AD-02-CM ③). 지어낸 글로 본다: 제목·본문·[취소]·[적용], 실패 줄, pending 이면 다시 눌러도 onConfirm 0·닫힘 0.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApplyConfirm } from './ApplyConfirm.tsx';

afterEach(cleanup);

function setup(extra: Partial<Parameters<typeof ApplyConfirm>[0]> = {}) {
  const onConfirm = vi.fn();
  const onClose = vi.fn();
  render(
    <ApplyConfirm
      title="지어낸 제목"
      body="지어낸 본문"
      cancel="그만"
      confirm="하기"
      failure={null}
      pending={false}
      onConfirm={onConfirm}
      onClose={onClose}
      {...extra}
    />,
  );
  return { onConfirm, onClose, dialog: screen.getByRole('dialog') };
}

describe('ApplyConfirm', () => {
  it('제목·본문·[그만]·[하기], 실패 줄 없음. [하기] → onConfirm, [그만] → onClose', () => {
    const { onConfirm, onClose, dialog } = setup();
    expect(within(dialog).getByRole('heading').textContent).toBe('지어낸 제목');
    expect(dialog.textContent).toContain('지어낸 본문');
    expect(within(dialog).queryByTestId('apply-failure')).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: '하기' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    fireEvent.click(within(dialog).getByRole('button', { name: '그만' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('failure 가 있으면 빨강 줄(alert)', () => {
    const { dialog } = setup({ failure: '지어낸 실패' });
    expect(within(dialog).getByRole('alert').textContent).toBe('지어낸 실패');
  });

  it('pending 이면 [하기] 를 눌러도 onConfirm 0, Esc 로도 닫히지 않는다', () => {
    const { onConfirm, onClose, dialog } = setup({ pending: true });
    for (const node of within(dialog).getAllByRole('button'))
      fireEvent.click(node);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('창 단추 줄은 공개 표면(dialog/index.ts)의 DialogFooter — 위 8(pt-2, AV2 디자인 대조 N3)', () => {
    const { dialog } = setup();
    const footer = within(dialog).getByRole('button', {
      name: '하기',
    }).parentElement!;
    expect(within(footer).getByRole('button', { name: '그만' })).toBeTruthy();
    expect(footer.className.split(/\s+/)).toContain('pt-2');
  });
});
