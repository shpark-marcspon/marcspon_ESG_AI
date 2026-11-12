// 검토 읽기·쓰기 훅(밴드 FW2 ①, GW-05·05a·05b·05c). 검토 JSON 을 거울로 지키고, 본문은 domain(markUpdate·confirmUpdate)이 짓는다.
//   - 채택·제외·확정은 PUT 이 끝난 뒤에 반영한다(서버가 돌려준 검토를 넣는다. 앞질러 바꾸지 않는다).
//   - 실패하면 검토는 그대로 두고 saveError 를 단다. 409 review_locked 면 다시 읽어 잠긴 상태를 넣고 saveError = review_locked.
//     409 run_not_done·no_review 는 다시 읽지 않고 saveError 에 그 code 를 단다(화면 글은 config/text.ts 의 saveRunNotDone·saveNoReview — 밴드 PL1 ②).
//   - 저장 중에는 다음 저장을 받지 않는다(false 를 돌려준다) — 본문이 늘 marks 전부라 앞 저장 뒤의 검토에서 지어야 한다 [B3].
//     막기는 ref(busy)로 한다: saving 상태는 다음 그리기에야 바뀌어 같은 그리기 안의 두 번째 부름을 놓친다(밴드 FW2 ⑤).
//   - 저장이 끝나기 전에 runId 가 바뀌면 늦게 온 저장 결과(와 409 뒤 다시 읽기)는 버린다 — 옛 실행의 검토가 새 실행의 읽기 상태를
//     덮지 않게(발주서 덧붙임 3). 그 저장의 참·거짓은 그대로 돌려준다.
// retry(밴드 LE1 ①): 읽기의 [다시 시도]. readReview 가 거절하지 않아 useLoad 는 늘 ready 이므로 reload 가 아니라 retry(loading 부터)다.
// 확정 전 다시 읽기(밴드 GW1R ③ Q14 — 디자인 답 ②③): 확정은 PUT 전에 검토를 GET 으로 다시 읽는다.
//   - marks 가 화면 값과 다르면(다른 창·다른 사람이 바꿈) PUT 하지 않고 saveError = stale. 화면은 [새로 불러오기](reload)를 둔다.
//   - 이미 확정돼 있으면(또는 확정 PUT 이 409 review_locked 면) 다시 읽은 확정 상태를 넣고 saveError = already_confirmed(잘못이 아니다 — 회색 정보 줄).
//   - 다시 읽기가 실패하면 PUT 하지 않고 rejected.
//   표시 저장(mark)의 409 review_locked 는 그대로 review_locked(빨강).
// 자동 저장 시각(밴드 GW2R ② Q6 — review@1 에 저장 시각이 없다): 이 탭에서 검토 PUT 이 받아들여진 마지막 때(ISO). 저장소·실행마다
//   모듈 기억(WeakMap)에 둔다 — GW-05 에서 저장하고 GW-04 로 가도 같은 값을 본다(새로고침하면 없다). 실패한 저장은 바꾸지 않는다.
// [새로 불러오기] 실패(밴드 GW2R ② — sid:MARC-ISSUE-227 ②): 다시 읽기가 안 되면 보던 검토를 그대로 두고 saveError = reload_failed
//   (화면 전체를 「불러오지 못함」으로 바꾸지 않는다). 확정은 계속 막힌다(화면이 stale·reload_failed 면 [확정]을 끈다).
// 무효 조건: 여러 사람이 같은 실행을 동시에 검토하면 뒤 저장이 앞 사람의 표시를 덮는다(서버 꼴이 marks 전부를 갈아 넣는다 — 발주서 §5).
//   확정 전 다시 읽기는 확정만 지킨다(GET 과 PUT 사이도 비어 있다 — 서버 If-Match 는 서버 물음).
// 고침(밴드 G1b-3 ③, review@2 — 본문은 domain editUpdate: marks 그대로 + 그 실행의 고침 전부):
//   - edit 는 mark 와 같은 저장 길(늦은 저장 막기·savedAt·409 갈래)이다. 실패(400 INVALID_REVIEW 등)면 saveError 를 달고 false —
//     화면은 고치던 칸을 닫지 않고 글을 남긴다.
//   - 앞 저장이 도는 중에 온 edit 는 버리지 않고 기다린다: 앞 저장이 끝나면(성공·실패 모두) 그 뒤의 검토에서 본문을 지어 한 번 보낸다.
//     기다리는 동안 더 온 edit 는 같은 한 번에 차례로 얹는다(칸마다 마지막 값). 그 사이 runId 가 바뀌면 보내지 않고 false.
//   - 확정 전 다시 읽기의 「서버와 같은가」는 marks 와 edits 둘 다 본다(edits 는 값만 — editedAt·editedBy 는 견주지 않는다).
// 저장 경합(밴드 GR1, sid:MARC-ISSUE-281 — 디자인 e9 답):
//   - 저장 중에 온 mark·confirm 은 여전히 보내지 않고 false 지만 조용히 버리지 않는다: busyRefusals 를 하나 올린다(화면은 잠깐
//     「저장 중이에요」 알림). 화면은 저장 중 [채택]·[제외]·[확정]을 끄고 「저장하고 있어요」를 보여 이 갈래를 드물게 한다.
//   - 마지막으로 받은 검토가 확정이면 기다린 고침을 보내지 않고 false 로 끝낸다(확정 뒤 409 review_locked 빨간 줄이
//     already_confirmed 회색 줄을 덮지 않게).
// 근거 고침·재판단(밴드 GRJ1 ③, review@3):
//   - evidence(change) 는 edit 와 같은 저장 길(기다림 줄도 같이 — 본문은 domain evidenceUpdate, 고침과 같이 기다렸으면 한 본문에).
//   - rejudge(itemIndex): 도는(기다리는) 저장이 끝나기를 기다린 뒤 POST(근거가 서버에 실린 뒤 만든다). 받으면 검토를 조용히 다시 읽는다.
//     409 rejudge_running·nothing_to_rejudge·review_locked 는 다시 읽고 saveError 에 그 code. 그 밖은 rejected. 누른 뒤 답까지는
//     pressing 에 그 문장(화면이 버튼을 「재판단 중…」으로 끈다).
//   - 다시 읽기: 받은 검토에 running 줄이 있으면 REJUDGE_POLL_MS 뒤 한 번 조용히 다시 읽는다(받을 때마다 다시 잼 — running 0 이면 멈춤).
//     실행이 바뀌거나 화면이 내려가면 멈춘다. 다시 읽기 실패는 saveError 를 바꾸지 않고 다음 간격에 또 본다. 그 사이 저장이 받아들여졌으면
//     그 답을 버린다(reload 와 같은 M1).
//   - 확정 PUT 의 409 rejudge_running(④ B1 — 재판단이 도는 동안 서버는 확정을 받지 않는다): 다시 읽고 saveError confirm_rejudging.
//     화면은 running 줄이 있으면 [확정]을 미리 끈다 — 이 갈래는 다른 탭이 재판단을 건 때다.
//     확정이 아닌 PUT 의 409 rejudge_running(GRJ3 — 도는 문장의 근거를 바꿈)은 다시 읽고 saveError rejudge_running(POST 와 같은 글).
import { useCallback, useEffect, useRef, useState } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import { parseReview } from '../api/index.ts';
import { storeErrorKind } from '../api/index.ts';
import type { GreenwashStore } from '../api/index.ts';
import {
  confirmUpdate,
  editUpdate,
  evidenceUpdate,
  flatEdit,
  markUpdate,
} from '../model/index.ts';
import type {
  EditChange,
  EvidenceChange,
  GreenwashReview,
  MarkChange,
  ReviewUpdate,
} from '../model/index.ts';

