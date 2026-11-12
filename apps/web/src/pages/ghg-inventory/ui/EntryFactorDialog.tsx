// S8 온실가스 종류별 배출계수 보기(밴드 W12-1b ② — 스펙 ① S8, 28556:28818). 보기는 두 역할 다 읽기 전용.
//   W12-3 ③: 아래 [배출계수 수정](edit prop — 부르는 쪽이 운영 관리자·저장된 행에서 연 때만 준다, 인덱스 기본 계수 보기는 0 · sid:MARC-ENT-469 2).
//   잠김·쓰는 중 끔(edit.disabled) · 그 행 고친 동안 끔 + 「저장한 뒤 바꿀 수 있어요」(edit.dirty — Q7). 누르면 S9(부르는 쪽).
//   보여 주는 계수 = row.factor ?? index.factor(부르는 쪽이 고른다). 직접입력(customId)은 판이 없어 기준연도·Tier·비고를 보인다.
//   W12-1c #17·#18(판 S12-03a): 폭 1320 상한 · 라벨 줄 표(라벨 칸 160 · 회색 · 줄 56) · 가스 머리 「포함여부」「온실가스 종류」(W12-1d N2) ·
//   순발열량 기준단위 따로 한 줄 · 포함 = 체크 20 읽기 전용(aria-checked 로 뜻, 켬 주황 · 끔 회색 — W12-1d N2) · 「버전」 · 투입량 기준단위 종류는 한글(pool.unitKinds).
//   S12-03a(e6 ④ — Figma 29429:28054, sid:MARC-ENT-644, 발주서 Q12): 직접입력 계수는 따로 꼴(CustomView) — 제목 줄 오른쪽 [수정](edit 를 받을 때만,
//   solid-black md 80) · 「온실가스 배출량 산식」 + 주황 「*직접입력」 · 배출계수명·투입량 기준단위(필수 점) / 순발열량·순발열량 기준단위(라벨 160, 반반) ·
//   회색 산식 한 줄 · 「기본정보」 가스 표 셋(온실가스 종류·배출계수·GWP, 같은 폭·가운데 — 포함한 가스만) · 「비고」 읽기 상자(비면 「-」). 풀 계수는 위 꼴 그대로.
import { Checkbox } from '@marcspon/ui/components/checkbox';
import { cn } from '@marcspon/ui/lib/utils';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import type {
  EntryCustomFactor,
  EntryFactor,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogCloseIconButton,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { CELL, HEAD_CELL, TABLE } from './entryTable.ts';

const words = GHG_TEXT.entry.factor;
const LABEL = cn(
  CELL,
  'w-40 bg-support-grey-subtle text-style-pre-body-05 text-text-tertiary',
);

/** 포함 체크(W12-1d N2 — 판 S12-03a): 읽기 전용(disabled) 그대로, 켬은 주황 채움 · 끔은 키트 disabled 회색 상자(background-tertiary). */
const INCLUDED =
  'align-middle disabled:cursor-default disabled:data-[state=checked]:border-button-orange disabled:data-[state=checked]:bg-button-orange disabled:data-[state=checked]:text-background-primary';

/** 단위 종류 글(모르는 종류는 글자 그대로). */
export const unitKindText = (kind: string) =>
  GHG_TEXT.pool.unitKinds[kind] ?? kind;

function Field({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <th scope="row" className={cn(LABEL, 'text-left')}>
        {label}
      </th>
      <td className={CELL}>{value}</td>
    </tr>
  );
}

/** S8 [배출계수 수정] — 없으면 단추 0. */
export interface EntryFactorEditControl {
  /** 잠김·쓰는 중. */
  disabled: boolean;
  /** 그 행에 저장 안 한 고침(Q7). */
  dirty: boolean;
  onEdit(): void;
}

/** 직접입력 꼴 라벨 칸(판 `.f12b-kv .k` — 안 여백 8/24 · 필수 점은 칸 오른쪽 끝 · 오른쪽 1px quaternary, 디자인 대조 F3). 풀 계수 보기 LABEL 은 그대로. */
const CUSTOM_LABEL = cn(
  LABEL,
  'border-r border-solid border-border-quaternary px-6',
);

/** 라벨 칸 하나(직접입력 꼴 — 반반 줄). */
function Pair({
  label,
  value,
  required = false,
}: {
  label: string;
  value: string;
  required?: boolean;
}) {
  return (
    <>
      <th scope="row" className={cn(CUSTOM_LABEL, 'text-left')}>
        <span className="flex w-full items-center justify-between">
          {label}
          {required && <RequiredMark />}
        </span>
      </th>
      <td className={CELL}>{value}</td>
    </>
  );
}

/** 묶음 머리 셋(산식·기본정보·비고 — 캔버스 v246 대조, 감독 de 11-10). */
const GROUP_HEAD = 'm-0 text-style-pre-heading-02 text-text-primary';

/** S12-03a 저장 뒤 창의 몸(직접입력 계수). */
function CustomView({
  factor,
  ncv,
  ncvUnit,
  formula,
}: {
  factor: EntryCustomFactor;
  ncv: string;
  ncvUnit: string;
  formula: string;
}) {
  const included = factor.gases.filter((gas) => gas.enabled);
  // 판 `.f12b-oth` 높이 40 · `.f12b-otd` 아래 선 tertiary(디자인 대조 F4).
  const center = cn(HEAD_CELL, 'h-10 text-center');
  const cell = cn(CELL, 'border-border-tertiary text-center');
  return (
    <>
      <section
        className="flex flex-col gap-2"
        data-testid="entry-factor-formula"
      >
        <h3 className={cn(GROUP_HEAD, 'flex items-center gap-2')}>
          {words.formulaHead}
          <span
            data-testid="entry-factor-custom-mark"
            className="text-style-pre-body-04 text-text-brand"
          >
            {words.customMark}
          </span>
        </h3>
        <table
          className={`${TABLE} w-full table-fixed border-0 border-t border-solid border-border-quaternary`}
          data-testid="entry-factor-fields"
        >
          <colgroup>
            <col className="w-40" />
            <col />
            <col className="w-40" />
            <col />
          </colgroup>
          <tbody>
            <tr>
              <Pair label={words.name} value={factor.name} required />
              <Pair
                label={words.inputUnit}
                value={`${unitKindText(factor.inputUnit.kind)} · ${factor.inputUnit.unit}`}
                required
              />
            </tr>
            <tr>
              <Pair label={words.ncv} value={ncv} />
              <Pair label={words.ncvUnit} value={ncvUnit} />
            </tr>
          </tbody>
        </table>
        <p
          data-testid="entry-factor-formula-text"
          className="m-0 text-style-pre-body-05 text-text-tertiary"
        >
          {formula}
        </p>
      </section>
      <section
        className="flex flex-col gap-2"
        data-testid="entry-factor-basics"
      >
        <h3 className={GROUP_HEAD}>{words.basics}</h3>
        <table className={`${TABLE} w-full table-fixed`}>
          <thead>
            <tr>
              <th scope="col" className={center}>
                {words.gas}
              </th>
              <th scope="col" className={center}>
                {`${words.value} (${factor.factorUnit})`}
              </th>
              <th scope="col" className={center}>
                {words.gwp}
              </th>
            </tr>
          </thead>
          <tbody>
            {included.map((gas) => (
              <tr key={gas.gas} data-testid={`entry-gas-${gas.gas}`}>
                <td className={cell}>{gas.gas}</td>
                <td className={cn(cell, 'tabular-nums')}>
                  {gas.factor ?? words.empty}
                </td>
                <td className={cn(cell, 'tabular-nums')}>
                  {gas.gwp ?? words.empty}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="flex flex-col gap-2">
        <h3 className={GROUP_HEAD}>{words.note}</h3>
        <div
          data-testid="entry-factor-note"
          className="box-border min-h-14 whitespace-pre-wrap rounded-component border border-solid border-border-tertiary px-4 py-3 text-style-pre-body-06 text-text-tertiary"
        >
          {factor.note || words.empty}
        </div>
      </section>
    </>
  );
}

export function EntryFactorDialog({
  factor,
  edit = null,
  onClose,
}: {
  factor: EntryFactor | EntryCustomFactor;
  edit?: EntryFactorEditControl | null;
  onClose(): void;
}) {
  const custom = 'customId' in factor ? factor : null;
  // GX2 S12-03a: 켰으면 값만(「켬」은 관리자 스위치 말), 껐으면 「쓰지 않음」.
  const ncv = factor.ncvEnabled ? (factor.ncv ?? words.empty) : words.ncvOff;
  // 판 S12-03a 산식 줄: 포함한 가스만 「+」로 잇는다. 포함 0 이면 「-」.
  const included = factor.gases
    .filter((gas) => gas.enabled)
    .map((gas) => gas.gas);
  const formula =
    included.length > 0 ?
      words.formulaText(included, factor.ncvEnabled)
    : words.empty;
  const ncvUnit =
    factor.ncvEnabled && factor.ncvUnit ?
      `${unitKindText(factor.ncvUnit.kind)} · ${factor.ncvUnit.unit}`
    : words.empty;
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="lg"
        data-testid="entry-factor"
        className={cn(
          'w-[min(1320px,calc(100vw-64px))]',
          // 판 `.f-modal.f12d-gap32`: 저장 뒤 창(직접입력)만 제목↔산식↔기본정보↔비고 32(디자인 대조 F2) — 풀 계수 보기는 그대로.
          custom && 'gap-8',
        )}
      >
        <DialogCloseIconButton aria-label={GHG_TEXT.entry.close} />
        {custom ?
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-4 pr-4">
              <DialogTitle className="text-style-pre-display-04">
                {words.title}
              </DialogTitle>
              {edit && (
                <Button
                  variant="solidBlack"
                  shape="round"
                  size="md"
                  className="min-w-20"
                  data-testid="entry-factor-edit-open"
                  disabled={edit.disabled || edit.dirty}
                  onClick={edit.onEdit}
                >
                  {GHG_TEXT.entry.factorEdit.cell}
                </Button>
              )}
            </div>
            {edit?.dirty && (
              <p
                data-testid="entry-factor-edit-dirty"
                className="m-0 text-right text-style-pre-caption-03 text-text-tertiary"
              >
                {GHG_TEXT.entry.factorEdit.dirty}
              </p>
            )}
          </div>
        : <DialogTitle className="text-style-pre-heading-02">
            {words.title}
          </DialogTitle>
        }
        {custom ?
          <CustomView
            factor={custom}
            ncv={ncv}
            ncvUnit={ncvUnit}
            formula={formula}
          />
        : <>
            <table
              className={`${TABLE} w-full table-fixed`}
              data-testid="entry-factor-fields"
            >
              <colgroup>
                <col className="w-40" />
                <col />
              </colgroup>
              <tbody>
                <Field label={words.source} value={factor.source} />
                <Field
                  label={words.version}
                  value={words.versionValue((factor as EntryFactor).version)}
                />
                <Field
                  label={words.inputUnit}
                  value={`${unitKindText(factor.inputUnit.kind)} · ${factor.inputUnit.unit}`}
                />
                <Field label={words.ncv} value={ncv} />
                <Field label={words.ncvUnit} value={ncvUnit} />
                <Field label={words.formula} value={formula} />
              </tbody>
            </table>
            <table className={`${TABLE} w-full`}>
              <thead>
                <tr>
                  <th scope="col" className={HEAD_CELL}>
                    {words.included}
                  </th>
                  <th scope="col" className={HEAD_CELL}>
                    {words.gas}
                  </th>
                  <th scope="col" className={HEAD_CELL}>
                    {`${words.value} (${factor.factorUnit})`}
                  </th>
                  <th scope="col" className={HEAD_CELL}>
                    {words.gwp}
                  </th>
                </tr>
              </thead>
              <tbody>
                {factor.gases.map((gas) => (
                  <tr key={gas.gas} data-testid={`entry-gas-${gas.gas}`}>
                    <td className={CELL}>
                      <Checkbox
                        size="lg"
                        variant="orange"
                        disabled
                        className={INCLUDED}
                        checked={gas.enabled}
                        aria-label={words.includedLabel(gas.gas)}
                      />
                    </td>
                    <td className={CELL}>{gas.gas}</td>
                    <td className={cn(CELL, 'tabular-nums')}>
                      {gas.factor ?? words.empty}
                    </td>
                    <td className={cn(CELL, 'tabular-nums')}>
                      {gas.gwp ?? words.empty}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        }
        {!custom && edit && (
          <DialogFooter className="flex-col items-center pt-0">
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              data-testid="entry-factor-edit-open"
              disabled={edit.disabled || edit.dirty}
              onClick={edit.onEdit}
            >
              {GHG_TEXT.entry.factorEdit.button}
            </Button>
            {edit.dirty && (
              <p
                data-testid="entry-factor-edit-dirty"
                className="m-0 text-style-pre-caption-03 text-text-tertiary"
              >
                {GHG_TEXT.entry.factorEdit.dirty}
              </p>
            )}
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
