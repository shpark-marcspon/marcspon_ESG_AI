// 예시 PDF 둘에 무엇을 어디에 그리는가. 좌표는 뷰어의 입력 계약과 같다(포인트, 왼쪽 위 원점, 화면에 놓인 대로).
//
// marks: 색칠한 사각형. public/sample/compare.json 의 강조 상자와 자리가 같다.
//   브라우저 테스트는 캔버스에서 이 색을 읽어 「강조 상자가 놓인 자리에 정말 이 사각형이 그려져 있는가」를 본다.
//   (둘이 같은 자리인지는 tools/sample.test.ts 가 지킨다. 여기를 고치면 compare.json 도 고친다.)
//   같은 색의 표시를 변이 맞닿게 놓지 않는다(테스트가 「상자 바로 바깥은 그 색이 아니다」도 보기 때문이다).
import type { Box } from '../src/widgets/doc-viewer/model/index.ts';

export type Rgb = readonly [number, number, number]; // 0~255

export interface SampleText {
  x: number;
  /** 글자 윗변의 y. */
  top: number;
  size: number;
  str: string;
}

export interface SampleTable {
  box: Box;
  rows: string[][];
}

/** 여러 줄로 놓인 문단 하나. 줄마다 글 한 토막이다. 문단의 글은 줄을 빈칸 하나로 이은 것이다(문서를 분해하는 쪽이 그렇게 잇는다). */
export interface SampleParagraph {
  id: string;
  lines: SampleText[];
}

export interface SamplePage {
  /** 화면에 놓였을 때의 크기. rotate 가 90 이면 PDF 안에는 가로·세로가 바뀌어 적힌다. */
  width: number;
  height: number;
  /** PDF 에 적는 쪽 회전(/Rotate). */
  rotate: 0 | 90;
  marks: { box: Box; color: Rgb }[];
  texts: SampleText[];
  tables: SampleTable[];
  /** 글자마다의 자리까지 아는 문단(tools/sample-places.ts 가 글자 자리를 만든다). 없을 수 있다. */
  paragraphs?: SampleParagraph[];
}

// ── 글자의 폭 ──────────────────────────────────────────────────────────────
// 예시 PDF 는 PDF 기본 글꼴 Helvetica 로 쓴다(tools/pdf-writer.ts). 그 글꼴의 글자 폭(글자 크기 1000 기준)은 정해져 있다(Adobe 의 Helvetica AFM).
// 아래 문단에 나오는 글자만 적었다. 이 표로 「몇 번째 글자가 어디에 있는가」를 셈해 문장 강조의 상자를 만든다.
// 표가 맞는지는 두 곳에서 본다: tools/pdf-writer.test.ts(pdf.js 가 읽은 줄의 폭과 같은가), e2e/(그려진 글자의 잉크가 상자 안에 있는가).
const HELVETICA: Record<string, number> = {
  ' ': 278,
  '.': 278,
  ',': 278,
  '0': 556,
  '1': 556,
  '2': 556,
  '3': 556,
  '4': 556,
  '5': 556,
  '6': 556,
  '7': 556,
  '8': 556,
  '9': 556,
  R: 722,
  T: 611,
  W: 944,
  a: 556,
  b: 556,
  c: 500,
  d: 556,
  e: 556,
  f: 278,
  g: 556,
  h: 556,
  i: 222,
  l: 222,
  m: 833,
  n: 556,
  o: 556,
  p: 556,
  r: 333,
  s: 500,
  t: 278,
  u: 556,
  v: 500,
  w: 722,
  y: 500,
};

/** 글자 하나의 폭(포인트). 표에 없는 글자면 멈춘다(어림하지 않는다). */
export function glyphWidth(char: string, size: number): number {
  const width = HELVETICA[char];
  if (width === undefined)
    throw new Error(
      `sample-layout: 글자 "${char}" 의 폭을 모른다. HELVETICA 표에 더한다`,
    );
  return (width * size) / 1000;
}

export const MARK_GREEN: Rgb = [200, 240, 200];
export const MARK_RED: Rgb = [250, 205, 205];
export const MARK_GRAY: Rgb = [215, 215, 225];

const PORTRAIT = { width: 595, height: 842 };
const LANDSCAPE = { width: 842, height: 595 };

