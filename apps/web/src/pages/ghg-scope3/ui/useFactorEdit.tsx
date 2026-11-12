// 그룹별 배출계수 창의 상태와 계수 수정 흐름(밴드 S3W3c2 ① — 발주서 1-6 「창의 상태」·「쓰기 답 표」, 처분 C1·C3·C4·C8~C13).
//   ★ 창을 연 때 {seen: current.runId, 줄 사진, 누른 단추} 를 얼린다. [수정]·[저장]·다시 시도는 그 seen·그 rowId 로만 보낸다 —
//     누른 때 지금 실행을 다시 읽지 않는다(창이 열린 사이 새 실행이면 본 값을 보내 서버 stale_run 이 일한다). 사진을 rowId 로 다시 찾아 갈아 끼우지 않는다
//     (rowId 는 새 실행에도 같은 글자이고 다른 줄이다). 잠김은 지금 값으로 [수정]만 막는다 — 수정 꼴에 들어간 뒤 잠기면 [저장]은 두고 서버 locked 가 일한다.
//   쓰기 답으로 화면을 덮지 않는다 — 답 뒤 reread(prop 하나). 답이 오면 상세가 내려갔어도 다시 읽는다. alive 는 초점·한 줄·창 상태만 막는다.
//   failed 는 「서버가 안 했다」가 아니다(답이 끊겼거나 2xx 꼴이 틀림) — 두 창을 둔 채 다시 읽는다. 같은 몸 다시 시도는 서버가 사건 0 으로 받아 안전하다.
//   [저장] 차례: 같은 고름이면 요청 0·보기 꼴(C10 — 값 검사보다 먼저) → 직접입력이면 칸 검사(첫 틀린 칸에 초점) → 사유 창(얼럿 없이 — C3).
//     failed 를 한 번 받은 창은 같은 고름 판정을 건너뛴다(감독 처분 R2 — 얼린 사진이 서버보다 낡았을 수 있다. 같은 몸은 서버가 사건 0).
//   직접입력 칸은 늘 켜 둔다. 칸에 글자를 넣으면 라디오를 직접입력으로 옮기고, 비워도 되돌리지 않는다. 다른 라디오를 누르면 그 고름을
//     따르고 칸 값은 두되 저장에 쓰지 않는다(감독 처분 R3 — e6).
//   답 뒤 다시 읽는 중(busy)에는 창을 열지 않는다(감독 처분 R1 — 고치기 전 사진을 얼리지 않게).
//   닫을 때 초점: 누른 칸 단추가 살아 있으면 그리로, 아니면 표 밖(fallback). 성공·잠김·그사이 갈래는 다시 읽기가 끝난 뒤 정한다(C4 — 합이 바뀌면 칸이 다시 달려 단추가 사라진다).
//   상태는 CategoryDetail 쪽에 둔다 — 칸은 컨텍스트로 open 을 부르고, 고름·창 상태는 표 columns 의존에 들지 않는다(b 규칙).
import { useEffect, useRef, useState } from 'react';
import type { Ref } from 'react';

import type { Scope3Port } from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  FACTOR_CUSTOM_FIELDS,
  customFaults,
  factorBlock,
  factorInput,
  initialCustom,
  initialPick,
  sameFactorPick,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  CategoryId,
  FactorCustomDraft,
  FactorCustomField,
  FactorPick,
  FactorTextFault,
  FactorValueFault,
  ResultRow,
} from '../../../entities/ghg-scope3/model/index.ts';
import { FactorWindowDialog } from './FactorWindowDialog.tsx';
import type { FactorEditView } from './FactorWindowDialog.tsx';
import { RowReasonDialog } from './RowReasonDialog.tsx';
import type { EditNotice } from './useRowEdit.tsx';

const words = S3_TEXT.detail.factorEdit;
const rowWords = S3_TEXT.rowEdit;

/** 연 때 얼린 것. */
interface Opened {
  seen: string | null;
  row: ResultRow;
  button: HTMLElement;
}

/** 사유 창을 연 때 얼린 고름. */
interface Asking {
  pick: FactorPick;
  draft: FactorCustomDraft;
  initial: string;
}

const FAULT_TEXT: Record<FactorValueFault | FactorTextFault, string> = {
  required: words.required,
  notPositive: words.notPositive,
  decimals: words.decimals,
  tooLong: words.tooLong,
};

/** 서버 422 custom.* 칸 → 칸 아래 글(C11 — 값은 0보다 큰 숫자 글, 제목·출처는 200자 글). */
const SERVER_FIELD: Record<string, FactorCustomField> = {
  'custom.title': 'title',
  'custom.value': 'value',
  'custom.source': 'source',
};

export interface FactorEditOptions {
  port: Scope3Port;
  category: CategoryId;
  /** 지금 결과 실행(card.state.current.runId — 마지막 실행이 아니다). 연 때만 읽는다. */
  runId: string | null;
  /** 지금 잠김 — [수정]만 막는다. */
  locked: boolean;
  reread(): Promise<void>;
  /** 표 밖 초점 자리. */
  fallback(): HTMLElement | null;
}

