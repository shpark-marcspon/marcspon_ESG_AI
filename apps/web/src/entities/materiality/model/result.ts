// 중대성평가 결과의 화면 꼴과 결과 표 줄(밴드 IRW1 ① — 발주서 §2-1). 순수 함수와 타입 — React·DOM·통신을 모른다.
// 화면 꼴은 materiality.result@2(apps/api-py/esgapi/materiality/contracts/shapes.py:392-655)를 계약 거울(api/contract/result.ts)이
//   줄인 것이다: 서버 message(failure·warnings·not_run)·모델 원문(raw·parsed)·설정(모델 이름·프롬프트 id)은 버린다.
//   가치사슬 활동(impact·financial valueChainActivities)과 pathway i 는 둔다 — 2-1·2-2 「가치사슬 활동」 열(밴드 IRW10, sid:MARC-ENT-558).
// 결과 표 줄은 최종 엑셀 규칙을 옮겨 적었다(apps/api-py/esgapi/materiality/outputs/final_xlsx.py — 가져오지 않는다):
//   서브토픽 차례 = part2 done 의 토픽 × 서브토픽(:80-86) · 2-1 줄 = impact done 의 rows(:186-200) · 2-2 줄 = pathway done 의 rows
//   (:202-221) · 컨텍스트 요약 = summary 를 규제 → 컨트로버시 차례로 셋까지, null 뺌(:131-135) · 1-1 칸 = merged_items(:97-117 —
//   2-1 rows 와 **재무(financial) rows** 의 context, url 이 같으면 처음 것 하나에 양쪽 라벨, :138-150).
import {
  FINANCIAL_OPPORTUNITY,
  FINANCIAL_RISK,
  IMPACT_NEGATIVE,
  IMPACT_POSITIVE,
  RISK_TYPE_PREFIX,
} from './wire.ts';

/** 결과 엑셀(apps/api-py/esgapi/materiality/outputs/final_xlsx.py:33 FILENAME). */
export const REPORT_FILE_NAME = 'materiality-final-report.xlsx';
/** 1부 리서치 엑셀(apps/api-py/esgapi/materiality/outputs/xlsx.py FILENAME — 둘째 단추, sid:MARC-ENT-449). */
export const RESEARCH_FILE_NAME = 'materiality-websearch.xlsx';

export type RunStatus = 'queued' | 'processing' | 'done' | 'failed';
export type StepStatus = 'pending' | 'running' | 'done' | 'failed';
export type Sector = 'financial' | 'non_financial';

/** 단계 하나. done·total = 단계 안 진행(토픽·서브토픽 자리 수, IRW6 — 둘 다 있을 때만 값, 아니면 둘 다 null). */
export interface RunStep {
  step: string;
  status: StepStatus;
  done: number | null;
  total: number | null;
}

/** 실행 하나(GET /runs/{id} 를 줄인 것). input 은 input@1 거울을 지났을 때만(못 지나면 null — 화면은 「–」). */
export interface MaterialityRun {
  runId: string;
  status: RunStatus;
  steps: RunStep[];
  failedStep: string | null;
  files: string[];
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  input: MaterialityInput | null;
}

/** materiality.input@1(shapes.py:94-118). 화면이 머리에 쓰는 칸만 이름으로 읽는다(나머지는 거울이 꼴만 본다). */
export interface MaterialityInput {
  schemaVersion: 'materiality.input@1';
  company: { name: string };
  industries: { standard: string; industryName: string; description: string }[];
  topics: { topic: string; description: string }[];
  geoScope: string;
  userLocation: string;
  mainLanguage: string;
  dateRange: string;
  sector: Sector;
  latestEventMode: boolean;
  subtopicsByTopic: Record<
    string,
    { name: string; description: string }[]
  > | null;
  valueChain:
    | {
        business_unit: string;
        business_unit_description: string;
        value_chain_stage: string;
        stakeholder: string;
        business_activity: string;
      }[]
    | null;
}

