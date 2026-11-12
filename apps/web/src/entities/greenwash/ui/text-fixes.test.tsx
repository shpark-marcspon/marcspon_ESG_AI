// @vitest-environment jsdom
// (밴드 FS1 ③: screen-fixes.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ⓪: FW1b 디자인 대조의 고칠 것과 sid:MARC-ISSUE-99 화면 고침. 글자는 문구 표(GW_TEXT) 값으로 단언한다.
// 실제 크기·색·스크롤은 e2e/greenwash.spec.ts 가 잰다(jsdom 에는 CSS 가 없다).
import { cleanup } from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { GW_TEXT } from '../config/text.ts';

afterEach(cleanup);

beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

/** PDF 를 열지 않는 openPdf(썸네일은 이 시험에서 그리지 않는다). */

const words = GW_TEXT.newCheck;

const status = GW_TEXT.status;

describe('문구 표 고침(디자인 대조 「지은 글 고칠 안」·서버 문장)', () => {
  it('쪽 범위 글: 거꾸로, 형식 오류의 조사(받침·숫자·그 밖)', () => {
    const range = words.parts.rangeError;
    expect(range.reversed(9, 3)).toBe(
      '9~3페이지는 앞 페이지 번호가 뒤 페이지보다 커요',
    );
    expect(range.not_number('가나')).toBe(
      '「가나」는 읽을 수 없어요. 숫자와 ~, 쉼표로 넣어 주세요',
    );
    expect(range.not_number('4쪽')).toBe(
      '「4쪽」은 읽을 수 없어요. 숫자와 ~, 쉼표로 넣어 주세요',
    );
    expect(range.not_number('4.5')).toMatch(/^「4\.5」는 /);
    expect(range.not_number('4~')).toMatch(/^「4~」은\(는\) /);
    expect(range.not_number('4.3')).toMatch(/^「4\.3」은 /);
    expect(words.problems.too_many_pages(320, 300)).toBe(
      '총 320페이지 문서예요. 최대 300페이지까지 점검할 수 있어요',
    );
  });

  it('사용자 결정 글은 시안 글자 그대로(감독 R1. 정리 글은 v76 — 발주서 덧붙임 2)', () => {
    // v115 GW-03 r3 「멈춤 · 오류」 카드 글(밴드 GW2R ②). 덧글(failureNote)은 걷었다(디자인 답 D4)
    expect(status.failure).toBe(
      '점검을 끝내지 못했어요. [다시 실행]을 누르면 같은 파일로 처음부터 다시 점검해요.',
    );
    expect(status).not.toHaveProperty('failureNote');
    expect(status.stages.summarize.body).toBe(
      '그린워싱 리스크 단어 빈도를 세고, 그린워싱 리스크 문장의 위치를 찾아 결과를 묶어요',
    );
    expect(status.rerun).toBe('다시 실행');
    expect(GW_TEXT.review.positionMissing).toBe(
      '이 문장은 페이지에서 자리를 찾지 못해 페이지로만 이동했어요',
    );
  });

  it('GW-03 meta 는 돌고 있을 때만 「이 창을 닫아도…」', () => {
    expect(status.meta('t', 4)).toContain('이 창을 닫아도');
    expect(status.meta('t', 4, false)).toBe('t 시작 · 점검할 페이지 4개');
  });
});

