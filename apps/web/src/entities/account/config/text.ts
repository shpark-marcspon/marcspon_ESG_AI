// 어드민 틀과 AD-01 계정 관리의 문구 표(밴드 AD1). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다.
// 이 파일은 아무것도 가져오지 않는다(app/guards/layers.test.ts 가 지킨다). e2e 가 이 표로 단언한다.
//
// 출처: 디자인 캔버스 「공통」 AD-01_r1·AD-01a_r1·AD-01b_r1·AD-01c_r1(판 1792310815-aa99) 원문. 말투는 해요체.
// 끝 마침표: 한 문장 글은 뺀다(MARC-ENT-269 — 표 아래 글도). 두 문장 글은 시안 원문 그대로 둔다.
// 틀 글(shell)은 AD2 때 자리를 옮길지 정한다(감독 판단 9). LNB 꼬리표 「관리자」는 이번엔 그리지 않는다(디자인 원문).
// 회사 이름(「고객사 A」)은 받을 경로가 없어 세 자리에서 뺐다(감독 판단 8 (가) — 디자인 원문 받아들임).
// 시안에 없던 글(초안 — 디자인 감독이 받아들임, 2026-10-18 sid:MARC-TICK-72 노트): 목록 실패·빈 목록·422 칸 글·만들기 실패·초기화 실패·
//   초기화 뒤 누구 줄·없는 계정·복사 실패. 쓰기 실패 끝은 LG1 ④ 디자인 원문 꼴(「잠시 뒤 다시 시도해 주세요.」 — 감독 판단 13).
//   아직 확정 전: 복사 성공 글·복사 실패 글은 이 밴드의 초안이다.
// ③ 의 글: 검색·상태 고르기·[사용 중지]·[취소]·[저장]·「편집 중」·AD-01c 는 시안 원문.
//   초안(디자인 확인 전): 거른 결과 없음, [다시 사용] 확인 모달의 제목·본문, 상태 고르기 이름·[이름 고치기] 이름(화면 읽기용).
// UA1W(실서버 쓰기)의 글 — 디자인 원문(marcspon-e0, 2026-10-19 밤, 발주서 끝 「디자인 원문」): 「만든 날」 열, 사용 중지 확인 본문
//   (이미 로그인한 사람도 {분}분 안에 — 분은 model 의 ACCESS_TTL_MINUTES 를 화면이 넣는다), 여럿 쓰기 일부 실패 글(모달 안 버튼 줄 위 —
//   성공이 있으면 성공 수를 앞에, 디자인 대조 C1 감독 판단 2026-10-19),
//   이름 고침 실패 글 셋(404 는 초기화의 「이 계정을 찾을 수 없어요」, 422 는 만들기의 「입력한 값을 확인해 주세요」와 같은 글).
//   쓰기 단추 옆 「준비 중」 글은 서버가 와서 걷었다(MARC-ENT-285).

