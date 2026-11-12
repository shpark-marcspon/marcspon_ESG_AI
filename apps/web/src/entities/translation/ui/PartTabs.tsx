// 파트 탭 줄(밴드 TRW0b, 시안 TR-03·04 「전체 · CEO 메시지 · 스토리 · 일반」, 결정 sid:MARC-ENT-392). 모양 부품: props 만 받는다.
// - 키트 Tabs(line). roving tabindex·←/→·aria-selected 는 radix 가 한다. 끝나지 않은 탭도 눌러진다.
// - 탭마다 이름 옆 작은 상태 글(완료는 ✓ 아이콘 + 글). [전체] 탭은 note(「1 / 3 완료」).
// - 파트 탭이 하나뿐이면(쪽을 한 파트에만 넣음) 탭 줄 없이 children 만(시안 상태 예시 ④). 쪽 없는 파트는 부르는 쪽이 빼고 넘긴다.
import type { ReactNode } from 'react';

import { CheckIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../../shared/ui/tabs/index.ts';
import type { PartKey, TabState } from '../model/index.ts';
import { tabLabel } from './labels.ts';

export type PartTabKey = 'all' | PartKey;

export interface PartTab {
  key: PartTabKey;
  label: string;
  state?: TabState;
  /** 상태 대신 붙는 작은 글([전체] 탭의 「1 / 3 완료」). */
  note?: string;
}

export interface PartTabsProps {
  tabs: readonly PartTab[];
  value: PartTabKey;
  onChange(key: PartTabKey): void;
  /** 탭 줄의 이름(스크린 리더). */
  'aria-label'?: string;
  children: ReactNode;
}

/** 탭 옆 상태 글의 꼴. */
const STATE_LOOK: Record<TabState, string> = {
  done: 'text-support-green-dark',
  running: 'text-support-orange-dark',
  queued: 'text-text-quaternary',
  failed: 'text-support-error',
  failed_partial: 'text-support-error',
};

export function PartTabs({
  tabs,
  value,
  onChange,
  'aria-label': ariaLabel,
  children,
}: PartTabsProps) {
  if (tabs.filter((tab) => tab.key !== 'all').length <= 1)
    return <>{children}</>;
  return (
    <Tabs
      value={value}
      onValueChange={(next) => onChange(next as PartTabKey)}
      variant="line"
    >
      <TabsList aria-label={ariaLabel}>
        {tabs.map((tab) => (
          <TabsTrigger
            key={tab.key}
            value={tab.key}
            data-tab={tab.key}
            className="inline-flex items-center gap-1.5"
          >
            {tab.label}
            {tab.state !== undefined ?
              <small
                data-state={tab.state}
                className={cn(
                  'inline-flex items-center gap-0.5 text-style-pre-caption-02 [&_svg]:size-3',
                  STATE_LOOK[tab.state],
                )}
              >
                {tab.state === 'done' && (
                  <CheckIcon aria-hidden className="gw-m-pop" />
                )}
                {tabLabel(tab.state)}
              </small>
            : tab.note !== undefined && (
                <small className="text-style-pre-caption-02 text-text-quaternary">
                  {tab.note}
                </small>
              )
            }
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value={value} className="pt-4">
        {/* 탭을 바꾸면 감싸개가 새로 붙어 다시 비친다(밴드 TRP4 ②-5). 탭 단추는 밖이라 ←/→ 초점은 그대로 */}
        <div key={value} className="gw-m-fade">
          {children}
        </div>
      </TabsContent>
    </Tabs>
  );
}
