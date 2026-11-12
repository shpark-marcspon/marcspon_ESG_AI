// IR-02 오류 줄 한 부품(밴드 IRW3 N3 — 판 v170 e-helper--error: 400 12 · ⓘ 16 · gap 4 · support-error).
//   칸 아래 오류(NewScreen·TopicCard)와 가치사슬 칸의 넣기 오류·밸류체인 빈 칸 글이 같이 쓴다. 아이콘은 aria-hidden — 읽히는 것은 글뿐.
import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';

export function FieldError({
  id,
  role,
  testId,
  children,
}: {
  id?: string;
  role?: 'alert';
  testId?: string;
  children: string;
}) {
  return (
    <p
      id={id}
      role={role}
      data-testid={testId}
      className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error"
    >
      <CircleWarningIcon aria-hidden className="size-4 shrink-0" />
      {children}
    </p>
  );
}
