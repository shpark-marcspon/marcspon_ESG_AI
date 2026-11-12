// 점검 단계 띠: STEP 1~3(파일·쪽 지정 / 문장 찾기·판정 / 결과 정리·검토). 몸은 shared/ui/step-flow — TRW0a ①, 그린워싱 글만 넣는다.
// 화면마다 지금 단계: GW-02 = 1, GW-03 = 2, GW-04·05 = 3. 단계 이름·목록 이름의 기본은 문구 표(config/text.ts)의 것.
import { StepFlow as SharedStepFlow } from '../../../shared/ui/step-flow/index.ts';
import type { StepFlowProps as SharedStepFlowProps } from '../../../shared/ui/step-flow/index.ts';
import { GW_TEXT } from '../config/text.ts';

export interface StepFlowProps extends Omit<
  SharedStepFlowProps,
  'steps' | 'label'
> {
  /** 단계 이름. 기본은 문구 표의 셋. */
  steps?: readonly string[];
  /** 목록의 이름. 기본 「점검 단계」. */
  label?: string;
}

function StepFlow({
  steps = GW_TEXT.stepFlow.steps,
  label = GW_TEXT.stepFlow.label,
  prefix = GW_TEXT.stepFlow.prefix,
  ...props
}: StepFlowProps) {
  return (
    <SharedStepFlow steps={steps} label={label} prefix={prefix} {...props} />
  );
}
StepFlow.displayName = 'StepFlow';

export { StepFlow };
