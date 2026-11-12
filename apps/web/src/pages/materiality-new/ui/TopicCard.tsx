// IR-02 「2. 중대 토픽 (Short-list)」의 토픽 카드 하나(밴드 IRW2 ② — 판 IR-02_r1 d-topic, 부록 A2·A6-⑬). 모양 부품: props 만 받는다.
//   펼친 카드: 이름 칸(A6-⑬ — 판은 이름을 머리 글로만 보임) · [토픽 빼기] · 설명 글 칸 + 안내 · 「서브토픽」 줄들(이름·설명·지우기) ·
//   [서브토픽 더하기]. 접힌 카드: 이름 · 「서브토픽 n개 · 펼치기」.
// 오류는 칸 아래 빨간 글(첫 오류 칸 초점은 부르는 쪽 — 칸 id 는 `${idBase}-topic-${key}` · `-subs-${key}` · `-sub-${subKey}`).
import { CloseIcon, PlusIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { filledSubtopics } from '../../../entities/materiality/model/index.ts';
import type {
  SubtopicDraft,
  TopicDraft,
} from '../../../entities/materiality/model/index.ts';
import { Button, IconButton } from '../../../shared/ui/button/index.ts';
import { FieldError } from './FieldError.tsx';

const words = IR_TEXT.newRun.topics;
const required = IR_TEXT.newRun.required;

export interface TopicErrors {
  name?: 'required' | 'duplicate';
  /** 서브토픽 0개. */
  subtopics?: boolean;
  /** 설명만 찬 서브토픽 줄의 key. */
  subNames: readonly number[];
}

export interface TopicCardProps {
  topic: TopicDraft;
  /** 카드 차례(1부터 — 이름 칸 aria). */
  order: number;
  open: boolean;
  errors: TopicErrors;
  idBase: string;
  disabled?: boolean;
  onChange(topic: TopicDraft): void;
  onRemove(): void;
  onOpen(): void;
  /** 새 서브토픽 줄의 key. */
  newKey(): number;
}

export function TopicCard({
  topic,
  order,
  open,
  errors,
  idBase,
  disabled = false,
  onChange,
  onRemove,
  onOpen,
  newKey,
}: TopicCardProps) {
  const name = topic.topic.trim();
  const count = filledSubtopics(topic).length;
  const nameId = `${idBase}-topic-${topic.key}`;
  const subsId = `${idBase}-subs-${topic.key}`;
  const setSub = (key: number, patch: Partial<SubtopicDraft>) =>
    onChange({
      ...topic,
      subtopics: topic.subtopics.map((sub) =>
        sub.key === key ? { ...sub, ...patch } : sub,
      ),
    });

  if (!open)
    return (
      <div
        data-testid="topic-card"
        data-open="false"
        className="flex items-center justify-between gap-3 rounded-component border border-solid border-border-tertiary px-5 py-4"
      >
        <b className="text-style-pre-body-04 text-text-primary">{name}</b>
        <Button
          variant="outlineGrey"
          size="sm"
          aria-expanded={false}
          aria-label={words.expand(name)}
          disabled={disabled}
          onClick={onOpen}
        >
          {words.folded(count)}
        </Button>
      </div>
    );

  return (
    <div
      data-testid="topic-card"
      data-open="true"
      className="flex flex-col gap-3 rounded-component border border-solid border-border-tertiary px-5 py-4"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <Input
            id={nameId}
            aria-label={words.nameLabel(order)}
            placeholder={words.namePlaceholder}
            value={topic.topic}
            disabled={disabled}
            aria-invalid={errors.name !== undefined || undefined}
            aria-describedby={errors.name ? `${nameId}-error` : undefined}
            onChange={(event) =>
              onChange({ ...topic, topic: event.target.value })
            }
            className={cn('w-1/2', errors.name && 'border-support-error')}
          />
          {errors.name && (
            <FieldError id={`${nameId}-error`}>
              {errors.name === 'required' ?
                required.topicName
              : required.topicDuplicate}
            </FieldError>
          )}
        </div>
        {errors.subtopics && (
          <span className="shrink-0 text-style-pre-caption-03 text-support-error">
            {words.subCount(0)}
          </span>
        )}
        <IconButton
          size="md"
          aria-label={words.remove}
          disabled={disabled}
          onClick={onRemove}
        >
          <CloseIcon />
        </IconButton>
      </div>
      <Textarea
        aria-label={words.descriptionLabel(name)}
        placeholder={words.descriptionPlaceholder}
        value={topic.description}
        disabled={disabled}
        aria-describedby={errors.subtopics ? `${subsId}-error` : undefined}
        onChange={(event) =>
          onChange({ ...topic, description: event.target.value })
        }
        rows={2}
      />
      <Note>{words.descriptionHint}</Note>
      <span className="text-style-pre-caption-03 font-bold text-text-tertiary">
        {words.subtopics}
      </span>
      <div className="flex flex-col gap-2 pl-6">
        {topic.subtopics.map((sub, index) => {
          const bad = errors.subNames.includes(sub.key);
          const subId = `${idBase}-sub-${sub.key}`;
          return (
            <div key={sub.key} className="flex flex-col gap-1">
              <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto] items-center gap-2">
                <Input
                  id={subId}
                  aria-label={words.subName(name)}
                  value={sub.name}
                  disabled={disabled}
                  aria-invalid={bad || undefined}
                  aria-describedby={bad ? `${subId}-error` : undefined}
                  onChange={(event) =>
                    setSub(sub.key, { name: event.target.value })
                  }
                  className={cn(bad && 'border-support-error')}
                />
                <Input
                  aria-label={words.subDescription(name)}
                  value={sub.description}
                  disabled={disabled}
                  onChange={(event) =>
                    setSub(sub.key, { description: event.target.value })
                  }
                />
                <IconButton
                  size="md"
                  aria-label={words.subRemove(name, index + 1)}
                  disabled={disabled}
                  onClick={() =>
                    onChange({
                      ...topic,
                      subtopics: topic.subtopics.filter(
                        (each) => each.key !== sub.key,
                      ),
                    })
                  }
                >
                  <CloseIcon />
                </IconButton>
              </div>
              {bad && (
                <FieldError id={`${subId}-error`}>
                  {required.subtopicName}
                </FieldError>
              )}
            </div>
          );
        })}
        {errors.subtopics && (
          <FieldError id={`${subsId}-error`}>{required.subtopics}</FieldError>
        )}
        <div>
          <Button
            id={subsId}
            variant="outlineGrey"
            size="sm"
            disabled={disabled}
            onClick={() =>
              onChange({
                ...topic,
                subtopics: [
                  ...topic.subtopics,
                  { key: newKey(), name: '', description: '' },
                ],
              })
            }
          >
            <PlusIcon aria-hidden />
            {words.addSub}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Note({ children }: { children: string }) {
  return (
    <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
      {children}
    </p>
  );
}
