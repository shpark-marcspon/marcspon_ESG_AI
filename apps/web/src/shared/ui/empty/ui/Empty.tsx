// 빈 목록 자리. 키트 table-empty 대신 다시 만들었다(밴드 FK2).
// 문구는 받기만 한다. 「{등록/검색}된 {정보}가 없어요」 같은 문장을 만드는 것은 쓰는 쪽 몫이다.
// 높이는 최소 200(내용이 길면 늘어난다), 가운데. 버튼(action)은 보통 solidGrey round md 를 준다.
import * as React from 'react';

import { cn } from '@marcspon/ui/lib/utils';

export interface EmptyProps extends Omit<
  React.HTMLAttributes<HTMLDivElement>,
  'title'
> {
  /** 굵은 한 줄. */
  title: React.ReactNode;
  /** 그 아래 설명. */
  description?: React.ReactNode;
  /** 맨 아래 버튼 자리. */
  action?: React.ReactNode;
}

const Empty = React.forwardRef<HTMLDivElement, EmptyProps>(
  ({ title, description, action, className, ...props }, ref) => (
    <div
      {...props}
      ref={ref}
      className={cn(
        'flex min-h-[200px] w-full flex-col items-center justify-center text-center',
        className,
      )}
    >
      <p className="text-style-pre-body-04 text-text-secondary">{title}</p>
      {description != null && (
        <p className="mt-1 text-style-pre-body-06 text-text-tertiary">
          {description}
        </p>
      )}
      {action != null && <div className="mt-4">{action}</div>}
    </div>
  ),
);
Empty.displayName = 'Empty';

export { Empty };
