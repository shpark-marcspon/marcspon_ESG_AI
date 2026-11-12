// AD-02 판 초안 하나(밴드 AD2W ③ — sid:MARC-ENT-387 「한 번 저장 = 새 판 하나」). 초안은 바탕 판 열쇠에 묶이고 구성을 옮겨도 남는다.
//   - 고친 적이 없으면 바탕 판 그대로의 초안(prompt-model 값)을 준다. 셈·칸 오류는 model 의 순수 함수(changes·modelErrors·promptErrors)가 낸다.
//   - 열쇠가 바뀌면(다른 판) 그 판의 초안은 새로 시작한다 — 고친 채 판을 바꾸는 것은 화면이 나가기 창으로 막는다.
//   - 모듈 초안 몫(AP1W ③ — AS3b 허락 설계 ⓐⓑⓒ): 모듈 슬롯(draft)이 있으면 그 판의 바탕 몫을 판 열쇠마다 한 번 읽고(떠났다 돌아와도 다시 읽지 않는다,
//     실패는 retry 가 다시), 모듈 초안을 공통 초안과 같은 상태에 둔다. 셈은 공통 셈에 모듈 셈(count)을 덧붙이고(ModuleChanges — changes() 는 그대로),
//     저장 본문 몫(moduleBody)과 저장 끔(blocked)은 바탕 몫을 읽었고 셈이 있을 때만. clear 하나가 둘 다 지운다.
//   - 저장 중 고침 막음(AP1W ③ Q7 — sid:MARC-ISSUE-297 ①): setLocked 가 켜져 있으면 update·updateModule 이 고침을 받지 않는다(그림은 그대로).
//     useSave 가 저장 흐름 동안과 정보 띠가 떠 있는 동안 켠다.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  changes,
  draftOf,
  modelErrors,
  promptErrors,
} from '../../../entities/ai-setting/model/index.ts';
import type {
  Changes,
  Draft,
  ModuleDraftSlot,
  PromptModel,
} from '../../../entities/ai-setting/model/index.ts';

const NONE: Changes = { model: 0, prompts: [], total: 0 };

/** 공통 셈 + 모듈 셈(module — 모듈 슬롯이 없거나 바탕 몫을 못 읽었으면 0). total 은 둘의 합. */
export type ModuleChanges = Changes & { module: number };

type BaseOutcome = { kind: 'ok'; base: unknown } | { kind: 'failed' };
/** 모듈 바탕 몫의 상태(모듈 슬롯이 없거나 판을 안 골랐으면 null). */
export type ModuleState = { kind: 'loading' } | BaseOutcome;

