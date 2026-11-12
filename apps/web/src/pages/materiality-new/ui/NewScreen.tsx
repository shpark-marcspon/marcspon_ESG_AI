// IR-02 새 평가(밴드 IRW2 ② — 시안 v166 IR-02_r1, 부록 A2·A3·A4·A6. 데이터 검증 DV-02 NewScreen 꼴을 옮겨 지음, 가져오지 않는다).
//   머리 「새 평가」 → IroFlow 단계 1 → 카드 셋(「1. 기업과 산업」 — 산업 분류 아래 업종 구분(IRW17)·가치사슬 활동 (선택) 포함 /
//   「2. 중대 토픽 (Short-list)」 / 「3. 리서치 조건」) → [취소]·[평가 시작]. 처음 꼴은 A6-⑪(판 예시 값은 싣지 않는다). 라우터를 모른다 — 저장소와 콜백 props.
// 상태(넣은 값)는 이 화면 안, 셈·해석·검사·input 짓기는 entities/materiality/model(draftProblems·buildInput — 부록 A3·A4).
// [평가 시작]: 검사 → 칸마다 알리고 첫 오류 칸으로 초점(넣은 값 그대로, 접힌 토픽은 펼침) → 통과면 store.createRun(input) 한 번
//   (두 번 눌러도 — ref) → started 면 onStarted(runId)(경로가 IR-03 으로 replace) · 거절·끊김은 판 「평가를 시작하지 못했어요…」
//   (서버 message 0). 기다리는 동안 단추 끔. 실패 뒤 같은 입력으로 다시 누르면 저장소가 같은 열쇠를 싣는다. 운영 관리자도 같은 화면.
// 칸 오류는 [평가 시작]을 누른 뒤부터 보이고, 고치면 그 자리에서 사라진다(검사를 그릴 때마다 다시 한다).
// 화면을 떠나면 저장소의 열쇠를 버린다(store.forget).
// 떠나기 경고(밴드 IRW15 ④ — 결정 MARC-ENT-668): 넣은 값이 처음 꼴과 다르면(토픽·서브토픽 카드 key 는 빼고 견줌) onDirtyChange(true).
//   IRW17: 가치사슬 칸이 쥔 것(붙여 넣기 글 · 파일 줄 — 실패 줄 포함)이 있어도 true(ValueChainField onDirtyChange 로 올림).
//   [평가 시작] 요청을 기다리는 동안은 false(막지 않는다). 경로 이동은 NewRoute 의 useBlocker 가 막고 leave 로 묻는다 — 창은 이 화면이 그린다.
// 「최신 이슈 반영」 토글은 IRW15 ③ 에서 뺐다(요청은 늘 false — model buildInput).
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { PlusIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import {
  RadioGroup,
  RadioGroupItem,
} from '@marcspon/ui/components/radio-group';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import type { MaterialityStore } from '../../../entities/materiality/api/index.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import {
  STANDARDS,
  blankTopic,
  buildInput,
  draftProblems,
  filledSubtopics,
  initialDraft,
} from '../../../entities/materiality/model/index.ts';
import type {
  DraftProblem,
  RunDraft,
  Sector,
  Standard,
  TopicDraft,
} from '../../../entities/materiality/model/index.ts';
import { IroFlow } from '../../../entities/materiality/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { Card, PageTitle } from '../../../shared/ui/card/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { RequiredMark } from '../../../shared/ui/required-mark/index.ts';
import { FieldError } from './FieldError.tsx';
import { LeaveDialog } from './LeaveDialog.tsx';
import { TopicCard } from './TopicCard.tsx';
import type { TopicErrors } from './TopicCard.tsx';
import { ValueChainField } from './ValueChainField.tsx';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from './formRows.ts';

const words = IR_TEXT.newRun;
const required = words.required;
const research = words.research;

export interface NewScreenProps {
  store: MaterialityStore;
  /** 지금(시작일 검사의 서울 오늘). 기본 new Date(). */
  now?: () => Date;
  onCancel(): void;
  onStarted(runId: string): void;
  /** 넣은 값이 처음 꼴과 다른가(시작 요청을 기다리는 동안은 false) — 바뀔 때마다. */
  onDirtyChange?(dirty: boolean): void;
  /** 경로 이동이 막혀 묻는 중(NewRoute 의 useBlocker). pending 이면 나가기 창. */
  leave?: { pending: boolean; proceed(): void; reset(): void };
}