// 밴드 GW2R ②(발주서 §3 A): GW-03 r3·GW-04 r2·GW-05 r2 글 꼴(판 그대로).
describe('GW-03·04 글 꼴(v115 판 그대로)', () => {
  const status = GW_TEXT.status;
  it('끝남 meta: 둘 다 있으면 「… 끝남 · n개의 그린워싱 리스크 문장을 찾았어요」, 하나만이면 그 토막, 둘 다 없으면 null', () => {
    expect(status.doneMeta('2026-10-15 14:52', 22)).toBe(
      '2026-10-15 14:52 끝남 · 22개의 그린워싱 리스크 문장을 찾았어요',
    );
    expect(status.doneMeta('2026-10-15 14:52', null)).toBe(
      '2026-10-15 14:52 끝남',
    );
    expect(status.doneMeta(null, 22)).toBe(
      '22개의 그린워싱 리스크 문장을 찾았어요',
    );
    expect(status.doneMeta(null, null)).toBeNull();
  });
  it('끝남 인식 실패 페이지 줄과 GW-04 줄(「못 읽은」→「인식 실패」 — sid:MARC-ENT-603)', () => {
    expect(status.failedPages([31, 58, 70])).toBe(
      '인식 실패 페이지 3개 (31 · 58 · 70페이지)',
    );
    expect(GW_TEXT.result.missedPages(3)).toBe('인식 실패 페이지 3개');
    expect(GW_TEXT.result.missedNote).toBe('이 페이지의 문장은 결과에 없어요');
  });
  it('자동 저장 토막: 있으면 끝에 「 · 자동 저장됨 HH:MM」, 없으면 없음', () => {
    expect(GW_TEXT.reviewScreen.tally(11, 3, 8, '14:31')).toBe(
      '채택 11 · 제외 3 · 미검토 8 · 자동 저장됨 14:31',
    );
    expect(GW_TEXT.reviewScreen.tally(11, 3, 8)).toBe(
      '채택 11 · 제외 3 · 미검토 8',
    );
    const base = {
      at: '2026-10-15 14:20',
      ordinal: 2,
      pageCount: 139,
      checked: 44,
      reviewed: 14,
      total: 22,
    };
    expect(GW_TEXT.result.meta({ ...base, savedAt: '14:31' })).toBe(
      '2026-10-15 14:20 · 2회차 · 총 139페이지 가운데 페이지 44개의 문장을 점검 · 검토 14/22 · 자동 저장됨 14:31',
    );
    expect(GW_TEXT.result.meta({ ...base, savedAt: null })).toBe(
      '2026-10-15 14:20 · 2회차 · 총 139페이지 가운데 페이지 44개의 문장을 점검 · 검토 14/22',
    );
  });
});

