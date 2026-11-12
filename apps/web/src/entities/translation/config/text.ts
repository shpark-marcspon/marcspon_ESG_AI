// 영문번역 화면 글(밴드 TRW0a ②·TRW0b). 화면 글은 전부 여기 한 곳이다 — 시안 판이 바뀌면 글만 바꾼다.
// 정본 판: 확정 판 v136(band-handoffs/TR-design-v136-boards, 2026-10-23 — TRW0b 가 TRW0a 글까지 글자로 대조해 맞춤).
// 아무것도 가져오지 않는다(app/guards/layers.test.ts). 값을 끼우는 글은 함수로 둔다. 시안 판에 글이 없는 갈래는 두지 않는다.
// 화면 글에 「비용」 말을 넣지 않는다(sid:MARC-ENT-334). CEO 쪽 한도는 6쪽 고정이라 한도 입력 칸 글이 없다(사용자 10-22 밤, e9 전달).
// 판 r1 에 없던 글 몇은 디자인 e9 의 답(감독 전달, 10-22 밤 — 다음 고침 묶음 판에 들어감)을 따른다: 쪽 범위 오류 넷·용어집 칸 안내·양식 실패 글.

const PART_NAMES = {
  ceo: 'CEO 메시지',
  story: '스토리',
  general: '일반',
} as const;

/** CEO 쪽 한도 글의 두 문장(쪽 범위 오류와 상태 카드가 같이 쓴다 — 카드는 까닭·안내를 나눠 보인다). */
const ceoLimitReason = (limit: number) =>
  `CEO 메시지는 최대 ${limit}페이지예요.`;
const CEO_LIMIT_GUIDE = 'CEO 메시지 파트를 맞게 골랐는지 확인해 주세요.';
/** 분량이 많아 막은 까닭(디자인 e9 — 크기·예산 한도 둘이 같은 글. 「비용」 말 없음, sid:MARC-ENT-334).
 *  목록 꼬리는 일반 실패와 같은 「실패」(밴드 TRW15, 마크스폰 11-11) — 까닭·안내는 결과 화면 실패 카드가 보인다. */
const TOO_LARGE = {
  reason: '분량이 많아 시작하지 않았어요.',
  guide: '페이지 범위를 줄여 새로 번역해 주세요.',
  tail: '실패',
} as const;
/** 쪽 없음·받지 않는 파일 꼴의 일반 실패(디자인 e9 10-23 — 같은 글). */
const NOT_STARTED = {
  reason: '이 파트를 시작하지 않았어요.',
  guide: '새 번역에서 페이지 범위와 파일을 확인해 주세요.',
  tail: '실패',
} as const;

/** 텍스트가 없는 PDF(입력 안내 줄과 실패 칸이 같이 쓴다 — 6c v174 TR-P02a, 검증 권고 R7). */
const NO_TEXT_PDF =
  '텍스트가 없는 PDF 예요(스캔본) · 텍스트 선택이 가능한 PDF 로 올려 주세요';
/** 차례 말(「셋째 문단」 — 6c v174 TR-P04·P05). 열을 넘으면 「11번째」. */
const ORDINALS = [
  '첫째',
  '둘째',
  '셋째',
  '넷째',
  '다섯째',
  '여섯째',
  '일곱째',
  '여덟째',
  '아홉째',
  '열째',
];
const ordinal = (n: number) => ORDINALS[n - 1] ?? `${n}번째`;

/** 견주기 A·B 값 사이(수치 칸·주석이 같이 쓴다). */
const PAIR_SEPARATOR = ' / ';
/** 용어집 행 거절 글 머리(「12행에 」 — 행을 모르면 빈 글). */
const inRow = (row: number | null) => (row === null ? '' : `${row}행에 `);

