// AD-02 AI 설정 껍데기(밴드 AD2 ②, 실서버 AD2R ③, GW2R ④, 모듈 슬롯·prompt-model AD2W ①② — 디자인 판 AD-02_r3).
// 라우터도 모듈도 모른다: 모듈 줄(modules — app/admin/ai-setting-modules.ts 가 짓는다)과 처음 고를 판 번호(initialVersion)를 props 로 받는다
//   (sid:MARC-ENT-386 「껍데기는 모듈을 가져오지 않는다」). 모듈 탭 줄은 그리지 않는다(r3 에 없다 — 첫 모듈 하나).
//   제목 줄([이 버전 적용] 하나) → 열 셋(버전 · 구성 · 단계 — 프롬프트 — 모듈이 흐름 띠(flow)를 주면 둘) → 고른 구성의 상세 카드.
//   - 판 열 = 공통 부품 VersionColumn: 저장 판(서버 차례) + 맨 아래 기본 판 한 줄(구분선). 줄 이름 「v3 · 이름」(이름 없는 옛 판 「v3」, 기본 판 「기본 설정」),
//     배지 초안 · 적용 중 · 지난 버전 · 기본(발주서 Q10), 꼬리 만든 날(기본 판 「번호 없음 · 처음부터 있는 설정」). total 이 많으면 끝에 [더 보기].
//   - 처음 고름(model firstPick): initialVersion(판 번호) → 가장 새 「초안」 → 적용 중(저장 판 또는 기본).
//   - 판을 고르면 그 판의 prompt-model 을 한 번 받는다(판마다 한 번 — usePromptModel). 300ms 뒤 상세 자리 스켈레톤, 실패는 실패 상자 + [다시 시도],
//     쓸 수 없는 판(409)은 서버 문장 한 줄.
//   - 구성 열(r3 차례): 모델 설정 · 프롬프트 · 모듈 줄(준비 중) · 서버 고정 값 묶음(차례대로) · 모듈의 읽기 전용 줄(고정 규칙). 꼬리는 서버 값으로 셈.
//     처음 고른 구성은 프롬프트. 셋째 열 = 단계의 프롬프트 칸 고름(「1. 칸 이름」) — 누르면 프롬프트 구성의 그 칸.
//     모듈이 흐름 띠(module.flow — AS3b ②)를 주면 셋째 열 대신 띠 마디로 고른다(서버가 짚은 칸 표시도 띠에). 띠는 프롬프트 카드 안 단계 줄 앞 소제목 꼴(inline — 밴드 PF1).
//   - [이 버전 적용]: 고른 판이 적용 중이 아닐 때만 켬. 누르면 공통 확인 창(ApplyConfirm) → port.apply → 창 닫고 목록 다시 읽음. 실패는 창 안 빨강 줄.
//     두 번 누름은 막는다. 적용 뒤 판 열 위에 알림 한 줄.
//   - 불러오기(MARC-ENT-260): 300ms 뒤 본문 자리에 키트 TableSkeleton(aria-busy), 실패는 CM-03 꼴 실패 상자 + [다시 시도].
//   - 판 초안·한 번 저장(AD2W ③ — sid:MARC-ENT-387): 고른 판에 초안 하나(useDraft — 구성을 옮겨도 남는다). 모델 칸을 고치면 저장 막대
//     (「고친 것 n개」 · [되돌리기] · [새 버전으로 저장]), 바탕 줄 주황 테두리 + 날짜 꼬리 다음 「<v> 바탕으로 고치는 중」(꼬리표 없음 — GW3R A11), 구성 꼬리 「고침 n」.
//     [새 버전으로 저장] → 저장 창(이름 1~40 · 메모 0~200 · 번호 추정) → [저장] = port.create 한 번(두 번 누름·Enter 도 — sending).
//     새 판이면 창 닫음 → 초안 비움 → 목록 다시 → 새 판 고름(그 판 prompt-model 을 받는다 — outputKept 는 저장 답에 없다) → 알림(답의 번호).
//     거절·실패는 창과 적은 것을 둔 채 창 안 빨강 줄(발주서 Q6): 모델 거절 「모델 설정 — 서버 문장」, 꼴 틀림 fields.title·memo 는 그 칸 아래, 그 밖은 일반 글.
//     고친 동안 [이 버전 적용]은 꺼지고(눌러도 창 0) 곁 글. 고친 채 다른 판 누름·메뉴 이동(라우터가 넘기는 leave)은 나가기 창.
//     [이 버전을 바탕으로 새 버전] = 고친 것 없고 판 읽기가 된 때만 — 같은 저장 창(고친 것 0, 본문은 바탕 값 그대로).
//   - 프롬프트 칸 고침(AD2W ④): 단계 카드의 글·메모(editable.prompts). 넘침·빈 글이면 칸 빨강 + 저장 끔. 저장 거절 AI_PROMPT_* 의 fields 경로는
//     (단계, 칸)으로 풀어 그 칸 빨강 + 칸 고름 줄 「고칠 곳 있음」(빨강 + 점), 창에 「<칸 이름> — 서버 문장」(모르는 경로는 창의 일반 줄에 서버 문장).
//   - 저장 뒤 목록 다시 읽기만 실패하면(cd 답 10-22) 앞 목록을 둔 채 저장 막대 자리에 정보 띠 「v<n> 을 저장했어요. 버전 목록을 …」 + [다시 시도]
//     — 다시 받으면 새 판을 고르고 평소 알림.
//   - 저장 흐름 경쟁(AD2S — sid:MARC-ISSUE-294): 저장 중 막힌 이동은 끝날 때까지 미룸 — 실패면 나가기 창, 저장됐으면 그대로 보냄.
//     저장 흐름(POST 와 그 뒤 목록 다시 받기 · 정보 띠 [다시 시도])이 도는 동안 [더 보기]·판 줄·[이 버전 적용]·[새 버전]·저장 막대 [저장]은 끈다.
//   - 저장 흐름은 hooks/useSave(port.create 한 곳), 구성 열 줄은 model/lines, 저장 거절 풀이는 model/refusal 로 뗐다(AD2S ② — 동작 0).
//   - 모델 칸·프롬프트 묶음 여럿(AP1W ② — ai.prompt-model@3): 묶음이 둘 이상이면 셋째 열에 묶음 머리(「n. 묶음」 — 고를 수 없음)와 그 아래 칸 이름(번호 없음),
//     하나면 지금처럼 「n. 칸」. 모델 칸이 둘 이상이면 셈 줄은 「모델 칸마다 1」. 저장 창 「고친 것」은 칸·묶음 어느 하나라도 둘 이상이면 항목 목록(model/lines changeList).
//   - 모듈 초안 슬롯(AP1W ③ — module.draft): 모듈 초안 줄(body draft)의 상세는 바탕 몫 읽는 중 스켈레톤 · 실패 상자 + [다시 시도] · 읽었으면 모듈 카드
//     (prompt-model 을 못 읽었으면 읽기 전용). 초안·셈·저장 본문 몫은 useDraft, 고친 것 조각(changed)은 저장 창 「고친 것」 끝에.
import { useEffect, useRef, useState } from 'react';

