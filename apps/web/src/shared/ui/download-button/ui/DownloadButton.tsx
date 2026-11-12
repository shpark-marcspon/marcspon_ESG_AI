// 내려받기 단추(밴드 GW2R ③ Q9 의 그린워싱 [엑셀 내보내기] 단추 ExcelButton 을 TRW0a ① 에서 shared 로 올림 — 그린워싱 엑셀·영문번역 Word). 모양 부품: 저장소를 모른다.
//   - 누르면 load()(쓰는 화면이 저장소를 넘긴다)로 파일을 받아 이 탭에서 내려받게 한다(shared/lib/saveBlob.ts — object URL + <a download>.
//     api·hooks 는 Blob 만 돌려준다: app/guards/layers.test.ts 의 HOOKS_DOM).
//   - 받는 동안 다시 눌러도 한 번만 부른다(ref 로 막는다 — 같은 그리기 안의 두 번째 누름도). 받는 동안은 도는 표시.
//   - 실패면 단추 옆 role="alert" 한 줄(디자인 답 D3 글 — 두 문장이라 마침표). 다시 누르면 지우고 다시 받는다.
//   - disabled(dry-run 결과 — 엑셀이 없다)면 aria-disabled + 흐림, 눌러도 아무것도 부르지 않는다(초점은 남는다).
//   - [TRW1a H4] busyLabel 이 있으면 받는 동안 단추 글을 그것으로(v136 「받는 중…」). load 가 {kind:'handled'} 로 끝나면
//     쓰는 화면이 이미 글을 보였다는 뜻이라 내려받지도 실패 글을 보이지도 않는다(영문번역 [모두 받기] 409 — 글 둘 겹침 막음).
//   - [PD1] variant·shape·size 를 받아 공용 Button 에 그대로 넘긴다(타입은 ButtonProps 의 것). 기본은 outlineGrey·round·md.
//     시안 값 보기: [모두 받기] solidBlack · 표 [Word] sm · 양식 square sm.
import { useRef, useState } from 'react';

import {
  CircleWarningIcon,
  DownloadIcon,
} from '@marcspon/common/generated/icons/MyIcons';

import { saveBlob } from '../../../lib/saveBlob.ts';
import { Button, type ButtonProps } from '../../button/index.ts';

export interface DownloadButtonProps extends Pick<
  ButtonProps,
  'variant' | 'shape' | 'size'
> {
  /** 단추 글. */
  label: string;
  /** 실패 글(단추 옆 role="alert"). */
  failedText: string;
  /** 파일을 받는다(쓰는 화면이 저장소를 부른다). 거절되면 실패 글. {kind:'handled'} 면 아무것도 하지 않는다(화면이 글을 보임). */
  load: () => Promise<{ blob: Blob; fileName: string } | { kind: 'handled' }>;
  /** 받는 동안의 단추 글. 없으면 label 그대로. */
  busyLabel?: string;
  /** 참이면 꺼진 꼴(누름이 아무것도 부르지 않는다). */
  disabled?: boolean;
  /** 단추의 data-testid. */
  testId?: string;
}

export function DownloadButton({
  label,
  failedText,
  load,
  busyLabel,
  disabled = false,
  testId,
  variant = 'outlineGrey',
  shape = 'round',
  size = 'md',
}: DownloadButtonProps) {
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const press = async () => {
    if (disabled || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setFailed(false);
    try {
      const file = await load();
      if (!('kind' in file)) saveBlob(file.blob, file.fileName);
    } catch {
      setFailed(true);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      {/* 라이브 영역은 늘 두고 글만 넣고 뺀다(실패). */}
      <p
        role="alert"
        data-testid={testId === undefined ? undefined : `${testId}-error`}
        className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent empty:hidden [&_svg]:size-4 [&_svg]:shrink-0"
      >
        {failed && (
          <>
            <CircleWarningIcon aria-hidden />
            {failedText}
          </>
        )}
      </p>
      {/* 공용 Button 의 asChild + disabled 는 aria-disabled 를 달고 초점은 남긴다. 흐림은 직접(asChild 자식엔 disabled 속성이 없다 — 디자인 대조 C5) */}
      <Button
        asChild
        disabled={disabled}
        loading={busy}
        variant={variant}
        shape={shape}
        size={size}
        // 받는 동안(loading)도 aria-disabled 라 흐림은 꺼진 때만 단다
        className={
          disabled ?
            'aria-disabled:cursor-not-allowed aria-disabled:opacity-40'
          : undefined
        }
      >
        <button type="button" data-testid={testId} onClick={() => void press()}>
          <DownloadIcon aria-hidden />
          {busy && busyLabel !== undefined ? busyLabel : label}
        </button>
      </Button>
    </span>
  );
}
