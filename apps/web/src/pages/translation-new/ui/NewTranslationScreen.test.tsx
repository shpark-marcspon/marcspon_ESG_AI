// @vitest-environment jsdom
// 새 번역 화면(밴드 TRW1a ② — 발주서 §3-2 10). 진짜 실어댑터 + 가짜 영문번역 서버. 시험 파일은 바이트로 짓는다(저장소에 .docx·.xlsx 0).
//   pageCount null(docx·txt — 시연 길) → 그리드 0·글자 칸 셋·쪽 수 셈·[번역 시작] 켜짐, 「/ n쪽」·over_last 0 · pageCount 64 → PageGrid 칸 ·
//   고객사 용어집 없으면 끔 · 회사 칸 비면 틀린 칸 셈 · [번역 시작] → startBatch 한 번(두 번 눌러도 한 번) → onStarted ·
//   일부 파트만 시작 → onStarted 에 못 한 파트 · 모두 못 함 → 이 화면에 오류 한 줄 · 옵션 바이트 넘음 → TR-02a 글.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';
// 썸네일 시험(밴드 TRW9) — 위 vitest 줄을 고치지 않는다, 더하기만.
import { beforeEach } from 'vitest';

import {
  fakeTranslationServer,
  json,
  refusal,
  serverStoreOf,
} from '../../../entities/translation/api/testing.ts';
import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { NewTranslationScreen } from './NewTranslationScreen.tsx';

afterEach(cleanup);

const words = TR_TEXT.newTranslation;
const TXT = new TextEncoder().encode(
  ['[PAGE 1]', 'a', '[PAGE 2]', 'b', '[PAGE 3]', 'c'].join('\n'),
);
/** xlsx 머리(PK)만 지은 바이트 — 가짜 서버는 내용을 읽지 않는다. */
const XLSX = new Uint8Array([80, 75, 3, 4, 1, 2]);

const flush = () => act(async () => {});

function draw(options: Parameters<typeof fakeTranslationServer>[0] = {}) {
  const server = fakeTranslationServer(options);
  const store = serverStoreOf(server, {
    newKey: (() => {
      let n = 0;
      return () => `0000000${n++}-0000-4000-8000-000000000000`;
    })(),
  });
  const onStarted = vi.fn();
  const onCancel = vi.fn();
  render(
    <NewTranslationScreen
      store={store}
      now={() => new Date(2026, 9, 19)}
      onStarted={onStarted}
      onCancel={onCancel}
    />,
  );
  return { server, store, onStarted, onCancel };
}

const fileInput = (scope: ParentNode = document) =>
  scope.querySelector<HTMLInputElement>('input[type="file"]')!;

async function pickExtract(name = 'sample_extract.txt') {
  const card = document.querySelector('[data-card="file"]')!;
  fireEvent.change(fileInput(card), {
    target: { files: [new File([TXT], name)] },
  });
  await flush();
}
async function pickClientGlossary() {
  const field = screen.getByTestId('glossary-client');
  fireEvent.change(fileInput(field), {
    target: { files: [new File([XLSX], 'glossary.xlsx')] },
  });
  await flush();
}
const type = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label, { exact: false }), {
    target: { value },
  });
const partField = (part: string) =>
  document.querySelector<HTMLInputElement>(`[data-part-field="${part}"]`)!;
function fillCompany() {
  type(words.company.name, 'Sample Corp');
  type(words.company.subject, 'virtual services');
  type(words.company.standards, 'GRI');
}
const startButton = () => screen.getByTestId('start');

