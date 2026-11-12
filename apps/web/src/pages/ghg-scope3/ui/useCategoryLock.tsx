// 상세 머리의 잠그기·풀기 흐름(밴드 S3W3a ③ — 값 파일 E1·Q9, 처분 Q7·Q9).
//   잠그기: 사용자가 본 current.runId 를 보낸다(새로 읽어 보내면 stale_run 이 무력해진다). 고객사는 확인 창 뒤, 운영 관리자는 바로.
//   풀기: 누른 때 연도를 다시 읽어 그 값의 핀 ≠ 기준이면 확인 창(풀면 고친 행이 빠지고 되돌릴 수 없다), 같으면 바로. 읽기 실패면 넘어가지 않고 실패 줄.
//   쓰기 답의 category 로 화면을 덮지 않는다 — 답 뒤 늘 reread(새 실행이 동시에 기준이 되면 옛 값이다, S3K2b-1 리뷰 L3).
//   stale_run 은 지금 결과를 다시 읽는다(본 값이 낡았다). not_computed·그 밖은 한 줄만.
//   고객사가 잠그면 단추가 그림으로 바뀌어 초점 돌아올 자리가 사라진다 — afterLock 이 [목록]으로 옮긴다.
//   답이 끊겨도(failed) 서버에 들었을 수 있다 — 다시 읽은 자물쇠가 바라던 쪽이면 ok 와 같이(줄 없음·afterLock), 아니면 실패 줄(sid:MARC-ISSUE-587, 발주서 S3W3d 1-6 A).
import { useEffect, useRef, useState } from 'react';

import type {
  CompanyRefusal,
  Scope3Port,
  Scope3WriteCode,
} from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import type { CurrentCard } from '../../../entities/ghg-scope3/model/index.ts';
import { ConfirmModal } from './ConfirmModal.tsx';
import { LockControl } from './LockControl.tsx';

const words = S3_TEXT.lock;

/** seen = 창을 연 때 사용자가 본 실행(창이 열린 사이의 다시 읽기가 값을 바꿔도 본 값을 보낸다). */
type Window =
  { kind: 'lock'; seen: string } | { kind: 'unlock'; edited: number };

export interface CategoryLockOptions {
  port: Scope3Port;
  year: number;
  card: CurrentCard;
  operator: boolean;
  /** 쓰기 답 뒤 지금 결과를 다시 읽는다(상세·검색·쪽은 그대로). */
  reread(): Promise<void>;
  /** 고객사가 잠근 뒤 초점 옮기기. */
  afterLock(): void;
}

/** 실패 한 줄. stale_run·not_computed 는 다시 시도해도 같은 값으로 막혀 갈래마다 글이 다르다. */
function problemOf(
  out:
    | { kind: 'refused'; company: CompanyRefusal }
    | { kind: 'rejected'; code: Scope3WriteCode | null }
    | { kind: 'failed' },
): string {
  if (out.kind === 'refused') return S3_TEXT.company[out.company];
  if (out.kind === 'rejected' && out.code === 'STALE_RUN')
    return words.lockStale;
  if (out.kind === 'rejected' && out.code === 'NOT_COMPUTED')
    return words.lockNotComputed;
  return words.lockFailed;
}

export function useCategoryLock({
  port,
  year,
  card,
  operator,
  reread,
  afterLock,
}: CategoryLockOptions) {
  const [opened, setOpened] = useState<Window | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const busyRef = useRef(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  /** 내려간 뒤의 답은 버린다. */
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  /** 답이 끊긴 쓰기가 바란 자물쇠. 다시 읽기 뒤 settled 가 한 번 재고 비운다(다음 쓰기에 남지 않는다). */
  const wished = useRef<boolean | null>(null);
  const [settled, setSettled] = useState(0);
  const locked = card.state?.locked ?? false;
  // reread 의 답 직후 card 는 낡았다 — settled 는 reread 뒤에 올리므로 이 effect 는 다시 읽은 값이 그려진 뒤에 돈다.
  useEffect(() => {
    const want = wished.current;
    if (want === null) return;
    wished.current = null;
    if (locked !== want) {
      setProblem(problemOf({ kind: 'failed' }));
      return;
    }
    if (locked && !operator) afterLock();
    // settled 로만 돈다(locked 가 따로 바뀌는 때는 재지 않는다).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settled]);

  /** 일 하나만(두 번 누름 막음). */
  const once = async (work: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setProblem(null);
    await work();
    busyRef.current = false;
    if (alive.current) setBusy(false);
  };

  /**
   * 쓰기가 안 된 갈래. failed 는 「서버가 안 했다」가 아니다(답이 끊겼거나 2xx 꼴이 틀림 — 이미 들었을 수 있다) — 다시 읽은 뒤에야 실패 줄을 정한다.
   * stale_run 도 다시 읽는다. refused·그 밖 rejected 는 서버가 거절했으니 그대로 둔다.
   */
  const notDone = async (
    out: Parameters<typeof problemOf>[0],
    want: boolean,
  ) => {
    if (out.kind === 'failed') {
      wished.current = want;
      await reread();
      if (alive.current) setSettled((now) => now + 1);
      return;
    }
    if (alive.current) setProblem(problemOf(out));
    if (out.kind === 'rejected' && out.code === 'STALE_RUN') await reread();
  };

  const lock = async (seen: string) => {
    const out = await port.lock(year, card.id, seen);
    // 답이 오면 [목록]으로 나갔어도 늘 다시 읽는다(서버와 반대 자물쇠가 남지 않게). alive 는 이 상세의 초점·한 줄만 막는다.
    if (out.kind === 'ok') {
      await reread();
      if (alive.current && !operator) afterLock();
      return;
    }
    await notDone(out, true);
  };

  const unlock = async () => {
    const out = await port.unlock(year, card.id);
    if (out.kind === 'ok') await reread();
    else await notDone(out, false);
  };

  const askUnlock = async () => {
    const read = await port.year(year);
    if (!alive.current) return;
    if (read.kind !== 'ok') {
      setProblem(problemOf(read));
      return;
    }
    const state = read.value.categories.find((one) => one.category === card.id);
    if (state?.current && state.current.runId !== read.value.baseRunId)
      setOpened({ kind: 'unlock', edited: state.editedRows });
    else await unlock();
  };

  const control = (
    <LockControl
      locked={locked}
      operator={operator}
      disabled={busy || (!locked && card.sheets === 0)}
      buttonRef={buttonRef}
      onLock={() => {
        const seen = card.state?.current?.runId;
        if (seen === undefined) return;
        if (operator) void once(() => lock(seen));
        else setOpened({ kind: 'lock', seen });
      }}
      onUnlock={() => void once(askUnlock)}
    />
  );

  const close = () => setOpened(null);
  const windows =
    opened === null ? null
    : opened.kind === 'lock' ?
      <ConfirmModal
        testId="s3-lock-confirm"
        title={words.lockConfirmPlain}
        cancel={words.cancel}
        confirm={words.lockOk}
        initialFocus="cancel"
        returnFocus={() => buttonRef.current}
        onConfirm={() => {
          close();
          void once(() => lock(opened.seen));
        }}
        onClose={close}
      />
    : <ConfirmModal
        testId="s3-unlock-confirm"
        title={words.unlockTitle}
        body={words.unlockBody(opened.edited)}
        cancel={words.cancel}
        confirm={words.unlockOk}
        initialFocus="cancel"
        returnFocus={() => buttonRef.current}
        onConfirm={() => {
          close();
          void once(unlock);
        }}
        onClose={close}
      />;

  return { control, windows, problem };
}
