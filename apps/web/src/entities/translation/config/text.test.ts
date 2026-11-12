// 영문번역 화면 글(밴드 TRW0a ②): 파트 이름 셋·오류 글 키가 다 있고 빈 글이 없다. 값을 끼우는 글은 값을 넣는다.
import { describe, expect, it } from 'vitest';

import { TR_TEXT } from './text.ts';

// 문구 표는 아무것도 가져오지 않는다(시험도 — app/guards/layers.test.ts). 파트 열쇠는 model 의 PART_KEYS 와 같은 셋.
const PART_KEYS = ['ceo', 'story', 'general'] as const;

/** 고정 글(값을 끼우는 함수 글은 아래 시험이 따로 본다)을 모두 모은다. */
function allTexts(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (value && typeof value === 'object')
    return Object.values(value).flatMap(allTexts);
  return [];
}

/** 방향 뜻의 「쪽」(결정 sid:MARC-ENT-459 — 그대로 둔다). 「뒤쪽」은 「앞쪽」과 같은 방향 말(밴드 TRW6 ③ — 6c v174 경고 글, 감독 답 10-29). */
const DIRECTION = /(왼|오른|위|아래|안|바깥|뒤|가까운 |먼 )쪽/g;
/** 함수 글을 부를 대표 인자: 수 하나와 수 배열(이름 묶음·쪽 목록 자리도 받는다). */
const SAMPLE_ARGS: readonly unknown[] = [5, [5, 9]];

/** 고정 글과 함수 글(대표 인자마다 불러 본 결과)을 모두 모은다(밴드 TRW4 전수 검사). */
function allRendered(value: unknown): string[] {
  if (typeof value === 'function')
    return SAMPLE_ARGS.flatMap((arg) => {
      try {
        return allRendered(value(...Array<unknown>(value.length).fill(arg)));
      } catch {
        return [];
      }
    });
  if (typeof value === 'string') return [value];
  if (value && typeof value === 'object')
    return Object.values(value).flatMap(allRendered);
  return [];
}

