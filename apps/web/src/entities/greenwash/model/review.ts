// 검토의 셈과 본문 짓기(밴드 FW2 ①, 시안 GW-05·05a·05b, 메모 gw-a-05d). 순수 함수만.
//   - 잇기: 문장의 열쇠는 (실행, itemIndex). 결과 items 의 차례와 검토 marks 를 잇는다. 표시가 없으면 미검토.
//   - PUT 본문 [B3]: 서버 뜻(service/apis/greenwash.py GreenwashReviewUpdate)은 「marks 는 그 실행의 표시 전부를 갈아 넣는다,
//     state 는 confirmed 나 없음만 받는다」다. 그래서 본문은 늘 그 실행의 marks 전부(itemIndex 오름차순, 겹침 없음)이고
//     state 는 싣지 않는다. 표시가 있으면 서버가 pending → in_review 로 옮긴다(결함 D1: in_review 를 실으면 400).
//   - 확정 본문: 서버 꼴에 「미검토 → 채택」이 없다. 미검토를 모두 adopted 로 채운 marks 전부와 state: confirmed 를 한 본문으로.
//     무효 조건: 서버가 확정 때 미검토를 스스로 채택으로 바꾸면 이 채우기는 겹친다(해는 없다).
//   - 제외 사유 글 [R6]: 서버 excludeReason 은 자유 글이다. 저장 글 = 「사유 이름」 또는 「사유 이름: 설명」(낫표 없음).
//     기타는 설명이 있어야 한다. 서버에서 받은 글은 되읽어 가르지 않는다(그대로 보인다).
//     무효 조건: 검증 감독이 사유를 코드 칸으로 바꾸면 이 글 짓기는 사라진다.
// 고침(밴드 G1b-3 ③, review@2 — 시안 GW-05_r2·05c_r2):
//   - 보이는 값 = 고친 값 ?? AI 값(칸마다: edit?.<칸>?.value ?? item.<칸>). AI 원본은 결과 items 그대로(review@2 에 AI 사본 없음).
//     등급 탭·05a 의 등급도 보이는 등급이다. 「고침」= 그 칸이 값(null 이 아님).
//   - 고침 PUT 본문(editUpdate): marks 는 받은 그대로 + edits 는 그 실행의 고침 전부(평평한 값 — 서버가 edits 를 갈아 넣는다).
//     AI 와 같은 값을 보내도 된다(서버가 null 로 접는다 — 그래서 화면은 접지 않는다). 채택·제외·확정 본문은 edits 를 싣지 않는다
//     (생략 = 고침 그대로).
//   - 판정 사유 글 칸: 한 줄 = 한 항목, 앞의 「- 」는 뗀다, 빈 줄은 버린다(앞뒤 공백 지움은 서버도 한다).
// 근거 고치기·재판단(밴드 GRJ1 ③, review@3 — 결정 MARC-ENT-617, 시안 GW-05 r4·r5):
//   - 기준 판단(basisOf) = 문장의 재판단 줄 current(가장 늦게 끝난 재판단) ?? 첫 판단(결과 items[i]). nonrisk 면 등급 null
//     (「리스크 아님」 — 등급 탭 High·Mid·Low 에 걸리지 않고 「전체」에만, 덧붙임 4). 서버 review.py 의 basis 와 같은 뜻.
//   - 보이는 값(shownValues) = 사용자 고침 ?? 기준 판단 ?? 첫 판단. 고침은 GRV1 처럼 기준 판단과 견줘 접힌다(서버).
//   - [재판단] 켜짐(nothingToRejudge 의 반대) = 지운 칩이 있거나 더한 조각이 기준 판단에 보낸 것과 다름(서버 R4 —
//     review.nothing_to_rejudge 와 같은 규칙). 서버는 재판단이 끝나면 removed 를 [] 로 읽어 준다(웹은 받은 그대로).
//   - 근거 PUT 본문(evidenceUpdate): marks 그대로 + evidence 는 그 실행의 근거 고침 전부(갈아 넣기 — edits 는 싣지 않는다 =
//     고침 그대로). 지운 칩·더한 조각이 둘 다 빈 문장은 싣지 않는다.
import type {
  EvidenceAdded,
  GreenwashReview,
  Level,
  ResultItem,
  ReviewDecision,
  ReviewEdit,
  ReviewEditIn,
  ReviewEvidence,
  ReviewEvidenceIn,
  ReviewMark,
  ReviewRejudge,
  ReviewUpdate,
} from './result.ts';

