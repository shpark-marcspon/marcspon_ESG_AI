// 그린워싱 화면·부품의 문구 표(밴드 FW1). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다.
// 이 파일은 아무것도 가져오지 않는다(app/guards/layers.test.ts 가 지킨다).
// shared/ui/text.ts 는 가져오지 않는다: shared/ui 부품의 문구가 필요하면 그 부품의 props 로 넘긴다(발주서 §1-2 [B3]).
//
// 확정 전인 것(무효 조건):
//   - 등급 글자 High·Mid·Low 와 등급 색: 우리 쪽 확정(2026-10-16 사용자 결정), 마크스폰 확인 전이다. 글자는 shared RiskBadge(PARTS_TEXT.risk)
//     하나가 그린다 — 여기 두 벌을 두지 않는다(sid:MARC-ISSUE-308).
//   - 상태 이름(AI 점검 중·멈춤·검토 대기·검토 중·검토 완료): 시안 댓글 1차 반영(sid:MARC-ENT-603). 확정 버튼·모달 동사 「확정」은 그대로. 검토·확정 흐름 전체가 마크스폰 확인 전이다(덧붙임 5절 1번).
//   - 단계 이름 셋: 시안 GW-02_r1 의 g-flow 글자.
//   - 검토·확정·비교 문구(review·exclude·confirm·lock·compare·versionFlow): 시안 GW-05·05a·05b·05c·06 의 글자.
// 말투(2026-10-16 사용자 결정, sid:MARC-TICK-73 노트): 화면 문구(안내 상자·설명 줄·모달 본문·잠금 띠·오류·빈 상태·화면 제목 아래 설명)는
//   해요체다. 시안의 합니다체 글은 뜻을 바꾸지 않고 해요체로 옮겼다. AI 결과 글(판정 사유·수정 방향·대체표현)은 합니다체다(이 표에 없다).
// 확인 모달 버튼은 동사([취소]/[제외], [취소]/[확정])로 둔다(같은 사용자 결정).
//   - 제외 사유 넷과 그 값 이름, 비교 분류 일곱의 값 이름: 계약(GC1) 초안 전이다. GC1 이 이름을 바꾸면 여기와 부품의 값 표를 바꾼다.
//   - 「확정하면 남은 문장은 채택으로 확정」: 디자인 감독 가정(인계 v56 덧붙임 4절). 사용자 확인 전이다.

