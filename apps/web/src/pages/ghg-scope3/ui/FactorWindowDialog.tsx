// S3-12 그룹별 배출계수 창(밴드 S3W4 ② — 판 캔버스 v214 S3-12_r2, 값은 S3W4-figma-values.md) + S3-12a·b 수정 꼴(밴드 S3W3c2 ① — S3W3c-figma-values.md ①·③, 보드 S3-12a_r2·S3-12b_r2).
// 틀 960 · 안쪽 32 · 섹션 사이 32 · 모서리 16(공용 DialogContent 의 lg 를 너비만 덮는다 — Q8). 머리는 닫기 줄 → 16 → 제목 줄 36.
// 보기 꼴: 받은 결과의 줄을 그린다(요청 0). 제목 줄 오른쪽 [수정] btn--md 80×36. 고친 줄은 제목·값·출처가 사건 값이고 산식은 「-」(S3W3c1).
// 수정 꼴: 그 자리 [취소][저장] · 기본 정보 · 탄소기원(있는 줄만 — 읽기 글, C2) · 적용 배출계수(AI 원안 — C1) · 추천(구매 줄만) · 직접입력. 라디오 하나로 묶는다.
//   직접입력 칸은 늘 켜 둔다 — 글자를 넣으면 라디오가 직접입력으로 옮고(R3), 검사는 직접입력일 때만(부르는 쪽 useFactorEdit). 단위 입력 칸 없음 — 머리 글에 그 줄 계수 단위(customFactorHead). FCF 입력 0.
// [수정] 막힘(값 파일 ③ — 하나만): 잠김은 감싼 span 툴팁 · C12·계수 없음은 왼쪽 8 에 글 · 보낼 줄·실행 없음은 막기만. 409 factor_not_editable 뒤는 창 머리 아래 alert(C9 — 그 창이 열린 동안 막음).
// 상태는 이 창이 쥐지 않는다 — useFactorEdit 가 연 때 얼린 줄 사진과 함께 준다(누른 때 다시 읽지 않는다).
// 닫기는 X·Esc·바깥 누름(공용 Dialog 기본 — 수정 꼴이면 쓴 것 버림). 요청 중에는 닫지 않는다. 닫을 때 초점은 returnFocus 가 정한다.
// 사유 창이 떠 있는 동안·막 닫힌 그 누름은 이 창의 바깥 누름이 아니다(형제 Radix 창 둘이 한 pointerdown 을 차례로 받으면 아래 창까지 닫혔다 — 부하 아래 e2e 에서 잼).
// 틀은 넘치지 않고(overflow-hidden) 머리 아래 몸만 민다(GX3 ②).
// 배출량 산식은 서버 글의 수식 마디만(숫자 자취 「= 9.1e+06 × …」는 뺀다 — GX1 L-4, formulaText), 생물기원 산식은 서버 칸이 없어 값 「-」(Q5).
// C12 처리방법별 비중 표(밴드 S3Q1 ② — S3Q1-figma-values ②, S3-12c 보기만): 서버 treatments 가 있는 줄만 5열(타이틀·처리방법·비중·배출계수·출처)
//   + 합계 줄(서버 shareTotal·가중 계수 그대로). 라디오·직접입력·[취소][저장] 0([수정]은 C12 막힘 그대로). 칸 없는 옛 결과는 아래 한 줄 표 그대로.
import type { ReactNode, Ref } from 'react';

import {
  CircleCloseIcon,
  CloseIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import {
  RadioGroup,
  RadioGroupItem,
} from '@marcspon/ui/components/radio-group';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  FACTOR_CUSTOM_FIELDS,
  aiRowOf,
  factorWindowOf,
  recommendable,
  recommendationsOf,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  FactorBlock,
  FactorCustomDraft,
  FactorCustomField,
  FactorPick,
  FactorWindow,
  ResultRow,
  TreatmentTable,
} from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogCloseIconButton,
  DialogContent,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { AiGroupStar } from './AiGroupStar.tsx';
