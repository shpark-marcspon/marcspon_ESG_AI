// AD-02 AI 설정(실서버 판)의 문구 표(밴드 AD2R). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다. 이 파일은 아무것도 가져오지 않는다.
// 판 열·판정 기준 표의 다른 글(제목·열 이름·상태 셋 등)은 그대로 entities/ai-setting/config/text.ts(AI_SETTING_TEXT)다 — 여기는 실서버로 새로 생긴 글만.
// 출처: 디자인 답 D1~D8(band-reports/AD2R-design-answers.md, 디자인 14, 2026-10-20 — 발주서 「디자인 원문 사본」)·캔버스 v110 AD-02-CM ①·③·
//   G2c 디자인 답(sid:MARC-ISSUE-197 노트 10-19 10:57). 말투는 해요체, 한 문장 글은 끝 마침표 뺌, 두 문장 이상은 마침표 둠(sid:MARC-ENT-269).
// 받기 거절 글(criteriaRefused): 서버 criteria_e0.py MESSAGES(271-287 줄, 15개 — SHAPE 포함)를 code 째 옮기고, 디자인 D5 대로 둘만 웹 글로 갈음했다
//   (SCHEMA_VERSION → SHAPE 와 같은 글, VERSION → 저장 실패 글). 서버 문장이 바뀌면 이 표를 따라 고친다.
// 가정(디자인이 「가정」이라 한 것): D1 저장 뒤 알림 「v{n} 으로 저장했어요」·[새 버전] 끈 단추 title, D3 적용 실패 글.
// 초안(디자인 확인 전): 만든 사람 이름을 못 풀 때 「알 수 없는 사람」, 판 열 끝 [더 보기], 빈 기준 글의 줄 아래 글(서버 TEXT_LENGTH 문장),
//   한 줄이 아닌 기준 글의 줄 아래 글(서버 TEXT_MULTILINE 문장), 숨은 글(불러오는 중).
// AS3b ①: AD-02 그린워싱 탭의 모듈 글(K9 — 공통 표 AI_SETTING_TEXT 에서 옮긴 모듈 이름·모델 카드 곁 글·고정 규칙 머리·꼬리)과 대상 단어 카드 글
//   (디자인 사본 AD-02_r3 · cd 답 246 노트 10-22 · e9 답 248 노트 10-23 — 셈 줄 「칸마다」). 대상 단어 거절 글(terms.refused)은 웹 글 — 서버 문장을 보이지 않는다.
//   초안(러너 — 디자인 확인 거리): 입력 칸 이름표 · TERMS_TEXT 거절 글.

/** 받기 거절 code → 화면 글. 모르는 code 는 saveFailed. */
export const CRITERIA_REFUSED: Readonly<Record<string, string>> = {
  CRITERIA_SHAPE: '기준표의 꼴이 맞지 않아요',
  // 디자인 D5: 내부 낱말(schemaVersion)이 보여 SHAPE 와 같은 글로.
  CRITERIA_SCHEMA_VERSION: '기준표의 꼴이 맞지 않아요',
  // 디자인 D5: 화면에 판 이름 칸이 없어 사용자가 고칠 수 없다 — 저장 실패 글로.
  CRITERIA_VERSION: '저장하지 못했어요. 다시 저장해 주세요.',
  CRITERIA_ROWS_FIXED: '기준표의 줄은 15줄 그대로여야 해요',
  CRITERIA_ROW_ORDER: '기준표의 줄 차례(id·order)는 바꿀 수 없어요',
  CRITERIA_ROW_KIND: '줄의 구분과 판정 결과는 바꿀 수 없어요',
  CRITERIA_KEYWORD_NAME: '대상 키워드 묶음의 이름은 바꿀 수 없어요',
  CRITERIA_TERMS_COUNT: '대상 키워드의 낱말은 1~30개로 넣어 주세요',
  CRITERIA_TERM_LENGTH: '대상 키워드의 낱말은 1~30자로 써 주세요',
  CRITERIA_TERM_COMMA: '대상 키워드의 낱말에는 쉼표를 쓸 수 없어요',
  CRITERIA_TERM_DUPLICATE: '같은 묶음에 같은 낱말을 두 번 넣을 수 없어요',
  CRITERIA_TERMS_NOT_ALLOWED: '낱말 목록은 대상 키워드 줄에만 넣을 수 있어요',
  CRITERIA_TEXT_LENGTH: '기준 글은 1~300자로 써 주세요',
  CRITERIA_TEXT_MULTILINE:
    '기준 글은 줄바꿈이나 보이지 않는 글자 없이 한 줄로 써 주세요',
  CRITERIA_GUIDELINE_LENGTH: '근거 가이드라인은 1~200자로 써 주세요',
};

