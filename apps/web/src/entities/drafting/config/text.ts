// 원고작성 화면 글 한 곳(밴드 RPW1 — RP-01~04). 해요체(sid:MARC-ENT-269). 아무것도 가져오지 않는다.
// 글의 출처 꼬리표: [초안 글] 시안 RP-0*_r1(캔버스 v188)의 글 그대로 · [처분] 발주서 §2-0 감독 처분의 글 · [러너 초안] 둘 다 없어
//   러너가 지은 글(보고 「시안과 다른 글」 — 디자인 74 대조). 서버 message·reason 은 화면에 싣지 않는다(발주서 §1-4 ③).
/** 「2026 · 이름」 — 이름이 그 해로 시작하면 해를 겹쳐 쓰지 않는다(시안 「2026 · 2026 …」 0). */
const yearAndName = (year: number, name: string) =>
  name.startsWith(String(year)) ? name : `${year} · ${name}`;

export const DR_TEXT = {
  /** 틀(AppShell) 글 — 온실가스 GHG_TEXT.shell 을 옮겨 적음(가져오지 않는다), title 만 「보고서 작성」. */
  shell: {
    menuLabel: '모듈 메뉴',
    logo: '로고 자리',
    title: '보고서 작성',
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
  /** STEP 띠(시안 RP-02~04). */
  steps: {
    label: '보고서 작성 단계',
    items: ['전년도 보고서', '목차 설정', '개조식 초안'],
  },
  /** 회사 거절 셋(sid:MARC-ENT-374 — 온실가스 글을 옮겨 적음, 다시 시도 없음). */
  company: {
    ambiguous: '작업할 회사를 정하지 못했어요. 운영 관리자에게 문의해 주세요',
    inactive: '사용이 중지된 회사예요. 운영 관리자에게 문의해 주세요',
    not_found: '회사 정보를 찾지 못했어요. 운영 관리자에게 문의해 주세요',
  },
  companyOperator: {
    ambiguous: '작업할 회사를 확인할 수 없어요',
    inactive: '작업할 회사가 사용 중지 상태예요',
    not_found: '작업할 회사 정보를 찾지 못했어요',
  },
  common: {
    retry: '다시 시도',
    /** [러너 초안] 불러오는 중 상자 이름(화면 읽기 프로그램용). */
    loading: '불러오는 중',
    toList: '목록으로',
  },
  /** RP-01 보고서 프로젝트 목록. */
  list: {
    title: '보고서 프로젝트',
    /** [초안 글] 머리 오른쪽 링크 → RP-00(밴드 RPW6, sid:MARC-ENT-530 — TR-01 「번역 안내」 꼴). */
    introLink: '작성 안내',
    /** [초안 글] 머리 아래 한 줄 — 회사 칸은 숨김(§2-0 ②), 「회사마다 …」 줄은 서버가 막지 않아 뺐다(⑬). */
    summary: (count: number) => `프로젝트 ${count}건`,
    /** [러너 초안] 서버 한 번 읽기(100줄) 밖이 더 있을 때. */
    more: '최근 100건만 보여요',
    newProject: '새 프로젝트',
    /** [초안 글] 검색 칸 — 「·회사」는 뺐다(회사 칸 숨김 §2-0 ②). 이름·전년도 보고서 파일 이름에서 찾는다. */
    search: '프로젝트 검색',
    yearAll: '보고연도 전체',
    yearLabel: '보고연도',
    yearOption: (year: number) => `${year}`,
    filterLabel: '상태 거르기',
    filters: {
      all: '전체',
      preparing: '준비 중',
      drafting: '만드는 중',
      done: '초안 완료',
      failed: '실패',
    },
    tableLabel: '보고서 프로젝트 목록',
    columns: {
      project: '보고서 프로젝트 · 전년도 보고서',
      year: '보고연도',
      leaves: '목차 · 초안',
      state: '상태',
      createdAt: '만든 날',
      next: '다음 할 일',
    },
    /** [초안 글] 「8개 중 5개」. */
    leaves: (drafted: number, total: number) => `${total}개 중 ${drafted}개`,
    noLeaves: '—',
    noDocumentName: '전년도 보고서 없음',
    /** [초안 글] 상태 칸 — 「읽기 실패」는 행 상태가 아니다(§2-0 ③). [처분] PDF 올리기 전·초안 전·실패. */
    states: {
      no_document: 'PDF 올리기 전',
      no_outline: '목차 설정 전',
      no_draft: '초안 전',
      drafting: '초안 만드는 중',
      done: '초안 완료',
      partial: '일부 목차 못 만듦',
      outline_changed: '목차 바뀜',
      failed: '실패',
    },
    /** [초안 글] 「초안 만드는 중 · 5/11」. */
    drafting: (done: number, total: number) =>
      `초안 만드는 중 · ${done}/${total}`,
    /** [초안 글] 다음 할 일 — 상태마다 하나. */
    next: {
      no_document: 'PDF 올리기',
      no_outline: '목차 설정',
      no_draft: '초안 만들기',
      drafting: '진행 보기',
      done: '초안 보기',
      partial: '초안 보기',
      outline_changed: '다시 만들기',
      failed: '초안 보기',
    },
    /** [초안 글] 빈 목록. */
    empty:
      '아직 만든 보고서 프로젝트가 없어요. 새 프로젝트를 만들고 전년도 보고서 PDF 를 올려 시작해요.',
    /** [초안 글] 거르기 빈 결과. */
    filteredEmpty: '조건에 맞는 프로젝트가 없어요',
    clearFilter: '거르기 풀기',
    /** [초안 글] 목록을 불러오지 못함(CM-03). */
    failed: '보고서 프로젝트 목록을 불러오지 못했어요',
    /** 표 카드 안 아래 회색 상자 — 판 RP-01 `.e-info` 글 그대로(밴드 RPW5 #2). */
    notice:
      '프로젝트를 만들고 전년도 보고서 PDF 를 올린 뒤 목차를 정하면, 목차마다 전년도 보고서에서 찾은 내용으로 개조식 초안을 지어요. 초안은 출처 페이지와 함께 보여요.',
  },
  /** [초안 글] RP-00 작성 안내(밴드 RPW6, 시안 v196 RP-00_r1 — TR_TEXT.intro 꼴을 옮겨 지음). 코드 사실과 대조함(보고 표):
   *  요구 내용 2,000자 = pages/drafting-outline REQUIREMENT_MAX · 네 단계 = outline.depths · 텍스트 PDF = create.dropFormats ·
   *  내려받기 = 실행 하나의 docx(store.downloadDocx(runId)) · 안내 = result.guide 와 같은 글. */
  intro: {
    title: '보고서 작성',
    heading: '보고서 작성이란',
    lead: [
      '전년도 지속가능경영보고서 PDF 와 올해 목차를 받아, 목차마다 전년도 보고서에서 맞는 페이지를 찾아 개조식 초안을 지어요.',
      'bullet 마다 근거가 된 페이지가 붙어 있어서, 원문 보기에서 근거 문단과 문장을 바로 확인할 수 있어요.',
    ],
    hint: '시작하기 버튼을 눌러 보고서 프로젝트를 만들어 보세요.',
    flowTitle: '작성 과정',
    flow: [
      {
        step: 'Step 1',
        title: '전년도 보고서',
        body: '전년도 보고서 PDF 를 올리면 페이지마다 글을 읽어요',
      },
      {
        step: 'Step 2',
        title: '목차 설정',
        body: '대·중·소·소소 네 단계로 목차를 세우고 목차마다 요구 내용을 적어요',
      },
      {
        step: 'Step 3',
        title: '개조식 초안',
        body: '목차마다 맞는 페이지를 찾아 초안을 짓고, 출처 페이지와 함께 보여 드려요',
      },
    ],
    give: {
      title: '올리는 것',
      head: ['항목', '설명', '넣기'],
      rows: [
        [
          '전년도 보고서 PDF',
          '텍스트 선택이 가능한 PDF 예요. 텍스트가 없는 그림 PDF 는 읽지 못해요',
          '필수',
        ],
        [
          '목차',
          '네 단계까지 세울 수 있고, 목차마다 요구 내용을 2,000자까지 적어요',
          '필수',
        ],
      ],
    },
    get: {
      title: '받는 것',
      head: ['결과', '설명'],
      rows: [
        [
          '개조식 초안',
          '목차마다 bullet 로 지은 초안이에요. bullet 마다 출처 페이지가 붙어요',
        ],
        [
          '원문 보기',
          '고른 목차의 근거 문단은 옅은 상자, 근거 문장은 진한 표시로 원본 PDF 위에 보여요',
        ],
        ['내려받기', '지금 보는 실행의 개조식 전부를 한 파일로 내려받아요'],
      ],
    },
    info: '출처는 AI 가 단 페이지예요 · 내용이 맞는지는 컨설턴트가 확인해요',
    start: '시작하기',
  },
  /** RP-02 새 프로젝트 · 전년도 보고서 올림. */
  create: {
    title: '새 보고서 프로젝트',
    reuploadTitle: '전년도 보고서 다시 올리기',
    lead: '연도를 정하고 전년도 보고서 PDF 를 올려요. 다음은 목차 설정이에요.',
    /** [초안 글] 다시 올리기 부제. */
    reuploadLead: '전년도 보고서 PDF 를 다시 올려요',
    projectSection: '1. 프로젝트',
    yearLabel: '보고연도',
    yearHint: '올해 쓸 보고서의 연도',
    nameLabel: '프로젝트 이름',
    /** [러너 초안] 이름 기본값 — 시안 「2026 지속가능경영보고서」 꼴. */
    nameDefault: (year: number) => `${year} 지속가능경영보고서`,
    /** [러너 초안] 이름 칸 오류. */
    nameRequired: '프로젝트 이름을 적어 주세요',
    nameTooLong: (max: number) => `프로젝트 이름은 ${max}자까지예요`,
    yearInvalid: '보고연도를 확인해 주세요',
    documentSection: '2. 전년도 보고서',
    documentHint: 'PDF 하나',
    dropGuide: '전년도 지속가능경영보고서 PDF 를 올려요',
    dropFormats: '.pdf 하나 · 텍스트 선택이 가능한 PDF',
    /** [초안 글] 「152페이지」. */
    pages: (count: number) => `${count}페이지`,
    notPdf: 'PDF(.pdf) 파일만 올릴 수 있어요',
    uploading: '올리는 중',
    /** [초안 글] 파일 줄 크기 「18.4MB」(고른 파일의 크기 — 서버 값이 아니다). */
    size: (bytes: number) =>
      bytes < 1024 * 1024 ?
        `${Math.max(1, Math.round(bytes / 1024))}KB`
      : `${(bytes / (1024 * 1024)).toFixed(1)}MB`,
    /** [러너 초안] 파일 줄 [취소] 이름(화면 읽기용 — 아래 [취소]와 가른다). */
    cancelFile: (name: string) => `${name} 취소`,
    /** [초안 글] 텍스트 없는 PDF 상자 아래. */
    otherPdf: '다른 PDF 올리기',
    /** [초안 글] 텍스트 없는 PDF. */
    noText:
      '이 PDF 에서 텍스트를 찾지 못했어요. 스캔본이면 텍스트 선택이 가능한 PDF 로 다시 만들어 올려 주세요',
    /** [초안 글] 읽기 실패. */
    readFailed:
      'PDF 를 읽지 못했어요. 파일이 열리는지 확인하고 다시 올려 주세요',
    /** [러너 초안] 프로젝트 만들기 실패(올리기 전). */
    createFailed: '프로젝트를 만들지 못했어요. 잠시 뒤 다시 시도해 주세요',
    /** [러너 초안] 다시 올리기 화면에서 프로젝트를 못 찾음. */
    projectMissing: '보고서 프로젝트를 찾지 못했어요',
    /** [러너 초안] 다시 올리기 화면에서 프로젝트를 못 불러옴. */
    projectLoadFailed: '보고서 프로젝트를 불러오지 못했어요',
    cancel: '취소',
    next: '다음 · 목차 설정',
  },
  /** RP-03 목차 설정. */
  outline: {
    title: '목차 설정',
    /** [러너 초안] 머리 아래 — 「2026 · 프로젝트 이름」(회사 칸 숨김 §2-0 ②). */
    lead: yearAndName,
    /** [초안 글] 부제 뒤 — 「 · 전년도 보고서 <파일> 152페이지」(쪽 수는 아는 값이 있을 때만). */
    leadFile: (fileName: string, pages: number | null) =>
      ` · 전년도 보고서 ${fileName}${pages === null ? '' : ` ${pages}페이지`}`,
    toList: '목록으로',
    treeTitle: '목차',
    /** [초안 글] 단계 이름(트리 줄 오른쪽). */
    depths: ['대', '중', '소', '소소'],
    /** [초안 글] 「대 3 · 중 7 · 소 2 · 소소 1 · 초안 지을 목차 8」. */
    counts: (depths: readonly number[], leaves: number) =>
      `대 ${depths[0]} · 중 ${depths[1]} · 소 ${depths[2]} · 소소 ${depths[3]} · 초안 지을 목차 ${leaves}`,
    save: '저장',
    saved: '저장했어요',
    /** [초안 글] 「2026-10-29 14:05 저장」 — 저장 응답을 받은 브라우저 시각(서버 칸 없음). */
    savedAt: (at: string) => ` · ${at} 저장`,
    start: '초안 만들기',
    /** [처분 ⑧] 앞 실행이 있으면 [초안 만들기] 대신. */
    toDraft: '초안 화면으로',
    /** [초안 글] 목차가 없을 때 [초안 만들기] 옆. */
    needNodes: '목차를 하나 이상 넣어 주세요',
    addTop: '대제목 더하기',
    addSibling: '같은 단계 더하기',
    addChild: '아래 단계 더하기',
    /** [러너 초안] 새 마디의 처음 이름(서버는 빈 제목을 받지 않는다). */
    newTitle: '새 목차',
    empty: '아직 목차가 없어요. 대제목부터 더해요.',
    nameLabel: '목차 이름',
    requirementLabel: '요구 내용',
    requirementHint:
      '이 목차에 무엇을 쓸지 적어요. AI 가 전년도 보고서에서 내용을 찾고 개조식을 지을 때 기준으로 써요 · 2,000자까지',
    /** [처분 ⑫] 글자 수 「120 / 2,000」. */
    requirementCount: (count: number, max: number) =>
      `${count.toLocaleString('ko-KR')} / ${max.toLocaleString('ko-KR')}`,
    up: '위로',
    down: '아래로',
    outdent: '한 단계 올리기',
    indent: '한 단계 내리기',
    remove: '이 목차 지우기',
    /** 편집 칸 머리 오른쪽(판 v197 `.rp-del`). */
    removeShort: '삭제',
    /** 트리 아래 단축키 도움말(판 v197 `.rp-help`). */
    help: '↑↓ 고르기 · Alt+↑↓ 옮기기 · Enter 이름 고치기 · Tab 한 단계 내리기 · Shift+Tab 올리기 · Delete 지우기',
    /** 아래 단계가 있는 목차 · 요구 글 없음(판 v197 `.rp-sub`). */
    upperHint: '아래 단계 목차마다 요구 내용을 적어요',
    /** 아래 단계가 있는 목차 · 요구 글 남음(판 v197 `.rp-ro`). */
    upperLeftover: '아래 단계가 생겨 이 글은 초안에 쓰지 않아요',
    clearRequirement: '글 지우기',
    /** 끌어 옮기기 — 놓을 수 없는 자리(판 v197). */
    tooDeep: '네 단계까지만 둘 수 있어요',
    /** 손 옆 표의 「<이름> · 아래 단계 N」. */
    dragChildren: (count: number) => `아래 단계 ${count}`,
    /** 트리 머리 「24개」(14줄을 넘을 때만). */
    treeTotal: (count: number) => `${count}개`,
    /** 편집 칸 머리 배지. 판 글자는 중제목·소제목이고, 대제목은 단추 글에서, 소소제목은 [러너 초안]. */
    depthBadges: ['대제목', '중제목', '소제목', '소소제목'],
    /** [러너 초안] 지우기 확인 창. */
    removeConfirm: (title: string) => `「${title}」 목차를 지울까요?`,
    removeChildren: (count: number) =>
      `아래 단계 목차 ${count}개도 함께 지워져요`,
    removeYes: '지우기',
    cancel: '취소',
    /** [초안 글] 안내. */
    guide: (leaves: number) =>
      `초안은 하위 목차가 없는 목차마다 지어요 · 지금 ${leaves}개 · 대·중·소·소소 네 단계까지 둘 수 있어요`,
    /** [초안 글] 고친 줄이 있을 때. */
    dirty: '저장하지 않은 고침이 있어요',
    /** [초안 글] 초안을 만든 뒤 목차를 고쳐 저장했을 때. */
    changedAfterRun:
      '목차를 고쳤어요. 초안 화면에서 바뀐 목차만 다시 만들 수 있어요',
    /** [초안 글] 저장 실패. */
    saveFailed: '목차를 저장하지 못했어요. 다시 시도해 주세요',
    /** [러너 초안] 저장 거절(줄을 가리키지 못한 422). */
    saveRejected: '목차를 저장하지 못했어요. 목차 단계와 수를 확인해 주세요',
    /** [러너 초안] 수 상한(마디 300 · 잎 150). */
    tooMany: (nodes: number, leaves: number) =>
      `목차는 ${nodes}개, 초안 지을 목차는 ${leaves}개까지예요`,
    /** [러너 초안] 줄 칸 오류. */
    titleProblem: (max: number) => `목차 이름을 1~${max}자로 적어 주세요`,
    requirementProblem: (max: number) =>
      `요구 내용은 ${max.toLocaleString('ko-KR')}자까지예요`,
    /** [러너 초안] 줄 오류 표지(트리). */
    rowProblem: '고칠 곳 있음',
    /** [러너 초안] 고친 줄 점(화면 읽기용). */
    rowChanged: '고침',
    /** [러너 초안] 나갈 때 물음. */
    leaveTitle: '저장하지 않은 고침이 있어요',
    leaveBody: '나가면 고친 목차가 사라져요',
    leaveStay: '계속 고치기',
    leaveGo: '저장하지 않고 나가기',
    projectMissing: '보고서 프로젝트를 찾지 못했어요',
    projectLoadFailed: '보고서 프로젝트를 불러오지 못했어요',
    /** RP-03a 목차 붙여넣기(밴드 RPW9, 디자인 e6 RP-03a·a1·a2 글 그대로). */
    paste: {
      open: '붙여넣기',
      title: '목차 붙여넣기',
      inputLabel: '붙여 넣을 목차',
      placeholder: '엑셀이나 문서에서 목차를 복사해 붙여 넣어 주세요',
      guide: [
        '단계: 들여쓰기 또는 번호(1. / 1.1 / 1.1.1 / 1.1.1.1), 네 단계까지',
        '요구 내용: 줄 끝 「요구:」 뒤나 탭 뒤(엑셀 두 칸)',
      ],
      preview: '미리보기',
      previewCounts: (nodes: number, leaves: number) =>
        `목차 ${nodes}개 · 끝 목차 ${leaves}개`,
      previewEmpty: '붙여 넣으면 읽은 목차가 여기에 보여요',
      requirementMark: '요구',
      requirementMarkTitle: '요구 내용 있음',
      /** 한도 띠 — total 은 지금 목차와 합친 수(바꾸기면 null — 괄호 없음, 처분 ④). */
      tooManyNodes: (max: number, total: number | null) =>
        `목차는 ${max}개까지 넣을 수 있어요${total === null ? '' : `(지금 목차와 합쳐 ${total}개)`}`,
      tooManyLeaves: (max: number, total: number | null) =>
        `끝 목차는 ${max}개까지 넣을 수 있어요${total === null ? '' : `(지금 목차와 합쳐 ${total}개)`}`,
      badSummary: (count: number) =>
        `${count}줄을 읽지 못했어요 — 넣을 때 빠져요`,
      badOpen: '펼치기',
      badClose: '접기',
      badLine: (line: number) => `${line}행`,
      reasons: {
        tooDeep: '다섯째 단계는 넣을 수 없어요',
        titleLong: (max: number) =>
          `이름이 ${max.toLocaleString('ko-KR')}자를 넘어요`,
        requirementLong: (max: number) =>
          `요구 내용이 ${max.toLocaleString('ko-KR')}자를 넘어요`,
        /** [러너 초안] 이름 없는 줄(번호만 · 첫 줄이 「요구:」) — 처분 ③. */
        noTitle: '이름이 없어요',
      },
      howLabel: '넣는 법',
      append: '지금 목차 뒤에 붙이기',
      replace: '지금 목차를 바꾸기',
      /** [목차에 넣기 (N개)] — 읽은 줄이 없으면 수 없이. */
      insert: (count: number | null) =>
        count === null ? '목차에 넣기' : `목차에 넣기 (${count}개)`,
      confirmTitle: '지금 목차를 바꿀까요?',
      confirmBody: (old: number, count: number) =>
        `지금 목차 ${old}개가 지워지고 새 목차 ${count}개로 바뀌어요`,
      confirmYes: '바꾸기',
    },
  },
  /** RP-04 실행 진행(경계 ②). */
  run: {
    title: '개조식 초안',
    /** [초안 글] 실행 고르기(RP-04 머리). 맨 위(가장 새 실행)만 「지금」. */
    picker: '실행',
    pickerOption: (n: number, at: string, latest: boolean) =>
      `실행 ${n} · ${at}${latest ? ' · 지금' : ''}`,
    /** [초안 글] 만드는 중. */
    making: '초안을 만들고 있어요',
    keepGoing: '이 창을 닫아도 계속돼요',
    /** [초안 글] 실행 중 머리 셈 — 아는 값만(잎 수). */
    headCount: (total: number) => `목차 ${total}개`,
    /** [처분 ④·초안 글] 진행 줄 셋. extract 는 수 없음. */
    steps: {
      extract: '전년도 보고서 읽는 중',
      map: '목차에 맞는 페이지 찾기',
      draft: '목차마다 초안 짓기',
    },
    /** [초안 글] 「목차 4/8」. */
    stepCount: (done: number, total: number) => `목차 ${done}/${total}`,
    /** [러너 초안] 진행 줄 설명 — 시안의 「148페이지를 목차 8개에 달았어요」는 서버 칸이 없어 수 없는 글로. */
    stepHints: {
      extract: '페이지마다 글자를 읽어요',
      map: '전년도 보고서 페이지를 목차에 달아요',
      draft: '찾은 내용으로 개조식을 지어요',
    },
    /** [초안 글] 「목차 8개 가운데 5번째」. */
    stepNow: (now: number, total: number) =>
      `목차 ${total}개 가운데 ${now}번째`,
    /** [러너 초안] 진행 막대 이름(화면 읽기용). */
    stepBar: '초안 지은 목차',
    stepStates: {
      pending: '기다림',
      running: '진행 중',
      done: '완료',
      failed: '멈춤',
    },
    /** [초안 글] 실행 실패 띠(errorCode·숫자 0). */
    failed: '이번 실행은 만들지 못했어요',
    /** [초안 글] 실패 띠 아래 [전체 다시 만들기] 옆 한 줄. */
    failedHint: '앞 실행이 있으면 실행 고르기에서 볼 수 있어요',
    /** [초안 글] 머리 단추. */
    toOutline: '목차 설정',
    restartAll: '전체 다시 만들기',
    runMissing: '이 초안 실행을 찾지 못했어요',
    runLoadFailed: '초안 진행을 불러오지 못했어요',
  },
  /** RP-04 결과 세 칸(경계 ③ — [초안 글] 시안 v188 RP-04_r1, 처분 ⑤⑦). */
  result: {
    /** [초안 글] 머리 셈(잎만). */
    counts: (
      total: number,
      drafted: number,
      noMaterial: number,
      failed: number,
      notRun: number,
    ) =>
      `목차 ${total}개 · 초안 ${drafted} · 맞는 자료 없음 ${noMaterial} · 못 만듦 ${failed} · 아직 ${notRun}`,
    /** [초안 글] 머리 아래 — 「2026 · 프로젝트 이름 · 전년도 보고서 파일 이름」(회사 칸 숨김). */
    subtitle: (year: number, name: string, fileName: string) =>
      `${yearAndName(year, name)} · 전년도 보고서 ${fileName}`,
    /** [초안 글] 탭 — 1차는 하나. */
    tab: '개조식',
    download: '내려받기',
    /** [러너 초안] 내려받기 실패(받기 모달의 그 줄 아래 한 줄). */
    downloadFailed: '파일을 받지 못했어요. 다시 눌러 주세요.',
    /** 받기 모달(밴드 RPW13 — 시안 RP-04a r1 · sid:MARC-ENT-662·663). 실패 글은 downloadFailed. */
    downloads: {
      title: '내려받기',
      close: '닫기',
      /** 꺼진 줄 (?) 단추 이름 머리. */
      helpLabel: '없는 까닭',
      busy: '받는 중',
      name: '개조식 초안',
      description: '지금 보는 실행의 개조식 전부를 한 파일로 내려받아요',
      fileLabel: 'Word',
      /** 꺼진 까닭 — 이번 실행 rejected. */
      rejected: '이번 실행은 만들지 못해 받을 파일이 없어요',
      /** 꺼진 까닭 — 이 실행 위에서 다시 짓는 중(readOnly). */
      rebuilding: '다시 만드는 중이에요 · 끝나면 받을 수 있어요',
    },
    tree: '목차 · 초안',
    treeFold: '목차 접기',
    treeOpen: '목차 펼치기',
    /** [초안 글] 「bullet 5 · 찾은 페이지 23~27」. */
    leafMeta: (bullets: number, span: [number, number] | null) =>
      span === null ? `bullet ${bullets}`
      : span[0] === span[1] ? `bullet ${bullets} · 찾은 페이지 ${span[0]}`
      : `bullet ${bullets} · 찾은 페이지 ${span[0]}~${span[1]}`,
    rebuildOne: '이 목차 다시 만들기',
    requirement: '요구 내용',
    guide: '출처는 AI 가 단 페이지예요 · 내용이 맞는지는 컨설턴트가 확인해요',
    chip: (page: number) => `전년도 보고서 · ${page}페이지`,
    noSource: '근거를 찾지 못했어요',
    notInSource: '원문에 없는 숫자예요',
    noMaterial: '이 목차에 맞는 자료가 없어요',
    leafFailed:
      '이 목차는 만들지 못했어요. [이 목차 다시 만들기]로 새로 만들 수 있어요',
    notRun: '아직 만들지 않았어요',
    /** [초안 글] 새로 더한 목차(added). */
    added:
      '새로 더한 목차예요 · [바뀐 목차 다시 만들기]를 누르면 초안을 지어요',
    /** [초안 글] 고른 줄이 부모(하위가 있는 목차)일 때 — [러너 초안]. */
    pickLeaf: '아래 목차를 고르면 초안이 보여요',
    /** [처분 ⑦] 앞 실행 위에서 다시 짓는 잎. */
    rebuilding: '다시 만드는 중',
    rebuildingNote: '이 목차의 초안을 다시 만들고 있어요',
    /** [초안 글] 고른 목차 말고도 다시 짓는 목차가 있을 때 — 회색 한 줄. */
    rebuildingMore: '못 만들었거나 아직인 목차도 함께 다시 만들어요',
    /** [초안 글·처분 ⑤] 띠 — 「같은 글로 다시」로 읽히는 말 0. */
    changed: '목차가 바뀌었어요',
    changedCount: (count: number) => `바뀐 목차 ${count}개`,
    changedMark: '바뀜',
    rebuildChanged: '바뀐 목차 다시 만들기',
    reuploaded: '전년도 보고서를 다시 올렸어요',
    /** [처분 ⑤] 실행 뒤 base.matched false — 회색 한 줄. */
    notMatched: '앞 초안을 이어 받지 못해 전부 새로 지었어요',
    /** [초안 글] status rejected — 숫자·서버 글 0. */
    rejected: '이번 실행은 만들지 못했어요',
    resultMissing: '개조식 초안을 찾지 못했어요',
    resultLoadFailed: '개조식 초안을 불러오지 못했어요',
    source: {
      title: '원문 보기',
      pageOf: (page: number, count: number) => `${page} / ${count}`,
      /** [러너 초안] ‹ › 이름(화면 읽기용). */
      pagePrev: '앞 페이지',
      pageNext: '다음 페이지',
      leafPages: '이 목차의 페이지',
      file: (name: string) => `전년도 보고서 · ${name}`,
      block: '근거 문단',
      sentence: '근거 문장',
      paragraphOnly: '문단까지만 찾았어요',
      /** [초안 글] 원본 PDF missing·failed. */
      failed: '원본 PDF 를 불러오지 못했어요',
    },
  },
  /** 실행 시작 거절 한 줄(발주서 §2-1 [초안 글] — 설정 화면 이름·서버 글 0). */
  startRefused:
    '초안을 시작하지 못했어요 — 목차와 전년도 보고서를 확인해 주세요',
  /** [초안 글] 실행 시작 연결 실패 한 줄(거절과 다른 글, 발주서 §2-0 ③ — 다시 누르면 같은 열쇠). */
  startFailed: '연결이 끊겨 초안을 시작하지 못했어요. 잠시 뒤 다시 눌러 주세요',
} as const;