export type Cell = string | null;
/** 맥락의 쪽(규제·컨트로버시). */
export type Side = 'regulations' | 'controversies';
export const SIDES: readonly Side[] = ['regulations', 'controversies'];
export interface ContextItem {
  title: Cell;
  summary: Cell;
  url: Cell;
}
export interface Context {
  regulations: ContextItem[];
  controversies: ContextItem[];
}
export interface ImpactRow {
  impactDefinition: Cell;
  impactType: Cell;
  valueChainActivities: string[];
  context: Context;
}
export interface FinancialRow {
  impactDefinition: Cell;
  impactType: Cell;
  riskType: Cell;
  valueChainActivities: string[];
  context: Context;
}
/** i = 재무 rows 차례(1부터 — shapes.py:489-494 「i 로 재무 rows 에서 잇는다」). null 이면 잇지 않음. */
export interface PathwayRow {
  i: number | null;
  impactDefinition: Cell;
  impactDriver: Cell;
  businessImpact: Cell;
  financialImpact: Cell;
  impactType: Cell;
  riskType: Cell;
  context: Context;
}
/** 2부 호출 하나의 갈래(실패 까닭·원문은 버린다). */
export type Outcome<Row> =
  | { status: 'done'; rows: Row[] }
  | { status: 'failed' }
  | { status: 'not_run' };

export interface SubtopicResult {
  name: string;
  autofilled: boolean;
  impact: Outcome<ImpactRow>;
  financial: Outcome<FinancialRow>;
  pathway: Outcome<PathwayRow>;
}
export interface Part2Topic {
  topic: string;
  subtopics: SubtopicResult[];
}
export type ResearchStatus = 'done' | 'failed' | 'not_run';
/** 1부 토픽 하나 — 규제·컨트로버시 조사의 갈래만(항목은 1-1 이 2부 context 에서 짓는다 — 발주서 Q2 (가)). */
export interface Part1Topic {
  topic: string;
  regulation: ResearchStatus;
  controversy: ResearchStatus;
}
/** 경고 한 줄(서버 message 는 버린다). */
export interface Warning {
  code: string;
  topic: string | null;
}

export interface MaterialityResult {
  companyName: string;
  scope: { topicCount: number; sector: Sector; dateRange: string };
  part1: Part1Topic[];
  part2: { status: 'not_run' } | { status: 'done'; topics: Part2Topic[] };
  warnings: Warning[];
}

/** 서브토픽 하나의 자리(토픽 › 서브토픽). */
export interface SubtopicRef {
  topic: string;
  subtopic: string;
}

/** 서브토픽 차례(final_xlsx._subtopics — part2 done 의 토픽 × 서브토픽). part2 not_run → 0. */
export function subtopicsOf(
  result: MaterialityResult,
): { topic: string; sub: SubtopicResult }[] {
  if (result.part2.status !== 'done') return [];
  return result.part2.topics.flatMap((topic) =>
    topic.subtopics.map((sub) => ({ topic: topic.topic, sub })),
  );
}

export const rowsOf = <Row>(outcome: Outcome<Row>): Row[] =>
  outcome.status === 'done' ? outcome.rows : [];

/** 서브토픽 차례에 자리(토픽·서브토픽 차례 — 0부터, 결과 본문 안 자리)를 붙인 것(밴드 IRW11 — 칸 주소 짓기). */
function placedSubtopics(
  result: MaterialityResult,
): { topic: string; sub: SubtopicResult; t: number; s: number }[] {
  if (result.part2.status !== 'done') return [];
  return result.part2.topics.flatMap((topic, t) =>
    topic.subtopics.map((sub, s) => ({ topic: topic.topic, sub, t, s })),
  );
}

/** 줄 하나의 결과 본문 안 자리(0부터 — 토픽·서브토픽·그 갈래 rows 차례, 밴드 IRW11). */
export interface RowAt {
  topic: number;
  subtopic: number;
  row: number;
}
/** 컨텍스트 요약 하나가 온 맥락 항목(쪽·그 쪽 안 차례, 밴드 IRW11). */
export interface SummaryAt {
  side: Side;
  k: number;
}

/** 컨텍스트 요약 내용(final_xlsx.summaries): summary 를 규제 → 컨트로버시 차례로 셋까지(null 뺌). */
export const SUMMARY_LIMIT = 3;
export function summariesOf(context: Context): string[] {
  return [...context.regulations, ...context.controversies]
    .map((item) => item.summary)
    .filter((summary): summary is string => summary !== null)
    .slice(0, SUMMARY_LIMIT);
}
/** summariesOf 와 같은 차례·같은 길이의 자리(어느 쪽 몇째 항목의 summary 인가 — 밴드 IRW11). */
export function summaryPositions(context: Context): SummaryAt[] {
  return SIDES.flatMap((side) =>
    context[side].map((item, k) => ({ side, k, summary: item.summary })),
  )
    .filter(({ summary }) => summary !== null)
    .slice(0, SUMMARY_LIMIT)
    .map(({ side, k }) => ({ side, k }));
}