/**
 * 저장이 안 된 까닭. invalid = 서버가 돌려준 검토가 꼴을 지나지 못함.
 * stale = 확정 전 다시 읽은 표시가 화면과 다름(PUT 안 함), already_confirmed = 확정하려는데 이미 확정됨(밴드 GW1R ③).
 * reload_failed = stale 뒤 [새로 불러오기]의 다시 읽기가 안 됨(보던 검토 그대로 — 밴드 GW2R ②).
 */
export type ReviewSaveError =
  | 'rejected'
  | 'review_locked'
  | 'run_not_done'
  | 'no_review'
  | 'invalid'
  | 'stale'
  | 'already_confirmed'
  | 'reload_failed'
  /** 재판단 만들기 409(GRJ1) — 그 문장의 재판단이 아직 돈다 · 근거가 기준 판단과 같다. */
  | 'rejudge_running'
  | 'nothing_to_rejudge'
  /** 확정 PUT 409 rejudge_running(GRJ1 ④ B1) — 도는 재판단이 있어 확정을 받지 않았다. */
  | 'confirm_rejudging';

/** 재판단이 도는 동안 검토를 다시 읽는 간격(ms). */
export const REJUDGE_POLL_MS = 2000;

type QueuedChange = EditChange | EvidenceChange;
const isEdit = (change: QueuedChange): change is EditChange =>
  'column' in change;

