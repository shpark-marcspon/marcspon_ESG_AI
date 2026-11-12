// S12 이력 줄의 수정 사유 보기 창(밴드 W12-4 ③ — sid:MARC-ISSUE-571, Figma 29431:28330 「변경 참고 내용 모달」, 디자인 e6 11-05).
//   공통 틀(폭 640 · 안쪽 32 · 구획 사이 24 · 제목 18 Bold) · 제목 「수정 사유」(Figma 글 「수정 사유 작성」을 보기 창이라 고침 — e6) ·
//   본문 14 Regular 줄 높이 1.6 text-secondary · 사유 **전체**를 줄바꿈해 보인다(Figma 의 한 줄 말줄임에서 벗어나는 한 곳 — e6) ·
//   길면 본문만 최대 높이 320 에서 스크롤(토큰 없는 값이라 임의 값) · [확인] 하나(검정) 가운데 · 열 때 초점 [확인] · Esc·✕·확인 = 닫힘.
//   쓰기 창(EntryReasonDialog)에 보기 모드를 넣지 않았다 — 쓰기 창의 검사·주의 띠가 섞인다(발주서 Q6).
//   닫히면 초점은 연 단추로(부르는 쪽이 returnFocus 로 준다).
import { useRef } from 'react';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

const words = GHG_TEXT.entry.history.reasonView;

export interface EntryReasonViewDialogProps {
  /** 그 줄의 사유 전체(자르지 않는다). */
  reason: string;
  testId?: string;
  /** 닫힐 때 초점을 줄 단추(찾는 때 부름 — 없거나 떨어졌으면 Radix 기본). */
  returnFocus?(): HTMLElement | null;
  onClose(): void;
}

export function EntryReasonViewDialog({
  reason,
  testId = 'entry-reason-view',
  returnFocus,
  onClose,
}: EntryReasonViewDialogProps) {
  const okRef = useRef<HTMLButtonElement>(null);
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="md"
        data-testid={testId}
        className="max-w-[calc(100vw-64px)] gap-6"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          okRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          const target = returnFocus?.();
          if (!target?.isConnected) return;
          event.preventDefault();
          target.focus();
        }}
      >
        <DialogTitle className="text-style-pre-heading-02">
          {words.title}
        </DialogTitle>
        <p
          data-testid={`${testId}-body`}
          className="m-0 max-h-[320px] overflow-y-auto whitespace-pre-wrap break-all text-style-pre-body-06 text-text-secondary"
        >
          {reason}
        </p>
        <DialogFooter className="pt-0">
          <Button
            ref={okRef}
            variant="solidBlack"
            shape="round"
            size="md"
            onClick={onClose}
          >
            {words.ok}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
