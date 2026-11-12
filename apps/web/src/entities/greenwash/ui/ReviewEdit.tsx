// 검토 고침의 모양 부품(밴드 G1b-3 ③, 시안 GW-05_r2·05c_r2). 상태·저장·흐름을 모른다 — 값은 props 로 받고 고르면 부르기만.
//   - EditedMark: 고친 칸·고친 문장 줄의 「고침」 딱지(시안 g-mark--edit — 파랑 옅은 바탕·짙은 파랑 글, :59·:96).
//   - LevelPicker: 「등급 [High ▾]」(:83, 시안 e-select). 키트 dropdown-menu 를 감싼다(키트는 고치지 않는다). 단추 이름 「등급 고르기」,
//     펼치면 High·Mid·Low(menuitemradio, 지금 값에 aria-checked). 고르면 onPick 만 — 저장은 쓰는 화면이 한다.
//   - AiOriginal: 고친 칸 아래 접기(:99 <details>) — 머리 「AI 원래 판단 보기 · 고친 사람 {이름} · {MM-DD HH:MM}」, 펼치면 AI 값.
//     세 칸(등급·판정 사유·수정 방향) 각각에 따로 둔다(디자인 80 회신 Q9 — 고친 사람·시각은 칸마다).
import type { ReactNode } from 'react';

import {
  CheckIcon,
  ChevronDownIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@marcspon/ui/components/dropdown-menu';
import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../config/text.ts';
import { RISK_LEVELS, RiskBadge } from './RiskBadge.tsx';
import type { RiskLevel } from './RiskBadge.tsx';

const words = GW_TEXT.reviewScreen.edit;

export interface EditedMarkProps {
  className?: string;
}

/** 「고침」 딱지(읽기 전용). */
function EditedMark({ className }: EditedMarkProps) {
  return (
    <Badge
      variant="blue"
      size="sm"
      data-edited
      className={cn('px-1.5 text-support-blue-dark', className)}
    >
      {words.edited}
    </Badge>
  );
}
EditedMark.displayName = 'EditedMark';

export interface LevelPickerProps {
  /** 지금 보이는 등급. */
  level: RiskLevel;
  /** 등급을 고르면 부른다(지금 값을 다시 골라도 부른다 — 거르는 것은 쓰는 쪽). */
  onPick(level: RiskLevel): void;
  /** 참이면 단추를 끈다(펼치지 않는다). */
  disabled?: boolean;
  className?: string;
}

/** 「등급 [High ▾]」 — 고르는 꼴. */
function LevelPicker({ level, onPick, disabled, className }: LevelPickerProps) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span className="text-style-pre-body-03 text-text-secondary">
        {words.levelLabel}
      </span>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={words.levelPick}
          disabled={disabled}
          data-level-pick={level}
          className="inline-flex h-9 min-w-[120px] cursor-pointer items-center justify-between gap-2 rounded-component border border-solid border-border-tertiary bg-background-primary px-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary disabled:cursor-default disabled:opacity-60 [&_svg]:size-4"
        >
          <RiskBadge level={level} />
          <ChevronDownIcon aria-hidden className="text-text-tertiary" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {RISK_LEVELS.map((pick) => (
            <DropdownMenuItem
              key={pick}
              role="menuitemradio"
              aria-checked={pick === level}
              onSelect={() => onPick(pick)}
              className="gap-2 px-3 py-2 [&_svg]:size-4"
            >
              <span className="inline-flex w-4" aria-hidden>
                {pick === level && <CheckIcon />}
              </span>
              <RiskBadge level={pick} />
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </span>
  );
}
LevelPicker.displayName = 'LevelPicker';

export interface AiOriginalProps {
  /** 고친 사람 이름. */
  by: string;
  /** 꾸민 고친 때(「10-15 14:28」). */
  at: string;
  /** 펼치면 보이는 AI 값. */
  children: ReactNode;
  /** 어느 칸인지(시험·보조 표지 — data-column). */
  column: 'level' | 'reasonBullets' | 'fixParagraph';
  className?: string;
}

/** 고친 칸의 「AI 원래 판단 보기」 접기. 처음엔 접힘. */
function AiOriginal({ by, at, children, column, className }: AiOriginalProps) {
  return (
    <details
      data-ai-original={column}
      className={cn('text-style-pre-caption-02 text-text-tertiary', className)}
    >
      <summary className="cursor-pointer">{words.aiOriginal(by, at)}</summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}
AiOriginal.displayName = 'AiOriginal';

const rejudgeWords = GW_TEXT.reviewScreen.rejudge;

/** 「리스크 아님」 회색 딱지(재판단 outcome nonrisk — 덧붙임 4). 등급 배지 자리. */
function NonRiskBadge({ className }: EditedMarkProps) {
  return (
    <Badge variant="grey" size="sm" data-nonrisk className={className}>
      {rejudgeWords.nonRisk}
    </Badge>
  );
}
NonRiskBadge.displayName = 'NonRiskBadge';

/** 「재판단」 딱지(목록 줄 — 「고침」과 같은 꼴, r4 ②). */
function RejudgedMark({ className }: EditedMarkProps) {
  return (
    <Badge
      variant="blue"
      size="sm"
      data-rejudged
      className={cn('px-1.5 text-support-blue-dark', className)}
    >
      {rejudgeWords.rejudgedMark}
    </Badge>
  );
}
RejudgedMark.displayName = 'RejudgedMark';

/** 「직접 더함」 딱지(더한 근거 조각 앞, r4 ①). */
function AddedMark({ className }: EditedMarkProps) {
  return (
    <Badge
      variant="orange"
      size="sm"
      data-added-piece
      className={cn('shrink-0 px-1.5', className)}
    >
      {rejudgeWords.addedMark}
    </Badge>
  );
}
AddedMark.displayName = 'AddedMark';

export {
  AddedMark,
  AiOriginal,
  EditedMark,
  LevelPicker,
  NonRiskBadge,
  RejudgedMark,
};