/** 판 열쇠마다 모듈 바탕 몫을 한 번 읽는다(usePromptModel 꼴 — 슬롯 key 가 바뀌면 비우고 늦게 온 옛 key 의 답은 버린다, 같은 key 의 새 슬롯 객체는 캐시를 두고 다음 읽기에 쓴다). */
function useModuleBase(slot: ModuleDraftSlot | undefined, key: string | null) {
  const [answers, setAnswers] = useState<ReadonlyMap<string, BaseOutcome>>(
    () => new Map(),
  );
  const asked = useRef(new Set<string>());
  const slotKey = slot?.key;
  const owner = useRef(slotKey);

  useEffect(() => {
    if (owner.current === slotKey) return;
    owner.current = slotKey;
    asked.current = new Set();
    setAnswers(new Map());
  }, [slotKey]);

  const ask = useCallback(
    (wanted: string) => {
      if (!slot || asked.current.has(wanted)) return;
      asked.current.add(wanted);
      const from = slot.key;
      void slot
        .load(wanted)
        .then(
          (outcome) => outcome,
          (): BaseOutcome => ({ kind: 'failed' }),
        )
        .then((outcome) => {
          if (owner.current !== from) return;
          setAnswers((before) => new Map(before).set(wanted, outcome));
        });
    },
    [slot],
  );

  useEffect(() => {
    if (key !== null) ask(key);
  }, [ask, key]);

  /** 그 열쇠를 잊고 다시 읽는다(실패 카드의 [다시 시도]). */
  const retry = useCallback(
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

  const state: ModuleState | null =
    !slot || key === null ? null : (answers.get(key) ?? { kind: 'loading' });
  return { state, retry };
}

export function useDraft(
  key: string | null,
  pm: PromptModel | null,
  slot?: ModuleDraftSlot,
) {
  // 고친 것(판 열쇠에 묶임): 공통 초안(안 고쳤으면 null)과 모듈 초안(안 고쳤으면 null — 값은 상자에 담는다).
  const [edit, setEdit] = useState<{
    key: string;
    draft: Draft | null;
    module: { value: unknown } | null;
  } | null>(null);
  const locked = useRef(false);
  const own = edit !== null && edit.key === key ? edit : null;
  const mine = own?.draft ?? null;
  const draft = useMemo(() => mine ?? (pm ? draftOf(pm) : null), [mine, pm]);
  const common = useMemo(
    () => (pm && mine ? changes(pm, mine) : NONE),
    [mine, pm],
  );
  const errors = useMemo(
    () => (pm && draft ? modelErrors(pm, draft) : []),
    [draft, pm],
  );
  const slotErrors = useMemo(
    () => (pm && draft ? promptErrors(pm, draft) : []),
    [draft, pm],
  );

  const base = useModuleBase(slot, key);
  const baseState = base.state;
  const moduleDraft =
    baseState?.kind === 'ok' ?
      own?.module ?
        own.module.value
      : baseState.base
    : undefined;
  const moduleCount =
    slot && baseState?.kind === 'ok' ?
      slot.count(baseState.base, moduleDraft)
    : 0;
  const counted: ModuleChanges = useMemo(
    () => ({
      ...common,
      module: moduleCount,
      total: common.total + moduleCount,
    }),
    [common, moduleCount],
  );
  // 모듈 몫은 바탕을 읽었고 고친 것이 있을 때만 본문에 들고 저장을 막을 수 있다(읽는 중·실패·셈 0 이면 공통 고침·복제 저장이 된다).
  const moduleEdited = moduleCount > 0;

  /** 초안을 고친다(바탕 판 prompt-model 이 있을 때만, 잠겨 있으면 받지 않는다). 받았으면 true. */
  const update = useCallback(
    (change: (before: Draft) => Draft) => {
      if (locked.current) return false;
      if (key === null || pm === null) return false;
      setEdit((before) => {
        const same = before !== null && before.key === key ? before : null;
        return {
          key,
          draft: change(same?.draft ?? draftOf(pm)),
          module: same?.module ?? null,
        };
      });
      return true;
    },
    [key, pm],
  );
  /** 모듈 초안을 바꾼다(바탕 판 prompt-model 이 있을 때만, 잠겨 있으면 받지 않는다 — update 와 같은 꼴). 받았으면 true. */
  const updateModule = useCallback(
    (next: unknown) => {
      if (locked.current) return false;
      if (key === null || pm === null) return false;
      setEdit((before) => ({
        key,
        draft: before !== null && before.key === key ? before.draft : null,
        module: { value: next },
      }));
      return true;
    },
    [key, pm],
  );
  const clear = useCallback(() => setEdit(null), []);
  const setLocked = useCallback((on: boolean) => {
    locked.current = on;
  }, []);

  return {
    draft,
    changes: counted,
    errors,
    slotErrors,
    dirty: counted.total > 0,
    /** 모델 칸·프롬프트 칸 오류가 없고 모듈이 저장을 막지 않는다(저장할 수 있다). */
    valid:
      errors.every(
        (one) => one.temperature === null && one.maxOutputTokens === null,
      ) &&
      slotErrors.every((step) =>
        step.every((one) => one.text === null && one.memo === null),
      ) &&
      !(slot && moduleEdited && slot.blocked(moduleDraft)),
    /** 모듈 바탕 몫과 초안(카드·구성 꼬리). */
    module:
      baseState?.kind === 'ok' ?
        { kind: 'ok' as const, base: baseState.base, draft: moduleDraft }
      : baseState,
    /** 저장 본문에 넣을 모듈 초안(고친 것이 없으면 null). */
    moduleBody: moduleEdited ? moduleDraft : null,
    retryModule: () => {
      if (key !== null) base.retry(key);
    },
    update,
    updateModule,
    clear,
    setLocked,
  };
}