/** 기준 판단 — 지금 AI 값(가장 늦게 끝난 재판단, 없으면 첫 판단). */
export interface Basis {
  /** 리스크 아님(재판단 outcome nonrisk)이면 null. */
  level: Level | null;
  nonrisk: boolean;
  riskTags: readonly string[];
  confirmedInEvidence: readonly string[];
  missingFields: readonly string[];
  reasonBullets: readonly string[];
  fixParagraph: string;
  evidencePages: readonly number[];
  /** 이 판단에 보낸 더한 조각(첫 판단이면 []). */
  added: readonly EvidenceAdded[];
  /** 재판단이면 그 실행 id·때·사람. 첫 판단이면 null. */
  rejudged: { runId: number; judgedAt: string; judgedBy: string } | null;
}

/** 문장 하나의 기준 판단(서버 review.py 기준 판단 고르기와 같은 뜻). */
export function basisOf(item: ResultItem, line: ReviewRejudge | null): Basis {
  const current = line?.current ?? null;
  if (current === null)
    return {
      level: item.level,
      nonrisk: false,
      riskTags: item.riskTags,
      confirmedInEvidence: item.confirmedInEvidence,
      missingFields: item.missingFields,
      reasonBullets: item.reasonBullets,
      fixParagraph: item.fixParagraph,
      evidencePages: item.evidencePages,
      added: [],
      rejudged: null,
    };
  const nonrisk = current.outcome === 'nonrisk';
  return {
    level: nonrisk ? null : current.level,
    nonrisk,
    riskTags: current.riskTags,
    confirmedInEvidence: current.confirmedInEvidence,
    missingFields: current.missingFields,
    reasonBullets: current.reasonBullets,
    fixParagraph: current.fixParagraph,
    evidencePages: current.evidencePages,
    added: current.added,
    rejudged: {
      runId: current.runId,
      judgedAt: current.judgedAt,
      judgedBy: current.judgedBy.name,
    },
  };
}

const samePieces = (a: readonly EvidenceAdded[], b: readonly EvidenceAdded[]) =>
  a.length === b.length &&
  a.every((piece, i) => piece.text === b[i]!.text && piece.page === b[i]!.page);

/** 다시 판단할 것이 없는가(서버 review.nothing_to_rejudge 와 같은 규칙 — 감독 R4). */
export function nothingToRejudge(
  removed: readonly number[],
  added: readonly EvidenceAdded[],
  basis: Pick<Basis, 'added'>,
): boolean {
  return removed.length === 0 && samePieces(added, basis.added);
}

/**
 * 보이는 등급·판정 사유·수정 방향.
 * 물음: 마크스폰 r4 ③ — 답 오면 여기만. 지금 안: 사용자 고침 ?? 기준 판단(재판단) ?? 첫 판단 — 재판단은 AI 값만 바꾸고
 * 고친 칸은 그대로 둔다(화면은 그 칸 머리에 「AI 판단이 바뀌었어요」).
 */
export function shownValues(
  edit: ReviewEdit | null,
  basis: Basis,
): { level: Level | null; reasons: readonly string[]; fix: string } {
  return {
    level: edit?.level?.value ?? basis.level,
    reasons: edit?.reasonBullets?.value ?? basis.reasonBullets,
    fix: edit?.fixParagraph?.value ?? basis.fixParagraph,
  };
}

