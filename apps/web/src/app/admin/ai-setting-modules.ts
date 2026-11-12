// AD-02 AI 설정의 모듈 줄(밴드 AD2W ① — sid:MARC-ENT-386: 껍데기(pages/admin-ai-settings)는 모듈을 import 하지 않고, 모듈은 여기에 한 줄).
//   모듈 줄 = 모듈 슬라이스의 실어댑터를 슬롯 꼴(entities/ai-setting 의 AiSettingModule)로 감싼 것. 통신은 슬라이스 어댑터가 한다(이 파일은 부르지 않는다).
//   - 그린워싱: 판 목록·적용은 entities/greenwash-setting 의 실어댑터, prompt-model 은 entities/ai-setting 의 공통 읽기 어댑터.
//     새 판 저장(③): 바탕 판의 기준표를 한 번 읽고(GET /{id} · 기본 판 /default — 발주서 Q4) 껍데기의 공통 본문과 합쳐 POST 한 번.
//     기준표 화면은 없어 바탕 판 기준표를 그대로 싣는다(sid:MARC-ENT-373). 바탕 판 읽기가 실패하면 POST 0 으로 failed.
//     구성 줄: 대상 단어(모듈 초안 슬롯 — AS3b ①, 카드는 entities/greenwash-setting/ui) · 고정 규칙(읽기 전용 줄 글 — GREENWASH_SETTING_TEXT.fixedRules).
//     파트·처리 값은 서버 fixed 가 준다. 대상 단어를 고쳤으면 그 목록을 싣고, 안 고친 저장·복제는 바탕 판 terms 그대로(null 은 null).
//     모듈 글(이름·모델 카드 곁 글·고정 규칙 머리·꼬리·셈 줄)은 GREENWASH_SETTING_TEXT.module(K9 — 공통 표에서 옮김).
//     처리 흐름 띠(AS3b ②): 셋째 열 대신 번호 마디로 프롬프트 칸을 고른다(entities/greenwash-setting/ui 의 flowSlot).
//   - 영문번역(밴드 TRA1): 판 목록·적용·저장은 entities/translation-setting 의 실어댑터, prompt-model 은 공통 읽기 어댑터(module 'translation').
//     모듈 몫이 없다 — 새 판 저장은 껍데기의 공통 본문 그대로 POST 한 번(바탕 판을 읽지 않는다, 모듈 초안 슬롯 없음). 구성 줄은 고정 규칙 하나,
//     모델 카드 곁 글 없음. 처리 흐름 띠(마디 = 프롬프트 묶음 다섯 + 칸 고름)는 entities/translation-setting/ui 의 flowSlot.
//     「고정 글」(서버 fixed readonly_prompts)은 이름만 — 글 몸(바탕 지시 2,433자 등)은 그리지 않는다(TRA2 D2, 접기는 2차).
//   - 데이터 검증(밴드 DVA2): 영문번역 꼴 — 판 목록·적용·저장은 entities/dataverify-setting, 공통 본문 그대로 POST 한 번. 흐름 띠는 마디 = 묶음 셋, 첫 칸 = 서버 차례({0,0}), 입력 글 자리 안내(promptNote)·출력 안내 모듈 글(outputNote).
//   - 중대성평가 IRO(밴드 IRA2): 데이터 검증 꼴 — entities/materiality-setting, 흐름 띠 마디 = 묶음 다섯 + 신뢰 출처, 실행 규칙은 서버 fixed 둘을 카드 하나로 접음, 분석 모델 temperature 줄 0(hideTemperature), 칸 아래 안내는 entity 의 materialityPromptNote(IRA3).
//   - 보고서 작성(밴드 RPA3): 중대성평가 꼴 — entities/drafting-setting, 흐름 띠 마디 = 묶음 둘, 입력 글 자리 안내, 모델 카드 곁 글 = 모의 위끝 안내(이슈 490), fixed 「근거 표지 규칙」은 이름만, 구성 줄 0.
//   다른 모듈(온실가스)은 서버 경로가 생기면 같은 꼴로 한 줄씩 더한다.
//   슬롯 id 가 AD-02 주소의 모듈 칸이다(/admin/ai-settings/<id> — 밴드 AM1). 다른 모듈 슬롯 id 는 경로 칸 낱말과 같게(translation·dataverify·…).
import { createPromptModelReader } from '../../entities/ai-setting/api/index.ts';
import { AI_SETTING_TEXT } from '../../entities/ai-setting/config/text.ts';
import { DEFAULT_VERSION_KEY } from '../../entities/ai-setting/model/index.ts';
import type {
  AiSettingModule,
  PromptModelOutcome,
  SaveOutcome,
  VersionPageOutcome,
  VersionRow,
} from '../../entities/ai-setting/model/index.ts';
import { createDataverifySettingServerPort } from '../../entities/dataverify-setting/api/index.ts';
import { DATAVERIFY_SETTING_TEXT } from '../../entities/dataverify-setting/config/text.ts';
import { REQUIRED_PLACEHOLDERS } from '../../entities/dataverify-setting/model/index.ts';
import type { SettingList as DataverifySettingList } from '../../entities/dataverify-setting/model/index.ts';
import { flowSlot as dataverifyFlowSlot } from '../../entities/dataverify-setting/ui/index.ts';
import { createDraftingSettingServerPort } from '../../entities/drafting-setting/api/index.ts';
import { DRAFTING_SETTING_TEXT } from '../../entities/drafting-setting/config/text.ts';
import { REQUIRED_PLACEHOLDERS as DRAFTING_PLACEHOLDERS } from '../../entities/drafting-setting/model/index.ts';
import type { SettingList as DraftingSettingList } from '../../entities/drafting-setting/model/index.ts';
import { flowSlot as draftingFlowSlot } from '../../entities/drafting-setting/ui/index.ts';
import { createGreenwashSettingServerPort } from '../../entities/greenwash-setting/api/index.ts';
import type { GreenwashSettingServerPort } from '../../entities/greenwash-setting/api/index.ts';
import { GREENWASH_SETTING_TEXT } from '../../entities/greenwash-setting/config/text.ts';
import type {
  SettingList,
  TermsDraft,
} from '../../entities/greenwash-setting/model/index.ts';
import {
  flowSlot,
  termsDraftSlot,
} from '../../entities/greenwash-setting/ui/index.ts';
import { createMaterialitySettingServerPort } from '../../entities/materiality-setting/api/index.ts';
import { MATERIALITY_SETTING_TEXT } from '../../entities/materiality-setting/config/text.ts';
import { ANALYSIS_SLOT } from '../../entities/materiality-setting/model/index.ts';
import type { SettingList as MaterialitySettingList } from '../../entities/materiality-setting/model/index.ts';
import { flowSlot as materialityFlowSlot } from '../../entities/materiality-setting/ui/index.ts';
import { materialityPromptNote } from '../../entities/materiality-setting/ui/index.ts';
import { createTranslationSettingServerPort } from '../../entities/translation-setting/api/index.ts';
import { TRANSLATION_SETTING_TEXT } from '../../entities/translation-setting/config/text.ts';
import {
  FLOW_GROUPS,
  firstShown,
} from '../../entities/translation-setting/model/index.ts';
import type { SettingList as TranslationSettingList } from '../../entities/translation-setting/model/index.ts';
import { flowSlot as translationFlowSlot } from '../../entities/translation-setting/ui/index.ts';
import type { Api } from '../../shared/api/index.ts';

