// 로그인·비밀번호 바꾸기 화면의 문구 표(밴드 LG1). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다.
// 이 파일은 아무것도 가져오지 않는다(app/guards/layers.test.ts 가 지킨다). e2e 가 이 표로 단언한다(N10).
//
// 출처: 디자인 캔버스 「공통」 CM-01_r1·CM-01a_r1·CM-01b_r1·CM-02_r1(캔버스 버전 89) 원문. 말투는 해요체.
// 끝 마침표: 한 문장 글은 뺀다(MARC-ENT-269). 두 문장 글은 시안 원문 그대로 둔다(감독 판단 6).
// 시안에 없던 상태의 글 다섯(로그인 실패·바꾸기 실패·처음부터 다시·비밀번호 거절·규칙 「아직」)은 디자인 감독 원문이다
//   (2026-10-18, sid:MARC-TICK-72 노트 — 밴드 LG1 ④). 끝 마침표도 그 원문대로.
// 확정 전인 것(무효 조건):
//   - 서비스 이름 「ESG 공시 대응 AI 솔루션」·「로고 자리」는 시안의 자리표 글이다.

const locked =
  '로그인에 5번 실패해 10분 동안 잠겼어요. 10분 뒤에 다시 시도해 주세요.';

export const SESSION_TEXT = {
  /** 카드 머리(시안의 자리표). */
  brand: { logo: '로고 자리', service: 'ESG 공시 대응 AI 솔루션' },
  /** CM-01 로그인과 CM-01a 실패 글. */
  login: {
    title: '로그인',
    username: '아이디',
    usernamePlaceholder: '아이디를 입력해 주세요',
    password: '비밀번호',
    passwordPlaceholder: '비밀번호를 입력해 주세요',
    showPassword: '비밀번호 보기',
    submit: '로그인',
    submitting: '로그인하는 중',
    forgot: '비밀번호를 잊으셨나요?',
    foot: '계정은 운영 관리자가 만들어 드려요',
    /** 401 INVALID_CREDENTIALS·422 VALIDATION_ERROR. 어느 칸인지·사용 중지인지 밝히지 않는다(MARC-ENT-282). */
    invalid: '아이디 또는 비밀번호가 맞지 않아요. 다시 확인해 주세요.',
    /** 401 ACCOUNT_LOCKED(MARC-ENT-283 — 계정 있음이 드러나는 것은 받아들인 위험). */
    locked,
    /** 연결 끊김·5xx·꼴 밖의 답(디자인 감독 원문). */
    failed: '로그인하지 못했어요. 잠시 뒤 다시 시도해 주세요.',
    /** 카드 위 unreachable 띠 안의 단추(부팅 복원을 한 번 더 — 디자인 감독 원문, sid:MARC-ISSUE-337 노트). */
    retry: '다시 시도',
  },
  /** 로그인 화면에 뜨는 세션의 안내(SessionNotice). */
  notice: {
    /** refresh 실패(MARC-ENT-260 5). */
    expired: '로그인이 끝났어요. 다시 로그인해 주세요',
    locked,
    /** 임시 비밀번호를 잃었거나(새로고침) 지금 비밀번호가 맞지 않음. 오류 띠가 아니라 회색 안내 띠(디자인 감독 원문). */
    relogin: '임시 비밀번호로 다시 로그인해 주세요',
    /** 부팅 복원이 서버에 닿지 못함(연결 끊김·5xx·상한 — refresh 는 남는다). 디자인 감독 원문(sid:MARC-ISSUE-337 노트). */
    unreachable:
      '서비스에 연결하지 못했어요. 잠시 뒤 다시 시도하거나 다시 로그인해 주세요',
  },
  /** CM-02 첫 로그인 비밀번호 바꾸기. */
  password: {
    title: '새 비밀번호를 정해 주세요',
    lead: '운영 관리자가 초기화한 임시 비밀번호로 로그인했어요. 계속하려면 새 비밀번호로 바꿔야 해요.',
    who: (username: string) => `${username} · 임시 비밀번호로 로그인함`,
    newPassword: '새 비밀번호',
    showNew: '새 비밀번호 보기',
    confirm: '새 비밀번호 확인',
    showConfirm: '새 비밀번호 확인 보기',
    rulesLabel: '비밀번호 규칙',
    ruleLength: '8자 이상',
    /** 규칙 줄 끝의 상태 글. 못 채움 「아직」은 디자인 감독 원문(회색 원 X·text-tertiary — 빨강 아님). */
    ruleMet: '충족',
    ruleUnmet: '아직',
    mismatch: '새 비밀번호와 같지 않아요. 다시 입력해 주세요.',
    submit: '비밀번호 바꾸고 시작하기',
    submitting: '비밀번호를 바꾸는 중',
    logout: '로그아웃',
    /** 400 PASSWORD_REJECTED·422 VALIDATION_ERROR. 새 비밀번호 칸 아래 오류 글(서버 message 는 보이지 않는다 — 감독 판단 5). */
    rejected: '이 비밀번호는 쓸 수 없어요. 다른 비밀번호를 입력해 주세요.',
    /** 연결 끊김·5xx(디자인 감독 원문). */
    failed: '비밀번호를 바꾸지 못했어요. 잠시 뒤 다시 시도해 주세요.',
  },
  /** CM-01b 비밀번호 안내 모달. */
  forgot: {
    title: '비밀번호를 잊으셨나요?',
    body: '비밀번호는 운영 관리자가 초기화해 드려요. 운영 관리자에게 초기화를 요청한 뒤, 받은 임시 비밀번호로 로그인해 주세요.',
    confirm: '확인',
  },
} as const;