/** 고친 칸의 고친 때가 기준 판단(재판단)보다 앞인가 — ③ 「AI 판단이 바뀌었어요」. 첫 판단이면 false. */
export function aiChangedSince(editedAt: string, basis: Basis): boolean {
  if (basis.rejudged === null) return false;
  return Date.parse(basis.rejudged.judgedAt) > Date.parse(editedAt);
}

export interface ReviewRow {
  /** 결과 items 의 차례(0부터). */
  index: number;
  item: ResultItem;
  /** 표시. 없으면 미검토. */
  mark: ReviewMark | null;
  /** 고침. 없으면 null(세 칸 다 AI 그대로). */
  edit: ReviewEdit | null;
  /** 근거 고침(GRJ1). 없으면 null(기준 판단 근거 그대로). */
  evidence: ReviewEvidence | null;
  /** 재판단 줄(GRJ1). 없으면 null(재판단 0). */
  rejudge: ReviewRejudge | null;
  /** 기준 판단(basisOf). */
  basis: Basis;
  /** 보이는 등급·판정 사유·수정 방향(shownValues). 등급 null = 리스크 아님(재판단). */
  shownLevel: Level | null;
  shownReasons: readonly string[];
  shownFix: string;
}

/** 결과 items 와 검토 marks·edits·evidence·rejudges 를 잇는다(items 차례). items 밖을 가리키는 것은 버린다. */
export function joinReview(
  items: readonly ResultItem[],
  marks: readonly ReviewMark[],
  edits: readonly ReviewEdit[] = [],
  evidence: readonly ReviewEvidence[] = [],
  rejudges: readonly ReviewRejudge[] = [],
): ReviewRow[] {
  const byIndex = new Map(marks.map((mark) => [mark.itemIndex, mark]));
  const editOf = new Map(edits.map((edit) => [edit.itemIndex, edit]));
  const evidenceOf = new Map(evidence.map((e) => [e.itemIndex, e]));
  const rejudgeOf = new Map(rejudges.map((r) => [r.itemIndex, r]));
  return items.map((item, index) => {
    const edit = editOf.get(index) ?? null;
    const rejudge = rejudgeOf.get(index) ?? null;
    const basis = basisOf(item, rejudge);
    const shown = shownValues(edit, basis);
    return {
      index,
      item,
      mark: byIndex.get(index) ?? null,
      edit,
      evidence: evidenceOf.get(index) ?? null,
      rejudge,
      basis,
      shownLevel: shown.level,
      shownReasons: shown.reasons,
      shownFix: shown.fix,
    };
  });
}

/** 문장 하나의 지금 근거(지운 칩 차례·더한 조각). 고침이 없으면 둘 다 빈 목록. */
export function evidenceNow(row: Pick<ReviewRow, 'evidence'>): {
  removed: readonly number[];
  added: readonly EvidenceAdded[];
} {
  return {
    removed: row.evidence?.removed ?? [],
    added: row.evidence?.added ?? [],
  };
}

/** 문장 하나의 근거를 바꾼 값(지운 칩 차례·더한 조각 — 갈아 넣기). */
export interface EvidenceChange {
  itemIndex: number;
  removed: readonly number[];
  added: readonly EvidenceAdded[];
}

/** 근거 PUT 본문: marks 그대로 + 그 실행의 근거 고침 전부(itemIndex 오름, 빈 문장은 뺌)에 changes 를 차례로 얹는다. edits 는 싣지 않는다. */
export function evidenceUpdate(
  review: GreenwashReview,
  ...changes: readonly EvidenceChange[]
): ReviewUpdate {
  const byIndex = new Map<number, ReviewEvidenceIn>(
    review.evidence.map((e) => [
      e.itemIndex,
      { itemIndex: e.itemIndex, removed: [...e.removed], added: [...e.added] },
    ]),
  );
  for (const change of changes)
    byIndex.set(change.itemIndex, {
      itemIndex: change.itemIndex,
      removed: [...new Set(change.removed)].sort((a, b) => a - b),
      added: change.added.map((piece) => ({ ...piece })),
    });
  return {
    marks: review.marks.map((mark) => ({ ...mark })),
    evidence: [...byIndex.values()]
      .filter((e) => e.removed.length > 0 || e.added.length > 0)
      .sort((a, b) => a.itemIndex - b.itemIndex),
  };
}

