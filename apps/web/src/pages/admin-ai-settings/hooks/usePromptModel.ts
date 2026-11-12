// AD-02 판 하나의 prompt-model 읽기(밴드 AD2W ② — 모듈 슬롯의 port.promptModel). 판 열쇠마다 한 번만 받는다(다시 고르면 요청 0).
//   - 실패(failed·missing)는 그 열쇠의 답을 버려 [다시 시도]가 다시 받는다. 쓸 수 없는 판(unusable)은 서버 문장 그대로 둔다.
//   - forget(key): 저장 뒤 새 판처럼 그 열쇠를 잊고 다시 받게 한다(outputKept 는 저장 응답에 없어 다시 읽는다 — 발주서 1-4).
//   - 어댑터가 바뀌면(모듈·세션) 받아 둔 것을 비운다. 늦게 온 옛 어댑터의 답은 버린다.
import { useCallback, useEffect, useRef, useState } from 'react';

import type {
  AiSettingPort,
  PromptModelOutcome,
} from '../../../entities/ai-setting/model/index.ts';

export type PromptModelState = { kind: 'loading' } | PromptModelOutcome;

export function usePromptModel(port: AiSettingPort, key: string | null) {
  const [answers, setAnswers] = useState<
    ReadonlyMap<string, PromptModelOutcome>
  >(() => new Map());
  // 보낸 열쇠(같은 열쇠를 두 번 보내지 않는다 — StrictMode 의 두 번 effect 도).
  const asked = useRef(new Set<string>());
  const owner = useRef(port);

  useEffect(() => {
    if (owner.current === port) return;
    owner.current = port;
    asked.current = new Set();
    setAnswers(new Map());
  }, [port]);

  const ask = useCallback(
    (wanted: string) => {
      if (asked.current.has(wanted)) return;
      asked.current.add(wanted);
      const from = port;
      void from
        .promptModel(wanted)
        .then(
          (outcome) => outcome,
          (): PromptModelOutcome => ({ kind: 'failed' }),
        )
        .then((outcome) => {
          if (owner.current !== from) return;
          setAnswers((before) => new Map(before).set(wanted, outcome));
        });
    },
    [port],
  );

  useEffect(() => {
    if (key !== null) ask(key);
  }, [ask, key]);

  /** 그 열쇠를 잊고 다시 받는다. */
  const forget = useCallback(
    (wanted: string) => {
      asked.current.delete(wanted);
      setAnswers((before) => {
        const next = new Map(before);
        next.delete(wanted);
        return next;
      });
      ask(wanted);
    },
    [ask],
  );

  const state: PromptModelState | null =
    key === null ? null : (answers.get(key) ?? { kind: 'loading' });
  return { state, forget };
}