export const GW_TEXT = {
  /** 실행 상태 배지의 글자. 「멈춤」은 디자인 답 D6(밴드 GW2R ①), 「AI 점검 중」·「검토 대기」·「검토 완료」는 시안 댓글 1차 반영(sid:MARC-ENT-603). */
  runStatus: {
    analyzing: 'AI 점검 중',
    failed: '멈춤',
    pending: '검토 대기',
    reviewing: '검토 중',
    confirmed: '검토 완료',
  },
  /**
   * 불러오기·오류 꼴의 단추(밴드 LE1, sid:MARC-ENT-260, 시안 CM-03). 실패 꼴은 [다시 시도](+ 주 데이터면 [목록으로]),
   * 없음 꼴은 [목록으로] 하나. 글(「{무엇}을 불러오지 못했어요」·「{무엇} 찾을 수 없어요」)은 화면마다의 칸에 둔다.
   */
  load: {
    retry: '다시 시도',
    toList: '목록으로',
    /** 데이터에서 오는 제목을 아직 모를 때 h2 의 숨긴 글(PageTitle pendingLabel — 밴드 GL1). */
    titlePending: '불러오는 중',
  },
  /**
   * 실행 만들기([점검 시작]·[다시 실행])의 답이 끊김 — 만들어졌는지 모른다(밴드 GR1·GR2, sid:MARC-ISSUE-225 · 디자인 e9 답 10-23).
   * 같은 단추를 다시 누르면 같은 열쇠로 보내 한 번만 시작된다(서버 사정 말은 넣지 않는다 — 사용자 10-22 밤). 단추 글은 그대로 + [목록으로].
   * 두 문장이라 마침표.
   */
  runUnreachable: {
    start:
      '요청이 전달됐는지 확인하지 못했어요. 다시 눌러도 점검은 한 번만 시작돼요.',
    rerun:
      '요청이 전달됐는지 확인하지 못했어요. 다시 눌러도 실행은 한 번만 시작돼요.',
  },
  /** 점검 단계 띠. */
  stepFlow: {
    label: '점검 단계',
    prefix: 'STEP',
    steps: ['파일·페이지 지정', '문장 찾기·판정', '결과 정리·검토'],
  },
  /** 문장 검토 표시. */
  review: {
    adopted: '채택',
    excluded: '제외',
    unreviewed: '미검토',
    /** 고르는 꼴의 묶음 이름. */
    groupLabel: '검토',
    /** 시안 v76 GW-05: position 이 null 인 문장(쪽 이동만). 미리보기 위 회색 안내. ④ 에서 쓴다(발주서 덧붙임 2). */
    positionMissing:
      '이 문장은 페이지에서 자리를 찾지 못해 페이지로만 이동했어요',
  },
  /** 제외 사유 모달(GW-05a). */
  exclude: {
    title: '이 문장을 제외할까요?',
    reasonLegend: '제외 사유',
    reasons: {
      not_claim: '환경 주장 문장이 아님',
      evidence_in_doc: '근거가 문서에 있음(AI 가 놓침)',
      other: '기타',
    },
    noteLabel: '설명',
    notice:
      '제외한 문장은 확정본과 엑셀에서 빠지고, 사유는 검토 기록에 남아요.',
    /** Figma Policy 「필수 입력 항목이에요」 꼴. 라디오라 「선택」(디자인 감독이 정함, sid:MARC-ISSUE-97 노트). */
    reasonRequired: '필수 선택 항목이에요',
    cancel: '취소',
    submit: '제외',
  },
  /** 확정 확인 모달(GW-05b). */
  confirm: {
    title: '검토를 확정할까요?',
    unreviewedWarning: (count: number) =>
      `미검토 문장 ${count}개가 남아 있어요. 확정하면 남은 문장은 「채택」으로 확정돼요.`,
    lockNotice:
      '확정하면 이 실행의 결과가 잠겨 채택·제외를 더 바꿀 수 없어요. 엑셀은 확정본으로 나가요.',
    cancel: '취소',
    submit: '확정',
  },
  /** 확정 뒤 잠금 띠(GW-05c). */
  lock: {
    /** 디자인 감독 가정(sid:MARC-TICK-73 노트 7O60U5DTjjM2GHugu2Es9, 밴드 FW2 ⑤): 「{일시} {이름}님이 …」, 이름이 비면 「{일시}에 …」. */
    banner: ({ by, at }: { by: string; at: string }) =>
      `${by.trim() === '' ? `${at}에` : `${at} ${by.trim()}님이`} 확정했어요. 채택·제외를 더 바꿀 수 없고, 엑셀은 확정본(채택한 문장)으로 나가요.`,
  },
  /** 수정본 비교 분류의 한 줄 글자(GW-06). 엑셀처럼 한 줄이 필요한 곳에 쓴다(덧붙임 68줄). 키는 계약 값(GC1 초안 전). */
  compare: {
    resolved_deleted: '해소 · 문장 삭제',
    resolved_not_flagged: '해소 · 더는 지적 안 됨',
    resolved_undetermined: '해소',
    remaining: '남음',
    level_changed: '등급 바뀜',
    new: '새로 생김',
    out_of_scope: '범위 밖',
  },
  /** 수정본 비교 배지의 글자(GW-06 표 칸). 해소 셋은 「해소」 한 장으로 묶는다(디자인 대조 물음 9, 밴드 FW1b ⓪). */
  compareBadge: {
    resolved_deleted: '해소',
    resolved_not_flagged: '해소',
    resolved_undetermined: '해소',
    remaining: '남음',
    level_changed: '등급 바뀜',
    new: '새로 생김',
    out_of_scope: '범위 밖',
  },
  /** 해소 갈래 글(배지 아래 작은 글). 갈래 없는 해소와 다른 분류는 없다. */
  compareNote: {
    resolved_deleted: '문장 삭제',
    resolved_not_flagged: '더는 지적 안 됨',
  },
  /** 버전 흐름 띠(GW-06). */
  versionFlow: {
    label: '버전 흐름',
    base: '비교 대상',
    current: '이번',
  },
  /** 새 점검(GW-02·02a). 글은 캔버스 v66 GW-02·v64 GW-02a 의 해요체 글 그대로다. 「(지은 글)」 표시는 시안에 없어 러너가 지은 것(디자인에 묻는다). */
  newCheck: {
    title: '새 점검',
    description:
      'PDF 파일과 파트별 페이지 번호를 넣으면 환경 주장 문장을 찾아 위험 등급을 매겨요.',
    upload: {
      heading: '1. 문서 올리기',
      guide: 'PDF 파일을 끌어 놓거나 눌러서 골라 주세요',
      /** 한도는 model MAX_PAGE_COUNT·MAX_UPLOAD_MB 를 받는다(한 수 — 이 표는 아무것도 가져오지 않는다). */
      formats: (maxPages: number, maxMb: number) =>
        `텍스트 선택이 가능한 PDF 만 점검해요 · 최대 ${maxPages}페이지, ${maxMb}MB 까지`,
      /** (지은 글) 크기 한도를 넘은 파일 — 고를 때(드롭존)와 서버 413 UPLOAD_TOO_LARGE 둘 다 이 글. 다시 눌러도 같으니 「잠시 뒤」를 쓰지 않는다. */
      tooLarge: (maxMb: number) => `${maxMb}MB 이하 PDF 만 올릴 수 있어요`,
      /** 목 저장소가 거절한 파일 줄의 상태 글(발주서 §2 ①). */
      uploadFailed: '올릴 수 없는 파일',
      /** 올린 파일의 쪽 수 줄. 시안 e-file 의 meta 칸(쪽 수 · 크기 · 텍스트 없음)에서 쪽 수. */
      pageMeta: (pageCount: number) => `총 ${pageCount}페이지`,
      /** 파일 크기(밴드 FW2 ⓪, 시안 e-file meta 「139쪽 · 18.4MB」). 1MB 아래는 KB(지은 꼴). */
      fileSize: (bytes: number) =>
        bytes >= 1024 * 1024 ?
          `${(bytes / (1024 * 1024)).toFixed(1)}MB`
        : `${Math.max(1, Math.round(bytes / 1024))}KB`,
      /** 쪽 수 · 크기를 한 줄에(파일 줄의 meta 칸). 글자 없는 PDF 는 끝에 「· 텍스트 없음」(v115 GW-02a_r2 「24쪽 · 31.2MB · 텍스트 없음」). */
      fileMeta: (pageMeta: string, size: string, hasText = true) =>
        `${pageMeta} · ${size}${hasText ? '' : ' · 텍스트 없음'}`,
      /** v115 GW-02a_r2 의 빨강 안내(GW-03 r3 스캔본 카드도 같은 글). */
      noText:
        '이 PDF는 텍스트를 선택할 수 없어요(스캔본·이미지로 만든 PDF). 텍스트를 선택할 수 있는 PDF로 다시 올려 주세요.',
      /** v115 GW-02a_r2 의 안내 아래 회색 줄(한 문장 끝 마침표 없음 — 판 그대로). */
      noTextHow:
        '확인하는 법: PDF 에서 텍스트를 마우스로 끌어 선택되는지 보세요. 선택되지 않으면 텍스트를 선택할 수 없는 PDF 예요',
    },
    year: {
      label: '보고연도',
      /** 고르지 않음 갈래(지은 글). */
      none: '선택 안 함',
    },
    parts: {
      heading: '2. 파트별 페이지 범위',
      groupLabel: '칠할 파트',
      names: { ceo: 'CEO 메시지', company: '회사소개', climate: '기후·환경' },
      pageCount: (count: number) => `페이지 ${count}개`,
      activeHint: (name: string) => `고른 파트: ${name}`,
      /** 썸네일 버튼의 이름: 「4페이지」, 「4페이지, CEO 메시지」, 「5페이지, CEO 메시지와 회사소개」. */
      thumbLabel: (page: number, names: readonly string[]) =>
        names.length === 0 ?
          `${page}페이지`
        : `${page}페이지, ${joinNames(names)}`,
      viewing: (from: number, to: number) =>
        `${from}~${to}페이지를 보고 있어요`,
      /** 보이지 않는 페이지에 칠한 파트: 「41~139페이지에 기후·환경 55~74페이지가 칠해져 있어요」. */
      hiddenPainted: (
        from: number,
        to: number,
        items: readonly { name: string; range: string }[],
      ) =>
        `${from}~${to}페이지에 ${items.map((it) => `${it.name} ${it.range}페이지`).join(', ')}가 칠해져 있어요`,
      more: (from: number, to: number) => `더 보기 (${from}~${to}페이지)`,
      legendOverlap: '두 파트 이상이 겹친 페이지',
      /** (지은 글) 썸네일 칸에서 PDF 를 열지 못함(sid:MARC-ISSUE-99 7). */
      pdfError: 'PDF 를 열 수 없어요. 파일을 지우고 다시 올려 주세요',
      /** (지은 글) 쪽 하나를 그리지 못함(문서 쪽 수가 PDF 보다 큰 때 등). */
      thumbError: '그릴 수 없음',
      /** 글자 칸 옆: 「페이지 10개 · 5페이지는 CEO 메시지와 겹침」. */
      fieldMeta: (count: number, overlap: string, others: readonly string[]) =>
        overlap === '' ?
          `페이지 ${count}개`
        : `페이지 ${count}개 · ${overlap}페이지는 ${withAnd(joinNames(others))} 겹침`,
      rangeHelp:
        '썸네일에서 끌어서 고르거나 글자로 넣으면 서로 맞춰져요. 페이지 번호는 PDF 페이지 기준이고, 떨어진 구간은 쉼표로 이어 써요.',
      checked: (count: number, pageCount: number) =>
        `점검할 페이지: ${count}개 / 총 ${pageCount}페이지. 넣지 않은 페이지는 문장 점검을 하지 않지만, 단어 빈도는 문서 전체에서 세어요.`,
      /** 글자 칸 아래 오류. over 는 시안 글, 나머지는 지은 글. */
      rangeError: {
        over: (page: number, pageCount: number) =>
          `${page}페이지는 문서의 마지막 페이지(${pageCount}페이지)를 넘어요`,
        /** 문서를 올리기 전(쪽 수를 모름): 1차 한도(지은 글). */
        overMax: (max: number) =>
          `페이지 번호는 ${max}페이지까지 넣을 수 있어요`,
        /** 디자인 대조 「지은 글 고칠 안」(밴드 FW2 ⓪). */
        reversed: (from: number, to: number) =>
          `${from}~${to}페이지는 앞 페이지 번호가 뒤 페이지보다 커요`,
        zero: '페이지 번호는 1부터 넣어 주세요',
        negative: '페이지 번호는 1부터 넣어 주세요',
        /** 디자인 대조 「지은 글 고칠 안」(밴드 FW2 ⓪). 조사는 토막의 끝 글자로 고른다(topicMarker). */
        not_number: (token: string) =>
          `「${token}」${topicMarker(token)} 읽을 수 없어요. 숫자와 ~, 쉼표로 넣어 주세요`,
      },
    },
    /** 「점검 시작」을 눌렀을 때의 사유. 칸마다 그 칸 아래에 보인다(밴드 FW2 ⓪). 쪽 범위 오류는 이미 칸 아래, 글자 없는 PDF 는 위 noText. */
    problems: {
      no_file: 'PDF 파일을 올려 주세요',
      too_many_pages: (pageCount: number, max: number) =>
        `총 ${pageCount}페이지 문서예요. 최대 ${max}페이지까지 점검할 수 있어요`,
      /** 파트는 하나 이상이면 된다(2026-10-16 사용자 결정, 시안 v74). */
      no_parts: '세 파트 가운데 하나 이상에 페이지를 넣어 주세요',
    },
    cancel: '취소',
    start: '점검 시작',
    /** (지은 글) 실행 만들기가 거절됨(밴드 FW2 ①, sid:MARC-ISSUE-99 1). 버튼 위 role="alert" 안내. */
    startRejected: '점검을 시작하지 못했어요. 잠시 뒤 다시 눌러 주세요',
    /**
     * 실행 만들기가 409 IDEMPOTENCY_KEY_REUSED(끊김 뒤 입력을 바꿔 다시 누름 — 앞 요청이 실행을 만들었을 수 있다, sid:MARC-ISSUE-312).
     * 디자인 74 답(10-29): 버튼 위 오류 안내 + [목록 보기]. 두 문장이라 마침표.
     */
    keyReused: {
      message:
        '앞서 누른 점검이 이미 시작됐을 수 있어요. 목록에서 먼저 확인해 주세요.',
      toList: '목록 보기',
    },
  },
  /** 문서 목록(GW-01, 밴드 FW2 ②). 시안 GW-01_r1(v74·v76 같음)의 글. (지은 글) 표시는 시안에 없는 글. */
  list: {
    title: '문서 목록',
    /**
     * 운영 관리자의 제목 줄 meta(GW-01b 머리 — sid:MARC-ENT-409). 회사는 서버가 고른 작업 회사(checks 의 companyName).
     * 고객사 사용자의 설명 줄(회사 · 문서 n건 · 실행 n회 · …)과 운영 관리자 꼴의 셈·안내 조각은 지웠다(사용 한도 상품이 아님 — 시안 댓글, sid:MARC-ENT-603).
     */
    metaOperator: (company: string) => `작업 회사 ${company}`,
    searchLabel: '문서명 검색',
    searchPlaceholder: '문서명 검색',
    yearLabel: '보고연도',
    /** (지은 글) 보고연도를 거르지 않음. */
    yearAll: '보고연도 전체',
    year: (year: number) => `보고연도 ${year}`,
    tabsLabel: '상태',
    tabs: {
      all: '전체',
      running: 'AI 점검 중',
      pending: '검토 대기',
      in_review: '검토 중',
      confirmed: '검토 완료',
      failed: '멈춤',
    },
    mineOnly: '내가 올린 것만',
    newCheck: '새 점검',
    tableLabel: '문서 목록',
    columns: {
      fileName: '문서명',
      reportYear: '보고연도',
      uploadedBy: '담당자',
      pageCount: '페이지 수',
      lastRun: 'AI점검 완료 일자',
      high: 'High',
      mid: 'Mid',
      low: 'Low',
      status: '상태',
      next: '다음 할 일',
    },
    none: '–',
    next: {
      view_progress: '진행 보기',
      rerun: '다시 실행',
      review: '검토하기',
      continue_review: '검토 이어 하기',
      view_result: '결과 보기',
    },
    /** (지은 글) 줄 누르기의 이름(보조기기). */
    rowLabel: (fileName: string, action: string) => `${fileName} — ${action}`,
    rowOpen: {
      result: '결과 요약 열기',
      status: '진행 상태 열기',
    },
    /** 제목 줄 오른쪽 GW-00 링크(시안 GW-01_r2·01b_r1). */
    introLink: '점검 안내',
    notice:
      '점검이 끝나면 검토 대기가 돼요. 문장마다 채택·제외를 고르고 확정하면 결과가 잠기고, 엑셀은 확정본으로 나가요. 실행마다 쓴 AI 사용량을 기록하고, 실행 횟수는 제한하지 않아요.',
    /** (지은 글) 빈 목록(거른 뒤 0건 포함). */
    emptyTitle: '보여 줄 문서가 없어요',
    emptyFiltered: '거르기를 바꾸거나 [새 점검]으로 문서를 올려 주세요',
    /** 목록을 읽지 못함(시안 CM-03 꼴 「{무엇}을 불러오지 못했어요」 + [다시 시도], 밴드 LE1). */
    loadFailed: '문서 목록을 불러오지 못했어요',
    /** (지은 글) 표 스켈레톤 옆 숨긴 글(보조기기). */
    loading: '문서 목록을 불러오는 중이에요',
    /** (지은 글) 목록의 [다시 실행]이 거절됨. */
    rerunRejected: '다시 실행하지 못했어요. 잠시 뒤 다시 눌러 주세요',
    /**
     * (지은 글) 목록의 [다시 실행] 답이 끊겼을 때(runUnreachable) 옆 단추 — 이미 목록이라 디자인 답의 [목록으로] 대신 목록을 새로 읽는다
     * (밴드 GR1, 디자인 확인 전).
     */
    reload: '새로 불러오기',
  },
  /** 결과 요약(GW-04, 밴드 FW2 ③). 시안 GW-04_r1(v74·v76 같음)의 글. (지은 글) 표시는 시안에 없는 글. */
  result: {
    /**
     * 「YYYY-MM-DD HH:mm · n회차 · 139쪽 가운데 44쪽의 문장을 점검 · 검토 n/전체 · 자동 저장됨 14:31」(v115 GW-04_r2 — 「추가 단어 n개」 뺌).
     * 시각을 모르면 앞 토막을 뺀다. savedAt(꾸민 HH:MM)이 없으면(아직 저장 없음·확정) 끝 토막을 뺀다(디자인 답 D2).
     */
    meta: (input: {
      at: string | null;
      ordinal: number | null;
      pageCount: number;
      checked: number;
      reviewed: number | null;
      total: number;
      savedAt?: string | null;
    }) =>
      [
        input.at,
        input.ordinal === null ? null : `${input.ordinal}회차`,
        `총 ${input.pageCount}페이지 가운데 페이지 ${input.checked}개의 문장을 점검`,
        input.reviewed === null ?
          null
        : `검토 ${input.reviewed}/${input.total}`,
        input.savedAt == null ? null : `자동 저장됨 ${input.savedAt}`,
      ]
        .filter((part) => part !== null)
        .join(' · '),
    /** 받기 모달(GW-04a) 파일 줄이 내려받지 못함(디자인 답 D3 — 두 문장이라 마침표). 그 줄 아래 role="alert"(밴드 GDL1). */
    excelFailed: '엑셀을 내려받지 못했어요. 잠시 뒤 다시 눌러 주세요.',
    confirm: '확정',
    continueReview: '검토 이어 하기',
    viewResult: '결과 보기',
    back: '목록으로',
    imageNotice:
      '표의 글자는 근거로 읽지만, 이미지·인포그래픽은 분석하지 않아요. 그래프에만 있는 수치는 「본문에서 확인되지 않음」으로 나올 수 있어요.',
    unconfirmedNotice:
      '아직 확정 전이에요. 지금 내려받는 엑셀에는 「확정 전 결과」라고 표시돼요. 확정하면 채택한 문장만 담긴 확정본이 나가요.',
    /**
     * 인식 실패 페이지 줄(v115 GW-04_r2 파랑 줄 — 밴드 GW2R ② Q7): 「인식 실패 페이지 3개」 + 회색 칩 「31페이지」… + 「이 페이지의 문장은 결과에 없어요」.
     * 판의 둘째 문장 「이 쪽만 다시 점검할 수 있어요.」와 [인식 실패 페이지만 다시 점검]은 서버 계약 전이라 뺀다(sid:MARC-ISSUE-260).
     * 남는 글은 한 문장이라 끝 마침표 없음(디자인 답 D9).
     */
    missedPages: (count: number) => `인식 실패 페이지 ${count}개`,
    missedPage: (page: number) => `${page}페이지`,
    missedNote: '이 페이지의 문장은 결과에 없어요',
    statsLabel: '판정 결과',
    stats: {
      total: '지적된 문장',
      High: '근거 부족·과장 가능성 큼',
      Mid: '근거 일부 확인',
      Low: '선언적 문장',
    },
    sentences: '문장',
    partsHeading: '파트별 결과',
    partsTableLabel: '파트별 결과',
    partColumns: {
      name: '파트',
      pages: '페이지',
      high: 'High',
      mid: 'Mid',
      low: 'Low',
    },
    /** 겹침 셈 안내(시안 글의 앞 두 문장. 셋째 「위 숫자는 … 예시예요」는 시안의 예시 설명이라 옮기지 않았다). 합·전체는 결과에서. */
    partsNote: (sum: number, total: number) =>
      `한 페이지가 두 파트에 들어가면 그 페이지의 문장은 두 파트에 모두 세어요. 파트별 합(${sum})이 전체(${total})보다 클 수 있어요.`,
    termsHeading: '그린워싱 리스크 단어 빈도',
    termsTabsLabel: '단어 범위',
    termsTabs: { total: '문서 전체', parts: '파트별' },
    termsNote: '단순 그린워싱 리스크 가능성이 있는 단어 사용의 빈도예요.',
    extraBadge: '추가',
    extraNote: '추가 배지는 이 점검에서 더한 단어예요.',
    /** (지은 글) 그 범위에 낱말이 없음. */
    termsEmpty: '센 단어가 없어요',
    /** (지은 글) dry-run 결과(items 없음): PageInfo 하나와 단어 빈도만. */
    dryRun:
      '이 실행은 AI 를 부르지 않고 요청 수만 센 시험 실행이에요. 판정한 문장이 없어 단어 빈도만 보여요.',
    /** (지은 글) 결과를 읽는 중 — 스켈레톤의 숨긴 글(보조기기). 제목 줄은 화면 이름 그대로(밴드 LE1). */
    loading: '결과를 불러오는 중이에요',
    /** 없음·꼴 오류·읽기 실패(시안 CM-03, sid:MARC-ENT-260 ③: 사용자에게는 없음과 그 밖 둘만 — invalid 와 failed 는 같은 글). 한 문장 글은 끝 마침표 없음(캔버스 v84, 밴드 LA1 ②). */
    missing: '결과를 찾을 수 없어요',
    invalid: '결과를 불러오지 못했어요',
    failed: '결과를 불러오지 못했어요',
    /** (지은 글) 제목 자리(파일 이름을 모를 때). */
    title: '결과 요약',
  },
  /** 머리 [내려받기] · 받기 모달(GW-04a r1 — 밴드 GDL1, sid:MARC-ENT-662 꼴, 값 band-handoffs/gw-download-values.md). 각주 없음.
   *  닫기·받는 중 이름은 값 파일에 없어 영문번역 받기 모달과 같은 글(발주서 §5). */
  downloads: {
    /** 머리 단추 글 · 모달 머리. */
    title: '내려받기',
    /** 파일 묶음 이름 = 단추 안 파일 이름(확정 전 / 뒤). */
    excel: '점검 결과 엑셀',
    excelConfirmed: '점검 결과 엑셀 · 확정본',
    /** 설명 한 줄(늘 보임, 확정 전·뒤 같음). */
    excelNote: '문장별 판정과 검토 내용, 단어 빈도를 담은 엑셀이에요',
    /** 시험 실행(!isScanResult)일 때 꺼진 줄의 (?) 툴팁. */
    excelMissing: '시험 실행이라 판정한 문장이 없어 만들지 않았어요',
    /** (?) 단추 aria-label 머리(「없는 까닭: <툴팁 글>」). */
    missingLabel: '없는 까닭',
    downloading: '받는 중',
    close: '닫기',
  },
  /** 문장 검토(GW-05·05c, 밴드 FW2 ④). 시안 GW-05_r1·GW-05c_r1(캔버스 v76)의 글. (지은 글) 표시는 시안에 없는 글. */
  reviewScreen: {
    title: '문장 검토',
    /** 제목 아래 meta 「파일명 · n문장」(상태 배지는 제목 줄에 붙인다 — GW-04 와 같은 자리). */
    meta: (fileName: string, total: number) => `${fileName} · ${total}문장`,
    back: '요약으로',
    /** 확정 뒤 제목 줄 [요약으로] 옆(GW-05c — 시안 댓글, sid:MARC-ENT-603). */
    toList: '목록으로 돌아가기',
    confirm: '확정',
    partTabsLabel: '파트',
    partTab: (name: string, count: number) => `${name} ${count}`,
    allParts: '전체',
    levelTabsLabel: '등급',
    levelTabs: {
      all: '전체',
      High: 'High',
      Mid: 'Mid',
      Low: 'Low',
      pending: '미검토',
      excluded: '제외',
    },
    progress: (reviewed: number, total: number) => `검토 ${reviewed}/${total}`,
    /**
     * 「채택 11 · 제외 3 · 미검토 8 · 고친 문장 2 · 자동 저장됨 14:31」(GW-05_r2 :54 — 밴드 G1b-3 ③ 에서 「고친 문장 n」을 더함).
     * savedAt 이 없으면 끝 토막을, edited 가 null 이면 「고친 문장」 토막을 뺀다(확정 뒤 GW-05c_r2 :55 는 「채택 · 제외 · 미검토」만).
     * saving 이면 끝 토막은 「저장하고 있어요」(밴드 GR1 — 디자인 e9 답, sid:MARC-ISSUE-281).
     */
    tally: (
      adopted: number,
      excluded: number,
      pending: number,
      savedAt: string | null = null,
      edited: number | null = null,
      saving = false,
    ) =>
      `채택 ${adopted} · 제외 ${excluded} · 미검토 ${pending}${edited === null ? '' : ` · 고친 문장 ${edited}`}${
        saving ? ' · 저장하고 있어요'
        : savedAt === null ? ''
        : ` · 자동 저장됨 ${savedAt}`
      }`,
    listLabel: '문장 목록',
    /** 줄의 「파트 · n쪽」(근거 쪽이 없으면 「· 근거 없음」). */
    rowMeta: (parts: readonly string[], page: number, noEvidence: boolean) =>
      [parts.join(', '), `${page}페이지`, noEvidence ? '근거 없음' : null]
        .filter((part) => part !== null)
        .join(' · '),
    /** (지은 글) 거른 뒤 문장이 없음. */
    listEmpty: '이 조건에 맞는 문장이 없어요',
    /** 가운데 칸 제목 「n쪽」과 「n / 전체」. */
    pageHeading: (page: number) => `${page}페이지`,
    pageOf: (page: number, total: number) => `${page} / ${total}`,
    prevPage: '이전 페이지',
    nextPage: '다음 페이지',
    /** 쪽 그림의 이름(보조기기). 상자가 있으면 등급을 말한다. */
    pageImage: (page: number, level: string | null) =>
      level === null ?
        `PDF ${page}페이지 미리보기`
      : `PDF ${page}페이지 미리보기, 고른 문장을 ${level} 색 상자로 강조한 페이지`,
    /** (지은 글) 쪽 위 문장 상자 단추의 이름(보조기기 — sid:MARC-ISSUE-341): 쪽 · 등급 · 문장 앞 20 글자. 누르면 그 문장을 고른다. */
    sentenceBox: (page: number, level: string, sentence: string) =>
      `${page}페이지 ${level} 문장: ${sentence.length > 20 ? `${sentence.slice(0, 20)}…` : sentence}`,
    /** (지은 글) 씨앗 문서처럼 PDF 가 없음. 디자인 물을 것. */
    previewUnavailable:
      '미리보기를 열 수 없어요. 문장은 오른쪽에서 확인해 주세요',
    /** (지은 글) PDF 를 여는 중. */
    previewLoading: '미리보기를 여는 중이에요',
    /** 미리보기 칸만 실패(시안 CM-03 cm-cellfail + 작은 [다시 시도]). PDF 읽기·pdf.js 열기·쪽 그리기 실패 모두. */
    previewFailed: '미리보기를 열지 못했어요. 문장은 오른쪽에서 확인해 주세요',
    /**
     * 오른쪽 상세 머리 「참고한 근거 페이지 28, 33」. 문장의 페이지는 가운데 칸 제목·왼쪽 줄에 이미 있어 뺐다(시안 댓글 중복 정보 — sid:MARC-ENT-603).
     * 근거가 없으면 머리에 그리지 않는다(아래 noEvidence 안내가 말한다).
     */
    detailPage: (evidence: readonly number[]) =>
      `참고한 근거 페이지 ${evidence.join(', ')}`,
    noEvidence: '참고한 근거 페이지: 없음 · 근거 조각을 찾지 못했어요',
    evidenceHeading: '근거 확인',
    confirmedInEvidence: '근거에서 확인됨',
    reasonHeading: '판정 사유',
    fixHeading: '수정 방향',
    /** 검토 줄 안내(GW-05_r2 :103 — 밴드 G1b-3 ③ 에서 고침 안내를 이어 붙임). */
    excludeHint:
      '제외하면 사유를 적어야 해요 · 등급·판정 사유·수정 방향은 고친 값으로 엑셀에 담기고, AI 원래 판단도 함께 남아요',
    locked: '확정됨 · 바꿀 수 없음',
    /** 고침(밴드 G1b-3 ③, 글은 GW-05_r2·05c_r2 그대로). */
    edit: {
      /** 고친 칸·고친 문장 줄의 딱지(GW-05_r2 :59·:96). */
      edited: '고침',
      /** 등급 고르기 앞 글과 단추 이름(GW-05_r2 :83). */
      levelLabel: '등급',
      levelPick: '등급 고르기',
      /** 판정 사유·수정 방향의 [고치기](GW-05_r2 :96). */
      start: '고치기',
      /** 고치는 중인 칸 제목 옆(GW-05_r2 :90). */
      editing: '고치는 중 · 칸을 벗어나면 저장돼요',
      /** 고친 칸의 접기 머리 「AI 원래 판단 보기 · 고친 사람 담당자 A · 10-15 14:28」(GW-05_r2 :99). at 은 꾸민 「MM-DD HH:MM」. */
      aiOriginal: (by: string, at: string) =>
        `AI 원래 판단 보기 · 고친 사람 ${by} · ${at}`,
      /** 확정 뒤 고친 칸 제목 옆(GW-05c_r2 :94). */
      lockedNote: '확정해서 잠김 · AI 원래 판단은 엑셀에 함께 담겨요',
      /** 고친 칸 머리 — 고친 뒤 재판단으로 AI 값이 바뀜(GW-05 r4 ③ [초안 글]). 접기 「AI 원래 판단 보기」 안에 새 AI 값. */
      aiChanged: 'AI 판단이 바뀌었어요',
    },
    /** 근거 고치기·재판단(밴드 GRJ1 ③ — 시안 GW-05 r4 ①②④·r5, 글은 [초안 글] 그대로). */
    rejudge: {
      /** 근거 줄의 [지우기]·지운 줄의 [되살리기](r4 ①). */
      remove: '지우기',
      restore: '되살리기',
      /** [+ 근거 더하기] 와 그 칸(r4 ①). */
      addOpen: '근거 더하기',
      addText: '더할 근거',
      addPage: '페이지(골라도 되고 안 골라도 돼요)',
      addNoPage: '고르지 않음',
      pageOption: (page: number) => `${page}페이지`,
      add: '더하기',
      cancel: '취소',
      /** 더한 조각 앞 딱지와 뒤 페이지(r4 ①). */
      addedMark: '직접 더함',
      addedPage: (page: number) => `(${page}페이지)`,
      /** [재판단] 단추·꺼짐 hover·도는 중(r4 ②). */
      button: '재판단',
      buttonRunning: '재판단 중…',
      buttonOff: '근거를 고치면 AI 가 다시 판단할 수 있어요',
      /** 근거 칸 아래 바뀜 한 줄(r4 ②). */
      changed: (removed: number, added: number) =>
        `근거가 바뀌었어요 · 지운 근거 ${removed} · 더한 근거 ${added} — [재판단]을 누르면 AI 가 이 근거로 다시 판단해요`,
      /** 도는 중 카드 머리 아래(r4 ②). */
      running: 'AI 가 바뀐 근거로 다시 판단하고 있어요',
      /** 끝난 뒤 등급 줄 아래 「재판단 · 11-09 14:32 · 담당자 A」(r4 ②). at 은 꾸민 「MM-DD HH:MM」. */
      judged: (at: string, by: string) => `재판단 · ${at} · ${by}`,
      /** 카드 맨 아래 접힘(r4 ② — 첫 판단 하나). */
      firstJudgment: 'AI 첫 판단 보기',
      /** 목록 줄 딱지(r4 ② — 「고침」 옆). */
      rejudgedMark: '재판단',
      /** 실패(r4 ④). */
      failed: '다시 판단하지 못했어요. 앞의 판단은 그대로예요',
      retry: '다시 시도',
      /** 리스크 아님(r5 — 덧붙임 4). */
      nonRisk: '리스크 아님',
      nonRiskNote:
        '재판단 결과 그린워싱 리스크가 아니에요 · 제외로 표시할 수 있어요',
      /** (지은 글) 409 rejudge_running — 그 문장이 이미 다시 판단하는 중. */
      saveRunning: '이미 다시 판단하고 있어요. 끝나면 결과가 보여요',
      /** (지은 글) 409 nothing_to_rejudge — 근거가 마지막 판단 때와 같다. */
      saveNothing: '근거가 마지막 판단 때와 같아서 다시 판단할 것이 없어요',
      /**
       * (감독 결정 글, GRJ1 ④ B1 — 디자인 확인 전) 재판단이 도는 동안 [확정]이 꺼진 까닭 한 줄 · 확정 PUT 의 409 rejudge_running.
       */
      confirmWaits: '재판단이 끝나면 확정할 수 있어요',
    },
    /** 05a 인용 뒤 자리 「기후·환경 30쪽 · Mid」. */
    quoteMeta: (parts: readonly string[], page: number, level: string) =>
      `${parts.join(', ')} ${page}페이지 · ${level}`,
    /** (지은 글) 05a 에서 「기타」를 고르고 설명을 비움. */
    noteRequired: '기타를 고르면 설명을 적어 주세요',
    /** (지은 글) 저장 실패·잠김·꼴 오류. */
    saveRejected: '저장하지 못했어요. 잠시 뒤 다시 눌러 주세요',
    /** 저장이 도는 중에 들어와 받지 않은 [채택]·[제외]·[확정](끌 수 없는 갈래만 — 밴드 GR1, 디자인 e9 답). 잠깐 보이는 알림. */
    saveBusy: '저장 중이에요. 잠시 뒤 다시 눌러 주세요.',
    saveLocked: '이미 확정된 검토라 바꿀 수 없어요',
    saveInvalid: '저장한 검토를 읽을 수 없어요. 화면을 다시 열어 주세요',
    /** (지은 글) 409 run_not_done — 분석이 끝나기 전에 저장을 눌렀다. */
    saveRunNotDone:
      '점검이 아직 끝나지 않아 저장할 수 없어요. 점검이 끝난 뒤 다시 열어 주세요',
    /** (지은 글) 409 no_review — 시험 실행(dry run)이라 검토가 없다. */
    saveNoReview: '시험 실행이라 저장할 검토가 없어요',
    /**
     * 확정 전 다시 읽은 검토가 화면과 다름(밴드 GW1R ③ Q14 — 디자인 답 ③, 두 문장이라 마침표). 05b 의 오류 줄 자리, 옆에 [새로 불러오기].
     */
    saveStale:
      '다른 창에서 검토 내용이 바뀌었어요. 새로 불러온 뒤 다시 확정해 주세요.',
    /** [새로 불러오기] — 검토를 다시 읽어 화면 값을 서버 값으로(디자인 답 ③). */
    reload: '새로 불러오기',
    /** [새로 불러오기]의 다시 읽기가 안 됨(227 디자인 답 ② — 두 문장이라 마침표, GW-05b r2 상태 예시 글 그대로). 05b 의 오류 줄 자리. */
    reloadFailed: '새로 불러오지 못했어요. 잠시 뒤 다시 눌러 주세요.',
    /** 확정하려는데 이미 확정됨(확정 PUT 409 REVIEW_LOCKED·확정 전 읽기가 confirmed). 회색 정보 줄(디자인 답 ② — 잘못이 아니다, 한 문장이라 마침표 없음). */
    alreadyConfirmed: '이미 확정된 점검이에요',
    /** (지은 글) 읽는 중 — 스켈레톤의 숨긴 글(보조기기). 제목 줄은 화면 이름 그대로(밴드 LE1). */
    loading: '문장 검토를 불러오는 중이에요',
    /**
     * 없음·꼴 오류·읽기 실패(시안 CM-03, sid:MARC-ENT-260 ③). 결과와 검토 중 먼저 걸린 쪽(결과가 먼저)의 글이다.
     * invalid 와 failed 는 같은 글.
     */
    missing: {
      result: '결과를 찾을 수 없어요',
      review: '검토를 찾을 수 없어요',
    },
    invalid: {
      result: '결과를 불러오지 못했어요',
      review: '검토를 불러오지 못했어요',
    },
    failed: {
      result: '결과를 불러오지 못했어요',
      review: '검토를 불러오지 못했어요',
    },
  },
  /** 셸(밴드 FW1b ③). 메뉴 여섯·머리 줄 제목·인사는 시안 GW-00·03_r1(v64)의 글. */
  shell: {
    menuLabel: '모듈 메뉴',
    logo: '로고 자리',
    title: '그린워싱 점검',
    greeting: '담당자님 안녕하세요',
    /** 운영 관리자의 인사말과 어드민으로 가는 단추(밴드 SV1 — 디자인 원문, sid:MARC-TICK-72 노트). 어드민 머리의 인사말과 같다. */
    adminGreeting: '운영 관리자님 안녕하세요',
    toAdmin: '관리자 화면',
    /** 목 탭(데모 빌드의 store=mock)의 머리 띠(sid:MARC-ISSUE-227 ① 디자인 답 — 두 문장이라 마침표). */
    demoNotice: '데모 자료예요. 올리거나 확정해도 서버에 저장되지 않아요.',
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
  /** 소개(GW-00). 글은 캔버스 v64 GW-00_r1 그대로. 등급 표의 예시 문장은 보고서 원문 인용 꼴이라 합니다체다. */
  intro: {
    title: '그린워싱 점검',
    aboutHeading: '그린워싱 점검이란',
    about: [
      '지속가능경영보고서를 비롯한 ESG공시 자료에서 환경에 관한 주장 문장을 찾아, 그 주장을 뒷받침하는 근거가 문서 안에 충분한지 살펴요.',
      '근거가 부족하거나 표현이 지나친 문장에는 위험 등급과 사유, 고쳐 쓸 방향을 알려 드려요.',
    ],
    tableLabel: '위험 등급 설명',
    columns: { level: '구분', meaning: '의미', example: '예시' },
    levels: {
      high: {
        meaning: '근거 없이 단정하거나 절대적인 표현을 쓴 주장',
        example: '「모든 제품을 100% 친환경 소재로 만듭니다」',
      },
      mid: {
        meaning:
          '주장은 있으나 수치 · 기준연도 · 범위 같은 근거 일부가 빠진 주장',
        example: '「온실가스 배출량을 크게 줄였습니다」',
      },
      low: {
        meaning: '방향이나 다짐을 밝히는 선언에 가까운 문장',
        example: '「환경 경영을 꾸준히 강화해 나가겠습니다」',
      },
    },
    startHint: '시작하기 버튼을 눌러 점검을 시작해 보세요.',
    /** 단계 띠 목록의 이름은 이 제목을 aria-labelledby 로 가리킨다(디자인 대조 물음 7). */
    processHeading: '점검 과정',
    process: [
      {
        step: 'Step 1',
        name: '파일·페이지 지정',
        body: 'PDF 파일을 올리고 CEO 메시지 · 회사소개 · 기후·환경 파트의 페이지 번호를 넣어요',
      },
      {
        step: 'Step 2',
        name: '문장 찾기·판정',
        body: '페이지마다 환경 주장 문장을 찾아 문서 안의 근거를 보고 등급을 매겨요',
      },
      {
        step: 'Step 3',
        name: '결과 정리·검토',
        body: '등급별 결과와 사유 · 수정 방향을 확인해요',
      },
    ],
    pdfInfo:
      '텍스트 선택이 가능한 PDF 만 점검해요. 이미지·인포그래픽은 분석하지 않아요.',
    start: '시작하기',
  },
  /**
   * 처리 상태(GW-03). 글은 캔버스 v115 GW-03_r3(안 B — 밴드 GW2R ②)과 디자인 답 D1·D4 그대로. 「(지은 글)」은 시안에 없어 러너가 지은 것.
   * 판의 「시안 설명」·「상태 예시」·.then·.g-end 줄은 설명이라 옮기지 않았다.
   */
  status: {
    /** (지은 글) 화면 이름: 불러오는 중·없음일 때의 제목 줄(밴드 LE1 — 틀을 두고 본문 자리만 바꾼다). */
    screenTitle: '처리 상태',
    title: {
      /** (지은 글) 실행 상태를 아직 읽지 못함(sid:MARC-ISSUE-99 7). 밴드 LE1 부터 스켈레톤의 숨긴 글(보조기기). */
      loading: '점검을 불러오는 중이에요',
      running: '점검 중이에요',
      /** 멈춘 실행(r3 「점검이 멈췄어요 · 오류」·「· 스캔본 PDF」 — 「· …」 꼬리는 판의 카드 이름표라 제목에서 뺐다, 추정). */
      failed: '점검이 멈췄어요',
      /** 끝난 실행: 저절로 넘기지 않고 [결과 보기]를 둔다(디자인 대조 C8). */
      done: '점검이 끝났어요',
    },
    /** 「이 창을 닫아도…」 토막은 돌고 있을 때만(멈춤·끝남에는 뺀다, 디자인 대조 고칠 것 1). */
    /** startedAt 은 꾸민 시각(ui 가 ISO 를 꾸민다). 아직 시작 전(null)이면 「시작 대기」(지은 글, 밴드 FW2 ① [N6]). */
    meta: (startedAt: string | null, checkedPages: number, running = true) =>
      `${startedAt === null ? '시작 대기' : `${startedAt} 시작`} · 점검할 페이지 ${checkedPages}개${running ? ' · 이 창을 닫아도 점검은 계속돼요' : ''}`,
    /**
     * 끝남 카드의 이름 아래 줄 「2026-10-15 14:52 끝남 · 22문장을 찾았어요」(r3 끝남 카드 — 밴드 GP4 부터 머리가 아니라 카드). 끝난 때·문장 수를 모르면(결과를 못 읽음·dry-run) 그 토막을 뺀다.
     * 둘 다 모르면 null(카드에 이 줄을 그리지 않는다).
     */
    doneMeta: (finishedAt: string | null, sentences: number | null) => {
      const parts = [
        finishedAt === null ? null : `${finishedAt} 끝남`,
        sentences === null ? null : (
          `${sentences}개의 그린워싱 리스크 문장을 찾았어요`
        ),
      ].filter((part) => part !== null);
      return parts.length === 0 ? null : parts.join(' · ');
    },
    /** 끝남의 파랑 정보 줄 「인식 실패 페이지 3개 (31 · 58 · 70페이지)」(r3 끝남 카드). 쪽은 결과 candidateStats.failedPages 오름차순. */
    failedPages: (pages: readonly number[]) =>
      `인식 실패 페이지 ${pages.length}개 (${pages.join(' · ')}페이지)`,
    back: '목록으로',
    /** 끝난 실행의 GW-04 로 가는 단추(디자인 대조 C8). */
    viewResult: '결과 보기',
    progressHeading: '진행',
    progressLabel: '점검 진행',
    percent: (value: number) => `${value}%`,
    stagesLabel: '처리 단계',
    stages: {
      extract: {
        name: '텍스트 추출',
        /** 끝난 단계의 글(r3). */
        /** 쪽 수를 아직 모르면(null, 밴드 FW2 ① [R5]) 「문서에서」(지은 글). */
        body: (pageCount: number | null) =>
          `${pageCount === null ? '문서' : `총 ${pageCount}페이지`}에서 텍스트를 추출해 근거로 찾을 수 있게 정리했어요`,
        /** 진행 중·대기·멈춤의 글(디자인 대조 고칠 것 2). 끝난 글에 맞춘 지은 글(초안 — 판은 끝난 글만 보인다). */
        bodyPending: (pageCount: number | null) =>
          `${pageCount === null ? '문서' : `총 ${pageCount}페이지`}에서 텍스트를 추출해 근거로 찾을 수 있게 정리해요`,
      },
      judge: {
        name: '문장 찾기·판정',
        body: (done: number, total: number) =>
          `지정한 페이지마다 환경 주장 문장을 골라 근거를 보고 High · Mid · Low 를 매겨요 · ${done} / ${total}페이지`,
      },
      summarize: {
        name: '정리',
        /** 시안 v76(발주서 덧붙임 2: 문장 위치는 pdfium 으로 찾는다 — 덧붙임 1). */
        body: '그린워싱 리스크 단어 빈도를 세고, 그린워싱 리스크 문장의 위치를 찾아 결과를 묶어요',
      },
    },
    stageState: {
      done: '완료',
      now: '진행 중',
      todo: '대기',
      /** (지은 글) */
      failed: '멈춤',
    },
    /** 실행 전체 실패(일반 멈춤)의 안내(r3 「멈춤 · 오류」 카드). 쪽 하나의 실패는 실행 실패가 아니다(결과 화면이 알린다). */
    failure:
      '점검을 끝내지 못했어요. [다시 실행]을 누르면 같은 파일로 처음부터 다시 점검해요.',
    /** 서비스 설정(키·공급사)이 없어 멈춘 실행(errorCode setup_error — 디자인 답 D1, 가정). 단추는 [목록으로]만. */
    setupFailure:
      '서비스 설정 문제로 점검을 시작하지 못했어요. 운영 관리자에게 알려 주세요.',
    /** 같은 문서·같은 입력으로 처음부터 도는 새 실행(실패한 실행에만). */
    rerun: '다시 실행',
    /** (지은 글) [다시 실행]이 거절됨(밴드 FW2 ①, sid:MARC-ISSUE-99 1). */
    rerunRejected: '다시 실행하지 못했어요. 잠시 뒤 다시 눌러 주세요',
    /** 없는 실행(시안 CM-03 꼴, 밴드 LE1). */
    missing: '점검을 찾을 수 없어요',
    /** 상태를 읽지 못함(CM-03 「{무엇}을 불러오지 못했어요」 + [다시 시도][목록으로] — 디자인 답, 밴드 GW1R. 한 문장이라 끝 마침표 없음). */
    loadFailed: '점검 상태를 불러오지 못했어요',
    /**
     * 글자 층이 없는 PDF 로 멈춘 실행(errorCode no_text_layer — 디자인 원문 v101, v115 GW-03 r3 「멈춤 · 스캔본 PDF」). 안내 글은 GW-02a 글 그대로
     * (newCheck.upload.noText), 단추는 [다시 실행] 대신 [새 점검], 파일 줄(안내 위 — 228 S2)은 이름 + 회색 「24쪽 · 텍스트 없음」(쪽 수를 모르면 「텍스트 없음」만).
     */
    noText: {
      fileMeta: (pageCount: number | null) =>
        pageCount === null ? '텍스트 없음' : (
          `총 ${pageCount}페이지 · 텍스트 없음`
        ),
      newCheck: '새 점검',
    },
  },
} as const;

/** 이름 이음: 「A」, 「A와 B」, 「A, B와 C」(와/과는 앞 글자 받침으로). */
function joinNames(names: readonly string[]): string {
  if (names.length <= 1) return names.join('');
  const head = names.slice(0, -1).join(', ');
  return `${withAnd(head)} ${names[names.length - 1]}`;
}

/** 주제 조사 은/는: 끝 글자가 한글이면 받침으로, 숫자면 읽는 소리(영·일·삼·육·칠·팔은 받침)로, 그 밖은 「은(는)」. */
function topicMarker(word: string): string {
  const last = word.charCodeAt(word.length - 1);
  if (last >= 0xac00 && last <= 0xd7a3)
    return (last - 0xac00) % 28 !== 0 ? '은' : '는';
  const char = word[word.length - 1] ?? '';
  if (/[0-9]/.test(char)) return '013678'.includes(char) ? '은' : '는';
  return '은(는)';
}

/** 이름 뒤에 와/과(받침 있으면 과). 한글이 아니면 「와」. */
function withAnd(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  const hangul = last >= 0xac00 && last <= 0xd7a3;
  return `${name}${hangul && (last - 0xac00) % 28 !== 0 ? '과' : '와'}`;
}

export type GwText = typeof GW_TEXT;

/** 문구 표의 글자 꼴을 넓힌다(as const 의 글자 그대로 타입 → string). 부품의 text prop 이 바꿀 문구를 받을 때 쓴다. */
export type Wording<T> =
  T extends string ? string
  : T extends (...args: infer A) => string ? (...args: A) => string
  : T extends readonly string[] ? readonly string[]
  : { [K in keyof T]: Wording<T[K]> };
