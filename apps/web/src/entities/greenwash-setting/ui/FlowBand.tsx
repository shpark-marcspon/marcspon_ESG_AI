// AD-02 그린워싱 탭의 처리 흐름 띠(밴드 AS3b ② — 디자인 사본 AD-02_r3 「처리 흐름」, 셋째 열을 갈음). 프롬프트 상세 카드 위에 그린다.
//   고정 마디(사용자 지정 → … → 결과)와 갈래 선은 인라인 SVG(1064×296 — 좁으면 가로 밀기), 번호 마디 넷은 그 위의 단추(누르면 그 칸 — onPick).
//   마디 이름은 서버 label(웹 상수에 이름 0 — key 로 찾음), 번호 = 묶음 안 칸 차례(저장 창 「2. … 프롬프트」와 같은 번호, e9 답 10-23).
//   고른 마디 회색 바탕 + grey-800 2px 테두리 · aria-pressed · 고친 칸 「● 고침」 · 서버가 짚은 칸 「고칠 곳 있음」(셋째 열 slot-refused 와 같은 표시).
//   응답에 없는 key 의 마디는 누를 수 없다. 공통 부품화는 플랫폼-웹 몫(이 밴드는 그린워싱 ui 안).
// 시안 값 맞춤(밴드 GP2 — GW3R-AD02 대조 (c) C1~C10, 시안이 정본): 마디 radius 8·안쪽 12·사이 4·높이 112·고른 마디 2px grey-800,
//   마디 이름 700 14·번호와 8, 번호 동그라미 24·700 12, 빈도 알약(background-secondary·full·0 8px·500 12 text-secondary),
//   「고침」은 이름 줄 오른쪽 끝 500 12 orange-dark, 고정 상자 테두리 없음·500 12 text-tertiary, 끝 상자 grey-800 바탕·흰 700 14(+ 400 12),
//   흐름 선 이름 500 12(시안 11px 는 토큰 12 로 — 「일반적이면」이 마디 사이 44 에 안 들어가 3번 마디부터 오른쪽을 36 밀었다), 제목은 카드 안 소제목 꼴 700 14, 카드 안 사이 24.
//   시안과 다르게 둔 것: 마디 이름 줄 높이는 토큰(1.6 — 700 14/1.4 토큰 없음). 처리 흐름을 프롬프트 카드 안에 넣는 자리·프롬프트 카드 사이는 플랫폼-웹 땅(AiSettingsScreen).
//   밴드 PF1: inline 이면 겉 카드 꼴 0 · 제목은 h4 소제목(시안 .a-sub — 700 14 + note 400 tertiary 왼쪽 6). 띠는 그대로.
import type { CSSProperties } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import type { GREENWASH_SETTING_TEXT } from '../config/text.ts';
import { flowNodes } from '../model/index.ts';
import type { FlowKey } from '../model/index.ts';

type At = { group: number; prompt: number };

export interface FlowBandProps {
  groups: readonly {
    key: string;
    prompts: readonly { key: string; label: string }[];
  }[];
  picked: At;
  edited: readonly At[];
  refused: readonly At[];
  onPick(at: At): void;
  words: (typeof GREENWASH_SETTING_TEXT)['flow'];
  /** 프롬프트 카드 안 소제목 꼴(밴드 PF1 — 겉 카드 0 · h4). 기본은 따로 카드. */
  inline?: boolean;
}

const WIDTH = 1064;
const HEIGHT = 296;
/** 번호 마디 자리(그림 좌표). */
const BOX: Record<FlowKey, { x: number; y: number }> = {
  detect: { x: 136, y: 88 },
  eval: { x: 632, y: 4 },
  repair: { x: 872, y: 4 },
  low_only: { x: 632, y: 172 },
};
const NODE_W = 160;
const NODE_H = 112;

const same = (a: At, b: At) => a.group === b.group && a.prompt === b.prompt;
const place = ({ x, y }: { x: number; y: number }): CSSProperties => ({
  left: x,
  top: y,
  width: NODE_W,
  height: NODE_H,
});

/** 고정 마디(여러 줄 글 상자). */
function Fixed({
  x,
  y,
  w,
  h,
  lines,
  end = false,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  lines: readonly string[];
  /** 끝 상자(결과 검토 화면): grey-800 바탕, 첫 줄 흰 700 14 · 나머지 흰 400 12(C7). */
  end?: boolean;
}) {
  const top = y + h / 2 - ((lines.length - 1) * 18) / 2 + 4;
  return (
    <g data-flow-fixed={end ? 'end' : ''}>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={8}
        className={end ? 'fill-grey-800' : 'fill-background-secondary'}
      />
      {lines.map((line, index) => (
        <text
          key={line}
          x={x + w / 2}
          y={top + index * 18}
          textAnchor="middle"
          className={
            !end ? 'fill-text-tertiary text-style-pre-caption-02'
            : index === 0 ?
              'fill-background-primary text-style-pre-body-04'
            : 'fill-background-primary text-style-pre-caption-03'
          }
        >
          {line}
        </text>
      ))}
    </g>
  );
}