/** 「찾은 글 없이 정함」(판 IR-04a): 그 토픽의 1부 규제·컨트로버시가 둘 다 done 이 아니다(1부에 없는 토픽도). */
export function researchMissing(
  result: MaterialityResult,
  topic: string,
): boolean {
  const found = result.part1.find((t) => t.topic === topic);
  return (
    found === undefined ||
    (found.regulation !== 'done' && found.controversy !== 'done')
  );
}

export type ImpactTone = 'positive' | 'negative' | 'other';
export const impactToneOf = (type: Cell): ImpactTone =>
  type === IMPACT_POSITIVE ? 'positive'
  : type === IMPACT_NEGATIVE ? 'negative'
  : 'other';

export type FinancialKind = 'risk' | 'opportunity' | 'other';
export const financialKindOf = (type: Cell): FinancialKind =>
  type === FINANCIAL_RISK ? 'risk'
  : type === FINANCIAL_OPPORTUNITY ? 'opportunity'
  : 'other';

/** 리스크 종류 보기: 「리스크-」로 시작하면 떼고, null·기회 → null(화면 회색 「–」). 그 밖은 글자 그대로. */
export function riskTypeView(kind: Cell, riskType: Cell): string | null {
  if (riskType === null || financialKindOf(kind) === 'opportunity') return null;
  return riskType.startsWith(RISK_TYPE_PREFIX) ?
      riskType.slice(RISK_TYPE_PREFIX.length)
    : riskType;
}

/** 2-1 표 한 줄. no = 거르기 전 시트 순번(엑셀 D 열). */
export interface ImpactLine {
  no: number;
  topic: string;
  subtopic: string;
  definition: Cell;
  type: Cell;
  tone: ImpactTone;
  summaries: string[];
  /** 가치사슬 활동(그 영향 줄의 valueChainActivities 그대로 — 빈 목록이면 화면 「–」). */
  activities: string[];
  researchMissing: boolean;
  /** 결과 본문 안 자리(impact rows — 밴드 IRW11). */
  at: RowAt;
  /** summaries 와 같은 길이 — 요약마다 그 맥락 항목의 자리. */
  summaryAt: SummaryAt[];
}
export function impactLines(result: MaterialityResult): ImpactLine[] {
  let no = 0;
  return placedSubtopics(result).flatMap(({ topic, sub, t, s }) =>
    rowsOf(sub.impact).map((row, r) => ({
      no: ++no,
      topic,
      subtopic: sub.name,
      definition: row.impactDefinition,
      type: row.impactType,
      tone: impactToneOf(row.impactType),
      summaries: summariesOf(row.context),
      activities: [...row.valueChainActivities],
      researchMissing: researchMissing(result, topic),
      at: { topic: t, subtopic: s, row: r },
      summaryAt: summaryPositions(row.context),
    })),
  );
}

/** 2-2 줄의 가치사슬 활동: pathway 줄엔 칸이 없어 i(1부터)로 같은 서브토픽의 재무 rows[i-1] 에서 잇는다.
 *  i 가 null·범위 밖이거나 재무가 done 이 아니면 빈 목록. */
export function pathwayActivities(
  sub: SubtopicResult,
  i: number | null,
): string[] {
  if (i === null) return [];
  const row = rowsOf(sub.financial)[i - 1];
  return i >= 1 && row !== undefined ? [...row.valueChainActivities] : [];
}

/** pathway 줄의 i(1부터) → 같은 서브토픽 재무 rows 의 차례(0부터). null·범위 밖·재무 done 아님이면 null
 *  (서버 outputs/edits.py _fin_of 와 같은 규칙 — 밴드 IRW11). */
export function finOf(sub: SubtopicResult, i: number | null): number | null {
  const rows = rowsOf(sub.financial);
  return i !== null && Number.isInteger(i) && i >= 1 && i <= rows.length ?
      i - 1
    : null;
}

