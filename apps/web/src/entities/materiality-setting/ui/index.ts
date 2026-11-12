// 중대성평가 IRO AI 설정 판 ui 칸의 공개 표면(밴드 IRA2). app/admin/ai-setting-modules.ts 만 가져온다.
//   materialityPromptNote: 칸 아래 안내 글(밴드 IRA3 — 모듈 줄 promptNote 가 부르기만).
//   flowSlot: 처리 흐름 띠 + 칸 고름 그리기 — 껍데기의 FlowProps 와 구조로 맞춘다(MaterialityFlowBand 에 글 표를 붙여 넘김, entities/ai-setting 은 가져오지 않는다).
import { createElement } from 'react';
import type { ReactNode } from 'react';

import type { MATERIALITY_SETTING_TEXT } from '../config/text.ts';
import { MaterialityFlowBand } from './MaterialityFlowBand.tsx';
import type { MaterialityFlowBandProps } from './MaterialityFlowBand.tsx';

export { MaterialityFlowBand } from './MaterialityFlowBand.tsx';
export { INPUT_PREFIXES, materialityPromptNote } from './promptNote.ts';
export type { MaterialityFlowBandProps } from './MaterialityFlowBand.tsx';

/** 처리 흐름 띠(AD-02 AiSettingModule.flow 꼴). */
export function flowSlot(words: (typeof MATERIALITY_SETTING_TEXT)['flow']) {
  return function flow(p: Omit<MaterialityFlowBandProps, 'words'>): ReactNode {
    return createElement(MaterialityFlowBand, { ...p, words });
  };
}
