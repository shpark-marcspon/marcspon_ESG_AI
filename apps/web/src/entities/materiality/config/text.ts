// 중대성평가 화면 글 한 곳(밴드 IRW1 — 발주서 Directive). 아무것도 가져오지 않는다(app/guards/layers.test.ts).
// 정본 차례: 사용자 > 시안 v157 판(band-handoffs/IR-design-v157-boards/IR-0*_r1.dc.html) > 발주서 §2 의 감독 정함 글(경고 표·
//   다시 실행 실패·정하지 못함 안내). 판·발주서 둘 다에 없는 글은 데이터 검증 DV_TEXT 의 같은 자리 글을 옮겨 적었다(보고의 물을 거리).
// 서버 message·errorMessage·failure.message·경고 message 는 화면에 0 — 갈래는 code·status 로 고른다. 없는 값(null)은 「–」.
// 진행 수(「4 / 6토픽」·「· 23건」)·「1회차」 글은 두지 않는다(sid:MARC-ISSUE-378 · 발주서 Q4).

const DASH = '–';
/** 없는 값은 「–」. */
const orDash = (value: string | number | null) =>
  value === null ? DASH : String(value);
/** 토픽 이름 묶음 「「A」·「B」」. */
const topicNames = (topics: readonly string[]) =>
  topics.map((topic) => `「${topic}」`).join('·');