/** 기다린 고침·근거 고침 → 한 본문(고침이 있으면 edits, 근거 고침이 있으면 evidence). */
function queuedUpdate(
  base: GreenwashReview,
  changes: readonly QueuedChange[],
): ReviewUpdate {
  const edits = changes.filter(isEdit);
  const proofs = changes.filter((c): c is EvidenceChange => !isEdit(c));
  const update: ReviewUpdate =
    edits.length > 0 ?
      editUpdate(base, ...edits)
    : { marks: base.marks.map((mark) => ({ ...mark })) };
  return proofs.length > 0 ?
      { ...update, evidence: evidenceUpdate(base, ...proofs).evidence ?? [] }
    : update;
}

export type ReviewReadState =
  | { state: 'loading' }
  | { state: 'ready'; review: GreenwashReview }
  | { state: 'missing' }
  | { state: 'invalid'; issues: string }
  | { state: 'failed' };

export interface ReviewHandle {
  status: ReviewReadState;
  /** 검토를 다시 읽는다(loading 부터, 화면의 [다시 시도]). */
  retry(): void;
  saving: boolean;
  saveError: ReviewSaveError | null;
  /** 표시 하나를 바꾼다(본문은 marks 전부). 저장되면 true. */
  mark(change: MarkChange): Promise<boolean>;
  /**
   * 칸 하나를 고친다(본문은 marks 그대로 + 고침 전부). 저장되면 true. 앞 저장이 도는 중이면 그것이 끝난 뒤 한 번 보내고
   * 그 결과를 돌려준다(버리지 않는다).
   */
  edit(change: EditChange): Promise<boolean>;
  /** 문장 하나의 근거 고침을 갈아 넣는다(GRJ1 — edit 와 같은 저장 길·기다림). 저장되면 true. */
  evidence(change: EvidenceChange): Promise<boolean>;
  /** 문장 하나를 재판단한다(GRJ1). 앞 저장이 끝난 뒤 만든다. 만들었으면 true. */
  rejudge(itemIndex: number): Promise<boolean>;
  /** 재판단을 눌러 답을 기다리는 문장들. */
  pressing: ReadonlySet<number>;
  /** 미검토를 채택으로 채워 확정한다. itemCount 는 결과 items 의 길이. 먼저 검토를 다시 읽는다(Q14). 저장되면 true. */
  confirm(itemCount: number): Promise<boolean>;
  /** [새로 불러오기]: 검토를 다시 읽어 화면 값을 서버 값으로(스켈레톤 없이). 받으면 saveError 를 지우고, 못 읽으면 보던 검토 그대로 reload_failed. */
  reload(): Promise<void>;
  /** 이 탭에서 이 실행의 검토 PUT 이 받아들여진 마지막 때(ISO 8601). 없으면 null(밴드 GW2R ② Q6). */
  savedAt: string | null;
  /** 저장 중이라 받지 않은 mark·confirm 의 횟수(바뀌면 화면이 「저장 중이에요」를 잠깐 보인다 — 밴드 GR1). */
  busyRefusals: number;
}

/** 자동 저장 시각: 저장소 → 실행 id → ISO(이 탭의 기억 — 화면 사이 이동에서 남는다). */
const savedTimes = new WeakMap<GreenwashStore, Map<string, string>>();

