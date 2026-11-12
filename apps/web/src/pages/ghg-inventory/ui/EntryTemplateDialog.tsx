// S4 양식 받기 창(밴드 W12-5 ② — Figma 28538:9738 ①·28549:13150 ②). S4 [양식 다운로드] 가 S4 위에 겹쳐 연다(선례 S8→S9→S11).
//   ① 데이터(Scope) 고르기 → [다음] ② 사업장 고르기 → [다음] = 양식 받기 → 성공이면 닫고 초점은 [양식 다운로드]. 마지막 단추도 「다음」(e6 — Figma 그대로).
//   사업장은 ② 를 열 때 쪽을 끝까지 돌아 inventoryEnabled 만 받은 차례로 싣는다(첫 쪽만 보면 21 번째부터 조용히 빠진다 — 발주서 Q4).
//   읽기 실패·사업장 0 은 ② 안 한 줄, [다음] 꺼짐. 안 고르면 [다음] 꺼짐. 고르기는 공통 NativeSelect(w-full, sid:MARC-ENT-430).
import { useEffect, useRef, useState } from 'react';

import type {
  CompanyRefusal,
  GhgEntryPort,
  GhgOrganizationPort,
} from '../../../entities/ghg/api/index.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { saveBlob } from '../../../shared/lib/saveBlob.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';

const words = GHG_TEXT.inventory.bulk.template;

interface Site {
  id: string;
  name: string;
}

export interface EntryTemplateDialogProps {
  port: GhgEntryPort;
  organization: GhgOrganizationPort;
  year: number;
  companyText: Record<CompanyRefusal, string>;
  returnFocus(): HTMLElement | null;
  onClose(): void;
  /** 내려받기(시험이 바꾼다). */
  save?: (blob: Blob, fileName: string) => void;
}

export function EntryTemplateDialog({
  port,
  organization,
  year,
  companyText,
  returnFocus,
  onClose,
  save = saveBlob,
}: EntryTemplateDialogProps) {
  const [scope, setScope] = useState<1 | 2 | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [sites, setSites] = useState<Site[] | null>(null);
  const [siteId, setSiteId] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  /** 닫힌 뒤 늦게 온 답은 버린다(닫았는데 파일이 받아지지 않게). */
  const open = useRef(true);
  useEffect(() => {
    open.current = true;
    return () => {
      open.current = false;
    };
  }, []);

  /** 쪽을 끝까지 돈다. 한 쪽이라도 실패면 그 글(일부만 보이지 않게). */
  const loadSites = async () => {
    const found: Site[] = [];
    for (let page = 1; ; page += 1) {
      const out = await organization.listBranches({ q: '', page });
      if (!open.current) return;
      if (out.kind !== 'ok') {
        setProblem(
          out.kind === 'refused' ? companyText[out.company] : words.sitesFailed,
        );
        setSites([]);
        return;
      }
      for (const branch of out.value.results)
        if (branch.inventoryEnabled)
          found.push({ id: branch.id, name: branch.name });
      if (!out.value.hasNext) break;
    }
    setProblem(found.length === 0 ? words.sitesEmpty : null);
    setSites(found);
  };

  const next = async () => {
    if (step === 1) {
      setStep(2);
      await loadSites();
      return;
    }
    if (scope === null || siteId === '' || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setProblem(null);
    const out = await port.template(year, scope, siteId);
    busyRef.current = false;
    if (!open.current) return;
    setBusy(false);
    if (out.kind === 'ok') {
      save(out.value.blob, out.value.fileName);
      onClose();
    } else
      setProblem(
        out.kind === 'notFound' ? words.notFound
        : out.kind === 'refused' ? companyText[out.company]
        : words.failed,
      );
  };

  const ready = step === 1 ? scope !== null : siteId !== '';

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent
        size="md"
        data-testid="entry-template"
        className="gap-6"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = returnFocus();
          if (target?.isConnected) target.focus();
        }}
      >
        <DialogTitle className="flex h-10 items-center text-style-pre-heading-02 text-text-secondary">
          {step === 1 ? words.scopeTitle : words.siteTitle}
        </DialogTitle>
        {step === 1 ?
          <NativeSelect
            aria-label={words.scopeTitle}
            data-testid="entry-template-scope"
            className="w-full"
            value={scope === null ? '' : `${scope}`}
            onChange={(event) => setScope(event.target.value === '1' ? 1 : 2)}
          >
            <option value="" disabled hidden>
              {words.scopePlaceholder}
            </option>
            <option value="1">{words.scope1}</option>
            <option value="2">{words.scope2}</option>
          </NativeSelect>
        : <NativeSelect
            aria-label={words.siteTitle}
            data-testid="entry-template-site"
            className="w-full"
            value={siteId}
            disabled={sites === null || sites.length === 0}
            onChange={(event) => setSiteId(event.target.value)}
          >
            <option value="" disabled hidden>
              {sites === null ? words.sitesLoading : words.sitePlaceholder}
            </option>
            {(sites ?? []).map((site) => (
              <option key={site.id} value={site.id}>
                {site.name}
              </option>
            ))}
          </NativeSelect>
        }
        {problem !== null && (
          <p
            role="alert"
            data-testid="entry-template-problem"
            className="m-0 text-style-pre-caption-03 text-support-error-accent"
          >
            {problem}
          </p>
        )}
        <DialogFooter className="justify-center gap-2 pt-0 sm:justify-center">
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            className="min-w-20"
            onClick={onClose}
          >
            {words.cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            className="min-w-20"
            data-testid="entry-template-next"
            disabled={!ready}
            loading={busy}
            onClick={() => void next()}
          >
            {words.next}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
