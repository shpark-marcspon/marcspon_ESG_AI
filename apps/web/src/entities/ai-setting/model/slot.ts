// AI 설정 모듈 슬롯의 꼴(밴드 AD2W ① — sid:MARC-ENT-386 「껍데기는 모듈을 가져오지 않는다」). 타입과 순수 함수만 있다.
//   AD-02 껍데기(pages/admin-ai-settings)는 모듈 한 줄(AiSettingModule)만 받는다. 모듈 줄은 app/admin/ai-setting-modules.ts 가 짓는다
//   (그린워싱 줄 — 모듈 슬라이스의 실어댑터를 이 꼴로 감싼다). 다른 모듈(DV·TR·IR)은 같은 꼴로 한 줄씩 더한다.
//   - port: 판 목록 한 쪽·적용(①) · prompt-model 읽기(②) · 새 판 저장(③). 판 열쇠는 저장 판 String(id), 기본 판 DEFAULT_VERSION_KEY.
//     저장은 껍데기가 지은 공통 본문(SaveBody — 판 이름·메모·모델 설정·프롬프트)과 바탕 판 열쇠를 넘기고, 모듈 몫(그린워싱 = 기준표)은 모듈 줄이
//     바탕 판에서 읽어 합친다(발주서 Q4 — [저장]을 누를 때 한 번). 껍데기는 모듈 몫의 꼴을 모른다.
//   - components: 구성 열에 모듈이 더하는 줄 — 준비 중(pending) · 읽기 전용 줄 글(lines) · 모듈 초안 카드(draft — 슬롯이 그린다, AS3b).
//   - 처음 고름(firstPick): 판 번호가 맞는 줄 → 가장 새 「초안」 → 적용 중 → 기본 판.
//   - 모듈 초안 슬롯(draft — AP1W ③, AS3b 허락 설계 ⓐⓑⓒ): 모듈이 저장 본문에 드는 제 몫(그린워싱 = 대상 단어)을 고치게 하는 꼴. 바탕 몫 읽기·셈·저장 끔·
//     구성 꼬리·거절 풀이·카드를 모듈이 주고, 초안 상태는 껍데기의 useDraft 한 곳이 판 열쇠에 묶어 둔다. 껍데기는 몫의 꼴을 모른다(unknown).
import type { ReactNode } from 'react';

import type { Schemas } from '../../../shared/api/index.ts';

/** 판 열에서 기본 판 줄의 열쇠(저장 판 열쇠는 String(id) — 숫자 글자라 겹치지 않는다). */
export const DEFAULT_VERSION_KEY = 'default';

/** 판 줄의 상태: 저장 판은 서버 상태, 기본 판은 적용 중이거나 「기본」. */
export type VersionStatus = 'testing' | 'applied' | 'past' | 'default';

export interface VersionRow {
  /** 고름 열쇠(저장 판 String(id), 기본 판 DEFAULT_VERSION_KEY). */
  key: string;
  kind: 'saved' | 'default';
  /** 판 번호(v<n>). 기본 판은 서버의 기본 판 이름. */
  number: string;
  /** 판 이름. 이름 없는 옛 저장 판은 null. 기본 판은 서버 default.title. */
  title: string | null;
  status: VersionStatus;
  /** 만든 때(서버 글 그대로 — +09:00). 기본 판은 null. */
  createdAt: string | null;
  /** 만든 사람 이름(못 풀면 null). */
  author: string | null;
  memo: string;
}

/** 판 목록 한 쪽: 저장 판(서버 차례 — 새 것 먼저)·기본 판 줄·저장 판 전체 수. */
export interface VersionPage {
  rows: VersionRow[];
  base: VersionRow;
  total: number;
}

export type VersionPageOutcome =
  { kind: 'ok'; page: VersionPage } | { kind: 'failed' };
type ApplyOutcome = { kind: 'ok' } | { kind: 'failed' };

/** 판 하나의 prompt-model(ai.prompt-model@3 — 모델 칸 목록 + 프롬프트 묶음 목록, generated 그대로). */
export type PromptModel = Schemas['AiPromptModel3'];
/** 모델 칸 하나(모델 설정 한 줄 — 입력 modelSettings.steps 의 차례). */
export type ModelSlot = Schemas['AiModelSlot'];
/** 프롬프트 묶음 하나(입력 prompts.steps 의 차례). modelSlots = 그 글을 받는 모델 칸 key(화면 안내). */
export type PromptGroup = Schemas['AiPromptGroup'];
export type PromptEntry = Schemas['AiPromptEntry'];
export type FixedGroup = Schemas['AiFixedGroup'];
export type RouteChoice = Schemas['AiRouteChoice'];

