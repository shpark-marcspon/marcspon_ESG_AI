// AD-01b 임시 비밀번호(밴드 AD1 ②). 만들기·초기화 모달이 성공하면 같은 모달 안에서 이 내용으로 바뀐다(닫히면 연 단추로 초점이 돌아간다).
//   - 값은 쓰는 모달의 상태에서 props 로만 받는다. 이 부품은 값을 어디에도 두지 않는다(복사는 넣어 준 copy 하나).
//   - 열릴 때 초점은 [복사](디자인 원문 2026-10-18). 닫힘은 [확인]만 — Esc·바깥 누름은 쓰는 모달이 막는다(감독 판단 15).
//   - 읽기 전용 칸(고정폭 글꼴, aria-label 「임시 비밀번호」). 복사 결과는 늘 있는 role=status 에 글만 넣는다.
import { useEffect, useRef, useState } from 'react';

import {
  CircleWarningIcon,
  CopySimpleIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';

import { ACCOUNT_TEXT } from '../../../entities/account/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';

const words = ACCOUNT_TEXT.password;

export interface TemporaryPasswordProps {
  /** 누구 줄(「{username} · {name} · 계정을 만들었어요」). */
  who: string;
  password: string;
  copy(text: string): Promise<void>;
  onConfirm(): void;
}

export function TemporaryPassword({
  who,
  password,
  copy,
  onConfirm,
}: TemporaryPasswordProps) {
  const copyRef = useRef<HTMLButtonElement>(null);
  const [copied, setCopied] = useState<'idle' | 'done' | 'failed'>('idle');
  useEffect(() => copyRef.current?.focus(), []);
  return (
    <>
      <DialogTitle className="text-style-pre-heading-02">
        {words.title}
      </DialogTitle>
      <DialogDescription
        data-testid="who"
        className="m-0 text-style-pre-caption-02 text-text-tertiary"
      >
        {who}
      </DialogDescription>
      <div className="flex items-center gap-2">
        <Input
          readOnly
          aria-label={words.label}
          value={password}
          autoComplete="off"
          spellCheck={false}
          className="h-10 flex-1 font-mono text-[18px] font-bold tracking-[0.06em] text-text-primary"
          onFocus={(event) => event.currentTarget.select()}
        />
        <Button
          ref={copyRef}
          variant="outlineGrey"
          shape="round"
          size="md"
          className="h-10"
          onClick={() => {
            copy(password).then(
              () => setCopied('done'),
              () => setCopied('failed'),
            );
          }}
        >
          <CopySimpleIcon aria-hidden />
          {words.copy}
        </Button>
      </div>
      <p
        role="status"
        className="m-0 text-style-pre-caption-01 text-text-tertiary empty:hidden"
      >
        {copied === 'done' ?
          words.copied
        : copied === 'failed' ?
          words.copyFailed
        : null}
      </p>
      <PageInfo tone="important" icon={<CircleWarningIcon aria-hidden />}>
        {words.important}
      </PageInfo>
      <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
        {words.next}
      </p>
      <DialogFooter>
        <Button
          variant="solidBlack"
          shape="round"
          size="md"
          onClick={onConfirm}
        >
          {words.confirm}
        </Button>
      </DialogFooter>
    </>
  );
}
