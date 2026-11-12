// 모달 제목. 키트 DialogTitle 을 감싸 기본 글자 꼴을 준다(밴드 FW1 ⓪).
//
// 키트 Title 은 클래스가 없고, 키트 default Header 의 text-style-pre-heading-02(18)를 물려받는다.
// 디자이너 값은 꼴마다 다르다: 일반 모달·표가 든 모달의 제목은 Bold 24(pre-display-04), 확인 모달(Alert)은 18(pre-heading-02).
// 우리 Content 는 default 꼴로 고정이므로 기본을 24 로 둔다. Alert 꼴 제목은 쓰는 쪽이 className 으로 덮는다
// (cn 의 text-style 그룹이 뒤의 것을 남긴다. 예: greenwash 의 ConfirmReviewDialog).
// 근거: band-reports/FK2-design-review.md 4, 디자인 시스템 v8 Modal 카드.
// ./kit.ts 는 키트 Title 을 그대로 다시 내보낸 채 둔다(FK2 의 기존 시험이 그것을 가져온다). 공개 표면 index.ts 는 이 파일의 것을 내보낸다.
import * as React from 'react';

import { DialogTitle as KitDialogTitle } from '@marcspon/ui/components/dialog';
import { cn } from '@marcspon/ui/lib/utils';

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof KitDialogTitle>,
  React.ComponentPropsWithoutRef<typeof KitDialogTitle>
>(({ className, ...props }, ref) => (
  <KitDialogTitle
    ref={ref}
    className={cn('text-style-pre-display-04 text-text-primary', className)}
    {...props}
  />
));
DialogTitle.displayName = 'DialogTitle';

export { DialogTitle };
