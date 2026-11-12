// 첫 로그인 비밀번호 바꾸기(밴드 LG1 ③, 시안 CM-02). 라우터를 모른다: 바꾸기는 onChange, 로그아웃은 onLogout(경로 컴포넌트가 잇는다).
// 지금 비밀번호 칸은 없다 — 세션이 로그인 때 친 임시 비밀번호를 보낸다(감독 판단 1 (가)).
// 규칙 목록 「8자 이상」 + 충족 표시(못 채우면 회색 원 X 「아직」)는 새 비밀번호 칸의 aria-describedby. 확인 칸이 다르면 aria-invalid + 칸 아래 오류.
// 서버가 새 비밀번호를 받지 않으면(400 PASSWORD_REJECTED·422) 새 비밀번호 칸 아래 오류 글(role=alert, aria-invalid). 연결·5xx 는 카드 안 오류 띠.
// [비밀번호 바꾸고 시작하기] 는 8자 이상이고 두 칸이 같을 때만 켜진다. 바뀌면 경로가 역할별 첫 화면으로 넘긴다.
import { useId } from 'react';

import {
  CheckIcon,
  CircleCloseIcon,
  CircleWarningIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Label } from '@marcspon/ui/components/label';
import { cn } from '@marcspon/ui/lib/utils';

import type { PasswordChangeOutcome } from '../../../entities/session/api/index.ts';
import { SESSION_TEXT } from '../../../entities/session/config/text.ts';
import {
  AuthAlert,
  AuthCard,
  PasswordInput,
} from '../../../entities/session/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { usePasswordForm } from '../hooks/index.ts';

const words = SESSION_TEXT.password;

export interface PasswordChangeScreenProps {
  /** 로그인한 계정의 아이디(/users/me). */
  username: string;
  onChange: (newPassword: string) => Promise<PasswordChangeOutcome>;
  onLogout: () => void;
}

/** 필수 칸 표시(시안 e-label--req). */
function Required({
  htmlFor,
  children,
}: {
  htmlFor: string;
  children: string;
}) {
  return (
    <Label htmlFor={htmlFor}>
      {children}
      <RequiredMark />
    </Label>
  );
}

export function PasswordChangeScreen({
  username,
  onChange,
  onLogout,
}: PasswordChangeScreenProps) {
  const form = usePasswordForm({ onChange });
  const id = useId();
  const titleId = `${id}-title`;
  const newId = `${id}-new`;
  const confirmId = `${id}-confirm`;
  const rulesId = `${id}-rules`;
  const mismatchId = `${id}-mismatch`;
  const rejectedId = `${id}-rejected`;
  const rejected = form.failure === 'rejected';
  return (
    <AuthCard
      screen="password"
      labelledBy={titleId}
      heading={
        <>
          <h2
            id={titleId}
            className="m-0 text-style-pre-display-04 font-bold text-text-primary"
          >
            {words.title}
          </h2>
          <p className="m-0 text-style-pre-body-06 text-text-tertiary">
            {words.lead}
          </p>
        </>
      }
    >
      <p
        data-testid="who"
        className="m-0 text-center text-style-pre-caption-02 text-text-tertiary"
      >
        {words.who(username)}
      </p>
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void form.submit();
        }}
      >
        <div className="flex flex-col gap-1.5">
          <Required htmlFor={newId}>{words.newPassword}</Required>
          <PasswordInput
            id={newId}
            required
            autoComplete="new-password"
            showLabel={words.showNew}
            aria-invalid={rejected || undefined}
            aria-describedby={rejected ? `${rejectedId} ${rulesId}` : rulesId}
            value={form.password}
            onChange={(event) => form.setPassword(event.target.value)}
          />
          <ul
            id={rulesId}
            aria-label={words.rulesLabel}
            className="m-0 mt-0.5 flex list-none flex-col gap-1 p-0 text-style-pre-caption-03"
          >
            <li
              data-met={form.lengthMet}
              className={cn(
                'flex items-center gap-1.5 [&_svg]:size-4 [&_svg]:shrink-0',
                form.lengthMet ?
                  'text-support-success-accent'
                : 'text-text-tertiary',
              )}
            >
              {form.lengthMet ?
                <CheckIcon aria-hidden />
              : <CircleCloseIcon aria-hidden />}
              {words.ruleLength}
              <span className="ml-auto text-style-pre-caption-03">
                {form.lengthMet ? words.ruleMet : words.ruleUnmet}
              </span>
            </li>
          </ul>
          {rejected && (
            <p
              id={rejectedId}
              role="alert"
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
            >
              <CircleWarningIcon aria-hidden />
              {words.rejected}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <Required htmlFor={confirmId}>{words.confirm}</Required>
          <PasswordInput
            id={confirmId}
            required
            autoComplete="new-password"
            showLabel={words.showConfirm}
            aria-invalid={form.mismatch || undefined}
            aria-describedby={form.mismatch ? mismatchId : undefined}
            value={form.confirm}
            onChange={(event) => form.setConfirm(event.target.value)}
          />
          {form.mismatch && (
            <p
              id={mismatchId}
              className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
            >
              <CircleWarningIcon aria-hidden />
              {words.mismatch}
            </p>
          )}
        </div>
        {form.failure === 'failed' && (
          <AuthAlert role="alert" reason="failed">
            {words.failed}
          </AuthAlert>
        )}
        <Button
          type="submit"
          variant="solidBlack"
          shape="round"
          size="lg"
          className="w-full"
          disabled={!form.ready}
          loading={form.pending}
          loadingLabel={words.submitting}
        >
          {words.submit}
        </Button>
        <Button
          variant="text"
          size="md"
          className="self-center underline"
          onClick={onLogout}
        >
          {words.logout}
        </Button>
      </form>
    </AuthCard>
  );
}
