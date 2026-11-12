// 파트 진행 카드(밴드 TRW0b, 시안 TR-03 1번 카드·줄인 꼴). 모양 부품: props 만 받는다(서버 단계 낱말과 잇는 것은 어댑터 — TRW1).
// - 큰 꼴: 「진행 · n / 3단계 · 번역 x / y쪽」 머리 + 단계 셋 줄(준비 · 번역·검수·자동 수정 · Word 만들기, data-state) + 주의 줄.
//   단계 줄은 그린워싱 상태 화면의 StageRow(pages/greenwash-status) 꼴을 따라 지었다 — 가져오지 않는다(pages 끼리 막힘).
// - 줄인 꼴(compact): 다른 탭의 진행 — 머리 한 줄 + 단계 이름 셋 + 「준비 중 · …」. 대기는 배지 + 한 줄만(TRP3 ② TC16).
// - 머리(밴드 TRP2 TC14, 시안 TR-03): meta caption-03 · 「진행」 h3 heading-02 | 오른쪽 「n / 3단계」 700 24/1.3 · 아래 「번역 x / y쪽」 caption-03.
//   그 아래 진행 막대(TE10 — role=progressbar, 값은 model stageProgress, 채움 폭은 style width 라 뒤에 움직임을 얹기 쉽다).
// - bare: Card 없이 div 로(부르는 쪽이 탭 줄과 함께 한 카드로 감쌀 때 — TE10 한 카드).
// - 굴림(밴드 TRP5, 6c TRP4 재대조 ①②): 「n / 3단계」는 굴리지 않고 값 그대로. 「번역 x / y쪽」은 그 파트(seenKey)의 쪽 수를 처음 보일 때만 0 에서 굴리고,
//   파트 탭을 오가 다시 붙으면 첫 그림부터 지금 값 — 이미 보인 열쇠는 모듈 안 SEEN 에 기억한다(새로 고침이면 비어 다시 0 에서). 폴링으로 바뀌면 앞 값에서 굴림.
// - pdf(밴드 TRW6 ④): PDF 흐름 파트의 준비 단계 진행 중 글만 「PDF 읽는 중 · …」(큰 꼴·줄인 꼴). 단계 수·이름·진행 셈은 워드와 같다.
import { useEffect, useState } from 'react';

import { CheckIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { Card } from '../../../shared/ui/card/index.ts';
import { useCountUp } from '../../../shared/ui/motion/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { TR_TEXT } from '../config/text.ts';
import { stageProgress } from '../model/index.ts';
import { StatusBadge } from './PartStatusText.tsx';

const words = TR_TEXT.stage;

export type StageState = 'done' | 'now' | 'todo' | 'failed';
const STAGES = ['prepare', 'translate', 'word'] as const;
type Stage = (typeof STAGES)[number];

export interface StageCardProps {
  /** 지금 단계(1 준비 · 2 번역·검수·자동 수정 · 3 Word 만들기). */
  stageIndex: 1 | 2 | 3;
  /** 단계 셋의 상태(차례대로). */
  stages: readonly [StageState, StageState, StageState];
  /** 쪽 진행(번역 단계). 없으면 쪽 글을 그리지 않는다. */
  pages?: { done: number; total: number };
  /** 머리 한 줄(「스토리 4~41쪽(38쪽) · 스타일 B · 11:48 시작」 — 부르는 쪽이 짓는다). */
  meta: string;
  compact?: boolean;
  /** 줄인 꼴의 대기 글(TR_TEXT.stage.queued). 있으면 대기 꼴. */
  queuedText?: string;
  /** 주의 줄. 큰 꼴에만(번역 진행 화면은 쓰지 않는다 — 안심 줄 지움, 밴드 WT1 · sid:MARC-ENT-625). */
  caution?: string;
  /** 참이면 Card 없이 div 로 그린다(부르는 쪽이 카드로 감쌈). */
  bare?: boolean;
  /** 쪽 수를 이미 보였는지 기억하는 열쇠(묶음 id + 파트). 없으면 늘 처음 붙음(0 에서 굴림). */
  seenKey?: string;
  /** PDF 흐름 파트(준비 진행 중 글만 바뀜 — 워드 파트는 넘기지 않는다). */
  pdf?: boolean;
}

/** 쪽 수를 이미 보인 열쇠(seenKey). 다시 붙을 때 굴리지 않는다. */
const SEEN = new Set<string>();

/** 전체 단계 진행 막대(높이 8 · 모서리 full · 바탕 tertiary · 채움 orange). */
function ProgressBar({ value }: { value: number }) {
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      aria-label={words.progressLabel}
      className="h-2 overflow-hidden rounded-full bg-background-tertiary"
    >
      <div
        data-testid="stage-progress-fill"
        className="gw-m-flow gw-m-width h-full rounded-full bg-support-orange"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

/** 단계 점의 꼴. */
const DOT_LOOK: Record<StageState, string> = {
  done: 'bg-support-green-dark text-text-primary-inverse',
  now: 'bg-button-orange text-text-primary-inverse',
  todo: 'bg-background-tertiary text-text-quaternary',
  failed: 'bg-support-error text-text-primary-inverse',
};
/** 단계 오른쪽 상태 글의 꼴. */
const STATE_LOOK: Record<StageState, string> = {
  done: 'text-text-tertiary',
  now: 'text-support-orange-dark',
  todo: 'text-text-quaternary',
  failed: 'text-support-error',
};

function stageBody(
  stage: Stage,
  state: StageState,
  pages: StageCardProps['pages'],
  prepareNow: string,
): string {
  if (stage === 'prepare')
    return state === 'now' ? prepareNow : words.body.prepare;
  if (stage === 'translate')
    return pages ?
        `${words.body.translate} · ${words.body.translatePages(pages.done, pages.total)}`
      : words.body.translate;
  return words.body.word;
}

export function StageCard({
  stageIndex,
  stages,
  pages,
  meta,
  compact = false,
  queuedText,
  caution,
  bare = false,
  seenKey,
  pdf = false,
}: StageCardProps) {
  const prepareNow = pdf ? words.prepareNowPdf : words.prepareNow;
  const step = words.step(stageIndex, STAGES.length);
  // 머리 「번역 x / y쪽」 글자만 굴린다(밴드 TRP4 ②-2, GA1b 꼴 — 단계 글은 TRP5 에서 걷음). 값의 뜻(aria-valuenow·단계 줄)은 끝 값.
  const done = pages?.done ?? 0;
  const [seen] = useState(() => seenKey !== undefined && SEEN.has(seenKey));
  const shownDone = useCountUp(done, undefined, { from: seen ? done : 0 });
  const showsPages = pages !== undefined && !compact;
  useEffect(() => {
    if (seenKey !== undefined && showsPages) SEEN.add(seenKey);
  }, [seenKey, showsPages]);
  const Frame = bare ? 'div' : Card;
  // 줄인 꼴 · 대기 = 회색 배지 + 400 16 #383C40 한 줄만(밴드 TRP2 TC16 · TRP3 ② — 머리 줄·단계 이름 셋 없음, 시안 TR-03 「차례를 기다릴 때」)
  if (compact && queuedText !== undefined)
    return (
      <Frame data-testid="stage-card" data-compact className="flex flex-col">
        <p
          data-testid="stage-queued"
          className="m-0 flex flex-wrap items-center gap-2 text-style-pre-body-03 text-text-secondary"
        >
          <StatusBadge look="grey">{words.queuedLabel}</StatusBadge>
          {queuedText}
        </p>
      </Frame>
    );
  if (compact)
    return (
      <Frame
        data-testid="stage-card"
        data-compact
        className="flex flex-col gap-2"
      >
        <span className="text-style-pre-body-06 text-text-secondary">
          {`${meta} · ${step}`}
        </span>
        <ol className="m-0 flex list-none flex-wrap gap-3 p-0">
          {STAGES.map((stage, index) => (
            <li
              key={stage}
              data-stage={stage}
              data-state={stages[index]}
              className={cn(
                'text-style-pre-caption-02',
                STATE_LOOK[stages[index]!],
              )}
            >
              {words.names[stage]}
            </li>
          ))}
        </ol>
        {stages[0] === 'now' && (
          <p className="m-0 text-style-pre-body-06 text-text-tertiary">
            {prepareNow}
          </p>
        )}
      </Frame>
    );
  return (
    <Frame data-testid="stage-card" className="flex flex-col gap-4">
      <span className="text-style-pre-caption-03 text-text-tertiary">
        {meta}
      </span>
      <div className="flex items-start justify-between gap-3">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.title}
        </h3>
        <div className="flex flex-col items-end">
          {/* 시안 700 24/1.3 — display-04(700 24/1.4)에 줄 높이만 덮는다 */}
          <span
            data-testid="stage-step"
            className="text-style-pre-display-04 leading-[1.3] tabular-nums text-text-primary"
          >
            {step}
          </span>
          {pages && (
            <span
              data-testid="stage-pages"
              className="text-style-pre-caption-03 tabular-nums text-text-tertiary"
            >
              {words.pages(shownDone, pages.total)}
            </span>
          )}
        </div>
      </div>
      <ProgressBar value={stageProgress(stageIndex, pages)} />
      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {STAGES.map((stage, index) => {
          const state = stages[index]!;
          return (
            <li
              key={stage}
              data-stage={stage}
              data-state={state}
              aria-current={state === 'now' ? 'step' : undefined}
              className={cn(
                'box-border flex items-center gap-4 rounded-component px-4 py-3',
                state === 'now' ? 'bg-background-brand'
                : state === 'failed' ? 'bg-support-error-subtle'
                : 'bg-background-primary',
              )}
            >
              <span
                aria-hidden
                className={cn(
                  'flex size-7 shrink-0 items-center justify-center rounded-full text-style-pre-caption-01 [&_svg]:size-4',
                  DOT_LOOK[state],
                  state === 'now' && 'gw-m-ring',
                )}
              >
                {state === 'done' ?
                  <CheckIcon className="gw-m-pop" />
                : index + 1}
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <b className="text-style-pre-body-04 text-text-primary">
                  {words.names[stage]}
                </b>
                <span className="text-style-pre-body-06 text-text-tertiary">
                  {stageBody(stage, state, pages, prepareNow)}
                </span>
              </div>
              <span
                className={cn(
                  'shrink-0 text-style-pre-caption-02',
                  STATE_LOOK[state],
                )}
              >
                {words.states[state]}
              </span>
            </li>
          );
        })}
      </ol>
      {caution !== undefined && (
        <PageInfo
          data-testid="stage-caution"
          tone="caution"
          icon={<PageInfoIcon />}
        >
          {caution}
        </PageInfo>
      )}
    </Frame>
  );
}
