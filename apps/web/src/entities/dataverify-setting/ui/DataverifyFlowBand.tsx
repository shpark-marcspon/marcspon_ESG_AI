// AD-02 데이터 검증 탭의 처리 흐름 띠 + 칸 고름(밴드 DVA2 — 시안 AD-02-DV r1 「처리 흐름」 .fa--dv, 1028×288). 프롬프트 상세 카드 위에 그린다.
//   번호 마디 셋 = 프롬프트 묶음 셋(이름은 서버 묶음 label — key 로 찾음, 응답에 없는 key 의 마디는 누를 수 없다). 마디 누름 → 그 묶음 칸 0(지시 글 — 서버 차례 = 보이는 차례).
//   고정 상자(읽기 · 경고 · 엑셀 만들기 / 결과)·마름모·갈래 글 셋·화살표는 시안 자리 그대로(도면 좌표는 토큰 밖 — 영문번역 띠와 같음). 마디 꼴은 영문번역 띠와 같다.
//   칸 고름(TRA1 K1 가 — 시안은 단계 안에 두 칸을 쌓지만 껍데기의 프롬프트 카드는 칸 하나라 칸 단추로 하나씩): 띠 아래 머리 줄(「단계 n 이름 · 빈도」) + 칸 단추
//   (서버 label · 소문자 key). 소묶음 없음. 고친 칸 「● 고침」 · 서버가 짚은 칸 「고칠 곳 있음」(영문번역 띠와 같은 표시). 키트·shared/ui 공개 표면만, api 칸은 가져오지 않는다.
import type { CSSProperties } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import type { DATAVERIFY_SETTING_TEXT } from '../config/text.ts';
import { flowNodes } from '../model/index.ts';
import type { FlowGroup } from '../model/index.ts';

type At = { group: number; prompt: number };

export interface DataverifyFlowBandProps {
  groups: readonly {
    key: string;
    /** 서버 묶음 이름(마디 이름). */
    label: string;
    prompts: readonly { key: string; label: string }[];
  }[];
  picked: At;
  edited: readonly At[];
  refused: readonly At[];
  onPick(at: At): void;
  words: (typeof DATAVERIFY_SETTING_TEXT)['flow'];
  /** 프롬프트 카드 안 소제목 꼴(PF1 — 겉 카드 0 · h4). 기본은 따로 카드. */
  inline?: boolean;
}

const WIDTH = 1028;
const HEIGHT = 288;
const NODE_W = 168;
const NODE_H = 112;
const NODE_TOP = 88;
/** 번호 마디 왼쪽 자리(시안 .fa-dv-n1~3). */
const LEFT: Record<FlowGroup, number> = {
  plan: 216,
  review: 404,
  insight: 592,
};
/** 고정 상자·마름모·갈래 글 자리(시안 .fa-dv-in·-q·-l-yes·-l-no·-warn·-l-skip·-out·-e). */
const BOX = {
  start: { left: 0, top: 116, width: 96, height: 56 },
  question: { left: 120, top: 124, width: 80, height: 40 },
  yes: { left: 200, top: 118 },
  no: { left: 166, top: 196 },
  warn: { left: 88, top: 228, width: 144, height: 44 },
  skip: { left: 316, top: 18 },
  out: { left: 780, top: 116, width: 96, height: 56 },
  end: { left: 896, top: 116, width: 72, height: 56 },
} satisfies Record<string, CSSProperties>;

const same = (a: At, b: At) => a.group === b.group && a.prompt === b.prompt;
const fixedBox =
  'absolute box-border flex flex-col items-center justify-center rounded-component bg-background-secondary px-2 py-1 text-center text-style-pre-caption-02 text-text-tertiary';
const lineLabel = 'absolute text-style-pre-caption-02 text-text-tertiary';

/** 「● 고침」 표시. */
function EditedTag({ text }: { text: string }) {
  return (
    <span
      data-testid="flow-edited"
      className="inline-flex shrink-0 items-center gap-1 text-style-pre-caption-02 text-support-orange-dark"
    >
      <span
        aria-hidden
        className="size-1.5 rounded-full bg-support-orange-dark"
      />
      {text}
    </span>
  );
}

/** 줄 나눔 글(시안 <br>). */
function Lines({ lines }: { lines: readonly string[] }) {
  return lines.map((line) => <span key={line}>{line}</span>);
}

