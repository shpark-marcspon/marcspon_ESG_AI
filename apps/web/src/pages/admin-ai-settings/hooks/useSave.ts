// AD-02 한 번 저장 흐름(밴드 AD2S ② — AiSettingsScreen 에서 옮김, 동작 0. AD2W ③④ · sid:MARC-ENT-387 「한 번 저장 = 새 판 하나」).
//   판을 만드는 부름(port.create)은 여기 한 곳이다. 두 번 누름·Enter 는 sending 이 막는다(상태는 다음 그림에서야 바뀐다).
//   - 저장 창 하나(form): 이름·메모, 서버가 짚은 칸 오류는 그 칸을 고칠 때까지 둔다. 거절·실패는 창과 적은 것을 둔 채 창 안 줄(refusalOf).
//   - 새 판이면 창 닫음 → 초안 비움 → onCreated(화면 알림 걷음) → 목록 다시(refreshKeep) → onSaved(새 판 고름·알림).
//     다시 읽기만 실패하면 saved 에 새 판을 두고(정보 띠) retrySaved 가 다시 받는다.
//   - saving = 저장 흐름이 도는 동안(POST · 그 뒤 목록 다시 받기 · retrySaved) — 화면이 이 동안 목록 세대·고른 판을 바꾸는 단추를 끈다(AD2S ①).
//   - 모듈 초안 몫(AP1W ③): 고친 저장이면 useDraft 의 moduleBody(고친 것이 없으면 null)를 create 셋째 인자로, 복제는 늘 null.
//     공통 code 밖의 거절은 모듈 슬롯(refusal)에 먼저 묻고, 모듈이 짚은 자리는 moduleRefused 로 둔다(모듈 초안을 고치면 걷는다).
//   - 저장 중 고침 막음(Q7 — sid:MARC-ISSUE-297 ①): sending 을 켜는 줄에서 초안을 잠그고, 끝날 때 정보 띠가 서지 않았으면 푼다.
//     정보 띠가 섰으면 잠근 채 두고 retrySaved 가 성공해 띠를 걷는 줄에서 푼다.
import { useRef, useState } from 'react';

import {
  bodyOf,
  promptLabel,
  saveFormProblems,
} from '../../../entities/ai-setting/model/index.ts';
import type {
  AiSettingPort,
  Draft,
  ModuleDraftSlot,
  ModuleRefused,
  PromptModel,
  SaveOutcome,
  VersionRow,
} from '../../../entities/ai-setting/model/index.ts';
import { refusalOf, slotKey } from '../model/index.ts';
import type {
  RefusalShown,
  RefusalWords,
  SlotRefusals,
} from '../model/index.ts';

/** 저장 창 하나의 상태(edit = 고친 것 저장, copy = 복제). */
export interface SaveForm extends RefusalShown {
  mode: 'edit' | 'copy';
  title: string;
  memo: string;
}

