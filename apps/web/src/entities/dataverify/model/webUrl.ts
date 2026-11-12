// 출처 주소가 새 탭 링크가 될 수 있는가(밴드 DV9 — sid:MARC-ISSUE-565). 출처는 AI 출력이라 http(s) 밖은 링크로 만들지 않는다.

const WEB_SCHEME = /^https?:\/\//i;

/**
 * 앞뒤 공백을 뗀 값이 `http(s)://` 로 시작하고 `new URL()` 로 파싱되면 참(빈 값·상대 주소·파싱 실패는 거짓. 스킴 대소문자는 가리지 않는다).
 * 공통 칩의 isSafeLinkUrl 과 같은 판별 — 화면이 이 값으로 칩·회색 글을 가른다(밴드 DV11. `http:example.com` 은 URL 이 받아도 칩이 안 된다).
 * 판별만 한다. 주소는 받은 글자 그대로 칩에 넘기고 utm 떼기는 칩이 한다(밴드 DV12, sid:MARC-ISSUE-570).
 */
export function isWebLink(url: string): boolean {
  const trimmed = url.trim();
  if (!WEB_SCHEME.test(trimmed)) return false;
  try {
    new URL(trimmed);
    return true;
  } catch {
    return false;
  }
}
