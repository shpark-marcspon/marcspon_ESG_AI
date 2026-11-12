// S9 직접 입력 단계의 칸(밴드 W12-3 ③ — 발주서 Q4). 판·검사·본문은 model(emptyFactorForm·validateFactor·factorDraft·factorUnitOf) 그대로,
//   칸 꼴은 pages/ghg-index-pool/ui/FactorDialog.tsx 를 옮겨 적었다(pages 끼리 import 0 — L 규칙. Choice·FieldError 도 parts.tsx 를 옮겨 적음 — Choice 속은 W12-4 ① 부터 공통 NativeSelect,
//   공통화는 widgets 허락이 필요해 후속). 다른 점: 배출량 기준단위 칸 0(options.defaults.emissionUnit 고정 — 서버 BAD_EMISSION_UNIT) ·
//   읽기 꼴 0 · 칸 id 앞머리 entry-custom-. 548 칸 글(서버 422 fields.custom.<칸>)은 부르는 쪽이 errors 에 「custom.」 을 뗀 열쇠로 넣는다.
import type { ReactNode } from 'react';

import { Input } from '@marcspon/ui/components/input';
import { Switch } from '@marcspon/ui/components/switch';
import { Textarea } from '@marcspon/ui/components/textarea';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { factorUnitOf } from '../../../entities/ghg/model/index.ts';
import type {
  FactorForm,
  PoolOptions,
} from '../../../entities/ghg/model/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';

const words = GHG_TEXT.factor;
const FIRST_YEAR = 1990;
/** 서버 NAME_MAX·SOURCE_MAX·NOTE_MAX(inventory/service/utils/ghg_pool.py — FactorDialog 와 같은 값). */
const NAME_MAX = 100;
const SOURCE_MAX = 200;
const NOTE_MAX = 1000;

/** 칸 열쇠 → DOM id(첫 오류 칸 초점). */
export const customFieldId = (field: string) =>
  `entry-custom-${field.replace(/\./g, '-')}`;

/** 칸 아래 오류 한 줄(비면 그리지 않는다 — parts.tsx FieldError 를 옮겨 적음). */
function FieldError({ id, children }: { id: string; children: ReactNode }) {
  if (children === null || children === undefined || children === false)
    return null;
  return (
    <p
      id={id}
      data-testid={id}
      className="m-0 text-style-pre-caption-03 text-support-error-accent"
    >
      {children}
    </p>
  );
}

/** 고르기 상자 — 공통 NativeSelect(sid:MARC-ENT-430, 36·모서리 8·tertiary·▾ — sid:MARC-ISSUE-573). 폼 칸이라 w-full. */
function Choice({
  id,
  label,
  value,
  placeholder,
  options,
  disabled,
  invalid,
  describedBy,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  options: readonly { value: string; label: string }[];
  disabled?: boolean;
  invalid?: boolean;
  describedBy?: string;
  onChange(value: string): void;
}) {
  return (
    <NativeSelect
      id={id}
      aria-label={label}
      value={value}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      onChange={(event) => onChange(event.target.value)}
      className="w-full min-w-0"
    >
      <option value="">{placeholder}</option>
      {options.map((one) => (
        <option key={one.value} value={one.value}>
          {one.label}
        </option>
      ))}
    </NativeSelect>
  );
}

export interface EntryCustomFactorFormProps {
  options: PoolOptions;
  form: FactorForm;
  /** 칸 열쇠(validateFactor 꼴 — name·inputUnit·gases.CO2.factor …) → 글. */
  errors: Readonly<Record<string, string>>;
  /** 기준연도 드롭다운의 끝. */
  thisYear: number;
  disabled: boolean;
  onChange(next: Partial<FactorForm>, clear: readonly string[]): void;
}

