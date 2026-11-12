// AD-01a 계정 만들기 모달(밴드 AD1 ②) → 성공하면 같은 모달이 AD-01b(임시 비밀번호)로 바뀐다.
// 쓰는 쪽(화면)은 열 때만 이 부품을 그린다 — 닫으면 마운트가 풀려 입력·임시 비밀번호가 상태째 사라진다(다시 여는 길이 없다).
//   - 아이디: autocomplete off, 도움 글 하나(쓸 수 없는 글자면 도움 글이 오류 꼴, aria-invalid). 409 는 칸 아래 오류 글 + 칸으로 초점.
//   - 이름: 도움 글 + 오른쪽 셈 「n / 20」(코드 포인트). 앞뒤 공백은 다듬어 보낸다.
//   - [만들기]: 두 칸이 차야 켜짐, 보내는 중 단추 안 도는 표시(두 번 보냄은 훅이 막는다).
//   - 보내는 중·임시 비밀번호가 보이는 동안은 Esc·바깥 누름으로 닫지 않는다(감독 판단 15 — [확인]으로만).
// 닫히면 연 자리([계정 만들기])로 초점을 돌린다(쓰는 쪽이 준 returnFocus).
import { useEffect, useId, useRef } from 'react';
import type { ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { Label } from '@marcspon/ui/components/label';
import { cn } from '@marcspon/ui/lib/utils';

import type { AccountsPort } from '../../../entities/account/api/index.ts';
import { ACCOUNT_TEXT } from '../../../entities/account/config/text.ts';
import { NAME_MAX } from '../../../entities/account/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { useCreateAccount } from '../hooks/index.ts';
import { TemporaryPassword } from './TemporaryPassword.tsx';

const words = ACCOUNT_TEXT.create;

export interface CreateAccountDialogProps {
  port: AccountsPort;
  copy(text: string): Promise<void>;
  /** 만들었거나 결과를 모를 때(409·쓰기 실패 — 행이 생겼을 수 있다) 목록을 다시 받는다. */
  onChanged(): void;
  /** 닫히면 초점을 돌려줄 자리(연 단추). */
  returnFocus: HTMLElement;
  onClose(): void;
}

/** 칸 아래 글(도움 또는 오류). */
function FieldNote({
  id,
  error,
  children,
}: {
  id: string;
  error?: boolean;
  children: ReactNode;
}) {
  return (
    <p
      id={id}
      role={error ? 'alert' : undefined}
      className={cn(
        'm-0 flex items-center gap-1 text-style-pre-caption-03 [&_svg]:size-4 [&_svg]:shrink-0',
        error ? 'text-support-error-accent' : 'text-text-tertiary',
      )}
    >
      {error && <CircleWarningIcon aria-hidden />}
      {children}
    </p>
  );
}

export function CreateAccountDialog({
  port,
  copy,
  onChanged,
  returnFocus,
  onClose,
}: CreateAccountDialogProps) {
  const form = useCreateAccount({ port, onChanged });
  const id = useId();
  const usernameRef = useRef<HTMLInputElement>(null);
  const locked = form.pending || form.issued !== null;
  const taken = form.error?.kind === 'taken';
  const invalid = (field: 'username' | 'name') =>
    form.error?.kind === 'invalid' && form.error.fields.includes(field);
  const usernameError = taken || invalid('username') || form.usernameInvalid;

  useEffect(() => {
    if (taken) usernameRef.current?.focus();
  }, [taken]);

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !locked) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid="create-account"
        onEscapeKeyDown={(event) => locked && event.preventDefault()}
        onInteractOutside={(event) => locked && event.preventDefault()}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocus.focus();
        }}
      >
        {form.issued ?
          <TemporaryPassword
            who={ACCOUNT_TEXT.password.created(
              form.issued.account.username,
              form.issued.account.name,
            )}
            password={form.issued.password}
            copy={copy}
            onConfirm={onClose}
          />
        : <form
            className="flex flex-col gap-4"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void form.submit();
            }}
          >
            <DialogTitle className="text-style-pre-heading-02">
              {words.title}
            </DialogTitle>
            <DialogDescription className="m-0 text-style-pre-body-06 text-text-tertiary">
              {words.lead}
            </DialogDescription>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-username`}>
                {words.username}
                <RequiredMark />
              </Label>
              <Input
                ref={usernameRef}
                id={`${id}-username`}
                required
                autoComplete="off"
                spellCheck={false}
                value={form.username}
                onChange={(event) => form.setUsername(event.target.value)}
                aria-invalid={usernameError || undefined}
                aria-describedby={
                  taken || invalid('username') ?
                    `${id}-username-error ${id}-username-help`
                  : `${id}-username-help`
                }
              />
              {(taken || invalid('username')) && (
                <FieldNote id={`${id}-username-error`} error>
                  {taken ? words.taken : words.invalid}
                </FieldNote>
              )}
              <FieldNote
                id={`${id}-username-help`}
                error={form.usernameInvalid && !taken}
              >
                {words.usernameHelp}
              </FieldNote>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-name`}>
                {words.name}
                <RequiredMark />
              </Label>
              <Input
                id={`${id}-name`}
                required
                value={form.name}
                onChange={(event) => form.setName(event.target.value)}
                aria-invalid={
                  invalid('name') || form.nameCount > NAME_MAX || undefined
                }
                aria-describedby={`${id}-name-help`}
              />
              {invalid('name') && (
                <FieldNote id={`${id}-name-error`} error>
                  {words.invalid}
                </FieldNote>
              )}
              <div
                id={`${id}-name-help`}
                className="flex items-center justify-between text-style-pre-caption-03 text-text-tertiary"
              >
                <span>{words.nameHelp}</span>
                <span
                  data-testid="name-count"
                  className={cn(
                    'tabular-nums',
                    form.nameCount > NAME_MAX && 'text-support-error-accent',
                  )}
                >
                  {words.nameCount(form.nameCount, NAME_MAX)}
                </span>
              </div>
            </div>
            <PageInfo icon={<PageInfoIcon />}>{words.notice}</PageInfo>
            {form.error?.kind === 'failed' && (
              <PageInfo
                tone="error"
                role="alert"
                icon={<CircleWarningIcon aria-hidden />}
              >
                {words.failed}
              </PageInfo>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outlineBlack"
                shape="round"
                size="md"
                disabled={form.pending}
                onClick={onClose}
              >
                {words.cancel}
              </Button>
              <Button
                type="submit"
                variant="solidBlack"
                shape="round"
                size="md"
                disabled={!form.ready}
                loading={form.pending}
                loadingLabel={words.submitting}
              >
                {words.submit}
              </Button>
            </DialogFooter>
          </form>
        }
      </DialogContent>
    </Dialog>
  );
}
