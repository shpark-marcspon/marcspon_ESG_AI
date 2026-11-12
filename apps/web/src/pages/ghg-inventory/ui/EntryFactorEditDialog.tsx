// S9 배출계수 선택(밴드 W12-3 ③ — Figma 28556:28480, e6 11-04 · 운영 관리자만 sid:MARC-ENT-469 2·3). S8 [배출계수 수정]이 연다.
//   폭 960 · 제목 「배출계수 선택」 24 Bold · 탭 없음 · 표 머리 체크 52 · 배출계수명 300 · 출처 · 산업 · 투입량 기준단위 · Tier · 줄 56 ·
//   끝 줄 「직접 입력」 · 단추 가운데 [이전](흰·테두리) [다음](검정).
//   S12-03(e6 ③ 11-10 — sid:MARC-ENT-644, 발주서 Q7·Q8): S8 [배출계수 수정] 말고 출처 칸 [수정]도 바로 연다. 열 폭 52·300·136×4 · 출처 가운데 ·
//   머리 40 · 빈 칸 「-」 · 빈 풀이면 표 자리 「등록된 배출계수가 없어요」 한 줄 + 「직접 입력」 줄 · 실패는 표 자리 공용 load-failure ·
//   pool 이 길면 표 몸 세로 스크롤(창 높이 안 — 머리 고정) · [이전] outline-grey.
//   디자인 대조(감독 de 11-10): 출처·산업·투입량 기준단위·Tier 가운데(왼쪽은 배출계수명뿐 — F5) · 고름 단계 사이 24(F6) · 빈 풀 줄 높이 96(F7).
//   - 열 때 pool.getFacility(잎) · pool.options() · 잎 계수마다 pool.getFactor(출처·산업·Tier — 요약에 없음). 하나라도 못 읽으면 실패 글.
//   - 고름은 하나(체크 꼴 라디오). 지금 계수(풀 계수면 그 줄, 직접입력이면 「직접 입력」)를 처음에 고르고, 같은 풀 계수면 [다음] 끔.
//   - 풀 계수 [다음] → S11 사유 → onSubmit({factorId}, 사유). 「직접 입력」 [다음] → 직접 입력 단계(EntryCustomFactorForm, Q4) →
//     [다음] 때 validateFactor(첫 오류 칸 초점) → S11 → onSubmit({custom: factorDraft}, 사유). 직접 입력 단계의 [이전]은 고름으로.
//   - 거절 갈래(발주서 §2-3 4): fields.reason → S11 칸 · fields.custom.<칸> → S11 닫고 이 창 칸 아래(548 글) · fields.factorId → S11 닫고 고르기 단계 줄에 서버 글(558) · forbidden · notFound·locked
//     → 기존 글 + 상세 다시 읽음(onGone) · 그 밖 실패 글. 성공은 onDone(부르는 쪽이 창 셋을 닫고 상세를 갈음).
//   - [이전](고름 단계)·✕·Esc: 바꾼 것(고름·직접 입력 칸)이 있으면 「저장하지 않고 닫을까요?」.
//   - S12-03a(e6 ④ — sid:MARC-ENT-644, 발주서 Q12): startCustom + 지금 계수가 직접입력이면 직접 입력 단계에서 열고 칸은 저장 값(customFactorFormOf).
//     그 판이 「처음」이라 안 바꾸면 나가기 확인 0. 고름 단계에서 「직접 입력」 [다음]으로 들면 지금처럼 빈 판.
import { useEffect, useRef, useState } from 'react';

