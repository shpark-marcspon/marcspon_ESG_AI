// 근거 고침·재판단의 흉내 규칙 한 벌(밴드 GRJ1 ③ — GMK1 교훈: 목 저장소 mockStore.ts 와 시험용 가짜 서버 api/testing.ts 가
// 같은 함수를 쓴다). 서버 정본: apps/api-py/esgapi/greenwash/service/actions/review.py(_checked_evidence·nothing_to_rejudge)·
// rejudge.py(규칙 5·6·7 차례). 값은 지어낸 것이다.
//   - 근거 PUT 검사(checkedEvidence): 문장 번호 범위 → 겹침 → 지운 칩 차례가 기준 판단 칩 수 밖 → 더한 조각 10개 →
//     조각 글 strip 전 2000자 그물 → 쓸 수 없는 글자(NUL·짝 없는 서로게이트 — 서버 has_bad_chars, ④ M1) → strip 뒤 빈 글 →
//     1000자 → 페이지 1~쪽 수. 글자 수는 코드 포인트. 둘 다 빈 문장은 싣지 않는다.
//   - 근거 고침 때·사람: 그 문장 값이 바뀐 PUT 에서만 새로(서버 _evidence_columns).
//   - 재판단 만들기 거절(rejudgeRefusal, 서버 차례): 확정됨 review_locked → 가장 늦은 재판단이 도는 중 rejudge_running →
//     지운 칩 0·더한 조각이 기준 판단에 보낸 것과 같음 nothing_to_rejudge(model 의 nothingToRejudge 를 부른다 — ④ L2).
//   - 확정 거절(confirmRefusal, 서버 review.py 규칙 8 — ④ B1): 그 실행에 도는 재판단이 하나라도 있으면 rejudge_running.
//     서버 차례대로 표시·고침·근거 검사(400) 뒤, 쓰기 앞에 본다.
//   - 근거 거절(evidenceRefusal, 규칙 8 넓힘 — GRJ3): 가장 늦은 재판단이 도는 문장의 근거를 지금 값과 다르게 바꾸면 rejudge_running.
//     같은 값을 다시 실음·다른 문장·evidence 생략은 받는다. 확정 거절 바로 뒤에 본다.
//   - 상태 바뀜: 만들면 running. 그 뒤 검토 읽기 REJUDGE_SETTLE_READS 번째에 끝난다(시간 대신 읽기 수 — 시험이 정해진 차례로 잼).
//     끝남 견본(mockJudgement): 더한 조각 글이 「(실패)」로 시작하면 failed, 「(리스크 아님)」으로 시작하면 nonrisk,
//     더한 조각이 있으면 Low, 없으면(지우기만) High. done 이 되면 그 문장의 지운 칩은 비운다(서버는 새 기준 판단에 대해 [] 로 읽는다).
//   - 목록 등급 수(basisCounts) = 고친 등급 ?? 기준 판단 등급. 리스크 아님은 세 칸 밖(서버 checks 와 같은 뜻).
import { basisOf, nothingToRejudge } from '../../model/index.ts';
import type {
  EvidenceAdded,
  Level,
  LevelCounts,
  Rejudged,
  ResultItem,
  ReviewEvidence,
  ReviewEvidenceIn,
  ReviewRejudge,
} from '../../model/index.ts';

/** 서버 models.py 의 EVIDENCE_* 와 같은 값. */
export const EVIDENCE_ADDED_MAX_ITEMS = 10;
export const EVIDENCE_TEXT_MAX_CHARS = 1000;
const EVIDENCE_TEXT_RAW_MAX_CHARS = EVIDENCE_TEXT_MAX_CHARS * 2;
/** 재판단이 끝나는 검토 읽기 차례(만든 뒤 n 번째 GET). */
export const REJUDGE_SETTLE_READS = 2;
/** 끝남 견본을 고르는 글 머리(지어낸 조각에만 쓴다). */
export const MOCK_FAIL_MARK = '(실패)';
export const MOCK_NONRISK_MARK = '(리스크 아님)';

const charsOf = (text: string) => [...text].length;
/** 서버 core/calc/ai_settings.has_bad_chars 와 같은 뜻: NUL 이나 짝 없는 서로게이트(jsonb 가 받지 않는다). */
const LONE_SURROGATE =
  /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/;
const hasBadChars = (text: string) =>
  text.includes('\u0000') || LONE_SURROGATE.test(text);

