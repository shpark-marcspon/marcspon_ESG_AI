// S2 배출량 현황 카드(밴드 W12-1a ③ — 발주서 2-3·Q11, 시안 28535:7000). 접는 머리 · 「Scope 1+2」 · 손 SVG 고리(차트 라이브러리 0) ·
//   가운데 합 · 범례(Scope 마다 값). 합·몫은 model cardOf 한 곳 — 이 파일은 셈하지 않는다(글자 그대로, 표시 반올림만 formatAmount).
//   카드는 q 없는 마지막 응답의 scopes 로 그린다(검색은 표만 바꾼다 — 부르는 쪽이 base 를 넘김).
//   밴드 DB4(sid:MARC-TICK-543 — 발주서 §2-②·③ · 감독 판단 2·3): 고리는 대시보드 도넛(pages/ghg-dashboard/ui/Donut.tsx)과 같은 쓸기 —
//   호들을 <g mask> 로 감싸고 mask 안 흰 원 하나에 gw-m-sweep(700ms · 120ms 뒤 · 12시에서 시계 방향 — svg 가 -rotate-90). 바탕 고리는 mask 밖.
//   가운데 합은 같은 지연으로 굴린다(RollingText — 셈은 model roll*, 때는 hooks useRoll). 단위·「총배출량」은 그대로.
//   밴드 DB5(sid:MARC-TICK-544 — 발주서 §2-①): 범례 값 칸도 가운데 합과 같은 지연(120)·길이(700)·때(moving)로 굴린다. Scope 이름·단위는 그대로.
//   언제: 그 해 카드의 첫 그림·연도 바꿈만(몸 key={year}). 검색은 base 가 그대로라, 같은 해 다시 읽기(고침·저장)는 같은 노드라 안 움직인다.
//   접고 펴면 몸이 다시 붙지만 움직이지 않는다(moving — 그 해 첫 그림이 이미 지남 · 감독 판단 2: 접힌 채 해가 바뀌어도 펼 때 안 움직임).
import { useId, useState } from 'react';
import type { CSSProperties } from 'react';