import { TableSkeleton } from '@marcspon/ui/components/table-skeleton';
import { cn } from '@marcspon/ui/lib/utils';

import { AI_SETTING_TEXT } from '../../../entities/ai-setting/config/text.ts';
import {
  changedModels,
  firstPick,
  nextNumber,
  versionLabel,
  versionName,
  withRoute,
} from '../../../entities/ai-setting/model/index.ts';
import type {
  AiSettingModule,
  Draft,
  ModelDraft,
  PromptModel,
  SlotAt,
  VersionRow,
  VersionStatus,
} from '../../../entities/ai-setting/model/index.ts';
import {
  ApplyConfirm,
  Column,
  ColumnItem,
  SaveBar,
  SaveDialog,
  VersionColumn,
} from '../../../shared/ui/ai-setting/index.ts';
import type { VersionColumnRow } from '../../../shared/ui/ai-setting/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import {
  useDelayed,
  useRetryFocus,
} from '../../../shared/ui/load-skeleton/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import {
  useAiSettings,
  useDraft,
  usePromptModel,
  useSave,
} from '../hooks/index.ts';
import type { PromptModelState } from '../hooks/index.ts';
import { changeList, componentLines, slotKey } from '../model/index.ts';
import {
  FixedCard,
  ModelDetail,
  ModuleDetail,
  PromptDetail,
} from './DetailCards.tsx';
import { ActionButton, LoadFailure } from './parts.tsx';

