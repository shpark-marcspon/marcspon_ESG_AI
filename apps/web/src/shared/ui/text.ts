// 다시 만든 부품(shared/ui/)의 기본 문구 표. 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다(FV3 7.1).
// 부품은 문구를 props 로 받는다. 받지 않았을 때만 이 표의 값을 쓴다.
// 화면이 쓰는 업무 문구(「등록된 정보가 없어요」 꼴)는 여기 두지 않는다. 그것은 쓰는 쪽 몫이다.
/** 거부 사유 문구에 끼우는 한도 값. 없는 값은 값 없는 꼴로 쓴다. */
export interface RejectLimits {
  /** 받을 형식의 확장자를 대문자로 이어 쓴 것(「XLSX·CSV」). 확장자가 없으면 없음. */
  formats?: string;
  /** 파일 하나의 크기 상한(MB). */
  maxMb?: number;
  /** 목록 전체의 개수 상한. */
  maxCount?: number;
}

export const PARTS_TEXT = {
  /** 버튼이 불러오는 중일 때 도는 표시의 이름(화면 읽기 프로그램용). */
  loading: '불러오는 중',
  /** 머리 줄 인사말 옆 글 단추(header-greeting, 밴드 AD1). */
  logout: '로그아웃',
  /** 파일 드롭존: 줄 앞 ✕ 버튼의 이름(앞에 파일 이름이 붙는다). */
  removeFile: '지우기',
  /** 파일 드롭존: 올리는 중인 줄의 상태 글, 칸의 도는 표시 이름. */
  uploading: '업로드 중',
  /** 파일 드롭존: 올리지 못한 줄의 상태 글. */
  uploadFailed: '업로드 실패',
  /**
   * 파일 드롭존: 거부 사유. 키는 domain 의 RejectReason. 한도 값이 있으면 그 값을 넣어 할 일을 말하고, 없을 때만 값 없는 꼴을 쓴다
   * (해요체, 괄호 없음. Figma Policy 의 문구 꼴. 밴드 FW1 ⓪, band-reports/FK2-design-review.md 질문 3).
   * formats 는 받을 형식의 확장자를 대문자로 이어 쓴 것(「PDF」, 「XLSX·CSV」. domain 의 formatsLabel).
   */
  rejectReason: {
    type: ({ formats }: RejectLimits) =>
      formats ? `${formats} 파일만 올려 주세요` : '올릴 수 없는 형식이에요',
    size: ({ maxMb }: RejectLimits) =>
      maxMb !== undefined ?
        `${maxMb}MB 이하 파일을 올려 주세요`
      : '파일이 너무 커요',
    duplicate: () => '같은 이름의 파일이 이미 있어요',
    count: ({ maxCount }: RejectLimits) =>
      maxCount !== undefined ?
        `${maxCount}개까지 올릴 수 있어요`
      : '더 올릴 수 없어요',
  },
  /** 불러오기 실패·없음 상자(load-failure)의 단추 기본 이름(밴드 TRW0a ① — 그린워싱에서 올림). */
  load: {
    retry: '다시 시도',
    toList: '목록으로',
  },
  /** 위험 등급 표시(risk-badge)의 등급 글자. */
  risk: { high: 'High', mid: 'Mid', low: 'Low' },
  /** 단계 띠(step-flow): 단계 번호 앞 글자. 단계 이름·목록 이름은 업무 글이라 쓰는 쪽이 준다. */
  stepFlow: {
    prefix: 'STEP',
  },
  /** AI 설정 모델 카드(ai-setting ModelCard): 줄 아래 「…에 쓰여요」 칸의 숨은 이름(dt, 화면 읽기 프로그램용 — AV1 검증 R4). */
  modelUses: '쓰는 곳',
  /** 링크 칩(link-chip): 칩 이름 끝에 붙는 안내(화면 읽기 프로그램용 — 밴드 MD1). */
  opensInNewTab: '새 탭에서 열려요',
  /** 마크다운 글(markdown): 표 스크롤 칸의 이름(화면 읽기 프로그램용 — 밴드 MD1). */
  markdownTable: '표',
} as const;

export type PartsText = typeof PARTS_TEXT;