export function useSave({
  port,
  chosen,
  model,
  draft,
  slot,
  refreshKeep,
  words,
  onCreated,
  onSaved,
}: {
  port: AiSettingPort;
  chosen: VersionRow | undefined;
  model: PromptModel | null;
  /** 고른 판의 초안(useDraft 결과 중 쓰는 것). */
  draft: {
    draft: Draft | null;
    valid: boolean;
    /** 저장 본문에 넣을 모듈 초안(고친 것이 없으면 null). */
    moduleBody: unknown;
    clear(): void;
    setLocked(on: boolean): void;
  };
  /** 모듈 초안 슬롯(거절 풀이를 묻는다 — 없으면 묻지 않음). */
  slot?: ModuleDraftSlot;
  /** 저장 뒤 목록 다시 받기(실패해도 지금 목록을 둔다 — 받았으면 true). */
  refreshKeep(): Promise<boolean>;
  words: RefusalWords;
  /** 새 판이 만들어졌다(목록 다시 받기 전). */
  onCreated(): void;
  /** 새 판이 목록에 실렸다 — 화면이 고르고 알린다. */
  onSaved(key: string, number: string): void;
}) {
  const [form, setForm] = useState<SaveForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [refused, setRefused] = useState<SlotRefusals>({});
  const [moduleRefused, setModuleRefused] = useState<ModuleRefused>({});
  /** 저장은 됐는데 목록 다시 읽기가 실패한 새 판(정보 띠). */
  const [saved, setSaved] = useState<{ key: string; number: string } | null>(
    null,
  );
  const sending = useRef(false);

  const openSave = (mode: SaveForm['mode']) =>
    setForm({
      mode,
      title: '',
      memo: '',
      failure: null,
      titleError: null,
      memoError: null,
    });
  const problems = saveFormProblems(form?.title ?? '', form?.memo ?? '');
  const canSave =
    form !== null &&
    problems.title === null &&
    problems.memo === null &&
    draft.valid;
  const submitSave = async () => {
    if (!chosen || !model || !draft.draft || !form || sending.current) return;
    sending.current = true;
    draft.setLocked(true);
    setSaving(true);
    // 정보 띠가 섰는가(그러면 잠금을 둔다 — 이 흐름이 세운 띠는 닫힌 값 saved 에 안 보인다. 앞 흐름의 띠가 남았으면 그대로 잠근다).
    let banded = saved !== null;
    try {
      const body = bodyOf(model, draft.draft, {
        title: form.title,
        memo: form.memo,
      });
      const outcome = await port
        .create(
          chosen.key,
          body,
          form.mode === 'copy' ? null : draft.moduleBody,
        )
        .catch((): SaveOutcome => ({ kind: 'failed' }));
      if (outcome.kind !== 'ok') {
        const {
          slots: marked,
          module: moduleMarked,
          ...shown
        } = refusalOf(
          outcome,
          promptLabel(model),
          words,
          slot && ((code, fields) => slot.refusal(code, fields)),
        );
        setRefused(marked);
        setModuleRefused(moduleMarked ?? {});
        setForm((before) => before && { ...before, ...shown });
        return;
      }
      setForm(null);
      draft.clear();
      setRefused({});
      setModuleRefused({});
      onCreated();
      if (!(await refreshKeep())) {
        banded = true;
        setSaved({ key: outcome.key, number: outcome.number });
        return;
      }
      onSaved(outcome.key, outcome.number);
    } finally {
      sending.current = false;
      if (!banded) draft.setLocked(false);
      setSaving(false);
    }
  };

  /** 저장 뒤 목록 다시 읽기를 다시 한다(정보 띠의 [다시 시도]). */
  const retrySaved = async () => {
    if (saved === null || sending.current) return;
    sending.current = true;
    draft.setLocked(true);
    setSaving(true);
    try {
      // 실패면 띠와 잠금을 둔다.
      if (!(await refreshKeep())) return;
      setSaved(null);
      draft.setLocked(false);
      onSaved(saved.key, saved.number);
    } finally {
      sending.current = false;
      setSaving(false);
    }
  };

  return {
    form,
    saving,
    refused,
    moduleRefused,
    saved,
    problems,
    canSave,
    openSave,
    submitSave,
    retrySaved,
    closeSave: () => setForm(null),
    setTitle: (title: string) =>
      setForm((before) => before && { ...before, title, titleError: null }),
    setMemo: (memo: string) =>
      setForm((before) => before && { ...before, memo, memoError: null }),
    /** 서버가 짚은 칸 오류를 모두 걷는다(판 바꿈·되돌리기 — 모듈이 짚은 자리도). */
    clearRefused: () => {
      setRefused({});
      setModuleRefused({});
    },
    /** 모듈이 짚은 자리를 걷는다(모듈 초안을 고침). */
    forgetModuleRefused: () => setModuleRefused({}),
    /** 그 칸의 고친 종류(글·메모)만 서버 오류를 걷는다. */
    forgetRefused: (group: number, prompt: number, fields: string[]) =>
      setRefused((before) => {
        const key = slotKey(group, prompt);
        const mine = before[key];
        if (!mine) return before;
        const left = { ...mine };
        for (const field of fields as ('text' | 'memo')[]) delete left[field];
        return { ...before, [key]: left };
      }),
  };
}