import { SourceText } from './SourceText.tsx';
import {
  baseUnitText,
  customFactorHead,
  factorNumberText,
  fcfText,
  formulaText,
  treatmentShareText,
  windowFactorText,
} from './detailText.ts';

const words = S3_TEXT.detail.factorWindow;
const edit = S3_TEXT.detail.factorEdit;
const EMPTY = S3_TEXT.result.empty;

const KV_ROW =
  'm-0 flex w-full border-0 border-t border-solid border-border-quaternary';
const KV_CELL =
  'm-0 box-border flex items-center border-0 border-b border-solid border-border-quaternary py-2';
const KV_KEY = `${KV_CELL} shrink-0 border-r bg-support-grey-subtle px-6 text-style-pre-body-05 text-text-tertiary`;
const KV_VALUE = `${KV_CELL} min-h-14 min-w-0 break-words bg-background-primary px-4 text-style-pre-body-06 text-text-secondary`;
const TABLE_HEAD =
  'box-border h-10 border-0 border-b border-solid border-border-tertiary bg-support-grey-subtle px-4 py-2 text-center text-style-pre-body-05 text-text-tertiary';
const TABLE_CELL =
  'box-border h-14 break-words border-0 border-b border-solid border-border-quaternary px-4 py-2 text-center text-style-pre-body-06 text-text-secondary';
/** C12 처리방법 표의 rowspan 두 칸(타이틀·출처): 위 맞춤 + 위 여백 16(시안 S3-12c r3 · 밴드 S3Q2 · c3 11-11). TABLE_CELL 의 py-2 위를 pt-4 가 덮는다. */
const SPAN_TOP = 'align-top pt-4';
/** 라디오 칸 52(보드 w-52). */
const PICK_CELL = `${TABLE_CELL} w-[52px]`;
/** 직접입력 줄은 칸 위로 붙인다(보드 f-form — 아래 글이 붙어도 줄이 흔들리지 않게). */
const FORM_CELL =
  'box-border break-words border-0 border-b border-solid border-border-quaternary px-4 py-2.5 align-top text-style-pre-body-06 text-text-secondary';

const pickValue = (pick: FactorPick) =>
  pick.choice === 'recommended' ? `rank:${pick.rank}` : pick.choice;

/** 수정 꼴의 상태와 손잡이(useFactorEdit 가 준다). */
export interface FactorEditView {
  mode: 'view' | 'edit';
  /** [수정]을 막는 까닭. */
  block: FactorBlock | null;
  /** 이 창에서 409 factor_not_editable 을 받았다(C9). */
  notEditable: boolean;
  busy: boolean;
  pick: FactorPick;
  draft: FactorCustomDraft;
  /** 칸 아래 글. */
  faults: Partial<Record<FactorCustomField, string>>;
  fieldRef(field: FactorCustomField): Ref<HTMLInputElement>;
  contentRef: Ref<HTMLDivElement>;
  /** 닫힐 때 초점 자리. null 이면 공용 기본, false 면 옮기지 않음(다시 읽은 뒤 부르는 쪽이 옮긴다). */
  returnFocus(): HTMLElement | null | false;
  /** 위 창(사유)이 떠 있거나 막 닫히는 중 — 그 바깥 누름이 이 창까지 닫지 않게(형제 창 둘이 한 누름을 차례로 받는 틈). */
  holdOutside(): boolean;
  onEdit(): void;
  onCancel(): void;
  onSave(): void;
  onPick(pick: FactorPick): void;
  onDraft(field: FactorCustomField, value: string): void;
}

export interface FactorWindowDialogProps {
  /** 연 때 얼린 줄 사진. */
  row: ResultRow;
  edit: FactorEditView;
  onClose(): void;
}

