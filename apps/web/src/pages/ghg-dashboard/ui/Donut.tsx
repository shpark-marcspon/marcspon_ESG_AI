// Scope 1+2+3 도넛(밴드 DB1 ② — 손 SVG, 차트 라이브러리 0. e6 값 파일 ② 카드 1): 150 · 바탕 고리 굵기 24.75(support-grey-subtle) ·
//   그 안 호 굵기 14 · 12시에서 시계 방향 Scope 1→2→3 · 호 사이 틈 약 2°(추정 — 사진 대조). 읽는 값은 범례가 준다(aria-hidden).
//   밴드 DB3(e6 ② 「도넛 쓸기 꼴」): 호들을 <g mask> 로 감싸고 mask 안 흰 원 하나에 gw-m-sweep(12시에서 시계 방향 — svg 가 -rotate-90).
//   바탕 고리는 mask 밖(처음부터 있음). 끝 상태(dashoffset 0)가 속성 그대로라 움직임을 줄이면 처음부터 다 그려진 도넛. still 이면 클래스·지연 0.
//   밴드 DB4(감독 판단 4): 가운데 합도 굴린다(Rolling — 쓸기 지연 120 에 맞춤). 폭 재기는 끝 글자로(굴리는 동안 끝 글자를 깔아 칸 폭을 잡음).
import { useId, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';

import { donutSweepDelay } from '../../../entities/ghg/model/index.ts';
import { Rolling } from './Rolling.tsx';
import { toneOf } from './tones.ts';

const SIZE = 150;
const BASE_WIDTH = 24.75;
const BASE_RADIUS = (SIZE - BASE_WIDTH) / 2;
const ARC_WIDTH = 14;
const ARC_RADIUS = (SIZE - 10.2 - ARC_WIDTH) / 2;
const ROUND = 2 * Math.PI * ARC_RADIUS;
const GAP = (2 / 360) * ROUND;
/** 가운데 글이 쓸 수 있는 폭(감독 판단 13): 안 지름(150 − 바탕 고리 둘) − 16. */
export const DONUT_TEXT_ROOM = SIZE - 2 * BASE_WIDTH - 16;
/** 가운데 합계 글 크기 차례(DB1 정본 18 Bold → 14 Bold). e6 의 「24→18→14」의 24 는 정본에 없어 18 부터(감독 41 11-08). */
const FIT_STEPS = [
  'text-style-pre-heading-02',
  'text-style-pre-body-04',
] as const;

/** 가운데 합계 글: 그려진 폭이 DONUT_TEXT_ROOM 을 넘으면 한 단계씩 내린다(글은 그대로 — 소수 자리 안 줄임). 글이 바뀌면 18 부터 다시. */
export function DonutAmount({
  text,
  still = false,
}: {
  text: string;
  /** 움직이지 않음(덮개 뒤 판 — 숫자 굴림 0). */
  still?: boolean;
}) {
  const [step, setStep] = useState(0);
  const [seen, setSeen] = useState(text);
  const ref = useRef<HTMLSpanElement>(null);
  if (seen !== text) {
    setSeen(text);
    setStep(0);
  }
  useLayoutEffect(() => {
    const measure = () => {
      const width = ref.current?.getBoundingClientRect().width ?? 0;
      if (width > DONUT_TEXT_ROOM && step < FIT_STEPS.length - 1)
        setStep(step + 1);
    };
    measure();
    // 웹 글꼴이 늦게 오면 폭이 바뀐다 — 다시 잼.
    let live = true;
    void document.fonts?.ready.then(() => live && measure());
    return () => {
      live = false;
    };
  }, [step, text]);
  return (
    <span
      ref={ref}
      data-testid="dashboard-donut-total"
      data-step={step}
      className={`whitespace-nowrap ${FIT_STEPS[step]} text-text-primary tabular-nums`}
    >
      <Rolling
        text={text}
        delay={donutSweepDelay()}
        still={still}
        align="center"
      />
    </span>
  );
}

export function Donut({
  shares,
  center,
  still = false,
}: {
  /** 0~1 몫(Scope 차례). */
  shares: readonly number[];
  center: ReactNode;
  /** 움직이지 않음(미설정 덮개 뒤 판). */
  still?: boolean;
}) {
  // 같은 화면을 두 번 그려도 mask id 가 겹치지 않게(React 18 useId 의 「:」는 url(#…) 에서 뺀다).
  const mask = `donut-sweep-${useId().replace(/:/g, '')}`;
  const shown = shares.filter((share) => share > 0).length;
  let start = 0;
  return (
    <div className="relative size-[150px] shrink-0">
      <svg
        aria-hidden
        data-testid="dashboard-donut"
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="size-full -rotate-90"
      >
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={BASE_RADIUS}
          fill="none"
          strokeWidth={BASE_WIDTH}
          className="stroke-current text-support-grey-subtle"
        />
        <mask
          id={mask}
          maskUnits="userSpaceOnUse"
          x={0}
          y={0}
          width={SIZE}
          height={SIZE}
        >
          <circle
            data-sweep
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={ARC_RADIUS}
            fill="none"
            stroke="white"
            strokeWidth={ARC_WIDTH + 2}
            strokeDasharray={ROUND}
            className={still ? undefined : 'gw-m-sweep'}
            style={
              still ? undefined : (
                ({
                  '--gw-m-round': ROUND,
                  '--gw-m-delay': `${donutSweepDelay()}ms`,
                } as CSSProperties)
              )
            }
          />
        </mask>
        <g mask={`url(#${mask})`}>
          {shares.map((share, index) => {
            const whole = share * ROUND;
            const offset = start;
            start += whole;
            const length = shown > 1 ? Math.max(whole - GAP, 0) : whole;
            return length <= 0 ? null : (
                <circle
                  key={index}
                  data-slice={index}
                  cx={SIZE / 2}
                  cy={SIZE / 2}
                  r={ARC_RADIUS}
                  fill="none"
                  strokeWidth={ARC_WIDTH}
                  strokeDasharray={`${length} ${ROUND - length}`}
                  strokeDashoffset={-offset}
                  className={`stroke-current ${toneOf(index)}`}
                />
              );
          })}
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {center}
      </div>
    </div>
  );
}
