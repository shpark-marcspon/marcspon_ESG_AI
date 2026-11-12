// AD-02 영문번역 탭의 처리 흐름 띠 + 칸 고름(밴드 TRA1 — 시안 AD-02-TR r1 「처리 흐름」 .fa-tr, 1028×312). 프롬프트 상세 카드 위에 그린다.
//   번호 마디 다섯 = 프롬프트 묶음 다섯(이름은 서버 묶음 label — key 로 찾음, 응답에 없는 key 의 마디는 누를 수 없다). 마디 누름 → 그 묶음의 보이는 차례 첫 칸(TRA2 D1).
//   고정 상자(파일 · 쪽 범위 / 결과)·메모 여섯·화살표는 시안 자리 그대로(도면 좌표는 토큰 밖 — 그린워싱 띠와 같음). 마디 꼴은 그린워싱 띠(FlowBand)와 같다.
//   칸 고름(K1 가 — 시안은 단계 칸 카드를 쌓지만 껍데기의 프롬프트 카드는 칸 하나라 칸 단추로 하나씩): 띠 아래 머리 줄(「단계 n 이름 · 빈도」) + 칸 단추
//   (서버 label · key). 번역 묶음만 소묶음 셋(.tr-grp — model 의 웹 표, 모르는 key 는 「그 밖」): 처음에는 공통만 펼침, 고른 칸이 든 소묶음은 펼침,
//   소묶음 머리 단추 aria-expanded. 고친 칸이 있는 소묶음 머리에 「고침 n」. 번역 묶음 머리 줄 아래 이어 붙임 안내 한 줄(시안 .tr-lead — TRA2 D8).
//   고친 칸 「● 고침」 · 서버가 짚은 칸 「고칠 곳 있음」(그린워싱 띠와 같은 표시). 키트·shared/ui 공개 표면만, api 칸은 가져오지 않는다.
import { useState } from 'react';
import type { CSSProperties } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import type { TRANSLATION_SETTING_TEXT } from '../config/text.ts';
import { firstShown, flowNodes, promptSections } from '../model/index.ts';
import type { FlowGroup, SectionKey } from '../model/index.ts';

type At = { group: number; prompt: number };

export interface TranslationFlowBandProps {
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
  words: (typeof TRANSLATION_SETTING_TEXT)['flow'];
  /** 프롬프트 카드 안 소제목 꼴(PF1 — 겉 카드 0 · h4). 기본은 따로 카드. */
  inline?: boolean;
}

const WIDTH = 1028;
const HEIGHT = 312;
const NODE_W = 150;
const NODE_H = 112;
const NODE_TOP = 100;
/** 번호 마디 왼쪽 자리(시안 .tr-n1~5). */
const LEFT: Record<FlowGroup, number> = {
  translate: 100,
  polish: 270,
  editorial_qa: 440,
  review: 610,
  autofix: 780,
};
/** 고정 상자·메모 자리(시안 .tr-s·.tr-e·.tr-k·.tr-q·.tr-ab·.tr-l-*). */
const BOX = {
  start: { left: 0, top: 134, width: 80, height: 44 },
  end: { left: 950, top: 122, width: 78, height: 68 },
  korean: { left: 96, top: 8, width: 290, height: 56 },
  qa: { left: 420, top: 8, width: 200, height: 56 },
  ab: { left: 640, top: 8, width: 388, height: 56 },
  table: { left: 200, top: 262 },
  afterFix: { left: 770, top: 262 },
  pre: { left: 0, top: 188, width: 80 },
} satisfies Record<string, CSSProperties>;

const same = (a: At, b: At) => a.group === b.group && a.prompt === b.prompt;
const fixedBox =
  'absolute box-border flex items-center justify-center rounded-component bg-background-secondary px-2 py-1 text-center text-style-pre-caption-02 text-text-tertiary';
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

