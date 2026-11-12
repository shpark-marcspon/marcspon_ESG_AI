// AD-02 그린워싱 탭의 대상 단어 초안(밴드 AS3b ① — sid:MARC-ENT-394). 순수 함수와 타입만 있다(다른 entities 를 가져오지 않는다).
//   - 초안 꼴(TermsDraft): 판의 terms 목록 그대로({text, enabled}, 판 차례). 바탕이 null(코드 기본 목록)이면 기본 낱말을 다 켠 목록 —
//     바탕과 초안은 같은 꼴이고 null 표식은 없다(null 을 그대로 싣는 것은 모듈 줄의 create 가 바탕 판을 다시 읽어 정한다).
//   - 셈: 같은 낱말 = trim 뒤 글이 같음. 더함·지움·사용 바꿈 각 1 — 되돌려 같아지면 0, 더하고 지운 새 낱말 0, 차례는 세지 않는다.
//   - 받기 검사([추가] 입력 — 사용자 도움만, 그물은 서버 TERMS_*): 1~30자 · 괄호·따옴표 0 · 비교 키 겹침 · 100개(켠+끈). 글자 유무·보이지 않는 글자는 서버.
//   - termKey: 서버 term_key(apps/api-py/esgapi/greenwash/engines/e0/gw1.py)의 사본(entities/greenwash 의 것을 가져오지 않는다 — 대조는 terms.test 의 고정 표).

/** 대상 단어 한 줄(판의 terms 꼴). */
export interface Term {
  text: string;
  enabled: boolean;
}

/** 대상 단어 초안(판 차례). */
export type TermsDraft = readonly Term[];

