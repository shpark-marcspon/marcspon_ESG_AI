// AD-02 보고서 작성 탭의 처리 흐름 띠 + 칸 고름(밴드 RPA3 — 시안 AD-02-RP r1 「처리 흐름」 .fa-rp, 1028×172 — v195 에서 띠 위 빈자리 60 뺌). 프롬프트 상세 카드 위에 그린다.
//   번호 마디 둘 = 프롬프트 묶음 둘(이름은 서버 묶음 label — key 로 찾음, 응답에 없는 key 의 마디는 누를 수 없다).
//   마디 누름 → 그 묶음 칸 0(서버 차례 = 보이는 차례). 선 넷·고정 상자(시작 · 출처 확인 / 결과)·갈래 글은 시안 자리 그대로
//   (도면 좌표는 토큰 밖 — 중대성평가 띠와 같음). 마디 꼴은 중대성평가 띠와 같다.
//   칸 고름(TRA1 K1 가 — 칸 단추로 하나씩): 띠 아래 머리 줄(「단계 n 이름 · 빈도」) + 칸 단추(서버 label · 소문자 key). 소묶음 없음.
//   고친 칸 「● 고침」 · 서버가 짚은 칸 「고칠 곳 있음」. 키트·shared/ui 공개 표면만, api 칸은 가져오지 않는다.
import type { CSSProperties } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import type { DRAFTING_SETTING_TEXT } from '../config/text.ts';
import { flowNodes } from '../model/index.ts';
import type { FlowNode } from '../model/index.ts';

type At = { group: number; prompt: number };

export interface DraftingFlowBandProps {
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
  words: (typeof DRAFTING_SETTING_TEXT)['flow'];
  /** 프롬프트 카드 안 소제목 꼴(PF1 — 겉 카드 0 · h4). 기본은 따로 카드. */
  inline?: boolean;
}

const WIDTH = 1028;
const HEIGHT = 172;
const NODE_W = 190;
const NODE_H = 112;
/** 마디 자리(시안 머리 <style> .fa-rp .rp-n1·rp-n2 — top 0. 띠 위 빈자리 60 을 뺐다, 캔버스 v195 · 밴드 RPW5 #8). */
const NODE_AT: Record<FlowNode['key'], CSSProperties> = {
  map: { left: 150, top: 0, width: NODE_W, height: NODE_H },
  draft: { left: 400, top: 0, width: NODE_W, height: NODE_H },
};
/** 고정 상자 자리(시안 .rp-s · .rp-k · .rp-e) · 갈래 글 자리(.rp-l1). */
const BOX = {
  start: { left: 0, top: 34, width: 110, height: 44 },
  check: { left: 650, top: 24, width: 200, height: 64 },
  end: { left: 900, top: 22, width: 128, height: 68 },
  branch: { left: 150, top: 130 },
} satisfies Record<string, CSSProperties>;
/** 선 넷(시안 경로 그대로 — 시작 → 1 → 2 → 출처 확인 → 결과). */
const LINES = ['M110 56H146', 'M340 56H396', 'M590 56H646', 'M850 56H896'];

const same = (a: At, b: At) => a.group === b.group && a.prompt === b.prompt;
const fixedBox =
  'absolute box-border flex flex-col items-center justify-center rounded-component bg-background-secondary px-2 py-1 text-center text-style-pre-caption-02 text-text-tertiary';

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

export function DraftingFlowBand({
  groups,
  picked,
  edited,
  refused,
  onPick,
  words,
  inline = false,
}: DraftingFlowBandProps) {
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
                id="rp-flow-arrow"
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
            {LINES.map((d) => (
              <path key={d} d={d} markerEnd="url(#rp-flow-arrow)" />
            ))}
          </svg>
          <span data-flow-fixed="" className={fixedBox} style={BOX.start}>
            <Lines lines={words.start} />
          </span>
          <span data-flow-fixed="check" className={fixedBox} style={BOX.check}>
            {words.check}
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
            const label =
              node.label === null ?
                undefined
              : words.nodeLabel(node.n, node.label, nodeEdited);
            return (
              <button
                key={node.key}
                type="button"
                data-flow-key={node.key}
                disabled={group === null}
                aria-disabled={group === null || undefined}
                aria-pressed={isPicked}
                aria-label={label}
                onClick={() => {
                  if (group !== null) onPick({ group, prompt: 0 });
                }}
                style={NODE_AT[node.key]}
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
          <span
            data-flow-branch=""
            className="absolute text-style-pre-caption-03 text-text-tertiary"
            style={BOX.branch}
          >
            {words.branch}
          </span>
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
              <span
                data-testid="flow-step-head"
                className="text-style-pre-caption-03 text-text-tertiary"
              >
                {words.steps[pickedNode.key].head}
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