export function FlowBand({
  groups,
  picked,
  edited,
  refused,
  onPick,
  words,
  inline = false,
}: FlowBandProps) {
  const nodes = flowNodes(groups);
  const line = 'fill-none stroke-border-secondary';
  const dashed = cn(line, '[stroke-dasharray:4_4]');
  const caption = 'fill-text-tertiary text-style-pre-caption-02';
  return (
    <section
      data-testid="flow-band"
      aria-label={words.title}
      className={cn(
        'box-border flex min-w-0 flex-col gap-6',
        !inline && 'rounded-dialog bg-background-primary p-8',
      )}
    >
      {inline ?
        <h4 className="m-0 text-style-pre-body-04 text-text-primary">
          {words.title}
          <small className="ml-1.5 text-style-pre-caption-03 text-text-tertiary">
            {words.note}
          </small>
        </h4>
      : <div className="flex flex-wrap items-baseline gap-3">
          <h3 className="m-0 text-style-pre-body-04 text-text-primary">
            {words.title}
          </h3>
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.note}
          </span>
        </div>
      }
      <div className="overflow-x-auto">
        <div className="relative" style={{ width: WIDTH, height: HEIGHT }}>
          <svg
            aria-hidden
            width={WIDTH}
            height={HEIGHT}
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="absolute inset-0"
          >
            <Fixed x={8} y={112} w={104} h={64} lines={words.start} />
            <path d="M112 144 H136" className={line} />
            <path d="M296 144 H316" className={line} />
            <Fixed x={316} y={100} w={160} h={88} lines={words.merge} />
            <path d="M476 144 H504" className={line} />
            <polygon
              points="548,100 592,144 548,188 504,144"
              className="fill-background-secondary stroke-border-tertiary"
            />
            {words.decision.map((text, index) => (
              <text
                key={text}
                x={548}
                y={140 + index * 14}
                textAnchor="middle"
                className="fill-text-secondary text-[11px]"
              >
                {text}
              </text>
            ))}
            <text x={548} y={286} textAnchor="middle" className={caption}>
              {words.decisionNote}
            </text>
            <path d="M548 100 V60 H632" className={line} />
            <text x={556} y={84} className={caption}>
              {words.no}
            </text>
            <path d="M548 188 V228 H632" className={line} />
            <text x={556} y={212} className={caption}>
              {words.yes}
            </text>
            <path d="M792 60 H872" className={dashed} />
            <text x={832} y={52} textAnchor="middle" className={caption}>
              {words.generic}
            </text>
            <path d="M712 116 V150 H1004 V200" className={dashed} />
            <text x={858} y={144} textAnchor="middle" className={caption}>
              {words.keep}
            </text>
            <path d="M952 116 V200" className={line} />
            <path d="M792 228 H892" className={line} />
            <Fixed x={892} y={200} w={164} h={64} lines={words.end} end />
          </svg>
          {nodes.map((node) => {
            const at = node.at;
            const step = words.steps[node.key];
            const isEdited = at !== null && edited.some((one) => same(one, at));
            const isRefused =
              at !== null && refused.some((one) => same(one, at));
            const isPicked = at !== null && same(picked, at);
            return (
              <button
                key={node.key}
                type="button"
                data-flow-key={node.key}
                disabled={at === null}
                aria-pressed={isPicked}
                // 이름표가 안의 글을 덮으니 「고칠 곳 있음」도 이름표에 잇는다(이슈 329 L1)
                aria-label={
                  at !== null && node.n !== null && node.label !== null ?
                    words.nodeLabel(node.n, node.label, isEdited) +
                    (isRefused ? `, ${words.refused}` : '')
                  : undefined
                }
                onClick={() => {
                  if (at !== null) onPick(at);
                }}
                style={place(BOX[node.key])}
                className={cn(
                  'absolute box-border flex flex-col items-start gap-1 rounded-component border border-solid border-border-tertiary bg-background-primary p-3 text-left disabled:cursor-not-allowed disabled:opacity-40',
                  isPicked &&
                    'border-2 border-grey-800 bg-background-secondary',
                  isRefused && 'border-support-error-accent',
                )}
              >
                <span
                  data-testid="flow-node-name"
                  className="flex w-full items-center gap-2 text-style-pre-body-04 text-text-primary"
                >
                  {node.n !== null && (
                    <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-background-secondary-inverse text-style-pre-caption-01 text-background-primary">
                      {node.n}
                    </span>
                  )}
                  {/* 이름은 한 줄 말줄임(고른 마디 2px 테두리 + 「● 고침」이면 꺾여 줄 높이가 24 → 45 — 밴드 GP4). 전체 이름은 title·이름표(aria-label) */}
                  <span
                    data-testid="flow-node-label"
                    title={node.label ?? undefined}
                    className="min-w-0 truncate"
                  >
                    {node.label ?? '–'}
                  </span>
                  {isEdited && (
                    <span
                      data-testid="flow-edited"
                      className="ml-auto inline-flex shrink-0 items-center gap-1 text-style-pre-caption-02 text-support-orange-dark"
                    >
                      <span
                        aria-hidden
                        className="size-1.5 rounded-full bg-support-orange-dark"
                      />
                      {words.edited}
                    </span>
                  )}
                </span>
                <span className="text-style-pre-caption-03 text-text-tertiary">
                  {step.does}
                </span>
                <span
                  data-testid="flow-runs"
                  className="rounded-full bg-background-secondary px-2 text-style-pre-med-04 text-text-secondary"
                >
                  {step.runs}
                </span>
                {isRefused && (
                  <span
                    data-testid="slot-refused"
                    className="text-style-pre-caption-02 text-support-error-accent"
                  >
                    {words.refused}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