export const GREENWASH_SETTING_TEXT = {
  /** AD-02 모듈 줄의 글(K9 — 공통 표 AI_SETTING_TEXT 에서 옮김, 글자 그대로). */
  module: {
    name: '그린워싱',
    /** 모델 설정 카드 머리 곁 글(r3 원문 — 한 문장, 마침표 없음). */
    modelNote: '모든 단계에 같이 쓰여요 · 모델 하나로 네 프롬프트를 불러요',
    /** 고정 규칙 카드 머리·꼬리(꼬리 두 문장 — 마침표 둠). */
    codeRules: {
      title: '고정 규칙 · 읽기 전용',
      foot: '고정 규칙은 프롬프트 글에서 고칠 수 없어요. 바꾸려면 흐름(코드)을 고쳐요.',
    },
  },
  /** 대상 단어 카드(디자인 사본 AD-02_r3 · cd 답 · D1~D4·D6). */
  terms: {
    title: '대상 단어',
    /** 고침 꼬리표(「● 고침 2」의 글 — 점은 그림). */
    edited: (n: number) => `고침 ${n}`,
    /** 안내(세 문장 — 마침표 둠, r2 사본 그대로). */
    notice:
      '고객사의 새 점검 화면에 읽기 전용으로 보이는 기본 단어예요. 결과의 단어 빈도를 문서 전체에서 이 단어로 세어요(AI 비용 없음). 고친 것은 위 [새 버전으로 저장]으로 함께 남아요.',
    add: '추가',
    remove: '삭제',
    /** 초안: 입력 칸 이름표(화면에는 자리 글만 보인다). */
    input: '더할 단어',
    placeholder: '단어 넣고 Enter',
    selectAll: '전체 고르기',
    word: '단어',
    use: '사용',
    pick: (word: string) => `${word} 고르기`,
    switchLabel: (word: string) => `${word} 사용`,
    /** 더한 줄 꼬리표(저장 전에만). */
    addedTag: '추가',
    /** 표 아래 줄(D2). */
    foot: (all: number, on: number, added: number) =>
      `${all}개 · 사용 ${on}개${added > 0 ? ` · 새로 더한 ${added}개는 저장 전이에요` : ''}`,
    /** 켠 것 0(D4 — 카드 아래). */
    noneEnabled: '켠 단어가 하나 이상 있어야 저장할 수 있어요',
    /** [추가] 입력 오류(D1 — 칸 아래 빨강 한 줄). */
    problem: {
      length: '1~30자로 써 주세요',
      chars: '괄호와 따옴표는 쓸 수 없어요',
      duplicate: '이미 있는 단어예요',
      count: '단어는 100개까지 넣을 수 있어요',
    },
    /** 저장 거절 code(TERMS_*) → 화면 글(창 줄 「대상 단어 — <글>」·짚은 줄 아래). 서버 문장은 보이지 않는다. */
    refused: {
      // 초안: 웹이 길이·괄호를 먼저 막아 서버까지 오는 것은 글자 없음·보이지 않는 글자뿐(디자인 D1 「글자나 숫자가 …」).
      TERMS_TEXT:
        '글자나 숫자가 하나 이상 있어야 하고 보이지 않는 글자는 쓸 수 없어요',
      TERMS_DUPLICATE: '이미 있는 단어예요',
      TERMS_COUNT: '단어는 100개까지 넣을 수 있어요',
      TERMS_NONE_ENABLED: '켠 단어가 하나 이상 있어야 저장할 수 있어요',
    },
    /** 구성 열 꼬리(D3 — 전체 낱말 수). */
    sum: (n: number) => `${n}개`,
    /** 저장 창 「고친 것」 조각(D6 — 0 조각 뺌). */
    changed: {
      label: '대상 단어',
      added: (n: number) => `${n}개 추가`,
      removed: (n: number) => `${n}개 삭제`,
      toggled: (n: number) => `${n}개 사용 바꿈`,
      join: ' · ',
    },
  },
  /** 기본 판 줄(디자인 D2): 이름은 서버 default.name 그대로, 적용 아닐 때 배지 「기본」(grey), 꼬리 글. */
  defaultRow: { badge: '기본', sum: '코랩 원본' },
  /** 만든 사람 이름을 못 풂(초안). */
  unknownAuthor: '알 수 없는 사람',
  /** 판 열 끝 — 서버 total 이 실린 수보다 많을 때(초안). */
  more: '더 보기',
  /** [새 버전] 끈 단추의 title(디자인 D1 — 가정). 한 문장 — 마침표 뺌. */
  newVersionTitle: '고친 뒤 저장하면 새 버전이 만들어져요',
  /** 구성 열 꼬리 — 서버에 없는 구성(디자인 D4). */
  pendingSum: '준비 중',
  /** 기본 정보 메모가 비었을 때(디자인 D6). */
  emptyMemo: '–',
  /** 판정 기준 카드 안내 글(디자인 D1 — 세 문장, 마침표 둠). r2 의 「… {version} 에 남아요 …」를 갈음. */
  saveNotice:
    '저장하면 이 표로 새 버전이 만들어져요. 지금 버전과 적용 중인 버전은 바뀌지 않아요. 사용을 끈 줄은 프롬프트에서 빠져요.',
  /** 저장 뒤 알림 줄(디자인 D1 — 가정). */
  saved: (name: string) => `${name} 으로 저장했어요`,
  /** 저장 실패(디자인 D5 — 두 문장, 마침표 둠). 모르는 code·NAME_CONFLICT·5xx·끊김. */
  saveFailed: '저장하지 못했어요. 다시 저장해 주세요.',
  /** 기준 글 검사(웹 — 서버와 같은 규칙). 300 넘음은 디자인 답(197 노트 10:57), 그 밖은 서버 문장(초안). */
  textProblem: {
    tooLong: '300자까지 쓸 수 있어요',
    empty: '기준 글은 1~300자로 써 주세요',
    multiline: '기준 글은 줄바꿈이나 보이지 않는 글자 없이 한 줄로 써 주세요',
  },
  /** 가이드라인 칸 머리 옆 회색 글(G2c 디자인 답 (1)). */
  guidelineNote: '기록용 · 판정에 쓰이지 않아요',
  /** 고정 규칙 넷(G2c 디자인 답 (4) — 원문 그대로, 한 문장은 마침표 뺌). */
  fixedRules: [
    'Low 를 내지 않아요(Low 는 코드 규칙이 먼저 정해요)',
    '핵심 근거가 비면 NonRisk 를 내지 않아요(최소 Mid)',
    '핵심 근거가 충분하면 NonRisk 로 해요',
    '답의 꼴(JSON 칸)은 코드가 정해요',
  ],
  /** 표 아래 셈 글(디자인 14 답 10-20: r2 의 「기준 글은 자리 글이에요…」 꼬리는 시안에만 있는 설명이라 웹에 두지 않는다 — 셈만). */
  criteriaFoot: (c: {
    all: number;
    targetKeyword: number;
    coreEvidence: number;
    high: number;
    mid: number;
    exception: number;
  }) =>
    `기준 ${c.all}줄(대상 키워드 ${c.targetKeyword}묶음 · 핵심 근거 ${c.coreEvidence} · High ${c.high} · Mid ${c.mid} · 예외 조항 ${c.exception})`,
  /** 처리 흐름 띠(AS3b ② — 디자인 사본 AD-02_r3 「처리 흐름」, 번호 마디 이름은 서버 label). 한 문장 글은 마침표 없음. */
  flow: {
    title: '처리 흐름',
    note: '흐름은 코드로 정해져 있어요 · 번호 붙은 단계의 프롬프트 글만 고칠 수 있어요 · 단계를 누르면 아래에 그 프롬프트가 열려요',
    start: ['사용자 지정', '페이지'],
    merge: ['분석 결과 통합·매칭', '후보 문장 + 관련 분석', '+ 검색 근거'],
    decision: ['선언적', '문장인가?'],
    decisionNote: '기존 판정 로직',
    yes: '예',
    no: '아니요',
    generic: '일반적이면',
    keep: '아니면 그대로',
    end: ['결과', '검토 화면'],
    /** 번호 마디의 하는 일·도는 횟수(웹 글 — 이름은 서버 label). */
    steps: {
      detect: {
        does: '페이지에서 환경 주장 문장 후보를 골라요',
        runs: '페이지마다 한 번',
      },
      eval: {
        does: '근거를 보고 등급·사유·수정 방향을 써요',
        runs: '문장마다 한 번',
      },
      repair: { does: '수정 방향이 일반적이면 다시 써요', runs: '필요할 때만' },
      low_only: {
        does: '선언적 문장에 사유·수정 방향만 써요',
        runs: '선언적 문장마다',
      },
    },
    /** 마디 이름표(「2. 판정 프롬프트 보기」, 고쳤으면 「, 고침」). */
    nodeLabel: (n: number, label: string, edited: boolean) =>
      `${n}. ${label} 프롬프트 보기${edited ? ', 고침' : ''}`,
    edited: '고침',
    /** 서버가 짚은 칸(셋째 열 「고칠 곳 있음」과 같은 글 — cd 답 10-22). */
    refused: '고칠 곳 있음',
  },
  /** 판정 기준 상세 불러오기 실패(디자인 D5 — CM-03 꼴, [다시 시도] 는 AI_SETTING_TEXT.retry). */
  detailFailed: '판정 기준을 불러오지 못했어요',
  detailLoading: '판정 기준을 불러오는 중',
  /** 적용 확인 창(디자인 D3 · v110 AD-02-CM ③). 기본 판이면 이름 자리에 「기본 버전」. */
  apply: {
    defaultName: '기본 버전',
    title: (name: string) => `${name} 을 적용할까요?`,
    /** 두 문장 — 마침표 둠. 지금 적용 판(m)이 이름. */
    body: (name: string, current: string) =>
      `다음 실행부터 ${name} 을 써요. 이미 돌고 있는 실행은 ${current} 으로 끝나요.`,
    cancel: '취소',
    confirm: '적용',
    /** 적용 뒤 알림(두 문장 — 마침표 둠). */
    done: (name: string) =>
      `${name} 을 적용했어요. 다음 실행부터 ${name} 을 써요.`,
    /** 창 안 오류 줄(디자인 D3 — 가정, 두 문장). */
    failed: '적용하지 못했어요. 다시 눌러 주세요.',
  },
} as const;