/** 새 판 저장의 공통 본문(모듈 몫은 모듈 줄이 합친다). 프롬프트는 늘 넷 다(발주서 Q1), 모델 webSearch 는 읽은 값 그대로(sid:MARC-ENT-372). */
export interface SaveBody {
  title: string;
  memo: string;
  modelSettings: Schemas['AiModelSettingsIn'];
  prompts: Schemas['AiPromptsIn'];
}

/**
 * 새 판 저장의 갈래: 새 판(열쇠·번호 — 번호는 서버가 매김), 서버가 답한 거절(알아본 code 만, 서버 문장·칸 경로 → 문장),
 * 닿지 못함·바탕 판 읽기 실패·꼴 틀린 답은 failed.
 */
export type SaveOutcome =
  | { kind: 'ok'; key: string; number: string }
  | {
      kind: 'rejected';
      code: string | null;
      message: string | null;
      fields: Readonly<Record<string, readonly string[]>>;
    }
  | { kind: 'failed' };

/** prompt-model 읽기의 갈래: 쓸 수 없는 판(409)은 서버 문장, 없는 판(404), 그 밖(끊김·꼴 틀림·5xx)은 failed. */
export type PromptModelOutcome =
  | { kind: 'ok'; model: PromptModel }
  | { kind: 'unusable'; message: string }
  | { kind: 'missing' }
  | { kind: 'failed' };

export interface AiSettingPort {
  /** 저장 판 목록의 한 쪽(offset 부터)과 기본 판 줄. */
  list(offset: number): Promise<VersionPageOutcome>;
  /** 적용 판 바꾸기. null 은 기본 판. */
  apply(key: string | null): Promise<ApplyOutcome>;
  /** 판 하나의 prompt-model(ai.prompt-model@3). 기본 판은 DEFAULT_VERSION_KEY. */
  promptModel(key: string): Promise<PromptModelOutcome>;
  /**
   * 새 판 하나 저장(POST 한 번). base 는 바탕 판 열쇠 — 모듈 몫을 거기서 읽는다. module 은 모듈 초안 슬롯이 있고 고친 몫이 있을 때만 그 초안
   * (안 고쳤거나 복제면 null — 모듈 줄이 바탕 판 몫을 쓴다).
   */
  create(base: string, body: SaveBody, module?: unknown): Promise<SaveOutcome>;
}

/** 모듈 거절 풀이가 짚은 자리(모듈이 정한 열쇠 → 문장들). */
export type ModuleRefused = Readonly<Record<string, readonly string[]>>;

/**
 * 모듈 초안 슬롯(AP1W ③ — AS3b 허락 설계). 바탕 몫(base)과 초안(draft)의 꼴은 모듈만 안다.
 *   셈 0 이면 깨끗(저장 본문에 넣지 않음), blocked 면 저장을 끈다(바탕 몫을 읽었고 셈이 있을 때만 묻는다).
 */
export interface ModuleDraftSlot {
  /** 구성 줄 열쇠(ModuleComponent.key — body {kind:'draft'} 인 줄과 짝). */
  key: string;
  /** 판 하나의 바탕 몫 읽기(판 열쇠마다 한 번). */
  load(
    version: string,
  ): Promise<{ kind: 'ok'; base: unknown } | { kind: 'failed' }>;
  /** 고친 것 셈(0 = 깨끗). */
  count(base: unknown, draft: unknown): number;
  /** 저장 창 「고친 것」 조각. */
  changed(base: unknown, draft: unknown): string[];
  /** 저장 끔. */
  blocked(draft: unknown): boolean;
  /** 구성 꼬리(안 고쳤을 때). */
  sum(base: unknown, draft: unknown): string;
  /** 모듈이 아는 거절이면 창 줄·짚은 자리, 모르면 null. */
  refusal(
    code: string | null,
    fields: Readonly<Record<string, readonly string[]>>,
  ): { line: string; refused: ModuleRefused } | null;
  /** 상세 카드. */
  render(p: {
    base: unknown;
    draft: unknown;
    readOnly: boolean;
    onChange(next: unknown): void;
    refused: ModuleRefused;
  }): ReactNode;
}

/** 프롬프트 칸 자리(묶음 i, 칸 j). */
export interface SlotAt {
  group: number;
  prompt: number;
}

/**
 * 처리 흐름 띠(AS3b ② — 셋째 열을 갈음)에 껍데기가 넘기는 것: 묶음·칸(서버 key·label), 고른 칸, 고친 칸, 서버가 짚은 칸, 칸 고름.
 * 모듈은 제 흐름 차례대로 마디를 그리고 마디 이름은 이 label 을 쓴다(웹 상수에 이름 0).
 */
export interface FlowProps {
  groups: readonly {
    key: string;
    /** 묶음 이름(서버 label — 마디 = 묶음인 모듈이 쓴다, 밴드 TRA1). */
    label: string;
    prompts: readonly { key: string; label: string }[];
  }[];
  picked: SlotAt;
  edited: readonly SlotAt[];
  refused: readonly SlotAt[];
  onPick(at: SlotAt): void;
  /** 프롬프트 카드 안 소제목 꼴로(PF1 — 겉 카드 0). */
  inline?: boolean;
}

