// S3 데이터 상세 모달(밴드 W12-1b ① — 스펙 ① S3, 화면 안 상태 Q3). 상세 하나를 읽어 사업장 블록마다 초안을 쥔다.
//   - 저장은 모달 아래 [저장] 하나(밴드 W12-1c ① — sid:MARC-ENT-529, 발주서 Q1·Q2): 누르면 모든 블록 draftProblems·메모 길이를 먼저 재고
//     (하나라도 걸리면 요청 0 · 화면 차례 첫 오류 칸 초점), 모든 블록 saveBody 를 먼저 만든 뒤, 바뀐 사업장만 화면 차례로 하나씩 PUT
//     (서버 저장 단위는 사업장 하나) → 메모가 바뀌었으면 마지막에 PUT memo. 첫 실패에서 멈춘다(메모도 보내지 않음).
//     저장하는 동안 입력·메모·소수점·잠금·추가·삭제·닫기를 막는다(감독 처분 — critic 권고 1).
//   - 본문은 model saveBody 만 부르고 try 로 감싼다(toRequestId 예외 — 1a 가지 리뷰). 422 rows.<i>… 는 fieldOf 로 같은 칸.
//   - 성공 응답은 그 블록만 갈음하고, 다른 블록의 고침은 mergeSiteDraft 로 지킨다.
//   - 409 locked·404 → 한 줄 + 상세 다시 읽음. 상세 404 → 모달 안 「찾을 수 없어요」 + 닫기.
//   - 잠긴 판: 입력·추가·삭제·N/A·저장·메모·소수점 비활성(보기는 됨). 쓰기가 있었으면 onClose(true) — S2 가 다시 읽는다.
//   - 저장 안 한 고침이 있는 채 닫으면 나가기 확인. 숨김(469-5): 담당자 줄·참고자료·계산식.
//   - W12-2 ②: S7 입력주기(블록 머리 → EntryPeriodDialog → PUT period → 그 블록만 응답 그대로 · 다른 블록 고침 지킴 · 날아가는 읽기 버림 ·
//     블록 알림 줄 「입력 주기가 저장됐어요」) · S12 [복구](EntryHistoryDialog — value 는 apply(out, null), period 는 그 블록 응답 그대로).
//     511: 메모·소수점 쓰기는 읽기 번호를 올리지 않는다(지운 뒤 읽기 보존). 대신 그 쓰기 전에 떠난 읽기가 늦게 오면 index.memo·decimals 를
//     쓴 값으로 다시 덮는다(그 판 일부만 — rebaseDraft 꼴).
//   - ②: 잠금(Q8 — 고객사 잠그기만, 운영 관리자 풀기도. W12-1c #10: 제목 옆 아이콘 단추 + 툴팁, R6: 고객사는 고친 것 없어도 확인 창)
//     · S12 히스토리 · S8 계수 보기(row.factor ?? index.factor, 두 역할 다 읽기 전용).
//   - W12-3 ③: 운영 관리자(pool prop 이 있을 때)만 저장된 행에서 연 S8 에 [배출계수 수정] → S9(EntryFactorEditDialog) → S11 사유 →
//     PUT factor. 성공 = restored 꼴(apply(out, null) · 날아가는 읽기 버림) + 창 셋 닫음 + 그 블록 알림 줄 「배출계수를 바꿨어요」(Q7).
//     그 행 고친 동안·잠김·쓰는 중 끔. 고객사는 pool null(경로 컴포넌트) — 단추 0.
//   - S12-05(sid:MARC-ENT-644): 이 회사에 그 잎의 자산/시설이 없으면(sites 0 — 서버가 블록에서 뺌) 「데이터 입력」 구역에 회색 한 줄
//     + [조직구조로](onOrganization — S17 의 시설 0 안내 꼴). 고친 것이 있으면 나가기 확인을 거친다.
import { useEffect, useRef, useState } from 'react';

