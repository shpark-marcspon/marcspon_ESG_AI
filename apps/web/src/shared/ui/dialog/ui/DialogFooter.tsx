// 모달 단추 줄. 키트 DialogFooter 를 감싸 위에 8 을 더 준다(pt-2 — 시안 `.e-modal .foot{padding-top:8px}`, 창마다 같다. AV2 디자인 대조 N3).
// 몸과 단추 줄 사이는 Content 의 gap 16 + 이 8 = 24 다. ./kit.ts 는 키트 Footer 를 그대로 다시 내보낸 채 둔다. 공개 표면 index.ts 는 이 파일의 것을 내보낸다.
import * as React from 'react';

import { DialogFooter as KitDialogFooter } from '@marcspon/ui/components/dialog';
import { cn } from '@marcspon/ui/lib/utils';

const DialogFooter = React.forwardRef<
  React.ElementRef<typeof KitDialogFooter>,
  React.ComponentPropsWithoutRef<typeof KitDialogFooter>
>(({ className, ...props }, ref) => (
  <KitDialogFooter ref={ref} className={cn('pt-2', className)} {...props} />
));
DialogFooter.displayName = 'DialogFooter';

export { DialogFooter };
