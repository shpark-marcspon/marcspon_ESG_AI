// 온실가스 화면 글 한 곳(밴드 W12-0a ① — S15 조직구조·S18 선택항목). 해요체(sid:MARC-ENT-269). 아무것도 가져오지 않는다.
// 글의 출처 꼬리표: [스펙] 스펙 ② 의 [확인]·[우리 해석] 글자 그대로 · [발주서] 발주서 W12-0a 의 「초안 글」 그대로 ·
//   [러너 초안] 둘 다 없어 러너가 지은 글(보고 「물을 거리」 — 감독이 고르거나 지운다). 서버 message 는 화면에 싣지 않는다.
/** 가스 한 줄 산식 글 — 관리자 계수 창 가스 행과 고객 계수 창 산식 줄이 같이 쓴다(GX2 S12-03a). */
const GHG_POOL_FORMULA = {
  withNcv: (gas: string) =>
    `(투입량 × 순발열량 ÷ 10^6) × ${gas} 배출계수 × ${gas} GWP`,
  withoutNcv: (gas: string) => `투입량 × ${gas} 배출계수 × ${gas} GWP`,
};

/** 앱 메뉴 글 — 모듈 탭 「대시보드」(밴드 DB1 ③)가 같은 글을 가리킨다(새 글 아님). */
const SHELL_MENU = {
  dashboard: '대시보드',
  ghg: '온실가스',
  greenwash: '그린워싱 점검',
  materiality: '중대성평가',
  validation: '데이터 검증',
  translation: '영문번역',
  drafting: '보고서 작성',
} as const;