import {
  CircleWarningIcon,
  LockIcon,
  LockOpenIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import { Textarea } from '@marcspon/ui/components/textarea';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import type {
  CompanyRefusal,
  EntryFactorTarget,
  EntryWrite,
  GhgEntryPort,
  GhgPoolAdminPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import {
  DECIMALS_RANGE,
  ENTRY_MEMO_MAX,
  addable,
  draftEdited,
  draftProblems,
  entryAtText,
  estimatedOn,
  fieldOf,
  mergeSiteDraft,
  newRowDraft,
  rowDraftOf,
  rowKeyOf,
  saveBody,
  withEstimated,
} from '../../../entities/ghg/model/index.ts';
import type {
  EntryCustomFactor,
  EntryFacility,
  EntryFactor,
  EntryIndex,
  EntryPeriod,
  EntryRowDraft,
  EntrySaveBody,
  EntrySite,
} from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogCloseIconButton,
  DialogContent,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { LoadSkeleton } from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { toast } from '../../../shared/ui/toast/index.ts';
import { ConfirmModal } from './ConfirmModal.tsx';
import { EntryAddDialog } from './EntryAddDialog.tsx';
import { EntryFactorDialog } from './EntryFactorDialog.tsx';
import { EntryFactorEditDialog } from './EntryFactorEditDialog.tsx';
import { EntryHistoryDialog } from './EntryHistoryDialog.tsx';
import { EntryPeriodDialog } from './EntryPeriodDialog.tsx';
import {
  EntrySiteBlock,
  cellKey,
  shownAmount,
  siteKey,
} from './EntrySiteBlock.tsx';
import type { EntryBlockState } from './EntrySiteBlock.tsx';
import { EstimatedWave, estimatedBox } from './EstimatedMark.tsx';
import { CELL, HEAD_CELL, SUM_CELL, TABLE } from './entryTable.ts';

const words = GHG_TEXT.entry;
const DECIMAL_OPTIONS = Array.from(
  { length: DECIMALS_RANGE.max - DECIMALS_RANGE.min + 1 },
  (_, index) => DECIMALS_RANGE.min + index,
);

export interface EntryDetailDialogProps {
  port: GhgEntryPort;
  year: number;
  nodeId: string;
  operator: boolean;
  /** 풀 실어댑터(운영 관리자만 — 고객사·없음이면 S8 [배출계수 수정] 0, W12-3 Q5). */
  pool?: GhgPoolAdminPort | null;
  /** 닫기 — wrote 면 S2 가 다시 읽는다. */
  onClose(wrote: boolean): void;
  /** S12-05 안내의 [조직구조로](안 넘기면 단추 0). */
  onOrganization?: () => void;
}

type Loaded =
  | { state: 'loading' }
  | { state: 'failed' }
  | { state: 'notFound' }
  | { state: 'refused'; company: CompanyRefusal }
  | { state: 'ready'; index: EntryIndex };

/** apply 의 「전부 응답으로」(잠그며 고침을 버릴 때). */
const ALL = '*';
/**
 * 총합 표의 자릿점(W12-1c #11, 감독 처분 Q6 — 총합 표만): formatAmount 글자의 정수부에 세 자리마다 쉼표. 셈 0, 숫자 꼴이 아니면 그대로.
 */
export function withComma(text: string): string {
  const match = /^(-?)([0-9]+)(\.[0-9]+)?$/.exec(text);
  if (!match) return text;
  const [, sign = '', int = '', frac = ''] = match;
  return `${sign}${int.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${frac}`;
}

/** 메모 칸의 등록 열쇠(초점). */
const MEMO = 'memo';

const emptyBlock = (site: EntrySite): EntryBlockState => ({
  drafts: site.rows.map((row) => rowDraftOf(row, site.slots)),
  checked: new Set(),
  errors: {},
  notice: null,
});

export function EntryDetailDialog({
  port,
  year,
  nodeId,
  operator,
  pool = null,
  onClose,
  onOrganization,
}: EntryDetailDialogProps) {
  const companyText = operator ? GHG_TEXT.companyOperator : GHG_TEXT.company;
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });
  const [blocks, setBlocks] = useState<Record<string, EntryBlockState>>({});
  const [memo, setMemo] = useState('');
  const [memoError, setMemoError] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  /** 모달 [저장] — 응답을 기다리는 동안 · 전부 저장된 뒤 제목 옆 「저장됐어요」 · 아래 한 줄(바꾼 것 없음 · 일부 실패). */
  const [saving, setSaving] = useState(false);
  const [footNotice, setFootNotice] = useState<string | null>(null);
  /** 나가기 확인(고친 것이 있을 때) — 닫기 또는 [조직구조로]. */
  const [leaving, setLeaving] = useState<'close' | 'organization' | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [adding, setAdding] = useState<string | null>(null);
  /** 잠금 확인 창 — 고친 것 있음(edited) · 고객사 고친 것 없음(plain, R6). */
  const [locking, setLocking] = useState<'edited' | 'plain' | null>(null);
  /** 잠금·풀기 쓰기를 기다리는 동안 — 단추를 막아 요청이 겹치지 않게(검증 R5). */
  const [lockBusy, setLockBusy] = useState(false);
  /** S8 — 보는 계수와 연 행(저장된 행에서 열었을 때만 — 인덱스 기본 계수 보기는 null). */
  const [viewFactor, setViewFactor] = useState<{
    factor: EntryFactor | EntryCustomFactor;
    row: { draft: EntryRowDraft; siteId: string } | null;
  } | null>(null);
  /** S9 를 연 행(W12-3 ③) · 그 행의 지금 계수(S8 에서 열면 S8 의 계수, 칸 [수정]이면 row.factor ?? index.factor — Q7). */
  const [editFactor, setEditFactor] = useState<{
    draft: EntryRowDraft;
    siteId: string;
    current: EntryFactor | EntryCustomFactor;
    /** S12-03a 저장 뒤 창의 [수정] — 직접 입력 단계를 저장 값으로(Q12). */
    filled?: boolean;
  } | null>(null);
  const [viewHistory, setViewHistory] = useState<{
    draft: EntryRowDraft;
    siteId: string;
  } | null>(null);
  /** S7 창이 열린 블록 · PUT period 를 기다리는 블록(그 블록 입력·[저장] 끔). */
  const [periodOf, setPeriodOf] = useState<string | null>(null);
  const [periodBusy, setPeriodBusy] = useState<string | null>(null);
  /** 511: 성공한 메모·소수점 쓰기 값과 그때의 읽기 번호(이 번호 이하로 떠난 읽기가 늦게 오면 이 값으로 덮는다). */
  const memoWrote = useRef<{ value: string; at: number } | null>(null);
  const decimalsWrote = useRef<{ value: number; at: number } | null>(null);
  const wrote = useRef(false);
  const writing = useRef(0);
  const asked = useRef(0);
  const hasIndex = useRef(false);
  const cells = useRef(new Map<string, HTMLElement>());
  const removeButtons = useRef(new Map<string, HTMLButtonElement>());
  const addButtons = useRef(new Map<string, HTMLButtonElement>());
  const closeRef = useRef<HTMLButtonElement>(null);
  /** 그린 뒤 초점 갈 칸 — 저장 중엔 칸이 꺼져 있어 응답을 받은 그 자리에서는 초점이 안 간다. */
  const pendingFocus = useRef<string | null>(null);
  useEffect(() => {
    if (pendingFocus.current === null) return;
    cells.current.get(pendingFocus.current)?.focus();
    pendingFocus.current = null;
  });

  const register = (key: string, element: HTMLElement | null) => {
    if (element) cells.current.set(key, element);
    else cells.current.delete(key);
  };

  /** 받은 상세를 판에 얹는다. fresh 블록(ALL 이면 전부)은 응답 그대로, 나머지는 고침을 지킨다. */
  const apply = (index: EntryIndex, fresh: string | null) => {
    hasIndex.current = true;
    setLoaded({ state: 'ready', index });
    setBlocks((old) =>
      Object.fromEntries(
        index.sites.map((site) => {
          const was = old[site.siteId];
          if (!was) return [site.siteId, emptyBlock(site)];
          const drafts =
            site.siteId === fresh || fresh === ALL ?
              site.rows.map((row) => rowDraftOf(row, site.slots))
            : mergeSiteDraft(was.drafts, site);
          const alive = new Set(drafts.map((draft) => draft.key));
          return [
            site.siteId,
            {
              ...was,
              drafts,
              checked: new Set([...was.checked].filter((k) => alive.has(k))),
            },
          ];
        }),
      ),
    );
  };

  const read = async () => {
    const ticket = ++asked.current;
    const out = await port.detail(year, nodeId);
    if (ticket !== asked.current) return;
    if (out.kind === 'ok') {
      const first = !hasIndex.current;
      // 511: 이 읽기가 메모·소수점 쓰기보다 먼저 떠났으면 그 칸은 옛 판이다 — 쓴 값으로 덮는다.
      const memoNow = memoWrote.current;
      const decimalsNow = decimalsWrote.current;
      const index = {
        ...out.value,
        ...(memoNow && ticket <= memoNow.at ? { memo: memoNow.value } : {}),
        ...(decimalsNow && ticket <= decimalsNow.at ?
          { decimals: decimalsNow.value }
        : {}),
      };
      apply(index, null);
      if (first) setMemo(index.memo);
      return;
    }
    if (out.kind === 'notFound') setLoaded({ state: 'notFound' });
    else if (hasIndex.current) setNotice(words.reloadFailed);
    else if (out.kind === 'refused')
      setLoaded({ state: 'refused', company: out.company });
    else setLoaded({ state: 'failed' });
  };
  useEffect(() => {
    void read();
    // 모달은 year·nodeId 마다 새로 뜬다(key).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const index = loaded.state === 'ready' ? loaded.index : null;
  const locked = index?.locked ?? false;
  /** S12-03 추정치 단추 하나(Q6): 켜짐 = N/A 아닌 줄 칸 중 하나라도 추정. */
  const estimated = estimatedOn(
    Object.values(blocks).flatMap((block) => block.drafts),
  );
  const memoEdited = index !== null && memo !== index.memo;
  const edited =
    memoEdited ||
    Object.values(blocks).some((block) => block.drafts.some(draftEdited));

  const close = () => onClose(wrote.current);
  const requestClose = () => {
    if (writing.current > 0) return;
    if (edited && !locked) setLeaving('close');
    else close();
  };
  const toOrganization = () => {
    if (writing.current > 0 || !onOrganization) return;
    if (edited && !locked) setLeaving('organization');
    else onOrganization();
  };

  const patchBlock = (siteId: string, patch: Partial<EntryBlockState>) =>
    setBlocks((old) => {
      const was = old[siteId];
      return was ? { ...old, [siteId]: { ...was, ...patch } } : old;
    });

  /** 쓰기 거절 → 한 줄(locked·notFound 는 상세도 다시 읽는다). */
  const refusalText = (out: Exclude<EntryWrite<unknown>, { kind: 'ok' }>) => {
    if (out.kind === 'locked') {
      void read();
      return words.locked;
    }
    if (out.kind === 'notFound') {
      void read();
      return words.gone;
    }
    if (out.kind === 'forbidden') return words.forbidden;
    if (out.kind === 'refused') return companyText[out.company];
    return words.saveFailed;
  };

  /** 차례가 앞선 오류 칸으로 초점(화면 차례). */
  const focusFirst = (
    drafts: readonly EntryRowDraft[],
    errors: Readonly<Record<string, string>>,
  ) => {
    for (const draft of drafts)
      for (const slot of ['unit', ...draft.edited.values.map((v) => v.slot)]) {
        const at = cellKey(draft.key, slot);
        if (errors[at]) {
          pendingFocus.current = at;
          return;
        }
      }
  };

  const rejected = (
    siteId: string,
    drafts: readonly EntryRowDraft[],
    body: EntrySaveBody,
    fields: Readonly<Record<string, unknown>>,
  ) => {
    const errors: Record<string, string> = {};
    const keys = Object.keys(fields);
    let general = keys.length === 0;
    for (const field of keys) {
      const spot = fieldOf(field, body);
      if (spot === null) general = true;
      else {
        const key = rowKeyOf(spot.rowId, spot.siteFacilityId);
        if (spot.slot !== null)
          errors[cellKey(key, spot.slot)] = words.amountRejected;
        else if (spot.field === 'unit')
          errors[cellKey(key, 'unit')] = words.unitRejected;
        else general = true;
      }
    }
    patchBlock(siteId, {
      errors,
      notice: general ? words.saveFailed : null,
    });
    if (general) pendingFocus.current = siteKey(siteId);
    focusFirst(drafts, errors);
  };

  /** 차례가 앞선 오류 칸으로 초점(화면 차례) — 블록마다 차례로 보고 처음 걸린 데서 멈춘다. */
  const focusFirstOf = (
    order: readonly {
      drafts: readonly EntryRowDraft[];
      errors: Readonly<Record<string, string>>;
    }[],
  ) => {
    for (const { drafts, errors } of order) {
      focusFirst(drafts, errors);
      if (pendingFocus.current !== null) return true;
    }
    return false;
  };

  /** 모달 [저장](529 — Q1·Q2). */
  const saveAll = async () => {
    if (index === null || locked || saving) return;
    const sites = index.sites.filter((site) => blocks[site.siteId]);
    // 1. 검사 먼저 — 모든 블록 + 메모 길이. 하나라도 걸리면 요청 0.
    const checked = sites.map((site) => {
      const { drafts } = blocks[site.siteId]!;
      const errors = Object.fromEntries(
        draftProblems(drafts).map(({ key, slot, problem }) => [
          cellKey(key, slot),
          problem === 'decimals' ? words.amountDecimals
          : problem === 'comma' ? words.amountComma
          : words.amountFormat,
        ]),
      );
      return { site, drafts, errors };
    });
    const memoTooLong = memo.length > ENTRY_MEMO_MAX;
    const blocked = checked.filter(
      ({ errors }) => Object.keys(errors).length > 0,
    );
    setFootNotice(null);
    if (blocked.length > 0 || memoTooLong) {
      for (const { site, errors } of checked)
        patchBlock(site.siteId, { errors, notice: null });
      setMemoError(memoTooLong);
      if (!focusFirstOf(checked) && memoTooLong) pendingFocus.current = MEMO;
      return;
    }
    // 2. 본문을 모두 먼저 만든다(첫 PUT 전에 — critic 권고 2).
    const plans: {
      site: EntrySite;
      drafts: readonly EntryRowDraft[];
      body: EntrySaveBody;
    }[] = [];
    for (const { site, drafts } of checked) {
      let body: EntrySaveBody;
      try {
        body = saveBody(drafts);
      } catch {
        patchBlock(site.siteId, { notice: words.saveFailed });
        pendingFocus.current = siteKey(site.siteId);
        return;
      }
      if (body.rows.length > 0) plans.push({ site, drafts, body });
    }
    const sendMemo = memoEdited;
    if (plans.length === 0 && !sendMemo) {
      for (const { site } of checked)
        patchBlock(site.siteId, { errors: {}, notice: null });
      setFootNotice(words.nothingToSave);
      return;
    }
    // 3. 바뀐 사업장만 화면 차례로 하나씩 → 메모. 첫 실패에서 멈춘다.
    setSaving(true);
    setMemoError(false);
    setNotice(null);
    for (const { site } of checked)
      patchBlock(site.siteId, { errors: {}, notice: null, done: null });
    writing.current += 1;
    let stored = 0;
    let failed = false;
    for (const { site, drafts, body } of plans) {
      const out = await port.saveRows(year, nodeId, site.siteId, body.rows);
      if (out.kind === 'ok') {
        wrote.current = true;
        // 날아가는 중인 읽기는 이 응답보다 옛 판일 수 있다 — 늦게 와도 버린다(가지 리뷰).
        asked.current += 1;
        apply(out.value, site.siteId);
        stored += 1;
        continue;
      }
      failed = true;
      if (out.kind === 'rejected')
        rejected(site.siteId, drafts, body, out.fields);
      else {
        patchBlock(site.siteId, { notice: refusalText(out) });
        pendingFocus.current = siteKey(site.siteId);
      }
      break;
    }
    let memoFailed = false;
    if (!failed && sendMemo) {
      const out = await port.memo(year, nodeId, memo);
      if (out.kind === 'ok') {
        wrote.current = true;
        memoWrote.current = { value: out.value, at: asked.current };
        setMemo(out.value);
        setLoaded((old) =>
          old.state === 'ready' ?
            { state: 'ready', index: { ...old.index, memo: out.value } }
          : old,
        );
      } else {
        memoFailed = true;
        if (out.kind === 'rejected' && 'memo' in out.fields) setMemoError(true);
        else setFootNotice(refusalText(out));
        pendingFocus.current = MEMO;
      }
    }
    writing.current -= 1;
    setSaving(false);
    if (failed) {
      if (stored > 0) setFootNotice(words.savePartial);
      return;
    }
    // S12-04: 「저장됐어요」는 공용 토스트(모달 위 — host 는 InventoryScreen).
    if (!memoFailed) toast({ message: words.saved });
  };

  const change = (
    siteId: string,
    key: string,
    update: (draft: EntryRowDraft) => EntryRowDraft,
    touched: (draft: EntryRowDraft) => string[],
  ) => {
    setFootNotice(null);
    setBlocks((old) => {
      const was = old[siteId];
      if (!was) return old;
      const drafts = was.drafts.map((draft) =>
        draft.key === key ? update(draft) : draft,
      );
      const after = drafts.find((draft) => draft.key === key);
      const errors = { ...was.errors };
      // 고친 행의 칸 오류는 다음 저장 때 다시 잰다.
      if (after) for (const at of touched(after)) delete errors[at];
      return {
        ...old,
        [siteId]: { ...was, drafts, errors, notice: null, done: null },
      };
    });
  };

  const removeChecked = async (site: EntrySite) => {
    const block = blocks[site.siteId];
    setRemoving(null);
    if (!block) return;
    const chosen = block.drafts.filter((draft) => block.checked.has(draft.key));
    const ids = chosen.flatMap((draft) =>
      draft.before ? [draft.before.rowId] : [],
    );
    const dropLocal = () =>
      setBlocks((old) => {
        const was = old[site.siteId];
        if (!was) return old;
        return {
          ...old,
          [site.siteId]: {
            ...was,
            drafts: was.drafts.filter(
              (draft) => draft.before !== null || !was.checked.has(draft.key),
            ),
            checked: new Set(),
          },
        };
      });
    if (ids.length === 0) {
      dropLocal();
      return;
    }
    writing.current += 1;
    const out = await port.deleteRows(year, nodeId, ids);
    writing.current -= 1;
    if (out.kind === 'ok') {
      wrote.current = true;
      dropLocal();
      void read();
      return;
    }
    patchBlock(site.siteId, { notice: refusalText(out) });
  };

  const addPicked = (site: EntrySite, picked: readonly EntryFacility[]) => {
    setAdding(null);
    if (index === null || picked.length === 0) return;
    setFootNotice(null);
    const unit = index.unitOptions[0] ?? index.factor.inputUnit.unit;
    setBlocks((old) => {
      const was = old[site.siteId];
      if (!was) return old;
      return {
        ...old,
        [site.siteId]: {
          ...was,
          notice: null,
          drafts: [
            ...was.drafts,
            // 추정 단추가 켜진 동안 더한 줄도 추정(Q6).
            ...picked.map((facility) =>
              withEstimated(newRowDraft(facility, unit, site.slots), estimated),
            ),
          ],
        },
      };
    });
  };

  /** 추정 단추: 켜짐 → 전부 끔 · 꺼짐 → N/A 아닌 모든 줄·칸 켬. 저장은 [저장] 하나(고친 것으로 셈). */
  const toggleEstimated = () => {
    const on = !estimated;
    setFootNotice(null);
    setBlocks((old) =>
      Object.fromEntries(
        Object.entries(old).map(([siteId, block]) => {
          const drafts = block.drafts.map((draft) => withEstimated(draft, on));
          return [
            siteId,
            drafts.every((draft, at) => draft === block.drafts[at]) ? block : (
              { ...block, drafts, notice: null, done: null }
            ),
          ];
        }),
      ),
    );
  };

  const saveDecimals = async (n: number) => {
    writing.current += 1;
    const out = await port.decimals(year, n);
    writing.current -= 1;
    if (out.kind === 'ok') {
      wrote.current = true;
      decimalsWrote.current = { value: out.value, at: asked.current };
      setNotice(null);
      setLoaded((old) =>
        old.state === 'ready' ?
          { state: 'ready', index: { ...old.index, decimals: out.value } }
        : old,
      );
    } else if (out.kind === 'rejected') setNotice(words.decimalsFailed);
    else setNotice(refusalText(out));
  };

  /** 잠금·풀기. 잠글 때 고침은 버린다(확인 뒤). 고객사 풀기 403·회사 둘 400 은 한 줄. */
  const changeLock = async (on: boolean) => {
    setLocking(null);
    setLockBusy(true);
    writing.current += 1;
    const out = await (on ?
      port.lock(year, nodeId)
    : port.unlock(year, nodeId));
    writing.current -= 1;
    setLockBusy(false);
    if (out.kind === 'ok') {
      wrote.current = true;
      setNotice(null);
      asked.current += 1;
      apply(out.value, on ? ALL : null);
      if (on) setMemo(out.value.memo);
    } else if (out.kind === 'rejected') setNotice(words.lockFailed);
    else setNotice(refusalText(out));
  };

  /** S7 — 그 블록만 응답 그대로(옛 칸 판은 쓸 수 없음 — Q4) · 다른 블록 고침 지킴 · 날아가는 읽기 버림. */
  const changePeriod = async (site: EntrySite, period: EntryPeriod) => {
    setPeriodOf(null);
    setPeriodBusy(site.siteId);
    setFootNotice(null);
    patchBlock(site.siteId, { notice: null, done: null });
    writing.current += 1;
    const out = await port.period(year, nodeId, site.siteId, period);
    writing.current -= 1;
    setPeriodBusy(null);
    if (out.kind === 'ok') {
      wrote.current = true;
      asked.current += 1;
      apply(out.value, site.siteId);
      patchBlock(site.siteId, { done: words.periodChange.saved });
      return;
    }
    patchBlock(site.siteId, {
      notice:
        out.kind === 'rejected' ?
          words.periodChange.rejected
        : refusalText(out),
    });
  };

  /** S12 복구 성공 — value 줄은 고침 지킴(apply null), period 줄은 그 블록 응답 그대로(Q4·Q5). 날아가는 읽기 버림. */
  const restored = (out: EntryIndex, kind: string, siteId: string) => {
    wrote.current = true;
    asked.current += 1;
    apply(out, kind === 'period' ? siteId : null);
  };

  /**
   * S9·S11 성공 — restored 꼴(고침 지킴 · 날아가는 읽기 버림) + 그 블록 알림 줄(Q7).
   * S12-03a(e6 ④, 발주서 Q12): 응답의 그 행 계수가 직접입력이면 S9 만 닫고 S8 을 새 계수로 다시 연다(저장 뒤 창). 풀 계수면 창 셋 닫음.
   */
  const factorChanged = (out: EntryIndex, siteId: string, rowId: string) => {
    wrote.current = true;
    asked.current += 1;
    apply(out, null);
    setEditFactor(null);
    const site = out.sites.find((one) => one.siteId === siteId);
    const row = site?.rows.find((one) => one.rowId === rowId);
    if (site && row?.factor && 'customId' in row.factor)
      setViewFactor({
        factor: row.factor,
        row: { draft: rowDraftOf(row, site.slots), siteId },
      });
    else setViewFactor(null);
    patchBlock(siteId, { notice: null, done: words.factorEdit.done });
  };
  const setRowFactor = async (
    rowId: string,
    target: EntryFactorTarget,
    reason: string,
  ) => {
    writing.current += 1;
    const out = await port.setRowFactor(year, nodeId, rowId, target, reason);
    writing.current -= 1;
    return out;
  };
  /** 그 행에 저장 안 한 고침이 있는가(S8 [배출계수 수정]·S12 [복구] 끔). */
  const rowDirty = (row: { draft: EntryRowDraft; siteId: string }) =>
    (blocks[row.siteId]?.drafts ?? []).some(
      (draft) => draft.key === row.draft.key && draftEdited(draft),
    );

  const removeSite = index?.sites.find((site) => site.siteId === removing);
  const periodSite = index?.sites.find((site) => site.siteId === periodOf);
  const addSite = index?.sites.find((site) => site.siteId === adding);
  const addChoices =
    addSite ?
      addable(addSite).filter(
        (facility) =>
          !(blocks[addSite.siteId]?.drafts ?? []).some(
            (draft) => draft.key === rowKeyOf(null, facility.id),
          ),
      )
    : [];

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) requestClose();
      }}
    >
      <DialogContent
        size="lg"
        data-screen="ghg-entry-detail"
        className="w-[calc(100vw-64px)]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          closeRef.current?.focus();
        }}
      >
        <DialogCloseIconButton ref={closeRef} aria-label={words.close} />
        {index === null ?
          <>
            <DialogTitle className="text-style-pre-heading-02">
              {loaded.state === 'notFound' ? words.notFound : words.detailTitle}
            </DialogTitle>
            {loaded.state === 'loading' && (
              <LoadSkeleton label={GHG_TEXT.common.loading} />
            )}
            {loaded.state === 'failed' && (
              <div
                role="alert"
                data-testid="entry-load-failure"
                className="flex flex-col items-start gap-4"
              >
                <PageInfo
                  tone="error"
                  icon={<CircleWarningIcon aria-hidden />}
                  className="w-full"
                >
                  {words.loadFailed}
                </PageInfo>
                <Button
                  variant="solidBlack"
                  shape="round"
                  size="md"
                  onClick={() => {
                    setLoaded({ state: 'loading' });
                    void read();
                  }}
                >
                  {GHG_TEXT.common.retry}
                </Button>
              </div>
            )}
            {loaded.state === 'refused' && (
              <PageInfo
                role="alert"
                tone="error"
                icon={<CircleWarningIcon aria-hidden />}
                data-testid="entry-company-refusal"
              >
                {companyText[loaded.company]}
              </PageInfo>
            )}
            {loaded.state === 'notFound' && (
              <div>
                <Button
                  variant="solidBlack"
                  shape="round"
                  size="md"
                  onClick={close}
                >
                  {words.close}
                </Button>
              </div>
            )}
          </>
        : <div className="flex flex-col gap-8">
            <header className="flex flex-col gap-4">
              <div className="flex items-center gap-4">
                <DialogTitle className="text-style-pre-display-04">
                  {index.name}
                </DialogTitle>
                <LockControl
                  locked={index.locked}
                  operator={operator}
                  disabled={lockBusy || saving}
                  onLock={() => {
                    if (edited) setLocking('edited');
                    else if (!operator) setLocking('plain');
                    else void changeLock(true);
                  }}
                  onUnlock={() => void changeLock(false)}
                  estimated={estimated}
                  estimatedName={words.estimatedAll(index.name)}
                  estimatedDisabled={locked || lockBusy || saving}
                  onEstimated={toggleEstimated}
                />
                {index.locked && index.lockedBy && index.lockedAt && (
                  <span
                    data-testid="entry-locked-by"
                    className="text-style-pre-caption-02 text-text-tertiary"
                  >
                    {words.lockedInfo(
                      index.lockedBy.name,
                      entryAtText(index.lockedAt),
                    )}
                  </span>
                )}
              </div>
              <p className="m-0 flex gap-2 text-style-pre-body-05 text-text-tertiary">
                <span className="w-16 shrink-0">{words.pathLabel}</span>
                <span data-testid="entry-path">{index.path.join(' > ')}</span>
              </p>
            </header>
            <p
              role="alert"
              data-testid="entry-notice"
              className="m-0 text-style-pre-caption-03 text-support-error-accent empty:hidden"
            >
              {notice}
            </p>
            <section className="flex flex-col gap-4">
              <div className="flex items-center gap-2">
                <h4 className="m-0 text-style-pre-heading-02 text-text-primary">
                  {words.detailTitle}
                </h4>
                <label className="ml-auto flex items-center gap-2 text-style-pre-caption-02 text-text-tertiary">
                  {words.decimalsLabel}
                  <NativeSelect
                    className="w-[120px] min-w-0"
                    aria-label={words.decimalsLabel}
                    disabled={locked || saving}
                    value={index.decimals}
                    onChange={(event) => {
                      const next = DECIMAL_OPTIONS.find(
                        (n) => `${n}` === event.target.value,
                      );
                      if (next !== undefined) void saveDecimals(next);
                    }}
                  >
                    {DECIMAL_OPTIONS.map((n) => (
                      <option key={n} value={n}>
                        {words.decimalsOption(n)}
                      </option>
                    ))}
                  </NativeSelect>
                </label>
              </div>
              <table
                data-testid="entry-totals"
                className={`${TABLE} w-full table-fixed`}
              >
                <thead>
                  <tr>
                    <th scope="col" className={HEAD_CELL}>
                      {words.siteHead}
                    </th>
                    {index.totals.years.map((y) => (
                      <th key={y} scope="col" className={HEAD_CELL}>
                        {`${y}`}
                      </th>
                    ))}
                    <th scope="col" className={HEAD_CELL}>
                      {words.unitHead}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    {
                      key: 'all',
                      name: words.total,
                      values: index.totals.all,
                    },
                    ...index.totals.bySite.map((site) => ({
                      key: site.siteId,
                      name: site.siteName,
                      values: site.values,
                    })),
                  ].map((line) => {
                    const sum = line.key === 'all';
                    const cell = sum ? cn(CELL, SUM_CELL) : CELL;
                    return (
                      <tr
                        key={line.key}
                        data-testid={`entry-total-${line.key}`}
                      >
                        <td className={cell}>
                          {!sum && (
                            <span
                              aria-hidden
                              className="mr-2 text-text-quaternary"
                            >
                              •
                            </span>
                          )}
                          {line.name}
                        </td>
                        {index.totals.years.map((y) => (
                          <td key={y} className={`${cell} tabular-nums`}>
                            {withComma(
                              shownAmount(
                                line.values[`${y}`] ?? null,
                                index.decimals,
                              ),
                            )}
                          </td>
                        ))}
                        <td className={cell}>{index.unit}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>
            <section className="flex flex-col gap-2">
              <h4 className="m-0 text-style-pre-heading-02 text-text-primary">
                {words.inputTitle}
              </h4>
              <div className="flex flex-col gap-3">
                {index.sites.length === 0 && (
                  <PageInfo data-testid="entry-no-facilities">
                    <span
                      data-testid="entry-no-facilities-line"
                      className="flex flex-wrap items-center gap-2"
                    >
                      {words.noFacilities}
                      {onOrganization && (
                        <Button
                          variant="outlineBlack"
                          shape="round"
                          size="sm"
                          disabled={saving}
                          onClick={toOrganization}
                        >
                          {words.toOrganization}
                        </Button>
                      )}
                    </span>
                  </PageInfo>
                )}
                {index.sites.map((site) => {
                  const block = blocks[site.siteId];
                  return block ?
                      <EntrySiteBlock
                        key={site.siteId}
                        site={site}
                        index={index}
                        block={block}
                        locked={locked}
                        busy={saving || periodBusy === site.siteId}
                        register={register}
                        addRef={(element) => {
                          if (element)
                            addButtons.current.set(site.siteId, element);
                        }}
                        removeRef={(element) => {
                          if (element)
                            removeButtons.current.set(site.siteId, element);
                        }}
                        onChange={(key, update) =>
                          change(site.siteId, key, update, (after) => [
                            cellKey(key, 'unit'),
                            ...after.edited.values.map((v) =>
                              cellKey(key, v.slot),
                            ),
                          ])
                        }
                        onCheck={(key, on) =>
                          setBlocks((old) => {
                            const was = old[site.siteId];
                            if (!was) return old;
                            const checked = new Set(was.checked);
                            if (on) checked.add(key);
                            else checked.delete(key);
                            return {
                              ...old,
                              [site.siteId]: { ...was, checked },
                            };
                          })
                        }
                        onRemove={() => setRemoving(site.siteId)}
                        onAdd={() => setAdding(site.siteId)}
                        onFactor={(draft) =>
                          setViewFactor({
                            factor: draft.before?.factor ?? index.factor,
                            row:
                              draft.before ?
                                { draft, siteId: site.siteId }
                              : null,
                          })
                        }
                        factorEdit={
                          pool ?
                            {
                              disabled:
                                locked ||
                                saving ||
                                lockBusy ||
                                periodBusy !== null,
                              onEdit: (draft) =>
                                setEditFactor({
                                  draft,
                                  siteId: site.siteId,
                                  current: draft.before?.factor ?? index.factor,
                                }),
                            }
                          : null
                        }
                        onHistory={(draft) =>
                          setViewHistory({ draft, siteId: site.siteId })
                        }
                        onPeriod={() => setPeriodOf(site.siteId)}
                      />
                    : null;
                })}
              </div>
            </section>
            <section className="flex flex-col gap-2">
              <label
                htmlFor="entry-memo"
                className="text-style-pre-heading-02 text-text-primary"
              >
                {words.memoLabel}
              </label>
              <Textarea
                id="entry-memo"
                className="min-h-[88px] border-border-tertiary px-4 py-3"
                ref={(element) => register(MEMO, element)}
                placeholder={words.memoPlaceholder}
                disabled={locked || saving}
                value={memo}
                aria-invalid={memoError || undefined}
                onChange={(event) => {
                  setMemo(event.target.value);
                  setMemoError(false);
                  setFootNotice(null);
                }}
              />
              {memoError && (
                <p
                  data-testid="entry-memo-error"
                  className="m-0 text-style-pre-caption-03 text-support-error-accent"
                >
                  {words.memoInvalid}
                </p>
              )}
            </section>
            <div className="flex items-center justify-end gap-2.5">
              <p
                role="alert"
                data-testid="entry-foot-notice"
                className="m-0 text-style-pre-caption-03 text-support-error-accent empty:hidden"
              >
                {footNotice}
              </p>
              <Button
                variant="solidBlack"
                shape="round"
                size="md"
                data-testid="entry-save"
                disabled={locked || saving || periodBusy !== null}
                onClick={() => void saveAll()}
              >
                {words.save}
              </Button>
            </div>
          </div>
        }
        {locking && (
          <ConfirmModal
            title={
              locking === 'edited' ? words.lockConfirm : words.lockConfirmPlain
            }
            cancel={words.cancel}
            confirm={words.lockOk}
            initialFocus="cancel"
            returnFocus={() => closeRef.current}
            testId="entry-lock-confirm"
            onClose={() => setLocking(null)}
            onConfirm={() => void changeLock(true)}
          />
        )}
        {viewFactor && (
          <EntryFactorDialog
            factor={viewFactor.factor}
            edit={
              pool && viewFactor.row ?
                {
                  disabled: locked || saving || lockBusy || periodBusy !== null,
                  dirty: rowDirty(viewFactor.row),
                  onEdit: () =>
                    setEditFactor(
                      viewFactor.row && {
                        ...viewFactor.row,
                        current: viewFactor.factor,
                        filled: 'customId' in viewFactor.factor,
                      },
                    ),
                }
              : null
            }
            onClose={() => setViewFactor(null)}
          />
        )}
        {pool && editFactor?.draft.before && (
          <EntryFactorEditDialog
            pool={pool}
            nodeId={nodeId}
            current={editFactor.current}
            startCustom={editFactor.filled ?? false}
            thisYear={Math.max(year, new Date().getFullYear())}
            onSubmit={(target, reason) =>
              setRowFactor(editFactor.draft.before!.rowId, target, reason)
            }
            onDone={(out) =>
              factorChanged(
                out,
                editFactor.siteId,
                editFactor.draft.before!.rowId,
              )
            }
            onGone={() => void read()}
            onClose={() => setEditFactor(null)}
          />
        )}
        {viewHistory?.draft.before && (
          <EntryHistoryDialog
            port={port}
            year={year}
            nodeId={nodeId}
            rowId={viewHistory.draft.before.rowId}
            operator={operator}
            rowDirty={rowDirty(viewHistory)}
            blockDirty={(blocks[viewHistory.siteId]?.drafts ?? []).some(
              draftEdited,
            )}
            onRestored={(out, line) =>
              restored(out, line.kind, viewHistory.siteId)
            }
            onGone={() => void read()}
            onClose={() => setViewHistory(null)}
          />
        )}
        {periodSite && (
          <EntryPeriodDialog
            current={periodSite.period}
            dirty={(blocks[periodSite.siteId]?.drafts ?? []).some(draftEdited)}
            onClose={() => setPeriodOf(null)}
            onPick={(period) => void changePeriod(periodSite, period)}
          />
        )}
        {leaving && (
          <ConfirmModal
            title={words.leaveConfirm}
            cancel={words.cancel}
            confirm={words.leaveOk}
            returnFocus={() => closeRef.current}
            testId="entry-leave"
            onClose={() => setLeaving(null)}
            onConfirm={
              leaving === 'organization' ? () => onOrganization?.() : close
            }
          />
        )}
        {removeSite && (
          <ConfirmModal
            title={words.removeConfirm}
            cancel={words.cancel}
            confirm={words.removeOk}
            returnFocus={() => {
              const button = removeButtons.current.get(removeSite.siteId);
              return button && !button.disabled ?
                  button
                : (addButtons.current.get(removeSite.siteId) ?? null);
            }}
            testId="entry-remove"
            onClose={() => setRemoving(null)}
            onConfirm={() => void removeChecked(removeSite)}
          />
        )}
        {addSite && (
          <EntryAddDialog
            facilityName={index?.name ?? ''}
            facilities={addChoices}
            onClose={() => setAdding(null)}
            onPick={(picked) => addPicked(addSite, picked)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

interface LockControlProps {
  locked: boolean;
  operator: boolean;
  disabled: boolean;
  onLock(): void;
  onUnlock(): void;
  /** S12-03 추정치 단추(Q6). */
  estimated: boolean;
  estimatedName: string;
  estimatedDisabled: boolean;
  onEstimated(): void;
}

/** 추정치 단추 꺼짐 꼴(S12C1 e3f9708d) — 크기·모양은 estimatedBox 와 같고 색만 회색 글·바탕 없음. */
const ESTIMATED_OFF =
  'inline-flex size-5 shrink-0 items-center justify-center rounded-[2px] bg-transparent text-text-tertiary';

/** #10 제목 옆 잠금 — 16 아이콘 + 안쪽 2 = 20(판 `.f12b-ibtn`) · 툴팁 「잠금」/「잠금 해제」. 고객사·잠김은 누르지 못하는 그림(풀기 0 — 469-2). */
function LockControl({
  locked,
  operator,
  disabled,
  onLock,
  onUnlock,
  estimated,
  estimatedName,
  estimatedDisabled,
  onEstimated,
}: LockControlProps) {
  // S12-03(Q6, e6 ②): 잠금 바로 옆(사이 4) 같은 크기의 추정치 단추 하나 · aria-pressed 토글 · 이름 「{자산/시설명} 추정치」(상태는 이름에 넣지 않음).
  // 켜짐 꼴은 판 S12-03_r2 `.f12b-est`: 목록 추정치 열과 같은 estimatedBox(true) + 물결.
  // 꺼짐은 S12C1 e3f9708d(마크스폰 댓글 — 「회색·바탕 없음」): 이웃 잠금 단추 열림 꼴과 같이 text-text-tertiary·bg-transparent(공용 estimatedBox 는 S2 목록이 같이 써 그대로).
  const estimate = (
    <button
      type="button"
      aria-pressed={estimated}
      aria-label={estimatedName}
      data-testid="entry-estimated"
      disabled={estimatedDisabled}
      className={`${estimated ? estimatedBox(true) : ESTIMATED_OFF} cursor-pointer border-0 p-0 focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-40`}
      onClick={onEstimated}
    >
      <EstimatedWave />
    </button>
  );
  return (
    <span
      data-testid="entry-lock-row"
      className="inline-flex items-center gap-1"
    >
      <LockButton
        locked={locked}
        operator={operator}
        disabled={disabled}
        onLock={onLock}
        onUnlock={onUnlock}
      />
      {estimate}
    </span>
  );
}

function LockButton({
  locked,
  operator,
  disabled,
  onLock,
  onUnlock,
}: Omit<
  LockControlProps,
  'estimated' | 'estimatedName' | 'estimatedDisabled' | 'onEstimated'
>) {
  const icon =
    locked ?
      <LockIcon aria-hidden data-testid="entry-locked" />
    : <LockOpenIcon aria-hidden />;
  const box = `inline-flex items-center rounded-control p-0.5 [&_svg]:size-4 ${
    locked ? 'bg-background-brand text-text-brand' : 'text-text-tertiary'
  }`;
  if (locked && !operator)
    return (
      <span role="img" aria-label={words.lockedLabel} className={box}>
        {icon}
      </span>
    );
  const label = locked ? words.unlock : words.lock;
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={label}
            data-testid="entry-lock"
            disabled={disabled}
            className={`${box} cursor-pointer border-0 focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-40 ${
              locked ? '' : 'bg-transparent'
            }`}
            onClick={locked ? onUnlock : onLock}
          >
            {icon}
          </button>
        </TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