export function useReview(store: GreenwashStore, runId: string): ReviewHandle {
  // readReview 는 거절하지 않는다(없음·꼴 오류·그 밖을 읽기 상태로 바꾼다). 그래서 useLoad 는 늘 ready 로 끝난다.
  const {
    status: read,
    set: setRead,
    retry,
  } = useLoad([store, runId], () => readReview(store, runId));
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<ReviewSaveError | null>(null);
  const [busyRefusals, setBusyRefusals] = useState(0);
  const [pressing, setPressing] = useState<ReadonlySet<number>>(new Set());
  /** 저장이 다 끝나기(도는 것도 기다리는 것도 없음)를 기다리는 rejudge 들. */
  const idleWaiters = useRef<(() => void)[]>([]);
  /** 조용한 다시 읽기가 실패했을 때 다음 간격을 다시 걸게 하는 표지. */
  const [pollTick, setPollTick] = useState(0);
  const flushIdle = useCallback(() => {
    if (busy.current || waiting.current !== null) return;
    const waiters = idleWaiters.current;
    idleWaiters.current = [];
    waiters.forEach((wake) => wake());
  }, []);
  const whenIdle = useCallback(
    () =>
      new Promise<void>((resolve) => {
        if (!busy.current && waiting.current === null) resolve();
        else idleWaiters.current.push(resolve);
      }),
    [],
  );
  /** 지금 보고 있는 실행(늦은 저장을 가르는 표지). */
  const latest = useRef(runId);
  /** 저장이 도는 중인가(겹친 저장 막기). */
  const busy = useRef(false);
  /** 저장이 받아들여진 횟수 — [새로 불러오기]의 늦은 답이 그 사이 저장된 표시를 덮지 않게(밴드 GW1R ⑤ M1). */
  const saved = useRef(0);
  /** 자동 저장 시각을 바꾼 뒤 다시 그리게 하는 표지. */
  const [, setSavedTick] = useState(0);
  /** 앞 저장이 끝나기를 기다리는 고침(차례대로)과 그 부름들의 답. */
  const waiting = useRef<{
    changes: QueuedChange[];
    answers: ((ok: boolean) => void)[];
  } | null>(null);
  /** 마지막으로 받은 검토(기다린 고침의 본문을 앞 저장 뒤의 검토에서 짓는다 — 다시 그리기 전에도). */
  const lastReview = useRef<GreenwashReview | null>(null);
  useEffect(() => {
    latest.current = runId;
  }, [runId]);

  useEffect(() => {
    setSaveError(null);
  }, [store, runId]);

  const status: ReviewReadState =
    read.state === 'ready' ? read.data : { state: 'loading' };
  const current = status.state === 'ready' ? status.review : null;
  useEffect(() => {
    lastReview.current = current;
  }, [current]);

  const put = useCallback(
    async (
      update: ReviewUpdate,
      lockedAs: 'review_locked' | 'already_confirmed' = 'review_locked',
    ): Promise<boolean> => {
      busy.current = true;
      setSaving(true);
      setSaveError(null);
      const stale = () => latest.current !== runId;
      try {
        const parsed = parseReview(await store.putReview(runId, update));
        if (stale()) return parsed.ok;
        if (!parsed.ok) {
          setSaveError('invalid');
          return false;
        }
        saved.current += 1;
        lastReview.current = parsed.value;
        const times = savedTimes.get(store) ?? new Map<string, string>();
        times.set(runId, new Date().toISOString());
        savedTimes.set(store, times);
        setSavedTick((n) => n + 1);
        setRead({ state: 'ready', review: parsed.value });
        return true;
      } catch (error) {
        if (stale()) return false;
        const kind = storeErrorKind(error);
        if (kind === 'review_locked') {
          const again = await readReview(store, runId);
          if (stale()) return false;
          if (again.state === 'ready') lastReview.current = again.review;
          setRead(again);
          setSaveError(lockedAs);
        } else if (kind === 'rejudge_running') {
          // 확정 PUT(④ B1) 또는 도는 문장의 근거를 바꾼 PUT(GRJ3) — 다시 읽어 도는 줄을 보이고(화면이 [확정]을 끈다) 까닭을 올린다
          const again = await readReview(store, runId);
          if (stale()) return false;
          if (again.state === 'ready') {
            lastReview.current = again.review;
            setRead(again);
          }
          setSaveError(
            update.state === 'confirmed' ?
              'confirm_rejudging'
            : 'rejudge_running',
          );
        } else if (kind === 'run_not_done' || kind === 'no_review')
          setSaveError(kind);
        else setSaveError('rejected');
        return false;
      } finally {
        busy.current = false;
        setSaving(false);
      }
    },
    [store, runId, setRead],
  );

  // 기다린 고침을 한 번에 보낸다(앞 저장이 끝난 뒤). 보내는 동안 또 기다린 것이 생기면 끝난 뒤 다시.
  const drain = useCallback(
    function drain(): void {
      const queued = waiting.current;
      if (queued === null || busy.current) return;
      waiting.current = null;
      const answer = (ok: boolean) => queued.answers.forEach((a) => a(ok));
      const base = lastReview.current;
      // 확정된 검토에는 고침을 보내지 않는다(보내면 409 review_locked — 밴드 GR1)
      if (
        latest.current !== runId ||
        base === null ||
        base.state === 'confirmed'
      ) {
        answer(false);
        return;
      }
      void put(queuedUpdate(base, queued.changes)).then((ok) => {
        answer(ok);
        drain();
        flushIdle();
      });
    },
    [flushIdle, put, runId],
  );

  const save = useCallback(
    async (
      update: ReviewUpdate,
      lockedAs: 'review_locked' | 'already_confirmed' = 'review_locked',
    ): Promise<boolean> => {
      const ok = await put(update, lockedAs);
      drain();
      flushIdle();
      return ok;
    },
    [put, drain, flushIdle],
  );

  /** 저장 중이라 받지 않는다(조용히 버리지 않는다 — 화면이 알린다). */
  const refuseBusy = useCallback(() => {
    setBusyRefusals((n) => n + 1);
    return false;
  }, []);

  const mark = useCallback(
    async (change: MarkChange) => {
      if (current === null) return false;
      if (busy.current) return refuseBusy();
      return save(markUpdate(current, change));
    },
    [current, refuseBusy, save],
  );
  const queue = useCallback(
    (change: QueuedChange): Promise<boolean> => {
      if (current === null) return Promise.resolve(false);
      if (!busy.current) return save(queuedUpdate(current, [change]));
      // 앞 저장 중: 기다렸다가 한 번 보낸다(본문은 앞 저장 뒤의 검토에서 — [B3] 와 같은 까닭)
      return new Promise<boolean>((resolve) => {
        const queued = waiting.current ?? { changes: [], answers: [] };
        queued.changes.push(change);
        queued.answers.push(resolve);
        waiting.current = queued;
      });
    },
    [current, save],
  );
  const edit = useCallback((change: EditChange) => queue(change), [queue]);
  const evidence = useCallback(
    (change: EvidenceChange) => queue(change),
    [queue],
  );

  /** 조용한 다시 읽기(재판단 뒤·도는 중): 실패면 그대로, 그 사이 저장이 받아들여졌거나 실행이 바뀌었으면 버린다. */
  const refresh = useCallback(async () => {
    const at = saved.current;
    const again = await readReview(store, runId);
    if (latest.current !== runId || saved.current !== at) return null;
    if (again.state !== 'ready') return null;
    lastReview.current = again.review;
    setRead(again);
    return again.review;
  }, [runId, setRead, store]);

  const rejudge = useCallback(
    async (itemIndex: number): Promise<boolean> => {
      if (current === null || current.state === 'confirmed') return false;
      setPressing((before) => new Set(before).add(itemIndex));
      const done = () =>
        setPressing((before) => {
          const next = new Set(before);
          next.delete(itemIndex);
          return next;
        });
      try {
        // 근거 저장(도는 것·기다리는 것)이 서버에 실린 뒤 만든다
        await whenIdle();
        if (latest.current !== runId) return false;
        setSaveError(null);
        try {
          await store.rejudge(runId, itemIndex);
        } catch (error) {
          if (latest.current !== runId) return false;
          const kind = storeErrorKind(error);
          if (
            kind === 'rejudge_running' ||
            kind === 'nothing_to_rejudge' ||
            kind === 'review_locked'
          ) {
            await refresh();
            if (latest.current === runId) setSaveError(kind);
          } else setSaveError('rejected');
          return false;
        }
        await refresh();
        return true;
      } finally {
        done();
      }
    },
    [current, refresh, runId, store, whenIdle],
  );

  // 재판단이 도는 동안 다시 읽는다(받은 검토마다 다시 잼 — running 0 이면 멈춤, 실행이 바뀌거나 내려가면 지움)
  const running = current?.rejudges.some((line) => line.status === 'running');
  useEffect(() => {
    if (!running) return;
    const timer = setTimeout(() => {
      void refresh().then((got) => {
        if (got === null) setPollTick((n) => n + 1);
      });
    }, REJUDGE_POLL_MS);
    return () => clearTimeout(timer);
  }, [running, current, refresh, pollTick]);

  const confirm = useCallback(
    async (itemCount: number): Promise<boolean> => {
      if (current === null) return false;
      if (busy.current) return refuseBusy();
      busy.current = true;
      setSaving(true);
      setSaveError(null);
      const stale = () => latest.current !== runId;
      // 다시 읽는 동안에도 다른 저장을 받지 않는다(busy) — PUT 으로 넘어가면 save 가 이어 쥔다.
      const stop = (error: ReviewSaveError | null) => {
        busy.current = false;
        setSaving(false);
        if (error !== null && !stale()) setSaveError(error);
        drain();
        flushIdle();
        return false;
      };
      const again = await readReview(store, runId);
      if (stale()) return stop(null);
      if (again.state !== 'ready') return stop('rejected');
      if (again.review.state === 'confirmed') {
        // 기다린 고침이 이 확정 상태를 보고 끝나게(drain 은 다시 그리기 전에 돈다)
        lastReview.current = again.review;
        setRead(again);
        return stop('already_confirmed');
      }
      if (!sameReview(again.review, current)) return stop('stale');
      return save(confirmUpdate(current, itemCount), 'already_confirmed');
    },
    [current, drain, flushIdle, refuseBusy, runId, save, setRead, store],
  );

  // 다시 읽는 사이에 저장이 받아들여졌으면 그 답을 버린다 — 늦은 GET 이 새 표시를 화면에서 지우고, 다음 PUT 이 그것을 빼고 보내
  // 서버에서도 지우는 길을 막는다(밴드 GW1R ⑤ M1). 그때 화면은 저장 답(더 새 것)이다.
  const reload = useCallback(async () => {
    const at = saved.current;
    const again = await readReview(store, runId);
    if (latest.current !== runId || saved.current !== at) return;
    if (again.state !== 'ready') {
      // 보던 검토를 그대로 둔다(화면 전체 실패로 바꾸지 않는다 — 227 ②)
      setSaveError('reload_failed');
      return;
    }
    setRead(again);
    setSaveError(null);
  }, [runId, setRead, store]);

  return {
    status,
    retry,
    saving,
    saveError,
    mark,
    edit,
    evidence,
    rejudge,
    pressing,
    confirm,
    reload,
    savedAt: savedTimes.get(store)?.get(runId) ?? null,
    busyRefusals,
  };
}

