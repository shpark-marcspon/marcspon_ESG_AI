// 실행 하나의 둘레(밴드 FW2 ③, GW-04 제목 줄): 문서(이름·수정본인지)·실행(만든 때)·회차.
// 목록 원재료(listCheckRows)에서 찾는다 — 실제 짝은 core_documents_get + runs_list(documentId). 회차 = 그 문서의 실행 차례(gw-a-01c).
// 찾지 못하면 doc·run 이 null 이고 회차도 null 이다(화면은 그 토막을 뺀다). 읽기가 거절돼도 같다(결과 화면은 결과만으로 그린다).
// refresh(밴드 FW2 ④): 값이 바뀌면 다시 읽는다(GW-05 가 확정한 뒤 확정한 사람을 다시 읽게 검토 상태를 넘긴다). 다시 읽는 동안은 앞 값을 그대로 낸다.
import { useEffect, useMemo, useRef } from 'react';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { runOrdinal } from '../../../entities/greenwash/model/index.ts';
import type {
  ListedDocument,
  ListedRun,
} from '../../../entities/greenwash/model/index.ts';
import { useLoad } from '../../../shared/lib/useLoad.ts';

export type RunSummary =
  | { state: 'loading' }
  | {
      state: 'ready';
      doc: ListedDocument | null;
      run: ListedRun | null;
      ordinal: number | null;
    };

export function useRunSummary(
  store: GreenwashStore,
  runId: string,
  refresh?: string,
): RunSummary {
  // 읽기가 거절돼도 ready(둘레 없음)로 받는다 — 그래서 다시 읽는 동안에도 늘 앞 값이 남는다.
  const { status, reload } = useLoad([store, runId], () =>
    store.listCheckRows().then(
      (source): Found => {
        const run = source.runs.find((r) => r.runId === runId) ?? null;
        const doc =
          (run &&
            source.documents.find((d) => d.documentId === run.documentId)) ??
          null;
        return {
          doc,
          run,
          ordinal: run ? runOrdinal(source.runs, runId) : null,
        };
      },
      (): Found => ({ doc: null, run: null, ordinal: null }),
    ),
  );
  // refresh 가 바뀔 때만 다시 읽는다(처음 그릴 때는 위 읽기 하나).
  const seen = useRef(refresh);
  useEffect(() => {
    if (seen.current === refresh) return;
    seen.current = refresh;
    reload();
  }, [refresh, reload]);
  return useMemo<RunSummary>(
    () =>
      status.state === 'ready' ?
        { state: 'ready', ...status.data }
      : { state: 'loading' },
    [status],
  );
}

type Found = Omit<Extract<RunSummary, { state: 'ready' }>, 'state'>;