/** 한 판에 둘 수 있는 낱말 수(켠+끈 — 서버 TERMS_MAX). */
export const TERMS_MAX = 100;
/** 낱말 한 개의 글자 수 상한(서버 TERM_CHARS). */
export const TERM_CHARS = 30;
/** 쓸 수 없는 글자: 괄호·따옴표(서버 TERM_REFUSED 와 같은 글자). */
const REFUSED_CHARS = /[(){}[\]"'“”‘’]/;
/** 낱말 정규화에서 공백으로 바꾸는 글자 여섯. */
const TERM_SEPARATORS = /[-_/·•∙]/g;

/** 겹침 판정 키: 소문자 → 앞뒤 공백 → 구분 글자를 공백으로 → 공백 접기 → 앞뒤 공백 → 공백 모두 지움. */
export function termKey(raw: string): string {
  return raw
    .toLowerCase()
    .trim()
    .replace(TERM_SEPARATORS, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/ /g, '');
}

/** 바탕 몫: 판의 terms, null 이면 기본 낱말을 다 켠 목록. */
export function termsBase(
  terms: readonly Term[] | null,
  defaults: readonly string[],
): TermsDraft {
  return terms === null ?
      defaults.map((text) => ({ text, enabled: true }))
    : terms.map(({ text, enabled }) => ({ text, enabled }));
}

const textOf = (term: Term) => term.text.trim();

/** 고친 것 셈의 조각: 더함·지움·사용 바꿈. */
export function termChanges(base: TermsDraft, draft: TermsDraft) {
  const before = new Map(base.map((term) => [textOf(term), term.enabled]));
  const after = new Map(draft.map((term) => [textOf(term), term.enabled]));
  let added = 0;
  let toggled = 0;
  for (const [text, enabled] of after) {
    const was = before.get(text);
    if (was === undefined) added += 1;
    else if (was !== enabled) toggled += 1;
  }
  const removed = [...before.keys()].filter((text) => !after.has(text)).length;
  return { added, removed, toggled };
}

/** 고친 것 셈(0 = 깨끗). */
export function termsCount(base: TermsDraft, draft: TermsDraft): number {
  const { added, removed, toggled } = termChanges(base, draft);
  return added + removed + toggled;
}

/** 저장 창 「고친 것」 조각 글(0 인 조각을 뺀다). */
export interface TermsChangedWords {
  label: string;
  added(n: number): string;
  removed(n: number): string;
  toggled(n: number): string;
  join: string;
}

/** 저장 창 「고친 것」 조각 — 고친 것이 없으면 빈 목록, 있으면 한 조각(「대상 단어 2개 추가 · 1개 삭제」). */
export function termsChanged(
  base: TermsDraft,
  draft: TermsDraft,
  words: TermsChangedWords,
): string[] {
  const { added, removed, toggled } = termChanges(base, draft);
  const parts = [
    ...(added > 0 ? [words.added(added)] : []),
    ...(removed > 0 ? [words.removed(removed)] : []),
    ...(toggled > 0 ? [words.toggled(toggled)] : []),
  ];
  return parts.length === 0 ? [] : [`${words.label} ${parts.join(words.join)}`];
}

/** 저장을 끈다: 켠 낱말이 하나도 없다. */
export function termsBlocked(draft: TermsDraft): boolean {
  return !draft.some((term) => term.enabled);
}

/** [추가] 입력 검사의 갈래. */
export type TermProblem = 'length' | 'chars' | 'duplicate' | 'count';

/** [추가] 입력 검사(글자 유무·보이지 않는 글자는 서버 TERMS_TEXT). 맞으면 null. */
export function termProblem(
  draft: TermsDraft,
  raw: string,
): TermProblem | null {
  const text = raw.trim();
  const chars = [...text].length;
  if (chars < 1 || chars > TERM_CHARS) return 'length';
  if (REFUSED_CHARS.test(text)) return 'chars';
  const key = termKey(text);
  if (draft.some((term) => termKey(term.text) === key)) return 'duplicate';
  if (draft.length >= TERMS_MAX) return 'count';
  return null;
}

/** 낱말 하나를 끝에 더한다(켬, trim 한 글). 검사에 걸리면 그 갈래. */
export function addTerm(
  draft: TermsDraft,
  raw: string,
):
  | { kind: 'ok'; draft: TermsDraft }
  | { kind: 'problem'; problem: TermProblem } {
  const problem = termProblem(draft, raw);
  if (problem !== null) return { kind: 'problem', problem };
  return { kind: 'ok', draft: [...draft, { text: raw.trim(), enabled: true }] };
}

/** 고른 낱말(글)을 지운다. */
export function removeTerms(
  draft: TermsDraft,
  picked: ReadonlySet<string>,
): TermsDraft {
  return draft.filter((term) => !picked.has(term.text));
}

/** 낱말 하나의 사용을 바꾼다. */
export function switchTerm(
  draft: TermsDraft,
  text: string,
  enabled: boolean,
): TermsDraft {
  return draft.map((term) =>
    term.text === text ? { ...term, enabled } : term,
  );
}

/** 바탕에 없는 낱말(「추가」 표시 — 저장 전에만)의 글. */
export function addedTexts(
  base: TermsDraft,
  draft: TermsDraft,
): ReadonlySet<string> {
  const before = new Set(base.map(textOf));
  return new Set(
    draft.filter((term) => !before.has(textOf(term))).map((term) => term.text),
  );
}

/** 대상 단어 저장 거절 code(서버 greenwash/flows/terms_e0 의 code — 대문자). */
export const TERMS_CODES = [
  'TERMS_TEXT',
  'TERMS_DUPLICATE',
  'TERMS_COUNT',
  'TERMS_NONE_ENABLED',
] as const;
export type TermsCode = (typeof TERMS_CODES)[number];

/**
 * 대상 단어 저장 거절 풀이: TERMS_* 넷 → 창 줄 「<머리> — <웹 글>」과 짚은 자리(서버 fields 의 terms 경로 → 웹 글). 서버 문장은 보이지 않는다.
 * 모르는 code 는 null(껍데기가 일반 글로).
 */
export function termsRefusal(
  code: string | null,
  fields: Readonly<Record<string, readonly string[]>>,
  words: { label: string; refused: Readonly<Record<TermsCode, string>> },
): {
  line: string;
  refused: Readonly<Record<string, readonly string[]>>;
} | null {
  const known: readonly string[] = TERMS_CODES;
  if (code === null || !known.includes(code)) return null;
  const text = words.refused[code as TermsCode];
  return {
    line: `${words.label} — ${text}`,
    refused: Object.fromEntries(
      Object.keys(fields)
        .filter((path) => path === 'terms' || path.startsWith('terms.'))
        .map((path) => [path, [text]]),
    ),
  };
}

/** 짚은 자리 경로 terms.<i>.text 의 줄 차례(그 밖은 null). */
export function refusedRow(path: string): number | null {
  const found = /^terms\.(\d+)\.text$/.exec(path);
  return found ? Number(found[1]) : null;
}