const words = AI_SETTING_TEXT;

/** 판 배지 → 키트 badge 변형(초안 blue, 적용 중 success, 지난 버전·기본 grey). */
export const STATUS_LOOK = {
  testing: 'blue',
  applied: 'success',
  past: 'grey',
  default: 'grey',
} as const satisfies Record<VersionStatus, 'blue' | 'success' | 'grey'>;

/** 「2026-10-19T11:40:00+09:00」 → 「2026-10-19」(서버가 +09:00 으로 준다 — 글자를 자른다). */
const dayOf = (at: string) => at.slice(0, 10);
/** 「2026-10-19 11:40」. */
const minuteOf = (at: string) => `${at.slice(0, 10)} ${at.slice(11, 16)}`;

export interface AiSettingsScreenProps {
  /** 모듈 줄(첫 줄을 그린다). */
  modules: readonly AiSettingModule[];
  /** 처음 고를 판 번호(search version). */
  initialVersion?: string;
  /** 고친 것이 생기고 없어질 때(라우터가 메뉴 이동을 막는 데 쓴다 — 화면은 라우터를 모른다). */
  onDirtyChange?(dirty: boolean): void;
  /** 라우터가 막아 둔 이동(pending 이면 나가기 창 — [나가기] proceed · [취소] reset). */
  leave?: { pending: boolean; proceed(): void; reset(): void };
}

/** 초안의 모델 칸 하나를 바꾼다. */
const setModel = (draft: Draft, slot: number, change: Partial<ModelDraft>) => ({
  ...draft,
  models: draft.models.map((one, index) =>
    index === slot ? { ...one, ...change } : one,
  ),
});

/** 판 열 줄 → 공통 부품 줄. */
const columnRow = (row: VersionRow): VersionColumnRow => ({
  key: row.key,
  name: versionLabel(row),
  badge: { label: words.status[row.status], look: STATUS_LOOK[row.status] },
  sum:
    row.kind === 'saved' && row.createdAt !== null ?
      dayOf(row.createdAt)
    : words.defaultSum,
  divided: row.kind === 'default',
});

/** 칸 고름 목록(묶음 차례 → 칸 차례). */
const slotList = (current: PromptModel) =>
  current.promptGroups.flatMap((group, groupIndex) =>
    group.prompts.map((entry, promptIndex) => ({
      groupIndex,
      promptIndex,
      entry,
    })),
  );