import { Checkbox } from '@marcspon/ui/components/checkbox';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  EntryFactorTarget,
  EntryWrite,
  GhgPoolAdminPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  customFactorFormOf,
  emptyFactorForm,
  factorDraft,
  sameFactorForm,
  validateFactor,
} from '../../../entities/ghg/model/index.ts';
import type {
  EntryCustomFactor,
  EntryFactor,
  EntryIndex,
  FactorForm,
  PoolFactor,
  PoolOptions,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogCloseIconButton,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { LoadFailure } from '../../../shared/ui/load-failure/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { ConfirmModal } from './ConfirmModal.tsx';
import {
  EntryCustomFactorForm,
  customFieldId,
} from './EntryCustomFactorForm.tsx';
import { EntryReasonDialog } from './EntryReasonDialog.tsx';
import { CELL, HEAD_CELL, TABLE } from './entryTable.ts';

const entryWords = GHG_TEXT.entry;
const words = entryWords.factorEdit;
const factorWords = GHG_TEXT.factor;
/** 고름 값 — 풀 계수 id 또는 직접 입력. */
const CUSTOM = 'custom';
const CUSTOM_PREFIX = 'custom.';

type Loaded =
  'loading' | 'failed' | { options: PoolOptions; factors: PoolFactor[] };

export interface EntryFactorEditDialogProps {
  pool: GhgPoolAdminPort;
  /** 잎(인덱스) id — 풀 시설 노드 id 와 같다. */
  nodeId: string;
  /** 그 행의 지금 계수(row.factor ?? index.factor). */
  current: EntryFactor | EntryCustomFactor;
  /** 직접 입력 기준연도 드롭다운의 끝. */
  thisYear: number;
  /** S12-03a [수정] — 지금 계수가 직접입력이면 직접 입력 단계 · 저장 값으로 연다(아니면 무시). */
  startCustom?: boolean;
  /** PUT …/rows/{row}/factor(부르는 쪽이 쓰기 수를 센다). */
  onSubmit(
    target: EntryFactorTarget,
    reason: string,
  ): Promise<EntryWrite<EntryIndex>>;
  /** 성공 — 응답 상세. */
  onDone(index: EntryIndex): void;
  /** 404·409 — 상세를 다시 읽는다. */
  onGone(): void;
  onClose(): void;
}

export function EntryFactorEditDialog({
  pool,
  nodeId,
  current,
  thisYear,
  startCustom = false,
  onSubmit,
  onDone,
  onGone,
  onClose,
}: EntryFactorEditDialogProps) {
  const currentId = 'customId' in current ? null : current.factorId;
  const filled = startCustom && 'customId' in current ? current : null;
  const firstPick = currentId ?? CUSTOM;
  const [loaded, setLoaded] = useState<Loaded>('loading');
  const [reload, setReload] = useState(0);
  const [picked, setPicked] = useState<string>(firstPick);
  const [step, setStep] = useState<'pick' | 'custom'>(
    filled ? 'custom' : 'pick',
  );
  const [base, setBase] = useState<FactorForm | null>(null);
  const [form, setForm] = useState<FactorForm | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [line, setLine] = useState<string | null>(null);
  const [asking, setAsking] = useState<EntryFactorTarget | null>(null);
  const [busy, setBusy] = useState(false);
  const [reasonProblem, setReasonProblem] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [focus, setFocus] = useState<{ field: string } | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  /** 548 거절로 S11 이 닫힐 때 초점 줄 칸(S11 의 닫힘 초점이 칸 초점을 덮지 않게 — ③b Y7). */
  const returnField = useRef<string | null>(null);

  useEffect(() => {
    let live = true;
    void (async () => {
      const [facility, options] = await Promise.all([
        pool.getFacility(nodeId),
        pool.options(),
      ]);
      if (!live) return;
      if (facility.kind !== 'ok' || options.kind !== 'ok')
        return setLoaded('failed');
      const summaries = [...facility.value.factors].sort(
        (a, b) => a.sortOrder - b.sortOrder || Number(a.id) - Number(b.id),
      );
      const reads = await Promise.all(
        summaries.map((one) => pool.getFactor(one.id)),
      );
      if (!live) return;
      const factors: PoolFactor[] = [];
      for (const read of reads) {
        if (read.kind !== 'ok') return setLoaded('failed');
        factors.push(read.value);
      }
      const first =
        filled ?
          customFactorFormOf(filled, options.value)
        : emptyFactorForm(options.value);
      setBase(first);
      setForm((old) => old ?? first);
      setLoaded({ options: options.value, factors });
    })();
    return () => {
      live = false;
    };
    // filled 는 연 때의 계수(current) — 다시 읽기(reload)가 고친 칸을 덮지 않게 old ?? 로 지킨다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pool, nodeId, reload]);

  useEffect(() => {
    if (focus) document.getElementById(customFieldId(focus.field))?.focus();
  }, [focus]);

  const ready = typeof loaded === 'object' ? loaded : null;
  const edited =
    picked !== firstPick ||
    (form !== null && base !== null && !sameFactorForm(form, base));
  const requestClose = () => {
    if (busy) return;
    if (edited) setLeaving(true);
    else onClose();
  };

  const industryName = (code: string) =>
    ready?.options.industries.find((one) => one.code === code)?.name ?? code;

  const next = () => {
    setLine(null);
    if (!ready || form === null) return;
    if (step === 'pick') {
      if (picked === CUSTOM) setStep('custom');
      else if (picked !== currentId) setAsking({ factorId: picked });
      return;
    }
    const problems = validateFactor(form, ready.options.gases);
    if (problems.length > 0) {
      const found: Record<string, string> = {};
      for (const [field, why] of problems)
        found[field] =
          field === 'gases' ? factorWords.noGas
          : why === 'number' ? factorWords.number
          : factorWords.required;
      setErrors(found);
      setFocus({ field: problems[0]![0] });
      return;
    }
    setErrors({});
    setAsking({ custom: factorDraft(form, ready.options.gases) });
  };

  const submit = async (reason: string) => {
    if (!asking) return;
    setBusy(true);
    setReasonProblem(null);
    const out = await onSubmit(asking, reason);
    setBusy(false);
    if (out.kind === 'ok') {
      onDone(out.value);
      return;
    }
    if (out.kind === 'rejected' && out.code === 'VALIDATION_ERROR') {
      const keys = Object.keys(out.fields);
      if (keys.includes('reason')) {
        setReasonProblem(entryWords.reason.rejected);
        return;
      }
      const custom = keys.filter((key) => key.startsWith(CUSTOM_PREFIX));
      if (custom.length > 0 && 'custom' in asking) {
        setAsking(null);
        const found: Record<string, string> = {};
        for (const key of custom)
          found[key.slice(CUSTOM_PREFIX.length)] =
            words.unitProblem[key] ?? factorWords.invalid;
        setErrors(found);
        setStep('custom');
        returnField.current = custom[0]!.slice(CUSTOM_PREFIX.length);
        setFocus({ field: returnField.current });
        return;
      }
      // 558: 고칠 칸이 없는 풀 계수 거절 — 서버 글(해요체)을 고르기 단계 줄에 그대로, 다른 계수를 고를 수 있게.
      const refused = out.fields.factorId?.[0];
      if (refused !== undefined) {
        setAsking(null);
        setLine(refused);
        return;
      }
    }
    setAsking(null);
    if (out.kind === 'notFound') {
      onGone();
      setLine(entryWords.gone);
    } else if (out.kind === 'locked') {
      onGone();
      setLine(entryWords.locked);
    } else if (out.kind === 'forbidden') setLine(words.forbidden);
    else if (out.kind === 'refused')
      setLine(GHG_TEXT.companyOperator[out.company]);
    else setLine(words.failed);
  };

  /** 빈 값 「-」(e6 ③ — 직접 입력 줄은 빈 칸 그대로). */
  const shownValue = (text: string) => (text === '' ? words.empty : text);
  const pickRow = (id: string, name: string, cells: readonly string[]) => (
    <tr
      key={id}
      data-testid={`entry-factor-pick-${id}`}
      aria-selected={picked === id}
    >
      <td className={cn(CELL, 'text-center')}>
        <Checkbox
          size="lg"
          className="align-middle"
          aria-label={words.pick(name)}
          checked={picked === id}
          disabled={busy}
          onCheckedChange={() => {
            setPicked(id);
            setLine(null);
          }}
        />
      </td>
      <td className={cn(CELL, 'truncate')}>{name}</td>
      {cells.map((cell, index) => (
        <td key={index} className={cn(CELL, 'truncate text-center')}>
          {cell}
        </td>
      ))}
    </tr>
  );

  const head = cn(HEAD_CELL, 'sticky top-0 z-[1] h-10');
  const pickTable = ready && (
    <div
      data-testid="entry-factor-pick-scroll"
      className="max-h-[calc(100vh-320px)] overflow-y-auto"
    >
      <table
        className={`${TABLE} w-full table-fixed`}
        data-testid="entry-factor-pick"
      >
        <colgroup>
          <col className="w-[52px]" />
          <col className="w-[300px]" />
          <col className="w-[136px]" />
          <col className="w-[136px]" />
          <col className="w-[136px]" />
          <col className="w-[136px]" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" className={head}>
              <span className="sr-only">{words.columns.name}</span>
            </th>
            <th scope="col" className={head}>
              {words.columns.name}
            </th>
            <th scope="col" className={cn(head, 'text-center')}>
              {words.columns.source}
            </th>
            <th scope="col" className={cn(head, 'text-center')}>
              {words.columns.industry}
            </th>
            <th scope="col" className={cn(head, 'text-center')}>
              {words.columns.inputUnit}
            </th>
            <th scope="col" className={cn(head, 'text-center')}>
              {words.columns.tier}
            </th>
          </tr>
        </thead>
        <tbody>
          {ready.factors.length === 0 && (
            <tr data-testid="entry-factor-pick-empty">
              <td
                colSpan={6}
                className={cn(CELL, 'h-24 text-center text-text-tertiary')}
              >
                {GHG_TEXT.pool.noFactors}
              </td>
            </tr>
          )}
          {ready.factors.map((factor) =>
            pickRow(factor.id, factor.name, [
              shownValue(factor.source),
              shownValue(industryName(factor.industryCode)),
              shownValue(factor.inputUnit.unit),
              `${factor.tier}`,
            ]),
          )}
          {pickRow(CUSTOM, words.custom, ['', '', '', ''])}
        </tbody>
      </table>
    </div>
  );

  const body =
    loaded === 'loading' ? <LoadSkeleton label={GHG_TEXT.common.loading} />
    : loaded === 'failed' ?
      <div data-testid="entry-factor-pick-failed">
        <LoadFailure
          kind="failed"
          message={words.loadFailed}
          retryLabel={GHG_TEXT.common.retry}
          onRetry={() => {
            setLoaded('loading');
            setReload((n) => n + 1);
          }}
        />
      </div>
    : step === 'pick' ? pickTable
    : form && (
        <EntryCustomFactorForm
          options={loaded.options}
          form={form}
          errors={errors}
          thisYear={thisYear}
          disabled={busy}
          onChange={(change, clear) => {
            setForm((old) => (old ? { ...old, ...change } : old));
            setLine(null);
            if (clear.length > 0)
              setErrors((old) => {
                const out = { ...old };
                for (const field of clear) delete out[field];
                return out;
              });
          }}
        />
      );

  return (
    <>
      <Dialog
        open
        onOpenChange={(open) => {
          if (!open) requestClose();
        }}
      >
        <DialogContent
          size="lg"
          data-testid="entry-factor-edit"
          data-step={step}
          className={cn(
            'w-[960px] max-w-[calc(100vw-64px)]',
            // 판 S12-03b `f-modal--l f12d-gap24`: 고름 단계 사이 24 · 직접 입력 단계는 S12-03a r1 `f-modal--l` 32(디자인 대조 F6).
            step === 'pick' ? 'gap-6' : 'gap-8',
          )}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            closeRef.current?.focus();
          }}
        >
          <DialogCloseIconButton ref={closeRef} aria-label={entryWords.close} />
          <DialogTitle className="text-style-pre-display-04">
            {step === 'pick' ? words.title : words.customTitle}
          </DialogTitle>
          {body}
          {line && (
            <p
              role="alert"
              data-testid="entry-factor-edit-line"
              className="m-0 text-style-pre-caption-03 text-support-error-accent"
            >
              {line}
            </p>
          )}
          <DialogFooter className="pt-0">
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              className="min-w-20"
              disabled={busy}
              onClick={() => {
                if (step === 'custom') {
                  setStep('pick');
                  setLine(null);
                } else requestClose();
              }}
            >
              {words.prev}
            </Button>
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              className="min-w-20"
              data-testid="entry-factor-next"
              disabled={
                busy ||
                !ready ||
                (step === 'pick' && picked !== CUSTOM && picked === currentId)
              }
              onClick={next}
            >
              {words.next}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {asking && (
        <EntryReasonDialog
          busy={busy}
          problem={reasonProblem}
          returnFocus={() => {
            const field = returnField.current;
            returnField.current = null;
            return field === null ? null : (
                document.getElementById(customFieldId(field))
              );
          }}
          onConfirm={(reason) => void submit(reason)}
          onClose={() => {
            setAsking(null);
            setReasonProblem(null);
          }}
        />
      )}
      {leaving && (
        <ConfirmModal
          title={factorWords.leaveConfirm}
          cancel={factorWords.stay}
          confirm={factorWords.leave}
          returnFocus={() => closeRef.current}
          testId="entry-factor-edit-leave"
          onClose={() => setLeaving(false)}
          onConfirm={onClose}
        />
      )}
    </>
  );
}
