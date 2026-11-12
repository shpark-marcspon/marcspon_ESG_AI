// 온실가스 Scope 3 화면 글 한 곳(밴드 S3W1 ①). 해요체(sid:MARC-ENT-269). 아무것도 가져오지 않는다.
// 글의 출처 꼬리표: [판] 캔버스 Scope 3 페이지 [1차] 보기 글자 그대로(판 번호 붙임) · [Figma] 판이 Figma 그림뿐이라 Figma 노드 글자 그대로 ·
//   [발주서] 발주서 S3W1 의 「초안 글」 그대로 · [러너 초안] 셋 다 없어 러너가 지은 글(보고 「물을 거리」 — 감독이 고르거나 지운다).
//   서버 message 는 화면에 싣지 않는다.
/** 카테고리 이름 한 벌(값 파일 V5 — 선택 창·카드·상세 머리가 같이 쓴다). */
const CATEGORY_NAMES = {
  C1: '구매 상품 및 서비스',
  C2: '자본재',
  C3: '연료 및 에너지 활동',
  C4: '업스트림 운송 및 유통',
  C5: '사업장 발생 폐기물',
  C6: '출장',
  C7: '출퇴근',
  C8: '업스트림 임차 자산',
  C9: '다운스트림 운송 및 유통',
  C10: '판매된 제품의 가공',
  C11: '판매된 제품의 사용',
  C12: '판매된 제품의 폐기',
  C13: '다운스트림 임차 자산',
  C14: '프랜차이즈',
  C15: '투자',
} as const;

