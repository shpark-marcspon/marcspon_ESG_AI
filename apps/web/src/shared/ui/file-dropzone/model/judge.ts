// 파일 판정. 순수 TypeScript 다(React·DOM 을 모른다. File 객체 대신 이름·크기·type 만 본다).
//
// 키트 use-file-dropzone 의 버그(FV3 4.3)를 바로잡은 자리:
//   1) 확장자를 부분 문자열로 비교했다(".xlsx".includes(".xls") 가 참이라 .xls 가 통과). → 확장자는 정확히 같은지 본다(대소문자 무시).
//      MIME 와일드카드("image/*")에 확장자를 비교해 .png 가 거부됐다. → MIME 은 따로, 와일드카드는 앞부분으로 본다.
//   3) 같은 이름 검사를 기존 목록과만 했다. → 한 번에 고른 파일끼리도 본다.
//      크기 상한을 기존+새 파일의 합계에 걸었다. → 파일 하나 기준이다.
//   4) 거부 규칙이 섞여 있었다(하나씩 거부와 개수 초과 전부 거부). → 하나로: 걸러서 통과.
//      규칙에 맞는 것은 받고, 안 맞는 것은 사유와 함께 거부 목록에 둔다. 개수 초과도 남은 자리만큼 앞에서부터 받는다.
// 「걸러서 통과」와 「크기는 파일 하나 기준」은 감독 판정이다(FK2 발주서 ④). 무효 조건: 디자인·업무 트랙이 「하나라도 틀리면 전부 거부」나
// 합계 상한으로 정하면 이 함수의 차례(아래 judgeFiles)를 바꾼다.

/** 판정에 쓰는 파일의 꼴. 브라우저 File 도 이 꼴을 만족한다. */
export interface PickedFile {
  name: string;
  size: number;
  /** MIME. 브라우저가 모르면 빈 글자. */
  type: string;
}

/** 이미 있는 목록의 항목에서 판정이 보는 것: 이름. */
export interface ExistingFile {
  name: string;
}

export interface FileRule {
  /**
   * 받을 형식. 확장자(".xlsx", 앞의 점 포함, 대소문자 무시), MIME("application/pdf"), MIME 와일드카드("image/*").
   * 비었거나 없으면 모든 형식을 받는다.
   */
  accept?: readonly string[];
  /** 파일 하나의 크기 상한(MB, 1MB = 1024×1024 바이트). 없으면 상한 없음. */
  maxMb?: number;
  /** 목록 전체(이미 있는 것 + 새로 받는 것)의 개수 상한. 없으면 상한 없음. */
  maxCount?: number;
}

export const REJECT_REASONS = ['type', 'size', 'duplicate', 'count'] as const;
/** 거부 사유: 형식(type) · 크기(size) · 같은 이름(duplicate) · 개수(count). */
export type RejectReason = (typeof REJECT_REASONS)[number];

export interface Rejected<T> {
  file: T;
  reason: RejectReason;
}
export interface Judgement<T> {
  accepted: T[];
  rejected: Rejected<T>[];
}

/** 파일 이름의 확장자(점 포함, 소문자). 점이 없거나 이름이 점으로만 시작하면 빈 글자. */
export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(dot).toLowerCase() : '';
}

/** 한 파일이 받을 형식 목록에 맞는가. */
export function matchesAccept(
  file: Pick<PickedFile, 'name' | 'type'>,
  accept: readonly string[] | undefined,
): boolean {
  if (!accept || accept.length === 0) return true;
  const extension = extensionOf(file.name);
  const type = file.type.toLowerCase();
  return accept.some((raw) => {
    const entry = raw.trim().toLowerCase();
    if (entry.startsWith('.')) return extension !== '' && extension === entry;
    if (entry.endsWith('/*'))
      return type !== '' && type.startsWith(entry.slice(0, -1));
    if (entry.includes('/')) return type === entry;
    return false;
  });
}

/**
 * 받을 형식을 사람이 읽는 꼴로: 점을 떼고 대문자로, 겹친 것은 한 번, 받은 차례대로 가운뎃점(·)으로 잇는다.
 * [".pdf"] → "PDF", [".xlsx", ".csv"] → "XLSX·CSV".
 * 확장자가 아닌 항목(MIME "application/pdf", 와일드카드 "image/*")이 하나라도 있으면 undefined 다: 확장자만 이어 쓰면
 * 실제로 받는 형식보다 좁게 말하게 된다(["image/*", ".png"] 를 「PNG 파일만」이라 하면 거짓). 그때는 값 없는 문구를 쓴다.
 * 비었거나 없어도 undefined. (밴드 FW1 ③, 가지 리뷰 지적. 무효 조건: MIME 을 이름으로 옮기는 표가 생기면 바꾼다.)
 */
export function formatsLabel(
  accept: readonly string[] | undefined,
): string | undefined {
  const names: string[] = [];
  for (const raw of accept ?? []) {
    const entry = raw.trim();
    if (!entry.startsWith('.') || entry.length < 2) return undefined;
    const name = entry.slice(1).toUpperCase();
    if (!names.includes(name)) names.push(name);
  }
  return names.length > 0 ? names.join('·') : undefined;
}

/** 숨긴 <input type=file> 의 accept 속성 값. */
export function acceptAttribute(
  accept: readonly string[] | undefined,
): string | undefined {
  return accept && accept.length > 0 ? accept.join(',') : undefined;
}

const sameName = (left: string, right: string) =>
  left.toLowerCase() === right.toLowerCase();

/**
 * 고른 파일들을 판정한다. 차례: 형식 → 크기 → 같은 이름(이미 있는 것 + 이번에 앞서 받은 것) → 개수.
 * 개수는 맨 마지막에 본다: 형식·크기·이름을 통과한 것 가운데 남은 자리만큼 앞에서부터 받는다.
 * 같은 이름은 대소문자를 가리지 않는다(Windows·macOS 의 파일 이름처럼).
 */
export function judgeFiles<T extends PickedFile>(
  picked: readonly T[],
  existing: readonly ExistingFile[],
  rule: FileRule,
): Judgement<T> {
  const accepted: T[] = [];
  const rejected: Rejected<T>[] = [];
  const limit = rule.maxMb === undefined ? Infinity : rule.maxMb * 1024 * 1024;
  const room =
    rule.maxCount === undefined ?
      Infinity
    : Math.max(0, rule.maxCount - existing.length);
  for (const file of picked) {
    if (!matchesAccept(file, rule.accept)) {
      rejected.push({ file, reason: 'type' });
    } else if (file.size > limit) {
      rejected.push({ file, reason: 'size' });
    } else if (
      existing.some((item) => sameName(item.name, file.name)) ||
      accepted.some((item) => sameName(item.name, file.name))
    ) {
      rejected.push({ file, reason: 'duplicate' });
    } else if (accepted.length >= room) {
      rejected.push({ file, reason: 'count' });
    } else {
      accepted.push(file);
    }
  }
  return { accepted, rejected };
}

/** 날짜를 YYYY-MM-DD 로(그 기기의 지역 시간). 목록 줄의 날짜 글자에 쓴다. */
export function toDateText(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}
