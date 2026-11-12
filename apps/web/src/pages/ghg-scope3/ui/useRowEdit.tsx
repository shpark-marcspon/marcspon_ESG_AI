// 상세 표의 고름·제외·복구 흐름(밴드 S3W3b ② — 발주서 1-6 쓰기 답 표, 값 파일 1·4절).
//   쓰는 실행은 card.state.current.runId(마지막 실행이 아니다). 사유 창을 연 때 {종류, seen, rowIds} 를 얼린다 — 창이 열린 사이 다시 읽기가 값을 바꿔도 본 값을 보내 stale_run 이 일하게. 다시 시도도 그 값.
//   쓰기 답의 category·rows 로 화면을 덮지 않는다 — 답 뒤 reread(S3K2b-1 리뷰 L3). 답이 오면 상세가 내려갔어도 다시 읽는다. alive 는 초점·한 줄·고름만 막는다.
//   failed 는 「서버가 안 했다」가 아니다(답이 끊겼거나 2xx 꼴이 틀림) — 창을 둔 채 다시 읽는다. 다시 시도는 서버가 이미 그 상태인 줄을 건너뛰어 안전하다.
//   rowId 는 「시트!엑셀 줄」이라 새 실행에도 같은 글자가 있고 다른 줄이다 — 실행이 바뀌거나 잠기면 고름을 푼다(sid:MARC-ENT-570). 얼린 창은 건드리지 않는다.
//   성공·잠김·그사이 뒤 고름이 풀려 누른 단추가 막히므로 초점은 afterDone(표 밖 [목록] — B4)으로.
import { useEffect, useRef, useState } from 'react';

import type { Scope3Port } from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  overRowLimit,
  pick,
  rowIdsOf,
  rowsToSend,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  CategoryId,
  ResultRow,
  RowEditKind,
} from '../../../entities/ghg-scope3/model/index.ts';
import { RowReasonDialog } from './RowReasonDialog.tsx';

const words = S3_TEXT.rowEdit;

/** 표 위 한 줄. status 는 성공, alert 는 실패. */
export interface EditNotice {
  tone: 'status' | 'alert';
  text: string;
}

interface Frozen {
  kind: RowEditKind;
  seen: string;
  rowIds: string[];
}

export interface RowEditOptions {
  port: Scope3Port;
  category: CategoryId;
  /** 지금 결과 실행(없으면 막음). */
  runId: string | null;
  locked: boolean;
  /** 그 카테고리 processed 시트의 줄 전부(덧씌운 값). */
  rows: readonly ResultRow[];
  reread(): Promise<void>;
  /** 표 밖 초점 자리. */
  fallback(): HTMLElement | null;
}

export function useRowEdit({
  port,
  category,
  runId,
  locked,
  rows,
  reread,
  fallback,
}: RowEditOptions) {
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [opened, setOpened] = useState<Frozen | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [notice, setNotice] = useState<EditNotice | null>(null);
  const busyRef = useRef(false);
  /** 창을 연 단추. 닫힐 때 고름이 풀렸으면 null(표 밖으로). */
  const pressed = useRef<HTMLElement | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  // 실행이 바뀌거나 잠기면 고름을 푼다 · 다시 읽은 뒤 사라진 줄은 뺀다. 그림 중 상태 맞춤.
  const scope = locked ? null : runId;
  const [heldScope, setHeldScope] = useState(scope);
  const known = new Set(rowIdsOf(rows));
  if (heldScope !== scope) {
    setHeldScope(scope);
    setChosen(new Set());
  } else if ([...chosen].some((id) => !known.has(id)))
    setChosen(new Set([...chosen].filter((id) => known.has(id))));

  const blocked = locked || runId === null;
  const excludeIds = rowsToSend(rows, chosen, 'exclude');
  const restoreIds = rowsToSend(rows, chosen, 'restore');

  const choose = (ids: readonly string[], on: boolean) => {
    setNotice(null);
    setChosen((now) => pick(now, ids, on));
  };
  const clearChosen = () => setChosen(new Set());

  const ask = (kind: RowEditKind, button: HTMLElement | null) => {
    const ids = kind === 'exclude' ? excludeIds : restoreIds;
    if (runId === null || blocked || ids.length === 0) return;
    if (overRowLimit(ids)) {
      setNotice({ tone: 'alert', text: words.tooMany });
      return;
    }
    setNotice(null);
    setProblem(null);
    setFailure(null);
    pressed.current = button;
    setOpened({ kind, seen: runId, rowIds: ids });
  };

  /** 창을 닫고 고름을 풀고 한 줄(성공·잠김·그사이 갈래). */
  const settle = (next: EditNotice) => {
    if (!alive.current) return;
    pressed.current = null;
    setOpened(null);
    clearChosen();
    setNotice(next);
  };

  const send = async ({ kind, seen, rowIds }: Frozen, reason: string) => {
    const write = kind === 'exclude' ? port.exclude : port.restore;
    const out = await write(seen, category, rowIds, reason);
    if (out.kind === 'ok') {
      settle({
        tone: 'status',
        text: (kind === 'exclude' ? words.excluded : words.restored)(
          rowIds.length,
        ),
      });
      await reread();
      return;
    }
    if (out.kind === 'refused') {
      if (!alive.current) return;
      setOpened(null);
      setNotice({ tone: 'alert', text: S3_TEXT.company[out.company] });
      return;
    }
    if (out.kind === 'failed') {
      if (alive.current) setFailure(words.failed);
      await reread();
      return;
    }
    if (out.code === 'LOCKED') {
      settle({ tone: 'alert', text: words.locked });
      await reread();
      return;
    }
    if (out.code === 'STALE_RUN') {
      settle({ tone: 'alert', text: words.stale });
      await reread();
      return;
    }
    if (out.code === 'VALIDATION_ERROR' && out.fields.includes('reason')) {
      if (alive.current) setProblem(words.reason.rejected);
      return;
    }
    if (out.code === 'VALIDATION_ERROR' && out.fields.includes('rowIds')) {
      settle({ tone: 'alert', text: words.stale });
      await reread();
      return;
    }
    if (alive.current) setFailure(words.failed);
  };

  const confirm = async (frozen: Frozen, reason: string) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setProblem(null);
    setFailure(null);
    await send(frozen, reason);
    busyRef.current = false;
    if (alive.current) setBusy(false);
  };

  /** 누른 단추가 살아 있고 켜져 있으면 그리로, 아니면 표 밖으로(막힌 단추는 초점을 못 받는다). */
  const focusTarget = () => {
    const button = pressed.current;
    return button?.isConnected && !button.matches(':disabled') ?
        button
      : fallback();
  };

  const dialog =
    opened === null ? null : (
      <RowReasonDialog
        busy={busy}
        problem={problem}
        failure={failure}
        returnFocus={focusTarget}
        onConfirm={(reason) => void confirm(opened, reason)}
        onClose={() => setOpened(null)}
      />
    );

  return {
    chosen,
    blocked,
    excludeCount: excludeIds.length,
    restoreCount: restoreIds.length,
    notice,
    dialog,
    choose,
    clearChosen,
    ask,
  };
}