describe('TR_TEXT', () => {
  it('파트 셋마다 이름·자리 글', () => {
    for (const part of PART_KEYS) {
      expect(TR_TEXT.parts.names[part].trim()).not.toBe('');
      expect(TR_TEXT.range.placeholder[part].trim()).not.toBe('');
    }
  });

  it('오류 글 키가 다 있고 값을 끼운다', () => {
    expect(TR_TEXT.range.errors.comma.trim()).not.toBe('');
    expect(TR_TEXT.range.errors.overLast(150, 64)).toBe(
      '150페이지는 문서의 마지막 페이지(64페이지)를 넘어요',
    );
    expect(TR_TEXT.range.errors.ceoOverLimit(6)).toBe(
      'CEO 메시지는 최대 6페이지예요. CEO 메시지 파트를 맞게 골랐는지 확인해 주세요.',
    );
    expect(TR_TEXT.range.errors.order(3, 1)).toBe(
      '3~1페이지는 앞 페이지 번호가 뒤 페이지보다 커요',
    );
    expect(TR_TEXT.range.errors.zero.trim()).not.toBe('');
    expect(TR_TEXT.range.errors.notNumber('abc')).toBe(
      '「abc」는 읽을 수 없어요. 숫자와 ~ 로 넣어 주세요',
    );
  });

  it('고정 글에 빈 글이 없다', () => {
    const texts = allTexts(TR_TEXT);
    expect(texts.length).toBeGreaterThan(30);
    for (const text of texts) expect(text.trim()).not.toBe('');
  });

  // 밴드 TRW4(결정 sid:MARC-ENT-459): 쪽수 단위는 「페이지」 — 함수 글은 대표 인자(수 하나 · 수 배열)로 불러 본다. 방향 「쪽」만 남는다.
  it('전수 검사: 고정 글·함수 글에 쪽수 단위 「쪽」이 없다', () => {
    const texts = allRendered(TR_TEXT);
    expect(texts.length).toBeGreaterThan(200);
    for (const text of texts) {
      expect(text).not.toMatch(/\d쪽|쪽 칸|가운데 쪽/);
      expect(text.replace(DIRECTION, '')).not.toContain('쪽');
    }
  });

  it('단계 줄 실패 값은 개수(마크스폰 댓글 — 밴드 TRW4): 「실패한 페이지 2개」', () => {
    expect(TR_TEXT.result.stepValues.failedPages(2)).toBe('실패한 페이지 2개');
  });

  it('검수 이슈 주석은 개수(디자인 N3 — 밴드 TRW5): 한 스타일 「12개」, 견주기 「12개 / 11개」', () => {
    expect(TR_TEXT.stats.notes.issuesBasis(12)).toBe(
      '자동 수정 전 글 기준 · 자동 수정한 페이지 12개',
    );
    expect(TR_TEXT.stats.notes.issuesBasis([12, 11])).toBe(
      '자동 수정 전 글 기준 · 자동 수정한 페이지 12개 / 11개',
    );
  });

  it('불러오기 글(CM-03 꼴, TRP1 W6): 없음은 두 문장, 실패 둘은 그대로', () => {
    expect(TR_TEXT.run.missing).toBe(
      '번역을 찾을 수 없어요. 목록에서 다시 골라 주세요',
    );
    expect(TR_TEXT.run.loadFailed).toBe('번역을 불러오지 못했어요');
    expect(TR_TEXT.run.resultFailed).toBe('결과를 불러오지 못했어요');
  });

  it('값 끼우기: 겹침 줄·번역할 쪽·쪽 칸 이름', () => {
    expect(
      TR_TEXT.range.overlapRow(35, [
        TR_TEXT.range.overlapWith('7~8', 'CEO 메시지와'),
      ]),
    ).toBe('총 35페이지 · 7~8페이지는 CEO 메시지와 겹침');
    expect(TR_TEXT.range.total(41, 64, ['CEO 메시지', '스토리'])).toBe(
      '번역할 페이지 41개 / 총 64페이지 · 파트 2개라 번역을 2번 해요(CEO 메시지 · 스토리).',
    );
    expect(TR_TEXT.grid.cellLabel(3, ['CEO 메시지'])).toBe(
      '3페이지, CEO 메시지',
    );
    expect(TR_TEXT.grid.cellLabel(9, [])).toBe('9페이지');
  });

  // TRW0b: 이름 묶음 조사(그린워싱 fieldMeta 꼴)·글 갈래 키.
  it('이름 묶음 조사: 하나 · 둘 · 셋', () => {
    expect(TR_TEXT.parts.withNames(['일반'])).toBe('일반과');
    expect(TR_TEXT.parts.withNames(['CEO 메시지', '일반'])).toBe(
      'CEO 메시지와 일반과',
    );
    expect(TR_TEXT.parts.withNames(['CEO 메시지', '스토리', '일반'])).toBe(
      'CEO 메시지, 스토리와 일반과',
    );
  });

  it('상태·까닭·이슈 유형 키가 다 있고 「비용」 말이 없다', () => {
    for (const key of [
      'done',
      'running',
      'queued',
      'failed',
      'failed_partial',
    ] as const)
      expect(TR_TEXT.state.tab[key].trim()).not.toBe('');
    expect(Object.keys(TR_TEXT.issues.types)).toHaveLength(10);
    expect(allTexts(TR_TEXT).join('\n')).not.toMatch(/비용/);
    expect(TR_TEXT.all.archiveMissing(2)).toBe(
      '2개 파일을 넣지 못했어요. 받은 zip 에 없는 파트는 아래 표의 [Word]로 받아 주세요',
    );
  });
});

// [TRW1a ② 감독 판단 4 ⓐ] 일부 파트만 시작한 띠 — 실제 파트 이름, 여럿이면 「 · 」, 조사는 마지막 이름 받침(은/는).
describe('partialStart 조사', () => {
  it('CEO 메시지(받침 없음)는 「는」', () => {
    expect(TR_TEXT.partialStart(['CEO 메시지'], ['스토리'])).toBe(
      'CEO 메시지는 시작했고, 스토리는 시작하지 못했어요. 페이지 범위를 확인해 새로 번역해 주세요.',
    );
  });
  it('스토리(받침 없음)는 「는」, 여럿은 「·」로 잇는다', () => {
    expect(TR_TEXT.partialStart(['스토리', 'CEO 메시지'], ['일반'])).toBe(
      '스토리·CEO 메시지는 시작했고, 일반은 시작하지 못했어요. 페이지 범위를 확인해 새로 번역해 주세요.',
    );
  });
  it('일반(받침 있음)은 「은」', () => {
    expect(TR_TEXT.partialStart(['일반'], ['CEO 메시지', '스토리'])).toBe(
      '일반은 시작했고, CEO 메시지·스토리는 시작하지 못했어요. 페이지 범위를 확인해 새로 번역해 주세요.',
    );
  });
});

