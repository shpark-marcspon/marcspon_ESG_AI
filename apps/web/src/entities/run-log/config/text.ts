// AD-04 실행 기록·지표의 문구 표(밴드 AD2 ③, 실서버 AD4R). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다. 이 파일은 아무것도 가져오지 않는다.
// 출처: 디자인 캔버스 「어드민」 AD-04_r1(판 1792310815-aa99) 원문. 말투는 해요체, 한 문장 글은 끝 마침표 뺌(MARC-ENT-269), 두 문장 이상은 원문 그대로.
// 디자인 원문 2: 불러오기 실패 「실행 기록을 불러오지 못했어요」 — 확정.
// 실서버(밴드 AD4R): 디자인 답(캔버스 AD-04 판 — sid:MARC-TICK-195, 감독 메시지 10-19)으로 확정 — 모듈 다섯 이름, 상태 넷(「대기」 추가·차례),
//   「알 수 없는 사람」, 빈 값 「–」(en dash), 「<$0.01」, 0건 글(낱말 「실행」 — 「조건에 맞는 실행이 없어요」 포함), 판 글 바닥글,
//   모의 공급사 안내 띠 「지금은 시험용 AI 연결이라 …」. 「{n}건 중 {m}건」·[더 보기]·더 보기 실패·[거르기 풀기]는 AD-05(AD5R 디자인 원문)와 같은 글.
// 초안(디자인 확인 전): 거르기 칸 이름(화면 읽기용 「모듈로 거르기」 꼴), 불러오는 중 숨은 글.
// 목(밴드 AD2 ③)의 글 — 예시 데이터 띠·옛 바닥글(세 문장) — 은 실서버(AD4R ②)에서 걷었다(sid:MARC-ENT-285, 디자인 답 2).
// AD4X ①: 서버가 review·aiSetting 을 실어(AD4S) 「AI 설정」·「검토」 열과 검토 거르기를 다시 단다 — 캔버스 v127 AD-04_r1 원문(열 이름·배지 글·판 네 문장 바닥글·「기본 설정」).
//   테스트 배지 글은 서버 엑셀 열 머리와 같은 「시험용」(sid:MARC-ISSUE-286, 디자인 답 10-22).
//   검토 pending 은 「미검토」(그린워싱 GW-01~05 와 같은 말), 검토 거르기 칸 이름 「검토로 거르기」 — cd 확정 10-22(AD4W).
// AD4X ②: [엑셀 내보내기] 의 글 — 판 S2~S5 원문(옆 글·만드는 중·0건 툴팁·실패). 초안: 상한 넘음 글(409), 대체 파일 이름(model 의 RUN_EXPORT_FALLBACK_NAME).
// AD4W(detail): 실행 상세 모달 — 캔버스 v127 AD-04a_r1 원문(제목·칸 이름·단계 표 머리·단계 상태·안내 줄·「결과 파일」·[닫기]·그린워싱 단계 이름 여섯).
//   판에서 줄임: 표 아래 글은 첫 문장만(둘째 「…번 불렀고 …번 다시」는 계약에 없다 — 한 문장이라 마침표 뺌).
//   cd 답 10-22 저녁(감독 d9 메시지): 실패 줄 「{단계} 단계에서 멈췄어요 · 오류 코드 {code}」·404 글·불러오기 실패 글·데이터 검증 단계 이름 다섯.
//   초안: 단계 밖 실패 글, 불러오는 중 숨은 글, 문서 단추의 이름(「{문서} 결과 보기」 — cd 답 「결과 보기」에 보이는 이름을 앞에 둠).
// AD4P: 같이 시작·이어서(결정 MARC-ENT-405, 캔버스 v138 AD-04_r1·AD-04a_r1 — 디자인 6c 답 10-25)와 결과 파일 404 글.
//   표는 배지 글 「같이 시작 #101 · 2/3」·「이어서 #88」, 상세는 칸 이름 「같이 시작」·「이어서」 + 값 「#101 · 2/3」·「#88」과 「같이 시작한 실행 2개」(글만 — 감독 답 Q1 (가)).
//   「이어서」 칸은 판에 아직 없다(디자인 가정 — 같이 시작 칸과 같은 꼴).