export interface ReviewTally {
  total: number;
  /** 채택 + 제외. */
  reviewed: number;
  adopted: number;
  excluded: number;
  pending: number;
  /** 고친 문장 수(칸 하나 이상 고친 문장). */
  edited: number;
}

export function reviewTally(rows: readonly ReviewRow[]): ReviewTally {
  let adopted = 0;
  let excluded = 0;
  let edited = 0;
  for (const row of rows) {
    if (row.mark?.decision === 'adopted') adopted++;
    else if (row.mark?.decision === 'excluded') excluded++;
    if (row.edit !== null) edited++;
  }
  return {
    total: rows.length,
    reviewed: adopted + excluded,
    adopted,
    excluded,
    pending: rows.length - adopted - excluded,
    edited,
  };
}

/** 문장 목록의 탭: 전체 · 등급 셋 · 미검토(검토 중) 또는 제외(확정 뒤, GW-05c). */
export type ReviewTab = 'all' | Level | 'pending' | 'excluded';

export interface ReviewFilter {
  /** 파트 이름(결과의 parts[].name). null 이면 전체. */
  part: string | null;
  tab: ReviewTab;
}

export function filterReviewRows(
  rows: readonly ReviewRow[],
  filter: ReviewFilter,
): ReviewRow[] {
  return rows.filter((row) => {
    if (filter.part !== null && !row.item.parts.includes(filter.part))
      return false;
    switch (filter.tab) {
      case 'all':
        return true;
      case 'pending':
        return row.mark === null;
      case 'excluded':
        return row.mark?.decision === 'excluded';
      default:
        return row.shownLevel === filter.tab;
    }
  });
}

/** 문장 하나의 새 표시. 제외면 사유 글이 있어야 한다(excludeReasonText 로 지은 것). */
export type MarkChange =
  | { itemIndex: number; decision: 'adopted' }
  | { itemIndex: number; decision: 'excluded'; reason: string };

/** 표시 하나를 바꾼 PUT 본문 [B3]: 그 실행의 marks 전부(오름차순). state 는 싣지 않는다(pending → in_review 는 서버가 옮긴다, 결함 D1). */
export function markUpdate(
  review: GreenwashReview,
  change: MarkChange,
): ReviewUpdate {
  const next: ReviewMark = {
    itemIndex: change.itemIndex,
    decision: change.decision,
    excludeReason: change.decision === 'excluded' ? change.reason : null,
  };
  const marks = sortMarks([
    ...review.marks.filter((mark) => mark.itemIndex !== change.itemIndex),
    next,
  ]);
  return { marks };
}

/** 확정 본문: 미검토를 모두 adopted 로 채운 marks 전부 + state: confirmed. itemCount 는 결과 items 의 길이. */
export function confirmUpdate(
  review: GreenwashReview,
  itemCount: number,
): ReviewUpdate {
  const byIndex = new Map(review.marks.map((mark) => [mark.itemIndex, mark]));
  const marks: ReviewMark[] = [];
  for (let index = 0; index < itemCount; index++)
    marks.push(
      byIndex.get(index) ?? {
        itemIndex: index,
        decision: 'adopted' satisfies ReviewDecision,
        excludeReason: null,
      },
    );
  return { state: 'confirmed', marks };
}

const sortMarks = (marks: ReviewMark[]) =>
  marks.sort((a, b) => a.itemIndex - b.itemIndex);

