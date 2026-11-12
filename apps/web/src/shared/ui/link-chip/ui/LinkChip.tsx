// 공통 링크 칩(보드 CM-04 r1): [지구][도메인] 제목 ↗, 새 탭. http(s) 가 아닌 값은 칩 없이 회색 글이고 주소를 속성에 싣지 않는다.
// 사이트 아이콘은 밖에서 가져오지 않는다. 툴팁은 native title 만 쓴다.
import { GlobeIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { isSafeLinkUrl } from '../../../lib/safeUrl.ts';
import { PARTS_TEXT } from '../../text.ts';
import { chipFacts, cleanText } from '../model/index.ts';

export interface LinkChipProps {
  /** 믿지 않는 값이어도 된다. 판별은 부품이 한다. */
  url: string;
  /** 제목. 없으면 경로 앞부분. */
  label?: string;
  className?: string;
}

const CHIP =
  'group relative box-border inline-flex h-6 max-w-[min(100%,calc(theme(spacing.16)*5))] items-center gap-1.5 whitespace-nowrap rounded-control border border-solid border-border-tertiary bg-background-secondary pl-1.5 pr-2 align-middle text-style-pre-caption-02 text-support-blue-dark no-underline hover:border-border-secondary hover:bg-background-tertiary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-support-blue-dark';

function LinkChip({ url, label, className }: LinkChipProps) {
  if (!isSafeLinkUrl(url))
    return (
      <span className={cn('break-all text-text-tertiary', className)}>
        {cleanText(label ?? '') || cleanText(url)}
      </span>
    );
  const { domain, title, tooltip, href } = chipFacts(url, label);
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={tooltip}
      aria-label={`${title} · ${domain} · ${PARTS_TEXT.opensInNewTab}`}
      className={cn(CHIP, className)}
    >
      <GlobeIcon
        aria-hidden="true"
        className="h-3 w-3 flex-none text-text-tertiary"
      />
      <span className="flex-none rounded-control bg-background-primary px-1 text-style-pre-caption-04 text-text-tertiary">
        {domain}
      </span>
      <span className="min-w-0 overflow-hidden text-ellipsis underline-offset-2 group-hover:underline">
        {title}
      </span>
      <span aria-hidden="true" className="flex-none text-text-tertiary">
        ↗
      </span>
    </a>
  );
}

export { LinkChip };