/** 구성 열에 모듈이 더하는 줄. */
export interface ModuleComponent {
  key: string;
  label: string;
  sum: string;
  body:
    | { kind: 'pending' }
    | { kind: 'lines'; title: string; lines: readonly string[]; foot: string }
    | { kind: 'draft' };
}

export interface AiSettingModule {
  /** 모듈 이름(경로 search·데이터 표식). */
  id: string;
  /** 보이는 이름(「그린워싱」). */
  name: string;
  port: AiSettingPort;
  components: readonly ModuleComponent[];
  /** 모델 설정 카드 머리 곁 글(모듈이 선언 — 없으면 곁 글 없음). 칸·묶음 목록은 @3 응답이 정본(AP1W Q1 (가)). */
  modelNote?: string;
  /** [이 버전 적용] 줄 아래 적용 안내 한 줄(모듈이 선언 — 없으면 줄 0, 밴드 RPW12). 글은 모듈 문구 표의 것. */
  applyNote?: string;
  /** 모듈 초안 슬롯(없으면 모듈 몫을 고치지 않는다 — 그린워싱 줄은 대상 단어, AS3b). */
  draft?: ModuleDraftSlot;
  /** 처리 흐름 띠(있으면 껍데기가 셋째 열을 그리지 않고 프롬프트 상세 위에 이것을 그린다, AS3b ②). */
  flow?: (p: FlowProps) => ReactNode;
  /** 처음 펼침·판 바꿈 때 고를 칸(모듈이 보이는 차례가 서버 차례와 다를 때 — 없으면 묶음 0 칸 0, 밴드 TRA2). */
  firstSlot?: (groups: FlowProps['groups']) => SlotAt;
  /** 프롬프트 상세 첫 줄 라벨 칸 글(없으면 공통 「단계」, 밴드 TRA2). */
  slotLabel?: string;
  /** 칸 KEY 를 소문자 그대로(없으면 대문자, 밴드 TRA2). */
  lowerKey?: boolean;
  /**
   * 글 칸 아래 안내 한 줄(묶음 key, 칸 key → 글 — null 이면 줄 0, 없으면 모든 칸 0. 밴드 DVA2 K1 — 데이터 검증 입력 글의 자리 안내).
   * 글은 모듈 문구 표의 것(껍데기·부품 안 한국어 0).
   */
  promptNote?: (group: string, prompt: string) => string | null;
  /**
   * 출력절 안내 글(묶음 key, 칸 key → 글, 밴드 DVA2 K2). 차례: ① 칸 outputSection null → 안내 0(TRA2 D4 — 숨김은 이것 하나뿐)
   * ② 모듈 글 → 그 글 ③ null 이거나 없으면 공통 글(숨김 아님).
   */
  outputNote?: (group: string, prompt: string) => string | null;
  /**
   * 모델 칸 key → 참이면 그 칸의 temperature 줄 0(라벨·값·「–」 다 — 밴드 IRA2 K3, 중대성평가 분석 모델 sid:MARC-ENT-468).
   * 없거나 거짓 = 지금 그대로(받지 않는 경로는 「–」 꺼진 칸). 초안·본문·셈은 바뀌지 않는다(숨긴 칸은 읽은 값 그대로 싣는다).
   */
  hideTemperature?: (slot: string) => boolean;
}

/** 처음 고를 줄의 열쇠: 판 번호(search version)가 맞는 줄 → 가장 새 「초안」 → 적용 중 → 기본 판. */
export function firstPick(
  rows: readonly VersionRow[],
  initial: string | undefined,
): string {
  return (
    rows.find((row) => initial !== undefined && row.number === initial)?.key ??
    rows.find((row) => row.status === 'testing')?.key ??
    rows.find((row) => row.status === 'applied')?.key ??
    DEFAULT_VERSION_KEY
  );
}

/** 프롬프트 칸 자리(묶음 i, 칸 j) → 서버 label(모르는 자리는 null — 저장 거절 경로 prompts.steps.<i>.prompts.<j> 풀이). */
export const promptLabel =
  (pm: PromptModel) =>
  (group: number, prompt: number): string | null =>
    pm.promptGroups[group]?.prompts[prompt]?.label ?? null;

/** 판 열의 이름: 「v3 · 이름」, 이름 없는 옛 판은 「v3」, 기본 판은 이름(서버 default.title). */
export function versionLabel(row: VersionRow): string {
  if (row.kind === 'default') return row.title ?? row.number;
  return row.title === null ? row.number : `${row.number} · ${row.title}`;
}

/** 글 안에서 부르는 판 이름: 저장 판은 번호, 기본 판은 이름. */
export function versionName(row: VersionRow): string {
  return row.kind === 'default' ? (row.title ?? row.number) : row.number;
}
