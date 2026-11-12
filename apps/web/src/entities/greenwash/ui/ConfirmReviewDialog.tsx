// 확정 확인 모달(밴드 FW1 ②, 시안 GW-05b). Alert 꼴: 제목 18 가운데.
//
// - [R6] 우리 DialogContent 는 variant 가 default 고정이라 키트 alert 머리 꼴을 쓸 수 없다.
//   그래서 Title 에 직접 text-style-pre-heading-02 + 가운데를 단다(1025px 이상에서 18. 그 아래 16. theme-tokens.ts pre-heading-02).
// - 미검토 n건이 있으면 경고 글을 보이고, 0 이면 숨긴다. 잠금 안내는 한 줄 안내(PageInfo)의 중요 꼴.
// - [취소]·[확정]. pending 이면 [확정] 이 도는 표시(Button loading)이고 눌리지 않는다. 확정은 onConfirm 만 부른다(잠그기·저장은 쓰는 쪽 몫. 발주서 §1-5).
// - 버튼은 디자인 시스템 Modal 카드: [취소] outlineBlack 알약 + [확인] solidBlack 알약. 시안 05b 는 Solid Grey + Solid Black 각.
// - 닫히면 열기 전 초점 자리로 돌린다: 공용 DialogContent 의 기본 동작(밴드 FW2 ⓪, sid:MARC-ISSUE-97 1번. Trigger 없이 open 으로 열어도).
// - 크기 sm(420). 시안 .e-modal 은 520 — 디자인 트랙에 물을 것.
// - 막힘(밴드 GW2R ② — v115 GW-05b_r2 상태 예시 둘, sid:MARC-ISSUE-228 S3·227 ②): blocked 글이 있으면 잠금 안내 자리에 오류 줄
//   (AD-01 이름 고침 실패 줄 꼴: 12 support-error-accent, 아이콘 16, role="alert")을 두고, 단추는 [취소] · [새로 불러오기](onReload) · 꺼진 [확정].
//   글은 쓰는 쪽이 고른다(다른 창에서 바뀜 / 새로 불러오지 못함). 모달은 열린 채다.
import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';

import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { GW_TEXT } from '../config/text.ts';
import type { Wording } from '../config/text.ts';
import { withDefaults } from './withDefaults.ts';

type ConfirmText = Wording<(typeof GW_TEXT)['confirm']>;

export interface ConfirmReviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 남은 미검토 문장 수. 0 이면 경고를 숨긴다. */
  unreviewedCount: number;
  /** [확정] 을 눌렀을 때. */
  onConfirm: () => void;
  /** 참이면 [확정] 이 도는 표시를 보이고 눌리지 않는다(두 번 누름 막기). 쓰는 쪽이 저장하는 동안 켠다. */
  pending?: boolean;
  /** 문구를 바꾼다(문구 표 위에 덮는다. undefined 인 칸은 기본 문구를 지킨다). */
  text?: Partial<ConfirmText>;
  /** 확정을 막는 까닭의 글(있으면 잠금 안내 대신 오류 줄, [확정] 꺼짐, [새로 불러오기]). 없으면 null. */
  blocked?: string | null;
  /** [새로 불러오기]의 글. blocked 일 때만 그린다. */
  reloadLabel?: string;
  /** [새로 불러오기]를 눌렀을 때. */
  onReload?: () => void;
}

function ConfirmReviewDialog({
  open,
  onOpenChange,
  unreviewedCount,
  onConfirm,
  pending = false,
  text,
  blocked = null,
  reloadLabel,
  onReload,
}: ConfirmReviewDialogProps) {
  const words: ConfirmText = withDefaults<ConfirmText>(GW_TEXT.confirm, text);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* 경고가 있으면 Radix 가 그 Description 을 aria-describedby 로 잇는다. 없으면 「설명 없음」을 밝혀 경고를 끈다. */}
      <DialogContent
        size="sm"
        {...(unreviewedCount > 0 ? {} : { 'aria-describedby': undefined })}
      >
        <DialogTitle className="text-center text-style-pre-heading-02">
          {words.title}
        </DialogTitle>
        {unreviewedCount > 0 && (
          <DialogDescription
            data-unreviewed={unreviewedCount}
            className="m-0 text-center text-style-pre-body-06 text-text-secondary"
          >
            {words.unreviewedWarning(unreviewedCount)}
          </DialogDescription>
        )}
        {blocked === null ?
          <PageInfo tone="important" icon={<PageInfoIcon />}>
            {words.lockNotice}
          </PageInfo>
        : <p
            role="alert"
            data-testid="confirm-blocked"
            className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
          >
            <CircleWarningIcon aria-hidden />
            {blocked}
          </p>
        }
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outlineBlack" shape="round" size="md">
              {words.cancel}
            </Button>
          </DialogClose>
          {blocked !== null && reloadLabel !== undefined && (
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              onClick={onReload}
            >
              {reloadLabel}
            </Button>
          )}
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            loading={pending}
            disabled={blocked !== null}
            onClick={onConfirm}
          >
            {words.submit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
ConfirmReviewDialog.displayName = 'ConfirmReviewDialog';

export { ConfirmReviewDialog };
