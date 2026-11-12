// S19 아래 「자산/시설」 판(밴드 W12-0b1 ③ — 스펙 ② S19 인덱스 정보 판). 새로(leafId null)와 있는 잎 둘 꼴.
//   - 칸: 자산/시설명 및 코드*(드롭다운 — 글은 name, 코드 글자 0) · 단위*(드롭다운 하나 — S12-07, 아래) · 툴팁 내용(1,000자).
//   - S12-07(값 파일 ⑧ — sid:MARC-ENT-644 덧, 디자인 b2): 단위는 드롭다운 하나 · 종류 이름이 묶음 머리(<optgroup>, 서버 차례) · 빈 값 「선택안함」 ·
//     머리 옆 ⓘ 툴팁. 종류는 고른 단위가 든 묶음에서 읽는다(값 = 「종류|단위」 — 계약 칸 그대로). 지금 값이 목록에 없으면 그 글자 그대로 한 줄 더함.
//   - 있는 잎: 배출계수 표(체크·배출계수명·투입량 기준단위·기본 배출계수 토글·행 끝 >) · 「삭제」(체크, 확인 창) · 「추가」(→ S20) ·
//     행 > · 행 전체·Tab+Enter → S20 읽기 꼴(sid:MARC-ENT-599). 기본 토글은 defaultFactorId 를 판 [저장]과 함께 보낸다(토글만 바꿔도 저장 켜짐).
//     계수 0 → 빈 상태 + 판 위 경고(스펙 글). 판 머리 「삭제」(이 잎 — 확인 창)·「취소」(바꾼 것 버림)·「저장」(고친 것 없으면 흐림).
//   - 새로: [저장]은 늘 켬 → POST facilities 201 → onCreated(그 잎을 고름).
//   - 저장 거절: 409 IN_USE → 잎 PUT 글 · 422 fields.facilityCodeId → 같은 코드 글 · fields.defaultFactorId → 다시 읽음 + 한 줄.
import { useEffect, useState } from 'react';
import type { KeyboardEvent, MouseEvent } from 'react';

import {
  ChevronRightIcon,
  CircleWarningIcon,
  InformationIcon,
  PlusIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Switch } from '@marcspon/ui/components/switch';
import { Textarea } from '@marcspon/ui/components/textarea';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  GhgPoolAdminPort,
  PoolWrite,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  emptyFacilityForm,
  facilityChanged,
  facilityCreateDraft,
  facilityFormOf,
  facilitySaveDraft,
  validateFacility,
} from '../../../entities/ghg/model/index.ts';
import type {
  FacilityCode,
  FacilityForm,
  PoolFacility,
  PoolOptions,
} from '../../../entities/ghg/model/index.ts';
import { Button, buttonVariants } from '../../../shared/ui/button/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import {
  ROW_FOCUS,
  ROW_HOVER,
  isActivationKey,
  isFromControl,
} from '../../../shared/ui/data-table/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { toast } from '../../../shared/ui/toast/index.ts';
import { FactorDialog } from './FactorDialog.tsx';
import { Choice, ConfirmDialog, FieldError } from './parts.tsx';

/** GX2 S12-07: 「자산/시설명 및 코드*」가 한 줄로(판 S12-07 기본 정보 칸) — 이 판의 라벨 칸만 160 → 200 · 줄바꿈 0. */
const LEAF_LABEL = cn(FORM_LABEL_CLASS, 'w-[200px] whitespace-nowrap');

const words = GHG_TEXT.pool;
/** S12-07 단위 고르기 값 = 「종류|단위」(종류는 고른 묶음에서 — 단위 이름에 「|」 0). */
const UNIT_SEP = '|';
const unitValue = (kind: string, unit: string) =>
  kind === '' || unit === '' ? '' : `${kind}${UNIT_SEP}${unit}`;
/** 서버 TOOLTIP_MAX. */
const TOOLTIP_MAX = 1000;

export interface FacilityPanelProps {
  port: GhgPoolAdminPort;
  options: PoolOptions;
  codes: readonly FacilityCode[];
  /** 있는 잎의 id. null 이면 새 잎. */
  leafId: string | null;
  /** 잎의 부모(배출활동) id. */
  parentId: string;
  thisYear: number;
  onCreated(id: string): void;
  onSaved(): void;
  onDeleted(): void;
  onCancelNew(): void;
}