export function useFactorEdit({
  port,
  category,
  runId,
  locked,
  reread,
  fallback,
}: FactorEditOptions) {
  const [opened, setOpened] = useState<Opened | null>(null);
  const [mode, setMode] = useState<'view' | 'edit'>('view');
  const [pick, setPick] = useState<FactorPick>({ choice: 'applied' });
  const [draft, setDraft] = useState<FactorCustomDraft>({
    title: '',
    value: '',
    source: '',
  });
  const [faults, setFaults] = useState<
    Partial<Record<FactorCustomField, string>>
  >({});
  const [notEditable, setNotEditable] = useState(false);
  const [asking, setAsking] = useState<Asking | null>(null);
  /** 사유 창이 떠 있다(닫힌 뒤 한 틱 더 — 같은 누름이 아래 창까지 닫지 않게). */
  const reasonUp = useRef(false);
  useEffect(() => {
    if (asking !== null) {
      reasonUp.current = true;
      return;
    }
    const timer = setTimeout(() => {
      reasonUp.current = false;
    }, 0);
    return () => clearTimeout(timer);
  }, [asking]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [notice, setNotice] = useState<EditNotice | null>(null);
  /** custom.* 거절 뒤 간직한 사유(다음 사유 창의 처음 글). */
  const [kept, setKept] = useState('');
  const busyRef = useRef(false);
  const alive = useRef(true);
  /** 두 창을 닫고 다시 읽은 뒤 초점을 옮기는 중(닫힐 때 공용 초점 돌림을 막는다). */
  const later = useRef(false);
  /** 이 창에서 failed 를 받았는가(R2 — 같은 고름 판정을 건너뛴다). */
  const failedOnce = useRef(false);
  /** 사유 창만 닫힐 때 초점 자리(null 이면 수정 꼴 [저장]). */
  const afterReason = useRef<HTMLElement | null>(null);
  const fields = useRef<Partial<Record<FactorCustomField, HTMLInputElement>>>(
    {},
  );
  const content = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLElement | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  /** 누른 칸 단추가 살아 있고 켜져 있으면 그리로, 아니면 표 밖. */
  const target = () => {
    const pressed = button.current;
    return pressed?.isConnected && !pressed.matches(':disabled') ?
        pressed
      : fallback();
  };

  const open = (row: ResultRow, pressed: HTMLElement) => {
    if (busyRef.current) return;
    // ★ 연 때 얼린다 — seen 은 지금 결과 실행, 사진은 누른 줄 그대로.
    button.current = pressed;
    later.current = false;
    failedOnce.current = false;
    setOpened({ seen: runId, row, button: pressed });
    setMode('view');
    setNotEditable(false);
    setFaults({});
    setNotice(null);
  };

  const block =
    opened === null ? null : (
      factorBlock(opened.row, { locked, seen: opened.seen })
    );

  const close = () => {
    setOpened(null);
    setAsking(null);
    setMode('view');
  };

  const startEdit = () => {
    if (opened === null || block !== null || notEditable) return;
    setPick(initialPick(opened.row));
    setDraft(initialCustom(opened.row));
    setFaults({});
    setKept('');
    setMode('edit');
  };

  const cancel = () => {
    setMode('view');
    setFaults({});
  };

  const focusField = (field: FactorCustomField) =>
    fields.current[field]?.focus();

  const save = (keep = '') => {
    if (opened === null || busyRef.current) return;
    // C10: 같은 고름이면 요청 0 · 보기 꼴(판정은 얼린 사진 — 값 검사보다 먼저).
    if (!failedOnce.current && sameFactorPick(opened.row, pick, draft)) {
      setMode('view');
      setFaults({});
      return;
    }
    if (pick.choice === 'custom') {
      const found = customFaults(draft);
      const shown: Partial<Record<FactorCustomField, string>> = {};
      for (const field of FACTOR_CUSTOM_FIELDS) {
        const fault = found[field];
        if (fault) shown[field] = FAULT_TEXT[fault];
      }
      setFaults(shown);
      const first = FACTOR_CUSTOM_FIELDS.find((field) => shown[field]);
      if (first) {
        focusField(first);
        return;
      }
    } else setFaults({});
    setProblem(null);
    setFailure(null);
    afterReason.current = null;
    reasonUp.current = true;
    setAsking({ pick, draft, initial: keep });
  };

  /** 두 창을 닫고 표 위 한 줄. 초점은 (다시 읽은 뒤) settleFocus 가 옮긴다. */
  const closeAll = (next: EditNotice) => {
    if (!alive.current) return;
    later.current = true;
    setAsking(null);
    setOpened(null);
    setMode('view');
    setNotice(next);
  };

  /** 닫힌 창들의 공용 초점 돌림이 끝난 뒤 옮긴다. */
  const settleFocus = () => {
    if (!alive.current) return;
    setTimeout(() => {
      later.current = false;
      if (alive.current) target()?.focus();
    }, 0);
  };

  const send = async (frozen: Opened, wanted: Asking, reason: string) => {
    const { row, seen } = frozen;
    if (row.rowId === null || seen === null) return;
    const out = await port.factor(
      seen,
      category,
      factorInput(row.rowId, wanted.pick, wanted.draft, reason),
    );
    if (out.kind === 'ok') {
      closeAll({ tone: 'status', text: words.saved });
      await reread();
      settleFocus();
      return;
    }
    if (out.kind === 'refused') {
      closeAll({ tone: 'alert', text: S3_TEXT.company[out.company] });
      settleFocus();
      return;
    }
    if (out.kind === 'failed') {
      // 쓰기가 들어갔을 수 있다 — 두 창을 둔 채 다시 읽는다(창은 사진 그대로).
      failedOnce.current = true;
      if (alive.current) setFailure(rowWords.failed);
      await reread();
      return;
    }
    const { code, fields: names } = out;
    if (code === 'LOCKED' || code === 'STALE_RUN') {
      closeAll({
        tone: 'alert',
        text: code === 'LOCKED' ? rowWords.locked : rowWords.stale,
      });
      await reread();
      settleFocus();
      return;
    }
    if (code === 'VALIDATION_ERROR') {
      // 단수 rowId(제외의 rowIds 와 다르다) · 없는 순위 — 그사이 결과가 바뀐 갈래.
      if (names.includes('rowId') || names.includes('rank')) {
        closeAll({ tone: 'alert', text: rowWords.stale });
        await reread();
        settleFocus();
        return;
      }
      if (names.includes('reason')) {
        if (alive.current) setProblem(rowWords.reason.rejected);
        return;
      }
      const shown: Partial<Record<FactorCustomField, string>> = {};
      for (const name of names) {
        const field = SERVER_FIELD[name];
        if (field)
          shown[field] = field === 'value' ? words.notPositive : words.tooLong;
      }
      const first = FACTOR_CUSTOM_FIELDS.find((field) => shown[field]);
      if (first) {
        if (!alive.current) return;
        // 사유 창을 닫고 쓴 사유는 간직한다(다시 [저장]이면 처음 글) · 수정 꼴은 둔다.
        afterReason.current = fields.current[first] ?? null;
        setFaults(shown);
        setAsking(null);
        setKept(reason);
        return;
      }
    }
    if (code === 'FACTOR_NOT_EDITABLE') {
      if (!alive.current) return;
      // C9: 사유 창·수정 칸을 닫고 사유는 버린다 · 그 창이 열린 동안 [수정] 막음 · 다시 읽지 않는다(서버 값이 안 바뀜).
      afterReason.current = content.current;
      setAsking(null);
      setMode('view');
      setFaults({});
      setNotEditable(true);
      setKept('');
      return;
    }
    if (alive.current) setFailure(rowWords.failed);
  };

  const confirm = async (reason: string) => {
    if (opened === null || asking === null || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setProblem(null);
    setFailure(null);
    await send(opened, asking, reason);
    busyRef.current = false;
    if (alive.current) setBusy(false);
  };

  const view: FactorEditView = {
    mode,
    block,
    notEditable,
    busy,
    pick,
    draft,
    faults,
    fieldRef:
      (field: FactorCustomField): Ref<HTMLInputElement> =>
      (element) => {
        if (element) fields.current[field] = element;
        else delete fields.current[field];
      },
    contentRef: content,
    returnFocus: () => (later.current ? false : target()),
    holdOutside: () => reasonUp.current,
    onEdit: startEdit,
    onCancel: cancel,
    onSave: () => save(kept),
    onPick: (next) => {
      setPick(next);
      setFaults({});
    },
    onDraft: (field, value) => {
      setDraft((now) => ({ ...now, [field]: value }));
      if (value !== '') setPick({ choice: 'custom' });
      setFaults((now) => {
        if (!(field in now)) return now;
        const next = { ...now };
        delete next[field];
        return next;
      });
    },
  };

  const dialog =
    opened === null ? null : (
      <>
        <FactorWindowDialog row={opened.row} edit={view} onClose={close} />
        {asking !== null && (
          <RowReasonDialog
            busy={busy}
            problem={problem}
            failure={failure}
            initial={asking.initial}
            returnFocus={() =>
              later.current ? false : (
                (afterReason.current ??
                content.current?.querySelector<HTMLElement>(
                  '[data-testid="s3-factor-save"]',
                ) ??
                null)
              )
            }
            onConfirm={(reason) => void confirm(reason)}
            onClose={() => setAsking(null)}
          />
        )}
      </>
    );

  return {
    /** 창을 연다(칸 단추가 부른다). */
    open,
    notice,
    dialog,
  };
}