export const SAMPLE_A: SamplePage[] = [
  {
    ...PORTRAIT,
    rotate: 0,
    marks: [
      { box: [226, 114, 270, 136], color: MARK_GREEN }, // 문장 속 숫자 1,234
      { box: [372, 230, 522, 260], color: MARK_GREEN }, // 표 r1c2
      { box: [372, 260, 522, 290], color: MARK_RED }, // 표 r2c2
      { box: [222, 290, 372, 320], color: MARK_GREEN }, // 표 r3c1
    ],
    texts: [
      {
        x: 72,
        top: 72,
        size: 18,
        str: 'Sample report A (generated, not a real document)',
      },
      { x: 72, top: 120, size: 12, str: 'Total emissions in 2024 were' },
      { x: 234, top: 120, size: 12, str: '1,234' },
      { x: 272, top: 120, size: 12, str: 'tCO2e, down from 1,300 in 2023.' },
    ],
    tables: [
      {
        box: [72, 200, 522, 320],
        rows: [
          ['Item', '2023', '2024'],
          ['Scope 1', '1,300', '1,234'],
          ['Scope 2', '2,410', '2,300'],
          ['Total', '3,710', '3,534'],
        ],
      },
    ],
  },
  {
    ...PORTRAIT,
    rotate: 0,
    marks: [{ box: [222, 160, 372, 190], color: MARK_GREEN }], // 표 r2c1
    texts: [
      { x: 72, top: 72, size: 18, str: 'Energy' },
      {
        x: 72,
        top: 300,
        size: 12,
        str: 'We will be carbon neutral across all sites by 2030.',
      },
      {
        x: 72,
        top: 330,
        size: 12,
        str: 'All suppliers were audited last year.',
      },
      {
        x: 72,
        top: 360,
        size: 12,
        str: 'Renewable electricity share rose to 88.5 percent.',
      },
    ],
    // 두 줄짜리 문단. 둘째 문장이 첫 줄 중간에서 시작해 둘째 줄 중간에서 끝난다(문장 강조 예시 s4: 줄마다 상자 하나).
    paragraphs: [
      {
        id: 'p2-water',
        lines: [
          {
            x: 72,
            top: 420,
            size: 12,
            str: 'Water use fell in every region. Recycled water now covers 41.5 percent of',
          },
          {
            x: 72,
            top: 438,
            size: 12,
            str: 'process demand at the two largest plants. Targets for 2026 are unchanged.',
          },
        ],
      },
    ],
    tables: [
      {
        box: [72, 100, 522, 220],
        rows: [
          ['Item', '2024', 'Unit'],
          ['Electricity', '4,200', 'MWh'],
          ['Renewable share', '88.5', '%'],
          ['Gas', '310', 'MWh'],
        ],
      },
    ],
  },
  {
    // 쪽 자체가 돌아가 있는 경우(/Rotate 90). 화면에는 가로로 놓인다.
    ...LANDSCAPE,
    rotate: 90,
    marks: [{ box: [100, 80, 300, 140], color: MARK_GRAY }],
    texts: [],
    tables: [],
  },
];

export const SAMPLE_B: SamplePage[] = [
  {
    ...LANDSCAPE,
    rotate: 0,
    marks: [
      { box: [550, 180, 700, 210], color: MARK_GREEN }, // 표 r1c3
      { box: [550, 210, 700, 240], color: MARK_RED }, // 표 r2c3
      { box: [400, 240, 550, 270], color: MARK_GREEN }, // 표 r3c2
    ],
    texts: [
      {
        x: 100,
        top: 72,
        size: 18,
        str: 'Sample data book B (generated, not a real document)',
      },
    ],
    tables: [
      {
        box: [100, 150, 700, 270],
        rows: [
          ['Item', '2022', '2023', '2024'],
          ['Scope 1', '1,350', '1,300', '1,234'],
          ['Scope 2', '2,500', '2,410', '2,290'],
          ['Total', '3,850', '3,710', '3,524'],
        ],
      },
    ],
  },
  {
    ...LANDSCAPE,
    rotate: 0,
    marks: [{ box: [296, 94, 340, 116], color: MARK_GREEN }], // 문장 속 숫자 88.5
    texts: [
      {
        x: 100,
        top: 100,
        size: 12,
        str: 'Renewable electricity share (percent):',
      },
      { x: 304, top: 100, size: 12, str: '88.5' },
    ],
    tables: [],
  },
];

export const SAMPLE_FILES = {
  'sample-a.pdf': SAMPLE_A,
  'sample-b.pdf': SAMPLE_B,
} as const;