/** 그린워싱 목록 한 쪽 → 슬롯 꼴(저장 판 줄 + 기본 판 줄). 적용 판은 줄의 상태로 접는다. */
export function greenwashPage(list: SettingList): VersionPageOutcome {
  return {
    kind: 'ok',
    page: {
      rows: list.items.map((item): VersionRow => ({
        key: String(item.id),
        kind: 'saved',
        number: item.name,
        title: item.title,
        status: item.status,
        createdAt: item.createdAt,
        author: item.createdBy.name,
        memo: item.memo,
      })),
      base: {
        key: DEFAULT_VERSION_KEY,
        kind: 'default',
        number: list.default.name,
        title: list.default.title,
        status: list.applied.kind === 'default' ? 'applied' : 'default',
        createdAt: null,
        author: null,
        memo: '',
      },
      total: list.total,
    },
  };
}

/** 그린워싱 모듈 줄. */
export function greenwashModule(api: Api): AiSettingModule {
  const server = createGreenwashSettingServerPort({ api });
  const readPromptModel = createPromptModelReader({ api, module: 'greenwash' });
  const words = AI_SETTING_TEXT;
  const own = GREENWASH_SETTING_TEXT;
  return {
    id: 'greenwash',
    name: own.module.name,
    modelNote: own.module.modelNote,
    flow: flowSlot(own),
    draft: termsDraftSlot(
      {
        get: (id) => server.get(id),
        getDefault: () => server.getDefault(),
        defaultTerms: () => server.defaultTerms(),
      },
      own,
    ),
    port: {
      async list(offset) {
        const outcome = await server.list(offset);
        return outcome.kind === 'ok' ?
            greenwashPage(outcome.list)
          : { kind: 'failed' };
      },
      async apply(key) {
        const outcome = await server.apply(key);
        return outcome.kind === 'ok' ? { kind: 'ok' } : { kind: 'failed' };
      },
      promptModel: readPromptModel,
      async create(base, body, moduleDraft): Promise<SaveOutcome> {
        const loaded =
          base === DEFAULT_VERSION_KEY ?
            await server.getDefault()
          : await server.get(base);
        if (loaded.kind !== 'ok') return { kind: 'failed' };
        const input: Parameters<GreenwashSettingServerPort['create']>[0] = {
          ...body,
          criteria: loaded.setting.criteria,
          // 안 고침·읽기 실패·복제(moduleDraft null·undefined)는 바탕 판 terms 그대로 — null 을 목록으로 펼치지 않는다.
          terms:
            moduleDraft === null || moduleDraft === undefined ?
              loaded.setting.terms
            : (moduleDraft as TermsDraft).map((term) => ({
                text: term.text.trim(),
                enabled: term.enabled,
              })),
        };
        const outcome = await server.create(input);
        if (outcome.kind === 'ok')
          return {
            kind: 'ok',
            key: String(outcome.setting.id),
            number: outcome.setting.name,
          };
        return outcome;
      },
    },
    components: [
      {
        key: 'terms',
        label: own.terms.title,
        sum: '',
        body: { kind: 'draft' },
      },
      {
        key: 'codeRules',
        label: words.codeRules.label,
        sum: words.codeRules.sum,
        body: {
          kind: 'lines',
          title: own.module.codeRules.title,
          lines: own.fixedRules,
          foot: own.module.codeRules.foot,
        },
      },
    ],
  };
}

