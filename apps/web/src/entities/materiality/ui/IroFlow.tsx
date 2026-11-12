// 중대성평가 STEP 띠(밴드 IRW1 ② — 시안 g-flow 는 이미 shared StepFlow, 발주서 Q8 (가)). 글 셋은 IR_TEXT.flow 한 곳.
//   IR-00·02 = 1(IRW2 가 받아 쓴다) · IR-03 = 2 · IR-04 = 3. 새 글 0.
import { StepFlow } from '../../../shared/ui/step-flow/index.ts';
import { IR_TEXT } from '../config/text.ts';

export interface IroFlowProps {
  /** 지금 STEP(1·2·3). */
  current: 1 | 2 | 3;
  className?: string;
}

export function IroFlow({ current, className }: IroFlowProps) {
  return (
    <StepFlow
      current={current}
      steps={IR_TEXT.flow.items.map((item) => item.label)}
      label={IR_TEXT.flow.label}
      className={className}
    />
  );
}