export const GHG_TEXT = {
  /** 틀(AppShell) 글 — 중대성평가 IR_TEXT.shell 을 옮겨 적음(가져오지 않는다), title 만 「온실가스」. */
  shell: {
    menuLabel: '모듈 메뉴',
    logo: '로고 자리',
    title: '온실가스',
    greeting: '담당자님 안녕하세요',
    adminGreeting: '운영 관리자님 안녕하세요',
    toAdmin: '관리자 화면',
    menu: SHELL_MENU,
  },
  /** S15 조직구조 목록. */
  organization: {
    /** [스펙] 회사 머리 띠는 1차에 뺐다(Q4) — 제목만. */
    title: '조직구조',
    /** [스펙] 사업장명 검색 칸. */
    searchLabel: '사업장명 검색',
    /** [발주서] 검색 칸 자리채움(W12-0b1 N4 — 시안 대조). */
    searchPlaceholder: '사업장명 검색',
    /** [러너 초안] 검색 단추. */
    search: '검색',
    /** [러너 초안] 표 이름(화면 읽기 프로그램용). */
    tableLabel: '사업장 목록',
    /** [러너 초안] 머리 체크박스·행 체크박스의 이름(화면 읽기 프로그램용). */
    selectAll: '전체 선택',
    selectRow: (name: string) => `${name} 선택`,
    /** [스펙] 표 머리. */
    columns: { name: '사업장명', inventory: '인벤토리 사용' },
    /** [발주서] 행 끝 > 열의 sr-only 머리(W12-0b1 N6). */
    openColumn: '상세 보기',
    /** [러너 초안] 행 토글·행 끝 > 의 이름(화면 읽기 프로그램용). */
    toggleRow: (name: string) => `${name} 인벤토리 사용`,
    openRow: (name: string) => `${name} 상세 보기`,
    /** [스펙] 단추 넷. */
    disableSelected: '인벤토리 사용취소',
    enableSelected: '인벤토리 사용',
    deleteSelected: '사업장 삭제',
    add: '사업장 추가',
    /** [발주서] 삭제 확인 창. */
    deleteConfirm: '선택한 사업장을 삭제할까요?',
    /** [러너 초안] 확인 창 단추. */
    confirmDelete: '삭제',
    cancel: '취소',
    /** [발주서] 상태 글. emptySearch 는 검색 중일 때만(GX2 M-8). */
    emptySearch: '검색 결과가 없어요',
    /** [초안 글 GX2 M-8] 검색 아닐 때 사업장 0. */
    empty: '등록된 사업장이 없어요',
    emptyGuide: '[사업장 추가]로 사업장을 넣어 주세요',
    loadFailed: '목록을 불러오지 못했어요. 다시 시도해 주세요',
    headquartersLocked: '본사는 끄거나 삭제할 수 없어요',
    inUse: '입력한 데이터가 있는 사업장은 삭제할 수 없어요',
    /** [러너 초안] 일괄·행 토글·삭제가 그 밖의 까닭으로 안 됐을 때(목록은 다시 읽는다). */
    writeFailed: '처리하지 못했어요. 다시 시도해 주세요',
    /** [러너 초안] 쪽 넘김(이전·다음, 「1 / 3」) — 이름은 [발주서] 「페이지」(W12-0b1 N5, sid:MARC-ENT-459). */
    pagerLabel: '페이지 넘김',
    prev: '이전',
    next: '다음',
    pageOf: (page: number, total: number) => `${page} / ${total}`,
  },
  /** S15 사업장 상세(새로 추가 겸용). */
  branch: {
    /** [스펙] 프레임 「사업장추가」 / [발주서] 있는 사업장의 제목(W12-0b1 N2). */
    titleNew: '사업장 추가',
    titleEdit: '사업장 정보',
    /** [스펙] 칸 이름. */
    name: '사업장명',
    /** [러너 초안] 사업장명 자리채움. */
    namePlaceholder: '사업장명을 입력해 주세요',
    inventory: '인벤토리 사용 상태',
    facilities: '자산/시설 정보',
    columns: { code: '시설명 및 코드', detail: '세부시설명' },
    /** [러너 초안] 줄 체크박스·머리 체크박스의 이름(화면 읽기 프로그램용). */
    selectLine: (name: string) => `${name} 선택`,
    selectAll: '전체 선택',
    /** [러너 초안] 자산/시설 줄이 없을 때. */
    noFacilities: '등록된 자산/시설이 없어요',
    /** [스펙] 단추 넷(설명 4·5·5-3·5-4). */
    removeLines: '삭제',
    addLine: '추가',
    cancel: '취소',
    save: '저장',
    /** [스펙] 저장 단추 Policy 의 필수 문구. */
    required: '필수 입력 항목이에요',
    /** [발주서] 상태 글. */
    duplicateFacility: '같은 시설명 및 코드와 세부시설명이 이미 있어요',
    saved: '저장했어요',
    leaveConfirm: '저장하지 않고 나갈까요?',
    notFound: '사업장을 찾지 못했어요',
    toList: '목록으로',
    headquartersLocked: '본사는 끄거나 삭제할 수 없어요',
    /** [러너 초안] PUT 409 IN_USE(빠진 줄이 쓰임 — 서버 자리만)·서버 422 fields.name(겹치는 사업장명). */
    inUse: '입력한 데이터가 있는 자산/시설은 삭제할 수 없어요',
    nameTaken: '이미 있는 사업장명이에요',
    /** [감독 글] 서버 422 fields.facilityCodeId(지운 코드를 고름 — 모달을 연 사이 운영 관리자가 지움). 폼은 그대로. */
    codeGone: '선택한 자산/시설 코드를 더 이상 쓸 수 없어요. 다시 골라 주세요',
    /** [발주서] PUT 404 뒤 다시 읽어 사업장이 있을 때(낡은 자산/시설 줄 — W12-0b1 M1). 폼은 그대로. */
    stale: '다른 곳에서 바뀌었어요. 다시 불러와 주세요',
    /** [초안 글] PUT 409 STALE·404 다시 읽기 뒤 줄 안 단추와 확인 창(밴드 K1b-3 — 고친 것이 있을 때만 창). 디자인 대조 전. */
    reload: '다시 불러오기',
    reloadConfirm: '지금 고친 내용은 사라져요. 다시 불러올까요?',
    reloadConfirmOk: '다시 불러오기',
    /** [러너 초안] 확인 창 단추·불러오기·저장 실패. */
    leave: '나가기',
    stay: '계속 고치기',
    loadFailed: '사업장을 불러오지 못했어요. 다시 시도해 주세요',
    saveFailed: '저장하지 못했어요. 다시 시도해 주세요',
  },
  /** S15 자산/시설 추가 모달. */
  facilityModal: {
    /** [발주서] 제목. */
    title: '자산/시설 추가',
    /** [스펙] 칸 이름. */
    code: '시설명 및 코드',
    detail: '세부시설명',
    /** [러너 초안] 드롭다운 자리채움·세부시설명 자리채움. */
    codePlaceholder: '선택해 주세요',
    detailPlaceholder: '세부시설명을 입력해 주세요',
    /** [발주서] 코드 목록이 비었을 때. */
    noCodes:
      '등록된 자산/시설명 및 코드가 없어요. 운영 관리자에게 등록을 요청해 주세요',
    /** [러너 초안] 코드 목록을 못 읽었을 때. */
    codesFailed: '자산/시설명 및 코드를 불러오지 못했어요. 다시 시도해 주세요',
    cancel: '취소',
    save: '저장',
  },
  /** S18 설정 > 선택항목 > 자산/시설명 및 코드(운영 관리자). */
  facilityCodes: {
    /** [스펙] 제목·항목 고르기. */
    title: '선택항목',
    itemLabel: '관리할 선택항목',
    item: '자산/시설명 및 코드',
    /** [스펙] 표 머리·행 단추. */
    column: '자산/시설명 및 코드',
    edit: '수정',
    /** [러너 초안] 표 이름·체크박스 이름(화면 읽기 프로그램용). */
    tableLabel: '자산/시설명 및 코드 목록',
    selectAll: '전체 선택',
    selectRow: (name: string) => `${name} 선택`,
    /** [스펙] 단추. */
    deleteSelected: '항목 삭제',
    add: '항목 추가',
    /** [발주서] 삭제 확인 창. */
    deleteConfirm: '선택한 항목을 삭제할까요?',
    confirmDelete: '삭제',
    /** [러너 초안] 모달 제목(추가·수정). */
    addTitle: '항목 추가',
    editTitle: '항목 수정',
    /** [스펙] 모달 칸·자리채움. */
    field: '자산/시설명 및 코드',
    placeholder: '자산/시설명 및 코드를 입력해 주세요',
    cancel: '취소',
    save: '저장',
    required: '필수 입력 항목이에요',
    duplicate: '이미 있는 항목이에요',
    empty: '등록된 항목이 없어요',
    inUse: '사용 중인 항목은 삭제할 수 없어요',
    /** [러너 초안] 불러오기·쓰기 실패·없는 항목·권한. */
    loadFailed: '목록을 불러오지 못했어요. 다시 시도해 주세요',
    writeFailed: '처리하지 못했어요. 다시 시도해 주세요',
    notFound: '이미 삭제된 항목이에요. 목록을 다시 불러왔어요',
    /** [발주서] 「페이지」(W12-0b1 N5, sid:MARC-ENT-459). */
    pagerLabel: '페이지 넘김',
    prev: '이전',
    next: '다음',
    pageOf: (page: number, total: number) => `${page} / ${total}`,
  },
  /** S19 인덱스 풀(운영 관리자 — 밴드 W12-0b1). */
  pool: {
    /** [스펙] 제목(메뉴 「인벤토리 관리 > 온실가스 인덱스」). */
    title: '온실가스 인덱스',
    /** [러너 초안] 검색 칸 이름·자리채움. */
    searchLabel: '인덱스 검색',
    searchPlaceholder: '이름 검색',
    /** [스펙] 4열 머리. */
    columns: {
      scope: '배출범위',
      source_type: '배출원 유형',
      activity: '배출활동',
      facility: '자산/시설명',
    },
    /** [발주서] 열 끝 추가(스펙 :144 차례와 어긋남 — 보고 물을 거리). */
    add: {
      scope: '+ 범위 추가',
      source_type: '+ 배출원 유형 추가',
      activity: '+ 배출활동 추가',
      facility: '+ 자산/시설명 및 코드 추가',
    },
    /** [스펙 우리 해석] 열 1~3 항목의 작은 메뉴. */
    menuLabel: (name: string) => `${name} 메뉴`,
    edit: '수정',
    remove: '삭제',
    /** [러너 초안] 하위 항목 수(화면 읽기 프로그램용 꼬리). */
    childCount: (n: number) => `하위 ${n}개`,
    /** [러너 초안] 빈 열·검색 결과 없음. */
    emptyColumn: '항목이 없어요',
    emptySearch: '검색 결과가 없어요',
    /** [러너 초안] 글자 모달(열 1~3). */
    nameDialogAdd: (column: string) => `${column} 추가`,
    nameDialogEdit: (column: string) => `${column} 수정`,
    nameField: '이름',
    namePlaceholder: '이름을 입력해 주세요',
    /** [발주서 초안 글] 같은 부모 아래 같은 이름(422 fields.name). */
    nameTaken: '같은 이름이 이미 있어요',
    /** [발주서] 삭제 확인·거절. */
    deleteConfirm: '선택한 항목을 삭제할까요?',
    confirmDelete: '삭제',
    hasChildren: '하위 항목을 먼저 삭제해 주세요',
    inUseDelete: '사용 중인 항목은 삭제할 수 없어요',
    /** [러너 초안] 이미 지워진 항목(404 — 다시 읽음). */
    notFound: '이미 삭제된 항목이에요. 다시 불러왔어요',
    /** [스펙] 자산/시설 판. */
    facilityTitleNew: '자산/시설명 및 코드 추가',
    facilityCode: '자산/시설명 및 코드',
    codePlaceholder: '선택해 주세요',
    unit: '단위',
    /** [Figma 28596:32704 — 값 파일 ⑧] S12-07 단위 드롭다운 빈 값. */
    unitNone: '선택안함',
    /** [값 파일 ⑧ 추정 글] S12-07 단위 머리 ⓘ 툴팁 · 그 단추 이름. */
    unitInfo: '배출량을 셀 때 쓰는 투입량의 단위예요. 하나만 고를 수 있어요.',
    unitInfoLabel: '단위 설명',
    /** [발주서] 단위 종류 글(W12-0b2 ① — 디자인 74 대조 B1). 모르는 종류는 글자 그대로(쓰는 자리가 `?? kind`). */
    unitKinds: {
      mass: '질량',
      volume: '부피',
      energy: '에너지',
      electricity: '전력',
    } as Readonly<Record<string, string>>,
    tooltip: '툴팁 내용',
    tooltipPlaceholder: '툴팁 내용을 입력해 주세요',
    factors: '배출계수',
    factorColumns: {
      name: '배출계수명',
      inputUnit: '투입량 기준단위',
      isDefault: '기본 배출계수',
      open: '상세 보기',
    },
    selectAll: '전체 선택',
    selectFactor: (name: string) => `${name} 선택`,
    defaultToggle: (name: string) => `${name} 기본 배출계수`,
    openFactor: (name: string) => `${name} 상세 보기`,
    removeFactors: '삭제',
    addFactor: '추가',
    removeFacility: '삭제',
    cancel: '취소',
    save: '저장',
    /** [스펙] 빈 상태·경고. */
    noFactors: '등록된 배출계수가 없어요',
    noDefault: '기본 배출계수가 없어 고객사가 고를 수 없어요',
    /** [스펙 우리 해석] 저장 토스트. */
    saved: '저장됐어요',
    required: '필수 입력 항목이에요',
    /** [발주서 초안 글] 잎 PUT 409 IN_USE · 같은 활동 아래 같은 코드 422 · 기본 계수가 사라짐(다시 읽음). */
    inUseSave: '고객사가 쓰고 있어 시설명 및 코드와 단위를 바꿀 수 없어요',
    codeTaken: '이 배출활동에 같은 자산/시설이 이미 있어요',
    defaultGone: '기본 배출계수가 바뀌었어요. 다시 불러왔어요',
    /** [러너 초안] 확인 창 — 이 잎 지우기·계수 지우기. */
    deleteFacilityConfirm: '이 자산/시설을 삭제할까요?',
    deleteFactorsConfirm: '선택한 배출계수를 삭제할까요?',
    loadFailed: '불러오지 못했어요. 다시 시도해 주세요',
    writeFailed: '처리하지 못했어요. 다시 시도해 주세요',
  },
  /** S20 배출계수 추가·수정 모달(운영 관리자 — 밴드 W12-0b1). */
  factor: {
    /** [러너 초안] 모달 제목 셋. */
    titleNew: '배출계수 추가',
    titleEdit: '배출계수 수정',
    titleView: '배출계수 정보',
    /** [러너 초안] 읽기 꼴의 버전 글(GX2 S12-08 — 고객 창 「버전 n」과 같이). */
    version: (n: number) => `버전 ${n}`,
    /** [스펙] 칸. */
    name: '배출계수명',
    source: '출처',
    baseYear: '기준연도',
    tier: 'Tier',
    country: '국가',
    industry: '산업',
    inputUnit: '투입량 기준단위',
    emissionUnit: '배출량 기준단위',
    ncv: '순발열량',
    ncvUnit: '순발열량 기준단위',
    note: '비고',
    choose: '선택해 주세요',
    unitKind: '단위 종류',
    unitName: '단위',
    /** [스펙] 가스 표. */
    gasColumns: {
      gas: '온실가스',
      enabled: '포함',
      factor: '배출계수',
      gwp: 'GWP',
      formula: '산식',
    },
    gasToggle: (gas: string) => `${gas} 포함`,
    gasFactor: (gas: string) => `${gas} 배출계수`,
    gasGwp: (gas: string) => `${gas} GWP`,
    /** [스펙] 산식 글(행마다 그 가스 이름 — 우리 해석). 셈은 하지 않는다(S12a). 고객 계수 창(entry.factor.formulaText)도 같은 글. */
    formulaWithNcv: GHG_POOL_FORMULA.withNcv,
    formulaWithoutNcv: GHG_POOL_FORMULA.withoutNcv,
    /** [러너 초안] 계수 칸 머리의 단위 꼬리. */
    factorUnit: (unit: string) => `배출계수(${unit})`,
    /** [스펙] 검사 글. */
    required: '필수 입력 항목이에요',
    /** [러너 초안] 숫자 칸·켠 가스 0·서버가 거른 칸. */
    number: '0보다 큰 숫자를 입력해 주세요',
    noGas: '포함할 온실가스를 하나 이상 켜 주세요',
    invalid: '입력값을 확인해 주세요',
    /** [스펙 우리 해석] 닫기 확인. */
    leaveConfirm: '저장하지 않고 닫을까요?',
    leave: '닫기',
    stay: '계속 입력',
    close: '닫기',
    cancel: '취소',
    save: '저장',
    edit: '수정',
    saved: '저장됐어요',
    loadFailed: '배출계수를 불러오지 못했어요. 다시 시도해 주세요',
    saveFailed: '저장하지 못했어요. 다시 시도해 주세요',
  },
  /** S17 인덱스 설정(고객사·운영 관리자 — 밴드 W12-0b2 ②). */
  indexSettings: {
    /** [시안] 28593:27731 제목·브레드크럼(감독 10-29 — 시안 따름, 발주서 「인덱스 설정」과 다름). */
    title: '온실가스 데이터 설정',
    breadcrumbLabel: '현재 위치',
    breadcrumb: ['온실가스 데이터', '인덱스 설정'],
    /** [스펙] 연도·검색. */
    yearLabel: '연도',
    yearOption: (year: number) => `${year}`,
    searchLabel: '인덱스 검색',
    searchPlaceholder: '인덱스 검색',
    /** [스펙] 4열 머리. */
    columns: {
      scope: '배출범위',
      source_type: '배출원 유형',
      activity: '배출활동',
      facility: '자산/시설명',
    },
    /** [러너 초안] 경로 줄 이름(화면 읽기 프로그램용)·항목 수 꼬리. */
    pathLabel: '고른 경로',
    count: (n: number) => `(${n})`,
    /** [러너 초안] 체크박스 이름(화면 읽기 프로그램용). */
    check: (name: string) => `${name} 선택`,
    /** [발주서 초안 글] 못 고르는 잎의 까닭(1-4 hasFactor — S12-05 뒤 기본 계수 없음 하나). */
    noFactor: '기본 배출계수가 없어요',
    /** [러너 초안] 빈 열·검색 결과 없음. */
    emptyColumn: '항목이 없어요',
    emptySearch: '검색 결과가 없어요',
    /** [스펙] 「선택한 인덱스」 표. */
    chosenTitle: '선택한 인덱스',
    chosenColumns: {
      scope: '범위',
      source_type: '배출활동 구분',
      activity: '활동 유형',
      facility: '자산/시설 유형',
    },
    clearAll: '전체 해제',
    /** [러너 초안] 행 ✕ 이름·빈 표. */
    removeChosen: (name: string) => `${name} 해제`,
    removeColumn: '해제',
    noneChosen: '선택한 인덱스가 없어요',
    cancel: '취소',
    save: '저장',
    /** [스펙 우리 해석] 상태 글. */
    emptyPool: '운영 관리자가 등록한 인덱스가 없어요',
    /** [e6 덧 11-10] S12-05 뒤 안내(앞 조건 아님 — 자산/시설 없는 잎도 고른다). */
    noFacilities: '자산/시설은 조직구조에서 추가할 수 있어요',
    /** [러너 초안] 시설 0 안내의 단추. */
    toOrganization: '조직구조로',
    /** [스펙 우리 해석] 나가기 확인. */
    leaveConfirm: '변경 내용을 저장하지 않고 나갈까요?',
    /** [러너 초안] 나가기 확인 단추. */
    leave: '나가기',
    stay: '계속 고르기',
    /** [초안 글] 데이터 있는 인덱스를 뺄 때 경고 — 머리·몸(sid:MARC-ISSUE-468 D9, 디자인 74 처방). */
    dataWarning: (n: number) => `데이터가 있는 인덱스 ${n}개를 빼요`,
    dataWarningBody: '목록에서 숨겨지고 데이터는 남아요',
    /** [마크스폰 댓글 da787b28 글 그대로] [저장] 확인 창 머리(단추 [취소][확인]). */
    saveConfirm: '선택하신 인덱스를 저장할까요?',
    /** [러너 초안] 경고 단추. */
    confirm: '확인',
    /** [발주서 초안 글] 422 두 칸. */
    badYear: '고를 수 없는 연도예요',
    badNodes: '고를 수 없는 인덱스가 섞여 있어요. 다시 불러올게요',
    /** [러너 초안] 읽기·다시 읽기·저장 실패. */
    loadFailed: '인덱스를 불러오지 못했어요. 다시 시도해 주세요',
    reloadFailed: '인덱스를 다시 불러오지 못했어요. 다시 시도해 주세요',
    saveFailed: '저장하지 못했어요. 다시 시도해 주세요',
  },
  /** S2 자리 「온실가스 데이터」(고객사·운영 관리자 — 밴드 W12-0b2 ③. 표·카드는 W12-1). */
  inventory: {
    /** [스펙] 제목·모듈 안 탭(발주서 Q3). */
    title: '온실가스 데이터',
    tabsLabel: '온실가스 메뉴',
    /** 「대시보드」는 앱 메뉴 글 그대로(밴드 DB1 ③ — sid:MARC-ENT-597). */
    tabs: {
      dashboard: SHELL_MENU.dashboard,
      inventory: '온실가스 데이터',
      organization: '조직구조',
    },
    yearLabel: '연도',
    yearOption: (year: number) => `${year}`,
    /** [스펙] 인덱스 설정 단추. */
    indexSettings: '인덱스 설정',
    /** [시안] 28575:23233 빈 상태 두 줄(원문 그대로). */
    emptyTitle: '등록된 데이터가 없어요',
    emptyBody:
      '우측 상단의 인덱스 설정을 등록하여 이행 현황을 확인하고 관리해 보세요.',
    /** [스펙 우리 해석] S17 저장 뒤 머리 옆 글. */
    saved: '저장됐어요',
    /** [러너 초안] 읽기 실패(첫 읽기 — 화면 자리)·다시 읽기 실패(연도 바꿈 — 한 줄). */
    loadFailed: '온실가스 데이터를 불러오지 못했어요. 다시 시도해 주세요',
    reloadFailed:
      '온실가스 데이터를 다시 불러오지 못했어요. 다시 시도해 주세요',
    /** [시안] 28535:7000 검색 칸(인덱스 이름 — 서버 q). */
    searchLabel: '인덱스 검색',
    /** [스펙 우리 해석] 검색 0 건 — 표 자리. */
    searchEmpty: '검색 결과가 없어요',
    /** [러너 초안] 검색 q 422(서버 상한 100자). */
    searchInvalid: '검색어는 100자까지 입력할 수 있어요',
    /** [시안] 28535:7000 배출량 현황 카드(Scope 1+2 고리 · 범례 · 합). 접기 단추 이름은 [러너 초안]. */
    card: {
      title: '배출량 현황',
      ringTitle: 'Scope 1+2',
      total: '총배출량',
      collapse: '배출량 현황 접기',
      expand: '배출량 현황 펼치기',
      /** [러너 초안] 고리 그림의 글 대체. */
      ringLabel: (parts: readonly string[]) =>
        `배출량 비율 ${parts.join(', ')}`,
    },
    /** [시안] 28535:7000 표 머리(1차 숨김 열 둘은 싣지 않음 — 발주서 1-4). 3개년 머리는 서버 years. */
    head: {
      source: '배출원 유형',
      activity: '배출활동',
      facility: '자산/시설 유형',
      unit: '단위',
      memo: '메모',
      estimated: '추정치',
      locked: '잠금',
    },
    /** [러너 초안] 표 이름(배출범위마다). */
    tableLabel: (scope: string) => `${scope} 배출량`,
    /** [시안] 메모 칩 글 — 메모가 있으면 진하게. 칩 이름은 [러너 초안]. */
    memoChip: '내용',
    memoOn: '메모 있음',
    memoOff: '메모 없음',
    /** [시안] 추정 표시(≈). 이름은 [러너 초안]. */
    estimatedMark: '≈',
    estimatedLabel: '추정치 있음',
    /** [초안 글] 추정 없는 행 상자 이름(디자인 대조 1). */
    estimatedOff: '추정치 없음',
    /** [러너 초안] 잠긴 행 자물쇠 이름. */
    lockedLabel: '잠김',
    /** [초안 글] 안 잠긴 행 자물쇠 이름(디자인 대조 3). */
    unlockedLabel: '잠기지 않음',
    /** [초안 글] 이름이 빈 자산/시설 칸 단추의 이름(가지 리뷰). */
    openUnnamed: '이름 없는 자산/시설 상세 보기',
    /** S4 일괄 업로드·양식 받기·S5 다운로드(밴드 W12-5). 꼬리표 없는 글은 [초안 글] — 보고 「디자인 확인 거리」. */
    bulk: {
      /** [스펙] S2 단추 둘. */
      uploadOpen: '데이터 일괄 업로드',
      downloadOpen: '데이터 다운로드',
      /** 올린 뒤 연도 줄 한 줄(칸 기준 — 사용자가 파일에 채운 단위). unresolved 글에 「이번」을 쓰지 않는다: 파일에 나온 잎 전체의 수다. */
      filled: (count: number) => `값 ${count}칸을 넣었어요`,
      unresolved: (count: number) =>
        `셈하지 못한 행이 ${count}개 있어요. 표에서 확인해 주세요`,
      upload: {
        /** [Figma 28535:9577] 제목·끌어 놓기 글·양식 상자·단추. */
        title: '데이터 업로드',
        guide: '드래그 & 드롭 혹은 파일을 선택하여 업로드해 주세요',
        /** [e6 값 파일 Q1] 서버 값(맨 바이트 20MB — MARC-ENT-593 · xlsx 만). 글 꼴은 Scope 3 창과 같다. */
        formats: '20MB 이내 첨부 가능 파일 형식: xlsx',
        templateTitle: '데이터 일괄 업로드용 양식 파일',
        templateOpen: '양식 다운로드',
        templateGuide1:
          '해당 데이터 업로드는 추가만 가능하고, 수정은 불가능해요.',
        templateGuide2:
          '먼저 데이터 일괄 업로드 양식을 다운로드하고 데이터를 추가해 주세요.',
        cancel: '취소',
        submit: '데이터 업로드',
        submitting: '올리는 중…',
        type: 'xlsx 파일만 올릴 수 있어요',
        size: '20MB 이하 파일만 올릴 수 있어요',
        /** [e6 값 파일 Q6] 오류 목록 머리. */
        linesHead: '파일에서 고칠 곳이 있어요',
        noValues: '넣을 값이 없어요. 양식에 값을 채워 올려 주세요',
        sameValues: '이미 같은 값이 있어서 바뀐 것이 없어요',
        locked: '잠긴 인덱스가 생겨 올리지 못했어요',
        notFound: '이 해에 고른 인덱스가 없어요',
        /** [e6 글] 요청을 보내지 않음이 확실한 갈래(검증 B1) — 결과를 모르는 글과 다르다. */
        unreadable: '파일을 읽지 못했어요. 파일을 다시 골라 주세요',
        /** ★ 결과를 모름 — 「실패」로 쓰지 않는다. 다시 읽음·못 읽음 둘(감독 K3). */
        unknownRead:
          '올리기 결과를 확인하지 못했어요. 표를 새로 불러왔으니 값이 들어갔는지 확인해 주세요. 같은 파일을 다시 올려도 값이 두 번 들어가지 않아요',
        unknownUnread:
          '올리기 결과를 확인하지 못했고 표도 새로 불러오지 못했어요. 잠시 뒤 값을 확인해 주세요. 같은 파일을 다시 올려도 값이 두 번 들어가지 않아요',
      },
      template: {
        /** [Figma 28538:9738·28549:13150] 제목·자리 글·목록·단추. 마지막 단추도 「다음」(e6). */
        scopeTitle: '데이터 선택',
        scopePlaceholder: '데이터를 선택해 주세요',
        scope1: 'Scope 1 데이터',
        scope2: 'Scope 2 데이터',
        siteTitle: '사업장 선택',
        sitePlaceholder: '사업장을 선택해 주세요',
        sitesLoading: '사업장을 불러오는 중이에요',
        sitesFailed: '사업장을 불러오지 못했어요. 다시 시도해 주세요.',
        sitesEmpty: '인벤토리를 사용하는 사업장이 없어요',
        cancel: '취소',
        next: '다음',
        notFound:
          '받을 줄이 없어요. 이 사업장·Scope 에 고른 인덱스가 있는지 확인해 주세요',
        failed: '받지 못했어요. 다시 시도해 주세요.',
      },
      download: {
        /** [Figma 28538:9695] 제목·무리 머리·줄·단추. groupBody 만 [e6 판단 GX2 S12-02] — 앱은 EDK 안에 붙지 않아 Figma 글을 고침(원칙의 예외). */
        title: '데이터 다운로드',
        groupTitle: '온실가스 인벤토리 데이터',
        groupBody: '온실가스 인벤토리에서 관리 중인 데이터예요',
        all: '전체 (Scope1+2) 데이터',
        scope1: 'Scope 1 데이터',
        scope2: 'Scope 2 데이터',
        cancel: '취소',
        ok: '확인',
        busy: '받는 중…',
        notFound: '받을 데이터가 없어요',
        failed: '받지 못했어요. 다시 시도해 주세요.',
      },
    },
  },
  /** S3 데이터 상세(밴드 W12-1b ① — 스펙 ① S3). 꼬리표 없는 글은 [초안 글] — 보고 「초안 글 자리」. */
  entry: {
    close: '닫기',
    loadFailed: '상세를 불러오지 못했어요. 다시 시도해 주세요',
    reloadFailed: '상세를 다시 불러오지 못했어요. 다시 시도해 주세요',
    notFound: '찾을 수 없어요',
    lockedLabel: '잠김',
    unlockedLabel: '잠기지 않음',
    /** [스펙] 데이터 상세 — 총합과 사업장별 3개년. */
    detailTitle: '데이터 상세',
    siteHead: '사업장',
    /** [시안 글] 총합 표 끝 열(W12-1c #11 — 연도 머리에서 단위를 뺌). */
    unitHead: '단위',
    /** [시안 글] 사업장 블록들 위 구역 제목(W12-1c #8). */
    inputTitle: '데이터 입력',
    /** [e6 ⑥ 11-10] S12-05 — 이 회사에 그 자산/시설이 없는 잎의 「데이터 입력」 자리 한 줄과 단추(S17 시설 0 안내 꼴). */
    noFacilities: '조직구조에서 자산/시설을 추가하세요',
    toOrganization: '조직구조로',
    /** [시안 글] 경로 라벨(W12-1c #9). */
    pathLabel: '경로',
    total: '총합',
    decimalsLabel: '소수점',
    decimalsOption: (n: number) => `${n}자리`,
    /** 블록 주기 한 줄(보기만). */
    period: { month: '월별', quarter: '분기별', year: '연간' } as Readonly<
      Record<string, string>
    >,
    slotMonth: (n: number) => `${n}월`,
    slotQuarter: (n: number) => `${n}분기`,
    slotYear: '연간',
    /** [스펙] 블록 행 열. */
    head: {
      select: '선택',
      detail: '상세 시설명',
      unit: '단위',
      factor: '배출계수 출처',
      na: 'N/A',
      emission: '배출량',
    },
    /** [e6 ② 11-10] S12-03 추정치 단추 하나(잠금 옆 — 칸 표식은 걷음, sid:MARC-ENT-644). 이름 = 「{자산/시설명} 추정치」, 상태는 aria-pressed. 그림은 물결(EstimatedWave). */
    estimatedAll: (name: string) => `${name} 추정치`,
    amountLabel: (row: string, slot: string) => `${row} ${slot} 사용량`,
    unitLabel: (row: string) => `${row} 단위`,
    naLabel: (row: string) => `${row} N/A`,
    selectLabel: (row: string) => `${row} 선택`,
    /** [스펙 :103] N/A 툴팁. */
    naTip: '이 시설은 해당 연도 실적이 없어요',
    /** Q7. */
    naValue: 'N/A',
    /** 셈 문제 셋. */
    noEmission: '셈할 수 없어요',
    emissionProblem: {
      unit_conversion_missing: '단위를 바꿀 수 있는 값이 없어요',
      factor_unit_invalid: '배출계수의 단위가 맞지 않아요',
      emission_out_of_range: '배출량이 저장할 수 있는 범위를 넘어요',
    } as Readonly<Record<string, string>>,
    /** 블록 단추. */
    remove: '삭제',
    add: '추가',
    save: '저장',
    /** 「저장됐어요」(스펙 S2 와 같은 글). */
    saved: '저장됐어요',
    nothingToSave: '바꾼 내용이 없어요',
    /** [결정 글 sid:MARC-ENT-529] 모달 [저장] 중 앞 사업장은 저장되고 뒤에서 멈췄을 때. */
    savePartial: '일부 사업장은 저장하지 못했어요',
    /** [스펙 :107] 삭제 확인. */
    removeConfirm: '선택한 자산/시설을 삭제할까요?',
    removeOk: '삭제',
    cancel: '취소',
    /** Q4 나가기 확인. */
    leaveConfirm: '변경 내용을 저장하지 않고 나갈까요?',
    leaveOk: '나가기',
    /** [시안 추정] 「자산/시설 추가」 고르기. */
    addTitle: '자산/시설 추가',
    /** W12-1c #15 — Figma 28556:29367 [취소] [확인]. */
    addOk: '확인',
    /** [시안 글] 추가 창 머리(W12-1c #15). 코드 칸은 서버에 없어 이름만(감독 처분 Q7). */
    addHeadName: '자산/시설명',
    addAll: '전체 선택',
    addEmpty: '추가할 수 있는 자산/시설이 없어요',
    /** [초안 글 GX2 M-7] 줄이 없는 사업장 블록 표. */
    rowsEmpty: '[추가]를 눌러 자산/시설을 넣어 주세요',
    addPick: (name: string) => `${name} 추가`,
    /** 칸 오류. */
    amountFormat: '0 이상의 숫자로 입력해 주세요',
    /** [발주서 GX2 S12-03] 쉼표가 있는 값(쉼표를 지워 받지는 않는다). */
    amountComma: '쉼표 없이 숫자만 입력해 주세요',
    amountDecimals: '소수는 6자리까지 입력할 수 있어요',
    amountRejected: '이 값은 저장할 수 없어요',
    unitRejected: '이 단위는 저장할 수 없어요',
    /** 거절 한 줄. */
    saveFailed: '저장하지 못했어요. 다시 시도해 주세요',
    locked: '잠겨 있어 저장할 수 없어요',
    gone: '데이터가 바뀌어 다시 불러왔어요',
    forbidden: '이 작업을 할 권한이 없어요',
    /** [확인 Policy] 메모 자리. */
    memoLabel: '메모',
    memoPlaceholder: '메모를 입력해 주세요.',
    memoSave: '메모 저장',
    memoInvalid: '메모는 2,000자까지 입력할 수 있어요',
    decimalsFailed: '소수점 설정을 저장하지 못했어요',
    /** 잠금(Q8 — 고객사는 잠그기만, 운영 관리자는 풀기도). */
    lock: '잠금',
    unlock: '잠금 해제',
    lockedInfo: (name: string, at: string) => `${name} · ${at}에 잠갔어요`,
    /** 고친 것이 있을 때(W12-1c #20 R6 — 나가기 창과 같은 꼴). */
    lockConfirm: '변경 내용을 저장하지 않고 잠글까요?',
    /** 고객사가 고친 것 없이 잠글 때(R6 — 고객사는 풀 수 없어 늘 묻는다). */
    lockConfirmPlain: '잠그면 운영 관리자만 풀 수 있어요. 잠글까요?',
    lockOk: '잠그기',
    lockFailed: '잠금을 바꾸지 못했어요. 다시 시도해 주세요',
    /** 행 끝 히스토리 칸. */
    historyHead: '히스토리',
    historyOpen: '히스토리 확인',
    historyLabel: (row: string) => `${row} 히스토리 확인`,
    factorLabel: (row: string, name: string) => `${row} 배출계수 보기 ${name}`,
    /** S12 수정 히스토리. [확인 :145] 머리·문구. unit·period·모르는 종류·쪽 넘김은 초안 글. */
    history: {
      title: '수정 히스토리',
      at: '수정일',
      actor: '수정자',
      unit: '단위',
      change: '변경 내용',
      emptyValue: '-',
      value: (before: string, after: string) => `${before} → ${after}`,
      slotValue: (slot: string, before: string, after: string) =>
        `${slot} ${before} → ${after}`,
      naOn: 'N/A 로 설정했어요',
      naOff: 'N/A 를 해제했어요',
      factor: (before: string, after: string) =>
        `배출계수를 변경했어요. ${before} → ${after}`,
      unitChange: (before: string, after: string) =>
        `단위를 변경했어요. ${before} → ${after}`,
      periodChange: (before: string, after: string) =>
        `입력주기를 변경했어요. ${before} → ${after}`,
      unknown: '변경했어요',
      reason: (text: string) => `사유: ${text}`,
      /** [Figma 29429:28326] 사유 있는 줄의 「수정 사유」 단추(W12-4 ③ — 보이는 글 = 접근 이름). */
      reasonOpen: '수정 사유',
      /** 수정 사유 보기 창(W12-4 ③ — Figma 29431:28330). */
      reasonView: {
        /** [e6] Figma 「수정 사유 작성」을 보기 창이라 고침. */
        title: '수정 사유',
        /** [Figma] */
        ok: '확인',
      },
      empty: '변경 기록이 없어요',
      prev: '이전',
      next: '다음',
      page: (page: number, total: number) => `${page} / ${total}`,
      loadFailed: '히스토리를 불러오지 못했어요',
      gone: '행이 없어져 상세를 다시 불러왔어요',
      /** [스펙 :144] 「히스토리 복구」 열·단추(W12-2 ② — Figma 28556:24923 차례: 수정일 · 수정자 · 복구 · 단위 · 변경 내용). */
      restoreHead: '히스토리 복구',
      restore: '복구',
      restoreLabel: (at: string) => `${at} 기록 복구`,
      /** [초안 글] value·factor 줄 복구 확인(Q6). period 줄은 periodChange.notice 를 쓴다(Q4). */
      restoreConfirm: '이 기록으로 되돌릴까요?',
      restoreOk: '복구',
      /** [초안 글] 그 행이 고쳐진 동안(Q5). */
      restoreDirty: '저장한 뒤 복구할 수 있어요',
      /** [초안 글] 복구 성공 한 줄. */
      restored: '복구했어요',
      /** [초안 글] 복구 거절 갈래(Q6 — 서버 차례). notFound 는 gone, locked 는 entry.locked 를 쓴다. */
      restoreRejected: '이 기록은 복구할 수 없어요',
      restoreForbidden: '배출계수 복구는 운영 관리자만 할 수 있어요',
      restoreStale: '입력 주기나 단위가 바뀌어 이 기록으로 되돌릴 수 없어요',
      restoreFailed: '복구하지 못했어요. 다시 시도해 주세요',
    },
    /** S7 입력주기 바꿈(W12-2 ② — Figma 28556:29293 열림 · 28556:29335 닫힘, e6 11-03). */
    periodChange: {
      /** [판 S12-03_r1] 블록 머리 단추. */
      button: '입력 주기 변경',
      /** [Figma] */
      title: '데이터 입력 주기',
      /** [Figma] 안내 줄 — 확인 글을 겸한다(둘째 확인 창 0). [스펙 :125] */
      notice:
        '입력 주기를 바꾸면 기존 데이터는 확인할 수 없어요. 히스토리에서 다시 복구할 수 있어요.',
      /** [초안 글] 그 블록에 저장 안 한 고침이 있을 때 안내 줄 뒤에(Q4). */
      dirty: '저장하지 않은 입력은 사라져요.',
      /** [Figma] */
      placeholder: '데이터 입력 주기 선택',
      /** [Figma] 목록 차례 그대로(년도·분기·월). */
      options: [
        { value: 'year', label: '년도' },
        { value: 'quarter', label: '분기' },
        { value: 'month', label: '월' },
      ] as const,
      cancel: '취소',
      /** [Figma] */
      submit: '선택 완료',
      /** [스펙 :125] 성공 한 줄(그 블록 알림 줄 — 공용 토스트 0). */
      saved: '입력 주기가 저장됐어요',
      /** [초안 글] 422 period. */
      rejected: '입력 주기를 바꾸지 못했어요',
      label: (site: string) => `${site} 입력 주기 변경`,
    },
    /** S8 배출계수 보기(읽기 전용). 머리는 [확인 28556:28818], 산식 한 줄은 스펙 MARC-ENT-463 을 줄인 초안 글. */
    factor: {
      title: '온실가스 종류별 배출계수',
      source: '배출계수 출처',
      version: '버전',
      versionValue: (n: number) => `버전 ${n}`,
      note: '비고',
      inputUnit: '투입량 기준단위',
      ncv: '순발열량',
      /** [시안 글] S12-03a 순발열량 기준단위 줄(W12-1c #17). */
      ncvUnit: '순발열량 기준단위',
      /** [발주서 GX2 S12-03a] 순발열량을 끈 계수(켠 계수는 값만). */
      ncvOff: '쓰지 않음',
      formula: '산식',
      /**
       * [판 S12-03a] 산식 줄 — 포함한 가스마다 한 묶음을 「+」로 잇는다(끈 가스는 빠짐 · 판대로).
       * 묶음 글은 관리자 창(factor.formulaWithNcv·formulaWithoutNcv)과 같은 말.
       */
      formulaText: (gases: readonly string[], ncv: boolean) =>
        gases
          .map(
            (gas) =>
              `(${ncv ? GHG_POOL_FORMULA.withNcv(gas) : GHG_POOL_FORMULA.withoutNcv(gas)})`,
          )
          .join(' + '),
      gas: '온실가스 종류',
      included: '포함여부',
      includedLabel: (gas: string) => `${gas} 포함여부`,
      included1: '포함',
      included0: '제외',
      value: '배출계수',
      gwp: 'GWP',
      empty: '-',
      /** [Figma 29429:28054 — e6 ④] S12-03a 저장 뒤 창(직접입력 계수 보기): 산식 묶음 머리 · 주황 표 · 배출계수명 칸. */
      formulaHead: '온실가스 배출량 산식',
      customMark: '*직접입력',
      /** [캔버스 v246 S12-03a r2 「저장 뒤 보기」] 가스 표 묶음 머리. */
      basics: '기본정보',
      name: '배출계수명',
    },
    /** S8 [배출계수 수정] → S9 배출계수 선택(W12-3 ③ — Figma 28556:28480, e6 11-04 · 운영 관리자만 sid:MARC-ENT-469). */
    factorEdit: {
      /** [초안 글] 스펙 :130 S8 아래 단추. */
      button: '배출계수 수정',
      /** [e6 ③ 11-10] S12-03 출처 칸 [수정](→ S9 바로 — 운영 관리자만) · 이름(화면 읽기 프로그램용). */
      cell: '수정',
      cellLabel: (row: string) => `${row} 배출계수 수정`,
      /** [초안 글] 그 행이 고쳐진 동안(Q7). */
      dirty: '저장한 뒤 바꿀 수 있어요',
      /** [Figma] */
      title: '배출계수 선택',
      /** [Figma] 표 머리 다섯. */
      columns: {
        name: '배출계수명',
        source: '출처',
        industry: '산업',
        inputUnit: '투입량 기준단위',
        tier: 'Tier',
      },
      /** [초안 글] 줄 고름 이름. */
      pick: (name: string) => `${name} 선택`,
      /** [Figma] 끝 줄. */
      custom: '직접 입력',
      /** [초안 글] 직접 입력 단계 제목. */
      customTitle: '배출계수 직접 입력',
      /** [Figma] */
      prev: '이전',
      next: '다음',
      /** [초안 글] */
      /** [e6 ③ 11-10] 표 자리 load-failure 글. */
      loadFailed: '배출계수를 불러오지 못했어요',
      empty: '-',
      /** [초안 글] 548 칸 글(서버 422 fields.custom.<칸> — sid:MARC-ISSUE-548). inputUnit 은 발주서 글. */
      unitProblem: {
        'custom.inputUnit': '이 시설의 단위로 바꿀 수 없는 단위예요',
        'custom.ncvUnit': '이 시설의 단위로 셈할 수 없는 순발열량 단위예요',
        'custom.factorUnit': '이 시설의 단위로 셈할 수 없는 배출계수 단위예요',
      } as Record<string, string>,
      /** [초안 글] 거절 갈래. notFound·locked 는 entry.gone·entry.locked 를 쓴다. */
      forbidden: '배출계수 수정은 운영 관리자만 할 수 있어요',
      failed: '배출계수를 바꾸지 못했어요. 다시 시도해 주세요',
      /** [초안 글] 성공 — 그 블록 알림 줄. */
      done: '배출계수를 바꿨어요',
    },
    /** S11 수정 사유(W12-3 ③ — Figma 29426:48839·48850, e6 11-04). 계수 바꿈·계수 줄 복구가 같이 쓴다(Q6). */
    reason: {
      /** [Figma] */
      title: '수정 사유 작성',
      /** [Figma] 주의 띠. */
      warning: '수정 사유는 한번 입력하면 수정이 불가능해요.',
      /** [Figma] 안내 글 — W12-3 m1(GX2): 「기준 연도」를 뺐다(어느 해를 고쳐도 같은 글). Scope 3 글(ghg-scope3 text)은 sid:MARC-ENT-576 held 라 그대로. */
      guide: '데이터를 수정하신 사유에 대해 기록해 주세요.',
      /** [Figma] */
      label: '내용',
      placeholder: '내용을 입력해 주세요.',
      cancel: '취소',
      confirm: '확인',
      /** [초안 글] 빈 사유(앞뒤 빈칸만도). */
      required: '수정 사유를 입력해 주세요',
      /** [감독 덧] 서버 REASON_MAX 를 넘음(마침표 없음). */
      tooLong: (max: number) => `${max}자까지 쓸 수 있어요`,
      /** [초안 글] 서버 422 fields.reason. */
      rejected: '수정 사유를 확인해 주세요',
    },
  },
  /** [러너 초안] 회사 거절 셋(sid:MARC-ENT-374 — 설정 잘못이라 다시 시도 없음, 화면 전체 자리에 한 줄). */
  company: {
    ambiguous: '작업할 회사를 정하지 못했어요. 운영 관리자에게 문의해 주세요',
    inactive: '사용이 중지된 회사예요. 운영 관리자에게 문의해 주세요',
    not_found: '회사 정보를 찾지 못했어요. 운영 관리자에게 문의해 주세요',
  },
  /** [러너 초안] 회사 거절 셋 — 운영 관리자 세션 글(W12-0b1, 발주서 초안 「작업할 회사를 확인할 수 없어요」 꼴. 「운영 관리자에게 문의」를 빼다). */
  companyOperator: {
    ambiguous: '작업할 회사를 확인할 수 없어요',
    inactive: '작업할 회사가 사용 중지 상태예요',
    not_found: '작업할 회사 정보를 찾지 못했어요',
  },
  /** S1 대시보드 온실가스 탭(밴드 DB1 ②). [판] Figma 28952:20455(시안1)·28607:13640(미설정) 글 그대로 · [e6] sid:MARC-ISSUE-599 노트 ·
   *  시장기반 토글 글은 싣지 않는다(숨김 — sid:MARC-ENT-469·461). 전년 대비·3개년 막대 글은 [e6 DB2] band-handoffs/DB2-figma-values.md ①② (sid:MARC-ENT-598). */
  dashboard: {
    /** 화면 읽기용 이름(눈에 보이는 제목은 앱 틀·탭). */
    screenLabel: SHELL_MENU.dashboard,
    yearLabel: '연도',
    yearOption: (year: number) => `${year}`,
    /** [판] 큰 카드 제목. */
    emissionTitle: '온실가스 배출량',
    /** [판] 총 배출량 카드 제목·부제. */
    totalTitle: '온실가스 총 배출량',
    totalCaption: 'Scope 1 + Scope 2 + Scope 3',
    /** [판] Scope 카드 제목 「Scope n 배출량」(n 은 scopes 차례 — 서버 뿌리 이름이 아니라 판 글). */
    scopeTitle: (scope: string) => `${scope} 배출량`,
    /** [판] 사업장별·배출원별 카드. */
    siteTitle: '사업장별 배출량',
    sourceTitle: '배출원별 배출량',
    /** [판] 단위 꼬리. */
    unitNote: (unit: string) => `단위: ${unit}`,
    /** [판] 몫 글 「54%」(정수 — 서버 share 를 반올림). */
    share: (share: number) => `${share}%`,
    /** 빈 값. */
    empty: '-',
    /** [e6] Scope 3 결과가 없는 해 — 총합 옆 작은 글(sid:MARC-ISSUE-599). */
    scope3None: 'Scope 3 결과 없음',
    /** [판 28607:13640] 미설정(configured 거짓) — 대시보드 전체를 덮는 안내. */
    setupTitle: '온실가스 인벤토리를 먼저 설정해 주세요.',
    setupBody: [
      '온실가스 데이터 설정 후 데이터를 입력하시면',
      '배출량 현황을 확인할 수 있어요.',
    ],
    setupAction: '바로가기',
    /** [e6 값 파일 ②] 판 머리 › 단추 이름. */
    more: (title: string) => `${title} 자세히 보기`,
    /** [판] Scope 이름(범례·배출원 카드·사업장 범례). */
    scopes: ['Scope 1', 'Scope 2', 'Scope 3'],
    /** [e6 값 파일 ②] 몫이 0 보다 크고 1% 미만. */
    shareBelow: '<1%',
    /** [캔버스 r1] Scope 3 카테고리 줄 이름 「C1. 구매 상품 및 서비스」. */
    categoryName: (category: string, name: string) => `${category}. ${name}`,
    /** [e6 DB2 ②] 총 배출량 숫자 아래 「전년 대비」(n 은 크기만 — 소수 한 자리). 반올림해 0.0 이면 「전년과 같음」. */
    yearUp: (percent: string) => `전년 대비 ${percent}% 증가`,
    yearDown: (percent: string) => `전년 대비 ${percent}% 감소`,
    yearSame: '전년과 같음',
    /** [e6 DB2 ①] 3개년 막대 칸 이름(aria-label) 「{해}년 {값} tCO2eq」. */
    barLabel: (year: number, value: string, unit: string) =>
      `${year}년 ${value} ${unit}`,
  },
  common: {
    retry: '다시 시도',
    /** [러너 초안] 불러오는 중 상자 이름(화면 읽기 프로그램용). */
    loading: '불러오는 중',
  },
} as const;

export type GhgText = typeof GHG_TEXT;
