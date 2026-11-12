// 흰 카드와 화면 제목 줄(밴드 FW1 ①). 디자인 시스템 v8 AppShell 카드(본문의 흰 카드, 모서리 16)와 그린워싱 시안의 제목 줄.
//
// Card: 흰 바탕, 모서리 rounded-dialog(16), 안쪽 32.
// PageTitle: 제목 Bold 24(pre-display-04 text-primary) + 설명(pre-body-06 text-tertiary), 오른쪽 동작 자리. 아래쪽으로 맞춘다.
//   headingRef 를 받으면 h2 에 tabIndex -1(초점을 받는 제목. 밴드 LA1 ①)과 Button·IconButton 과 같은 focus-visible 바깥선(밴드 SB2 ①). 안 받으면 둘 다 없음.
//   자리 잡기(밴드 LD1 ③④, sid:MARC-ENT-443): 미리 아는 제목·설명은 처음부터 진짜 글로 준다(pending 을 쓰지 않는다).
//     데이터에서 오는 제목만 titlePending(h2 는 그대로 — 헤딩·headingRef 초점 유지 — 안에 막대 28%×22 + 숨긴 글),
//     데이터에서 오는 설명만 descriptionPending(설명 줄과 같은 높이의 자리에 막대 360×12 — 받은 뒤 아래가 1px 도 안 밀리게).
//     막대는 글 줄 안에 겹쳐 둔다(폭 0 글자로 줄 높이를 지키고 막대는 absolute) — 막대가 줄 높이를 바꾸지 않는다.
//   브레드크럼은 없다(그린워싱 화면 GW-01~06 은 제목 줄만 둔다. 인계 v56 덧붙임 1절).
import * as React from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import { SkeletonBar } from '../../skeleton-bar/index.ts';
import { PARTS_TEXT } from '../../text.ts';

const Card = React.forwardRef<
  HTMLElement,
  React.HTMLAttributes<HTMLElement> & { as?: 'section' | 'div' }
>(({ as: Tag = 'section', className, ...props }, ref) => (
  <Tag
    ref={ref as React.Ref<HTMLDivElement>}
    className={cn(
      'box-border min-w-0 rounded-dialog bg-background-primary p-8',
      className,
    )}
    {...props}
  />
));
Card.displayName = 'Card';

export interface PageTitleProps {
  /** 제목(h2). */
  title: React.ReactNode;
  /** 제목 아래 한 줄 설명. */
  description?: React.ReactNode;
  /** 오른쪽 동작 자리(버튼 줄). */
  actions?: React.ReactNode;
  /** 제목(h2)의 ref. 받으면 h2 가 초점을 받을 수 있다(tabIndex -1 — 다시 시도 뒤 초점, 밴드 LA1 ①). */
  headingRef?: React.Ref<HTMLHeadingElement>;
  /** 데이터에서 오는 제목을 아직 모른다. 참이면 h2 안에 막대(28%×22)와 숨긴 글(pendingLabel). title 은 그리지 않는다. */
  titlePending?: boolean;
  /** titlePending 때 h2 의 숨긴 글. 기본 「불러오는 중」. */
  pendingLabel?: string;
  /** 데이터에서 오는 설명을 아직 모른다. 참이고 description 이 없으면 설명 자리에 막대(360×12). */
  descriptionPending?: boolean;
  className?: string;
}

/** 글 줄 높이를 지키는 폭 0 글자. 막대(absolute)만 있으면 줄 상자가 생기지 않는다. */
const LINE_KEEPER = '\u200b';

function PageTitle({
  title,
  description,
  actions,
  headingRef,
  titlePending = false,
  pendingLabel = PARTS_TEXT.loading,
  descriptionPending = false,
  className,
}: PageTitleProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-end justify-between gap-4',
        className,
      )}
    >
      {/* 막대 폭(28%·360)의 기준이 되게 자리 잡는 동안 왼쪽 칸이 남은 폭을 갖는다. */}
      <div
        className={cn(
          'min-w-0',
          (titlePending || (descriptionPending && description == null)) &&
            'flex-1',
        )}
      >
        <h2
          ref={headingRef}
          tabIndex={headingRef ? -1 : undefined}
          className={cn(
            'm-0 text-style-pre-display-04 text-text-primary',
            titlePending && 'relative',
            headingRef &&
              'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary',
          )}
        >
          {titlePending ?
            <>
              <span className="sr-only">{pendingLabel}</span>
              <span aria-hidden data-testid="title-pending">
                {LINE_KEEPER}
                <SkeletonBar className="absolute left-0 top-1/2 h-[22px] w-[28%] -translate-y-1/2" />
              </span>
            </>
          : title}
        </h2>
        {description != null ?
          <p className="m-0 mt-1 text-style-pre-body-06 text-text-tertiary">
            {description}
          </p>
        : descriptionPending && (
            <p
              aria-hidden
              data-testid="description-pending"
              className="relative m-0 mt-1 text-style-pre-body-06 text-text-tertiary"
            >
              {LINE_KEEPER}
              {/* 6c 의 「제목 아래 10」: 줄(mt-1 = 4) 안 위 6 = 제목에서 10. 막대 12 는 줄 높이(22.4) 안에 든다. */}
              <SkeletonBar className="absolute left-0 top-1.5 h-3 w-[360px]" />
            </p>
          )
        }
      </div>
      {actions != null && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  );
}
PageTitle.displayName = 'PageTitle';

export { Card, PageTitle };
