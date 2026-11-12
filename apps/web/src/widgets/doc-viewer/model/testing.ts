// 테스트가 쓰는 자료. 훅·헤드리스 컴포넌트·화면의 테스트가 같은 것을 쓴다.
import { parseViewerInput } from './contract.ts';
import type { ViewerInput } from './contract.ts';

export const TEST_PAGES = Array.from({ length: 5 }, () => ({
  width: 600,
  height: 800,
}));

function parsed(raw: unknown): ViewerInput {
  const result = parseViewerInput(raw);
  if (!result.ok) throw new Error(result.errors.join('\n'));
  return result.input;
}

/** 문서 둘(a, b)에 항목 셋. 항목 1 은 A 의 1쪽·B 의 4쪽, 항목 2 는 A 의 4쪽·B 의 1쪽, 항목 3 은 A 의 5쪽에만. */
export function makeTwoDocInput(): ViewerInput {
  return parsed({
    version: 1,
    documents: [
      { id: 'a', url: 'a.pdf', pages: TEST_PAGES },
      { id: 'b', url: 'b.pdf', pages: TEST_PAGES },
    ],
    highlights: [
      {
        id: '1-a',
        documentId: 'a',
        page: 1,
        box: [50, 50, 150, 80],
        kind: 'match',
      },
      {
        id: '1-b',
        documentId: 'b',
        page: 4,
        box: [50, 50, 150, 80],
        kind: 'match',
      },
      {
        id: '2-a',
        documentId: 'a',
        page: 4,
        box: [50, 300, 150, 330],
        kind: 'mismatch',
      },
      {
        id: '2-b',
        documentId: 'b',
        page: 1,
        box: [50, 300, 150, 330],
        kind: 'mismatch',
      },
      {
        id: '3-a',
        documentId: 'a',
        page: 5,
        box: [50, 300, 150, 330],
        kind: 'unverified',
      },
    ],
    items: [
      {
        id: '1',
        title: '첫째',
        highlightIds: ['1-a', '1-b'],
        review: { status: 'pending' },
      },
      {
        id: '2',
        title: '둘째',
        highlightIds: ['2-a', '2-b'],
        review: { status: 'pending' },
      },
      {
        id: '3',
        title: '셋째',
        highlightIds: ['3-a'],
        review: { status: 'pending' },
      },
    ],
  });
}

/** 같은 자리에 겹친 상자가 있는 자료: B 의 1쪽 한 칸을 항목 1(일치)과 항목 4(불일치)가 같이 가리킨다. 항목 5 는 따로. */
export function makeOverlapInput(): ViewerInput {
  return parsed({
    version: 1,
    documents: [{ id: 'b', url: 'b.pdf', pages: TEST_PAGES }],
    highlights: [
      {
        id: '1-b',
        documentId: 'b',
        page: 1,
        box: [50, 50, 150, 80],
        kind: 'match',
      },
      {
        id: '4-b',
        documentId: 'b',
        page: 1,
        box: [50, 50, 150, 80],
        kind: 'mismatch',
      },
      {
        id: '5-b',
        documentId: 'b',
        page: 1,
        box: [50, 300, 150, 330],
        kind: 'match',
      },
    ],
    items: [
      {
        id: '1',
        title: '첫째',
        highlightIds: ['1-b'],
        review: { status: 'pending' },
      },
      {
        id: '4',
        title: '넷째',
        highlightIds: ['4-b'],
        review: { status: 'pending' },
      },
      {
        id: '5',
        title: '다섯째',
        highlightIds: ['5-b'],
        review: { status: 'pending' },
      },
    ],
  });
}

/** A 의 2쪽에 두 줄짜리 문장 강조 s(상자 둘), 그것과 상자가 전부 같은 강조 t(다른 종류, 다른 항목), 한 줄짜리 u. */
export function makeLinesInput(): ViewerInput {
  const twoLines = [
    [300, 400, 500, 412],
    [50, 416, 220, 428],
  ];
  return parsed({
    version: 1,
    documents: [{ id: 'a', url: 'a.pdf', pages: TEST_PAGES }],
    highlights: [
      {
        id: 's-a',
        documentId: 'a',
        page: 2,
        box: [50, 380, 550, 450],
        innerBoxes: twoLines,
        kind: 'sentence',
      },
      {
        id: 't-a',
        documentId: 'a',
        page: 2,
        box: [50, 380, 550, 450],
        innerBoxes: twoLines,
        kind: 'note',
      },
      {
        id: 'u-a',
        documentId: 'a',
        page: 2,
        box: [50, 500, 550, 520],
        innerBox: [60, 500, 90, 512],
        kind: 'note',
      },
    ],
    items: [
      {
        id: 's',
        title: '두 줄 문장',
        highlightIds: ['s-a'],
        review: { status: 'pending' },
      },
      {
        id: 't',
        title: '같은 자리의 다른 항목',
        highlightIds: ['t-a'],
        review: { status: 'pending' },
      },
      {
        id: 'u',
        title: '한 줄',
        highlightIds: ['u-a'],
        review: { status: 'pending' },
      },
    ],
    kinds: [
      { kind: 'sentence', label: '문장', color: '#d97706' },
      { kind: 'note', label: '메모', color: '#2563eb' },
    ],
  });
}
