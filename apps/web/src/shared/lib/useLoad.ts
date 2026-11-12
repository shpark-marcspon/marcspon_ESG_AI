// 읽기 하나를 맡는 훅(밴드 CW1 ①). 화면 훅마다 손으로 되풀이하던 「let alive = true 로 늦은 응답 막기」를 여기 한 곳에 모았다.
//   - 상태는 loading → ready(data) | failed(error). error 는 받은 그대로 든다(화면이 not_found 와 그 밖을 가를 수 있게).
//   - key 는 값들의 배열이다(보통 [store, runId]). 칸마다 Object.is 로 견주어 하나라도 다르면 다른 읽기로 본다:
//     loading 부터 다시 시작하고, 앞 key 의 응답은 늦게 와도 버린다. 언마운트 뒤에 온 응답도 버린다.
//   - key 가 null 이면 읽지 않는다. 상태는 loading 그대로다(따로 idle 을 두지 않는다 — 쓰는 훅이 「아직 없음」으로 바꾼다).
//   - reload(): 같은 key 로 다시 읽는다. ready 면 다시 읽는 동안 앞 값을 그대로 내고(새 값이 오면 갈아 넣는다),
//     failed 면 loading 으로 간 뒤 ready/failed(다시 시도). 다시 읽는 중에 또 부르면 앞의 다시 읽기 응답은 버린다.
//   - retry(): 같은 key 로 다시 읽되 상태와 무관하게 늘 loading 으로 간 뒤 ready/failed 다(화면의 [다시 시도] — 밴드 LE1).
//     ready 가 꼴 오류(invalid)를 든 경우처럼 앞 값을 남기면 안 되는 자리에 쓴다. 앞 값을 남기는 다시 읽기는 reload 다.
//   - reload·retry 를 받은 그리기의 key 가 지금 key 가 아니면(늦은 부름) 아무것도 안 한다(새 key 를 한 번 더 읽지 않는다).
//   - set(data): 지금 key 의 값을 ready(data) 로 갈아 넣는다(저장이 돌려준 값 넣기). 그 set 을 받은 그리기의 key 가
//     지금 key 가 아니면(늦게 온 저장) 아무것도 안 한다. 도는 읽기를 멈추지는 않는다.
// load 는 그리기마다 새 함수여도 된다(마지막 것을 부른다). 다시 읽는 때는 key 와 reload 만 정한다.
import { useCallback, useEffect, useRef, useState } from 'react';

export type LoadState<T> =
  | { state: 'loading' }
  | { state: 'ready'; data: T }
  | { state: 'failed'; error: unknown };

export type LoadKey = readonly unknown[];

export interface Load<T> {
  status: LoadState<T>;
  /** 같은 key 로 다시 읽는다(ready 면 앞 값을 낸 채). key 가 null 이면 아무것도 안 한다. */
  reload(): void;
  /** 같은 key 로 다시 읽는다. 늘 loading 부터([다시 시도]). key 가 null 이면 아무것도 안 한다. */
  retry(): void;
  /** 지금 key 의 값을 갈아 넣는다(ready). key 가 바뀐 뒤의 늦은 부름은 버린다. */
  set(data: T): void;
}

const LOADING = { state: 'loading' } as const;

const sameKey = (a: LoadKey | null, b: LoadKey | null) =>
  a === b ||
  (a !== null &&
    b !== null &&
    a.length === b.length &&
    a.every((value, i) => Object.is(value, b[i])));

/**
 * 칸이 같은 동안은 처음 받은 배열을 그대로 돌려준다(그리기마다 새 배열 글자여도 같은 key).
 * 「그리기 중 props 로 state 고치기」 꼴이다(그리기 중 ref 를 쓰지 않는다 — 버려지는 그리기가 ref 를 고치지 않게).
 * 칸이 바뀐 그리기에서는 새 key 를 바로 돌려준다(React 가 그 그리기를 버리고 고친 state 로 다시 그린다).
 */
function useSameKey(key: LoadKey | null): LoadKey | null {
  const [kept, setKept] = useState(key);
  if (sameKey(kept, key)) return kept;
  setKept(key);
  return key;
}

export function useLoad<T>(
  key: LoadKey | null,
  load: () => Promise<T>,
): Load<T> {
  const current = useSameKey(key);
  const [read, setRead] = useState<{
    key: LoadKey | null;
    status: LoadState<T>;
  }>({ key: current, status: LOADING });
  /** reload 마다 하나 오른다(같은 key 로 다시 읽게 하는 표지). */
  const [round, setRound] = useState(0);
  const latestLoad = useRef(load);
  /** 그려진 지금 key(늦은 set 을 가르는 표지). */
  const latestKey = useRef(current);

  // 아래 읽기 effect 보다 먼저 돈다(effect 는 적은 차례로 돈다).
  useEffect(() => {
    latestLoad.current = load;
  });
  useEffect(() => {
    latestKey.current = current;
  }, [current]);

  useEffect(() => {
    if (current === null) return;
    let alive = true;
    // load 가 던져도(동기) failed 로 받는다.
    new Promise<T>((resolve) => resolve(latestLoad.current())).then(
      (data) => {
        if (alive) setRead({ key: current, status: { state: 'ready', data } });
      },
      (error: unknown) => {
        if (alive)
          setRead({ key: current, status: { state: 'failed', error } });
      },
    );
    return () => {
      alive = false;
    };
  }, [current, round]);

  const reload = useCallback(() => {
    if (current === null || latestKey.current !== current) return;
    setRead((prev) =>
      prev.key === current && prev.status.state === 'failed' ?
        { key: current, status: LOADING }
      : prev,
    );
    setRound((n) => n + 1);
  }, [current]);

  const retry = useCallback(() => {
    if (current === null || latestKey.current !== current) return;
    setRead({ key: current, status: LOADING });
    setRound((n) => n + 1);
  }, [current]);

  const set = useCallback(
    (data: T) => {
      if (current === null || latestKey.current !== current) return;
      setRead({ key: current, status: { state: 'ready', data } });
    },
    [current],
  );

  const status = read.key === current ? read.status : LOADING;
  return { status, reload, retry, set };
}
