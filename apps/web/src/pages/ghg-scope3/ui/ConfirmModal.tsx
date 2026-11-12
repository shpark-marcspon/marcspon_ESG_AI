// Scope 3 확인 창 하나(밴드 S3W3a — 고객사 잠그기 · 570 경고 · 핀 ≠ 기준 풀기). pages 끼리 import 0(L 규칙)이라 ghg-inventory 의 ConfirmModal 을 옮겨 적었다.
// <form onSubmit> 이라 확인 단추에서 Enter 가 확인이고, 취소 단추는 type button 이라 초점이 취소면 Enter 는 취소다(sid:MARC-ISSUE-564).
// 원본에 없는 칸: body(제목 아래 한 줄 — 값 파일 Q9). 닫히면 초점을 returnFocus 로 돌린다. 폭 420 · 위 64 · 좌우 16 · 아래 32 · 글↔단추 32.
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
  /** 제목 아래 한 줄(없으면 제목만). */
  body?: string;
  cancel: string;
  confirm: string;
  /** 닫히면 초점을 돌려줄 단추(닫힐 때 찾는다). */
  returnFocus(): HTMLElement | null;
  testId: string;
  /** 열 때 초점(기본 'confirm'). 되돌릴 수 없는 일은 'cancel'(sid:MARC-ISSUE-564). */
  initialFocus?: 'confirm' | 'cancel';
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
          <div className="flex flex-col gap-2">
            <DialogTitle className="text-center text-style-pre-heading-02 text-text-secondary">
              {title}
            </DialogTitle>
            {body !== undefined && (
              <p className="m-0 text-center text-style-pre-body-06 text-text-tertiary">
                {body}
              </p>
            )}
          </div>
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