/** 2-2 표 한 줄(Pathway row — final_xlsx :202-221). */
export interface PathwayLine {
  no: number;
  topic: string;
  subtopic: string;
  definition: Cell;
  type: Cell;
  kind: FinancialKind;
  riskType: string | null;
  driver: Cell;
  business: Cell;
  financial: Cell;
  summaries: string[];
  /** 가치사슬 활동(pathwayActivities — 재무 rows[i-1]). */
  activities: string[];
  researchMissing: boolean;
  /** 결과 본문 안 자리(pathway rows — 밴드 IRW11). */
  at: RowAt;
  /** summaries 와 같은 길이 — 요약마다 그 pathway 맥락 항목의 자리. */
  summaryAt: SummaryAt[];
  /** i 가 잇는 재무 rows 차례(finOf — 못 이으면 null: 그 요약은 고칠 수 없다). */
  fin: number | null;
}
export function pathwayLines(result: MaterialityResult): PathwayLine[] {
  let no = 0;
  return placedSubtopics(result).flatMap(({ topic, sub, t, s }) =>
    rowsOf(sub.pathway).map((row, r) => ({
      no: ++no,
      topic,
      subtopic: sub.name,
      definition: row.impactDefinition,
      type: row.impactType,
      kind: financialKindOf(row.impactType),
      riskType: riskTypeView(row.impactType, row.riskType),
      driver: row.impactDriver,
      business: row.businessImpact,
      financial: row.financialImpact,
      summaries: summariesOf(row.context),
      activities: pathwayActivities(sub, row.i),
      researchMissing: researchMissing(result, topic),
      at: { topic: t, subtopic: s, row: r },
      summaryAt: summaryPositions(row.context),
      fin: finOf(sub, row.i),
    })),
  );
}

/** 2-1 을 정하지 못한 서브토픽: impact 가 done 이 아니다. */
export const impactUndecided = (sub: SubtopicResult) =>
  sub.impact.status !== 'done';
/**
 * 2-2 를 정하지 못한 서브토픽: financial 이 done 이 아니거나 pathway 가 failed.
 * 재무 done·rows 0 의 pathway not_run 은 정한 것이다(영향 없음 — shapes.py:558-561).
 */
export const pathwayUndecided = (sub: SubtopicResult) =>
  sub.financial.status !== 'done' || sub.pathway.status === 'failed';

const refsOf = (
  result: MaterialityResult,
  test: (sub: SubtopicResult) => boolean,
): SubtopicRef[] =>
  subtopicsOf(result)
    .filter(({ sub }) => test(sub))
    .map(({ topic, sub }) => ({ topic, subtopic: sub.name }));

export const undecidedImpact = (result: MaterialityResult) =>
  refsOf(result, impactUndecided);
export const undecidedPathway = (result: MaterialityResult) =>
  refsOf(result, pathwayUndecided);
/** 2-1·2-2 어느 쪽이든 정하지 못한 서브토픽(겹침 하나 — m). */
export const undecidedSubtopics = (result: MaterialityResult) =>
  refsOf(result, (sub) => impactUndecided(sub) || pathwayUndecided(sub));
/** {전체} = part2 서브토픽 전체(지어 넣은 것 포함). */
export const subtopicTotal = (result: MaterialityResult) =>
  subtopicsOf(result).length;

/** 1-1 항목 하나의 라벨: 환경·사회 · 재무 · 둘 다(url 이 같아 합침). */
export type ItemLabel = 'social' | 'financial' | 'both';
/** 맥락 항목 하나의 결과 본문 안 자리(토픽 안 — 서브토픽·갈래·줄·쪽·쪽 안 차례, 밴드 IRW11). */
export interface ItemAt {
  subtopic: number;
  phase: 'impact' | 'financial';
  row: number;
  side: Side;
  k: number;
}
export interface MergedItem {
  label: ItemLabel;
  title: Cell;
  url: Cell;
  /** 묶음 첫 자리(= 서버의 바른 주소 자리). 자리 목록을 주지 않고 부르면 null. */
  at: ItemAt | null;
}

