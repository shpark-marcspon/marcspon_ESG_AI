// AD-02 그린워싱 탭의 대상 단어 카드(밴드 AS3b ① — 디자인 사본 AD-02_r3 · cd 답 246 노트 10-22 · D1~D4).
//   머리 「대상 단어」 + 고침 꼬리표(「● 고침 n」) · 오른쪽 [삭제](회색 — 고른 줄) [추가](검정 — 입력 칸의 글, Enter 도) · 안내 · 한 줄 입력(오류는 칸 아래 빨강 한 줄)
//   · 표(머리 [전체 고르기] 「단어」 「사용」 — 줄마다 고르기 · 낱말(더한 줄은 주황 바탕 + 「추가」) · 사용 스위치. 다 싣고 카드 안 스크롤, 머리 고정)
//   · 아래 줄 「<n>개 · 사용 <m>개」(+ 새로 더한 것) · 켠 것 0 이면 카드 밖 아래 글(D4 — 저장은 껍데기가 끈다).
//   표 꼴(밴드 GP2 — GW3R-AD02 대조 C13·C14, 시안이 정본): 머리 칸 500 14 · support-grey-subtle 바탕 · 위아래 1px border-tertiary · 0 16px · 높이 40,
//   몸 칸 0 16px · 높이 56, 표 둘레 상자 없음.
//   초안·짚은 자리는 props — 저장 본문에 드는 상태는 껍데기의 useDraft 한 곳(이 카드는 입력 글·오류·고름만 든다, 발주서 K1).
import { useId, useState } from 'react';

import { Checkbox } from '@marcspon/ui/components/checkbox';
import { Input } from '@marcspon/ui/components/input';
import { Switch } from '@marcspon/ui/components/switch';
import { cn } from '@marcspon/ui/lib/utils';

import { Button } from '../../../shared/ui/button/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import type { GREENWASH_SETTING_TEXT } from '../config/text.ts';
import {
  addTerm,
  addedTexts,
  refusedRow,
  removeTerms,
  switchTerm,
  termsBlocked,
  termsCount,
} from '../model/index.ts';
import type { TermProblem, TermsDraft } from '../model/index.ts';

export interface TermsCardProps {
  base: TermsDraft;
  draft: TermsDraft;
  readOnly: boolean;
  /** 서버가 짚은 자리(terms.<i>.text → 그 줄, terms → 카드 아래). */
  refused: Readonly<Record<string, readonly string[]>>;
  onChange(next: TermsDraft): void;
  words: (typeof GREENWASH_SETTING_TEXT)['terms'];
}

