// 중대성평가 화면 글(밴드 IRW1 ①): 빈 글이 없고, 값을 끼우는 글은 값을 넣는다. 진행 수·「1회차」·「비용」·websearch 0.
import { describe, expect, it } from 'vitest';

import { IR_TEXT } from './text.ts';

// 문구 표는 아무것도 가져오지 않는다(시험도 — app/guards/layers.test.ts).
function allTexts(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (typeof value === 'function') {
    const call = value as (...args: unknown[]) => unknown;
    // 토픽 이름 묶음을 받는 글(빈 토픽 안내 — 밴드 IRW1b J2)은 목록으로 부른다
    let out: unknown;
    try {
      out = call(1, 2, 3, 4, 5);
    } catch {
      out = call(['가', '나']);
    }
    return typeof out === 'string' ? [out] : [];
  }
  if (value && typeof value === 'object')
    return Object.values(value).flatMap(allTexts);
  return [];
}

describe('IR_TEXT', () => {
  it('빈 글이 없다', () => {
    expect(allTexts(IR_TEXT).filter((text) => text.trim() === '')).toEqual([]);
  });

  it('진행 수·「1회차」·「비용」·websearch·서버 갈래 이름 0', () => {
    // IR-00 재무 영향 뜻(IRW17 — 구분 표 줄 둘)에는 「비용」이 없어 뺄 글이 없다(옛 리스크 뜻 「매출 · 비용 · 자산」은 지웠다).
    const all = allTexts(IR_TEXT).join('\n');
    for (const word of ['토픽 4 /', '/ 6토픽', '1회차', '비용', 'websearch'])
      expect(all).not.toContain(word);
    for (const kind of ['unparsable', 'provider_error', 'not_run'])
      expect(all).not.toContain(kind);
  });

  it('셸 글은 데이터 검증 셸과 같은 꼴이고 제목만 「중대성평가」', () => {
    expect(IR_TEXT.shell.title).toBe('중대성평가');
    expect(IR_TEXT.shell.menu.materiality).toBe('중대성평가');
    expect(IR_TEXT.flow.items.map((i) => i.label)).toEqual([
      '기본 정보 입력',
      'IRO 도출',
      '결과',
    ]);
  });

  it('W7 「이 창을 닫아도…」는 돌 때만 · J2 빈 토픽 묶음(밴드 IRW1b)', () => {
    expect(
      IR_TEXT.status.startedLine('2026-10-19 14:02', '가상건설', '6', false),
    ).toBe('2026-10-19 14:02 시작 · 가상건설 · 토픽 6개');
    expect(IR_TEXT.result.shortlist.noControversy(['가상 A'])).toBe(
      '「가상 A」 토픽은 검색 기간 안에 찾은 컨트로버시가 없어요. 영향은 규제·정책과 기업 정보로만 정했어요.',
    );
    expect(IR_TEXT.result.shortlist.noControversy(['가상 A', '가상 B'])).toBe(
      '「가상 A」·「가상 B」 토픽은 검색 기간 안에 찾은 컨트로버시가 없어요. 영향은 규제·정책과 기업 정보로만 정했어요.',
    );
    expect(IR_TEXT.result.shortlist.noRegulation(['가상 A', '가상 B'])).toBe(
      '「가상 A」·「가상 B」 토픽은 검색 기간 안에 찾은 규제·정책이 없어요. 영향은 컨트로버시와 기업 정보로만 정했어요.',
    );
  });

  it('값을 끼운다(판 글)', () => {
    expect(
      IR_TEXT.status.startedLine('2026-10-19 14:02', '가상건설', '6'),
    ).toBe(
      '2026-10-19 14:02 시작 · 가상건설 · 토픽 6개 · 이 창을 닫아도 평가는 계속돼요',
    );
    expect(IR_TEXT.status.doneLine('2026-10-19 14:39', '18', '14')).toBe(
      '2026-10-19 14:39 · 환경·사회 영향 18 · 재무 영향 경로 14',
    );
    expect(IR_TEXT.status.undecided(11, 2)).toBe(
      '서브토픽 11개 가운데 2개는 영향을 정하지 못했어요. 나머지 결과는 볼 수 있고, 빠진 서브토픽은 결과 표에 「정하지 못함」으로 남아요.',
    );
    expect(
      IR_TEXT.result.meta(
        '2026-10-19 13:41',
        '6',
        '11',
        IR_TEXT.result.period('2024-01-01', '2026-10-19'),
        IR_TEXT.sector.non_financial,
      ),
    ).toBe(
      '2026-10-19 13:41 끝남 · 토픽 6 · 서브토픽 11 · 리서치 기간 2024-01-01 ~ 2026-10-19 · 비금융',
    );
    expect(
      IR_TEXT.result.undecided(
        11,
        2,
        [
          IR_TEXT.result.subtopicRef('안전보건', '협력회사 현장 안전'),
          IR_TEXT.result.subtopicRef('윤리경영', '공정거래'),
        ].join(IR_TEXT.result.refJoiner),
      ),
    ).toBe(
      '서브토픽 11개 가운데 2개(안전보건 › 협력회사 현장 안전, 윤리경영 › 공정거래)는 영향을 정하지 못했어요. 다시 실행하면 새 실행으로 리서치부터 다시 해요.',
    );
    expect(IR_TEXT.warnings.other(3)).toBe(
      'AI 답을 읽으며 정리한 곳이 3곳 있어요. 원문은 엑셀 RAW_JSON 시트에 있어요.',
    );
    expect(IR_TEXT.orDash(null)).toBe('–');
  });
});