type Line =
  | 'inUseSave'
  | 'codeTaken'
  | 'defaultGone'
  | 'inUseDelete'
  | 'notFound'
  | 'writeFailed'
  | null;
/** 누를 수 있는 줄(DataTable 과 같은 셋 — 커서·hover·초점). 누를 수 없는 줄은 셋 다 없다(결정 599 규칙 2). */
const CLICKABLE_ROW = ['cursor-pointer', ROW_HOVER, ROW_FOCUS];

/**
 * 누를 수 있는 줄 — 공용 clickableRowProps(shared/ui/data-table hooks/useDataTable.ts)와 같은 갈래(칸 안 컨트롤은 무시,
 * Enter·Space 는 줄 자신에 초점이 있을 때만, preventDefault). 창을 닫으면 초점을 돌릴 자리로 그 줄(<tr>)을 넘긴다.
 */
function rowOpener(open: (from: HTMLElement) => void) {
  return {
    tabIndex: 0 as const,
    onClick: (event: MouseEvent<HTMLElement>) => {
      if (isFromControl(event.target, event.currentTarget)) return;
      open(event.currentTarget);
    },
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if (!isActivationKey(event.key)) return;
      if (event.target !== event.currentTarget) return;
      event.preventDefault();
      open(event.currentTarget);
    },
  };
}
type Confirm = { kind: 'facility' | 'factors'; from: HTMLElement } | null;
type FactorModal = { factorId: string | null; from: HTMLElement } | null;

const headClass =
  'h-10 whitespace-nowrap border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
const cellClass =
  'h-12 border-0 border-b border-solid border-border-tertiary px-4 text-left';

