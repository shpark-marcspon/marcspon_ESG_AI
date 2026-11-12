// 모달의 본체(Content). 키트 dialog 의 Content 만 다시 짰다(밴드 FK2, 2026-10-15 사용자 결정 「넷 다 디자이너 값」).
// Header·Body·Footer·Close·Title·Description 과 루트 Dialog 는 키트 것을 그대로 쓴다(./kit.ts 가 다시 내보낸다).
//
// 키트 Content 와 다른 것은 넷이다.
//   1) 덮개 색: bg-black-transparent-500 (#1C1E21 50%. 디자이너 값). 키트는 bg-[rgba(0,0,0,0.48)].
//   2) 그림자: shadow/strong (아래 SHADOW_STRONG). 키트는 shadow-lg.
//   3) 덮개를 우리가 그린다: 키트 DialogOverlay 에 className 으로 색을 덮어써서 Portal 안에 직접 둔다.
//   4) 바탕 글 14(pre-body-06)·간격 16(gap-4). 키트는 글을 정하지 않아 16 을 물려받고 간격은 24 다(sid:MARC-ISSUE-344 SB9).
// 나머지(가운데 자리, 크기 sm 420·md 640·lg 800, rounded-dialog, 안쪽 32, scrollBehavior, z-modal, twp)는
// 키트 dialogContentVariants·DialogOverlay 의 클래스를 그대로 따른다.
//
// 크기와 변형 [B1]: 키트의 DialogStyleContext 는 export 되지 않아 우리 Content 가 루트 Dialog 의 size 를 읽을 수 없다.
// 그래서 size 는 Content 의 prop 으로 받는다(기본 md). variant 는 default 로 고정하고 받지 않는다.
// 키트 Header·Body·Footer 는 context 에서 variant 만 읽는데, 루트에 variant 를 주지 않으면 context 는 default 다.
//
// 초점 되돌리기(밴드 FW2 ⓪, sid:MARC-ISSUE-97 1번): Radix 는 닫힐 때 DialogTrigger 로만 초점을 돌린다. 코드로(open) 연 모달은 Trigger 가 없어
// 닫힌 뒤 초점이 body 로 떨어진다. 그래서 열릴 때 초점이 있던 요소를 적어 두었다가 닫힐 때 그리로 돌린다(Trigger 로 열었으면 그 자리가 곧 Trigger).
// 쓰는 쪽의 onOpenAutoFocus·onCloseAutoFocus 는 먼저 부른다. 쓰는 쪽이 onCloseAutoFocus 에서 preventDefault 하면 돌리지 않는다(쓰는 쪽이 초점을 정함).
import * as React from 'react';

import {
  DialogOverlay,
  dialogContentVariants,
} from '@marcspon/ui/components/dialog';
import { cn } from '@marcspon/ui/lib/utils';
import * as DialogPrimitive from '@radix-ui/react-dialog';

/**
 * 모달 그림자 shadow/strong: 3px 3px 10px, 순수 검정 20%(#00000033. #1C1E21 20% 가 아니다).
 * 출처: Figma 변수 shadow/strong, 디자인 시스템 시안 v8 의 --shadow-strong. 2026-10-15 디자인 감독 확인(FK2 발주서 §1-5).
 * 키트에 그림자 토큰이 없어 이 한 자리만 임의 값을 쓴다. 그림자 토큰이 생기면 그 클래스로 바꾼다.
 */
const SHADOW_STRONG = 'shadow-[3px_3px_10px_#00000033]';

export const DIALOG_SIZES = ['sm', 'md', 'lg'] as const;
export type DialogSize = (typeof DIALOG_SIZES)[number];

export interface DialogContentProps extends React.ComponentPropsWithoutRef<
  typeof DialogPrimitive.Content
> {
  /** 너비: sm 420 · md 640 · lg 800. 기본 md. */
  size?: DialogSize;
  /** inside: 본문이 모달 안에서 스크롤된다(기본). outside: 모달이 화면과 함께 스크롤된다. */
  scrollBehavior?: 'inside' | 'outside';
}

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  DialogContentProps
>(
  (
    {
      className,
      children,
      size = 'md',
      scrollBehavior = 'inside',
      onOpenAutoFocus,
      onCloseAutoFocus,
      ...props
    },
    ref,
  ) => {
    const returnTo = React.useRef<HTMLElement | null>(null);
    const content = (
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          dialogContentVariants({ variant: 'default', size }),
          SHADOW_STRONG,
          'gap-4 text-style-pre-body-06',
          scrollBehavior === 'outside' &&
            'relative left-auto top-auto max-h-none shrink-0 overflow-visible [translate:0_0]',
          className,
        )}
        onOpenAutoFocus={(event) => {
          // 모달이 초점을 옮기기 전이라 지금 초점이 연 자리다.
          const active = document.activeElement;
          returnTo.current = active instanceof HTMLElement ? active : null;
          onOpenAutoFocus?.(event);
        }}
        onCloseAutoFocus={(event) => {
          const target = returnTo.current;
          returnTo.current = null;
          onCloseAutoFocus?.(event);
          if (event.defaultPrevented) return;
          if (target && target.isConnected) {
            event.preventDefault();
            target.focus();
          }
        }}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    );
    return (
      <DialogPrimitive.Portal>
        <DialogOverlay className="bg-black-transparent-500" />
        {scrollBehavior === 'outside' ?
          <div className="twp fixed inset-0 z-modal overflow-y-auto">
            <div className="box-border flex min-h-full items-center justify-center py-20">
              {content}
            </div>
          </div>
        : content}
      </DialogPrimitive.Portal>
    );
  },
);
DialogContent.displayName = 'DialogContent';

export { DialogContent };
