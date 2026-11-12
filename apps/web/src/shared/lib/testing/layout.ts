// 테스트가 쓰는 것. jsdom 에는 배치(layout)가 없어 모든 요소의 크기가 0 이다.
// 가상 스크롤은 스크롤 상자와 행의 높이를 읽으므로, 테스트에서는 그 값을 정해 준다.

/** 스크롤 상자(data-testid="rt-scroll")는 높이 400, 행(data-index 가 붙은 요소)은 높이 40 으로 보이게 한다. 되돌리는 함수를 돌려준다. */
export function fakeLayout(): () => void {
  const height = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    'offsetHeight',
  );
  const width = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    'offsetWidth',
  );
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    get(this: HTMLElement) {
      if (this.dataset.testid === 'rt-scroll') return 400;
      return this.dataset.index !== undefined ? 40 : 0;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
    configurable: true,
    get: () => 800,
  });
  return () => {
    if (height)
      Object.defineProperty(HTMLElement.prototype, 'offsetHeight', height);
    if (width)
      Object.defineProperty(HTMLElement.prototype, 'offsetWidth', width);
  };
}