/** 영문번역 목록 한 쪽 → 슬롯 꼴(저장 판 줄 + 기본 판 줄 — greenwashPage 와 같은 꼴). 적용 판은 줄의 상태로 접는다. */
export function translationPage(
  list: TranslationSettingList,
): VersionPageOutcome {
  return {
    kind: 'ok',
    page: {
      rows: list.items.map((item): VersionRow => ({
        key: String(item.id),
        kind: 'saved',
        number: item.name,
        title: item.title,
        status: item.status,
        createdAt: item.createdAt,
        author: item.createdBy.name,
        memo: item.memo,
      })),
      base: {
        key: DEFAULT_VERSION_KEY,
        kind: 'default',
        number: list.default.name,
        title: list.default.title,
        status: list.applied.kind === 'default' ? 'applied' : 'default',
        createdAt: null,
        author: null,
        memo: '',
      },
      total: list.total,
    },
  };
}

/** 영문번역 「고정 글」 묶음의 값을 비운다(카드는 이름만 — FixedCard 의 null 길). 처리 값 등 다른 묶음은 그대로. */
export function translationPromptModel(
  outcome: PromptModelOutcome,
): PromptModelOutcome {
  if (outcome.kind !== 'ok') return outcome;
  return {
    kind: 'ok',
    model: {
      ...outcome.model,
      fixed: outcome.model.fixed.map((group) =>
        group.key === 'readonly_prompts' ?
          {
            ...group,
            items: group.items.map((item) => ({ ...item, value: null })),
          }
        : group,
      ),
    },
  };
}

