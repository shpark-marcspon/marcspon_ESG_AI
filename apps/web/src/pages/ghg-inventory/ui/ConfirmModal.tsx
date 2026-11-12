// S2 자리 확인 창 하나(밴드 W12-0b2 ③ — 초기 세팅 모달). pages 끼리 import 0(L 규칙)이라 ghg-index-settings 의 ConfirmModal 을
// 옮겨 적었다(sid:MARC-ISSUE-335 꼴 후속). sid:MARC-ISSUE-460 L1·L2: <form onSubmit> 이라 확인 단추에서 Enter 가 확인이고, 열 때 초점은 확인 단추
//   (initialFocus 기본 'confirm'). 초기 모달만 'cancel' — 열기만 해도 뜨는 창이라 Enter 한 번에 쓰기가 일지 않게(sid:MARC-ISSUE-564, 디자인 e6).
//   취소 단추는 type button(키트 기본)이라 초점이 취소면 Enter 는 취소다.
// 닫히면 초점을 returnFocus 로 돌린다(초기 모달은 연 단추가 없어 [인덱스 설정] 단추 — 그래서 원본과 달리 닫힐 때 부르는 함수).
// W12-1c #19(판 S12-02a `.f12a-alert`): 폭 420 그대로 · 위 64 · 좌우 16 · 아래 32 · 글↔단추 32 · 글 text-secondary.
import { useRef } from 'react';
import type { FormEvent } from 'react';

import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

export interface ConfirmModalProps {
  title: string;
  cancel: string;
  confirm: string;
  /** 닫히면 초점을 돌려줄 단추(닫힐 때 찾는다 — 모달과 같이 그려지는 단추라 그릴 때는 아직 없을 수 있다). */
  returnFocus(): HTMLElement | null;
  testId: string;
  /** 열 때 초점(기본 'confirm' — 다른 창 그대로). 초기 모달만 'cancel'(sid:MARC-ISSUE-564). */
  initialFocus?: 'confirm' | 'cancel';
  onConfirm(): void;
  onClose(): void;
}

export function ConfirmModal({
  title,
  cancel,
  confirm,
  returnFocus,
  testId,
  initialFocus = 'confirm',
  onConfirm,
  onClose,
}: ConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onConfirm();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid={testId}
        className="px-4 pb-8 pt-16"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          (initialFocus === 'cancel' ? cancelRef : confirmRef).current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <form onSubmit={submit} className="flex flex-col gap-8">
          <DialogTitle className="text-center text-style-pre-heading-02 text-text-secondary">
            {title}
          </DialogTitle>
          <DialogFooter className="pt-0">
            <Button
              ref={cancelRef}
              variant="outlineBlack"
              shape="round"
              size="md"
              onClick={onClose}
            >
              {cancel}
            </Button>
            <Button
              ref={confirmRef}
              type="submit"
              variant="solidBlack"
              shape="round"
              size="md"
            >
              {confirm}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
