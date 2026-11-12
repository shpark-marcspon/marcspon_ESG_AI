// 그린워싱 AI 설정 판의 꼴과 순수 함수(밴드 AD2R ①). 서버 /ai-settings/greenwash(G2c2)의 계약 꼴을 import type 으로만 받는다.
//   - 판 열 줄(versionRows): 저장 판(서버 차례 — 새 것 먼저) + 맨 아래 기본 판 한 줄. 기본 판은 서버 목록의 행이 아니다(default + applied.kind).
//   - 처음 고름(firstPick): 이름이 맞는 판 → 가장 새 「시험 중」 → 적용 중(저장 판 또는 기본).
//   - 기준 글 검사(criterionTextProblem): 서버 받기(criteria_e0.py `_accept_text`·`_one_line`)와 같은 차례 — trim 뒤 1~300 코드 포인트, 그다음 한 줄.
//   - 저장 본문(saveBody): 서버 판은 바뀌지 않는다 — 고친 것은 늘 새 판(POST). 칸을 이름으로 골라 담아 모르는 칸이 실리지 않는다.
//     AD2W ③: 본문 다섯 칸(title·criteria·memo·modelSettings·prompts)을 통째로 받는다(AD-02 「한 번 저장」 — sid:MARC-ENT-387).
//     G2d: 여섯째 칸 terms(대상 단어 {text, enabled} 목록 — null 은 코드 기본 목록, sid:MARC-ENT-394). 받은 그대로 싣는다(null 은 null).
//   - 나가는 id(idOut): 웹 id 는 글자로 다루고, 경로·본문에 실을 때 `^[1-9][0-9]*$` 만 숫자로(아니면 요청 0 — 서버는 숫자 아닌 id 에 422).
import type { Schemas } from '../../../shared/api/index.ts';

export type SettingList = Schemas['GreenwashAiSettingList'];
export type SettingSummary = Schemas['GreenwashAiSettingSummary'];
export type Setting = Schemas['GreenwashAiSetting'];
export type SettingDefault = Schemas['GreenwashAiSettingDefault'];
export type SettingCriteria = Schemas['GreenwashCriteria'];
export type SettingRow = Schemas['GreenwashCriterionRow'];
/** 판의 대상 단어 하나(G2d — 켠 낱말만 판 차례대로 빈도를 센다). */
export type SettingTerm = Schemas['GreenwashTerm'];
export type SettingStatus = SettingSummary['status'];
/** 저장 본문. 서버는 criteria 를 선택으로 받지만(빠지면 기본 기준표) 웹은 늘 기준표를 싣는다 — 좁혀 둔다(AS3a-2 B1). */
export type SettingCreate = Omit<
  Schemas['GreenwashAiSettingCreate'],
  'criteria'
> & {
  criteria: SettingCriteria;
};

/** 저장 판의 상태 셋(계약 enum). */
export const SETTING_STATUSES = [
  'testing',
  'applied',
  'past',
] as const satisfies readonly SettingStatus[];

/** 기준표 줄 id 15개(계약 enum 의 차례 — rows 는 늘 이 차례 그대로). */
export const CRITERION_IDS = [
  'keyword-ghg',
  'keyword-exclusion',
  'evidence-quantity',
  'evidence-baseline',
  'evidence-boundary',
  'evidence-offset',
  'high-1',
  'high-2',
  'high-3',
  'high-4',
  'mid-1',
  'exception-1',
  'exception-2',
  'exception-3',
  'exception-4',
] as const satisfies readonly SettingRow['id'][];

/** 기준 글의 최대 코드 포인트 수(서버 TEXT_CHARS). */
export const CRITERION_TEXT_MAX = 300;

/** 판 열에서 기본 판 줄의 열쇠(저장 판 열쇠는 String(id) — 숫자 글자라 겹치지 않는다). */
export const DEFAULT_KEY = 'default';

/** 판 열 줄의 배지: 저장 판은 서버 상태, 기본 판은 적용 중이거나 「기본」. */
export type VersionBadge = SettingStatus | 'default';

export type VersionRow =
  | {
      kind: 'saved';
      key: string;
      name: string;
      badge: SettingStatus;
      summary: SettingSummary;
    }
  | {
      kind: 'default';
      key: typeof DEFAULT_KEY;
      name: string;
      badge: 'applied' | 'default';
    };

