// 파트 실패 카드(밴드 TRW0b, 시안 TR-03 3·4번, 결정 sid:MARC-ENT-393). 모양 부품: props 만 받는다.
// - server_error·partial: 글 + [이 파트만 다시](파트가 하나면 [다시 실행]) — onRetry 가 있을 때만. 안내 글은 [이 파트만 다시] 꼴에만(판에 [다시 실행] 안내 글 없음).
// - rejected(준비 단계에서 막음): 파일 줄 + 까닭 + 안내 한 줄, 다시 하는 단추는 그리지 않는다(같은 설정이면 다시 막힌다).
// - retrying 이면 다시 단추를 끈다(보내는 동안 — 두 번 눌러도 한 번, 밴드 TRW1b).
// - [목록으로]는 onBack 이 있을 때만. 「실패한 쪽만 다시」 단추는 없다.
// - PDF 파트(밴드 TRW6 W8·W6): 읽지 못함·텍스트 없음이면 그 글 한 줄만(안내·다시 단추 0 — 같은 PDF 면 다시 막힌다),
//   그 밖 PDF 파트는 다시 단추 아래 회색 한 줄. 서버 문장은 보이지 않는다.
// 운영 관리자도 고객사 사용자와 같은 일을 한다(확정 판 v136 TR-01a · sid:MARC-ENT-380) — 숨기는 갈래가 없다.
import {
  CircleWarningIcon,
  FileIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import { Button } from '../../../shared/ui/button/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';
import { TR_TEXT } from '../config/text.ts';
import type { RejectionKey } from '../model/index.ts';
import { rejectionText } from './labels.ts';

const words = TR_TEXT.failure;

export interface PartFailureCardProps {
  kind: 'server_error' | 'partial' | 'rejected';
  /** rejected 의 까닭. */
  reason?: RejectionKey;
  /** 파일 줄(「…추출본.docx · 스토리 4~41쪽(38쪽)」 — 부르는 쪽이 짓는다). */
  fileLine?: string;
  onRetry?(): void;
  /** 다시 하기를 보내는 중(단추 꺼짐). */
  retrying?: boolean;
  /** 파트가 하나면 [다시 실행](여럿이면 [이 파트만 다시]). */
  single?: boolean;
  onBack?(): void;
  /** PDF 파트의 갈래(워드 파트는 넘기지 않는다 — DOM 이 BASE 와 같다). */
  pdf?: 'run' | 'unreadable' | 'no_text';
}

export function PartFailureCard({
  kind,
  reason,
  fileLine,
  onRetry,
  retrying = false,
  single = false,
  onBack,
  pdf,
}: PartFailureCardProps) {
  const rejected = kind === 'rejected';
  const pdfLine =
    pdf === 'unreadable' ? words.pdf.unreadable
    : pdf === 'no_text' ? words.pdf.noText
    : null;
  const text =
    rejected && reason !== undefined && pdfLine === null ?
      rejectionText(reason)
    : null;
  const canRetry = !rejected && pdfLine === null && onRetry !== undefined;
  return (
    <Card
      data-testid="part-failure"
      data-kind={kind}
      className="flex flex-col gap-3"
    >
      {/* 파일 줄 = 파일 아이콘 + 500 16 #383C40 · 까닭 = PageInfo error(밴드 TRP2 TC17, 시안 TR-03 3·4번 e-file·e-info--invalid) */}
      {fileLine !== undefined && (
        <span className="flex items-center gap-2 text-style-pre-body-02 text-text-secondary [&_svg]:size-5 [&_svg]:shrink-0">
          <FileIcon aria-hidden />
          {fileLine}
        </span>
      )}
      <PageInfo tone="error" icon={<CircleWarningIcon aria-hidden />}>
        <span className="text-style-pre-body-06">
          {pdfLine !== null ?
            pdfLine
          : rejected ?
            text?.reason
          : kind === 'server_error' ?
            words.serverError
          : words.partial}
        </span>
      </PageInfo>
      {text !== null && (
        <p
          data-testid="part-failure-guide"
          className="m-0 text-style-pre-body-06 text-text-secondary"
        >
          {text.guide}
        </p>
      )}
      {canRetry && !single && (
        <p
          data-testid="part-failure-guide"
          className="m-0 text-style-pre-body-06 text-text-secondary"
        >
          {words.retryGuide}
        </p>
      )}
      {(canRetry || onBack !== undefined) && (
        <div className="flex gap-2">
          {canRetry && (
            <Button
              variant="solidBlack"
              shape="round"
              size="md"
              disabled={retrying}
              onClick={() => onRetry?.()}
            >
              {single ? words.retrySingle : words.retryPart}
            </Button>
          )}
          {onBack !== undefined && (
            <Button
              variant="outlineGrey"
              shape="round"
              size="md"
              onClick={() => onBack?.()}
            >
              {words.back}
            </Button>
          )}
        </div>
      )}
      {canRetry && pdf === 'run' && (
        <p
          data-testid="part-failure-pdf-note"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          {words.pdf.retryNote}
        </p>
      )}
    </Card>
  );
}
