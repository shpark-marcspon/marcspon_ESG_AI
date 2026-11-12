// 한 줄 안내(Figma Page Info, 키트에 없다). 밴드 FW1 ①, 디자인 시스템 v8 PageInfo 카드.
//
// 꼴 넷: 기본(background-secondary + text-tertiary) · 중요(background-brand + support-orange-dark)
//        · 오류(support-error-subtle + support-error-accent) · 주의(support-blue-subtle + support-blue-dark — 시안 g-info--caution, 밴드 PD1).
// 위아래 12 · 좌우 16, 모서리 8, 아이콘(16)과 글 사이 8, 글자 pre-body-06.
// 알림 역할(role)은 붙이지 않는다: 화면에 처음부터 있는 안내다. 방금 생긴 오류를 알려야 하면 쓰는 쪽이 role 을 준다.
import * as React from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import { type VariantProps, cva } from 'class-variance-authority';

export const PAGE_INFO_TONES = [
  'default',
  'important',
  'error',
  'caution',
] as const;

const pageInfoVariants = cva(
  'box-border flex items-center gap-2 rounded-component px-4 py-3 text-style-pre-body-06 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      tone: {
        default: 'bg-background-secondary text-text-tertiary',
        important: 'bg-background-brand text-support-orange-dark',
        error: 'bg-support-error-subtle text-support-error-accent',
        caution: 'bg-support-blue-subtle text-support-blue-dark',
      },
    },
    defaultVariants: { tone: 'default' },
  },
);

export interface PageInfoProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof pageInfoVariants> {
  /** 글 앞 아이콘(키트 아이콘, 16). */
  icon?: React.ReactNode;
}

const PageInfo = React.forwardRef<HTMLDivElement, PageInfoProps>(
  ({ className, tone, icon, children, ...props }, ref) => (
    <div
      ref={ref}
      data-tone={tone ?? 'default'}
      className={cn(pageInfoVariants({ tone }), className)}
      {...props}
    >
      {icon}
      <div className="min-w-0">{children}</div>
    </div>
  ),
);
PageInfo.displayName = 'PageInfo';

export { PageInfo, pageInfoVariants };
