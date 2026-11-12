// 단계 띠(밴드 FW1 ① 의 그린워싱 점검 단계 띠를 TRW0a ① 에서 shared 로 올림 — 그린워싱·영문번역이 쓴다). 시안 GW-02_r1 의 g-flow 꼴.
//
// 순서 있는 목록(ol)이고 지금 단계에 aria-current="step". 단계 사이 화살표는 꾸밈이라 aria-hidden.
// 단계 칸: 높이 36, 좌우 14, 모서리 8, 흰 바탕 + text-quaternary 글자(pre-body-06), 「STEP n」은 굵게, 사이 세로 막대.
//   지금 단계는 주황 바탕(button-orange = orange.500) + 흰 글자.
// 단계 이름(steps)과 목록 이름(label)은 업무 글이라 쓰는 쪽이 꼭 넘긴다. 번호 앞 글자만 기본이 PARTS_TEXT.stepFlow.prefix.
import { ChevronRightIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { PARTS_TEXT } from '../../text.ts';

export interface StepFlowProps {
  /** 지금 단계(1부터). 범위 밖이면 고른 단계 없음. */
  current: number;
  /** 단계 이름(업무 글 — 쓰는 쪽이 준다). */
  steps: readonly string[];
  /** 목록의 이름(업무 글 — 쓰는 쪽이 준다). */
  label: string;
  /** 단계 번호 앞 글자. 기본 「STEP」. */
  prefix?: string;
  className?: string;
}

function StepFlow({
  current,
  steps,
  label,
  prefix = PARTS_TEXT.stepFlow.prefix,
  className,
}: StepFlowProps) {
  return (
    <ol
      aria-label={label}
      className={cn(
        'm-0 flex list-none flex-wrap items-center gap-2 p-0',
        className,
      )}
    >
      {steps.map((name, index) => {
        const number = index + 1;
        const on = number === current;
        return (
          // 단계 이름이 겹쳐도 되게 차례를 key 로 쓴다(목록은 늘 통째로 바뀐다).
          <li key={index} className="flex items-center gap-2">
            <span
              aria-current={on ? 'step' : undefined}
              className={cn(
                'box-border inline-flex h-9 items-center gap-2 whitespace-nowrap rounded-component px-3.5 text-style-pre-body-06',
                on ?
                  'bg-button-orange text-text-primary-inverse'
                : 'bg-background-primary text-text-quaternary',
              )}
            >
              <b className="font-bold">
                {prefix} {number}
              </b>
              <i aria-hidden className="h-3 w-px bg-current opacity-50" />
              <span>{name}</span>
            </span>
            {index < steps.length - 1 && (
              <ChevronRightIcon
                aria-hidden
                className="size-4 shrink-0 text-text-quaternary"
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
StepFlow.displayName = 'StepFlow';

export { StepFlow };