/** 흉내의 재판단 실행 하나. */
export interface MockRejudgeRun {
  runId: number;
  itemIndex: number;
  status: 'running' | 'failed' | 'done';
  /** 만든 뒤 읽힌 검토 GET 수. */
  reads: number;
  /** 만들 때 굳힌 더한 조각(기준 판단의 added 가 된다). */
  added: EvidenceAdded[];
  /** done 이면 판단. */
  judged: Rejudged | null;
}

/** 재판단 실행들(만든 차례) → 문장마다의 줄(서버 review@3 rejudges 와 같은 뜻 — current 는 가장 늦은 done). */
export function rejudgeLines(runs: readonly MockRejudgeRun[]): ReviewRejudge[] {
  const byIndex = new Map<number, MockRejudgeRun[]>();
  for (const run of runs)
    byIndex.set(run.itemIndex, [...(byIndex.get(run.itemIndex) ?? []), run]);
  return [...byIndex.entries()]
    .sort(([a], [b]) => a - b)
    .map(([itemIndex, mine]) => {
      let current: Rejudged | null = null;
      let count = 0;
      for (const run of mine)
        if (run.status === 'done' && run.judged !== null) {
          current = run.judged;
          count++;
        }
      return {
        itemIndex,
        status: mine[mine.length - 1]!.status,
        count,
        current: current === null ? null : structuredClone(current),
      };
    });
}

/** 문장 하나의 기준 판단(줄을 runs 에서 셈). */
function basisFor(
  items: readonly ResultItem[],
  runs: readonly MockRejudgeRun[],
  index: number,
) {
  const line = rejudgeLines(runs).find((l) => l.itemIndex === index) ?? null;
  return basisOf(items[index]!, line);
}

/** 근거 PUT 검사·정규화(서버 _checked_evidence 차례). 잘못이면 서버 400 의 문장. */
export function checkedEvidence(
  items: readonly ResultItem[],
  runs: readonly MockRejudgeRun[],
  pageCount: number,
  wanted: readonly ReviewEvidenceIn[],
): ReviewEvidenceIn[] | string {
  const out: ReviewEvidenceIn[] = [];
  const seen = new Set<number>();
  for (const edit of wanted) {
    const index = edit.itemIndex;
    if (!Number.isInteger(index) || index < 0 || index >= items.length)
      return `문장 번호 ${index}은(는) 이 결과에 없어요(0부터 ${items.length - 1}까지)`;
    if (seen.has(index))
      return `근거를 고친 문장 번호 ${index}이(가) 두 번 왔어요`;
    seen.add(index);
    const chips = basisFor(items, runs, index).confirmedInEvidence.length;
    const removed = [...new Set(edit.removed)].sort((a, b) => a - b);
    if (removed.some((chip) => chip < 0 || chip >= chips))
      return `지운 근거 번호가 이 문장의 근거(${chips}개) 밖이에요`;
    if (edit.added.length > EVIDENCE_ADDED_MAX_ITEMS)
      return `근거는 문장마다 ${EVIDENCE_ADDED_MAX_ITEMS}개까지 더할 수 있어요`;
    const added: EvidenceAdded[] = [];
    for (const piece of edit.added) {
      if (charsOf(piece.text) > EVIDENCE_TEXT_RAW_MAX_CHARS)
        return `더한 근거는 ${EVIDENCE_TEXT_MAX_CHARS}자까지 쓸 수 있어요`;
      if (hasBadChars(piece.text))
        return '더한 근거에 쓸 수 없는 글자가 있어요';
      const text = piece.text.trim();
      if (text === '') return '더한 근거는 비워 둘 수 없어요';
      if (charsOf(text) > EVIDENCE_TEXT_MAX_CHARS)
        return `더한 근거는 ${EVIDENCE_TEXT_MAX_CHARS}자까지 쓸 수 있어요`;
      if (piece.page !== null && (piece.page < 1 || piece.page > pageCount))
        return `더한 근거의 페이지는 1부터 ${pageCount}까지예요`;
      added.push({ text, page: piece.page });
    }
    if (removed.length > 0 || added.length > 0)
      out.push({ itemIndex: index, removed, added });
  }
  return out.sort((a, b) => a.itemIndex - b.itemIndex);
}