/** 영문번역 모듈 줄(밴드 TRA1). */
export function translationModule(api: Api): AiSettingModule {
  const server = createTranslationSettingServerPort({ api });
  const readPromptModel = createPromptModelReader({
    api,
    module: 'translation',
  });
  const own = TRANSLATION_SETTING_TEXT;
  return {
    id: 'translation',
    name: own.module.name,
    flow: translationFlowSlot(own.flow),
    // 처음 펼침·판 바꿈 = 보이는 차례의 첫 칸(번역 묶음은 소묶음 차례 — TRA2 D1). 상세 라벨 「칸」·KEY 소문자(D9·D10).
    firstSlot: (groups) => {
      const group = Math.max(
        0,
        groups.findIndex((one) => one.key === FLOW_GROUPS[0]),
      );
      return {
        group,
        prompt: groups[group] ? firstShown(groups[group]) : 0,
      };
    },
    slotLabel: own.module.slotLabel,
    lowerKey: true,
    port: {
      async list(offset) {
        const outcome = await server.list(offset);
        return outcome.kind === 'ok' ?
            translationPage(outcome.list)
          : { kind: 'failed' };
      },
      async apply(key) {
        const outcome = await server.apply(key);
        return outcome.kind === 'ok' ? { kind: 'ok' } : { kind: 'failed' };
      },
      promptModel: async (key) =>
        translationPromptModel(await readPromptModel(key)),
      // 모듈 몫이 없어 바탕 판(base)을 읽지 않는다 — 공통 본문 그대로 POST 한 번.
      async create(_base, body): Promise<SaveOutcome> {
        const outcome = await server.create(body);
        if (outcome.kind === 'ok')
          return {
            kind: 'ok',
            key: String(outcome.setting.id),
            number: outcome.setting.name,
          };
        return outcome;
      },
    },
    components: [
      {
        key: 'codeRules',
        label: AI_SETTING_TEXT.codeRules.label,
        sum: AI_SETTING_TEXT.codeRules.sum,
        body: {
          kind: 'lines',
          title: own.module.codeRules.title,
          lines: own.fixedRules,
          foot: own.module.codeRules.foot,
        },
      },
    ],
  };
}

/** 데이터 검증 목록 한 쪽 → 슬롯 꼴(저장 판 줄 + 기본 판 줄 — translationPage 와 같은 꼴). 적용 판은 줄의 상태로 접는다. */
export function dataverifyPage(
  list: DataverifySettingList,
): VersionPageOutcome {
  return {
    kind: 'ok',
    page: {
      rows: list.items.map((item): VersionRow => ({
        key: String(item.id),
        kind: 'saved',
        number: item.name,
        title: item.title,
        status: item.status,
        createdAt: item.createdAt,
        author: item.createdBy.name,
        memo: item.memo,
      })),
      base: {
        key: DEFAULT_VERSION_KEY,
        kind: 'default',
        number: list.default.name,
        title: list.default.title,
        status: list.applied.kind === 'default' ? 'applied' : 'default',
        createdAt: null,
        author: null,
        memo: '',
      },
      total: list.total,
    },
  };
}

