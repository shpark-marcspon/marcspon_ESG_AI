// 데이터 검증 AI 설정 판 ui 칸의 공개 표면(밴드 DVA2). app/admin/ai-setting-modules.ts 만 가져온다.
//   flowSlot: 처리 흐름 띠 + 칸 고름 그리기 — 껍데기의 FlowProps 와 구조로 맞춘다(DataverifyFlowBand 에 글 표를 붙여 넘김, entities/ai-setting 은 가져오지 않는다).
import { createElement } from 'react';
import type { ReactNode } from 'react';

import type { DATAVERIFY_SETTING_TEXT } from '../config/text.ts';
import { DataverifyFlowBand } from './DataverifyFlowBand.tsx';
import type { DataverifyFlowBandProps } from './DataverifyFlowBand.tsx';

export { DataverifyFlowBand } from './DataverifyFlowBand.tsx';
export type { DataverifyFlowBandProps } from './DataverifyFlowBand.tsx';

/** 처리 흐름 띠(AD-02 AiSettingModule.flow 꼴). */
export function flowSlot(words: (typeof DATAVERIFY_SETTING_TEXT)['flow']) {
  return function flow(p: Omit<DataverifyFlowBandProps, 'words'>): ReactNode {
    return createElement(DataverifyFlowBand, { ...p, words });
  };
}
