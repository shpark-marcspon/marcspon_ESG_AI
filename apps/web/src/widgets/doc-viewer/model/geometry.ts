// 쪽 좌표 → 화면 좌표.
//
// 쪽 좌표(입력 계약의 box): PDF 포인트(1/72 인치), 원점은 쪽의 왼쪽 위, y 는 아래로 자란다.
//   [x0, y0, x1, y1] = 왼쪽, 위, 오른쪽, 아래.  (쪽이 화면에 바로 놓였을 때의 자리)
// 화면 좌표: 그려진 쪽의 왼쪽 위에서 잰 CSS 픽셀.
//
// 배율(scale)은 「1 포인트 = 몇 CSS 픽셀」이다. 회전(rotation)은 보는 사람이 쪽을 시계 방향으로 돌린 각도다.
// pdf.js 가 캔버스를 그릴 때 쓰는 계산(viewport)과 같은 결과를 내야 상자가 글자 위에 놓인다.
// 그 일치는 브라우저 테스트(e2e/)가 확인한다.

export type Box = readonly [x0: number, y0: number, x1: number, y1: number];
export type Rotation = 0 | 90 | 180 | 270;

export interface PageSize {
  width: number;
  height: number;
}

export interface ScreenRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** 돌린 뒤 쪽이 화면에서 차지하는 크기(CSS 픽셀). 90·270 도면 가로와 세로가 바뀐다. */
export function pageScreenSize(
  page: PageSize,
  scale: number,
  rotation: Rotation = 0,
): PageSize {
  const sideways = rotation === 90 || rotation === 270;
  return {
    width: (sideways ? page.height : page.width) * scale,
    height: (sideways ? page.width : page.height) * scale,
  };
}

/** 쪽 위의 점 하나를 시계 방향으로 돌린다. 결과도 「왼쪽 위 원점, y 아래로」다. */
function rotatePoint(
  x: number,
  y: number,
  page: PageSize,
  rotation: Rotation,
): [number, number] {
  switch (rotation) {
    case 0:
      return [x, y];
    case 90:
      return [page.height - y, x];
    case 180:
      return [page.width - x, page.height - y];
    case 270:
      return [y, page.width - x];
  }
}

/** 쪽 좌표의 상자가 화면의 어디에 놓이는가. */
export function boxToScreenRect(
  box: Box,
  page: PageSize,
  scale: number,
  rotation: Rotation = 0,
): ScreenRect {
  const [x0, y0, x1, y1] = box;
  const [ax, ay] = rotatePoint(x0, y0, page, rotation);
  const [bx, by] = rotatePoint(x1, y1, page, rotation);
  // 돌리면 어느 모서리가 왼쪽 위인지가 바뀌므로 작은 쪽을 다시 고른다.
  return {
    left: Math.min(ax, bx) * scale,
    top: Math.min(ay, by) * scale,
    width: Math.abs(bx - ax) * scale,
    height: Math.abs(by - ay) * scale,
  };
}

// ── 쪽을 세로로 쌓았을 때의 자리 ──────────────────────────────────────────────

/** 쪽과 쪽 사이, 그리고 맨 위·맨 아래의 틈(CSS 픽셀). 쪽의 자리는 전부 코드가 셈해 주므로 CSS 에는 이 값이 없다. */
export const PAGE_GAP = 12;

/** 쪽마다 스크롤 영역의 맨 위에서 얼마나 내려와 있는가(CSS 픽셀). offsets[0] 이 1쪽이다. */
export function pageOffsets(
  pages: readonly PageSize[],
  scale: number,
  rotation: Rotation = 0,
): number[] {
  const offsets: number[] = [];
  let top = PAGE_GAP;
  for (const page of pages) {
    offsets.push(top);
    top += pageScreenSize(page, scale, rotation).height + PAGE_GAP;
  }
  return offsets;
}

/** 쌓은 쪽 전체의 높이. */
export function totalHeight(
  pages: readonly PageSize[],
  scale: number,
  rotation: Rotation = 0,
): number {
  return pages.reduce(
    (sum, page) =>
      sum + pageScreenSize(page, scale, rotation).height + PAGE_GAP,
    PAGE_GAP,
  );
}

/**
 * 지금 그려야 하는 쪽의 범위(1부터 세는 쪽 번호, 양 끝 포함).
 * 보이는 쪽에 앞뒤로 overscan 쪽씩 더한다. 이 범위 밖의 쪽은 빈 자리만 둔다.
 */
export function visiblePageRange(
  scrollTop: number,
  viewportHeight: number,
  pages: readonly PageSize[],
  scale: number,
  rotation: Rotation = 0,
  overscan = 1,
): { first: number; last: number } {
  if (pages.length === 0) return { first: 1, last: 0 };
  const offsets = pageOffsets(pages, scale, rotation);
  const bottom = scrollTop + viewportHeight;
  let first = pages.length;
  let last = 1;
  pages.forEach((page, index) => {
    const pageTop = offsets[index]!;
    const pageBottom = pageTop + pageScreenSize(page, scale, rotation).height;
    if (pageBottom >= scrollTop && pageTop <= bottom) {
      first = Math.min(first, index + 1);
      last = Math.max(last, index + 1);
    }
  });
  if (first > last) {
    // 틈만 보이는 경우는 없지만(틈이 쪽보다 작다), 높이가 0 인 화면에서는 첫 쪽으로 둔다.
    first = last = 1;
  }
  return {
    first: Math.max(1, first - overscan),
    last: Math.min(pages.length, last + overscan),
  };
}