/** 견줄 꼴 — 화면이 준 카드 key 를 뺀 넣은 값. */
const draftShape = (draft: RunDraft) =>
  JSON.stringify(draft, (name, value: unknown) =>
    name === 'key' ? undefined : value,
  );

/** 검사 하나 → 그 칸의 id 끝(첫 오류 칸 초점). */
function focusKey(problem: DraftProblem, draft: RunDraft): string | null {
  switch (problem.field) {
    case 'company':
      return 'company';
    case 'industry':
      return `industry-${problem.standard}`;
    case 'stage':
      return `stage-${problem.rows[0]! - 1}`;
    case 'topics':
      return 'add-topic';
    case 'topic':
      return `topic-${draft.topics[problem.index]!.key}`;
    case 'subtopics':
      return `subs-${draft.topics[problem.index]!.key}`;
    case 'subtopic':
      return `sub-${draft.topics[problem.index]!.subtopics[problem.sub]!.key}`;
    case 'geoScope':
      return 'geo';
    case 'startDate':
      return 'start-date';
    case 'size':
      return null;
  }
}

/** 오류가 든 토픽 카드 차례. */
const topicIndexOf = (problem: DraftProblem) =>
  (
    problem.field === 'topic' ||
    problem.field === 'subtopics' ||
    problem.field === 'subtopic'
  ) ?
    problem.index
  : null;