export const S3_TEXT = {
  /** [판 S3-01] 「온실가스 데이터」 제목 아래 Scope 탭 줄(Figma 28023:7468) — app/ghg 의 ScopeTabs 가 S2 자리와 이 화면에 그린다. */
  scopeTabs: { scope12: 'Scope 1&2', scope3: 'Scope 3' },
  /** [러너 초안] Scope 탭 줄의 이름(읽는 기계용 — 화면 글자 0). */
  scopeTabsLabel: 'Scope 선택',
  /** 카테고리 C1~C15 의 이름 — [판 S3-02] 글자 그대로(번호는 model 의 CATEGORIES). */
  categories: CATEGORY_NAMES,
  /** [GX1 대조 e6](sid:MARC-ISSUE-506 새는 글) C10 을 고를 수 없는 까닭(판은 「비활성(기획 9~13쪽)」 표시만 — 글 없음). */
  disabledReason: '지금은 이 카테고리를 계산할 수 없어요',
  /** [판 S3-01] 산정 프로세스 Step 넷 — Step 3 은 1차 「데이터 업로드」(sid:MARC-ENT-315). */
  steps: {
    start: '시작하기',
    categories: '카테고리 선택',
    upload: '데이터 업로드',
    calculate: '배출량 계산',
  },
  /** S3-01 첫 화면. */
  screen: {
    /** [판 S3-01] 머리 제목(Scope 1·2 자리와 같은 「온실가스 데이터」). */
    title: '온실가스 데이터',
    yearLabel: '연도',
    yearOption: (year: number) => `${year}`,
    /** [값 파일 V4] 빈 해 안내 띠. */
    yearHint: (year: number, to: number) =>
      `${year}년 결과는 아직 없어요. 가장 최근 결과는 ${to}년이에요`,
    yearHintGo: (to: number) => `${to}년 보기`,
    /** [판 S3-01] 소개 머리·글 둘. */
    introTitle: '온실가스 인벤토리 Scope 3',
    intro: [
      'Scope 3는 우리 회사가 직접 통제하지 않지만, 우리 사업과 연결된 곳에서 발생하는 모든 간접 온실가스 배출량입니다.',
      '대부분의 기업에서, 전체 배출량의 70~90%가 Scope 3에서 발생합니다. 그래서, Scope 1, 2만 관리하면 실제 탄소 영향의 대부분을 놓치게 됩니다.',
    ],
    /** [판 S3-01] 구분 표. */
    tableLabel: 'Scope 구분',
    columns: { scope: '구분', meaning: '의미', example: '예시' },
    rows: [
      {
        scope: 'Scope 1',
        meaning: '우리가 직접 배출',
        example: '공장 굴뚝, 회사 차량',
      },
      {
        scope: 'Scope 2',
        meaning: '구매한 에너지 사용으로 발생하는 간접 배출',
        example: '구매한 전기',
      },
      {
        scope: 'Scope 3',
        meaning: '밸류체인 전반에서 발생하는 간접배출',
        example: '공급망, 출장, 제품 사용',
      },
    ],
    /** [판 S3-01] 표 아래 한 줄(1차 「툴러 → 눌러」 고침 반영). */
    categoryNote:
      'Scope 3는 총 15개 카테고리로 구성됩니다. 시작하기 버튼을 눌러 배출량을 산정해 보세요.',
    /** [판 S3-01] 산정 프로세스. */
    processTitle: 'Scope3 산정 프로세스',
    stepPrefix: (n: number) => `Step ${n}`,
    /** [판 S3-01a] 끝난 Step 의 표시. */
    stepDone: '완료',
    /** [판 S3-01] 아래 단추(1차 판 글 「다음」 — 발주서 [시작하기] 와 다름, 보고). */
    start: '다음',
    /** [Figma 29419:11469] 계산 창을 닫았을 때 화면 안 글 둘. */
    runningTitle: 'AI가 온실가스 배출량을 산정하고 있어요.',
    /** [Figma 28029:2819](값 파일 GX3 ② 고침 12) 두 줄. */
    runningBody: [
      '각 카테고리 데이터를 분석하여 배출량을 계산 중이에요.',
      '잠시만 기다려 주세요.',
    ],
    /** [러너 초안] 계산 창을 닫은 뒤 다시 여는 단추. */
    openProgress: '진행 보기',
    /** [Figma 28160:13433] 그 해 마지막 실행이 실패했을 때 — 계산 창의 실패 글과 같은 글. */
    failedLine: '탄소 배출량 산정을 완료하지 못했어요',
    /** [러너 초안] 상태를 알 수 없는 실행. */
    unknownLine: '계산 상태를 확인하지 못했어요',
    /** [러너 초안] 첫 읽기 실패(화면 자리)·다시 읽기 실패(notice). */
    loadFailed: '계산 기록을 불러오지 못했어요',
    reloadFailed:
      '계산 기록을 다시 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요',
    retryLoad: '다시 시도',
    /** [러너 초안] 진행 상태를 잃었을 때 그 해 마지막 실행을 다시 읽음. */
    recheck: '다시 확인',
    /** [러너 초안] 읽는 동안(화면 읽기 프로그램용). */
    loading: '계산 기록을 불러오는 중이에요',
  },
  /** 회사 거절 셋 — [러너 초안](온실가스 GHG_TEXT 의 회사 글과 같은 뜻, 칸끼리 가져오지 않는다). */
  company: {
    ambiguous: '작업할 회사를 먼저 골라 주세요',
    inactive: '이 회사는 지금 쓸 수 없어요',
    not_found: '회사를 찾지 못했어요',
  },
  /** S3-02 카테고리 선택. */
  categoryDialog: {
    /** [판 S3-02] 제목·안내(1차 — 담당자 지정 뺌)·표 머리·단추. */
    title: '카테고리 선택',
    guideLead: '데이터 취합이 가능한 ',
    guideStrong: '카테고리를 선택',
    guideTail: '해 주세요.',
    column: '카테고리',
    cancel: '취소',
    confirm: '확인',
    /** [러너 초안] 표·체크박스의 이름(화면 읽기 프로그램용). */
    listLabel: '카테고리 목록',
    item: (number: number, name: string) => `C${number}. ${name}`,
    /** [e6 판단](값 파일 GX3 ② 고침 7) 머리 전체 고름 체크의 이름. */
    selectAll: '카테고리 전체 고르기',
    /** [e6 판단](값 파일 GX3 ①) 머리 (?) 단추의 이름 — 설명 창을 연다. */
    infoOpen: '카테고리 설명 보기',
  },
  /** S3-02a 카테고리 설명 창(sid:MARC-ENT-528 — 값 파일 GX3 ①, Figma 28024:1803). 설명 15 는 Figma 글자 그대로. */
  categoryInfo: {
    title: '카테고리 설명',
    columns: { category: '카테고리', description: '설명' },
    confirm: '확인',
    descriptions: {
      C1: '원재료, 소모품, 외주 서비스 등 우리 회사가 구매한 모든 물품의 생산 과정에서 나온 탄소',
      C2: '건물, 기계 설비, 공장 장비, 차량 등 우리 회사의 고정자산(PP&E)을 구매할 때 발생한 탄소',
      C3: '우리가 쓴 전기나 가스를 만드는 과정(원료 채굴, 송배전 손실 등)에서 발생한 추가 탄소',
      C4: '협력사로부터 우리 회사(공장/매장)까지 원재료와 제품을 실어 나를 때 발생한 탄소',
      C5: '우리 회사 내부나 공장에서 발생한 쓰레기를 매립, 소각, 재활용 처리할 때 나오는 탄소',
      C6: '임직원이 업무 목적으로 기차, 비행기, 택시, 고속버스 등을 타고 출장을 갈 때 발생한 탄소',
      C7: '임직원들이 회사로 출퇴근할 때 이용하는 대중교통이나 자차 운행으로 인해 발생하는 탄소',
      C8: '우리 회사가 다른 건물주나 업체로부터 빌려서 쓰고 있는 사무실이나 차량에서 발생하는 탄소',
      C9: '우리 제품이 판매된 후, 최종 고객이나 소매점까지 배송 및 보관(물류창고 등)되는 과정에서 나오는 탄소',
      C10: '우리가 만든 중간재(부품, 원단 등)를 사간 다른 기업이 완성품으로 조립·가공할 때 쓰는 탄소',
      C11: '고객이 우리 제품을 사가서 실제로 사용할 때(가전제품 전력 소비, 자동차 연료 소비 등) 나오는 탄소',
      C12: '고객이 수명이 다한 우리 제품을 쓰레기로 버려서 매립, 소각, 분해될 때 발생하는 탄소',
      C13: '우리 회사가 소유하고 있는 건물이나 장비를 다른 회사에 빌려주었을 때, 그 임차인이 쓰는 탄소',
      C14: '가맹본부(본사)가 아닌, 가맹점주들이 각각의 매장을 운영하면서 소비하는 전력과 연료 등에서 나오는 탄소',
      C15: '우리 회사가 투자한 대상 기업이나 프로젝트가 사업을 영위하면서 뿜어내는 탄소 중 우리 지분만큼의 양',
    },
  },
  /** S3-03 데이터 업로드. */
  uploadDialog: {
    /** [Figma 28029:2331] 제목·끌어다 놓기 글·형식·양식 칸·단추. */
    title: '데이터 업로드',
    guide: '드래그 & 드롭 혹은 파일을 선택하여 업로드해 주세요',
    formats: '20MB 이내 첨부 가능 파일 형식: xls, xlsx',
    templateTitle: '데이터 일괄 업로드용 양식 파일',
    templateDownload: '양식 다운로드',
    /** [초안 글] 양식 칸 안내(Figma 글은 Scope 1·2 의 글이라 쓰지 않음 — 감독 86 10-30). */
    templateGuide:
      '양식 파일 한 권에 카테고리별 시트가 있어요. 데이터를 채운 뒤 올려 주세요.',
    /** [러너 초안] 양식 내려받기 실패. */
    templateFailed: '양식을 받지 못했어요. 다시 시도해 주세요.',
    cancel: '취소',
    submit: '데이터 업로드',
    /** [러너 초안] 올리는 동안 단추 글. */
    submitting: '올리는 중…',
    /** [러너 초안] 고른 카테고리 수(화면 표시만 — 요청에 싣지 않는다). */
    chosen: (count: number) => `고른 카테고리 ${count}개`,
    /** [발주서] 실행 거절 글. */
    invalidOptions: '계산을 시작하지 못했어요',
    /** [GX1 대조 e6](sid:MARC-ISSUE-506 새는 글) 서버 사정을 말하지 않는다. */
    flowNotRunnable: '지금은 Scope 3 계산을 시작할 수 없어요',
    operatorForbidden: '운영 관리자는 아직 Scope 3 계산을 시작할 수 없어요',
    /** [러너 초안] 그 밖 거절·끊김. */
    failed: '올리지 못했어요. 다시 시도해 주세요',
    /** [GX1 대조 e6](M-5) 서버가 파일을 받지 않음(0바이트 등 — 다시 해도 같다). */
    fileRejected: '파일을 읽지 못했어요. 파일을 다시 골라 주세요',
  },
  /** S3-07 배출량 계산 진행. */
  progressDialog: {
    /** [값 파일 V1·덧] 셈 한 줄. 수는 서버 단계에서 잰다. */
    countDone: (total: number, done: number) =>
      `카테고리 ${total}개 중 ${done}개를 마쳤어요`,
    assembling: '결과를 정리하고 있어요',
    /** [Figma 28029:2521] 제목. */
    title: '배출량 계산',
    /** [Figma 29419:11469] 진행 글 둘(계산 창 글은 「계산 중입니다」라 해요체 쪽을 씀 — sid:MARC-ENT-269). */
    runningTitle: 'AI가 온실가스 배출량을 산정하고 있어요.',
    /** [Figma 28029:2819](값 파일 GX3 ② 고침 12) 두 줄. */
    runningBody: [
      '각 카테고리 데이터를 분석하여 배출량을 계산 중이에요.',
      '잠시만 기다려 주세요.',
    ],
    /** [Figma 28160:13433] 실패 제목·단추. */
    failedTitle: '탄소 배출량 산정을 완료하지 못했어요',
    /**
     * 실패 본문 넷(발주서 S3W2a §1-6 — errorCode 갈래). file·general 은 [발주서], setup·transient 는 [e6 대조 — 감독 확정](S3W2c ② 9·10 —
     * transient 는 Figma 28160:13433 글에 마침표·「눌러」를 더함). setup 은 창·화면 모두 단추 0(닫기만).
     */
    failureBody: {
      setup: '지금은 계산할 수 없어요. 운영 관리자에게 알려 주세요',
      file: '올린 파일을 읽지 못했어요. 파일을 다시 올려 주세요',
      transient:
        '일시적인 연결 오류로 분석이 중단되었어요. 아래 버튼을 눌러 배출량을 다시 산정해 주세요',
      general:
        '계산 중 오류로 분석이 중단되었어요. 아래 버튼을 눌러 다시 산정해 주세요',
    },
    retry: '배출량 재계산하기',
    /** [러너 초안] 진행 상태를 읽지 못함·다시 계산 거절·닫기. */
    pollFailed: '진행 상태를 불러오지 못했어요. 창을 닫고 다시 들어와 주세요',
    retryFailed: '다시 계산을 시작하지 못했어요',
    close: '닫기',
  },
  /** 카테고리 잠금(밴드 S3W3a ③). 꼬리표 없는 글은 [S1·2 글] — entities/ghg config entry 의 글 그대로. */
  lock: {
    lock: '잠금',
    unlock: '잠금 해제',
    lockedLabel: '잠김',
    unlockedLabel: '잠기지 않음',
    lockedInfo: (name: string, at: string) => `${name} · ${at}에 잠갔어요`,
    lockConfirmPlain: '잠그면 운영 관리자만 풀 수 있어요. 잠글까요?',
    lockOk: '잠그기',
    lockFailed: '잠금을 바꾸지 못했어요. 다시 시도해 주세요',
    /** [e6 글](값 파일 「S3W3a ③ 화면 확인」) 다시 시도해도 같은 값으로 막히는 갈래. */
    lockStale:
      '그사이 결과가 바뀌었어요. 바뀐 결과를 확인한 뒤 다시 잠가 주세요',
    lockNotComputed: '아직 계산된 결과가 없어 잠글 수 없어요',
    cancel: '취소',
    /** [e6 글](값 파일 Q9) 핀 ≠ 기준 풀기. */
    unlockTitle: '잠금을 풀면 이 카테고리 결과가 최근 계산으로 바뀌어요',
    unlockBody: (edited: number) =>
      edited > 0 ?
        `고친 행 ${edited}개가 빠지고, 다시 잠가도 되돌릴 수 없어요.`
      : '다시 잠가도 되돌릴 수 없어요.',
    unlockOk: '잠금 풀기',
  },
  /** [결정 글 570 · e6 글](값 파일 E2) 새 실행 앞 경고. */
  rerunWarning: {
    title: (rows: number) =>
      `다시 계산하면 고친 행 ${rows}개가 사라져요. 계속할까요?`,
    cancel: '취소',
    confirm: '계속하기',
    readFailed: '고친 행을 확인하지 못했어요. 다시 시도해 주세요',
  },
  /** S3-08 카테고리 카드 목록(밴드 S3W2a). */
  result: {
    /** [e6 대조 — 감독 확정](S3W2c ② 7) AI 제안값 안내 띠 — 해요체·저장 없는 1차 꼴. */
    notice: 'AI 제안값은 참고용이에요. 최종 값은 담당자가 직접 확인해 주세요',
    /** [판 S3-08 그림] 단추·카드 제목·합 아래 글. */
    upload: '데이터 업로드',
    /** [판 S3-15 · GX1 리뷰] 결과 화면 [데이터 다운로드](btn--sm black — [데이터 업로드] 오른쪽 끝, Figma 28023:11429). */
    download: '데이터 다운로드',
    cardTitle: (number: number) => `Category ${number}`,
    totalLabel: '총 배출량',
    /** [값 파일 V5] 카드 이름은 categories 한 벌. */
    cards: CATEGORY_NAMES,
    /** [GX1 대조 e6](Figma 29204:27416 「별도, 총계 제외」를 카드 폭에 맞춤) 생물기원 합. */
    biogenicLabel: '생물기원 CO2(총계 제외)',
    /** [발주서] 합이 없는 카드(빈 시트·C10)와 실패한 카드. */
    empty: '-',
    cardFailed: '계산 실패',
    /** [e6 글](값 파일 E3) 시트 여럿 카테고리에서 일부만 실패 — 합 아래 둘째 줄. */
    cardPartial: (sheets: number) => `시트 ${sheets}개 계산 실패`,
    /** [사용자 11-11 · 디자인 c3](밴드 S3N1, sid:MARC-ENT-683) 1차 결과를 그대로 두는 카테고리 이름 옆 고정 안내. */
    adjustLater: '확인 필요 — 2차에서 보정',
    /** [e6 글](값 파일 E4) Scope 3 총합 줄. */
    scopeTotalLabel: 'Scope 3 총 배출량',
    scopeTotalMissing: (sheets: number) => `시트 ${sheets}개 빠짐`,
    /**
     * [e6 대조 — 감독 확정](S3W2c ② 8) done 인데 시트·AI 호출이 실패했을 때 — AI 호출은 수를 말하지 않고 「일부 줄」로.
     * 둘 다 0 이면 화면이 줄을 그리지 않는다.
     */
    problems: (sheets: number, calls: number) => {
      if (sheets > 0 && calls > 0)
        return `시트 ${sheets}개와 일부 줄을 계산하지 못했어요`;
      return sheets > 0 ?
          `시트 ${sheets}개를 계산하지 못했어요`
        : '일부 줄은 계산하지 못했어요';
    },
    /** [발주서] 결과가 거절일 때(reason 셋). */
    rejected: {
      reader_problem:
        '올린 파일을 읽지 못했어요. 양식을 확인해 다시 올려 주세요',
      factor_book: '배출계수 자료를 읽지 못했어요. 운영 관리자에게 알려 주세요',
      /** [GX1 대조 e6](M-6) 서버가 빈 통합문서·다른 양식도 이 갈래로 보낸다 — 이전 양식이라고 단정하지 않는다. */
      legacy_template:
        'Scope 3 양식이 아니거나 이전 양식이에요. 양식을 새로 받아 다시 올려 주세요',
    },
    /** [러너 초안] 결과 읽는 중·읽기 실패·다시 시도. */
    loading: '계산 결과를 불러오는 중이에요',
    loadFailed: '계산 결과를 불러오지 못했어요',
    retryLoad: '다시 시도',
  },
  /** S3-09·S3-10 카테고리 상세(밴드 S3W2b). 머리 글은 [Figma] 시트 프레임 머리 글(발주서 §1-5 표 — 초안이 읽음), ≈ 열은 뜻이 다른 근사. */
  detail: {
    /** [러너 초안] 상세 위 목록으로 돌아가는 단추(Q4). */
    back: '목록',
    /** [초안 글] 시트 갈래 글(Q3). */
    sheetFailed: '이 시트를 계산하지 못했어요',
    sheetEmpty: '이 시트에 데이터가 없어요',
    /** [러너 초안] 이 카테고리에 시트가 하나도 없을 때. */
    noSheets: '이 카테고리에 올린 시트가 없어요',
    /** 검색 칸 — 이름 [러너 초안] · 자리글 [Figma](S3W2c ② Q10). */
    searchLabel: '표 검색',
    searchPlaceholder: '검색',
    /** [러너 초안] 검색에 맞는 줄이 없을 때. */
    noMatch: '검색 결과가 없어요',
    /** [e6 판단] 값 파일 ③ C15 — 표 머리 위 오른쪽 한 줄. */
    noFactorEdit: '이 카테고리는 배출계수를 고칠 수 없어요',
    /** [러너 초안] 추정 줄 표시(Q9 — 배출량 칸 뒤). */
    estimate: '추정',
    /**
     * [디자인 e6 11-04] 출처 칸 — 갈래 값(model 의 sourceKind) → 계수 책 이름(구매 계수는 모두 책 한 권에서 나온다).
     * 줄마다 책 칸이 없어 글로 둔다(시트 글자 `구매_USEPA` 는 화면에 내지 않는다).
     */
    sourceBooks: {
      usepa: 'US EPA',
      'usepa-estimate': 'US EPA',
    },
    /**
     * [GX1 대조 e6](M-3 · L-5 — sid:MARC-ISSUE-563 1번 꼴, 엔진 글은 그대로 sid:MARC-ENT-442) 서버 출처 글(시트 이름) → 화면 글.
     * 글자가 같은 것만 바꾼다. 구매 줄을 고친 출처는 「구매_USEPA <원화 열 머리>」라 앞머리로 본다(detailText 의 rawSourceText).
     */
    sourceSheets: {
      폐기물_C5: '폐기물 배출계수 표',
      폐기물_C12: '폐기물 배출계수 표',
    },
    sourcePurchasePrefix: '구매_USEPA',
    /**
     * [e6 값 파일 GX3 ④] 이동·운송 수단 칸(C6-1 · C7 · C9-1 — 서버 mode 의 정규화 코드 → 화면 글). 거리 kind 의 입력 행에는 원문 칸이 없다.
     * 표에 없는 코드(unknown 포함)는 modeOther — 코드를 화면에 내지 않는다.
     */
    modeLabels: {
      flight: '항공',
      flight_dom: '항공(국내선)',
      flight_short: '항공(단거리)',
      flight_long: '항공(장거리)',
      flight_biz: '항공(비즈니스)',
      flight_short_biz: '항공(단거리 · 비즈니스)',
      flight_long_biz: '항공(장거리 · 비즈니스)',
      flight_long_prem: '항공(장거리 · 프리미엄 이코노미)',
      flight_first: '항공(퍼스트)',
      flight_long_first: '항공(장거리 · 퍼스트)',
      train: '철도',
      tram: '경전철 · 트램',
      subway: '지하철',
      bus: '버스',
      coach: '장거리 버스',
      taxi: '택시',
      car: '승용차',
      car_small: '승용차(소형)',
      car_medium: '승용차(중형)',
      car_large: '승용차(대형)',
      car_hybrid: '승용차(하이브리드)',
      car_ev: '전기차',
      rental_car: '렌터카',
      motorcycle: '오토바이',
      motorcycle_small: '오토바이(소형)',
      motorcycle_large: '오토바이(대형)',
      ferry: '여객선',
      ferry_foot: '여객선(도보 승선)',
      walk: '도보',
      bicycle: '자전거',
      lodging: '숙박',
      road: '도로(트럭)',
      parcel: '택배',
      rail: '철도',
      sea: '해상',
      air: '항공',
      sea_bulk: '해상(벌크선)',
      inland_water: '내륙 수로',
    },
    modeOther: '기타',
    /** [디자인 e6 11-05] usepa-estimate 줄의 책 이름 뒤 회색 글(추정 표시는 배출량 칸 하나 — S3WS2). */
    sourceOther: '· 기타',
    /** [디자인 e6 11-04] usepa-estimate 줄의 출처 칸 hover. */
    sourceEstimateHint: '맞는 품목이 없어 ‘기타’ 계수로 셈했어요',
    /** S3-12 그룹별 배출계수 창(밴드 S3W4). [Figma 29209:30180] 창 글 · [디자인 e6 11-05] 별·빈 표 글. */
    factorWindow: {
      title: '그룹별 배출계수',
      /** [디자인 e6 11-05] 별 hover·aria. */
      aiGroup: 'AI 가 고른 그룹이에요',
      close: '닫기',
      basicTitle: '기본 정보',
      carbonTitle: '탄소기원 구분',
      factorTitle: '배출계수',
      baseUnit: '투입량 기준단위',
      /** 구매 줄의 기준단위(서버 칸이 아니라 금액 줄의 뜻 — 발주서 Q6). */
      won: '원',
      source: '출처',
      emission: '배출량',
      biogenicEmission: '생물기원 CO2 배출량',
      carbonKind: '구분',
      biogenic: '생물기원 CO2',
      fcf: 'FCF',
      fcfLong: '(화석탄소 비율)',
      basis: '분류 근거 / 출처',
      columnTitle: '타이틀',
      /** 기준단위가 없으면 단위 꼬리를 뺀다(발주서 Q6 — e6 확정). */
      columnFactor: (unit: string | null) =>
        unit === null ? '배출계수' : `배출계수 (kg CO2e /${unit})`,
      columnSource: '출처',
      /** [디자인 e6 4절 4번] 계수 없는 줄. */
      noFactor: '배출계수가 없어요',
      /** S3-12c C12 처리방법별 표(밴드 S3Q1 ② — 값 파일 ②). [Figma 29453:38817] 열 머리 둘 · [Figma 29453:39100] 합계 줄. */
      columnTreatment: '처리방법',
      columnShare: '비중',
      total: '합계 / 가중 배출계수',
      /** [디자인 c3 11-11] 제품명이 빈 C12 줄의 여는 글(회색) · 그 단추의 aria 이름(n = 그 줄 번호 칸). 밴드 S3Q2. */
      noName: '이름 없음',
      openAria: (row: string | null) =>
        row === null ? '배출계수 보기' : `${row}번 줄 배출계수 보기`,
    },
    /**
     * S3-12a·b 계수 수정 꼴(밴드 S3W3c2). [Figma 29209:30228·30321] 단추·섹션 제목·자리글·필수 글 · [e6 글] 값 파일 ③·덧 · [초안 글] C11 둘(e6 받음).
     */
    factorEdit: {
      edit: '수정',
      cancel: '취소',
      save: '저장',
      appliedTitle: '적용 배출계수',
      recommendedTitle: '추천 배출계수',
      customTitle: '직접입력 배출계수',
      /** [러너 초안] 라디오 묶음 이름(화면 읽기 프로그램용). */
      pickLabel: '배출계수 고르기',
      pickApplied: '적용 배출계수 고르기',
      pickRecommended: (rank: number) => `추천 배출계수 ${rank}순위 고르기`,
      pickCustom: '직접입력 배출계수 고르기',
      /** 직접 입력 칸 이름(화면 읽기 프로그램용 — 표 머리와 같은 글). */
      customFieldLabel: {
        title: '직접입력 타이틀',
        value: '직접입력 배출계수',
        source: '직접입력 출처',
      },
      placeholders: {
        title: '타이틀을 입력해 주세요',
        value: '숫자를 입력해 주세요',
        source: '내용을 입력해 주세요',
      },
      required: '필수 입력 항목이에요',
      /** [초안 글 — e6 받음] C11. */
      notPositive: '0보다 큰 숫자를 입력해 주세요',
      /** [기획 → e6 해요체] C11. */
      decimals: '소수점 아래는 10자리까지 입력할 수 있어요',
      /** [초안 글 — e6 받음] C11. */
      tooLong: '200자까지 입력할 수 있어요',
      /** [e6 글] 값 파일 ③ C12. */
      c12: '이 카테고리는 배출계수를 고칠 수 없어요',
      /** [e6 판단] 값 파일 ③ 줄 하나 사정(C8 막음 · 409 factor_not_editable 뒤 창 머리 아래). */
      rowNotEditable: '이 줄은 배출계수를 고칠 수 없어요',
      /** [e6 글] 덧 C4 — 성공 뒤 표 위 한 줄. */
      saved: '배출계수를 고쳤어요',
      /** 직접입력 머리 — 계수 단위의 분모가 기준단위와 다를 때 서버 단위 글자 그대로(창 머리 columnFactor 꼴). */
      columnFactorUnit: (unit: string) => `배출계수 (${unit})`,
    },
    /** [러너 초안] 표 이름(화면 읽기 프로그램용). */
    tableLabel: (sheet: string) => `${sheet} 표`,
    /** [러너 초안] 쪽 나눔. */
    pagerLabel: '쪽 이동',
    prevPage: '이전',
    nextPage: '다음',
    pageStatus: (page: number, count: number) => `${page} / ${count}`,
    /**
     * [Figma 29204:27416](S3W2c ② Q9) C5·C12 생물기원 띠 — 「…입니다」 말투는 Figma 글 그대로(e6 확인).
     * total·biogenic 은 표기 글자(값 + 단위 「tCO2eq」 — ENT-264, Figma 「tCO2-eq」 아님. 값이 없으면 「-」 단위 없이).
     */
    biogenicNotice: (total: string, biogenic: string) =>
      `총 배출량 ${total}는 생물기원 CO2 ${biogenic}를 제외한 값입니다. 매립 배출원은 재질과 무관하게 화석기원으로 전량 포함됩니다.`,
    /** 공통 열 머리. [Figma] 행·온실가스 배출량·배출량 비율·배출계수·출처·그룹명 · [러너 초안] 그 밖(시트별 글이 없을 때만). */
    columns: {
      row: '행',
      /** [Figma] 입력 열(S3W2c — 결과 줄 input). 이름 열(inName)·에너지 열(inEnergy) 등은 시트별 글이 이긴다. */
      inCountry: '국가',
      inSite: '사업장',
      inName: '이름',
      inVehicle: '수단',
      inEnergy: '에너지명',
      inPeople: '인원수',
      inBuildingArea: '건물전체 면적',
      inUsedArea: '사용 면적',
      inBuildingPeople: '건물전체 인원수',
      inOwnPeople: '자사 인원수',
      inProductCount: '제품수량',
      inSales: '판매량',
      inWeight: '제품 중량',
      inStores: '가맹점 수',
      /** [Figma] C11 「평균사용기간 (개월)」(S3R3 — 괄호 앞 띄어씀 그대로). */
      inUseMonths: '평균사용기간 (개월)',
      group: '그룹명',
      spendKrw: '금액',
      treatment: '처리 방법',
      mode: '수단',
      activity: '활동량',
      baseAmount: '환산 활동량',
      people: '인원수',
      km: '거리(km)',
      roundTrip: '왕복계수',
      trips: '이동횟수',
      workdays: '근무일수',
      buildingTotal: '건물전체 사용량',
      investShare: '지분율(%)',
      scope1: '피투자 Scope 1',
      scope2: '피투자 Scope 2',
      factor: '배출계수',
      source: '출처',
      co2e: '온실가스 배출량',
      share: '배출량 비율',
      biogenic: '생물기원 CO2',
      fcf: 'FCF',
    },
    /**
     * [Figma] 시트별 머리 글(S3W2b 보고 「뺀 열」 이름 · 발주서 S3W2c §1-5). 에너지 열(inEnergy)은 input 이 없는 옛 줄에서 계수 이름(근사)을 보인다.
     * C6-1 「이동거리(km)」·「왕복계수」는 S3W2b 감독 C0 처분(Figma 「왕복 이동거리」와 뜻이 다름).
     */
    sheetColumns: {
      C1: { inName: '품목명', spendKrw: '연간지출금액(원)' },
      C2: { inName: '자산명', spendKrw: '연간취득금액(원)' },
      C3: { inEnergy: '연료·에너지명', activity: '연간 사용량' },
      'C4-1': {
        inName: '자재명/품목명',
        baseAmount: '연간운송량',
        km: '운송거리(km)',
      },
      'C4-2': { inName: '자재명/품목명', activity: '연간운송금액' },
      C5: {
        inSite: '사업장명',
        inName: '폐기물',
        treatment: '처리 방법',
        activity: '연간처리량',
      },
      'C6-1': {
        mode: '교통 수단',
        people: '인원수',
        km: '이동거리(km)',
        roundTrip: '왕복계수',
        trips: '연간이동횟수',
      },
      'C6-2': {
        inSite: '출장주체',
        inVehicle: '출장항목',
        inPeople: '인원수',
        activity: '연간 지출 금액',
      },
      C7: {
        mode: '교통수단',
        km: '이동거리(km)',
        people: '인원수',
        workdays: '연간근무일수',
      },
      'C8-1': {
        inName: '임차자산명',
        inEnergy: '에너지 종류',
        activity: '연간사용량',
      },
      'C8-2': {
        inName: '임차자산명',
        inEnergy: '에너지 종류',
        inBuildingArea: '건물전체 면적',
        inUsedArea: '사용 면적',
        buildingTotal: '건물전체 연간사용량',
      },
      'C8-3': {
        inName: '임차자산명',
        inEnergy: '에너지 종류',
        inBuildingPeople: '건물전체 인원수',
        inOwnPeople: '자사 인원수',
        buildingTotal: '건물전체 연간사용량',
      },
      'C9-1': {
        mode: '운송수단',
        inName: '제품명',
        baseAmount: '연간운송량',
        km: '운송거리(km)',
      },
      'C9-2': {
        inName: '제품명',
        inVehicle: '운송수단',
        activity: '연간운송금액',
      },
      C11: {
        inName: '제품명',
        inProductCount: '제품수량',
        inEnergy: '에너지명',
        /** [Figma] S3R3 — 값은 C11 줄 activity(입력 날값과 단위). */
        activity: '제품당 연간 에너지 사용량',
        inUseMonths: '평균사용기간 (개월)',
      },
      C12: { inName: '제품명', inSales: '판매량', inWeight: '제품 중량' },
      'C13-1': {
        inName: '임대자산명',
        inEnergy: '에너지 종류',
        activity: '연간사용량',
      },
      'C13-2': {
        inName: '임대자산명',
        inEnergy: '에너지 종류',
        inBuildingArea: '건물 전체 면적',
        inUsedArea: '사용 면적',
        buildingTotal: '건물전체 연간사용량',
      },
      'C13-3': {
        inName: '임대자산명',
        inEnergy: '에너지 종류',
        inBuildingPeople: '건물 전체 인원수',
        inOwnPeople: '자사 인원수',
        buildingTotal: '건물전체 연간사용량',
      },
      C14: {
        inName: '프랜차이즈 명',
        inStores: '가맹점 수',
        inEnergy: '연료 종류',
        activity: '연료 사용량',
      },
      C15: {
        inName: '기업명',
        investShare: '지분율(%)',
        scope1: '피투자 Scope 1',
        scope2: '피투자 Scope 2',
        co2e: '총 온실가스 배출량',
      },
    },
  },
  /**
   * S3-15 데이터 다운로드 창(밴드 S3D1). [판 S3-15 r1 1차] 글 — Scope 1·2 창(GHG_TEXT.inventory.bulk.download)과 같은 글자,
   * groupBody 는 [e6 판단 GX1 리뷰 S12-02] 「…관리 중인 데이터예요」(감독 처분 Q5). 보고서(PDF) 무리는 1차 숨김(자리 0).
   */
  download: {
    title: '데이터 다운로드',
    groupTitle: '온실가스 인벤토리 데이터',
    groupBody: '온실가스 인벤토리에서 관리 중인 데이터예요',
    /** [러너 초안] 줄 하나 — Scope 1·2 창의 「Scope 1 데이터」 꼴. */
    line: 'Scope 3 데이터',
    cancel: '취소',
    ok: '확인',
    /** [e6 11-10] 같은 화면 [원본 다운로드]·앱 다른 내려받기(DownloadButton busyLabel · TR-04)와 같은 말줄임표. */
    busy: '받는 중…',
    notFound: '받을 데이터가 없어요',
    failed: '받지 못했어요. 다시 시도해 주세요.',
  },
  /** S3-09 [원본 다운로드](밴드 S3Q1 ① — 값 파일 S3Q1-figma-values ①). [Figma 29585:11498] 단추 글 · [e6 11-10] 받는 중… · [e6 글] 실패 둘. */
  original: {
    button: '원본 다운로드',
    /** [e6 11-10] 다른 내려받기(DownloadButton busyLabel · 시안 TR-04)와 같은 말줄임표. */
    busy: '받는 중…',
    failed: '원본 파일을 받지 못했어요. 다시 시도해 주세요.',
    notFound: '원본 파일이 없어요',
  },
  /** 줄 제외·복구·히스토리(밴드 S3W3b — 값 파일 S3W3b-figma-values). */
  rowEdit: {
    /** [Figma 29585:11478] 표 위 단추. */
    exclude: '산정 제외',
    restore: '산정으로 복구',
    /** [Figma 29209:29754] 제외 줄 앞 글(뒤에 「 - 」와 칸 글). 칸 글이 없으면 이 글만(e6 덧 B3). */
    excludedLead: '산정 제외',
    excludedSeparator: ' - ',
    /** [초안 글] 체크 상자 이름(화면 읽기 프로그램용). */
    pickPage: '이 쪽 줄 모두 고르기',
    pickRow: (row: string) => `${row}행 고르기`,
    /** [e6 글] 한도 넘음(값 파일 1절). */
    tooMany: '한 번에 2,000줄까지 고를 수 있어요',
    /** [e6 글] E1 잠긴 단추 툴팁(값 파일 4절). */
    locked: '잠겨 있어 고칠 수 없어요',
    /** [e6 글] 값 파일 4절 뒤 알림. */
    excluded: (count: number) => `${count}개 줄을 산정에서 뺐어요`,
    restored: (count: number) => `${count}개 줄을 산정으로 되돌렸어요`,
    stale: '그사이 결과가 바뀌었어요. 바뀐 결과를 확인한 뒤 다시 해 주세요',
    failed: '바꾸지 못했어요. 다시 시도해 주세요',
    /** 사유 창. [Figma 29426:48753] 제목·띠·안내·칸 · [S1·2 글] 칸 아래 글·단추. 「기준 연도」 글은 sid:MARC-ENT-576 이 열린 동안 그대로. */
    reason: {
      title: '수정 사유 작성',
      warning: '수정 사유는 한번 입력하면 수정이 불가능해요.',
      guide: '기준 연도 데이터를 수정하신 사유에 대해 기록해 주세요.',
      label: '내용',
      placeholder: '내용을 입력해 주세요.',
      required: '수정 사유를 입력해 주세요',
      tooLong: (max: number) => `${max}자까지 쓸 수 있어요`,
      rejected: '수정 사유를 확인해 주세요',
      cancel: '취소',
      confirm: '확인',
    },
    /** 히스토리 창. [Figma 28276:7773] 제목·열 · [e6 글] 값 파일 5절·덧 B2 · [초안 글] 읽는 중. */
    history: {
      column: '히스토리',
      open: '히스토리 확인',
      title: '히스토리 확인',
      at: '수정일시',
      by: '수정자',
      reason: '수정사유',
      kinds: {
        exclude: '산정 제외',
        restore: '산정으로 복구',
        factor: '배출계수 수정',
      },
      empty: '수정 이력이 없어요',
      failed: '이력을 불러오지 못했어요',
      retry: '다시 시도',
      loading: '이력을 불러오는 중이에요',
      close: '확인',
      /** [e6 글] 덧 C6 — 「{AI 값} → {고른 값}」의 화살표(Scope 1·2 히스토리와 같은 띄어씀). */
      arrow: ' → ',
    },
  },
  /** 올릴 파일을 받지 않는 까닭 — [러너 초안](판·Figma 에 글 없음, 상한 20MB 는 RPT-21 §3.3). */
  fileProblem: {
    type: 'xls·xlsx 파일만 올릴 수 있어요',
    size: '20MB 이하 파일만 올릴 수 있어요',
    /** [GX1 대조 e6](M-5) 0바이트 파일 — 서버 거절과 같은 글. */
    empty: '파일을 읽지 못했어요. 파일을 다시 골라 주세요',
  },
} as const;