/**
 * 화면에서 「보는 줄」의 높이(화면 높이에 대한 비율). 강조로 갈 때 상자의 윗변을 이 줄에 놓고(scrollTopForBox),
 * 「지금 쪽」도 이 줄에 걸린 쪽으로 친다(pageAtScroll). 둘이 같은 줄을 써야 고른 상자가 있는 쪽의 번호가 보인다.
 * (전에는 지금 쪽을 화면 가운데 줄로 쳐서, 고른 상자가 쪽의 맨 아래에 있으면 다음 쪽 번호가 보였다.)
 */
export const FOCUS_LINE = 1 / 3;

/** 화면의 보는 줄(FOCUS_LINE)에 걸린 쪽(없으면 가장 가까운 쪽). 쪽 번호 표시에 쓴다. */
export function pageAtScroll(
  scrollTop: number,
  viewportHeight: number,
  pages: readonly PageSize[],
  scale: number,
  rotation: Rotation = 0,
): number {
  const offsets = pageOffsets(pages, scale, rotation);
  const line = scrollTop + viewportHeight * FOCUS_LINE;
  let current = 1;
  offsets.forEach((top, index) => {
    if (top <= line) current = index + 1;
  });
  return current;
}

/**
 * 상자가 화면에 보이도록 스크롤할 자리. 상자를 화면 높이의 3분의 1 지점(FOCUS_LINE)에 둔다
 * (맨 위에 붙이면 위쪽 문맥이 안 보인다).
 */
export function scrollTopForBox(
  pageNumber: number,
  box: Box,
  viewportHeight: number,
  pages: readonly PageSize[],
  scale: number,
  rotation: Rotation = 0,
): number {
  const page = pages[pageNumber - 1];
  const pageTop = pageOffsets(pages, scale, rotation)[pageNumber - 1];
  if (!page || pageTop === undefined) return 0;
  const rect = boxToScreenRect(box, page, scale, rotation);
  const target = pageTop + rect.top - viewportHeight * FOCUS_LINE;
  const max = Math.max(0, totalHeight(pages, scale, rotation) - viewportHeight);
  return Math.min(max, Math.max(0, target));
}

/**
 * 배율이나 회전을 바꾼 뒤에도 보던 쪽의 같은 높이를 보고 있도록 하는 스크롤 자리.
 * (회전이 바뀌면 쪽 안의 자리는 어긋난다. 그때는 같은 쪽의 같은 비율 높이로 간다.)
 */
export function scrollTopAfterResize(
  scrollTop: number,
  pages: readonly PageSize[],
  from: { scale: number; rotation: Rotation },
  to: { scale: number; rotation: Rotation },
): number {
  if (pages.length === 0) return 0;
  const before = pageOffsets(pages, from.scale, from.rotation);
  // 화면 맨 위에 걸린 쪽을 기준으로 삼는다.
  let index = 0;
  before.forEach((top, i) => {
    if (top <= scrollTop) index = i;
  });
  const page = pages[index]!;
  const heightBefore = pageScreenSize(page, from.scale, from.rotation).height;
  const heightAfter = pageScreenSize(page, to.scale, to.rotation).height;
  const fraction = (scrollTop - before[index]!) / heightBefore;
  return Math.max(
    0,
    pageOffsets(pages, to.scale, to.rotation)[index]! + fraction * heightAfter,
  );
}

/**
 * 상자가 가로로도 보이도록 스크롤할 자리. 쪽이 화면보다 넓을 때(크게 확대했을 때)만 0 이 아니다.
 * 쪽은 쌓는 영역의 가운데에 놓이고, 쌓는 영역의 폭은 「화면 폭」과 「가장 넓은 쪽 + 양옆 틈」 가운데 큰 쪽이다.
 */
export function scrollLeftForBox(
  pageNumber: number,
  box: Box,
  viewportWidth: number,
  pages: readonly PageSize[],
  scale: number,
  rotation: Rotation = 0,
): number {
  const page = pages[pageNumber - 1];
  if (!page) return 0;
  const widest = Math.max(
    ...pages.map((p) => pageScreenSize(p, scale, rotation).width),
  );
  const stackWidth = Math.max(viewportWidth, widest + 2 * PAGE_GAP);
  const pageLeft =
    (stackWidth - pageScreenSize(page, scale, rotation).width) / 2;
  const rect = boxToScreenRect(box, page, scale, rotation);
  // 상자의 가운데를 화면의 가운데에 둔다.
  const target = pageLeft + rect.left + rect.width / 2 - viewportWidth / 2;
  return Math.min(stackWidth - viewportWidth, Math.max(0, target));
}
