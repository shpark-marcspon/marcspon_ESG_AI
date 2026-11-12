// AD-01c 사용 중지 확인과 [다시 사용] 확인(밴드 AD1 ③ — 같은 꼴). 확인하면 바로 적용한다(시안 메모 ad-a-01c — [저장]은 이름 고침에만).
// 고른 줄 목록 「{username} · {name}」(시안 g-quote). 적용은 넣어 준 onConfirm 하나(화면이 PATCH /users/{id} 를 id 마다 보낸다 — UA1W ②).
// 닫히면 연 단추로 초점을 돌린다. 일부 실패면 화면이 계정을 실패한 것만으로 줄여 다시 그리고, 버튼 줄 바로 위에 빨강 한 줄(디자인 원문 Q4).
//   성공이 하나라도 있으면 그 줄이 성공 수를 앞에 말한다(덮개 뒤 배지는 읽기 어렵다 — UA1W 디자인 대조 C1). 모두 실패면 실패 글만.
import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';

import { ACCOUNT_TEXT } from '../../../entities/account/config/text.ts';
import type { Account } from '../../../entities/account/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

const words = ACCOUNT_TEXT.active;

export interface ActiveDialogProps {
  /** 사용 중지(false) 또는 다시 사용(true). */
  isActive: boolean;
  accounts: readonly Account[];
  /** 사용 중지 뒤에도 access 가 통하는 분(본문 글 — ACCESS_TTL_MINUTES). */
  ttlMinutes: number;
  /** 앞 적용의 성공·실패 수(실패가 없으면 null). */
  result: { done: number; failed: number } | null;
  pending: boolean;
  returnFocus: HTMLElement;
  onConfirm(): void;
  onClose(): void;
}

export function ActiveDialog({
  isActive,
  accounts,
  ttlMinutes,
  result,
  pending,
  returnFocus,
  onConfirm,
  onClose,
}: ActiveDialogProps) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid="active-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocus.focus();
        }}
      >
        <DialogTitle className="text-center text-style-pre-heading-02">
          {isActive ?
            words.reactivateTitle(accounts.length)
          : words.deactivateTitle(accounts.length)}
        </DialogTitle>
        <ul className="m-0 flex list-none flex-col gap-1 rounded-component bg-background-secondary px-4 py-3 text-style-pre-body-05 text-text-primary">
          {accounts.map((account) => (
            <li key={account.id}>
              {words.who(account.username, account.name)}
            </li>
          ))}
        </ul>
        <DialogDescription className="m-0 text-center text-style-pre-body-06 text-text-secondary">
          {isActive ? words.reactivateBody : words.deactivateBody(ttlMinutes)}
        </DialogDescription>
        {result !== null && (
          <p
            role="alert"
            data-testid="active-failure"
            className="m-0 flex items-center justify-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
          >
            <CircleWarningIcon aria-hidden />
            {result.done === 0 ?
              isActive ?
                words.reactivateFailed(result.failed)
              : words.deactivateFailed(result.failed)
            : isActive ?
              words.reactivatePartly(result.done, result.failed)
            : words.deactivatePartly(result.done, result.failed)}
          </p>
        )}
        <DialogFooter>
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            disabled={pending}
            onClick={onClose}
          >
            {words.cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            loading={pending}
            onClick={onConfirm}
          >
            {isActive ? words.reactivate : words.deactivate}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
