// 한 줄 안내의 아이콘(밴드 AV2, sid:MARC-ISSUE-344 SB5). 시안 v149 는 선 동그라미 i(stroke)라 생성 아이콘 InformationIcon 을 쓴다.
// MyIcons 의 InfoIcon 은 칠한 동그라미라 시안과 다르다. 크기(16)와 색(tone 글자색)은 PageInfo 가 정한다.
// 쓰는 법: <PageInfo icon={<PageInfoIcon />}>. 그림이라 늘 aria-hidden 이다.
import * as React from 'react';

import { InformationIcon } from '@marcspon/common/generated/icons/MyIcons';

export type PageInfoIconProps = React.SVGProps<SVGSVGElement>;

function PageInfoIcon(props: PageInfoIconProps) {
  return <InformationIcon {...props} aria-hidden />;
}
PageInfoIcon.displayName = 'PageInfoIcon';

export { PageInfoIcon };