export function AiSettingsScreen({
  modules,
  initialVersion,
  onDirtyChange,
  leave,
}: AiSettingsScreenProps) {
  const module = modules[0]!;
  const { port } = module;
  const settings = useAiSettings(port);
  const state = settings.state;
  const loading = useDelayed(state.phase === 'loading');
  const retryFocus = useRetryFocus<HTMLHeadingElement>(state.phase);
  const [picked, setPicked] = useState<string | null>(null);
  const [component, setComponent] = useState('prompt');
  /** 고른 칸(null = 모듈의 첫 칸 — firstSlot, 없으면 묶음 0 칸 0. 밴드 TRA2). */
  const [slot, setSlot] = useState<SlotAt | null>(null);
  const [applyOpen, setApplyOpen] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyFailure, setApplyFailure] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [leaveTo, setLeaveTo] = useState<string | null>(null);
  const [revertOpen, setRevertOpen] = useState(false);
  // 같은 틱의 두 번 누름도 막는다(상태는 다음 그림에서야 바뀐다).
  const busy = useRef(false);
  const applyButton = useRef<HTMLSpanElement>(null);

  const rows =
    state.phase === 'ready' ? [...state.page.rows, state.page.base] : [];
  const chosenKey =
    state.phase !== 'ready' ? null
    : rows.some((row) => row.key === picked) ? picked
    : firstPick(rows, initialVersion);
  const chosen = rows.find((row) => row.key === chosenKey);
  const read = usePromptModel(port, chosenKey);
  const detailLoading = useDelayed(read.state?.kind === 'loading');
  const model = read.state?.kind === 'ok' ? read.state.model : null;
  const draft = useDraft(chosenKey, model, module.draft);
  const flowGroups =
    model?.promptGroups.map((one) => ({
      key: one.key,
      label: one.label,
      prompts: one.prompts.map(({ key, label }) => ({ key, label })),
    })) ?? [];
  const slotNow: SlotAt =
    slot ??
    (model && module.firstSlot ?
      module.firstSlot(flowGroups)
    : { group: 0, prompt: 0 });
  const moduleLoading = useDelayed(draft.module?.kind === 'loading');
  const { dirty } = draft;
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);
  const save = useSave({
    port,
    chosen,
    model,
    draft,
    slot: module.draft,
    refreshKeep: settings.refreshKeep,
    words: words.save,
    onCreated: () => setNotice(null),
    onSaved: (key, number) => {
      setPicked(key);
      setNotice(words.save.done(number));
    },
  });
  const { form, saving, refused, moduleRefused, saved, problems, canSave } =
    save;

  const canApply =
    chosen !== undefined &&
    chosen.status !== 'applied' &&
    !applying &&
    !dirty &&
    !saving;
  const nameOf = (row: VersionRow) =>
    row.kind === 'default' ? words.applyDialog.defaultName : row.number;
  const appliedRow = rows.find((row) => row.status === 'applied');
  const appliedName = () =>
    appliedRow ? nameOf(appliedRow) : words.applyDialog.defaultName;
  // 창을 연 때의 켬(창이 열린 뒤 적용 중으로 바뀌면 보내지 않는다).
  const canApplyNow = useRef(false);
  canApplyNow.current = chosen !== undefined && chosen.status !== 'applied';
  const confirmApply = async () => {
    if (!chosen || busy.current || !canApplyNow.current) return;
    busy.current = true;
    setApplying(true);
    setApplyFailure(null);
    try {
      // 모듈 어댑터는 실패를 갈래로 준다 — 던져도 같은 실패 줄(창은 열린 채).
      const outcome = await port
        .apply(chosen.kind === 'default' ? null : chosen.key)
        .catch(() => ({ kind: 'failed' as const }));
      if (outcome.kind !== 'ok') {
        setApplyFailure(words.applyDialog.failed);
        return;
      }
      await settings.refresh();
      setApplyOpen(false);
      setNotice(words.applyDialog.done(nameOf(chosen)));
    } finally {
      busy.current = false;
      setApplying(false);
    }
  };

  /** 판을 바꾼다(초안·고른 칸은 새로 — 검증 권고 R3). */
  const pick = (key: string) => {
    setPicked(key);
    setSlot(null);
    draft.clear();
    save.clearRefused();
  };
  /** 판 줄 누름: 고친 채 다른 판이면 나가기 창. */
  const onPick = (key: string) => {
    if (saving) return;
    if (key === chosenKey) return;
    if (dirty) {
      setLeaveTo(key);
      return;
    }
    pick(key);
  };

  // 막힌 이동을 보내는 곳은 여기 하나: 저장 중이면 끝난 뒤에, 고친 것이 남았으면(실패·거절) 나가기 창, 없으면 그대로 보낸다.
  //   막힌 이동은 고친 것이 있을 때만 생기므로(라우터 shouldBlockFn) 「pending · 고친 것 0」은 저장 성공 뒤이거나 [나가기](초안 비움) 뒤뿐이다.
  //   leave 는 그림마다 새 객체라 deps 에 넣지 않고 최신 proceed 를 ref 로 부른다.
  const proceedLeave = useRef(leave?.proceed);
  proceedLeave.current = leave?.proceed;
  const leavePending = leave?.pending === true;
  useEffect(() => {
    if (leavePending && !saving && !dirty) proceedLeave.current?.();
  }, [leavePending, saving, dirty]);

  const slots = model ? slotList(model) : [];
  // 모듈이 고친 것 조각(글 한 줄이면 「 · 」로 잇고, 항목 목록이면 항목으로 덧붙인다).
  const moduleChanged =
    module.draft && draft.module?.kind === 'ok' && draft.changes.module > 0 ?
      module.draft.changed(draft.module.base, draft.module.draft)
    : [];
  const commonChanged =
    model && draft.draft ?
      changeList({
        model,
        changedSlots: changedModels(model, draft.draft),
        changes: draft.changes,
        words: { ...words.changed, slot: words.prompt.slot },
      })
    : null;
  const changedLine =
    commonChanged === null || moduleChanged.length === 0 ? commonChanged
    : Array.isArray(commonChanged) ? [...commonChanged, ...moduleChanged]
    : [commonChanged, ...moduleChanged]
        .filter((one) => one !== '')
        .join(words.changed.join);
  const grouped = (model?.promptGroups.length ?? 0) > 1;

  const lines = componentLines({
    model,
    changes: draft.changes,
    components: module.components,
    words: {
      ...words.components,
      pending: words.pendingSum,
      retry: words.retry,
    },
    moduleTail:
      module.draft && draft.module ?
        {
          state: draft.module.kind,
          count: draft.changes.module,
          sum:
            draft.module.kind === 'ok' ?
              module.draft.sum(draft.module.base, draft.module.draft)
            : '',
        }
      : undefined,
  });
  const shownComponent =
    lines.some((line) => line.key === component) ? component : 'prompt';

  const detail = (current: PromptModelState | null) => {
    if (!chosen || current === null) return null;
    const moduleLine = module.components.find(
      (one) => `module:${one.key}` === shownComponent,
    );
    if (moduleLine?.body.kind === 'draft') {
      const slot = module.draft;
      const mine = draft.module;
      if (!slot || !mine) return null;
      if (mine.kind === 'loading')
        return (
          <Card
            aria-busy={moduleLoading || undefined}
            data-testid="module-loading"
          >
            {moduleLoading ?
              <TableSkeleton />
            : null}
          </Card>
        );
      if (mine.kind === 'failed')
        return (
          <Card>
            <LoadFailure
              text={words.failed}
              retry={words.retry}
              testId="module-failure"
              onRetry={draft.retryModule}
            />
          </Card>
        );
      return slot.render({
        base: mine.base,
        draft: mine.draft,
        readOnly: read.state?.kind !== 'ok',
        refused: moduleRefused,
        onChange: (next) => {
          // 잠긴 동안(저장 흐름·정보 띠)은 초안이 받지 않으니 짚은 자리도 그대로 둔다.
          if (draft.updateModule(next)) save.forgetModuleRefused();
        },
      });
    }
    if (moduleLine)
      return (
        <ModuleDetail component={{ ...moduleLine, body: moduleLine.body }} />
      );
    if (current.kind === 'loading')
      return (
        <Card
          aria-busy={detailLoading || undefined}
          data-testid="detail-loading"
        >
          {detailLoading ?
            <TableSkeleton />
          : null}
        </Card>
      );
    if (current.kind === 'unusable')
      return (
        <Card>
          <PageInfo tone="error" role="alert" data-testid="detail-unusable">
            {current.message}
          </PageInfo>
        </Card>
      );
    if (current.kind !== 'ok')
      return (
        <Card>
          <LoadFailure
            text={words.failed}
            retry={words.retry}
            testId="detail-failure"
            onRetry={() => read.forget(chosen.key)}
          />
        </Card>
      );
    const pm = current.model;
    if (shownComponent === 'model' && draft.draft)
      return (
        <ModelDetail
          slots={pm.models}
          groups={pm.promptGroups}
          note={module.modelNote}
          hideTemperature={module.hideTemperature}
          models={draft.draft.models}
          errors={draft.errors}
          readOnly={!pm.editable.model}
          edited={draft.changes.model > 0}
          onRoute={(index, route) =>
            draft.update((before) => withRoute(pm, before, index, route))
          }
          onTemperature={(index, text) =>
            draft.update((before) =>
              setModel(before, index, { temperature: text }),
            )
          }
          onMaxOutputTokens={(index, text) =>
            draft.update((before) =>
              setModel(before, index, { maxOutputTokens: text }),
            )
          }
        />
      );
    const group = pm.fixed.find((one) => `fixed:${one.key}` === shownComponent);
    if (group) return <FixedCard group={group} />;
    const at =
      pm.promptGroups[slotNow.group]?.prompts[slotNow.prompt] ?
        slotNow
      : { group: 0, prompt: 0 };
    const entry = pm.promptGroups[at.group]?.prompts[at.prompt];
    const value = draft.draft?.prompts[at.group]?.[at.prompt];
    if (!entry || !value) return null;
    const setSlotValue = (change: { text?: string; memo?: string }) => {
      // 서버가 짚은 칸 오류는 그 칸을 고치면 걷는다(고침을 받았을 때만 — 잠긴 동안은 그대로).
      if (
        draft.update((before) => ({
          ...before,
          prompts: before.prompts.map((group, groupIndex) =>
            group.map((one, promptIndex) =>
              groupIndex === at.group && promptIndex === at.prompt ?
                { ...one, ...change }
              : one,
            ),
          ),
        }))
      )
        save.forgetRefused(at.group, at.prompt, Object.keys(change));
    };
    // 처리 흐름은 프롬프트 카드 안 단계 줄 앞 소제목 꼴로(밴드 PF1 — 시안 AD-02_r3, 따로 카드 0).
    const flow =
      module.flow ?
        module.flow({
          groups: flowGroups,
          picked: at,
          edited: draft.changes.prompts,
          refused: slots
            .filter(
              ({ groupIndex, promptIndex }) =>
                Object.keys(refused[slotKey(groupIndex, promptIndex)] ?? {})
                  .length > 0,
            )
            .map(({ groupIndex, promptIndex }) => ({
              group: groupIndex,
              prompt: promptIndex,
            })),
          onPick: (next) => setSlot(next),
          inline: true,
        })
      : undefined;
    return (
      <PromptDetail
        value={value}
        errors={
          draft.slotErrors[at.group]?.[at.prompt] ?? { text: null, memo: null }
        }
        server={refused[slotKey(at.group, at.prompt)] ?? {}}
        edited={draft.changes.prompts.some(
          (one) => one.group === at.group && one.prompt === at.prompt,
        )}
        basedOn={dirty ? words.prompt.basedOn(versionName(chosen)) : null}
        notice={dirty ? words.prompt.notice(appliedName()) : null}
        readOnly={!pm.editable.prompts}
        onText={(text) => setSlotValue({ text })}
        onMemo={(memo) => setSlotValue({ memo })}
        version={versionName(chosen)}
        meta={
          chosen.kind === 'saved' && chosen.createdAt !== null ?
            {
              created: `${minuteOf(chosen.createdAt)} · ${chosen.author ?? words.unknownAuthor}`,
              memo: chosen.memo,
            }
          : null
        }
        entry={entry}
        limits={pm.limits}
        flow={flow}
        slotLabel={module.slotLabel}
        lowerKey={module.lowerKey}
        promptNote={module.promptNote?.(
          pm.promptGroups[at.group]!.key,
          entry.key,
        )}
        outputNote={module.outputNote?.(
          pm.promptGroups[at.group]!.key,
          entry.key,
        )}
      />
    );
  };

  const body = () => {
    if (state.phase === 'loading')
      return (
        <Card aria-busy={loading || undefined} data-testid="loading">
          {loading ?
            <TableSkeleton />
          : null}
        </Card>
      );
    if (state.phase === 'failed')
      return (
        <Card>
          <LoadFailure
            text={words.failed}
            retry={words.retry}
            retryRef={retryFocus.actionRef}
            onRetry={retryFocus.arm(settings.retry)}
          />
        </Card>
      );
    if (!chosen) return null;
    return (
      <>
        {notice !== null && (
          <PageInfo role="status" data-testid="notice">
            {notice}
          </PageInfo>
        )}
        {saved !== null && (
          <div
            data-testid="saved-band"
            className="flex flex-wrap items-center justify-between gap-3"
          >
            <PageInfo role="status" className="grow">
              {words.save.listFailed(saved.number)}
            </PageInfo>
            <ActionButton
              off={false}
              variant="solidBlack"
              shape="round"
              size="md"
              onClick={() => void save.retrySaved()}
            >
              {words.retry}
            </ActionButton>
          </div>
        )}
        {dirty && (
          <SaveBar
            count={words.saveBar.count(draft.changes.total)}
            revert={words.saveBar.revert}
            save={words.saveBar.save}
            saveOff={!draft.valid || saving}
            onRevert={() => setRevertOpen(true)}
            onSave={() => save.openSave('edit')}
          />
        )}
        <div
          className={cn(
            'box-border grid overflow-hidden rounded-dialog border border-solid border-grey-800 bg-background-primary',
            module.flow ? 'grid-cols-2' : 'grid-cols-3',
          )}
        >
          <VersionColumn
            title={words.columns.version}
            newVersion={{
              label: words.newVersion,
              off: dirty || model === null || saving,
              title: words.newVersionNote,
              onClick: () => save.openSave('copy'),
            }}
            selected={chosenKey}
            onSelect={onPick}
            rows={rows.map((row) =>
              dirty && row.key === chosenKey ?
                {
                  ...columnRow(row),
                  editing: true,
                  editNote: words.editingSum(versionName(row)),
                }
              : columnRow(row),
            )}
            footer={
              state.more ?
                <ActionButton
                  off={state.loadingMore || saving}
                  size="sm"
                  className="w-full"
                  onClick={settings.loadMore}
                >
                  {words.more}
                </ActionButton>
              : undefined
            }
          />
          <Column title={words.columns.component}>
            {lines.map((line) => (
              <ColumnItem
                key={line.key}
                selected={line.key === shownComponent}
                onSelect={() => setComponent(line.key)}
                sum={line.sum}
                locked={line.locked}
              >
                {line.label}
              </ColumnItem>
            ))}
          </Column>
          {!module.flow && (
            <Column title={words.columns.category}>
              {model ?
                slots.map(({ groupIndex, promptIndex, entry }, index) => [
                  grouped && promptIndex === 0 && (
                    <li
                      key={`group:${groupIndex}`}
                      data-group={model.promptGroups[groupIndex]!.key}
                      className="px-3 pt-2 pb-1 text-style-pre-caption-02 text-text-tertiary"
                    >
                      {words.prompt.slot(
                        groupIndex + 1,
                        model.promptGroups[groupIndex]!.label,
                      )}
                    </li>
                  ),
                  <ColumnItem
                    key={`${groupIndex}/${entry.key}`}
                    sum={
                      (
                        Object.keys(
                          refused[slotKey(groupIndex, promptIndex)] ?? {},
                        ).length > 0
                      ) ?
                        <span className="inline-flex items-center gap-1 text-support-error-accent">
                          <span
                            aria-hidden
                            className="size-1.5 rounded-full bg-support-error-accent"
                          />
                          <span data-testid="slot-refused">
                            {words.prompt.slotError}
                          </span>
                        </span>
                      : undefined
                    }
                    selected={
                      shownComponent === 'prompt' &&
                      slotNow.group === groupIndex &&
                      slotNow.prompt === promptIndex
                    }
                    onSelect={() => {
                      setSlot({ group: groupIndex, prompt: promptIndex });
                      setComponent('prompt');
                    }}
                  >
                    {grouped ?
                      entry.label
                    : words.prompt.slot(index + 1, entry.label)}
                  </ColumnItem>,
                ])
              : null}
            </Column>
          )}
        </div>
        {detail(read.state)}
      </>
    );
  };

  return (
    <div
      data-screen="admin-ai-settings"
      data-module={module.id}
      className="flex flex-col gap-6"
    >
      {/* 적용 안내(모듈 applyNote — 있을 때만, 밴드 RPW12): 바깥 gap-6 안에서 제목과 한 겹으로 감싸 12 를 낸다. */}
      <div className="flex flex-col gap-3">
        <PageTitle
          title={words.title(module.name)}
          headingRef={retryFocus.doneRef}
          description={words.description}
          actions={
            <span ref={applyButton} className="contents">
              {dirty && (
                <span
                  data-testid="apply-note"
                  className="text-style-pre-caption-03 text-text-tertiary"
                >
                  {words.applyAfterSave}
                </span>
              )}
              <ActionButton
                off={!canApply}
                shape="round"
                size="md"
                onClick={() => {
                  if (!canApply) return;
                  setApplyFailure(null);
                  setApplyOpen(true);
                }}
              >
                {words.apply}
              </ActionButton>
            </span>
          }
        />
        {module.applyNote && (
          <p
            data-testid="module-apply-note"
            className="m-0 text-style-pre-caption-03 text-text-tertiary"
          >
            {module.applyNote}
          </p>
        )}
      </div>
      <span className="sr-only" role="status">
        {loading ? words.loading : null}
      </span>
      {body()}
      {applyOpen && chosen && (
        <ApplyConfirm
          title={words.applyDialog.title(nameOf(chosen))}
          body={words.applyDialog.body(nameOf(chosen), appliedName())}
          cancel={words.applyDialog.cancel}
          confirm={words.applyDialog.confirm}
          failure={applyFailure}
          pending={applying}
          returnFocus={applyButton.current?.querySelector('button') ?? null}
          onConfirm={() => void confirmApply()}
          onClose={() => setApplyOpen(false)}
        />
      )}
      {revertOpen && chosen && (
        <ApplyConfirm
          testId="revert-confirm"
          title={words.revert.title(draft.changes.total)}
          body={words.revert.body(versionName(chosen))}
          cancel={words.revert.cancel}
          confirm={words.revert.confirm}
          failure={null}
          pending={false}
          onConfirm={() => {
            draft.clear();
            save.clearRefused();
            setRevertOpen(false);
          }}
          onClose={() => setRevertOpen(false)}
        />
      )}
      {(leaveTo !== null || (leavePending && !saving && dirty)) && (
        <ApplyConfirm
          testId="leave-confirm"
          title={words.leave.title}
          body={words.leave.body}
          cancel={words.leave.cancel}
          confirm={words.leave.confirm}
          failure={null}
          pending={false}
          onConfirm={() => {
            if (leaveTo !== null) {
              pick(leaveTo);
              setLeaveTo(null);
              return;
            }
            // 고친 것이 0 이 되면 위 효과가 막은 이동을 보낸다.
            draft.clear();
          }}
          onClose={() => {
            setLeaveTo(null);
            leave?.reset();
          }}
        />
      )}
      {form && chosen && (
        <SaveDialog
          title={words.save.title}
          body={
            form.mode === 'copy' ?
              words.save.copyBody(
                words.baseName(versionName(chosen), chosen.kind === 'default'),
                appliedName(),
              )
            : words.save.body(
                words.baseName(versionName(chosen), chosen.kind === 'default'),
                draft.changes.total,
                appliedName(),
              )
          }
          changesLabel={words.save.changes}
          changes={form.mode === 'copy' ? null : changedLine}
          numberLabel={words.save.number}
          number={nextNumber(rows)}
          numberNote={words.save.numberNote}
          nameLabel={words.save.name}
          nameNote={words.save.nameNote}
          name={form.title}
          nameError={
            form.titleError ??
            (problems.title === 'empty' ? words.save.nameEmpty
            : problems.title === 'over' ? words.save.nameOver
            : null)
          }
          memoLabel={words.save.memo}
          memoNote={words.save.memoNote}
          memo={form.memo}
          memoError={
            form.memoError ??
            (problems.memo === 'over' ? words.save.memoOver : null)
          }
          failure={form.failure}
          cancel={words.save.cancel}
          confirm={words.save.confirm}
          canSave={canSave}
          pending={saving}
          onName={save.setTitle}
          onMemo={save.setMemo}
          onSave={() => void save.submitSave()}
          onClose={save.closeSave}
        />
      )}
    </div>
  );
}