export function FactorWindowDialog({
  row,
  edit: view,
  onClose,
}: FactorWindowDialogProps) {
  const cells = factorWindowOf(row);
  if (cells === null) return null;
  const editing = view.mode === 'edit';
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !view.busy) onClose();
      }}
    >
      <DialogContent
        ref={view.contentRef}
        size="lg"
        aria-describedby={undefined}
        data-testid="s3-factor-window"
        data-mode={view.mode}
        className="w-[960px] gap-8 overflow-hidden"
        onPointerDownOutside={(event) => {
          const target = event.target as Node | null;
          if (
            view.busy ||
            view.holdOutside() ||
            (target !== null && !target.isConnected)
          )
            event.preventDefault();
        }}
        onCloseAutoFocus={(event) => {
          const target = view.returnFocus();
          if (target === null) return;
          event.preventDefault();
          if (target) target.focus();
        }}
      >
        <div className="flex flex-col gap-4">
          <div className="flex justify-end">
            <DialogCloseIconButton
              placement="inline"
              aria-label={words.close}
              disabled={view.busy}
              className="text-text-secondary"
            >
              <CloseIcon aria-hidden className="size-6" />
            </DialogCloseIconButton>
          </div>
          <div className="flex h-9 items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <DialogTitle>{words.title}</DialogTitle>
              {cells.aiGroup && <AiGroupStar />}
            </div>
            {editing ?
              <div className="flex items-center gap-2">
                <Button
                  variant="solidGrey"
                  shape="round"
                  size="md"
                  disabled={view.busy}
                  data-testid="s3-factor-cancel"
                  onClick={view.onCancel}
                >
                  {edit.cancel}
                </Button>
                <Button
                  variant="solidBlack"
                  shape="round"
                  size="md"
                  disabled={view.busy}
                  data-testid="s3-factor-save"
                  onClick={view.onSave}
                >
                  {edit.save}
                </Button>
              </div>
            : <EditButton view={view} />}
          </div>
          {view.notEditable && (
            <p
              role="alert"
              data-testid="s3-factor-not-editable"
              className="m-0 text-style-pre-caption-02 text-text-tertiary"
            >
              {edit.rowNotEditable}
            </p>
          )}
        </div>
        {/* 머리(닫기·제목 줄)는 고정, 몸만 민다(GX1 S3-11b·S3-14 — 긴 창에서 닫기가 위로 잘림). 좌우 4 는 초점 테두리 자리. */}
        <div
          data-testid="s3-factor-window-body"
          className="-mx-1 flex min-h-0 flex-col gap-8 overflow-y-auto px-1"
        >
          <BasicSection cells={cells} />
          {cells.carbon !== null && <CarbonSection carbon={cells.carbon} />}
          {editing ?
            <EditSections row={row} cells={cells} view={view} />
          : <FactorSection cells={cells} />}
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 보기 꼴 [수정]과 막힘 꼴(하나만). */
function EditButton({ view }: { view: FactorEditView }) {
  const { block } = view;
  const disabled = block !== null || view.notEditable;
  const button = (
    <Button
      variant="solidBlack"
      shape="round"
      size="md"
      disabled={disabled}
      data-testid="s3-factor-edit"
      onClick={view.onEdit}
    >
      {edit.edit}
    </Button>
  );
  const note =
    view.notEditable ? null
    : block === 'c12' ? edit.c12
    : block === 'noFactor' ? edit.rowNotEditable
    : null;
  if (block === 'locked' && !view.notEditable)
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span
              tabIndex={0}
              data-testid="s3-factor-locked"
              className="inline-flex"
            >
              {button}
            </span>
          </TooltipTrigger>
          <TooltipContent>{S3_TEXT.rowEdit.locked}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  return (
    <div className="flex items-center gap-2">
      {note !== null && (
        <span
          data-testid="s3-factor-blocked"
          className="text-style-pre-caption-02 text-text-tertiary"
        >
          {note}
        </span>
      )}
      {button}
    </div>
  );
}

function Section({
  title,
  testId,
  children,
}: {
  title: string;
  testId: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={title}
      data-testid={testId}
      className="flex flex-col gap-2"
    >
      <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
        {title}
      </h3>
      {children}
    </section>
  );
}