export const IR_TEXT = {
  dash: DASH,
  orDash,
  /** 틀(AppShell) 글 — 데이터 검증 DV_TEXT.shell 을 옮겨 적음(가져오지 않는다), title 만 「중대성평가」. */
  shell: {
    menuLabel: '모듈 메뉴',
    logo: '로고 자리',
    title: '중대성평가',
    greeting: '담당자님 안녕하세요',
    adminGreeting: '운영 관리자님 안녕하세요',
    toAdmin: '관리자 화면',
    menu: {
      dashboard: '대시보드',
      ghg: '온실가스',
      greenwash: '그린워싱 점검',
      materiality: '중대성평가',
      validation: '데이터 검증',
      translation: '영문번역',
      drafting: '보고서 작성',
    },
  },
  /** STEP 띠(판 g-flow — IR-00·02 = 1 · IR-03 = 2 · IR-04 = 3). IRW2 가 받아 쓴다. */
  flow: {
    label: '평가 단계',
    items: [
      { step: 'STEP 1', label: '기본 정보 입력' },
      { step: 'STEP 2', label: 'IRO 도출' },
      { step: 'STEP 3', label: '결과' },
    ],
  },
  common: {
    toList: '목록으로',
    retry: '다시 시도',
    rerun: '다시 실행',
    rerunFailed: '다시 실행하지 못했어요. 잠시 뒤 다시 눌러 주세요.',
    viewResult: '결과 보기',
    downloadFailed: '파일을 받지 못했어요. 다시 시도해 주세요.',
    notFound: '평가를 찾을 수 없어요',
    rerunAgain:
      '평가를 끝내지 못했어요. 다시 실행하면 새 실행으로 리서치부터 다시 해요.',
  },
  /** 실행 상태 배지(queued 대기 · processing 처리 중 · done 완료 · failed 실패). */
  badge: {
    queued: '대기',
    processing: '처리 중',
    done: '완료',
    failed: '실패',
  },
  sector: { financial: '금융', non_financial: '비금융' },
  /** 「<회사> · 중대성평가」(IR-03 끝남·실패 머리 · IR-04 머리). */
  titleOf: (company: string) => `${company} · 중대성평가`,
  /** IR-03 처리 상태(판 그대로 — 진행 수 0). */
  status: {
    title: '평가 중이에요',
    /** 「이 창을 닫아도…」 토막은 돌고 있을 때만(끝남·실패에는 뺀다 — 디자인 대조 W7, 그린워싱 GW_TEXT 머리 줄 꼴). */
    startedLine: (
      at: string,
      company: string,
      topics: string,
      running = true,
    ) =>
      `${at} 시작 · ${company} · 토픽 ${topics}개${running ? ' · 이 창을 닫아도 평가는 계속돼요' : ''}`,
    queuedLine: (at: string, company: string, topics: string) =>
      `${at} 접수 · ${company} · 토픽 ${topics}개 · 이 창을 닫아도 평가는 계속돼요`,
    progress: '진행',
    /** 진행 중 줄·머리의 수(판 「4 / 6토픽」 — 수와 단위 사이 빈칸 0. 2부는 서브토픽 자리, IRW6 Q2). */
    count: (done: number, total: number, unit: 'topic' | 'subtopic') =>
      `${done} / ${total}${unit === 'topic' ? '토픽' : '서브토픽'}`,
    lineStatus: {
      done: '완료',
      running: '진행 중',
      pending: '대기',
      failed: '실패',
    },
    /** 줄 여섯의 이름·설명(판 글 — 「· 23건」은 뺌, 「· 4 / 6토픽」은 진행 중 줄만 수(IRW6). 줄 1·2 는 현재형 — 6c 10-26, 덧붙임 B2). */
    lines: {
      regulation: {
        name: '규제·정책 리서치',
        text: '토픽별 규제·정책·가이드라인 변화를 웹에서 찾아요',
      },
      controversy: {
        name: '컨트로버시 리서치',
        text: '토픽별 키워드를 뽑아 언론·기관이 다룬 이슈를 찾아요',
      },
      impact: {
        name: '환경·사회 영향 정의',
        text: '서브토픽마다 기업이 환경·사회에 주는 긍정·부정 영향을 정해요',
      },
      financial: {
        name: '재무 영향 정의',
        text: '서브토픽마다 기업에 오는 리스크·기회를 정해요',
      },
      pathway: {
        name: '재무 영향 경로',
        text: '원인 → 비즈니스 영향 → 재무 영향에 따라 리스크·기회를 식별해요',
      },
      report: { name: '결과 정리', text: '결과 표와 엑셀을 만들어요' },
    },
    waiting: '차례를 기다리고 있어요 · 앞 작업이 끝나면 저절로 시작해요',
    doneTitle: '평가가 끝났어요',
    /** 제목 doneTitle 아래 줄 — 「끝남」은 제목과 겹쳐 뺐다(IRW17 — 댓글 20be9a06 「두번 중복」). */
    doneLine: (at: string, impact: string, pathway: string) =>
      `${at} · 환경·사회 영향 ${impact} · 재무 영향 경로 ${pathway}`,
    undecided: (total: number, m: number) =>
      `서브토픽 ${total}개 가운데 ${m}개는 영향을 정하지 못했어요. 나머지 결과는 볼 수 있고, 빠진 서브토픽은 결과 표에 「정하지 못함」으로 남아요.`,
    loadFailed: '진행 상태를 불러오지 못했어요',
  },
  /** IR-04·04a 결과(판 그대로 — 「1회차」 0, 컨트로버시 심각도 작은 줄 0). */
  result: {
    meta: (
      at: string,
      topics: string,
      subtopics: string,
      period: string,
      sector: string,
    ) =>
      `${at} 끝남 · 토픽 ${topics} · 서브토픽 ${subtopics} · 리서치 기간 ${period} · ${sector}`,
    period: (start: string, end: string) => `${start} ~ ${end}`,
    loadFailed: '결과를 불러오지 못했어요',
    cards: {
      topics: '토픽',
      regulation: '규제·정책',
      controversy: '컨트로버시',
      impact: '환경·사회 영향',
      pathway: '재무 영향 경로',
      unitCount: '개',
      unitCase: '건',
      subtopics: (n: number) => `서브토픽 ${n}`,
      impactSub: (positive: number, negative: number) =>
        `긍정 ${positive} · 부정 ${negative}`,
      pathwaySub: (risk: number, opportunity: number) =>
        `리스크 ${risk} · 기회 ${opportunity}`,
    },
    undecided: (total: number, m: number, list: string) =>
      `서브토픽 ${total}개 가운데 ${m}개(${list})는 영향을 정하지 못했어요. 다시 실행하면 새 실행으로 리서치부터 다시 해요.`,
    subtopicRef: (topic: string, subtopic: string) => `${topic} › ${subtopic}`,
    refJoiner: ', ',
    tabs: {
      label: '결과 표',
      shortlist: '1-1 토픽별 리서치',
      impact: '2-1 환경·사회 영향',
      pathway: '2-2 재무 영향',
    },
    topicLabel: '토픽',
    topicAll: '토픽 전체',
    undecidedCell: '정하지 못함',
    researchMissing: '찾은 글 없이 정함',
    filteredEmpty: '조건에 맞는 영향이 없어요',
    /** 거르기 없이 빈 2-1·2-2(6c 10-26 — 덧붙임 B3, 단추 없음). */
    noImpacts: '찾은 영향이 없어요',
    clearFilter: '거르기 풀기',
    summaryLabel: '컨텍스트 요약',
    impact: {
      title: '2-1 환경·사회 영향',
      sub: 'Impact materiality',
      kindLabel: '영향 유형',
      all: (n: number) => `전체 ${n}`,
      positive: (n: number) => `긍정 ${n}`,
      negative: (n: number) => `부정 ${n}`,
      head: {
        no: 'No',
        topic: '토픽',
        subtopic: '서브토픽',
        activities: '가치사슬 활동',
        definition: '영향 정의',
        type: '유형',
        summary: '컨텍스트 요약',
      },
      foot: '영향 정의는 AI 가 쓴 글이고, 컨텍스트 요약은 리서치에서 찾은 글의 요약이에요. 출처는 「1-1 토픽별 리서치」 탭에 있어요.',
    },
    pathway: {
      title: '2-2 재무 영향',
      sub: 'Financial materiality',
      kindLabel: '리스크·기회',
      all: (n: number) => `전체 ${n}`,
      risk: (n: number) => `리스크 ${n}`,
      opportunity: (n: number) => `기회 ${n}`,
      head: {
        no: 'No',
        topic: '토픽',
        subtopic: '서브토픽',
        activities: '가치사슬 활동',
        definition: '영향 정의',
        kind: '리스크/기회',
        riskType: '리스크 종류',
        driver: '① 영향 요인',
        business: '② 비즈니스 영향',
        financial: '③ 재무 영향',
      },
      foot: '리스크 종류는 규제 및 법률 · 평판 · 기술 · 시장 넷이고, 기회에는 붙지 않아요.',
      expandHint: '컨텍스트 요약 열은 줄을 누르면 펼쳐 보여요.',
      /** 누를 수 있는 줄의 이름(규칙 4 — sid:MARC-ENT-599, 밴드 IRW13 개정 2 · 디자인 e6 11-08). 펼침 상태는 이름에 넣지 않는다(aria-expanded). 서브토픽이 비면 번호만. */
      rowLabel: (no: number, subtopic: string | null | undefined) =>
        typeof subtopic === 'string' && subtopic.trim() !== '' ?
          `${no}번 ${subtopic} 컨텍스트 요약`
        : `${no}번 컨텍스트 요약`,
    },
    shortlist: {
      title: '1-1 토픽별 리서치',
      head: {
        no: 'No',
        topic: '토픽',
        regulation: '규제 및 정책',
        controversy: '컨트로버시',
      },
      label: {
        social: '[환경·사회]',
        financial: '[재무]',
        both: '[환경·사회·재무]',
      },
      /** 1-1 표 아래 foot 앞 근거 글(IRW14 — 시안 댓글 8d65ea15, 결정 MARC-ENT-656). */
      basis: '영향의 근거로 쓴 규제·정책·컨트로버시만 보여요.',
      /** basis 뒤에 — 리서치 엑셀 파일이 있을 때만(밴드 IRW16 — 실행 files 에 리서치 엑셀). */
      basisResearch: '전체는 리서치 엑셀에 있어요.',
      foot: '[환경·사회] · [재무] 표시는 그 글을 어느 단계에서 썼는지예요. 출처를 누르면 새 탭에서 열려요.',
      notResearched: '이 토픽은 리서치를 하지 못했어요',
      /** 빈 토픽을 묶은 안내 하나(「「A」·「B」 토픽은…」 — 토픽 하나면 「「A」 토픽은…」. 디자인 대조 J2). */
      noControversy: (topics: readonly string[]) =>
        `${topicNames(topics)} 토픽은 검색 기간 안에 찾은 컨트로버시가 없어요. 영향은 규제·정책과 기업 정보로만 정했어요.`,
      noRegulation: (topics: readonly string[]) =>
        `${topicNames(topics)} 토픽은 검색 기간 안에 찾은 규제·정책이 없어요. 영향은 컨트로버시와 기업 정보로만 정했어요.`,
    },
    /** 결과 글 칸 고치기(판 IR-04·04a r3, 밴드 IRW11 — 결정 sid:MARC-ENT-561). */
    edit: {
      column: '고치기',
      open: '고치기',
      cancel: '취소',
      save: '저장',
      /** 2-1·2-2 편집 줄 아래(critic 블로커 처분 ① — 디자인 e6 ②④). */
      rowNote:
        '요약을 고치면 같은 글을 근거로 쓴 다른 줄의 요약도 함께 바뀌어요 · 요약을 비우고 저장하면 그 요약은 이 줄에서 빠져요(출처는 1-1 에 남아요) · 한 번에 한 줄씩 고칠 수 있어요',
      shortlistNote:
        '1-1 을 고치면 2-1 · 2-2 의 같은 항목 요약도 함께 바뀌어요 · 한 번에 한 줄씩 고칠 수 있어요',
      definition: '영향 정의',
      summary: (n: number) => `컨텍스트 요약 ${n}`,
      title: '제목',
      url: '출처 주소',
      urlPlaceholder: 'https://',
      errors: {
        tooLong: '4,000자까지 쓸 수 있어요',
        titleTooLong: '제목은 1,000자까지 쓸 수 있어요',
        urlTooLong: '주소는 2,048자까지 쓸 수 있어요',
        urlScheme: 'http:// 나 https:// 로 시작하는 주소만 넣을 수 있어요',
        urlLocked: '여러 영향이 함께 쓰는 출처라 주소를 비울 수 없어요',
        urlDuplicate: '같은 출처가 이미 있어요',
      },
      conflict: '다른 사람이 먼저 고쳤어요. 새로 불러온 뒤 다시 고쳐 주세요',
      reload: '새로 불러오기',
      saveFailed: '저장하지 못했어요. 잠시 뒤 다시 눌러 주세요',
      /** 연필 툴팁·이름. */
      editedBy: (name: string, at: string) => `고친 사람 ${name} · ${at}`,
      editedLabel: (name: string, at: string) =>
        `고친 칸 · 고친 사람 ${name} · ${at}`,
      /** 표 머리 배지(고친 칸이 있을 때만). */
      badge: (n: number, at: string) => `고친 칸 ${n} · 저장 ${at}`,
      leaveTitle: '저장하지 않은 글이 있어요',
      leaveBody: '나가면 고친 글이 사라져요',
      leaveStay: '계속 고치기',
      leaveGo: '나가기',
    },
    notRun:
      '이 평가는 영향 정의까지 가지 못했어요. 다시 실행하면 새 실행으로 리서치부터 다시 해요.',
    /** 머리 [내려받기] → 공용 받기 모달(밴드 IRW16 — 판 IR-04b r1 · IR-04 r4, 결정 sid:MARC-ENT-662·663). 줄 차례는 files 열쇠 차례. */
    downloads: {
      title: '내려받기',
      close: '닫기',
      fileMissingLabel: '없는 까닭',
      downloading: '받는 중',
      files: { report: '결과 엑셀', research: '리서치 엑셀' },
      fileNotes: {
        report: '고친 값이 나가요 · 시트 4개(1-1 · 2-1 · 2-2 · RAW_JSON)',
        research: 'AI 가 찾은 원본 그대로예요 · 시트 2개',
      },
      /** 실행 files 에 그 파일이 없을 때 꺼진 줄의 (?) 까닭. */
      fileMissing: {
        report: '이 실행에는 결과 엑셀이 없어요',
        research: '이 실행에는 리서치 엑셀이 없어요',
      },
      /** 실행(GET /runs/{id})을 못 읽었을 때 머리 [내려받기] 자리(381 m3 — 부록 A6-⑫). */
      runFailed:
        '실행 정보를 불러오지 못해 내려받기를 열 수 없어요. 새로 고침해 주세요.',
    },
  },
  /** IR-01·01a 평가 목록(판 그대로 — 머리 아래 셈·안내 줄은 지웠다: 그린워싱과 맞춤, sid:MARC-ENT-625. 내 실행만 거르기·아래 안내 띠·기업명 옆 최신 이슈 표시는 IRW17 이 지웠다). */
  list: {
    title: '평가 목록',
    introLink: '평가 안내',
    newRun: '새 평가',
    tabsLabel: '상태',
    tabs: {
      all: '전체',
      active: '대기·처리 중',
      done: '완료',
      failed: '실패',
    },
    columns: {
      company: '기업',
      industry: '산업(SASB)',
      topics: '토픽',
      period: '리서치 기간',
      createdBy: '실행한 사람',
      lastRun: '평가 완료 일자',
      impact: '환경·사회 영향',
      pathway: '재무 영향 경로',
      status: '상태',
      next: '다음 할 일',
    },
    industryJoiner: ', ',
    processing: (line: string | null) =>
      line === null ? '처리 중' : `처리 중 · ${line}`,
    next: { result: '결과 보기', progress: '진행 보기', rerun: '다시 실행' },
    empty: '아직 돌린 평가가 없어요. 기업·산업과 중대 토픽을 넣어 시작해요.',
    emptyFiltered: '조건에 맞는 평가가 없어요',
    clearFilter: '거르기 풀기',
    loadFailed: '평가 목록을 불러오지 못했어요',
  },
  /** IR-00 평가 안내(밴드 IRW2 ② — 판 IR-00_r1 v166 글자 그대로, 부록 A1 · IRW17 1차 댓글 고침). 띠 단계 이름은 IR_TEXT.flow. */
  intro: {
    title: '중대성평가',
    heading: '중대성평가 IRO란',
    lead: [
      '미리 골라 둔 중대 토픽마다 회사 밖에서 일어난 일(규제·정책 변화와 컨트로버시)을 웹에서 찾아, 회사가 환경·사회에 주는 영향(Impact)과 회사 재무에 돌아오는 리스크·기회(Risk · Opportunity)를 정리해요. 영향은 환경·사회적 중대성, 리스크·기회는 재무적 중대성 쪽의 말이에요.',
      '찾은 글은 제목 · 출처 주소와 함께 남아서, 영향마다 어떤 글을 보고 정했는지 따라가 볼 수 있어요. 날짜는 리서치 엑셀에 있어요.',
    ],
    kinds: {
      head: ['구분', '의미', '예시'],
      impact: {
        name: '환경·사회 영향',
        sub: 'Impact',
        meaning: '회사 활동이 환경과 사람에게 주는 영향이에요.',
        positive: '긍정',
        negative: '부정',
        meaningTail: '으로 나눠요',
        example:
          '「현장 장비와 자재 생산에서 나오는 온실가스가 기후변화를 키웁니다」',
      },
      financial: {
        name: '재무 영향',
        sub: 'Risk · Opportunity',
        risk: '리스크',
        opportunity: '기회',
        meaning:
          '회사 재무에 돌아오는 영향이에요. 불리하면 리스크, 유리하면 기회로 나누고, 리스크는 규제 및 법률 · 평판 · 기술 · 시장 가운데 어느 종류인지 붙여요. 영향 요인 → 비즈니스 영향 → 재무 영향으로 이어 보여 드려요',
        riskExample: '배출 공시 의무 강화 → 저탄소 공법 전환 → 설비 투자 증가',
        opportunityExample:
          '고효율 장비 도입 → 현장 전력 사용 감소 → 운영비 절감',
      },
    },
    /** [시작하기] 단추 바로 왼쪽 회색 작은 글(IRW17 — 댓글 c755af0e). */
    hint: '시작하기 버튼을 눌러 평가를 시작해 보세요.',
    flowTitle: 'IRO 도출 과정',
    /** 단계 띠(판 g-stepband — 이름은 IR_TEXT.flow.items 의 label 과 같은 글). 옛 입력·결과 표 둘의 요약(IRW17 — 댓글 f0a1e9f6). */
    flow: [
      {
        step: 'Step 1',
        body: '기업명과 산업 분류(SASB 필수 · GICS·KSIC 선택), 도출된 중대 토픽과 서브토픽, 리서치 조건(검색 지역 · 언어 · 기간, 비금융 · 금융)을 넣어요',
      },
      {
        step: 'Step 2',
        body: '토픽마다 규제·정책과 컨트로버시를 웹에서 찾고(리서치), 그 글을 근거로 서브토픽마다 환경·사회 영향과 리스크·기회를 도출해요',
      },
      {
        step: 'Step 3',
        body: '1-1 토픽별 리서치 · 2-1 환경·사회 영향 · 2-2 재무 영향 표를 확인하고, 결과 엑셀·리서치 엑셀로 내려받아요',
      },
    ],
    start: '시작하기',
  },
  /** IR-02 새 평가(밴드 IRW2 ② — 판 IR-02_r1 v166 글자 그대로 + 부록 A6 감독 정함 글). */
  newRun: {
    title: '새 평가',
    lead: '기업·산업과 중대 토픽(Short-list)을 넣으면 토픽별 외부 맥락을 찾아 영향·리스크·기회를 정리해요.',
    company: {
      title: '1. 기업과 산업',
      name: '기업명',
      industryName: (standard: string) => `${standard} 산업명`,
      industryDescription: (standard: string) => `${standard} 산업 설명`,
      industryPlaceholder:
        '이 산업의 주요 사업과 관리 포인트를 한두 문장으로 적어요',
      /** SASB 설명 입력칸 바로 아래 늘 보이는 예시 한 줄(IRW14 — 시안 댓글 c4c9d1f7, 결정 MARC-ENT-656 · 자리는 IRW14b, 디자인 c3 11-10). */
      industryExample:
        '산업 설명 예) 자동차 부품 제조 — 협력사 공급망, 작업장 안전, 제품 품질',
      industryHint:
        '산업은 세 기준으로 적어요. 하나만 알면 그것만 적어도 돼요 · SASB 는 꼭 적어요 · 설명에 적은 사업을 기준으로 관련 규제를 걸러요',
    },
    valueChain: {
      title: '가치사슬 활동 (선택)',
      tabsLabel: '넣는 방법',
      tabFile: '엑셀 올리기',
      tabPaste: '붙여 넣기',
      /** MARC-ENT-466 — 셋째 탭(빈 행 하나 + [행 추가]로 시작). */
      tabManual: '직접 입력',
      dropTitle:
        '가치사슬 표가 있는 엑셀 파일을 끌어 놓거나 눌러서 골라 주세요',
      dropHint:
        '열 5개: 사업 부문 · 사업 내용 · 밸류체인 · 이해관계자 · 관련 비즈니스 활동 · .xlsx 한 개',
      pick: '파일 고르기',
      /** 열 안내 줄 아래 [양식 받기](IRW15 ① — 결정 MARC-ENT-668). 파일은 apps/web/public/templates/ 의 같은 이름(머리 다섯만). */
      template: '양식 받기',
      templateFile: '가치사슬_양식.xlsx',
      pasteLabel: '가치사슬 활동 붙여 넣기',
      pastePlaceholder:
        '엑셀에서 표를 복사해 여기에 붙여 넣어요\n열 5개: 사업 부문 · 사업 내용 · 밸류체인 · 이해관계자 · 관련 비즈니스 활동',
      empty: '비워 두면 활동을 잇지 않고 평가해요',
      fileLine: (rows: number, units: number) =>
        `활동 ${rows}개 · 사업 부문 ${units}개`,
      removeFile: '파일 지우기',
      failed: '넣지 못함',
      columns: [
        '사업 부문',
        '사업 내용',
        '밸류체인',
        '이해관계자',
        '관련 비즈니스 활동',
      ],
      removeHead: '지우기',
      cell: (row: number, column: string) => `${row}행 ${column}`,
      removeRow: (row: number) => `${row}행 지우기`,
      /** 밸류체인 고름 칸(Q2 서버 값 차례 — upstream·own operations·downstream). */
      stages: ['업스트림', '자체운영', '다운스트림'],
      choose: '고르기',
      addRow: '행 추가',
      clear: '모두 지우기',
      errors: {
        badHeader:
          '엑셀의 열 이름이 달라요. 사업 부문 · 사업 내용 · 밸류체인 · 이해관계자 · 관련 비즈니스 활동 차례로 맞춰 주세요',
        notTable: '표가 비어 있거나 엑셀(.xlsx) 파일이 아니에요',
        columns: (n: number) =>
          `붙여 넣은 표가 ${n}열이에요. 사업 부문부터 관련 비즈니스 활동까지 5열을 복사해 주세요`,
        /** A2 · A6-⑧: 셋까지 「·」, 넘으면 「a·b·c행 외 k행」. */
        stage: (rows: readonly number[]) =>
          `밸류체인은 업스트림 · 자체운영 · 다운스트림 중에서 골라 주세요 (${
            rows.length <= 3 ?
              `${rows.join('·')}행`
            : `${rows.slice(0, 3).join('·')}행 외 ${rows.length - 3}행`
          })`,
        /** A6-①. */
        tooLarge: '파일이 너무 커요. 1MB 이하로 올려 주세요',
        /** A6-②. */
        tooManyRows: '활동이 너무 많아요. 100행까지 넣을 수 있어요',
        /** A6-③. */
        tooLong: (row: number, column: string, max: number) =>
          `${row}행의 ${column} 칸이 너무 길어요. ${max}자까지예요`,
        /** A6-④. */
        notText: (row: number, column: string) =>
          `${row}행의 ${column} 칸이 글자가 아니에요. 셀 서식을 텍스트로 바꿔 주세요`,
        /** A6-⑥ 올리기 끊김·5xx. */
        unreadable: '파일을 읽지 못했어요. 잠시 뒤 다시 올려 주세요',
        /** A6-⑮. */
        tooManyScannedRows:
          '빈 줄이 너무 많아요 · 표만 남기고 다시 올려 주세요',
      },
    },
    topics: {
      title: '2. 중대 토픽 (Short-list)',
      count: (topics: number, subtopics: number) =>
        `토픽 ${topics}개 · 서브토픽 ${subtopics}개`,
      /** A6-⑬. */
      nameLabel: (n: number) => `${n}번째 토픽 이름`,
      namePlaceholder: '토픽 이름',
      remove: '토픽 빼기',
      /** A6-⑬ — 이름이 있으면 「{토픽} 토픽 설명」, 비면 「토픽 설명」. */
      descriptionLabel: (topic: string) =>
        topic === '' ? '토픽 설명' : `${topic} 토픽 설명`,
      descriptionPlaceholder:
        '이 토픽에서 무엇을 조사할지 한두 문장으로 적어요',
      /** 늘 보이는 안내 + 예시(IRW14 — 시안 댓글 c8a25796, 결정 MARC-ENT-656). */
      descriptionHint:
        '설명을 기준으로 규제·컨트로버시를 찾아요 · 예) 사업장·공급망의 온실가스 배출과 감축',
      subtopics: '서브토픽',
      /** 토픽 이름이 비면 앞 빈칸 없이(토픽 설명 aria 꼴 — IRW3). */
      subName: (topic: string) =>
        topic === '' ? '서브토픽 이름' : `${topic} 서브토픽 이름`,
      subDescription: (topic: string) =>
        topic === '' ? '서브토픽 설명' : `${topic} 서브토픽 설명`,
      /** A6-⑬. */
      subRemove: (topic: string, n: number) =>
        topic === '' ? `서브토픽 ${n} 지우기` : `${topic} 서브토픽 ${n} 지우기`,
      addSub: '서브토픽 더하기',
      folded: (n: number) => `서브토픽 ${n}개 · 펼치기`,
      expand: (topic: string) => (topic === '' ? '펼치기' : `${topic} 펼치기`),
      subCount: (n: number) => `서브토픽 ${n}개`,
      add: '토픽 더하기',
      hint: '토픽 설명은 서브토픽을 모두 담도록 적어 주세요',
    },
    research: {
      title: '3. 리서치 조건',
      geoScope: '검색 지역',
      /** A6-⑪ 처음 값. */
      geoScopeDefault: '글로벌(대한민국 · 북미 · EU 우선)',
      location: '기준 국가',
      locationOption: (code: string) => `기준 국가 ${code}`,
      language: '주 검색 언어',
      /** 주 검색 언어 칸 아래 회색 한 줄(IRW17 — 댓글 dc1240f4). 값은 엔진의 main_language. */
      languageHint: '결과는 늘 한국어로 정리돼요',
      period: '검색 기간',
      startDate: '시작일',
      until: '~',
      untilToday: '오늘까지',
      sector: '업종 구분',
      sectorHint: '규제·정책을 찾을 신뢰 출처 목록이 달라요',
      note: 'AI 가 웹 검색을 써요. 찾은 글은 결과에 제목·출처 주소와 함께 남아요.',
    },
    cancel: '취소',
    start: '평가 시작',
    /** 넣은 채 떠날 때 묻는 창(IRW15 ④ — 결정 MARC-ENT-668, IR-04 나가기 창 꼴). */
    leave: {
      title: '입력한 내용이 저장되지 않아요',
      body: '나가면 넣은 내용이 사라져요',
      stay: '계속 입력',
      go: '나가기',
    },
    /** [평가 시작] 검사 글(부록 A4·A6). */
    required: {
      company: '기업명을 넣어 주세요',
      sasb: 'SASB 산업명을 넣어 주세요 · GICS · KSIC 만으로는 시작할 수 없어요',
      /** A6-⑩. */
      descriptionOnly: (standard: string) =>
        `${standard} 산업명을 넣어 주세요 · 설명만으로는 넣지 않아요`,
      /** A6-⑭. */
      geoScope: '검색 지역을 넣어 주세요',
      startBeforeToday: '시작일은 오늘보다 앞선 날이어야 해요',
      /** A6-⑨. */
      startDate: '시작일을 넣어 주세요',
      topics: '토픽을 하나 이상 넣어 주세요',
      /** A6-⑤. */
      topicName: '토픽 이름을 넣어 주세요',
      topicDuplicate:
        '같은 이름의 토픽이 있어요. 토픽 이름은 한 번씩만 넣어 주세요',
      subtopics:
        '서브토픽을 하나 이상 넣어 주세요 · 영향은 서브토픽마다 정해요',
      subtopicName: '서브토픽 이름을 넣어 주세요',
      /** A6-⑦. */
      size: '넣은 내용이 너무 길어요. 설명이나 가치사슬 활동을 줄여 주세요',
    },
    startFailed:
      '평가를 시작하지 못했어요. 넣은 내용은 그대로 있으니 잠시 뒤 [평가 시작]을 다시 눌러 주세요.',
  },
  /** 경고 줄(발주서 §2-1 경고 문구 표 — 감독 정함). */
  warnings: {
    item_date_unreadable: (n: number) =>
      `토픽 ${n}개에서 날짜를 읽지 못한 리서치 글은 기간으로 거르지 않고 영향 정의에 썼어요.`,
    items_out_of_range: (n: number) =>
      `토픽 ${n}개에서 리서치 기간 밖의 글은 영향 정의에 쓰지 않았어요.`,
    subtopic_autofilled: (n: number) =>
      `서브토픽을 넣지 않은 토픽 ${n}개는 토픽 설명으로 서브토픽 하나를 지어 평가했어요.`,
    subtopic_key_unmatched: (n: number) =>
      `토픽 이름과 맞지 않는 서브토픽 묶음 ${n}개는 평가에 쓰지 않았어요.`,
    keywords_missing_for_topic: (n: number) =>
      `토픽 ${n}개는 검색 키워드를 얻지 못해 키워드 없이 컨트로버시를 찾았어요.`,
    answer_truncated: (n: number) =>
      `AI 답이 길이 상한에서 잘린 곳이 ${n}곳 있어요. 읽은 만큼만 결과에 담았어요.`,
    xlsx_cell_truncated: (n: number) =>
      `엑셀 칸 하나에 다 들어가지 않는 글 ${n}개는 앞부분만 담았어요.`,
    other: (n: number) =>
      `AI 답을 읽으며 정리한 곳이 ${n}곳 있어요. 원문은 엑셀 RAW_JSON 시트에 있어요.`,
  },
} as const;
