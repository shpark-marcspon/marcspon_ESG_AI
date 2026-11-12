// AD-02 AI 설정 껍데기의 문구 표(밴드 AD2W — 모듈 공통). 부품 안에는 한국어 글자를 박지 않고 여기 한 곳에 둔다. 이 파일은 아무것도 가져오지 않는다.
// 출처: 디자인 판 AD-02_r3(캔버스 v127 — 사본 band-handoffs/AD2W-design-r3.md, 판이 정본). 말투는 해요체, 한 문장 글은 끝 마침표 뺌,
//   두 문장 이상은 마침표 둠(sid:MARC-ENT-269). 칸 이름·기본 글·메모·고정 값은 서버 글이라 여기 두지 않는다(sid:MARC-ENT-384).
// 옛 목 화면의 글(판정 기준 표·의심 단어·처리 값 고침·예시 데이터 띠 등)은 걷었다(sid:MARC-ISSUE-278). 그린워싱 실서버 판에서 옮긴 일반 글
//   (적용 창·더 보기·기본 판 배지·준비 중·만든 사람 모름)은 낱말 그대로 — 적용 창의 조사만 판대로(「v2 로」).
// 초안(판에 없는 글 — 디자인 확인 거리, 발주서 Q7): 아래 「초안」 주석이 붙은 글.