export function TranslationFlowBand({
  groups,
  picked,
  edited,
  refused,
  onPick,
  words,
  inline = false,
}: TranslationFlowBandProps) {
  const nodes = flowNodes(groups);
  /** 소묶음 펼침을 사용자가 바꾼 값(없으면 공통·고른 칸이 든 소묶음만 펼침). */
  const [toggled, setToggled] = useState<Partial<Record<SectionKey, boolean>>>(
    {},
  );
  const pickedGroup = groups[picked.group];
  const pickedNode = nodes.find((node) => node.group === picked.group);
  const sections = pickedGroup ? promptSections(pickedGroup) : [];
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
                id="tr-flow-arrow"
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
            {[80, 250, 420, 590, 760, 930].map((x) => (
              <path
                key={x}
                d={`M${x} 156H${x + 18}`}
                markerEnd="url(#tr-flow-arrow)"
              />
            ))}
            <path d="M175 100V64" className="[stroke-dasharray:4_4]" />
            <path d="M515 100V64" className="[stroke-dasharray:4_4]" />
            <path
              d="M175 212V256H685V214"
              className="[stroke-dasharray:4_4]"
              markerEnd="url(#tr-flow-arrow)"
            />
            <path d="M855 212V256" className="[stroke-dasharray:4_4]" />
          </svg>
          <span data-flow-fixed="" className={fixedBox} style={BOX.start}>
            {words.start.join(' ')}
          </span>
          <span className={fixedBox} style={BOX.korean}>
            {words.notes.korean}
          </span>
          <span className={fixedBox} style={BOX.qa}>
            {words.notes.qa}
          </span>
          <span className={fixedBox} style={BOX.ab}>
            {words.notes.ab}
          </span>
          <span className={lineLabel} style={BOX.table}>
            {words.notes.table}
          </span>
          <span className={lineLabel} style={BOX.afterFix}>
            {words.notes.afterFix}
          </span>
          <span className={cn(lineLabel, 'text-center')} style={BOX.pre}>
            {words.notes.pre}
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
            const at =
              group === null ? null : (
                { group, prompt: firstShown(groups[group]!) }
              );
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
                disabled={at === null}
                aria-pressed={isPicked}
                // 이름표가 안의 글을 덮으니 「고칠 곳 있음」도 이름표에 잇는다(이슈 476 — 그린 GIS1 꼴)
                aria-label={
                  node.label !== null ?
                    words.nodeLabel(node.n, node.label, nodeEdited) +
                    (nodeRefused ? `, ${words.refused}` : '')
                  : undefined
                }
                onClick={() => {
                  if (at !== null) onPick(at);
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
          {pickedGroup.key === 'translate' && (
            <p
              data-testid="flow-lead"
              className="m-0 bg-support-grey-subtle px-4 py-3 text-style-pre-body-05 text-text-secondary"
            >
              {words.lead}
            </p>
          )}
          {sections.map((section) => {
            const key = section.key;
            const holdsPicked = section.prompts.some(
              (one) => one.prompt === picked.prompt,
            );
            const open =
              key === null ||
              (toggled[key] ?? (key === 'common' || holdsPicked));
            const editedHere = section.prompts.filter((one) =>
              isEdited({ group: picked.group, prompt: one.prompt }),
            ).length;
            const head = key === null ? null : words.sections[key];
            return (
              <div
                key={key ?? 'all'}
                data-section={key ?? ''}
                className={cn(
                  'flex flex-col',
                  key !== null && 'bg-background-secondary',
                )}
              >
                {head && key !== null && (
                  <button
                    type="button"
                    aria-expanded={open}
                    onClick={() =>
                      setToggled((now) => ({ ...now, [key]: !open }))
                    }
                    className="box-border flex min-h-10 w-full cursor-pointer items-center gap-2 border-0 bg-transparent px-4 py-2 text-left text-style-pre-body-04 text-text-primary hover:bg-background-overlay-subtle"
                  >
                    <svg
                      aria-hidden
                      viewBox="0 0 16 16"
                      className={cn(
                        'size-4 shrink-0 fill-none stroke-current text-text-tertiary',
                        !open && '-rotate-90',
                      )}
                    >
                      <path d="M4 6l4 4 4-4" strokeWidth={1.5} />
                    </svg>
                    {head.title}
                    {head.note !== '' && (
                      <span className="text-style-pre-caption-03 text-text-tertiary">
                        {head.note}
                      </span>
                    )}
                    {editedHere > 0 && (
                      <span data-testid="section-edited">
                        <EditedTag text={words.sectionEdited(editedHere)} />
                      </span>
                    )}
                    <span className="ml-auto text-style-pre-caption-02 text-text-tertiary">
                      {words.sectionCount(section.prompts.length, open)}
                    </span>
                  </button>
                )}
                {open && (
                  <div className="flex flex-wrap gap-2 bg-background-primary py-2">
                    {section.prompts.map((one) => {
                      const at = { group: picked.group, prompt: one.prompt };
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
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
