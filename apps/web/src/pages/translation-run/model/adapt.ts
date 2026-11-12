// 결과·요약 → 결과 화면 꼴(밴드 TRW1a ③, 시안 TR-04·04a). 순수 함수 — 글은 짓지 않고 열쇠와 수만 낸다(글은 ui 가 config 로).
//   이슈 유형(★J): 서버 issueType 은 엔진의 ALLOWED_ISSUE_TYPES 열(대문자) — IssueTypeKey 열에 하나씩. 열 밖 글자·HIGH/MEDIUM/LOW 밖 심각도는
//     줄을 버리고 dropped 로 센다(판에 「그 밖」 줄이 없다 — 지어내지 않음).
//   수치는 요약(digest)에서 — 요약이 없거나 끝나지 않은 파트는 null(「–」, 0 과 다르다).
import type {
  DigestVariant,
  IssueTypeKey,
  ResultVariant,
  Severity,
  TranslationDigest,
} from '../../../entities/translation/model/index.ts';
import type { QaIssue } from './issues.ts';

const ISSUE_TYPE: Readonly<Record<string, IssueTypeKey>> = {
  GLOSSARY_VIOLATION: 'glossary_violation',
  TERMINOLOGY_INCONSISTENCY: 'term_inconsistency',
  TAG_MODIFIED: 'structure_changed',
  OMISSION: 'omission',
  UNTRANSLATED: 'untranslated',
  NUMBER_UNIT_ERROR: 'number_unit',
  GRAMMAR: 'grammar',
  UNNATURAL: 'unnatural',
  TABLE_CONTENT: 'table_content',
  VISUAL_CONTENT: 'figure_caption',
};
const SEVERITY: Readonly<Record<string, Severity>> = {
  HIGH: 'high',
  MEDIUM: 'mid',
  LOW: 'low',
};

/** 심각도 차례(High → Mid → Low — 밴드 TRP2 TC27, 시안 TR-04). */
const SEVERITY_RANK: Readonly<Record<Severity, number>> = {
  high: 0,
  mid: 1,
  low: 2,
};

/** 문체 하나의 검수 이슈(심각도 차례, 같은 심각도 안은 쪽 차례 — 안정 정렬). 모르는 유형·심각도는 버리고 센다. */
export function issuesOf(variant: ResultVariant): {
  issues: QaIssue[];
  dropped: number;
} {
  const issues: QaIssue[] = [];
  let dropped = 0;
  for (const page of variant.pages)
    for (const issue of page.review.issues) {
      const type =
        Object.hasOwn(ISSUE_TYPE, issue.issueType) ?
          ISSUE_TYPE[issue.issueType]
        : undefined;
      const severity =
        Object.hasOwn(SEVERITY, issue.severity) ?
          SEVERITY[issue.severity]
        : undefined;
      if (type === undefined || severity === undefined) {
        dropped += 1;
        continue;
      }
      issues.push({
        page: page.pageNum,
        type,
        severity,
        span: issue.originalSpan,
        suggestion: issue.suggestion,
        reason: issue.reason,
      });
    }
  // 쪽 차례로 모은 뒤 심각도로 안정 정렬(Array.prototype.sort 는 안정) — 같은 심각도 안은 쪽 차례 그대로.
  issues.sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
  return { issues, dropped };
}

/** 검수가 멈췄을 때 검수한 쪽 구간(시작 쪽 ~ 멈춘 쪽 - 1 — 밴드 TRP2 TC26, 시안 TR-04a 「4~29쪽」). 멈추지 않았거나 첫 쪽에서 멈췄으면 null. */
export function reviewedRangeOf(
  start: number | null,
  stoppedAt: number | null,
): { from: number; to: number } | null {
  if (start === null || stoppedAt === null || stoppedAt <= start) return null;
  return { from: start, to: stoppedAt - 1 };
}

/** 용어집 미반영 줄. */
export const missesOf = (variant: ResultVariant) =>
  variant.glossaryCheck.map((miss) => ({
    page: miss.pageNum,
    ko: miss.termKo,
    en: miss.termEn,
    count: miss.sourceCount,
  }));

/** 확인할 쪽 한 줄(시안 TR-04a). 까닭은 열쇠 목록. */
export interface CheckRow {
  /** 「27」·「31~41」. */
  pages: string;
  translate: 'failed' | 'done';
  review:
    | { kind: 'reviewed' }
    | { kind: 'not_run' }
    | { kind: 'stopped_at'; page: number };
  reasons: (
    | { kind: 'call_failed' }
    | { kind: 'korean_left' }
    | { kind: 'not_reviewed_after'; page: number }
    | { kind: 'review_call_failed' }
    | { kind: 'earlier_stopped' }
  )[];
}

