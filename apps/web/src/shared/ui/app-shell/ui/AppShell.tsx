// 화면의 뼈대: 어두운 왼쪽 메뉴 120 + 흰 머리 줄 64 + 회색 본문(밴드 FW1 ①, 디자인 시스템 v8 AppShell 카드).
//
// - 왼쪽 메뉴는 이 모듈의 것이다. EDK 메뉴를 옮긴 것이 아니라 생김새만 가져왔다: 바탕 background-primary-inverse,
//   글자 text-secondary-inverse, 고른 항목은 주황 글자(orange-400) + 오른쪽 3px 주황 막대(support-orange).
// - 항목은 props 로 받는다. 고른 항목에 aria-current="page", 쓰지 않는 항목은 aria-disabled(누를 수 없고 Tab 에 남는다).
//   href 가 있으면 a, 없으면 button 으로 그린다(onSelect 로 알린다).
// - 머리 줄: 높이 64, 좌우 32, 아래 선 border-tertiary, 큰 제목 nanum-display-01 + font-black(900 — 시안 「관리자」, GW3R A1) text-secondary. 오른쪽 자리는 headerRight.
// - 본문: background-secondary, 좌우 32, 위 24·아래 40, 사이 24. 흰 카드는 shared/ui/card 의 Card 를 쓴다.
// - 로고는 넣지 않는다(카드: 자리 표시). logo 를 주면 그 자리에 그린다.
// - 하위 줄(밴드 LN1, sid:MARC-ENT-441 · 시안 AD-02_r3 .a-subnav): 항목의 children 을 부모 <li> 안 <ul>(aria-label = childrenLabel)로 늘 펼쳐 그린다.
//   한 단계뿐(AppShellSubItem 에 children·icon 이 없다). 글만, 왼쪽 맞춤. 꺼짐·href/onSelect 갈래는 위 항목과 같은 규칙.
//   currentId 가 하위 줄이면 그 줄(흰 글 700, 막대 없음)과 부모(위 고른 꼴 그대로) 둘 다 aria-current="page".
// - 맨 아래 줄(밴드 WS2, sid:MARC-ISSUE-371 L18 · 시안 admin-r1.css 「서비스 화면」 margin-top:auto): 항목에 pinBottom 을 주면
//   메뉴 ul 이 nav 의 남은 높이를 채우고(flex-1) 그 li 가 mt-auto 로 맨 아래에 붙는다. pinBottom 항목이 없으면 ul·li 클래스는 그대로다.
//   밴드 WS3(sid:MARC-TICK-335): nav 는 화면 높이에 고정(sticky top-0 · h-dvh · self-start)이라 문서를 스크롤해도 맨 아래 줄이
//   화면 왼쪽 아래에 남는다. 메뉴가 화면보다 길면 nav 안에서만 세로로 스크롤된다(overflow-y-auto, 로고 자리는 shrink-0).
//   h-dvh: 데스크톱에선 100vh 와 같고, 주소창이 접히는 브라우저에선 보이는 높이를 따라가 맨 아래 줄이 가려지지 않는다.
// 하지 않는 것: 좁은 화면에서 메뉴를 위로 눕히는 꼴(시안 gw-r1.css 의 좁은 화면 규칙). 화면은 1920 데스크톱 기준이다.
//   최소 폭 1280(sid:MARC-ENT-213): 그보다 좁으면 줄이지 않고 화면 전체가 가로로 스크롤된다.
import * as React from 'react';

import { cn } from '@marcspon/ui/lib/utils';

/** 하위 줄. 아이콘·손자가 없다(한 단계만). */
export interface AppShellSubItem {
  id: string;
  label: string;
  /** 있으면 링크로 그린다. */
  href?: string;
  /** 참이면 aria-disabled. 누를 수 없다. */
  disabled?: boolean;
}

export interface AppShellMenuItem extends AppShellSubItem {
  /** 글자 위 20 아이콘(키트 아이콘). */
  icon?: React.ReactNode;
  /** 늘 펼친 하위 줄(한 단계). */
  children?: readonly AppShellSubItem[];
  /** 하위 줄 묶음 ul 의 이름(쓰는 쪽 문구 표). */
  childrenLabel?: string;
  /** 참이면 메뉴 맨 아래에 붙는다(시안 admin-r1.css 의 margin-top:auto — 어드민 「서비스 화면」). */
  pinBottom?: boolean;
}