export const AI_SETTING_TEXT = {
  /** 머리 제목(모듈 이름). */
  title: (module: string) => `AI 설정 — ${module}`,
  /** 두 문장 — 끝 마침표 둠(r3). */
  description:
    '적용 중인 버전은 하나예요. 구성과 단계를 오가며 고친 것은 [새 버전으로 저장] 한 번에 새 버전 하나로 남고, [이 버전 적용]을 눌러야 다음 실행부터 쓰여요.',
  apply: '이 버전 적용',
  /** [이 버전 적용] 곁 글 — 고친 것이 있는 동안(r3). */
  applyAfterSave: '저장한 뒤에 적용할 수 있어요',
  columns: { version: '버전', component: '구성', category: '단계 — 프롬프트' },
  /** 판 열 첫 줄과 곁 글(r3). */
  newVersion: '이 버전을 바탕으로 새 버전',
  newVersionNote: '고치지 않고 그대로 새 버전으로 복제해요(이름 창이 떠요)',
  /** 배지(r3 — 「시험 중」은 「초안」으로, 발주서 Q10). 기본 판이 적용 중이 아니면 「기본」. */
  status: {
    testing: '초안',
    applied: '적용 중',
    past: '지난 버전',
    default: '기본',
  },
  /** 기본 판 줄 꼬리(r3). */
  defaultSum: '번호 없음 · 처음부터 있는 설정',
  /** 고치는 중인 바탕 줄 꼬리(r3). */
  editingSum: (version: string) => `${version} 바탕으로 고치는 중`,
  /** 판 열 끝 — 서버 total 이 실린 수보다 많을 때(초안 — 그린워싱 실서버 판에서 옮김). */
  more: '더 보기',
  /** 구성 열(r3 차례 — 모델 설정 · 프롬프트 · 모듈 줄 · 고정 값 · 읽기 전용 규칙). */
  components: {
    model: '모델 설정',
    prompt: '프롬프트',
    /** 모델 칸 하나(AD6 — 칸이 둘 이상인데 모델이 다 같으면 modelSlots). */
    modelOne: '모든 단계에 하나',
    /** 모델 칸 둘 이상 · 모두 같은 모델(AD6, sid:MARC-ISSUE-515). */
    modelSlots: (n: number) => `${n}칸`,
    modelMany: (first: string) => `${first} · 단계마다 다름`,
    /** 프롬프트 꼬리(AD6 — 시안 꼴 「<단계 수>단계 · <칸 수>칸」. 프롬프트는 고칠 수 있어 「고정」을 뺐다). */
    promptFixed: (steps: number, prompts: number) =>
      `${steps}단계 · ${prompts}칸`,
    /** 초안: r3 은 파트 「3개 · 고정」·처리 값 「6항목 · 고정」 — 묶음마다 낱말이 달라 「개」 하나로. */
    fixedSum: (n: number) => `${n}개 · 고정`,
    edited: (n: number) => `고침 ${n}`,
  },
  pending: '이 구성의 상세 화면은 준비 중이에요',
  pendingSum: '준비 중',
  /** 읽기 전용 규칙 줄의 구성 열 이름·꼬리(r3). 카드 머리·꼬리·줄 글은 모듈이 넘긴다(AS3b K9 — 그린워싱 글은 그 모듈 글 표로). */
  codeRules: {
    label: '고정 규칙',
    sum: '읽기 전용',
  },
  /** 고정 값 카드 곁 글(r3). */
  fixedNote: '고정 값이라 바꿀 수 없어요',
  fixedTitle: (label: string) => `${label} · 고정`,
  /** 값 없는 항목·빈 칸. */
  none: '–',
  model: {
    title: '모델 설정',
    /** 모델 칸이 둘 이상일 때 칸 줄 아래 — 그 칸이 받는 묶음 이름들(e9 Q2 (가) — 「 · 」 이음, 「에」 앞 띄어쓰기 없음). */
    uses: (groups: readonly string[]) => `${groups.join(' · ')}에 쓰여요`,
    route: '모델',
    temperature: 'temperature',
    maxOutputTokens: '출력 상한 토큰',
    /** 초안: 범위 밖. */
    temperatureRange: '0~2 사이로 입력해 주세요',
    maxOutputRange: (max: number) => `1~${max} 사이의 정수로 입력해 주세요`,
  },
  prompt: {
    /** 상세 카드 머리(판 이름 — 저장 판은 번호, 기본 판은 이름). */
    title: (version: string) => `프롬프트 — ${version}`,
    basedOn: (version: string) => `${version} 바탕 · 저장 전`,
    /** 두 문장 — 마침표 둠(r3). */
    notice: (applied: string) =>
      `고친 것은 위 [새 버전으로 저장]으로 다른 구성의 고침과 함께 새 버전 하나로 남아요. 적용 중인 ${applied} 는 바뀌지 않아요.`,
    /** 칸 고름 줄(「1. 판정」). */
    slot: (index: number, label: string) => `${index}. ${label}`,
    /** 단계 카드 라벨 칸(시안 v148 「단계 · 프롬프트 · 메모」). */
    stepLabel: '단계',
    text: '프롬프트',
    /** 두 문장 — 마침표 둠(r3). */
    outputNote:
      '[출력(JSON …)]으로 시작하는 절은 결과를 읽는 형식이에요. 이 절을 고치면 결과를 읽지 못할 수 있어요.',
    untouched: '처음 받은 글 그대로 · 글 전체를 고칠 수 있어요',
    memo: '메모',
    memoNote: '이 프롬프트의 설명이나 고친 이유 · 이 버전에 함께 남아요',
    edited: '고침 · 저장 전',
    /** 초안: 출력절이 글에 없을 때. */
    outputLost: '출력 형식 절이 처음 글과 달라요 · 결과를 읽지 못할 수 있어요',
    /** 초안: 글자 수 줄. */
    count: (n: number, max: number) => `${n} / ${max}자`,
    /** 초안: 넘침. */
    over: (max: number) => `${max}자까지 쓸 수 있어요`,
    /** 초안: 빈 글(서버 문장과 같은 뜻). */
    empty: '프롬프트 글을 넣어 주세요',
    /** cd 답(10-22 저녁): 칸 고름 줄에서 서버가 짚은 칸의 표시(오류 빨강 글 + 점 — 마크스폰의 시안 상태 이름 「확인필요」와 섞이지 않게). */
    slotError: '고칠 곳 있음',
  },
  /** 저장 막대(r3). */
  saveBar: {
    count: (n: number) => `고친 것 ${n}개 · 아직 저장 전이에요`,
    revert: '되돌리기',
    save: '새 버전으로 저장',
  },
  /** 저장 모달(r3 ① ②). */
  save: {
    title: '새 버전으로 저장할까요?',
    /** 두 문장 — 마침표 둠. base = 「v3 를」 자리(기본 판은 「기본 설정을」). */
    body: (base: string, n: number, applied: string) =>
      `${base} 바탕으로 고친 것 ${n}개가 새 버전으로 남아요. 적용 중인 ${applied} 는 바뀌지 않아요.`,
    /** 초안: 복제(고친 것 0). */
    copyBody: (base: string, applied: string) =>
      `${base} 고치지 않고 그대로 새 버전으로 남겨요. 적용 중인 ${applied} 는 바뀌지 않아요.`,
    changes: '고친 것',
    number: '버전 번호',
    numberNote: '자동으로 붙어요',
    name: '버전 이름',
    nameNote: '1~40자 · 같은 이름도 쓸 수 있어요',
    nameEmpty: '버전 이름을 적어야 저장할 수 있어요 · 1~40자',
    /** 초안. */
    nameOver: '버전 이름은 40자까지예요',
    memo: '버전 메모',
    memoNote: '적지 않아도 돼요 · 200자까지',
    /** 초안. */
    memoOver: '200자까지 쓸 수 있어요',
    cancel: '취소',
    confirm: '저장',
    /** r3 ③ 저장 실패(두 문장 — 마침표 둠). 토스트 대신 모달 안 빨강 줄(발주서 Q6). */
    failed: '새 버전을 저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.',
    /** 초안: 모델 거절·칸 거절 줄. */
    modelRefused: (message: string) => `모델 설정 — ${message}`,
    fieldRefused: (label: string, message: string) => `${label} — ${message}`,
    /** cd 답(10-22 저녁): 저장은 됐는데 목록 다시 읽기만 실패 — 정보 띠(두 문장 — 마침표 둠) + [다시 시도]. */
    listFailed: (version: string) =>
      `${version} 을 저장했어요. 버전 목록을 다시 불러오지 못했어요.`,
    /** r3 ④ 저장 뒤 알림(두 문장 — 마침표 둠). */
    done: (version: string) =>
      `${version} 를 저장했어요. 쓰려면 [이 버전 적용]을 눌러요.`,
  },
  /** 「고친 것」 줄의 낱말(프롬프트 칸은 칸 고름 줄 꼴 「2. 칸 이름」 — prompt.slot). */
  changed: {
    model: '모델 설정',
    join: ' · ',
    /** 모델 칸·묶음이 여럿일 때 목록 항목(e9 덧·N3): 모델 칸 「모델 설정 · <칸>」, 프롬프트 「<묶음 순번>. <묶음> · <칸>」. */
    slotModel: (slot: string) => `모델 설정 · ${slot}`,
    slotPrompt: (n: number, group: string, slot: string) =>
      `${n}. ${group} · ${slot}`,
  },
  /** 바탕 판을 부르는 글(「v3 를」·「기본 설정을」). */
  baseName: (version: string, isDefault: boolean) =>
    isDefault ? `${version}을` : `${version} 를`,
  /** 되돌리기 모달(r3 ⑤). */
  revert: {
    title: (n: number) => `고친 것 ${n}개를 되돌릴까요?`,
    body: (version: string) =>
      `저장하지 않은 고침이 모두 사라지고 ${version} 그대로 돌아가요.`,
    cancel: '취소',
    confirm: '되돌리기',
  },
  /** 나가기 모달(r3 ⑥). */
  leave: {
    title: '저장하지 않고 나갈까요?',
    body: '저장하지 않은 고침이 있어요. 나가면 고친 내용이 사라져요.',
    cancel: '취소',
    confirm: '나가기',
  },
  /** 적용 확인 창(r3 ⑦ — 그린워싱 실서버 판에서 옮김). 기본 판이면 이름 자리에 「기본 버전」. */
  applyDialog: {
    defaultName: '기본 버전',
    title: (name: string) => `${name} 을 적용할까요?`,
    /** 두 문장 — 마침표 둠. */
    body: (name: string, current: string) =>
      `다음 실행부터 ${name} 을 써요. 이미 돌고 있는 실행은 ${current} 로 끝나요.`,
    cancel: '취소',
    confirm: '적용',
    /** 적용 뒤 알림(두 문장 — 마침표 둠). */
    done: (name: string) =>
      `${name} 을 적용했어요. 다음 실행부터 ${name} 을 써요.`,
    /** 창 안 오류 줄(두 문장). */
    failed: '적용하지 못했어요. 다시 눌러 주세요.',
  },
  /** 만든 사람 이름을 못 풂(초안 — 옮김). */
  unknownAuthor: '알 수 없는 사람',
  emptyMemo: '–',
  loading: 'AI 설정을 불러오는 중',
  failed: 'AI 설정을 불러오지 못했어요',
  retry: '다시 시도',
} as const;
