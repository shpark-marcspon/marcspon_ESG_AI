// dataverify.result@2 와 실행(GET /runs/{id})의 화면 꼴(밴드 DV2a ①). 계약 거울(api/contract/)이 이 꼴로 맞춘다.
// 정본: apps/api-py/esgapi/dataverify/contracts/shapes.py · tests/data/flow-shapes/dataverify.result@2.schema.json,
//   실행은 apps/api-py/esgapi/runs/service/schemas/runs.py(RunOut). 서버 message·errorMessage 는 싣지 않는다(화면에 0).
// 수(value·diff·tolerance)는 repr(float) 의 글자 그대로다. 모델이 준 인자(item·year·args 등)는 JSON 값 그대로(unknown).
import type { Company, DataverifyInput } from './options.ts';
import type { InputSource } from './source.ts';

export type FailureKind =
  | 'unparsable'
  | 'budget_exceeded'
  | 'truncated'
  | 'refusal'
  | 'provider_error'
  | 'timeout'
  | 'tool_executor_raised'
  | 'schema_mismatch';

export const FAILURE_KINDS: readonly FailureKind[] = [
  'unparsable',
  'budget_exceeded',
  'truncated',
  'refusal',
  'provider_error',
  'timeout',
  'tool_executor_raised',
  'schema_mismatch',
];

/** 단계 실패의 까닭(message 는 거울이 버린다). */
export interface Failure {
  kind: FailureKind;
}

export type PlanStage =
  | { status: 'done'; partial: boolean; formulas: readonly string[] }
  | { status: 'failed'; failure: Failure }
  | { status: 'not_run' };

export type YearStatus = 'OK' | 'FAIL';
export type YearNote = 'non-numeric' | 'division by zero';

export interface YearResult {
  year: unknown;
  ok: boolean;
  status: YearStatus;
  diff: string | null;
  note: YearNote | null;
  explanation: string;
}

export type CheckRule = 'sum' | 'sum_n' | 'ratio';

export type Check =
  | { kind: 'value'; seq: number; tool: string }
  | { kind: 'search'; seq: number; tool: string }
  | {
      kind: 'check';
      seq: number;
      tool: string;
      rule: CheckRule;
      items: {
        byName: Readonly<Record<string, unknown>> | null;
        raw: Readonly<Record<string, unknown>> | null;
      };
      tolerance: string | null;
      years: readonly YearResult[];
    }
  | { kind: 'error'; seq: number; tool: string };

export type ReviewStage =
  | {
      status: 'done';
      partial: boolean;
      report: string;
      checks: readonly Check[];
    }
  | { status: 'failed'; checks: readonly Check[]; failure: Failure }
  | { status: 'not_run'; checks: readonly Check[] };

export interface InsightRow {
  area: string;
  indicator: string;
  observation: string;
  risk: string;
  interpretation: string;
}

export interface WebSource {
  title: string | null;
  url: string;
}

export type RowsParsed = 'parsed' | 'unparsed' | 'none';

export type InsightStage =
  | {
      status: 'done';
      partial: boolean;
      report: string;
      rows: readonly InsightRow[];
      rowsParsed: RowsParsed;
      sources: readonly WebSource[];
    }
  | { status: 'failed'; failure: Failure; partialText: string | null }
  | { status: 'not_run' };

export interface Scope {
  themes: readonly string[];
  itemCount: number;
  keyItemCount: number;
  years: readonly string[];
}

export interface DataverifyResult {
  company: Company;
  scope: Scope;
  /** 검사 도구의 허용 오차(repr(float) 글자). */
  tolerance: string;
  plan: PlanStage;
  review: ReviewStage;
  insight: InsightStage;
  /** 경고 code 만(message 는 버린다). */
  warnings: readonly string[];
}

export type RunStatus = 'queued' | 'processing' | 'done' | 'failed';
export type StepStatus = 'pending' | 'running' | 'done' | 'failed';
/** 흐름 dataverify.colab@156 의 단계 다섯(colab_156.py:675-679). */
export const STEP_NAMES = [
  'load',
  'plan',
  'review',
  'insight',
  'report',
] as const;
export type StepName = (typeof STEP_NAMES)[number];

export interface RunStep {
  step: string;
  status: StepStatus;
}

/** 실행 하나(GET /runs/{id}). input 은 options.input 을 거울에 대 본 것(못 지나면 null). source 는 options.source(없는 옛 실행·꼴 밖이면 null — DV2b). */
export interface DataverifyRun {
  runId: string;
  status: RunStatus;
  steps: readonly RunStep[];
  failedStep: string | null;
  errorCode: string | null;
  files: readonly string[];
  createdAt: string;
  finishedAt: string | null;
  input: DataverifyInput | null;
  source: InputSource | null;
}

/** 결과 엑셀의 이름(dataverify/outputs/xlsx.py:27). */
export const REPORT_FILE_NAME = 'dataverify-report.xlsx';