export interface AppShellProps {
  /** 왼쪽 메뉴 항목. */
  menu: readonly AppShellMenuItem[];
  /** 고른 항목의 id. */
  currentId?: string;
  /** 메뉴 nav 의 이름(예: 「모듈 메뉴」). */
  menuLabel: string;
  /** href 없는 항목을 눌렀을 때. */
  onSelect?: (id: string) => void;
  /** 머리 줄의 큰 제목(h1). */
  title: React.ReactNode;
  /** 머리 줄 오른쪽(인사말·사용자 메뉴 자리). */
  headerRight?: React.ReactNode;
  /** 메뉴 위 로고 자리(64). 없으면 빈 자리. */
  logo?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

const itemClass =
  'box-border flex min-h-[58px] w-full flex-col items-center justify-center gap-1 border-0 border-r-[3px] border-solid border-transparent bg-transparent px-1 py-1.5 text-center text-style-pre-caption-02 text-text-secondary-inverse no-underline transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-secondary [&_svg]:size-5 [&_svg]:shrink-0';
const currentClass = 'border-r-support-orange text-orange-400';
const enabledClass = 'cursor-pointer hover:text-text-primary-inverse';
const disabledClass = 'cursor-not-allowed opacity-40';
// 하위 묶음 바탕 #111315 는 시안 값 그대로(토큰 밖 — 토큰 맞춤은 시안 몫 다음 판).
const subListClass = 'm-0 flex list-none flex-col bg-[#111315] px-0 py-1.5';
const subItemClass =
  'box-border flex min-h-[32px] w-full items-center justify-start border-0 bg-transparent px-3 py-1.5 text-left text-style-pre-caption-03 text-text-secondary-inverse no-underline transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-secondary';
const subCurrentClass = 'font-bold text-text-primary-inverse';

/** 메뉴 한 줄: href 가 있으면 a, 없으면 button. 꺼지면 aria-disabled(누를 수 없고 Tab 에 남는다). */
function MenuEntry({
  item,
  current,
  className,
  onSelect,
  children,
}: {
  item: AppShellSubItem;
  current: boolean;
  className: string;
  onSelect?: (id: string) => void;
  children: React.ReactNode;
}) {
  const look = cn(className, item.disabled ? disabledClass : enabledClass);
  return item.href !== undefined ?
      <a
        href={item.disabled ? undefined : item.href}
        role={item.disabled ? 'link' : undefined}
        tabIndex={item.disabled ? 0 : undefined}
        aria-current={current ? 'page' : undefined}
        aria-disabled={item.disabled || undefined}
        className={look}
      >
        {children}
      </a>
    : <button
        type="button"
        aria-current={current ? 'page' : undefined}
        aria-disabled={item.disabled || undefined}
        onClick={() => {
          if (!item.disabled) onSelect?.(item.id);
        }}
        className={look}
      >
        {children}
      </button>;
}

function AppShell({
  menu,
  currentId,
  menuLabel,
  onSelect,
  title,
  headerRight,
  logo,
  className,
  children,
}: AppShellProps) {
  return (
    <div
      data-app-shell=""
      className={cn(
        'grid min-h-full min-w-[1280px] grid-cols-[120px_minmax(0,1fr)] grid-rows-[64px_auto] bg-background-secondary text-text-secondary',
        className,
      )}
    >
      <nav
        aria-label={menuLabel}
        className="sticky top-0 row-span-2 flex h-dvh flex-col items-stretch self-start overflow-y-auto bg-background-primary-inverse"
      >
        <div className="box-border flex h-16 shrink-0 items-center justify-center border-0 border-b border-solid border-grey-700 text-style-pre-caption-01 text-text-secondary-inverse">
          {logo}
        </div>
        <ul
          className={cn(
            'm-0 flex list-none flex-col p-0',
            menu.some((item) => item.pinBottom) && 'flex-1',
          )}
        >
          {menu.map((item) => {
            const current =
              item.id === currentId ||
              (item.children?.some((sub) => sub.id === currentId) ?? false);
            return (
              <li
                key={item.id}
                className={item.pinBottom ? 'mt-auto' : undefined}
              >
                <MenuEntry
                  item={item}
                  current={current}
                  className={cn(itemClass, current && currentClass)}
                  onSelect={onSelect}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </MenuEntry>
                {item.children && item.children.length > 0 && (
                  <ul aria-label={item.childrenLabel} className={subListClass}>
                    {item.children.map((sub) => {
                      const subCurrent = sub.id === currentId;
                      return (
                        <li key={sub.id}>
                          <MenuEntry
                            item={sub}
                            current={subCurrent}
                            className={cn(
                              subItemClass,
                              subCurrent && subCurrentClass,
                            )}
                            onSelect={onSelect}
                          >
                            {sub.label}
                          </MenuEntry>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
      <header className="box-border flex h-16 items-center justify-between gap-4 border-0 border-b border-solid border-border-tertiary bg-background-primary px-8">
        <h1 className="m-0 text-style-nanum-display-01 font-black text-text-secondary">
          {title}
        </h1>
        {headerRight}
      </header>
      <main className="flex min-w-0 flex-col gap-6 px-8 pb-10 pt-6">
        {children}
      </main>
    </div>
  );
}
AppShell.displayName = 'AppShell';

export { AppShell };