export function NewScreen({
  store,
  now = () => new Date(),
  onCancel,
  onStarted,
  onDirtyChange,
  leave,
}: NewScreenProps) {
  const ids = useId();
  const keys = useRef(0);
  const nextKey = () => (keys.current += 1);
  const [draft, setDraft] = useState<RunDraft>(() =>
    initialDraft(research.geoScopeDefault, blankTopic(nextKey(), nextKey())),
  );
  /** 펼친 토픽 카드의 key. */
  const [open, setOpen] = useState<ReadonlySet<number>>(
    () => new Set([draft.topics[0]!.key]),
  );
  const [tried, setTried] = useState(false);
  const [starting, setStarting] = useState(false);
  const startingRef = useRef(false);
  const [startFailed, setStartFailed] = useState(false);
  const [focusTo, setFocusTo] = useState<{ id: string } | null>(null);
  /** 처음 꼴(견줄 꼴). */
  const [initialShape] = useState(() => draftShape(draft));
  const changed = useMemo(
    () => draftShape(draft) !== initialShape,
    [draft, initialShape],
  );
  /** 가치사슬 칸이 행 밖에 쥔 것(붙여 넣기 글 · 파일 줄). */
  const [valueChainHeld, setValueChainHeld] = useState(false);
  const dirty = (changed || valueChainHeld) && !starting;
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  // 첫 오류 칸 초점은 칸 글이 깔리고 접힌 카드가 펼쳐진 그리기 뒤에 옮긴다(누를 때마다 한 번 — 새 객체).
  useEffect(() => {
    if (focusTo !== null) document.getElementById(focusTo.id)?.focus();
  }, [focusTo]);
  // 화면을 떠나면 쥔 열쇠를 버린다.
  useEffect(() => () => store.forget(), [store]);

  const problems = tried ? draftProblems(draft, now()) : [];
  const has = (match: (problem: DraftProblem) => boolean) =>
    problems.some(match);
  const industryProblem = (standard: Standard) =>
    problems.find(
      (problem) =>
        problem.field === 'industry' && problem.standard === standard,
    ) as Extract<DraftProblem, { field: 'industry' }> | undefined;
  const startProblem = problems.find(
    (problem) => problem.field === 'startDate',
  ) as Extract<DraftProblem, { field: 'startDate' }> | undefined;
  const topicErrors = (index: number): TopicErrors => {
    const name = problems.find(
      (problem) => problem.field === 'topic' && problem.index === index,
    ) as Extract<DraftProblem, { field: 'topic' }> | undefined;
    return {
      name: name?.code,
      subtopics: has(
        (problem) => problem.field === 'subtopics' && problem.index === index,
      ),
      subNames: problems.flatMap((problem) =>
        problem.field === 'subtopic' && problem.index === index ?
          [draft.topics[index]!.subtopics[problem.sub]!.key]
        : [],
      ),
    };
  };

  const edit = (patch: Partial<RunDraft>) => {
    setDraft((prev) => ({ ...prev, ...patch }));
    setStartFailed(false);
  };
  const setTopic = (key: number, topic: TopicDraft) =>
    edit({
      topics: draft.topics.map((each) => (each.key === key ? topic : each)),
    });
  const setIndustry = (
    standard: Standard,
    patch: Partial<RunDraft['industries'][Standard]>,
  ) =>
    edit({
      industries: {
        ...draft.industries,
        [standard]: { ...draft.industries[standard], ...patch },
      },
    });

  const addTopic = () => {
    const topic = blankTopic(nextKey(), nextKey());
    edit({ topics: [...draft.topics, topic] });
    // 새 카드만 펼친다(판 — 앞 카드는 「서브토픽 n개 · 펼치기」로 접힘).
    setOpen(new Set([topic.key]));
  };

  const start = () => {
    if (startingRef.current) return;
    const found = draftProblems(draft, now());
    if (found.length > 0) {
      setTried(true);
      setStartFailed(false);
      const withErrors = found.flatMap((problem) => {
        const index = topicIndexOf(problem);
        return index === null ? [] : [draft.topics[index]!.key];
      });
      if (withErrors.length > 0) setOpen(new Set([...open, ...withErrors]));
      const target = found
        .map((problem) => focusKey(problem, draft))
        .find((key) => key !== null);
      if (target) setFocusTo({ id: `${ids}-${target}` });
      return;
    }
    startingRef.current = true;
    setStarting(true);
    setStartFailed(false);
    const done = () => {
      startingRef.current = false;
      setStarting(false);
    };
    store.createRun(buildInput(draft)).then(
      (result) => {
        done();
        if (result.kind === 'started') onStarted(result.runId);
        else setStartFailed(true);
      },
      () => {
        done();
        setStartFailed(true);
      },
    );
  };

  const subtopicTotal = draft.topics.reduce(
    (sum, topic) => sum + filledSubtopics(topic).length,
    0,
  );

  return (
    <div data-screen="materiality-new" className="flex flex-col gap-6">
      <PageTitle title={words.title} description={words.lead} />
      <IroFlow current={1} />

      <Card className="flex flex-col gap-4" data-card="company">
        <Heading>{words.company.title}</Heading>
        <div className={FORM_ROWS_CLASS}>
          <div className={FORM_ROW_CLASS}>
            <label htmlFor={`${ids}-company`} className={FORM_LABEL_CLASS}>
              {words.company.name}
              <RequiredMark />
            </label>
            <div
              className={cn(
                FORM_VALUE_CLASS,
                'flex-col justify-center gap-1.5',
              )}
            >
              <Input
                id={`${ids}-company`}
                value={draft.company}
                aria-required
                disabled={starting}
                aria-invalid={has((p) => p.field === 'company') || undefined}
                aria-describedby={
                  has((p) => p.field === 'company') ?
                    `${ids}-company-error`
                  : undefined
                }
                onChange={(event) => edit({ company: event.target.value })}
                className={cn(
                  'w-1/2',
                  has((p) => p.field === 'company') && 'border-support-error',
                )}
              />
              {has((p) => p.field === 'company') && (
                <FieldError id={`${ids}-company-error`}>
                  {required.company}
                </FieldError>
              )}
            </div>
          </div>
          {STANDARDS.map((standard) => {
            const problem = industryProblem(standard);
            const id = `${ids}-industry-${standard}`;
            return (
              <div key={standard} className={FORM_ROW_CLASS}>
                <label htmlFor={id} className={FORM_LABEL_CLASS}>
                  {standard}
                  {standard === 'SASB' && <RequiredMark />}
                </label>
                <div
                  className={cn(
                    FORM_VALUE_CLASS,
                    'flex-col justify-center gap-1.5',
                  )}
                >
                  <Input
                    id={id}
                    aria-label={words.company.industryName(standard)}
                    aria-required={standard === 'SASB' || undefined}
                    value={draft.industries[standard].name}
                    disabled={starting}
                    aria-invalid={problem !== undefined || undefined}
                    aria-describedby={problem ? `${id}-error` : undefined}
                    onChange={(event) =>
                      setIndustry(standard, { name: event.target.value })
                    }
                    className={cn(problem && 'border-support-error')}
                  />
                  {problem && (
                    <FieldError id={`${id}-error`}>
                      {problem.code === 'required' ?
                        required.sasb
                      : required.descriptionOnly(standard)}
                    </FieldError>
                  )}
                  <Textarea
                    aria-label={words.company.industryDescription(standard)}
                    placeholder={words.company.industryPlaceholder}
                    value={draft.industries[standard].description}
                    disabled={starting}
                    onChange={(event) =>
                      setIndustry(standard, { description: event.target.value })
                    }
                    rows={2}
                  />
                  {standard === 'SASB' && (
                    <Note testId="industry-example">
                      {words.company.industryExample}
                    </Note>
                  )}
                </div>
              </div>
            );
          })}
          {/* 업종 구분은 산업 분류 칸들 바로 아래(IRW17 — 댓글 eb6298ea, 같은 draft.sector) */}
          <div className={FORM_ROW_CLASS}>
            <span id={`${ids}-sector`} className={FORM_LABEL_CLASS}>
              {research.sector}
              <RequiredMark />
            </span>
            <div className={cn(FORM_VALUE_CLASS, 'items-center gap-4')}>
              <RadioGroup
                aria-labelledby={`${ids}-sector`}
                value={draft.sector}
                disabled={starting}
                onValueChange={(value) => edit({ sector: value as Sector })}
                className="flex items-center gap-4"
              >
                {(['non_financial', 'financial'] as const).map((sector) => (
                  <label
                    key={sector}
                    className="flex items-center gap-2 text-style-pre-body-06 text-text-secondary"
                  >
                    <RadioGroupItem value={sector} />
                    {IR_TEXT.sector[sector]}
                  </label>
                ))}
              </RadioGroup>
              <Note>{research.sectorHint}</Note>
            </div>
          </div>
          <div className={FORM_ROW_CLASS}>
            <span className={FORM_LABEL_CLASS}>{words.valueChain.title}</span>
            <div className={cn(FORM_VALUE_CLASS, 'flex-col')}>
              <ValueChainField
                store={store}
                rows={draft.valueChain}
                onRows={(valueChain) => edit({ valueChain })}
                tried={tried}
                idBase={ids}
                disabled={starting}
                onDirtyChange={setValueChainHeld}
              />
            </div>
          </div>
        </div>
        <Note>{words.company.industryHint}</Note>
      </Card>

      <Card className="flex flex-col gap-4" data-card="topics">
        <div className="flex items-center justify-between gap-3">
          <Heading>{words.topics.title}</Heading>
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.topics.count(draft.topics.length, subtopicTotal)}
          </span>
        </div>
        {draft.topics.map((topic, index) => (
          <TopicCard
            key={topic.key}
            topic={topic}
            order={index + 1}
            open={open.has(topic.key)}
            errors={topicErrors(index)}
            idBase={ids}
            disabled={starting}
            onChange={(next) => setTopic(topic.key, next)}
            onRemove={() =>
              edit({
                topics: draft.topics.filter((each) => each.key !== topic.key),
              })
            }
            onOpen={() => setOpen(new Set([...open, topic.key]))}
            newKey={nextKey}
          />
        ))}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            id={`${ids}-add-topic`}
            variant="outlineGrey"
            disabled={starting}
            aria-describedby={
              has((p) => p.field === 'topics') ?
                `${ids}-topics-error`
              : undefined
            }
            onClick={addTopic}
          >
            <PlusIcon aria-hidden />
            {words.topics.add}
          </Button>
          <Note>{words.topics.hint}</Note>
        </div>
        {has((p) => p.field === 'topics') && (
          <FieldError id={`${ids}-topics-error`}>{required.topics}</FieldError>
        )}
      </Card>

      <Card className="flex flex-col gap-4" data-card="research">
        <Heading>{research.title}</Heading>
        <div className={FORM_ROWS_CLASS}>
          <div className={FORM_ROW_CLASS}>
            <label htmlFor={`${ids}-geo`} className={FORM_LABEL_CLASS}>
              {research.geoScope}
              <RequiredMark />
            </label>
            <div
              className={cn(
                FORM_VALUE_CLASS,
                'flex-col justify-center gap-1.5',
              )}
            >
              <div className="flex items-center gap-2">
                <Input
                  id={`${ids}-geo`}
                  value={draft.geoScope}
                  aria-required
                  disabled={starting}
                  aria-invalid={has((p) => p.field === 'geoScope') || undefined}
                  aria-describedby={
                    has((p) => p.field === 'geoScope') ?
                      `${ids}-geo-error`
                    : undefined
                  }
                  onChange={(event) => edit({ geoScope: event.target.value })}
                  className={cn(
                    'w-1/2',
                    has((p) => p.field === 'geoScope') &&
                      'border-support-error',
                  )}
                />
                <NativeSelect
                  aria-label={research.location}
                  value={draft.userLocation}
                  disabled={starting}
                  onChange={(event) =>
                    edit({ userLocation: event.target.value })
                  }
                >
                  <option value={draft.userLocation}>
                    {research.locationOption(draft.userLocation)}
                  </option>
                </NativeSelect>
              </div>
              {has((p) => p.field === 'geoScope') && (
                <FieldError id={`${ids}-geo-error`}>
                  {required.geoScope}
                </FieldError>
              )}
            </div>
          </div>
          <div className={FORM_ROW_CLASS}>
            <label htmlFor={`${ids}-language`} className={FORM_LABEL_CLASS}>
              {research.language}
              <RequiredMark />
            </label>
            <div
              className={cn(
                FORM_VALUE_CLASS,
                'flex-col justify-center gap-1.5',
              )}
            >
              <NativeSelect
                id={`${ids}-language`}
                aria-label={research.language}
                value={draft.mainLanguage}
                disabled={starting}
                onChange={(event) => edit({ mainLanguage: event.target.value })}
              >
                <option value={draft.mainLanguage}>{draft.mainLanguage}</option>
              </NativeSelect>
              <Note testId="language-hint">{research.languageHint}</Note>
            </div>
          </div>
          <div className={FORM_ROW_CLASS}>
            <label htmlFor={`${ids}-start-date`} className={FORM_LABEL_CLASS}>
              {research.period}
              <RequiredMark />
            </label>
            <div
              className={cn(
                FORM_VALUE_CLASS,
                'flex-col justify-center gap-1.5',
              )}
            >
              <div className="flex items-center gap-2 text-style-pre-body-06 text-text-secondary">
                <Input
                  id={`${ids}-start-date`}
                  aria-label={research.startDate}
                  inputMode="numeric"
                  value={draft.startDate}
                  aria-required
                  disabled={starting}
                  aria-invalid={startProblem !== undefined || undefined}
                  aria-describedby={
                    startProblem ? `${ids}-start-date-error` : undefined
                  }
                  onChange={(event) => edit({ startDate: event.target.value })}
                  className={cn('w-40', startProblem && 'border-support-error')}
                />
                <span>{research.until}</span>
                <span>{research.untilToday}</span>
              </div>
              {startProblem && (
                <FieldError id={`${ids}-start-date-error`}>
                  {startProblem.code === 'required' ?
                    required.startDate
                  : required.startBeforeToday}
                </FieldError>
              )}
            </div>
          </div>
        </div>
        <PageInfo icon={<PageInfoIcon />} data-testid="research-note">
          {research.note}
        </PageInfo>
      </Card>

      {has((p) => p.field === 'size') && (
        <PageInfo
          tone="error"
          icon={<PageInfoIcon />}
          role="alert"
          data-testid="size-error"
        >
          {required.size}
        </PageInfo>
      )}
      {startFailed && (
        <PageInfo
          tone="error"
          icon={<PageInfoIcon />}
          role="alert"
          data-testid="start-error"
        >
          {words.startFailed}
        </PageInfo>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Button
          variant="outlineGrey"
          shape="round"
          size="md"
          disabled={starting}
          onClick={onCancel}
        >
          {words.cancel}
        </Button>
        <Button
          asChild
          variant="solidBlack"
          shape="round"
          size="md"
          loading={starting}
          disabled={starting}
        >
          <button type="button" data-testid="start" onClick={start}>
            {words.start}
          </button>
        </Button>
      </div>
      {leave?.pending === true && (
        <LeaveDialog onStay={leave.reset} onLeave={leave.proceed} />
      )}
    </div>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return (
    <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
      {children}
    </h3>
  );
}

/** 도움 글(400 12 — 시안 .g-small). */
function Note({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <p
      data-testid={testId}
      className="m-0 text-style-pre-caption-03 text-text-tertiary"
    >
      {children}
    </p>
  );
}
