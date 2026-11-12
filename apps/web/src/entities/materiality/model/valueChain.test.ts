// 가치사슬 표 한 곳(밴드 IRW2 ② — 발주서 §3 시험 1). 붙여 넣기(열 이름 뗌·5열 아님·따옴표 칸·짝 없는 따옴표·CRLF·끝 빈 줄·물려받기·
// 건너뜀·행 번호·101행·긴 칸)와 서버 행, normalizeStage. 값은 전부 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import {
  VALUE_CHAIN_HEADER,
  VALUE_CHAIN_MAX_CHARS,
  blankValueChainRow,
  businessUnitCount,
  filledRows,
  normalizeStage,
  rowsFromPaste,
  rowsFromServer,
  splitPaste,
  stagelessRows,
} from './valueChain.ts';

const HEADER = VALUE_CHAIN_HEADER.join('\t');
const line = (...cells: string[]) => cells.join('\t');

describe('normalizeStage', () => {
  it('한국어 셋·코랩 영어 셋 → 서버 값(앞뒤 공백·대소문자 무시)', () => {
    expect(normalizeStage('업스트림')).toBe('upstream');
    expect(normalizeStage('  자체운영 ')).toBe('own operations');
    expect(normalizeStage('다운스트림')).toBe('downstream');
    expect(normalizeStage('Upstream')).toBe('upstream');
    expect(normalizeStage('OWN OPERATIONS')).toBe('own operations');
    expect(normalizeStage(' downstream')).toBe('downstream');
  });

  it('못 맞추면 null(빈 글·셋 밖)', () => {
    for (const text of ['', '  ', '중류', 'upstreams'])
      expect(normalizeStage(text), text).toBeNull();
  });

  it('안쪽 공백도 떼고 견준다(IRW3 — 「자체 운영」·「Own  Operations」·「업 스트림」)', () => {
    expect(normalizeStage('자체 운영')).toBe('own operations');
    expect(normalizeStage('Own  Operations')).toBe('own operations');
    expect(normalizeStage('업 스트림')).toBe('upstream');
    expect(normalizeStage('down\tstream')).toBe('downstream');
    expect(normalizeStage('ownoperations')).toBe('own operations');
  });

  it.each([
    ['own_operation', 'own operations'],
    ['own_operations', 'own operations'],
    ['own-operations', 'own operations'],
    ['Own Operation', 'own operations'],
    ['ownoperation', 'own operations'],
    ['OWN_OPERATIONS', 'own operations'],
    ['UPSTREAM', 'upstream'],
    ['UpStream', 'upstream'],
    ['up-stream', 'upstream'],
    ['DOWNSTREAM', 'downstream'],
    ['Down_Stream', 'downstream'],
    ['자체_운영', 'own operations'],
  ] as const)('밑줄·붙임표·단수도 받는다(IRW15 ②): %s → %s', (text, stage) => {
    expect(normalizeStage(text)).toBe(stage);
  });

  it.each([
    'own',
    'operations',
    'own operationss',
    'operation',
    '_',
    '-',
    'mid_stream',
    'upstream2',
  ])('받지 않는 꼴(IRW15 ②): %s → null', (text) => {
    expect(normalizeStage(text)).toBeNull();
  });

  it('붙여 넣기·서버 행이 같은 함수 — 둘 다 정규 값(IRW15 ②)', () => {
    const pasted = rowsFromPaste(
      line('가', '나', 'own_operations', '다', '라'),
    );
    expect(pasted.ok && pasted.rows[0]!.value_chain_stage).toBe(
      'own operations',
    );
    const read = rowsFromServer([
      {
        business_unit: '가',
        business_unit_description: '나',
        value_chain_stage: 'Own-Operation',
        stakeholder: '다',
        business_activity: '라',
      },
    ]);
    expect(read.ok && read.rows[0]!.value_chain_stage).toBe('own operations');
  });
});

