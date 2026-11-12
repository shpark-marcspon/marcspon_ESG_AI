// 결과를 「확인 필요 — 2차에서 보정」으로 표시하는 카테고리(밴드 S3N1 — sid:MARC-ENT-683 노트, 목록 3-6).
// 1차는 결과 값·셈을 그대로 두고(고침은 2차 새 흐름) 카드·상세의 카테고리 이름 옆에 고정 안내만 붙인다.
// 받은 예시에서 실제로 걸린 것은 C3 뿐이다(이슈 591·597). 늘리려면 이 목록에만 더한다.
// 꼴은 공용 중요 안내의 주황 글(PageInfo important 의 text-support-orange-dark) + 이 화면이 쓰는 경고 아이콘. 툴팁 0(디자인 c3 11-11).
import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import type { CategoryId } from '../../../entities/ghg-scope3/model/index.ts';

export const ADJUST_LATER_CATEGORIES: readonly CategoryId[] = ['C3'];

/**
 * 이름 옆 고정 안내. 목록에 없는 카테고리면 아무것도 그리지 않는다.
 * 이름과는 빈칸 하나로 띄운다 — 좁은 카드에서 다음 줄로 넘어가면 그 줄 머리가 이름과 맞는다(여백이면 들여 써짐, 그림 대조).
 */
export function AdjustLaterMark({ category }: { category: CategoryId }) {
  if (!ADJUST_LATER_CATEGORIES.includes(category)) return null;
  return (
    <>
      {' '}
      <span
        data-testid="s3-adjust-later"
        className="inline-flex items-center gap-1 align-middle text-style-pre-caption-02 text-support-orange-dark"
      >
        <CircleWarningIcon aria-hidden className="size-4 shrink-0" />
        {S3_TEXT.result.adjustLater}
      </span>
    </>
  );
}
