// 데이터 검증 화면 글 한 곳(밴드 DV2a — 발주서 Directive). 아무것도 가져오지 않는다(app/guards/layers.test.ts).
// 정본 차례: 사용자 > 디자인 2e band-handoffs/DV2a-design-text.md(①~⑦) > 시안 v148 판(band-handoffs/DV-design-v148-boards/DV-0*_r1.dc.html)
//   > 감독 글 표 DV2a-copy.md. 판·2e 둘 다에 없는 글은 짓지 않는다(빈 칸 + 보고의 물을 거리).
// 서버 message·errorMessage·failure.message 는 화면에 0 — 갈래는 code·kind 로 고른다. 없는 값(null)은 「–」.

const DASH = '–';
/** 없는 값은 「–」. */
const orDash = (value: string | number | null) =>
  value === null ? DASH : String(value);

/** 연도 범위(「2022~2024년」, 하나면 「2024년」, 없으면 「–」). */
const yearSpan = (years: readonly string[]) =>
  years.length === 0 ? DASH
  : years.length === 1 ? `${years[0]}년`
  : `${years[0]}~${years[years.length - 1]}년`;

/** 항목 칸 조각(이름형 글 · 「N/A」 · 주지 않음). */
type TermText =
  { kind: 'text'; text: string } | { kind: 'na' } | { kind: 'missing' };
/** 판정 허용 오차가 0 인가 — 글자가 아니라 수로 본다(새 실행 "0.0", 옛 실행의 모델 값 "0" 도 0 — 밴드 DV16, sid:MARC-ENT-685). */
const zeroTolerance = (tolerance: string) =>
  tolerance.trim() !== '' && Number(tolerance) === 0;

const term = (t: TermText) =>
  t.kind === 'text' ? t.text
  : t.kind === 'na' ? '값 없음'
  : DASH;