describe('splitPaste', () => {
  it('탭·줄(\\n·\\r\\n), 끝 빈 줄은 뗀다', () => {
    expect(splitPaste('a\tb\r\nc\td\n\n\n')).toEqual([
      ['a', 'b'],
      ['c', 'd'],
    ]);
    expect(splitPaste('')).toEqual([]);
    expect(splitPaste('a\t')).toEqual([['a', '']]);
  });

  it('\\r 하나도 줄 끝 · \\r\\n 과 섞여도 · 따옴표 칸 뒤 \\r 도(IRW3)', () => {
    expect(splitPaste('a\tb\rc\td\r')).toEqual([
      ['a', 'b'],
      ['c', 'd'],
    ]);
    expect(splitPaste('a\r\nb\rc\nd')).toEqual([['a'], ['b'], ['c'], ['d']]);
    expect(splitPaste('"따옴\n칸"\rx')).toEqual([['따옴\n칸'], ['x']]);
  });

  it('따옴표 칸은 짝 따옴표까지 한 칸(""=")·줄바꿈·탭을 품는다(Q13)', () => {
    expect(splitPaste('"줄\n바뀐 "" 칸"\t"탭\t칸"\r\nx\ty')).toEqual([
      ['줄\n바뀐 " 칸', '탭\t칸'],
      ['x', 'y'],
    ]);
  });

  it('짝 따옴표 뒤가 탭·줄 끝·글 끝이 아니거나 짝이 없으면 따옴표째 글 그대로', () => {
    expect(splitPaste('"반"쪽\tb')).toEqual([['"반"쪽', 'b']]);
    expect(splitPaste('"닫히지 않음\tb')).toEqual([['"닫히지 않음', 'b']]);
    expect(splitPaste('말 "가운데" 따옴표\tb')).toEqual([
      ['말 "가운데" 따옴표', 'b'],
    ]);
  });
});