/** 정규화한 근거 → 저장할 근거 고침. 값이 그대로인 문장은 앞 때·사람을 둔다. */
export function nextEvidence(
  before: readonly ReviewEvidence[],
  checked: readonly ReviewEvidenceIn[],
  now: { at: string; by: { id: number; name: string } },
): ReviewEvidence[] {
  const old = new Map(before.map((e) => [e.itemIndex, e]));
  return checked.map((e) => {
    const prev = old.get(e.itemIndex);
    const same =
      prev !== undefined &&
      JSON.stringify([prev.removed, prev.added]) ===
        JSON.stringify([e.removed, e.added]);
    return {
      itemIndex: e.itemIndex,
      removed: [...e.removed],
      added: e.added.map((piece) => ({ ...piece })),
      editedAt: same ? prev.editedAt : now.at,
      editedBy: same ? { ...prev.editedBy } : { ...now.by },
    };
  });
}

export type RejudgeRefusal =
  'review_locked' | 'rejudge_running' | 'nothing_to_rejudge';

/** 재판단 만들기 거절(서버 rejudge.py 규칙 5·6·7 차례). 문장 번호 범위는 부르는 쪽이 먼저 404 로 본다. */
export function rejudgeRefusal(input: {
  confirmed: boolean;
  items: readonly ResultItem[];
  runs: readonly MockRejudgeRun[];
  evidence: readonly ReviewEvidence[];
  itemIndex: number;
}): RejudgeRefusal | null {
  if (input.confirmed) return 'review_locked';
  const mine = input.runs.filter((run) => run.itemIndex === input.itemIndex);
  if (mine.at(-1)?.status === 'running') return 'rejudge_running';
  const now = input.evidence.find((e) => e.itemIndex === input.itemIndex);
  const basis = basisFor(input.items, input.runs, input.itemIndex);
  const same = nothingToRejudge(now?.removed ?? [], now?.added ?? [], basis);
  return same ? 'nothing_to_rejudge' : null;
}

/** 확정 PUT 의 거절(서버 review.py 규칙 8): 그 실행에 도는 재판단이 하나라도 있으면 rejudge_running. */
export function confirmRefusal(
  runs: readonly MockRejudgeRun[],
): 'rejudge_running' | null {
  return runs.some((run) => run.status === 'running') ? 'rejudge_running' : (
      null
    );
}

/**
 * 근거 PUT 의 거절(서버 review.py 규칙 8 넓힘 — GRJ3): 가장 늦은 재판단이 도는 문장의 근거를 지금 값과 다르게 바꾸면
 * rejudge_running. 같은 값을 다시 실음·다른 문장·evidence 생략(null)은 받는다. checked 는 checkedEvidence 의 정규화 값.
 */
export function evidenceRefusal(
  runs: readonly MockRejudgeRun[],
  before: readonly ReviewEvidence[],
  checked: readonly ReviewEvidenceIn[] | null,
): 'rejudge_running' | null {
  if (checked === null) return null;
  const proof = (list: readonly ReviewEvidenceIn[], index: number) => {
    const e = list.find((x) => x.itemIndex === index);
    return JSON.stringify([e?.removed ?? [], e?.added ?? []]);
  };
  const running = new Set<number>();
  for (const index of new Set(runs.map((run) => run.itemIndex)))
    if (
      runs.filter((run) => run.itemIndex === index).at(-1)?.status === 'running'
    )
      running.add(index);
  for (const index of running)
    if (proof(checked, index) !== proof(before, index))
      return 'rejudge_running';
  return null;
}

/** 재판단 하나를 만든다(running). 만들 때의 더한 조각을 굳힌다. */
export function startRejudge(
  runId: number,
  itemIndex: number,
  evidence: readonly ReviewEvidence[],
): MockRejudgeRun {
  const now = evidence.find((e) => e.itemIndex === itemIndex);
  return {
    runId,
    itemIndex,
    status: 'running',
    reads: 0,
    added: (now?.added ?? []).map((piece) => ({ ...piece })),
    judged: null,
  };
}

