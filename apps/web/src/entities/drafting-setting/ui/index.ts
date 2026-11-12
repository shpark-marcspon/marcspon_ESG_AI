// 원고작성 AI 설정 판 ui 칸의 공개 표면(밴드 RPA3). app/admin/ai-setting-modules.ts 만 가져온다.
//   flowSlot: 처리 흐름 띠 + 칸 고름 그리기 — 껍데기의 FlowProps 와 구조로 맞춘다(DraftingFlowBand 에 글 표를 붙여 넘김, entities/ai-setting 은 가져오지 않는다).
import { createElement } from 'react';
import type { ReactNode } from 'react';

import type { DRAFTING_SETTING_TEXT } from '../config/text.ts';
import { DraftingFlowBand } from './DraftingFlowBand.tsx';
import type { DraftingFlowBandProps } from './DraftingFlowBand.tsx';

export { DraftingFlowBand } from './DraftingFlowBand.tsx';
export type { DraftingFlowBandProps } from './DraftingFlowBand.tsx';

/** 처리 흐름 띠(AD-02 AiSettingModule.flow 꼴). */
export function flowSlot(words: (typeof DRAFTING_SETTING_TEXT)['flow']) {
  return function flow(p: Omit<DraftingFlowBandProps, 'words'>): ReactNode {
    return createElement(DraftingFlowBand, { ...p, words });
  };
}