/** 문장 하나의 칸 하나를 고친 값. */
export type EditChange =
  | { itemIndex: number; column: 'level'; value: Level }
  | { itemIndex: number; column: 'reasonBullets'; value: readonly string[] }
  | { itemIndex: number; column: 'fixParagraph'; value: string };

/** 고침 하나 → PUT 의 평평한 값(때·사람은 서버가 넣는다). */
export function flatEdit(edit: ReviewEdit): ReviewEditIn {
  return {
    itemIndex: edit.itemIndex,
    level: edit.level?.value ?? null,
    reasonBullets: edit.reasonBullets?.value ?? null,
    fixParagraph: edit.fixParagraph?.value ?? null,
  };
}

/**
 * 고침 PUT 본문: marks 는 그대로 + 그 실행의 고침 전부(평평한 값, itemIndex 오름차순)에 changes 를 차례로 얹는다.
 * state 는 싣지 않는다(고침이 있으면 서버가 pending → in_review 로 옮긴다).
 */
export function editUpdate(
  review: GreenwashReview,
  ...changes: readonly EditChange[]
): ReviewUpdate {
  const byIndex = new Map(
    review.edits.map((edit) => [edit.itemIndex, flatEdit(edit)]),
  );
  for (const change of changes) {
    const before = byIndex.get(change.itemIndex) ?? {
      itemIndex: change.itemIndex,
      level: null,
      reasonBullets: null,
      fixParagraph: null,
    };
    byIndex.set(
      change.itemIndex,
      change.column === 'level' ? { ...before, level: change.value }
      : change.column === 'reasonBullets' ?
        { ...before, reasonBullets: [...change.value] }
      : { ...before, fixParagraph: change.value },
    );
  }
  return {
    marks: review.marks.map((mark) => ({ ...mark })),
    edits: [...byIndex.values()].sort((a, b) => a.itemIndex - b.itemIndex),
  };
}

/**
 * 판정 사유 → 글 칸의 글(항목마다 한 줄, 목록 표지 없이). 표지 「- 」를 칸에 두면 그 앞에 친 글이 「(친 글)- 원래 글」 한 줄로
 * 남는다(sid:MARC-ISSUE-315). 칸 밖 목록(Bullets)이 표지를 그린다.
 */
export function reasonsText(bullets: readonly string[]): string {
  return bullets.join('\n');
}

/**
 * 판정 사유 글 칸 → 항목: 한 줄 = 한 항목, 앞뒤 공백과 앞의 「- 」(「-」만 있는 줄도)를 떼고, 빈 줄은 버린다.
 * keep(지금 보이는 항목)과 글이 같은 줄은 그대로 둔다 — 「- 」로 시작하는 AI 항목을 손대지 않았는데 떼여 저장되지 않게(GP1 검증 R2).
 */
export function reasonsFromText(
  text: string,
  keep: readonly string[] = [],
): string[] {
  const kept = new Set(keep);
  return text
    .split(/\r?\n/)
    .map((line) =>
      kept.has(line.trim()) ?
        line.trim()
      : line
          .trim()
          .replace(/^-(?:\s+|$)/, '')
          .trim(),
    )
    .filter((line) => line !== '');
}

export type ExcludeReasonResult =
  { ok: true; text: string } | { ok: false; code: 'note_required' };

/**
 * 제외 사유 글 [R6]. label 은 05a 라디오 글자(문구 표), note 는 설명(앞뒤 공백을 지운다. 비면 없음).
 * 「기타」(requiresNote)는 설명이 있어야 한다.
 */
export function excludeReasonText(input: {
  label: string;
  note: string;
  requiresNote: boolean;
}): ExcludeReasonResult {
  const note = input.note.trim();
  if (input.requiresNote && note === '')
    return { ok: false, code: 'note_required' };
  return {
    ok: true,
    text: note === '' ? input.label : `${input.label}: ${note}`,
  };
}