/** 데이터 검증 모듈 줄(밴드 DVA2). */
export function dataverifyModule(api: Api): AiSettingModule {
  const server = createDataverifySettingServerPort({ api });
  const own = DATAVERIFY_SETTING_TEXT;
  return {
    id: 'dataverify',
    name: own.module.name,
    modelNote: own.module.modelNote,
    flow: dataverifyFlowSlot(own.flow),
    // 띠 차례 = 서버 차례라 firstSlot 없음(묶음 0 칸 0 = 계산 계획 지시 글 — TRA2 D1). 상세 라벨 「칸」·KEY 소문자(D9·D10).
    slotLabel: own.module.slotLabel,
    lowerKey: true,
    // 입력 글 칸 아래 자리 안내(이슈 sid:MARC-ISSUE-370 처분 (가) — 막지 않음, 지우면 서버 400 이 칸 오류로). 지시 글은 null.
    promptNote: (_group, prompt) => {
      const slots = REQUIRED_PLACEHOLDERS[prompt];
      if (!slots) return null;
      const words = own.placeholders;
      const body = prompt === 'review_user' ? words.review : words.company;
      return `${words.lead(slots)} — ${body} · ${words.tail}`;
    },
    // 출력 안내 모듈 글(계산 계획·인사이트 지시 글). 그 밖 칸은 null → 껍데기 규칙(outputSection 있으면 공통 글).
    outputNote: (_group, prompt) => own.outputNotes[prompt] ?? null,
    port: {
      async list(offset) {
        const outcome = await server.list(offset);
        return outcome.kind === 'ok' ?
            dataverifyPage(outcome.list)
          : { kind: 'failed' };
      },
      async apply(key) {
        const outcome = await server.apply(key);
        return outcome.kind === 'ok' ? { kind: 'ok' } : { kind: 'failed' };
      },
      // 받은 그대로(계산 도구·처리 값은 서버 fixed 그대로 — 영문번역의 「고정 글」 비움 같은 덮기 없음).
      promptModel: createPromptModelReader({ api, module: 'dataverify' }),
      // 모듈 몫이 없어 바탕 판(base)을 읽지 않는다 — 공통 본문 그대로 POST 한 번.
      async create(_base, body): Promise<SaveOutcome> {
        const outcome = await server.create(body);
        if (outcome.kind === 'ok')
          return {
            kind: 'ok',
            key: String(outcome.setting.id),
            number: outcome.setting.name,
          };
        return outcome;
      },
    },
    components: [
      {
        key: 'codeRules',
        label: AI_SETTING_TEXT.codeRules.label,
        sum: AI_SETTING_TEXT.codeRules.sum,
        body: {
          kind: 'lines',
          title: own.module.codeRules.title,
          lines: own.fixedRules,
          foot: own.module.codeRules.foot,
        },
      },
    ],
  };
}

/** 중대성평가 IRO 목록 한 쪽 → 슬롯 꼴(저장 판 줄 + 기본 판 줄 — dataverifyPage 와 같은 꼴). 적용 판은 줄의 상태로 접는다. */
export function materialityPage(
  list: MaterialitySettingList,
): VersionPageOutcome {
  return {
    kind: 'ok',
    page: {
      rows: list.items.map((item): VersionRow => ({
        key: String(item.id),
        kind: 'saved',
        number: item.name,
        title: item.title,
        status: item.status,
        createdAt: item.createdAt,
        author: item.createdBy.name,
        memo: item.memo,
      })),
      base: {
        key: DEFAULT_VERSION_KEY,
        kind: 'default',
        number: list.default.name,
        title: list.default.title,
        status: list.applied.kind === 'default' ? 'applied' : 'default',
        createdAt: null,
        author: null,
        memo: '',
      },
      total: list.total,
    },
  };
}

/** 서버 fixed 의 웹 검색 묶음 key 와 실행 규칙 묶음 key(prompt_model_155.fixed_groups). */
const MATERIALITY_TOOLS = 'tools';
const MATERIALITY_PROCESSING = 'processing';

/**
 * 중대성평가 IRO fixed 둘(웹 검색 · 실행 규칙)을 카드 하나로 접는다(발주서 Q1 (가) — sid:MARC-ENT-468 「실행 규칙 · 고정」 카드 하나).
 * key·label 은 실행 규칙 것, 항목은 웹 검색 항목(label 「<웹 검색> · <항목>」 — 서버 글 이음) 다음 실행 규칙 항목. 값은 그대로.
 * 둘 중 하나라도 없으면 받은 그대로. 다른 묶음은 그 자리 그대로.
 */
export function materialityPromptModel(
  outcome: PromptModelOutcome,
): PromptModelOutcome {
  if (outcome.kind !== 'ok') return outcome;
  const { fixed } = outcome.model;
  const tools = fixed.find((group) => group.key === MATERIALITY_TOOLS);
  const processing = fixed.find(
    (group) => group.key === MATERIALITY_PROCESSING,
  );
  if (!tools || !processing) return outcome;
  const folded = {
    ...processing,
    items: [
      ...tools.items.map((item) => ({
        ...item,
        key: `${tools.key}.${item.key}`,
        label: `${tools.label} · ${item.label}`,
      })),
      ...processing.items,
    ],
  };
  return {
    kind: 'ok',
    model: {
      ...outcome.model,
      fixed: fixed.flatMap((group) =>
        group === tools ? [folded]
        : group === processing ? []
        : [group],
      ),
    },
  };
}

