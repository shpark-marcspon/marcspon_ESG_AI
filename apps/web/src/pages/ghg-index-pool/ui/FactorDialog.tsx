// S20 배출계수 추가·수정·읽기 모달(밴드 W12-0b1 ③ — 스펙 ② S20, 결정 sid:MARC-ENT-469 3). 한 꼴로 셋:
//   - 새로(factorId null) → POST facilities/{id}/factors 201 · 있는 것 → PUT ghg-factors/{id}(늘 새 판). 성공 → onSaved(화면이 「저장됐어요」).
//   - 읽기(행 >) = 칸 꺼짐 + 「판 n」 + [수정](→ 쓰기 꼴). 옛 판 고르기·계산식 설정·산식 초기화 모달은 숨김(1차).
//   - 칸은 options 로 채운다: 기준연도 1990~올해 · Tier 1·2·3 · 국가·산업 드롭다운(「기존 선택 모달」 대신 — 스펙) · 단위 종류+단위.
//   - 가스 표 일곱(options.gases 차례): 포함 토글 · 배출계수 · GWP · 산식 글(그 가스 이름 — 셈 0, S12a). 켠 줄만 칸이 살아남.
//     계수 칸 머리에 factorUnit 글자(없으면 options.defaults 의 켬·끔 값 — 값을 바꾸어 보이지 않는다, sid:MARC-ENT-474).
//   - [저장]은 늘 켬 · 누를 때 validateFactor · 첫 오류 칸 초점. 서버 422 fields.<칸>·gases.<가스>.<칸> → 같은 칸 글(모듈 글).
//   - [취소]·✕: 바꾼 것이 있으면 「저장하지 않고 닫을까요?」.
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';