// 밴드 GCM1: 그린워싱 시안 댓글 1차 반영(sid:MARC-ENT-603). 스레드 번호는 발주서 §1 표의 #. 바뀐 글은 그대로, 지운 줄은 「없음」으로 단언한다.
describe('GCM1 시안 댓글 1차 반영 — 글자·줄 지움', () => {
  const W = GW_TEXT;
  it('#1·#3 GW-00 소개 글', () => {
    expect(W.intro.about[0]).toMatch(
      /^지속가능경영보고서를 비롯한 ESG공시 자료에서 환경에 관한 주장 문장을 찾아/,
    );
    expect(W.intro.about[0]).not.toContain('같은 문서에서');
    expect(W.intro.pdfInfo).toBe(
      '텍스트 선택이 가능한 PDF 만 점검해요. 이미지·인포그래픽은 분석하지 않아요.',
    );
    expect(W.intro.startHint).toBe(
      '시작하기 버튼을 눌러 점검을 시작해 보세요.',
    );
  });
  it('#6·#7·#8 GW-01 탭·배지·열 머리 이름', () => {
    expect(W.list.tabs).toEqual({
      all: '전체',
      running: 'AI 점검 중',
      pending: '검토 대기',
      in_review: '검토 중',
      confirmed: '검토 완료',
      failed: '멈춤',
    });
    expect(W.runStatus).toEqual({
      analyzing: 'AI 점검 중',
      failed: '멈춤',
      pending: '검토 대기',
      reviewing: '검토 중',
      confirmed: '검토 완료',
    });
    // 확정 버튼·모달 동사·엑셀 「확정본」은 그대로(엑셀 이름은 밴드 GDL1 에서 받기 모달 줄로 — GW-04a r1)
    expect(W.result.confirm).toBe('확정');
    expect(W.reviewScreen.confirm).toBe('확정');
    expect(W.confirm.submit).toBe('확정');
    expect(W.downloads.excelConfirmed).toBe('점검 결과 엑셀 · 확정본');
    expect(W.list.columns.uploadedBy).toBe('담당자');
    expect(W.list.columns.lastRun).toBe('AI점검 완료 일자');
  });
  it('#12·#26 GW-02·03 「텍스트」 낱말', () => {
    expect(W.newCheck.upload.formats(300, 50)).toBe(
      '텍스트 선택이 가능한 PDF 만 점검해요 · 최대 300페이지, 50MB 까지',
    );
    expect(W.newCheck.upload.noText).toBe(
      '이 PDF는 텍스트를 선택할 수 없어요(스캔본·이미지로 만든 PDF). 텍스트를 선택할 수 있는 PDF로 다시 올려 주세요.',
    );
    expect(W.newCheck.upload.noTextHow).toBe(
      '확인하는 법: PDF 에서 텍스트를 마우스로 끌어 선택되는지 보세요. 선택되지 않으면 텍스트를 선택할 수 없는 PDF 예요',
    );
    expect(JSON.stringify(W.newCheck)).not.toContain('글자를 고를');
  });
  it('#13·#14·#15·#17·#18 GW-02 지운 줄과 조각', () => {
    expect(W.newCheck.year).not.toHaveProperty('help');
    expect(W.newCheck.parts).not.toHaveProperty('help');
    expect(W.newCheck.parts.activeHint('CEO 메시지')).toBe(
      '고른 파트: CEO 메시지',
    );
    expect(W.newCheck.parts.legendOverlap).toBe('두 파트 이상이 겹친 페이지');
    expect(W.newCheck).not.toHaveProperty('settings');
  });
  it('#21·#22·#23·#24·#25 GW-03 처리 상태', () => {
    expect(W.status.stages.extract.name).toBe('텍스트 추출');
    expect(W.status.stages.extract.body(12)).toBe(
      '총 12페이지에서 텍스트를 추출해 근거로 찾을 수 있게 정리했어요',
    );
    expect(W.status.stages.extract.bodyPending(null)).toBe(
      '문서에서 텍스트를 추출해 근거로 찾을 수 있게 정리해요',
    );
    expect(W.status.stages.summarize.body).toBe(
      '그린워싱 리스크 단어 빈도를 세고, 그린워싱 리스크 문장의 위치를 찾아 결과를 묶어요',
    );
    expect(W.status).not.toHaveProperty('runningNote');
    expect(W.status.failedPages([2])).toBe('인식 실패 페이지 1개 (2페이지)');
    expect(W.status.doneMeta(null, 3)).toBe(
      '3개의 그린워싱 리스크 문장을 찾았어요',
    );
  });
  it('#27·#29·#30 GW-04 결과 요약', () => {
    expect(W.result.missedPages(1)).toBe('인식 실패 페이지 1개');
    expect(W.result.termsHeading).toBe('그린워싱 리스크 단어 빈도');
    expect(W.result.termsNote).toBe(
      '단순 그린워싱 리스크 가능성이 있는 단어 사용의 빈도예요.',
    );
  });
  it('#5 GW-01 설명 줄: 고객사 꼴 없음, 운영 관리자는 작업 회사만', () => {
    expect(W.list).not.toHaveProperty('meta');
    expect(W.list.metaOperator('가-회사')).toBe('작업 회사 가-회사');
  });
  it('GW-01 안내 글: 상태 이름 「검토 대기」 띄어 씀(시안 v228, 밴드 GWT1)', () => {
    expect(W.list.notice.startsWith('점검이 끝나면 검토 대기가 돼요.')).toBe(
      true,
    );
    expect(W.list.notice).not.toContain('검토대기');
  });
  it('#32·#34·#35 GW-05 검토', () => {
    expect(Object.keys(W.exclude.reasons)).toEqual([
      'not_claim',
      'evidence_in_doc',
      'other',
    ]);
    expect(W.reviewScreen.detailPage([28, 33])).toBe(
      '참고한 근거 페이지 28, 33',
    );
    expect(W.reviewScreen.toList).toBe('목록으로 돌아가기');
  });
  it('그린워싱 문구 표에 옛 낱말이 남지 않는다(「못 읽은 페이지」·「친환경 단어」·「글자를 고를」·「글자 뽑기」)', () => {
    const all = JSON.stringify(W, (_key, value: unknown) =>
      typeof value === 'function' ? String(value) : value,
    );
    expect(all).not.toMatch(
      /못 읽은 페이지|친환경 단어|글자를 고를|글자 뽑기|올린 사람|마지막 실행/,
    );
  });
});