describe('rowsFromPaste', () => {
  it('첫 줄이 열 이름 다섯이면 뗀다 · 밸류체인은 서버 값 · 글은 trim', () => {
    const parsed = rowsFromPaste(
      [
        HEADER,
        line(' 가상 부문 ', '가상 시공', '자체운영', '근로자', '안전 관리'),
        line('가상 부문', '가상 조달', 'Upstream', '협력회사', '구매'),
      ].join('\n'),
    );
    expect(parsed).toEqual({
      ok: true,
      rows: [
        {
          business_unit: '가상 부문',
          business_unit_description: '가상 시공',
          value_chain_stage: 'own operations',
          stakeholder: '근로자',
          business_activity: '안전 관리',
        },
        {
          business_unit: '가상 부문',
          business_unit_description: '가상 조달',
          value_chain_stage: 'upstream',
          stakeholder: '협력회사',
          business_activity: '구매',
        },
      ],
    });
  });

  it('열 이름이 아닌 첫 줄은 행이다', () => {
    const parsed = rowsFromPaste(line('가', '나', '업스트림', '라', '마'));
    expect(parsed.ok && parsed.rows).toHaveLength(1);
  });

  it('칸 수가 5 아닌 첫 줄의 칸 수로 columns(건너뛰기 전)', () => {
    expect(rowsFromPaste(line('가', '나', '다', '라'))).toEqual({
      ok: false,
      error: 'columns',
      columns: 4,
    });
    expect(
      rowsFromPaste(
        [
          line('가', '나', '업스트림', '라', '마'),
          line('a', 'b', 'c', 'd', 'e', 'f'),
        ].join('\n'),
      ),
    ).toEqual({ ok: false, error: 'columns', columns: 6 });
    // 가운데 빈 줄은 뗀다(IRW3) — 칸 수를 세지 않는다
    expect(
      rowsFromPaste(
        [
          line('가', '나', '업스트림', '라', '마'),
          '',
          line('가', '나', '업스트림', '라', '마'),
        ].join('\n'),
      ),
    ).toMatchObject({ ok: true, rows: [{}, {}] });
  });

  it('칸이 다 공백뿐인 줄(앞·가운데·끝, 공백만·탭만)은 열 이름 줄을 떼기 전에 먼저 뗀다(IRW3)', () => {
    const parsed = rowsFromPaste(
      [
        '',
        '   ',
        HEADER,
        line('가', '나', '업스트림', '라', '마'),
        '\t\t\t\t',
        ' \t ',
        line('', '', '자체운영', '라2', '마2'),
        '',
        '  ',
      ].join('\r\n'),
    );
    expect(parsed).toEqual({
      ok: true,
      rows: [
        {
          business_unit: '가',
          business_unit_description: '나',
          value_chain_stage: 'upstream',
          stakeholder: '라',
          business_activity: '마',
        },
        {
          business_unit: '가',
          business_unit_description: '나',
          value_chain_stage: 'own operations',
          stakeholder: '라2',
          business_activity: '마2',
        },
      ],
    });
  });

  it('\\r 줄 끝 · 띄어 쓴 밸류체인도 같은 표(IRW3)', () => {
    expect(
      rowsFromPaste(
        [
          line('가', '나', '자체 운영', '라', '마'),
          line('가', '나', 'Own  Operations', '라', '마'),
        ].join('\r'),
      ),
    ).toMatchObject({
      ok: true,
      rows: [
        { value_chain_stage: 'own operations' },
        { value_chain_stage: 'own operations' },
      ],
    });
  });

  it('밸류체인·이해관계자·활동이 다 빈 행은 건너뛰고 행 번호는 건너뛴 행을 세지 않는다', () => {
    const parsed = rowsFromPaste(
      [
        line('가', '나', '업스트림', '라', '마'),
        line('빈 자리', '설명만', '', ' ', ''),
        line('바', '사', '다운스트림', '아', 'x'.repeat(201)),
      ].join('\n'),
    );
    expect(parsed).toEqual({
      ok: false,
      error: 'too_long',
      row: 2,
      column: 4,
      max: 200,
    });
  });

  it('사업 부문이 빈 행만 위 데이터 행에서 물려받는다(사업 내용도 비었으면 그것도 — Q4 ③ (나))', () => {
    const parsed = rowsFromPaste(
      [
        line('', '첫 행 설명', '업스트림', '가', '가'),
        line('부문 A', '설명 A', '업스트림', '나', '나'),
        line('', '', '자체운영', '다', '다'),
        line('', '새 설명', '다운스트림', '라', '라'),
        line('부문 B', '', '다운스트림', '마', '마'),
      ].join('\r\n'),
    );
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(
      parsed.rows.map((row) => [
        row.business_unit,
        row.business_unit_description,
      ]),
    ).toEqual([
      ['', '첫 행 설명'],
      ['부문 A', '설명 A'],
      ['부문 A', '설명 A'],
      ['부문 A', '새 설명'],
      ['부문 B', ''],
    ]);
  });

  it('못 맞춘 밸류체인은 행을 넣고 그 칸만 비운다', () => {
    const parsed = rowsFromPaste(
      [
        line('가', '나', '중류', '라', '마'),
        line('가', '나', '', '라', '마'),
      ].join('\n'),
    );
    expect(
      parsed.ok && parsed.rows.map((row) => row.value_chain_stage),
    ).toEqual(['', '']);
    expect(parsed.ok && stagelessRows(parsed.rows)).toEqual([1, 2]);
  });

  it('데이터 행 100 까지 받고 101 은 too_many_rows', () => {
    const rows = (n: number) =>
      Array.from({ length: n }, (_, i) =>
        line(`부문 ${i}`, '', '업스트림', '', ''),
      ).join('\n');
    const hundred = rowsFromPaste(rows(100));
    expect(hundred.ok && hundred.rows).toHaveLength(100);
    expect(rowsFromPaste(rows(101))).toEqual({
      ok: false,
      error: 'too_many_rows',
      row: 101,
    });
  });

  it('칸 글자 상한(50·200·20·50·200) — 꼭 그만큼은 받고 하나 넘으면 too_long', () => {
    expect(VALUE_CHAIN_MAX_CHARS).toEqual([50, 200, 20, 50, 200]);
    for (const [column, max] of VALUE_CHAIN_MAX_CHARS.entries()) {
      const cells = ['가', '나', '업스트림', '라', '마'];
      cells[column] = 'x'.repeat(max);
      expect(rowsFromPaste(line(...cells)).ok, `col ${column} ok`).toBe(true);
      cells[column] = 'x'.repeat(max + 1);
      expect(rowsFromPaste(line(...cells))).toEqual({
        ok: false,
        error: 'too_long',
        row: 1,
        column,
        max,
      });
    }
  });

  it('글자 수는 코드 포인트로 센다(서버 len() 과 같게 — 검증 2 m2): 이모지 50 은 받고 51 은 too_long', () => {
    const emoji = '\u{1F33F}';
    expect(
      rowsFromPaste(line(emoji.repeat(50), '', '업스트림', '', '')).ok,
    ).toBe(true);
    expect(
      rowsFromPaste(line(emoji.repeat(51), '', '업스트림', '', '')),
    ).toEqual({ ok: false, error: 'too_long', row: 1, column: 0, max: 50 });
  });

  it('열 이름 줄뿐·다 빈 행이면 no_rows', () => {
    expect(rowsFromPaste(HEADER)).toEqual({ ok: false, error: 'no_rows' });
    expect(rowsFromPaste(line('가', '나', '', '', ''))).toEqual({
      ok: false,
      error: 'no_rows',
    });
  });
});

