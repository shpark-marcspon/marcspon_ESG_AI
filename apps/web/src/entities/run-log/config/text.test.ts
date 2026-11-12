// AD-04 문구 원문(밴드 AD2 ③, 실서버 AD4R). 시안 원문·디자인 원문·디자인 답(캔버스 AD-04 판)·결정(MARC-ENT-269)을 글자로 박는다.
import { describe, expect, it } from 'vitest';

import { RUN_LOG_TEXT } from './text.ts';

const t = RUN_LOG_TEXT;

describe('AD-04 문구 원문', () => {
  it('시안 원문(두 문장 이상은 끝 마침표 둠)·디자인 원문', () => {
    expect(t.title).toBe('실행 기록·지표');
    expect(t.description).toBe(
      '모든 모듈의 실행이 한 곳에 쌓여요. 처리 시간과 비용은 리드타임·운영비 지표의 원자료예요.',
    );
    expect(t.failed).toBe('실행 기록을 불러오지 못했어요');
    // 「AI 설정」·「검토」 열(캔버스 v127 AD-04_r1 S7, AD4X ①) — 열하나.
    expect(Object.values(t.columns)).toEqual([
      '시각',
      '모듈',
      '문서',
      '흐름',
      'AI 설정',
      '담당자',
      '처리 시간',
      '토큰',
      '비용(추정)',
      '상태',
      '검토',
    ]);
    // 목의 글(예시 데이터 띠)은 걷었다. 검토 거르기는 서버 review 로 다시 단다(AD4X ①).
    expect('mockBand' in t).toBe(false);
    expect('review' in t).toBe(true);
  });

  it('실서버 판 글(디자인 답)', () => {
    expect(t.foot).toBe(
      '비용은 토큰 수 × 모델 단가로 낸 추정이에요. 토큰·비용은 실행에 붙은 AI 호출만 세요. 검토는 그린워싱 실행에만 있어요(인벤토리의 검토·확정은 2차). AI 설정 칸은 그 실행이 쓴 버전이에요.',
    );
    expect(t.review.label).toBe('검토');
    expect(t.review.options).toEqual({
      all: '전체',
      pending: '미검토',
      in_review: '검토 중',
      confirmed: '확정',
    });
    expect(t.defaultSetting).toBe('기본 설정');
    // 서버 엑셀의 「시험용」 열과 같은 글(sid:MARC-ISSUE-286).
    expect(t.test).toBe('시험용');
    expect(t.aiMockNotice).toBe(
      '지금은 시험용 AI 연결이라 토큰과 비용이 실제 값이 아니에요.',
    );
    expect(t.status.options).toEqual({
      all: '전체',
      queued: '대기',
      processing: '처리 중',
      done: '완료',
      failed: '실패',
    });
    expect(t.unknownUploader).toBe('알 수 없는 사람');
    expect(t.empty).toBe('–');
    expect(t.costBelow).toBe('<$0.01');
    expect(t.emptyPeriod(t.period.options.month)).toBe('이번 달 실행이 없어요');
    expect(t.emptyPeriod(t.period.options.lastMonth)).toBe(
      '지난달 실행이 없어요',
    );
    expect(t.widenPeriod).toBe('기간을 넓혀 보세요.');
    expect(t.emptyAll).toBe('아직 실행이 없어요');
    expect(t.noMatch).toBe('조건에 맞는 실행이 없어요');
    expect(t.countOf(128, 50)).toBe('128건 중 50건');
    expect(t.count(3)).toBe('3건');
    expect(t.more).toBe('더 보기');
    expect(t.moreFailed).toBe('기록을 더 불러오지 못했어요');
    expect(t.clearFilter).toBe('거르기 풀기');
  });

  it('한 문장 글은 끝 마침표 없음(MARC-ENT-269)', () => {
    for (const line of [
      t.failed,
      t.noMatch,
      t.emptyAll,
      t.moreFailed,
      t.emptyPeriod('이번 달'),
    ])
      expect(line.endsWith('.'), line).toBe(false);
  });
});

