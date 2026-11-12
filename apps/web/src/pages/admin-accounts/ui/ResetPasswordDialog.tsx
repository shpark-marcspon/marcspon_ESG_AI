// 비밀번호 초기화 확인(AD-01c 와 같은 꼴, 밴드 AD1 ②) → 성공하면 같은 모달이 AD-01b(임시 비밀번호)로 바뀐다.
// 쓰는 쪽은 열 때만 그린다 — 닫으면 상태째 사라진다. 닫히면 그 줄의 [초기화]로 초점을 돌린다(쓰는 쪽이 준 returnFocus).
//   - [초기화](동사 — MARC-ENT-216): 보내는 중 도는 표시(두 번 보냄은 훅이 막는다). 없는 계정이면 글 한 줄 + [초기화] 꺼짐.
//   - 보내는 중·임시 비밀번호가 보이는 동안은 Esc·바깥 누름으로 닫지 않는다([확인]으로만).
import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';

import type { AccountsPort } from '../../../entities/account/api/index.ts';
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
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { useResetPassword } from '../hooks/index.ts';
import { TemporaryPassword } from './TemporaryPassword.tsx';

const words = ACCOUNT_TEXT.reset;

export interface ResetPasswordDialogProps {
  port: AccountsPort;
  account: Account;
  copy(text: string): Promise<void>;
  onChanged(): void;
  /** 닫히면 초점을 돌려줄 자리(연 단추). */
  returnFocus: HTMLElement;
  onClose(): void;
}

export function ResetPasswordDialog({
  port,
  account,
  copy,
  onChanged,
  returnFocus,
  onClose,
}: ResetPasswordDialogProps) {
  const flow = useResetPassword({ port, account, onChanged });
  const locked = flow.pending || flow.issued !== null;
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !locked) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid="reset-password"
        onEscapeKeyDown={(event) => locked && event.preventDefault()}
        onInteractOutside={(event) => locked && event.preventDefault()}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocus.focus();
        }}
      >
        {flow.issued ?
          <TemporaryPassword
            who={ACCOUNT_TEXT.password.reset(
              flow.issued.account.username,
              flow.issued.account.name,
            )}
            password={flow.issued.password}
            copy={copy}
            onConfirm={onClose}
          />
        : <>
            <DialogTitle className="text-center text-style-pre-heading-02">
              {words.title(account.username)}
            </DialogTitle>
            <DialogDescription className="m-0 text-center text-style-pre-body-06 text-text-secondary">
              {words.body}
            </DialogDescription>
            {flow.error && (
              <PageInfo
                tone="error"
                role="alert"
                icon={<CircleWarningIcon aria-hidden />}
              >
                {flow.error === 'missing' ? words.missing : words.failed}
              </PageInfo>
            )}
            <DialogFooter>
              <Button
                variant="outlineBlack"
                shape="round"
                size="md"
                disabled={flow.pending}
                onClick={onClose}
              >
                {words.cancel}
              </Button>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                disabled={flow.error === 'missing'}
                loading={flow.pending}
                loadingLabel={words.submitting}
                onClick={() => void flow.submit()}
              >
                {words.submit}
              </Button>
            </DialogFooter>
          </>
        }
      </DialogContent>
    </Dialog>
  );
}