export const RUN_LOG_TEXT = {
  title: '실행 기록·지표',
  /** 두 문장 — 끝 마침표 둠. */
  description:
    '모든 모듈의 실행이 한 곳에 쌓여요. 처리 시간과 비용은 리드타임·운영비 지표의 원자료예요.',
  /** 모의 공급사일 때만 지표 위에 다는 정보 띠(디자인 답 6 — 한 문장, 원문 그대로 마침표 둠). */
  aiMockNotice: '지금은 시험용 AI 연결이라 토큰과 비용이 실제 값이 아니에요.',
  export: '엑셀 내보내기',
  /** 내보내는 동안 단추 글(판 S3). */
  exporting: '엑셀 만드는 중…',
  /** 단추 옆 작은 글(판 S2 — 수는 화면이 쉼표를 넣어 준다). */
  exportCount: (count: string) => `거른 결과 ${count}건을 엑셀로 받아요`,
  /** 0건일 때 꺼진 단추의 툴팁·숨은 설명(판 S4). */
  exportEmpty: '내보낼 기록이 없어요',
  /** 실패(판 S5 — 두 문장이라 마침표 둠). 판은 토스트, 토스트 부품이 없어 단추 옆 alert 한 줄(감독 처분 Q4). */
  exportFailed: '엑셀을 만들지 못했어요. 다시 시도해 주세요.',
  /** 상한(서버 1만 건)을 넘음 — 409 RUN_LOG_EXPORT_TOO_LARGE(초안, 감독 처분 Q3. 두 문장). */
  exportTooLarge: '내보낼 실행이 너무 많아요. 기간을 좁혀 주세요.',
  metrics: {
    runsThisMonth: '이번 달 실행',
    times: '회',
    averageDuration: '평균 처리 시간',
    tokens: '토큰',
    cost: '비용',
    estimated: '추정',
    failureRate: '실패율',
    percent: '%',
  },
  searchPlaceholder: '문서명 검색',
  searchLabel: '문서명 검색',
  module: {
    label: '모듈',
    name: '모듈로 거르기',
    all: '전체',
  },
  /**
   * 모듈 여섯(키 = 서버 module id — model 의 RUN_MODULES 와 같은 차례 = 셸 메뉴 차례, AD6). 표에 없는 id 는 id 그대로 보인다.
   * 「보고서 작성」은 셸 메뉴 이름(shell.menu.drafting) 그대로. inventory.scope12 는 실행 행이 생기지 않아(끼움 없음) 넣지 않는다.
   */
  modules: {
    'inventory.scope3': '온실가스 Scope 3',
    greenwash: '그린워싱',
    materiality: '중대성평가 IRO',
    dataverify: '데이터 검증',
    translation: '영문번역',
    drafting: '보고서 작성',
  } as Readonly<Record<string, string>>,
  period: {
    label: '기간',
    name: '기간으로 거르기',
    options: { month: '이번 달', lastMonth: '지난달', all: '전체' },
  },
  status: {
    label: '상태',
    name: '상태로 거르기',
    /** 키 = 서버 status 값(차례: 전체·대기·처리 중·완료·실패 — 디자인 답 1). */
    options: {
      all: '전체',
      queued: '대기',
      processing: '처리 중',
      done: '완료',
      failed: '실패',
    },
  },
  review: {
    label: '검토',
    name: '검토로 거르기',
    /** 키 = 서버 review 값(차례: 전체·미검토·검토 중·확정). 「미검토」는 cd 확정 10-22. */
    options: {
      all: '전체',
      pending: '미검토',
      in_review: '검토 중',
      confirmed: '확정',
    },
  },
  count: (n: number) => `${n}건`,
  /** 다 불러오지 않았을 때(AD-05 와 같은 꼴 — 「128건 중 50건」). */
  countOf: (total: number, shown: number) => `${total}건 중 ${shown}건`,
  tableLabel: '실행 기록',
  columns: {
    at: '시각',
    module: '모듈',
    document: '문서',
    flow: '흐름',
    aiSetting: 'AI 설정',
    uploadedBy: '담당자',
    duration: '처리 시간',
    tokens: '토큰',
    cost: '비용(추정)',
    status: '상태',
    review: '검토',
  },
  test: '시험용',
  /** 같이 시작 묶음(launchSize 2 이상만) — 표 문서 칸 아래 줄의 회색 배지. */
  launch: (first: number, index: number, size: number) =>
    `같이 시작 #${first} · ${index}/${size}`,
  /** 이어서 돌린 실행 — 같은 줄의 회색 배지. */
  resumed: (id: number) => `이어서 #${id}`,
  /** 이름·아이디가 풀리지 않은 담당자(회색 — AD-05 대체 글과 같게). */
  unknownUploader: '알 수 없는 사람',
  /** 기본 판의 AI 설정 칸 글(서버 aiSetting.id 가 null). */
  defaultSetting: '기본 설정',
  /** 빈 값(처리 시간·평균 처리 시간·실패율) — en dash U+2013(디자인 답 4). */
  empty: '–',
  /** 0 < 비용 < $0.005. */
  costBelow: '<$0.01',
  /** 네 문장 — 판 글 그대로(캔버스 v127 AD-04_r1). */
  foot: '비용은 토큰 수 × 모델 단가로 낸 추정이에요. 토큰·비용은 실행에 붙은 AI 호출만 세요. 검토는 그린워싱 실행에만 있어요(인벤토리의 검토·확정은 2차). AI 설정 칸은 그 실행이 쓴 버전이에요.',
  more: '더 보기',
  /** 한 문장 — 끝 마침표 뺌. */
  moreFailed: '기록을 더 불러오지 못했어요',
  clearFilter: '거르기 풀기',
  /** 기간만 거른 0건의 제목(디자인 답 5 — 「이번 달 실행이 없어요」). */
  emptyPeriod: (period: string) => `${period} 실행이 없어요`,
  /** 그 보조 줄(디자인 원문 그대로 — 마침표 둠). */
  widenPeriod: '기간을 넓혀 보세요.',
  /** 기간 「전체」의 0건(보조 줄 없음). */
  emptyAll: '아직 실행이 없어요',
  loading: '실행 기록을 불러오는 중',
  failed: '실행 기록을 불러오지 못했어요',
  retry: '다시 시도',
  /** 다른 거르기가 있는 0건(디자인 답 5 — 낱말 「실행」). */
  noMatch: '조건에 맞는 실행이 없어요',
  /** AD-04a 실행 상세 모달(AD4W). */
  detail: {
    title: '실행 상세',
    /** 문서 칸 단추의 이름(화면 읽기용 — 보이는 글은 문서 이름). */
    openLabel: (name: string) => `${name} 결과 보기`,
    /** 문서 없는 줄의 단추 이름(보이는 글은 「–」 — 그 줄 「시각」 칸의 글을 넣는다, ND1W). */
    openLabelNoDocument: (at: string) => `${at} 실행 결과 보기`,
    fields: {
      document: '문서',
      moduleFlow: '모듈 · 흐름',
      uploadedBy: '담당자',
      at: '시각',
      total: '합계',
      /** 칸 목록 맨 위(있을 때만 — AD4P). */
      launch: '같이 시작',
      resumed: '이어서',
    },
    /** 같이 시작 칸의 값(접두 「같이 시작」은 칸 이름이 맡는다). */
    launch: (first: number, index: number, size: number) =>
      `#${first} · ${index}/${size}`,
    /** 같은 칸의 글(형제 수 = launchSize − 1). 누름 동작은 없다(감독 답 Q1 (가)). */
    launchSiblings: (n: number) => `같이 시작한 실행 ${n}개`,
    /** 이어서 칸의 값. */
    resumed: (id: number) => `#${id}`,
    /** 모듈 · 흐름 칸 아래 작은 글(「AI 설정 그린워싱 v2」). */
    aiSetting: (module: string, setting: string) =>
      `AI 설정 ${module} ${setting}`,
    started: (at: string) => `${at} 시작`,
    finished: (at: string) => `${at} 끝`,
    tokens: (n: string) => `토큰 ${n}`,
    cost: (c: string) => `비용(추정) ${c}`,
    columns: {
      step: '단계',
      status: '상태 · 진행',
      duration: '시간',
      tokens: '토큰',
      cost: '비용(추정)',
    },
    /** 키 = 서버 단계 status 값(model 의 RUN_STEP_STATUSES 와 같은 차례). */
    stepStatus: {
      pending: '대기',
      running: '처리 중',
      done: '완료',
      failed: '실패',
    },
    /** 단계 기록이 없는 실행(stepUsageRecorded 거짓)의 안내 줄 — 한 문장. */
    noStepUsage: '이 실행은 단계별 토큰·비용 기록이 없어 합계만 보여요',
    /** 단계 표 아래 글(판 첫 문장 — 한 문장이라 마침표 뺌). */
    stepUsageNote: '토큰과 비용은 AI 를 부른 단계에만 있어요',
    failedAt: (step: string) => `${step} 단계에서 멈췄어요`,
    failedOutside: '단계 밖에서 멈췄어요',
    errorCode: (code: string) => `오류 코드 ${code}`,
    files: '결과 파일',
    /** 결과 파일(step null) 이름 옆 단추(결정 MARC-ENT-395 — 디자인 cd 초안). */
    download: '내려받기',
    /** 단추의 읽는 이름(줄이 여럿이라 파일 이름을 붙인다). */
    downloadLabel: (name: string) => `${name} 내려받기`,
    /** 받기 실패(503·403·500·연결·꼴 틀림 — 두 문장이라 마침표 둠). */
    downloadFailed: '파일을 받지 못했어요. 다시 시도해 주세요.',
    /** 받기 404(RUN_NOT_FOUND·RUN_FILE_NOT_FOUND — 시안 v138, 한 문장이라 마침표 뺌). */
    fileNotFound: '파일을 찾을 수 없어요',
    close: '닫기',
    notFound: '이 실행을 찾을 수 없어요',
    failed: '실행 상세를 불러오지 못했어요',
    loading: '실행 상세를 불러오는 중',
    /**
     * 단계 이름(모듈 → 서버 단계 이름 → 글). 표에 없으면 서버 이름 그대로.
     * AD6: 서버 흐름의 단계 전부(FlowStep name). 글의 원천은 그 모듈 화면의 단계·진행 줄 글 — 화면에 없던 것은 감독 정함(a8, 11-04).
     *   translation = 진행 카드 stage.names(report = 셋째 단계 「Word 만들기」), materiality = IR-03 줄 이름(줄 ↔ 단계 model/steps.ts),
     *   inventory.scope3 = 카테고리 이름(S3_TEXT.categories — 서버 단계 c1~c15, c10 없음), drafting = RP-04 진행 줄.
     *   inventory.scope3 의 pipeline(llm-first@1 — 끼움 없어 실행이 생기지 않음)은 넣지 않는다.
     */
    steps: {
      greenwash: {
        extract: '글 뽑기',
        index: '색인',
        judge: '판정',
        wordcount: '낱말 세기',
        locate: '위치 찾기',
        report: '결과 만들기',
        rewrite: '대체표현 만들기',
      },
      dataverify: {
        load: '불러오기',
        plan: '계산 계획',
        review: '계산 검토',
        insight: '리스크 진단',
        report: '결과 엑셀',
      },
      translation: {
        prepare: '준비',
        translate: '번역 · 검수 · 자동 수정',
        report: 'Word 만들기',
      },
      materiality: {
        load: '불러오기',
        regulation: '규제·정책 리서치',
        keywords: '키워드 뽑기',
        controversy: '컨트로버시 리서치',
        report: '1부 결과 정리',
        part2_seed: '2부 준비',
        impact: '환경·사회 영향 정의',
        financial: '재무 영향 정의',
        pathway: '재무 영향 경로',
        report_iro: '결과 정리',
      },
      'inventory.scope3': {
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
      },
      drafting: {
        extract: '전년도 보고서 읽기',
        map: '목차에 맞는 페이지 찾기',
        draft: '목차마다 초안 짓기',
        report: '결과 만들기',
      },
    } as Readonly<Record<string, Readonly<Record<string, string>>>>,
  },
} as const;