describe('AD-04a 실행 상세 문구(밴드 AD4W)', () => {
  const d = t.detail;

  it('판 원문(캔버스 v127 AD-04a_r1)', () => {
    expect(d.title).toBe('실행 상세');
    expect(d.fields).toEqual({
      document: '문서',
      moduleFlow: '모듈 · 흐름',
      uploadedBy: '담당자',
      at: '시각',
      total: '합계',
      launch: '같이 시작',
      resumed: '이어서',
    });
    expect(d.aiSetting('그린워싱', 'v2')).toBe('AI 설정 그린워싱 v2');
    expect(d.started('2026-10-15 14:20')).toBe('2026-10-15 14:20 시작');
    expect(d.finished('14:28')).toBe('14:28 끝');
    expect(d.tokens('112,800')).toBe('토큰 112,800');
    expect(d.cost('$0.68')).toBe('비용(추정) $0.68');
    expect(Object.values(d.columns)).toEqual([
      '단계',
      '상태 · 진행',
      '시간',
      '토큰',
      '비용(추정)',
    ]);
    expect(d.stepStatus).toEqual({
      pending: '대기',
      running: '처리 중',
      done: '완료',
      failed: '실패',
    });
    expect(d.noStepUsage).toBe(
      '이 실행은 단계별 토큰·비용 기록이 없어 합계만 보여요',
    );
    expect(d.stepUsageNote).toBe('토큰과 비용은 AI 를 부른 단계에만 있어요');
    expect(d.files).toBe('결과 파일');
    expect(d.close).toBe('닫기');
  });

  it('cd 답(10-22 저녁)·초안 글', () => {
    expect(d.failedAt('판정')).toBe('판정 단계에서 멈췄어요');
    expect(d.errorCode('step_error')).toBe('오류 코드 step_error');
    expect(d.failedOutside).toBe('단계 밖에서 멈췄어요');
    expect(d.notFound).toBe('이 실행을 찾을 수 없어요');
    expect(d.failed).toBe('실행 상세를 불러오지 못했어요');
    expect(d.loading).toBe('실행 상세를 불러오는 중');
    expect(d.openLabel('지어낸 문서.pdf')).toBe('지어낸 문서.pdf 결과 보기');
    expect(d.openLabelNoDocument('2026-10-22 14:20')).toBe(
      '2026-10-22 14:20 실행 결과 보기',
    );
  });

  it('단계 이름: 그린워싱 여섯(판 S4) + rewrite(AD6 감독 정함)·데이터 검증 다섯(cd 답)', () => {
    expect(d.steps.greenwash).toEqual({
      extract: '글 뽑기',
      index: '색인',
      judge: '판정',
      wordcount: '낱말 세기',
      locate: '위치 찾기',
      report: '결과 만들기',
      rewrite: '대체표현 만들기',
    });
    expect(d.steps.dataverify).toEqual({
      load: '불러오기',
      plan: '계산 계획',
      review: '계산 검토',
      insight: '리스크 진단',
      report: '결과 엑셀',
    });
  });

  it('단계 이름: Scope 3 = 서버 단계 c1~c15(c10 없음)·assemble — 카테고리 이름은 S3_TEXT 와 같은 글자(밴드 S3T1)', () => {
    const s3 = d.steps['inventory.scope3'];
    expect(Object.keys(s3 ?? {})).toEqual([
      'c1',
      'c2',
      'c3',
      'c4',
      'c5',
      'c6',
      'c7',
      'c8',
      'c9',
      'c11',
      'c12',
      'c13',
      'c14',
      'c15',
      'assemble',
    ]);
    expect(s3).toEqual({
      c1: '구매 상품 및 서비스',
      c2: '자본재',
      c3: '연료 및 에너지 활동',
      c4: '업스트림 운송 및 유통',
      c5: '사업장 발생 폐기물',
      c6: '출장',
      c7: '출퇴근',
      c8: '업스트림 임차 자산',
      c9: '다운스트림 운송 및 유통',
      c11: '판매된 제품의 사용',
      c12: '판매된 제품의 폐기',
      c13: '다운스트림 임차 자산',
      c14: '프랜차이즈',
      c15: '투자',
      assemble: '결과 만들기',
    });
  });

  it('단계 상태 키 차례 = 대기·처리 중·완료·실패(model 의 RUN_STEP_STATUSES — model 시험이 맞춘다)', () => {
    expect(Object.keys(d.stepStatus)).toEqual([
      'pending',
      'running',
      'done',
      'failed',
    ]);
  });

  it('검토 pending 은 「미검토」(그린워싱과 같은 말)', () => {
    expect(t.review.options.pending).toBe('미검토');
  });

  it('결과 파일 [내려받기]·실패 글(결정 MARC-ENT-395 — 디자인 cd 초안, 실패는 하나)', () => {
    expect(d.download).toBe('내려받기');
    expect(d.downloadLabel('지어낸 결과.pdf')).toBe('지어낸 결과.pdf 내려받기');
    expect(d.downloadFailed).toBe('파일을 받지 못했어요. 다시 시도해 주세요.');
  });

  it('한 문장 글은 끝 마침표 없음(MARC-ENT-269)', () => {
    for (const line of [
      d.noStepUsage,
      d.stepUsageNote,
      d.failedOutside,
      d.notFound,
      d.failed,
      d.failedAt('판정'),
    ])
      expect(line.endsWith('.'), line).toBe(false);
  });
});

describe('같이 시작·이어서·결과 파일 404 문구(밴드 AD4P — 캔버스 v138, 디자인 6c 답 10-25)', () => {
  const d = t.detail;

  it('표 배지 글: 「같이 시작 #101 · 2/3」·「이어서 #88」', () => {
    expect(t.launch(101, 2, 3)).toBe('같이 시작 #101 · 2/3');
    expect(t.resumed(88)).toBe('이어서 #88');
  });

  it('상세 칸: 이름 「같이 시작」·「이어서」, 값 「#101 · 2/3」·「#88」, 「같이 시작한 실행 2개」', () => {
    expect(d.fields.launch).toBe('같이 시작');
    expect(d.fields.resumed).toBe('이어서');
    expect(d.launch(101, 2, 3)).toBe('#101 · 2/3');
    expect(d.resumed(88)).toBe('#88');
    expect(d.launchSiblings(2)).toBe('같이 시작한 실행 2개');
  });

  it('받기 404 글(한 문장 — 마침표 없음)과 실패 글은 따로', () => {
    expect(d.fileNotFound).toBe('파일을 찾을 수 없어요');
    expect(d.fileNotFound.endsWith('.')).toBe(false);
    expect(d.fileNotFound).not.toBe(d.downloadFailed);
  });
});