/** 중대성평가 IRO 모듈 줄(밴드 IRA2). */
export function materialityModule(api: Api): AiSettingModule {
  const server = createMaterialitySettingServerPort({ api });
  const readPromptModel = createPromptModelReader({
    api,
    module: 'materiality',
  });
  const own = MATERIALITY_SETTING_TEXT;
  return {
    id: 'materiality',
    name: own.module.name,
    modelNote: own.module.modelNote,
    flow: materialityFlowSlot(own.flow),
    // 띠 차례 = 서버 차례라 firstSlot 없음(묶음 0 칸 0 = 규제 지시 글 — TRA2 D1). 상세 라벨 「칸」·KEY 소문자(D9·D10).
    slotLabel: own.module.slotLabel,
    lowerKey: true,
    // 분석 모델은 temperature 를 싣지 않는다(sid:MARC-ENT-468 — 줄 0, 본문은 읽은 값 null 그대로).
    hideTemperature: (slot) => slot === ANALYSIS_SLOT,
    // 칸 아래 안내(자리 지킴 칸 넷 · 1부 입력 글 셋 — 몸은 entity 의 materialityPromptNote, 밴드 IRA3). 그 밖 칸은 null.
    promptNote: (_group, prompt) => materialityPromptNote(prompt),
    // 출력 안내 모듈 글(출력절 칸 여섯). 그 밖 칸은 null → 껍데기 규칙(outputSection 있으면 공통 글).
    outputNote: (_group, prompt) => own.outputNotes[prompt] ?? null,
    port: {
      async list(offset) {
        const outcome = await server.list(offset);
        return outcome.kind === 'ok' ?
            materialityPage(outcome.list)
          : { kind: 'failed' };
      },
      async apply(key) {
        const outcome = await server.apply(key);
        return outcome.kind === 'ok' ? { kind: 'ok' } : { kind: 'failed' };
      },
      promptModel: async (key) =>
        materialityPromptModel(await readPromptModel(key)),
      // 모듈 몫이 없어 바탕 판(base)을 읽지 않는다 — 공통 본문 그대로 POST 한 번.
      async create(_base, body): Promise<SaveOutcome> {
        const outcome = await server.create(body);
        if (outcome.kind === 'ok')
          return {
            kind: 'ok',
            key: String(outcome.setting.id),
            number: outcome.setting.name,
          };
        return outcome;
      },
    },
    components: [
      {
        key: 'codeRules',
        label: AI_SETTING_TEXT.codeRules.label,
        sum: AI_SETTING_TEXT.codeRules.sum,
        body: {
          kind: 'lines',
          title: own.module.codeRules.title,
          lines: own.fixedRules,
          foot: own.module.codeRules.foot,
        },
      },
    ],
  };
}

/** 보고서 작성 목록 한 쪽 → 슬롯 꼴(저장 판 줄 + 기본 판 줄 — materialityPage 와 같은 꼴). 적용 판은 줄의 상태로 접는다. */
export function draftingPage(list: DraftingSettingList): VersionPageOutcome {
  return {
    kind: 'ok',
    page: {
      rows: list.items.map((item): VersionRow => ({
        key: String(item.id),
        kind: 'saved',
        number: item.name,
        title: item.title,
        status: item.status,
        createdAt: item.createdAt,
        author: item.createdBy.name,
        memo: item.memo,
      })),
      base: {
        key: DEFAULT_VERSION_KEY,
        kind: 'default',
        number: list.default.name,
        title: list.default.title,
        status: list.applied.kind === 'default' ? 'applied' : 'default',
        createdAt: null,
        author: null,
        memo: '',
      },
      total: list.total,
    },
  };
}

