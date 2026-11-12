// 결과 글 칸 고침 훅(밴드 IRW11 — 발주서 Q6·Q7, critic 처분 ②). revision·고침과 **저장 뒤 다시 읽은 결과**를 쥔다
// (useResult 는 그대로 — 그 retry 는 loading 부터라 화면이 떨어져 탭·거르기가 리셋된다).
//   state: loading → ready | failed(못 읽음 — 화면은 읽기 전용, Q7).
//   save(changes): POST {baseRevision: 쥔 revision, changes} → saved 면 revision·고침을 쥐고 GET result 를 다시 읽어 result 에 끼운다
//     (loading 0). 다시 읽기가 실패하면 쥔 결과(없으면 base)에 보낸 칸만 보낸 값으로 덮는다(퍼진 자리는 다음 읽기에). 갈래를 돌려준다.
//   reload(): result·edits 를 같이 다시 읽는다(409 뒤 [새로 불러오기]) — loading 0. 읽은 결과를 돌려준다(못 읽으면 null).
import { useCallback, useEffect, useRef, useState } from 'react';

import type {
  MaterialityStore,
  ResultEditChange,
  SaveEditsResult,
} from '../api/index.ts';
import type { MaterialityResult, ResultEdit } from '../model/index.ts';

export interface ResultEditsHandle {
  state: 'loading' | 'ready' | 'failed';
  revision: number;
  edits: ResultEdit[];
  /** 저장·다시 읽기 뒤 새로 읽은 결과(아직 없으면 null — 화면은 useResult 의 결과를 쓴다). */
  result: MaterialityResult | null;
  save(
    changes: readonly ResultEditChange[],
    base: MaterialityResult,
  ): Promise<SaveEditsResult['kind']>;
  reload(): Promise<MaterialityResult | null>;
}

/** 화면 꼴 결과에 보낸 칸만 덮는다(화면 꼴의 part2 자리 이름은 서버 본문과 같다 — 주소가 그대로 맞는다). */
export function applyChanges(
  result: MaterialityResult,
  changes: readonly ResultEditChange[],
): MaterialityResult {
  const out = structuredClone(result);
  for (const { pointer, value } of changes) {
    const parts = pointer.split('/').slice(1);
    const last = parts.pop()!;
    let at: unknown = out;
    for (const part of parts) {
      if (typeof at !== 'object' || at === null) break;
      at = (at as Record<string, unknown>)[part];
    }
    if (typeof at === 'object' && at !== null && last in at)
      (at as Record<string, unknown>)[last] = value;
  }
  return out;
}

interface Held {
  state: 'loading' | 'ready' | 'failed';
  revision: number;
  edits: ResultEdit[];
  result: MaterialityResult | null;
}

export function useResultEdits(
  store: MaterialityStore,
  runId: string,
): ResultEditsHandle {
  const [held, setHeld] = useState<Held>({
    state: 'loading',
    revision: 0,
    edits: [],
    result: null,
  });
  const ref = useRef(held);
  ref.current = held;
  const alive = useRef(true);
  const update = useCallback((next: Partial<Held>) => {
    if (!alive.current) return;
    ref.current = { ...ref.current, ...next };
    setHeld(ref.current);
  }, []);

  useEffect(() => {
    alive.current = true;
    update({ state: 'loading', revision: 0, edits: [], result: null });
    store.getEdits(runId).then(
      (read) => update({ state: 'ready', ...read }),
      () => update({ state: 'failed' }),
    );
    return () => {
      alive.current = false;
    };
  }, [store, runId, update]);

  const save = useCallback(
    async (changes: readonly ResultEditChange[], base: MaterialityResult) => {
      const answer = await store.saveEdits(
        runId,
        ref.current.revision,
        changes,
      );
      if (answer.kind !== 'saved') return answer.kind;
      update({ ...answer.edits });
      let fresh: MaterialityResult;
      try {
        fresh = await store.getResult(runId);
      } catch {
        fresh = applyChanges(ref.current.result ?? base, changes);
      }
      update({ result: fresh });
      return answer.kind;
    },
    [store, runId, update],
  );

  const reload = useCallback(async () => {
    try {
      const [fresh, read] = await Promise.all([
        store.getResult(runId),
        store.getEdits(runId),
      ]);
      update({ state: 'ready', ...read, result: fresh });
      return fresh;
    } catch {
      return null;
    }
  }, [store, runId, update]);

  return { ...held, save, reload };
}