/** 번역·검수가 끝나지 않은 쪽(번역 실패 쪽, 검수가 멈춘 쪽, 그 뒤 검수하지 않은 쪽 — 이어진 것은 한 줄로). */
export function checkRowsOf(variant: ResultVariant): CheckRow[] {
  const failed = new Map(
    variant.fragments
      .filter((fragment) => fragment.status === 'error')
      .map((fragment) => [fragment.pageNum, fragment]),
  );
  const stopped = variant.pages.find(
    (page) => page.review.status === 'call_failed',
  );
  const rows: CheckRow[] = [];
  /** 이어서 검수하지 않은 쪽 구간(모으는 중). */
  const pending: { range: { from: number; to: number } | null } = {
    range: null,
  };
  const flush = () => {
    const run = pending.range;
    if (run === null) return;
    rows.push({
      pages: run.from === run.to ? `${run.from}` : `${run.from}~${run.to}`,
      translate: 'done',
      review: { kind: 'not_run' },
      reasons: [{ kind: 'earlier_stopped' }],
    });
    pending.range = null;
  };
  for (const page of variant.pages) {
    const fragment = failed.get(page.pageNum);
    const status = page.review.status;
    if (fragment) {
      flush();
      const review: CheckRow['review'] =
        status === 'call_failed' ? { kind: 'stopped_at', page: page.pageNum }
        : status === 'not_run' ? { kind: 'not_run' }
        : { kind: 'reviewed' };
      rows.push({
        pages: `${page.pageNum}`,
        translate: 'failed',
        review,
        reasons: [
          fragment.remainingKorean.length > 0 ?
            { kind: 'korean_left' }
          : { kind: 'call_failed' },
          ...(status === 'not_run' && stopped ?
            [{ kind: 'not_reviewed_after' as const, page: stopped.pageNum }]
          : []),
        ],
      });
    } else if (status === 'call_failed') {
      flush();
      rows.push({
        pages: `${page.pageNum}`,
        translate: 'done',
        review: { kind: 'stopped_at', page: page.pageNum },
        reasons: [{ kind: 'review_call_failed' }],
      });
    } else if (status === 'not_run') {
      const run = pending.range;
      if (run !== null && run.to === page.pageNum - 1) run.to = page.pageNum;
      else {
        flush();
        pending.range = { from: page.pageNum, to: page.pageNum };
      }
    }
  }
  flush();
  // 번역 실패 쪽을 먼저(시안 차례), 그 뒤 검수 줄.
  return [
    ...rows.filter((row) => row.translate === 'failed'),
    ...rows.filter((row) => row.translate === 'done'),
  ];
}

/** 단계 줄의 값(시안 TR-04a). */
export type StepValue =
  | { kind: 'done' }
  | { kind: 'failed_pages'; n: number }
  | { kind: 'stopped_at'; page: number }
  | { kind: 'not_run' }
  | { kind: 'bilingual_only' };
export function stepLineOf(
  digest: TranslationDigest,
  variant: DigestVariant,
): {
  translate: StepValue;
  glossary: StepValue;
  review: StepValue;
  autofix: StepValue;
  word: StepValue;
} {
  const files = variant.files;
  return {
    translate:
      digest.failedPages.length > 0 ?
        { kind: 'failed_pages', n: digest.failedPages.length }
      : { kind: 'done' },
    glossary: { kind: 'done' },
    review:
      variant.reviewStatus === 'reviewed' ? { kind: 'done' }
      : variant.reviewStoppedAt === null ? { kind: 'not_run' }
      : { kind: 'stopped_at', page: variant.reviewStoppedAt },
    autofix:
      variant.autofixStatus === 'done' ? { kind: 'done' } : { kind: 'not_run' },
    word:
      files.bilingual !== null && files.qa === null && files.autofix === null ?
        { kind: 'bilingual_only' }
      : { kind: 'done' },
  };
}

/** 파트 하나의 수치(요약 문체 하나에서 — 요약이 없으면 모두 null). */
export interface PartNumbers {
  pageCount: number | null;
  translated: number | null;
  failedPages: readonly number[] | null;
  issues: number | null;
  misses: number | null;
  /** 자동 수정한 쪽 — 자동 수정이 끝까지 돌지 않았으면 null(「돌리지 않음」). */
  fixed: number | null;
}
export function numbersOf(
  digest: TranslationDigest | null,
  variant: DigestVariant | undefined,
): PartNumbers {
  if (digest === null || digest.status !== 'done' || variant === undefined)
    return {
      pageCount: null,
      translated: null,
      failedPages: null,
      issues: null,
      misses: null,
      fixed: null,
    };
  return {
    pageCount: digest.pageCount,
    translated: digest.pageCount - digest.failedPages.length,
    failedPages: digest.failedPages,
    issues: variant.issueCount,
    misses: variant.glossaryMisses,
    fixed:
      variant.autofixStatus === 'done' ? variant.autofixChangedPages : null,
  };
}

/** 끝난 파트들의 합(하나라도 null 이면 그 칸은 null — 모름을 0 으로 삼키지 않는다). */
export function sumNumbers(parts: readonly PartNumbers[]): {
  pageCount: number | null;
  translated: number | null;
  untranslated: number | null;
  issues: number | null;
  misses: number | null;
  fixed: number | null;
} {
  const sum = (pick: (p: PartNumbers) => number | null) =>
    parts.reduce<number | null>((acc, part) => {
      const value = pick(part);
      return acc === null || value === null ? null : acc + value;
    }, 0);
  return {
    pageCount: sum((p) => p.pageCount),
    translated: sum((p) => p.translated),
    untranslated: sum((p) =>
      p.failedPages === null ? null : p.failedPages.length,
    ),
    issues: sum((p) => p.issues),
    misses: sum((p) => p.misses),
    fixed: sum((p) => p.fixed),
  };
}