export function DataverifyFlowBand({
  groups,
  picked,
  edited,
  refused,
  onPick,
  words,
  inline = false,
}: DataverifyFlowBandProps) {
  const nodes = flowNodes(groups);
  const pickedGroup = groups[picked.group];
  const pickedNode = nodes.find((node) => node.group === picked.group);
  const isEdited = (at: At) => edited.some((one) => same(one, at));
  const isRefused = (at: At) => refused.some((one) => same(one, at));
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
            className="absolute inset-0 fill-none stroke-border-secondary"
          >
            <defs>
              <marker
                id="dv-flow-arrow"
                viewBox="0 0 8 8"
                refX="7"
                refY="4"
                markerWidth="8"
                markerHeight="8"
                orient="auto"
              >
                <path d="M0 0L8 4L0 8z" className="fill-border-secondary" />
              </marker>
            </defs>
            {[
              'M96 144H118',
              'M200 144H214',
              'M160 184V226',
              'M232 250H828V174',
              'M384 144H402',
              'M572 144H590',
              'M760 144H778',
              'M876 144H894',
            ].map((d) => (
              <path key={d} d={d} markerEnd="url(#dv-flow-arrow)" />
            ))}
            <polygon points="120,144 160,104 200,144 160,184" />
            <path
              d="M300 88V40H676V86"
              className="[stroke-dasharray:4_4]"
              markerEnd="url(#dv-flow-arrow)"
            />
          </svg>
          <span data-flow-fixed="" className={fixedBox} style={BOX.start}>
            <Lines lines={words.start} />
          </span>
          <span
            data-flow-fixed="question"
            className="absolute box-border flex flex-col items-center justify-center text-center text-style-pre-caption-02 text-text-secondary"
            style={BOX.question}
          >
            <Lines lines={words.question} />
          </span>
          <span className={lineLabel} style={BOX.yes}>
            {words.yes}
          </span>
          <span className={lineLabel} style={BOX.no}>
            {words.no}
          </span>
          <span data-flow-fixed="warn" className={fixedBox} style={BOX.warn}>
            <Lines lines={words.warn} />
          </span>
          <span className={lineLabel} style={BOX.skip}>
            {words.skip}
          </span>
          <span data-flow-fixed="out" className={fixedBox} style={BOX.out}>
            <Lines lines={words.out} />
          </span>
          <span
            data-flow-fixed="end"
            className="absolute box-border flex flex-col items-center justify-center rounded-component bg-grey-800 text-center text-background-primary"
            style={BOX.end}
          >
            <b className="text-style-pre-body-04">{words.end.title}</b>
            {words.end.lines.map((line) => (
              <small key={line} className="text-style-pre-caption-03">
                {line}
              </small>
            ))}
          </span>
          {nodes.map((node) => {
            const group = node.group;
            const step = words.steps[node.key];
            const nodeEdited =
              group !== null && edited.some((one) => one.group === group);
            const nodeRefused =
              group !== null && refused.some((one) => one.group === group);
            const isPicked = group !== null && picked.group === group;
            return (
              <button
                key={node.key}
                type="button"
                data-flow-key={node.key}
                disabled={group === null}
                aria-disabled={group === null || undefined}
                aria-pressed={isPicked}
                aria-label={
                  node.label !== null ?
                    words.nodeLabel(node.n, node.label, nodeEdited)
                  : undefined
                }
                onClick={() => {
                  if (group !== null) onPick({ group, prompt: 0 });
                }}
                style={{
                  left: LEFT[node.key],
                  top: NODE_TOP,
                  width: NODE_W,
                  height: NODE_H,
                }}
                className={cn(
                  'absolute box-border flex flex-col items-start gap-1 rounded-component border border-solid border-border-tertiary bg-background-primary p-3 text-left disabled:cursor-not-allowed disabled:opacity-40',
                  isPicked &&
                    'border-2 border-grey-800 bg-background-secondary',
                  nodeRefused && 'border-support-error-accent',
                )}
              >
                <span
                  data-testid="flow-node-name"
                  className="flex w-full items-center gap-2 text-style-pre-body-04 text-text-primary"
                >
                  <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-background-secondary-inverse text-style-pre-caption-01 text-background-primary">
                    {node.n}
                  </span>
                  <span
                    data-testid="flow-node-label"
                    title={node.label ?? undefined}
                    className="min-w-0 truncate"
                  >
                    {node.label ?? '–'}
                  </span>
                  {nodeEdited && (
                    <span className="ml-auto">
                      <EditedTag text={words.edited} />
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
                {nodeRefused && (
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
      {pickedGroup && (
        <div
          role="group"
          aria-label={words.picker}
          data-testid="flow-picker"
          className="flex flex-col gap-2"
        >
          <p className="m-0 flex flex-wrap items-center gap-2 text-style-pre-body-04 text-text-primary">
            {words.stepHead(
              pickedNode?.n ?? picked.group + 1,
              pickedGroup.label,
            )}
            {pickedNode && (
              <span className="text-style-pre-caption-03 text-text-tertiary">
                {words.steps[pickedNode.key].runs}
              </span>
            )}
          </p>
          <div className="flex flex-wrap gap-2 bg-background-primary py-2">
            {pickedGroup.prompts.map((one, prompt) => {
              const at = { group: picked.group, prompt };
              const pressed = same(at, picked);
              return (
                <button
                  key={one.key}
                  type="button"
                  data-prompt-key={one.key}
                  aria-pressed={pressed}
                  onClick={() => onPick(at)}
                  className={cn(
                    'box-border inline-flex cursor-pointer items-center gap-2 rounded-component border border-solid border-border-tertiary bg-background-primary px-3 py-2 text-left text-style-pre-body-04 text-text-primary',
                    pressed &&
                      'border-2 border-grey-800 bg-background-secondary',
                    isRefused(at) && 'border-support-error-accent',
                  )}
                >
                  {one.label}
                  <code className="rounded-control bg-background-secondary px-1 text-style-pre-caption-02 text-text-tertiary">
                    {one.key}
                  </code>
                  {isEdited(at) && <EditedTag text={words.edited} />}
                  {isRefused(at) && (
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
      )}
    </section>
  );
}
