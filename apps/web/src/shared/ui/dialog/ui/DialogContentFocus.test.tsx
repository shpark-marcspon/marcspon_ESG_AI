// @vitest-environment jsdom
// 모달 Content 의 초점 되돌리기(밴드 FW2 ⓪, sid:MARC-ISSUE-97 1번).
// Radix 는 닫힐 때 DialogTrigger 로만 초점을 돌린다. 우리 Content 는 열릴 때의 초점 자리를 적어 두었다가 닫힐 때 그리로 돌린다.
// 쓰는 쪽 onOpenAutoFocus·onCloseAutoFocus 는 함께 불리고, 쓰는 쪽이 닫힘에서 preventDefault 하면 돌리지 않는다.
// 실제 브라우저의 같은 동작은 e2e/greenwash.spec.ts 가 본다.
import { useState } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { DialogContent } from './DialogContent.tsx';
import { Dialog, DialogClose, DialogDescription, DialogTitle } from './kit.ts';

afterEach(cleanup);

function CodeOpened({
  onOpenAutoFocus,
  onCloseAutoFocus,
}: {
  onOpenAutoFocus?: (event: Event) => void;
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        코드로 열기
      </button>
      <button type="button">다른 단추</button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          onOpenAutoFocus={onOpenAutoFocus}
          onCloseAutoFocus={onCloseAutoFocus}
        >
          <DialogTitle>제목</DialogTitle>
          <DialogDescription>설명</DialogDescription>
          <DialogClose>닫기</DialogClose>
        </DialogContent>
      </Dialog>
    </>
  );
}

async function openAndClose() {
  const opener = screen.getByRole('button', { name: '코드로 열기' });
  opener.focus();
  await act(async () => {
    fireEvent.click(opener);
  });
  expect(screen.getByRole('dialog')).toBeTruthy();
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: '닫기' }));
  });
  expect(screen.queryByRole('dialog')).toBeNull();
  // Radix FocusScope 는 내려간 뒤 다음 차례(setTimeout 0)에 닫힘 초점 사건을 낸다.
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  return opener;
}

describe('DialogContent 초점 되돌리기', () => {
  it('Trigger 없이 open 으로 연 모달을 닫으면 연 자리(단추)로 초점이 돌아간다', async () => {
    render(<CodeOpened />);
    const opener = await openAndClose();
    expect(document.activeElement).toBe(opener);
  });

  it('쓰는 쪽 onOpenAutoFocus·onCloseAutoFocus 도 불린다', async () => {
    const onOpen = vi.fn();
    const onClose = vi.fn();
    render(<CodeOpened onOpenAutoFocus={onOpen} onCloseAutoFocus={onClose} />);
    const opener = await openAndClose();
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.activeElement).toBe(opener);
  });

  it('쓰는 쪽이 닫힘에서 preventDefault 하고 초점을 정하면 그대로 둔다', async () => {
    render(
      <CodeOpened
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          screen.getByRole('button', { name: '다른 단추' }).focus();
        }}
      />,
    );
    const opener = await openAndClose();
    expect(document.activeElement).not.toBe(opener);
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: '다른 단추' }),
    );
  });
});