/** 판 열 줄: 저장 판(서버 차례 그대로) + 기본 판 한 줄(맨 아래). 기본 판 배지는 applied.kind 로 정한다. */
export function versionRows(list: SettingList): VersionRow[] {
  return [
    ...list.items.map((summary): VersionRow => ({
      kind: 'saved',
      key: String(summary.id),
      name: summary.name,
      badge: summary.status,
      summary,
    })),
    {
      kind: 'default',
      key: DEFAULT_KEY,
      name: list.default.name,
      badge: list.applied.kind === 'default' ? 'applied' : 'default',
    },
  ];
}

/** 처음 고를 줄의 열쇠: 이름(search version)이 맞는 줄 → 가장 새 시험 중 → 적용 중 → 기본 판. */
export function firstPick(
  rows: readonly VersionRow[],
  initial: string | undefined,
): string {
  return (
    rows.find((row) => initial !== undefined && row.name === initial)?.key ??
    rows.find((row) => row.badge === 'testing')?.key ??
    rows.find((row) => row.badge === 'applied')?.key ??
    DEFAULT_KEY
  );
}

/** 한 줄 검사에서 막는 글자: 제어·서식·짝 없는 서로게이트·사용자 정의·배정 안 됨·줄 나눔·문단 나눔(서버 INVISIBLE). 줄바꿈 글자는 모두 Cc·Zl·Zp 다. */
const INVISIBLE = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zl}\p{Zp}]/u;

/**
 * 기준 글이 서버 받기에 걸리는 까닭(없으면 null). trim 뒤 코드 포인트 수가 1~300 이 아니면 length, 그다음 보이지 않는 글자·줄바꿈이 있으면 multiline.
 * Unicode 판 차이(배정 안 됨 Cn)는 서버 400 이 마지막 그물이다.
 */
export function criterionTextProblem(
  text: string,
): null | 'length' | 'multiline' {
  const trimmed = text.trim();
  const length = [...trimmed].length;
  if (length < 1 || length > CRITERION_TEXT_MAX) return 'length';
  if (INVISIBLE.test(trimmed)) return 'multiline';
  return null;
}

/** 줄 하나를 계약 칸만 골라 새로 담는다(모르는 칸이 실리지 않게). */
const rowOut = (row: SettingRow): SettingRow => ({
  id: row.id,
  category: row.category,
  order: row.order,
  enabled: row.enabled,
  text: row.text,
  terms: row.terms === null ? null : [...row.terms],
  verdict: row.verdict,
  guideline:
    row.guideline === null ?
      null
    : { text: row.guideline.text, status: row.guideline.status },
});

/** 새 판 저장의 입력(밴드 AD2W ③ — 82 허락): 바탕 판의 기준표(머리 + 15줄) · 판 이름·메모 · 모델 설정 · 프롬프트(늘 넷 — 발주서 Q1) · 대상 단어(G2d — null = 코드 기본 목록). */
interface SaveInput {
  criteria: Pick<SettingCriteria, 'schemaVersion' | 'version'> & {
    rows: readonly SettingRow[];
  };
  title: string;
  memo: string;
  modelSettings: NonNullable<SettingCreate['modelSettings']>;
  prompts: NonNullable<SettingCreate['prompts']>;
  terms: readonly SettingTerm[] | null;
}

/** 새 판 저장 본문: 판 이름 + 바탕 판의 기준표 머리(schemaVersion·version) + 15줄 + 판 메모 + 모델 설정 + 프롬프트 + 대상 단어. 서버가 version 을 새 판 번호로 덮는다. */
export function saveBody({
  criteria,
  title,
  memo,
  modelSettings,
  prompts,
  terms,
}: SaveInput): SettingCreate {
  return {
    title,
    criteria: {
      schemaVersion: criteria.schemaVersion,
      version: criteria.version,
      rows: criteria.rows.map(rowOut),
    },
    memo,
    modelSettings: {
      steps: modelSettings.steps.map((step) => ({
        key: step.key,
        route: step.route,
        temperature: step.temperature,
        maxOutputTokens: step.maxOutputTokens,
        webSearch: step.webSearch,
      })),
    },
    prompts: {
      steps: prompts.steps.map((step) => ({
        key: step.key,
        prompts: step.prompts.map((one) => ({
          key: one.key,
          text: one.text,
          memo: one.memo,
        })),
      })),
    },
    terms:
      terms === null ? null : (
        terms.map((term) => ({ text: term.text, enabled: term.enabled }))
      ),
  };
}

/** 웹 id(글자) → 서버 id(양의 정수). 0 으로 시작하거나 숫자가 아니면 null(요청 0). */
export function idOut(id: string): number | null {
  if (!/^[1-9][0-9]*$/.test(id)) return null;
  const value = Number(id);
  return Number.isSafeInteger(value) ? value : null;
}