export function TermsCard({
  base,
  draft,
  readOnly,
  refused,
  onChange,
  words,
}: TermsCardProps) {
  const [text, setText] = useState('');
  const [problem, setProblem] = useState<TermProblem | null>(null);
  const problemId = useId();
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set());
  // 판을 바꾸면(바탕 몫이 바뀜) 카드 안 잠깐 상태 — 고름·입력 글·오류 — 를 비운다(같은 부품이 다음 판에 남으므로).
  const [shownBase, setShownBase] = useState(base);
  if (shownBase !== base) {
    setShownBase(base);
    setText('');
    setProblem(null);
    setPicked(new Set());
  }
  const shownPicked = new Set(
    draft.filter((term) => picked.has(term.text)).map((term) => term.text),
  );
  const count = termsCount(base, draft);
  const added = addedTexts(base, draft);
  const blocked = termsBlocked(draft);
  const allPicked = draft.length > 0 && shownPicked.size === draft.length;
  const refusedRows = new Map(
    Object.entries(refused).flatMap(([path, lines]) => {
      const row = refusedRow(path);
      return row === null ? [] : [[row, lines.join(' ')] as const];
    }),
  );
  const refusedAll = refused.terms?.join(' ') ?? null;

  const add = () => {
    if (readOnly) return;
    const outcome = addTerm(draft, text);
    if (outcome.kind === 'problem') {
      setProblem(outcome.problem);
      return;
    }
    setProblem(null);
    setText('');
    onChange(outcome.draft);
  };
  const remove = () => {
    if (readOnly || shownPicked.size === 0) return;
    setPicked(new Set());
    onChange(removeTerms(draft, shownPicked));
  };

  return (
    <div className="flex flex-col gap-2">
      <Card data-testid="terms-card" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.title}
          </h3>
          {count > 0 && (
            <span
              data-testid="terms-edited"
              className="inline-flex items-center gap-1 text-style-pre-caption-02 text-text-brand"
            >
              <span
                aria-hidden
                className="size-1.5 rounded-full bg-text-brand"
              />
              {words.edited(count)}
            </span>
          )}
          <span className="ml-auto flex gap-2">
            <Button
              variant="solidGrey"
              shape="square"
              size="sm"
              disabled={readOnly || shownPicked.size === 0}
              onClick={remove}
            >
              {words.remove}
            </Button>
            <Button
              variant="solidBlack"
              shape="square"
              size="sm"
              disabled={readOnly}
              onClick={add}
            >
              {words.add}
            </Button>
          </span>
        </div>
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {words.notice}
        </p>
        <div className="flex flex-col gap-1">
          <Input
            aria-label={words.input}
            aria-invalid={problem !== null || undefined}
            aria-describedby={problem !== null ? problemId : undefined}
            placeholder={words.placeholder}
            value={text}
            disabled={readOnly}
            onChange={(event) => {
              setText(event.target.value);
              setProblem(null);
            }}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' || event.nativeEvent.isComposing)
                return;
              event.preventDefault();
              add();
            }}
          />
          {problem !== null && (
            <p
              id={problemId}
              role="alert"
              data-testid="terms-problem"
              className="m-0 text-style-pre-caption-03 text-support-error-accent"
            >
              {words.problem[problem]}
            </p>
          )}
        </div>
        <div
          data-testid="terms-scroll"
          className="max-h-[440px] overflow-y-auto"
        >
          <table className="w-full border-separate border-spacing-0 text-style-pre-body-06 text-text-secondary">
            <thead className="sticky top-0 z-[1] bg-background-primary">
              <tr>
                <th
                  scope="col"
                  className="box-border h-10 w-10 border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 py-0 text-left"
                >
                  <Checkbox
                    aria-label={words.selectAll}
                    checked={
                      allPicked ? true
                      : shownPicked.size > 0 ?
                        'indeterminate'
                      : false
                    }
                    disabled={readOnly || draft.length === 0}
                    onCheckedChange={(checked) =>
                      setPicked(
                        checked === true ?
                          new Set(draft.map((term) => term.text))
                        : new Set(),
                      )
                    }
                  />
                </th>
                <th
                  scope="col"
                  className="box-border h-10 border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 py-0 text-left text-style-pre-body-05 text-text-tertiary"
                >
                  {words.word}
                </th>
                <th
                  scope="col"
                  className="box-border h-10 w-20 border-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 py-0 text-left text-style-pre-body-05 text-text-tertiary"
                >
                  {words.use}
                </th>
              </tr>
            </thead>
            <tbody>
              {draft.map((term, index) => {
                const isAdded = added.has(term.text);
                const wrong = refusedRows.get(index) ?? null;
                return (
                  <tr
                    key={term.text}
                    data-term={term.text}
                    data-added={isAdded || undefined}
                    data-refused={wrong !== null || undefined}
                    className={cn(
                      isAdded && 'bg-support-orange-subtle',
                      wrong !== null && 'text-support-error-accent',
                    )}
                  >
                    <td className="box-border h-14 border-0 border-b border-solid border-border-tertiary px-4 py-0">
                      <Checkbox
                        aria-label={words.pick(term.text)}
                        checked={shownPicked.has(term.text)}
                        disabled={readOnly}
                        onCheckedChange={(checked) => {
                          const next = new Set(shownPicked);
                          if (checked === true) next.add(term.text);
                          else next.delete(term.text);
                          setPicked(next);
                        }}
                      />
                    </td>
                    <td className="box-border h-14 border-0 border-b border-solid border-border-tertiary px-4 py-0">
                      <span className="inline-flex flex-wrap items-center gap-2">
                        {term.text}
                        {isAdded && (
                          <span
                            data-testid="terms-added-tag"
                            className="inline-flex h-5 items-center rounded-control bg-support-orange px-1.5 text-style-pre-caption-02 text-background-primary"
                          >
                            {words.addedTag}
                          </span>
                        )}
                      </span>
                      {wrong !== null && (
                        <p
                          data-testid="terms-row-refused"
                          className="m-0 text-style-pre-caption-03 text-support-error-accent"
                        >
                          {wrong}
                        </p>
                      )}
                    </td>
                    <td className="box-border h-14 border-0 border-b border-solid border-border-tertiary px-4 py-0">
                      <Switch
                        aria-label={words.switchLabel(term.text)}
                        checked={term.enabled}
                        disabled={readOnly}
                        onCheckedChange={(checked) =>
                          onChange(switchTerm(draft, term.text, checked))
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p
          data-testid="terms-foot"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          {words.foot(
            draft.length,
            draft.filter((term) => term.enabled).length,
            added.size,
          )}
        </p>
        {refusedAll !== null && (
          <p
            role="alert"
            data-testid="terms-refused"
            className="m-0 text-style-pre-caption-03 text-support-error-accent"
          >
            {refusedAll}
          </p>
        )}
      </Card>
      {blocked && (
        <p
          data-testid="terms-none-enabled"
          className="m-0 px-2 text-style-pre-caption-03 text-support-error-accent"
        >
          {words.noneEnabled}
        </p>
      )}
    </div>
  );
}
