// S17 확인 창 하나(밴드 W12-0b2 ② — 나가기 확인·데이터 있는 인덱스 경고). pages 끼리 import 0(L 규칙)이라 ghg-index-pool 의 ConfirmDialog 꼴을
// 옮겨 적었다(sid:MARC-ISSUE-335 꼴 후속). sid:MARC-ISSUE-460 L1·L2: <form onSubmit> 이라 Enter 가 확인이고, 열 때 초점은 확인 단추,
// 닫히면 초점을 연 단추로 돌린다.
// GX2 S12-05: 꼴은 ghg-inventory ConfirmModal(판 S12-02a `.f12a-alert`)과 같이 — 위 64 · 좌우 16 · 아래 32 · 글↔단추 32 · 머리 text-secondary.
import { useRef } from 'react';
import type { FormEvent } from 'react';

import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

export interface ConfirmModalProps {
  title: string;
  /** 머리 아래 회색 몸 글(없으면 머리만 — sid:MARC-ISSUE-468 D9). */
  body?: string;
  cancel: string;
  confirm: string;
  /** 닫히면 초점을 돌려줄 단추(연 단추). */
  returnFocus: HTMLElement | null;
  testId: string;
  onConfirm(): void;
  onClose(): void;
}

export function ConfirmModal({
  title,
  body,
  cancel,
  confirm,
  returnFocus,
  testId,
  onConfirm,
  onClose,
}: ConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
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
          confirmRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (returnFocus?.isConnected) returnFocus.focus();
        }}
      >
        <form onSubmit={submit} className="flex flex-col gap-8">
          <div className="flex flex-col">
            <DialogTitle className="text-center text-style-pre-heading-02 text-text-secondary">
              {title}
            </DialogTitle>
            {body && (
              <DialogDescription className="mt-2 text-center text-style-pre-body-06 text-text-tertiary">
                {body}
              </DialogDescription>
            )}
          </div>
          <DialogFooter className="pt-0">
            <Button
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
