// Scope 카드 3개년 막대 칸(밴드 DB2 ② — sid:MARC-ENT-598). 값·꼴: band-handoffs/DB2-figma-values.md(e6) ①·③·④ — Figma 28952:20528.
//   칸 셋은 늘 둔다(왼쪽부터 고른 해 −2 · −1 · 고른 해). 없음·아직 안 옴 = 막대·말풍선 0, 연도 글만, 초점 안 받음. 0 = 높이 0 + 말풍선 「0」.
//   고른 해 막대는 진하게 · 앞 두 해 opacity-40. 말풍선은 세 해 모두 올리거나 초점이 갈 때만 뜬다(밴드 DB4 — 사용자 11-08 「호버 하면 나오면」 ·
//   고른 해 늘 뜸과 그 자리 재기(DB3 trendTipFits·RC1 ResizeObserver)는 걷었다). 화면 읽기는 막대의 aria-label 이 늘 값을 준다.
//   말풍선 자리: 앞 해는 막대 오른쪽, 고른 해는 막대 왼쪽 · 위끝은 막대 꼭대기(그림 안으로 누름 — model trendTipTop). 겹치면 올린 쪽이 위(z 차례).
//   밴드 DB3(넘김 R1 → e6 정함 1 · 감독 판단 8): 눈금 글 칸 = 가장 긴 눈금 글 + 4(오른쪽 맞춤, 늘 비워 둠). 선과 막대는 그 오른쪽 —
//   남은 폭을 셋으로 나눈 칸 가운데에 막대 칸(폭 21).
//   움직임(e6 ②, still 이면 0): 막대 gw-m-grow-y(칸 차례 지연) · 말풍선 gw-m-fade 220ms 지연 없음(DB4 감독 판단 3).
//   셈(눈금·높이·자리·지연)은 model(trendOf·trendTipTop·trendBarDelay) — 이 파일은 그리기만.
import { useState } from 'react';
import type { CSSProperties } from 'react';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  TREND_HEIGHT,
  trendBarDelay,
  trendTipTop,
} from '../../../entities/ghg/model/index.ts';
import type { Trend } from '../../../entities/ghg/model/index.ts';
import { toneOf, washOf } from './tones.ts';

const words = GHG_TEXT.dashboard;
/** 눈금 선 다섯(한 칸 40 — e6 ①). */
const LINES = [0, 1, 2, 3, 4] as const;

export interface TrendBarsProps {
  trend: Trend;
  /** 0·1·2 = Scope 1·2·3(색). */
  index: number;
  /** 고른 해(오른쪽 끝 — 강조·말풍선은 막대 왼쪽). */
  year: number;
  /** 값 글자 → 표기(단위 없이 — 화면의 amount). */
  format(value: string): string;
  unit: string;
  testId: string;
  /** 움직이지 않음(미설정 덮개 뒤 판 — e6 ③). 끄면 움직임 클래스·지연 style 0. */
  still?: boolean;
}

export function TrendBars({
  trend,
  index,
  year,
  format,
  unit,
  testId,
  still = false,
}: TrendBarsProps) {
  const [active, setActive] = useState<number | null>(null);
  const longest = trend.ticks.reduce((long, tick) =>
    tick.length > long.length ? tick : long,
  );
  return (
    <div
      data-testid={testId}
      className={`flex w-full flex-col gap-4 rounded-component px-4 py-8 ${washOf(index)}`}
    >
      {/* 눈금 글 칸(글 + 4) | 그림(선 161 + 연도 줄 — 사이 6 + 글 17) — 막대 묶음은 그림 칸을 셋으로 나눈다 */}
      <div className="flex">
        <ol
          aria-hidden
          className="relative m-0 h-[161px] w-max list-none p-0 pr-1 text-right text-style-pre-caption-04 text-text-quaternary"
        >
          {trend.ticks.map((tick, at) => (
            <li
              key={at}
              data-testid={`${testId}-tick`}
              className="absolute right-1 -translate-y-1/2 whitespace-nowrap tabular-nums"
              style={{ top: at * 40 + 0.5 }}
            >
              {tick}
            </li>
          ))}
          {/* 폭을 잡는 보이지 않는 글(가장 긴 눈금 글) */}
          <li className="invisible whitespace-nowrap tabular-nums">
            {longest}
          </li>
        </ol>
        <div className="relative h-[184px] min-w-0 flex-1">
          {LINES.map((line) => (
            <span
              key={line}
              aria-hidden
              className={`absolute inset-x-0 h-px ${line === 4 ? 'bg-background-tertiary' : 'bg-background-secondary'}`}
              style={{ top: line * 40 }}
            />
          ))}
          <div className="absolute inset-0 grid grid-cols-3">
            {trend.bars.map((bar, column) => {
              const chosen = bar.year === year;
              const drawn = bar.kind === 'value';
              // 세 해 모두 올림·초점 때만(밴드 DB4).
              const tip = drawn && active === bar.year;
              return (
                <div key={bar.year} className="flex justify-center">
                  <div
                    data-testid={`${testId}-bar-${bar.year}`}
                    data-kind={bar.kind}
                    {...(drawn ?
                      {
                        role: 'img',
                        tabIndex: 0,
                        'aria-label': words.barLabel(
                          bar.year,
                          format(bar.value),
                          unit,
                        ),
                        onMouseEnter: () => setActive(bar.year),
                        onMouseLeave: () => setActive(null),
                        onFocus: () => setActive(bar.year),
                        onBlur: () => setActive(null),
                      }
                    : {})}
                    className="flex w-[21px] flex-col items-center rounded-[2px] outline-offset-2"
                  >
                    <div
                      className="relative w-2.5"
                      style={{ height: TREND_HEIGHT }}
                    >
                      {drawn && (
                        <span
                          data-bar
                          className={`absolute inset-x-0 bottom-0 rounded-[2px] bg-current ${toneOf(index)} ${chosen ? '' : 'opacity-40'} ${still ? '' : 'gw-m-grow-y'}`}
                          style={{
                            height: bar.height,
                            ...(still ?
                              {}
                            : ({
                                '--gw-m-delay': `${trendBarDelay(column)}ms`,
                              } as CSSProperties)),
                          }}
                        />
                      )}
                      {tip && (
                        <span
                          data-testid={`${testId}-tip-${bar.year}`}
                          className={`absolute flex max-w-[100px] flex-col whitespace-nowrap rounded-control bg-background-primary p-1.5 drop-shadow-[0_0_5px_rgba(0,0,0,0.12)] ${chosen ? 'right-[29px] z-10' : 'left-[29px] z-20'} ${still ? '' : 'gw-m-fade'}`}
                          style={{ top: trendTipTop(bar.height) }}
                        >
                          <span className="text-style-pre-caption-04 text-text-tertiary">
                            {words.yearOption(bar.year)}
                          </span>
                          <span className="truncate text-style-pre-body-04 text-text-secondary tabular-nums">
                            {format(bar.value)}
                          </span>
                        </span>
                      )}
                    </div>
                    <span className="mt-[7px] text-style-pre-caption-02 text-text-tertiary tabular-nums">
                      {words.yearOption(bar.year)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <p className="m-0 text-right text-style-pre-caption-02 text-text-quaternary">
        {words.unitNote(unit)}
      </p>
    </div>
  );
}
