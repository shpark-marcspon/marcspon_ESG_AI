// AD-02 고른 구성의 상세 카드(밴드 AD2 ②, 실서버 AD2R ③, 모듈 슬롯·prompt-model AD2W ② — 디자인 판 AD-02_r3).
//   - 모델 설정: 공통 부품 ModelCard(모델 칸마다 한 줄 — 모델 · temperature · 출력 상한 토큰, 웹검색 0 — sid:MARC-ENT-372).
//     AP1W ②: 머리 곁 글은 모듈 선언(modelNote — 없으면 없음). 칸이 둘 이상이면 줄마다 칸 이름 + 「<묶음들>에 쓰여요」(쓰는 곳 0 이면 없음).
//     AD2W ③: 값은 판 초안(바탕 판 그대로이거나 고친 것)에서, editable.model 이 참이면 고칠 칸(경로 고름·수 글). 범위 밖이면 칸 아래 빨강 줄.
//   - 프롬프트: 머리 「프롬프트 — v3」 + 판 기본 정보(만든 때 · 만든 사람 · 메모) + 공통 부품 PromptCard(고른 칸 하나 — 글 전문·출력절 안내·메모).
//     PF1: 모듈이 처리 흐름을 주면 같은 카드 안 단계 줄 앞(시안 .a-sub 소제목 + 띠) · 카드 안 간격 24(시안 e-card gap space-6).
//     칸 이름·기본 글·메모는 서버 글(sid:MARC-ENT-384 — 웹 글 표 0).
//     AD2W ④: editable.prompts 면 글·메모를 고친다. 글자 수는 코드포인트(메모는 Python strip 뒤 — 서버 셈), 넘침·빈 글(Python strip)·서버가 짚은 칸은 빨강.
//     고친 글에 출력절이 바이트 그대로 없으면 그 자리에서 경고(막지 않음 — 서버 outputKept 와 같은 규칙).
//   - 고정 값 묶음(서버 fixed — 차례대로, key 를 가정하지 않음): 「<묶음 이름> · 고정」 + 「고정 값이라 바꿀 수 없어요」 + 항목 줄(값 없는 항목은 이름만).
//   - 모듈 줄: 준비 중(pending) 카드 · 읽기 전용 줄 글(lines — 그린워싱 고정 규칙).
//   LK2: 고정 값 카드 머리 h3 앞 16px 자물쇠(시안 v148 .e-card h3 svg.lock, 머리 사이 8 — CardHead locked).
import type { ReactNode } from 'react';

import { LockIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { AI_SETTING_TEXT } from '../../../entities/ai-setting/config/text.ts';
import {
  codepoints,
  pyStrip,
} from '../../../entities/ai-setting/model/index.ts';
import type {
  FixedGroup,
  ModelDraft,
  ModelErrors,
  ModelSlot,
  ModuleComponent,
  PromptEntry,
  PromptErrors,
  PromptGroup,
} from '../../../entities/ai-setting/model/index.ts';
import { ModelCard, PromptCard } from '../../../shared/ui/ai-setting/index.ts';
import type { ModelCardRow } from '../../../shared/ui/ai-setting/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import { modelName, modelUses } from '../model/index.ts';

const words = AI_SETTING_TEXT;

function CardHead({
  title,
  children,
  locked = false,
}: {
  title: string;
  children?: ReactNode;
  /** 고정 값 카드 — 제목 앞 자물쇠. */
  locked?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <h3
        className={cn(
          'm-0 text-style-pre-heading-02 text-text-primary',
          locked && 'flex items-center gap-2',
        )}
      >
        {locked && (
          <LockIcon
            aria-hidden
            className="size-4 shrink-0 text-text-tertiary"
          />
        )}
        {title}
      </h3>
      {children}
    </div>
  );
}

/**
 * 모델 칸 하나의 줄: 값은 초안(one), 경로 이름은 고른 경로의 첫 모델(경로가 고를 거리에 없으면 바탕 판 모델).
 * hidden 이면 temperature 를 싣지 않는다(모듈 hideTemperature — 밴드 IRA2 K3, 그 줄 0).
 */
export function modelRow(
  slot: ModelSlot,
  many: boolean,
  one: ModelDraft,
  errors?: ModelErrors,
  uses: readonly string[] = [],
  hidden = false,
): ModelCardRow {
  const t = words.model;
  const { model } = slot;
  const choice = slot.routeChoices.find((each) => each.route === one.route);
  const row: ModelCardRow = {
    key: slot.key,
    name: many ? slot.label : undefined,
    uses: many && uses.length > 0 ? t.uses(uses) : undefined,
    route: {
      label: t.route,
      value: one.route,
      name:
        choice ?
          modelName(choice.models, choice.route)
        : modelName(model.models, one.route),
      options: slot.routeChoices.map((each) => ({
        value: each.route,
        label: modelName(each.models, each.route),
      })),
    },
    temperature: {
      label: t.temperature,
      value: one.temperature ?? words.none,
      off: one.temperature === null,
      error: errors?.temperature === 'range' ? t.temperatureRange : null,
    },
    maxOutputTokens: {
      label: t.maxOutputTokens,
      value: one.maxOutputTokens,
      error:
        errors?.maxOutputTokens === 'range' ?
          t.maxOutputRange(choice?.maxOutputTokensMax ?? 0)
        : null,
    },
  };
  const { temperature, ...rest } = row;
  return hidden ? rest : { ...rest, temperature };
}

export function ModelDetail({
  slots,
  groups,
  note,
  hideTemperature,
  models,
  errors,
  readOnly,
  edited,
  onRoute,
  onTemperature,
  onMaxOutputTokens,
}: {
  slots: readonly ModelSlot[];
  /** 프롬프트 묶음(모델 칸이 쓰이는 곳 — modelSlots). */
  groups: readonly PromptGroup[];
  /** 머리 곁 글(모듈 선언 — 없으면 없음). */
  note?: string;
  /** 모델 칸 key → 참이면 temperature 줄 0(모듈 선언 — 없으면 모든 칸 그대로, 밴드 IRA2 K3). */
  hideTemperature?: (slot: string) => boolean;
  /** 초안의 모델 칸마다 모델(slots 차례). */
  models: readonly ModelDraft[];
  errors: readonly ModelErrors[];
  readOnly: boolean;
  /** 모델을 고쳤는가(머리 꼬리표). */
  edited: boolean;
  onRoute(slot: number, route: string): void;
  onTemperature(slot: number, text: string): void;
  onMaxOutputTokens(slot: number, text: string): void;
}) {
  const at = (key: string) => slots.findIndex((slot) => slot.key === key);
  const uses = modelUses({ models: slots, promptGroups: groups });
  return (
    <Card data-card="model-detail" className="flex flex-col gap-4">
      <CardHead title={words.model.title} />
      <ModelCard
        title={words.model.title}
        note={note}
        readOnly={readOnly}
        tag={
          edited ?
            <span
              data-testid="model-edited"
              className="text-style-pre-caption-02 text-support-orange"
            >
              {words.prompt.edited}
            </span>
          : undefined
        }
        rows={slots.map((slot, index) =>
          modelRow(
            slot,
            slots.length > 1,
            models[index]!,
            errors[index],
            uses[slot.key],
            hideTemperature?.(slot.key) ?? false,
          ),
        )}
        onRoute={(key, route) => onRoute(at(key), route)}
        onTemperature={(key, text) => onTemperature(at(key), text)}
        onMaxOutputTokens={(key, text) => onMaxOutputTokens(at(key), text)}
      />
    </Card>
  );
}

/** 프롬프트 카드의 판 기본 정보(기본 판은 없음). */
export interface VersionMeta {
  /** 「2026-10-19 11:40 · 만든 사람」 꼴(화면이 지음). */
  created: string;
  memo: string;
}

export function PromptDetail({
  version,
  meta,
  entry,
  value,
  errors,
  server,
  edited,
  basedOn,
  notice,
  readOnly,
  limits,
  flow,
  slotLabel,
  lowerKey,
  promptNote,
  outputNote,
  onText,
  onMemo,
}: {
  version: string;
  meta: VersionMeta | null;
  /** 바탕 판의 칸(label·KEY·출력절·처음 글 여부). */
  entry: PromptEntry;
  /** 초안의 글·메모. */
  value: { text: string; memo: string };
  errors: PromptErrors;
  /** 서버가 짚은 칸 오류 문장(저장 거절 fields). */
  server: { text?: string; memo?: string };
  edited: boolean;
  /** 고친 동안 머리 곁 「v3 바탕 · 저장 전」(없으면 null). */
  basedOn: string | null;
  /** 고친 동안 머리 아래 안내 줄(r3 「고친 것은 위 [새 버전으로 저장]으로 …」, 없으면 null). */
  notice: string | null;
  readOnly: boolean;
  limits: { textMax: number; memoMax: number };
  /** 모듈의 처리 흐름(카드 안 단계 줄 앞 — 밴드 PF1, 없으면 없음). */
  flow?: ReactNode;
  /** 첫 줄 라벨 칸 글(모듈 slotLabel — 없으면 「단계」, 밴드 TRA2). */
  slotLabel?: string;
  /** 칸 KEY 소문자 그대로(모듈 lowerKey, 밴드 TRA2). */
  lowerKey?: boolean;
  /** 글 칸 아래 안내 한 줄(모듈 promptNote 의 이 칸 글 — 없거나 null 이면 줄 0, 밴드 DVA2 K1). */
  promptNote?: string | null;
  /** 출력절 안내 모듈 글(모듈 outputNote 의 이 칸 글 — 없거나 null 이면 공통 글, 밴드 DVA2 K2). */
  outputNote?: string | null;
  onText(text: string): void;
  onMemo(memo: string): void;
}) {
  const t = words.prompt;
  const textError =
    errors.text === 'over' ? t.over(limits.textMax)
    : errors.text === 'empty' ? t.empty
    : (server.text ?? null);
  const memoError =
    errors.memo === 'over' ? t.over(limits.memoMax) : (server.memo ?? null);
  // 출력절: 안 고쳤으면 서버 outputKept, 고쳤으면 글에 절이 바이트 그대로 있는가(서버와 같은 규칙 — 막지 않음).
  const outputKept =
    value.text === entry.text ?
      entry.outputKept
    : entry.outputSection === null || value.text.includes(entry.outputSection);
  return (
    <Card data-card="prompt" className="flex flex-col gap-6">
      <CardHead title={t.title(version)}>
        {basedOn !== null && (
          <span
            data-testid="based-on"
            className="text-style-pre-caption-03 text-support-orange"
          >
            {basedOn}
          </span>
        )}
      </CardHead>
      {notice !== null && (
        <p
          data-testid="prompt-notice"
          className="m-0 text-style-pre-caption-03 text-text-secondary"
        >
          {notice}
        </p>
      )}
      {meta && (
        <p
          data-testid="version-meta"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          <span data-testid="created">{meta.created}</span>
          {' · '}
          <span data-testid="memo">
            {meta.memo === '' ? words.emptyMemo : meta.memo}
          </span>
        </p>
      )}
      <PromptCard
        title={entry.label}
        tag={entry.key}
        lowerKey={lowerKey}
        edited={edited ? t.edited : null}
        readOnly={readOnly}
        stepLabel={slotLabel ?? t.stepLabel}
        textLabel={t.text}
        text={value.text}
        textCount={t.count(codepoints(value.text), limits.textMax)}
        textError={textError}
        note={promptNote ?? null}
        outputNote={
          entry.outputSection === null ? null : (outputNote ?? t.outputNote)
        }
        outputLost={outputKept ? null : t.outputLost}
        untouched={entry.isDefault && !edited ? t.untouched : null}
        memoLabel={t.memo}
        memo={value.memo}
        memoCount={t.count(codepoints(pyStrip(value.memo)), limits.memoMax)}
        memoError={memoError}
        memoNote={t.memoNote}
        flow={flow}
        onText={onText}
        onMemo={onMemo}
      />
    </Card>
  );
}

/** 고정 값 하나의 글: null 이름만, 배열 「 · 」로 잇기. */
export const fixedValue = (value: FixedGroup['items'][number]['value']) =>
  value === null ? null
  : Array.isArray(value) ? value.join(' · ')
  : String(value);

export function FixedCard({ group }: { group: FixedGroup }) {
  return (
    <Card data-card="fixed" className="flex flex-col gap-3">
      <CardHead title={words.fixedTitle(group.label)} locked>
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {words.fixedNote}
        </span>
      </CardHead>
      <ul
        data-testid="fixed-items"
        className="m-0 flex flex-col gap-1 pl-5 text-style-pre-body-06 text-text-secondary"
      >
        {group.items.map((item) => {
          const value = fixedValue(item.value);
          return (
            <li key={item.key} data-fixed={item.key}>
              {item.label}
              {value !== null && (
                <span className="ml-2 text-text-primary">{value}</span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

/** 모듈이 더한 구성 줄의 상세(준비 중 · 읽기 전용 줄 글). */
export function ModuleDetail({
  component,
}: {
  component: ModuleComponent & {
    body: Exclude<ModuleComponent['body'], { kind: 'draft' }>;
  };
}) {
  if (component.body.kind === 'pending')
    return (
      <Card data-card="pending">
        <p className="m-0 text-style-pre-body-06 text-text-tertiary">
          {words.pending}
        </p>
      </Card>
    );
  const { title, lines, foot } = component.body;
  return (
    <Card data-card="lines" className="flex flex-col gap-3">
      <div
        data-testid="fixed-rules"
        className="flex flex-col gap-2 rounded-component border border-dashed border-border-secondary bg-support-grey-subtle px-6 py-4"
      >
        <h4 className="m-0 flex items-center gap-2 text-style-pre-body-04 text-text-primary">
          <LockIcon aria-hidden className="size-4" />
          {title}
        </h4>
        <ul className="m-0 flex flex-col gap-1 pl-5 text-style-pre-body-06 text-text-secondary">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {foot}
        </p>
      </div>
    </Card>
  );
}