// 밴드 TRC1 §3-5-11 → 밴드 WT1(sid:MARC-ENT-625, 시안 v233 TR-01·01a): 목록 머리 설명 줄은 운영 관리자의 「작업 회사 {company}」만.
describe('TR_TEXT.list.metaOperator (TRC1 → WT1)', () => {
  const words = TR_TEXT.list;
  it('「작업 회사 {company}」 하나 — 셈·안내 조각 0, 일반 사용자 꼴(meta) 0', () => {
    expect(words.metaOperator('고객사 A')).toBe('작업 회사 고객사 A');
    expect('meta' in words).toBe(false);
  });
});

// 밴드 WT1(sid:MARC-ENT-625, 시안 v233 · 영문번역 0f 답 sid:MARC-TICK-223): 낱말 맞춤과 지운 줄.
describe('TR_TEXT 글 맞춤 (WT1)', () => {
  it('텍스트 선택이 가능한 PDF · 텍스트가 없는 PDF', () => {
    expect(TR_TEXT.pdfNew.upload.noText).toBe(
      '텍스트가 없는 PDF 예요(스캔본) · 텍스트 선택이 가능한 PDF 로 올려 주세요',
    );
    expect(TR_TEXT.failure.pdf.noText).toBe(TR_TEXT.pdfNew.upload.noText);
    expect(TR_TEXT.failure.pdf.unreadable).toBe(
      'PDF 를 읽지 못했어요. 텍스트 선택이 가능한 PDF 인지 확인하고 다시 올려 주세요',
    );
    expect(TR_TEXT.pdfNew.upload.formats).toBe(
      '텍스트 선택이 가능한 PDF 여야 해요 · 스캔한 그림뿐인 페이지는 번역하지 못해요 · 암호가 걸린 PDF 는 받지 않아요 · .pdf 한 개',
    );
  });
  it('목록 열 「담당자」 · 「마지막 시작」 그대로', () => {
    expect(TR_TEXT.list.columns.uploader).toBe('담당자');
    expect(TR_TEXT.list.columns.started).toBe('마지막 시작');
  });
  it('진행 안심 줄(caution) 지움 · 「이 창을 닫아도 번역은 계속돼요」 그대로', () => {
    expect('caution' in TR_TEXT.stage).toBe(false);
    expect(TR_TEXT.stage.keepsRunning).toBe('이 창을 닫아도 번역은 계속돼요');
  });
  it('0f 답 셋: 과정 설명 괄호 지움 · 범위 카드 lead 지움 · 참고 문체 help 한 마디', () => {
    expect(TR_TEXT.stage.body.translate).toBe(
      '파트 문체로 페이지마다 옮기고 다듬은 뒤, 용어집 반영 검사·번역 검수(QA)를 하고 이슈가 있는 페이지만 자동 수정해요 · A·B 비교면 문체마다 한 번씩 돌아요',
    );
    expect('lead' in TR_TEXT.range).toBe(false);
    expect(TR_TEXT.newTranslation.peer.help).toBe(
      '용어집이 이 글보다 먼저예요',
    );
  });
  it('옛 낱말이 남지 않는다(「글자를 고를」·「글자가 없는 PDF」·「올린 사람」·「몇 페이지를 못 옮겨도」·「(AI 를 쓰지 않음)」)', () => {
    expect(JSON.stringify(TR_TEXT)).not.toMatch(
      /글자를 고를|글자가 없는 PDF|올린 사람|몇 페이지를 못 옮겨도|\(AI 를 쓰지 않음\)|계정이 시작한 번역/,
    );
  });
});