describe('NewTranslationScreen (§3-2 10)', () => {
  it('pageCount null(txt): 그리드 0·글자 칸 셋·쪽 수 셈·「/ n쪽」 0·큰 쪽도 over_last 0·[번역 시작] 켜짐', async () => {
    draw();
    await pickExtract();
    expect(screen.getByTestId('file-meta').textContent).not.toContain('페이지');
    expect(document.querySelector('[data-page]')).toBeNull();
    expect(screen.queryByTestId('page-grid')).toBeNull();
    expect(document.querySelectorAll('[data-part-field]')).toHaveLength(3);
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    fireEvent.change(partField('general'), { target: { value: '4~500' } });
    expect(screen.getByTestId('range-total').textContent).toBe(
      '번역할 페이지 500개 · 파트 2개라 번역을 2번 해요(스토리 · 일반).',
    );
    expect(document.querySelector('[data-below="error"]')).toBeNull();
    await pickClientGlossary();
    fillCompany();
    expect(screen.queryByTestId('start-blocked')).toBeNull();
    expect(startButton().getAttribute('aria-disabled')).toBeNull();
  });

  it('pageCount 64: PageGrid 칸이 뜨고 65쪽은 over_last 오류', async () => {
    draw({ serverPageCount: 64 });
    await pickExtract('sample_extract.docx');
    expect(screen.getByTestId('file-meta').textContent).toContain(
      '총 64페이지',
    );
    expect(screen.getByTestId('page-grid')).toBeTruthy();
    expect(document.querySelectorAll('[data-page]').length).toBeGreaterThan(0);
    fireEvent.change(partField('general'), { target: { value: '60~65' } });
    expect(document.querySelector('[data-below="error"]')?.textContent).toBe(
      TR_TEXT.range.errors.overLast(65, 64),
    );
  });

  it('docx 의 쪽 수를 서버가 세면(밴드 TRP6 — confirm null, pages 12) 그리드가 뜨고 글자 칸 안내는 없다', async () => {
    const { server } = draw({ translationPageCount: 12 });
    await pickExtract('sample_extract.docx');
    expect(server.count('GET /translation/documents/12/pages')).toBe(1);
    expect(screen.getByTestId('file-meta').textContent).toContain(
      '총 12페이지',
    );
    expect(screen.getByTestId('page-grid')).toBeTruthy();
    expect(screen.queryByTestId('range-basis')).toBeNull();
  });

  it('pages 가 null 이면(태그 없음) 그리드 0·글자 칸 안내', async () => {
    draw({ translationPageCount: null });
    await pickExtract('sample_extract.docx');
    expect(screen.queryByTestId('page-grid')).toBeNull();
    expect(screen.getByTestId('range-basis')).toBeTruthy();
  });

  it('pages 500 이면 그리드 0, 올림은 성공(파일 칸이 뜬다)', async () => {
    const { server } = draw({ translationPageCount: 12 });
    server.override['GET /translation/documents/12/pages'] = () =>
      refusal(500, 'INTERNAL_ERROR');
    await pickExtract('sample_extract.docx');
    expect(screen.getByText('sample_extract.docx')).toBeTruthy();
    expect(screen.getByTestId('file-meta').textContent).not.toContain('페이지');
    expect(screen.queryByTestId('page-grid')).toBeNull();
    expect(screen.getByTestId('range-basis')).toBeTruthy();
  });

  it('첫 파일의 pages 가 늦게 와도 그 파일을 지우고 둘째를 올렸으면 둘째 값만 보인다(밴드 TRS2, MARC-ISSUE-385)', async () => {
    const { server } = draw();
    let releaseFirst: (response: Response) => void = () => {};
    server.override['GET /translation/documents/12/pages'] = () =>
      new Promise<Response>((resolve) => {
        releaseFirst = resolve;
      });
    server.override['GET /translation/documents/13/pages'] = () =>
      json(200, { documentId: 13, pageCount: 7 });
    await pickExtract('first_extract.docx');
    expect(server.count('GET /translation/documents/12/pages')).toBe(1);
    // 올리는 중에는 칸이 잠긴다 — 첫 파일을 지우고(올림 차례 +1) 둘째를 올린다.
    fireEvent.click(
      screen.getByLabelText('first_extract.docx', { exact: false }),
    );
    await flush();
    await pickExtract('second_extract.docx');
    expect(server.count('GET /translation/documents/13/pages')).toBe(1);
    expect(screen.getByTestId('file-meta').textContent).toContain('총 7페이지');
    releaseFirst(json(200, { documentId: 12, pageCount: 40 }));
    await flush();
    await flush();
    expect(screen.getByText('second_extract.docx')).toBeTruthy();
    expect(screen.queryByText('first_extract.docx')).toBeNull();
    expect(screen.getByTestId('file-meta').textContent).toContain('총 7페이지');
    expect(screen.getByTestId('file-meta').textContent).not.toContain('40');
    expect(document.querySelectorAll('[data-page="40"]')).toHaveLength(0);
  });

  it('고객사 용어집이 없으면 끔·회사 칸 비면 틀린 칸 셈, 파일을 올린 뒤 칸 오류가 보이고 끈 단추는 startBatch 0', async () => {
    const { server } = draw();
    await pickExtract();
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    expect(screen.getByTestId('start-blocked').textContent).toBe(
      words.blocked(4),
    );
    expect(startButton().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(startButton());
    await flush();
    expect(screen.getByText(TR_TEXT.glossary.client.missing)).toBeTruthy();
    expect(screen.getByText(words.company.nameMissing)).toBeTruthy();
    expect(server.count('POST /runs')).toBe(0);
    await pickClientGlossary();
    expect(screen.getByTestId('start-blocked').textContent).toBe(
      words.blocked(3),
    );
  });

  it('[번역 시작] → startBatch 한 번(두 번 눌러도) → onStarted(문서·묶음·시작한 파트)', async () => {
    const { server, onStarted } = draw();
    await pickExtract();
    fireEvent.change(partField('ceo'), { target: { value: '1' } });
    fireEvent.change(partField('story'), { target: { value: '2~3' } });
    await pickClientGlossary();
    fillCompany();
    fireEvent.click(startButton());
    fireEvent.click(startButton());
    await flush();
    expect(server.count('POST /runs')).toBe(2);
    expect(onStarted).toHaveBeenCalledTimes(1);
    expect(onStarted).toHaveBeenCalledWith({
      documentId: '12',
      batchKey: '00000000-0000-4000-8000-000000000000',
      started: ['ceo', 'story'],
      failed: [],
    });
    const [ceo, story] = server.runBodies() as {
      options: { ceoPageLimit: number | null; glossary: unknown };
    }[];
    expect(ceo!.options.ceoPageLimit).toBe(6);
    expect(story!.options.ceoPageLimit).toBeNull();
    expect(ceo!.options.glossary).toEqual({
      final: [
        { ko: '지어낸용어', en: 'Made-up Term' },
        { ko: '가상지표', en: 'Virtual Metric' },
      ],
    });
  });

  it('일부 파트만 시작 → onStarted 에 못 한 파트, 모두 못 함 → 이 화면에 오류 한 줄', async () => {
    const first = draw();
    first.server.override['POST /runs'] = [
      () => refusal(400, 'INVALID_OPTIONS'),
      () =>
        new Response(JSON.stringify({ id: 40, status: 'queued' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
    ];
    await pickExtract();
    fireEvent.change(partField('ceo'), { target: { value: '1' } });
    fireEvent.change(partField('story'), { target: { value: '2~3' } });
    await pickClientGlossary();
    fillCompany();
    fireEvent.click(startButton());
    await flush();
    expect(first.onStarted).toHaveBeenCalledWith(
      expect.objectContaining({ started: ['story'], failed: ['ceo'] }),
    );
    cleanup();

    const second = draw();
    second.server.override['POST /runs'] = () =>
      refusal(400, 'INVALID_OPTIONS');
    await pickExtract();
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    await pickClientGlossary();
    fillCompany();
    fireEvent.click(startButton());
    await flush();
    expect(second.onStarted).not.toHaveBeenCalled();
    expect(screen.getByTestId('start-error').textContent).toBe(
      words.startFailed,
    );
  });

  it('참고 문체가 너무 길면 보내지 않고 TR-02a 글', async () => {
    const { server } = draw();
    await pickExtract();
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    await pickClientGlossary();
    fillCompany();
    fireEvent.click(screen.getByRole('switch'));
    fireEvent.change(screen.getByLabelText(words.peer.label), {
      target: { value: 'a'.repeat(300 * 1024) },
    });
    fireEvent.click(startButton());
    await flush();
    expect(server.count('POST /runs')).toBe(0);
    expect(screen.getByTestId('start-error').textContent).toBe(words.tooLong);
  });

  it('올리지 못함 → 파일 줄 「올리지 못함」 + 안내, [번역 시작] 끔 · 받지 않는 꼴(.pdf)은 올림 0', async () => {
    const { server } = draw();
    server.override['POST /documents'] = () => refusal(500, 'INTERNAL');
    await pickExtract();
    expect(screen.getByText(words.upload.failed)).toBeTruthy();
    expect(screen.getByText(words.upload.failedHelp)).toBeTruthy();
    expect(startButton().getAttribute('aria-disabled')).toBe('true');
    cleanup();
    const other = draw();
    await pickExtract('report.pdf');
    expect(other.server.count('POST /documents')).toBe(0);
    expect(screen.getByText(/받지 않는 꼴/)).toBeTruthy();
  });

  it('용어집 거절: bad_header 는 판 글, 행 거절은 행 번호가 든 글', async () => {
    draw({
      glossaryAnswer: { ok: false, kind: 'bad_header', row: 1, message: 'x' },
    });
    await pickClientGlossary();
    expect(screen.getByText(words.glossaryRejected.bad_header)).toBeTruthy();
    cleanup();
    draw({
      glossaryAnswer: { ok: false, kind: 'not_text', row: 12, message: 'x' },
    });
    await pickClientGlossary();
    const notText = words.glossaryRejected.not_text(12);
    expect(notText).toContain('12행');
    expect(screen.getByText(notText)).toBeTruthy();
    expect(screen.queryByText(words.glossaryRejected.notXlsx)).toBeNull();
  });

  // [TRW11] 거절 종류마다 제 글 — 빈 템플릿(no_rows)이 「xlsx 만 받아요」로 뭉개지던 것(sid:MARC-ISSUE-530).
  it('용어집 거절(고객사 칸): no_rows 는 「용어가 없어요」, 서버 message 는 싣지 않음, 파일 칸 비움 · [번역 시작] 막힘', async () => {
    draw({
      glossaryAnswer: {
        ok: false,
        kind: 'no_rows',
        row: null,
        message: '서버가 지은 글',
      },
    });
    await pickExtract();
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    fillCompany();
    await pickClientGlossary();
    const field = screen.getByTestId('glossary-client');
    expect(
      within(field).getByText(words.glossaryRejected.no_rows),
    ).toBeTruthy();
    expect(words.glossaryRejected.no_rows).toContain('용어가 없어요');
    expect(screen.queryByText('서버가 지은 글')).toBeNull();
    expect(screen.queryByText(words.glossaryRejected.notXlsx)).toBeNull();
    expect(within(field).queryByText('glossary.xlsx')).toBeNull();
    expect(startButton().getAttribute('aria-disabled')).toBe('true');
  });

  it('용어집 거절(평가 칸): 같은 글 함수 — no_rows · 행 거절(duplicate_ko 7행) · 형식 오류(not_xlsx)', async () => {
    const pickEvaluation = async () => {
      fireEvent.change(fileInput(screen.getByTestId('glossary-evaluation')), {
        target: { files: [new File([XLSX], 'evaluation.xlsx')] },
      });
      await flush();
    };
    const cases = [
      [{ kind: 'no_rows', row: null }, words.glossaryRejected.no_rows],
      [
        { kind: 'duplicate_ko', row: 7 },
        words.glossaryRejected.duplicate_ko(7),
      ],
      [{ kind: 'not_xlsx', row: null }, words.glossaryRejected.notXlsx],
    ] as const;
    for (const [answer, text] of cases) {
      draw({ glossaryAnswer: { ok: false, ...answer, message: 'x' } });
      await pickEvaluation();
      const field = screen.getByTestId('glossary-evaluation');
      expect(within(field).getByText(text)).toBeTruthy();
      cleanup();
    }
    expect(words.glossaryRejected.duplicate_ko(7)).toContain('7행');
  });

  it('용어집 거절 too_many_rows: 행이 있으면 500줄 글, null 이면 훑는 행 글', async () => {
    draw({
      glossaryAnswer: {
        ok: false,
        kind: 'too_many_rows',
        row: 502,
        message: 'x',
      },
    });
    await pickClientGlossary();
    expect(screen.getByText(words.glossaryRejected.too_many_rows)).toBeTruthy();
    cleanup();
    draw({
      glossaryAnswer: {
        ok: false,
        kind: 'too_many_rows',
        row: null,
        message: 'x',
      },
    });
    await pickClientGlossary();
    expect(
      screen.getByText(words.glossaryRejected.too_many_scanned_rows),
    ).toBeTruthy();
  });
});

// [TRP2 TE7·TE8] 차례와 양식 줄 꼴(시안 TR-02 .e-formrows). 클래스로 단언한다(jsdom 은 tailwind 를 계산하지 못함).
describe('NewTranslationScreen 양식 줄(TRP2 TE7·TE8)', () => {
  const before = (a: Element, b: Element) =>
    expect(
      a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  const classesOf = (element: Element) => element.className.split(/\s+/);

  it('쪽 범위 카드 차례: 칩 줄 → 쪽 칸 → 범례 → 글자 칸, 범례는 쪽 칸 상자 밖', async () => {
    draw({ serverPageCount: 64 });
    await pickExtract('sample_extract.docx');
    const card = document.querySelector('[data-card="parts"]')!;
    const chips = card.querySelector('[role="radiogroup"]')!;
    const grid = screen.getByTestId('page-grid');
    const legend = screen.getByText(TR_TEXT.grid.legendOverlap);
    before(chips, grid);
    before(grid, legend);
    before(legend, partField('ceo'));
    expect(grid.contains(legend)).toBe(false);
    // 밴드 WT1(0f 답, sid:MARC-TICK-223): 범위 카드 머리 lead 줄 지움 — 범례는 그대로.
    expect(card.textContent).not.toMatch(/둘은 서로 맞춰져요|끌어서 칠하거나/);
  });

  it('쪽 수를 모르면 쪽 칸·범례 둘 다 없음', async () => {
    draw();
    await pickExtract();
    expect(screen.queryByTestId('page-grid')).toBeNull();
    expect(screen.queryByText(TR_TEXT.grid.legendOverlap)).toBeNull();
  });

  it('글자 칸 셋은 양식 줄(이름 칸 160 · htmlFor 짝 · Input 폭 180 · 아래 한 줄)', async () => {
    draw();
    await pickExtract();
    for (const part of ['ceo', 'story', 'general']) {
      const input = partField(part);
      const label = document.querySelector(`label[for="${input.id}"]`)!;
      expect(classesOf(label)).toEqual(
        expect.arrayContaining(['w-40', 'bg-support-grey-subtle']),
      );
      expect(classesOf(input)).toContain('w-[180px]');
      expect(classesOf(label.parentElement!)).toContain('min-h-16');
      expect(
        input.parentElement!.contains(
          document.getElementById(input.getAttribute('aria-describedby')!),
        ),
      ).toBe(true);
    }
  });

  it('용어집 둘·회사 칸은 양식 줄 · 회사 이름은 이름 칸 label(htmlFor) · 용어집 [바꾸기]·[양식 내려받기] 한 줄', async () => {
    draw();
    await pickExtract();
    await pickClientGlossary();
    for (const id of ['glossary-evaluation', 'glossary-client'])
      expect(classesOf(screen.getByTestId(id))).toContain('min-h-16');
    const client = screen.getByTestId('glossary-client');
    const replace = within(client).getByRole('button', {
      name: TR_TEXT.glossary.replace,
    });
    const template = within(client).getByTestId('glossary-client-template');
    expect(replace.parentElement!.contains(template)).toBe(true);
    const name = screen.getByLabelText(words.company.name, { exact: false });
    const label = document.querySelector(`label[for="${name.id}"]`)!;
    expect(classesOf(label)).toContain('w-40');
  });

  it('참고 문체: 켜면 [예시 양식 넣기]가 스위치와 같은 줄', async () => {
    draw();
    const toggle = screen.getByRole('switch', { name: words.peer.toggle });
    if (toggle.getAttribute('aria-checked') !== 'true') fireEvent.click(toggle);
    const fill = screen.getByRole('button', { name: words.peer.fillExample });
    expect(fill.parentElement!.contains(toggle)).toBe(true);
  });
});

// [TRP2 ②] 새 번역 화면 꼴: TC1 글 400 12 · TC7 칩 · TC8 합 줄 상자 · TC9 라디오·스위치 · TC10 글 상자 · TC11 시작 전 확인 · TC12 단추 · TC13 틀린 칸 글·경고 아이콘 · TE9 쪽 범위 오류 상자.
describe('NewTranslationScreen 꼴(TRP2 ②)', () => {
  const classesOf = (element: Element) => element.className.split(/\s+/);
  const has = (element: Element, ...names: string[]) =>
    expect(classesOf(element)).toEqual(expect.arrayContaining(names));

  it('TC7 칩: 안 고른 것 테두리 tertiary · 좌우 14 · 점 10 · 쪽 수 400', async () => {
    draw();
    await pickExtract();
    const chips = [...document.querySelectorAll('[data-part-key]')];
    const off = chips.find((c) => c.getAttribute('aria-checked') === 'false')!;
    has(off, 'border-border-tertiary', 'px-3.5');
    expect(classesOf(off)).not.toContain('px-4');
    has(off.querySelector('span[aria-hidden]')!, 'size-2.5');
    has(off.lastElementChild!, 'font-normal');
  });

  it('TC8 합 줄은 기본 톤 PageInfo · TC1 칸 아래 글 caption-03 · TE9 쪽 범위 오류면 error 상자', async () => {
    draw({ serverPageCount: 64 });
    await pickExtract('sample_extract.docx');
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    const total = screen.getByTestId('range-total');
    expect(total.getAttribute('data-tone')).toBe('default');
    has(
      total.querySelector('span:not([aria-hidden])')!,
      'text-style-pre-body-06',
      'text-text-tertiary',
    );
    has(document.querySelector('[data-below]')!, 'text-style-pre-caption-03');
    expect(screen.queryByTestId('range-error-help')).toBeNull();
    fireEvent.change(partField('general'), { target: { value: '60~65' } });
    const help = screen.getByTestId('range-error-help');
    expect(help.getAttribute('data-tone')).toBe('error');
    expect(help.textContent).toBe(TR_TEXT.range.errors.overLastHelp);
    // TC13: 오류 글 앞 경고 아이콘
    expect(document.querySelector('[data-below="error"] svg')).not.toBeNull();
  });

  it('TC9 라디오 16·고른 것 5px · 글 body-06 · 스위치 w-9 · TC10 사업 분야·공시 기준은 글 상자 96, 참고 문체 rows 6', () => {
    draw();
    const radio = document.querySelector('input[type="radio"]')!;
    has(
      radio,
      'size-4',
      'appearance-none',
      'checked:border-[5px]',
      'checked:border-border-primary',
    );
    has(radio.closest('label')!, 'text-style-pre-body-06');
    const subject = screen.getByLabelText(words.company.subject, {
      exact: false,
    });
    expect(subject.tagName).toBe('TEXTAREA');
    has(subject, 'h-24', 'px-4', 'py-3');
    expect(
      screen.getByLabelText(words.company.standards, { exact: false }).tagName,
    ).toBe('TEXTAREA');
    expect(
      screen.getByLabelText(words.company.name, { exact: false }).tagName,
    ).toBe('INPUT');
    const toggle = screen.getByRole('switch', { name: words.peer.toggle });
    has(toggle, 'w-9');
    if (toggle.getAttribute('aria-checked') !== 'true') fireEvent.click(toggle);
    const peer = screen.getByRole('textbox', { name: words.peer.label });
    expect(peer.getAttribute('rows')).toBe('6');
    has(peer, 'h-40');
    // 밴드 WT1(0f 답): 참고 문체 help 는 「용어집이 이 글보다 먼저예요」 한 마디만.
    expect(screen.getByText(words.peer.help).textContent).toBe(
      '용어집이 이 글보다 먼저예요',
    );
    expect(screen.queryByText(/길어도 돼요|끄면 이 칸이 숨어요/)).toBeNull();
  });

  it('TC12 [취소]·[번역 시작] 36 알약 · TC13 「틀린 칸 n곳」 tertiary · TC11 시작 전 확인 머리 heading-02·양식 줄', async () => {
    draw();
    await pickExtract();
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    for (const button of [
      screen.getByRole('button', { name: words.cancel }),
      startButton(),
    ])
      has(button, 'h-9', 'rounded-full');
    has(
      screen.getByTestId('start-blocked'),
      'text-text-tertiary',
      'text-style-pre-caption-03',
    );
    const preflight = screen.getByTestId('preflight');
    has(preflight.querySelector('h3')!, 'text-style-pre-heading-02');
    has(preflight.querySelector('dt')!, 'w-40', 'bg-support-grey-subtle');
    has(preflight.querySelector('dd span')!, 'text-style-pre-body-03');
  });
});

// 밴드 TRP3 ② TE8(디자인 6c 재대조): 회사 영문명 칸은 값 칸의 절반(시안 width 50% — 1440 에서 500). 다른 칸은 그대로.
describe('NewTranslationScreen 회사 영문명 칸 · TRP3 ②', () => {
  it('회사 영문명 Input 은 w-1/2, 사업 분야 칸에는 없음', async () => {
    draw();
    await pickExtract();
    const name = screen.getByLabelText(TR_TEXT.newTranslation.company.name);
    expect(name.className.split(/\s+/)).toContain('w-1/2');
    const subject = screen.getByLabelText(
      TR_TEXT.newTranslation.company.subject,
    );
    expect(subject.className.split(/\s+/)).not.toContain('w-1/2');
  });
});

// 밴드 TRW6 ② S2: TR-P02(input="pdf") — .pdf 하나 → uploadPdf(pages 0) · 제목·파일 칸·범위 안내 둘·PDF 기준 글 ·
//   pageCount 정수면 그리드, null 이면 글자 칸 · hasText false 면 안내 한 줄(시작은 막지 않음) · 「머리글 · 꼬리말」·회색 줄 ·
//   [번역 시작] 본문 flowId. 워드 꼴(기본)에는 PDF 글·flowId 0.
const pdfWords = TR_TEXT.pdfNew;
const PDF = new TextEncoder().encode('%PDF-1.4\n%made-up\n');

function drawPdf(options: Parameters<typeof fakeTranslationServer>[0] = {}) {
  const server = fakeTranslationServer(options);
  const store = serverStoreOf(server, {
    newKey: (() => {
      let n = 0;
      return () => `0000000${n++}-0000-4000-8000-000000000000`;
    })(),
  });
  const onStarted = vi.fn();
  render(
    <NewTranslationScreen
      store={store}
      input="pdf"
      now={() => new Date(2026, 9, 29)}
      onStarted={onStarted}
      onCancel={vi.fn()}
    />,
  );
  return { server, onStarted };
}
async function pickPdf(name = 'made_up_report.pdf') {
  const card = document.querySelector('[data-card="file"]')!;
  fireEvent.change(fileInput(card), {
    target: { files: [new File([PDF], name, { type: 'application/pdf' })] },
  });
  await flush();
}
const bodyText = () => document.body.textContent ?? '';

describe('NewTranslationScreen input="pdf" (TRW6 ② S2)', () => {
  it('받는 꼴 .pdf · 제목·파일 칸 글·범위 안내 둘이 파일 전에 보인다', () => {
    drawPdf();
    const card = document.querySelector('[data-card="file"]')!;
    expect(fileInput(card).getAttribute('accept')).toContain('.pdf');
    expect(fileInput(card).getAttribute('accept')).not.toContain('.docx');
    expect(screen.getByRole('heading', { name: pdfWords.title })).toBeTruthy();
    expect(card.textContent).toContain(pdfWords.upload.guide);
    expect(card.textContent).toContain(pdfWords.upload.formats);
    expect(card.textContent).toContain(pdfWords.upload.note);
    expect(screen.getByTestId('pdf-range-guide').textContent).toBe(
      pdfWords.range.limit + pdfWords.range.basis,
    );
    // 추출본 글([PAGE n]·원본 PDF 는 아직)은 0.
    expect(bodyText()).not.toContain('[PAGE n]');
    expect(bodyText()).not.toContain(words.upload.note);
    expect(bodyText()).toContain(pdfWords.range.help);
    expect(bodyText()).toContain(pdfWords.retryNote);
  });

  it('uploadPdf: confirm 의 pageCount 64 → 그리드, pages 경로 0 · hasText true 면 안내 줄 0', async () => {
    const { server } = drawPdf({ serverPageCount: 64, serverHasText: true });
    await pickPdf();
    expect(server.count('GET /translation/documents/12/pages')).toBe(0);
    expect(screen.getByTestId('file-meta').textContent).toContain(
      '총 64페이지',
    );
    expect(screen.getByTestId('page-grid')).toBeTruthy();
    expect(screen.queryByTestId('range-basis')).toBeNull();
    expect(screen.queryByTestId('pdf-no-text')).toBeNull();
    fireEvent.change(partField('general'), { target: { value: '60~65' } });
    expect(screen.getByTestId('range-error-help').textContent).toBe(
      pdfWords.range.overLastHelp,
    );
  });

  it('pageCount null → 그리드 0·글자 칸 아래 PDF 기준 글 · hasText false → 안내 한 줄, 시작은 막지 않음', async () => {
    const { server } = drawPdf({
      serverPageCount: null,
      serverHasText: false,
      translationPageCount: 9,
    });
    await pickPdf('scan.pdf');
    expect(server.count('GET /translation/documents/12/pages')).toBe(0);
    expect(screen.queryByTestId('page-grid')).toBeNull();
    expect(screen.getByTestId('range-basis').textContent).toBe(
      pdfWords.range.basis,
    );
    expect(screen.getByTestId('pdf-no-text').textContent).toBe(
      pdfWords.upload.noText,
    );
    fireEvent.change(partField('story'), { target: { value: '1~3' } });
    await pickClientGlossary();
    fillCompany();
    expect(screen.queryByTestId('start-blocked')).toBeNull();
    expect(startButton().getAttribute('aria-disabled')).toBeNull();
  });

  it('시작 전 확인에 「머리글 · 꼬리말」 줄 · [번역 시작] → POST /runs 본문 flowId translation.pdf@158', async () => {
    const { server, onStarted } = drawPdf({
      serverPageCount: 3,
      serverHasText: true,
    });
    await pickPdf();
    fireEvent.change(partField('general'), { target: { value: '1~3' } });
    await pickClientGlossary();
    fillCompany();
    const preflight = screen.getByTestId('preflight');
    expect(preflight.textContent).toContain(pdfWords.preflight.headerFooter);
    expect(preflight.textContent).toContain(
      pdfWords.preflight.headerFooterValue,
    );
    fireEvent.click(startButton());
    await flush();
    expect(server.count('POST /runs')).toBe(1);
    const [body] = server.runBodies() as { flowId?: string }[];
    expect(body!.flowId).toBe('translation.pdf@158');
    expect(onStarted).toHaveBeenCalledTimes(1);
  });
});

describe('NewTranslationScreen 워드 꼴 — PDF 갈래 0 (TRW6 ②)', () => {
  it('PDF 글·안내 줄·「머리글 · 꼬리말」 0, 본문에 flowId 키 없음', async () => {
    const { server } = draw({ serverPageCount: 3 });
    await pickExtract('sample_extract.docx');
    expect(screen.queryByTestId('pdf-range-guide')).toBeNull();
    expect(screen.queryByTestId('pdf-no-text')).toBeNull();
    expect(bodyText()).not.toContain(pdfWords.retryNote);
    expect(bodyText()).toContain(TR_TEXT.range.help);
    fireEvent.change(partField('general'), { target: { value: '1~3' } });
    await pickClientGlossary();
    fillCompany();
    expect(screen.getByTestId('preflight').textContent).not.toContain(
      pdfWords.preflight.headerFooter,
    );
    fireEvent.click(startButton());
    await flush();
    const [body] = server.runBodies() as Record<string, unknown>[];
    expect('flowId' in body!).toBe(false);
  });
});

// 밴드 TRW9: PDF 꼴 + openPdf → 쪽 칸 썸네일 · 파일 지움 → 그리드 0·url 닫음 · 워드 꼴은 openPdf 를 받아도 안 씀 · 안 주면 칸 그대로.
describe('NewTranslationScreen 쪽 칸 썸네일 (TRW9)', () => {
  const original = {
    create: URL.createObjectURL,
    revoke: URL.revokeObjectURL,
  };
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:made-up');
    URL.revokeObjectURL = vi.fn();
  });
  afterEach(() => {
    URL.createObjectURL = original.create;
    URL.revokeObjectURL = original.revoke;
  });

  function drawWith(input: 'word' | 'pdf', withOpen = true) {
    const openPdf = vi.fn<OpenPdf>(async () => ({
      renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
      close() {},
    }));
    const store = serverStoreOf(fakeTranslationServer({ serverPageCount: 3 }), {
      newKey: () => '00000000-0000-4000-8000-000000000000',
    });
    render(
      <NewTranslationScreen
        store={store}
        input={input}
        {...(withOpen ? { openPdf } : {})}
        now={() => new Date(2026, 9, 29)}
        onStarted={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    return { openPdf };
  }
  const canvases = () => document.querySelectorAll('canvas');

  it('PDF 꼴 + openPdf: 올림 끝 → 한 번 열어 칸마다 그림 · 파일 지움 → 그리드 0·url 닫음', async () => {
    const { openPdf } = drawWith('pdf');
    expect(openPdf).not.toHaveBeenCalled();
    await pickPdf();
    await flush();
    expect(openPdf).toHaveBeenCalledTimes(1);
    expect(canvases()).toHaveLength(3);
    fireEvent.click(
      screen.getByRole('button', { name: /^made_up_report\.pdf / }),
    );
    await flush();
    expect(screen.queryByTestId('page-grid')).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:made-up');
  });

  it('워드 꼴 + openPdf: 열기 0 · 캔버스 0 · data-pdf-state 없음', async () => {
    const { openPdf } = drawWith('word');
    await pickExtract();
    await flush();
    expect(screen.getByTestId('page-grid')).toBeTruthy();
    expect(openPdf).not.toHaveBeenCalled();
    expect(canvases()).toHaveLength(0);
    expect(screen.getByTestId('page-grid').hasAttribute('data-pdf-state')).toBe(
      false,
    );
  });

  it('PDF 꼴 + openPdf 안 줌: 칸은 그대로 · 캔버스 0', async () => {
    drawWith('pdf', false);
    await pickPdf();
    expect(document.querySelectorAll('[data-page]')).toHaveLength(3);
    expect(canvases()).toHaveLength(0);
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