function BasicSection({ cells }: { cells: FactorWindow }) {
  return (
    <Section title={words.basicTitle} testId="s3-window-basic">
      <dl className={KV_ROW}>
        <dt className={`${KV_KEY} w-40`}>{words.baseUnit}</dt>
        <dd className={`${KV_VALUE} w-[200px] shrink-0 border-r`}>
          {baseUnitText(cells.base) ?? EMPTY}
        </dd>
        <dt className={`${KV_KEY} w-[100px]`}>{words.source}</dt>
        <dd className={`${KV_VALUE} flex-1`}>
          <SourceText source={cells.source} />
        </dd>
      </dl>
      <dl className="m-0 flex flex-col gap-1 text-style-pre-body-06 text-text-tertiary">
        <Formula
          name={words.emission}
          text={
            cells.formula === null ? EMPTY : formulaText(cells.formula) || EMPTY
          }
        />
        {cells.carbon !== null && (
          <Formula name={words.biogenicEmission} text={EMPTY} />
        )}
      </dl>
    </Section>
  );
}

function Formula({ name, text }: { name: string; text: string }) {
  return (
    <div className="flex gap-[15px]">
      <dt className="min-w-[120px] shrink-0 font-bold">{name}</dt>
      <dd className="m-0 min-w-0 break-words font-medium">{text}</dd>
    </div>
  );
}

function CarbonSection({
  carbon,
}: {
  carbon: NonNullable<FactorWindow['carbon']>;
}) {
  return (
    <Section title={words.carbonTitle} testId="s3-window-carbon">
      <dl className={KV_ROW}>
        <dt className={`${KV_KEY} w-20`}>{words.carbonKind}</dt>
        <dd className={`${KV_VALUE} min-h-[82px] w-[133px] shrink-0 border-r`}>
          {carbon.fcf === null ? EMPTY : words.biogenic}
        </dd>
        <dt
          className={`${KV_KEY} w-[150px] flex-col !items-start justify-center`}
        >
          <span>{words.fcf}</span>
          <span>{words.fcfLong}</span>
        </dt>
        <dd
          data-testid="s3-window-fcf"
          className={`${KV_VALUE} w-[133px] shrink-0 border-r`}
        >
          {fcfText(carbon.fcf)}
        </dd>
        <dt className={`${KV_KEY} w-[150px]`}>{words.basis}</dt>
        <dd className={`${KV_VALUE} flex-1`}>{carbon.note ?? EMPTY}</dd>
      </dl>
    </Section>
  );
}

function FactorHead({
  factorHead,
  pick,
}: {
  factorHead: string;
  pick: boolean;
}) {
  return (
    <thead>
      <tr>
        {pick && <th scope="col" className={`${TABLE_HEAD} w-[52px]`} />}
        <th scope="col" className={TABLE_HEAD}>
          {words.columnTitle}
        </th>
        <th scope="col" className={TABLE_HEAD}>
          {factorHead}
        </th>
        <th scope="col" className={TABLE_HEAD}>
          {words.columnSource}
        </th>
      </tr>
    </thead>
  );
}

const TABLE =
  'w-full table-fixed border-collapse border-0 border-t border-solid border-border-tertiary';

