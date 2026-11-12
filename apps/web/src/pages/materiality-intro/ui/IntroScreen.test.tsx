// @vitest-environment jsdom
// IR-00 평가 안내 화면 시험(밴드 IRW2 ② — 발주서 §3 시험 6, 시안 v166 IR-00_r1). 판 글 그대로 · 배지 색 · 단계 띠 · [시작하기].
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { IntroScreen } from './IntroScreen.tsx';

afterEach(cleanup);

const words = IR_TEXT.intro;

function setup() {
  const onStart = vi.fn();
  render(<IntroScreen onStart={onStart} />);
  return { onStart };
}

describe('IR-00 평가 안내', () => {
  it('머리·설명 두 줄 그대로 · 아래 e-info(Short-list 선정 줄) 0 · 「최신 이슈」 0', () => {
    setup();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      '중대성평가',
    );
    expect(
      screen.getByRole('heading', { name: '중대성평가 IRO란' }),
    ).toBeTruthy();
    const body = document.body.textContent!;
    expect(body).toContain(words.lead[0]);
    expect(body).toContain(words.lead[1]);
    expect(body).toContain('날짜는 리서치 엑셀에 있어요.');
    // cb02d6d1 — 아래 note 줄을 뺐다
    expect(screen.queryByTestId('intro-note')).toBeNull();
    expect(body).not.toContain('Short-list 선정');
    expect(body).not.toContain('중대성 점수 매기기');
    // 212c2680 — 판에서 「최신 이슈」 글 0
    expect(body).not.toContain('최신 이슈');
  });

  it('c755af0e 시작 안내는 카드 밖 [시작하기] 바로 왼쪽 같은 줄 회색 작은 글', () => {
    setup();
    const hint = screen.getByTestId('intro-hint');
    expect(hint.textContent).toBe('시작하기 버튼을 눌러 평가를 시작해 보세요.');
    expect(hint.className).toMatch(/text-text-tertiary/);
    const button = screen.getByRole('button', { name: '시작하기' });
    expect(hint.nextElementSibling).toBe(button);
    expect(hint.parentElement).toBe(button.parentElement);
    // 카드(「중대성평가 IRO란」) 안에는 0
    const card = screen.getByRole('heading', {
      name: '중대성평가 IRO란',
    }).parentElement!;
    expect(card.contains(hint)).toBe(false);
    expect(card.textContent).not.toContain('시작하기 버튼을 눌러');
    expect(
      document.body.textContent!.split('시작하기 버튼을 눌러').length - 1,
    ).toBe(1);
  });

  it('9589017e 구분 표 줄 둘: 환경·사회 영향(긍정·부정) · 재무 영향(리스크 error · 기회 success, 예시 둘에 배지)', () => {
    setup();
    const table = screen.getByRole('table', { name: '중대성평가 IRO란' });
    const head = within(table).getAllByRole('columnheader');
    expect(head.map((cell) => cell.textContent)).toEqual([
      '구분',
      '의미',
      '예시',
    ]);
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]!.textContent).toContain('환경·사회 영향');
    expect(rows[0]!.textContent).toContain('Impact');
    expect(rows[0]!.textContent).toContain(
      '회사 활동이 환경과 사람에게 주는 영향이에요. 긍정 부정 으로 나눠요',
    );
    expect(rows[0]!.textContent).toContain(
      '「현장 장비와 자재 생산에서 나오는 온실가스가 기후변화를 키웁니다」',
    );
    const badge = (row: HTMLElement, text: string) =>
      within(row).getAllByText(text, {
        selector: '[data-slot], span, div',
      })[0]!;
    expect(badge(rows[0]!, '긍정').className).toMatch(/success/);
    expect(badge(rows[0]!, '부정').className).toMatch(/error/);
    const cells = within(rows[1]!).getAllByRole('cell');
    expect(cells[0]!.textContent).toContain('재무 영향');
    expect(cells[0]!.textContent).toContain('Risk · Opportunity');
    expect(badge(cells[0]!, '리스크').className).toMatch(/error/);
    expect(badge(cells[0]!, '기회').className).toMatch(/success/);
    expect(cells[1]!.textContent).toBe(
      '회사 재무에 돌아오는 영향이에요. 불리하면 리스크, 유리하면 기회로 나누고, 리스크는 규제 및 법률 · 평판 · 기술 · 시장 가운데 어느 종류인지 붙여요. 영향 요인 → 비즈니스 영향 → 재무 영향으로 이어 보여 드려요',
    );
    const risk = within(rows[1]!).getByTestId('example-risk');
    const opportunity = within(rows[1]!).getByTestId('example-opportunity');
    expect(risk.textContent).toBe(
      '리스크 배출 공시 의무 강화 → 저탄소 공법 전환 → 설비 투자 증가',
    );
    expect(opportunity.textContent).toBe(
      '기회 고효율 장비 도입 → 현장 전력 사용 감소 → 운영비 절감',
    );
    expect(badge(risk, '리스크').className).toMatch(/error/);
    expect(badge(opportunity, '기회').className).toMatch(/success/);
    // 리스크 예시가 기회 예시 앞
    expect(
      risk.compareDocumentPosition(opportunity) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // 옛 줄 셋의 리스크 뜻 0
    expect(table.textContent).not.toContain('매출 · 비용 · 자산');
  });

  it('IRO 도출 과정 띠: 제목 · Step 1~3 · 이름(IR_TEXT.flow) · body 는 옛 표 요약', () => {
    setup();
    expect(
      screen.getByRole('heading', { level: 3, name: 'IRO 도출 과정' }),
    ).toBeTruthy();
    expect(document.body.textContent).not.toContain('평가 과정');
    const band = screen.getByTestId('process-band');
    const steps = within(band).getAllByRole('listitem');
    expect(steps.map((step) => step.querySelector('b')!.textContent)).toEqual([
      'Step 1',
      'Step 2',
      'Step 3',
    ]);
    expect(
      steps.map((step) => step.querySelector('strong')!.textContent),
    ).toEqual(['기본 정보 입력', 'IRO 도출', '결과']);
    expect(steps.map((step) => step.children[2]!.textContent)).toEqual([
      '기업명과 산업 분류(SASB 필수 · GICS·KSIC 선택), 도출된 중대 토픽과 서브토픽, 리서치 조건(검색 지역 · 언어 · 기간, 비금융 · 금융)을 넣어요',
      '토픽마다 규제·정책과 컨트로버시를 웹에서 찾고(리서치), 그 글을 근거로 서브토픽마다 환경·사회 영향과 리스크·기회를 도출해요',
      '1-1 토픽별 리서치 · 2-1 환경·사회 영향 · 2-2 재무 영향 표를 확인하고, 결과 엑셀·리서치 엑셀로 내려받아요',
    ]);
  });

  it('f0a1e9f6 「넣을 것」·「받는 것」 표 0 — 표는 구분 표 하나', () => {
    setup();
    expect(screen.getAllByRole('table')).toHaveLength(1);
    expect(screen.queryByRole('table', { name: '넣을 것' })).toBeNull();
    expect(screen.queryByRole('table', { name: '받는 것' })).toBeNull();
    const body = document.body.textContent!;
    expect(body).not.toContain('넣을 것');
    expect(body).not.toContain('받는 것');
    expect(body).not.toContain('위 표 셋과 복원용 원문을 담은 시트 4개');
  });

  it('[시작하기] 한 번 = onStart 한 번(서버 0)', () => {
    const { onStart } = setup();
    fireEvent.click(screen.getByRole('button', { name: '시작하기' }));
    expect(onStart).toHaveBeenCalledTimes(1);
  });
});
