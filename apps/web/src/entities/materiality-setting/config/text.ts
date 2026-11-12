// AD-02 중대성평가 IRO 탭의 문구 표(밴드 IRA2). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다. 이 파일은 아무것도 가져오지 않는다.
// 출처: 시안 AD-02-IR r1(캔버스 v170 — band-handoffs/IR-design-v170-boards, rv-note 글은 옮기지 않음. inputNote·규제 출력 안내는 v211 — 밴드 IRA3). 말투는 해요체, 한 문장 글은 끝 마침표 뺌, 두 문장 이상은 마침표 둠(sid:MARC-ENT-269).
// 마디·칸·고정 값 이름은 서버 label(웹 글 0 — sid:MARC-ENT-384·442). 여기는 마디 아래 하는 일·빈도, 고정 상자 글, 고정 규칙, 칸 아래 안내뿐이다.
// 시안 글이 흐름 코드(IR4 materiality/flows/colab_155·part2_155·iro_155 · prompt_model_155 OUTPUT_MARKS)와 어긋나면 코드 사실대로 둔다(DVA2 처분 5 — 대조 표는 band-reports/IRA2.md).
// 모듈 이름 「중대성평가 IRO」는 감사 낱말(AUDIT_TEXT.entry.modules.materiality)·시안 제목과 같다(메뉴 줄은 짧은 「중대성평가」 — 발주서 Q4). 같음은 모듈 줄 시험이 본다.