/** C12 처리방법별 표(S3Q1). 타이틀·출처는 첫 줄만(rowspan), 합계 줄은 회색 바탕 굵게 · 타이틀·출처 칸 비움. */
function TreatmentSection({
  cells,
  table,
}: {
  cells: FactorWindow;
  table: TreatmentTable;
}) {
  const span = table.lines.length;
  const title = table.title ?? table.code;
  const code = table.title === null ? null : table.code;
  const TOTAL = `${TABLE_CELL} bg-support-grey-subtle !text-style-pre-body-04`;
  return (
    <Section title={words.factorTitle} testId="s3-window-factor">
      <table className={TABLE} data-testid="s3-window-treatments">
        <thead>
          <tr>
            <th scope="col" className={TABLE_HEAD}>
              {words.columnTitle}
            </th>
            <th scope="col" className={`${TABLE_HEAD} w-[145px]`}>
              {words.columnTreatment}
            </th>
            <th scope="col" className={`${TABLE_HEAD} w-20`}>
              {words.columnShare}
            </th>
            <th scope="col" className={TABLE_HEAD}>
              {words.columnFactor(baseUnitText(cells.base))}
            </th>
            <th scope="col" className={TABLE_HEAD}>
              {words.columnSource}
            </th>
          </tr>
        </thead>
        <tbody>
          {table.lines.map((line, index) => (
            <tr key={line.treatment} data-testid="s3-window-treatment">
              {index === 0 && (
                <td
                  rowSpan={span}
                  className={`${TABLE_CELL} border-b-0 ${SPAN_TOP}`}
                >
                  {title === null ?
                    EMPTY
                  : <>
                      <span className="block">{title}</span>
                      {code !== null && (
                        <span className="block" data-testid="s3-window-code">
                          {code}
                        </span>
                      )}
                    </>
                  }
                </td>
              )}
              <td className={TABLE_CELL}>{line.treatment}</td>
              <td className={`${TABLE_CELL} tabular-nums`}>
                {treatmentShareText(line.share)}
              </td>
              <td className={`${TABLE_CELL} tabular-nums`}>
                {windowFactorText(line.factor, cells.base)}
              </td>
              {index === 0 && (
                <td
                  rowSpan={span}
                  className={`${TABLE_CELL} border-b-0 ${SPAN_TOP}`}
                >
                  <SourceText source={cells.source} />
                </td>
              )}
            </tr>
          ))}
          <tr data-testid="s3-window-treatment-total">
            <td className={TOTAL} />
            <td className={TOTAL}>{words.total}</td>
            <td className={`${TOTAL} tabular-nums`}>
              {treatmentShareText(table.total.share)}
            </td>
            <td className={`${TOTAL} tabular-nums`}>
              {windowFactorText(table.total.factor, cells.base)}
            </td>
            <td className={TOTAL} />
          </tr>
        </tbody>
      </table>
    </Section>
  );
}

function FactorSection({ cells }: { cells: FactorWindow }) {
  const { factor } = cells;
  if (cells.treatments !== null)
    return <TreatmentSection cells={cells} table={cells.treatments} />;
  return (
    <Section title={words.factorTitle} testId="s3-window-factor">
      <table className={TABLE}>
        <FactorHead
          factorHead={words.columnFactor(baseUnitText(cells.base))}
          pick={false}
        />
        <tbody>
          {factor === null ?
            <tr>
              <td colSpan={3} className={`${TABLE_CELL} text-text-tertiary`}>
                {words.noFactor}
              </td>
            </tr>
          : <tr>
              <td className={TABLE_CELL}>{factor.title ?? EMPTY}</td>
              <td className={`${TABLE_CELL} tabular-nums`}>
                {windowFactorText(factor.value, cells.base)}
              </td>
              <td className={TABLE_CELL}>
                <SourceText source={cells.source} />
              </td>
            </tr>
          }
        </tbody>
      </table>
    </Section>
  );
}

