// AD-02 보고서 작성 탭의 문구 표(밴드 RPA3). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다. 이 파일은 아무것도 가져오지 않는다.
// 출처: 시안 AD-02-RP r1(캔버스 v193, rv-note 글·프롬프트 몸 글·메모 예시·처리 값 숫자는 옮기지 않음). 말투는 해요체, 한 문장 글은 끝 마침표 뺌(sid:MARC-ENT-269).
// 마디·칸·모델 칸·고정 값 이름은 서버 label(웹 글 0 — sid:MARC-ENT-442). 여기는 마디 아래 하는 일·빈도, 고정 상자 글, 칸 아래 안내뿐이다.
//   모델 카드 곁 글(모의 공급사 안내)은 뺐다(밴드 RPA4 — sid:MARC-ISSUE-490 처분 Q1 (가) 뒤집음, 모의 위끝은 서버가 칸 값과 4,000 중 작은 것으로).
// 시안 글은 흐름 코드(drafting/flows/draft_v2.py — map 은 쪽 묶음마다 S2, draft 는 목차 잎마다 S3 · 쪽 0 이면 no_material 로 짓지 않음 ·
//   engines/v2/checks.py 결정적 출처 검사 — 근거 없거나 원문에 없는 숫자면 unsupported 표시)와 대 봤다(대조 표는 band-reports/RPA3.md).
// 모듈 이름 「보고서 작성」은 메뉴 낱말(ACCOUNT_TEXT shell.menu.aiSettingsDrafting)·시안 제목과 같다(sid:MARC-ENT-525). 같음은 모듈 줄 시험이 본다.
//   감사·실행 기록 낱말(AUDIT_TEXT.entry.modules · RUN_LOG_TEXT)에도 같은 이름으로 들어갔다(밴드 AD6, 병합 7a7c5601).

export const DRAFTING_SETTING_TEXT = {
  module: {
    name: '보고서 작성',
    /** 프롬프트 상세 첫 줄 라벨(칸 이름이 「지시 글」·「입력 글」 — TRA2 D9). */
    slotLabel: '칸',
  },
  /** [이 버전 적용] 줄 아래 적용 안내(밴드 RPW12 · 디자인 c3 확정 11-10 — 적용은 다음 실행부터, 이어 받기 없음 sid:MARC-ENT-656). */
  applyNote:
    '적용한 설정은 다음 실행부터 써요 · 도는 중인 실행은 그대로예요 · 다음 실행은 앞 초안을 이어 받지 않고 전부 새로 지어요',
  /**
   * 입력 글 칸 아래 자리 안내(DVA2 이슈 sid:MARC-ISSUE-370 처분 (가) 꼴 — 칠하기 0, 그 칸의 자리를 늘어놓는다).
   * 꼴은 「<자리들> 자리는 실행 때 채워요 · 지우면 저장할 수 없어요」(시안 칸 아래 g-small). 지시 글 둘은 자리가 없어 줄 0.
   */
  placeholders: {
    lead: (slots: readonly string[]) =>
      `${slots.join(' · ')} 자리는 실행 때 채워요`,
    tail: '지우면 저장할 수 없어요',
  },
  /** 처리 흐름 띠(시안 「처리 흐름」 .fa-rp). */
  flow: {
    title: '처리 흐름',
    note: '흐름은 코드로 정해져 있어요 · 번호 붙은 단계의 프롬프트 글만 고칠 수 있어요 · 단계를 누르면 아래에 그 단계의 칸이 열려요',
    /** 시작 상자(시안 .rp-s — 두 줄). */
    start: ['전년도 보고서', '· 목차'],
    /** 출처 확인 상자(시안 .rp-k — 흐름 코드 engines/v2/checks.py 와 같음). */
    check: '출처 확인 — 근거 페이지가 없거나 원문에 없는 숫자면 bullet 에 표시',
    /** 끝 상자(시안 .rp-e). */
    end: { title: '결과', lines: ['목차마다', 'bullet · 출처'] },
    /** 마디 1 아래 갈래 글(시안 .rp-l1 — draft_v2 no_material). */
    branch: '맞는 페이지가 없는 목차는 짓지 않아요',
    /**
     * 번호 마디의 하는 일·빈도 알약(웹 글 — 이름은 서버 묶음 label)과 칸 고름 머리 줄의 빈도 글(head — 시안 단계 머리).
     */
    steps: {
      map: {
        does: '페이지마다 맞는 목차를 골라요',
        runs: '페이지 묶음마다',
        head: '페이지 묶음마다 한 번',
      },
      draft: {
        does: '달린 페이지로 개조식을 지어요',
        runs: '목차마다',
        head: '목차마다 한 번',
      },
    },
    /** 칸 고름 이름표. */
    picker: '단계의 칸',
    edited: '고침',
    refused: '고칠 곳 있음',
    /** 마디 이름표(「1. 목차 달기 프롬프트 보기」, 고쳤으면 「, 고침」). */
    nodeLabel: (n: number, label: string, edited: boolean) =>
      `${n}. ${label} 프롬프트 보기${edited ? ', 고침' : ''}`,
    /** 칸 고름 머리 줄(「단계 2 초안 짓기」). */
    stepHead: (n: number, label: string) => `단계 ${n} ${label}`,
  },
} as const;
