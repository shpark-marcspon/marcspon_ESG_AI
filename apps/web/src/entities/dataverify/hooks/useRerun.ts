// [다시 실행] 훅(밴드 DV2a ③, DV-03 멈춤·DV-04 머리). 저장소의 rerun(GET /runs/{id} 의 options 그대로 새 POST /runs — 처음부터)을 잇는다.
//   rerun() 은 새 실행 id(만들어짐) 또는 null(거절·끊김 — failed 를 켠다). 누르는 동안 rerunning, 그동안 다시 눌러도 한 번.
//   거절 글은 화면이 고른다(감독 답 4 — DV-02 시작 실패 글 그대로). 다시 누르면 failed 를 지운다.
import { useRef, useState } from 'react';

import type { DataverifyStore } from '../api/index.ts';

export interface RerunHandle {
  rerunning: boolean;
  failed: boolean;
  rerun(): Promise<string | null>;
}

export function useRerun(store: DataverifyStore, runId: string): RerunHandle {
  const [rerunning, setRerunning] = useState(false);
  const [failed, setFailed] = useState(false);
  const busy = useRef(false);
  const rerun = async () => {
    if (busy.current) return null;
    busy.current = true;
    setRerunning(true);
    setFailed(false);
    try {
      const out = await store.rerun(runId);
      if (out.kind === 'started') return out.runId;
      setFailed(true);
      return null;
    } finally {
      busy.current = false;
      setRerunning(false);
    }
  };
  return { rerunning, failed, rerun };
}
