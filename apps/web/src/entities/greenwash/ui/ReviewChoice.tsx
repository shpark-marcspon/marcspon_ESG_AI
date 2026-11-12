// 문장 검토 표시: 채택 · 제외 · 미검토(밴드 FW1 ②, 시안 GW-05·05c 의 g-mark).
//
// 꼴 둘:
//   - 읽기 전용(ReviewMark): 작은 딱지 하나. 채택 success, 제외 회색 바탕 + text-secondary, 미검토 테두리만(ring 1px border-tertiary).
//   - 고르는 꼴(ReviewChoice): 토글 버튼 둘(채택·제외, aria-pressed). 누르면 onChange 만 부른다.
//     제외를 눌러도 사유 모달을 열지 않는다: 그것은 쓰는 화면(FW1b·FW2)의 흐름이다(발주서 §1-5).
// 이 부품은 상태를 갖지 않는다. 값은 늘 props(value)로 받는다.
// 값 이름 adopted·excluded·unreviewed 는 GC1 초안 전이다(무효 조건: 계약이 이름을 바꾸면 REVIEW_VALUES 를 바꾼다).
import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import { Button } from '../../../shared/ui/button/index.ts';
import { GW_TEXT } from '../config/text.ts';

export const REVIEW_VALUES = ['adopted', 'excluded', 'unreviewed'] as const;
export type ReviewValue = (typeof REVIEW_VALUES)[number];
/** 고를 수 있는 값(미검토로 되돌리는 버튼은 없다. 시안 GW-05). */
export type ReviewPick = Exclude<ReviewValue, 'unreviewed'>;

type BadgeVariant = NonNullable<BadgeProps['variant']>;

/** 검토 값 → 딱지 꼴. 시안 g-mark--ok·out·todo. */
export const REVIEW_MARK_LOOK = {
  adopted: { variant: 'success', label: GW_TEXT.review.adopted },
  excluded: {
    variant: 'grey',
    className: 'text-text-secondary',
    label: GW_TEXT.review.excluded,
  },
  unreviewed: {
    variant: 'grey',
    className: 'bg-transparent ring-1 ring-inset ring-border-tertiary',
    label: GW_TEXT.review.unreviewed,
  },
} as const satisfies Record<
  ReviewValue,
  { variant: BadgeVariant; label: string; className?: string }
>;

export interface ReviewMarkProps {
  value: ReviewValue;
  className?: string;
}

/** 읽기 전용 딱지. */
function ReviewMark({ value, className }: ReviewMarkProps) {
  const look: { variant: BadgeVariant; label: string; className?: string } =
    REVIEW_MARK_LOOK[value];
  return (
    <Badge
      variant={look.variant}
      size="sm"
      data-review={value}
      className={cn('px-1.5', look.className, className)}
    >
      {look.label}
    </Badge>
  );
}
ReviewMark.displayName = 'ReviewMark';

export interface ReviewChoiceProps {
  /** 지금 값. 미검토면 둘 다 눌리지 않은 꼴. */
  value: ReviewValue;
  /** 버튼을 누르면 그 값으로 부른다. 이미 눌린 버튼을 다시 눌러도 같은 값으로 부른다. */
  onChange: (value: ReviewPick) => void;
  /** 묶음 이름. 기본 「검토」. */
  label?: string;
  /** 참이면 aria-disabled 로 끄고 누름을 막는다(초점은 남는다). */
  disabled?: boolean;
  className?: string;
}

// 차례는 [제외][채택](주 동작 채택이 오른쪽). 시안 GW-05, 디자인 대조 물음 6(밴드 FW1b ⓪).
const PICKS: readonly ReviewPick[] = ['excluded', 'adopted'];

/** 고르는 꼴: 토글 버튼 둘. */
function ReviewChoice({
  value,
  onChange,
  label = GW_TEXT.review.groupLabel,
  disabled,
  className,
}: ReviewChoiceProps) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('flex items-center gap-2', className)}
    >
      {PICKS.map((pick) => {
        const pressed = value === pick;
        return (
          // 꺼짐은 aria-disabled + 누름 막기(Button asChild 가 캡처 단계에서 막는다). 진짜 disabled 면 저장 중에
          // 초점이 body 로 빠진다(밴드 FW2 ⑤ M4).
          <Button
            key={pick}
            asChild
            disabled={disabled}
            variant={pressed ? 'solidBlack' : 'outlineGrey'}
            shape="round"
            size="md"
          >
            <button
              type="button"
              aria-pressed={pressed}
              onClick={() => onChange(pick)}
            >
              {REVIEW_MARK_LOOK[pick].label}
            </button>
          </Button>
        );
      })}
    </div>
  );
}
ReviewChoice.displayName = 'ReviewChoice';

export { ReviewChoice, ReviewMark };