export function EntryCustomFactorForm({
  options,
  form,
  errors,
  thisYear,
  disabled,
  onChange,
}: EntryCustomFactorFormProps) {
  const gases = options.gases;
  const unitKinds = options.units.map((one) => ({
    value: one.kind,
    label: GHG_TEXT.pool.unitKinds[one.kind] ?? one.kind,
  }));
  const unitsOf = (kind: string) =>
    (options.units.find((one) => one.kind === kind)?.units ?? []).map(
      (unit) => ({ value: unit, label: unit }),
    );
  const years = Array.from(
    { length: Math.max(0, thisYear - FIRST_YEAR + 1) },
    (_, index) => String(thisYear - index),
  ).map((year) => ({ value: year, label: year }));
  const err = (field: string) => errors[field] ?? null;
  const described = (field: string) =>
    errors[field] ? `${customFieldId(field)}-error` : undefined;
  const setGas = (gas: string, next: Partial<FactorForm['gases'][string]>) =>
    onChange(
      {
        gases: {
          ...form.gases,
          [gas]: { ...form.gases[gas]!, ...next },
        },
      },
      [`gases.${gas}.factor`, `gases.${gas}.gwp`, 'gases', 'factorUnit'],
    );

  const row = (
    field: string,
    label: string,
    required: boolean,
    body: ReactNode,
  ) => (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={customFieldId(field)}
        className="flex items-center text-style-pre-body-05 text-text-secondary"
      >
        {label}
        {required && <RequiredMark />}
      </label>
      {body}
      <FieldError id={`${customFieldId(field)}-error`}>{err(field)}</FieldError>
    </div>
  );
  const text = (field: 'name' | 'source', label: string, max: number) =>
    row(
      field,
      label,
      true,
      <Input
        id={customFieldId(field)}
        value={form[field]}
        maxLength={max}
        disabled={disabled}
        aria-invalid={err(field) !== null || undefined}
        aria-describedby={described(field)}
        onChange={(event) => onChange({ [field]: event.target.value }, [field])}
      />,
    );
  const choice = (
    field: 'baseYear' | 'tier' | 'countryCode' | 'industryCode',
    label: string,
    choices: readonly { value: string; label: string }[],
  ) =>
    row(
      field,
      label,
      true,
      <Choice
        id={customFieldId(field)}
        label={label}
        value={form[field]}
        placeholder={words.choose}
        options={choices}
        disabled={disabled}
        invalid={err(field) !== null}
        describedBy={described(field)}
        onChange={(value) => onChange({ [field]: value }, [field])}
      />,
    );

  return (
    <div
      data-testid="entry-custom-form"
      className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto"
    >
      <div className="grid grid-cols-2 gap-4">
        {text('name', words.name, NAME_MAX)}
        {text('source', words.source, SOURCE_MAX)}
        {choice('baseYear', words.baseYear, years)}
        {choice(
          'tier',
          words.tier,
          ['1', '2', '3'].map((tier) => ({ value: tier, label: tier })),
        )}
        {choice(
          'countryCode',
          words.country,
          options.countries.map((one) => ({
            value: one.code,
            label: one.name,
          })),
        )}
        {choice(
          'industryCode',
          words.industry,
          options.industries.map((one) => ({
            value: one.code,
            label: one.name,
          })),
        )}
        {row(
          'inputUnit',
          words.inputUnit,
          true,
          <div className="flex gap-2">
            <Choice
              id={customFieldId('inputUnit')}
              label={`${words.inputUnit} ${words.unitKind}`}
              value={form.inputKind}
              placeholder={words.unitKind}
              options={unitKinds}
              disabled={disabled}
              invalid={err('inputUnit') !== null}
              describedBy={described('inputUnit')}
              onChange={(value) =>
                // 투입 단위 종류가 바뀌면 계수 단위의 분모가 어긋난다 — 서버 기본으로(null, FactorDialog 와 같음).
                onChange(
                  {
                    inputKind: value,
                    inputUnit: '',
                    ...(value === form.inputKind ? {} : { factorUnit: null }),
                  },
                  ['inputUnit', 'factorUnit'],
                )
              }
            />
            <Choice
              id={`${customFieldId('inputUnit')}-unit`}
              label={`${words.inputUnit} ${words.unitName}`}
              value={form.inputUnit}
              placeholder={words.unitName}
              options={unitsOf(form.inputKind)}
              disabled={disabled}
              invalid={err('inputUnit') !== null}
              onChange={(value) =>
                onChange({ inputUnit: value }, ['inputUnit', 'factorUnit'])
              }
            />
          </div>,
        )}
        {row(
          'ncv',
          words.ncv,
          false,
          <div className="flex items-center gap-2">
            <Switch
              aria-label={words.ncv}
              checked={form.ncvEnabled}
              disabled={disabled}
              onCheckedChange={(checked) =>
                // 순발열량을 바꾸면 계수 단위는 서버 기본으로(null) — 값은 그대로 둔다.
                onChange({ ncvEnabled: checked, factorUnit: null }, [
                  'ncv',
                  'ncvUnit',
                  'factorUnit',
                ])
              }
            />
            <Input
              id={customFieldId('ncv')}
              value={form.ncv}
              inputMode="decimal"
              maxLength={40}
              disabled={disabled || !form.ncvEnabled}
              aria-invalid={err('ncv') !== null || undefined}
              aria-describedby={described('ncv')}
              onChange={(event) =>
                onChange({ ncv: event.target.value }, ['ncv'])
              }
            />
          </div>,
        )}
        {row(
          'ncvUnit',
          words.ncvUnit,
          form.ncvEnabled,
          <div className="flex gap-2">
            <Choice
              id={customFieldId('ncvUnit')}
              label={`${words.ncvUnit} ${words.unitKind}`}
              value={form.ncvKind}
              placeholder={words.unitKind}
              options={unitKinds}
              disabled={disabled || !form.ncvEnabled}
              invalid={err('ncvUnit') !== null}
              describedBy={described('ncvUnit')}
              onChange={(value) =>
                onChange({ ncvKind: value, ncvUnit: '' }, ['ncvUnit'])
              }
            />
            <Choice
              id={`${customFieldId('ncvUnit')}-unit`}
              label={`${words.ncvUnit} ${words.unitName}`}
              value={form.ncvUnit}
              placeholder={words.unitName}
              options={unitsOf(form.ncvKind)}
              disabled={disabled || !form.ncvEnabled}
              onChange={(value) => onChange({ ncvUnit: value }, ['ncvUnit'])}
            />
          </div>,
        )}
      </div>
      <section
        aria-labelledby="entry-custom-gases-title"
        className="flex flex-col gap-2"
      >
        <h3
          id="entry-custom-gases-title"
          className="m-0 text-style-pre-heading-02 text-text-primary"
        >
          {words.gasColumns.gas}
        </h3>
        <FieldError id={`${customFieldId('gases')}-error`}>
          {err('gases')}
        </FieldError>
        <FieldError id={`${customFieldId('factorUnit')}-error`}>
          {err('factorUnit')}
        </FieldError>
        <table
          id={customFieldId('gases')}
          tabIndex={-1}
          className="w-full border-separate border-spacing-0 text-style-pre-body-06 text-text-secondary"
        >
          <thead>
            <tr>
              <th scope="col" className="px-2 py-2 text-left">
                {words.gasColumns.gas}
              </th>
              <th scope="col" className="px-2 py-2 text-left">
                {words.gasColumns.enabled}
              </th>
              <th
                id={customFieldId('factorUnit')}
                tabIndex={-1}
                scope="col"
                data-testid="entry-custom-factor-unit"
                aria-describedby={described('factorUnit')}
                className="px-2 py-2 text-left"
              >
                {words.factorUnit(factorUnitOf(form, options))}
              </th>
              <th scope="col" className="px-2 py-2 text-left">
                {words.gasColumns.gwp}
              </th>
            </tr>
          </thead>
          <tbody>
            {gases.map((gas) => {
              const one = form.gases[gas]!;
              const off = disabled || !one.enabled;
              return (
                <tr key={gas} data-gas={gas}>
                  <th scope="row" className="px-2 py-2 text-left">
                    {gas}
                  </th>
                  <td className="px-2 py-2">
                    <Switch
                      aria-label={words.gasToggle(gas)}
                      checked={one.enabled}
                      disabled={disabled}
                      onCheckedChange={(checked) =>
                        setGas(gas, { enabled: checked })
                      }
                    />
                  </td>
                  {(['factor', 'gwp'] as const).map((key) => {
                    const field = `gases.${gas}.${key}`;
                    return (
                      <td key={key} className="px-2 py-2">
                        <Input
                          id={customFieldId(field)}
                          aria-label={
                            key === 'factor' ?
                              words.gasFactor(gas)
                            : words.gasGwp(gas)
                          }
                          value={one[key]}
                          inputMode="decimal"
                          maxLength={40}
                          disabled={off}
                          aria-invalid={err(field) !== null || undefined}
                          aria-describedby={described(field)}
                          onChange={(event) =>
                            setGas(gas, { [key]: event.target.value })
                          }
                        />
                        <FieldError id={`${customFieldId(field)}-error`}>
                          {err(field)}
                        </FieldError>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      {row(
        'note',
        words.note,
        false,
        <Textarea
          id={customFieldId('note')}
          value={form.note}
          maxLength={NOTE_MAX}
          disabled={disabled}
          onChange={(event) => onChange({ note: event.target.value }, [])}
        />,
      )}
    </div>
  );
}
