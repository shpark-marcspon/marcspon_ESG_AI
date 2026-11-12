// 탭. 키트 tabs 를 감싸 시안 v149 의 꼴을 준다(밴드 AV2, sid:MARC-ISSUE-344 SB2·SB3).
//
// 키트와 다른 것:
//   - box: 안 고른 칸 글자 tertiary(#6F7781). 키트는 quaternary.
//   - line: 목록 밑줄 1px(border-b). 키트는 2px. 칸은 최소 96(min-w-24)·가운데 정렬, 고른 칸의 2px 밑줄이 목록 밑줄에 겹치게 -mb-px.
// 그 밖 변형(page·editor·modal)은 키트 그대로 넘긴다. 쓰는 쪽 className 이 마지막이다.
//
// 키트의 변형 context(TabsStyleContext)는 export 되지 않는다(dialog 와 같은 사정). 그래서 루트 Tabs 가 variant 를
// 우리 context 에도 담고, 우리 List·Trigger 는 그 값을 읽어 덧붙일 클래스를 고른다. 키트 Tabs 에도 같은 variant 를 넘긴다.
import * as React from 'react';

import {
  Tabs as KitTabs,
  TabsList as KitTabsList,
  TabsTrigger as KitTabsTrigger,
  TabsContent,
} from '@marcspon/ui/components/tabs';
import type { TabsProps } from '@marcspon/ui/components/tabs';
import { cn } from '@marcspon/ui/lib/utils';

type TabsVariant = NonNullable<TabsProps['variant']>;

const TabsVariantContext = React.createContext<TabsVariant>('line');

function Tabs({ variant = 'line', ...props }: TabsProps) {
  return (
    <TabsVariantContext.Provider value={variant}>
      <KitTabs variant={variant} {...props} />
    </TabsVariantContext.Provider>
  );
}

const TabsList = React.forwardRef<
  React.ElementRef<typeof KitTabsList>,
  React.ComponentPropsWithoutRef<typeof KitTabsList>
>(({ className, ...props }, ref) => {
  const variant = React.useContext(TabsVariantContext);
  return (
    <KitTabsList
      ref={ref}
      className={cn(variant === 'line' && 'border-b', className)}
      {...props}
    />
  );
});
TabsList.displayName = 'TabsList';

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof KitTabsTrigger>,
  React.ComponentPropsWithoutRef<typeof KitTabsTrigger>
>(({ className, ...props }, ref) => {
  const variant = React.useContext(TabsVariantContext);
  return (
    <KitTabsTrigger
      ref={ref}
      className={cn(
        variant === 'box' && 'text-text-tertiary',
        variant === 'line' && '-mb-px min-w-24 justify-center',
        className,
      )}
      {...props}
    />
  );
});
TabsTrigger.displayName = 'TabsTrigger';

export { Tabs, TabsContent, TabsList, TabsTrigger };
export type { TabsProps };
