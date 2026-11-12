// AI 설정의 모델 설정 카드(밴드 AD2W ②③ — 디자인 판 AD-02_r3 「모델 설정」). 도메인을 모른다: 칸 이름·값·고를 거리·오류 글은 모두 props 로 받는다.
//   - 줄 묶음 하나 = 모델 칸 하나(칸이 하나면 칸 이름 없이). 칸 셋(줄마다 라벨 칸 | 값 칸 — 시안 .e-formrows, GW3R B9): 모델(경로 고름) · temperature · 출력 상한 토큰. 웹검색 칸은 없다(sid:MARC-ENT-372).
//     칸이 둘 이상이면 줄마다 칸 이름(칸 이름 앞)과 줄 아래 회색 한 줄 「<묶음들>에 쓰여요」(uses — 밴드 AP1W). 머리 곁 글(note)은 없으면 그리지 않는다.
//   - readOnly 면 값을 글로만 보인다(고칠 칸 0). 고칠 때는 경로 = 고름 칸, 수 = 글 칸(쓰는 화면이 글을 수로 읽고 범위를 본다).
//   - temperature 를 받지 않는 경로면(off) 칸이 꺼지고 값은 「–」. 오류 글이 있으면 칸 아래 빨강 줄.
//   - temperature 없으면 줄 0(모듈 hideTemperature — IRA2). 다른 두 줄의 꼴·차례는 그대로.
//   - 수 칸 폭은 80(w-20 — 시안 v148, 밴드 LK2 §7 B9).
import type { ReactNode } from 'react';

import { Input } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

import { NativeSelect } from '../../filter-select/index.ts';
import { PARTS_TEXT } from '../../text.ts';

export interface ModelCardField {
  label: string;
  value: string;
  error?: string | null;
  /** 칸을 끈다(값을 받지 않는 경로). */
  off?: boolean;
}

export interface ModelCardRow {
  key: string;
  /** 모델 칸 이름(칸이 둘 이상일 때만 — 칸 이름 앞에 붙는다). */
  name?: string;
  /** 그 칸을 쓰는 곳(줄 아래 회색 한 줄 — 없으면 줄 0). */
  uses?: string;
  /** 경로: value 는 고름 열쇠(option value 와 같은 것), name 은 읽기에 보이는 이름(밴드 AD2W ③ — 검증 권고 R1). */
  route: ModelCardField & {
    name: string;
    options: readonly { value: string; label: string }[];
  };
  /** 없으면 그 줄(라벨·값) 통째 0(밴드 IRA2 K3). */
  temperature?: ModelCardField;
  maxOutputTokens: ModelCardField;
}

export interface ModelCardProps {
  title: string;
  /** 머리 곁 글(없으면 그리지 않는다). */
  note?: string;
  rows: readonly ModelCardRow[];
  readOnly: boolean;
  /** 머리 오른쪽(고침 꼬리표 등). */
  tag?: ReactNode;
  onRoute?(key: string, route: string): void;
  onTemperature?(key: string, text: string): void;
  onMaxOutputTokens?(key: string, text: string): void;
  /** 「…에 쓰여요」 줄의 숨은 이름(dt sr-only). 없으면 PARTS_TEXT.modelUses. */
  usesLabel?: string;
}

const labelOf = (row: ModelCardRow, field: ModelCardField) =>
  row.name ? `${row.name} ${field.label}` : field.label;

// 칸 줄 꼴(시안 .e-formrows — GW-02 양식 줄과 같은 값, GW3R B9·B10): 묶음 위 선, 줄마다 아래 선·높이 64 이상,
// 160 라벨 칸은 옅은 회색 바탕·오른쪽 선·500 14 회색 글·좌우 24, 값 칸은 위아래 12·좌우 16. 단계 카드(PromptCard)도 쓴다.
/** 줄 묶음(위 선). */
export const FORM_ROWS_LOOK =
  'm-0 flex flex-col border-0 border-t border-solid border-border-tertiary';
/** 줄 하나(아래 선). */
export const FORM_ROW_LOOK =
  'flex min-h-16 items-stretch border-0 border-b border-solid border-border-tertiary';
/** 라벨 칸. */
export const FORM_LABEL_LOOK =
  'box-border flex w-40 shrink-0 items-center border-0 border-r border-solid border-border-tertiary bg-support-grey-subtle px-6 text-style-pre-body-05 text-text-tertiary';
/** 값 칸. */
export const FORM_VALUE_LOOK =
  'm-0 flex min-w-0 flex-1 flex-col gap-1 px-4 py-3';

function FieldError({ text }: { text?: string | null }) {
  if (!text) return null;
  return (
    <p
      role="alert"
      className="m-0 text-style-pre-caption-03 text-support-error-accent"
    >
      {text}
    </p>
  );
}

export function ModelCard({
  title,
  note,
  rows,
  readOnly,
  tag,
  onRoute,
  onTemperature,
  onMaxOutputTokens,
  usesLabel = PARTS_TEXT.modelUses,
}: ModelCardProps) {
  return (
    <section
      aria-label={title}
      data-card="model"
      className="flex flex-col gap-3 rounded-component border border-solid border-border-tertiary px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="m-0 text-style-pre-body-05 text-text-primary">
          {title}
        </h4>
        {note !== undefined && (
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {note}
          </span>
        )}
        {tag}
      </div>
      {rows.map((row) => (
        <dl key={row.key} data-step={row.key} className={FORM_ROWS_LOOK}>
          <div className={FORM_ROW_LOOK}>
            <dt className={FORM_LABEL_LOOK}>{labelOf(row, row.route)}</dt>
            <dd className={FORM_VALUE_LOOK}>
              {readOnly ?
                <span data-value="route">{row.route.name}</span>
              : <NativeSelect
                  aria-label={labelOf(row, row.route)}
                  value={row.route.value}
                  onChange={(event) => onRoute?.(row.key, event.target.value)}
                  className="self-start"
                >
                  {row.route.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </NativeSelect>
              }
              <FieldError text={row.route.error} />
            </dd>
          </div>
          {(
            [
              // temperature 없으면 줄 0(밴드 IRA2 K3)
              ...(row.temperature ?
                [[row.temperature, onTemperature, 'temperature'] as const]
              : []),
              [row.maxOutputTokens, onMaxOutputTokens, 'maxOutputTokens'],
            ] as const
          ).map(([field, change, name]) => (
            <div key={name} className={FORM_ROW_LOOK}>
              <dt className={FORM_LABEL_LOOK}>{labelOf(row, field)}</dt>
              <dd className={FORM_VALUE_LOOK}>
                {readOnly || field.off ?
                  <span
                    data-value={name}
                    className={cn(field.off && 'text-text-tertiary')}
                  >
                    {field.value}
                  </span>
                : <Input
                    aria-label={labelOf(row, field)}
                    aria-invalid={field.error ? true : undefined}
                    inputMode="decimal"
                    value={field.value}
                    onChange={(event) => change?.(row.key, event.target.value)}
                    className={cn(
                      'w-20',
                      field.error && 'border-support-error-accent',
                    )}
                  />
                }
                <FieldError text={field.error} />
              </dd>
            </div>
          ))}
          {row.uses !== undefined && (
            <div>
              <dt className="sr-only">{usesLabel}</dt>
              <dd
                data-testid="model-uses"
                className="m-0 px-4 py-2 text-style-pre-caption-03 text-text-tertiary"
              >
                {row.uses}
              </dd>
            </div>
          )}
        </dl>
      ))}
    </section>
  );
}