/** 수정 꼴의 세 섹션. 라디오 하나(적용 1 + 추천 n + 직접 1). */
function EditSections({
  row,
  cells,
  view,
}: {
  row: ResultRow;
  cells: FactorWindow;
  view: FactorEditView;
}) {
  // 적용 칸은 AI 원안(C1 — 서버 applied 는 원안으로 되돌림). 고친 줄도 본문 계수를 그린다.
  const ai = factorWindowOf(aiRowOf(row)) ?? cells;
  const recommendations = recommendationsOf(row);
  const head = words.columnFactor(baseUnitText(cells.base));
  const options: FactorPick[] = [
    { choice: 'applied' },
    ...recommendations.map((_, index) => ({
      choice: 'recommended' as const,
      rank: index + 1,
    })),
    { choice: 'custom' },
  ];
  const unit =
    row.detail.shape === 'basic' ? null : (row.detail.factor?.unit ?? null);
  return (
    <RadioGroup
      value={pickValue(view.pick)}
      onValueChange={(value) => {
        const found = options.find((one) => pickValue(one) === value);
        if (found) view.onPick(found);
      }}
      disabled={view.busy}
      aria-label={edit.pickLabel}
      data-testid="s3-factor-pick"
      className="flex flex-col gap-8"
    >
      <Section title={edit.appliedTitle} testId="s3-factor-applied">
        <table className={TABLE}>
          <FactorHead factorHead={head} pick />
          <tbody>
            <tr>
              <td className={PICK_CELL}>
                <RadioGroupItem
                  value="applied"
                  size="lg"
                  aria-label={edit.pickApplied}
                  data-testid="s3-factor-pick-applied"
                />
              </td>
              <td className={TABLE_CELL}>{ai.factor?.title ?? EMPTY}</td>
              <td className={`${TABLE_CELL} tabular-nums`}>
                {ai.factor === null ?
                  EMPTY
                : windowFactorText(ai.factor.value, cells.base)}
              </td>
              <td className={TABLE_CELL}>
                <SourceText source={ai.source} />
              </td>
            </tr>
          </tbody>
        </table>
      </Section>
      {recommendations.length > 0 && (
        <Section title={edit.recommendedTitle} testId="s3-factor-recommended">
          <table className={TABLE}>
            <FactorHead factorHead={head} pick />
            <tbody>
              {recommendations.map((item, index) => {
                // 순위는 서버 배열 자리 + 1(C12 처분 — 값 null 을 거른 뒤 번호를 매기지 않는다).
                const rank = index + 1;
                return (
                  <tr key={rank} data-testid="s3-factor-recommendation">
                    <td className={PICK_CELL}>
                      <RadioGroupItem
                        value={`rank:${rank}`}
                        size="lg"
                        disabled={!recommendable(item, rank)}
                        aria-label={edit.pickRecommended(rank)}
                        data-testid="s3-factor-pick-rank"
                        data-rank={rank}
                      />
                    </td>
                    <td className={TABLE_CELL}>{item.title}</td>
                    <td className={`${TABLE_CELL} tabular-nums`}>
                      {factorNumberText(item.value)}
                    </td>
                    <td className={TABLE_CELL}>
                      <SourceText source={ai.source} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      )}
      <Section title={edit.customTitle} testId="s3-factor-custom">
        <table className={TABLE}>
          <FactorHead factorHead={customFactorHead(unit, cells.base)} pick />
          <tbody>
            <tr>
              <td className={`${FORM_CELL} w-[52px] text-center`}>
                <span className="inline-flex h-9 items-center">
                  <RadioGroupItem
                    value="custom"
                    size="lg"
                    aria-label={edit.pickCustom}
                    data-testid="s3-factor-pick-custom"
                  />
                </span>
              </td>
              {FACTOR_CUSTOM_FIELDS.map((field) => (
                <td key={field} className={FORM_CELL}>
                  <CustomField field={field} view={view} />
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </Section>
    </RadioGroup>
  );
}

function CustomField({
  field,
  view,
}: {
  field: FactorCustomField;
  view: FactorEditView;
}) {
  const id = `s3-factor-${field}`;
  const fault = view.faults[field] ?? null;
  return (
    <div className="flex flex-col items-start gap-1">
      <Input
        ref={view.fieldRef(field)}
        id={id}
        data-testid={id}
        aria-label={edit.customFieldLabel[field]}
        placeholder={edit.placeholders[field]}
        inputMode={field === 'value' ? 'decimal' : undefined}
        autoComplete="off"
        value={view.draft[field]}
        disabled={view.busy}
        aria-invalid={fault !== null || undefined}
        aria-describedby={fault ? `${id}-error` : undefined}
        className="text-center"
        onChange={(event) => view.onDraft(field, event.target.value)}
      />
      {fault && (
        <p
          id={`${id}-error`}
          data-testid={`${id}-error`}
          className="m-0 flex items-center gap-0.5 text-style-pre-caption-03 text-support-error"
        >
          <CircleCloseIcon aria-hidden className="size-4 shrink-0" />
          {fault}
        </p>
      )}
    </div>
  );
}
