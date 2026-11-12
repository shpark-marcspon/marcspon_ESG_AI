// AI 가 쓴 마크다운 글을 그린다(밴드 MD1, 결정 sid:MARC-ENT-572, 서식은 보드 CM-04 r1). 믿지 않는 글이라는 전제다.
// 원 HTML 은 요소로 만들지 않고 글자로 보인다(rehype-raw 금지). 링크는 공통 칩이 가르고, 그림은 부르지 않고 대체 글자만 남긴다.
// preflight 가 꺼져 있어 여백·목록·테두리의 브라우저 기본값을 요소마다 지운다(border 는 border-solid 가 있어야 그려진다).
// 상자 테두리는 쓰는 쪽 몫이다.
import type { ComponentProps, ReactNode } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import ReactMarkdown, {
  type Components,
  type ExtraProps,
} from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { LinkChip } from '../../link-chip/index.ts';
import { PARTS_TEXT } from '../../text.ts';
import { isPlainNumber, nodeText, remarkLinks } from '../model/index.ts';

export interface MarkdownTextProps {
  /** 마크다운 글. */
  children: string;
  className?: string;
  'data-testid'?: string;
}

const REMARK_PLUGINS = [remarkGfm, remarkLinks];
const HEADING_HIGH =
  'm-0 mt-2 text-style-pre-body-01 text-text-primary first:mt-0';
const HEADING_LOW = 'm-0 text-style-pre-body-04 text-text-primary';
const LIST = 'm-0 flex flex-col gap-1 pl-6';
const CELL = 'border-0 border-b border-solid px-3 py-2';

type HeadingProps = ComponentProps<'h1'>;

// 화면이 h1~h4 를 쓰므로 글 안 제목은 요소를 낮춘다. 각주 머리(h2.sr-only)가 보이지 않게 className 은 지킨다.
function HighHeading({ children, className }: HeadingProps) {
  return <h5 className={cn(HEADING_HIGH, className)}>{children}</h5>;
}

function LowHeading({ children, className }: HeadingProps) {
  return <h6 className={cn(HEADING_LOW, className)}>{children}</h6>;
}

function ChipLink({ href, node }: ComponentProps<'a'> & ExtraProps) {
  return <LinkChip url={href ?? ''} label={nodeText(node)} />;
}

function ImageAlt({ alt }: ComponentProps<'img'>): ReactNode {
  return alt ? <span>{alt}</span> : null;
}

function Cell({ children, node }: ComponentProps<'td'> & ExtraProps) {
  return (
    <td
      className={cn(
        CELL,
        'min-w-16 border-border-quaternary align-top text-text-secondary [tr:last-child>&]:border-b-0',
        isPlainNumber(nodeText(node)) && 'min-w-0 whitespace-nowrap text-right',
      )}
    >
      {children}
    </td>
  );
}

const COMPONENTS: Components = {
  a: ChipLink,
  img: ImageAlt,
  h1: HighHeading,
  h2: HighHeading,
  h3: LowHeading,
  h4: LowHeading,
  h5: LowHeading,
  h6: LowHeading,
  p: ({ children }) => <p className="m-0">{children}</p>,
  strong: ({ children }) => (
    <strong className="font-bold text-text-primary">{children}</strong>
  ),
  ul: ({ children }) => <ul className={cn(LIST, 'list-disc')}>{children}</ul>,
  ol: ({ children }) => (
    <ol className={cn(LIST, 'list-decimal')}>{children}</ol>
  ),
  pre: ({ children }) => (
    <pre className="m-0 overflow-x-auto rounded-component bg-background-secondary px-4 py-3 [&>code]:bg-transparent [&>code]:px-0">
      {children}
    </pre>
  ),
  code: ({ children, className }) => (
    <code
      className={cn(
        'rounded-control bg-background-secondary px-1 font-mono text-style-pre-caption-03 text-text-primary',
        className,
      )}
    >
      {children}
    </code>
  ),
  blockquote: ({ children }) => (
    <blockquote className="m-0 flex flex-col gap-3 border-0 border-l-2 border-solid border-border-tertiary pl-3 text-text-tertiary">
      {children}
    </blockquote>
  ),
  hr: () => (
    <hr className="m-0 h-0 w-full border-0 border-t border-solid border-border-quaternary" />
  ),
  table: ({ children }) => (
    <div
      className="max-w-full overflow-x-auto rounded-component border border-solid border-border-tertiary"
      data-markdown-table=""
      tabIndex={0}
      role="region"
      aria-label={PARTS_TEXT.markdownTable}
    >
      <table className="m-0 min-w-full border-collapse text-style-pre-caption-03 tabular-nums">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th
      className={cn(
        CELL,
        'whitespace-nowrap border-border-tertiary bg-background-secondary text-left text-style-pre-caption-02 text-text-tertiary',
      )}
    >
      {children}
    </th>
  ),
  td: Cell,
};

function MarkdownText({
  children,
  className,
  'data-testid': testId,
}: MarkdownTextProps) {
  return (
    <div
      data-markdown=""
      data-testid={testId}
      className={cn(
        'flex min-w-0 flex-col gap-3 break-words text-style-pre-body-06 leading-[1.7] text-text-secondary',
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

export { MarkdownText };
