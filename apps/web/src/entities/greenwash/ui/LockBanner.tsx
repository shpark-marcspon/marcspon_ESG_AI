// 확정 뒤 잠금 띠(밴드 FW1 ②, 시안 GW-05c 의 g-lockband). 확정한 사람·일시를 글자로 보인다.
//
// 1px border-tertiary 테두리, 모서리 8, background-secondary, 위아래 12 · 좌우 16, 잠금 아이콘 16(text-tertiary)과 글 사이 8,
// 글자 pre-body-05 text-secondary. 화면에 처음부터 있는 안내라 알림 역할(role)은 붙이지 않는다.
// 문구는 문구 표(config/text.ts 의 lock.banner)이고 text 로 통째로 바꿀 수 있다.
import { LockIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../config/text.ts';

export interface LockBannerProps {
  /** 확정한 사람(가정 칸. 인계 v56 덧붙임 4절). 모르면 빈 글자 — 기본 문구는 「{일시}에 확정했어요」 꼴(밴드 FW2 ⑤). */
  by: string;
  /** 확정한 일시 글자(쓰는 쪽이 꼴을 정한다. 예: 「2026-10-16 10:20」). */
  at: string;
  /** 문구를 바꾼다. 확정한 사람·일시를 따로 받는다(말 차례를 쓰는 쪽이 정하게). */
  text?: (who: { by: string; at: string }) => string;
  className?: string;
}

function LockBanner({ by, at, text, className }: LockBannerProps) {
  return (
    <div
      data-lock-banner=""
      className={cn(
        'box-border flex items-center gap-2 rounded-component border border-solid border-border-tertiary bg-background-secondary px-4 py-3 text-style-pre-body-05 text-text-secondary',
        className,
      )}
    >
      <LockIcon aria-hidden className="size-4 shrink-0 text-text-tertiary" />
      <span className="min-w-0">
        {(text ?? GW_TEXT.lock.banner)({ by, at })}
      </span>
    </div>
  );
}
LockBanner.displayName = 'LockBanner';

export { LockBanner };
