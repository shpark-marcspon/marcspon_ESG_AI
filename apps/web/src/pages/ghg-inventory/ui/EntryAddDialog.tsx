// S3 「자산/시설 추가」 고르기(밴드 W12-1b ① — 스펙 ② S15 「①이 씀」 28556:29367 [추정]). 고른 것은 화면에만 새 행이 되고 블록 저장 때 나간다.
//   <form onSubmit> 이라 Enter 가 확인, 닫히면 초점은 연 단추로(DialogContent 기본 — sid:MARC-ISSUE-460).
//   W12-1c #15(Figma 28556:29367): 폭 980 · 표(전체 고름 · 「자산/시설명」 · 「상세 시설명」, 줄 56 · 체크 20) · [취소] [확인].
//   「자산/시설명」 값은 그 잎 이름(줄마다 같음) — 서버에 코드 칸이 없어 머리도 이름만(W12-1d N3, 코드가 생기면 「및 코드」). 전체 고름 = 보이는 것 전부 켬/끔, 일부면 indeterminate.
import { useRef, useState } from 'react';
import type { FormEvent } from 'react';

import { Checkbox } from '@marcspon/ui/components/checkbox';
import { cn } from '@marcspon/ui/lib/utils';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import type { EntryFacility } from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { CELL, HEAD_CELL, TABLE } from './entryTable.ts';

const words = GHG_TEXT.entry;

export function EntryAddDialog({
  facilityName,
  facilities,
  onPick,
  onClose,
}: {
  /** 그 잎 자산/시설 이름(상세 index.name). */
  facilityName: string;
  facilities: readonly EntryFacility[];
  onPick(picked: readonly EntryFacility[]): void;
  onClose(): void;
}) {
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const okRef = useRef<HTMLButtonElement>(null);
  const picked = facilities.filter((facility) => chosen.has(facility.id));
  const all =
    picked.length === 0 ? false
    : picked.length === facilities.length ? true
    : 'indeterminate';
  const submit = (event: FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    onPick(picked);
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid="entry-add"
        className="w-[980px] max-w-[calc(100vw-64px)]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          okRef.current?.focus();
        }}
      >
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogTitle className="text-style-pre-heading-02">
            {words.addTitle}
          </DialogTitle>
          {facilities.length === 0 ?
            <p className="m-0 text-style-pre-body-06 text-text-tertiary">
              {words.addEmpty}
            </p>
          : <table className={`${TABLE} w-full table-fixed`}>
              <colgroup>
                <col className="w-[52px]" />
                <col />
                <col />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col" className={cn(HEAD_CELL, 'text-center')}>
                    <Checkbox
                      size="lg"
                      className="align-middle"
                      aria-label={words.addAll}
                      checked={all}
                      onCheckedChange={() =>
                        setChosen(
                          all === true ?
                            new Set()
                          : new Set(facilities.map((facility) => facility.id)),
                        )
                      }
                    />
                  </th>
                  <th scope="col" className={HEAD_CELL}>
                    {words.addHeadName}
                  </th>
                  <th scope="col" className={HEAD_CELL}>
                    {words.head.detail}
                  </th>
                </tr>
              </thead>
              <tbody>
                {facilities.map((facility) => (
                  <tr
                    key={facility.id}
                    data-testid={`entry-add-${facility.id}`}
                  >
                    <td className={cn(CELL, 'text-center')}>
                      <Checkbox
                        size="lg"
                        className="align-middle"
                        aria-label={words.addPick(facility.detailName)}
                        checked={chosen.has(facility.id)}
                        onCheckedChange={(on) =>
                          setChosen((old) => {
                            const next = new Set(old);
                            if (on === true) next.add(facility.id);
                            else next.delete(facility.id);
                            return next;
                          })
                        }
                      />
                    </td>
                    <td className={CELL}>{facilityName}</td>
                    <td className={CELL}>{facility.detailName}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
          <DialogFooter>
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              onClick={onClose}
            >
              {words.cancel}
            </Button>
            <Button
              ref={okRef}
              type="submit"
              variant="solidBlack"
              shape="round"
              size="md"
            >
              {words.addOk}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