async function readReview(
  store: GreenwashStore,
  runId: string,
): Promise<ReviewReadState> {
  try {
    const parsed = parseReview(await store.getReview(runId));
    return parsed.ok ?
        { state: 'ready', review: parsed.value }
      : { state: 'invalid', issues: parsed.issues };
  } catch (error) {
    return storeErrorKind(error) === 'not_found' ?
        { state: 'missing' }
      : { state: 'failed' };
  }
}

/** 확정 전 다시 읽은 검토가 화면 값과 같은가: 표시와 고침(값만 — 고친 때·사람은 견주지 않는다) 둘 다. */
function sameReview(a: GreenwashReview, b: GreenwashReview): boolean {
  return sameMarks(a.marks, b.marks) && sameEdits(a.edits, b.edits);
}

/** 두 고침 목록의 값이 같은가(itemIndex 로 맞춘다. editedAt·editedBy 는 빼고). */
function sameEdits(
  a: GreenwashReview['edits'],
  b: GreenwashReview['edits'],
): boolean {
  const key = (edits: GreenwashReview['edits']) =>
    JSON.stringify(
      [...edits].sort((x, y) => x.itemIndex - y.itemIndex).map(flatEdit),
    );
  return key(a) === key(b);
}

/** 두 표시 목록이 같은가(문장 차례·결정·사유). 차례는 itemIndex 로 맞춘다. */
function sameMarks(
  a: GreenwashReview['marks'],
  b: GreenwashReview['marks'],
): boolean {
  if (a.length !== b.length) return false;
  const key = (marks: GreenwashReview['marks']) =>
    [...marks]
      .sort((x, y) => x.itemIndex - y.itemIndex)
      .map((m) => `${m.itemIndex}:${m.decision}:${m.excludeReason ?? ''}`)
      .join('|');
  return key(a) === key(b);
}