export const MATERIALITY_SETTING_TEXT = {
  module: {
    name: '중대성평가 IRO',
    /** 프롬프트 상세 첫 줄 라벨(칸 이름이 「지시 글」·「가변 입력」 — TRA2 D9). */
    slotLabel: '칸',
    /** 모델 설정 카드 머리 곁 글(시안 「모델 설정」 small). */
    modelNote:
      '모델 칸 둘 · 리서치 두 단계는 리서치 모델, 영향 · 재무 세 단계는 분석 모델을 불러요',
    /** 고정 규칙 카드 머리·꼬리(시안 「고정 규칙 · 읽기 전용」 — 꼬리 한 문장, 마침표 뺌). */
    codeRules: {
      title: '고정 규칙 · 읽기 전용',
      foot: '고정 규칙은 여기서 고칠 수 없어요',
    },
  },
  /** 고정 규칙 줄(시안 원문 — 흐름 코드와 대 봄. 두 문장 이상만 마침표 둠). */
  fixedRules: [
    '영향은 서브토픽마다 정해요. 중대성 점수는 매기지 않아요.',
    '리서치 두 단계는 늘 웹 검색을 써요. 영향 · 재무 단계는 새 평가에서 「최신 이슈 반영」을 켰을 때만 웹 검색을 써요.',
    '「5. 재무 영향 경로」는 「4. 재무 영향 정의」의 표를 받아요. 재무 영향을 정하지 못한 서브토픽은 건너뛰어요.',
    '신뢰 출처 목록은 입력의 업종 구분(금융·비금융)에 따라 둘 중 하나가 규제·정책 리서치에 쓰여요',
    '분석 모델에는 temperature 를 싣지 않아요',
    '출력 형식 절은 고치지 않는 것이 안전해요',
  ],
  /**
   * 칸 아래 자리 안내(K1 — 시안 칸 아래 g-small. 자리 칠하기가 없어(sid:MARC-ENT-433) 시안의 「{ } 자리」 대신 그 칸의 자리를 늘어놓는다).
   * 꼴은 「<자리들> 자리에는 실행 때 값이 끼워져요 — <어디서 오나> · 자리 이름은 지우지 마세요」. 규제 지시 글은 신뢰 출처 글(whitelist).
   * 영향·재무 입력 글에는 가치사슬 활동 자리가 있다(서버 REQUIRED — 시안 글에는 빠짐, 코드 사실대로).
   */
  placeholders: {
    lead: (slots: readonly string[]) =>
      `${slots.join(' · ')} 자리에는 실행 때 값이 끼워져요`,
    whitelist: (slots: readonly string[]) =>
      `${slots.join(' · ')} 자리에는 실행 때 입력의 업종 구분(금융·비금융)에 따라 「신뢰 출처 목록」의 비금융 · 금융 글 중 하나가 끼워져요`,
    /** 칸 key → 자리 값이 어디서 오나. */
    from: {
      impact_input:
        '기업명 · 산업 정의 · 가치사슬 활동 · 토픽 · 서브토픽은 새 평가에서 넣은 값, 두 리서치의 답은 1·2 묶음의 결과',
      financial_input:
        '기업명 · 산업 정의 · 가치사슬 활동 · 토픽 · 서브토픽은 새 평가에서 넣은 값, 두 리서치의 답은 1·2 묶음의 결과',
      pathway_input: '재무 영향 정의의 답은 4 묶음의 결과를 표로 옮긴 것',
    } as Readonly<Record<string, string>>,
    tail: '자리 이름은 지우지 마세요',
  },
  /** 1부 입력 글 셋(규제·키워드·이슈 입력) 아래 안내(시안 v211 AD-02-IR :182·:226·:274 — 한 문장, 마침표 뺌. 밴드 IRA3). */
  inputNote: '{ } 칸은 실행할 때 평가 만들기 입력이 들어가요',
  /** 출력절 안내(K2 — 시안 p-warn 여섯 칸 글, 두 문장이라 마침표 둠). 서버 outputSection 이 있는 칸만 그린다. */
  outputNotes: {
    regulation_system:
      '[9] URL 출력 형식 · [10] 출력 형식 강제 두 절은 답(JSON)과 주소를 읽는 꼴이에요. 이 절을 고치면 리서치 결과를 읽지 못할 수 있어요.',
    keywords_prefix:
      '3) 아래 JSON 형식으로만 절은 답(JSON)을 읽는 꼴이에요. 이 절을 고치면 키워드를 읽지 못할 수 있어요.',
    controversy_system:
      '[OUTPUT] 출력 형식 강제 절은 답(JSON)을 읽는 꼴이에요. 이 절을 고치면 리서치 결과를 읽지 못할 수 있어요.',
    impact_system:
      '[FINAL OUTPUT — JSON ONLY] 절은 답(JSON)을 읽는 꼴이에요. 이 절을 고치면 결과를 읽지 못할 수 있어요.',
    financial_system:
      '[FINAL OUTPUT — JSON ONLY] 절은 답(JSON)을 읽는 꼴이에요. 이 절을 고치면 결과를 읽지 못할 수 있어요.',
    pathway_system:
      '[FINAL OUTPUT — JSON ONLY] 절은 답(JSON)을 읽는 꼴이에요. 이 절을 고치면 결과를 읽지 못할 수 있어요.',
  } as Readonly<Record<string, string>>,
  /** 처리 흐름 띠(시안 「처리 흐름」 .fa--ir). */
  flow: {
    title: '처리 흐름',
    note: '흐름은 정해져 있어요 · 번호 붙은 단계와 신뢰 출처 목록의 글만 고칠 수 있어요 · 누르면 아래에 그 프롬프트가 열려요',
    /** 고정 상자 둘(입력 · 엑셀 만들기)과 끝 상자. */
    start: ['기업·토픽', '입력'],
    out: ['결과 엑셀', '만들기'],
    end: { title: '결과', lines: ['엑셀'] },
    /**
     * 번호 마디의 하는 일·빈도 알약(웹 글 — 이름은 서버 묶음 label. 걸음 수 글자는 박지 않음, DVA2 처분 3)과
     * 칸 고름 머리 줄의 빈도 글(head — 시안 단계 머리, 「웹 검색 · 칸 n」 꼬리는 뺌).
     */
    steps: {
      regulation: {
        does: '토픽마다 규제·정책 변화를 찾아요',
        runs: '토픽마다',
        head: '토픽마다',
      },
      controversy: {
        does: '키워드를 뽑아 이슈를 찾아요',
        runs: '토픽마다',
        head: '키워드는 실행마다 한 번 · 이슈는 토픽마다',
      },
      impact: {
        does: '긍정·부정 영향을 정해요',
        runs: '서브토픽마다',
        head: '서브토픽마다',
      },
      financial: {
        does: '리스크·기회를 정해요',
        runs: '서브토픽마다',
        head: '서브토픽마다',
      },
      pathway: {
        does: '원인 → 사업 → 재무로 이어요',
        runs: '서브토픽마다',
        head: '서브토픽마다',
      },
    },
    /** 신뢰 출처 마디(번호 없음 — 이름은 서버 묶음 label)의 곁 글과 칸 고름 머리 줄 글. */
    whitelist: {
      does: '1 규제·정책 지시 글에 끼워져요 · 비금융 · 금융',
      head: '규제·정책 리서치 지시 글의 {신뢰 출처 목록} 자리에 끼워져요 · 입력의 업종 구분(금융·비금융)에 따라 둘 중 하나',
    },
    /** 칸 고름 이름표. */
    picker: '단계의 칸',
    edited: '고침',
    refused: '고칠 곳 있음',
    /** 마디 이름표(「1. 규제·정책 리서치 프롬프트 보기」, 고쳤으면 「, 고침」). */
    nodeLabel: (n: number, label: string, edited: boolean) =>
      `${n}. ${label} 프롬프트 보기${edited ? ', 고침' : ''}`,
    /** 신뢰 출처 마디 이름표(「신뢰 출처 목록 보기」). */
    whitelistLabel: (label: string, edited: boolean) =>
      `${label} 보기${edited ? ', 고침' : ''}`,
    /** 칸 고름 머리 줄(「단계 1 규제·정책 리서치」). */
    stepHead: (n: number, label: string) => `단계 ${n} ${label}`,
  },
} as const;
