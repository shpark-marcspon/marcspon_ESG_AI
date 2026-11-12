// 누를 수 있는 바깥 주소인가. shared/lib — 업무 모름, materiality 의 SAFE_URL 을 뒤 링크 칩 밴드가 이리로 갈아 끼운다.
const HTTP_SCHEME = /^https?:\/\//i;

/** 앞뒤 공백을 뗀 값이 http(s) 주소이고 host 가 있으면 참. href 에는 공백 뗀 값을 싣는다. */
export function isSafeLinkUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!HTTP_SCHEME.test(trimmed)) return false;
  try {
    return new URL(trimmed).host !== '';
  } catch {
    return false;
  }
}
