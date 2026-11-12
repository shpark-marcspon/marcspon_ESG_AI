// 새 평가 폼 → materiality.input@1(밴드 IRW2 ② — 발주서 §1-3 「폼 → input@1」, 부록 A3 정본).
// 열쇠 차례·이름은 계약 그대로(contracts/shapes.py:95-118), schemaVersion 이 첫 열쇠. 글은 trim() 만. 0행 가치사슬 → null.
// dateRange = `<시작>~오늘까지`(공백 0 — 서버 wire.py DATE_RANGE). 서버 값 글자는 model/wire.ts — 이 파일에 한국어 0.
// 크기: options({input})를 파이썬 json.dumps(…, ensure_ascii=False)의 기본 구분자(", "·": ")로 적은 UTF-8 바이트(서버
//   apps/api-py/esgapi/runs/service/actions/runs.py:256 `_options_too_large`)가 262,144 를 넘으면 보내지 않는다(A6-⑦).
//   이 입력은 글·참거짓·null·목록·객체뿐이라 글은 JSON.stringify 와 같은 escape(바이트 수 같음)로 잰다.
import type { MaterialityInput, Sector } from './result.ts';
import { filledRows } from './valueChain.ts';
import type { ValueChainRow } from './valueChain.ts';
import { INPUT_SHAPE, UNTIL_TODAY } from './wire.ts';

/** 실행 옵션 UTF-8 바이트 상한(서버 materiality 흐름의 상한). */
export const OPTIONS_MAX_OCTETS = 262_144;
/** 산업 기준 셋(화면·입력 차례). */
export const STANDARDS = ['SASB', 'GICS', 'KSIC'] as const;
export type Standard = (typeof STANDARDS)[number];

export interface IndustryDraft {
  name: string;
  description: string;
}
export interface SubtopicDraft {
  key: number;
  name: string;
  description: string;
}
export interface TopicDraft {
  key: number;
  topic: string;
  description: string;
  subtopics: SubtopicDraft[];
}

/** 화면이 쥔 폼(넣은 값 그대로 — 고치지 않는다). */
export interface RunDraft {
  company: string;
  industries: Record<Standard, IndustryDraft>;
  valueChain: ValueChainRow[];
  topics: TopicDraft[];
  geoScope: string;
  userLocation: string;
  mainLanguage: string;
  /** YYYY-MM-DD. */
  startDate: string;
  sector: Sector;
}

const blank = (text: string) => text.trim() === '';

/** 두 칸 다 빈 서브토픽 줄은 뺀다(부록 A4). */
export const filledSubtopics = (topic: TopicDraft) =>
  topic.subtopics.filter((sub) => !(blank(sub.name) && blank(sub.description)));

/** 폼 → input@1(검사는 model/draft.ts — 이 함수는 짓기만). */
export function buildInput(draft: RunDraft): MaterialityInput {
  // Object.fromEntries — 토픽 이름이 「__proto__」여도 제 칸이 된다(대입은 원형을 바꿔 칸이 빠진다).
  const subtopicsByTopic: Record<
    string,
    { name: string; description: string }[]
  > = Object.fromEntries(
    draft.topics.map((topic) => [
      topic.topic.trim(),
      filledSubtopics(topic).map((sub) => ({
        name: sub.name.trim(),
        description: sub.description.trim(),
      })),
    ]),
  );
  return {
    schemaVersion: INPUT_SHAPE,
    company: { name: draft.company.trim() },
    industries: STANDARDS.filter(
      (standard) => !blank(draft.industries[standard].name),
    ).map((standard) => ({
      standard,
      industryName: draft.industries[standard].name.trim(),
      description: draft.industries[standard].description.trim(),
    })),
    topics: draft.topics.map((topic) => ({
      topic: topic.topic.trim(),
      description: topic.description.trim(),
    })),
    geoScope: draft.geoScope.trim(),
    userLocation: draft.userLocation,
    mainLanguage: draft.mainLanguage,
    dateRange: `${draft.startDate.trim()}~${UNTIL_TODAY}`,
    sector: draft.sector,
    // 화면에 토글이 없다(IRW15 ③, MARC-ENT-668) — 계약의 필수 bool 은 늘 끔.
    latestEventMode: false,
    subtopicsByTopic,
    valueChain: valueChainInput(filledRows(draft.valueChain)),
  };
}

/** 가치사슬 행 → input@1 valueChain(다섯 칸 다 빈 행은 이미 뺌 — 남은 행 0 이면 null, IRW3 Q2). */
function valueChainInput(rows: readonly ValueChainRow[]) {
  return rows.length === 0 ?
      null
    : rows.map((row) => ({
        business_unit: row.business_unit.trim(),
        business_unit_description: row.business_unit_description.trim(),
        value_chain_stage: row.value_chain_stage,
        stakeholder: row.stakeholder.trim(),
        business_activity: row.business_activity.trim(),
      }));
}

/** POST /runs 의 options(열쇠 input 하나 — options_shapes.py). */
export const buildOptions = (input: MaterialityInput) => ({ input });

/** 파이썬 json.dumps(value, ensure_ascii=False) 꼴의 글(글·참거짓·null·목록·객체). */
export function pyJson(value: unknown): string {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(pyJson).join(', ')}]`;
  if (typeof value === 'object')
    return `{${Object.entries(value)
      .map(([key, each]) => `${JSON.stringify(key)}: ${pyJson(each)}`)
      .join(', ')}}`;
  throw new TypeError(`pyJson: ${typeof value}`);
}

/** options 의 서버 셈 바이트. */
export const optionsOctets = (options: unknown) =>
  new TextEncoder().encode(pyJson(options)).length;

/** 서버 상한을 넘는가. */
export const optionsTooLarge = (options: unknown) =>
  optionsOctets(options) > OPTIONS_MAX_OCTETS;