/** 끝남 견본(지어낸 판단). */
export function mockJudgement(
  item: ResultItem,
  run: Pick<MockRejudgeRun, 'runId' | 'added'>,
  now: { at: string; by: { id: number; name: string } },
): Rejudged | 'failed' {
  if (run.added.some((piece) => piece.text.startsWith(MOCK_FAIL_MARK)))
    return 'failed';
  const nonrisk = run.added.some((piece) =>
    piece.text.startsWith(MOCK_NONRISK_MARK),
  );
  const level: Level = run.added.length > 0 ? 'Low' : 'High';
  return {
    runId: run.runId,
    judgedAt: now.at,
    judgedBy: { ...now.by },
    outcome: nonrisk ? 'nonrisk' : 'judged',
    level: nonrisk ? null : level,
    riskTags: nonrisk ? [] : [...item.riskTags],
    confirmedInEvidence: [
      ...run.added.map((piece) => piece.text),
      '다시 본 근거에서 확인한 사실(흉내)',
    ],
    missingFields: nonrisk ? [] : [...item.missingFields],
    reasonBullets: [
      nonrisk ?
        '바뀐 근거로 보면 그린워싱 리스크가 아니에요(흉내).'
      : '바뀐 근거로 다시 본 사유예요(흉내).',
    ],
    fixParagraph:
      nonrisk ? '' : '바뀐 근거에 맞춰 범위를 밝혀 쓰는 것이 좋아요(흉내).',
    evidencePages: [
      ...new Set(
        run.added.flatMap((piece) => (piece.page === null ? [] : [piece.page])),
      ),
    ].sort((a, b) => a - b),
    added: run.added.map((piece) => ({ ...piece })),
  };
}

/**
 * 검토 읽기 한 번: 도는 재판단의 읽기 수를 올리고 REJUDGE_SETTLE_READS 에 닿으면 끝낸다(견본). done 이면 그 문장의 지운 칩을 비운다.
 * 돌려주는 것은 바뀐 근거 고침(지운 칩 비움 뒤 — 둘 다 빈 문장은 빠진다).
 */
export function settleOnRead(
  items: readonly ResultItem[],
  runs: MockRejudgeRun[],
  evidence: readonly ReviewEvidence[],
  now: { at: string; by: { id: number; name: string } },
): ReviewEvidence[] {
  let out = [...evidence];
  for (const run of runs) {
    if (run.status !== 'running') continue;
    run.reads += 1;
    if (run.reads < REJUDGE_SETTLE_READS) continue;
    const judged = mockJudgement(items[run.itemIndex]!, run, now);
    if (judged === 'failed') {
      run.status = 'failed';
      continue;
    }
    run.status = 'done';
    run.judged = judged;
    out = out
      .map((e) => (e.itemIndex === run.itemIndex ? { ...e, removed: [] } : e))
      .filter((e) => e.removed.length > 0 || e.added.length > 0);
  }
  return out;
}

/**
 * 기준 판단을 얹은 items(고침 견줌용 — 서버는 「AI 값과 같으면 고침 null」을 기준 판단과 견준다, GRJ1 §2-4).
 * 리스크 아님이면 등급이 null 이라 어떤 고친 등급과도 다르다(등급 칸은 ResultItem 꼴을 지키려고 단언으로 싣는다).
 */
export function basisItems(
  items: readonly ResultItem[],
  runs: readonly MockRejudgeRun[],
): ResultItem[] {
  const lines = new Map(rejudgeLines(runs).map((l) => [l.itemIndex, l]));
  return items.map((item, index) => {
    const current = lines.get(index)?.current ?? null;
    if (current === null) return item;
    return {
      ...item,
      level: current.level as Level,
      reasonBullets: current.reasonBullets,
      fixParagraph: current.fixParagraph,
    };
  });
}

/**
 * 목록 등급 수: 결과의 등급 수(counts.byLevel)에서 출발해, 효력 등급(고친 등급 ?? 기준 판단 등급)이 첫 판단과 다른 문장만 옮긴다
 * (리스크 아님은 세 칸 밖 — 서버 checks 와 같은 뜻). 재판단·고침이 없으면 byLevel 그대로(목 effectiveCounts 와 같다).
 */
export function basisCounts(
  items: readonly ResultItem[],
  byLevel: LevelCounts,
  editedLevels: ReadonlyMap<number, Level>,
  runs: readonly MockRejudgeRun[],
): LevelCounts {
  const lines = new Map(rejudgeLines(runs).map((l) => [l.itemIndex, l]));
  const counts: LevelCounts = { ...byLevel };
  items.forEach((item, index) => {
    const level =
      editedLevels.get(index) ?? basisOf(item, lines.get(index) ?? null).level;
    if (level === item.level) return;
    counts[item.level] -= 1;
    if (level !== null) counts[level] += 1;
  });
  return counts;
}
