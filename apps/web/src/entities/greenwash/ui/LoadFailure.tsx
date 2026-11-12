// 불러오기 실패·없음 상자. 몸은 shared/ui/load-failure — TRW0a ①, 그린워싱 글만 넣는다.
// 단추 이름의 기본은 문구 표(config/text.ts)의 GW_TEXT.load.
import { LoadFailure as SharedLoadFailure } from '../../../shared/ui/load-failure/index.ts';
import type { LoadFailureProps } from '../../../shared/ui/load-failure/index.ts';
import { GW_TEXT } from '../config/text.ts';

export { LOAD_FAILURE_KINDS } from '../../../shared/ui/load-failure/index.ts';
export type {
  LoadFailureKind,
  LoadFailureProps,
} from '../../../shared/ui/load-failure/index.ts';

function LoadFailure({
  retryLabel = GW_TEXT.load.retry,
  listLabel = GW_TEXT.load.toList,
  ...props
}: LoadFailureProps) {
  return (
    <SharedLoadFailure
      retryLabel={retryLabel}
      listLabel={listLabel}
      {...props}
    />
  );
}
LoadFailure.displayName = 'LoadFailure';

export { LoadFailure };
