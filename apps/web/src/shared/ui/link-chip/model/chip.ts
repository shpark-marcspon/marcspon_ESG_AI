// 칩에 보일 값을 주소와 제목에서 뽑는다(보드 CM-04 r1 의 칩 규칙·구현 메모). 믿지 않는 글이라는 전제다.
// 주소는 부르는 쪽이 isSafeLinkUrl 로 거른 뒤에만 chipFacts 에 넣는다.
const INVISIBLE = /[\p{Cc}‪-‮⁦-⁩‎‏؜]/gu;
const SCHEME_AND_WWW = /^(?:https?:\/\/)?(?:www\.)?/i;
const UTM_PARAM = /^utm_/i;
const OPENAI_TAIL = /^utm_source=openai$/i;

export interface ChipFacts {
  /** 호스트에서 www. 를 뗀 값(뱃지). */
  domain: string;
  /** 받은 제목, 없거나 주소 자체면 경로 앞부분, 경로도 없으면 도메인. */
  title: string;
  /** 툴팁: utm_ 꼬리를 뗀 전체 주소. */
  tooltip: string;
  /** 여는 주소: utm_source=openai 만 뗀 값(chipHref). */
  href: string;
}

/** 보이는 글에서 제어·방향 글자를 지우고 앞뒤 공백을 다듬는다. */
export function cleanText(text: string): string {
  return text.replace(INVISIBLE, '').trim();
}

/** 퍼센트 인코딩을 풀어 읽게 한다. 풀지 못하면(잘못된 %) 받은 값. */
function readable(text: string): string {
  try {
    return cleanText(decodeURI(text));
  } catch {
    return cleanText(text);
  }
}

/** 스킴·www 를 떼고 푼 값끼리 견줘 같으면 제목이 아니라 주소다. */
function sameAddress(label: string, url: string): boolean {
  const bare = (value: string) => readable(value).replace(SCHEME_AND_WWW, '');
  return bare(label) === bare(url);
}

/** utm_ 꼬리만 뗀다. 남은 쿼리는 받은 글자 그대로 둔다(URLSearchParams 는 %20 을 + 로 바꾼다). */
function withoutUtm(parsed: URL): URL {
  const kept = parsed.search
    .slice(1)
    .split('&')
    .filter((part) => part !== '' && !UTM_PARAM.test(part));
  const next = new URL(parsed.href);
  next.search = kept.length > 0 ? `?${kept.join('&')}` : '';
  return next;
}

/**
 * 여는 주소: 앞뒤 공백을 떼고 쿼리의 utm_source=openai 만 뗀다(밴드 AD8, sid:MARC-ISSUE-570. 대소문자 무시). 툴팁(모든 utm_)과 규칙이 다르다.
 * 받은 글자를 조각으로만 다룬다 — URL 로 되짓지 않아 남은 쿼리·조각이 그대로다. 뗄 것이 없으면 끝 「?」 까지 받은 그대로, 남은 조각이 비면 「?」 도 없다.
 */
export function chipHref(url: string): string {
  const trimmed = url.trim();
  const hash = trimmed.indexOf('#');
  const body = hash < 0 ? trimmed : trimmed.slice(0, hash);
  const fragment = hash < 0 ? '' : trimmed.slice(hash);
  const mark = body.indexOf('?');
  if (mark < 0) return trimmed;
  const parts = body.slice(mark + 1).split('&');
  const kept = parts.filter((part) => !OPENAI_TAIL.test(part));
  if (kept.length === parts.length) return trimmed;
  const query = kept.some((part) => part !== '') ? `?${kept.join('&')}` : '';
  return `${body.slice(0, mark)}${query}${fragment}`;
}

/** 앞뒤 「/」 를 뗀다. 긴 주소가 들어오므로 정규식 대신 끝에서 훑는다. */
function trimSlashes(text: string): string {
  let start = 0;
  let end = text.length;
  while (start < end && text[start] === '/') start += 1;
  while (end > start && text[end - 1] === '/') end -= 1;
  return text.slice(start, end);
}

export function chipFacts(url: string, label?: string): ChipFacts {
  const parsed = new URL(url.trim());
  const domain = parsed.host.replace(/^www\./i, '');
  const path = trimSlashes(readable(parsed.pathname));
  const given = cleanText(label ?? '');
  const title =
    given !== '' && !sameAddress(given, url) ? given : path || domain;
  return {
    domain,
    title,
    tooltip: readable(withoutUtm(parsed).href),
    href: chipHref(url),
  };
}
