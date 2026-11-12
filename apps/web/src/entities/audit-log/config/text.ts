// AD-05 감사 기록의 문구 표(밴드 AD2 ①). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다. 이 파일은 아무것도 가져오지 않는다.
// 출처: 디자인 캔버스 「어드민」 AD-05_r1(판 1792310815-aa99) 원문. 말투는 해요체, 한 문장 글은 끝 마침표 뺌(MARC-ENT-269), 두 문장 글은 원문 그대로.
// 예시 데이터 띠·바닥글 「이름과 숫자는 모두 지어낸 예시예요」는 실서버(AD5R)에서 걷었다(sid:MARC-ENT-285 — AD-05 에서만).
// 디자인 원문 2(발주서 끝): 불러오기 실패 「감사 기록을 불러오지 못했어요」·거른 결과 없음 「조건에 맞는 기록이 없어요」 확정.
// 초안(디자인 확인 전): 거르기 칸 이름(화면 읽기용 「기간으로 거르기」 꼴), 불러오는 중 숨은 글.
// 실서버(밴드 AD5R): 행동 아홉(키 = 서버 action 값), 사람 대체 글·대상 글·실패 까닭(entry), 「{n}건 중 {m}건」·[더 보기]·더 보기 실패·[거르기 풀기]·
//   안내 띠 새 글, 0건 빈 상태 글(디자인 원문 2 — 발주서 「디자인 원문 2」) — 디자인 원문(캔버스 v99 판 AD-05, 발주서 band-handoffs/AD5R-order.md 「디자인 원문」). 확정(초안 아님).
// AD4X ③: AI 설정 줄 「[AI 설정] · 그린워싱 · v3 만듦」·「… · v2 적용」 — 캔버스 v127 AD-05_r1 원문. 「(v2 바탕)」은 서버가 바탕 판을 싣지 않아 뺐다(디자인 확인 거리).
//   초안: 기본 판 적용 「기본 설정 적용」(판에 없음). 모듈 이름은 실행 기록 문구 표의 사본.

export const AUDIT_TEXT = {
  title: '감사 기록',
  /** 두 문장 — 끝 마침표 둠. */
  description:
    '누가 언제 무엇을 했는지 남아요. 기록은 고치거나 지울 수 없어요.',
  searchPlaceholder: '사람·대상 검색',
  searchLabel: '사람·대상 검색',
  period: {
    label: '기간',
    name: '기간으로 거르기',
    options: { week: '이번 주', month: '이번 달', all: '전체' },
  },
  actor: { label: '사람', name: '사람으로 거르기', all: '전체' },
  action: { label: '행동', name: '행동으로 거르기', all: '전체' },
  count: (n: number) => `${n}건`,
  /** 다 불러오지 않았을 때(디자인 원문 — 「128건 중 50건」). */
  countOf: (total: number, shown: number) => `${total}건 중 ${shown}건`,
  tableLabel: '감사 기록',
  columns: {
    at: '시각',
    actor: '사람',
    action: '행동',
    target: '대상',
    result: '결과',
  },
  /** 행동 아홉(키 = 서버 action 값). */
  actions: {
    login: '로그인',
    logout: '로그아웃',
    upload: '업로드',
    run: '실행',
    download: '내려받기',
    setting_change: '설정 변경',
    adopt: '채택',
    exclude: '제외',
    confirm: '확정',
  },
  /** 줄의 사람·대상·실패 까닭 글(model 의 toEntry·actorOptions 에 넣는다 — AuditEntryWords 꼴). */
  entry: {
    actor: {
      command: '관리 명령',
      anonymous: '없는 아이디',
      unknown: '알 수 없는 사람',
      admin: ' · 운영 관리자',
    },
    target: {
      account: '계정',
      created: (label: string | null) =>
        label === null ? '만듦' : `${label} 만듦`,
      reset: (label: string | null) =>
        label === null ? '비밀번호 초기화' : `${label} 비밀번호 초기화`,
      updated: (label: string | null) =>
        label === null ? '고침' : `${label} 고침`,
      passwordChanged: '비밀번호 바꿈',
      aiSetting: 'AI 설정',
      settingCreated: (label: string | null) =>
        label === null ? '만듦' : `${label} 만듦`,
      settingApplied: (label: string) => `${label} 적용`,
      defaultSetting: '기본 설정',
    },
    /** 모듈 여섯(키 = 서버 module id). 실행 기록 문구 표(RUN_LOG_TEXT.modules)의 사본 — entities 끼리 가져오지 않는다(같음은 화면 시험이 본다). */
    modules: {
      'inventory.scope3': '온실가스 Scope 3',
      greenwash: '그린워싱',
      materiality: '중대성평가 IRO',
      dataverify: '데이터 검증',
      translation: '영문번역',
      drafting: '보고서 작성',
    } as Readonly<Record<string, string>>,
    reasons: {
      wrong_password: '비밀번호 틀림',
      unknown_user: '없는 아이디',
      inactive_user: '사용 중지된 계정',
      account_locked: '잠긴 계정',
    },
  },
  noTarget: '—',
  success: '성공',
  /** 까닭이 빈 글자면(모르는 까닭) 「실패」만. */
  failure: (reason: string) => (reason === '' ? '실패' : `실패 · ${reason}`),
  more: '더 보기',
  /** 한 문장 — 끝 마침표 뺌. */
  moreFailed: '기록을 더 불러오지 못했어요',
  clearFilter: '거르기 풀기',
  /** 기간만 거른 0건의 제목(디자인 원문 2 — 「이번 주 기록이 없어요」). */
  emptyPeriod: (period: string) => `${period} 기록이 없어요`,
  /** 그 보조 줄(디자인 원문 2 그대로 — 마침표 둠). */
  widenPeriod: '기간을 넓혀 보세요.',
  /** 기간 「전체」의 0건(보조 줄 없음). */
  emptyAll: '아직 기록이 없어요',
  /** 세 문장 — 원문 그대로(디자인 원문 6). */
  notice:
    '행동: 로그인 · 로그아웃 · 업로드 · 실행 · 내려받기 · 설정 변경 · 채택 · 제외 · 확정. 계정 줄은 계정 관리로 이어져요. 이름이 회색인 줄은 사람을 찾을 수 없는 기록이에요.',
  loading: '감사 기록을 불러오는 중',
  failed: '감사 기록을 불러오지 못했어요',
  retry: '다시 시도',
  noMatch: '조건에 맞는 기록이 없어요',
} as const;