export const ACCOUNT_TEXT = {
  /** 어드민 틀(AD-01_r1 의 LNB·머리 줄). */
  shell: {
    menuLabel: '관리자 메뉴',
    /** 「AI 설정」 하위 줄 묶음 이름(시안 AD-02_r3 .a-subnav aria-label). */
    aiSettingsModulesLabel: 'AI 설정 모듈',
    logo: '로고 자리',
    title: '관리자',
    /** 제목 옆 꼬리표(시안 .a-staff). */
    staff: 'STAFF',
    /** 시안 글 그대로 — 이름을 넣지 않는다. */
    greeting: '운영 관리자님 안녕하세요',
    menu: {
      accounts: '계정 관리',
      aiSettings: 'AI 설정',
      runs: '실행 기록',
      audit: '감사 기록',
      service: '서비스 화면',
      /** 밴드 W12-0a ③: 설정 > 선택항목(S18 — 시안 「설정(선택항목·언어·EDK계정)」 중 선택항목 하나). */
      options: '선택항목',
      /** 밴드 W12-0b1 ③: 인벤토리 관리 > 온실가스 인덱스(S19 — Figma 운영 콘솔 「인벤토리 관리 > 온실가스 인덱스」 한 줄). */
      ghgIndex: '온실가스 인덱스',
      /** 「AI 설정」 하위 줄(밴드 LN1 — 시안 AD-02_r3 차례·글). */
      aiSettingsGreenwash: '그린워싱',
      /** 시안 「Scope 3」 줄 — 사용자 10-26 「온실가스」로(결정 441 노트). 사용자 화면 모듈 메뉴 ghg 글과 같다. */
      aiSettingsGhg: '온실가스',
      aiSettingsMateriality: '중대성평가',
      aiSettingsDataverify: '데이터 검증',
      aiSettingsTranslation: '영문번역',
      aiSettingsDrafting: '보고서 작성',
    },
  },
  /** AD-01 계정 관리. */
  list: {
    title: '고객사 사용자 계정 관리',
    description: (count: number) =>
      `고객사 사용자 계정 ${count}개 · 운영 관리자가 계정을 만들고, 비밀번호를 잊으면 운영 관리자가 초기화해요`,
    /** 두 문장 — 끝 마침표 둠. */
    notice:
      '1차에는 회사가 1곳으로 정해져 있고, 여기의 계정은 모두 고객사 사용자 계정이에요. 모든 계정은 이 회사에 속하고, 같은 회사의 문서를 함께 봐요.',
    create: '계정 만들기',
    tableLabel: '고객사 사용자 계정',
    columns: {
      username: '아이디',
      name: '이름',
      status: '상태',
      lastLogin: '마지막 로그인',
      createdAt: '만든 날',
      password: '비밀번호',
    },
    never: '—',
    reset: '초기화',
    /** 그 줄의 [초기화] 이름(화면 읽기용). */
    resetLabel: (username: string) => `${username} 비밀번호 초기화`,
    /** 한 문장 — 끝 마침표 뺌(MARC-ENT-269, 감독 판단 11). */
    foot: '초기화하면 임시 비밀번호가 한 번만 보이고, 그 계정은 다음 로그인 때 새 비밀번호를 정해요',
    loading: '계정 목록을 불러오는 중',
    failed: '계정 목록을 불러오지 못했어요',
    retry: '다시 시도',
    empty: '아직 만든 계정이 없어요',
    /** 거른 결과가 없을 때(초안). */
    noMatch: '조건에 맞는 계정이 없어요',
    searchLabel: '아이디 또는 이름 검색',
    searchPlaceholder: '아이디 · 이름 검색',
    statusLabel: '상태로 거르기',
    statusAll: '전체 상태',
    deactivate: '사용 중지',
    reactivate: '다시 사용',
    cancel: '취소',
    save: '저장',
    selectAll: '전체 고르기',
    select: (username: string) => `${username} 고르기`,
    editing: '편집 중',
    /** 이름 칸 단추의 이름(화면 읽기용, 초안). */
    editName: (username: string) => `${username} 이름 고치기`,
    nameLabel: '이름',
    /** 이름 고침 실패(거르기 줄의 단추 무리 옆 한 줄 — 디자인 원문 Q5). */
    rename: {
      /** 404 USER_NOT_FOUND(초기화의 글과 같다). */
      missing: '이 계정을 찾을 수 없어요',
      /** 422(만들기의 칸 글과 같다). */
      invalid: '입력한 값을 확인해 주세요',
      failed: '이름을 바꾸지 못했어요. 잠시 뒤 다시 시도해 주세요.',
    },
  },
  /** 상태 배지(디자인 원문 — 잠김 빨강). */
  status: {
    inactive: '사용 중지',
    locked: '잠김',
    initial: '초기화 대기',
    active: '사용 중',
  },
  /** AD-01a 계정 만들기. */
  create: {
    title: '계정 만들기',
    lead: '고객사 사용자 계정이에요',
    username: '아이디',
    usernameHelp:
      '영문 · 숫자와 . @ + - _ 만 쓸 수 있어요 · 만든 뒤에는 바꿀 수 없어요',
    name: '이름',
    nameHelp: '담당자 이름이나 부서',
    nameCount: (n: number, max: number) => `${n} / ${max}`,
    notice: '임시 비밀번호는 자동으로 정해지고, 만든 뒤 한 번만 보여요',
    cancel: '취소',
    submit: '만들기',
    submitting: '계정을 만드는 중',
    /** 409 USERNAME_TAKEN(시안 원문 — 두 문장). */
    taken: '이미 쓰고 있는 아이디예요. 다른 아이디를 입력해 주세요.',
    /** 422 VALIDATION_ERROR 의 칸 글(초안). */
    invalid: '입력한 값을 확인해 주세요',
    failed: '계정을 만들지 못했어요. 잠시 뒤 다시 시도해 주세요.',
  },
  /** 비밀번호 초기화 확인(AD-01c 와 같은 꼴). */
  reset: {
    title: (username: string) => `${username} 의 비밀번호를 초기화할까요?`,
    /** 한 문장 — 끝 마침표 뺌(MARC-ENT-269. 시안에는 있다). */
    body: '지금 비밀번호로는 더 로그인할 수 없고, 임시 비밀번호가 새로 정해져요',
    cancel: '취소',
    submit: '초기화',
    submitting: '비밀번호를 초기화하는 중',
    missing: '이 계정을 찾을 수 없어요',
    failed: '비밀번호를 초기화하지 못했어요. 잠시 뒤 다시 시도해 주세요.',
  },
  /** AD-01c 사용 중지 확인과 [다시 사용] 확인(같은 꼴). */
  active: {
    deactivateTitle: (n: number) => `계정 ${n}개를 사용 중지할까요?`,
    /** 세 문장 — 디자인 원문(UA1W Q13). minutes 는 access 가 통하는 분(ACCESS_TTL_MINUTES). */
    deactivateBody: (minutes: number) =>
      `사용 중지한 계정은 로그인할 수 없어요. 이미 로그인한 사람도 ${minutes}분 안에 끊겨요. 올린 문서와 기록은 그대로 남아요.`,
    /** 일부(또는 모두) 실패 — 모달 안 버튼 줄 바로 위 빨강 한 줄(디자인 원문 Q4). count 는 실패한 수. */
    deactivateFailed: (count: number) =>
      `계정 ${count}개를 사용 중지하지 못했어요. 잠시 뒤 다시 시도해 주세요.`,
    deactivate: '사용 중지',
    /** [다시 사용] 확인(초안 — 시안에 없다). */
    reactivateTitle: (n: number) => `계정 ${n}개를 다시 사용할까요?`,
    reactivateBody: '다시 사용한 계정은 다시 로그인할 수 있어요',
    reactivateFailed: (count: number) =>
      `계정 ${count}개를 다시 사용하지 못했어요. 잠시 뒤 다시 시도해 주세요.`,
    /** 성공이 하나 이상인 일부 실패(done 성공 수, count 실패 수). 모두 실패면 위 두 글. */
    deactivatePartly: (done: number, count: number) =>
      `계정 ${done}개는 사용 중지했어요. ${count}개는 하지 못했어요. 잠시 뒤 다시 시도해 주세요.`,
    reactivatePartly: (done: number, count: number) =>
      `계정 ${done}개는 다시 사용하게 했어요. ${count}개는 다시 사용하게 하지 못했어요. 잠시 뒤 다시 시도해 주세요.`,
    reactivate: '다시 사용',
    who: (username: string, name: string) => `${username} · ${name}`,
    cancel: '취소',
  },
  /** AD-01b 임시 비밀번호. */
  password: {
    title: '임시 비밀번호를 전해 주세요',
    created: (username: string, name: string) =>
      `${username} · ${name} · 계정을 만들었어요`,
    reset: (username: string, name: string) =>
      `${username} · ${name} · 비밀번호를 초기화했어요`,
    label: '임시 비밀번호',
    copy: '복사',
    copied: '복사했어요',
    copyFailed: '복사하지 못했어요. 칸의 글자를 골라 직접 복사해 주세요.',
    /** 두 문장 — 시안 원문. */
    important: '이 창을 닫으면 다시 볼 수 없어요. 잊으면 다시 초기화해요.',
    next: '이 계정은 다음 로그인 때 새 비밀번호를 정해요',
    confirm: '확인',
  },
} as const;
