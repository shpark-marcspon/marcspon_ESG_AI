// 불러오기 실패·없음 상자(밴드 LE1 ①, sid:MARC-ENT-260 ②③, 시안 CM-03 의 cm-fail — TRW0a ① 에서 그린워싱에서 shared 로 올림). 화면 주 데이터의 본문 자리 전체에 둔다.
//   - failed(꼴 틀림·읽기 실패·연결 끊김 — 사용자에게는 하나): 오류 안내(PageInfo error) + [다시 시도](solidBlack) + [목록으로](outlineGrey).
//   - missing(없음 404): 회색 안내(PageInfo 기본) + [목록으로] 하나. 다시 시도는 없다.
// 글은 받기만 한다(화면이 제 문구 표에서 준다). 단추 이름은 기본이 PARTS_TEXT.load. 단추는 받은 콜백이 있을 때만 그린다.
// actionRef 는 첫 단추(failed 는 [다시 시도], missing 은 [목록으로])에 붙는다 — 다시 시도 뒤 초점(밴드 LA1 ①, useRetryFocus).
// role="alert": 다시 시도 뒤 또 실패하면 쓰는 쪽이 loading 을 거쳐 이 상자를 새로 그리므로 다시 읽힌다(단추 안 스피너는 없다).
import type { Ref } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { Button } from '../../button/index.ts';
import { Card } from '../../card/index.ts';
import { PageInfo, PageInfoIcon } from '../../page-info/index.ts';
import { PARTS_TEXT } from '../../text.ts';

export const LOAD_FAILURE_KINDS = ['failed', 'missing'] as const;
export type LoadFailureKind = (typeof LOAD_FAILURE_KINDS)[number];

export interface LoadFailureProps {
  kind: LoadFailureKind;
  /** 안내 한 문장(「결과를 불러오지 못했어요」·「결과를 찾을 수 없어요」). */
  message: string;
  /** [다시 시도]. failed 에서만 그린다. */
  onRetry?(): void;
  /** [목록으로]. */
  onList?(): void;
  retryLabel?: string;
  listLabel?: string;
  /** 첫 단추(failed 는 [다시 시도], missing 은 [목록으로])의 ref. */
  actionRef?: Ref<HTMLButtonElement>;
  className?: string;
}

function LoadFailure({
  kind,
  message,
  onRetry,
  onList,
  retryLabel = PARTS_TEXT.load.retry,
  listLabel = PARTS_TEXT.load.toList,
  actionRef,
  className,
}: LoadFailureProps) {
  const failed = kind === 'failed';
  const retrying = failed && onRetry != null;
  return (
    <Card
      role="alert"
      data-testid="load-failure"
      data-kind={kind}
      className={cn('flex flex-col gap-4', className)}
    >
      <PageInfo
        tone={failed ? 'error' : 'default'}
        icon={failed ? <CircleWarningIcon aria-hidden /> : <PageInfoIcon />}
      >
        {message}
      </PageInfo>
      {(retrying || onList) && (
        <div className="flex flex-wrap items-center gap-2">
          {retrying && (
            <Button
              ref={actionRef}
              variant="solidBlack"
              shape="round"
              size="md"
              onClick={onRetry}
            >
              {retryLabel}
            </Button>
          )}
          {onList && (
            <Button
              ref={retrying ? undefined : actionRef}
              variant="outlineGrey"
              shape="round"
              size="md"
              onClick={onList}
            >
              {listLabel}
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}
LoadFailure.displayName = 'LoadFailure';

export { LoadFailure };
