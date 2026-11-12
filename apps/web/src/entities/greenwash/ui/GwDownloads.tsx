// 그린워싱 머리 [내려받기] + 받기 모달(밴드 GDL1 — GW-04a r1 · GW-04 r4 · GW-05c r4, 결정 sid:MARC-ENT-662 꼴 · sid:MARC-ENT-663 공용 자리).
//   옛 「엑셀 내보내기」·「엑셀 내보내기 · 확정본」 단추 둘을 갈음한다. 모양 부품: 저장소를 모르고 load 를 받는다.
//   - 머리 단추: outline-grey · round · 받기 아이콘(왼쪽) + 「내려받기」. 시험 실행이어도 켠다(모달을 열면 줄이 꺼져 있다).
//   - 모달: 공용 shared/ui/download-dialog 의 DownloadDialog. 파일 묶음 하나(점검 결과 엑셀, XLSX 아이콘), 각주 없음.
//     확정 전 / 뒤는 묶음 이름과 단추 안 이름만 바뀐다(받는 파일은 부르는 쪽 load — 확정 뒤 ?confirmed=true).
//     꺼짐은 시험 실행(scan=false)일 때만 — (?) 툴팁 「시험 실행이라 …」. 실패는 그 줄 아래 role=alert(GW_TEXT.result.excelFailed).
//   - 닫히면 초점은 머리 [내려받기]로(공용 모달의 returnFocus).
import { useRef, useState } from 'react';

import { DownloadIcon } from '@marcspon/common/generated/icons/MyIcons';

import { Button } from '../../../shared/ui/button/index.ts';
import { DownloadDialog } from '../../../shared/ui/download-dialog/index.ts';
import { ReportXlsxIcon } from '../../../shared/ui/file-type-icon/index.ts';
import { GW_TEXT } from '../config/text.ts';

const words = GW_TEXT.downloads;

export interface GwDownloadsProps {
  /** 확정된 실행이면 확정본 이름. */
  confirmed: boolean;
  /** 점검 실행(판정한 문장이 있음)이면 참 — 거짓이면 모달의 줄이 꺼진다. */
  scan: boolean;
  /** 엑셀을 받는다(쓰는 화면이 store.getReport 를 부른다). */
  load: () => Promise<{ blob: Blob; fileName: string }>;
  /** 내려받기(시험이 바꾼다). */
  save?: (blob: Blob, fileName: string) => void;
}

export function GwDownloads({ confirmed, scan, load, save }: GwDownloadsProps) {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const name = confirmed ? words.excelConfirmed : words.excel;
  return (
    <>
      <Button
        ref={opener}
        variant="outlineGrey"
        shape="round"
        size="md"
        data-testid="gw-downloads"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        <DownloadIcon aria-hidden />
        {words.title}
      </Button>
      {open && (
        <DownloadDialog
          testId="gw-download-dialog"
          title={words.title}
          closeLabel={words.close}
          helpLabel={words.missingLabel}
          failedText={GW_TEXT.result.excelFailed}
          busyLabel={words.downloading}
          files={[
            {
              key: 'excel',
              name,
              description: words.excelNote,
              fileLabel: name,
              icon: <ReportXlsxIcon />,
              download: load,
              ...(scan ? {} : { disabledReason: words.excelMissing }),
            },
          ]}
          onClose={() => setOpen(false)}
          returnFocus={() => opener.current}
          {...(save === undefined ? {} : { save })}
        />
      )}
    </>
  );
}