export function FacilityPanel({
  port,
  options,
  codes,
  leafId,
  parentId,
  thisYear,
  onCreated,
  onSaved,
  onDeleted,
  onCancelNew,
}: FacilityPanelProps) {
  const [facility, setFacility] = useState<
    PoolFacility | 'loading' | 'failed' | null
  >(leafId === null ? null : 'loading');
  const [base, setBase] = useState<FacilityForm>(emptyFacilityForm);
  const [form, setForm] = useState<FacilityForm>(emptyFacilityForm);
  const [problem, setProblem] = useState<'facilityCodeId' | 'unit' | null>(
    null,
  );
  const [line, setLine] = useState<Line>(null);
  const [saving, setSaving] = useState(false);
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [factorModal, setFactorModal] = useState<FactorModal>(null);

  const reload = async (id: string) => {
    const out = await port.getFacility(id);
    if (out.kind !== 'ok') return setFacility('failed');
    const next = facilityFormOf(out.value);
    setFacility(out.value);
    setBase(next);
    setForm(next);
    setPicked(new Set());
  };
  useEffect(() => {
    if (leafId !== null) void reload(leafId);
    // reload 는 port·leafId 로만 바뀐다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, leafId]);

  const change = (next: Partial<FacilityForm>) => {
    setForm((before) => ({ ...before, ...next }));
    setLine(null);
  };

  const failLine = (outcome: PoolWrite<unknown>): Line => {
    if (outcome.kind !== 'rejected') return 'writeFailed';
    if (outcome.code === 'IN_USE') return 'inUseSave';
    if (outcome.code === 'NOT_FOUND') return 'notFound';
    if (outcome.code === 'VALIDATION_ERROR') {
      if ('facilityCodeId' in outcome.fields) return 'codeTaken';
      if ('defaultFactorId' in outcome.fields) return 'defaultGone';
    }
    return 'writeFailed';
  };

  const save = async () => {
    if (saving) return;
    setLine(null);
    const missing = validateFacility(form);
    setProblem(missing);
    if (missing) {
      document
        .getElementById(missing === 'unit' ? 'ghg-leaf-unit' : 'ghg-leaf-code')
        ?.focus();
      return;
    }
    setSaving(true);
    if (leafId === null) {
      const outcome = await port.createFacility(
        facilityCreateDraft(parentId, form),
      );
      setSaving(false);
      if (outcome.kind === 'ok') return onCreated(outcome.value.id);
      return setLine(failLine(outcome));
    }
    const outcome = await port.saveFacility(
      leafId,
      facilitySaveDraft(base, form),
    );
    setSaving(false);
    if (outcome.kind === 'ok') {
      const next = facilityFormOf(outcome.value);
      setFacility(outcome.value);
      setBase(next);
      setForm(next);
      toast({ message: words.saved }); // S12-04: 공용 토스트(host 는 GhgIndexPoolScreen)
      onSaved();
      return;
    }
    const why = failLine(outcome);
    setLine(why);
    if (why === 'defaultGone' || why === 'notFound') {
      await reload(leafId);
      setLine(why);
    }
  };

  const removeConfirmed = async () => {
    if (!confirm || leafId === null) return;
    setSaving(true);
    if (confirm.kind === 'facility') {
      const outcome = await port.deleteNodes([leafId]);
      setSaving(false);
      setConfirm(null);
      if (outcome.kind === 'ok') return onDeleted();
      setLine(
        outcome.kind === 'rejected' && outcome.code === 'IN_USE' ?
          'inUseDelete'
        : failLine(outcome),
      );
      return;
    }
    const outcome = await port.deleteFactors([...picked]);
    setSaving(false);
    setConfirm(null);
    await reload(leafId);
    if (outcome.kind !== 'ok')
      setLine(
        outcome.kind === 'rejected' && outcome.code === 'IN_USE' ?
          'inUseDelete'
        : failLine(outcome),
      );
  };

  if (facility === 'loading')
    return (
      <Card data-testid="facility-panel">
        <LoadSkeleton label={GHG_TEXT.common.loading} />
      </Card>
    );
  if (facility === 'failed')
    return (
      <Card data-testid="facility-panel">
        <PageInfo
          role="alert"
          tone="error"
          icon={<CircleWarningIcon aria-hidden />}
        >
          {words.loadFailed}
        </PageInfo>
      </Card>
    );

  const isNew = leafId === null;
  const factors = facility?.factors ?? [];
  const canSave = isNew || facilityChanged(base, form);
  const unitPicked = unitValue(form.unitKind, form.unit);
  const unitListed = options.units.some(
    (one) => one.kind === form.unitKind && one.units.includes(form.unit),
  );
  const unitEmpty = options.units.every((one) => one.units.length === 0);
  const allPicked =
    factors.length > 0 && factors.every((f) => picked.has(f.id));

  return (
    <Card data-testid="facility-panel" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="m-0 text-style-pre-heading-02 text-text-primary">
          {isNew ? words.facilityTitleNew : facility!.facilityName}
        </h2>
        <div data-testid="facility-actions" className="flex items-center gap-2">
          {!isNew && (
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              disabled={saving}
              onClick={(event) =>
                setConfirm({ kind: 'facility', from: event.currentTarget })
              }
            >
              {words.removeFacility}
            </Button>
          )}
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            disabled={saving}
            onClick={() => {
              if (isNew) return onCancelNew();
              setForm(base);
              setProblem(null);
              setLine(null);
            }}
          >
            {words.cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            loading={saving}
            disabled={!canSave}
            onClick={() => void save()}
          >
            {words.save}
          </Button>
        </div>
      </div>
      {!isNew && factors.length === 0 && (
        <PageInfo
          tone="caution"
          icon={<CircleWarningIcon aria-hidden />}
          data-testid="no-default"
        >
          {words.noDefault}
        </PageInfo>
      )}
      <p
        role="alert"
        data-testid="facility-line"
        className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
      >
        {line && (
          <>
            <CircleWarningIcon aria-hidden />
            {words[line]}
          </>
        )}
      </p>
      <div className={FORM_ROWS_CLASS}>
        <div className={FORM_ROW_CLASS}>
          <label htmlFor="ghg-leaf-code" className={LEAF_LABEL}>
            {words.facilityCode}
            <RequiredMark />
          </label>
          <div className={cn(FORM_VALUE_CLASS, 'flex-col gap-1')}>
            <Choice
              id="ghg-leaf-code"
              label={words.facilityCode}
              value={form.facilityCodeId}
              placeholder={words.codePlaceholder}
              options={codes.map((code) => ({
                value: code.id,
                label: code.name,
              }))}
              disabled={saving}
              invalid={problem === 'facilityCodeId'}
              onChange={(value) => {
                change({ facilityCodeId: value });
                setProblem(null);
              }}
            />
            <FieldError id="ghg-leaf-code-error">
              {problem === 'facilityCodeId' ? words.required : null}
            </FieldError>
          </div>
        </div>
        <div className={FORM_ROW_CLASS}>
          <div className={cn(LEAF_LABEL, 'gap-1')}>
            <label htmlFor="ghg-leaf-unit" className="inline-flex items-center">
              {words.unit}
              <RequiredMark />
            </label>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    data-testid="ghg-leaf-unit-info"
                    aria-label={words.unitInfoLabel}
                    aria-describedby="ghg-leaf-unit-info-text"
                    className="inline-flex size-4 cursor-pointer items-center justify-center border-0 bg-transparent p-0 text-text-tertiary focus-visible:outline-2"
                  >
                    <InformationIcon aria-hidden className="size-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>{words.unitInfo}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <span id="ghg-leaf-unit-info-text" className="sr-only">
              {words.unitInfo}
            </span>
          </div>
          <div className={cn(FORM_VALUE_CLASS, 'flex-col gap-1')}>
            <NativeSelect
              id="ghg-leaf-unit"
              value={unitPicked}
              disabled={saving || (unitEmpty && unitPicked === '')}
              aria-invalid={problem === 'unit' || undefined}
              onChange={(event) => {
                const [kind = '', unit = ''] =
                  event.target.value === '' ?
                    []
                  : event.target.value.split(UNIT_SEP);
                change({ unitKind: kind, unit });
                setProblem(null);
              }}
              className="w-full min-w-0"
            >
              <option value="">{words.unitNone}</option>
              {unitPicked !== '' && !unitListed && (
                <option value={unitPicked}>{form.unit}</option>
              )}
              {options.units
                .filter((one) => one.units.length > 0)
                .map((one) => (
                  <optgroup
                    key={one.kind}
                    label={GHG_TEXT.pool.unitKinds[one.kind] ?? one.kind}
                  >
                    {one.units.map((unit) => (
                      <option key={unit} value={unitValue(one.kind, unit)}>
                        {unit}
                      </option>
                    ))}
                  </optgroup>
                ))}
            </NativeSelect>
            <FieldError id="ghg-leaf-unit-error">
              {problem === 'unit' ? words.required : null}
            </FieldError>
          </div>
        </div>
        <div className={FORM_ROW_CLASS}>
          <label htmlFor="ghg-leaf-tooltip" className={LEAF_LABEL}>
            {words.tooltip}
          </label>
          <div className={FORM_VALUE_CLASS}>
            <Textarea
              id="ghg-leaf-tooltip"
              value={form.tooltip}
              maxLength={TOOLTIP_MAX}
              placeholder={words.tooltipPlaceholder}
              disabled={saving}
              onChange={(event) => change({ tooltip: event.target.value })}
            />
          </div>
        </div>
      </div>
      {!isNew && (
        <section
          className="flex flex-col gap-3"
          aria-labelledby="ghg-leaf-factors"
        >
          <div className="flex items-center justify-between gap-3">
            <h3
              id="ghg-leaf-factors"
              className="m-0 text-style-pre-heading-02 text-text-primary"
            >
              {words.factors}
            </h3>
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-disabled={picked.size === 0 || undefined}
                className={cn(
                  buttonVariants({ variant: 'outlineGrey', size: 'sm' }),
                  picked.size === 0 && 'cursor-not-allowed opacity-40',
                )}
                onClick={(event) => {
                  if (picked.size > 0)
                    setConfirm({ kind: 'factors', from: event.currentTarget });
                }}
              >
                {words.removeFactors}
              </button>
              <Button
                variant="outlineGrey"
                size="sm"
                onClick={(event) =>
                  setFactorModal({ factorId: null, from: event.currentTarget })
                }
              >
                <PlusIcon aria-hidden />
                {words.addFactor}
              </Button>
            </div>
          </div>
          <table
            aria-labelledby="ghg-leaf-factors"
            className="w-full table-fixed border-separate border-spacing-0 text-style-pre-body-06 text-text-secondary"
          >
            <colgroup>
              <col style={{ width: 48 }} />
              <col />
              <col style={{ width: 160 }} />
              <col style={{ width: 120 }} />
              <col style={{ width: 64 }} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className={headClass}>
                  <Checkbox
                    aria-label={words.selectAll}
                    checked={
                      allPicked ? true
                      : picked.size > 0 ?
                        'indeterminate'
                      : false
                    }
                    disabled={factors.length === 0}
                    onCheckedChange={(checked) =>
                      setPicked(
                        checked === true ?
                          new Set(factors.map((f) => f.id))
                        : new Set(),
                      )
                    }
                  />
                </th>
                <th scope="col" className={headClass}>
                  {words.factorColumns.name}
                </th>
                <th scope="col" className={headClass}>
                  {words.factorColumns.inputUnit}
                </th>
                <th scope="col" className={headClass}>
                  {words.factorColumns.isDefault}
                </th>
                <th scope="col" className={headClass}>
                  <span className="sr-only">{words.factorColumns.open}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {factors.length === 0 ?
                <tr>
                  <td
                    colSpan={5}
                    className={cn(cellClass, 'text-center text-text-tertiary')}
                  >
                    {words.noFactors}
                  </td>
                </tr>
              : factors.map((factor) => (
                  <tr
                    key={factor.id}
                    data-factor-id={factor.id}
                    aria-label={factor.name}
                    className={cn(CLICKABLE_ROW)}
                    // GX2 D3(sid:MARC-ISSUE-461): 행 전체(클릭·Tab+Enter)가 S20 읽기 꼴을 연다 — 체크·토글·> 는 제 일.
                    // 닫으면 초점은 연 그 행으로(밴드 RC1, sid:MARC-ENT-599).
                    {...rowOpener((from) =>
                      setFactorModal({ factorId: factor.id, from }),
                    )}
                  >
                    <td className={cellClass}>
                      <Checkbox
                        aria-label={words.selectFactor(factor.name)}
                        checked={picked.has(factor.id)}
                        onCheckedChange={(checked) =>
                          setPicked((before) => {
                            const next = new Set(before);
                            if (checked === true) next.add(factor.id);
                            else next.delete(factor.id);
                            return next;
                          })
                        }
                      />
                    </td>
                    <td className={cn(cellClass, 'break-all')}>
                      {factor.name}
                    </td>
                    <td className={cellClass}>{factor.inputUnit.unit}</td>
                    <td className={cellClass}>
                      <Switch
                        aria-label={words.defaultToggle(factor.name)}
                        checked={form.defaultFactorId === factor.id}
                        disabled={saving}
                        onCheckedChange={(checked) => {
                          // 늘 정확히 하나 켜짐 — 켠 줄로 옮긴다(끄기는 받지 않는다).
                          if (checked) change({ defaultFactorId: factor.id });
                        }}
                      />
                    </td>
                    <td className={cn(cellClass, 'text-center')}>
                      <button
                        type="button"
                        aria-label={words.openFactor(factor.name)}
                        data-factor-open=""
                        className="inline-flex size-8 items-center justify-center rounded-control border-0 bg-transparent p-0 text-text-tertiary [&_svg]:size-4"
                        onClick={(event) =>
                          setFactorModal({
                            factorId: factor.id,
                            from: event.currentTarget,
                          })
                        }
                      >
                        <ChevronRightIcon aria-hidden />
                      </button>
                    </td>
                  </tr>
                ))
              }
            </tbody>
          </table>
        </section>
      )}
      {confirm && (
        <ConfirmDialog
          title={
            confirm.kind === 'facility' ?
              words.deleteFacilityConfirm
            : words.deleteFactorsConfirm
          }
          cancel={words.cancel}
          confirm={words.confirmDelete}
          returnFocus={confirm.from}
          testId="facility-delete-dialog"
          busy={saving}
          onConfirm={() => void removeConfirmed()}
          onClose={() => setConfirm(null)}
        />
      )}
      {factorModal && leafId !== null && (
        <FactorDialog
          port={port}
          options={options}
          facilityId={leafId}
          factorId={factorModal.factorId}
          thisYear={thisYear}
          returnFocus={factorModal.from}
          onSaved={() => {
            setFactorModal(null);
            toast({ message: words.saved });
            void reload(leafId);
          }}
          onClose={() => setFactorModal(null)}
        />
      )}
    </Card>
  );
}
