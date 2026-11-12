// AD-04a 결과 파일 받기(밴드 RF1W, 결정 MARC-ENT-395). [내려받기] 한 번에 GET /run-logs/{run_id}/files/{name} 한 번.
//   - 한 번에 하나: 받는 중이면 그 모달의 모든 [내려받기] 누름을 여기서 막는다(요청 0 — 단추의 끔 꼴은 화면이 그린다. 처리기는 이 한 자리).
//   - 받으면 Blob·서버 이름을 save 로 넘긴다(DOM 저장은 ui 층의 몫 — 넣어 준 save 가 한다). 실패는 failed·notFound 로(아래 줄), 다시 누르면 지운다.
//   - 404 둘(어댑터의 notFound — 실행·그 이름 없음)은 notFound 로 따로 둔다(AD4P — 글이 다르다). 단추는 끄지 않고 다시 누르면 새 요청(감독 답 Q3).
//   - 늦게 온 답은 세대 셈이 버린다(모달을 닫거나 다른 실행을 열면 앞 답은 저장도 실패 글도 0). 상태는 연 차례(seq)에 붙인다.
import { useCallback, useEffect, useRef, useState } from 'react';

import type { RunLogServerPort } from '../../../entities/run-log/api/index.ts';
import type { RunDetailOpened } from './useRunDetail.ts';

export type RunFileState =
  | { phase: 'idle' }
  | { phase: 'busy'; name: string }
  | { phase: 'notFound' }
  | { phase: 'failed' };

export function useRunFile(
  port: RunLogServerPort,
  opened: RunDetailOpened | null,
  save: (blob: Blob, fileName: string) => void,
) {
  const [stored, setStored] = useState<{
    seq: number;
    state: RunFileState;
  } | null>(null);
  const generation = useRef(0);
  const busy = useRef(false);
  const runId = opened?.runId ?? null;
  const seq = opened?.seq ?? null;

  // 연 차례가 바뀌면(닫음·다른 실행) 앞 받기의 답을 버리고 다시 누를 수 있게 한다.
  useEffect(() => {
    const counter = generation;
    return () => {
      counter.current++;
      busy.current = false;
    };
  }, [seq]);

  const download = useCallback(
    (name: string) => {
      if (runId === null || seq === null || busy.current) return;
      busy.current = true;
      const mine = ++generation.current;
      setStored({ seq, state: { phase: 'busy', name } });
      void port
        .file(runId, name)
        .catch(() => ({ kind: 'failed' }) as const)
        .then((outcome) => {
          if (mine !== generation.current) return;
          busy.current = false;
          if (outcome.kind === 'ok') save(outcome.blob, outcome.fileName);
          setStored({
            seq,
            state:
              outcome.kind === 'ok' ? { phase: 'idle' }
              : outcome.kind === 'notFound' ? { phase: 'notFound' }
              : { phase: 'failed' },
          });
        });
    },
    [port, runId, seq, save],
  );

  const state: RunFileState =
    seq !== null && stored?.seq === seq ? stored.state : { phase: 'idle' };
  return { state, download };
}