export const DV_TEXT = {
  dash: DASH,
  orDash,
  yearSpan,
  /** 틀(AppShell) 글 — 영문번역 TR_TEXT.shell 을 옮겨 적음(가져오지 않는다, 2e ⑦), title 만 「데이터 검증」. */
  shell: {
    menuLabel: '모듈 메뉴',
    logo: '로고 자리',
    title: '데이터 검증',
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
  /** STEP 띠(2e ⑦ — DV-02 = 1 · DV-03 = 2 · DV-04 = 3). */
  steps: {
    label: '검증 단계',
    items: [
      { step: 'STEP 1', label: '파일·기업 정보' },
      { step: 'STEP 2', label: '계산 검사·리스크 진단' },
      { step: 'STEP 3', label: '결과' },
    ],
  },
  common: {
    toList: '목록으로',
    retry: '다시 시도',
    rerun: '다시 실행',
    viewResult: '결과 보기',
    newCheck: '새 검증',
    download: '내려받기',
    downloadFailed: '파일을 받지 못했어요. 다시 시도해 주세요.',
    notFound: '결과를 찾을 수 없어요',
  },
  /** DV-00 검증 안내(판 그대로 — 올리는 것은 「JSON」 없이 엑셀로 말한다: 컨설턴트 댓글 11-10, sid:MARC-ISSUE-646 · 밴드 DV13). */
  intro: {
    title: '데이터 검증',
    heading: '데이터 검증이란',
    lead: [
      'EDK 인벤토리 엑셀을 올리면, 환경 항목 사이에 서로 맞아야 하는 산식(합계 · 부분합 · 비율)을 세우고 연도별 값이 맞는지 계산해요.',
      '데이터와 기업 정보를 보고 데이터 품질 · 정보 · 해석 리스크의 가설을 표로 정리해 드려요.',
    ],
    table: {
      head: ['구분', '의미', '예시'],
      rows: [
        [
          '맞음',
          '산식 양쪽의 차이가 0 인 검사',
          '「Scope 1 + Scope 2 = 총 배출량」이 2023년에 차이 0 으로 맞음',
        ],
        [
          '어긋남',
          '산식 양쪽의 차이가 0 이 아닌 검사 · 아주 작은 차이도 어긋남이에요',
          '2024년 총 배출량이 구성 합과 0.5 다름',
        ],
        [
          '계산 못 함',
          '값이 비었거나 수가 아니거나 0 으로 나누게 되어 계산할 수 없는 검사',
          '재생에너지 비율의 분모(총 에너지 사용량)가 0',
        ],
        [
          '리스크',
          'AI 가 데이터를 보고 세운 품질 · 해석의 가설. 웹 검색으로 찾은 기준은 출처를 함께 적어요',
          '「보고범위가 바뀌었을 가능성이 있습니다(정보 부족)」',
        ],
      ],
    },
    hint: '시작하기 버튼을 눌러 검증을 시작해 보세요.',
    flowTitle: '검증 과정',
    flow: [
      {
        step: 'Step 1',
        title: '파일 · 기업 정보',
        body: 'EDK 인벤토리 엑셀을 올리고 기업명 · SASB 산업분류 · 주요 중대토픽 · 보고연도를 넣어요',
      },
      {
        step: 'Step 2',
        title: '계산 검사 · 리스크 진단',
        body: '검증 산식을 세워 연도별 값이 맞는지 계산하고, 데이터 품질 · 해석 리스크를 정리해요',
      },
      {
        step: 'Step 3',
        title: '결과',
        body: '검사 기록과 리스크 표를 확인하고 결과 엑셀을 내려받아요',
      },
    ],
    give: {
      title: '올리는 것',
      rows: [
        [
          '파일',
          'EDK 인벤토리 양식 그대로의 엑셀(.xlsx) 한 개 · 붙여 넣어도 돼요',
        ],
        ['검증 범위', '테마 「환경」의 항목 · 넣은 데이터에 담긴 연도 모두'],
        ['기업 정보', '기업명 · SASB 산업분류 · 주요 중대토픽 · 보고연도'],
      ],
    },
    get: {
      title: '받는 것',
      rows: [
        [
          '결과 화면',
          '계산 계획 · 검증 결과(맞음 · 어긋남 · 계산 못 함) · 리스크 표 · 검토 글',
        ],
        [
          '결과 엑셀',
          '시트 7개: 요약 · 계산 계획 · 검증 결과 · 검토 글 · 리스크 · 출처 · 설정',
        ],
        ['다시 실행', '같은 파일을 다시 돌리면 새 실행으로 기록해요'],
      ],
    },
    start: '시작하기',
  },
  /** 입력 출처 글(DV2b — DV-03·04 머리는 2e ④ 「파일명(붙여 넣었으면 「붙여 넣은 데이터」)」, 목록 줄은 판 DV-01 「· 시각」). */
  source: {
    paste: '붙여 넣은 데이터',
    /** DV-03·04 머리 제목: 파일 이름 · 「붙여 넣은 데이터」 · 출처 없는 옛 실행은 fallback(기업명 — DV2a Q4 (나)). */
    title: (
      source: { kind: 'file'; name: string } | { kind: 'paste' } | null,
      fallback: string,
    ) =>
      source === null ? fallback
      : source.kind === 'file' ? source.name
      : '붙여 넣은 데이터',
    pastedAt: (at: string) => `붙여 넣은 데이터 · ${at}`,
  },
  /** DV-01·01a 검증 목록(판 그대로 — 머리 아래 셈·안내 줄은 지웠다: 그린워싱과 맞춤, sid:MARC-ENT-625). */
  list: {
    title: '검증 목록',
    introLink: '검증 안내',
    search: '파일명 검색',
    yearLabel: '보고연도',
    yearAll: '보고연도 전체',
    tabsLabel: '상태',
    tabs: {
      all: '전체',
      active: '대기·처리 중',
      done: '완료',
      failed: '실패',
    },
    mineOnly: '내가 올린 것만',
    newCheck: '새 검증',
    columns: {
      fileName: '파일명',
      reportingYear: '보고연도',
      createdBy: '담당자',
      itemCount: '환경 항목',
      lastRun: '검증 완료 일자',
      mismatches: '어긋남',
      uncomputable: '계산 못 함',
      status: '상태',
      next: '다음 할 일',
    },
    badge: {
      queued: '대기',
      /** 「검증 중 · 계산 검토」(판). 단계를 모르면 앞 몫만. */
      processing: (step: string | null) =>
        step === null ? '검증 중' : `검증 중 · ${step}`,
      done: '완료',
      someFailed: '일부 단계 못 함',
      failed: '실패',
    },
    next: {
      result: '결과 보기',
      progress: '진행 보기',
      rerun: '다시 실행',
    },
    notice:
      '파일을 올리면 테마 「환경」의 항목으로 검증 산식을 세우고, 합계·부분합·비율이 맞는지 계산한 뒤 데이터 품질·해석 리스크를 정리해요. 같은 파일을 다시 실행하면 새 실행으로 기록해요.',
    empty: '아직 검증한 파일이 없어요. EDK 인벤토리 엑셀을 올려 시작해요.',
    emptyFiltered: '조건에 맞는 검증이 없어요',
    clearFilter: '거르기 풀기',
    loadFailed: '검증 목록을 불러오지 못했어요',
    retry: '다시 시도',
    /** 읽는 동안 300ms 뒤 숨긴 상태 글(옛 LoadSkeleton 의 PARTS_TEXT.loading 과 같은 글 — 밴드 DV4). */
    loading: '불러오는 중',
  },
  /** DV-02 새 검증(판 그대로 + 2e ⑤⑦). */
  newCheck: {
    title: '새 검증',
    lead: 'EDK 정량 데이터와 기업 정보를 넣으면 수치의 정합성과 해석 리스크를 살펴요.',
    dataTitle: '1. 데이터 넣기',
    tabsLabel: '넣는 방법',
    tabFile: '파일 올리기',
    tabPaste: '붙여 넣기',
    dropTitle: 'EDK 인벤토리 엑셀 파일을 끌어 놓거나 눌러서 골라 주세요',
    dropHint: 'EDK 인벤토리 양식 그대로의 엑셀(.xlsx) 한 개',
    dropButton: '파일 고르기',
    removeFile: '파일 지우기',
    pasteLabel: 'EDK 정량 데이터 JSON',
    pastePlaceholder: 'EDK 정량 데이터 JSON 을 붙여 넣어 주세요',
    reading: '파일을 읽는 중이에요',
    readingHint: '다 읽을 때까지 [검증 시작]은 눌리지 않아요',
    /** 파일 줄(2e ⑦ — 날짜 뺌). */
    fileLine: (themes: number, items: number, size: string) =>
      `테마 ${themes}개 · 항목 ${items}개 · ${size}`,
    /** 미리 읽기 줄. */
    preview: (envItems: number, keyItems: number, years: string) =>
      `검증은 테마 「환경」의 항목만 해요 · 환경 ${envItems}항목(핵심데이터 ${keyItems}) · ${years}`,
    /** 양식 내려받기 단추(밴드 DVX1 ② — 올리기 칸 머리 오른쪽). */
    templateDownload: '엑셀 양식 내려받기',
    templateFailed: '양식을 내려받지 못했어요. 잠시 뒤 다시 눌러 주세요',
    /** 양식 단추 아래 회색 한 줄(디자인 74 판). */
    templateHint:
      'EDK 인벤토리 양식 또는 이 양식에 맞춰 입력한 파일을 올려 주세요',
    /** 엑셀 읽기에서 뺀 테마(이름 없이 수만 — 서버가 이름을 보내지 않는다). */
    skippedThemes: (themes: number, items: number) =>
      `검증에 쓰지 않는 테마 ${themes}개(항목 ${items}개)는 빼고 읽었어요`,
    /** 엑셀 읽기로 보고연도를 채웠을 때(companyFilled 자리). */
    yearFilled: (year: string) =>
      `파일의 마지막 연도로 보고연도를 ${year}년으로 골랐어요`,
    errors: {
      notJsonFile: '엑셀(.xlsx)이나 JSON(.json) 파일만 올릴 수 있어요',
      fileTooLarge:
        '파일이 너무 커요. 엑셀은 1MB, JSON 은 256KB 안의 파일만 올릴 수 있어요',
      /** 엑셀 읽기 거절(서버 kind 마다 — 서버 글은 쓰지 않는다). 행 번호는 엑셀의 행 번호. */
      xlsx: {
        too_large:
          '파일이 너무 커요. 엑셀은 1MB, JSON 은 256KB 안의 파일만 올릴 수 있어요',
        not_xlsx:
          '엑셀 파일을 열지 못했어요. EDK 인벤토리 양식을 .xlsx 로 저장한 파일인지 확인해 주세요',
        unsafe_xlsx:
          '이 엑셀 파일은 열 수 없어요. 표만 새 파일에 옮겨 저장한 뒤 다시 올려 주세요',
        bad_header:
          '첫 행에서 EDK 인벤토리 양식의 열 이름(ID·테마·항목…·연도)을 찾지 못했어요. 첫 행을 고치지 말고 올려 주세요',
        bad_cell: (row: number | null) =>
          row === null ?
            '날짜나 참/거짓 칸이 있어요. 숫자나 글자로 바꿔 주세요'
          : `${row}행에 날짜나 참/거짓 칸이 있어요. 숫자나 글자로 바꿔 주세요`,
        no_theme: (row: number | null) =>
          row === null ? '테마 칸이 빈 행이 있어요' : (
            `${row}행의 테마 칸이 비어 있어요`
          ),
        too_many_rows: (max: number) =>
          `항목이 너무 많아요. ${max.toLocaleString('en-US')}개 안의 파일만 올릴 수 있어요`,
        too_many_scanned_rows:
          '빈 행이 너무 많아요. 표 아래의 빈 행을 지우고 다시 올려 주세요',
        no_rows: '항목이 하나도 없어요. 항목을 채운 파일을 올려 주세요',
        no_target_theme:
          '「환경」 테마 항목이 없어요. 환경 테마 줄이 든 파일을 올려 주세요',
        long_cell: (row: number | null, column: number | null, max: number) =>
          row === null || column === null ?
            `글이 너무 긴 칸이 있어요. ${max.toLocaleString('en-US')}자 안으로 줄여 주세요`
          : `${row}행 ${column}열 칸의 글이 너무 길어요. ${max.toLocaleString('en-US')}자 안으로 줄여 주세요`,
        /** 서버가 모으다 멈춘 갈래 — 화면이 바꾼 뒤 재는 convertedTooLarge 와 같은 글. */
        converted_too_large:
          '읽은 항목이 너무 많아 한 번에 검증할 수 없어요. 환경 테마 줄을 나눠 올려 주세요',
      },
      /** 엑셀을 data 로 바꾼 글이 256KiB 를 넘음(보낼 수 없다). */
      convertedTooLarge:
        '읽은 항목이 너무 많아 한 번에 검증할 수 없어요. 환경 테마 줄을 나눠 올려 주세요',
      /** 엑셀 읽기 경로가 답하지 않았거나 답의 꼴이 틀림. */
      xlsxUnreachable: '파일을 읽지 못했어요. 잠시 뒤 다시 올려 주세요',
      fileUnreadable:
        '파일을 읽지 못했어요. 테마별 항목 꼴의 JSON 인지 확인해 주세요',
      pasteNotJson: 'JSON 꼴이 아니에요. 중괄호·따옴표를 확인해 주세요',
      pasteTooLarge: '256KB 안으로 넣어 주세요',
      badName:
        '파일 이름에 쓸 수 없는 글자가 있거나 너무 길어요 · 이름을 고쳐 다시 올려 주세요',
      startFailed:
        '검증을 시작하지 못했어요. 넣은 내용은 그대로 있으니 다시 눌러 주세요.',
    },
    companyTitle: '2. 기업 정보',
    name: '기업명',
    sasb: 'SASB 산업분류',
    topics: '주요 중대토픽',
    topicPlaceholder: '토픽을 넣고 Enter',
    topicAdd: '중대토픽 더하기',
    topicRemove: (topic: string) => `${topic} 빼기`,
    topicsHint: '하나 이상',
    year: '보고연도',
    companyHint:
      '기업 정보는 AI 가 수치를 해석하고 리스크를 정리할 때 참고해요.',
    /** 서버 입력 꼴 파일·글의 회사 정보로 빈 칸을 채웠을 때(밴드 DV5). */
    companyFilled: '넣은 데이터의 회사 정보로 빈 칸을 채웠어요',
    required: {
      name: '기업명을 넣어 주세요',
      sasb: 'SASB 산업분류를 넣어 주세요',
      topics: '중대토픽을 하나 이상 넣어 주세요',
    },
    checksTitle: '3. 검사 내용',
    checksHead: ['단계', '하는 일'],
    checks: [
      [
        '계산 계획',
        '항목 이름과 단위를 보고, 서로 맞아야 하는 검증 산식(합계·부분합·비율)을 세워요',
      ],
      [
        '계산 검토',
        '산식마다 연도별 값을 찾아 계산 도구로 맞는지 봐요. 차이가 0 이면 맞음, 0 이 아니면 어긋남이에요',
      ],
      [
        '리스크 진단',
        '데이터와 기업 정보를 보고 데이터 품질·정보·해석 리스크를 표로 정리해요. 계산 검토 결과는 보지 않고 따로 돌아요. 웹 검색으로 찾은 기준은 출처를 함께 적어요',
      ],
    ],
    cancel: '취소',
    start: '검증 시작',
  },
  /** DV-03 처리 상태(판 + 2e ③④⑦). */
  status: {
    running: '검증 중이에요',
    keepsGoing: '이 창을 닫아도 검증은 계속돼요',
    /** 머리: 시작 · 제목(출처 글 — DV2b, 옛 실행은 기업명) · 계속돼요(2e ④ — 항목 수 뺌).
     *  「계속돼요」 토막은 돌고 있을 때만(끝남은 뺀다 — 그린워싱 GW-03 meta 꼴, 밴드 DV13 ③). */
    head: (startedAt: string, title: string, running = true) =>
      `${startedAt} 시작 · ${title}${running ? ' · 이 창을 닫아도 검증은 계속돼요' : ''}`,
    nth: (step: string, n: number) => `${step} · 다섯 단계 가운데 ${n}번째`,
    progressTitle: '진행',
    progressNth: (n: number) => `다섯 단계 가운데 ${n}번째`,
    footnote:
      '계산 계획을 세우지 못하면 계산 검토는 건너뛰고 리스크 진단으로 가요. 계산 검토가 다 마치기 전에 멈추면 그때까지 본 산식만 남겨요.',
    queued: '차례를 기다리고 있어요 · 앞 작업이 끝나면 저절로 시작해요',
    /** 단계 이름과 상태 글(2e ④ — 처리 중엔 상태 글만, 수 0). 대기 글이 판에 없는 단계는 빈 글. */
    stepNames: {
      load: '파일 읽기',
      plan: '계산 계획',
      review: '계산 검토',
      insight: '리스크 진단',
      report: '결과 엑셀 만들기',
    },
    stepText: {
      load: {
        done: '테마 「환경」 항목을 읽었어요',
        running: '넣은 데이터를 읽고 있어요',
        pending: '대기',
      },
      plan: {
        done: '검증 산식을 세웠어요',
        running: '항목 이름과 단위를 보고 검증 산식을 세우고 있어요',
        // 판 DV-03 에 없어 판 DV-02 「검사 내용」 표의 글로(새 낱말 0 — 감독 답 10-23, 다른 단계 대기 글과 같은 꼴).
        pending:
          '항목 이름과 단위를 보고, 서로 맞아야 하는 검증 산식(합계·부분합·비율)을 세워요',
      },
      review: {
        done: '산식마다 연도별 값을 맞춰 봤어요',
        running: '산식마다 연도별 값을 찾아 맞는지 계산하고 있어요',
        pending: '산식마다 연도별 값을 찾아 계산 도구로 맞는지 봐요',
      },
      insight: {
        done: '리스크 표를 정리했어요',
        running: '데이터와 기업 정보를 보고 리스크를 표로 정리하고 있어요',
        pending:
          '데이터와 기업 정보를 보고 데이터 품질·해석 리스크를 표로 정리해요',
      },
      report: {
        done: '결과 엑셀을 만들었어요',
        running: '결과 엑셀을 만들고 있어요',
        pending: '계산 검토와 리스크 진단을 엑셀 한 파일로 묶어요',
      },
    },
    stepBadge: {
      done: '완료',
      running: '진행 중',
      pending: '대기',
      failed: '못 함',
      not_run: '돌리지 않음',
    },
    doneTitle: '검증이 끝났어요',
    /** 끝남 카드의 이름 아래 줄(2e ④ — 결과를 못 읽으면 끝 시각만. 밴드 DV13 ③ 부터 머리가 아니라 카드). 「산식」 = Plan 산식 수(계획을 못 세웠으면 칸 뺌) ·
     *  「검산 n곳(맞음 · 어긋남 · 계산 못 함)」 = 연도 칸(+ 도구 오류 줄) 셈, DV-04 요약 카드와 같은 셈(시안 v212 DV-03 r2, 밴드 DV7) · 리스크(밴드 DV6). */
    doneLine: (
      finishedAt: string,
      counts: {
        plan: number | null;
        places: number;
        ok: number;
        mismatches: number;
        uncomputable: number;
        risks: number | null;
      } | null,
    ) =>
      counts === null ?
        `${finishedAt} 끝남`
      : `${finishedAt} 끝남 · ${counts.plan === null ? '' : `산식 ${counts.plan}개 · `}검산 ${counts.places}곳(맞음 ${counts.ok} · 어긋남 ${counts.mismatches} · 계산 못 함 ${counts.uncomputable}) · 리스크 ${counts.risks === null ? DASH : `${counts.risks}건`}`,
    /** 「확인할 곳 — …」(2e ③ — 줄을 「 · 」로). */
    checkPlaces: (items: readonly string[]) =>
      `확인할 곳 — ${items.join(' · ')}`,
    failedTitle: '검증이 멈췄어요',
    failedBody:
      '검증을 끝내지 못했어요. [다시 실행]을 누르면 같은 파일로 처음부터 다시 봐요.',
    noTargetTitle: '검증할 항목이 없어요',
    noTargetBody:
      '파일에서 「환경」 테마 항목을 찾지 못해 계산 계획·검토·리스크 진단을 하지 않았어요. 결과 엑셀 「요약」 시트에 이 경고만 남아요.',
    loadFailed: '진행 상태를 불러오지 못했어요',
  },
  /** 결과 단계 갈래 글(2e ③). short = DV-03 「확인할 곳」, band = DV-04 띠·DV-04a 글.
   *  partial 은 「다 마치기 전에 멈췄어요」 꼴 — 횟수 상한은 사용자에게 말하지 않는다(밴드 DV6). */
  notices: {
    plan_partial: {
      short: '계산 계획이 다 마치기 전에 멈췄어요',
      band: '계산 계획이 다 마치기 전에 멈췄어요. 빠진 산식이 있을 수 있고, 그때까지 세운 산식으로 검토했어요. 다시 실행하면 처음부터 다시 봐요.',
    },
    plan_unreadable: {
      short: '계산 계획을 못 했어요',
      band: 'AI 가 낸 검증 산식을 읽지 못해 계산 검토를 돌리지 않았어요. 리스크 표는 그대로 보여요. 다시 실행해 주세요.',
    },
    plan_failed: {
      short: '계산 계획을 못 했어요',
      band: '계산 계획을 끝내지 못했어요 · AI 호출이 실패했어요. 계산 검토는 돌리지 않았고, 리스크 진단은 따로 정리했어요. 다시 실행하면 새 실행으로 처음부터 봐요.',
    },
    review_partial: {
      short: '계산 검토가 다 마치기 전에 멈췄어요',
      band: (formulas: number) =>
        `계산 검토가 다 마치기 전에 멈췄어요. 산식 ${formulas}개 가운데 덜 본 산식이 있을 수 있고, 그때까지의 결과로 정리했어요. 다시 실행하면 처음부터 다시 봐요.`,
    },
    review_failed: {
      short: '계산 검토를 끝내지 못했어요',
      band: (places: number) =>
        `계산 검토를 끝내지 못했어요 · AI 호출이 실패했어요. 실패 전까지 검산한 ${places}곳은 아래에 있고 엑셀에도 담겨요. 리스크 진단은 데이터와 기업 정보만 보고 따로 정리했어요. 다시 실행하면 새 실행으로 처음부터 봐요.`,
    },
    insight_partial: {
      short: '리스크 진단이 다 마치기 전에 멈췄어요',
      band: '리스크 진단이 다 마치기 전에 멈췄어요. 빠진 리스크가 있을 수 있고, 그때까지 정리한 리스크만 보여요. 다시 실행하면 처음부터 다시 봐요.',
    },
    insight_failed: {
      short: '리스크 진단을 못 했어요',
      band: '리스크 진단을 끝내지 못했어요 · AI 호출이 실패했어요. 계산 검토 결과는 아래에 있어요. 다시 실행하면 새 실행으로 처음부터 봐요.',
    },
    noTarget:
      '넣은 데이터에 테마 「환경」이 없어 검증할 항목이 없어요. 환경 테마를 포함한 데이터로 다시 넣어 주세요.',
  },
  /** DV-04·04a 결과(판 + 2e ①②⑥⑦). */
  result: {
    done: '완료',
    someFailed: '일부 단계 못 함',
    /** 메타 줄(「1회차」 0 — 서버에 회차 없음). */
    meta: (
      finishedAt: string,
      company: string,
      year: string,
      envItems: number,
      keyItems: number,
      years: string,
    ) =>
      `${finishedAt} 끝남 · ${company} · 보고연도 ${year} · 테마 환경 ${envItems}항목(핵심 ${keyItems}) · ${years}`,
    stagesLabel: '단계',
    stageNames: {
      plan: '계산 계획',
      review: '계산 검토',
      insight: '리스크 진단',
    },
    stageState: {
      done: '완료',
      partial: '완료',
      failed: '실패',
      not_run: '돌리지 않음',
    },
    partialTag: '다 마치기 전에 멈춤',
    cards: {
      /** 「검산」 = 맞음 + 어긋남 + 계산 못 함(연도 칸·도구 오류 줄 「곳」) — 「산식」은 Plan 셈에만(밴드 DV6 · DV7, 시안 v212 DV-04 r2). */
      checks: '검산',
      checksValue: (n: number) => `${n}곳`,
      checksSub: '맞음 + 어긋남 + 계산 못 함',
      ok: '맞음',
      okValue: (n: number) => `${n}곳`,
      /** 판정 허용 오차 0 인 실행은 「차이 0」, 옛 실행(0 이 아님)은 옛 글(밴드 DV16, sid:MARC-ENT-685). */
      okSub: (tolerance: string) =>
        zeroTolerance(tolerance) ? '차이 0' : '허용 오차 안',
      mismatches: '어긋남',
      mismatchesValue: (n: number) => `${n}곳`,
      mismatchesSub: (tolerance: string) =>
        zeroTolerance(tolerance) ? '차이가 있는 연도' : '허용 오차를 넘은 연도',
      uncomputable: '계산 못 함',
      /** 어긋남·계산 못 함은 연도 칸(+ 도구 오류 줄)의 셈이라 「곳」(밴드 DV6). */
      uncomputableValue: (n: number) => `${n}곳`,
      /** 0 이 아닌 갈래만 차례대로(2e ②). */
      uncomputableSub: (nonNumeric: number, division: number, tool: number) =>
        [
          nonNumeric > 0 ? `수가 아닌 값 ${nonNumeric}` : null,
          division > 0 ? `0으로 나눔 ${division}` : null,
          tool > 0 ? `도구가 답을 못 냄 ${tool}` : null,
        ]
          .filter((part) => part !== null)
          .join(' · '),
      risks: '리스크',
      risksValue: (n: number | null) => (n === null ? DASH : `${n}건`),
      risksSub: '리스크 진단 표',
      risksUnparsed: '표로 나누지 못했어요',
      risksNone: '못 함',
      /** 큰 수 뒤의 단위(작은 글 — 밴드 DV3 W8). 「–」에는 붙이지 않는다. */
      units: {
        checks: '곳',
        ok: '곳',
        mismatches: '곳',
        uncomputable: '곳',
        risks: '건',
      },
    },
    planTitle: '계산 계획',
    planLead: (n: number) => `AI 가 세운 검증 산식 ${n}개`,
    planHead: ['산식'],
    checksTitle: '검증 결과',
    /** 표 머리(2e ⑦ — settings.tolerance 는 실행의 기본값, 실제 쓴 값은 검사 줄 설명(explain). 밴드 DV4, sid:MARC-ISSUE-365 (가)).
     *  「빠지면」·「검산마다」가 「지표마다」로 읽혀 실제 동작(AI 가 검산 도구 부름마다 정함, 안 주면 기본값)대로 고침 — 컨설턴트 댓글 11-10 · sid:MARC-ISSUE-648 (밴드 DV14).
     *  판정 허용 오차 0 인 실행은 「차이가 0 이 아니면 어긋남」, 옛 실행(0 이 아님)은 그때 판정한 규칙 글 그대로(밴드 DV16, sid:MARC-ENT-685). */
    checksLead: (tolerance: string) =>
      zeroTolerance(tolerance) ?
        '차이가 0 이 아니면 어긋남이에요 · 항목 단위, 비율은 %p'
      : `허용 오차는 AI 가 검산마다 정하고, 정하지 않은 검산은 기본값(${tolerance})을 써요 · 항목 단위, 비율은 %p`,
    checksLeadFailed: (places: number, tolerance: string) =>
      zeroTolerance(tolerance) ?
        `실패 전까지 검산 ${places}곳 · 차이가 0 이 아니면 어긋남이에요 · 항목 단위, 비율은 %p`
      : `실패 전까지 검산 ${places}곳 · 허용 오차는 AI 가 검산마다 정하고, 정하지 않은 검산은 기본값(${tolerance})을 써요 · 항목 단위, 비율은 %p`,
    onlyProblems: '어긋남·계산 못 함만',
    checksHead: ['규칙', '항목', '연도', '판정', '차이', '메모', '계산 식'],
    rules: { sum: '합계', sum_n: '부분합', ratio: '비율' },
    verdicts: { ok: '맞음', mismatch: '어긋남', uncomputable: '계산 못 함' },
    notes: {
      'non-numeric': '수가 아닌 값',
      'division by zero': '0으로 나눔',
      tool: '도구가 답을 내지 못했어요',
    },
    show: '보기',
    hide: '접기',
    /** 카드 머리 접기 단추(계산 계획·검증 결과·리스크·검토 글 — 밴드 DV17). */
    fold: (title: string) => `${title} 접기`,
    unfold: (title: string) => `${title} 펼치기`,
    formula: '계산 식',
    /** 항목 칸 줄(판 DV-04: 이름형 합계·비율, 단건 부분합 꼴). */
    items: {
      term,
      sumByName: (target: TermText, addends: readonly TermText[]) => [
        `합계 ${term(target)}`,
        ...addends.map((a, i) => `${i === 0 ? '=' : '+'} ${term(a)}`),
      ],
      sumRaw: (target: TermText, addends: readonly TermText[]) => [
        `더한 값 ${addends.map(term).join(' + ')} ≈ 대상 ${term(target)}`,
      ],
      ratioByName: (n: TermText, d: TermText, e: TermText) => [
        term(n),
        `÷ ${term(d)} × 100`,
        `≈ ${term(e)}`,
      ],
      ratioRaw: (n: TermText, d: TermText, e: TermText) => [
        `${term(n)} ÷ ${term(d)} × 100 ≈ ${term(e)}`,
      ],
    },
    /** 계산 식 펼침의 이름 단 줄 다섯(밴드 DV6 — 계산식·입력값·실제값·판정·차이). */
    explainRows: {
      formula: '계산식',
      input: '입력값',
      actual: '실제값',
      verdict: '판정',
      diff: '차이',
      /** 입력값 = 파일에 적힌 값, 실제값 = 다시 계산한 값(머리 뒤 작은 글). */
      inputHint: '파일에 적힌 값',
      actualHint: '다시 계산한 값',
      percent: (value: string) => `${value}%`,
      /** 실제값 뒤 괄호 = 넣은 값(설명 글의 글자 그대로 — 밴드 DV17). 합계·부분합은 더한 값을 「 + 」로(0개면 괄호 없음), 비율은 「분자 ÷ 분모 × 100」. */
      actualWith: (
        value: string,
        inputs:
          | { kind: 'sum'; addends: readonly string[] }
          | { kind: 'ratio'; numerator: string; denominator: string },
      ) =>
        inputs.kind === 'ratio' ?
          `${value} (${inputs.numerator} ÷ ${inputs.denominator} × 100)`
        : inputs.addends.length === 0 ? value
        : `${value} (${inputs.addends.join(' + ')})`,
      /** 차이 값 뒤: 비율은 %p, 값은 대상 항목의 단위(빈 칸·null 은 수만 — 밴드 DV10). 허용 오차 값에는 단위를 붙이지 않는다.
       *  그 검산의 허용 오차가 0 이면 차이만 보인다(「허용 오차 0 안/넘음」 없음 — 밴드 DV16, sid:MARC-ENT-685). */
      diffValue: (
        diff: string,
        kind: 'value' | 'percent',
        tolerance: string,
        within: boolean,
        unit: string | null = null,
      ) =>
        kind === 'percent' ?
          `${diff}%p${zeroTolerance(tolerance) ? '' : ` · 허용 오차 ${tolerance}%p ${within ? '안' : '넘음'}`}`
        : `${diff}${unit ? ` ${unit}` : ''}${zeroTolerance(tolerance) ? '' : ` · 허용 오차 ${tolerance} ${within ? '안' : '넘음'}`}`,
    },
    /** 계산 못 함의 이유(펼침 실제값 뒤 — 2e ①). */
    explain: {
      nonNumeric: '수가 아닌 값이 있어 계산하지 못했어요',
      divisionByZero: '나누는 값이 0이라 계산하지 못했어요',
    },
    checksFootnote:
      '계산 검토가 본 차례대로예요. 차이는 (더한 값) − 대상이고, 비율은 퍼센트 포인트예요. 값 조회·검색 기록과 오류 원문은 엑셀 「검증 결과」 시트에 담겨요.',
    noProblems: (tolerance: string) =>
      zeroTolerance(tolerance) ?
        '어긋남과 계산 못 함이 없어요. 모든 검사의 차이가 0 이에요'
      : '어긋남과 계산 못 함이 없어요. 모든 검사가 허용 오차 안에서 맞았어요',
    noChecks: '계산 검토에서 한 검사가 없어요',
    /** 카드 제목은 단계 이름과 같게(밴드 DV17 감독 판단 — 86a9fc65). 위 수 칸 「리스크 n건」은 건수라 그대로. */
    risksTitle: '리스크 진단',
    risksLead: '리스크 진단 · AI 생성',
    risksHead: [
      '영역',
      '지표',
      '관찰 내용 및 스토리',
      '잠재 리스크',
      '해석·가설',
    ],
    sources: '출처',
    risksEmpty: 'AI 가 정리한 리스크가 없어요',
    risksUnparsed:
      'AI 가 쓴 리스크 글을 표로 나누지 못해 원문 그대로 보여 드려요.',
    risksFailed: '리스크 표를 만들지 못했어요',
    risksPartialText: 'AI 가 쓴 리스크 글 일부를 원문 그대로 보여 드려요.',
    reviewTitle: '검토 글',
    reviewLead: '계산 검토 · AI 생성',
    /** 받기 모달(머리 [내려받기] → 공용 DownloadDialog, 판 DV-04b r1 · 밴드 DV15 — sid:MARC-ENT-662). 제목은 common.download. */
    downloads: {
      close: '닫기',
      busy: '받는 중',
      help: '없는 까닭',
      reportName: '결과 엑셀',
      reportNote:
        'AI 데이터 검증 결과물 — 검증 결과와 리스크 표를 담은 엑셀이에요',
    },
    loadFailed: '결과를 불러오지 못했어요',
  },
} as const;