/** 서버 fixed 의 근거 표지 규칙 묶음 key(prompt_model_v2.fixed_groups). */
const DRAFTING_RULES = 'rules';

/**
 * 보고서 작성 「근거 표지 규칙」 묶음의 값을 모두 비운다(카드는 이름만 — FixedCard 의 null 길, 발주서 Q2 (가) · translationPromptModel 꼴).
 * 항목 목록은 서버 그대로(이름·차례·수를 웹에 박지 않는다 — 항목이 늘어도 다 비운다). 실행 규칙 등 다른 묶음은 그대로.
 */
export function draftingPromptModel(
  outcome: PromptModelOutcome,
): PromptModelOutcome {
  if (outcome.kind !== 'ok') return outcome;
  return {
    kind: 'ok',
    model: {
      ...outcome.model,
      fixed: outcome.model.fixed.map((group) =>
        group.key === DRAFTING_RULES ?
          {
            ...group,
            items: group.items.map((item) => ({ ...item, value: null })),
          }
        : group,
      ),
    },
  };
}

/** 보고서 작성 모듈 줄(밴드 RPA3). */
export function draftingModule(api: Api): AiSettingModule {
  const server = createDraftingSettingServerPort({ api });
  const readPromptModel = createPromptModelReader({
    api,
    module: 'drafting',
  });
  const own = DRAFTING_SETTING_TEXT;
  return {
    id: 'drafting',
    name: own.module.name,
    flow: draftingFlowSlot(own.flow),
    // 띠 차례 = 서버 차례라 firstSlot 없음(묶음 0 칸 0 = map_system — TRA2 D1). 상세 라벨 「칸」·KEY 소문자(D9·D10).
    slotLabel: own.module.slotLabel,
    applyNote: own.applyNote,
    lowerKey: true,
    // 입력 글 둘 아래 자리 안내(DVA2 꼴 — 막지 않음, 지우면 서버 400 이 칸 오류로). 지시 글 둘은 null. 출력 안내는 서버 outputSection 이 늘 null 이라 0.
    promptNote: (_group, prompt) => {
      const slots = DRAFTING_PLACEHOLDERS[prompt];
      if (!slots) return null;
      const words = own.placeholders;
      return `${words.lead(slots)} · ${words.tail}`;
    },
    port: {
      async list(offset) {
        const outcome = await server.list(offset);
        return outcome.kind === 'ok' ?
            draftingPage(outcome.list)
          : { kind: 'failed' };
      },
      async apply(key) {
        const outcome = await server.apply(key);
        return outcome.kind === 'ok' ? { kind: 'ok' } : { kind: 'failed' };
      },
      promptModel: async (key) =>
        draftingPromptModel(await readPromptModel(key)),
      // 모듈 몫이 없어 바탕 판(base)을 읽지 않는다 — 공통 본문 그대로 POST 한 번.
      async create(_base, body): Promise<SaveOutcome> {
        const outcome = await server.create(body);
        if (outcome.kind === 'ok')
          return {
            kind: 'ok',
            key: String(outcome.setting.id),
            number: outcome.setting.name,
          };
        return outcome;
      },
    },
    // 구성 줄 0(발주서 Q5 (가) — 시안 구성 열 = 모델 설정 · 프롬프트 · 처리 값, 고정 규칙 카드 없음). 처리 값은 서버 fixed.
    components: [],
  };
}

/** AI 설정 머리 글(「AI 설정 — <모듈>」). 슬롯 없이 제 화면을 그리는 온실가스 껍데기가 쓴다(밴드 AD8) — AdminRoutes 는 글 표를 직접 가져오지 않는다. */
export const aiSettingTitle = AI_SETTING_TEXT.title;

/** AD-02 모듈 목록(그린워싱 · 영문번역 · 데이터 검증 · 중대성평가 IRO · 보고서 작성 — 모듈 탭 줄은 그리지 않는다, 주소의 모듈 칸이 하나를 고른다). */
export const aiSettingModules = (api: Api): readonly AiSettingModule[] => [
  greenwashModule(api),
  translationModule(api),
  dataverifyModule(api),
  materialityModule(api),
  draftingModule(api),
];
