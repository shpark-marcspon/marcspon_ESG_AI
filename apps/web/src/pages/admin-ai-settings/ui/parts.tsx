// AD-02 화면 안 작은 부품(밴드 AD2 ②). 시안 꼴(a-chip·e-btn--disabled)이 키트·shared/ui 에 없어 이 화면 ui 안에서 Tailwind 로 그린다.
// 열 상자·고르는 줄·「편집중」 꼬리표·판 열은 밴드 AD2R ② 에서 공통 부품 shared/ui/ai-setting 으로 옮겼다(sid:MARC-ENT-350).
import type { MouseEvent, ReactNode, Ref } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import type { ButtonProps } from '../../../shared/ui/button/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';

/**
 * 끌 수 있는 단추(디자인 원문 — 끈 단추는 e-btn--disabled + aria-disabled 로 보이되 끔, 설명 글 없음). Tab 에 남는다.
 * 공용 Button 은 aria-disabled 를 스스로 정해(asChild 아닐 때 없음) 네이티브 단추에 꼴만 빌린다(AD-01 [사용 중지]와 같은 꼴).
 * off 면 누름 처리기를 부르지 않는다(critic 반영 2 — 속성만이 아니라 동작까지 끔).
 */
export function ActionButton({
  off,
  onClick,
  variant = 'solidGrey',
  shape = 'square',
  size = 'sm',
  children,
  className,
}: {
  off: boolean;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  variant?: ButtonProps['variant'];
  shape?: ButtonProps['shape'];
  size?: ButtonProps['size'];
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      aria-disabled={off || undefined}
      className={cn(
        buttonVariants({ variant, shape, size }),
        off && 'cursor-not-allowed opacity-40',
        className,
      )}
      onClick={(event) => {
        if (off) return;
        onClick?.(event);
      }}
    >
      {children}
    </button>
  );
}

/** 자리 글 칩(시안 .a-chip). */
export function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex h-5 items-center rounded-control bg-background-secondary px-1.5 text-style-pre-caption-02 text-text-tertiary">
      {children}
    </span>
  );
}

/** 실패 상자(CM-03 꼴 — MARC-ENT-260). */
export function LoadFailure({
  text,
  retry,
  onRetry,
  retryRef,
  testId = 'load-failure',
}: {
  text: string;
  retry: string;
  onRetry(): void;
  retryRef?: Ref<HTMLButtonElement>;
  /** 시험이 찾는 표식(상세 실패는 detail-failure). */
  testId?: string;
}) {
  return (
    <div
      role="alert"
      data-testid={testId}
      className="flex flex-col items-start gap-4 py-6"
    >
      <PageInfo
        tone="error"
        icon={<CircleWarningIcon aria-hidden />}
        className="w-full"
      >
        {text}
      </PageInfo>
      <Button
        ref={retryRef}
        variant="solidBlack"
        shape="round"
        size="md"
        onClick={onRetry}
      >
        {retry}
      </Button>
    </div>
  );
}