describe('rowsFromServer', () => {
  it('밸류체인 글을 서버 값으로, 못 맞추면 그 칸만 비움 — 다른 칸은 그대로', () => {
    const parsed = rowsFromServer([
      {
        business_unit: '가',
        business_unit_description: '나',
        value_chain_stage: '자체운영',
        stakeholder: '다',
        business_activity: '라',
      },
      {
        business_unit: '가',
        business_unit_description: '나',
        value_chain_stage: '모름',
        stakeholder: '다',
        business_activity: '라',
      },
    ]);
    expect(
      parsed.ok && parsed.rows.map((row) => row.value_chain_stage),
    ).toEqual(['own operations', '']);
    expect(parsed.ok && parsed.rows[1]!.stakeholder).toBe('다');
  });

  it('빈 목록 no_rows · 101 행 too_many_rows', () => {
    expect(rowsFromServer([])).toEqual({ ok: false, error: 'no_rows' });
    const row = {
      business_unit: '',
      business_unit_description: '',
      value_chain_stage: '',
      stakeholder: '',
      business_activity: '',
    };
    expect(
      rowsFromServer(Array.from({ length: 101 }, () => row)),
    ).toMatchObject({
      ok: false,
      error: 'too_many_rows',
    });
  });
});

describe('businessUnitCount', () => {
  it('사업 부문 서로 다른 값 수(빈 글 뺌)', () => {
    const parsed = rowsFromPaste(
      [
        line('가', '', '업스트림', '', ''),
        line('가', '', '업스트림', '', ''),
        line('나', '', '업스트림', '', ''),
      ].join('\n'),
    );
    expect(parsed.ok && businessUnitCount(parsed.rows)).toBe(2);
  });
});

describe('filledRows · stagelessRows(IRW3 Q2)', () => {
  const row = (patch: Partial<ReturnType<typeof blankValueChainRow>>) => ({
    ...blankValueChainRow(),
    ...patch,
  });

  it('다섯 칸이 다 빈(공백뿐 포함) 행을 뺀다 · 하나라도 차면 남긴다', () => {
    const rows = [
      blankValueChainRow(),
      row({ business_unit: '  ' }),
      row({ stakeholder: '라' }),
      row({ value_chain_stage: 'upstream' }),
    ];
    expect(filledRows(rows)).toEqual([rows[2], rows[3]]);
    expect(filledRows([blankValueChainRow()])).toEqual([]);
  });

  it('밸류체인 빔은 다 빈 행을 빼고 · 번호는 화면 표의 번호 그대로', () => {
    const rows = [
      blankValueChainRow(),
      row({ business_unit: '가' }),
      blankValueChainRow(),
      row({ value_chain_stage: 'upstream', stakeholder: '라' }),
      row({ business_activity: '마' }),
    ];
    expect(stagelessRows(rows)).toEqual([2, 5]);
    expect(stagelessRows([blankValueChainRow(), blankValueChainRow()])).toEqual(
      [],
    );
  });
});