export const TR_TEXT = {
  /** 파트 이름(알약·글자 칸·범례·쪽 칸 이름). */
  parts: {
    names: PART_NAMES,
    /** 이름 묶음에 조사(그린워싱 fieldMeta 의 withAnd(joinNames) 꼴 — TRW0b): 「일반과」·「CEO 메시지와 일반과」. */
    withNames: (names: readonly string[]) => withAnd(joinNames(names)),
  },
  /** TR-02 「2. 파트별 쪽 범위」. */
  range: {
    /** 파트 고르기 묶음의 이름. */
    groupLabel: '칠할 파트',
    pageCount: (count: number) => `총 ${count}페이지`,
    activeHint: (name: string) =>
      `고른 파트: ${name} · 시작 페이지에서 끝 페이지까지 끌거나, 떨어진 페이지를 누르면 거기까지 늘어나요`,
    placeholder: { ceo: '예: 1~3', story: '예: 4~41', general: '예: 42~64' },
    /** 빈 글자 칸 아래. */
    empty: '비우면 옮기지 않아요',
    /** 겹친 파트의 칸 아래: 「35쪽 · 7~8쪽은 CEO 메시지와 겹침」. */
    overlapRow: (count: number, items: readonly string[]) =>
      `총 ${count}페이지 · ${items.join(' · ')}`,
    overlapWith: (pages: string, withName: string) =>
      `${pages}페이지는 ${withName} 겹침`,
    overlapNote:
      '겹친 페이지는 두 파트에서 한 번씩 옮기고, 검은 테두리와 두 색 점으로 보여요',
    /** 확정 판 v136 TR-02. */
    help: '페이지는 [PAGE n] 기준 · 파트마다 한 구간 · CEO 메시지는 최대 6페이지',
    /** TR-02a 오류 꼴에서만 help 아래에 더 보이는 줄(디자인 6c 대조 — 밴드 TRW5, sid:MARC-ISSUE-398 ①). */
    errorHelp: '「1-3」은 「1~3」으로, 페이지 하나는 「5」',
    noParts: '세 파트 가운데 하나 이상에 페이지를 넣어 주세요',
    /** 「번역할 쪽: 41쪽 / 64쪽 · 파트 2개라 번역을 2번 해요(CEO 메시지 · 스토리).」 */
    total: (pages: number, last: number, names: readonly string[]) =>
      `번역할 페이지 ${pages}개 / 총 ${last}페이지 · 파트 ${names.length}개라 번역을 ${names.length}번 해요(${names.join(' · ')}).`,
    /** 쪽 수를 모를 때(docx·txt — 감독 판단 1)의 합 줄: 「/ 마지막 쪽」을 뺀 꼴. */
    totalOpen: (pages: number, names: readonly string[]) =>
      `번역할 페이지 ${pages}개 · 파트 ${names.length}개라 번역을 ${names.length}번 해요(${names.join(' · ')}).`,
    /** 쪽 수를 모를 때 글자 칸 아래(디자인 e9 답, 223 노트 10-23 01:42 — 감독 판단 1). */
    pageBasis: '페이지 번호는 추출본의 [PAGE n] 기준이에요',
    /** 글자 칸 오류(TR-02a · e9 답). */
    errors: {
      comma: '한 파트에는 이어진 한 구간만 넣어 주세요',
      order: (from: number, to: number) =>
        `${from}~${to}페이지는 앞 페이지 번호가 뒤 페이지보다 커요`,
      zero: '페이지 번호는 1부터 넣어 주세요',
      notNumber: (token: string) =>
        `「${token}」는 읽을 수 없어요. 숫자와 ~ 로 넣어 주세요`,
      overLast: (page: number, last: number) =>
        `${page}페이지는 문서의 마지막 페이지(${last}페이지)를 넘어요`,
      overLastHelp:
        '페이지 범위를 고쳐 주세요. 페이지 번호는 추출본의 [PAGE n] 기준이에요.',
      /** CEO 쪽 한도(6쪽 고정)를 넘음 — e9 확정 판 예고 글(감독 전달 10-23). */
      ceoOverLimit: (limit: number) =>
        `${ceoLimitReason(limit)} ${CEO_LIMIT_GUIDE}`,
    },
  },
  /** 쪽 칸 그리드(자리 그림). */
  grid: {
    /** 칸 이름: 「3쪽, CEO 메시지」(칠하지 않은 쪽은 「3쪽」). */
    cellLabel: (page: number, names: readonly string[]) =>
      names.length === 0 ?
        `${page}페이지`
      : `${page}페이지, ${names.join(', ')}`,
    viewing: (from: number, to: number) => `${from}~${to}페이지를 보고 있어요`,
    /** 「41~64쪽에 스토리 41쪽이 칠해져 있어요」. */
    hiddenPainted: (from: number, to: number, items: readonly string[]) =>
      `${from}~${to}페이지에 ${items.join(' · ')}가 칠해져 있어요`,
    hiddenItem: (name: string, pages: string) => `${name} ${pages}페이지`,
    more: (from: number, to: number) => `더 보기 (${from}~${to}페이지)`,
    legendOverlap: '두 파트가 겹친 페이지',
    /** 디자인 e9 답(감독 판단 5 — TRW1a 가 바꿈). */
    note: '페이지를 누르면 칠하거나 지워요 · 한 구간만 고를 수 있어 가운데 페이지를 지우면 가까운 끝까지 같이 빠져요',
  },
  /** TR-02 「3. 용어집」. */
  glossary: {
    evaluation: {
      title: '평가용어집',
      optional: '선택',
      help: '평가에 맞춰 정리한 용어예요. 비우면 평가 용어집 없이 번역해요.',
    },
    client: {
      title: '고객사 용어집',
      help: '회사가 정한 공식 표현이에요. 같은 한국어 용어가 두 곳에 있으면 고객사 용어집을 따라요.',
      missing:
        '고객사 용어집을 올려 주세요. 고객사 용어집이 있어야 번역을 시작할 수 있어요',
    },
    pairs: (count: number) => `국문 → 영문 ${count}개`,
    replace: '바꾸기',
    template: '양식 내려받기',
    templateFailed: '양식을 받지 못했어요. 다시 시도해 주세요.',
    /** 빈 꼴 파일 칸의 안내. */
    guide: '「한국어 | 영문」 두 열 엑셀(.xlsx) · 파일마다 500줄까지',
    note: '두 용어집 모두 「한국어 | 영문」 두 열 엑셀(.xlsx) · 파일마다 500줄까지 · 빈 양식은 [양식 내려받기]',
  },
  /** TR-02 「시작 전 확인」. */
  preflight: {
    title: '시작 전 확인',
    lead: '넣은 값으로 셈해요',
    pages: '번역할 페이지',
    pagesValue: (total: number, items: readonly string[]) =>
      [`총 ${total}페이지`, ...items].join(' · '),
    pagesItem: (name: string, range: string, count: number) =>
      `${name} ${range}페이지(총 ${count}페이지)`,
    runs: '번역 횟수',
    runsValue: (runs: number, style: string) =>
      `${runs}번 · 파트마다 한 번 · 스타일 ${style}`,
    runsCompare: (runs: number, pages: number) =>
      `${runs}번(파트마다 한 번) · 번역마다 A · B 두 스타일로 옮겨 ${pages}페이지 분량`,
    runsNote:
      '번역 목록에는 이 파일 한 줄 아래 파트마다 생겨요 · 창을 닫아도 계속 옮겨요',
  },
  /** 파트 상태 글(밴드 TRW0b — 시안 TR-01·03·04·04a, 디자인 e9 확정 판 예고). */
  state: {
    /** 탭 옆 작은 상태 글(완료는 앞에 ✓ 아이콘). */
    tab: {
      done: '완료',
      running: '진행 중',
      queued: '대기',
      failed: '실패',
      failed_partial: '실패 · 일부 페이지',
    },
    /** 묶음 셈의 상태 이름(실패 둘은 「실패」 하나). */
    summary: {
      done: '완료',
      running: '진행 중',
      queued: '대기',
      failed: '실패',
    },
    /** 「완료 2」. */
    summaryItem: (label: string, n: number) => `${label} ${n}`,
    /** 진행 중 파트의 줄 글: 「진행 중 · 번역 20/38쪽」, 쪽 진행이 없으면 「진행 중 · 준비」. */
    runningPages: (done: number, total: number) =>
      `진행 중 · 번역 ${done}/${total}페이지`,
    runningPrepare: '진행 중 · 준비',
  },
  /** 준비 단계에서 막은 까닭(시안 TR-03 4번 표의 다섯 — 글은 디자인 e9: 까닭 둘 + 그 밖 일반 실패). 까닭·안내·목록 꼬리. */
  rejection: {
    no_pages: NOT_STARTED,
    bad_file: NOT_STARTED,
    too_large: TOO_LARGE,
    over_budget: TOO_LARGE,
    ceo_over_limit: NOT_STARTED,
  },
  /** 화면 제목(시안 TR-03 「화면 제목은 …」). */
  screenTitle: {
    running: '번역 중이에요',
    done: '번역이 끝났어요',
    needs_retry: '번역이 끝났어요 · 한 파트는 다시 해야 해요',
  },
  /** 파트 탭(시안 TR-03·04). */
  tabs: {
    all: '전체',
    /** [전체] 탭 옆: 「1 / 3 완료」. */
    allNote: (done: number, total: number) => `${done} / ${total} 완료`,
    /** 「3파트 중 1파트 완료 · 2파트 진행 중」. */
    remaining: (
      total: number,
      items: readonly { label: string; n: number }[],
    ) =>
      `${total}파트 중 ${items.map(({ label, n }) => `${n}파트 ${label}`).join(' · ')}`,
  },
  /** 진행 카드(시안 TR-03 1번 카드·줄인 꼴). 「비용」 말은 뺐다(디자인 e9 — sid:MARC-ENT-334). */
  stage: {
    title: '진행',
    step: (index: number, total: number) => `${index} / ${total}단계`,
    pages: (done: number, total: number) => `번역 ${done} / ${total}페이지`,
    /** 진행 막대 이름(시안 TR-03 aria-label). */
    progressLabel: '전체 단계 진행',
    names: {
      prepare: '준비',
      translate: '번역 · 검수 · 자동 수정',
      word: 'Word 만들기',
    },
    body: {
      prepare: '파일을 읽고 옮길 페이지와 분량을 확인했어요',
      translate:
        '파트 문체로 페이지마다 옮기고 다듬은 뒤, 용어집 반영 검사·번역 검수(QA)를 하고 이슈가 있는 페이지만 자동 수정해요 · A·B 비교면 문체마다 한 번씩 돌아요',
      translatePages: (done: number, total: number) =>
        `번역 ${done} / ${total}페이지 · 검수·자동 수정은 페이지 진행 없이 이어서 해요`,
      word: '병기 번역본 · 자동 수정 병기본 · 검수 결과 Word 를 만들어요(A·B 면 문체마다)',
    },
    states: { done: '완료', now: '진행 중', todo: '대기', failed: '실패' },
    /** 줄인 꼴 · 준비 단계. */
    prepareNow: '준비 중 · 파일을 읽고 옮길 페이지와 분량을 확인해요',
    /** PDF 흐름(latest.flowId)의 준비 단계 진행 중 — 큰 꼴·줄인 꼴 같이(밴드 TRW6 ④, 6c v174 TR-03 「PDF 읽기」 단계 설명. 단계 셈은 그대로 셋). */
    prepareNowPdf:
      'PDF 읽는 중 · 원본 PDF 에서 페이지마다 문단 · 표 · 그림 안 글의 자리를 읽어요',
    /** 줄인 꼴 · 대기(「서버가 둘까지…」 설명은 뺐다 — 디자인 e9). */
    queuedLabel: '대기',
    queued: (name: string, range: string) =>
      `${name} ${range}페이지는 차례를 기다리고 있어요 · 앞 파트가 끝나면 저절로 시작해요`,
    keepsRunning: '이 창을 닫아도 번역은 계속돼요',
    /** 진행 카드 머리(시안 TR-03 「스토리 4~41쪽(38쪽) · 스타일 B · 11:48 시작」 — 밴드 TRW1a ③). */
    meta: (title: string, style: string, started: string) =>
      `${title} · 스타일 ${style} · ${started} 시작`,
  },
  /** 실패 카드(시안 TR-03 3·4번, 결정 sid:MARC-ENT-393). */
  failure: {
    serverError:
      '이 파트를 끝내지 못했어요 · 번역·검수 단계에서 서버 오류로 멈췄어요.',
    partial: '이 파트를 끝내지 못했어요.',
    retryGuide:
      '[이 파트만 다시]를 누르면 같은 설정으로 이 파트만 처음부터 다시 옮겨요.',
    retryPart: '이 파트만 다시',
    retrySingle: '다시 실행',
    /** [이 파트만 다시]·[다시 실행]이 거절·끊김일 때(판에 없음 — 디자인 6c 확인, 밴드 TRW1b). */
    retryFailed: '다시 시작하지 못했어요. 다시 시도해 주세요.',
    back: '목록으로',
    /** PDF 파트의 실패 글(밴드 TRW6 W8, 6c v174 TR-P02a). 서버 문장은 보이지 않는다 — 갈래 둘 + 분량 넘침은 rejection.too_large. */
    pdf: {
      /** unsupported_input 전부(PDF 아님·암호·페이지 너무 많음·시간 초과). */
      unreadable:
        'PDF 를 읽지 못했어요. 텍스트 선택이 가능한 PDF 인지 확인하고 다시 올려 주세요',
      /** errorCode no_text_layer — 같은 PDF 면 다시 막혀 다시 하는 단추가 없다. */
      noText: NO_TEXT_PDF,
      /** PDF 파트의 [이 파트만 다시] 아래 회색 한 줄(W6). */
      retryNote: '같은 PDF · 같은 범위로 다시 해요',
    },
  },
  /** 수치 칸(시안 TR-04·04a). */
  stats: {
    labels: {
      translated: '번역한 페이지',
      untranslated: '번역하지 못한 페이지',
      glossaryMiss: '용어집 미반영',
      issues: '검수 이슈',
      fixed: '자동 수정한 페이지',
      /** PDF 묶음 [전체] 탭만(밴드 TRW7 ③a W10 — 판 v182 TR-P04). */
      checks: '확인할 곳',
    },
    units: { page: '개', count: '건', place: '곳' },
    /** 수치 없음(0 과 가름). */
    none: '–',
    /** A·B 견주기 칸 「12 / 9」의 사이와 칸 이름 끝(밴드 TRW2 · 6c 10-26). */
    pairSeparator: PAIR_SEPARATOR,
    pairLabel: (label: string) => `${label} · A / B`,
    notes: {
      outOf: (total: number) => `총 ${total}페이지 가운데`,
      outOfParts: (total: number, parts: number) =>
        `총 ${total}페이지 가운데 · 파트 ${parts}`,
      /** PDF 「번역한 페이지」 칸 아래(디자인 74 답, 판 TR-P04). 그림뿐인 쪽이 0 이거나 셀 수 없으면(null) 앞 마디만. */
      outOfImages: (total: number, images: number | null) =>
        images === null || images === 0 ?
          `총 ${total}페이지 가운데`
        : `총 ${total}페이지 가운데 · 그림뿐인 ${images}페이지 빼고`,
      allTranslated: '모든 페이지를 옮김',
      summed: '파트마다 그 파트의 페이지만 세어 더함',
      /** PDF 묶음 「확인할 곳」 칸 아래(판 TR-P04). 누르면 PDF 보기가 「확인할 곳」 거르기로 열린다. */
      checks: (pages: number) =>
        `페이지 ${pages}개 · 누르면 PDF 보기에서 확인할 곳만`,
      /** 한 스타일 「… 12개」, 견주기 「… 12개 / 11개」(밴드 TRW5 — 디자인 N3). */
      issuesBasis: (fixed: number | readonly [number, number]) =>
        `자동 수정 전 글 기준 · 자동 수정한 페이지 ${typeof fixed === 'number' ? `${fixed}개` : fixed.map((n) => `${n}개`).join(PAIR_SEPARATOR)}`,
      partGlossary: (name: string) =>
        `${name} 페이지 안에서 · AI 를 쓰지 않은 글자 대조`,
      fixedBasis: '이슈가 있던 페이지만 · 고친 뒤 다시 검수하지 않음',
      untranslatedCounted: (pages: number) =>
        `번역하지 못한 페이지 ${pages}개는 미반영으로 셈`,
      fixNotRun: '돌리지 않음 · 검수가 멈춤',
    },
  },
  /** [전체] 탭(시안 TR-04). */
  all: {
    title: '전체 요약',
    lead: '끝난 파트만 더해요',
    downloadLead: '자동 수정 병기본이 있는 끝난 파트만 받아요',
    /** 받을 자동 수정 병기본이 하나도 없어 [모두 받기]를 끈 때(확정 판 v136 TR-04). */
    noFiles:
      '받을 자동 수정 병기본이 없어요 · 파트 탭에서 병기 번역본을 받아요',
    downloadAll: '모두 받기',
    /** [모두 받기] 누른 뒤 묶음이 64MB 를 넘음(409 ARCHIVE_TOO_LARGE — 디자인 e9 10-23). */
    archiveTooLarge:
      '파일이 커서 한 번에 묶지 못했어요(64MB 넘음). 다시 해도 같아요 — 아래 표의 [Word]로 파트마다 받아 주세요',
    /** 받은 zip 에 빠진 파일(디자인 e9 10-23). */
    archiveMissing: (n: number) =>
      `${n}개 파일을 넣지 못했어요. 받은 zip 에 없는 파트는 아래 표의 [Word]로 받아 주세요`,
    tableTitle: '파트별',
    /** 파트별 표 줄 이름(줄을 누르면 그 파트 탭 — 밴드 TRP2 TC22, 지은 글: 그린워싱 rowLabel 꼴). */
    rowLabel: (part: string) => `${part} — 파트 탭 열기`,
    columns: {
      part: '파트 · 페이지',
      round: '회차',
      time: '시작 · 끝남',
      state: '상태',
      issues: '검수 이슈',
      glossaryMiss: '용어집 미반영',
      fixed: '자동 수정한 페이지',
      download: '내려받기',
    },
    /** A·B 견주기 표 머리 아랫줄(작은 회색 — 괄호 없이, 밴드 TRW5 · 디자인 N2. 옛 「검수 이슈 (A / B)」는 괄호 가운데서 꺾였다). */
    pairSub: 'A / B',
    word: 'Word',
    /** A·B 견주기 줄의 스타일마다 [Word](판 용어 「스타일 A/B」). */
    wordOf: (style: 'A' | 'B') => `Word ${style}`,
  },
  /** 표 칸의 값 꼴(목록·결과 같이). */
  cells: {
    partRange: (name: string, range: string) => `${name} · ${range}페이지`,
    round: (n: number) => `회차 ${n}`,
    time: (started: string, finished: string) => `${started} · ${finished}`,
    count: (n: number) => `${n}건`,
    pages: (n: number) => `${n}개`,
    times: (n: number) => `${n}회`,
  },
  /** 파트 결과 머리(시안 TR-04·04a). */
  result: {
    title: (name: string, range: string, count: number) =>
      `${name} ${range}페이지(총 ${count}페이지)`,
    meta: (style: string, glossaryCount: number, started: string) =>
      `스타일 ${style} · 고객사 용어집 ${glossaryCount}개 · ${started} 시작`,
    finished: (time: string) => `${time} 끝남`,
    files: {
      bilingual: '병기 번역본 Word',
      review: '검수 결과 Word',
      autofix: '자동 수정 병기본 Word',
    },
    /** 머리 [내려받기] 단추 · 받기 모달 머리(밴드 TRW14 ① — TR-04a r2, sid:MARC-ENT-662). */
    downloadsTitle: '내려받기',
    /** 받기 모달 파일 설명(늘 보임 — TR-04a r2. PDF 흐름도 같은 글). */
    fileNotes: {
      bilingual:
        '자동 수정 전 영문 번역본이에요 · 제목 첫 줄에 국문을 함께 적어요',
      review:
        '자동 수정 전 영문에 이슈 자리를 노랗게 칠하고, 끝에 이슈 표를 붙인 파일이에요',
      autofix:
        '이슈가 있던 페이지를 자동으로 고친 영문이에요 · 제목 첫 줄에 국문을 함께 적어요',
    },
    /** 없는 파일의 (?) 툴팁(한 줄). bilingual 은 앱에 조건 글이 없어 지은 글(감독 답 Q6 — c3). */
    fileMissing: {
      bilingual: 'Word 를 만들지 못했어요',
      review: '검수가 모든 페이지를 마쳤을 때만 있어요',
      autofix: '자동 수정이 끝났을 때만 있어요',
    },
    /** (?) 단추 이름 머리(「없는 까닭: <툴팁 글>」). */
    fileMissingLabel: '없는 까닭',
    /** 받기 줄이 받는 동안 도는 표시의 이름. */
    downloading: '받는 중',
    close: '닫기',
    wordNote: 'Word 는 원본 레이아웃이 아니라 번역 원고예요.',
    /** Word·[모두 받기] 내려받기 실패(디자인 e9 확정 10-23 — AD-04a 결과 파일 실패 글과 같음, sid:MARC-ISSUE-296). */
    downloadFailed: '파일을 받지 못했어요. 다시 시도해 주세요.',
    stepsLabel: '단계',
    /** 단계 줄(시안 TR-04a — 실패 · 일부 쪽일 때, 밴드 TRW1a ③). */
    steps: {
      translate: '번역',
      glossary: '용어집 반영 검사',
      review: '번역 검수',
      autofix: '자동 수정',
      word: 'Word 만들기',
    },
    stepValues: {
      done: '완료',
      failedPages: (n: number) => `실패한 페이지 ${n}개`,
      stoppedAt: (page: number) => `${page}페이지에서 멈춤`,
      notRun: '돌리지 않음',
      bilingualOnly: '병기 번역본만',
    },
    /** 안내 줄(시안 TR-04a). 검수 멈춤은 AI 호출 실패(call_failed)일 때의 글. */
    notices: {
      reviewStopped: (page: number, end: number) =>
        `번역 검수가 ${page}페이지에서 멈췄어요 · AI 호출이 실패했어요. ${page - 1}페이지까지 찾은 이슈는 아래에 있고, ${page}~${end}페이지는 검수하지 않았어요. 검수가 멈춰 검수 결과 Word 를 만들지 않았어요. 자동 수정을 돌리지 않아 병기 번역본은 자동 수정 전 글이에요.`,
      untranslated: (pages: readonly number[]) =>
        `번역하지 못한 페이지가 ${pages.length}개 있어요(${pages.join(' · ')}페이지). 번역본에는 그 페이지가 원문 그대로 「번역 오류」 표시와 함께 남아요.`,
    },
    /** 확인할 쪽 표의 값(시안 TR-04a). */
    check: {
      failed: '실패',
      done: '완료',
      reviewed: '검수함',
      notRun: '돌리지 않음',
      stoppedAt: (page: number) => `${page}페이지에서 멈춤`,
      callFailed:
        'AI 호출이 실패했어요. 번역본에는 원문이 남고, 검수는 그 글로 했어요',
      koreanLeft: '옮긴 글에 국문이 남아 번역하지 못한 페이지로 쳤어요',
      notReviewedAfter: (page: number) =>
        `검수가 ${page}페이지에서 멈춰 이 페이지는 검수하지 않았어요`,
      reviewCallFailed: '검수 AI 호출이 실패했어요',
      earlierStopped: '앞 페이지에서 검수가 멈췄어요',
    },
    /** 번역하지 못한 쪽 칸 아래(시안 TR-04a 「27 · 33쪽」). */
    failedPagesNote: (pages: readonly number[]) => `${pages.join(' · ')}페이지`,
  },
  /** 번역 검수 이슈 표(시안 TR-04). */
  issues: {
    title: '번역 검수(QA) 이슈',
    basis: '자동 수정 전 글 기준',
    /** 검수가 멈췄을 때 기준 글(시안 TR-04a 「4~29쪽 · 7건 · 자동 수정 전 글 기준」 — 밴드 TRP2 TC26). */
    basisStopped: (from: number, to: number, n: number) =>
      `${from}~${to}페이지 · ${n}건 · 자동 수정 전 글 기준`,
    typeFilter: '유형',
    allTypes: '전체',
    severityLabel: '심각도',
    allSeverities: '전체',
    columns: {
      page: '페이지',
      type: '유형',
      severity: '심각도',
      span: '고칠 부분',
      suggestion: '제안',
      reason: '까닭',
    },
    empty: '검수에서 찾은 이슈가 없어요',
    types: {
      glossary_violation: '용어집 위반',
      term_inconsistency: '용어 불일치',
      structure_changed: '구조 표시 바뀜',
      omission: '누락',
      untranslated: '번역 안 됨',
      number_unit: '숫자·단위 오류',
      grammar: '문법',
      unnatural: '부자연스러움',
      table_content: '표 내용',
      figure_caption: '그림 설명',
    },
  },
  /** 용어집 미반영 표(시안 TR-04). */
  glossaryMiss: {
    title: '용어집 미반영',
    basis:
      '자동 수정 전 글 기준 · 고른 파트의 페이지만 · AI 를 쓰지 않고 글자로 맞춰 본 결과',
    columns: {
      page: '페이지',
      ko: '원문 용어',
      en: '지정한 영문',
      count: '원문 등장',
    },
    note: '영어 대소문자와 띄어쓰기 차이는 반영으로 봐요.',
    empty: '원문에 나온 용어집 용어를 모두 지켰어요',
  },
  /** 확인할 쪽 표(시안 TR-04a). */
  pagesToCheck: {
    title: '확인할 페이지',
    basis: '번역 · 검수가 끝나지 않은 페이지만',
    columns: {
      pages: '페이지',
      translate: '번역',
      review: '번역 검수',
      reason: '까닭',
    },
  },
  /**
   * 틀(AppShell) 글(밴드 TRW1a ② — 그린워싱 GW_TEXT.shell 을 옮겨 적음, 가져오지 않는다. 공통화는 후속 「app 셸 공통」).
   * 머리 제목은 확정 판 v136 TR-01·02 「영문번역」.
   */
  shell: {
    menuLabel: '모듈 메뉴',
    logo: '로고 자리',
    title: '영문번역',
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
  /** 새 번역(시안 TR-02·02a 확정 판 v136, 밴드 TRW1a ②). */
  newTranslation: {
    title: '새 번역',
    description:
      '국문 추출본과 파트별 페이지 범위를 넣으면 파트마다 그 파트의 문체로 영어로 옮기고 검수해요.',
    /** 단계 띠(시안 STEP 1~3). 목록 이름은 판에 없어 화면 제목과 같은 글. */
    steps: ['파일·용어집', '번역·검수', '결과'],
    stepPrefix: 'STEP',
    stepsLabel: '새 번역',
    upload: {
      heading: '1. 파일 올리기',
      guide: '국문 추출본 파일(Word · 텍스트)을 끌어 놓거나 눌러서 골라 주세요',
      note: '페이지마다 [PAGE n] 표시가 있는 추출본(docx · txt)만 받아요 · 원본 PDF 는 목록의 [PDF로 새 번역]에서 올려요 · 같은 파일을 다시 옮길 때도 다시 올려요(번역 목록에 새 줄로 생기고 앞 줄은 남아요)',
      /** 파일 줄 meta: 쪽 수를 알면 「64쪽 · 1.2MB」, 모르면 크기만(날짜는 드롭존이 붙인다). */
      meta: (pageCount: number | null, size: string) =>
        pageCount === null ? size : `총 ${pageCount}페이지 · ${size}`,
      uploading: '올리는 중',
      failed: '올리지 못함',
      failedHelp: '파일을 올리지 못했어요. 다시 골라 주세요',
      /** 받지 않는 꼴(드롭존 거부 줄 「<이름> · …」). */
      rejected:
        '받지 않는 꼴 · Word(docx)·텍스트(txt) 추출본만 받아요. 원본 PDF 는 목록의 [PDF로 새 번역]에서 올려 주세요',
    },
    rangeHeading: '2. 파트별 페이지 범위',
    glossaryHeading: '3. 용어집',
    /** 용어집 거절 글(TR-02a 표, 밴드 TRW11 — 거절 종류마다 하나). 서버 message 는 버리고 kind·row 로 짓는다. 서버
     * (tools/glossary_xlsx.py)는 행 거절에 칸 이름·앞 행을 글로만 주므로 행 번호까지만 싣는다. */
    glossaryRejected: {
      too_large: '파일이 너무 커요. 1MB 이하로 올려 주세요',
      unsafe_xlsx:
        '이 엑셀 파일은 열 수 없어요. [양식 내려받기]로 받은 양식에 새로 채워 올려 주세요',
      bad_header: '1행 머리가 양식과 달라요',
      empty_cell: (row: number | null) =>
        `${inRow(row)}빈 칸이 있어요. 한국어 · 영문을 둘 다 채워 주세요`,
      not_text: (row: number | null) =>
        `${inRow(row)}글자가 아닌 칸이 있어요. 셀 서식을 텍스트로 바꿔 주세요`,
      too_long: (row: number | null) =>
        `${inRow(row)}너무 긴 용어가 있어요. 한국어는 30자, 영문은 100자까지예요`,
      duplicate_ko: (row: number | null) =>
        `${inRow(row)}앞 행과 같은 한국어가 있어요. 한 번만 적어 주세요`,
      too_many_rows: '용어가 500줄을 넘어요. 500줄까지 줄여 다시 올려 주세요',
      /** 서버가 훑는 행(10,000)을 넘음 — 이때 row 는 null(빈 행이 많은 파일). */
      too_many_scanned_rows:
        '빈 행이 너무 많아요. 용어 아래 빈 행을 지우고 다시 올려 주세요',
      no_rows: '용어가 없어요. 2행부터 한국어 · 영문을 채워 올려 주세요',
      notXlsx:
        '한국어 · 영문 두 열의 엑셀(xlsx)만 받아요. [양식 내려받기]로 받은 양식에 옮겨 적어 주세요',
    },
    /** 옵션 바이트 상한을 넘음(TR-02a — [번역 시작]을 누를 때 잼). */
    tooLong:
      '용어집과 회사 정보·참고 문체를 합친 설정이 한 번에 보낼 수 있는 길이를 넘었어요. 용어집 줄이나 참고 문체 글을 줄여 주세요',
    company: {
      heading: '4. 회사 정보와 문체',
      name: '회사 영문명',
      nameMissing: '회사 영문명을 적어 주세요',
      subject: '사업 분야',
      subjectExample:
        'construction services, infrastructure development, housing, occupational health and safety, climate risk management',
      subjectHelp: '영어로 적어요 · 번역할 때 업계 용어를 고르는 데 써요',
      standards: '따르는 공시 기준',
      standardsExample:
        'GRI Standards 2021, ISSB (IFRS S1 and IFRS S2), TCFD, SASB, UN SDGs',
    },
    style: {
      label: '번역 스타일',
      A: 'A 표준 — 뜻을 정확히, 보고서에 맞는 안정적인 영어',
      B: 'B 원어민 윤문 — 미국 원어민 번역가가 다듬은 듯한 자연스러운 영어',
      AB: 'A · B 견주기 — 두 스타일로 옮겨 보고 하나를 고를 때',
      compareNote: '샘플 몇 페이지로 견주고, 정식 번역은 하나로 해 보세요.',
    },
    peer: {
      label: '참고 문체',
      toggle: '같은 업계 보고서의 문체를 반영',
      fillExample: '예시 양식 넣기',
      example: [
        '1. 따를 차례: 회사의 지난 영문 보고서 → 용어집 → 같은 업계 보고서',
        '2. 참고할 보고서: [같은 업계 회사 보고서 이름]',
        '3. 가져올 것: 공시 어조, 중대성 평가·리스크 관리 표현, 성과 관리 표현',
        '4. 가져오지 않을 것: 다른 회사의 사실·수치·프로그램 이름·수상 내역',
      ].join('\n'),
      help: '용어집이 이 글보다 먼저예요',
    },
    cancel: '취소',
    start: '번역 시작',
    /** 틀린 칸이 있어 [번역 시작]을 끈 때(TR-02a). */
    blocked: (n: number) => `틀린 칸 ${n}곳 · 고치면 번역을 시작할 수 있어요`,
    /** 하나도 시작하지 못함(감독 판단 4 ⓑ — 디자인 e9 답). */
    startFailed: '번역을 시작하지 못했어요. 다시 시도해 주세요.',
  },
  /** PDF 새 번역(밴드 TRW6 ②, 6c v174 TR-P02·P02a). 여기 없는 칸(용어집·회사 정보·단추·오류)은 newTranslation·range 글을 같이 쓴다. */
  pdfNew: {
    title: 'PDF로 새 번역',
    description:
      '원본 PDF 와 파트별 페이지 범위를 넣으면 파트마다 그 파트의 문체로 영어로 옮기고 검수해요.',
    upload: {
      guide: '원본 PDF 를 끌어 놓거나 눌러서 골라 주세요',
      formats:
        '텍스트 선택이 가능한 PDF 여야 해요 · 스캔한 그림뿐인 페이지는 번역하지 못해요 · 암호가 걸린 PDF 는 받지 않아요 · .pdf 한 개',
      note: '같은 파일을 다시 옮길 때도 다시 올려요(번역 목록에 새 줄로 생기고 앞 줄은 남아요)',
      /** 드롭존 거부 줄(판에 없음 — P02a 「추출본(Word · 텍스트)은 기존 [새 번역]에서 옮겨요」를 이음, 6c 대조에 넘김). */
      rejected:
        '받지 않는 꼴 · .pdf 만 받아요. 추출본(Word · 텍스트)은 기존 [Word로 새 번역]에서 옮겨요',
      /** confirm 답 hasText false(시작은 막지 않는다 — W4). 글은 P02a 「텍스트가 없는 PDF 일 때」. */
      noText: NO_TEXT_PDF,
    },
    range: {
      /** 범위 카드 머리 안내 둘(입력 전에 보임 — 분량은 안내 줄 + 거절 글만, 사용자 10-28). */
      limit:
        '한 번에 옮길 수 있는 분량에 한도가 있어요 · 두꺼운 보고서는 파트마다 필요한 페이지만 골라 주세요',
      basis:
        '페이지 번호는 PDF 뷰어에서 보이는 순서예요(보고서에 인쇄된 페이지 번호와 다를 수 있어요)',
      /** 글자 칸 아래(워드 help 의 「[PAGE n] 기준」을 뺀 꼴). */
      help: '파트마다 한 구간 · CEO 메시지는 최대 6페이지',
      overLastHelp:
        '페이지 범위를 고쳐 주세요. 페이지 번호는 PDF 뷰어에서 보이는 순서예요.',
    },
    preflight: {
      headerFooter: '머리글 · 꼬리말',
      headerFooterValue: '머리글 · 꼬리말은 번역하지 않고 원문 그대로 보여요',
    },
    /** [번역 시작] 위 회색 줄. */
    retryNote:
      '결과에서 「실패한 페이지만 다시」는 같은 PDF · 같은 페이지 범위일 때만 돼요 · 범위를 바꾸면 새 번역으로 옮겨요',
  },
  /** PDF 보기(밴드 TRW6 ③, 6c v174 TR-P04·P05·P05a). 상자 종류·경고 여섯·짝 칸. */
  pdfView: {
    open: 'PDF로 보기',
    back: '결과 요약',
    lead: '원본 페이지 위 상자를 누르면 원문과 번역을 맞대어 봐요',
    filters: {
      all: (n: number) => `페이지 전체 ${n}`,
      checks: (n: number) => `확인할 곳 ${n}`,
    },
    pageLine: {
      places: (page: number, n: number) => `${page}페이지 번역 ${n}곳`,
      imageOnly: (page: number) => `${page}페이지 그림뿐인 페이지 · 번역 0곳`,
      /** 두 줄 꼴(밴드 TRW7 ①, 6c v182 TR-P05 .tp-pg): 첫 줄 「12페이지」 · 둘째 줄 「번역 8곳 · 이슈 3 · 확인할 곳 1」. 이어 읽으면 위 places·imageOnly 와 같다. */
      title: (page: number) => `${page}페이지`,
      placesOnly: (n: number) => `번역 ${n}곳`,
      imageOnlyOnly: '그림뿐인 페이지 · 번역 0곳',
      checks: (n: number) => `확인할 곳 ${n}`,
      issues: (n: number) => `이슈 ${n}`,
    },
    only: (style: string) => `스타일 ${style} 에서만`,
    /** 쪽 목록 묶음 머리(밴드 TRW7 ① W8, 판 .tp-grp): 「스토리 · 4~41페이지」. */
    group: (part: string, first: number, last: number) =>
      first === last ?
        `${part} · ${first}페이지`
      : `${part} · ${first}~${last}페이지`,
    /** 쪽 칸 머리(판 「12페이지 [스토리]」). */
    pageTitle: (page: number) => `${page}페이지`,
    /** 상자 범례(판 .tp-legend — 그 쪽에 있는 종류와 상관없이 늘 전부). */
    legend: {
      label: '상자 범례',
      block: '문단',
      group: '여러 문단',
      cell: '표 · 칸',
      table: '표 전체',
      visual: '그림 안 글',
      sourceOnly: '머리글 · 꼬리말',
      missing: '번역 안 됨',
      check: '확인할 곳',
      issueSample: '2',
      issue: '이슈',
    },
    /** 짝 칸 이슈·용어 줄(밴드 TRW7 ① W2, 판 .tp-il). */
    issueLine: {
      fixed: '자동 수정에서 고쳤어요',
      span: '고칠 부분',
      suggestion: '제안',
    },
    termLine: {
      pair: (ko: string, en: string) => `${ko} → ${en}`,
      note: '번역에 지정한 영문이 없어요',
    },
    /** 표 짝 머리(판 「2행 1열」·「칸 12개」 — 표 이름은 layout 에 없어 뺌). */
    cellAt: (row: number, col: number) => `${row}행 ${col}열`,
    cellCount: (n: number) => `칸 ${n}개`,
    pageOf: (page: number, total: number) => `${page} / ${total}`,
    prev: '이전 페이지',
    next: '다음 페이지',
    stage: {
      autofix: '자동 수정을 마친 글이에요',
      translated: '자동 수정 전 번역 그대로예요',
    },
    styleOf: (style: string) => `스타일 ${style}`,
    pair: {
      source: '원문',
      translation: '번역',
      none: '이 자리의 번역을 찾지 못했어요',
      /** 아무 상자도 고르지 않았을 때 항목 칸 머리: 「12페이지 항목 6개」(밴드 TRW8 ③ — 화면 글은 「항목」, 코드 이름은 pair 그대로). */
      listTitle: (page: number, n: number) => `${page}페이지 항목 ${n}개`,
      /** 고른 항목 머리 줄 ‹ 「3 / 8」 ›(쪽은 왼쪽 쪽 머리에 있음). */
      position: (n: number, total: number) => `${n} / ${total}`,
      unselect: '목록으로',
      /** 아이콘 단추 이름. */
      prev: '이전 항목',
      next: '다음 항목',
      /** 목록 꼴 line 탭 둘(밴드 TRW8 ⑥): 「항목 8」·「검수 이슈 3」(이슈 + 용어집 미반영 — 쪽 위 「이슈 N」 합과 같음). */
      tabs: {
        items: (n: number) => `항목 ${n}`,
        issues: (n: number) => `검수 이슈 ${n}`,
      },
      noIssues: '이 페이지에는 검수 이슈가 없어요',
      /** 검수 이슈 탭 묶음 머리: 「항목 3」. */
      itemOf: (n: number) => `항목 ${n}`,
      /** 검수 이슈 탭 맨 아래 항목에 못 붙은 묶음 머리. */
      pageWhole: '페이지 전체',
      /** 상세 「번역」 머리 줄 오른쪽 전환(밴드 TRW8 ④ 개정 — sid:MARC-ENT-502): 「A」·「B」·「둘 다」. */
      styles: {
        label: '번역 스타일',
        one: (style: string) => style,
        both: '둘 다',
      },
      /** 「둘 다」 번역 칸 머리: 「번역 A」. */
      translationOf: (style: string) => `번역 ${style}`,
      /** 상세 「번역 복사」 아이콘 단추(밴드 TRW14 ③ — TR-P05 c3 스펙): 툴팁·이름, 「둘 다」 문체 칸 이름, 누른 뒤 글(약 2초). */
      copy: {
        label: '번역 복사',
        labelOf: (style: string) => `번역 ${style} 복사`,
        done: '번역을 복사했어요',
        failed: '복사하지 못했어요',
      },
      /** 「둘 다」 이슈 묶음 머리: 「스타일 A 이슈 2」(이슈 + 용어집 미반영). */
      issuesOf: (style: string, n: number) => `스타일 ${style} 이슈 ${n}`,
      /** 「둘 다」에서 다른 스타일 쪽에 같은 단위 항목이 없을 때. */
      noSame: '이 스타일에는 같은 항목이 없어요',
      group: '문단을 하나씩 맞추지 못해 묶어서 보여요',
      tableWhole: '칸을 하나씩 맞추지 못해 표 전체로 보여요',
      sourceOnly: '머리글 · 꼬리말은 번역하지 않아요',
      visual:
        '그림 속 글자는 글자로 된 것만 옮겨요 · 그림으로 그려진 글은 읽지 않아요',
    },
    kinds: {
      block: '문단',
      group: '여러 문단',
      table: '표 전체',
      cell: '표 칸',
      visual: '그림 안 글',
      source_only: '머리글 · 꼬리말',
      missing: '번역 안 됨',
    },
    /** 상자 이름(누름 손잡이 aria-label): 「12페이지 셋째 문단」. */
    boxLabel: (page: number, n: number, kind: string) =>
      `${page}페이지 ${ordinal(n)} ${kind}`,
    imageOnly: '이 페이지는 그림뿐이라 번역하지 않았어요',
    unplaced: (n: number) => `자리를 찾지 못한 번역 ${n}개`,
    warnings: {
      tag_missing: '이 페이지에서 번역 한 곳이 빠졌어요',
      tag_extra: '원문에 없는 번역 글이 더 있어요',
      tag_shift:
        '뒤쪽 번역의 자리가 어긋났을 수 있어요 — 엉뚱한 글에 붙었을 수 있으니 원문과 맞대어 봐 주세요',
      page_missing: '이 페이지 번역이 통째로 없어요',
      length_ratio:
        '번역 길이가 원문과 많이 달라요 — 빠지거나 덧붙은 데가 있는지 봐 주세요',
      image_only_page: '그림뿐인 페이지예요',
    },
    /** 경고가 붙은 자리: 「14페이지 · 셋째 문단」·「17페이지」. */
    warningAt: (page: number, n: number | null) =>
      n === null ? `${page}페이지` : `${page}페이지 · ${ordinal(n)} 문단`,
    /** 상자 오른쪽 아래 「이슈 N」(검수 이슈 + 용어집 미반영 수). */
    badge: (n: number) => `이슈 ${n}`,
    /** 문단을 찾지 못한 이슈(페이지에 붙음). */
    pageIssuesTitle: (n: number) => `이 페이지 전체의 검수 이슈 ${n}건`,
    pageIssuesNote: '어느 문단의 글인지 찾지 못해 페이지 전체에 붙였어요',
    pageMissesTitle: (n: number) => `이 페이지 전체의 용어집 미반영 ${n}건`,
    /** layout 409 — 판에 없음(6c 대조에 넘김). */
    notDone: '아직 번역 중이에요 · 끝나면 PDF 로 볼 수 있어요',
    loadFailed: 'PDF 보기를 불러오지 못했어요',
    issuesTitle: (n: number) =>
      `이 문단의 검수 이슈 ${n}건 · 자동 수정 전 글 기준`,
    missesTitle: (n: number) => `이 문단의 용어집 미반영 ${n}건`,
    pdfFailed: '원본 PDF 를 불러오지 못했어요',
    retry: '다시 시도',
    /** layout 404 — 판에 없음(6c 대조에 넘김). */
    notFound: '이 파트는 PDF 보기를 만들지 않았어요',
    /** 검수 이슈 표에서 들어왔을 때 띠: 「검수 이슈 표에서 왔어요 · 12페이지 둘째 문단 · 숫자·단위 오류」. */
    fromTable: (where: string, type: string) =>
      `검수 이슈 표에서 왔어요 · ${where} · ${type}`,
    /** 표 「자리」 칸. */
    place: '자리',
    placeUnit: (page: number, n: number) => `${page}페이지 ${ordinal(n)} 문단`,
    placeWhole: (page: number) => `${page}페이지 전체`,
  },
  /** 일부 파트만 시작한 묶음 화면 띠(감독 판단 4 ⓐ — 디자인 e9 답). 이름이 여럿이면 「·」로 잇고(v142), 조사는 마지막 이름의 받침으로. */
  partialStart: (started: readonly string[], failed: readonly string[]) =>
    `${withTopic(started.join('·'))} 시작했고, ${withTopic(failed.join('·'))} 시작하지 못했어요. 페이지 범위를 확인해 새로 번역해 주세요.`,
  /** 번역 목록(시안 TR-01·01a, 결정 sid:MARC-ENT-404 — 한 줄 = [번역 시작] 한 번 = 묶음). */
  list: {
    columns: {
      file: '파일명',
      part: '파트 · 페이지',
      style: '스타일',
      uploader: '담당자',
      started: '마지막 시작',
      state: '상태',
      next: '다음 할 일',
    },
    uploaded: (time: string) => `${time} 올림`,
    /** 원본 PDF 로 시작한 줄(묶음 inputKind pdf)의 파일명 앞 회색 배지(6c v174 TR-01, 밴드 TRW6 ④). */
    pdfMark: 'PDF',
    /** 검색 칸 이름·자리표시(시안 TR-01 — 밴드 TRP2 TE2). */
    searchLabel: '파일명 검색',
    /** 표 아래 안내 상자(시안 TR-01 e-info — 밴드 TRP2 TE4). */
    guide:
      '[번역 시작] 한 번이 한 줄이에요 · 같은 파일을 다시 번역하면 새 줄 · 펼치면 파트마다 상태와 [결과 보기]·[진행 보기]',
    /** 묶음 줄 꺾쇠 단추 이름(시안 TR-01 aria-label — 밴드 TRP2 TE3). */
    expandParts: '파트 펼치기',
    collapseParts: '파트 접기',
    partCount: (n: number) => `파트 ${n}`,
    viewResult: '결과 보기',
    viewProgress: '진행 보기',
    /** 누를 수 있는 목록 줄 이름(결정 sid:MARC-ENT-599 규칙 4, 밴드 TRW12) — 「파일명 · (파트 ·) 보기 단추 글」. */
    rowLabel: (file: string, view: string, part?: string) =>
      part === undefined ? `${file} · ${view}` : `${file} · ${part} · ${view}`,
    /** 머리 오른쪽 링크(시안 v149 TR-01_r1 .g-small — 밴드 TRP3, sid:MARC-ENT-435). */
    introLink: '번역 안내',
    /** 화면 머리(밴드 TRW1a ③ — 시안 TR-01·01a). 회사는 서버 목록 응답 companyName(TRC1, sid:MARC-ISSUE-360).
     *  설명 줄은 운영 관리자의 작업 회사만(sid:MARC-ENT-409) — 일반 사용자의 「회사 · 번역 n건 · …」 줄과 셈·안내 조각은
     *  지웠다(그린워싱 metaOperator 와 같은 꼴, 밴드 WT1 · sid:MARC-ENT-625 · 시안 v233). 회사 이름이 비면 화면이 줄을 뺀다. */
    title: '번역 목록',
    metaOperator: (company: string) => `작업 회사 ${company}`,
    tabsLabel: '상태',
    tabs: {
      all: '전체',
      active: '대기·진행 중',
      done: '완료',
      failed: '실패',
    },
    /** 스타일 칸(A·B, 견주기는 「A · B」 — 시안 TR-02 「A · B 견주기」의 앞 글). */
    styles: { A: 'A', B: 'B', AB: 'A · B' },
    mineOnly: '내가 올린 것만',
    /** 머리·빈 목록 단추(밴드 TRW14 ② — TR-01 c3 스펙, 글만). */
    newTranslation: 'Word로 새 번역',
    /** [Word로 새 번역] 옆(밴드 TRW6 ②, 6c v174 TR-01). */
    newPdf: 'PDF로 새 번역',
    empty:
      '아직 번역한 파일이 없어요. 국문 추출본(Word · 텍스트)과 용어집을 올려 시작해요.',
    emptyFiltered: '조건에 맞는 번역이 없어요',
    clearFilter: '거르기 풀기',
    loadFailed: '번역 목록을 불러오지 못했어요',
    retry: '다시 시도',
  },
  /** 묶음 화면 머리(밴드 TRW1a ③ — 시안 TR-03·04). */
  run: {
    /** 「<파일> · <시각> 올림 · 파트 3」(문서 쪽 수는 모르는 때가 있어 뺐다 — docx·txt). */
    meta: (fileName: string, uploaded: string | null, parts: number) =>
      [
        fileName,
        ...(uploaded === null ? [] : [`${uploaded} 올림`]),
        `파트 ${parts}`,
      ].join(' · '),
    back: '목록으로',
    tabsLabel: '파트',
    styleTabsLabel: '스타일',
    styleTab: (label: string) => `스타일 ${label}`,
    /** 없음(404 — 디자인 6c 답 CM-03 꼴, TRP1 W6): 두 문장, 다시 시도 없음. */
    missing: '번역을 찾을 수 없어요. 목록에서 다시 골라 주세요',
    loadFailed: '번역을 불러오지 못했어요',
    resultFailed: '결과를 불러오지 못했어요',
    /** [모두 받기]를 받는 동안(시안 TR-04 「받는 중…」). */
    downloading: '받는 중…',
  },
  /** TR-00 번역 안내(밴드 TRP3, 시안 v149 TR-00_r1 그대로 — sid:MARC-ENT-435). */
  intro: {
    title: '영문번역',
    heading: '영문번역이란',
    lead: [
      '국문 지속가능경영보고서를 영어로 옮겨요. 올린 용어집의 용어는 반드시 지정한 영문으로 옮기고, CEO 메시지 · 스토리 · 일반 가운데 페이지를 넣은 파트마다 그 파트의 문체로 써요. 파트마다 따로 옮기고, 결과는 파일 하나 아래 파트별로 모여요.',
      '번역이 끝나면 용어집이 지켜졌는지 글자로 맞춰 보고, 번역 검수(QA)로 누락 · 숫자 · 문법 같은 이슈를 찾은 뒤 이슈가 있는 페이지를 자동으로 고쳐요.',
    ],
    hint: '시작하기 버튼을 눌러 번역을 시작해 보세요.',
    flowTitle: '번역 과정',
    flow: [
      {
        step: 'Step 1',
        title: '파일·용어집',
        body: '추출본과 용어집을 올리고 파트별 페이지 범위와 회사 정보를 넣어요',
      },
      {
        step: 'Step 2',
        title: '번역·검수',
        body: '페이지마다 옮기고 다듬은 뒤 용어집 반영 검사 · 번역 검수(QA) · 자동 수정을 해요',
      },
      {
        step: 'Step 3',
        title: '결과',
        body: '파트마다 검수 이슈와 용어집 미반영을 확인하고 Word 를 내려받아요',
      },
    ],
    give: {
      title: '올리는 것',
      head: ['항목', '설명', '넣기'],
      rows: [
        [
          '국문 추출본',
          '보고서의 글과 표를 페이지마다 [PAGE n] 표시와 함께 옮겨 둔 docx 나 txt 파일이에요',
          '필수',
        ],
        [
          '용어집',
          '고객사 용어집과 평가용어집이에요. 둘 다 국문 · 영문 두 열의 엑셀이고, 양식은 새 번역 화면에서 내려받아요',
          '평가용어집만 선택',
        ],
        [
          '파트별 페이지 범위',
          'CEO 메시지 · 스토리 · 일반마다 페이지 칸(페이지 번호만 있는 자리 그림)을 끌어 칠하거나 몇 페이지부터 몇 페이지까지인지 적어요. 파트마다 이어진 한 구간이에요. 비운 파트는 옮기지 않고, [번역 시작]을 한 번 누르면 페이지를 넣은 파트마다 따로 옮겨요',
          '한 파트 이상',
        ],
        [
          '회사 정보',
          '회사 영문명 · 사업 분야 · 따르는 공시 기준을 영어로 적어요. 업계 용어를 고르는 데 써요',
          '공시 기준만 선택',
        ],
        [
          '번역 스타일',
          'A 표준 · B 원어민 윤문 가운데 고르거나 둘을 견줘요. 「같은 업계 보고서의 문체를 반영」을 켜면 그 문체를 참고해 옮겨요',
          '문체 반영만 선택',
        ],
      ],
    },
    get: {
      title: '받는 것',
      head: ['결과', '설명'],
      rows: [
        [
          '병기 번역본 Word',
          '자동 수정 전 영문이에요. 페이지 표시를 지키고, 제목 첫 줄에만 국문을 함께 적어요. 파트마다 하나씩, A · B 견주기로 돌리면 스타일마다 하나씩이에요',
        ],
        [
          '자동 수정 병기본 Word',
          '이슈가 있던 페이지를 자동으로 고친 영문이에요. 꼴은 병기 번역본과 같아요',
        ],
        [
          '검수 결과 Word',
          '자동 수정 전 영문에서 이슈 자리를 노랗게 칠하고, 끝에 이슈 표(페이지 · 유형 · 심각도 · 제안)를 붙여요',
        ],
        [
          '화면의 결과',
          '파트마다 번역한 페이지 · 번역하지 못한 페이지 · 용어집 미반영 · 자동 수정한 페이지를 한눈에 보고 검수 이슈를 페이지별로 살펴요',
        ],
      ],
    },
    /** 6c v174 TR-00(밴드 TRW6 ④ — 앞 판 「원본 PDF 와 그림 속 글자는 아직 옮기지 않아요」를 갈음). */
    info: '추출본(Word · 텍스트)의 글과 표를 옮겨요. 원본 PDF 로도 번역할 수 있어요 — 페이지 위에서 원문과 번역을 맞대어 봐요. 그림으로 그려진 글자는 옮기지 않아요.',
    start: '시작하기',
  },
} as const;

/** 이름 늘어놓기(그린워싱 config/text.ts joinNames 와 같은 뜻 — 가져오지 않고 옮겨 적음): 「A」·「A와 B」·「A, B와 C」. */
function joinNames(names: readonly string[]): string {
  if (names.length <= 1) return names.join('');
  const head = names.slice(0, -1).join(', ');
  return `${withAnd(head)} ${names[names.length - 1]}`;
}

/** 끝 글자 받침으로 와/과(그린워싱 withAnd 와 같은 뜻). */
function withAnd(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  const hangul = last >= 0xac00 && last <= 0xd7a3;
  return `${name}${hangul && (last - 0xac00) % 28 !== 0 ? '과' : '와'}`;
}

/** 끝 글자 받침으로 은/는(밴드 TRW1a ② — 감독 판단 4 의 띠). */
function withTopic(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  const hangul = last >= 0xac00 && last <= 0xd7a3;
  return `${name}${hangul && (last - 0xac00) % 28 !== 0 ? '은' : '는'}`;
}