import {
  ChevronDownIcon,
  ChevronUpIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { useRoll } from '../../../entities/ghg/hooks/index.ts';
import {
  cardOf,
  donutSweepDelay,
  formatAmount,
} from '../../../entities/ghg/model/index.ts';
import type { EntryRows } from '../../../entities/ghg/model/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
// 움직임 클래스(gw-m-sweep)만 쓴다 — CSS 는 이 표면이 싣는다(shared/ui/motion/index.ts 머리, 밴드 RPW5 #7).
import '../../../shared/ui/motion/index.ts';

const words = GHG_TEXT.inventory.card;

/** 고리 색(배출범위 차례 — 시안: 첫째 초록 · 둘째 하늘). 셋째부터는 회색. 둘째는 판 `.sw-b` = support-blue-subtle-2(#85BEFF, GX2 S12-02). */
export const TONES = [
  'text-support-success',
  'text-support-blue-subtle2',
] as const;
const RADIUS = 52;
const ROUND = 2 * Math.PI * RADIUS;

/**
 * J4(밴드 W12-1c #21): 고리 가운데 합계 글이 쓸 수 있는 폭은 약 117px(검토 셈). 1280 Chromium 실측(W12-1c C0 ★J):
 * heading-02(18/700) 10자 109.4 · 11자 121.0 / body-01(16/700) 11자 107.5 · 12자 117.8. 글자 수로 정한다(jsdom 은 폭을 못 잰다).
 */
export const TOTAL_FIT = { heading: 10, body: 11 } as const;

/** 합계 글 꼴 — ≤10자 heading-02 · 11자 body-01 · 12자 이상 body-01 + 줄임표(폭 117). */
export function totalClass(text: string): string {
  if (text.length <= TOTAL_FIT.heading)
    return 'text-style-pre-heading-02 tabular-nums';
  if (text.length <= TOTAL_FIT.body)
    return 'text-style-pre-body-01 tabular-nums';
  return 'block max-w-[117px] truncate text-style-pre-body-01 tabular-nums';
}

/**
 * 숫자 칸 굴림(밴드 DB4 — 대시보드 Rolling 과 같은 꼴, pages 끼리는 가져오지 않아 여기 둔다). 굴리는 동안 끝 글자를 깔아 칸 폭을 잡고
 * 프레임은 aria-hidden, 화면 읽기는 sr-only 끝 글자(바깥 칸의 aria-label 은 그대로). 다 굴면 끝 글자 하나만.
 * 밴드 DB5(sid:MARC-TICK-544 — 발주서 §2-① · 감독 판단 1): 가운데 합(가운데 맞춤)과 범례 값(오른쪽 맞춤 — 끝 글자의 끝자리에 맞춤)이 같은 칸·같은 지연·같은 때.
 */
function RollingText({
  text,
  moving,
  align,
}: {
  text: string;
  moving: boolean;
  align: 'center' | 'end';
}) {
  const frame = useRoll(text, { delay: donutSweepDelay(), enabled: moving });
  if (frame === null) return <>{text}</>;
  const side = align === 'end' ? 'text-right' : 'text-center';
  return (
    <span data-rolling="" className="inline-grid">
      <span aria-hidden className="invisible [grid-area:1/1]">
        {text}
      </span>
      <span aria-hidden className={`${side} [grid-area:1/1]`}>
        {frame}
      </span>
      <span className="sr-only">{text}</span>
    </span>
  );
}

export function EmissionCard({ rows }: { rows: EntryRows }) {
  const [open, setOpen] = useState(true);
  // 지금 몸이 그 해 첫 그림인가(움직여도 되나). 해가 바뀌면 그때 펼쳐 있을 때만 다시 참 · 접거나 펴면 거짓(감독 판단 2).
  const [seenYear, setSeenYear] = useState(rows.year);
  const [moving, setMoving] = useState(true);
  if (seenYear !== rows.year) {
    setSeenYear(rows.year);
    setMoving(open);
  }
  const mask = `ring-sweep-${useId().replace(/:/g, '')}`;
  const card = cardOf(rows.scopes, rows.year);
  const shown = (value: string | null) => formatAmount(value, rows.decimals);
  const totalText = shown(card.total);
  let start = 0;
  return (
    <Card data-testid="emission-card" className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="m-0 text-style-pre-heading-02">{words.title}</h3>
        <button
          type="button"
          aria-expanded={open}
          aria-label={open ? words.collapse : words.expand}
          className="flex size-8 items-center justify-center rounded-md text-text-secondary hover:bg-background-secondary focus-visible:outline-2 [&_svg]:size-5"
          onClick={() => {
            setOpen((now) => !now);
            setMoving(false);
          }}
        >
          {open ?
            <ChevronUpIcon aria-hidden />
          : <ChevronDownIcon aria-hidden />}
        </button>
      </div>
      {open && (
        <div key={rows.year} className="flex flex-wrap items-center gap-8">
          <div className="flex flex-col gap-2">
            <p className="m-0 text-style-pre-body-05">{words.ringTitle}</p>
            <div className="relative size-[180px]">
              <svg
                role="img"
                aria-label={words.ringLabel(
                  card.scopes.map(
                    (scope) =>
                      `${scope.scopeName} ${shown(scope.value)} ${rows.unit}`,
                  ),
                )}
                data-testid="emission-ring"
                viewBox="0 0 120 120"
                className="size-full -rotate-90"
              >
                <circle
                  cx="60"
                  cy="60"
                  r={RADIUS}
                  fill="none"
                  strokeWidth="12"
                  className="stroke-current text-background-secondary"
                />
                <mask
                  id={mask}
                  maskUnits="userSpaceOnUse"
                  x={0}
                  y={0}
                  width={120}
                  height={120}
                >
                  <circle
                    data-sweep
                    cx="60"
                    cy="60"
                    r={RADIUS}
                    fill="none"
                    stroke="white"
                    strokeWidth={14}
                    strokeDasharray={ROUND}
                    className={moving ? 'gw-m-sweep' : undefined}
                    style={
                      moving ?
                        ({
                          '--gw-m-round': ROUND,
                          '--gw-m-delay': `${donutSweepDelay()}ms`,
                        } as CSSProperties)
                      : undefined
                    }
                  />
                </mask>
                <g mask={`url(#${mask})`}>
                  {card.scopes.map((scope, index) => {
                    const length = scope.share * ROUND;
                    const offset = start;
                    start += length;
                    return length <= 0 ? null : (
                        <circle
                          key={scope.scopeId}
                          data-scope={scope.scopeId}
                          cx="60"
                          cy="60"
                          r={RADIUS}
                          fill="none"
                          strokeWidth="12"
                          strokeDasharray={`${length} ${ROUND - length}`}
                          strokeDashoffset={-offset}
                          className={`stroke-current ${TONES[index] ?? 'text-text-tertiary'}`}
                        />
                      );
                  })}
                </g>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span
                  data-testid="emission-total"
                  aria-label={totalText}
                  className={totalClass(totalText)}
                >
                  {/* 줄임표 꼴(12자 이상 — totalClass)은 굴리지 않는다: 깔개 칸이 넘쳐 줄임표 대신 잘려 보인다. */}
                  <RollingText
                    text={totalText}
                    moving={moving && totalText.length <= TOTAL_FIT.body}
                    align="center"
                  />
                </span>
                <span
                  data-testid="emission-total-unit"
                  className="text-style-pre-heading-02"
                >
                  {rows.unit}
                </span>
                <span
                  data-testid="emission-total-label"
                  className="text-style-pre-body-05 text-text-tertiary"
                >
                  {words.total}
                </span>
              </div>
            </div>
          </div>
          <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
            {card.scopes.map((scope, index) => (
              <li
                key={scope.scopeId}
                data-testid={`emission-${scope.scopeId}`}
                className="flex items-center gap-2"
              >
                <span
                  aria-hidden
                  className={`size-2 rounded-full bg-current ${TONES[index] ?? 'text-text-tertiary'}`}
                />
                <span className="w-[84px] text-style-pre-body-05 text-text-secondary">
                  {scope.scopeName}
                </span>
                <span
                  data-testid={`emission-${scope.scopeId}-value`}
                  className="text-style-pre-body-01 text-text-primary tabular-nums"
                >
                  <RollingText
                    text={shown(scope.value)}
                    moving={moving}
                    align="end"
                  />
                </span>
                <span className="text-style-pre-body-05 text-text-tertiary">
                  {rows.unit}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
