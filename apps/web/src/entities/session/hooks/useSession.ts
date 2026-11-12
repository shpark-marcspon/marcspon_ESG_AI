// 세션 상태 훅(밴드 LG1 ①). 저장소의 스냅샷을 useSyncExternalStore 로 읽는다.
// 부팅 복원은 여기서 부르지 않는다: 가드(app/)가 저장소의 기억된 약속(ready)을 기다린다 — effect 에서 부르면
// StrictMode 의 이중 effect 가 refresh 를 두 번 낼 수 있다(발주서 §2). 스냅샷에는 임시 비밀번호가 없다(N4).
import { useSyncExternalStore } from 'react';

import type { SessionStore } from '../api/index.ts';
import type { SessionState } from '../model/index.ts';

export function useSession(store: SessionStore): SessionState {
  return useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getSnapshot,
  );
}