/** merged_items: SOC → FIN 차례로 모으되 url(앞뒤 공백 뗌, null·빈 글은 안 합침)이 같은 항목은 처음 것 하나로. */
export function mergedItems(
  social: readonly ContextItem[],
  financial: readonly ContextItem[],
  positions?: { social: readonly ItemAt[]; financial: readonly ItemAt[] },
): MergedItem[] {
  const out: MergedItem[] = [];
  const byUrl = new Map<string, MergedItem>();
  const sides: [ItemLabel, readonly ContextItem[], readonly ItemAt[]][] = [
    ['social', social, positions?.social ?? []],
    ['financial', financial, positions?.financial ?? []],
  ];
  for (const [label, items, places] of sides)
    for (const [index, item] of items.entries()) {
      const url =
        item.url !== null && item.url.trim() !== '' ? item.url.trim() : null;
      const seen = url === null ? undefined : byUrl.get(url);
      if (seen !== undefined) {
        if (seen.label !== label) seen.label = 'both';
        continue;
      }
      const entry: MergedItem = {
        label,
        title: item.title,
        url: item.url,
        at: places[index] ?? null,
      };
      out.push(entry);
      if (url !== null) byUrl.set(url, entry);
    }
  return out;
}

/** 1-1 칸 하나: 그 쪽 1부 조사가 done 이 아니면 researched false(화면 「이 토픽은 리서치를 하지 못했어요」). */
export interface ShortlistCell {
  researched: boolean;
  items: MergedItem[];
}
export interface ShortlistLine {
  no: number;
  topic: string;
  regulation: ShortlistCell;
  controversy: ShortlistCell;
}

/** 1-1 줄(final_xlsx.shortlist_rows — 2부 토픽 차례, 2-1 rows 와 재무 rows 의 context). part2 not_run → 0. */
export function shortlistLines(result: MaterialityResult): ShortlistLine[] {
  if (result.part2.status !== 'done') return [];
  return result.part2.topics.map((topic, index) => {
    const placed = (phase: 'impact' | 'financial') =>
      topic.subtopics.flatMap((sub, s) =>
        rowsOf<ImpactRow | FinancialRow>(sub[phase]).map((row, r) => ({
          row,
          s,
          r,
        })),
      );
    const social = placed('impact');
    const financial = placed('financial');
    const part1 = result.part1.find((t) => t.topic === topic.topic);
    const cell = (
      side: Side,
      status: ResearchStatus | undefined,
    ): ShortlistCell => {
      const of = (
        phase: 'impact' | 'financial',
        rows: { row: ImpactRow | FinancialRow; s: number; r: number }[],
      ) =>
        rows.flatMap(({ row, s, r }) =>
          row.context[side].map((item, k) => ({
            item,
            at: { subtopic: s, phase, row: r, side, k },
          })),
        );
      const socialItems = of('impact', social);
      const financialItems = of('financial', financial);
      return {
        researched: status === 'done',
        items: mergedItems(
          socialItems.map(({ item }) => item),
          financialItems.map(({ item }) => item),
          {
            social: socialItems.map(({ at }) => at),
            financial: financialItems.map(({ at }) => at),
          },
        ),
      };
    };
    return {
      no: index + 1,
      topic: topic.topic,
      regulation: cell('regulations', part1?.regulation),
      controversy: cell('controversies', part1?.controversy),
    };
  });
}

/** 숫자 카드 다섯. part2 not_run 이면 토픽 수만, 나머지 넷 null(화면 「–」). 그 밖 유형 값은 합에만. */
export interface ResultCards {
  topics: number;
  subtopics: number | null;
  regulation: number | null;
  controversy: number | null;
  impact: { total: number; positive: number; negative: number } | null;
  pathway: { total: number; risk: number; opportunity: number } | null;
}
export function resultCards(result: MaterialityResult): ResultCards {
  const topics = result.part1.length;
  if (result.part2.status !== 'done')
    return {
      topics,
      subtopics: null,
      regulation: null,
      controversy: null,
      impact: null,
      pathway: null,
    };
  const shortlist = shortlistLines(result);
  const impacts = impactLines(result);
  const pathways = pathwayLines(result);
  return {
    topics,
    subtopics: subtopicTotal(result),
    regulation: shortlist.reduce(
      (n, line) => n + line.regulation.items.length,
      0,
    ),
    controversy: shortlist.reduce(
      (n, line) => n + line.controversy.items.length,
      0,
    ),
    impact: {
      total: impacts.length,
      positive: impacts.filter((line) => line.tone === 'positive').length,
      negative: impacts.filter((line) => line.tone === 'negative').length,
    },
    pathway: {
      total: pathways.length,
      risk: pathways.filter((line) => line.kind === 'risk').length,
      opportunity: pathways.filter((line) => line.kind === 'opportunity')
        .length,
    },
  };
}