import { Input } from '@marcspon/ui/components/input';
import { Switch } from '@marcspon/ui/components/switch';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import type { GhgPoolAdminPort } from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  emptyFactorForm,
  factorDraft,
  factorFormOf,
  factorUnitOf,
  sameFactorForm,
  validateFactor,
} from '../../../entities/ghg/model/index.ts';
import type {
  FactorForm,
  PoolFactor,
  PoolOptions,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { Choice, ConfirmDialog, FieldError } from './parts.tsx';

const words = GHG_TEXT.factor;
const FIRST_YEAR = 1990;
/** 서버 NAME_MAX·SOURCE_MAX·NOTE_MAX(inventory/service/utils/ghg_pool.py). */
const NAME_MAX = 100;
const SOURCE_MAX = 200;
const NOTE_MAX = 1000;

/** 칸 열쇠 → DOM id(첫 오류 칸 초점). */
const fieldId = (field: string) => `ghg-factor-${field.replace(/\./g, '-')}`;

export interface FactorDialogProps {
  port: GhgPoolAdminPort;
  options: PoolOptions;
  /** 계수를 단 잎. */
  facilityId: string;
  /** 있는 계수면 그 id(읽기 꼴로 연다), 새로면 null. */
  factorId: string | null;
  /** 기준연도 드롭다운의 끝(올해 — 경로 컴포넌트가 넣는다). */
  thisYear: number;
  returnFocus: HTMLElement | null;
  onSaved(factor: PoolFactor): void;
  onClose(): void;
}

type Errors = Record<string, string>;

export function FactorDialog({
  port,
  options,
  facilityId,
  factorId,
  thisYear,
  returnFocus,
  onSaved,
  onClose,
}: FactorDialogProps) {
  const gases = options.gases;
  const [loaded, setLoaded] = useState<
    'loading' | 'failed' | { factor: PoolFactor | null }
  >(factorId === null ? { factor: null } : 'loading');
  const [base, setBase] = useState<FactorForm>(() => emptyFactorForm(options));
  const [form, setForm] = useState<FactorForm>(base);
  const [mode, setMode] = useState<'view' | 'edit'>(
    factorId === null ? 'edit' : 'view',
  );
  const [errors, setErrors] = useState<Errors>({});
  const [line, setLine] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [focus, setFocus] = useState<{ field: string } | null>(null);

  useEffect(() => {
    if (factorId === null) return;
    let live = true;
    void port.getFactor(factorId).then((outcome) => {
      if (!live) return;
      if (outcome.kind !== 'ok') return setLoaded('failed');
      const next = factorFormOf(outcome.value, options);
      setBase(next);
      setForm(next);
      setLoaded({ factor: outcome.value });
    });
    return () => {
      live = false;
    };
  }, [port, factorId, options]);

  useEffect(() => {
    if (focus) document.getElementById(fieldId(focus.field))?.focus();
  }, [focus]);

  const readOnly = mode === 'view' || saving;
  const change = (next: Partial<FactorForm>) => {
    setForm((before) => ({ ...before, ...next }));
    setLine(null);
  };
  const clear = (...fields: string[]) =>
    setErrors((before) => {
      const out = { ...before };
      for (const field of fields) delete out[field];
      return out;
    });
  const setGas = (gas: string, next: Partial<FactorForm['gases'][string]>) => {
    setForm((before) => ({
      ...before,
      gases: {
        ...before.gases,
        [gas]: { ...before.gases[gas]!, ...next },
      },
    }));
    clear(`gases.${gas}.factor`, `gases.${gas}.gwp`, 'gases');
  };

  const close = () => {
    if (saving) return;
    if (mode === 'edit' && !sameFactorForm(form, base)) setLeaving(true);
    else onClose();
  };

  const save = async () => {
    if (saving) return;
    setLine(null);
    const problems = validateFactor(form, gases);
    if (problems.length > 0) {
      const next: Errors = {};
      for (const [field, why] of problems)
        next[field] =
          field === 'gases' ? words.noGas
          : why === 'number' ? words.number
          : words.required;
      setErrors(next);
      setFocus({ field: problems[0]![0] });
      return;
    }
    setErrors({});
    const body = factorDraft(form, gases);
    setSaving(true);
    const outcome =
      factorId === null ?
        await port.createFactor(facilityId, body)
      : await port.saveFactor(factorId, body);
    setSaving(false);
    if (outcome.kind === 'ok') return onSaved(outcome.value);
    if (outcome.kind === 'rejected' && outcome.code === 'VALIDATION_ERROR') {
      const fields = Object.keys(outcome.fields);
      if (fields.length > 0) {
        const next: Errors = {};
        for (const field of fields)
          next[field] = field === 'gases' ? words.noGas : words.invalid;
        setErrors(next);
        setFocus({ field: fields[0]! });
        return;
      }
    }
    setLine(words.saveFailed);
  };

  const title =
    factorId === null ? words.titleNew
    : mode === 'view' ? words.titleView
    : words.titleEdit;
  const version =
    typeof loaded === 'object' && loaded.factor ? loaded.factor.version : null;
  const unitKinds = options.units.map((one) => ({
    value: one.kind,
    label: GHG_TEXT.pool.unitKinds[one.kind] ?? one.kind,
  }));
  const unitsOf = (kind: string) =>
    (options.units.find((one) => one.kind === kind)?.units ?? []).map(
      (unit) => ({ value: unit, label: unit }),
    );
  const emissionUnits = [
    ...new Set([options.defaults.emissionUnit.unit, form.emissionUnit]),
  ]
    .filter((unit) => unit !== '')
    .map((unit) => ({
      value: unit,
      label: unit,
    }));
  const years = Array.from(
    { length: Math.max(0, thisYear - FIRST_YEAR + 1) },
    (_, index) => String(thisYear - index),
  ).map((year) => ({ value: year, label: year }));
  const err = (field: string) => errors[field] ?? null;
  const described = (field: string) =>
    errors[field] ? `${fieldId(field)}-error` : undefined;

  const row = (
    field: string,
    label: string,
    required: boolean,
    body: ReactNode,
  ) => (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={fieldId(field)}
        className="flex items-center text-style-pre-body-05 text-text-secondary"
      >
        {label}
        {/* GX2 D5(sid:MARC-ISSUE-461): 읽기 꼴에는 필수 점 0. */}
        {required && mode !== 'view' && <RequiredMark />}
      </label>
      {body}
      <FieldError id={`${fieldId(field)}-error`}>{err(field)}</FieldError>
    </div>
  );
  const text = (field: 'name' | 'source', label: string, max: number) =>
    row(
      field,
      label,
      true,
      <Input
        id={fieldId(field)}
        value={form[field]}
        maxLength={max}
        disabled={readOnly}
        aria-invalid={err(field) !== null || undefined}
        aria-describedby={described(field)}
        onChange={(event) => {
          change({ [field]: event.target.value });
          clear(field);
        }}
      />,
    );

  const body =
    loaded === 'loading' ? <LoadSkeleton label={GHG_TEXT.common.loading} />
    : loaded === 'failed' ?
      <p
        role="alert"
        className="m-0 text-style-pre-body-06 text-support-error-accent"
      >
        {words.loadFailed}
      </p>
      // GX2 D1(sid:MARC-ISSUE-461): 몸 높이 60vh → 100vh − 240(머리·발·여백) — 900 화면에서 가스 표가 한눈에 더 든다. 폭 800 그대로.
    : <div
        data-testid="factor-body"
        className="flex max-h-[calc(100vh-240px)] flex-col gap-4 overflow-y-auto"
      >
        {version !== null && (
          <p
            data-testid="factor-version"
            className="m-0 text-style-pre-caption-03 text-text-tertiary"
          >
            {words.version(version)}
          </p>
        )}
        <div className="grid grid-cols-2 gap-4">
          {text('name', words.name, NAME_MAX)}
          {text('source', words.source, SOURCE_MAX)}
          {row(
            'baseYear',
            words.baseYear,
            true,
            <Choice
              id={fieldId('baseYear')}
              label={words.baseYear}
              value={form.baseYear}
              placeholder={words.choose}
              options={years}
              disabled={readOnly}
              invalid={err('baseYear') !== null}
              describedBy={described('baseYear')}
              onChange={(value) => {
                change({ baseYear: value });
                clear('baseYear');
              }}
            />,
          )}
          {row(
            'tier',
            words.tier,
            true,
            <Choice
              id={fieldId('tier')}
              label={words.tier}
              value={form.tier}
              placeholder={words.choose}
              options={['1', '2', '3'].map((tier) => ({
                value: tier,
                label: tier,
              }))}
              disabled={readOnly}
              invalid={err('tier') !== null}
              describedBy={described('tier')}
              onChange={(value) => {
                change({ tier: value });
                clear('tier');
              }}
            />,
          )}
          {row(
            'countryCode',
            words.country,
            true,
            <Choice
              id={fieldId('countryCode')}
              label={words.country}
              value={form.countryCode}
              placeholder={words.choose}
              options={options.countries.map((one) => ({
                value: one.code,
                label: one.name,
              }))}
              disabled={readOnly}
              invalid={err('countryCode') !== null}
              describedBy={described('countryCode')}
              onChange={(value) => {
                change({ countryCode: value });
                clear('countryCode');
              }}
            />,
          )}
          {row(
            'industryCode',
            words.industry,
            true,
            <Choice
              id={fieldId('industryCode')}
              label={words.industry}
              value={form.industryCode}
              placeholder={words.choose}
              options={options.industries.map((one) => ({
                value: one.code,
                label: one.name,
              }))}
              disabled={readOnly}
              invalid={err('industryCode') !== null}
              describedBy={described('industryCode')}
              onChange={(value) => {
                change({ industryCode: value });
                clear('industryCode');
              }}
            />,
          )}
          {row(
            'inputUnit',
            words.inputUnit,
            true,
            <div className="flex gap-2">
              <Choice
                id={fieldId('inputUnit')}
                label={`${words.inputUnit} ${words.unitKind}`}
                value={form.inputKind}
                placeholder={words.unitKind}
                options={unitKinds}
                disabled={readOnly}
                invalid={err('inputUnit') !== null}
                describedBy={described('inputUnit')}
                onChange={(value) => {
                  // 투입 단위 종류가 바뀌면 계수 단위의 분모가 어긋난다(서버 _check_unit_kinds) — 서버 기본으로(null).
                  change({
                    inputKind: value,
                    inputUnit: '',
                    ...(value === form.inputKind ? {} : { factorUnit: null }),
                  });
                  clear('inputUnit', 'factorUnit');
                }}
              />
              <Choice
                id={`${fieldId('inputUnit')}-unit`}
                label={`${words.inputUnit} ${words.unitName}`}
                value={form.inputUnit}
                placeholder={words.unitName}
                options={unitsOf(form.inputKind)}
                disabled={readOnly}
                onChange={(value) => {
                  change({ inputUnit: value });
                  clear('inputUnit');
                }}
              />
            </div>,
          )}
          {row(
            'emissionUnit',
            words.emissionUnit,
            true,
            <Choice
              id={fieldId('emissionUnit')}
              label={words.emissionUnit}
              value={form.emissionUnit}
              placeholder={words.unitName}
              options={emissionUnits}
              disabled={readOnly}
              invalid={err('emissionUnit') !== null}
              describedBy={described('emissionUnit')}
              onChange={(value) => {
                change({ emissionUnit: value });
                clear('emissionUnit');
              }}
            />,
          )}
          {row(
            'ncv',
            words.ncv,
            false,
            <div className="flex items-center gap-2">
              <Switch
                aria-label={words.ncv}
                checked={form.ncvEnabled}
                disabled={readOnly}
                onCheckedChange={(checked) => {
                  // 순발열량을 바꾸면 계수 단위는 서버 기본으로(null) — 값은 그대로 둔다.
                  change({ ncvEnabled: checked, factorUnit: null });
                  clear('ncv', 'ncvUnit', 'factorUnit');
                }}
              />
              <Input
                id={fieldId('ncv')}
                value={form.ncv}
                inputMode="decimal"
                maxLength={40}
                disabled={readOnly || !form.ncvEnabled}
                aria-invalid={err('ncv') !== null || undefined}
                aria-describedby={described('ncv')}
                onChange={(event) => {
                  change({ ncv: event.target.value });
                  clear('ncv');
                }}
              />
            </div>,
          )}
          {row(
            'ncvUnit',
            words.ncvUnit,
            form.ncvEnabled,
            <div className="flex gap-2">
              <Choice
                id={fieldId('ncvUnit')}
                label={`${words.ncvUnit} ${words.unitKind}`}
                value={form.ncvKind}
                placeholder={words.unitKind}
                options={unitKinds}
                disabled={readOnly || !form.ncvEnabled}
                invalid={err('ncvUnit') !== null}
                describedBy={described('ncvUnit')}
                onChange={(value) => {
                  change({ ncvKind: value, ncvUnit: '' });
                  clear('ncvUnit');
                }}
              />
              <Choice
                id={`${fieldId('ncvUnit')}-unit`}
                label={`${words.ncvUnit} ${words.unitName}`}
                value={form.ncvUnit}
                placeholder={words.unitName}
                options={unitsOf(form.ncvKind)}
                disabled={readOnly || !form.ncvEnabled}
                onChange={(value) => {
                  change({ ncvUnit: value });
                  clear('ncvUnit');
                }}
              />
            </div>,
          )}
        </div>
        <section
          aria-labelledby="ghg-factor-gases"
          className="flex flex-col gap-2"
        >
          <h3
            id="ghg-factor-gases"
            className="m-0 text-style-pre-heading-02 text-text-primary"
          >
            {words.gasColumns.gas}
          </h3>
          <FieldError id={`${fieldId('gases')}-error`}>
            {err('gases')}
          </FieldError>
          <FieldError id={`${fieldId('factorUnit')}-error`}>
            {err('factorUnit')}
          </FieldError>
          <table
            id={fieldId('gases')}
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
                  id={fieldId('factorUnit')}
                  tabIndex={-1}
                  scope="col"
                  data-testid="factor-unit-head"
                  aria-describedby={described('factorUnit')}
                  className="px-2 py-2 text-left"
                >
                  {words.factorUnit(factorUnitOf(form, options))}
                </th>
                <th scope="col" className="px-2 py-2 text-left">
                  {words.gasColumns.gwp}
                </th>
                <th scope="col" className="px-2 py-2 text-left">
                  {words.gasColumns.formula}
                </th>
              </tr>
            </thead>
            <tbody>
              {gases.map((gas) => {
                const one = form.gases[gas]!;
                const off = readOnly || !one.enabled;
                return (
                  <tr key={gas} data-gas={gas}>
                    <th scope="row" className="px-2 py-2 text-left">
                      {gas}
                    </th>
                    <td className="px-2 py-2">
                      <Switch
                        aria-label={words.gasToggle(gas)}
                        checked={one.enabled}
                        disabled={readOnly}
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
                            id={fieldId(field)}
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
                          <FieldError id={`${fieldId(field)}-error`}>
                            {err(field)}
                          </FieldError>
                        </td>
                      );
                    })}
                    <td
                      className={cn(
                        'px-2 py-2 text-style-pre-caption-03',
                        off && 'text-text-tertiary',
                      )}
                    >
                      {form.ncvEnabled ?
                        words.formulaWithNcv(gas)
                      : words.formulaWithoutNcv(gas)}
                    </td>
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
            id={fieldId('note')}
            value={form.note}
            maxLength={NOTE_MAX}
            disabled={readOnly}
            onChange={(event) => change({ note: event.target.value })}
          />,
        )}
        {line && (
          <p
            role="alert"
            data-testid="factor-line"
            className="m-0 text-style-pre-caption-03 text-support-error-accent"
          >
            {line}
          </p>
        )}
      </div>;

  return (
    <>
      <Dialog
        open
        onOpenChange={(open) => {
          if (!open) close();
        }}
      >
        <DialogContent
          size="lg"
          data-testid="factor-dialog"
          data-mode={mode}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (returnFocus?.isConnected) returnFocus.focus();
          }}
        >
          <DialogTitle className="text-style-pre-heading-02">
            {title}
          </DialogTitle>
          {body}
          <DialogFooter>
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              disabled={saving}
              onClick={close}
            >
              {mode === 'view' ? words.close : words.cancel}
            </Button>
            {mode === 'view' ?
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                disabled={typeof loaded !== 'object'}
                onClick={() => setMode('edit')}
              >
                {words.edit}
              </Button>
            : <Button
                variant="solidBlack"
                shape="round"
                size="md"
                loading={saving}
                onClick={() => void save()}
              >
                {words.save}
              </Button>
            }
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {leaving && (
        <ConfirmDialog
          title={words.leaveConfirm}
          cancel={words.stay}
          confirm={words.leave}
          returnFocus={null}
          testId="factor-leave-dialog"
          onConfirm={onClose}
          onClose={() => setLeaving(false)}
        />
      )}
    </>
  );
}
