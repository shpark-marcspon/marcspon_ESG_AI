// AI 설정의 판 열 부품(밴드 AD2R ② — sid:MARC-ENT-350 「버전(목록·새 버전·적용)은 모듈 공통」, 디자인 캔버스 v110 AD-02-CM ①).
// 도메인을 모른다: 판 줄(이름·배지·꼬리 글·편집 글)과 글은 모두 props 로 받는다. 모듈마다 다른 규칙 값(기준표 등)은 이 부품 밖이다.
//   - Column: 열 상자 하나(머리 52px + 고르는 줄 목록). ColumnItem: 고르는 줄(aria-pressed).
//   - VersionColumn: 판 열 — 맨 위 [새 버전](끌 수 있음 — 끄면 aria-disabled 이고 누름 처리기가 돌지 않는다), 판 줄, 줄 사이 구분선(divided), 끝 자리(footer).
//     편집 중인 줄은 주황 2px 테두리 + 날짜 꼬리 다음 주황 둘째 꼬리 글(editNote — 시안 v148, 「편집중」 꼬리표 없음 GW3R A11). 시안의 줄 끝 끌기 손잡이(.hdl)는 차례 바꾸기 동작이 없어 그리지 않는다.
//     밴드 AD2W ②: 판 이름이 길면 줄 안에서 말줄임, 올리면 전체 이름(title — r3 「40자로 길 때 목록에서 말줄임」).
//   밴드 LK2: 고정(읽기 전용) 줄은 locked — 이름 앞 14px 자물쇠(시안 v148 .a-item .lock, aria-hidden — 버튼 이름 그대로).
import type { ReactNode } from 'react';

import { PlusIcon } from '@marcspon/common/generated/icons/MyIcons';
import { LockIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

/** 열 상자 하나(시안 .a-col — 머리 + 고르는 줄 목록). */
export function Column({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="flex min-w-0 flex-col border-0 border-r border-solid border-border-tertiary last:border-r-0"
    >
      <h3 className="m-0 flex h-[52px] items-center justify-center border-0 border-b border-solid border-border-quaternary px-0 text-center text-style-pre-body-04 text-text-primary">
        {title}
      </h3>
      <ul className="m-0 flex list-none flex-col gap-1 p-2">{children}</ul>
    </section>
  );
}

/** 열 상자의 고르는 줄(시안 .a-item — 고른 것은 .on, 편집 중은 .edit). */
export function ColumnItem({
  selected,
  onSelect,
  children,
  sum,
  editNote,
  tag,
  editing = false,
  divided = false,
  locked = false,
}: {
  selected: boolean;
  onSelect(): void;
  children: ReactNode;
  sum?: ReactNode;
  /** 편집 줄의 둘째 꼬리 글(날짜 꼬리 다음, 주황). */
  editNote?: ReactNode;
  tag?: ReactNode;
  /** 저장하지 않은 고침이 있는 줄(주황 테두리). */
  editing?: boolean;
  /** 앞 줄과 사이에 구분선. */
  divided?: boolean;
  /** 고정(읽기 전용) 줄 — 이름 앞 자물쇠. */
  locked?: boolean;
}) {
  return (
    <li
      className={cn(
        divided &&
          'mt-1 border-0 border-t border-solid border-border-tertiary pt-2',
      )}
    >
      <button
        type="button"
        aria-pressed={selected}
        data-editing={editing || undefined}
        onClick={onSelect}
        className={cn(
          'box-border flex w-full cursor-pointer items-center gap-2 rounded-component border-2 border-solid px-3 py-2 text-left text-style-pre-body-06 text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary',
          editing ? 'border-support-orange' : 'border-transparent',
          selected ?
            'bg-background-secondary text-text-secondary'
          : 'bg-transparent hover:bg-background-secondary',
        )}
      >
        <span className="flex min-w-0 grow flex-wrap items-center gap-1.5">
          {locked ?
            <span className="flex min-w-0 items-center gap-2">
              <LockIcon
                aria-hidden
                className="size-3.5 shrink-0 text-text-tertiary"
              />
              {children}
            </span>
          : children}
        </span>
        {sum != null && (
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {sum}
          </span>
        )}
        {editNote != null && (
          <span
            data-edit-note
            className="text-style-pre-caption-02 text-support-orange-dark"
          >
            {editNote}
          </span>
        )}
        {tag}
      </button>
    </li>
  );
}

/** 판 줄 배지의 꼴(키트 badge 변형 — 시험 중 blue, 적용 중 success, 그 밖 grey). */
export type VersionBadgeLook = 'blue' | 'success' | 'grey';

export interface VersionColumnRow {
  /** 고름 열쇠(data-version 에도 싣는다). */
  key: string;
  name: string;
  badge: { label: string; look: VersionBadgeLook };
  /** 꼬리 글(만든 날 · 요약). */
  sum?: ReactNode;
  /** 저장하지 않은 고침이 이 판에 있는가(주황 테두리). */
  editing?: boolean;
  /** 편집 줄의 둘째 꼬리 글(「v3 바탕으로 고치는 중」 — 날짜 꼬리 다음). */
  editNote?: ReactNode;
  /** 앞 줄과 사이에 구분선(기본 판 줄 — 디자인 D2). */
  divided?: boolean;
}

export interface VersionColumnProps {
  /** 열 머리 글(「버전」). */
  title: string;
  rows: readonly VersionColumnRow[];
  /** 고른 줄의 열쇠. */
  selected: string | null;
  onSelect(key: string): void;
  /** 맨 위 [새 버전]. off 면 aria-disabled, 누름 처리기가 돌지 않는다. */
  newVersion?: {
    label: string;
    off: boolean;
    title?: string;
    onClick?(): void;
  };
  /** 줄 목록 끝 자리([더 보기] 등). */
  footer?: ReactNode;
}

export function VersionColumn({
  title,
  rows,
  selected,
  onSelect,
  newVersion,
  footer,
}: VersionColumnProps) {
  return (
    <Column title={title}>
      {newVersion && (
        <li>
          <button
            type="button"
            aria-disabled={newVersion.off || undefined}
            title={newVersion.title}
            className={cn(
              'flex h-10 w-full items-center gap-2 border-0 bg-transparent px-3 text-left text-style-pre-body-06 text-text-tertiary',
              newVersion.off ?
                'cursor-not-allowed opacity-40'
              : 'cursor-pointer',
            )}
            onClick={() => {
              if (newVersion.off) return;
              newVersion.onClick?.();
            }}
          >
            <span className="inline-flex size-5 items-center justify-center rounded-full bg-background-secondary">
              <PlusIcon aria-hidden className="size-4" />
            </span>
            {newVersion.label}
          </button>
        </li>
      )}
      {rows.map((row) => (
        <ColumnItem
          key={row.key}
          selected={row.key === selected}
          onSelect={() => onSelect(row.key)}
          sum={row.sum}
          editNote={row.editNote}
          editing={row.editing}
          divided={row.divided}
        >
          <b
            data-version={row.key}
            title={row.name}
            className="min-w-0 truncate"
          >
            {row.name}
          </b>
          <Badge variant={row.badge.look}>{row.badge.label}</Badge>
        </ColumnItem>
      ))}
      {footer != null && <li>{footer}</li>}
    </Column>
  );
}
