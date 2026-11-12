// 데이터 검증 화면 글(밴드 DV2a ①): 빈 글이 없고(계산 계획·계산 검토 대기 글은 ③ 에서 판 DV-02 글로 채움), 값을 끼우는 글은 값을 넣는다. 「비용」 0.
import { describe, expect, it } from 'vitest';

import { DV_TEXT } from './text.ts';

// 문구 표는 아무것도 가져오지 않는다(시험도 — app/guards/layers.test.ts).
function allTexts(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (value && typeof value === 'object')
    return Object.values(value).flatMap(allTexts);
  return [];
}

describe('DV_TEXT', () => {
  it('빈 글이 없다(계산 계획·계산 검토 대기 글은 판 DV-02 검사 내용 글 — ③)', () => {
    const empty = allTexts(DV_TEXT).filter((text) => text.trim() === '');
    expect(empty).toHaveLength(0);
    expect(DV_TEXT.newCheck.checks[0]![1]).toBe(
      DV_TEXT.status.stepText.plan.pending,
    );
    expect(DV_TEXT.newCheck.checks[1]![1]).toContain(
      DV_TEXT.status.stepText.review.pending.replace(/요$/, ''),
    );
  });

  it('판정 허용 오차 0 — DV-00 검사 종류 표 · 검사 내용 단계(밴드 DV16, sid:MARC-ENT-685)', () => {
    const rows = DV_TEXT.intro.table.rows;
    expect(rows[0]!.slice(0, 2)).toEqual([
      '맞음',
      '산식 양쪽의 차이가 0 인 검사',
    ]);
    expect(rows[1]!.slice(0, 2)).toEqual([
      '어긋남',
      '산식 양쪽의 차이가 0 이 아닌 검사 · 아주 작은 차이도 어긋남이에요',
    ]);
    expect(DV_TEXT.newCheck.checks[1]).toEqual([
      '계산 검토',
      '산식마다 연도별 값을 찾아 계산 도구로 맞는지 봐요. 차이가 0 이면 맞음, 0 이 아니면 어긋남이에요',
    ]);
    const all = allTexts(DV_TEXT).join('\n');
    expect(all).not.toContain('빠질 때');
  });

  it('「비용」·서버 갈래 이름 0', () => {
    const all = allTexts(DV_TEXT).join('\n');
    expect(all).not.toContain('비용');
    for (const kind of ['unparsable', 'budget_exceeded', 'provider_error'])
      expect(all).not.toContain(kind);
  });

  it('셸 글은 영문번역 셸과 같고 제목만 「데이터 검증」', () => {
    expect(DV_TEXT.shell.title).toBe('데이터 검증');
    expect(DV_TEXT.shell.menu.validation).toBe('데이터 검증');
  });

  it('값을 끼운다', () => {
    expect(DV_TEXT.yearSpan(['2022', '2023', '2024'])).toBe('2022~2024년');
    expect(DV_TEXT.yearSpan(['2024'])).toBe('2024년');
    expect(DV_TEXT.yearSpan([])).toBe('–');
    expect(DV_TEXT.orDash(null)).toBe('–');
    expect(DV_TEXT.newCheck.preview(12, 4, '2022~2024년')).toBe(
      '검증은 테마 「환경」의 항목만 해요 · 환경 12항목(핵심데이터 4) · 2022~2024년',
    );
    expect(DV_TEXT.newCheck.fileLine(3, 41, '0.2MB')).toBe(
      '테마 3개 · 항목 41개 · 0.2MB',
    );
    expect(DV_TEXT.result.cards.uncomputableSub(1, 1, 2)).toBe(
      '수가 아닌 값 1 · 0으로 나눔 1 · 도구가 답을 못 냄 2',
    );
    expect(DV_TEXT.result.cards.uncomputableSub(0, 0, 2)).toBe(
      '도구가 답을 못 냄 2',
    );
    // 펼침 차이 줄(밴드 DV6 ①) — 음수 차이 · 비율은 %p
    expect(
      DV_TEXT.result.explainRows.diffValue('-5.0', 'value', '1.1', false),
    ).toBe('-5.0 · 허용 오차 1.1 넘음');
    expect(
      DV_TEXT.result.explainRows.diffValue('1.0', 'percent', '1.1', true),
    ).toBe('1.0%p · 허용 오차 1.1%p 안');
    // 차이 단위(밴드 DV10): 값은 대상 단위를 차이 뒤에만(허용 오차 값 0) · 빈 칸·null 은 수만 · 비율은 단위가 와도 %p 만
    expect(
      DV_TEXT.result.explainRows.diffValue(
        '5.0',
        'value',
        '0.01',
        false,
        'tCO2eq',
      ),
    ).toBe('5.0 tCO2eq · 허용 오차 0.01 넘음');
    expect(
      DV_TEXT.result.explainRows.diffValue('5.0', 'value', '0.01', false, ''),
    ).toBe('5.0 · 허용 오차 0.01 넘음');
    expect(
      DV_TEXT.result.explainRows.diffValue('5.0', 'value', '0.01', true, null),
    ).toBe('5.0 · 허용 오차 0.01 안');
    expect(
      DV_TEXT.result.explainRows.diffValue('1.0', 'percent', '1.1', true, '%'),
    ).toBe('1.0%p · 허용 오차 1.1%p 안');
    expect(DV_TEXT.result.explainRows.percent('25.0000')).toBe('25.0000%');
    // 표 머리의 허용 오차는 AI 가 검산마다 정하고 안 주면 기본값(밴드 DV4·DV14, sid:MARC-ISSUE-365 (가)·sid:MARC-ISSUE-648)
    expect(DV_TEXT.result.checksLead('1.1')).toBe(
      '허용 오차는 AI 가 검산마다 정하고, 정하지 않은 검산은 기본값(1.1)을 써요 · 항목 단위, 비율은 %p',
    );
    expect(DV_TEXT.result.checksLeadFailed(3, '1.1')).toBe(
      '실패 전까지 검산 3곳 · 허용 오차는 AI 가 검산마다 정하고, 정하지 않은 검산은 기본값(1.1)을 써요 · 항목 단위, 비율은 %p',
    );
    // 판정 허용 오차 0 인 실행(새 실행 "0.0" · 수로 0 인 "0"): 머리는 0 규칙, 차이 칸은 차이만(밴드 DV16, sid:MARC-ENT-685)
    for (const zero of ['0.0', '0', '-0.0']) {
      expect(DV_TEXT.result.checksLead(zero)).toBe(
        '차이가 0 이 아니면 어긋남이에요 · 항목 단위, 비율은 %p',
      );
      expect(DV_TEXT.result.checksLeadFailed(3, zero)).toBe(
        '실패 전까지 검산 3곳 · 차이가 0 이 아니면 어긋남이에요 · 항목 단위, 비율은 %p',
      );
      expect(
        DV_TEXT.result.explainRows.diffValue(
          '5.0',
          'value',
          zero,
          false,
          'tCO2eq',
        ),
      ).toBe('5.0 tCO2eq');
      expect(
        DV_TEXT.result.explainRows.diffValue('0.0', 'value', zero, true, null),
      ).toBe('0.0');
      expect(
        DV_TEXT.result.explainRows.diffValue('-0.5', 'percent', zero, false),
      ).toBe('-0.5%p');
    }
    // 빈 글은 0 으로 보지 않는다(Number('') === 0 함정)
    expect(DV_TEXT.result.checksLead('')).toContain('기본값()');
    // 「빠지면」은 뜻이 안 보여 뺐고 기본값 숫자는 남는다(컨설턴트 댓글 11-10, 밴드 DV14, sid:MARC-ISSUE-648)
    for (const lead of [
      DV_TEXT.result.checksLead('2.5'),
      DV_TEXT.result.checksLeadFailed(1, '2.5'),
    ]) {
      expect(lead).not.toContain('빠지면');
      expect(lead).toContain('정하지 않은 검산은 기본값(2.5)을 써요');
    }
    expect(
      DV_TEXT.status.checkPlaces([
        '계산 검토가 일찍 끝났어요',
        '리스크 진단을 못 했어요',
      ]),
    ).toBe('확인할 곳 — 계산 검토가 일찍 끝났어요 · 리스크 진단을 못 했어요');
    expect(
      DV_TEXT.status.doneLine('10:58', {
        plan: 2,
        places: 5,
        ok: 2,
        mismatches: 1,
        uncomputable: 2,
        risks: null,
      }),
    ).toBe(
      '10:58 끝남 · 산식 2개 · 검산 5곳(맞음 2 · 어긋남 1 · 계산 못 함 2) · 리스크 –',
    );
    expect(
      DV_TEXT.status.doneLine('10:58', {
        plan: null,
        places: 0,
        ok: 0,
        mismatches: 0,
        uncomputable: 0,
        risks: 3,
      }),
    ).toBe(
      '10:58 끝남 · 검산 0곳(맞음 0 · 어긋남 0 · 계산 못 함 0) · 리스크 3건',
    );
    expect(DV_TEXT.status.doneLine('10:58', null)).toBe('10:58 끝남');
    expect(DV_TEXT.result.cards.checks).toBe('검산');
    expect(DV_TEXT.result.cards.checksValue(5)).toBe('5곳');
    // 요약 카드 다섯 칸의 단위 · 밑 글(시안 v212 DV-04 r2, 밴드 DV7)
    expect(DV_TEXT.result.cards.checksSub).toBe('맞음 + 어긋남 + 계산 못 함');
    expect(DV_TEXT.result.cards.ok).toBe('맞음');
    expect(DV_TEXT.result.cards.okValue(1)).toBe('1곳');
    // 숫자 칸 밑 글 · 문제 없음 글: 판정 허용 오차 0 인 실행은 「차이」, 옛 실행은 옛 글(밴드 DV16, sid:MARC-ENT-685)
    expect(DV_TEXT.result.cards.okSub('0.0')).toBe('차이 0');
    expect(DV_TEXT.result.cards.okSub('0')).toBe('차이 0');
    expect(DV_TEXT.result.cards.okSub('1.1')).toBe('허용 오차 안');
    expect(DV_TEXT.result.cards.mismatchesSub('0.0')).toBe('차이가 있는 연도');
    expect(DV_TEXT.result.cards.mismatchesSub('1.1')).toBe(
      '허용 오차를 넘은 연도',
    );
    expect(DV_TEXT.result.noProblems('0.0')).toBe(
      '어긋남과 계산 못 함이 없어요. 모든 검사의 차이가 0 이에요',
    );
    expect(DV_TEXT.result.noProblems('1.1')).toBe(
      '어긋남과 계산 못 함이 없어요. 모든 검사가 허용 오차 안에서 맞았어요',
    );
    expect(DV_TEXT.result.cards.units).toEqual({
      checks: '곳',
      ok: '곳',
      mismatches: '곳',
      uncomputable: '곳',
      risks: '건',
    });
    // 실패 띠(DV-04a r2) — 「검산한 n곳은」
    expect(DV_TEXT.notices.review_failed.band(2)).toBe(
      '계산 검토를 끝내지 못했어요 · AI 호출이 실패했어요. 실패 전까지 검산한 2곳은 아래에 있고 엑셀에도 담겨요. 리스크 진단은 데이터와 기업 정보만 보고 따로 정리했어요. 다시 실행하면 새 실행으로 처음부터 봐요.',
    );
    expect(DV_TEXT.result.cards.mismatchesValue(1)).toBe('1곳');
    expect(DV_TEXT.result.cards.uncomputableValue(4)).toBe('4곳');
    expect(
      DV_TEXT.result.items.sumRaw({ kind: 'text', text: '1500' }, [
        { kind: 'text', text: '1200.5' },
        { kind: 'na' },
      ]),
    ).toEqual(['더한 값 1200.5 + 값 없음 ≈ 대상 1500']);
  });

  it('plan 단계의 화면 이름은 「계산 계획」 · 「계산 Plan」 0 — 엑셀 시트 이름도 「계산 계획」(DV2c → 밴드 DV17)', () => {
    expect(DV_TEXT.newCheck.checks[0]![0]).toBe('계산 계획');
    expect(DV_TEXT.result.stageNames.plan).toBe('계산 계획');
    expect(DV_TEXT.result.planTitle).toBe('계산 계획');
    expect(DV_TEXT.notices.plan_partial.short).toBe(
      '계산 계획이 다 마치기 전에 멈췄어요',
    );
    expect(DV_TEXT.notices.plan_failed.short).toBe('계산 계획을 못 했어요');
    expect(
      allTexts(DV_TEXT).filter((text) => text.includes('계산 Plan')),
    ).toEqual([]);
    expect(
      allTexts(DV_TEXT).filter((text) => text.includes('시트 7개')),
    ).toEqual([
      '시트 7개: 요약 · 계산 계획 · 검증 결과 · 검토 글 · 리스크 · 출처 · 설정',
    ]);
    expect(DV_TEXT.result.downloads.reportNote).toBe(
      'AI 데이터 검증 결과물 — 검증 결과와 리스크 표를 담은 엑셀이에요',
    );
  });

  it('낱말 통일(밴드 DV17): 「인사이트」·「AI 가 쓴 글 그대로」·「AI 가 쓴 표」·「JSON(.json)도」·「14열」 0 · 「리스크 진단」 · 「AI 생성」', () => {
    const texts = allTexts(DV_TEXT);
    for (const old of [
      '인사이트',
      'AI 가 쓴 글 그대로',
      'AI 가 쓴 표',
      'JSON(.json)도',
      '14열',
    ])
      expect(texts.filter((text) => text.includes(old))).toEqual([]);
    expect(DV_TEXT.result.stageNames.insight).toBe('리스크 진단');
    expect(DV_TEXT.status.stepNames.insight).toBe('리스크 진단');
    expect(DV_TEXT.result.cards.risksSub).toBe('리스크 진단 표');
    expect(DV_TEXT.result.risksTitle).toBe('리스크 진단');
    expect(DV_TEXT.result.cards.risks).toBe('리스크');
    expect(DV_TEXT.result.risksLead).toBe('리스크 진단 · AI 생성');
    expect(DV_TEXT.result.reviewLead).toBe('계산 검토 · AI 생성');
    expect(DV_TEXT.notices.insight_partial.short).toBe(
      '리스크 진단이 다 마치기 전에 멈췄어요',
    );
    expect(DV_TEXT.notices.insight_failed.short).toBe(
      '리스크 진단을 못 했어요',
    );
    expect(DV_TEXT.result.planHead).toEqual(['산식']);
    expect(DV_TEXT.result.checksHead).not.toContain('순번');
  });

  it('「최대 횟수」「정해진 횟수」 0 — 글과 글을 짓는 함수의 몸 모두(밴드 DV6 ③, 횟수 상한은 사용자에게 말하지 않는다)', () => {
    const sources = (value: unknown): string[] =>
      typeof value === 'string' || typeof value === 'function' ? [String(value)]
      : value && typeof value === 'object' ?
        Object.values(value).flatMap(sources)
      : [];
    const all = sources(DV_TEXT).join('\n');
    expect(all).toContain('다 마치기 전에 멈췄어요');
    for (const word of ['최대 횟수', '정해진 횟수'])
      expect(all).not.toContain(word);
    expect(DV_TEXT.result.partialTag).toBe('다 마치기 전에 멈춤');
  });

  it('파일 이름 꼴 밖 오류 글(DV2c)', () => {
    expect(DV_TEXT.newCheck.errors.badName).toBe(
      '파일 이름에 쓸 수 없는 글자가 있거나 너무 길어요 · 이름을 고쳐 다시 올려 주세요',
    );
  });

  it('엑셀 입력 글(DVX1 ②): 엑셀이 먼저 · 값을 끼운다 · 서버 kind 이름은 글에 0', () => {
    const w = DV_TEXT.newCheck;
    expect(w.dropTitle.indexOf('엑셀')).toBeGreaterThanOrEqual(0);
    // 끌어 놓기 안내는 엑셀 한 갈래(JSON 받기는 남음 — 오류 글 notJsonFile 그대로, 밴드 DV17)
    expect(w.dropHint).toBe('EDK 인벤토리 양식 그대로의 엑셀(.xlsx) 한 개');
    expect(w.templateHint).toBe(
      'EDK 인벤토리 양식 또는 이 양식에 맞춰 입력한 파일을 올려 주세요',
    );
    expect(w.errors.notJsonFile).toBe(
      '엑셀(.xlsx)이나 JSON(.json) 파일만 올릴 수 있어요',
    );
    expect(w.errors.xlsx.too_large).toBe(w.errors.fileTooLarge);
    expect(w.errors.xlsx.bad_cell(7)).toBe(
      '7행에 날짜나 참/거짓 칸이 있어요. 숫자나 글자로 바꿔 주세요',
    );
    expect(w.errors.xlsx.no_theme(9)).toBe('9행의 테마 칸이 비어 있어요');
    expect(w.errors.xlsx.too_many_rows(2000)).toBe(
      '항목이 너무 많아요. 2,000개 안의 파일만 올릴 수 있어요',
    );
    expect(w.errors.xlsx.long_cell(7, 3, 2000)).toBe(
      '7행 3열 칸의 글이 너무 길어요. 2,000자 안으로 줄여 주세요',
    );
    expect(w.skippedThemes(4, 17)).toBe(
      '검증에 쓰지 않는 테마 4개(항목 17개)는 빼고 읽었어요',
    );
    expect(w.yearFilled('2024')).toBe(
      '파일의 마지막 연도로 보고연도를 2024년으로 골랐어요',
    );
    const xlsxTexts = [
      ...allTexts(w.errors.xlsx),
      w.errors.xlsx.bad_cell(1),
      w.errors.xlsx.no_theme(1),
      w.errors.xlsx.too_many_rows(1),
    ].join('\n');
    for (const kind of [
      'not_xlsx',
      'unsafe_xlsx',
      'bad_header',
      'no_target_theme',
    ])
      expect(xlsxTexts).not.toContain(kind);
  });
});
